import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
con.execute("""CREATE TABLE jissn AS
WITH j AS (SELECT "Journal ISSN (print version)" AS p, "Journal EISSN (online version)" AS e,
                  CAST("OA start" AS INT) AS oa FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true))
SELECT upper(trim(issn)) AS issn, min(greatest(oa,2003)) AS min_year, min(oa) AS oa_start
FROM j, UNNEST([p,e]) AS t(issn) WHERE issn IS NOT NULL AND trim(issn) <> '' GROUP BY 1""")
con.execute("""CREATE TABLE new26 AS
SELECT DISTINCT w.doi, w.pub_year, j.oa_start
FROM (SELECT doi, pub_year, created, upper(trim(t.s)) AS issn
      FROM read_parquet('D:/crossref/parquet/2026/works/*.parquet'),
           UNNEST(str_split(issn,';')) AS t(s) WHERE created >= '2023-04') w
JOIN jissn j USING (issn) WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026""")
con.execute("""CREATE TABLE cc AS SELECT DISTINCT doi FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')""")

def show(t,q):
    cur=con.execute(q); print("\n["+t+"]"); print("  "+" | ".join(d[0] for d in cur.description))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

show("1. 표 8 재계산 (created >= 2023-04)", """
SELECT CASE WHEN pub_year >= 2023 THEN '2023년 이후 출판분' ELSE '과거 출판분의 신규 등록' END AS 구분,
       count(*) AS 논문수,
       round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc))/count(*),1) AS 기재율
FROM new26 GROUP BY 1 ORDER BY 2 DESC""")
show("1-2. 전체", """
SELECT count(*) AS 전체, round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc))/count(*),1) AS 기재율 FROM new26""")

# Unpaywall 표본을 빠짐없이 분류
con.execute("""CREATE TABLE exn AS SELECT * FROM read_csv_auto('D:/crossref/external_check.csv', header=true)""")
con.execute("""CREATE TABLE exp AS SELECT * FROM read_csv_auto('D:/crossref/external_positive.csv', header=true)""")
show("2. 미기재 표본 500건 전수 분류", """
SELECT CASE WHEN license LIKE 'cc%' THEN 'CC 라이선스 확인'
            WHEN license IS NULL OR license = '' THEN '라이선스 정보 없음'
            ELSE '기타: ' || license END AS 구분, count(*) AS 건수
FROM exn GROUP BY 1 ORDER BY 2 DESC""")
show("3. 기재 표본 500건 전수 분류", """
SELECT CASE WHEN unpaywall_lic = crossref_lic THEN '동일 CC'
            WHEN unpaywall_lic LIKE 'cc%' THEN '다른 CC'
            WHEN unpaywall_lic IS NULL OR unpaywall_lic = '' THEN '라이선스 정보 없음'
            ELSE '기타: ' || unpaywall_lic END AS 구분, count(*) AS 건수
FROM exp GROUP BY 1 ORDER BY 2 DESC""")
show("4. 미기재 표본의 OA location 유형", """
SELECT coalesce(nullif(host,''),'(없음)') AS host_type, count(*) AS 건수 FROM exn GROUP BY 1 ORDER BY 2 DESC""")

show("5. 민감도: 전환연도 자체 제외 (pub_year > OA 시작연도)", """
WITH b AS (SELECT s.doi, s.cc23, s.cc26, s.pub_year, j.oa_start
  FROM read_parquet('D:/crossref/parquet/state_panel.parquet') s
  JOIN (SELECT doi, max(oa_start) AS oa_start FROM
        (SELECT w.doi, j.oa_start FROM
          (SELECT doi, upper(trim(t.s)) AS issn FROM read_parquet('D:/crossref/parquet/2023/works/*.parquet'),
           UNNEST(str_split(issn,';')) AS t(s)) w JOIN jissn j USING (issn)) GROUP BY doi) j USING (doi)
  WHERE s.in26=1)
SELECT '기본 (pub_year >= OA start)' AS 기준,
       count(*) FILTER (WHERE cc23=0) AS 미기재,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/count(*) FILTER (WHERE cc23=0),2) AS 보완율 FROM b
UNION ALL
SELECT '전환연도 제외 (pub_year > OA start)',
       count(*) FILTER (WHERE cc23=0),
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/count(*) FILTER (WHERE cc23=0),2)
FROM b WHERE pub_year > oa_start""")
