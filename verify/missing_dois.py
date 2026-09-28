import os
﻿import duckdb, csv, json, os, time, urllib.parse, urllib.request

MAIL = os.environ.get("CROSSREF_MAILTO", "")   # 바꾸세요
SRC  = r"D:\crossref\missing_all.csv"
OUT  = r"D:\crossref\missing_dois.csv"
PER  = 20   # 저널당 조회할 DOI 수

targets = []
with open(SRC, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["match"] == "3_조건충족논문존재":
            targets.append((int(r["jid"]), r["title"], r["issns"].split(",")))
print("대상", len(targets), "종")

done = set()
if os.path.exists(OUT):
    with open(OUT, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f): done.add(int(r["jid"]))
    print("이미 완료", len(done), "종 — 이어서 진행")
else:
    with open(OUT, "w", encoding="utf-8-sig") as f:
        f.write("jid,issn,doi,created\n")

def api(issn):
    q = {"filter": f"issn:{issn},from-pub-date:2000-01-01,type:journal-article",
         "rows": PER, "select": "DOI,created", "mailto": MAIL}
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": f"check (mailto:{MAIL})"})
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)["message"]["items"]
        except Exception:
            time.sleep(2 * (a + 1))
    return []

t0 = time.time(); n = 0
with open(OUT, "a", encoding="utf-8-sig") as f:
    for jid, title, issns in targets:
        if jid in done: continue
        items = []
        for i in issns:
            items = api(i)
            if items: break
        for it in items:
            c = str(it.get("created", {}).get("date-time"))[:7]
            f.write(f'{jid},{issns[0]},{it["DOI"].lower()},{c}\n')
        f.flush(); n += 1
        if n % 25 == 0:
            el = time.time() - t0
            print(f"  {n}종 완료 | 경과 {el/60:.0f}분 | 남은 시간 약 {(len(targets)-len(done)-n)*el/n/60:.0f}분", flush=True)
        time.sleep(0.15)

con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
p = OUT.replace(chr(92), "/")
con.execute(f"CREATE TABLE api AS SELECT * FROM read_csv_auto('{p}', header=true)")
for y in ("2023", "2026"):
    con.execute(f"""CREATE TABLE w{y} AS SELECT DISTINCT doi FROM
      read_parquet('D:/crossref/parquet/{y}/works/*.parquet') WHERE doi IN (SELECT doi FROM api)""")

print("\n[DOI 단위 결과]")
for r in con.execute("""
SELECT count(*) AS API_DOI,
       count(*) FILTER (WHERE created >= '2023-04') AS 스냅숏_이후_등록,
       round(100.0*count(*) FILTER (WHERE created >= '2023-04')/count(*),1) AS 비율,
       count(*) FILTER (WHERE created < '2023-04' AND doi NOT IN (SELECT doi FROM w2023)) AS 누락의심,
       count(*) FILTER (WHERE doi IN (SELECT doi FROM w2026)) AS 우리2026
FROM api""").fetchall(): print(" ", r)

print("\n[저널 단위: 누락의심 DOI가 있는 저널]")
for r in con.execute("""
SELECT jid, any_value(issn) AS issn, count(*) AS API,
       count(*) FILTER (WHERE created < '2023-04' AND doi NOT IN (SELECT doi FROM w2023)) AS 누락의심
FROM api GROUP BY jid HAVING 누락의심 > 0 ORDER BY 4 DESC LIMIT 15""").fetchall(): print(" ", r)
