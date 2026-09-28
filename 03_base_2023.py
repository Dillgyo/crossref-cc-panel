import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")

con.execute("""
CREATE TABLE panel AS
WITH j AS (SELECT "Journal ISSN (print version)" AS p, "Journal EISSN (online version)" AS e,
                  CAST("OA start" AS INT) AS oa
           FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true))
SELECT upper(trim(issn)) AS issn, min(greatest(oa, 2003)) AS min_year
FROM j, UNNEST([p, e]) AS t(issn)
WHERE issn IS NOT NULL AND trim(issn) <> '' GROUP BY 1
""")

con.execute("""
CREATE TABLE base AS
SELECT DISTINCT w.doi, w.member, w.publisher, w.pub_year
FROM (SELECT doi, member, publisher, pub_year, upper(trim(s)) AS issn
      FROM read_parquet('D:/crossref/parquet/2023/works/*.parquet'),
           UNNEST(str_split(issn, ';')) AS t(s)) w
JOIN panel p USING (issn)
WHERE w.pub_year >= p.min_year AND w.pub_year <= 2023
""")

con.execute("""
CREATE TABLE cc AS
SELECT DISTINCT doi FROM read_parquet('D:/crossref/parquet/2023/licenses/*.parquet')
WHERE url ILIKE '%creativecommons.org%'
  AND coalesce(content_version,'') IN ('vor','am','unspecified')
""")

def show(title, q):
    cur = con.execute(q); cols=[d[0] for d in cur.description]
    print("\n["+title+"]"); print("  "+" | ".join(cols))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

show("1. 2023 시점 전체", """
SELECT count(*) AS 논문수,
       count(*) FILTER (WHERE doi IN (SELECT doi FROM cc)) AS CC있음,
       round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc))/count(*),1) AS 기재율
FROM base""")

show("2. 출판연도 구간별", """
SELECT CASE WHEN pub_year < 2010 THEN '2003-2009' WHEN pub_year < 2015 THEN '2010-2014'
            WHEN pub_year < 2020 THEN '2015-2019' ELSE '2020-2023' END AS 구간,
       count(*) AS 논문수,
       round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc))/count(*),1) AS 기재율
FROM base GROUP BY 1 ORDER BY 1""")

show("3. 논문 수 상위 15개 출판사", """
SELECT member, any_value(publisher) AS publisher, count(*) AS 논문수,
       count(*) - count(*) FILTER (WHERE doi IN (SELECT doi FROM cc)) AS 비어있음,
       round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc))/count(*),1) AS 기재율
FROM base GROUP BY member ORDER BY 3 DESC LIMIT 15""")

show("4. 비어 있는 논문이 많은 출판사 10곳", """
SELECT member, any_value(publisher) AS publisher, count(*) AS 논문수,
       count(*) - count(*) FILTER (WHERE doi IN (SELECT doi FROM cc)) AS 비어있음,
       round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc))/count(*),1) AS 기재율
FROM base GROUP BY member ORDER BY 4 DESC LIMIT 10""")
