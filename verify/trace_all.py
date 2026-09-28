import os
﻿import duckdb, json, random, time, urllib.parse, urllib.request

MAIL = os.environ.get("CROSSREF_MAILTO", "")   # 바꾸세요
N = 200

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
random.seed(42); sample = random.sample(rows, min(N, len(rows)))

def api(path, params):
    params["mailto"] = MAIL
    url = "https://api.crossref.org/" + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": f"check (mailto:{MAIL})"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["message"]

# 1단계: 의심 저널 재추출
suspect = []
for jid, title, issns in sample:
    issn = issns.split(",")[0]
    try:
        if api("works", {"filter": f"issn:{issn}", "rows": 0})["total-results"] == 0: 
            continue
        if api("works", {"filter": f"issn:{issn},from-pub-date:2000-01-01,type:journal-article",
                         "rows": 0})["total-results"] > 0:
            suspect.append((title, issn))
    except Exception:
        pass
    time.sleep(0.15)
print("의심 저널", len(suspect), "종 — DOI 표본 대조 시작")

# 2단계: 저널별 DOI 20건씩 받아 우리 추출과 대조
recs = []
for title, issn in suspect:
    try:
        m = api("works", {"filter": f"issn:{issn},from-pub-date:2000-01-01,type:journal-article",
                          "rows": 20, "select": "DOI,created"})
        for it in m["items"]:
            recs.append((issn, title, it["DOI"].lower(), str(it.get("created",{}).get("date-time"))[:7]))
    except Exception as ex:
        print("  조회 실패", issn)
    time.sleep(0.2)

con.execute("CREATE TABLE api(issn VARCHAR, title VARCHAR, doi VARCHAR, created VARCHAR)")
con.executemany("INSERT INTO api VALUES (?,?,?,?)", recs)
for y in ("2023","2026"):
    con.execute(f"""CREATE TABLE w{y} AS SELECT DISTINCT doi FROM
      read_parquet('D:/crossref/parquet/{y}/works/*.parquet') WHERE doi IN (SELECT doi FROM api)""")

print("\n[전체 요약]")
for r in con.execute("""
SELECT count(*) AS API_DOI,
       count(*) FILTER (WHERE created < '2023-04') AS 스냅숏_이전_등록,
       count(*) FILTER (WHERE doi IN (SELECT doi FROM w2023)) AS 우리2023,
       count(*) FILTER (WHERE created < '2023-04' AND doi NOT IN (SELECT doi FROM w2023)) AS 진짜_누락의심,
       count(*) FILTER (WHERE doi IN (SELECT doi FROM w2026)) AS 우리2026
FROM api""").fetchall(): print(" ", r)

print("\n[저널별]")
for r in con.execute("""
SELECT any_value(title) AS 저널, issn, count(*) AS API,
       count(*) FILTER (WHERE created < '2023-04') AS 스냅숏이전등록,
       count(*) FILTER (WHERE doi IN (SELECT doi FROM w2023)) AS 우리2023,
       count(*) FILTER (WHERE doi IN (SELECT doi FROM w2026)) AS 우리2026
FROM api GROUP BY issn ORDER BY 4 DESC""").fetchall(): print(" ", r)
