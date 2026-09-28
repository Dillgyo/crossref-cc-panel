import gzip, json, os, re, sys, csv, tarfile, time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

YEAR = sys.argv[1]
TARS = {"2024": r"D:\crossref\April_2024_Public_Data_File_from_Crossref.tar",
        "2025": r"D:\crossref\April_2025_Public_Data_File_from_Crossref.tar",
        "2026": r"D:\crossref\March_2026_Public_Data_File_from_Crossref.tar"}
TAR = TARS[YEAR]
OUT = rf"D:\crossref\raw_trace_{YEAR}.csv"
COL = {"2024": "in24", "2025": "in25", "2026": "in26"}[YEAR]
DOIRE = re.compile(rb'"DOI"\s*:\s*"([^"]+)"')
TGT = None

def init(t):
    global TGT
    TGT = t

def year_of(r):
    for k in ("issued", "published", "published-print", "published-online"):
        dp = (r.get(k) or {}).get("date-parts")
        if dp and dp[0] and dp[0][0]:
            return dp[0][0]
    return None

def scan(name, raw):
    data = gzip.decompress(raw)
    recs = []
    if name.endswith(".jsonl.gz"):
        for ln in data.splitlines():
            m = DOIRE.search(ln)
            if m and m.group(1).decode("utf-8", "ignore").lower() in TGT:
                recs.append(json.loads(ln))
    else:
        for r in json.loads(data).get("items", []):
            if (r.get("DOI") or "").lower() in TGT:
                recs.append(r)
    return [[(r.get("DOI") or "").lower(), r.get("type"), ";".join(r.get("ISSN") or []),
             year_of(r), r.get("member")] for r in recs]

def members(p):
    with tarfile.open(p, mode="r|") as tar:
        for m in tar:
            if m.isfile() and m.name.endswith((".json.gz", ".jsonl.gz")):
                yield m.name, tar.extractfile(m).read(), m.offset_data + m.size

if __name__ == "__main__":
    tg = {}
    with open(r"D:\crossref\trace_targets.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r[COL] == "0":
                tg[r["doi"].lower()] = (r["issn"] or "", r["pub_year"])
    print(f"{YEAR}년판 추적 대상 {len(tg):,}건", flush=True)

    total = os.path.getsize(TAR); t0 = time.time(); last = t0; found = []
    with ProcessPoolExecutor(max_workers=6, initializer=init, initargs=(set(tg),)) as ex:
        pend = set()
        for name, raw, off in members(TAR):
            pend.add(ex.submit(scan, name, raw))
            if len(pend) >= 12:
                done, pend = wait(pend, return_when=FIRST_COMPLETED)
                for x in done: found += x.result()
            if time.time() - last > 60:
                last = time.time(); pct = off / total
                print(f"  {pct:.1%} | 찾음 {len(found):,} | 남은 약 {(time.time()-t0)/pct*(1-pct)/60:.0f}분", flush=True)
        for x in pend: found += x.result()

    fmap = {r[0]: r for r in found}
    c = Counter()
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["doi", "원인", "type", "ISSN", "출판연도", "member", "2023_ISSN", "2023_출판연도"])
        for d, (i23, y23) in tg.items():
            r = fmap.get(d)
            if r is None:                   why = "원본 파일에 없음"
            elif r[1] != "journal-article": why = "유형 변경"
            elif not r[2]:                  why = "ISSN 없음"
            elif r[3] is None or r[3] < 2000: why = "출판연도 이탈"
            else:                           why = "조건 충족 (추출 누락 의심)"
            c[why] += 1
            w.writerow([d, why] + (r[1:] if r else ["", "", "", ""]) + [i23, y23])
    print(f"\n[{YEAR}년판] 대상 {len(tg):,}건 원인별")
    for k, v in c.most_common(): print(f"  {k}: {v:,}")
    print(f"저장: {OUT}  ({(time.time()-t0)/60:.0f}분)")
