import duckdb
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
for y in ("2023","2026"):
    print("==", y)
    for r in con.execute(f"""
    SELECT count(*) AS member9794, 
           count(*) FILTER (WHERE doi LIKE '10.22501/%') AS prefix22501
    FROM read_parquet('D:/crossref/parquet/{y}/works/*.parquet') WHERE member='9794'""").fetchall():
        print("  ", r)
    for r in con.execute(f"""
    SELECT count(*) AS prefix_전체
    FROM read_parquet('D:/crossref/parquet/{y}/works/*.parquet') WHERE doi LIKE '10.22501/%'""").fetchall():
        print("  ", r)
    for r in con.execute(f"""
    SELECT count(*) AS issn2341
    FROM read_parquet('D:/crossref/parquet/{y}/works/*.parquet') WHERE issn LIKE '%2341-9687%'""").fetchall():
        print("  ", r)
