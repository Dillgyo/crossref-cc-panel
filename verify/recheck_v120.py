"""
크로스체크(2026-11-22) 중 AI 도구가 계산한 † 수치를 저자가 직접 재검증하는 스크립트.
Claude가 GPT의 질의를 보지 않고 저장소 정의(04_state_panel.py, 05_tables.py)만 따라 새로 작성했다.

실행
    python verify/recheck_v120.py
    (자료 위치는 CROSSREF_ROOT, 출력 위치는 CROSSREF_OUT으로 바꿀 수 있다. 기본값은 D:/crossref와 이 파일의 폴더)

입력
    D:/crossref/parquet/state_panel.parquet
    D:/crossref/parquet/{2023,2024,2025,2026}/{works,licenses}/*.parquet
    D:/crossref/doaj_panel_journals.csv
    D:/crossref/raw_trace_2026.csv        (G 묶음만)

출력
    화면과 recheck_out.txt
    각 줄 끝에 [일치] 또는 [불일치 기대 …]를 찍는다.

범위
    A 후속 등록·시간대    B member 결측·집중도    C 종점 2025년판
    D AIP 중간 변동       E content-version        F 신규 등록 비교
    G 탈락 사유(기존 산출물 확인)
    변동 분해(47.03/25.71/27.27%)와 순열(약 0.14%)은 이 스크립트에 넣지 않았다.
    verify/recheck_v120_part2.py에서 확인한다.
"""
import os
import time

import duckdb

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
P = f"{ROOT}/parquet"
DOAJ = f"{ROOT}/doaj_panel_journals.csv"
TMP = f"{ROOT}/_tmp"
OUTDIR = os.environ.get("CROSSREF_OUT", os.path.dirname(os.path.abspath(__file__)))
OUT = f"{OUTDIR}/recheck_out.txt"
os.makedirs(TMP, exist_ok=True)
os.makedirs(OUTDIR, exist_ok=True)

logf = open(OUT, "w", encoding="utf-8")
T0 = time.time()
RESULT = {"일치": 0, "불일치": 0}


def log(s=""):
    print(s, flush=True)
    logf.write(s + "\n")
    logf.flush()


def chk(label, val, exp, nd=None):
    """exp가 None이면 값만 출력. nd가 있으면 반올림 후 비교."""
    if exp is None:
        log(f"  {label}: {val:,}" if isinstance(val, int) else f"  {label}: {val}")
        return
    v = round(val, nd) if nd is not None else val
    ok = (v == exp)
    RESULT["일치" if ok else "불일치"] += 1
    shown = f"{v:,}" if isinstance(v, int) else f"{v}"
    mark = "[일치]" if ok else f"[불일치 기대 {exp}]"
    log(f"  {label}: {shown}  {mark}")


def one(q):
    return con.execute(q).fetchone()


con = duckdb.connect()
for q in ["SET threads=4", "SET memory_limit='6GB'",
          "SET preserve_insertion_order=false", f"SET temp_directory='{TMP}'"]:
    con.execute(q)

CC = "url ILIKE '%creativecommons.org%'"
ELIG = CC + " AND coalesce(content_version,'') IN ('vor','am','unspecified')"

con.execute(f"CREATE VIEW st AS SELECT * FROM read_parquet('{P}/state_panel.parquet')")
con.execute("CREATE VIEW s AS SELECT * FROM st WHERE in26=1")
for y in ("2023", "2024", "2025", "2026"):
    con.execute(f"CREATE VIEW w{y} AS SELECT * FROM read_parquet('{P}/{y}/works/*.parquet')")
    con.execute(f"CREATE VIEW l{y} AS SELECT * FROM read_parquet('{P}/{y}/licenses/*.parquet')")

log("=" * 72)
log("0. 기준값 (원고에 이미 있는 값으로 패널을 확인)")
log("=" * 72)
n, m, a = one("SELECT count(*), count(*) FILTER (WHERE cc23=0), "
              "count(*) FILTER (WHERE cc23=0 AND cc26=1) FROM s")
chk("고정 패널", n, 7215883)
chk("2023년판 미기재", m, 2944831)
chk("보완", a, 167779)

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("A. 후속 등록과 시간대 (3.2절, 4.2절, 4.5절, 5.3절)")
log("=" * 72)
con.execute("""CREATE TABLE t AS
SELECT doi, cc23, cc26, dep23, dep26,
       date_diff('second',
                 try_strptime(dep23, '%Y-%m-%dT%H:%M:%SZ'),
                 try_strptime(dep26, '%Y-%m-%dT%H:%M:%SZ')) d
FROM s""")
chk("deposited 해석 실패(결측·비표준) 건수", one("SELECT count(*) FROM t WHERE d IS NULL")[0], 0)
chk("문자열 비교와 시각 비교가 다른 건수",
    one("SELECT count(*) FROM t WHERE d IS NOT NULL AND ((dep26 > dep23) <> (d > 0))")[0], 0)
fwd = one("SELECT count(*) FROM t WHERE cc23=0 AND dep26 > dep23")[0]
chk("미기재 중 후속 등록 (dep26 > dep23)", fwd, 910393)
chk("† 그중 2026년판 deposited가 2023-04-01 이전",
    one("SELECT count(*) FROM t WHERE cc23=0 AND dep26 > dep23 AND dep26 < '2023-04-01'")[0], 22421)
chk("패널 역행 전체 (dep26 < dep23)", one("SELECT count(*) FROM t WHERE d < 0")[0], 402241)
chk("† 역행 중 정확히 -4시간 또는 -5시간",
    one("SELECT count(*) FROM t WHERE d IN (-14400, -18000)")[0], 402072)
p4, p5 = one("SELECT count(*) FILTER (WHERE d=14400), count(*) FILTER (WHERE d=18000) FROM t")
chk("† 정확히 +4시간", p4, 28071)
chk("† 정확히 +5시간", p5, 15167)
chk("† 정확히 +4·+5시간 합", p4 + p5, 43238)
pm = one("SELECT count(*) FROM t WHERE cc23=0 AND d IN (14400, 18000)")[0]
chk("† 그중 2023년판 미기재", pm, 21327)
chk("† 그중 보완", one("SELECT count(*) FROM t WHERE cc23=0 AND cc26=1 AND d IN (14400, 18000)")[0], 0)
chk("† 대칭 처리 시 후속 등록 집단 보완율(%)", 100.0 * a / (fwd - pm), 18.87, 2)
neg = one("SELECT count(*) FROM t WHERE cc23=0 AND dep26 < dep23")[0]
chk("미기재 중 역행", neg, 148327)
chk("역행 포함 시 보완율(%)", 100.0 * a / (fwd + neg), 15.85, 2)

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("B. member 결측과 집중도 (3.2절, 4.3절)")
log("=" * 72)
NULLM = "(member IS NULL OR trim(member) = '')"
chk("† member 결측 (패널)", one(f"SELECT count(*) FROM s WHERE {NULLM}")[0], 2524)
nm = one(f"SELECT count(*) FROM s WHERE {NULLM} AND cc23=0")[0]
chk("† member 결측 중 미기재", nm, 1810)
na = one(f"SELECT count(*) FROM s WHERE {NULLM} AND cc23=0 AND cc26=1")[0]
chk("† member 결측 미기재 중 보완", na, 0)
top = con.execute(f"""
SELECT member, any_value(publisher) pub, count(*) n
FROM s WHERE cc23=0 AND cc26=1 AND NOT {NULLM}
GROUP BY member ORDER BY n DESC LIMIT 5""").fetchall()
for mem, pub, k in top:
    log(f"    보완 상위: member {mem}  {pub}  {k:,}")
exp_top = [42339, 24232, 14096, 13786, 12412]
chk("보완 상위 5개 건수 목록 일치", [k for _, _, k in top] == exp_top, True)
tops = ",".join(f"'{mem}'" for mem, _, _ in top)
t5a = sum(k for _, _, k in top)
t5m = one(f"SELECT count(*) FROM s WHERE cc23=0 AND member IN ({tops})")[0]
chk("상위 5개 보완 합", t5a, 106865)
chk("상위 5개 미기재", t5m, 520303)
chk("상위 5개와 member 결측 제외 보완율(%)", 100.0 * (a - t5a - na) / (m - t5m - nm), 2.51, 2)

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("C. 종점을 2025년판으로 (4.5절)")
log("=" * 72)
a25 = one("SELECT count(*) FROM s WHERE cc23=0 AND cc25=1")[0]
chk("† 2025년판 종점 보완", a25, 123378)
chk("† 2025년판 종점 보완율(%)", 100.0 * a25 / m, 4.19, 2)
chk("† 그중 2026년판에 미기재", one("SELECT count(*) FROM s WHERE cc23=0 AND cc25=1 AND cc26=0")[0], 0)

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("D. AIP Publishing의 중간 변동 (4.5절, 5.2절)")
log("=" * 72)
aip = one("""SELECT member FROM s WHERE publisher ILIKE '%AIP Publishing%'
             GROUP BY member ORDER BY count(*) DESC LIMIT 1""")[0]
log(f"    AIP member = {aip}")
MID = ("cc23 = cc26 AND NOT (cc23 = cc24 AND cc24 = cc25 AND cc25 = cc26)")
chk("패널 전체 중간 변동", one(f"SELECT count(*) FROM s WHERE {MID}")[0], 2657)
r = one(f"""SELECT count(*), sum(cc23), sum(cc24), sum(cc25), sum(cc26)
            FROM s WHERE member = '{aip}'""")
chk("AIP 패널 레코드", r[0], 17511)
chk("AIP 판별 기재 (2023/2024/2025/2026)", tuple(int(x) for x in r[1:]), (2774, 119, 113, 16827))
chk("† AIP 중간 변동", one(f"SELECT count(*) FROM s WHERE member='{aip}' AND {MID}")[0], 2619)
con.execute(f"""CREATE TABLE aip1001 AS SELECT doi FROM s
                WHERE member='{aip}' AND cc23=1 AND cc24=0 AND cc25=0 AND cc26=1""")
chk("AIP 1001 패턴", one("SELECT count(*) FROM aip1001")[0], 2612)
chk("† AIP 1101 패턴",
    one(f"SELECT count(*) FROM s WHERE member='{aip}' AND cc23=1 AND cc24=1 AND cc25=0 AND cc26=1")[0], 7)
chk("† 1001 가운데 2024년판 라이선스 항목이 있는 DOI",
    one("SELECT count(DISTINCT doi) FROM l2024 WHERE doi IN (SELECT doi FROM aip1001)")[0], 0)
chk("† 1001 가운데 2025년판 라이선스 항목이 있는 DOI",
    one("SELECT count(DISTINCT doi) FROM l2025 WHERE doi IN (SELECT doi FROM aip1001)")[0], 0)

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("E. content-version 규칙 (4.5절)")
log("=" * 72)
con.execute("CREATE TABLE pd AS SELECT doi, cc23, cc26 FROM s")
con.execute(f"CREATE TABLE e23 AS SELECT DISTINCT doi FROM l2023 WHERE {ELIG} AND doi IN (SELECT doi FROM pd)")
chk("state의 cc23과 라이선스 파일 판정이 다른 건수",
    one("""SELECT count(*) FROM pd
           WHERE (cc23=1) <> (doi IN (SELECT doi FROM e23))""")[0], 0)
for y in ("2023", "2026"):
    con.execute(f"""CREATE TABLE v{y} AS SELECT DISTINCT doi FROM l{y}
                    WHERE {CC} AND content_version = 'vor' AND doi IN (SELECT doi FROM pd)""")
vm = one("SELECT count(*) FROM pd WHERE doi NOT IN (SELECT doi FROM v2023)")[0]
va = one("""SELECT count(*) FROM pd WHERE doi NOT IN (SELECT doi FROM v2023)
            AND doi IN (SELECT doi FROM v2026)""")[0]
chk("VoR만 인정 미기재", vm, 4482717)
chk("VoR만 인정 보완", va, 336258)
vh = one("""SELECT count(*) FROM pd WHERE doi NOT IN (SELECT doi FROM v2023)
            AND doi IN (SELECT doi FROM v2026) AND cc23=1""")[0]
chk("† VoR 보완 중 2023년판에 이미 적격 CC가 있던 건수", vh, 287206)
chk("† 그 비율(%)", 100.0 * vh / va, 85.4, 1)
vf = one("SELECT count(*) FROM pd WHERE cc23=0 AND doi IN (SELECT doi FROM v2026)")[0]
chk("† 기본 미기재 분모 고정, 2026년판 VoR 확인", vf, 49052)
chk("† 그 비율(%)", 100.0 * vf / m, 1.67, 2)
uo = one(f"""
WITH b AS (SELECT doi FROM pd WHERE cc23=0 AND cc26=1)
SELECT count(*) FROM (
  SELECT doi, bool_and(content_version = 'unspecified') only_u
  FROM l2026 WHERE {ELIG} AND doi IN (SELECT doi FROM b) GROUP BY doi)
WHERE only_u""")[0]
chk("보완 중 unspecified 항목만으로 판정", uo, 118398)
chk("그 비율(%)", 100.0 * uo / a, 70.6, 1)

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("F. 신규 등록 비교 (4.4절, 5.1절, 결론)")
log("=" * 72)
con.execute(f"""CREATE TABLE jrow AS
SELECT row_number() OVER () jid,
       upper(trim("Journal ISSN (print version)")) p,
       upper(trim("Journal EISSN (online version)")) e,
       CAST("OA start" AS INT) oa
FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true)""")
con.execute("""CREATE TABLE j2i AS SELECT jid, issn FROM jrow, UNNEST([p, e]) t(issn)
               WHERE issn IS NOT NULL AND trim(issn) <> ''""")
con.execute("""CREATE TABLE jissn AS SELECT i.issn, min(greatest(j.oa, 2003)) min_year
               FROM j2i i JOIN jrow j USING (jid) GROUP BY i.issn""")
con.execute("""CREATE TABLE nw AS
SELECT doi, min(pub_year) pub_year, min(created) created FROM
 (SELECT doi, pub_year, created, upper(trim(t.s)) issn
  FROM w2026, UNNEST(str_split(issn, ';')) t(s)) w
JOIN jissn j USING (issn)
WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026
GROUP BY doi HAVING min(created) >= '2023-04-01'""")
con.execute(f"CREATE TABLE c26n AS SELECT DISTINCT doi FROM l2026 WHERE {ELIG} AND doi IN (SELECT doi FROM nw)")
r = one("""SELECT count(*),
  count(*) FILTER (WHERE pub_year <= 2022),
  count(*) FILTER (WHERE pub_year <= 2022 AND doi IN (SELECT doi FROM c26n)),
  count(*) FILTER (WHERE pub_year >= 2023),
  count(*) FILTER (WHERE pub_year >= 2023 AND doi IN (SELECT doi FROM c26n)) FROM nw""")
chk("신규 등록 전체", r[0], 3357592)
chk("과거 출판분", r[1], 123309)
chk("과거 출판분 기재", r[2], 45257)
old_rate = 100.0 * r[2] / r[1]
chk("과거 출판분 기재율(%)", old_rate, 36.7, 1)
chk("2023년 이후 출판분", r[3], 3234283)
chk("2023년 이후 출판분 기재율(%)", 100.0 * r[4] / r[3], 85.0, 1)
wt = one("""
WITH o AS (SELECT pub_year, count(*) n FROM nw WHERE pub_year <= 2022 GROUP BY pub_year),
     pc AS (SELECT pub_year, avg(cc26) cov FROM s WHERE pub_year <= 2022 GROUP BY pub_year)
SELECT sum(o.n * pc.cov) / sum(o.n), sum(o.n),
       sum(o.n) FILTER (WHERE pc.cov IS NULL) FROM o LEFT JOIN pc USING (pub_year)""")
chk("과거 출판분 중 패널에 같은 출판연도가 없는 건수", int(wt[2] or 0), 0)
chk("† 출판연도 비중을 맞춘 고정 패널 2026년판 기재율(%)", 100.0 * wt[0], 59.7, 1)
chk("† 차이(%p)", 100.0 * wt[0] - old_rate, 23.0, 1)
log("    과거 출판분의 출판연도 분포 (2021·2022년의 합 44,373건 기대)")
for y, k in con.execute("SELECT pub_year, count(*) FROM nw WHERE pub_year <= 2022 GROUP BY 1 ORDER BY 1").fetchall():
    log(f"      {y}: {k:,}")
con.execute("""CREATE TABLE fy AS SELECT doi, min(y) fy FROM (
  SELECT doi, 2024 y FROM w2024 WHERE doi IN (SELECT doi FROM nw) UNION ALL
  SELECT doi, 2025 FROM w2025 WHERE doi IN (SELECT doi FROM nw) UNION ALL
  SELECT doi, 2026 FROM w2026 WHERE doi IN (SELECT doi FROM nw)) GROUP BY doi""")
for y in ("2024", "2025"):
    con.execute(f"CREATE TABLE c{y}n AS SELECT DISTINCT doi FROM l{y} WHERE {ELIG} AND doi IN (SELECT doi FROM nw)")
rows = con.execute("""
SELECT CASE WHEN n.pub_year <= 2022 THEN '과거' ELSE '최근' END g, f.fy, count(*) k,
  100.0 * avg(CASE f.fy WHEN 2024 THEN (n.doi IN (SELECT doi FROM c2024n))::INT
                        WHEN 2025 THEN (n.doi IN (SELECT doi FROM c2025n))::INT
                        ELSE (n.doi IN (SELECT doi FROM c26n))::INT END) first_rate,
  100.0 * avg((n.doi IN (SELECT doi FROM c26n))::INT) last_rate
FROM nw n JOIN fy f USING (doi) GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
mx = 0.0
for g, f, k, fr, lr in rows:
    log(f"    {g} 출판분 / 첫 관찰 {f}년판  {k:,}건  첫 관찰 {fr:.3f}%  2026년판 {lr:.3f}%  차이 {lr - fr:+.3f}%p")
    mx = max(mx, abs(lr - fr))
chk("† 여섯 집단의 첫 관찰판·2026년판 기재율 차이 최대(%p)", mx, 1.81, 2)

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("G. 2026년판 탈락 9,181건의 사유 (3.1절, 기존 산출물 확인)")
log("=" * 72)
rt = f"{ROOT}/raw_trace_2026.csv"
if os.path.exists(rt):
    cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{rt}', all_varchar=true)").fetchall()]
    log(f"    열: {cols}")
    total = one(f"SELECT count(*) FROM read_csv_auto('{rt}', all_varchar=true)")[0]
    log(f"    행 수: {total:,}")
    for c in cols:
        k = one(f'SELECT count(DISTINCT "{c}") FROM read_csv_auto(\'{rt}\', all_varchar=true)')[0]
        if 1 < k <= 12:
            log(f"    [{c}] 값별 건수 (기대: 원본 부재 5,101 / 출판연도 이탈 2,820 / 유형 변경 1,067 / ISSN 없음 193)")
            for v, kk in con.execute(f'SELECT "{c}", count(*) FROM read_csv_auto(\'{rt}\', all_varchar=true) GROUP BY 1 ORDER BY 2 DESC').fetchall():
                log(f"      {v}: {kk:,}")
else:
    log("    raw_trace_2026.csv가 없어 건너뜀")

log("\n" + "=" * 72)
log(f"요약: 일치 {RESULT['일치']}  불일치 {RESULT['불일치']}  ({time.time() - T0:.0f}초)")
log("불일치가 있으면 해당 줄의 계산값과 기대값을 Claude에게 보내 주세요.")
log("=" * 72)
