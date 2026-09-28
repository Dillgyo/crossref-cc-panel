import os
﻿import duckdb, json, os, time, urllib.parse, urllib.request

MAIL = os.environ.get("CROSSREF_MAILTO", "")   # 반드시 바꾸세요
OUT  = r"D:\crossref\missing_all.csv"

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
SELECT jid, title, issns FROM m WHERE hit = 0 ORDER BY jid""").fetchall()
print("대상", len(rows), "종")

done = set()
if os.path.exists(OUT):
    import csv
    with open(OUT, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f): done.add(int(r["jid"]))
    print("이미 완료", len(done), "종 — 이어서 진행")
else:
    with open(OUT, "w", encoding="utf-8-sig") as f:
        f.write("jid,title,issns,total,match,n_recent\n")

def api(issn, extra=""):
    q = {"filter": f"issn:{issn}" + extra, "rows": 0, "mailto": MAIL}
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": f"check (mailto:{MAIL})"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)["message"]["total-results"]
        except Exception:
            time.sleep(2 * (attempt + 1))
    return -1

t0 = time.time(); n = 0
with open(OUT, "a", encoding="utf-8-sig") as f:
    for jid, title, issns in rows:
        if jid in done: continue
        lst = issns.split(",")
        total = max((api(i) for i in lst), default=0)
        if total < 0:
            k, recent = "4_조회실패", 0
        elif total == 0:
            k, recent = "1_DOI없음", 0
        else:
            recent = max((api(i, ",from-pub-date:2000-01-01,type:journal-article") for i in lst), default=0)
            k = "3_조건충족논문존재" if recent > 0 else "2_조건미해당"
        safe = title.replace('"', "'")
        f.write(f'{jid},"{safe}","{issns}",{total},{k},{recent}\n'); f.flush()
        n += 1
        if n % 50 == 0:
            el = time.time() - t0
            left = (len(rows) - len(done) - n) * el / n
            print(f"  {n}종 완료 | 경과 {el/60:.0f}분 | 남은 시간 약 {left/60:.0f}분", flush=True)
        time.sleep(0.12)

print("\n[전체 결과]")
r = con.execute(f"""SELECT match, count(*) AS 종수,
  round(100.0*count(*)/sum(count(*)) OVER (),1) AS 비율
  FROM read_csv_auto('{OUT.replace(chr(92),"/")}', header=true) GROUP BY 1 ORDER BY 1""").fetchall()
for x in r: print(" ", x)
