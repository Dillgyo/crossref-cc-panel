import os
﻿import duckdb, json, os, csv, random, time, urllib.parse, urllib.request
MAIL = os.environ.get("CROSSREF_MAILTO", "")
N, OUT = 500, r"D:\crossref\external_positive.csv"

con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
con.execute("""CREATE TABLE lic AS
SELECT doi, min(CASE WHEN url ILIKE '%/by/%' THEN 'cc-by'
            WHEN url ILIKE '%by-nc-nd%' THEN 'cc-by-nc-nd' WHEN url ILIKE '%by-nc-sa%' THEN 'cc-by-nc-sa'
            WHEN url ILIKE '%by-nc%' THEN 'cc-by-nc' WHEN url ILIKE '%by-sa%' THEN 'cc-by-sa'
            WHEN url ILIKE '%by-nd%' THEN 'cc-by-nd' ELSE 'cc-other' END) AS cr_lic
FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')
GROUP BY doi""")
rows = con.execute("""SELECT s.doi, s.publisher, s.container_title, s.pub_year, l.cr_lic
FROM s JOIN lic l USING (doi) WHERE s.cc26=1 USING SAMPLE 3000 ROWS""").fetchall()
random.seed(7); sample = random.sample(rows, N)
print("표본", len(sample), "건 (Crossref에 CC 기재됨)")

done = set()
if os.path.exists(OUT):
    with open(OUT, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f): done.add(r["doi"])
    print("이미 완료", len(done), "건")
else:
    with open(OUT, "w", encoding="utf-8-sig") as f:
        f.write("doi,publisher,pub_year,crossref_lic,unpaywall_oa,oa_status,unpaywall_lic\n")

def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "check (mailto:" + MAIL + ")"})
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(2*(a+1))
        except Exception: time.sleep(2*(a+1))
    return "ERR"

t0=time.time(); n=0
with open(OUT, "a", encoding="utf-8-sig") as f:
    for doi, pub, journal, yr, crlic in sample:
        if doi in done: continue
        m = api("https://api.unpaywall.org/v2/" + urllib.parse.quote(doi) + "?email=" + urllib.parse.quote(MAIL))
        if m == "ERR": oa, st, up = "ERR","",""
        elif m is None: oa, st, up = "NOTFOUND","",""
        else:
            oa = "TRUE" if m.get("is_oa") else "FALSE"
            st = m.get("oa_status") or ""
            up = ((m.get("best_oa_location") or {}).get("license") or "")
        safe = lambda x: (x or "").replace('"',"'").replace(","," ")
        f.write(f'{doi},"{safe(pub)}",{yr},{crlic},{oa},{st},{up}\n'); f.flush()
        n+=1
        if n % 50 == 0: print(f"  {n}건 | {(time.time()-t0)/60:.1f}분", flush=True)
        time.sleep(0.12)

p = OUT.replace(chr(92),"/")
con.execute(f"CREATE TABLE ex AS SELECT * FROM read_csv_auto('{p}', header=true)")
def show(t,q):
    cur=con.execute(q); print("\n["+t+"]"); print("  "+" | ".join(d[0] for d in cur.description))
    for r in cur.fetchall(): print("  "+" | ".join("" if v is None else str(v) for v in r))
show("1. Crossref CC 기재분의 Unpaywall 라이선스", """
SELECT CASE WHEN unpaywall_lic = '' OR unpaywall_lic IS NULL THEN '없음'
            WHEN unpaywall_lic = crossref_lic THEN '일치'
            WHEN unpaywall_lic LIKE 'cc%' THEN '다른 CC'
            ELSE '기타' END AS 구분, count(*) AS 건수,
       round(100.0*count(*)/sum(count(*)) OVER (),1) AS 비율 FROM ex GROUP BY 1 ORDER BY 2 DESC""")
show("2. 불일치 조합 상위", """
SELECT crossref_lic AS Crossref, unpaywall_lic AS Unpaywall, count(*) AS 건수
FROM ex WHERE unpaywall_lic LIKE 'cc%' AND unpaywall_lic <> crossref_lic GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10""")
show("3. Crossref는 CC인데 Unpaywall은 비OA", """
SELECT count(*) FILTER (WHERE unpaywall_oa='FALSE') AS 비OA, count(*) AS 전체 FROM ex""")
