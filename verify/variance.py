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

  저널이 둘 이상의 member에 걸치는 경우 레코드가 가장 많은 member에 배정한다. 임의로 고르면
  실행마다 값이 달라진다. 무작위 재배치는 시드를 고정하여 10회 반복한다.

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

# 본문에 적을 값
EXPECTED = {
    "N": 2944831, "보완": 167779, "보완율": 5.70,
    "eta_출판사": 47.09, "eta_저널": 72.74, "eta_저널명": 73.15,
    "eta_출판연도": 1.22, "eta_후속등록": 13.50,
    # 중첩 분해 (2절) — 저널의 소속 출판사를 최빈 member로 고정한 뒤 확정한다
    "중첩_출판사": 47.09,
    "집중_50": 4, "집중_80": 20, "집중_90": 61, "집중_95": 109,
}


def check(key, value, digits=None):
    if key not in EXPECTED:
        return f"{value:,}" if isinstance(value, int) else f"{value}"
    exp = EXPECTED[key]
    v = round(value, digits) if digits is not None else value
    shown = f"{v:,}" if isinstance(v, int) else f"{v}"
    return shown + ("  일치" if v == exp else f"  불일치 (원고 {exp})")


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
    key = {"출판사 (member)": "eta_출판사", "DOAJ 저널": "eta_저널",
           "저널명 (container_title)": "eta_저널명", "출판연도": "eta_출판연도",
           "후속 등록 여부": "eta_후속등록"}.get(label)
    mark = check(key, round(100*eta2, 2), 2) if key else f"{100*eta2:.2f}"
    log(f"  {label:<26} 집단 {k:>7,}  대상 {n_used:>10,}  "
        f"eta^2 {mark}   epsilon^2 {100*eps2:>6.2f}%")
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

# 저널이 출판사 안에 온전히 들어가는지 먼저 본다
con.execute("""CREATE TABLE bj AS
SELECT b.doi, b.member, d.jid, b.y FROM base b JOIN dj d USING (doi)
WHERE b.member IS NOT NULL""")
nest = con.execute("""
SELECT count(*), count(*) FILTER (WHERE k > 1) FROM
 (SELECT jid, count(DISTINCT member) k FROM bj GROUP BY jid)""").fetchone()
log(f"\n  저널 {nest[0]:,}종 가운데 두 개 이상의 member에 걸친 저널 {nest[1]:,}종")
log("  이 수가 작으면 저널은 출판사 안에 중첩된다고 보고 삼분할 수 있다.")
log("  걸쳐 있는 저널은 레코드가 가장 많은 member에 배정한다(동수이면 member 번호가 작은 쪽).")

r = con.execute("""
WITH tot AS (SELECT count(*) n, avg(y) p FROM bj),
     pub AS (SELECT member, count(*) n_p, avg(y) p_p FROM bj GROUP BY 1),
     -- 둘 이상의 member에 걸친 저널은 레코드가 가장 많은 member에 배정한다
     jmode AS (SELECT jid, member FROM
                (SELECT jid, member, count(*) c,
                        row_number() OVER (PARTITION BY jid ORDER BY count(*) DESC, member) rn
                 FROM bj GROUP BY jid, member) WHERE rn = 1),
     jnl AS (SELECT b.jid, m.member, count(*) n_j, avg(b.y) p_j
             FROM bj b JOIN jmode m USING (jid) GROUP BY 1, 2)
SELECT (SELECT n FROM tot), (SELECT p FROM tot),
       (SELECT sum(n_p*(p_p-(SELECT p FROM tot))*(p_p-(SELECT p FROM tot))) FROM pub),
       (SELECT sum(j.n_j*(j.p_j-p.p_p)*(j.p_j-p.p_p)) FROM jnl j JOIN pub p USING (member)),
       (SELECT count(*) FROM pub), (SELECT count(*) FROM jnl)""").fetchone()
n2, p2, ss_pub, ss_jwp, k_pub, k_jnl = r
sst2 = n2 * p2 * (1 - p2)
ss_res = sst2 - ss_pub - ss_jwp
log(f"\n  대상 {n2:,}건, 출판사 {k_pub:,}곳, 저널 {k_jnl:,}종")
log(f"\n  [중첩 분해]")
log(f"    출판사 사이            {100*ss_pub/sst2:>6.2f}%")
log(f"    출판사 안의 저널 사이    {100*ss_jwp/sst2:>6.2f}%")
log(f"    저널 안의 잔차          {100*ss_res/sst2:>6.2f}%")
log(f"    합계                 {100*(ss_pub+ss_jwp+ss_res)/sst2:>6.2f}%")

# 무작위 귀무: 출판사 안에서 저널 표를 섞는다. 크기 분포는 그대로 둔다.
log(f"\n  [무작위 귀무 비교]")
log("    각 출판사 안에서 저널 표를 무작위로 섞어 같은 크기 분포를 유지한 채 다시 계산한다.")
log("    저널 구분이 아무 정보도 주지 않는다면 아래 값이 위의 '출판사 안의 저널 사이'와 같아야 한다.")
vals = []
NTRIAL = 10
for trial in range(NTRIAL):
    con.execute(f"SELECT setseed({0.10 + 0.07 * trial:.2f})")
    con.execute("DROP TABLE IF EXISTS perm")
    con.execute(f"""CREATE TABLE perm AS
WITH a AS (SELECT doi, member, y, row_number() OVER (PARTITION BY member ORDER BY random()) rn FROM bj),
     b AS (SELECT member, jid, row_number() OVER (PARTITION BY member ORDER BY jid, doi) rn FROM bj)
SELECT a.doi, a.member, b.jid, a.y FROM a JOIN b ON a.member=b.member AND a.rn=b.rn""")
    rr = con.execute(f"""
WITH pub AS (SELECT member, count(*) n_p, avg(y) p_p FROM perm GROUP BY 1),
     jmode AS (SELECT jid, member FROM
                (SELECT jid, member, count(*) c,
                        row_number() OVER (PARTITION BY jid ORDER BY count(*) DESC, member) rn
                 FROM perm GROUP BY jid, member) WHERE rn = 1),
     jnl AS (SELECT p.jid, m.member, count(*) n_j, avg(p.y) p_j
             FROM perm p JOIN jmode m USING (jid) GROUP BY 1, 2)
SELECT sum(j.n_j*(j.p_j-p.p_p)*(j.p_j-p.p_p)) FROM jnl j JOIN pub p USING (member)""").fetchone()[0]
    vals.append(100 * rr / sst2)
    log(f"    {trial+1:>2}회차  {100*rr/sst2:>6.2f}%")
vals.sort()
mid = vals[len(vals)//2] if len(vals) % 2 else (vals[len(vals)//2-1] + vals[len(vals)//2]) / 2
log(f"\n    무작위 {NTRIAL}회  최소 {vals[0]:.2f}%  중앙값 {mid:.2f}%  최대 {vals[-1]:.2f}%")
log(f"    실제 {100*ss_jwp/sst2:.2f}%  =  최대값의 {100*ss_jwp/sst2/vals[-1]:.0f}배")
log("    시드를 고정하였으므로 다시 실행해도 같은 값이 나온다.")

log(f"\n  [원고 대조]")
log(f"    출판사 사이            {check('중첩_출판사', round(100*ss_pub/sst2, 2), 2)}%")
log(f"    출판사 안의 저널 사이    {100*ss_jwp/sst2:.2f}%   ← 이 값을 원고에 적는다")
log(f"    저널 안의 잔차          {100*ss_res/sst2:.2f}%   ← 이 값을 원고에 적는다")

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
log("4. 원고 대조")
log("=" * 76)
log(f"""
  N               {check('N', N)}
  보완            {check('보완', int(round(N*PBAR)))}
  보완율          {check('보완율', round(100*PBAR, 2), 2)}%
""")

log(f"\n완료. 결과: {OUT}")
logf.close()
