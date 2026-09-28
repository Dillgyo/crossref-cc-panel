import duckdb
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("CREATE VIEW st AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet')")
con.execute("CREATE VIEW s AS SELECT * FROM st WHERE in26=1")

print("[1. 중간 시점 레코드 부재 여부]")
for r in con.execute("""
SELECT count(*) AS 최종패널,
       count(*) FILTER (WHERE in24=0) AS 없음2024,
       count(*) FILTER (WHERE in25=0) AS 없음2025,
       count(*) FILTER (WHERE in24=0 OR in25=0) AS 중간부재
FROM s""").fetchall(): print("  ", r)

print("\n[2. 1001 패턴 2,612건의 중간 시점 레코드 존재 여부]")
for r in con.execute("""
SELECT count(*) AS 전체, count(*) FILTER (WHERE in24=1 AND in25=1) AS 양쪽존재,
       count(*) FILTER (WHERE in24=0 OR in25=0) AS 레코드부재
FROM s WHERE cc23=1 AND cc24=0 AND cc25=0 AND cc26=1""").fetchall(): print("  ", r)

print("\n[3. 중간 변동·보완 전체에서 레코드 부재가 섞였는지]")
for r in con.execute("""
SELECT CASE WHEN cc23=1 AND cc24=1 AND cc25=1 AND cc26=1 THEN '1111'
            WHEN cc23=0 AND cc24=0 AND cc25=0 AND cc26=0 THEN '0000'
            WHEN cc23=0 AND cc26=1 THEN '보완'
            WHEN cc23=1 AND cc26=0 THEN '소실'
            ELSE '중간변동' END AS 구분,
       count(*) AS 논문수, count(*) FILTER (WHERE in24=0 OR in25=0) AS 레코드부재포함
FROM s GROUP BY 1 ORDER BY 2 DESC""").fetchall(): print("  ", r)

print("\n[4. 레코드 부재를 제외했을 때 핵심 수치]")
for r in con.execute("""
SELECT count(*) FILTER (WHERE cc23=0) AS 미기재,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) AS 보완,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/count(*) FILTER (WHERE cc23=0),2) AS 보완율
FROM s WHERE in24=1 AND in25=1""").fetchall(): print("  ", r)

print("\n[5. 2026 전체 대상 논문의 단면 기재율 (신규 포함)]")
for r in con.execute("""
SELECT round(100.0*avg(cc26),1) AS 코호트내_2026기재율 FROM s""").fetchall(): print("  ", r)
