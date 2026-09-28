import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")

# tdm 포함 기준
for y in ("2023","2026"):
    con.execute(f"""
    CREATE TABLE loose{y} AS
    SELECT DISTINCT doi FROM read_parquet('D:/crossref/parquet/{y}/licenses/*.parquet')
    WHERE url ILIKE '%creativecommons.org%'
    """)

def show(title, q):
    cur = con.execute(q); cols=[d[0] for d in cur.description]
    print("\n["+title+"]"); print("  "+" | ".join(cols))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

show("1. 민감도: 판정 규칙(tdm 포함 여부)", """
SELECT '본 분석 (vor/am/unspecified)' AS 기준,
       count(*) FILTER (WHERE cc23=0) AS 비어있었음,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),2) AS 보강률
FROM s
UNION ALL
SELECT 'tdm 포함',
       count(*) FILTER (WHERE l23.doi IS NULL),
       round(100.0*count(*) FILTER (WHERE l23.doi IS NULL AND l26.doi IS NOT NULL)/nullif(count(*) FILTER (WHERE l23.doi IS NULL),0),2)
FROM s LEFT JOIN loose2023 l23 USING (doi) LEFT JOIN loose2026 l26 USING (doi)""")

show("2. 민감도: 하한 연도", """
SELECT '2003 (본 분석)' AS 하한, count(*) FILTER (WHERE cc23=0) AS 비어있었음,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),2) AS 보강률 FROM s
UNION ALL SELECT '2010', count(*) FILTER (WHERE cc23=0),
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),2) FROM s WHERE pub_year>=2010
UNION ALL SELECT '2015', count(*) FILTER (WHERE cc23=0),
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),2) FROM s WHERE pub_year>=2015
UNION ALL SELECT '2020', count(*) FILTER (WHERE cc23=0),
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),2) FROM s WHERE pub_year>=2020""")

show("3. 민감도: 출판사 쏠림 제거 (상위 5곳 뺀 보강률)", """
SELECT count(*) FILTER (WHERE cc23=0) AS 비어있었음,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),2) AS 보강률
FROM s WHERE member NOT IN ('276','2399','317','297','2373')""")

show("4. 저널 단위 분포 (2023년에 비어 있던 논문 100건 이상인 저널)", """
WITH j AS (SELECT container_title, count(*) FILTER (WHERE cc23=0) AS 비었음,
                  round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),1) AS 보강률
           FROM s GROUP BY 1 HAVING count(*) FILTER (WHERE cc23=0) >= 100)
SELECT CASE WHEN 보강률 = 0 THEN '0%' WHEN 보강률 < 5 THEN '0-5%'
            WHEN 보강률 < 50 THEN '5-50%' WHEN 보강률 < 95 THEN '50-95%' ELSE '95% 이상' END AS 구간,
       count(*) AS 저널수, sum(비었음) AS 해당논문수
FROM j GROUP BY 1 ORDER BY 1""")

show("5. 보강 없는 대형 출판사 vs 일괄 처리한 곳 (비었음 1만 건 이상)", """
SELECT any_value(publisher) AS publisher, count(*) FILTER (WHERE cc23=0) AS 비었음,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),1) AS 보강률
FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000
ORDER BY 3 DESC""")
