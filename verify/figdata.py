import duckdb, csv, os
os.makedirs(r"D:\crossref\figs", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")

def save(name, q):
    cur = con.execute(q)
    p = f"D:/crossref/figs/{name}.csv"
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow([d[0] for d in cur.description]); w.writerows(cur.fetchall())
    print("저장:", p)

# 그림1: 출판연도별 시점별 기재율
save("fig1_year_by_snapshot", """
SELECT pub_year AS 출판연도, count(*) AS 논문수,
       round(100.0*avg(cc23),2) AS y2023, round(100.0*avg(cc24),2) AS y2024,
       round(100.0*avg(cc25),2) AS y2025, round(100.0*avg(cc26),2) AS y2026
FROM s GROUP BY 1 ORDER BY 1""")

# 그림2: 월별 보강 건수
save("fig2_monthly_backfill", """
SELECT substr(coalesce(dep26,dep25,dep24),1,7) AS 재등록월, count(*) AS 보강건수
FROM s WHERE cc23=0 AND cc26=1 GROUP BY 1 HAVING 재등록월 >= '2023-04' ORDER BY 1""")

# 그림3: 저널별 보강률 분포
save("fig3_journal_backfill", """
SELECT container_title AS 저널, any_value(publisher) AS 출판사,
       count(*) FILTER (WHERE cc23=0) AS 비었음,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),2) AS 보강률
FROM s GROUP BY container_title HAVING count(*) FILTER (WHERE cc23=0) >= 100 ORDER BY 3 DESC""")

# 표3: 출판사별 종합 (비었음 1만 건 이상)
save("tab3_publisher", """
SELECT any_value(publisher) AS 출판사, count(*) AS 패널논문수,
       round(100.0*avg(cc23),1) AS 기재율2023, count(*) FILTER (WHERE cc23=0) AS 비었음,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) AS 보강됨,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),1) AS 보강률,
       round(100.0*avg(cc26),1) AS 기재율2026
FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000 ORDER BY 4 DESC""")
