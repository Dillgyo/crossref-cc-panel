import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")

def show(title, q):
    cur = con.execute(q); cols=[d[0] for d in cur.description]
    print("\n["+title+"]"); print("  "+" | ".join(cols))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

show("1. Wolters Kluwer 보강분의 재등록 월 (2024 스냅숏 기준)", """
SELECT substr(dep24,1,7) AS 재등록월, count(*) AS 논문수
FROM s WHERE member='276' AND cc23=0 AND cc24=1
GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")

show("2. AIP 보강분의 재등록 월 (2026 스냅숏 기준)", """
SELECT substr(dep26,1,7) AS 재등록월, count(*) AS 논문수
FROM s WHERE member='317' AND cc23=0 AND cc26=1
GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")

show("3. Editorial CSIC 보강분의 재등록 월 (2025 스냅숏 기준)", """
SELECT substr(dep25,1,7) AS 재등록월, count(*) AS 논문수
FROM s WHERE member='2373' AND cc23=0 AND cc25=1
GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")

show("4. OpenEdition 보강분의 재등록 월", """
SELECT substr(coalesce(dep25,dep26),1,7) AS 재등록월, count(*) AS 논문수
FROM s WHERE member='2399' AND cc23=0 AND cc26=1
GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")

show("5. 보강 상위 5곳: 재등록이 한 달에 몰린 정도", """
WITH b AS (SELECT member, doi, substr(coalesce(dep26,dep25,dep24),1,7) AS m
           FROM s WHERE cc23=0 AND cc26=1 AND member IN ('276','2399','317','297','2373')),
     c AS (SELECT member, m, count(*) AS n FROM b GROUP BY 1,2),
     t AS (SELECT member, sum(n) AS total, max(n) AS top FROM c GROUP BY 1)
SELECT member, total AS 보강건수, top AS 최다월_건수,
       round(100.0*top/total,1) AS 최다월_비중
FROM t ORDER BY 2 DESC""")

show("6. 전체 보강분: 재등록 월 상위 10개", """
SELECT substr(coalesce(dep26,dep25,dep24),1,7) AS 재등록월, count(*) AS 논문수
FROM s WHERE cc23=0 AND cc26=1 GROUP BY 1 ORDER BY 2 DESC LIMIT 10""")
