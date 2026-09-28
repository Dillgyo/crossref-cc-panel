import duckdb, csv
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")

print("[1. 2783-5502 저널의 누락 원인]")
con.execute("CREATE TABLE api AS SELECT * FROM read_csv_auto('D:/crossref/missing_dois.csv', header=true)")
dois = [r[0] for r in con.execute("SELECT doi FROM api WHERE issn='2783-5502' LIMIT 20").fetchall()]
print("  API DOI 예시:", dois[:3])
pref = dois[0].split('/')[0] if dois else None
for y in ("2023","2026"):
    r = con.execute(f"""SELECT count(*), any_value(issn), any_value(container_title), any_value(member)
      FROM read_parquet('D:/crossref/parquet/{y}/works/*.parquet') WHERE doi LIKE '{pref}/%'""").fetchone()
    print(f"  {y}년판 같은 접두사({pref}) 레코드:", r)
    r = con.execute(f"""SELECT count(*) FROM read_parquet('D:/crossref/parquet/{y}/works/*.parquet')
      WHERE issn LIKE '%2783-5502%'""").fetchone()
    print(f"  {y}년판 ISSN 2783-5502 레코드:", r)

print("\n[2. 표 S1 재계산 (이후 계속 80% 유지 기준)]")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
for r in con.execute("""
WITH y AS (SELECT member, any_value(publisher) AS pub, pub_year, count(*) AS n, avg(cc26) AS rate
           FROM s GROUP BY member, pub_year),
     big AS (SELECT member FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000),
     ok AS (SELECT member, pub_year, min(rate) OVER (PARTITION BY member ORDER BY pub_year
                ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS min_after
            FROM y WHERE n >= 100 AND member IN (SELECT member FROM big)),
     t AS (SELECT member, min(pub_year) FILTER (WHERE min_after >= 0.8) AS ty FROM ok GROUP BY member)
SELECT any_value(s.publisher) AS pub, t.ty AS 전환연도,
       round(100.0*avg(s.cc26),1) AS 이전기재율, count(*) AS 이전논문수
FROM t JOIN s ON s.member=t.member AND s.pub_year < t.ty
WHERE t.ty IS NOT NULL GROUP BY s.member, t.ty ORDER BY 2, 1""").fetchall(): print("  ", r)

print("\n[3. 주요 출판사 신규 출판분 기재율 (created >= 2023-04)]")
con.execute("""CREATE TABLE jissn AS
WITH j AS (SELECT "Journal ISSN (print version)" AS p, "Journal EISSN (online version)" AS e,
                  CAST("OA start" AS INT) AS oa FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true))
SELECT upper(trim(issn)) AS issn, min(greatest(oa,2003)) AS min_year
FROM j, UNNEST([p,e]) AS t(issn) WHERE issn IS NOT NULL AND trim(issn) <> '' GROUP BY 1""")
con.execute("""CREATE TABLE cc AS SELECT DISTINCT doi FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')""")
for r in con.execute("""
WITH n AS (SELECT DISTINCT w.doi, w.member, w.publisher FROM
  (SELECT doi, member, publisher, pub_year, created, upper(trim(t.s)) AS issn
   FROM read_parquet('D:/crossref/parquet/2026/works/*.parquet'), UNNEST(str_split(issn,';')) AS t(s)
   WHERE created >= '2023-04' AND pub_year >= 2023) w JOIN jissn j USING (issn) WHERE w.pub_year <= 2026)
SELECT any_value(publisher), count(*), round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc))/count(*),1)
FROM n WHERE member IN ('1968','1965','297','78') GROUP BY member ORDER BY 2 DESC""").fetchall(): print("  ", r)
