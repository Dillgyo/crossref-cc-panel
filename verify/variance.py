"""
보완 여부의 변동이 어느 단위에서 발생하는지 분산 분해로 확인한다.

왜 회귀가 아닌가
  대상은 표본이 아니라 정의된 코호트 전체이며 n이 294만이다. 이 크기에서는
  어떤 계수든 통상적인 유의수준을 넘으므로 유의성 검정이 정보를 주지 않는다.
  따라서 이 스크립트는 검정 통계량을 내지 않고, 보완 여부의 변동 가운데
  각 집단 구분이 설명하는 몫만 보고한다.

무엇을 재는가
  2023년 미기재 레코드 각각에 대해 y = 1(2026년 기재), 0(미기재)으로 둔다.
  y의 총제곱합을 집단 간과 집단 내로 나누고, 집단 간 몫을 다음 두 지표로 낸다.

    eta^2      = SS_between / SS_total
    epsilon^2  = (SS_between - df_between * MS_within) / SS_total

  eta^2은 집단 수가 많을수록 위로 치우치므로, 치우침을 뺀 epsilon^2을 함께 낸다.
  두 값이 크게 다르지 않으면 집단 수에서 온 값이 아니라는 뜻이다.

  비교하는 집단 구분
    출판사(member), DOAJ 저널, 저널명, 출판연도, 출판사 소재국,
    후속 등록 여부(dep26 > dep23)

  이어서 저널이 출판사 위에 무엇을 더 설명하는지(출판사 내 저널 간 몫)를 낸다.
  이 값이 작으면 보완 여부를 가르는 단위는 저널이 아니라 출판사다.

실행
  python 11_variance.py

입력
  D:/crossref/parquet/state_panel.parquet
  D:/crossref/parquet/2023/works/*.parquet
  D:/crossref/doaj_panel_journals.csv
  D:/crossref/doaj_country.csv        (없으면 소재국만 건너뛴다)

출력
  D:/crossref/variance_out.txt
"""
import os

import duckdb

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
P = os.environ.get("CROSSREF_PARQUET", f"{ROOT}/parquet")
DOAJ = os.environ.get("CROSSREF_DOAJ", f"{ROOT}/doaj_panel_journals.csv")
CTRY = os.environ.get("CROSSREF_DOAJ_COUNTRY", f"{ROOT}/doaj_country.csv")
OUT = os.environ.get("CROSSREF_VAR_OUT", f"{ROOT}/variance_out.txt")
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

con.execute(f"CREATE VIEW st AS SELECT * FROM read_parquet('{P}/state_panel.parquet')")
con.execute("CREATE VIEW s AS SELECT * FROM st WHERE in26=1")
con.execute(f"CREATE VIEW w2023 AS SELECT * FROM read_parquet('{P}/2023/works/*.parquet')")

# DOAJ 저널 키 — 05_tables.py와 같은 방식
con.execute(f"""CREATE TABLE jrow AS
SELECT row_number() OVER () jid, "Journal title" title,
       upper(trim("Journal ISSN (print version)")) p,
       upper(trim("Journal EISSN (online version)")) e
FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true)""")
con.execute("""CREATE TABLE j2i AS
SELECT jid, issn FROM jrow, UNNEST([p, e]) t(issn)
WHERE issn IS NOT NULL AND trim(issn) <> ''""")
con.execute("""CREATE TABLE dj AS
SELECT DISTINCT w.doi, m.jid FROM
 (SELECT doi, upper(trim(t.s)) issn FROM w2023, UNNEST(str_split(issn,';')) t(s)) w
JOIN j2i m USING (issn)
WHERE w.doi IN (SELECT doi FROM s)""")

# 분석 대상: 2023년 미기재 레코드. y = 2026년 기재 여부
con.execute("""CREATE TABLE base AS
SELECT doi, member, publisher, container_title, pub_year,
       CAST(cc26 AS INT) y,
       CASE WHEN dep26 > dep23 THEN 1 ELSE 0 END redeposit
FROM s WHERE cc23 = 0""")

HAS_CTRY = os.path.exists(CTRY)
if HAS_CTRY:
    con.execute(f"""CREATE TABLE ctry AS
SELECT upper(trim(t.issn)) issn, any_value(c) country FROM
 (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e,
         "Country of publisher" c
  FROM read_csv_auto('{CTRY}', header=true, all_varchar=true)),
 UNNEST([p, e]) t(issn)
WHERE issn IS NOT NULL AND trim(issn) <> '' GROUP BY 1""")
    con.execute("""CREATE TABLE doi2c AS
SELECT b.doi, any_value(c.country) country
FROM base b
JOIN (SELECT doi, upper(trim(t.s)) issn FROM w2023, UNNEST(str_split(issn,';')) t(s)) w
  ON w.doi = b.doi
JOIN ctry c USING (issn)
GROUP BY b.doi""")

N, PBAR = con.execute("SELECT count(*), avg(y) FROM base").fetchone()
SS_T = N * PBAR * (1.0 - PBAR)

log("=" * 76)
log("보완 여부의 분산 분해")
log("=" * 76)
log(f"\n  대상  2023년 미기재 {N:,}건   (원고 2,944,831)")
log(f"  보완  {con.execute('SELECT sum(y) FROM base').fetchone()[0]:,}건  "
    f"= {100*PBAR:.2f}%   (원고 5.70%)")
log(f"  총제곱합 SS_total = n·p(1-p) = {SS_T:,.1f}")
log("\n  유의성 검정은 내지 않는다. 표본이 아니라 코호트 전체이기 때문이다.")


def decomp(label, group_sql, from_sql="base"):
    """집단 간 제곱합을 구해 eta^2과 epsilon^2을 낸다."""
    r = con.execute(f"""
WITH g AS (SELECT {group_sql} AS gk, count(*) n_g, avg(y) p_g
           FROM {from_sql} WHERE {group_sql} IS NOT NULL GROUP BY 1)
SELECT count(*), sum(n_g), sum(n_g * (p_g - {PBAR})*(p_g - {PBAR}))
FROM g""").fetchone()
    k, n_used, ss_b = r[0], r[1], (r[2] or 0.0)
    # 결측 집단을 뺀 경우를 위해 해당 부분집합의 총제곱합을 다시 구한다
    ss_t = con.execute(f"""
SELECT count(*) * avg(y) * (1 - avg(y)) FROM {from_sql}
WHERE {group_sql} IS NOT NULL""").fetchone()[0]
    ss_w = ss_t - ss_b
    df_b, df_w = k - 1, n_used - k
    ms_w = ss_w / df_w if df_w > 0 else float("nan")
    eta2 = ss_b / ss_t if ss_t else float("nan")
    eps2 = (ss_b - df_b * ms_w) / ss_t if ss_t else float("nan")
    log(f"  {label:<26} 집단 {k:>7,}  대상 {n_used:>10,}  "
        f"eta^2 {100*eta2:>6.2f}%   epsilon^2 {100*eps2:>6.2f}%")
    return eta2, eps2, ss_b, ss_t


log("\n" + "=" * 76)
log("1. 어느 구분이 보완 여부의 변동을 설명하는가")
log("=" * 76)
log("")
decomp("출판사 (member)", "member")
decomp("DOAJ 저널", "d.jid", "base b JOIN dj d USING (doi)")
decomp("저널명 (container_title)", "container_title")
decomp("출판연도", "pub_year")
if HAS_CTRY:
    decomp("출판사 소재국", "c.country", "base b JOIN doi2c c USING (doi)")
else:
    log(f"  출판사 소재국               건너뜀 — 파일이 없다: {CTRY}")
decomp("후속 등록 여부", "redeposit")

log("\n  eta^2과 epsilon^2이 가깝다면 집단 수에서 온 값이 아니다.")

log("\n" + "=" * 76)
log("2. 저널은 출판사 위에 무엇을 더 설명하는가")
log("=" * 76)

r = con.execute(f"""
WITH b AS (SELECT b.doi, b.member, d.jid, b.y FROM base b JOIN dj d USING (doi)),
     tot AS (SELECT count(*) n, avg(y) p FROM b),
     bypub AS (SELECT member, count(*) n_g, avg(y) p_g FROM b GROUP BY 1),
     byjnl AS (SELECT jid, count(*) n_g, avg(y) p_g FROM b GROUP BY 1)
SELECT (SELECT n FROM tot), (SELECT p FROM tot),
       (SELECT sum(n_g*(p_g-(SELECT p FROM tot))*(p_g-(SELECT p FROM tot))) FROM bypub),
       (SELECT sum(n_g*(p_g-(SELECT p FROM tot))*(p_g-(SELECT p FROM tot))) FROM byjnl),
       (SELECT count(*) FROM bypub), (SELECT count(*) FROM byjnl)""").fetchone()
n2, p2, ssb_pub, ssb_jnl, k_pub, k_jnl = r
sst2 = n2 * p2 * (1 - p2)
log(f"\n  저널에 연결된 미기재 {n2:,}건 기준")
log(f"    출판사만                  eta^2 {100*ssb_pub/sst2:>6.2f}%   (집단 {k_pub:,})")
log(f"    저널 (출판사 구분 없이)     eta^2 {100*ssb_jnl/sst2:>6.2f}%   (집단 {k_jnl:,})")
log(f"    저널이 더 설명하는 몫                {100*(ssb_jnl-ssb_pub)/sst2:>6.2f}%p")
log("\n  이 증분이 작으면 보완 여부를 가르는 단위는 저널이 아니라 출판사다.")

log("\n" + "=" * 76)
log("3. 집중도")
log("=" * 76)

rows = con.execute("""
SELECT member, any_value(publisher) pub, sum(y) add_n
FROM base WHERE member IS NOT NULL GROUP BY member
HAVING sum(y) > 0 ORDER BY 3 DESC""").fetchall()
tot_add = sum(r[2] for r in rows)
cum = 0
marks = {}
for idx, (m, pub, a) in enumerate(rows, 1):
    cum += a
    for q in (50, 80, 90, 95):
        if q not in marks and cum >= tot_add * q / 100:
            marks[q] = idx
log(f"\n  보완이 1건 이상인 출판사 {len(rows):,}곳, 보완 합계 {tot_add:,}건")
for q in (50, 80, 90, 95):
    if q in marks:
        log(f"    보완의 {q}%를 차지하는 데 필요한 출판사 수  {marks[q]:,}곳")

log("\n" + "=" * 76)
log("4. 원고에 넣을 문장의 재료")
log("=" * 76)
log("""
  아래 형태로 한 문단을 씁니다. 실제 값은 위 출력에서 가져옵니다.

  본 연구는 정의된 코호트 전체를 관찰하므로 유의성 검정 대신 보완 여부의
  변동이 어느 단위에서 발생하는지를 분산 분해로 확인하였다. 2023년 미기재
  레코드의 보완 여부에서 출판사 구분이 설명하는 몫은 eta^2 = __%였고,
  DOAJ 저널 구분은 __%, 출판연도는 __%였다. 저널을 출판사 위에 더해도
  설명되는 몫은 __%p만 늘어난다. 즉 보완 여부를 가르는 단위는 개별 논문이나
  저널이 아니라 출판사다.
""")

log(f"\n완료. 결과: {OUT}")
logf.close()
