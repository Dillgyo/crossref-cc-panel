import os
﻿import duckdb, json, os, csv, random, time, urllib.parse, urllib.request

MAIL = os.environ.get("CROSSREF_MAILTO", "")   # 영문 주소로 바꾸세요
N    = 500
OUT  = r"D:\crossref\external_check.csv"

con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")
rows = con.execute("""
SELECT doi, member, publisher, container_title, pub_year
FROM s WHERE cc23=0 AND cc26=0 USING SAMPLE 3000 ROWS""").fetchall()
random.seed(42); sample = random.sample(rows, N)
print("표본", len(sample), "건 (2023·2026 모두 미기재)")

done = {}
if os.path.exists(OUT):
    with open(OUT, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f): done[r["doi"]] = 1
    print("이미 완료", len(done), "건 — 이어서 진행")
else:
    with open(OUT, "w", encoding="utf-8-sig") as f:
        f.write("doi,publisher,journal,pub_year,unpaywall_oa,oa_status,license,host\n")

def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "check (mailto:" + MAIL + ")"})
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(2*(a+1))
        except Exception:
            time.sleep(2*(a+1))
    return "ERR"

t0 = time.time(); n = 0
with open(OUT, "a", encoding="utf-8-sig") as f:
    for doi, member, pub, journal, yr in sample:
        if doi in done: continue
        u = "https://api.unpaywall.org/v2/" + urllib.parse.quote(doi) + "?email=" + urllib.parse.quote(MAIL)
        m = api(u)
        if m == "ERR":
            oa, st, lic, host = "ERR", "", "", ""
        elif m is None:
            oa, st, lic, host = "NOTFOUND", "", "", ""
        else:
            oa = "TRUE" if m.get("is_oa") else "FALSE"
            st = m.get("oa_status") or ""
            best = m.get("best_oa_location") or {}
            lic = (best.get("license") or "")
            host = (best.get("host_type") or "")
        safe = lambda x: (x or "").replace('"', "'").replace(",", " ")
        f.write(f'{doi},"{safe(pub)}","{safe(journal)}",{yr},{oa},{st},{lic},{host}\n'); f.flush()
        n += 1
        if n % 50 == 0:
            el = time.time() - t0
            print(f"  {n}건 | 경과 {el/60:.1f}분 | 남은 시간 약 {(N-len(done)-n)*el/n/60:.0f}분", flush=True)
        time.sleep(0.12)

p = OUT.replace(chr(92), "/")
con.execute(f"CREATE TABLE ex AS SELECT * FROM read_csv_auto('{p}', header=true)")
def show(t, q):
    cur = con.execute(q); cols=[d[0] for d in cur.description]
    print("\n["+t+"]"); print("  "+" | ".join(cols))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else str(v) for v in r))

show("1. Unpaywall 기준 OA 여부", """
SELECT unpaywall_oa AS 구분, count(*) AS 건수,
       round(100.0*count(*)/sum(count(*)) OVER (),1) AS 비율 FROM ex GROUP BY 1 ORDER BY 2 DESC""")
show("2. OA 상태별", """
SELECT coalesce(oa_status,'(없음)') AS 상태, count(*) AS 건수 FROM ex GROUP BY 1 ORDER BY 2 DESC""")
show("3. Unpaywall이 확인한 라이선스", """
SELECT coalesce(nullif(license,''),'(없음)') AS 라이선스, count(*) AS 건수,
       round(100.0*count(*)/sum(count(*)) OVER (),1) AS 비율 FROM ex GROUP BY 1 ORDER BY 2 DESC LIMIT 12""")
show("4. CC 라이선스가 확인된 비율", """
SELECT count(*) AS 전체,
       count(*) FILTER (WHERE license LIKE 'cc%') AS CC확인,
       round(100.0*count(*) FILTER (WHERE license LIKE 'cc%')/count(*),1) AS 비율 FROM ex""")
show("5. 출판사별 (10건 이상)", """
SELECT publisher, count(*) AS 표본, count(*) FILTER (WHERE license LIKE 'cc%') AS CC확인,
       count(*) FILTER (WHERE unpaywall_oa='TRUE') AS OA확인
FROM ex GROUP BY 1 HAVING count(*) >= 10 ORDER BY 2 DESC LIMIT 15""")
