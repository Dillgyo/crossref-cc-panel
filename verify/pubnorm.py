import duckdb
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
cur = con.execute("""
SELECT member, any_value(publisher) AS publisher, count(*) AS n
FROM s WHERE lower(publisher) LIKE '%wolters%' OR lower(publisher) LIKE '%ovid%'
   OR lower(publisher) LIKE '%medknow%' OR lower(publisher) LIKE '%informa%'
   OR lower(publisher) LIKE '%taylor%' OR lower(publisher) LIKE '%springer%'
   OR lower(publisher) LIKE '%scielo%' OR lower(publisher) LIKE '%fapunifesp%'
   OR lower(publisher) LIKE '%aip%' OR lower(publisher) LIKE '%csic%'
   OR lower(publisher) LIKE '%openedition%'
GROUP BY member ORDER BY 3 DESC""")
for r in cur.fetchall(): print(r)
print()
print("member 하나당 publisher 문자열이 여러 개인 경우:")
for r in con.execute("""
SELECT member, count(DISTINCT publisher) AS 이름수, string_agg(DISTINCT publisher, ' / ') AS 이름들
FROM s GROUP BY member HAVING count(DISTINCT publisher) > 1 ORDER BY 2 DESC LIMIT 10""").fetchall():
    print(r)
