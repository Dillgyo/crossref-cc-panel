import duckdb
con = duckdb.connect()
con.execute("""
CREATE TABLE j AS SELECT * FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true)
""")
print("행 수:", con.execute("SELECT count(*) FROM j").fetchone()[0])
print("고유 저널명:", con.execute("""SELECT count(DISTINCT "Journal title") FROM j""").fetchone()[0])
print("\n[같은 이름이 여러 번 나오는 저널]")
for r in con.execute("""
SELECT "Journal title", count(*) AS n,
       string_agg("Journal EISSN (online version)", ' / ') AS eissn,
       string_agg("Publisher", ' / ') AS pub
FROM j GROUP BY 1 HAVING count(*) > 1 ORDER BY 2 DESC LIMIT 15""").fetchall():
    print(" ", r)
