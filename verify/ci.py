import duckdb, math
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("CREATE TABLE exn AS SELECT * FROM read_csv_auto('D:/crossref/external_check.csv', header=true)")
con.execute("CREATE TABLE exp AS SELECT * FROM read_csv_auto('D:/crossref/external_positive.csv', header=true)")

def wilson(k, n, z=1.96):
    p = k/n; d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return 100*(c-h), 100*(c+h)

print("[외부 검증 표본의 신뢰구간 (Wilson 95%)]")
for lab, k, n in [("미기재 표본 CC 확인", 470, 500),
                  ("기재 표본 CC 일치", 489, 500),
                  ("기재 표본 CC 확인(종류 무관)", 497, 500)]:
    lo, hi = wilson(k, n)
    print(f"  {lab}: {100*k/n:.1f}% (95% CI {lo:.1f}–{hi:.1f})")

print("\n[미확인 저널 전수 조사는 표본이 아님 — DOI 대조만 표본]")
lo, hi = wilson(6488, 6588)
print(f"  스냅숏 이후 등록: 98.5% (95% CI {lo:.1f}–{hi:.1f})")

print("\n[모집단 대비 표본 비중]")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
for r in con.execute("""SELECT count(*) FILTER (WHERE cc23=0 AND cc26=0) AS 계속미기재,
  count(*) FILTER (WHERE cc26=1) AS 기재2026 FROM s""").fetchall(): print("  ", r)

print("\n[출판사 구성이 표본과 모집단에서 비슷한지]")
for r in con.execute("""
WITH pop AS (SELECT publisher, count(*) AS n FROM s WHERE cc23=0 AND cc26=0 GROUP BY 1),
     tot AS (SELECT sum(n) AS t FROM pop)
SELECT p.publisher, round(100.0*p.n/t.t,1) AS 모집단비율,
       (SELECT count(*) FROM exn e WHERE e.publisher = p.publisher) AS 표본건수
FROM pop p, tot t ORDER BY p.n DESC LIMIT 10""").fetchall(): print("  ", r)
