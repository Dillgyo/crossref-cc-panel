import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
src = "read_parquet('D:/crossref/parquet/2026/works/*.parquet')"
dups = [r[0] for r in con.execute(
    f"SELECT doi FROM {src} GROUP BY doi HAVING count(*) > 1").fetchall()]
print("중복 DOI", len(dups), "개")
for d in dups:
    print("=" * 60)
    print(d)
    for r in con.execute(
        f"SELECT member, publisher, container_title, pub_year, created, deposited, n_license "
        f"FROM {src} WHERE doi = ?", [d]).fetchall():
        print("  ", r)
