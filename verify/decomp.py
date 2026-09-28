import duckdb
con = duckdb.connect()
for q in ["SET threads=4","SET memory_limit='6GB'","SET preserve_insertion_order=false","SET temp_directory='D:/crossref/_tmp'"]: con.execute(q)
P="D:/crossref/parquet"
con.execute("""CREATE TABLE jissn AS
WITH j AS (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e, CAST("OA start" AS INT) oa
           FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true, all_varchar=true))
SELECT upper(trim(issn)) issn, min(greatest(oa,2003)) min_year FROM j, UNNEST([p,e]) t(issn)
WHERE issn IS NOT NULL AND trim(issn)<>'' GROUP BY 1""")
con.execute(f"""CREATE TABLE u AS SELECT doi, min(pub_year) pub_year, min(created) created FROM (
  SELECT doi, pub_year, created, upper(trim(t.s)) issn FROM read_parquet('{P}/2026/works/*.parquet'), UNNEST(str_split(issn,';')) t(s)) w
  JOIN jissn j USING (issn) WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026 GROUP BY doi""")
con.execute("CREATE TABLE b AS SELECT * FROM u WHERE created >= '2023-04-01'")
con.execute(f"""CREATE TABLE cc AS SELECT DISTINCT doi FROM read_parquet('{P}/2026/licenses/*.parquet')
  WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')""")
con.execute(f"""CREATE TABLE mf AS
WITH x AS (SELECT doi,2024 y FROM read_parquet('{P}/2024/works/*.parquet') UNION ALL
           SELECT doi,2025 FROM read_parquet('{P}/2025/works/*.parquet') UNION ALL
           SELECT doi,2026 FROM read_parquet('{P}/2026/works/*.parquet')),
 f AS (SELECT doi, min(y) fy FROM x GROUP BY doi),
 m24 AS (SELECT doi, any_value(member) m FROM read_parquet('{P}/2024/works/*.parquet') GROUP BY doi),
 m25 AS (SELECT doi, any_value(member) m FROM read_parquet('{P}/2025/works/*.parquet') GROUP BY doi),
 m26 AS (SELECT doi, any_value(member) m FROM read_parquet('{P}/2026/works/*.parquet') GROUP BY doi)
SELECT b.doi, b.pub_year, CASE f.fy WHEN 2024 THEN m24.m WHEN 2025 THEN m25.m ELSE m26.m END member
FROM b JOIN f USING (doi) LEFT JOIN m24 ON m24.doi=b.doi LEFT JOIN m25 ON m25.doi=b.doi LEFT JOIN m26 ON m26.doi=b.doi""")
r = con.execute("""
WITH t AS (SELECT member,
   count(*) FILTER (WHERE pub_year>=2023) n_new, count(*) FILTER (WHERE pub_year<2023) n_old,
   1.0*count(*) FILTER (WHERE pub_year>=2023 AND doi IN (SELECT doi FROM cc))/nullif(count(*) FILTER (WHERE pub_year>=2023),0) r_new,
   1.0*count(*) FILTER (WHERE pub_year<2023 AND doi IN (SELECT doi FROM cc))/nullif(count(*) FILTER (WHERE pub_year<2023),0) r_old
 FROM mf GROUP BY member),
 ok AS (SELECT * FROM t WHERE r_new IS NOT NULL AND r_old IS NOT NULL)
SELECT 100.0*sum(n_new*r_new)/sum(n_new) a_new, 100.0*sum(n_old*r_old)/sum(n_old) a_old,
       100.0*sum(n_old*r_new)/sum(n_old) cf_old, 100.0*sum(n_new*r_old)/sum(n_new) cf_new FROM ok""").fetchone()
a_new,a_old,cf_old,cf_new = r
print(f"신규 실제 {a_new:.3f} / 과거 실제 {a_old:.3f} / 과거구성 적용 {cf_old:.3f} / 신규구성 적용 {cf_new:.3f}")
print(f"격차 {a_new-a_old:.3f}%p")
print(f"[과거 구성 기준] 구성 효과 {a_new-cf_old:.3f}%p + 출판사 내 효과 {cf_old-a_old:.3f}%p = {a_new-a_old:.3f}%p")
print(f"[신규 구성 기준] 구성 효과 {cf_new-a_old:.3f}%p + 출판사 내 효과 {a_new-cf_new:.3f}%p = {a_new-a_old:.3f}%p")
