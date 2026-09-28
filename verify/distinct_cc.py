import duckdb
con = duckdb.connect()
print(con.execute("""SELECT count(DISTINCT doi) FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')""").fetchone())
