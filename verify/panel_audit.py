"""
패널 무결성과 저널 단위 재집계 점검

실행
  python panel_audit.py

확인하는 것
  1. state_panel의 행 수와 DOI 수가 같은지 (DISTINCT로 인한 DOI 중복 여부)
  2. 그림 3을 ISSN 기준으로 다시 세면 저널 수와 구간 분포가 어떻게 달라지는지
  3. 그림 2를 캡션의 규칙(라이선스가 처음 확인된 스냅숏의 deposited)으로 다시 집계한 결과
"""
import duckdb
import os

P = "D:/crossref/parquet"
DOAJ = "D:/crossref/doaj_panel_journals.csv"
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)

con = duckdb.connect()
for q in ["SET threads=4", "SET memory_limit='6GB'",
          "SET preserve_insertion_order=false",
          "SET temp_directory='D:/crossref/_tmp'"]:
    con.execute(q)


def show(t, q):
    cur = con.execute(q)
    print(f"\n[{t}]")
    print("  " + " | ".join(d[0] for d in cur.description))
    for r in cur.fetchall():
        print("  " + " | ".join(
            "" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) for v in r))


con.execute(f"CREATE VIEW st AS SELECT * FROM read_parquet('{P}/state_panel.parquet')")
con.execute("CREATE VIEW s AS SELECT * FROM st WHERE in26=1")

# ------------------------------------------------------------
print("=" * 60)
print("1. 패널 무결성")
print("=" * 60)

show("1-1. 행 수 대 DOI 수", """
SELECT count(*) 전체행, count(DISTINCT doi) 고유DOI, count(*) - count(DISTINCT doi) 중복행 FROM st""")

show("1-2. in26=1 기준 (논문의 7,215,883과 대조)", """
SELECT count(*) 전체행, count(DISTINCT doi) 고유DOI, count(*) - count(DISTINCT doi) 중복행 FROM s""")

show("1-3. 한 DOI가 여러 행으로 남은 원인", """
SELECT count(*) 중복DOI수,
       count(*) FILTER (WHERE n_ct > 1) 저널명이_다름,
       count(*) FILTER (WHERE n_cr > 1) created가_다름,
       count(*) FILTER (WHERE n_py > 1) 출판연도가_다름,
       count(*) FILTER (WHERE n_mb > 1) member가_다름
FROM (SELECT doi, count(*) n,
             count(DISTINCT container_title) n_ct, count(DISTINCT created) n_cr,
             count(DISTINCT pub_year) n_py, count(DISTINCT member) n_mb
      FROM st GROUP BY doi HAVING count(*) > 1)""")

show("1-4. container_title 결측", """
SELECT count(*) FILTER (WHERE container_title IS NULL) 저널명_NULL,
       count(*) FILTER (WHERE trim(coalesce(container_title,'')) = '') 저널명_빈값 FROM s""")

# ------------------------------------------------------------
print()
print("=" * 60)
print("2. 그림 3 저널 단위: 저널명 기준 대 ISSN 기준")
print("=" * 60)

con.execute(f"""CREATE TABLE jissn AS
WITH j AS (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e
           FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true))
SELECT upper(trim(issn)) issn FROM j, UNNEST([p, e]) t(issn)
WHERE issn IS NOT NULL AND trim(issn) <> '' GROUP BY 1""")

# 논문을 저널(ISSN)에 다시 연결. 한 DOI가 두 저널에 걸리면 양쪽에 계수된다.
con.execute(f"""CREATE TABLE di AS
SELECT DISTINCT w.doi, w.issn FROM
 (SELECT doi, upper(trim(t.s)) issn
  FROM read_parquet('{P}/2023/works/*.parquet'), UNNEST(str_split(issn,';')) t(s)) w
JOIN jissn j USING (issn)
WHERE w.doi IN (SELECT doi FROM s)""")

BUCKET = """CASE WHEN a = 0 THEN '1 0%'
                 WHEN r <= 5 THEN '2 0~5%'
                 WHEN r <= 25 THEN '3 5~25%'
                 WHEN r <= 50 THEN '4 25~50%'
                 WHEN r <= 75 THEN '5 50~75%'
                 WHEN r <= 95 THEN '6 75~95%'
                 ELSE '7 95% 초과' END"""

show("2-1. 저널명 기준 (현재 그림 3)", f"""
WITH t AS (SELECT container_title k,
             count(*) FILTER (WHERE cc23=0) n,
             count(*) FILTER (WHERE cc23=0 AND cc26=1) a
           FROM s GROUP BY container_title
           HAVING count(*) FILTER (WHERE cc23=0) >= 100),
     u AS (SELECT k, n, a, 100.0*a/n r FROM t)
SELECT {BUCKET} 구간, count(*) 저널수 FROM u GROUP BY 1 ORDER BY 1""")

show("2-2. ISSN 기준", f"""
WITH t AS (SELECT d.issn k,
             count(*) FILTER (WHERE s.cc23=0) n,
             count(*) FILTER (WHERE s.cc23=0 AND s.cc26=1) a
           FROM s JOIN di d USING (doi) GROUP BY d.issn
           HAVING count(*) FILTER (WHERE s.cc23=0) >= 100),
     u AS (SELECT k, n, a, 100.0*a/n r FROM t)
SELECT {BUCKET} 구간, count(*) 저널수 FROM u GROUP BY 1 ORDER BY 1""")

show("2-3. 두 기준의 저널 수 합계", f"""
WITH ct AS (SELECT count(*) n FROM (SELECT container_title FROM s GROUP BY 1
              HAVING count(*) FILTER (WHERE cc23=0) >= 100)),
     iss AS (SELECT count(*) n FROM (SELECT d.issn FROM s JOIN di d USING (doi) GROUP BY 1
              HAVING count(*) FILTER (WHERE s.cc23=0) >= 100))
SELECT (SELECT n FROM ct) 저널명기준, (SELECT n FROM iss) ISSN기준""")

# ------------------------------------------------------------
print()
print("=" * 60)
print("3. 그림 2 월 정의 비교")
print("=" * 60)

show("3-1. 현재 코드 (dep26 우선) 대 캡션 규칙 (처음 확인된 스냅숏)", """
WITH b AS (SELECT
   substr(CAST(coalesce(dep26,dep25,dep24) AS VARCHAR),1,7) m_now,
   substr(CAST(CASE WHEN cc24=1 THEN dep24 WHEN cc25=1 THEN dep25 ELSE dep26 END AS VARCHAR),1,7) m_first
 FROM s WHERE cc23=0 AND cc26=1)
SELECT count(*) 보완전체, count(*) FILTER (WHERE m_now = m_first) 같은달,
       count(*) FILTER (WHERE m_now <> m_first) 다른달,
       round(100.0*count(*) FILTER (WHERE m_now <> m_first)/count(*),1) 다른달_비율 FROM b""")

show("3-2. 캡션 규칙으로 집계한 상위 12개월", """
SELECT substr(CAST(CASE WHEN cc24=1 THEN dep24 WHEN cc25=1 THEN dep25 ELSE dep26 END AS VARCHAR),1,7) 월,
       count(*) 보완건수
FROM s WHERE cc23=0 AND cc26=1 GROUP BY 1 ORDER BY 2 DESC LIMIT 12""")

show("3-3. 현재 코드로 집계한 상위 12개월 (대조용)", """
SELECT substr(CAST(coalesce(dep26,dep25,dep24) AS VARCHAR),1,7) 월, count(*) 보완건수
FROM s WHERE cc23=0 AND cc26=1 GROUP BY 1 ORDER BY 2 DESC LIMIT 12""")

print("\n점검 끝")
