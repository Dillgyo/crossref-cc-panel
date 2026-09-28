"""
Crossref Public Data File 추출 스크립트 (2023~2026 공통)

사용법
  python crossref_extract.py <tar 경로> <스냅숏 이름> <출력 폴더> [--limit N] [--workers N]

예시 (시험: 앞쪽 300개 파일만)
  python crossref_extract.py D:\\crossref\\April_2023_Public_Data_File_from_Crossref.tar 2023test D:\\crossref\\parquet --limit 300

결과
  <출력 폴더>\\<스냅숏 이름>\\works\\part-00000.parquet ...    논문 1건당 1행
  <출력 폴더>\\<스냅숏 이름>\\licenses\\part-00000.parquet ... 논문 x 라이선스당 1행
  <출력 폴더>\\extract_<스냅숏 이름>.log                      진행 기록

거르는 기준: journal-article, ISSN 있음, 출판연도 2000년 이상
파일 형식: .json.gz(items 배열, 2023·2024)와 .jsonl.gz(한 줄 1건, 2025·2026) 모두 처리
"""
import argparse
import gzip
import os
import sys
import tarfile
import time
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

import pyarrow as pa
import pyarrow.parquet as pq

try:
    import orjson
    loads = orjson.loads
    JSON_LIB = "orjson"
except ImportError:
    import json
    loads = json.loads
    JSON_LIB = "json"

MIN_YEAR = 2000
FLUSH_ROWS = 2_000_000

WORK_SCHEMA = pa.schema([
    ("doi", pa.string()),
    ("member", pa.string()),
    ("publisher", pa.string()),
    ("issn", pa.string()),
    ("container_title", pa.string()),
    ("title", pa.string()),
    ("pub_year", pa.int32()),
    ("issued", pa.string()),
    ("published", pa.string()),
    ("published_print", pa.string()),
    ("published_online", pa.string()),
    ("created", pa.string()),
    ("deposited", pa.string()),
    ("volume", pa.string()),
    ("issue", pa.string()),
    ("n_license", pa.int32()),
    ("snapshot", pa.string()),
])

LIC_SCHEMA = pa.schema([
    ("doi", pa.string()),
    ("url", pa.string()),
    ("content_version", pa.string()),
    ("start", pa.string()),
    ("delay_in_days", pa.int64()),
    ("snapshot", pa.string()),
])


# ------------------------------------------------------------
# 값 정리
# ------------------------------------------------------------
def date_parts(d):
    """{"date-parts": [[2020, 3, 15]]} -> "2020-03-15" (없으면 None)"""
    if not isinstance(d, dict):
        return None
    try:
        p = d.get("date-parts")[0]
        out = []
        for i, x in enumerate(p):
            if x is None:
                break
            out.append(f"{int(x):04d}" if i == 0 else f"{int(x):02d}")
        return "-".join(out) or None
    except (TypeError, IndexError, ValueError):
        return None


def date_time(d):
    """created·deposited·license start용: date-time 우선, 없으면 date-parts"""
    if not isinstance(d, dict):
        return None
    return d.get("date-time") or date_parts(d)


def first(v):
    if isinstance(v, list):
        return str(v[0]) if v else None
    return None if v is None else str(v)


def year_of(r):
    for k in ("issued", "published", "published-print", "published-online"):
        s = date_parts(r.get(k))
        if s:
            try:
                return int(s[:4])
            except ValueError:
                pass
    return None


def to_int(v):
    try:
        return None if v is None else int(v)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------
# 파일 하나 처리 (작업 프로세스에서 실행)
# ------------------------------------------------------------
def iter_records(name, raw):
    data = gzip.decompress(raw)
    if name.endswith(".jsonl.gz"):
        for line in data.splitlines():
            if line.strip():
                yield loads(line)
    else:
        obj = loads(data)
        for r in obj.get("items", []):
            yield r


def process(name, raw, snap):
    W = {f.name: [] for f in WORK_SCHEMA}
    L = {f.name: [] for f in LIC_SCHEMA}
    seen = kept = 0

    for r in iter_records(name, raw):
        seen += 1
        if r.get("type") != "journal-article":
            continue
        issn = r.get("ISSN") or []
        if not issn:
            continue
        y = year_of(r)
        if y is None or y < MIN_YEAR:
            continue
        doi = (r.get("DOI") or "").strip().lower()
        if not doi:
            continue

        lic = r.get("license") or []
        kept += 1
        member = r.get("member")

        W["doi"].append(doi)
        W["member"].append(None if member is None else str(member))
        W["publisher"].append(r.get("publisher"))
        W["issn"].append(";".join(sorted({str(s).strip().upper() for s in issn})))
        W["container_title"].append(first(r.get("container-title")))
        W["title"].append(first(r.get("title")))
        W["pub_year"].append(y)
        W["issued"].append(date_parts(r.get("issued")))
        W["published"].append(date_parts(r.get("published")))
        W["published_print"].append(date_parts(r.get("published-print")))
        W["published_online"].append(date_parts(r.get("published-online")))
        W["created"].append(date_time(r.get("created")))
        W["deposited"].append(date_time(r.get("deposited")))
        W["volume"].append(r.get("volume"))
        W["issue"].append(r.get("issue"))
        W["n_license"].append(len(lic))
        W["snapshot"].append(snap)

        for l in lic:
            if not isinstance(l, dict):
                continue
            L["doi"].append(doi)
            L["url"].append(l.get("URL"))
            L["content_version"].append(l.get("content-version"))
            L["start"].append(date_time(l.get("start")))
            L["delay_in_days"].append(to_int(l.get("delay-in-days")))
            L["snapshot"].append(snap)

    return (seen, kept,
            pa.Table.from_pydict(W, schema=WORK_SCHEMA),
            pa.Table.from_pydict(L, schema=LIC_SCHEMA))


# ------------------------------------------------------------
# 저장
# ------------------------------------------------------------
class Sink:
    def __init__(self, folder):
        os.makedirs(folder, exist_ok=True)
        self.folder = folder
        self.buf, self.rows, self.part, self.total = [], 0, 0, 0

    def add(self, t):
        if t.num_rows == 0:
            return
        self.buf.append(t)
        self.rows += t.num_rows
        if self.rows >= FLUSH_ROWS:
            self.flush()

    def flush(self):
        if not self.buf:
            return
        t = pa.concat_tables(self.buf)
        pq.write_table(t, os.path.join(self.folder, f"part-{self.part:05d}.parquet"),
                       compression="zstd")
        self.part += 1
        self.total += t.num_rows
        self.buf, self.rows = [], 0


# ------------------------------------------------------------
# tar 순차 읽기 (압축 해제 없이 스트리밍)
# ------------------------------------------------------------
def members(tar_path, limit):
    n = 0
    with tarfile.open(tar_path, mode="r|") as tar:
        for m in tar:
            if not m.isfile():
                continue
            if not (m.name.endswith(".json.gz") or m.name.endswith(".jsonl.gz")):
                continue
            raw = tar.extractfile(m).read()
            yield m.name, raw, m.offset_data + m.size
            n += 1
            if limit and n >= limit:
                return


def fmt(sec):
    sec = int(sec)
    return f"{sec // 3600}시간 {sec % 3600 // 60:02d}분"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tar_path")
    ap.add_argument("snapshot")
    ap.add_argument("out_root")
    ap.add_argument("--limit", type=int, default=0, help="앞쪽 N개 파일만 처리(시험용)")
    ap.add_argument("--workers", type=int,
                    default=max(1, min(6, (os.cpu_count() or 2) - 2)))
    a = ap.parse_args()

    out_dir = os.path.join(a.out_root, a.snapshot)
    if os.path.isdir(out_dir) and os.listdir(out_dir):
        print(f"[중단] 출력 폴더가 비어 있지 않습니다: {out_dir}")
        print("       이전 결과를 지우거나 다른 스냅숏 이름을 쓰세요.")
        sys.exit(1)

    os.makedirs(a.out_root, exist_ok=True)
    log_path = os.path.join(a.out_root, f"extract_{a.snapshot}.log")
    logf = open(log_path, "a", encoding="utf-8")

    def log(msg):
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    total_size = os.path.getsize(a.tar_path)
    works = Sink(os.path.join(out_dir, "works"))
    lics = Sink(os.path.join(out_dir, "licenses"))

    log(f"시작: {a.tar_path}")
    log(f"스냅숏={a.snapshot}, 작업 프로세스={a.workers}, JSON={JSON_LIB}, limit={a.limit or '없음'}")

    t0 = time.time()
    last_report = t0
    files = seen = kept = 0
    offset = 0

    def handle(fut):
        nonlocal files, seen, kept
        s, k, wt, lt = fut.result()
        files += 1
        seen += s
        kept += k
        works.add(wt)
        lics.add(lt)

    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        pending = set()
        for name, raw, offset in members(a.tar_path, a.limit):
            pending.add(ex.submit(process, name, raw, a.snapshot))
            if len(pending) >= a.workers * 2:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for f in done:
                    handle(f)

            now = time.time()
            if now - last_report >= 60:
                last_report = now
                el = now - t0
                pct = offset / total_size
                eta = el / pct * (1 - pct) if pct > 0 else 0
                log(f"진행 {pct:6.2%} | 파일 {files:,} | 레코드 {seen:,} | 추출 {kept:,} "
                    f"| 경과 {fmt(el)} | 전체 완료까지 약 {fmt(eta)}")

        for f in pending:
            handle(f)

    works.flush()
    lics.flush()

    el = time.time() - t0
    pct = offset / total_size if total_size else 0
    log("완료")
    log(f"  처리 파일 {files:,}개 (tar 기준 {pct:.2%} 지점까지)")
    log(f"  전체 레코드 {seen:,}건 중 추출 {kept:,}건")
    log(f"  라이선스 행 {lics.total:,}개")
    log(f"  소요 {fmt(el)}")
    if a.limit and pct > 0:
        log(f"  이 속도라면 tar 전체 처리에 약 {fmt(el / pct)} 예상")
    logf.close()


if __name__ == "__main__":
    main()
