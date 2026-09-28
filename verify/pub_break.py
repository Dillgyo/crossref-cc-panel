import duckdb
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")

def show(title, q):
    cur = con.execute(q); cols=[d[0] for d in cur.description]
    print("\n["+title+"]"); print("  "+" | ".join(cols))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

show("1. 보강 논문이 많은 출판사 15곳", """
SELECT member, any_value(publisher) AS publisher,
       count(*) FILTER (WHERE cc23=0) AS 비어있었음,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) AS 보강됨,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),1) AS 보강률
FROM s GROUP BY member ORDER BY 4 DESC LIMIT 15""")

show("2. 보강 시점 분포 (보강된 논문 기준)", """
SELECT CASE WHEN cc24=1 THEN '2023-2024년 사이'
            WHEN cc25=1 THEN '2024-2025년 사이'
            ELSE '2025-2026년 사이' END AS 시기,
       count(*) AS 논문수
FROM s WHERE cc23=0 AND cc26=1 GROUP BY 1 ORDER BY 1""")

show("3. 상위 출판사별 보강 시점", """
SELECT any_value(publisher) AS publisher,
       count(*) FILTER (WHERE cc24=1) AS y24,
       count(*) FILTER (WHERE cc24=0 AND cc25=1) AS y25,
       count(*) FILTER (WHERE cc24=0 AND cc25=0 AND cc26=1) AS y26,
       count(*) AS 합계
FROM s WHERE cc23=0 AND cc26=1 GROUP BY member ORDER BY 5 DESC LIMIT 10""")

show("4. 누락이 큰 출판사 12곳의 보강률", """
SELECT member, any_value(publisher) AS publisher,
       count(*) FILTER (WHERE cc23=0) AS 비어있었음,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) AS 보강됨,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),2) AS 보강률
FROM s GROUP BY member ORDER BY 3 DESC LIMIT 12""")

show("5. 재등록 여부별 보강 (2023년에 비어 있던 논문)", """
SELECT CASE WHEN dep26 > dep23 THEN '재등록 있었음' ELSE '재등록 없음' END AS 구분,
       count(*) AS 논문수,
       count(*) FILTER (WHERE cc26=1) AS 보강됨,
       round(100.0*count(*) FILTER (WHERE cc26=1)/count(*),2) AS 보강률
FROM s WHERE cc23=0 GROUP BY 1 ORDER BY 2 DESC""")

show("6. 출판연도 구간별 보강률", """
SELECT CASE WHEN pub_year < 2010 THEN '2003-2009' WHEN pub_year < 2015 THEN '2010-2014'
            WHEN pub_year < 2020 THEN '2015-2019' ELSE '2020-2023' END AS 구간,
       count(*) FILTER (WHERE cc23=0) AS 비어있었음,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),1) AS 보강률
FROM s GROUP BY 1 ORDER BY 1""")
