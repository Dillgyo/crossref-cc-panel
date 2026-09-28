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
con.execute(f"""CREATE TABLE w26 AS SELECT doi, pub_year, created FROM (
  SELECT doi, pub_year, created, upper(trim(t.s)) issn FROM read_parquet('{P}/2026/works/*.parquet'), UNNEST(str_split(issn,';')) t(s)) w
  JOIN jissn j USING (issn) WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026""")
con.execute("CREATE TABLE u AS SELECT doi, any_value(pub_year) pub_year, any_value(created) created FROM w26 GROUP BY doi")
con.execute(f"CREATE TABLE in23 AS SELECT DISTINCT doi FROM read_parquet('{P}/2023/works/*.parquet')")
con.execute(f"""CREATE TABLE cc AS SELECT DISTINCT doi FROM read_parquet('{P}/2026/licenses/*.parquet')
  WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')""")
con.execute("CREATE TABLE ua AS SELECT *, doi NOT IN (SELECT doi FROM in23) a, created >= '2023-04-01' b FROM u")

show("1-1. 같은 조건의 집합 대조 (DOI 단위)", """SELECT count(*) 전체, count(*) FILTER (WHERE a AND b) 교집합,
  count(*) FILTER (WHERE a AND NOT b) A만, count(*) FILTER (WHERE b AND NOT a) B만, count(*) FILTER (WHERE b) B전체 FROM ua""")
show("1-2. 표 7 재계산 (B 기준, DOI 단위)", """SELECT CASE WHEN pub_year>=2023 THEN '2023년 이후 출판' ELSE '과거 출판' END 구분,
  count(*) 논문수, count(*) FILTER (WHERE doi IN (SELECT doi FROM cc)) 기재건수,
  round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc))/count(*),1) 기재율 FROM ua WHERE b GROUP BY 1 ORDER BY 1""")
show("1-3. 두 저널에 걸친 DOI (출판연도 기준 중복 가능성)", "SELECT count(*) FROM (SELECT doi FROM w26 GROUP BY doi HAVING count(DISTINCT pub_year)>1 OR count(*)>1)")
show("1-4. B만 29건: 2023년판 created와 2026년판 created 비교", f"""
SELECT u.doi, w.created c23, u.created c26 FROM ua u
JOIN (SELECT doi, any_value(created) created FROM read_parquet('{P}/2023/works/*.parquet') GROUP BY doi) w USING (doi)
WHERE u.b AND NOT u.a LIMIT 10""")

show("3. S2 교차표: start 연도와 출판연도의 관계 × 2023년 이상 여부", f"""
WITH d AS (SELECT l.doi, min(CAST(substr(CAST(l.start AS VARCHAR),1,4) AS INT)) sy
           FROM read_parquet('{P}/2026/licenses/*.parquet') l JOIN (SELECT doi FROM s WHERE cc23=0 AND cc26=1) a USING (doi)
           WHERE l.url ILIKE '%creativecommons.org%' AND coalesce(l.content_version,'') IN ('vor','am','unspecified') GROUP BY l.doi)
SELECT CASE WHEN d.sy <= s.pub_year THEN '1 start ≤ 출판연도' ELSE '2 start > 출판연도' END 관계,
  CASE WHEN d.sy >= 2023 THEN 'start ≥ 2023' ELSE 'start < 2023' END 시기, count(*) n
FROM d JOIN s USING (doi) GROUP BY 1,2 ORDER BY 1,2""")

print("\n[2. S1 비교: 출판사별 전환 출판연도]")
res = {}
for base in ("cc26","cc23"):
    for th in (0.7,0.8,0.9):
        res[(base,th)] = dict(con.execute(f"""
        WITH y AS (SELECT member, pub_year, count(*) n, avg({base}) r FROM s GROUP BY member, pub_year),
             big AS (SELECT member FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000),
             ok AS (SELECT member, pub_year, min(r) OVER (PARTITION BY member ORDER BY pub_year ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) ma
                    FROM y WHERE n >= 100 AND member IN (SELECT member FROM big))
        SELECT member, min(pub_year) FILTER (WHERE ma >= {th}) FROM ok GROUP BY member""").fetchall())
names = dict(con.execute("SELECT member, any_value(publisher) FROM s GROUP BY member").fetchall())
main = res[("cc26",0.8)]
def cmp(d):
    same_y = sum(1 for m in main if main[m] is not None and main[m]==d.get(m))
    both_none = sum(1 for m in main if main[m] is None and d.get(m) is None)
    diff = [(names[m][:25], main[m], d.get(m)) for m in main if main[m] is not None and d.get(m) is not None and main[m]!=d.get(m)]
    one = [(names[m][:25], main[m], d.get(m)) for m in main if (main[m] is None) != (d.get(m) is None)]
    return same_y, both_none, diff, one
for k in [("cc26",0.7),("cc26",0.9),("cc23",0.8),("cc23",0.7),("cc23",0.9)]:
    sy, bn, diff, one = cmp(res[k])
    print(f"\n  기준(2026·80%) 대 {k[0]}·{int(k[1]*100)}%: 같은 연도 {sy}, 양쪽 모두 없음 {bn}, 다른 연도 {len(diff)}, 한쪽만 있음 {len(one)}")
    for x in diff: print("    다른 연도:", x)
    for x in one: print("    한쪽만:", x)
