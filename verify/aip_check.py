import duckdb
con = duckdb.connect()
for q in ["SET threads=4","SET memory_limit='6GB'","SET preserve_insertion_order=false","SET temp_directory='D:/crossref/_tmp'"]: con.execute(q)
P="D:/crossref/parquet"
def show(t,q):
    cur=con.execute(q); print(f"\n[{t}]"); print("  "+" | ".join(d[0] for d in cur.description))
    for r in cur.fetchall(): print("  "+" | ".join("" if v is None else (f"{v:,}" if isinstance(v,int) else str(v)) for v in r))
con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1")

# ── A. 1001 패턴의 출판사 분포 ──
show("A-1. 1001 패턴 2,612건의 출판사", """
SELECT member, any_value(publisher) publisher, count(*) n FROM s
WHERE cc23=1 AND cc24=0 AND cc25=0 AND cc26=1 GROUP BY member ORDER BY 3 DESC LIMIT 8""")
show("A-2. 중간 변동 2,657건 전체의 패턴별 분포", """
SELECT cc23||cc24||cc25||cc26 패턴, count(*) n, any_value(publisher) 최다출판사예시 FROM s
WHERE NOT (cc23=1 AND cc24=1 AND cc25=1 AND cc26=1) AND NOT (cc23=0 AND cc24=0 AND cc25=0 AND cc26=0)
  AND NOT (cc23=0 AND cc26=1) AND NOT (cc23=1 AND cc26=0) GROUP BY 1 ORDER BY 2 DESC""")
show("A-3. AIP(317)의 네 시점 상태 분해", """
SELECT cc23||cc24||cc25||cc26 패턴, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),1) 비율
FROM s WHERE member='317' GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")
show("A-4. 2024·2025년판에서 기재율이 크게 떨어진 출판사 (패널 5,000건 이상)", """
SELECT member, any_value(publisher) publisher, count(*) n,
  round(100.0*avg(cc23),1) y23, round(100.0*avg(cc24),1) y24, round(100.0*avg(cc25),1) y25, round(100.0*avg(cc26),1) y26
FROM s GROUP BY member HAVING count(*) >= 5000 AND 100.0*avg(cc24) < 100.0*avg(cc23) - 10
ORDER BY (avg(cc23)-avg(cc24)) DESC LIMIT 10""")
show("A-5. AIP 레코드의 라이선스 항목 자체가 사라졌는지", f"""
SELECT '2023' 판, count(*) 항목, count(DISTINCT doi) DOI FROM read_parquet('{P}/2023/licenses/*.parquet')
WHERE doi IN (SELECT doi FROM s WHERE member='317')
UNION ALL SELECT '2024', count(*), count(DISTINCT doi) FROM read_parquet('{P}/2024/licenses/*.parquet')
WHERE doi IN (SELECT doi FROM s WHERE member='317')
UNION ALL SELECT '2025', count(*), count(DISTINCT doi) FROM read_parquet('{P}/2025/licenses/*.parquet')
WHERE doi IN (SELECT doi FROM s WHERE member='317')
UNION ALL SELECT '2026', count(*), count(DISTINCT doi) FROM read_parquet('{P}/2026/licenses/*.parquet')
WHERE doi IN (SELECT doi FROM s WHERE member='317')""")
show("A-6. AIP의 연도판별 라이선스 URL·content-version 구성", f"""
SELECT '2023' 판, coalesce(content_version,'(없음)') cv, count(*) n FROM read_parquet('{P}/2023/licenses/*.parquet')
WHERE doi IN (SELECT doi FROM s WHERE member='317') GROUP BY 1,2
UNION ALL SELECT '2024', coalesce(content_version,'(없음)'), count(*) FROM read_parquet('{P}/2024/licenses/*.parquet')
WHERE doi IN (SELECT doi FROM s WHERE member='317') GROUP BY 1,2
UNION ALL SELECT '2025', coalesce(content_version,'(없음)'), count(*) FROM read_parquet('{P}/2025/licenses/*.parquet')
WHERE doi IN (SELECT doi FROM s WHERE member='317') GROUP BY 1,2
UNION ALL SELECT '2026', coalesce(content_version,'(없음)'), count(*) FROM read_parquet('{P}/2026/licenses/*.parquet')
WHERE doi IN (SELECT doi FROM s WHERE member='317') GROUP BY 1,2
ORDER BY 1,3 DESC""")

# ── B. 부분집합 출판사 수 (귀속 기준별) ──
con.execute("""CREATE TABLE jissn AS SELECT upper(trim(issn)) issn, min(greatest(oa,2003)) min_year FROM
  (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e, CAST("OA start" AS INT) oa
   FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true, all_varchar=true)), UNNEST([p,e]) t(issn)
  WHERE issn IS NOT NULL AND trim(issn)<>'' GROUP BY 1""")
con.execute(f"""CREATE TABLE b AS SELECT doi, pub_year FROM (
  SELECT doi, min(pub_year) pub_year, min(created) created FROM
  (SELECT doi, pub_year, created, upper(trim(t.s)) issn FROM read_parquet('{P}/2026/works/*.parquet'), UNNEST(str_split(issn,';')) t(s)) w
  JOIN jissn j USING (issn) WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026 GROUP BY doi) WHERE created >= '2023-04-01'""")
con.execute(f"""CREATE TABLE mm AS
WITH x AS (SELECT doi,2024 y FROM read_parquet('{P}/2024/works/*.parquet') UNION ALL
           SELECT doi,2025 FROM read_parquet('{P}/2025/works/*.parquet') UNION ALL
           SELECT doi,2026 FROM read_parquet('{P}/2026/works/*.parquet')),
 f AS (SELECT doi, min(y) fy FROM x GROUP BY doi),
 m24 AS (SELECT doi, any_value(member) m FROM read_parquet('{P}/2024/works/*.parquet') GROUP BY doi),
 m25 AS (SELECT doi, any_value(member) m FROM read_parquet('{P}/2025/works/*.parquet') GROUP BY doi),
 m26 AS (SELECT doi, any_value(member) m FROM read_parquet('{P}/2026/works/*.parquet') GROUP BY doi)
SELECT b.doi, b.pub_year,
  CASE f.fy WHEN 2024 THEN m24.m WHEN 2025 THEN m25.m ELSE m26.m END m_first, m26.m m_2026
FROM b JOIN f USING (doi) LEFT JOIN m24 ON m24.doi=b.doi LEFT JOIN m25 ON m25.doi=b.doi LEFT JOIN m26 ON m26.doi=b.doi""")
show("B. 귀속 기준별 부분집합 출판사 수", """
SELECT '최초 관찰 연도판' 기준,
  count(*) FILTER (WHERE n_new>0 AND n_old>0) 부분집합, count(*) 전체출판사
FROM (SELECT m_first m, count(*) FILTER (WHERE pub_year>=2023) n_new, count(*) FILTER (WHERE pub_year<2023) n_old FROM mm GROUP BY 1)
UNION ALL
SELECT '2026년판', count(*) FILTER (WHERE n_new>0 AND n_old>0), count(*)
FROM (SELECT m_2026 m, count(*) FILTER (WHERE pub_year>=2023) n_new, count(*) FILTER (WHERE pub_year<2023) n_old FROM mm GROUP BY 1)""")
