import duckdb, os
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
con.execute("CREATE VIEW s AS SELECT * FROM read_parquet('D:/crossref/parquet/state_panel.parquet') WHERE in26=1")

def show(title, q):
    cur = con.execute(q); cols=[d[0] for d in cur.description]
    print("\n["+title+"]"); print("  "+" | ".join(cols))
    for r in cur.fetchall():
        print("  "+" | ".join("" if v is None else f"{v:,}" if isinstance(v,int) and abs(v)>=10000 else str(v) for v in r))

# (1) 출판사별 기재 시작 연도: 2026 시점에서 기재율이 처음 80%를 넘는 출판연도
show("1. 출판사별 기재 시작 연도 (2026 스냅숏 기준, 미기재 1만 건 이상)", """
WITH y AS (SELECT member, any_value(publisher) AS publisher, pub_year, count(*) AS n,
                  avg(cc26) AS rate FROM s GROUP BY member, pub_year),
     big AS (SELECT member FROM s GROUP BY member HAVING count(*) FILTER (WHERE cc23=0) >= 10000),
     f AS (SELECT member, publisher, min(pub_year) FILTER (WHERE rate >= 0.8 AND n >= 100) AS 시작연도
           FROM y WHERE member IN (SELECT member FROM big) GROUP BY 1,2)
SELECT publisher, 시작연도,
       (SELECT round(100.0*avg(cc26),1) FROM s x WHERE x.member=f.member AND x.pub_year < f.시작연도) AS 이전_기재율,
       (SELECT count(*) FROM s x WHERE x.member=f.member AND x.pub_year < f.시작연도) AS 이전_논문수
FROM f ORDER BY 시작연도 NULLS LAST""")

# (2) 보강 라이선스 종류 vs DOAJ 등록 라이선스
con.execute("""
CREATE TABLE doaj AS
WITH j AS (SELECT "Journal ISSN (print version)" AS p, "Journal EISSN (online version)" AS e,
                  "Journal license" AS lic FROM read_csv_auto('D:/crossref/doaj_panel_journals.csv', header=true))
SELECT upper(trim(issn)) AS issn, any_value(lic) AS doaj_lic
FROM j, UNNEST([p, e]) AS t(issn) WHERE issn IS NOT NULL AND trim(issn) <> '' GROUP BY 1
""")
con.execute("""
CREATE TABLE lic26 AS
SELECT doi,
       CASE WHEN url ILIKE '%/by/%' THEN 'CC BY'
            WHEN url ILIKE '%by-nc-nd%' THEN 'CC BY-NC-ND'
            WHEN url ILIKE '%by-nc-sa%' THEN 'CC BY-NC-SA'
            WHEN url ILIKE '%by-nc%' THEN 'CC BY-NC'
            WHEN url ILIKE '%by-sa%' THEN 'CC BY-SA'
            WHEN url ILIKE '%by-nd%' THEN 'CC BY-ND'
            WHEN url ILIKE '%zero%' OR url ILIKE '%publicdomain%' THEN 'CC0'
            ELSE '기타' END AS cc_type
FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet')
WHERE url ILIKE '%creativecommons.org%'
  AND coalesce(content_version,'') IN ('vor','am','unspecified')
""")
con.execute("""
CREATE TABLE w26issn AS
SELECT doi, upper(trim(t.s)) AS issn FROM read_parquet('D:/crossref/parquet/2026/works/*.parquet'),
UNNEST(str_split(issn, ';')) AS t(s)
""")

show("2-1. 보강된 논문의 CC 종류 분포", """
SELECT l.cc_type AS Crossref_종류, count(DISTINCT s.doi) AS 논문수
FROM s JOIN lic26 l USING (doi) WHERE s.cc23=0 AND s.cc26=1
GROUP BY 1 ORDER BY 2 DESC""")

show("2-2. DOAJ 등록 라이선스와 Crossref 기재의 일치 (보강분)", """
WITH b AS (SELECT DISTINCT s.doi FROM s WHERE s.cc23=0 AND s.cc26=1),
     m AS (SELECT DISTINCT b.doi, d.doaj_lic, l.cc_type
           FROM b JOIN w26issn w USING (doi) JOIN doaj d USING (issn) JOIN lic26 l ON l.doi = b.doi)
SELECT CASE WHEN doaj_lic ILIKE '%' || cc_type || '%' THEN '일치' ELSE '불일치' END AS 구분,
       count(DISTINCT doi) AS 논문수
FROM m GROUP BY 1 ORDER BY 2 DESC""")

show("2-3. 불일치 조합 상위 10개", """
WITH b AS (SELECT DISTINCT s.doi FROM s WHERE s.cc23=0 AND s.cc26=1),
     m AS (SELECT DISTINCT b.doi, d.doaj_lic, l.cc_type
           FROM b JOIN w26issn w USING (doi) JOIN doaj d USING (issn) JOIN lic26 l ON l.doi = b.doi)
SELECT doaj_lic AS DOAJ등록, cc_type AS Crossref기재, count(DISTINCT doi) AS 논문수
FROM m WHERE NOT (doaj_lic ILIKE '%' || cc_type || '%') GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10""")

# (3) 신규분도 0%인 출판사: 라이선스 자체가 없는지
show("3. Medknow·JMIR 등의 라이선스 기재 형태 (2026 스냅숏)", """
SELECT any_value(s.publisher) AS publisher,
       count(*) AS 패널논문,
       count(*) FILTER (WHERE s.doi IN (SELECT doi FROM read_parquet('D:/crossref/parquet/2026/licenses/*.parquet'))) AS 라이선스행있음,
       count(*) FILTER (WHERE s.cc26=1) AS CC기재
FROM s WHERE s.member IN ('2581','1010','16518','1893','1898') GROUP BY s.member""")

show("3-2. 그 출판사들이 쓰는 라이선스 URL 상위 10개", """
SELECT l.url, l.content_version, count(*) AS 행수
FROM s JOIN read_parquet('D:/crossref/parquet/2026/licenses/*.parquet') l USING (doi)
WHERE s.member IN ('2581','1010') GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10""")
