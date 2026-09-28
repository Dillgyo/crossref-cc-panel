import os
﻿import duckdb, json, random, time, urllib.parse, urllib.request
MAIL = os.environ.get("CROSSREF_MAILTO", "")   # 바꾸세요

con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("""CREATE TABLE jrn AS SELECT row_number() OVER () AS jid, "Journal title" AS title,
  upper(trim("Journal ISSN (print version)")) AS p, upper(trim("Journal EISSN (online version)")) AS e
  FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true)""")
con.execute("""CREATE TABLE jissn AS SELECT jid, title, upper(trim(issn)) AS issn
  FROM jrn, UNNEST([p,e]) AS t(issn) WHERE issn IS NOT NULL AND issn <> ''""")
con.execute("""CREATE TABLE w23i AS SELECT DISTINCT upper(trim(t.s)) AS issn
  FROM read_parquet('D:/crossref/parquet/2023/works/*.parquet'), UNNEST(str_split(issn,';')) AS t(s)""")
rows = con.execute("""
WITH m AS (SELECT j.jid, any_value(j.title) AS title, string_agg(j.issn,',') AS issns,
                  count(w.issn) AS hit FROM jissn j LEFT JOIN w23i w USING (issn) GROUP BY j.jid)
SELECT jid, title, issns FROM m WHERE hit = 0""").fetchall()
random.seed(42); sample = random.sample(rows, 200)

def api(issn):
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(
        {"filter": f"issn:{issn}", "rows": 0, "mailto": MAIL})
    req = urllib.request.Request(url, headers={"User-Agent": f"check (mailto:{MAIL})"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["message"]["total-results"]

only_second = []
none_both = 0
for jid, title, issns in sample:
    lst = issns.split(",")
    if len(lst) < 2: continue
    try:
        a, b = api(lst[0]), api(lst[1])
    except Exception:
        continue
    if a == 0 and b > 0:
        only_second.append((title, lst[0], lst[1], b))
    time.sleep(0.15)

print("첫 ISSN으로는 0건이나 두 번째 ISSN으로는 검색되는 저널:", len(only_second), "종")
for r in only_second[:15]: print(" ", r)
