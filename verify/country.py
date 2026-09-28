import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
DOAJ = "D:/doaj_journalcsv_20260817_2320_utf8.csv"

# 원본에서 국가·언어 열 이름 찾기
cur = con.execute(f"SELECT * FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true) LIMIT 1")
cols = [d[0] for d in cur.description]
cand = [c for c in cols if 'ountry' in c or 'anguage' in c]
print("[열 이름 후보]")
for c in cand: print("  ", c)

CTRY = [c for c in cand if 'ountry' in c][0]
LANG = [c for c in cand if 'anguage' in c][0]
print(f"\n사용: 국가='{CTRY}' / 언어='{LANG}'")

con.execute(f"""CREATE TABLE jmeta AS
WITH j AS (SELECT upper(trim("Journal ISSN (print version)")) AS p,
                  upper(trim("Journal EISSN (online version)")) AS e,
                  "{CTRY}" AS country, "{LANG}" AS lang
           FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true))
SELECT upper(trim(issn)) AS issn, any_value(country) AS country, any_value(lang) AS lang
FROM j, UNNEST([p,e]) AS t(issn) WHERE issn IS NOT NULL AND issn <> '' GROUP BY 1""")

con.execute("""CREATE TABLE w23 AS SELECT doi, upper(trim(t.s)) AS issn
  FROM read_parquet('D:/crossref/parquet/2023/works/*.parquet'), UNNEST(str_split(issn,';')) AS t(s)""")
con.execute("""CREATE TABLE p AS
SELECT DISTINCT s.doi, s.cc23, s.cc26, m.country, m.lang
FROM read_parquet('D:/crossref/parquet/state_panel.parquet') s
JOIN w23 w USING (doi) JOIN jmeta m USING (issn) WHERE s.in26=1""")

def show(t,q):
    cur=con.execute(q); print("\n["+t+"]"); print("  "+" | ".join(d[0] for d in cur.description))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

show("1. 국가별 미식별률 (논문 2만 건 이상)", """
SELECT country AS 국가, count(*) AS 논문수,
       round(100.0*(1-avg(cc23)),1) AS 미식별_2023,
       round(100.0*(1-avg(cc26)),1) AS 미식별_2026,
       round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/nullif(count(*) FILTER (WHERE cc23=0),0),2) AS 보완율
FROM p GROUP BY 1 HAVING count(*) >= 20000 ORDER BY 4 DESC""")

show("2. 상위·하위 요약", """
WITH t AS (SELECT country, count(*) AS n, 100.0*(1-avg(cc26)) AS gap FROM p GROUP BY 1 HAVING count(*) >= 20000)
SELECT round(min(gap),1) AS 최저, round(median(gap),1) AS 중앙값, round(max(gap),1) AS 최고, count(*) AS 국가수 FROM t""")

show("3. 언어별 (논문 2만 건 이상)", """
SELECT lang AS 언어, count(*) AS 논문수,
       round(100.0*(1-avg(cc26)),1) AS 미식별_2026
FROM p GROUP BY 1 HAVING count(*) >= 20000 ORDER BY 3 DESC LIMIT 15""")
