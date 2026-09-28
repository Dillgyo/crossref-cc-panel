"""
그림 3 저널 단위 재집계 (수정판)

앞 판은 ISSN 단위로 묶어 인쇄판·온라인판 ISSN을 모두 가진 저널을 두 번 세었다.
이번에는 DOAJ 저널(행)에 번호를 붙여 저널 단위로 묶는다.

실행
  python panel_audit2.py
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


con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1")

# DOAJ 저널에 번호를 붙이고, ISSN -> 저널번호 대응표를 만든다.
con.execute(f"""CREATE TABLE jrow AS
SELECT row_number() OVER () jid,
       "Journal title" title,
       upper(trim("Journal ISSN (print version)")) p,
       upper(trim("Journal EISSN (online version)")) e
FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true)""")

con.execute("""CREATE TABLE j2i AS
SELECT jid, issn FROM jrow, UNNEST([p, e]) t(issn)
WHERE issn IS NOT NULL AND trim(issn) <> ''""")

show("0. 대응표 점검 (ISSN 하나가 저널 하나에 대응하는지)", """
SELECT count(*) 대응행, count(DISTINCT issn) 고유ISSN, count(DISTINCT jid) 저널수,
       count(*) - count(DISTINCT issn) ISSN중복 FROM j2i""")

# 논문 -> 저널. 한 DOI가 두 저널에 걸리면 양쪽에 계수된다 (논문 3.2절의 처리와 같음).
con.execute(f"""CREATE TABLE dj AS
SELECT DISTINCT w.doi, m.jid FROM
 (SELECT doi, upper(trim(t.s)) issn
  FROM read_parquet('{P}/2023/works/*.parquet'), UNNEST(str_split(issn,';')) t(s)) w
JOIN j2i m USING (issn)
WHERE w.doi IN (SELECT doi FROM s)""")

show("1. 분석 패널에 논문이 있는 저널 수 (논문의 11,949와 대조)", """
SELECT count(DISTINCT jid) 저널수, count(DISTINCT doi) 논문수, count(*) 연결행수 FROM dj""")

show("2. 한 DOI가 여러 저널에 걸리는 경우", """
SELECT count(*) DOI수 FROM (SELECT doi FROM dj GROUP BY doi HAVING count(*) > 1)""")

BUCKET = """CASE WHEN a = 0 THEN '1 0%'
                 WHEN r <= 5 THEN '2 0~5%'
                 WHEN r <= 25 THEN '3 5~25%'
                 WHEN r <= 50 THEN '4 25~50%'
                 WHEN r <= 75 THEN '5 50~75%'
                 WHEN r <= 95 THEN '6 75~95%'
                 ELSE '7 95% 초과' END"""

show("3. 저널(DOAJ 행) 기준 보완율 구간 분포", f"""
WITH t AS (SELECT d.jid,
             count(*) FILTER (WHERE s.cc23=0) n,
             count(*) FILTER (WHERE s.cc23=0 AND s.cc26=1) a
           FROM s JOIN dj d USING (doi) GROUP BY d.jid
           HAVING count(*) FILTER (WHERE s.cc23=0) >= 100),
     u AS (SELECT jid, n, a, 100.0*a/n r FROM t)
SELECT {BUCKET} 구간, count(*) 저널수 FROM u GROUP BY 1 ORDER BY 1""")

show("4. 세 기준의 저널 수 비교 (미기재 100건 이상)", f"""
WITH ct AS (SELECT count(*) n FROM (SELECT container_title FROM s GROUP BY 1
              HAVING count(*) FILTER (WHERE cc23=0) >= 100)),
     jd AS (SELECT count(*) n FROM (SELECT d.jid FROM s JOIN dj d USING (doi) GROUP BY 1
              HAVING count(*) FILTER (WHERE s.cc23=0) >= 100))
SELECT (SELECT n FROM ct) 저널명기준, (SELECT n FROM jd) DOAJ저널기준""")

show("5. 저널명 하나에 DOAJ 저널이 여럿 묶인 사례 상위", """
SELECT s.container_title 저널명, count(DISTINCT d.jid) 묶인저널수, count(*) 논문수
FROM s JOIN dj d USING (doi) GROUP BY 1
HAVING count(DISTINCT d.jid) > 1 ORDER BY 2 DESC, 3 DESC LIMIT 10""")

show("6. DOAJ 저널 하나가 여러 저널명으로 나뉜 사례 상위", """
SELECT any_value(j.title) DOAJ저널명, count(DISTINCT s.container_title) 나뉜이름수, count(*) 논문수
FROM s JOIN dj d USING (doi) JOIN jrow j ON j.jid = d.jid
GROUP BY d.jid HAVING count(DISTINCT s.container_title) > 1 ORDER BY 2 DESC, 3 DESC LIMIT 10""")

print("\n점검 끝")
