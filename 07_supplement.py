"""
보충자료 표 S1~S5와 본문 4.4·4.5·4.9절의 수치를 재계산한다.

실행
  python 07_supplement.py

입력
  D:/crossref/parquet/state_panel.parquet
  D:/crossref/parquet/{2023,2024,2025,2026}/{works,licenses}/*.parquet
  D:/crossref/doaj_panel_journals.csv
  D:/crossref/data/doaj_country.csv        표 S5에만 필요 (없으면 건너뛴다)

출력
  화면과 D:/crossref/supplement_out.txt

05_tables.py와 같은 방식으로, 보충자료에 실린 값을 EXPECTED에 담아 대조한다.

재현할 수 없는 항목
  표 S3의 '제외한 224종 포함' 행은 OA 시작연도 이상치로 제외한 224종이 필요하다.
  doaj_panel_journals.csv는 이미 그 224종을 뺀 목록이므로 이 행은 계산하지 않는다.
  해당 행을 재현하려면 224종을 포함한 저널 목록이 따로 있어야 한다.
"""
import os

import duckdb

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
P = os.environ.get("CROSSREF_PARQUET", f"{ROOT}/parquet")
DOAJ = os.environ.get("CROSSREF_DOAJ", f"{ROOT}/doaj_panel_journals.csv")
DOAJ_C = os.environ.get("CROSSREF_DOAJ_COUNTRY", f"{ROOT}/data/doaj_country.csv")
OUT = os.environ.get("CROSSREF_SUPP_OUT", f"{ROOT}/supplement_out.txt")
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
          "SET preserve_insertion_order=false",
          f"SET temp_directory='{TMP}'"]:
    con.execute(q)

CC_URL = "url ILIKE '%creativecommons.org%'"
CCQ = f"{CC_URL} AND coalesce(content_version,'') IN ('vor','am','unspecified')"

# 보충자료에 실린 값 ---------------------------------------------------------
EXPECTED = {
    # 표 S1
    "전환연도_확인": 18,
    "SciELO_전환": 2019, "SciELO_이전N": 197143, "SciELO_이전율": 2.2,
    "Springer_전환": 2019, "Springer_이전N": 500173, "Springer_이전율": 38.5,
    "Frontiers_전환": 2018, "Frontiers_이전N": 92795, "Frontiers_이전율": 0.9,
    # 표 S2
    "start_이하": 153965, "start_초과_2023미만": 5131, "start_초과_2023이상": 8683,
    "start_2023이상_전체": 12775, "start_2023이상_출판도2023이상": 4092,
    # 표 S3
    "vor_미기재": 4482717, "vor_보완": 336258, "vor_보완율": 7.50,
    "vorun_미기재": 2956455, "vorun_보완": 168887, "vorun_보완율": 5.71,
    "본분석_미기재": 2944831, "본분석_보완": 167779, "본분석_보완율": 5.70,
    "tdm_미기재": 2752943, "tdm_보완": 166210, "tdm_보완율": 6.04,
    "하한2010_N": 6815503, "하한2010_보완율": 5.75,
    "하한2015_N": 5708490, "하한2015_보완율": 6.38,
    "하한2020_N": 3095990, "하한2020_미기재": 656049, "하한2020_보완율": 9.71,
    "전환연도제외_N": 6944610, "전환연도제외_미기재": 2801997,
    "전환연도제외_보완": 161814, "전환연도제외_보완율": 5.77,
    # 표 S4
    "집중_전체N": 2944831, "집중_제외후N": 2422718, "집중_제외후보완율": 2.51,
    "집중_상위5미기재": 520303, "집중_member미상": 1810,
    # 표 S5
    "국가수": 116, "국가결측": 0, "국가_2만이상": 37,
    # 4.4절
    "상위5_보완합": 106865, "상위5_보완비중": 63.7, "상위5_미기재비중": 17.7,
    "CSIC_최다월비중": 99.7, "AIP_최다월비중": 78.2, "Springer_최다월비중": 53.2,
    "WK_최다월비중": 42.0, "OpenEdition_최다월비중": 27.9,
    # 4.9절
    "unspecified만_보완": 118398, "unspecified만_비율": 70.6, "비표준URL만_보완": 8,
    "AM제외_미기재차": 11624,
}


def check(key, value, digits=None):
    if key not in EXPECTED:
        return f"{value}  (기대값 없음)"
    exp = EXPECTED[key]
    v = round(value, digits) if digits is not None else value
    mark = "일치" if v == exp else f"불일치 (보충자료 {exp})"
    return f"{v:,}  {mark}" if isinstance(v, int) else f"{v}  {mark}"


def show(t, q):
    cur = con.execute(q)
    log(f"\n[{t}]")
    log("  " + " | ".join(d[0] for d in cur.description))
    for r in cur.fetchall():
        log("  " + " | ".join(
            "" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) for v in r))


def one(q):
    return con.execute(q).fetchone()


def pct(num, den, digits=2):
    """0으로 나누는 경우를 막는다."""
    return round(100.0 * num / den, digits) if den else 0.0


con.execute(f"CREATE VIEW st AS SELECT * FROM read_parquet('{P}/state_panel.parquet')")
con.execute("CREATE VIEW s AS SELECT * FROM st WHERE in26=1")
for y in ("2023", "2024", "2025", "2026"):
    con.execute(f"CREATE VIEW w{y} AS SELECT * FROM read_parquet('{P}/{y}/works/*.parquet')")
    con.execute(f"CREATE VIEW l{y} AS SELECT * FROM read_parquet('{P}/{y}/licenses/*.parquet')")
con.execute("CREATE TABLE addx AS SELECT * FROM s WHERE cc23=0 AND cc26=1")
con.execute(f"""CREATE TABLE jissn AS
WITH j AS (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e,
                  CAST("OA start" AS INT) oa
           FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true))
SELECT upper(trim(issn)) issn, min(greatest(oa,2003)) min_year, min(oa) oa_start
FROM j, UNNEST([p,e]) t(issn) WHERE issn IS NOT NULL AND trim(issn)<>'' GROUP BY 1""")

N = one("SELECT count(*) FROM s")[0]

# ---------------------------------------------------------------------------
log("=" * 72)
log("표 S1. 출판사별 기재율 전환 출판연도")
log("=" * 72)
log("  정의: 연간 논문 100건 이상인 출판연도 가운데, 그 해부터 마지막 연도까지")
log("        모든 해의 2026년판 기재율이 80% 이상인 최초의 연도")

con.execute("""CREATE TABLE turn AS
WITH y AS (SELECT member, any_value(publisher) pub, pub_year, count(*) n, avg(cc26) r
           FROM s GROUP BY member, pub_year),
     big AS (SELECT member FROM s GROUP BY member
             HAVING count(*) FILTER (WHERE cc23=0) >= 10000),
     ok AS (SELECT member, pub_year,
                   min(r) OVER (PARTITION BY member ORDER BY pub_year
                                ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) ma
            FROM y WHERE n >= 100 AND member IN (SELECT member FROM big))
SELECT member, min(pub_year) FILTER (WHERE ma >= 0.8) ty FROM ok GROUP BY member""")

n_turn = one("SELECT count(*) FROM turn WHERE ty IS NOT NULL")[0]
n_big = one("""SELECT count(*) FROM (SELECT member FROM s GROUP BY member
                HAVING count(*) FILTER (WHERE cc23=0) >= 10000)""")[0]
log(f"\n  미기재 1만 건 이상 출판사 {n_big}곳 중 전환연도 확인 {check('전환연도_확인', n_turn)}")

show("전환연도와 그 이전 출판분 (2026년판 기재율)", """
SELECT any_value(s.publisher) 출판사, t.ty 전환연도,
       count(*) FILTER (WHERE s.pub_year < t.ty) 이전출판분,
       round(100.0*avg(CASE WHEN s.pub_year < t.ty THEN s.cc26 END),1) 이전기재율
FROM s JOIN turn t USING (member) WHERE t.ty IS NOT NULL
GROUP BY t.member, t.ty ORDER BY t.ty, 3 DESC""")

log("\n  본문 4.5절에 인용된 세 곳 (member 번호가 아니라 출판사명으로 찾는다)")
for lab, pat in (("SciELO", "%SciELO%"), ("Springer", "Springer%"), ("Frontiers", "Frontiers%")):
    r = one(f"""SELECT t.ty, count(*) FILTER (WHERE s.pub_year < t.ty),
                100.0*avg(CASE WHEN s.pub_year < t.ty THEN s.cc26 END)
                FROM s JOIN turn t USING (member)
                WHERE s.publisher ILIKE '{pat}' AND t.ty IS NOT NULL GROUP BY t.ty""")
    if r:
        log(f"    {lab:<10} 전환 {check(lab + '_전환', r[0])}  "
            f"이전 출판분 {check(lab + '_이전N', r[1])}  "
            f"기재율 {check(lab + '_이전율', round(r[2], 1))}%")
    else:
        log(f"    {lab:<10} 전환연도가 확인되지 않음")

show("Frontiers 정책 확인 구간 (2013~2017년 출판분)", """
SELECT count(*) 논문수, round(100.0*avg(cc23),1) 기재율_2023,
       round(100.0*avg(cc26),1) 기재율_2026
FROM s WHERE publisher ILIKE 'Frontiers%' AND pub_year BETWEEN 2013 AND 2017""")
show("Frontiers 2017년까지 출판분", """
SELECT count(*) 논문수, round(100.0*avg(cc23),1) 기재율_2023,
       round(100.0*avg(cc26),1) 기재율_2026
FROM s WHERE publisher ILIKE 'Frontiers%' AND pub_year <= 2017""")

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("표 S2. 보완된 라이선스의 start 날짜")
log("=" * 72)
con.execute(f"""CREATE TABLE st26 AS
SELECT a.doi, a.pub_year, min(CAST(l.start AS VARCHAR)) st
FROM addx a JOIN l2026 l USING (doi) WHERE {CCQ} GROUP BY 1,2""")
r = one("""SELECT count(*),
  count(*) FILTER (WHERE CAST(substr(st,1,4) AS INT) <= pub_year),
  count(*) FILTER (WHERE CAST(substr(st,1,4) AS INT) > pub_year
                     AND CAST(substr(st,1,4) AS INT) < 2023),
  count(*) FILTER (WHERE CAST(substr(st,1,4) AS INT) > pub_year
                     AND CAST(substr(st,1,4) AS INT) >= 2023),
  count(*) FILTER (WHERE CAST(substr(st,1,4) AS INT) >= 2023),
  count(*) FILTER (WHERE CAST(substr(st,1,4) AS INT) >= 2023 AND pub_year >= 2023),
  count(*) FILTER (WHERE st IS NULL) FROM st26""")
tot, a1, a2, a3, a4, a5, a6 = r
log(f"  대상 {tot:,}")
log(f"    start 연도 ≤ 출판연도                {check('start_이하', a1)}  ({100.0*a1/tot:.1f}%)")
log(f"    출판연도 초과이면서 2023년 미만       {check('start_초과_2023미만', a2)}  ({100.0*a2/tot:.1f}%)")
log(f"    출판연도 초과이면서 2023년 이상       {check('start_초과_2023이상', a3)}  ({100.0*a3/tot:.1f}%)")
log(f"    start 연도 2023년 이상 전체          {check('start_2023이상_전체', a4)}  ({100.0*a4/tot:.1f}%)")
log(f"      그중 출판연도도 2023년 이상         {check('start_2023이상_출판도2023이상', a5)}")
log(f"    start 없음                          {a6:,}")

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("표 S3. 판정 규칙과 하한연도에 따른 보완율과 기재율")
log("=" * 72)
log("  '제외한 224종 포함' 행은 224종을 담은 저널 목록이 없어 계산하지 않는다.")

RULES = [
    ("vor", "VoR만 인정", "content_version = 'vor'"),
    ("vorun", "VoR·unspecified 인정", "coalesce(content_version,'') IN ('vor','unspecified')"),
    ("본분석", "본 분석 (VoR·AM·unspecified)", "coalesce(content_version,'') IN ('vor','am','unspecified')"),
    ("tdm", "tdm 포함", "1=1"),
]
for key, lab, cond in RULES:
    con.execute(f"CREATE OR REPLACE TABLE r23 AS SELECT DISTINCT doi FROM l2023 WHERE {CC_URL} AND ({cond})")
    con.execute(f"CREATE OR REPLACE TABLE r26 AS SELECT DISTINCT doi FROM l2026 WHERE {CC_URL} AND ({cond})")
    r = one("""SELECT count(*),
      count(*) FILTER (WHERE a.doi IS NULL),
      count(*) FILTER (WHERE a.doi IS NULL AND b.doi IS NOT NULL),
      100.0*count(*) FILTER (WHERE a.doi IS NOT NULL)/count(*),
      100.0*count(*) FILTER (WHERE b.doi IS NOT NULL)/count(*)
      FROM s LEFT JOIN r23 a USING (doi) LEFT JOIN r26 b USING (doi)""")
    tot, miss, add, c23, c26 = r
    log(f"\n  {lab}")
    log(f"    전체 {tot:,}  초기 미기재 {check(key + '_미기재', miss)}  "
        f"보완 {check(key + '_보완', add)}  "
        f"보완율 {check(key + '_보완율', pct(add, miss))}%")
    log(f"    기재율 2023 {c23:.1f}%   기재율 2026 {c26:.1f}%")

for yr in (2010, 2015, 2020):
    r = one(f"""SELECT count(*), count(*) FILTER (WHERE cc23=0),
      count(*) FILTER (WHERE cc23=0 AND cc26=1),
      100.0*avg(cc23), 100.0*avg(cc26) FROM s WHERE pub_year >= {yr}""")
    tot, miss, add, c23, c26 = r
    log(f"\n  저널별 하한과 {yr}년 중 늦은 해")
    log(f"    전체 {check(f'하한{yr}_N', tot)}  초기 미기재 {miss:,}  보완 {add:,}  "
        f"보완율 {check(f'하한{yr}_보완율', pct(add, miss))}%")
    log(f"    기재율 2023 {c23:.1f}%   기재율 2026 {c26:.1f}%")

r = one("""
WITH o AS (SELECT w.doi, max(j.oa_start) oa FROM
  (SELECT doi, upper(trim(t.s)) issn FROM w2023, UNNEST(str_split(issn,';')) t(s)) w
  JOIN jissn j USING (issn) GROUP BY w.doi)
SELECT count(*), count(*) FILTER (WHERE cc23=0), count(*) FILTER (WHERE cc23=0 AND cc26=1),
       100.0*avg(cc23), 100.0*avg(cc26)
FROM s JOIN o USING (doi) WHERE s.pub_year > o.oa""")
tot, miss, add, c23, c26 = r
log("\n  OA 전환연도 자체 제외")
log(f"    전체 {check('전환연도제외_N', tot)}  초기 미기재 {check('전환연도제외_미기재', miss)}  "
    f"보완 {check('전환연도제외_보완', add)}  "
    f"보완율 {check('전환연도제외_보완율', pct(add, miss))}%")
log(f"    기재율 2023 {c23:.1f}%   기재율 2026 {c26:.1f}%")

# 4.9절 본문
log("\n  4.9절 본문 수치")
r = one("""SELECT count(*) FROM s WHERE cc23=0""")[0]
con.execute(f"CREATE OR REPLACE TABLE vu23 AS SELECT DISTINCT doi FROM l2023 WHERE {CC_URL} AND coalesce(content_version,'') IN ('vor','unspecified')")
miss_vu = one("SELECT count(*) FROM s LEFT JOIN vu23 a USING (doi) WHERE a.doi IS NULL")[0]
log(f"    AM 제외 시 미기재 집단의 차이  {check('AM제외_미기재차', miss_vu - r)}")

con.execute(f"""CREATE OR REPLACE TABLE q AS
SELECT l.doi, lower(l.url) url, lower(coalesce(l.content_version,'')) cv
FROM l2026 l JOIN addx a USING (doi) WHERE {CCQ}""")
r = one(r"""
WITH d AS (SELECT doi,
   bool_or(regexp_matches(url, '^https?://(www\.)?creativecommons\.org/(licenses|publicdomain)/')) std,
   bool_or(cv IN ('vor','am')) vam FROM q GROUP BY doi)
SELECT count(*), count(*) FILTER (WHERE NOT vam), count(*) FILTER (WHERE NOT std) FROM d""")
tot, nvam, nstd = r
log(f"    unspecified 항목만으로 판정된 보완  {check('unspecified만_보완', nvam)}  "
    f"({check('unspecified만_비율', pct(nvam, tot, 1))}%)")
log(f"    비표준 URL 항목만으로 판정된 보완    {check('비표준URL만_보완', nstd)}")

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("표 S4. 집중도 분해")
log("=" * 72)
# 상위 5개 출판사는 번호를 박아 두지 않고 보완 건수로 직접 구한다.
top5 = [r[0] for r in con.execute("""
    SELECT member FROM s WHERE cc23=0 AND cc26=1 AND member IS NOT NULL
    GROUP BY member ORDER BY count(*) DESC LIMIT 5""").fetchall()]
TOP5 = "(" + ", ".join("'" + m + "'" for m in top5) + ")"
show("보완 상위 5개 출판사", f"""
SELECT any_value(publisher) 출판사, count(*) FILTER (WHERE cc23=0 AND cc26=1) 보완,
       count(*) FILTER (WHERE cc23=0) 미기재
FROM s WHERE member IN {TOP5} GROUP BY member ORDER BY 2 DESC""")
r = one(f"""SELECT
  count(*) FILTER (WHERE cc23=0) a,
  count(*) FILTER (WHERE cc23=0 AND cc26=1) b,
  count(*) FILTER (WHERE cc23=0 AND member IN {TOP5}) c,
  count(*) FILTER (WHERE cc23=0 AND member IS NULL) d,
  count(*) FILTER (WHERE cc23=0 AND member NOT IN {TOP5} AND member IS NOT NULL) e,
  count(*) FILTER (WHERE cc23=0 AND cc26=1 AND member NOT IN {TOP5} AND member IS NOT NULL) f,
  count(*) FILTER (WHERE cc23=0 AND cc26=1 AND member IN {TOP5}) g
FROM s""")
a, b, c, d, e, f_, g = r
log(f"  전체                      {check('집중_전체N', a)}  보완율 {pct(b, a)}%")
log(f"  상위 5개 및 member 미상 제외 {check('집중_제외후N', e)}  "
    f"보완율 {check('집중_제외후보완율', pct(f_, e))}%")
log(f"  상위 5개의 미기재 합        {check('집중_상위5미기재', c)}")
log(f"  member 미상               {check('집중_member미상', d)}")
log(f"\n  상위 5개의 보완 합          {check('상위5_보완합', g)}  "
    f"({check('상위5_보완비중', pct(g, b, 1))}%)")
log(f"  상위 5개가 차지하는 미기재 비중 {check('상위5_미기재비중', pct(c, a, 1))}%")

log("\n  4.4절 출판사별 월 집중 (CC가 처음 관찰된 연도판의 deposited 월)")
show("상위 5개 출판사의 최다 월", f"""
WITH ym AS (SELECT member, any_value(publisher) pub,
   substr(CAST(CASE WHEN cc24=1 THEN dep24 WHEN cc25=1 THEN dep25 ELSE dep26 END AS VARCHAR),1,7) m,
   count(*) n FROM addx WHERE member IN {TOP5} GROUP BY member, 3)
SELECT pub 출판사, m 최다월, n 건수,
       round(100.0*n/sum(n) OVER (PARTITION BY member),1) 비중 FROM ym
QUALIFY row_number() OVER (PARTITION BY member ORDER BY n DESC) = 1
ORDER BY 4 DESC""")

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("표 S5. 출판사 소재국별 미식별률")
log("=" * 72)
if not os.path.exists(DOAJ_C):
    log(f"  건너뜀 — 국가 정보 파일이 없다: {DOAJ_C}")
    log("  DOAJ 원본 덤프에서 ISSN과 Country of publisher 두 열을 뽑아 저장하면 계산된다.")
else:
    con.execute(f"""CREATE TABLE jc AS
    SELECT upper(trim(issn)) issn, any_value(c) country FROM
     (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e,
             "Country of publisher" c FROM read_csv_auto('{DOAJ_C}', header=true, all_varchar=true)),
     UNNEST([p,e]) t(issn) WHERE issn IS NOT NULL AND trim(issn)<>'' GROUP BY 1""")
    con.execute("""CREATE TABLE pc AS
    SELECT DISTINCT w.doi, j.country FROM
     (SELECT doi, upper(trim(t.s)) issn FROM w2023, UNNEST(str_split(issn,';')) t(s)) w
    JOIN jc j USING (issn) WHERE w.doi IN (SELECT doi FROM s)""")
    r = one("""SELECT count(DISTINCT doi),
      count(DISTINCT doi) FILTER (WHERE country IS NULL OR country=''),
      count(DISTINCT country) FROM pc""")
    log(f"  논문 {r[0]:,}  국가 결측 {check('국가결측', r[1])}  국가 수 {check('국가수', r[2])}")
    n20 = one("""SELECT count(*) FROM (SELECT country FROM pc JOIN s USING (doi)
                  GROUP BY country HAVING count(DISTINCT doi) >= 20000)""")[0]
    log(f"  논문 2만 건 이상 국가 {check('국가_2만이상', n20)}")
    show("상하위 6개국", """
    WITH t AS (SELECT p.country,
        count(DISTINCT s.doi) n,
        100.0*(1 - avg(s.cc23)) u23, 100.0*(1 - avg(s.cc26)) u26,
        100.0*count(*) FILTER (WHERE s.cc23=0 AND s.cc26=1)
          /nullif(count(*) FILTER (WHERE s.cc23=0),0) addr
      FROM s JOIN pc p USING (doi) GROUP BY p.country
      HAVING count(DISTINCT s.doi) >= 20000),
      r AS (SELECT *, row_number() OVER (ORDER BY u26) lo,
                      row_number() OVER (ORDER BY u26 DESC) hi FROM t)
    SELECT country 국가, n 논문수, round(u23,1) 미식별률_2023,
           round(u26,1) 미식별률_2026, round(addr,2) 보완율
    FROM r WHERE lo <= 6 OR hi <= 6 ORDER BY u26""")

log(f"\n완료. 결과: {OUT}")
logf.close()
