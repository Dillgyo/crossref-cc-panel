import duckdb
con = duckdb.connect()
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
for r in con.execute("""
SELECT member, any_value(publisher) AS pub, count(*) AS n,
       round(100.0*avg(cc23),1) AS rate23,
       round(100.0*avg(cc26),1) AS rate26,
       count(*) FILTER (WHERE cc23=0) AS missing,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) AS filled
FROM s WHERE member IN ('317','2373','78') GROUP BY member""").fetchall():
    print(" ", r)
