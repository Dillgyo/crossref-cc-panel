import os
﻿import duckdb, json, time, urllib.parse, urllib.request

MAIL = os.environ.get("CROSSREF_MAILTO", "")   # 바꾸세요
ISSNS = ["2709-9997","2560-8312","1689-4642","2395-9908","2492-0983",
         "1814-3199","2500-784X","1753-0296","2392-6031","2325-2871"]

def api(path, params):
    params["mailto"] = MAIL
    url = "https://api.crossref.org/" + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": f"check (mailto:{MAIL})"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["message"]

rows = []
for issn in ISSNS:
    try:
        m = api("works", {"filter": f"issn:{issn},type:journal-article", "rows": 5,
                          "select": "DOI,ISSN,issued,published,created,container-title"})
        for it in m["items"]:
            rows.append((issn, it["DOI"].lower(), ";".join(it.get("ISSN") or []),
                         str(it.get("issued",{}).get("date-parts")),
                         str(it.get("created",{}).get("date-time"))[:10]))
    except Exception as ex:
        print("조회 실패", issn, ex)
    time.sleep(0.3)

con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("CREATE TABLE api(issn VARCHAR, doi VARCHAR, api_issn VARCHAR, issued VARCHAR, created VARCHAR)")
con.executemany("INSERT INTO api VALUES (?,?,?,?,?)", rows)

for y in ("2023","2026"):
    con.execute(f"""CREATE TABLE w{y} AS SELECT doi, issn AS ext_issn, pub_year
      FROM read_parquet('D:/crossref/parquet/{y}/works/*.parquet')
      WHERE doi IN (SELECT doi FROM api)""")

print("\n[API가 준 DOI가 우리 추출에 있는지]")
for r in con.execute("""
SELECT a.issn AS 검색ISSN, count(*) AS API_DOI,
       count(w23.doi) AS 우리_2023, count(w26.doi) AS 우리_2026,
       any_value(a.api_issn) AS API가_보여준_ISSN, any_value(w26.ext_issn) AS 우리가_뽑은_ISSN
FROM api a LEFT JOIN w2023 w23 ON w23.doi=a.doi LEFT JOIN w2026 w26 ON w26.doi=a.doi
GROUP BY a.issn ORDER BY 1""").fetchall():
    print(" ", r)

print("\n[개별 DOI 5건 예시]")
for r in con.execute("""
SELECT a.doi, a.api_issn, a.issued, a.created,
       CASE WHEN w23.doi IS NULL THEN '없음' ELSE '있음' END AS 우리2023,
       CASE WHEN w26.doi IS NULL THEN '없음' ELSE '있음' END AS 우리2026
FROM api a LEFT JOIN w2023 w23 ON w23.doi=a.doi LEFT JOIN w2026 w26 ON w26.doi=a.doi
LIMIT 5""").fetchall():
    print(" ", r)
