import os
﻿import duckdb, os, json, csv, time, re, random, urllib.request, urllib.parse

MAIL = os.environ.get("CROSSREF_MAILTO", "")          # 영문 주소로 바꾸세요
OUT  = r"D:\crossref\calc_all_results.txt"
P    = "D:/crossref/parquet"
DOAJ = "D:/doaj_journalcsv_20260817_2320_utf8.csv"
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
logf = open(OUT, "w", encoding="utf-8")
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); logf.write(s + "\n"); logf.flush()
con = duckdb.connect()
for q in ["SET threads=4", "SET memory_limit='6GB'", "SET preserve_insertion_order=false",
          "SET temp_directory='D:/crossref/_tmp'"]: con.execute(q)
def show(title, q):
    cur = con.execute(q); cols = [d[0] for d in cur.description]
    log(f"\n[{title}]"); log("  " + " | ".join(cols))
    for r in cur.fetchall():
        log("  " + " | ".join("" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) for v in r))
T0 = time.time()
def step(n): log(f"\n{'='*12} {n}  ({(time.time()-T0)/60:.1f}분) {'='*12}")
CCQ = "url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')"

con.execute(f"CREATE VIEW st AS SELECT * FROM read_parquet('{P}/state_panel.parquet')")
con.execute("CREATE VIEW s AS SELECT * FROM st WHERE in26=1")
for y in ("2023","2024","2025","2026"):
    con.execute(f"CREATE VIEW w{y} AS SELECT * FROM read_parquet('{P}/{y}/works/*.parquet')")
    con.execute(f"CREATE VIEW l{y} AS SELECT * FROM read_parquet('{P}/{y}/licenses/*.parquet')")
log("state_panel 열:", [r[0] for r in con.execute("DESCRIBE st").fetchall()])

# 공통 테이블
con.execute(f"""CREATE TABLE jissn AS
WITH j AS (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e, CAST("OA start" AS INT) oa
           FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true, all_varchar=true))
SELECT upper(trim(issn)) issn, min(greatest(oa,2003)) min_year, min(oa) oa_start
FROM j, UNNEST([p,e]) t(issn) WHERE issn IS NOT NULL AND trim(issn)<>'' GROUP BY 1""")
for y in ("2023","2024","2025","2026"):
    con.execute(f"CREATE TABLE c{y} AS SELECT DISTINCT doi FROM l{y} WHERE {CCQ}")
con.execute("CREATE TABLE addx AS SELECT * FROM s WHERE cc23=0 AND cc26=1")

step("07 추출 집합의 created·deposited 범위")
for y in ("2023","2024","2025","2026"):
    show(f"{y}년판", f"SELECT min(created) created_min, max(created) created_max, min(deposited) dep_min, max(deposited) dep_max FROM w{y}")

step("15 레코드 존재 × CC 상태 교차표")
show("범주별 중간 시점 존재 여부", """
SELECT CASE WHEN cc23=1 AND cc24=1 AND cc25=1 AND cc26=1 THEN '1 계속기재'
            WHEN cc23=0 AND cc24=0 AND cc25=0 AND cc26=0 THEN '2 계속미기재'
            WHEN cc23=0 AND cc26=1 THEN '3 보완' WHEN cc23=1 AND cc26=0 THEN '4 소실' ELSE '5 중간변동' END 범주,
  count(*) 전체, count(*) FILTER (WHERE in24=1 AND in25=1) 둘다있음,
  count(*) FILTER (WHERE in24=0 AND in25=1) 없음_2024만,
count(*) FILTER (WHERE in24=1 AND in25=0) 없음_2025만,
  count(*) FILTER (WHERE in24=0 AND in25=0) 둘다없음
FROM s GROUP BY 1 ORDER BY 1""")
con.execute("""COPY (SELECT st.doi, st.in24, st.in25, st.in26, w.issn, w.pub_year
  FROM st JOIN (SELECT doi, any_value(issn) issn, any_value(pub_year) pub_year FROM w2023 GROUP BY doi) w USING (doi)
  WHERE st.in24=0 OR st.in25=0 OR st.in26=0) TO 'D:/crossref/trace_targets.csv' (HEADER)""")
log("  → 08번 원본 추적 대상 저장: D:/crossref/trace_targets.csv")

step("17 member 변경 (2023년판 → 2026년판)")
con.execute("CREATE TABLE m26 AS SELECT doi, any_value(member) m26 FROM w2026 GROUP BY doi")
show("주 패널과 보완 집합", """
SELECT count(*) 전체, count(*) FILTER (WHERE s.member<>m.m26) 변경, round(100.0*count(*) FILTER (WHERE s.member<>m.m26)/count(*),3) 변경률,
  count(*) FILTER (WHERE cc23=0 AND cc26=1) 보완, count(*) FILTER (WHERE cc23=0 AND cc26=1 AND s.member<>m.m26) 보완중변경
FROM s JOIN m26 m USING (doi)""")
show("보완 집합의 변경 상위", """
SELECT s.member m23, any_value(s.publisher) pub23, m.m26, count(*) n FROM addx s JOIN m26 m USING (doi)
WHERE s.member<>m.m26 GROUP BY 1,3 ORDER BY 4 DESC LIMIT 10""")

step("19 신규 등록 두 정의의 교집합")
con.execute("CREATE TABLE in23 AS SELECT DISTINCT doi FROM w2023")
con.execute("""CREATE TABLE u AS SELECT DISTINCT w.doi, w.pub_year, w.created, w.member FROM
  (SELECT doi, pub_year, created, member, upper(trim(t.s)) issn FROM w2026, UNNEST(str_split(issn,';')) t(s)) w
  JOIN jissn j USING (issn) WHERE w.pub_year >= j.min_year AND w.pub_year <= 2026""")
con.execute("CREATE TABLE ua AS SELECT *, doi NOT IN (SELECT doi FROM in23) a, created >= '2023-04-01' b FROM u")
show("A=2023년판 부재 후 최초 관찰, B=created≥2023-04-01", """
SELECT count(*) FILTER (WHERE a AND b) 교집합, count(*) FILTER (WHERE a AND NOT b) A만, count(*) FILTER (WHERE b AND NOT a) B만 FROM ua""")
show("A만인 DOI의 created 범위", "SELECT min(created), max(created), count(*) FROM ua WHERE a AND NOT b")

step("18 신규 등록의 첫 관찰 판과 측정 시점")
con.execute("""CREATE TABLE fo AS SELECT doi, min(y) fy FROM (SELECT doi,2024 y FROM w2024 UNION ALL
  SELECT doi,2025 FROM w2025 UNION ALL SELECT doi,2026 FROM w2026) GROUP BY doi""")
show("집단 × 첫 관찰 판: 2026년판 기재율 대 첫 관찰 판 기재율", """
SELECT CASE WHEN u.pub_year>=2023 THEN '2023년 이후 출판' ELSE '과거 출판' END 집단, f.fy 첫관찰판, count(*) n,
  round(100.0*avg(CASE WHEN c6.doi IS NOT NULL THEN 1 ELSE 0 END),1) 기재율_2026,
  round(100.0*avg(CASE WHEN (f.fy=2024 AND c4.doi IS NOT NULL) OR (f.fy=2025 AND c5.doi IS NOT NULL)
                         OR (f.fy=2026 AND c6.doi IS NOT NULL) THEN 1 ELSE 0 END),1) 기재율_첫관찰
FROM ua u JOIN fo f USING (doi) LEFT JOIN c2024 c4 USING (doi) LEFT JOIN c2025 c5 USING (doi) LEFT JOIN c2026 c6 USING (doi)
WHERE u.b GROUP BY 1,2 ORDER BY 1,2""")
show("집단 × created 연도", """
SELECT CASE WHEN pub_year>=2023 THEN '2023년 이후 출판' ELSE '과거 출판' END 집단, substr(created,1,4) created연도, count(*) n
FROM ua WHERE b GROUP BY 1,2 ORDER BY 1,2""")

step("21 '다른 ISSN으로 이미 추출' 63건의 실제 ISSN")
con.execute("CREATE TABLE api AS SELECT * FROM read_csv_auto('D:/crossref/missing_dois.csv', header=true, all_varchar=true)")
con.execute("""CREATE TABLE jp AS SELECT upper(trim("Journal ISSN (print version)")) p, upper(trim("Journal EISSN (online version)")) e,
  "Journal title" title FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true, all_varchar=true)""")
rows = con.execute("""SELECT a.doi, upper(trim(a.issn)) q, w.issn rec, w.ct FROM api a
  JOIN (SELECT doi, any_value(issn) issn, any_value(container_title) ct FROM w2023 GROUP BY doi) w ON lower(a.doi)=w.doi
  WHERE a.created < '2023-04'""").fetchall()
pairs = con.execute("SELECT p, e, title FROM jp").fetchall()
from collections import Counter
cat = Counter(); ex = []
for doi, q, rec, ct in rows:
    j = next(((p, e, t) for p, e, t in pairs if q in (p, e)), None)
    recset = {x.strip().upper() for x in (rec or "").split(";") if x.strip()}
    if j is None: k = "조회 ISSN의 저널을 찾지 못함"
    elif recset & {j[0], j[1]}: k = "레코드 ISSN이 DOAJ ISSN과 같음"
    else: k = "레코드 ISSN이 DOAJ ISSN과 다름"
    cat[k] += 1
    if len(ex) < 8: ex.append((doi, q, rec, ct, j[2] if j else None))
log(f"\n[63건 분류] 총 {len(rows)}건")
for k, v in cat.most_common(): log(f"  {k}: {v}")
for e_ in ex: log("  예:", e_)

step("12 느슨한 판정 규칙이 보완 집합에 미친 영향")
con.execute(f"""CREATE TABLE q AS SELECT l.doi, lower(l.url) url, lower(coalesce(l.content_version,'')) cv
  FROM l2026 l JOIN addx a USING (doi) WHERE l.{CCQ.replace('url ILIKE', 'url ILIKE')}""")
show("보완 167,779건의 CC 항목 성격 (DOI 단위)", """
WITH d AS (SELECT doi,
   bool_or(regexp_matches(url, '^https?://(www\\.)?creativecommons\\.org/(licenses|publicdomain)/')) std,
   bool_or(regexp_matches(url, '^https?://(www\\.)?creativecommons\\.org')) host,
   bool_or(cv IN ('vor','am')) vam FROM q GROUP BY doi)
SELECT count(*) 전체, count(*) FILTER (WHERE NOT std) 표준경로없음, count(*) FILTER (WHERE NOT host) 호스트불일치,
  count(*) FILTER (WHERE NOT vam) unspecified만, count(*) FILTER (WHERE NOT std OR NOT vam) 둘중하나 FROM d""")
show("null content-version을 가진 CC 항목 (2026, 참고)", """
SELECT count(*) 항목, count(DISTINCT doi) DOI FROM l2026 WHERE url ILIKE '%creativecommons.org%' AND content_version IS NULL""")

step("14 보완 건의 start 날짜")
show("미래 start와 결측", f"""
WITH d AS (SELECT l.doi, min(CAST(l.start AS VARCHAR)) st FROM l2026 l JOIN addx a USING (doi) WHERE l.{CCQ} GROUP BY l.doi)
SELECT count(*) 전체, count(*) FILTER (WHERE st IS NULL) start없음, count(*) FILTER (WHERE st > '2026-03-02') 관찰시점이후 FROM d""")

step("23 보완이 정확히 0건인 출판사")
show("미기재 1만 건 이상 33곳", """
WITH t AS (SELECT member, any_value(publisher) pub, count(*) FILTER (WHERE cc23=0) n, count(*) FILTER (WHERE cc23=0 AND cc26=1) a
           FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000)
SELECT count(*) 출판사, count(*) FILTER (WHERE a=0) 정확히0건, count(*) FILTER (WHERE a>0 AND 100.0*a/n<0.05) 양수인데0_0표시,
  count(*) FILTER (WHERE 100.0*a/n<1) 일퍼센트미만 FROM t""")
show("양수인데 0.0%로 보이는 곳", """
WITH t AS (SELECT member, any_value(publisher) pub, count(*) FILTER (WHERE cc23=0) n, count(*) FILTER (WHERE cc23=0 AND cc26=1) a
           FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000)
SELECT pub, n, a FROM t WHERE a>0 AND 100.0*a/n<0.05 ORDER BY n DESC""")

step("24 상위 5곳의 초기 미기재 비중")
show("", """SELECT count(*) FILTER (WHERE cc23=0 AND member IN ('276','2399','317','297','2373')) 상위5미기재,
  count(*) FILTER (WHERE cc23=0) 전체미기재,
  round(100.0*count(*) FILTER (WHERE cc23=0 AND member IN ('276','2399','317','297','2373'))/count(*) FILTER (WHERE cc23=0),1) 비중 FROM s""")

step("25 상위 5곳 × 월 (CC가 처음 관찰된 판의 deposited 월)")
con.execute("""CREATE TABLE ym AS SELECT member, any_value(publisher) pub,
  substr(CAST(CASE WHEN cc24=1 THEN dep24 WHEN cc25=1 THEN dep25 ELSE dep26 END AS VARCHAR),1,7) ym, count(*) n
  FROM addx WHERE member IN ('276','2399','317','297','2373') GROUP BY member, 3""")
con.execute("COPY (SELECT * FROM ym ORDER BY member, ym) TO 'D:/crossref/figs/top5_by_month.csv' (HEADER)")
show("출판사별 상위 3개월과 비중", """
SELECT pub, ym, n, round(100.0*n/sum(n) OVER (PARTITION BY member),1) 비중 FROM ym
QUALIFY row_number() OVER (PARTITION BY member ORDER BY n DESC) <= 3 ORDER BY pub, n DESC""")

step("27 Frontiers 출판연도 구간")
show("member 1965", """
SELECT CASE WHEN pub_year<=2012 THEN '1 2012년까지' WHEN pub_year<=2017 THEN '2 2013~2017' ELSE '3 2018 이후' END 구간,
  count(*) n, round(100.0*avg(cc23),1) 기재율_2023, round(100.0*avg(cc26),1) 기재율_2026
FROM s WHERE member='1965' GROUP BY 1 ORDER BY 1""")

step("32 민감도 조건별 전체 수치")
for lab, cond in [("VoR만","content_version='vor'"), ("VoR+unspecified","content_version IN ('vor','unspecified')"),
                  ("본 분석", "content_version IN ('vor','am','unspecified')"), ("tdm 포함","1=1")]:
    con.execute(f"CREATE OR REPLACE TABLE r23 AS SELECT DISTINCT doi FROM l2023 WHERE url ILIKE '%creativecommons.org%' AND ({cond})")
    con.execute(f"CREATE OR REPLACE TABLE r26 AS SELECT DISTINCT doi FROM l2026 WHERE url ILIKE '%creativecommons.org%' AND ({cond})")
    show(f"규칙: {lab}", """SELECT count(*) 전체N, count(*) FILTER (WHERE a.doi IS NULL) 초기미기재, count(*) FILTER (WHERE a.doi IS NULL AND b.doi IS NOT NULL) 보완,
      round(100.0*count(*) FILTER (WHERE a.doi IS NULL AND b.doi IS NOT NULL)/count(*) FILTER (WHERE a.doi IS NULL),2) 보완율,
      round(100.0*avg(CASE WHEN a.doi IS NOT NULL THEN 1 ELSE 0 END),1) 기재율23, round(100.0*avg(CASE WHEN b.doi IS NOT NULL THEN 1 ELSE 0 END),1) 기재율26
      FROM s LEFT JOIN r23 a USING (doi) LEFT JOIN r26 b USING (doi)""")
for yr in (2010, 2015, 2020):
    show(f"하한: 저널별 하한과 {yr}년 중 늦은 해", f"""SELECT count(*) 전체N, count(*) FILTER (WHERE cc23=0) 초기미기재, count(*) FILTER (WHERE cc23=0 AND cc26=1) 보완,
      round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/count(*) FILTER (WHERE cc23=0),2) 보완율,
      round(100.0*avg(cc23),1) 기재율23, round(100.0*avg(cc26),1) 기재율26 FROM s WHERE pub_year >= {yr}""")
show("OA 전환연도 자체 제외", """
WITH o AS (SELECT w.doi, max(j.oa_start) oa FROM (SELECT doi, upper(trim(t.s)) issn FROM w2023, UNNEST(str_split(issn,';')) t(s)) w
           JOIN jissn j USING (issn) GROUP BY w.doi)
SELECT count(*) 전체N, count(*) FILTER (WHERE cc23=0) 초기미기재, count(*) FILTER (WHERE cc23=0 AND cc26=1) 보완,
  round(100.0*count(*) FILTER (WHERE cc23=0 AND cc26=1)/count(*) FILTER (WHERE cc23=0),2) 보완율,
  round(100.0*avg(cc23),1) 기재율23, round(100.0*avg(cc26),1) 기재율26
FROM s JOIN o USING (doi) WHERE s.pub_year > o.oa""")

step("26 전환 출판연도 규칙 비교")
res = {}
for base in ("cc26", "cc23"):
    for th in (0.7, 0.8, 0.9):
        for persist in (True, False):
            rows = con.execute(f"""
            WITH y AS (SELECT member, any_value(publisher) pub, pub_year, count(*) n, avg({base}) r FROM s GROUP BY member, pub_year),
                 big AS (SELECT member FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000),
                 ok AS (SELECT member, pub_year, r, min(r) OVER (PARTITION BY member ORDER BY pub_year ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) ma
                        FROM y WHERE n >= 100 AND member IN (SELECT member FROM big))
            SELECT member, min(pub_year) FILTER (WHERE {'ma' if persist else 'r'} >= {th}) FROM ok GROUP BY member""").fetchall()
            res[(base, th, persist)] = dict(rows)
main = res[("cc26", 0.8, True)]
names = dict(con.execute("SELECT member, any_value(publisher) FROM s GROUP BY member").fetchall())
log(f"\n[기준: 2026년판·80%·지속성] 전환연도 확인 {sum(1 for v in main.values() if v)}곳")
for k, d in res.items():
    if k == ("cc26", 0.8, True): continue
    same = sum(1 for m in main if main[m] == d.get(m))
    shifts = [abs(main[m] - d[m]) for m in main if main[m] and d.get(m)]
    appear = sum(1 for m in main if (main[m] is None) != (d.get(m) is None))
    log(f"  {k[0]} {int(k[1]*100)}% {'지속' if k[2] else '최초'}: 동일 {same}/33, 최대 이동 {max(shifts) if shifts else 0}년, 유무가 바뀐 곳 {appear}")

step("41 출판사 소재국 결측과 국가별 N")
con.execute(f"""CREATE TABLE jc AS SELECT upper(trim(issn)) issn, any_value(c) country FROM
  (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e, "Country of publisher" c
   FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true)), UNNEST([p,e]) t(issn) WHERE issn IS NOT NULL AND issn<>'' GROUP BY 1""")
show("", """WITH pc AS (SELECT DISTINCT w.doi, j.country FROM (SELECT doi, upper(trim(t.s)) issn FROM w2023, UNNEST(str_split(issn,';')) t(s)) w
  JOIN jc j USING (issn) WHERE w.doi IN (SELECT doi FROM s))
SELECT count(DISTINCT doi) 논문, count(DISTINCT doi) FILTER (WHERE country IS NULL OR country='') 국가결측,
  count(DISTINCT country) 국가수 FROM pc""")

step("33 Unpaywall 라이선스와 DOAJ 저널 라이선스 대조")
con.execute(f"""CREATE TABLE dl AS SELECT upper(trim(issn)) issn, any_value(lic) lic FROM
  (SELECT "Journal ISSN (print version)" p, "Journal EISSN (online version)" e, "Journal license" lic
   FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true)), UNNEST([p,e]) t(issn) WHERE issn IS NOT NULL AND issn<>'' GROUP BY 1""")
def doaj_lic(sample_csv, col):
    return con.execute(f"""SELECT e.doi, e.{col}, any_value(d.lic) FROM read_csv_auto('{sample_csv}', header=true, all_varchar=true) e
      JOIN (SELECT doi, upper(trim(t.s)) issn FROM w2023, UNNEST(str_split(issn,';')) t(s)) w ON lower(e.doi)=w.doi
      JOIN dl d USING (issn) GROUP BY 1,2""").fetchall()
norm = lambda x: {t.strip().lower().replace(" ", "-") for t in (x or "").split(",") if t.strip()}
neg = doaj_lic("D:/crossref/external_check.csv", "license")
c = Counter()
for doi, up, dj in neg:
    ds = norm(dj)
    if not up or not up.startswith("cc"): c["Unpaywall CC 아님"] += 1
    elif len(ds) > 1: c["DOAJ 복수 라이선스" + (" (포함)" if up in ds else " (불포함)")] += 1
    elif up in ds: c["DOAJ 단일 라이선스와 일치"] += 1
    else: c["DOAJ 단일 라이선스와 불일치"] += 1
log(f"\n[미기재 표본] 대조 {len(neg)}건")
for k, v in c.most_common(): log(f"  {k}: {v}")
pos = con.execute("""SELECT e.doi, e.crossref_lic, e.unpaywall_lic, any_value(d.lic) FROM read_csv_auto('D:/crossref/external_positive.csv', header=true, all_varchar=true) e
  JOIN (SELECT doi, upper(trim(t.s)) issn FROM w2023, UNNEST(str_split(issn,';')) t(s)) w ON lower(e.doi)=w.doi
  JOIN dl d USING (issn) GROUP BY 1,2,3""").fetchall()
c2 = Counter()
for doi, cr, up, dj in pos:
    ds = norm(dj)
    if len(ds) != 1 or cr in ds: continue
    c2["Crossref≠DOAJ인 경우: Unpaywall=" + ("Crossref" if up == cr else "DOAJ" if up in ds else "둘다아님")] += 1
log(f"\n[기재 표본] Crossref와 DOAJ가 다른 경우 Unpaywall이 따르는 쪽")
for k, v in c2.most_common(): log(f"  {k}: {v}")

step("34 Unpaywall 표본 상태와 재조회")
for f_, col in (("external_check.csv","unpaywall_oa"), ("external_positive.csv","unpaywall_oa")):
    show(f_, f"SELECT {col}, count(*) FROM read_csv_auto('D:/crossref/{f_}', header=true, all_varchar=true) GROUP BY 1")
log("  참고: 표본은 DuckDB USING SAMPLE 3000 ROWS(시드 없음) 뒤 random.seed(42/7)로 500건 추출. DOI 목록이 CSV로 보존됨")
dois = [r[0] for r in con.execute("SELECT doi FROM read_csv_auto('D:/crossref/external_check.csv', header=true, all_varchar=true)").fetchall()]
RQ = r"D:\crossref\unpaywall_requery.jsonl"
done = set()
if os.path.exists(RQ):
    for ln in open(RQ, encoding="utf-8"): done.add(json.loads(ln)["doi"])
with open(RQ, "a", encoding="utf-8") as f:
    for i, d in enumerate(dois):
        if d in done: continue
        u = "https://api.unpaywall.org/v2/" + urllib.parse.quote(d) + "?email=" + urllib.parse.quote(MAIL)
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "check (mailto:"+MAIL+")"}), timeout=40) as r:
                m = json.load(r)
        except Exception as e: m = {"doi": d, "error": str(e)}
        m["doi"] = d; f.write(json.dumps(m) + "\n")
        if i % 100 == 0: log(f"  재조회 {i}/{len(dois)}")
        time.sleep(0.12)
ev = Counter(); rep = 0; lic_src = Counter()
for ln in open(RQ, encoding="utf-8"):
    m = json.loads(ln); b = m.get("best_oa_location") or {}
    ev[b.get("evidence") or "(evidence 없음)"] += 1
    if any((l.get("host_type") == "repository") for l in (m.get("oa_locations") or [])): rep += 1
log(f"\n[재조회 {sum(ev.values())}건] best_oa_location의 evidence")
for k, v in ev.most_common(): log(f"  {k}: {v}")
log(f"  저장소 위치를 하나라도 가진 DOI: {rep}")

step("45·46 참고문헌 서지 대조 (Crossref API)")
REFS = ["10.1002/asi.24979","10.1007/s11192-022-04367-w","10.1007/s11192-025-05293-3","10.1371/journal.pone.0345417",
 "10.31222/osf.io/3zm5r_v1","10.1162/qss_a_00286","10.31274/jlsc.19779","10.59350/4svpe-kcj07","10.1007/s11192-019-03217-6",
 "10.1162/qss_a_00022","10.1162/qss_a_00031","10.1162/qss_a_00348","10.1002/asi.24549","10.1162/qss_a_00210",
 "10.3390/publications7020023","10.1007/s11192-021-03972-5","10.1162/qss_a_00023","10.7717/peerj.4375","10.1162/qss.a.1",
 "10.1162/QSS.a.407","10.31222/osf.io/smxe5","10.1162/qss_a_00112","10.13003/8wx5k","10.13003/849J5WP",
 "10.13003/87bfgcee6g","10.13003/nggf-vt1j","10.48550/arXiv.1902.03937"]
with open(r"D:\crossref\ref_check.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["doi","year","container","volume","issue","page","authors","title"])
    for d in REFS:
        u = "https://api.crossref.org/works/" + urllib.parse.quote(d) + "?mailto=" + urllib.parse.quote(MAIL)
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "check (mailto:"+MAIL+")"}), timeout=40) as r:
                m = json.load(r)["message"]
            yr = ((m.get("published") or m.get("issued") or {}).get("date-parts") or [[None]])[0][0]
            au = "; ".join(f"{a.get('family','')}, {a.get('given','')}" for a in (m.get("author") or []))
            row = [d, yr, "; ".join(m.get("container-title") or []), m.get("volume"), m.get("issue"), m.get("page"), au, "; ".join(m.get("title") or [])]
        except Exception as e:
            row = [d, "", "", "", "", "", "", f"조회 실패: {e}"]
        w.writerow(row); log("  " + " | ".join(str(x) for x in row[:6]))
        time.sleep(0.2)
log("  → 저자 전체는 D:/crossref/ref_check.csv")
log(f"\n완료 ({(time.time()-T0)/60:.1f}분). 결과: {OUT}")
