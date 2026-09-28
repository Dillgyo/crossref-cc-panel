"""deposited 역행의 오프셋이 미국 동부 시간대와 맞는지 월별로 확인한다."""
import os
import duckdb

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute(f"""CREATE VIEW d AS
SELECT CAST(dep23 AS VARCHAR) a, CAST(dep26 AS VARCHAR) b
FROM read_parquet('{ROOT}/parquet/state_panel.parquet') WHERE in26=1""")

q = """
WITH x AS (
  SELECT month(strptime(a, '%Y-%m-%dT%H:%M:%SZ')) AS m,
         date_diff('hour', strptime(b, '%Y-%m-%dT%H:%M:%SZ'),
                           strptime(a, '%Y-%m-%dT%H:%M:%SZ')) AS h
  FROM d WHERE b < a)
SELECT m AS 월,
       count(*) FILTER (WHERE h = 4) AS 네시간,
       count(*) FILTER (WHERE h = 5) AS 다섯시간,
       count(*) FILTER (WHERE h NOT IN (4, 5)) AS 그밖
FROM x GROUP BY 1 ORDER BY 1"""

cur = con.execute(q)
print("  " + " | ".join(x[0] for x in cur.description))
for r in cur.fetchall():
    print("  " + " | ".join(f"{v:,}" if isinstance(v, int) else str(v) for v in r))
print("\n3~10월이 네시간, 11~2월이 다섯시간으로 갈리면 미국 동부 시간대다.")
