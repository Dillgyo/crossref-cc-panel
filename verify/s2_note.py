"""
표 S2 각주의 4,092건이 어느 정의에서 나오는지 찾는다.

실행
  python s2_note.py
"""
import os
import duckdb

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
P = f"{ROOT}/parquet"
os.makedirs(f"{ROOT}/_tmp", exist_ok=True)

con = duckdb.connect()
for q in ["SET threads=4", "SET memory_limit='6GB'",
          "SET preserve_insertion_order=false",
          f"SET temp_directory='{ROOT}/_tmp'"]:
    con.execute(q)

CCQ = ("url ILIKE '%creativecommons.org%' "
       "AND coalesce(content_version,'') IN ('vor','am','unspecified')")

con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1")
con.execute("CREATE TABLE addx AS SELECT * FROM s WHERE cc23=0 AND cc26=1")
con.execute(f"CREATE VIEW l26 AS SELECT * FROM read_parquet('{P}/2026/licenses/*.parquet')")
con.execute(f"""CREATE TABLE py26 AS
SELECT doi, min(pub_year) py_min, max(pub_year) py_max
FROM read_parquet('{P}/2026/works/*.parquet') GROUP BY doi""")

# DOI 단위 start: 최솟값과 최댓값을 모두 만든다
con.execute(f"""CREATE TABLE st AS
SELECT a.doi, a.pub_year py23,
       min(CAST(l.start AS VARCHAR)) st_min, max(CAST(l.start AS VARCHAR)) st_max
FROM addx a JOIN l26 l USING (doi) WHERE {CCQ} GROUP BY 1,2""")


def show(t, q):
    cur = con.execute(q)
    print(f"\n[{t}]")
    print("  " + " | ".join(d[0] for d in cur.description))
    for r in cur.fetchall():
        print("  " + " | ".join(
            "" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) for v in r))


show("0. 기준 확인 (보충자료: 12,775 / 4,092)", """
SELECT count(*) 대상,
       count(*) FILTER (WHERE CAST(substr(st_min,1,4) AS INT) >= 2023) start최솟값_2023이상,
       count(*) FILTER (WHERE CAST(substr(st_max,1,4) AS INT) >= 2023) start최댓값_2023이상
FROM st""")

show("1. 출판연도를 어디서 가져오는가", """
SELECT count(*) FILTER (WHERE CAST(substr(st_min,1,4) AS INT) >= 2023 AND s.py23 >= 2023) 패널_pub_year,
       count(*) FILTER (WHERE CAST(substr(st_min,1,4) AS INT) >= 2023 AND p.py_min >= 2023) y2026_최솟값,
       count(*) FILTER (WHERE CAST(substr(st_min,1,4) AS INT) >= 2023 AND p.py_max >= 2023) y2026_최댓값
FROM st s LEFT JOIN py26 p USING (doi)""")

show("2. start를 최댓값으로 잡으면", """
SELECT count(*) FILTER (WHERE CAST(substr(st_max,1,4) AS INT) >= 2023 AND s.py23 >= 2023) 패널_pub_year,
       count(*) FILTER (WHERE CAST(substr(st_max,1,4) AS INT) >= 2023 AND p.py_min >= 2023) y2026_최솟값
FROM st s LEFT JOIN py26 p USING (doi)""")

show("3. 라이선스 행 단위로 세면", f"""
SELECT count(*) 행수, count(DISTINCT l.doi) DOI수
FROM l26 l JOIN addx a USING (doi)
WHERE {CCQ} AND CAST(substr(CAST(l.start AS VARCHAR),1,4) AS INT) >= 2023 AND a.pub_year >= 2023""")

show("4. 패널의 출판연도 분포 (2023년 이상)", """
SELECT py23 출판연도, count(*) 건수 FROM st WHERE py23 >= 2022 GROUP BY 1 ORDER BY 1""")

show("5. 2026년판과 패널의 출판연도가 다른 보완 레코드", """
SELECT count(*) 전체, count(*) FILTER (WHERE s.py23 <> p.py_min) 출판연도_다름
FROM st s JOIN py26 p USING (doi)""")

print("\n점검 끝. 4,092가 나오는 열이 원래 정의다.")
