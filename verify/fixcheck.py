import duckdb
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
con.execute("CREATE TABLE api AS SELECT * FROM read_csv_auto('D:/crossref/missing_dois.csv', header=true)")
con.execute("""CREATE TABLE w23 AS SELECT DISTINCT doi FROM
  read_parquet('D:/crossref/parquet/2023/works/*.parquet') WHERE doi IN (SELECT doi FROM api)""")

print("[A. 4.1절 100건의 내역]")
for r in con.execute("""
SELECT count(*) AS 전체,
       count(*) FILTER (WHERE created >= '2023-04') AS 스냅숏이후등록,
       count(*) FILTER (WHERE created < '2023-04' AND doi IN (SELECT doi FROM w23)) AS 이전등록_추출에있음,
       count(*) FILTER (WHERE created < '2023-04' AND doi NOT IN (SELECT doi FROM w23)) AS 이전등록_추출에없음
FROM api""").fetchall(): print("  ", r)

print("\n[B. 집중도: 상위 5개 출판사 미기재 실측]")
for r in con.execute("""
SELECT member, any_value(publisher) AS pub, count(*) FILTER (WHERE cc23=0) AS 미기재,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) AS 보완
FROM s WHERE member IN ('276','2399','317','297','2373') GROUP BY member ORDER BY 3 DESC""").fetchall():
    print("  ", r)
for r in con.execute("""
SELECT count(*) FILTER (WHERE cc23=0) AS 전체미기재,
       count(*) FILTER (WHERE cc23=0 AND member NOT IN ('276','2399','317','297','2373')) AS 제외후미기재
FROM s""").fetchall(): print("  합계:", r)

print("\n[C. 표 12 과소추정 실측 (2023/2026)]")
for r in con.execute("""
SELECT any_value(publisher) AS pub,
       round(100.0*(1-avg(cc23)),1) AS gap23, round(100.0*(1-avg(cc26)),1) AS gap26
FROM s WHERE member IN ('2399','1010','2581','276','530','179','297','1965','311','301','78')
GROUP BY member ORDER BY 2 DESC""").fetchall(): print("  ", r)

print("\n[D. AIP·CSIC 2026 기재율]")
for r in con.execute("""
SELECT any_value(publisher) AS pub, round(100.0*avg(cc23),1) AS r23, round(100.0*avg(cc26),1) AS r26,
       count(*) FILTER (WHERE cc23=0) AS 미기재, count(*) FILTER (WHERE cc23=0 AND cc26=1) AS 보완
FROM s WHERE member IN ('317','2373') GROUP BY member""").fetchall(): print("  ", r)

print("\n[E. 기재 관행 도입 시점: 임계값 70/80/90% 비교]")
for r in con.execute("""
WITH y AS (SELECT member, any_value(publisher) AS pub, pub_year, count(*) AS n, avg(cc26) AS rate
           FROM s GROUP BY member, pub_year),
     big AS (SELECT member FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000)
SELECT any_value(pub) AS 출판사,
       min(pub_year) FILTER (WHERE rate>=0.7 AND n>=100) AS y70,
       min(pub_year) FILTER (WHERE rate>=0.8 AND n>=100) AS y80,
       min(pub_year) FILTER (WHERE rate>=0.9 AND n>=100) AS y90
FROM y WHERE member IN (SELECT member FROM big) GROUP BY member
HAVING y80 IS NOT NULL ORDER BY y80""").fetchall(): print("  ", r)
