import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
con.execute("""CREATE TABLE jissn AS
WITH j AS (SELECT "Journal ISSN (print version)" AS p, "Journal EISSN (online version)" AS e,
                  CAST("OA start" AS INT) AS oa FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true))
SELECT upper(trim(issn)) AS issn, min(greatest(oa,2003)) AS min_year
FROM j, UNNEST([p,e]) AS t(issn) WHERE issn IS NOT NULL AND trim(issn) <> '' GROUP BY 1""")
con.execute("""CREATE TABLE new26 AS
SELECT DISTINCT w.doi, w.member, w.publisher, w.pub_year
FROM (SELECT doi, member, publisher, pub_year, created, upper(trim(t.s)) AS issn
      FROM read_parquet('D:/crossref/parquet/2026/works/*.parquet'),
           UNNEST(str_split(issn,';')) AS t(s) WHERE created >= '2023-05') w
JOIN jissn j USING (issn) WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026""")
con.execute("""CREATE TABLE cc AS SELECT DISTINCT doi FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')""")

print("[동일 출판사 내 신규출판 vs 과거출판 신규등록 (backfile 500건 이상)]")
for r in con.execute("""
SELECT any_value(publisher) AS pub,
       count(*) FILTER (WHERE pub_year >= 2023) AS 신규출판,
       round(100.0*count(*) FILTER (WHERE pub_year >= 2023 AND doi IN (SELECT doi FROM cc))
             / nullif(count(*) FILTER (WHERE pub_year >= 2023),0),1) AS 신규율,
       count(*) FILTER (WHERE pub_year < 2023) AS 과거등록,
       round(100.0*count(*) FILTER (WHERE pub_year < 2023 AND doi IN (SELECT doi FROM cc))
             / nullif(count(*) FILTER (WHERE pub_year < 2023),0),1) AS 과거율
FROM new26 GROUP BY member HAVING count(*) FILTER (WHERE pub_year < 2023) >= 500
   AND count(*) FILTER (WHERE pub_year >= 2023) >= 500
ORDER BY 4 DESC LIMIT 20""").fetchall(): print("  ", r)

print("\n[출판사별 차이의 중앙값]")
for r in con.execute("""
WITH t AS (SELECT member,
  100.0*count(*) FILTER (WHERE pub_year>=2023 AND doi IN (SELECT doi FROM cc))/nullif(count(*) FILTER (WHERE pub_year>=2023),0) AS a,
  100.0*count(*) FILTER (WHERE pub_year<2023 AND doi IN (SELECT doi FROM cc))/nullif(count(*) FILTER (WHERE pub_year<2023),0) AS b
  FROM new26 GROUP BY member
  HAVING count(*) FILTER (WHERE pub_year<2023) >= 100 AND count(*) FILTER (WHERE pub_year>=2023) >= 100)
SELECT count(*) AS 출판사수, round(median(a),1) AS 신규율중앙값, round(median(b),1) AS 과거율중앙값,
       round(median(a-b),1) AS 차이중앙값, count(*) FILTER (WHERE a > b) AS 신규가더높은곳
FROM t""").fetchall(): print("  ", r)

print("\n[판정 규칙 민감도: 2023 미기재 대비 보완율]")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
for lab, cond in [("VoR만","content_version='vor'"),
                  ("VoR+unspecified","content_version IN ('vor','unspecified')"),
                  ("VoR+AM+unspecified (본 분석)","content_version IN ('vor','am','unspecified')"),
                  ("tdm 포함","1=1")]:
    for y in ("2023","2026"):
        con.execute(f"""CREATE OR REPLACE TABLE t{y} AS SELECT DISTINCT doi FROM
        read_parquet('D:/crossref/parquet/{y}/licenses/*.parquet')
        WHERE url ILIKE '%creativecommons.org%' AND ({cond})""")
    r = con.execute("""SELECT count(*) FILTER (WHERE a.doi IS NULL),
        count(*) FILTER (WHERE a.doi IS NULL AND b.doi IS NOT NULL)
        FROM s LEFT JOIN t2023 a USING (doi) LEFT JOIN t2026 b USING (doi)""").fetchone()
    print(f"  {lab}: 미기재 {r[0]:,} / 보완 {r[1]:,} / {100*r[1]/r[0]:.2f}%")
