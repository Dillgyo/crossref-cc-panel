import duckdb
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
print("[member 9794 레코드 예시 - 2026]")
for r in con.execute("""
SELECT doi, issn, container_title, pub_year
FROM read_parquet('D:/crossref/parquet/2026/works/*.parquet')
WHERE member='9794' LIMIT 5""").fetchall(): print(" ", r)
print("\n[ISSN이 빈 레코드는 애초에 추출되지 않았으므로, 전체 규모 확인]")
for r in con.execute("""
SELECT count(*) AS ISSN있는_journal_article_2026
FROM read_parquet('D:/crossref/parquet/2026/works/*.parquet')""").fetchall(): print(" ", r)
