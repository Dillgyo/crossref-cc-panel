import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
con.execute("""CREATE VIEW w AS SELECT * FROM read_parquet('D:/crossref/parquet/2023/works/*.parquet')""")
con.execute("""CREATE VIEW l AS SELECT * FROM read_parquet('D:/crossref/parquet/2023/licenses/*.parquet')""")
con.execute("""
CREATE TABLE f AS
SELECT doi,
       max(CASE WHEN cc AND coalesce(content_version,'') IN ('vor','am','unspecified') THEN 1 ELSE 0 END) AS main,
       max(CASE WHEN cc AND coalesce(content_version,'') NOT IN ('vor','am','unspecified') THEN 1 ELSE 0 END) AS other
FROM (SELECT doi, content_version, url ILIKE '%creativecommons.org%' AS cc FROM l)
GROUP BY doi
""")
def show(title, q):
    cur = con.execute(q); cols=[d[0] for d in cur.description]
    print("\n["+title+"]"); print("  "+" | ".join(cols))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

show("1. CC 기재 방식별 논문 수", """
SELECT CASE WHEN main=1 AND other=1 THEN '둘 다'
            WHEN main=1 THEN 'vor/am/unspecified 에만'
            ELSE 'tdm 등에만' END AS 구분,
       count(*) AS 논문수
FROM f WHERE main=1 OR other=1 GROUP BY 1 ORDER BY 2 DESC""")

show("2. tdm 등에만 있는 논문이 많은 출판사 10곳", """
SELECT w.member, any_value(w.publisher) AS publisher, count(*) AS 논문수
FROM f JOIN w USING (doi)
WHERE f.main=0 AND f.other=1
GROUP BY w.member ORDER BY 3 DESC LIMIT 10""")

show("3. 그 출판사들의 전체 논문 대비 비중", """
WITH t AS (SELECT w.member, count(*) FILTER (WHERE f.main=0 AND f.other=1) AS only_other,
                  count(*) FILTER (WHERE f.main=1) AS main_ok, count(*) AS total
           FROM w LEFT JOIN f USING (doi) GROUP BY w.member)
SELECT member, only_other, main_ok, total,
       round(100.0*only_other/total,1) AS pct_only_other
FROM t WHERE only_other > 10000 ORDER BY pct_only_other DESC LIMIT 10""")

show("4. tdm 등에만 있는 경우의 content-version 분포", """
SELECT coalesce(l.content_version,'(없음)') AS content_version, count(*) AS 행수
FROM f JOIN l USING (doi)
WHERE f.main=0 AND f.other=1 AND l.url ILIKE '%creativecommons.org%'
GROUP BY 1 ORDER BY 2 DESC""")
