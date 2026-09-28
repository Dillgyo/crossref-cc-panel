import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")

con.execute("""
CREATE TABLE panel AS
WITH j AS (
  SELECT "Journal title" AS title, "Publisher" AS pub,
         "Journal ISSN (print version)" AS p, "Journal EISSN (online version)" AS e,
         CAST("OA start" AS INT) AS oa_start
  FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true)
)
SELECT DISTINCT upper(trim(issn)) AS issn, title, pub,
       greatest(oa_start, 2003) AS min_year
FROM j, UNNEST([p, e]) AS t(issn)
WHERE issn IS NOT NULL AND trim(issn) <> ''
""")
print("모집단 ISSN 수:", con.execute("SELECT count(*) FROM panel").fetchone()[0])

con.execute("""
CREATE TABLE w23 AS
SELECT doi, member, publisher, pub_year, deposited,
       upper(trim(s)) AS issn
FROM read_parquet('D:/crossref/parquet/2023/works/*.parquet'),
     UNNEST(str_split(issn, ';')) AS t(s)
""")

def show(title, q):
    cur = con.execute(q); cols=[d[0] for d in cur.description]
    print("\n["+title+"]"); print("  "+" | ".join(cols))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

show("1. 저널 커버리지", """
SELECT count(DISTINCT p.title) AS 모집단_저널수,
       count(DISTINCT CASE WHEN w.doi IS NOT NULL THEN p.title END) AS 논문이_잡힌_저널수
FROM panel p LEFT JOIN w23 w USING (issn)""")

show("2. 논문 수", """
SELECT count(DISTINCT w.doi) AS 매칭_논문수,
       count(DISTINCT CASE WHEN w.pub_year >= p.min_year THEN w.doi END) AS 하한_적용_후
FROM panel p JOIN w23 w USING (issn)""")

show("3. 저널당 논문 수 분포", """
WITH c AS (SELECT p.title, count(DISTINCT w.doi) AS n
           FROM panel p LEFT JOIN w23 w USING (issn) GROUP BY p.title)
SELECT CASE WHEN n = 0 THEN '0건' WHEN n < 100 THEN '1-99건'
            WHEN n < 1000 THEN '100-999건' ELSE '1000건 이상' END AS 구간,
       count(*) AS 저널수
FROM c GROUP BY 1 ORDER BY 1""")

show("4. 논문 수 상위 출판사 10곳 (모집단 기준)", """
SELECT w.member, any_value(w.publisher) AS publisher, count(DISTINCT w.doi) AS 논문수
FROM panel p JOIN w23 w USING (issn)
WHERE w.pub_year >= p.min_year
GROUP BY w.member ORDER BY 3 DESC LIMIT 10""")
