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

# 2026 스냅숏에만 있는 신규 등록분 (2023 패널에 없는 DOI)
con.execute("""
CREATE TABLE new26 AS
SELECT DISTINCT w.doi, w.member, w.publisher, w.pub_year
FROM (SELECT doi, member, publisher, pub_year, created, upper(trim(s)) AS issn
      FROM read_parquet('D:/crossref/parquet/2026/works/*.parquet'),
           UNNEST(str_split(issn, ';')) AS t(s)
      WHERE created >= '2023-05') w
JOIN panel p USING (issn)
WHERE w.pub_year >= p.min_year AND w.pub_year <= 2026
""")
con.execute("""
CREATE TABLE cc26 AS
SELECT DISTINCT doi FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
WHERE url ILIKE '%creativecommons.org%'
  AND coalesce(content_version,'') IN ('vor','am','unspecified')
""")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")

def show(title, q):
    cur = con.execute(q); cols=[d[0] for d in cur.description]
    print("\n["+title+"]"); print("  "+" | ".join(cols))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

show("1. 신규 등록분 전체", """
SELECT count(*) AS 신규논문, count(*) FILTER (WHERE doi IN (SELECT doi FROM cc26)) AS CC있음,
       round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc26))/count(*),1) AS 기재율
FROM new26""")

show("2. 출판사별: 옛 논문 보강률 vs 신규분 기재율", """
WITH old AS (SELECT member, count(*) FILTER (WHERE cc23=0) AS 비었음,
                    round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),1) AS 보강률,
                    round(100.0*avg(cc23),1) AS 기재율23
             FROM s GROUP BY member),
     nw AS (SELECT member, any_value(publisher) AS publisher, count(*) AS 신규수,
                   round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc26))/count(*),1) AS 신규기재율
            FROM new26 GROUP BY member)
SELECT nw.publisher, old.비었음, old.기재율23, old.보강률, nw.신규수, nw.신규기재율
FROM old JOIN nw USING (member) WHERE old.비었음 > 20000
ORDER BY old.비었음 DESC LIMIT 15""")

show("3. 보강된 라이선스의 start 날짜와 출판연도 관계", """
WITH b AS (SELECT s.doi, s.pub_year FROM s WHERE s.cc23=0 AND s.cc26=1),
     l AS (SELECT doi, min(start) AS start FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
           WHERE url ILIKE '%creativecommons.org%'
             AND coalesce(content_version,'') IN ('vor','am','unspecified')
           GROUP BY doi)
SELECT CASE WHEN l.start IS NULL THEN 'start 없음'
            WHEN CAST(substr(l.start,1,4) AS INT) <= b.pub_year THEN '출판연도 이전/같음 (소급)'
            WHEN CAST(substr(l.start,1,4) AS INT) >= 2023 THEN '2023년 이후 (기재 시점)'
            ELSE '그 사이' END AS 구분,
       count(*) AS 논문수
FROM b LEFT JOIN l USING (doi) GROUP BY 1 ORDER BY 2 DESC""")

show("4. 보강분 start 연도 상위 10개", """
WITH b AS (SELECT doi FROM s WHERE cc23=0 AND cc26=1),
     l AS (SELECT doi, min(start) AS start FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
           WHERE url ILIKE '%creativecommons.org%'
             AND coalesce(content_version,'') IN ('vor','am','unspecified')
           GROUP BY doi)
SELECT substr(l.start,1,4) AS start연도, count(*) AS 논문수
FROM b JOIN l USING (doi) GROUP BY 1 ORDER BY 2 DESC LIMIT 10""")
