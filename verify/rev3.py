import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
con.execute("""CREATE TABLE jissn AS
WITH j AS (SELECT row_number() OVER () AS jid, "Journal ISSN (print version)" AS p,
                  "Journal EISSN (online version)" AS e, CAST("OA start" AS INT) AS oa,
                  "Added on Date" AS added
           FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true))
SELECT jid, upper(trim(issn)) AS issn, greatest(oa,2003) AS min_year FROM j, UNNEST([p,e]) AS t(issn)
WHERE issn IS NOT NULL AND trim(issn) <> ''""")
con.execute("""CREATE TABLE new26 AS
SELECT DISTINCT w.doi, w.member, w.publisher, w.pub_year
FROM (SELECT doi, member, publisher, pub_year, created, upper(trim(t.s)) AS issn
      FROM read_parquet('D:/crossref/parquet/2026/works/*.parquet'),
           UNNEST(str_split(issn,';')) AS t(s) WHERE created >= '2023-04') w
JOIN jissn j USING (issn) WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026""")
con.execute("""CREATE TABLE cc AS SELECT DISTINCT doi FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')""")

print("[1. 구성효과 분해 (직접표준화)]")
for r in con.execute("""
WITH t AS (SELECT member,
    count(*) FILTER (WHERE pub_year>=2023) AS n_new,
    count(*) FILTER (WHERE pub_year<2023) AS n_old,
    1.0*count(*) FILTER (WHERE pub_year>=2023 AND doi IN (SELECT doi FROM cc))/nullif(count(*) FILTER (WHERE pub_year>=2023),0) AS r_new,
    1.0*count(*) FILTER (WHERE pub_year<2023 AND doi IN (SELECT doi FROM cc))/nullif(count(*) FILTER (WHERE pub_year<2023),0) AS r_old
  FROM new26 GROUP BY member),
  ok AS (SELECT * FROM t WHERE r_new IS NOT NULL AND r_old IS NOT NULL)
SELECT count(*) AS 출판사수,
  round(100.0*sum(n_new*r_new)/sum(n_new),1) AS 신규_실제,
  round(100.0*sum(n_old*r_old)/sum(n_old),1) AS 과거_실제,
  round(100.0*sum(n_old*r_new)/sum(n_old),1) AS 신규율을_과거구성에적용,
  round(100.0*sum(n_new*r_old)/sum(n_new),1) AS 과거율을_신규구성에적용
FROM ok""").fetchall(): print("  ", r)

print("\n[2. 224종 포함 시 민감도 — 별도 계산 필요 여부 확인]")
for r in con.execute("""SELECT count(*) FROM jissn""").fetchall(): print("  모집단 ISSN:", r)

print("\n[3. start 날짜 배타적 3구간 재계산]")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
for r in con.execute("""
WITH b AS (SELECT doi, pub_year FROM s WHERE cc23=0 AND cc26=1),
     l AS (SELECT doi, min(start) AS st FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
           WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')
           GROUP BY doi)
SELECT CASE WHEN l.st IS NULL THEN 'start 없음'
            WHEN CAST(substr(l.st,1,4) AS INT) <= b.pub_year THEN 'A: start연도 <= 출판연도'
            WHEN CAST(substr(l.st,1,4) AS INT) < 2023 THEN 'B: 출판연도 < start연도 < 2023'
            ELSE 'C: start연도 >= 2023' END AS 구분, count(*) AS 논문수
FROM b LEFT JOIN l USING (doi) GROUP BY 1 ORDER BY 2 DESC""").fetchall(): print("  ", r)

print("\n[4. 신규 DOI의 member 귀속: 2026 값 사용 확인]")
for r in con.execute("""SELECT count(*) AS 신규DOI, count(DISTINCT member) AS member수 FROM new26""").fetchall():
    print("  ", r)
