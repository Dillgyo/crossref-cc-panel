import duckdb, os, time
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
t0 = time.time()

con.execute("""
CREATE TABLE panel AS
WITH j AS (SELECT "Journal ISSN (print version)" AS p, "Journal EISSN (online version)" AS e,
                  CAST("OA start" AS INT) AS oa
           FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true))
SELECT upper(trim(issn)) AS issn, min(greatest(oa, 2003)) AS min_year
FROM j, UNNEST([p, e]) AS t(issn)
WHERE issn IS NOT NULL AND trim(issn) <> '' GROUP BY 1
""")

# 2023 기준 패널
con.execute("""
CREATE TABLE base AS
SELECT DISTINCT w.doi, w.member, w.publisher, w.container_title, w.pub_year, w.created
FROM (SELECT doi, member, publisher, container_title, pub_year, created, upper(trim(s)) AS issn
      FROM read_parquet('D:/crossref/parquet/2023/works/*.parquet'),
           UNNEST(str_split(issn, ';')) AS t(s)) w
JOIN panel p USING (issn)
WHERE w.pub_year >= p.min_year AND w.pub_year <= 2023
""")
print("패널:", con.execute("SELECT count(*) FROM base").fetchone()[0], f"({time.time()-t0:.0f}초)")

# 시점별 CC 여부와 deposited
for y in ("2023", "2024", "2025", "2026"):
    con.execute(f"""
    CREATE TABLE cc{y} AS
    SELECT DISTINCT doi FROM read_parquet('D:/crossref/parquet/{y}/licenses/*.parquet')
    WHERE url ILIKE '%creativecommons.org%'
      AND coalesce(content_version,'') IN ('vor','am','unspecified')
    """)
    con.execute(f"""
    CREATE TABLE dep{y} AS
    SELECT doi, max(deposited) AS dep FROM read_parquet('D:/crossref/parquet/{y}/works/*.parquet')
    GROUP BY doi
    """)
    print(y, "준비 완료", f"({time.time()-t0:.0f}초)")

con.execute("""
CREATE TABLE state AS
SELECT b.doi, b.member, b.publisher, b.container_title, b.pub_year, b.created,
       CASE WHEN c23.doi IS NOT NULL THEN 1 ELSE 0 END AS cc23,
       CASE WHEN c24.doi IS NOT NULL THEN 1 ELSE 0 END AS cc24,
       CASE WHEN c25.doi IS NOT NULL THEN 1 ELSE 0 END AS cc25,
       CASE WHEN c26.doi IS NOT NULL THEN 1 ELSE 0 END AS cc26,
       d23.dep AS dep23, d24.dep AS dep24, d25.dep AS dep25, d26.dep AS dep26,
       CASE WHEN d24.doi IS NULL THEN 0 ELSE 1 END AS in24,
       CASE WHEN d25.doi IS NULL THEN 0 ELSE 1 END AS in25,
       CASE WHEN d26.doi IS NULL THEN 0 ELSE 1 END AS in26
FROM base b
LEFT JOIN cc2023 c23 USING (doi) LEFT JOIN cc2024 c24 USING (doi)
LEFT JOIN cc2025 c25 USING (doi) LEFT JOIN cc2026 c26 USING (doi)
LEFT JOIN dep2023 d23 USING (doi) LEFT JOIN dep2024 d24 USING (doi)
LEFT JOIN dep2025 d25 USING (doi) LEFT JOIN dep2026 d26 USING (doi)
""")
con.execute("COPY state TO 'D:/crossref/parquet/state_panel.parquet' (FORMAT PARQUET)")
print("상태표 저장 완료", f"({time.time()-t0:.0f}초)")

def show(title, q):
    cur = con.execute(q); cols=[d[0] for d in cur.description]
    print("\n["+title+"]"); print("  "+" | ".join(cols))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

show("1. 이후 시점에서의 존재 여부", """
SELECT count(*) AS 패널, sum(in24) AS 있음24, sum(in25) AS 있음25, sum(in26) AS 있음26 FROM state""")

show("2. 시점별 CC 기재율", """
SELECT round(100.0*avg(cc23),1) AS y23, round(100.0*avg(cc24),1) AS y24,
       round(100.0*avg(cc25),1) AS y25, round(100.0*avg(cc26),1) AS y26 FROM state""")

show("3. 네 시점 패턴 분포 (상위 12개)", """
SELECT concat(cc23,cc24,cc25,cc26) AS 패턴, count(*) AS 논문수
FROM state WHERE in26=1 GROUP BY 1 ORDER BY 2 DESC LIMIT 12""")

show("4. 핵심 요약 (2026까지 남아 있는 논문 기준)", """
SELECT count(*) FILTER (WHERE cc23=0) AS 처음_비어있음,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) AS 나중에_채워짐,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),2) AS 보강률,
       count(*) FILTER (WHERE cc23=1 AND cc26=0) AS 사라짐,
       round(100.0*count(*) FILTER (WHERE cc23=1 AND cc26=0)/nullif(count(*) FILTER (WHERE cc23=1),0),2) AS 소실률
FROM state WHERE in26=1""")
