import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
for y in ("2023","2026"):
    con.execute(f"""CREATE TABLE loose{y} AS SELECT DISTINCT doi FROM
    read_parquet('D:/crossref/parquet/{y}/licenses/*.parquet') WHERE url ILIKE '%creativecommons.org%'""")

print("[민감도: 대상 / 보강 / 보강률]")
for lab, cond in [("본 분석","1=1"),("하한 2010","pub_year>=2010"),("하한 2015","pub_year>=2015"),("하한 2020","pub_year>=2020")]:
    r = con.execute(f"""SELECT count(*) FILTER (WHERE cc23=0), count(*) FILTER (WHERE cc23=0 AND cc26=1) FROM s WHERE {cond}""").fetchone()
    print(f"  {lab}: {r[0]:,} / {r[1]:,} / {100*r[1]/r[0]:.2f}%")
r = con.execute("""SELECT count(*) FILTER (WHERE l23.doi IS NULL),
       count(*) FILTER (WHERE l23.doi IS NULL AND l26.doi IS NOT NULL)
FROM s LEFT JOIN loose2023 l23 USING (doi) LEFT JOIN loose2026 l26 USING (doi)""").fetchone()
print(f"  tdm 포함: {r[0]:,} / {r[1]:,} / {100*r[1]/r[0]:.2f}%")

print("\n[주요 출판사군의 member 목록]")
for r in con.execute("""
SELECT member, any_value(publisher) AS publisher, count(*) AS n,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) AS 보강
FROM s WHERE lower(publisher) LIKE '%wolters%' OR lower(publisher) LIKE '%ovid%'
   OR lower(publisher) LIKE '%medknow%' OR lower(publisher) LIKE '%lippincott%'
   OR lower(publisher) LIKE '%springer%' OR lower(publisher) LIKE '%nature%'
   OR lower(publisher) LIKE '%scielo%' OR lower(publisher) LIKE '%aip%'
   OR lower(publisher) LIKE '%csic%' OR lower(publisher) LIKE '%openedition%'
GROUP BY member ORDER BY 3 DESC""").fetchall():
    print(" ", r)
