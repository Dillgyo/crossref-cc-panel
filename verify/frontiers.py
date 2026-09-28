import duckdb
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet')")
con.execute("CREATE VIEW l23 AS SELECT * FROM read_parquet('D:/crossref/parquet/2023/licenses/*.parquet')")

def show(title, q):
    cur = con.execute(q); cols=[d[0] for d in cur.description]
    print("\n["+title+"]"); print("  "+" | ".join(cols))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

show("1. Frontiers 비어 있는 논문의 연도 분포", """
SELECT pub_year, count(*) FILTER (WHERE cc23=0) AS 비어있음, count(*) AS 전체,
       round(100.0*count(*) FILTER (WHERE cc23=1)/count(*),1) AS 기재율
FROM s WHERE member='1965' GROUP BY 1 ORDER BY 1""")

show("2. 비어 있는 논문에 라이선스가 아예 없는지, 다른 형태로 있는지", """
SELECT coalesce(l.content_version,'(라이선스 행 없음)') AS content_version,
       count(DISTINCT s.doi) AS 논문수,
       count(*) FILTER (WHERE l.url ILIKE '%creativecommons%') AS CC주소행
FROM s LEFT JOIN l23 l USING (doi)
WHERE s.member='1965' AND s.cc23=0 GROUP BY 1 ORDER BY 2 DESC""")

show("3. 그 논문들에 붙은 라이선스 주소 상위 5개", """
SELECT l.url, count(*) AS 행수 FROM s JOIN l23 l USING (doi)
WHERE s.member='1965' AND s.cc23=0 GROUP BY 1 ORDER BY 2 DESC LIMIT 5""")

show("4. 비어 있는 논문이 많은 저널 5개", """
SELECT container_title, count(*) FILTER (WHERE cc23=0) AS 비어있음, count(*) AS 전체
FROM s WHERE member='1965' GROUP BY 1 ORDER BY 2 DESC LIMIT 5""")
