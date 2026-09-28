import duckdb
con = duckdb.connect()
for q in ["SET threads=4","SET memory_limit='6GB'","SET preserve_insertion_order=false","SET temp_directory='D:/crossref/_tmp'"]: con.execute(q)
P="D:/crossref/parquet"
def show(t,q):
    cur=con.execute(q); print(f"\n[{t}]"); print("  "+" | ".join(d[0] for d in cur.description))
    for r in cur.fetchall(): print("  "+" | ".join("" if v is None else (f"{v:,}" if isinstance(v,int) else str(v)) for v in r))
con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1")
con.execute(f"CREATE VIEW l26 AS SELECT * FROM read_parquet('{P}/2026/licenses/*.parquet')")
CC = "url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')"

show("1. 비표준 표기 19,090의 단위와 포함 관계", f"""
SELECT count(*) 항목수, count(DISTINCT doi) DOI수,
  count(*) FILTER (WHERE url ILIKE '%/licenses/%') licenses경로에_포함,
  count(*) FILTER (WHERE url ILIKE '%/publicdomain/%') publicdomain경로에_포함,
  count(*) FILTER (WHERE url NOT ILIKE '%/licenses/%' AND url NOT ILIKE '%/publicdomain/%') 둘다아님
FROM l26 WHERE {CC} AND (url LIKE '%/CC-%' OR url LIKE '%/BY%')""")
show("1-2. 예시", f"""SELECT url, count(*) n FROM l26 WHERE {CC} AND (url LIKE '%/CC-%' OR url LIKE '%/BY%') GROUP BY 1 ORDER BY 2 DESC LIMIT 6""")

show("2. 표 5·9 출판사 행의 member와 publisher 문자열", """
SELECT member, any_value(publisher) publisher, count(*) 패널논문,
  count(*) FILTER (WHERE cc23=0) 미기재2023
FROM s WHERE member IN ('276','2581','179','311','297','1965','2399','317','2373','530','301','78','1968','2049','1010','339','340','1965')
   OR publisher ILIKE '%SciELO%' OR publisher ILIKE '%Wolters%' OR publisher ILIKE '%AGUIA%' OR publisher ILIKE '%Agencia USP%'
GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 5000 ORDER BY 4 DESC""")

show("3. SciELO 계열 member 전체 (패널 내)", """
SELECT member, any_value(publisher) publisher, count(*) n FROM s WHERE publisher ILIKE '%scielo%'
GROUP BY member ORDER BY 3 DESC""")

show("4. AGUIA의 publisher 문자열 (2026년판 원문)", f"""
SELECT member, publisher, count(*) n FROM read_parquet('{P}/2026/works/*.parquet')
WHERE publisher ILIKE '%AGUIA%' OR publisher ILIKE '%Agência%' OR publisher ILIKE '%Agencia USP%'
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 5""")

show("5. ISSN 변경 사례가 63건에 포함되는지", f"""
WITH api AS (SELECT lower(doi) doi, upper(trim(issn)) q, created FROM read_csv_auto('D:/crossref/missing_dois.csv', header=true, all_varchar=true)),
     w23 AS (SELECT doi, any_value(issn) issn FROM read_parquet('{P}/2023/works/*.parquet') GROUP BY doi)
SELECT a.q 조회ISSN, count(*) n, any_value(w.issn) 레코드ISSN
FROM api a JOIN w23 w USING (doi) WHERE a.created < '2023-04'
GROUP BY 1 ORDER BY 2 DESC LIMIT 12""")

show("6. 과거 출판분이 있는 출판사가 모두 부분집합에 포함되는지", f"""
WITH jissn AS (SELECT upper(trim(issn)) issn, min(greatest(oa,2003)) min_year FROM
  (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e, CAST("OA start" AS INT) oa
   FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true, all_varchar=true)), UNNEST([p,e]) t(issn)
  WHERE issn IS NOT NULL AND trim(issn)<>'' GROUP BY 1),
 u AS (SELECT doi, min(pub_year) pub_year, min(created) created FROM
   (SELECT doi, pub_year, created, upper(trim(t.s)) issn FROM read_parquet('{P}/2026/works/*.parquet'), UNNEST(str_split(issn,';')) t(s)) w
   JOIN jissn j USING (issn) WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026 GROUP BY doi),
 b AS (SELECT * FROM u WHERE created >= '2023-04-01'),
 mm AS (SELECT b.doi, b.pub_year, any_value(w.member) member FROM b JOIN
   (SELECT doi, member FROM read_parquet('{P}/2026/works/*.parquet')) w USING (doi) GROUP BY 1,2),
 t AS (SELECT member, count(*) FILTER (WHERE pub_year>=2023) n_new, count(*) FILTER (WHERE pub_year<2023) n_old FROM mm GROUP BY member)
SELECT count(*) FILTER (WHERE n_old>0) 과거출판분_보유_출판사,
  count(*) FILTER (WHERE n_old>0 AND n_new>0) 부분집합_포함,
  sum(n_old) 과거출판분_전체, sum(n_old) FILTER (WHERE n_new>0) 부분집합_과거출판분 FROM t""")

show("7. AIP Publishing의 연도판별 기재율", """
SELECT round(100.0*avg(cc23),1) "2023년판", round(100.0*avg(cc24),1) "2024년판",
       round(100.0*avg(cc25),1) "2025년판", round(100.0*avg(cc26),1) "2026년판", count(*) n
FROM s WHERE member='317'""")
