import duckdb
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
cur = con.execute("""
SELECT count(*) AS 존속패널,
       sum(cc23) AS y23, sum(cc24) AS y24, sum(cc25) AS y25, sum(cc26) AS y26,
       count(*) FILTER (WHERE cc23=0 AND cc26=1) AS 보강전체,
       count(*) FILTER (WHERE cc23=0 AND cc26=1 AND member IN ('276','2399','317','297','2373')) AS 상위5_보강,
       count(*) FILTER (WHERE cc23=0 AND member NOT IN ('276','2399','317','297','2373')) AS 나머지_미기재,
       count(*) FILTER (WHERE cc23=0 AND cc26=1 AND member NOT IN ('276','2399','317','297','2373')) AS 나머지_보강
FROM s""")
r = dict(zip([d[0] for d in cur.description], cur.fetchone()))
n = r['존속패널']
for y in ('y23','y24','y25','y26'):
    print(y, f"{r[y]:,}", f"{100*r[y]/n:.2f}%")
print("보강 전체", f"{r['보강전체']:,}")
print("상위5 보강", f"{r['상위5_보강']:,}", f"{100*r['상위5_보강']/r['보강전체']:.1f}%")
print("나머지", f"{r['나머지_보강']:,}", "/", f"{r['나머지_미기재']:,}", f"{100*r['나머지_보강']/r['나머지_미기재']:.2f}%")
