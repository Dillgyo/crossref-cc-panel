"""
member 유지 집합에서 상위 5개 출판사의 보완 집중도를 다시 계산한다.

배경
  표 S4와 4.4절의 집중도는 2023년판 member를 기준으로 삼는다.
  그런데 보완 레코드의 9.4%는 2026년판에서 member가 바뀌었으므로,
  "2023년판 member에 귀속된 보완"과 "그 출판사가 수행한 보완"이 같지 않다.
  member가 두 판에서 같은 레코드만 남기고 같은 계산을 다시 해서,
  집중도 결론이 member 변경에 좌우되지 않음을 보인다.

실행
  python 10_member_stable.py

입력
  D:/crossref/parquet/state_panel.parquet
  D:/crossref/parquet/2026/works/*.parquet   (2026년판 member)

출력
  D:/crossref/member_stable_out.txt
"""
import os

import duckdb

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
P = os.environ.get("CROSSREF_PARQUET", f"{ROOT}/parquet")
OUT = os.environ.get("CROSSREF_MS_OUT", f"{ROOT}/member_stable_out.txt")
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

# 원고에 이미 적힌 값. 다르게 나오면 바로 보이게 둔다.
EXPECTED = {
    "보완_전체": 167779,
    "member_유지": 151997,
    "member_변경률": 9.4,
    "상위5_전체기준": 63.7,
    "상위5_유지기준": 66.7,
}


def pct(num, den, digits=1):
    return round(100.0 * num / den, digits) if den else 0.0


def check(key, value, digits=None):
    if key not in EXPECTED:
        return f"{value:,}" if isinstance(value, int) else f"{value}"
    exp = EXPECTED[key]
    v = round(value, digits) if digits is not None else value
    shown = f"{v:,}" if isinstance(v, int) else f"{v}"
    return shown + "  " + ("일치" if v == exp else f"불일치 (원고 {exp:,})")


def show(title, q):
    cur = con.execute(q)
    log(f"\n[{title}]")
    log("  " + " | ".join(d[0] for d in cur.description))
    for r in cur.fetchall():
        log("  " + " | ".join(
            "" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) for v in r))


con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1")
con.execute(f"""CREATE TABLE m26 AS
SELECT doi, any_value(member) member26
FROM read_parquet('{P}/2026/works/*.parquet') GROUP BY doi""")

# 보완 = 2023년판 미기재, 2026년판 기재
con.execute("""CREATE TABLE addx AS
SELECT s.doi, s.member member23, s.publisher, m.member26
FROM s LEFT JOIN m26 m USING (doi)
WHERE s.cc23 = 0 AND s.cc26 = 1""")

log("=" * 70)
log("1. 보완 레코드의 member 변경")
log("=" * 70)

r = con.execute("""
SELECT count(*) n_all,
       count(*) FILTER (WHERE member23 IS NOT NULL AND member26 IS NOT NULL
                          AND member23 = member26) n_same,
       count(*) FILTER (WHERE member23 IS NOT NULL AND member26 IS NOT NULL
                          AND member23 <> member26) n_diff,
       count(*) FILTER (WHERE member23 IS NULL OR member26 IS NULL) n_null
FROM addx""").fetchone()
n_all, n_same, n_diff, n_null = r
log(f"\n  보완 전체            {check('보완_전체', n_all)}")
log(f"  member 동일          {check('member_유지', n_same)}  ({pct(n_same, n_all)}%)")
log(f"  member 변경          {n_diff:,}  ({pct(n_diff, n_all)}%)")
log(f"  어느 한쪽 member 없음 {n_null:,}  ({pct(n_null, n_all)}%)")
log(f"\n  member 변경률(변경 + 결측) {check('member_변경률', pct(n_diff + n_null, n_all), 1)}%")

log("\n" + "=" * 70)
log("2. 상위 5개 출판사 — 두 기준 비교")
log("=" * 70)

# (가) 원고 기준: 2023년판 member로 상위 5개를 정하고 보완 전체를 분모로 한다
top5_all = [r[0] for r in con.execute("""
SELECT member23 FROM addx WHERE member23 IS NOT NULL
GROUP BY member23 ORDER BY count(*) DESC LIMIT 5""").fetchall()]
T5A = "(" + ", ".join("'" + m + "'" for m in top5_all) + ")"

show("가. 2023년판 member 기준 상위 5개 (원고의 기준)", f"""
SELECT member23 member, any_value(publisher) 출판사, count(*) 보완건수,
       round(100.0*count(*)/{n_all}, 1) 보완내비중
FROM addx WHERE member23 IN {T5A} GROUP BY member23 ORDER BY 3 DESC""")

g_all = con.execute(
    f"SELECT count(*) FROM addx WHERE member23 IN {T5A}").fetchone()[0]
log(f"\n  상위 5개의 보완 합 {g_all:,} / 보완 전체 {n_all:,} = {check('상위5_전체기준', pct(g_all, n_all), 1)}%")

# (나) member 유지 집합만으로 다시 정한다
top5_st = [r[0] for r in con.execute("""
SELECT member23 FROM addx
WHERE member23 IS NOT NULL AND member26 IS NOT NULL AND member23 = member26
GROUP BY member23 ORDER BY count(*) DESC LIMIT 5""").fetchall()]
T5S = "(" + ", ".join("'" + m + "'" for m in top5_st) + ")"

show("나. member 유지 집합 안에서 다시 정한 상위 5개", f"""
SELECT member23 member, any_value(publisher) 출판사, count(*) 보완건수,
       round(100.0*count(*)/{n_same}, 1) 유지집합내비중
FROM addx
WHERE member23 = member26 AND member23 IS NOT NULL AND member26 IS NOT NULL
  AND member23 IN {T5S}
GROUP BY member23 ORDER BY 3 DESC""")

g_st = con.execute(f"""
SELECT count(*) FROM addx
WHERE member23 = member26 AND member23 IS NOT NULL AND member26 IS NOT NULL
  AND member23 IN {T5S}""").fetchone()[0]
log(f"\n  상위 5개의 보완 합 {g_st:,} / member 유지 {n_same:,} = {check('상위5_유지기준', pct(g_st, n_same), 1)}%")

log(f"\n  상위 5개 출판사 목록이 두 기준에서 같은가: "
    f"{'같다' if set(top5_all) == set(top5_st) else '다르다'}")
if set(top5_all) != set(top5_st):
    log(f"    2023년판 기준만: {sorted(set(top5_all) - set(top5_st))}")
    log(f"    유지집합 기준만: {sorted(set(top5_st) - set(top5_all))}")

log("\n" + "=" * 70)
log("3. 원고에 넣을 문장")
log("=" * 70)
log(f"""
  보완 {n_all:,}건 가운데 2023년판과 2026년판의 member가 같은 {n_same:,}건
  ({pct(n_same, n_all)}%)만으로 다시 집계하여도 상위 5개 출판사가 차지하는 비중은
  {pct(g_st, n_same)}%로, 전체 기준의 {pct(g_all, n_all)}%와 크게 다르지 않았다.
  따라서 4.4절의 집중 양상은 member 변경에 좌우된 것이 아니다.
""")
log("  ※ 위 두 비율이 크게 갈리면 이 문장을 쓰지 말고 알려 주십시오.")

log(f"\n완료. 결과: {OUT}")
logf.close()
