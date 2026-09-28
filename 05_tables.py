"""
논문 본문 표 1~9와 그림 1~3의 데이터를 한 번에 산출한다.

실행
  python 05_tables.py

입력
  D:/crossref/parquet/state_panel.parquet        03_panel.py의 산출물
  D:/crossref/parquet/{2023,2024,2025,2026}/{works,licenses}/*.parquet
  D:/crossref/doaj_panel_journals.csv

출력
  화면과 D:/crossref/tables_out.txt 에 표별 수치
  D:/crossref/figs/*.csv 에 그림 1~3의 작도용 데이터

원고에 실린 값을 EXPECTED에 넣어두고 계산 결과와 대조한다.
  일치  계산값이 원고와 같다
  불일치 원고를 고치거나 계산을 다시 봐야 한다
  (기대값 없음) 대조 대상으로 등록하지 않은 값

두 가지는 원고와 다른 규칙으로 계산한다. 원고 수정이 필요한 부분이다.
  그림 2  라이선스가 처음 확인된 스냅숏의 deposited 월 (원고 캡션의 규칙)
          이전 코드는 마지막 스냅숏의 deposited를 썼다
  표 6·그림 3  저널 키를 DOAJ 저널로 둔다
          이전 코드는 레코드의 container_title로 묶었다
"""
import csv
import os

import duckdb

# 기본값은 이 연구의 실행 환경이다. 다른 환경에서는 환경 변수로 덮어쓴다.
ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
P = os.environ.get("CROSSREF_PARQUET", f"{ROOT}/parquet")
DOAJ = os.environ.get("CROSSREF_DOAJ", f"{ROOT}/doaj_panel_journals.csv")
FIGS = os.environ.get("CROSSREF_FIGS", f"{ROOT}/figs")
OUT = os.environ.get("CROSSREF_TABLES_OUT", f"{ROOT}/tables_out.txt")
TMP = os.environ.get("CROSSREF_TMP", f"{ROOT}/_tmp")

os.makedirs(TMP, exist_ok=True)
os.makedirs(FIGS, exist_ok=True)

logf = open(OUT, "w", encoding="utf-8")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    logf.write(s + "\n")
    logf.flush()


con = duckdb.connect()
for q in ["SET threads=4", "SET memory_limit='6GB'",
          "SET preserve_insertion_order=false",
          f"SET temp_directory='{TMP}'"]:
    con.execute(q)

CCQ = ("url ILIKE '%creativecommons.org%' "
       "AND coalesce(content_version,'') IN ('vor','am','unspecified')")

# 원고에 실린 값 -------------------------------------------------------------
EXPECTED = {
    # 표 1
    "패널_저널": 11949, "패널_논문_하한적용": 7225064, "패널_논문_최종": 7215883,
    "저널_논문확인": 11955, "논문_논문확인": 8294247,
    # 표 2
    "기재_2023": 4271052, "기재_2024": 4335171, "기재_2025": 4390886, "기재_2026": 4437819,
    "기재율_2023": 59.2, "기재율_2026": 61.5,
    # 표 3
    "계속기재": 4267386, "계속미기재": 2777049, "보완": 167779,
    "중간변동": 2657, "소실": 1012,
    "미기재_2023": 2944831, "보완율": 5.70, "소실률": 0.02,
    "패턴_1001": 2612, "패턴_비단조": 3,
    # 표 4
    "후속등록없음": 2034438, "후속등록있음": 910393, "후속등록_보완율": 18.43,
    # 표 6 (저널명 기준 = 원고 현재값)
    "저널_100건이상_저널명기준": 5491, "저널_0퍼센트_저널명기준": 4556,
    "저널_95초과_저널명기준": 140,
    # 표 7
    "신규_2023이후": 3234283, "신규_과거": 123309, "신규_전체": 3357592,
    "신규_기재율_2023이후": 85.0, "신규_기재율_과거": 36.7, "신규_기재율_전체": 83.3,
    # 표 8
    "표준화_출판사수": 1372, "표준화_비중": 86.0,
    # 표 8은 원고가 소수 둘째 자리로 표기한다 (22.450이 정확히 경계값이라
    # 첫째 자리로 반올림하면 두 기준 중 한쪽만 합이 격차와 맞는다)
    "반사실_과거구성": 59.16, "반사실_신규구성": 57.18,
    "구성효과_과거기준": 30.18, "출판사내효과_과거기준": 22.45,
    "구성효과_신규기준": 20.46, "출판사내효과_신규기준": 32.17,
    # 표 9
    "미식별률_2023": 40.8, "미식별률_2026": 38.5,
    # 4.8
    "start_출판연도이하": 153965, "start_출판연도이하_비율": 91.8,
}


def check(key, value, digits=None):
    """계산값을 원고값과 대조한 표시 문자열을 돌려준다."""
    if key not in EXPECTED:
        return f"{value}  (기대값 없음)"
    exp = EXPECTED[key]
    v = round(value, digits) if digits is not None else value
    mark = "일치" if v == exp else f"불일치 (원고 {exp})"
    shown = f"{v:,}" if isinstance(v, int) else f"{v}"
    return f"{shown}  {mark}"


def show(title, q):
    cur = con.execute(q)
    log(f"\n[{title}]")
    log("  " + " | ".join(d[0] for d in cur.description))
    for r in cur.fetchall():
        log("  " + " | ".join(
            "" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) for v in r))


def save(name, q):
    cur = con.execute(q)
    p = f"{FIGS}/{name}.csv"
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([d[0] for d in cur.description])
        w.writerows(cur.fetchall())
    log(f"  작도용 데이터 저장: {p}")


def one(q):
    return con.execute(q).fetchone()


# 공통 뷰와 테이블 ---------------------------------------------------------
con.execute(f"CREATE VIEW st AS SELECT * FROM read_parquet('{P}/state_panel.parquet')")
con.execute("CREATE VIEW s AS SELECT * FROM st WHERE in26=1")
for y in ("2023", "2024", "2025", "2026"):
    con.execute(f"CREATE VIEW w{y} AS SELECT * FROM read_parquet('{P}/{y}/works/*.parquet')")
    con.execute(f"CREATE VIEW l{y} AS SELECT * FROM read_parquet('{P}/{y}/licenses/*.parquet')")

# DOAJ 저널에 번호를 붙인다. 저널 단위 집계의 키로 쓴다.
con.execute(f"""CREATE TABLE jrow AS
SELECT row_number() OVER () jid, "Journal title" title,
       upper(trim("Journal ISSN (print version)")) p,
       upper(trim("Journal EISSN (online version)")) e,
       CAST("OA start" AS INT) oa
FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true)""")
con.execute("""CREATE TABLE j2i AS
SELECT jid, issn FROM jrow, UNNEST([p, e]) t(issn)
WHERE issn IS NOT NULL AND trim(issn) <> ''""")
con.execute("""CREATE TABLE jissn AS
SELECT i.issn, min(greatest(j.oa, 2003)) min_year, min(j.oa) oa_start
FROM j2i i JOIN jrow j USING (jid) GROUP BY i.issn""")

# 논문을 DOAJ 저널에 연결한다. 한 DOI가 두 저널에 걸리면 양쪽에 계수된다.
con.execute("""CREATE TABLE dj AS
SELECT DISTINCT w.doi, m.jid FROM
 (SELECT doi, upper(trim(t.s)) issn FROM w2023, UNNEST(str_split(issn,';')) t(s)) w
JOIN j2i m USING (issn)
WHERE w.doi IN (SELECT doi FROM s)""")

for y in ("2023", "2024", "2025", "2026"):
    con.execute(f"CREATE TABLE cc{y} AS SELECT DISTINCT doi FROM l{y} WHERE {CCQ}")
con.execute("CREATE TABLE addx AS SELECT * FROM s WHERE cc23=0 AND cc26=1")

log("=" * 70)
log("표 1. 모집단과 분석 패널의 구성")
log("=" * 70)
log("  DOAJ 등재 전체, CC 라이선스 사용, 2021년까지 등재의 세 행은")
log("  DOAJ 원본 덤프가 필요하다. 이 스크립트는 필터 적용 후 단계만 산출한다.")
n_j_doaj = one("SELECT count(*) FROM jrow")[0]
log(f"\n  OA 시작연도 이상치 제외(모집단): 저널 {n_j_doaj:,}")
r = one("""SELECT count(DISTINCT jid), count(DISTINCT doi) FROM dj""")
log(f"  저널별 하한연도 적용:            저널 {check('패널_저널', r[0])}")
log(f"  하한연도 적용 후 논문:           {check('패널_논문_하한적용', one('SELECT count(*) FROM st')[0])}")
log(f"  2026년판에도 포함(최종 패널):     {check('패널_논문_최종', one('SELECT count(*) FROM s')[0])}")
log(f"  최종 패널에서 제외된 DOI:        {one('SELECT count(*) FROM st WHERE in26=0')[0]:,}")

log("\n" + "=" * 70)
log("표 2. 시점별 CC 기재 상태")
log("=" * 70)
n = one("SELECT count(*) FROM s")[0]
prev = first = None
for y, col in (("2023", "cc23"), ("2024", "cc24"), ("2025", "cc25"), ("2026", "cc26")):
    k = one(f"SELECT sum({col}) FROM s")[0]
    rate = 100.0 * k / n                      # 반올림 전 값
    if prev is None:
        d, first = "-", rate
    else:
        d = f"{rate - prev:+.1f}%p"           # 전기 대비도 반올림 전 값으로 계산
    log(f"  {y}년판  {check('기재_' + y, k)}   {rate:.1f}%   {d}")
    prev = rate
log(f"\n  3년간 순증가  {prev - first:+.1f}%p")
log("  전기 대비와 순증가는 반올림 전 기재율의 차이다. 반올림한 값끼리 빼면 0.1%p 어긋날 수 있다.")

log("\n" + "=" * 70)
log("표 3. 상태 전이")
log("=" * 70)
r = one("""SELECT
  count(*) FILTER (WHERE cc23=1 AND cc24=1 AND cc25=1 AND cc26=1) a,
  count(*) FILTER (WHERE cc23=0 AND cc24=0 AND cc25=0 AND cc26=0) b,
  count(*) FILTER (WHERE cc23=0 AND cc26=1) c,
  count(*) FILTER (WHERE cc23=1 AND cc26=0) d,
  count(*) FILTER (WHERE cc23=0) e, count(*) FILTER (WHERE cc23=1) f,
  count(*) g FROM s""")
a, b, c, d, e, f, g = r
mid = g - a - b - c - d
log(f"  계속 기재 (1111)  {check('계속기재', a)}   {100.0*a/g:.2f}%")
log(f"  계속 미기재 (0000) {check('계속미기재', b)}   {100.0*b/g:.2f}%")
log(f"  보완              {check('보완', c)}   {100.0*c/g:.2f}%")
log(f"  중간 변동          {check('중간변동', mid)}   {100.0*mid/g:.2f}%")
log(f"  소실              {check('소실', d)}   {100.0*d/g:.2f}%")
log(f"  합계              {check('패널_논문_최종', g)}")
log(f"\n  2023년 미기재     {check('미기재_2023', e)}")
log(f"  보완율            {check('보완율', 100.0*c/e, 2)}%")
log(f"  소실률            {check('소실률', 100.0*d/f, 2)}%")
show("패턴 분포 (상위 12개)", """
SELECT concat(cc23,cc24,cc25,cc26) 패턴, count(*) 논문수
FROM s GROUP BY 1 ORDER BY 2 DESC LIMIT 12""")
n_1001 = one("SELECT count(*) FROM s WHERE cc23=1 AND cc24=0 AND cc25=0 AND cc26=1")[0]
n_0101 = one("SELECT count(*) FROM s WHERE cc23=0 AND cc24=1 AND cc25=0 AND cc26=1")[0]
log("\n  1001 패턴         " + check('패턴_1001', n_1001))
log("  비단조 보완(0101)  " + check('패턴_비단조', n_0101))

log("\n" + "=" * 70)
log("표 4. 후속 등록 여부별 보완")
log("=" * 70)
log("  후속 등록 있음의 정의는 dep26 > dep23 이다. 부등호 비교이므로 한쪽이 NULL이면")
log("  결과가 NULL이 되어 '없음'으로 분류된다. 대조를 위해 다른 두 정의도 함께 계산한다.")
for lab, cond in [
    ("가. dep26 > dep23 (본 분석)", "dep26 > dep23"),
    ("나. dep26 <> dep23 (NULL도 변화로 봄)", "dep26 IS DISTINCT FROM dep23"),
    ("다. 시점 간 어느 구간이든 변화", "dep24 IS DISTINCT FROM dep23 OR dep25 IS DISTINCT FROM dep24 OR dep26 IS DISTINCT FROM dep25"),
]:
    r = one(f"""SELECT
      count(*) FILTER (WHERE NOT ({cond})) n0,
      count(*) FILTER (WHERE {cond}) n1,
      count(*) FILTER (WHERE NOT ({cond}) AND cc26=1) a0,
      count(*) FILTER (WHERE ({cond}) AND cc26=1) a1
    FROM s WHERE cc23=0""")
    n0, n1, a0, a1 = r
    log(f"\n  {lab}")
    log(f"    후속 등록 없음  {check('후속등록없음', n0)}   보완 {a0:,}")
    log(f"    후속 등록 있음  {check('후속등록있음', n1)}   보완 {a1:,}   "
        f"보완율 {check('후속등록_보완율', 100.0*a1/n1 if n1 else 0, 2)}%")

show("'없음'으로 분류되는 사유별 내역 (2023년 미기재 기준)", """
SELECT count(*) FILTER (WHERE dep23 IS NULL AND dep26 IS NULL) 둘다NULL,
       count(*) FILTER (WHERE dep23 IS NULL AND dep26 IS NOT NULL) dep23만NULL,
       count(*) FILTER (WHERE dep26 IS NULL AND dep23 IS NOT NULL) dep26만NULL,
       count(*) FILTER (WHERE dep23 IS NOT NULL AND dep26 IS NOT NULL AND dep26 = dep23) 값이같음,
       count(*) FILTER (WHERE dep23 IS NOT NULL AND dep26 IS NOT NULL AND dep26 < dep23) dep26이_더_이름
FROM s WHERE cc23=0""")
show("NULL이거나 역행하는 경우의 보완 건수", """
SELECT count(*) FILTER (WHERE dep23 IS NULL OR dep26 IS NULL) NULL있음,
       count(*) FILTER (WHERE (dep23 IS NULL OR dep26 IS NULL) AND cc26=1) NULL있음_보완,
       count(*) FILTER (WHERE dep23 IS NOT NULL AND dep26 IS NOT NULL AND dep26 < dep23) 역행,
       count(*) FILTER (WHERE dep23 IS NOT NULL AND dep26 IS NOT NULL AND dep26 < dep23 AND cc26=1) 역행_보완
FROM s WHERE cc23=0""")

log("\n" + "=" * 70)
log("표 5. 출판사별 현황")
log("=" * 70)
show("2023년 미기재 1만 건 이상, 미기재 순", """
SELECT any_value(publisher) 출판사, count(*) 패널논문,
       round(100.0*avg(cc23),1) 기재율_2023,
       count(*) FILTER (WHERE cc23=0) 미기재,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) 보완,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)
             /nullif(count(*) FILTER (WHERE cc23=0),0),2) 보완율,
       round(100.0*avg(cc26),1) 기재율_2026
FROM s GROUP BY member
HAVING count(*) FILTER (WHERE cc23=0) >= 10000
ORDER BY 4 DESC""")
r = one("""WITH t AS (SELECT member, count(*) FILTER (WHERE cc23=0) n,
                   count(*) FILTER (WHERE cc23=0 AND cc26=1) a
            FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000)
SELECT count(*), count(*) FILTER (WHERE a=0), count(*) FILTER (WHERE 100.0*a/n < 1) FROM t""")
log(f"\n  1만 건 이상 출판사 {r[0]}곳 / 보완 0건 {r[1]}곳 / 보완율 1% 미만 {r[2]}곳")

log("\n" + "=" * 70)
log("표 6. 저널 단위 보완율 분포")
log("=" * 70)
BUCKET = """CASE WHEN a = 0 THEN '1 0% (보완 전무)'
                 WHEN r <= 5 THEN '2 0% 초과 ~ 5% 이하'
                 WHEN r <= 50 THEN '3 5% 초과 ~ 50% 이하'
                 WHEN r <= 95 THEN '4 50% 초과 ~ 95% 이하'
                 ELSE '5 95% 초과' END"""
for lab, src in [
    ("가. DOAJ 저널 기준 (권장)",
     "s JOIN dj d USING (doi) GROUP BY d.jid"),
    ("나. container_title 기준 (원고 현재값)",
     "s GROUP BY container_title"),
]:
    log(f"\n  {lab}")
    cur = con.execute(f"""
    WITH t AS (SELECT count(*) FILTER (WHERE s.cc23=0) n,
                      count(*) FILTER (WHERE s.cc23=0 AND s.cc26=1) a
               FROM {src} HAVING count(*) FILTER (WHERE s.cc23=0) >= 100),
         u AS (SELECT n, a, 100.0*a/n r FROM t)
    SELECT {BUCKET} 구간, count(*) 저널수, sum(n) 미기재논문 FROM u GROUP BY 1 ORDER BY 1""")
    rows = cur.fetchall()
    tot_j = sum(x[1] for x in rows)
    tot_n = sum(x[2] for x in rows)
    for g_, jn, nn in rows:
        log(f"    {g_:<24} {jn:>6,}  {100.0*jn/tot_j:5.1f}%  {nn:>10,}")
    log(f"    {'합계':<24} {tot_j:>6,}  100.0%  {tot_n:>10,}")
    if "DOAJ" in lab:
        log(f"    → 저널 수 합계 {tot_j:,} (원고 저널명 기준 {EXPECTED['저널_100건이상_저널명기준']:,})")

for lab, src in [("DOAJ 저널 기준", "s JOIN dj d USING (doi) GROUP BY d.jid"),
                 ("container_title 기준", "s GROUP BY container_title")]:
    show(f"보완율 분위수 ({lab})", f"""
    WITH t AS (SELECT count(*) FILTER (WHERE s.cc23=0) n,
                      count(*) FILTER (WHERE s.cc23=0 AND s.cc26=1) a
               FROM {src} HAVING count(*) FILTER (WHERE s.cc23=0) >= 100)
    SELECT round(median(100.0*a/n),2) 중앙값,
           round(quantile_cont(100.0*a/n, 0.75),2) 제3사분위,
           round(quantile_cont(100.0*a/n, 0.95),2) 제95분위,
           count(*) FILTER (WHERE a > 0) 보완있는저널,
           round(100.0*count(*) FILTER (WHERE a > 0)/count(*),1) 비율 FROM t""")

log("\n" + "=" * 70)
log("표 7. 신규 등록 레코드의 CC 기재율")
log("=" * 70)
con.execute("""CREATE TABLE u26 AS
SELECT doi, min(pub_year) pub_year, min(created) created FROM
 (SELECT doi, pub_year, created, upper(trim(t.s)) issn
  FROM w2026, UNNEST(str_split(issn,';')) t(s)) w
JOIN jissn j USING (issn)
WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026
GROUP BY doi""")
con.execute("CREATE TABLE nw AS SELECT * FROM u26 WHERE created >= '2023-04-01'")
show("created 2023-04-01 이후 등록, DOI 단위", """
SELECT CASE WHEN pub_year >= 2023 THEN '2023년 이후 출판분'
            ELSE '과거 출판분의 신규 등록' END 구분,
       count(*) 논문수,
       count(*) FILTER (WHERE doi IN (SELECT doi FROM cc2026)) 기재건수,
       round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc2026))/count(*),1) 기재율
FROM nw GROUP BY 1 ORDER BY 2 DESC""")
r = one("""SELECT count(*), count(*) FILTER (WHERE doi IN (SELECT doi FROM cc2026)) FROM nw""")
log(f"  전체  {check('신규_전체', r[0])}   기재 {r[1]:,}   "
    f"기재율 {check('신규_기재율_전체', 100.0*r[1]/r[0], 1)}%")

log("\n" + "=" * 70)
log("표 8. 신규 출판분과 과거 출판분 기재율 격차의 분해")
log("=" * 70)
con.execute("""CREATE TABLE fy AS
SELECT doi, min(y) fy FROM (
  SELECT doi, 2024 y FROM w2024 UNION ALL
  SELECT doi, 2025 FROM w2025 UNION ALL
  SELECT doi, 2026 FROM w2026) GROUP BY doi""")
con.execute("""CREATE TABLE mfirst AS
WITH m24 AS (SELECT doi, any_value(member) m FROM w2024 GROUP BY doi),
     m25 AS (SELECT doi, any_value(member) m FROM w2025 GROUP BY doi),
     m26 AS (SELECT doi, any_value(member) m FROM w2026 GROUP BY doi)
SELECT b.doi, b.pub_year,
       CASE f.fy WHEN 2024 THEN m24.m WHEN 2025 THEN m25.m ELSE m26.m END member
FROM nw b JOIN fy f USING (doi)
LEFT JOIN m24 ON m24.doi=b.doi LEFT JOIN m25 ON m25.doi=b.doi LEFT JOIN m26 ON m26.doi=b.doi""")
r = one("""
WITH t AS (SELECT member,
    count(*) FILTER (WHERE pub_year>=2023) n_new,
    count(*) FILTER (WHERE pub_year<2023) n_old,
    1.0*count(*) FILTER (WHERE pub_year>=2023 AND doi IN (SELECT doi FROM cc2026))
      /nullif(count(*) FILTER (WHERE pub_year>=2023),0) r_new,
    1.0*count(*) FILTER (WHERE pub_year<2023 AND doi IN (SELECT doi FROM cc2026))
      /nullif(count(*) FILTER (WHERE pub_year<2023),0) r_old
  FROM mfirst GROUP BY member),
 ok AS (SELECT * FROM t WHERE r_new IS NOT NULL AND r_old IS NOT NULL)
SELECT count(*), sum(n_new)+sum(n_old), (SELECT count(*) FROM nw),
  100.0*sum(n_new*r_new)/sum(n_new), 100.0*sum(n_old*r_old)/sum(n_old),
  100.0*sum(n_old*r_new)/sum(n_old), 100.0*sum(n_new*r_old)/sum(n_new) FROM ok""")
npub, ntgt, nall, a_new, a_old, cf_old, cf_new = r
log(f"  표준화 대상 출판사  {check('표준화_출판사수', npub)}")
log(f"  대상 논문 {ntgt:,} / 신규 등록 전체 {nall:,} = "
    f"{check('표준화_비중', 100.0*ntgt/nall, 1)}%")
log(f"  신규 실제 {a_new:.3f}%  과거 실제 {a_old:.3f}%  격차 {a_new-a_old:.3f}%p")
log(f"\n  과거 출판분의 출판사 구성: 반사실 {check('반사실_과거구성', round(cf_old,2))}%  "
    f"구성 효과 {check('구성효과_과거기준', round(a_new-cf_old,2))}%p  "
    f"출판사 내 효과 {check('출판사내효과_과거기준', round(cf_old-a_old,2))}%p")
log(f"  신규 출판분의 출판사 구성: 반사실 {check('반사실_신규구성', round(cf_new,2))}%  "
    f"구성 효과 {check('구성효과_신규기준', round(cf_new-a_old,2))}%p  "
    f"출판사 내 효과 {check('출판사내효과_신규기준', round(a_new-cf_new,2))}%p")
log("\n  반올림 전 값 (성분을 각각 반올림하면 합이 격차와 어긋날 수 있다)")
log(f"    반사실 과거구성 {cf_old:.3f}  구성 {a_new-cf_old:.3f}  출판사 내 {cf_old-a_old:.3f}  "
    f"합 {(a_new-cf_old)+(cf_old-a_old):.3f}")
log(f"    반사실 신규구성 {cf_new:.3f}  구성 {cf_new-a_old:.3f}  출판사 내 {a_new-cf_new:.3f}  "
    f"합 {(cf_new-a_old)+(a_new-cf_new):.3f}")

log("\n" + "=" * 70)
log("표 9. 출판사별 Crossref CC 기반 OA 미식별률")
log("=" * 70)
show("2023년 미기재 1만 건 이상", """
SELECT any_value(publisher) 출판사,
       round(100.0*(1-avg(cc23)),1) 미식별률_2023,
       round(100.0*(1-avg(cc26)),1) 미식별률_2026
FROM s GROUP BY member
HAVING count(*) FILTER (WHERE cc23=0) >= 10000
ORDER BY 2 DESC""")
r = one("SELECT 100.0*(1-avg(cc23)), 100.0*(1-avg(cc26)) FROM s")
log(f"\n  전체  {check('미식별률_2023', round(r[0],1))}%  →  {check('미식별률_2026', round(r[1],1))}%")

log("\n" + "=" * 70)
log("4.8 보완된 라이선스의 시작일")
log("=" * 70)
r = one(f"""
WITH d AS (SELECT a.doi, a.pub_year, min(CAST(l.start AS VARCHAR)) st
           FROM addx a JOIN l2026 l USING (doi) WHERE {CCQ} GROUP BY 1,2)
SELECT count(*), count(*) FILTER (WHERE CAST(substr(st,1,4) AS INT) <= pub_year),
       count(*) FILTER (WHERE CAST(substr(st,1,4) AS INT) > pub_year
                          AND CAST(substr(st,1,4) AS INT) >= 2023),
       count(*) FILTER (WHERE st IS NULL) FROM d""")
log(f"  보완 {r[0]:,} 가운데")
log(f"    start 연도가 출판연도 이하  {check('start_출판연도이하', r[1])}  "
    f"({check('start_출판연도이하_비율', round(100.0*r[1]/r[0],1))}%)")
log(f"    출판연도보다 늦고 2023년 이상 {r[2]:,}")
log(f"    start 없음                  {r[3]:,}")

log("\n" + "=" * 70)
log("그림 1~3 작도용 데이터")
log("=" * 70)

save("fig1_year_by_snapshot", """
SELECT pub_year 출판연도, count(*) 논문수,
       round(100.0*avg(cc23),2) y2023, round(100.0*avg(cc24),2) y2024,
       round(100.0*avg(cc25),2) y2025, round(100.0*avg(cc26),2) y2026
FROM s GROUP BY 1 ORDER BY 1""")

# 그림 2: 라이선스가 처음 확인된 스냅숏의 deposited 월 (원고 캡션의 규칙)
save("fig2_monthly_backfill", """
SELECT substr(CAST(CASE WHEN cc24=1 THEN dep24 WHEN cc25=1 THEN dep25
                        ELSE dep26 END AS VARCHAR),1,7) 등록월,
       count(*) 보완건수
FROM s WHERE cc23=0 AND cc26=1
GROUP BY 1 HAVING 등록월 >= '2023-04' ORDER BY 1""")
show("그림 2 상위 8개월 (처음 확인된 스냅숏 기준)", """
SELECT substr(CAST(CASE WHEN cc24=1 THEN dep24 WHEN cc25=1 THEN dep25
                        ELSE dep26 END AS VARCHAR),1,7) 등록월, count(*) 보완건수
FROM s WHERE cc23=0 AND cc26=1 GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")

# 그림 3: DOAJ 저널 기준
save("fig3_journal_backfill", """
SELECT d.jid 저널번호, any_value(j.title) 저널명, any_value(s.publisher) 출판사,
       count(*) FILTER (WHERE s.cc23=0) 미기재,
       round(100.0*count(*) FILTER (WHERE s.cc23=0 AND s.cc26=1)
             /nullif(count(*) FILTER (WHERE s.cc23=0),0),2) 보완율
FROM s JOIN dj d USING (doi) JOIN jrow j ON j.jid=d.jid
GROUP BY d.jid HAVING count(*) FILTER (WHERE s.cc23=0) >= 100
ORDER BY 4 DESC""")

save("tab5_publisher", """
SELECT any_value(publisher) 출판사, count(*) 패널논문수,
       round(100.0*avg(cc23),1) 기재율2023, count(*) FILTER (WHERE cc23=0) 미기재,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) 보완,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)
             /nullif(count(*) FILTER (WHERE cc23=0),0),2) 보완율,
       round(100.0*avg(cc26),1) 기재율2026
FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000
ORDER BY 4 DESC""")

log(f"\n완료. 결과: {OUT}")
logf.close()
