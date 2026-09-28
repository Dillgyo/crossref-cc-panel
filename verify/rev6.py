import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
con.execute("CREATE VIEW l26 AS SELECT * FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')")

def show(t,q):
    cur=con.execute(q); print("\n["+t+"]"); print("  "+" | ".join(d[0] for d in cur.description))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

# M3: CC 판정에 걸리는 URL의 실제 구성
show("1. CC로 판정된 URL의 종류 (2026, vor·am·unspecified)", """
SELECT CASE WHEN url ILIKE '%creativecommons.org/licenses/%' THEN 'licenses/ 경로'
            WHEN url ILIKE '%creativecommons.org/publicdomain/%' THEN 'publicdomain/ 경로'
            ELSE '기타 creativecommons.org' END AS 구분,
       count(*) AS 행수, count(DISTINCT doi) AS DOI수
FROM l26 WHERE url ILIKE '%creativecommons.org%'
  AND coalesce(content_version,'') IN ('vor','am','unspecified')
GROUP BY 1 ORDER BY 2 DESC""")

show("2. 기타에 해당하는 URL 예시", """
SELECT url, count(*) AS 행수 FROM l26
WHERE url ILIKE '%creativecommons.org%' AND url NOT ILIKE '%/licenses/%' AND url NOT ILIKE '%/publicdomain/%'
  AND coalesce(content_version,'') IN ('vor','am','unspecified')
GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")

show("3. 비표준 표기 (경로에 대문자 또는 CC- 포함)", """
SELECT count(*) AS 행수, count(DISTINCT doi) AS DOI수 FROM l26
WHERE url ILIKE '%creativecommons.org%' AND (url LIKE '%/CC-%' OR url LIKE '%/BY%')
  AND coalesce(content_version,'') IN ('vor','am','unspecified')""")

# M6: 출판사·저널 단위 분포
show("4. 출판사별 보완율 분포 (2023 미기재 1,000건 이상)", """
WITH t AS (SELECT member, count(*) FILTER (WHERE cc23=0) AS n,
             100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0) AS rate
           FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 1000)
SELECT count(*) AS 출판사수, round(median(rate),2) AS 중앙값,
       round(quantile_cont(rate, 0.25),2) AS Q1, round(quantile_cont(rate, 0.75),2) AS Q3,
       round(quantile_cont(rate, 0.90),2) AS P90,
       count(*) FILTER (WHERE rate = 0) AS 보완0인곳 FROM t""")

show("5. 분모 하한을 바꿨을 때 (출판사 단위 중앙값)", """
WITH t AS (SELECT member, count(*) FILTER (WHERE cc23=0) AS n,
             100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0) AS rate
           FROM s GROUP BY member)
SELECT '100건 이상' AS 기준, count(*) FILTER (WHERE n>=100) AS 출판사수,
       round(median(rate) FILTER (WHERE n>=100),2) AS 중앙값 FROM t
UNION ALL SELECT '1,000건 이상', count(*) FILTER (WHERE n>=1000), round(median(rate) FILTER (WHERE n>=1000),2) FROM t
UNION ALL SELECT '10,000건 이상', count(*) FILTER (WHERE n>=10000), round(median(rate) FILTER (WHERE n>=10000),2) FROM t""")

show("6. 저널 단위 보완율 분포 (미기재 100건 이상)", """
WITH j AS (SELECT container_title, count(*) FILTER (WHERE cc23=0) AS n,
             100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0) AS rate
           FROM s GROUP BY 1 HAVING count(*) FILTER (WHERE cc23=0) >= 100)
SELECT count(*) AS 저널수, round(median(rate),2) AS 중앙값,
       round(quantile_cont(rate,0.75),2) AS Q3, round(quantile_cont(rate,0.95),2) AS P95 FROM j""")
