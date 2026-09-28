import duckdb
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
print("[출판사별 과소추정 폭]")
for r in con.execute("""
SELECT any_value(publisher) AS pub, count(*) AS n,
       round(100.0*avg(cc23),1) AS oa23,
       round(100.0*(1-avg(cc23)),1) AS gap23,
       round(100.0*(1-avg(cc26)),1) AS gap26
FROM s GROUP BY member HAVING count(*) >= 20000 ORDER BY 4 DESC LIMIT 20""").fetchall():
    print(" ", r)
print("[전체]")
for r in con.execute("""
SELECT round(100.0*(1-avg(cc23)),1) AS gap23, round(100.0*(1-avg(cc26)),1) AS gap26 FROM s""").fetchall():
    print(" ", r)
