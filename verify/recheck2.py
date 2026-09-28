import duckdb
con = duckdb.connect()
for q in ["SET threads=4","SET memory_limit='6GB'","SET preserve_insertion_order=false","SET temp_directory='D:/crossref/_tmp'"]: con.execute(q)
P = "D:/crossref/parquet"
def show(t, q):
    cur = con.execute(q); print(f"\n[{t}]"); print("  " + " | ".join(d[0] for d in cur.description))
    for r in cur.fetchall(): print("  " + " | ".join("" if v is None else (f"{v:,}" if isinstance(v,int) else str(v)) for v in r))

con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1")
con.execute("""CREATE TABLE jissn AS
WITH j AS (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e, CAST("OA start" AS INT) oa
           FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true, all_varchar=true))
SELECT upper(trim(issn)) issn, min(greatest(oa,2003)) min_year FROM j, UNNEST([p,e]) t(issn)
WHERE issn IS NOT NULL AND trim(issn)<>'' GROUP BY 1""")
con.execute(f"""CREATE TABLE w26 AS SELECT doi, pub_year, created, member FROM (
  SELECT doi, pub_year, created, member, upper(trim(t.s)) issn
  FROM read_parquet('{P}/2026/works/*.parquet'), UNNEST(str_split(issn,';')) t(s)) w
  JOIN jissn j USING (issn) WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026""")
con.execute(f"CREATE TABLE in23 AS SELECT DISTINCT doi FROM read_parquet('{P}/2023/works/*.parquet')")
con.execute(f"""CREATE TABLE cc AS SELECT DISTINCT doi FROM read_parquet('{P}/2026/licenses/*.parquet')
  WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')""")

# DOI 단위 집합 (값이 갈리는 DOI가 있는지 먼저 확인)
show("0. DOI별 속성이 갈리는 경우", """
SELECT count(*) 전체DOI,
  count(*) FILTER (WHERE ny>1) 출판연도가_다름, count(*) FILTER (WHERE nc>1) created가_다름, count(*) FILTER (WHERE nm>1) member가_다름
FROM (SELECT doi, count(DISTINCT pub_year) ny, count(DISTINCT created) nc, count(DISTINCT member) nm FROM w26 GROUP BY doi)""")
con.execute("""CREATE TABLE u AS SELECT doi, min(pub_year) pub_year, min(created) created, min(member) member
  FROM w26 GROUP BY doi""")
con.execute("CREATE TABLE b AS SELECT * FROM u WHERE created >= '2023-04-01'")

# ── 1. 표준화 대상과 표 8을 DOI 단위로 재집계 ──
con.execute(f"""CREATE TABLE fm AS
WITH x AS (SELECT doi, 2024 y FROM read_parquet('{P}/2024/works/*.parquet')
  UNION ALL SELECT doi, 2025 FROM read_parquet('{P}/2025/works/*.parquet')
  UNION ALL SELECT doi, 2026 FROM read_parquet('{P}/2026/works/*.parquet'))
SELECT doi, min(y) fy FROM x GROUP BY doi""")
con.execute(f"""CREATE TABLE mfirst AS
SELECT f.doi, CASE f.fy
  WHEN 2024 THEN (SELECT any_value(member) FROM read_parquet('{P}/2024/works/*.parquet') w WHERE w.doi=f.doi)
  WHEN 2025 THEN (SELECT any_value(member) FROM read_parquet('{P}/2025/works/*.parquet') w WHERE w.doi=f.doi)
  ELSE (SELECT any_value(member) FROM read_parquet('{P}/2026/works/*.parquet') w WHERE w.doi=f.doi) END m
FROM fm f WHERE f.doi IN (SELECT doi FROM b)""") if False else None
# 위 상관 서브쿼리는 느리므로 조인 방식으로
con.execute(f"""CREATE OR REPLACE TABLE mfirst AS
WITH m24 AS (SELECT doi, any_value(member) m FROM read_parquet('{P}/2024/works/*.parquet') GROUP BY doi),
     m25 AS (SELECT doi, any_value(member) m FROM read_parquet('{P}/2025/works/*.parquet') GROUP BY doi),
     m26 AS (SELECT doi, any_value(member) m FROM read_parquet('{P}/2026/works/*.parquet') GROUP BY doi)
SELECT b.doi, b.pub_year, f.fy,
  CASE f.fy WHEN 2024 THEN m24.m WHEN 2025 THEN m25.m ELSE m26.m END member
FROM b JOIN fm f USING (doi)
LEFT JOIN m24 ON m24.doi=b.doi LEFT JOIN m25 ON m25.doi=b.doi LEFT JOIN m26 ON m26.doi=b.doi""")

show("1-1. 표 7 (DOI 단위, 재확인)", """
SELECT CASE WHEN pub_year>=2023 THEN '2023년 이후 출판' ELSE '과거 출판' END 구분, count(*) 논문수,
  count(*) FILTER (WHERE doi IN (SELECT doi FROM cc)) 기재건수,
  round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc))/count(*),1) 기재율 FROM b GROUP BY 1 ORDER BY 1""")
show("1-2. 표준화 대상과 비중", """
WITH t AS (SELECT member,
    count(*) FILTER (WHERE pub_year>=2023) n_new, count(*) FILTER (WHERE pub_year<2023) n_old,
    1.0*count(*) FILTER (WHERE pub_year>=2023 AND doi IN (SELECT doi FROM cc))/nullif(count(*) FILTER (WHERE pub_year>=2023),0) r_new,
    1.0*count(*) FILTER (WHERE pub_year<2023 AND doi IN (SELECT doi FROM cc))/nullif(count(*) FILTER (WHERE pub_year<2023),0) r_old
  FROM mfirst GROUP BY member),
  ok AS (SELECT * FROM t WHERE r_new IS NOT NULL AND r_old IS NOT NULL)
SELECT count(*) 출판사수, sum(n_new)+sum(n_old) 대상논문, (SELECT count(*) FROM b) 신규등록전체,
  round(100.0*(sum(n_new)+sum(n_old))/(SELECT count(*) FROM b),2) 비중,
  round(100.0*sum(n_new*r_new)/sum(n_new),1) 신규실제, round(100.0*sum(n_old*r_old)/sum(n_old),1) 과거실제,
  round(100.0*sum(n_old*r_new)/sum(n_old),1) 과거구성적용, round(100.0*sum(n_new*r_old)/sum(n_new),1) 신규구성적용
FROM ok""")

# ── 2. S1 판 간 비교: 18곳 전체 ──
print("\n[2. 전환 출판연도: 2026년판 대 2023년판 (80%, 지속성)]")
res={}
for base in ("cc26","cc23"):
    res[base]=dict(con.execute(f"""
    WITH y AS (SELECT member, pub_year, count(*) n, avg({base}) r FROM s GROUP BY member, pub_year),
         big AS (SELECT member FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000),
         ok AS (SELECT member, pub_year, min(r) OVER (PARTITION BY member ORDER BY pub_year ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) ma
                FROM y WHERE n >= 100 AND member IN (SELECT member FROM big))
    SELECT member, min(pub_year) FILTER (WHERE ma >= 0.8) FROM ok GROUP BY member""").fetchall())
names=dict(con.execute("SELECT member, any_value(publisher) FROM s GROUP BY member").fetchall())
rows=[(names[m][:32], res['cc26'][m], res['cc23'].get(m)) for m in res['cc26'] if res['cc26'][m] is not None]
print(f"  2026년판 기준 확인된 출판사 {len(rows)}곳")
for r in sorted(rows, key=lambda x:(x[1],x[0])):
    mark = "동일" if r[1]==r[2] else ("2023년판 미확인" if r[2] is None else f"{r[1]}→{r[2]}")
    print(f"    {r[0]:<34} {r[1]}  {mark}")

# ── 3. created 갱신 29건 전수 ──
show("3. B에만 해당하는 DOI 전수 (2023년판 created 대 2026년판 created)", f"""
SELECT b.doi, w.created c23, b.created c26, b.pub_year, any_value(w.publisher) pub
FROM b JOIN (SELECT doi, any_value(created) created, any_value(publisher) publisher
             FROM read_parquet('{P}/2023/works/*.parquet') GROUP BY doi) w USING (doi)
WHERE b.doi IN (SELECT doi FROM in23) GROUP BY 1,2,3,4 ORDER BY 2""")
show("3-2. 요약", f"""
SELECT count(*) 전체, count(DISTINCT substr(doi,1,8)) 접두사수,
  min(substr(c23,1,4)) c23최소연도, max(substr(c23,1,4)) c23최대연도
FROM (SELECT b.doi, any_value(w.created) c23 FROM b JOIN (SELECT doi, created FROM read_parquet('{P}/2023/works/*.parquet')) w USING (doi)
      WHERE b.doi IN (SELECT doi FROM in23) GROUP BY b.doi)""")
