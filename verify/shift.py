import duckdb
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
print("[전환 출판연도: 2023 스냅숏 기준 vs 2026 스냅숏 기준]")
for r in con.execute("""
WITH y AS (SELECT member, any_value(publisher) AS pub, pub_year, count(*) AS n,
                  avg(cc23) AS r23, avg(cc26) AS r26 FROM s GROUP BY member, pub_year),
     big AS (SELECT member FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000)
SELECT any_value(pub) AS 출판사,
       min(pub_year) FILTER (WHERE r23>=0.8 AND n>=100) AS 기준2023,
       min(pub_year) FILTER (WHERE r26>=0.8 AND n>=100) AS 기준2026
FROM y WHERE member IN (SELECT member FROM big) GROUP BY member
HAVING 기준2026 IS NOT NULL ORDER BY 3""").fetchall(): print("  ", r)
