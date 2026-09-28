"""
OA 시작연도 이상치로 제외한 224종을 복원하고, 표 S3의 '제외한 224종 포함' 행을 재계산한다.

실행
  python 09_excluded_224.py

입력
  D:/doaj_journalcsv_20260817_2320_utf8.csv   DOAJ 원본 덤프
  D:/crossref/doaj_panel_journals.csv         분석 모집단 13,806종
  D:/crossref/parquet/state_panel.parquet
  D:/crossref/parquet/{2023,2026}/{works,licenses}/*.parquet

출력
  화면과 D:/crossref/excluded224_out.txt
  D:/crossref/data/doaj_excluded_224.csv      복원한 224종 목록

복원 원리
  모집단 확정에 쓴 세 필터는 순차적이다.
    (1) CC 계열 라이선스만              23,325 → 23,149
    (2) DOAJ 등재일이 2021년 이전        23,149 → 14,030
    (3) OA 시작연도 > 등재연도인 저널 제외 14,030 → 13,806
  (1)(2)만 적용한 14,030종에서 doaj_panel_journals.csv의 13,806종을 빼면
  (3)에서 제외된 224종이 그대로 남는다. 추정이 아니라 차집합이다.
"""
import csv
import os

import duckdb

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
P = os.environ.get("CROSSREF_PARQUET", f"{ROOT}/parquet")
DOAJ = os.environ.get("CROSSREF_DOAJ", f"{ROOT}/doaj_panel_journals.csv")
DUMP = os.environ.get("CROSSREF_DOAJ_DUMP", "D:/doaj_journalcsv_20260817_2320_utf8.csv")
OUT = os.environ.get("CROSSREF_224_OUT", f"{ROOT}/excluded224_out.txt")
DATA = os.environ.get("CROSSREF_DATA", f"{ROOT}/data")
TMP = os.environ.get("CROSSREF_TMP", f"{ROOT}/_tmp")
os.makedirs(TMP, exist_ok=True)
os.makedirs(DATA, exist_ok=True)

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

CCQ = ("url ILIKE '%creativecommons.org%' "
       "AND coalesce(content_version,'') IN ('vor','am','unspecified')")

EXPECTED = {"전체": 14030, "모집단": 13806, "제외": 224,
            "확장_N": 7392143, "확장_미기재": 3008697, "확장_보완": 172838,
            "확장_보완율": 5.74, "확장_기재율23": 59.3, "확장_기재율26": 61.6}


def check(key, value, digits=None):
    if key not in EXPECTED:
        return f"{value}"
    exp = EXPECTED[key]
    v = round(value, digits) if digits is not None else value
    return (f"{v:,}" if isinstance(v, int) else f"{v}") + \
        ("  일치" if v == exp else f"  불일치 (원고 {exp})")


if not os.path.exists(DUMP):
    log(f"[중단] DOAJ 원본 덤프가 없습니다: {DUMP}")
    log("  경로가 다르면 환경 변수로 지정하십시오.")
    log('  set CROSSREF_DOAJ_DUMP=D:\\경로\\doaj_...csv')
    raise SystemExit(1)

log("=" * 72)
log("1. 224종 복원")
log("=" * 72)

con.execute(f"""CREATE TABLE dump AS SELECT * FROM
read_csv_auto('{DUMP}', header=true, all_varchar=true)""")
cols = [r[0] for r in con.execute("DESCRIBE dump").fetchall()]
log(f"  덤프 열 {len(cols)}개")


def find(label, exact, contains_all=(), contains_any=()):
    """열 이름이 판본마다 다르므로 정확한 이름을 먼저 찾고, 없으면 부분 일치로 찾는다."""
    for c in exact:
        if c in cols:
            return c
    low = {c: c.lower() for c in cols}
    for c, lc in low.items():
        if contains_all and all(t in lc for t in contains_all):
            return c
    for c, lc in low.items():
        if contains_any and any(t in lc for t in contains_any):
            return c
    log(f"\n[중단] '{label}'에 해당하는 열을 찾지 못했습니다. 덤프의 열 목록은 다음과 같습니다.")
    for i, c in enumerate(cols, 1):
        log(f"  {i:>3}. {c}")
    raise SystemExit(1)


C_TITLE = find("저널명", ["Journal title", "Title"], ("journal", "title"))
C_PISSN = find("인쇄 ISSN", ["Journal ISSN (print version)"], ("issn", "print"))
C_EISSN = find("온라인 ISSN", ["Journal EISSN (online version)"], ("issn", "online"),
               ("eissn",))
C_LIC = find("저널 라이선스", ["Journal license"], ("journal", "license"), ("licence", "license"))
C_ADDED = find("등재일", ["Added on Date", "Added on date"], ("added",))
C_OA = find("OA 시작연도",
            ["OA start",
             "When did the journal start to publish all content using an open license?"],
            ("start", "open license"),
            ("oa start", "oa_start", "first calendar year",
             "open access content", "open license"))

log("\n  사용할 열")
for lab, c in (("저널명", C_TITLE), ("인쇄 ISSN", C_PISSN), ("온라인 ISSN", C_EISSN),
               ("라이선스", C_LIC), ("등재일", C_ADDED), ("OA 시작연도", C_OA)):
    log(f"    {lab:<12} {c}")

# 이후 질의가 쓸 수 있도록 열 이름을 통일한 뷰를 만든다.
con.execute(f"""CREATE VIEW d0 AS SELECT
  "{C_TITLE}"  AS "Journal title",
  "{C_PISSN}"  AS "Journal ISSN (print version)",
  "{C_EISSN}"  AS "Journal EISSN (online version)",
  "{C_LIC}"    AS "Journal license",
  "{C_ADDED}"  AS "Added on Date",
  "{C_OA}"     AS "OA start"
FROM dump""")

n_all = con.execute("SELECT count(*) FROM d0").fetchone()[0]

# CC 필터의 정의를 확정한다. 원고의 23,149와 맞는 것을 고른다.
log("\n  CC 필터 후보별 저널 수 (원고 23,149)")
CANDS = [
    ("license ILIKE '%CC%' (어디든 CC 포함)", '"Journal license" ILIKE \'%CC%\''),
    ("license LIKE 'CC%' (대문자 CC로 시작)", '"Journal license" LIKE \'CC%\''),
    ("license ILIKE 'CC%' (대소문자 무시, CC로 시작)", '"Journal license" ILIKE \'CC%\''),
    ("쉼표로 나눈 모든 항목이 CC로 시작",
     "NOT EXISTS (SELECT 1 FROM UNNEST(str_split(\"Journal license\", ',')) u(x) "
     "WHERE trim(x) <> '' AND NOT trim(x) LIKE 'CC%')"
     " AND trim(coalesce(\"Journal license\",'')) <> ''"),
]
best = None
for lab, cond in CANDS:
    n = con.execute(f"SELECT count(*) FROM d0 WHERE {cond}").fetchone()[0]
    mark = "  ← 원고와 일치" if n == 23149 else ""
    log(f"    {n:>7,}  {lab}{mark}")
    if n == 23149 and best is None:
        best = (lab, cond)

if best is None:
    log("\n    원고의 23,149와 맞는 후보가 없다. 차집합의 라이선스 값을 아래에서 확인한다.")
    best = (CANDS[0][0], CANDS[0][1])
else:
    log(f"\n    채택: {best[0]}")

con.execute(f"""CREATE TABLE f1 AS SELECT * FROM d0 WHERE {best[1]}""")
con.execute("""CREATE TABLE f2 AS SELECT * FROM f1 WHERE substr("Added on Date",1,4) <= '2021'""")
n1 = con.execute("SELECT count(*) FROM f1").fetchone()[0]
n2 = con.execute("SELECT count(*) FROM f2").fetchone()[0]
log(f"  DOAJ 등재 전체                {n_all:,}")
log(f"  CC 계열 라이선스만            {n1:,}")
log(f"  2021년까지 등재              {n2:,}  (원고 14,030 = 13,806 + 224)")

con.execute(f"""CREATE TABLE panel_raw AS SELECT * FROM
read_csv_auto('{DOAJ}', header=true, all_varchar=true)""")
pcols = [r[0] for r in con.execute("DESCRIBE panel_raw").fetchall()]
for need in ("Journal ISSN (print version)", "Journal EISSN (online version)"):
    if need not in pcols:
        log(f"[중단] 모집단 파일에 '{need}' 열이 없습니다. 열 목록: {pcols}")
        raise SystemExit(1)
con.execute("CREATE VIEW panel AS SELECT * FROM panel_raw")
n_panel = con.execute("SELECT count(*) FROM panel").fetchone()[0]
log(f"  모집단 (doaj_panel_journals) {check('모집단', n_panel)}")

# ISSN 집합으로 차집합을 구한다. 한 저널이 ISSN 둘을 가질 수 있으므로 둘 다 본다.
con.execute("""CREATE TABLE key2 AS
SELECT *, upper(trim(coalesce("Journal ISSN (print version)",''))) || '|' ||
          upper(trim(coalesce("Journal EISSN (online version)",''))) k FROM f2""")
con.execute("""CREATE TABLE keyp AS
SELECT upper(trim(coalesce("Journal ISSN (print version)",''))) || '|' ||
       upper(trim(coalesce("Journal EISSN (online version)",''))) k FROM panel""")
con.execute("""CREATE TABLE diff0 AS
SELECT * EXCLUDE (k) FROM key2 WHERE k NOT IN (SELECT k FROM keyp)""")
n_diff = con.execute("SELECT count(*) FROM diff0").fetchone()[0]
log(f"  차집합                       {n_diff:,}")

# 차집합 가운데 제외 기준을 충족하는 것만 남긴다.
con.execute("""CREATE TABLE ex AS SELECT * FROM diff0
WHERE TRY_CAST("OA start" AS INT) > TRY_CAST(substr("Added on Date",1,4) AS INT)""")
n_ex = con.execute("SELECT count(*) FROM ex").fetchone()[0]
log(f"  그중 OA 시작연도 > 등재연도    {check('제외', n_ex)}")

n_other = n_diff - n_ex
if n_other:
    log(f"\n  기준을 충족하지 않는 {n_other}종이 차집합에 섞여 있다.")
    log("  CC 필터의 정의가 원본과 다르면 이런 저널이 딸려온다. 라이선스 값은 다음과 같다.")
    cur = con.execute("""SELECT "Journal license" 라이선스, count(*) 저널수 FROM diff0
      WHERE NOT (TRY_CAST("OA start" AS INT) > TRY_CAST(substr("Added on Date",1,4) AS INT))
      GROUP BY 1 ORDER BY 2 DESC""")
    log("  " + " | ".join(d[0] for d in cur.description))
    for row in cur.fetchall():
        log("  " + " | ".join("" if v is None else str(v) for v in row))

cur = con.execute("""SELECT "Journal title" 저널, "Journal ISSN (print version)" 인쇄ISSN,
  "Journal EISSN (online version)" 온라인ISSN, substr("Added on Date",1,10) 등재일,
  "OA start" OA시작 FROM ex ORDER BY TRY_CAST("OA start" AS INT) DESC LIMIT 10""")
log("\n  [차이가 큰 10종]")
log("  " + " | ".join(d[0] for d in cur.description))
for row in cur.fetchall():
    log("  " + " | ".join("" if v is None else str(v) for v in row))

# 목록 저장
outp = f"{DATA}/doaj_excluded_224.csv"
cur = con.execute("SELECT * FROM ex")
with open(outp, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow([d[0] for d in cur.description])
    w.writerows(cur.fetchall())
log(f"\n  목록 저장: {outp}")

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("2. 표 S3의 '제외한 224종 포함' 행 재계산")
log("=" * 72)

# 확장 패널의 저널 집합 = 모집단 13,806 + 복원한 224. f2(14,044)를 그대로 쓰면
# CC 필터 차이로 딸려온 저널까지 포함되므로 쓰지 않는다.
con.execute("""CREATE TABLE jset AS
SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e,
       TRY_CAST("OA start" AS INT) oa FROM panel
UNION ALL
SELECT "Journal ISSN (print version)", "Journal EISSN (online version)",
       TRY_CAST("OA start" AS INT) FROM ex""")
n_jset = con.execute("SELECT count(*) FROM jset").fetchone()[0]
log(f"  확장 저널 집합 {check('전체', n_jset)}")

con.execute("""CREATE TABLE jissn AS
SELECT upper(trim(issn)) issn, min(greatest(oa,2003)) min_year
FROM jset, UNNEST([p,e]) t(issn) WHERE issn IS NOT NULL AND trim(issn)<>'' GROUP BY 1""")

con.execute(f"""CREATE TABLE base AS
SELECT DISTINCT w.doi FROM
 (SELECT doi, pub_year, upper(trim(t.s)) issn
  FROM read_parquet('{P}/2023/works/*.parquet'), UNNEST(str_split(issn,';')) t(s)) w
JOIN jissn j USING (issn) WHERE w.pub_year >= j.min_year AND w.pub_year <= 2023""")
log(f"  2023년판 기준 확장 패널 {con.execute('SELECT count(*) FROM base').fetchone()[0]:,}")

con.execute(f"""CREATE TABLE in26 AS SELECT DISTINCT doi
FROM read_parquet('{P}/2026/works/*.parquet') WHERE doi IN (SELECT doi FROM base)""")
for y in ("2023", "2026"):
    con.execute(f"""CREATE TABLE cc{y} AS SELECT DISTINCT doi
    FROM read_parquet('{P}/{y}/licenses/*.parquet')
    WHERE {CCQ} AND doi IN (SELECT doi FROM base)""")

r = con.execute("""SELECT count(*),
  count(*) FILTER (WHERE a.doi IS NULL),
  count(*) FILTER (WHERE a.doi IS NULL AND b.doi IS NOT NULL),
  100.0*count(*) FILTER (WHERE a.doi IS NOT NULL)/count(*),
  100.0*count(*) FILTER (WHERE b.doi IS NOT NULL)/count(*)
FROM in26 n LEFT JOIN cc2023 a ON a.doi=n.doi LEFT JOIN cc2026 b ON b.doi=n.doi""").fetchone()
tot, miss, add, c23, c26 = r
log(f"\n  전체 N        {check('확장_N', tot)}")
log(f"  초기 미기재    {check('확장_미기재', miss)}")
log(f"  보완          {check('확장_보완', add)}")
log(f"  보완율        {check('확장_보완율', round(100.0*add/miss, 2) if miss else 0)}%")
log(f"  기재율 2023   {check('확장_기재율23', round(c23, 1))}%")
log(f"  기재율 2026   {check('확장_기재율26', round(c26, 1))}%")

base_n = con.execute(
    f"SELECT count(*) FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1").fetchone()[0]
log(f"\n  본 분석 패널 {base_n:,} 대비 증가 {tot - base_n:,}건")

log(f"\n완료. 결과: {OUT}")
logf.close()
