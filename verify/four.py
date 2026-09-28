import duckdb
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("CREATE TABLE api AS SELECT * FROM read_csv_auto('D:/crossref/missing_dois.csv', header=true)")
con.execute("""CREATE TABLE sus AS SELECT doi, issn, created FROM api
  WHERE jid IN (8266, 12592, 2634, 6558) AND created < '2023-04'""")
for y in ("2023","2026"):
    con.execute(f"""CREATE TABLE w{y} AS SELECT doi, issn AS ext_issn, container_title, pub_year, created, deposited
      FROM read_parquet('D:/crossref/parquet/{y}/works/*.parquet') WHERE doi IN (SELECT doi FROM sus)""")
print("[의심 DOI가 우리 추출에 있는지]")
for r in con.execute("""
SELECT s.issn AS DOAJ_ISSN, count(*) AS 의심DOI,
       count(w23.doi) AS 우리2023, count(w26.doi) AS 우리2026,
       any_value(w26.ext_issn) AS 우리ISSN, any_value(w26.container_title) AS 저널명
FROM sus s LEFT JOIN w2023 w23 ON w23.doi=s.doi LEFT JOIN w2026 w26 ON w26.doi=s.doi
GROUP BY s.issn""").fetchall(): print(" ", r)
print("\n[개별 예시]")
for r in con.execute("""
SELECT s.doi, s.created AS API_created, w26.ext_issn, w26.pub_year, w26.created AS 우리created
FROM sus s LEFT JOIN w2026 w26 ON w26.doi=s.doi ORDER BY s.issn LIMIT 12""").fetchall(): print(" ", r)
