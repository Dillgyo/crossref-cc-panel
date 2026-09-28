import duckdb
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
for r in con.execute("""
SELECT doi, issn, container_title, pub_year, created, deposited
FROM read_parquet('D:/crossref/parquet/2023/works/*.parquet')
WHERE container_title ILIKE '%Defensoria%' LIMIT 10""").fetchall(): print(" ", r)
print()
for r in con.execute("""
SELECT count(*), any_value(issn), any_value(container_title)
FROM read_parquet('D:/crossref/parquet/2026/works/*.parquet')
WHERE issn LIKE '%2674-5755%'""").fetchall(): print(" ", r)
