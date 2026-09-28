import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
con.execute("CREATE VIEW st AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet')")
con.execute("CREATE VIEW s AS SELECT * FROM st WHERE in26=1")

print("[1. 각 스냅숏의 수록 cutoff (deposited 최댓값)]")
for y in ("2023","2024","2025","2026"):
    r = con.execute(f"""SELECT max(deposited), max(created) FROM
      read_parquet('D:/crossref/parquet/{y}/works/*.parquet')""").fetchone()
    print(f"  {y}: deposited 최대 {r[0]} / created 최대 {r[1]}")

print("\n[2. 최종 패널의 저널 수]")
con.execute("""CREATE TABLE jissn AS
WITH j AS (SELECT row_number() OVER () AS jid, "Journal ISSN (print version)" AS p,
                  "Journal EISSN (online version)" AS e, CAST("OA start" AS INT) AS oa
           FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true))
SELECT jid, upper(trim(issn)) AS issn, greatest(oa,2003) AS min_year
FROM j, UNNEST([p,e]) AS t(issn) WHERE issn IS NOT NULL AND trim(issn) <> ''""")
con.execute("""CREATE TABLE w23 AS SELECT doi, upper(trim(t.s)) AS issn, pub_year
  FROM read_parquet('D:/crossref/parquet/2023/works/*.parquet'), UNNEST(str_split(issn,';')) AS t(s)""")
for r in con.execute("""
SELECT count(DISTINCT j.jid) FILTER (WHERE w.doi IS NOT NULL) AS 논문확인,
       count(DISTINCT j.jid) FILTER (WHERE w.pub_year >= j.min_year) AS 하한적용,
       count(DISTINCT j.jid) FILTER (WHERE w.pub_year >= j.min_year AND w.doi IN (SELECT doi FROM s)) AS 최종패널
FROM jissn j LEFT JOIN w23 w USING (issn)""").fetchall(): print("  ", r)

print("\n[3. 판정 규칙별 미포착률]")
for lab, cond in [("VoR만","content_version='vor'"),
                  ("VoR+unspecified","content_version IN ('vor','unspecified')"),
                  ("본 분석","content_version IN ('vor','am','unspecified')"),
                  ("tdm 포함","1=1")]:
    for y in ("2023","2026"):
        con.execute(f"""CREATE OR REPLACE TABLE t{y} AS SELECT DISTINCT doi FROM
        read_parquet('D:/crossref/parquet/{y}/licenses/*.parquet')
        WHERE url ILIKE '%creativecommons.org%' AND ({cond})""")
    r = con.execute("""SELECT count(*),
        count(*) FILTER (WHERE a.doi IS NULL), count(*) FILTER (WHERE b.doi IS NULL)
        FROM s LEFT JOIN t2023 a USING (doi) LEFT JOIN t2026 b USING (doi)""").fetchone()
    print(f"  {lab}: 2023 미포착 {100*r[1]/r[0]:.1f}% / 2026 미포착 {100*r[2]/r[0]:.1f}%")

print("\n[4. 전환 출판연도: 지속성 조건 적용]")
for r in con.execute("""
WITH y AS (SELECT member, any_value(publisher) AS pub, pub_year, count(*) AS n, avg(cc26) AS rate
           FROM s GROUP BY member, pub_year),
     big AS (SELECT member FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000),
     ok AS (SELECT member, pub_year, rate, n,
              min(rate) OVER (PARTITION BY member ORDER BY pub_year
                              ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS min_after
            FROM y WHERE n >= 100 AND member IN (SELECT member FROM big))
SELECT any_value(y.pub) AS 출판사,
       min(y.pub_year) FILTER (WHERE y.rate>=0.8) AS 최초80,
       min(ok.pub_year) FILTER (WHERE ok.min_after>=0.8) AS 이후계속80
FROM y JOIN ok USING (member, pub_year) GROUP BY y.member HAVING 최초80 IS NOT NULL ORDER BY 2""").fetchall():
    print("  ", r)

print("\n[5. 소실률 worst-case]")
for r in con.execute("""
SELECT count(*) FILTER (WHERE cc23=1) AS 기재2023,
       count(*) FILTER (WHERE cc23=1 AND in26=1 AND cc26=0) AS 소실_현재기준,
       count(*) FILTER (WHERE cc23=1 AND in26=0) AS 레코드사라짐,
       round(100.0*(count(*) FILTER (WHERE cc23=1 AND in26=1 AND cc26=0)
             + count(*) FILTER (WHERE cc23=1 AND in26=0))/count(*) FILTER (WHERE cc23=1),2) AS worst소실률
FROM st""").fetchall(): print("  ", r)
