"""
표 9의 Wiley 2026년 미식별률 13.6%와 표 5 역산값 13.4%의 차이를 확인한다.

배경
  표 5에서 Wiley는 패널 163,698건, 2023년 미기재 27,931건, 보완 6,069건이다.
  소실이 없다면 2026년 미기재는 27,931 - 6,069 = 21,862건, 즉 13.4%가 된다.
  표 9의 실제 값은 13.6%이므로 그 차이만큼 소실이 있어야 한다.
  전체 소실이 1,012건뿐이므로, 한 출판사에 그 상당 부분이 몰려 있다는 뜻이 된다.
  사실이면 본문에 한 줄 적을 값어치가 있고, 아니면 어딘가 잘못된 것이다.

실행
  python 11_wiley_loss.py
"""
import os

import duckdb

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
P = os.environ.get("CROSSREF_PARQUET", f"{ROOT}/parquet")
OUT = os.environ.get("CROSSREF_WILEY_OUT", f"{ROOT}/wiley_loss_out.txt")
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

con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1")


def show(title, q):
    cur = con.execute(q)
    log(f"\n[{title}]")
    log("  " + " | ".join(d[0] for d in cur.description))
    for r in cur.fetchall():
        log("  " + " | ".join(
            "" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) for v in r))


log("=" * 72)
log("1. 소실 1,012건은 어느 출판사에 있는가")
log("=" * 72)

show("소실 상위 10개 출판사", """
SELECT any_value(publisher) 출판사, member,
       count(*) FILTER (WHERE cc23=1 AND cc26=0) 소실,
       count(*) 패널논문,
       count(*) FILTER (WHERE cc23=1) 기재_2023,
       round(100.0*count(*) FILTER (WHERE cc23=1 AND cc26=0)/nullif(count(*) FILTER (WHERE cc23=1),0), 3) 소실률
FROM s GROUP BY member
HAVING count(*) FILTER (WHERE cc23=1 AND cc26=0) > 0
ORDER BY 3 DESC LIMIT 10""")

tot = con.execute("SELECT count(*) FROM s WHERE cc23=1 AND cc26=0").fetchone()[0]
log(f"\n  전체 소실 {tot:,}건  (원고 1,012)")

log("\n" + "=" * 72)
log("2. Wiley 한 곳만 따로")
log("=" * 72)

show("Wiley (publisher 문자열로 찾는다)", """
SELECT any_value(publisher) 출판사, member, count(*) 패널논문,
       count(*) FILTER (WHERE cc23=1) 기재_2023,
       count(*) FILTER (WHERE cc23=0) 미기재_2023,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) 보완,
       count(*) FILTER (WHERE cc23=1 AND cc26=0) 소실,
       count(*) FILTER (WHERE cc26=0) 미기재_2026
FROM s WHERE publisher ILIKE '%Wiley%' GROUP BY member ORDER BY 3 DESC""")

r = con.execute("""
SELECT count(*), count(*) FILTER (WHERE cc23=0), count(*) FILTER (WHERE cc23=0 AND cc26=1),
       count(*) FILTER (WHERE cc23=1 AND cc26=0), count(*) FILTER (WHERE cc26=0)
FROM s WHERE publisher ILIKE '%Wiley%'""").fetchone()
n, miss23, add, loss, miss26 = r
if n:
    log(f"\n  패널 {n:,}  (표 5: 163,698)")
    log(f"  2023 미기재 {miss23:,}  (표 5: 27,931)")
    log(f"  보완 {add:,}  (표 5: 6,069)")
    log(f"  소실 {loss:,}   ← 확인 대상")
    log(f"\n  2026 미기재 실제        {miss26:,}  = {100.0*miss26/n:.2f}%  (표 9: 13.6%)")
    log(f"  소실을 0으로 놓은 계산   {miss23-add:,}  = {100.0*(miss23-add)/n:.2f}%  (심사자 역산: 13.4%)")
    log(f"  차이                    {miss26-(miss23-add):,}  = 소실 건수와 같아야 한다")
    log(f"\n  소실 {loss:,}건이 전체 소실에서 차지하는 비중 {100.0*loss/tot:.1f}%")

log("\n" + "=" * 72)
log("3. 원고에 넣을 문장")
log("=" * 72)
log(f"""
  소실 {tot:,}건 가운데 {loss:,}건({100.0*loss/tot:.1f}%)이 한 출판사(Wiley)에 몰려 있었다.
  그 출판사의 2023년 기재 {con.execute("SELECT count(*) FROM s WHERE publisher ILIKE '%Wiley%' AND cc23=1").fetchone()[0]:,}건에 대한 비율로는
  {100.0*loss/con.execute("SELECT count(*) FROM s WHERE publisher ILIKE '%Wiley%' AND cc23=1").fetchone()[0]:.2f}%다.
""")
log("  ※ 소실이 Wiley에 몰려 있지 않다면 위 문장을 쓰지 말고 출력을 알려 주십시오.")

log(f"\n완료. 결과: {OUT}")
logf.close()
