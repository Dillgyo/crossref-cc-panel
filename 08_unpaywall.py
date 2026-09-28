"""
표 S6과 5.4절의 Unpaywall 대조 수치를 재계산한다.

실행
  python 08_unpaywall.py

입력
  D:/crossref/external_check.csv       미기재 표본 500건의 Unpaywall 응답
  D:/crossref/external_positive.csv    기재 표본 500건
  D:/crossref/unpaywall_requery.jsonl  재조회 원본 (없으면 해당 절만 건너뛴다)
  D:/crossref/doaj_panel_journals.csv  저널 라이선스
  D:/crossref/parquet/2023/works       DOI를 저널에 연결

이 셋은 외부 API 조회 결과이므로 다시 조회하면 같은 값이 나오지 않는다.
저장소에 그대로 포함해야 재현된다.
"""
import json
import os
from collections import Counter

import duckdb

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
P = os.environ.get("CROSSREF_PARQUET", f"{ROOT}/parquet")
DOAJ = os.environ.get("CROSSREF_DOAJ", f"{ROOT}/doaj_panel_journals.csv")
NEG = os.environ.get("CROSSREF_EXT_NEG", f"{ROOT}/external_check.csv")
POS = os.environ.get("CROSSREF_EXT_POS", f"{ROOT}/external_positive.csv")
RQ = os.environ.get("CROSSREF_REQUERY", f"{ROOT}/unpaywall_requery.jsonl")
OUT = os.environ.get("CROSSREF_S6_OUT", f"{ROOT}/unpaywall_out.txt")
TMP = os.environ.get("CROSSREF_TMP", f"{ROOT}/_tmp")
os.makedirs(TMP, exist_ok=True)

logf = open(OUT, "w", encoding="utf-8")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    logf.write(s + "\n")
    logf.flush()


con = duckdb.connect()
for q in ["SET threads=4", "SET memory_limit='6GB'",
          "SET preserve_insertion_order=false", f"SET temp_directory='{TMP}'"]:
    con.execute(q)

EXPECTED = {
    "미기재_CC": 470, "미기재_pd": 1, "미기재_없음": 29,
    "기재_CC": 497, "기재_pd": 3, "기재_없음": 0,
    "기재_같은CC": 489, "기재_다른CC": 8,
    "s62_단일일치": 348, "s62_복수일치": 76, "s62_단일불일치": 42, "s62_복수불일치": 4,
    "s62_합계": 470, "DOAJ일치": 424, "DOAJ일치율": 90.2,
    "기재_CR과DOAJ다름": 20, "기재_UP가CR": 11, "기재_UP가DOAJ": 4, "기재_UP가둘다아님": 5,
    "evidence_deprecated": 500, "저장소위치": 385, "출판사사이트": 500,
}


def pct(num, den, digits=1):
    return round(100.0 * num / den, digits) if den else 0.0


def check(key, value, digits=None):
    if key not in EXPECTED:
        return f"{value}  (기대값 없음)"
    exp = EXPECTED[key]
    v = round(value, digits) if digits is not None else value
    return f"{v}  " + ("일치" if v == exp else f"불일치 (보충자료 {exp})")


for path in (NEG, POS, DOAJ):
    if not os.path.exists(path):
        log(f"[중단] 파일이 없습니다: {path}")
        raise SystemExit(1)

con.execute(f"CREATE TABLE neg AS SELECT * FROM read_csv_auto('{NEG}', header=true, all_varchar=true)")
con.execute(f"CREATE TABLE pos AS SELECT * FROM read_csv_auto('{POS}', header=true, all_varchar=true)")
ncols = [r[0] for r in con.execute("DESCRIBE neg").fetchall()]
pcols = [r[0] for r in con.execute("DESCRIBE pos").fetchall()]
log("미기재 표본 열:", ncols)
log("기재 표본 열:  ", pcols)


def pick(cols, *cands):
    for c in cands:
        if c in cols:
            return c
    return None


NEG_LIC = pick(ncols, "license", "unpaywall_lic", "lic")
POS_UP = pick(pcols, "unpaywall_lic", "license")
POS_CR = pick(pcols, "crossref_lic", "cr_lic")
NEG_HOST = pick(ncols, "host", "host_type")
if not (NEG_LIC and POS_UP and POS_CR):
    log("[중단] 필요한 열을 찾지 못했습니다. 위 열 이름을 알려주십시오.")
    raise SystemExit(1)


def bucket(v):
    v = (v or "").strip().lower()
    if v.startswith("cc"):
        return "CC"
    if v in ("public-domain", "public domain", "pd"):
        return "PD"
    if v == "" or v in ("nan", "none", "null"):
        return "NONE"
    return "OTHER:" + v


log("\n" + "=" * 70)
log("표 S6-1. Unpaywall이 보고한 라이선스 (각 500건)")
log("=" * 70)
for lab, tbl, col, keys in (("미기재", "neg", NEG_LIC, ("미기재_CC", "미기재_pd", "미기재_없음")),
                            ("기재", "pos", POS_UP, ("기재_CC", "기재_pd", "기재_없음"))):
    rows = con.execute(f"SELECT {col} FROM {tbl}").fetchall()
    c = Counter(bucket(r[0]) for r in rows)
    n = len(rows)
    log(f"\n  {lab} 표본 {n}건")
    log(f"    CC 라이선스 보고   {check(keys[0], c['CC'])}  ({pct(c['CC'], n)}%)")
    log(f"    public-domain     {check(keys[1], c['PD'])}  ({pct(c['PD'], n)}%)")
    log(f"    라이선스 정보 없음  {check(keys[2], c['NONE'])}  ({pct(c['NONE'], n)}%)")
    for k, v in sorted(c.items()):
        if k.startswith("OTHER:"):
            log(f"    그 밖: {k[6:]}  {v}")

# 기재 표본에서 Unpaywall과 Crossref의 CC 종류 비교
rows = con.execute(f"SELECT {POS_CR}, {POS_UP} FROM pos").fetchall()
same = sum(1 for cr, up in rows if (cr or "").strip().lower() == (up or "").strip().lower())
diff_cc = sum(1 for cr, up in rows
              if (up or "").strip().lower().startswith("cc")
              and (cr or "").strip().lower() != (up or "").strip().lower())
n_cc = sum(1 for _, up in rows if (up or "").strip().lower().startswith("cc"))
log(f"\n  기재 표본에서 Unpaywall의 CC 종류가 Crossref와 같음  {check('기재_같은CC', same)}  "
    f"({pct(same, len(rows))}%)")
log(f"  다른 CC 종류  {check('기재_다른CC', diff_cc)}")
log(f"  CC를 보고한 {n_cc}건만 분모로 하면 일치율 {pct(same, n_cc)}%")

# ---------------------------------------------------------------------------
log("\n" + "=" * 70)
log("표 S6-2. 미기재 표본의 Unpaywall CC와 DOAJ 저널 라이선스")
log("=" * 70)
con.execute(f"""CREATE TABLE dl AS
SELECT upper(trim(issn)) issn, any_value(lic) lic FROM
 (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e,
         "Journal license" lic FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true)),
 UNNEST([p,e]) t(issn) WHERE issn IS NOT NULL AND trim(issn)<>'' GROUP BY 1""")
con.execute(f"""CREATE TABLE w23 AS
SELECT doi, upper(trim(t.s)) issn FROM read_parquet('{P}/2023/works/*.parquet'),
UNNEST(str_split(issn,';')) t(s)""")

pairs = con.execute(f"""
SELECT e.doi, e.{NEG_LIC} up, any_value(d.lic) dj
FROM neg e JOIN w23 w ON lower(e.doi)=w.doi JOIN dl d USING (issn)
GROUP BY 1,2""").fetchall()


def norm(x):
    return {t.strip().lower().replace(" ", "-") for t in (x or "").split(",") if t.strip()}


c = Counter()
for doi, up, dj in pairs:
    u = (up or "").strip().lower()
    if not u.startswith("cc"):
        continue
    ds = norm(dj)
    if len(ds) == 1:
        c["단일일치" if u in ds else "단일불일치"] += 1
    else:
        c["복수일치" if u in ds else "복수불일치"] += 1

tot = sum(c.values())
log(f"\n  대조된 미기재 표본 {len(pairs)}건 가운데 Unpaywall이 CC를 보고한 {tot}건")
for lab, key in (("DOAJ 단일 라이선스와 일치", "단일일치"),
                 ("DOAJ 복수 라이선스 중 하나와 일치", "복수일치"),
                 ("DOAJ 단일 라이선스와 불일치", "단일불일치"),
                 ("DOAJ 복수 라이선스 어느 것과도 불일치", "복수불일치")):
    v = c[key]
    log(f"    {lab:<34} {check('s62_' + key, v)}  ({pct(v, tot)}%)")
log(f"    {'합계':<34} {check('s62_합계', tot)}")
agree = c["단일일치"] + c["복수일치"]
log(f"\n  DOAJ 저널 라이선스와 일치 {check('DOAJ일치', agree)}  "
    f"({check('DOAJ일치율', pct(agree, tot))}%)")

# 기재 표본에서 Crossref와 DOAJ가 다른 경우
pos_pairs = con.execute(f"""
SELECT e.doi, e.{POS_CR} cr, e.{POS_UP} up, any_value(d.lic) dj
FROM pos e JOIN w23 w ON lower(e.doi)=w.doi JOIN dl d USING (issn)
GROUP BY 1,2,3""").fetchall()
c2 = Counter()
n_diff = 0
for doi, cr, up, dj in pos_pairs:
    ds = norm(dj)
    crl = (cr or "").strip().lower()
    upl = (up or "").strip().lower()
    if len(ds) != 1 or crl in ds:
        continue
    n_diff += 1
    c2["Crossref" if upl == crl else ("DOAJ" if upl in ds else "둘다아님")] += 1
log(f"\n  기재 표본에서 Crossref와 DOAJ가 다른 경우 {check('기재_CR과DOAJ다름', n_diff)}")
log(f"    Unpaywall이 Crossref와 일치   {check('기재_UP가CR', c2['Crossref'])}")
log(f"    Unpaywall이 DOAJ와 일치       {check('기재_UP가DOAJ', c2['DOAJ'])}")
log(f"    어느 쪽과도 다름              {check('기재_UP가둘다아님', c2['둘다아님'])}")

# ---------------------------------------------------------------------------
log("\n" + "=" * 70)
log("5.4절. 재조회 원본")
log("=" * 70)
if not os.path.exists(RQ):
    log(f"  건너뜀 — 파일이 없다: {RQ}")
else:
    ev = Counter()
    host = Counter()
    rep = 0
    n = 0
    for line in open(RQ, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        m = json.loads(line)
        n += 1
        b = m.get("best_oa_location") or {}
        ev[b.get("evidence") or "(evidence 없음)"] += 1
        host[b.get("host_type") or "(없음)"] += 1
        if any((l or {}).get("host_type") == "repository" for l in (m.get("oa_locations") or [])):
            rep += 1
    log(f"  재조회 {n}건")
    log("\n  best_oa_location의 evidence")
    for k, v in ev.most_common():
        mark = check("evidence_deprecated", v) if k == "deprecated" else f"{v}"
        log(f"    {k}: {mark}")
    log("\n  best_oa_location의 host_type")
    for k, v in host.most_common():
        mark = check("출판사사이트", v) if k == "publisher" else f"{v}"
        log(f"    {k}: {mark}")
    log(f"\n  저장소 위치를 하나라도 가진 DOI  {check('저장소위치', rep)}")

log(f"\n완료. 결과: {OUT}")
logf.close()
