"""
deposited 역행이 어느 시점에서 발생했는지, 오프셋이 정확히 몇 시간인지 확인

실행
  python dep_check2.py
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

con.execute(f"""CREATE VIEW d AS
SELECT doi, member, publisher,
       CAST(dep23 AS VARCHAR) d23, CAST(dep24 AS VARCHAR) d24,
       CAST(dep25 AS VARCHAR) d25, CAST(dep26 AS VARCHAR) d26,
       cc23, cc26
FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1""")


def show(t, q):
    cur = con.execute(q)
    print(f"\n[{t}]")
    print("  " + " | ".join(x[0] for x in cur.description))
    for r in cur.fetchall():
        print("  " + " | ".join(
            "" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) for v in r))


# 별칭이 숫자로 시작하면 DuckDB가 거부한다. 앞에 글자를 붙인다.
show("1. 역행이 처음 나타나는 구간", """
SELECT count(*) AS 역행전체,
       count(*) FILTER (WHERE d24 < d23) AS y24_에서_낮아짐,
       count(*) FILTER (WHERE d25 < d24) AS y25_에서_낮아짐,
       count(*) FILTER (WHERE d26 < d25) AS y26_에서_낮아짐,
       count(*) FILTER (WHERE d24 = d23 AND d25 = d24 AND d26 = d25) AS 변화없음
FROM d WHERE d26 < d23""")

show("2. 각 구간별 역행 규모 (전체 패널)", """
SELECT count(*) AS 전체,
       count(*) FILTER (WHERE d24 < d23) AS y23_to_y24,
       count(*) FILTER (WHERE d25 < d24) AS y24_to_y25,
       count(*) FILTER (WHERE d26 < d25) AS y25_to_y26
FROM d""")

show("3. 오프셋 시간 분포 (역행 사례)", """
SELECT CAST(round(date_diff('minute', strptime(d26, '%Y-%m-%dT%H:%M:%SZ'),
                            strptime(d23, '%Y-%m-%dT%H:%M:%SZ')) / 60.0, 2) AS VARCHAR) AS 차이_시간,
       count(*) AS 건수
FROM d WHERE d26 < d23 GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")

show("4. 4시간 차이와 5시간 차이가 서머타임과 맞는지", """
WITH x AS (SELECT strptime(d23, '%Y-%m-%dT%H:%M:%SZ') t23,
                  date_diff('hour', strptime(d26, '%Y-%m-%dT%H:%M:%SZ'),
                                    strptime(d23, '%Y-%m-%dT%H:%M:%SZ')) h
           FROM d WHERE d26 < d23)
SELECT h AS 차이_시간, count(*) AS 건수,
       min(month(t23)) AS 최소월, max(month(t23)) AS 최대월
FROM x GROUP BY 1 ORDER BY 2 DESC LIMIT 10""")

show("5. 역행 사례 가운데 보완이 일어난 건수", """
SELECT count(*) AS 역행, count(*) FILTER (WHERE cc23=0) AS 미기재,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) AS 보완,
       count(*) FILTER (WHERE cc23=1 AND cc26=0) AS 소실
FROM d WHERE d26 < d23""")

show("6. 오프셋을 보정하면 실제로 재등록된 것이 있는지", """
WITH x AS (SELECT strptime(d23, '%Y-%m-%dT%H:%M:%SZ') t23,
                  strptime(d26, '%Y-%m-%dT%H:%M:%SZ') t26, cc23, cc26
           FROM d WHERE d26 < d23)
SELECT count(*) AS 역행전체,
       count(*) FILTER (WHERE date_diff('hour', t26, t23) IN (4, 5)) AS 오프셋만,
       count(*) FILTER (WHERE date_diff('hour', t26, t23) NOT IN (4, 5)) AS 그밖의_차이,
       count(*) FILTER (WHERE date_diff('hour', t26, t23) NOT IN (4, 5) AND cc23=0 AND cc26=1) AS 그밖에서_보완
FROM x""")

print("\n점검 끝")
