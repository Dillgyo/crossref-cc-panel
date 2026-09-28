import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")

# 1. ISSN 공유 저널
con.execute("""CREATE TABLE jrow AS
WITH j AS (SELECT row_number() OVER () AS jid, "Journal title" AS title,
                  upper(trim("Journal ISSN (print version)")) AS p,
                  upper(trim("Journal EISSN (online version)")) AS e,
                  CAST("OA start" AS INT) AS oa
           FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true))
SELECT jid, title, upper(trim(issn)) AS issn, greatest(oa,2003) AS min_year
FROM j, UNNEST([p,e]) AS t(issn) WHERE issn IS NOT NULL AND issn <> ''""")
print("[1. 같은 ISSN을 공유하는 저널]")
for r in con.execute("""
SELECT issn, count(DISTINCT jid) AS 저널수, min(min_year) AS 최소하한, max(min_year) AS 최대하한,
       string_agg(DISTINCT title, ' / ') AS 저널들
FROM jrow GROUP BY issn HAVING count(DISTINCT jid) > 1 ORDER BY 2 DESC""").fetchall(): print("  ", r)

# 2. 신규 DOI의 member: 최초 관찰 스냅숏 기준 재계산
con.execute("""CREATE TABLE jissn AS
SELECT issn, min(min_year) AS min_year FROM jrow GROUP BY issn""")
for y in ("2024","2025","2026"):
    con.execute(f"""CREATE TABLE w{y} AS
    SELECT doi, member, publisher, pub_year, created, upper(trim(t.s)) AS issn
    FROM read_parquet('D:/crossref/parquet/{y}/works/*.parquet'), UNNEST(str_split(issn,';')) AS t(s)
    WHERE created >= '2023-04'""")
con.execute("""CREATE TABLE firstmem AS
SELECT doi, any_value(member) AS member_first FROM (
  SELECT doi, member, 1 AS ord FROM w2024
  UNION ALL SELECT doi, member, 2 FROM w2025
  UNION ALL SELECT doi, member, 3 FROM w2026) t
GROUP BY doi""")
con.execute("""CREATE TABLE cc AS SELECT DISTINCT doi FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')""")
con.execute("""CREATE TABLE new26 AS
SELECT DISTINCT w.doi, w.member AS member26, f.member_first, w.pub_year
FROM w2026 w JOIN jissn j USING (issn) JOIN firstmem f USING (doi)
WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026""")

print("\n[2. member 귀속이 달라지는 DOI]")
for r in con.execute("""
SELECT count(*) AS 전체, count(*) FILTER (WHERE member26 <> member_first) AS 귀속변경,
       round(100.0*count(*) FILTER (WHERE member26 <> member_first)/count(*),2) AS 비율
FROM new26""").fetchall(): print("  ", r)

print("\n[3. 최초 관찰 member 기준 재계산]")
for r in con.execute("""
SELECT CASE WHEN pub_year >= 2023 THEN '2023년 이후 출판분' ELSE '과거 출판분' END AS 구분,
       count(*) AS 논문수,
       round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc))/count(*),1) AS 기재율
FROM new26 GROUP BY 1 ORDER BY 2 DESC""").fetchall(): print("  ", r)
for r in con.execute("""
WITH t AS (SELECT member_first AS m,
    count(*) FILTER (WHERE pub_year>=2023) AS n_new, count(*) FILTER (WHERE pub_year<2023) AS n_old,
    1.0*count(*) FILTER (WHERE pub_year>=2023 AND doi IN (SELECT doi FROM cc))/nullif(count(*) FILTER (WHERE pub_year>=2023),0) AS r_new,
    1.0*count(*) FILTER (WHERE pub_year<2023 AND doi IN (SELECT doi FROM cc))/nullif(count(*) FILTER (WHERE pub_year<2023),0) AS r_old
  FROM new26 GROUP BY 1),
  ok AS (SELECT * FROM t WHERE r_new IS NOT NULL AND r_old IS NOT NULL)
SELECT count(*) AS 출판사수, round(100.0*sum(n_new*r_new)/sum(n_new),1) AS 신규실제,
  round(100.0*sum(n_old*r_old)/sum(n_old),1) AS 과거실제,
  round(100.0*sum(n_old*r_new)/sum(n_old),1) AS 과거구성적용,
  round(100.0*sum(n_new*r_old)/sum(n_new),1) AS 신규구성적용,
  sum(n_new)+sum(n_old) AS 포괄논문수
FROM ok""").fetchall(): print("  ", r)
