import duckdb
con = duckdb.connect()
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
for y in ("2024","2025"):
    con.execute(f"CREATE TABLE t{y} AS SELECT * FROM read_csv_auto('D:/crossref/raw_trace_{y}.csv', header=true, all_varchar=true)")
print("[패널 내 중간 부재 185건의 원인]")
for r in con.execute("""
SELECT 판, 원인, count(*) n FROM (
  SELECT '2024년판' 판, t.원인 FROM t2024 t JOIN s ON lower(t.doi)=s.doi
  UNION ALL SELECT '2025년판', t.원인 FROM t2025 t JOIN s ON lower(t.doi)=s.doi)
GROUP BY 1,2 ORDER BY 1,3 DESC""").fetchall(): print("  ", r)
