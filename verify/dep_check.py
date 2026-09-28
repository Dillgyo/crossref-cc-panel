"""
deposited 역행 148,327건의 원인 확인

실행
  python dep_check.py

state_panel.parquet만 읽는다.
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

con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1")
# 문자열로 다룬다. state_panel의 열 타입이 무엇이든 비교 방식을 고정한다.
con.execute("""CREATE VIEW d AS SELECT doi, member, publisher, pub_year, cc23, cc26,
  CAST(dep23 AS VARCHAR) a, CAST(dep26 AS VARCHAR) b FROM s""")


def show(t, q):
    cur = con.execute(q)
    print(f"\n[{t}]")
    print("  " + " | ".join(x[0] for x in cur.description))
    for r in cur.fetchall():
        print("  " + " | ".join(
            "" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) for v in r))


show("1. 전체 패널에서의 역행 규모", """
SELECT count(*) 전체,
       count(*) FILTER (WHERE b > a) 증가,
       count(*) FILTER (WHERE b = a) 같음,
       count(*) FILTER (WHERE b < a) 역행,
       count(*) FILTER (WHERE a IS NULL OR b IS NULL) NULL포함 FROM d""")

show("2. 문자열 길이 분포 (형식 차이 확인)", """
SELECT length(a) dep23_길이, length(b) dep26_길이, count(*) 건수
FROM d GROUP BY 1,2 ORDER BY 3 DESC LIMIT 12""")

show("3. 역행 사례의 문자열 길이", """
SELECT length(a) dep23_길이, length(b) dep26_길이, count(*) 건수
FROM d WHERE b < a GROUP BY 1,2 ORDER BY 3 DESC LIMIT 12""")

show("4. 역행 사례에서 날짜 부분(앞 10자)만 비교하면", """
SELECT count(*) 역행전체,
       count(*) FILTER (WHERE substr(b,1,10) = substr(a,1,10)) 같은날,
       count(*) FILTER (WHERE substr(b,1,10) < substr(a,1,10)) 날짜도_이름,
       count(*) FILTER (WHERE substr(b,1,10) > substr(a,1,10)) 날짜는_늦음
FROM d WHERE b < a""")

show("5. 역행 사례 실제 값 20건", """
SELECT doi, a dep23, b dep26, publisher FROM d WHERE b < a
ORDER BY random() LIMIT 20""")

show("6. 날짜까지 다른 역행 사례 20건 (형식 차이로 설명되지 않는 경우)", """
SELECT doi, a dep23, b dep26, publisher FROM d
WHERE b < a AND substr(b,1,10) <> substr(a,1,10)
ORDER BY random() LIMIT 20""")

show("7. 역행이 몰린 출판사 상위 10곳", """
SELECT any_value(publisher) 출판사, count(*) FILTER (WHERE b < a) 역행,
       count(*) 패널논문,
       round(100.0*count(*) FILTER (WHERE b < a)/count(*),1) 비율
FROM d GROUP BY member ORDER BY 2 DESC LIMIT 10""")

show("8. 시점별로 어디서 값이 낮아지는지", """
SELECT count(*) 역행,
       count(*) FILTER (WHERE CAST(dep24 AS VARCHAR) < CAST(dep23 AS VARCHAR)) 이미_2024에서,
       count(*) FILTER (WHERE CAST(dep25 AS VARCHAR) < CAST(dep24 AS VARCHAR)) 2025에서,
       count(*) FILTER (WHERE CAST(dep26 AS VARCHAR) < CAST(dep25 AS VARCHAR)) 2026에서
FROM s WHERE CAST(dep26 AS VARCHAR) < CAST(dep23 AS VARCHAR)""")

print("\n점검 끝")
