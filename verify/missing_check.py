import os
﻿import duckdb, json, random, time, urllib.parse, urllib.request

MAIL = os.environ.get("CROSSREF_MAILTO", "")   # 반드시 본인 메일로 바꾸세요
N = 200

con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("""CREATE TABLE jrn AS SELECT row_number() OVER () AS jid, "Journal title" AS title,
  upper(trim("Journal ISSN (print version)")) AS p, upper(trim("Journal EISSN (online version)")) AS e
  FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true)""")
con.execute("""CREATE TABLE jissn AS SELECT jid, title, upper(trim(issn)) AS issn
  FROM jrn, UNNEST([p,e]) AS t(issn) WHERE issn IS NOT NULL AND issn <> ''""")
con.execute("""CREATE TABLE w23 AS SELECT DISTINCT upper(trim(t.s)) AS issn
  FROM read_parquet('D:/crossref/parquet/2023/works/*.parquet'), UNNEST(str_split(issn,';')) AS t(s)""")
rows = con.execute("""
WITH m AS (SELECT j.jid, any_value(j.title) AS title, string_agg(j.issn,',') AS issns,
                  count(w.issn) AS hit FROM jissn j LEFT JOIN w23 w USING (issn) GROUP BY j.jid)
SELECT jid, title, issns FROM m WHERE hit = 0""").fetchall()
print("미확인 저널", len(rows), "종 중", N, "종 표본 조사")

random.seed(42); sample = random.sample(rows, min(N, len(rows)))

def api(path, params):
    params["mailto"] = MAIL
    url = "https://api.crossref.org/" + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": f"crossref-check (mailto:{MAIL})"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["message"]

tally = {}
detail = []
for i, (jid, title, issns) in enumerate(sample, 1):
    issn = issns.split(",")[0]
    try:
        total = api("works", {"filter": f"issn:{issn}", "rows": 0})["total-results"]
        if total == 0:
            k = "1. ISSN으로 Crossref DOI 없음"
        else:
            recent = api("works", {"filter": f"issn:{issn},from-pub-date:2000-01-01,type:journal-article",
                                   "rows": 0})["total-results"]
            if recent == 0:
                k = "2. DOI는 있으나 조건(2000년 이후 journal-article) 미해당"
            else:
                k = "3. 조건 충족 논문 존재 — 매칭 실패 의심"
                detail.append((title, issn, recent))
    except Exception as ex:
        k = "4. 조회 실패"
    tally[k] = tally.get(k, 0) + 1
    if i % 25 == 0: print(" ", i, "종 완료", tally)
    time.sleep(0.2)

print("\n[결과]")
for k in sorted(tally): print(f"  {k}: {tally[k]}종 ({100*tally[k]/len(sample):.1f}%)")
print("\n[매칭 실패 의심 사례 (상위 10건)]")
for d in sorted(detail, key=lambda x: -x[2])[:10]: print(" ", d)
