import duckdb, os, time
os.makedirs(r"D:\crossref\_tmp", exist_ok=True)
con = duckdb.connect()
con.execute("SET threads=4"); con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET temp_directory='D:/crossref/_tmp'")
t0 = time.time()
DOAJ = "D:/doaj_journalcsv_20260817_2320_utf8.csv"

con.execute(f"""
CREATE TABLE jall AS
WITH j AS (SELECT "Journal title" AS title,
                  upper(trim("Journal ISSN (print version)")) AS p,
                  upper(trim("Journal EISSN (online version)")) AS e,
                  "Journal license" AS lic,
                  CAST(substr(CAST("Added on Date" AS VARCHAR), 1, 4) AS INT) AS added_y,
                  CAST("When did the journal start to publish all content using an open license?" AS INT) AS oa
           FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true))
SELECT * FROM j
WHERE added_y <= 2021
  AND len(list_filter(str_split(lic, ','), x -> NOT starts_with(trim(x), 'CC'))) = 0
""")
print("CC + 2021년까지 등재:", con.execute("SELECT count(*) FROM jall").fetchone()[0])
print("  이 중 OA 시작연도 > 등재연도:",
      con.execute("SELECT count(*) FROM jall WHERE oa > added_y").fetchone()[0])

con.execute("""CREATE TABLE jissn AS
SELECT upper(trim(issn)) AS issn, min(greatest(oa,2003)) AS min_year
FROM jall, UNNEST([p,e]) AS t(issn) WHERE issn IS NOT NULL AND issn <> '' GROUP BY 1""")
con.execute("""CREATE TABLE base AS
SELECT DISTINCT w.doi FROM
(SELECT doi, pub_year, upper(trim(t.s)) AS issn FROM read_parquet('D:/crossref/parquet/2023/works/*.parquet'),
 UNNEST(str_split(issn,';')) AS t(s)) w
JOIN jissn j USING (issn) WHERE w.pub_year >= j.min_year AND w.pub_year <= 2023""")
print("패널 후보:", con.execute("SELECT count(*) FROM base").fetchone()[0], f"({time.time()-t0:.0f}초)", flush=True)

for y in ("2023","2026"):
    con.execute(f"""CREATE TABLE cc{y} AS SELECT DISTINCT doi FROM
      read_parquet('D:/crossref/parquet/{y}/licenses/*.parquet')
      WHERE url ILIKE '%creativecommons.org%' AND coalesce(content_version,'') IN ('vor','am','unspecified')""")
    con.execute(f"""CREATE TABLE in{y} AS SELECT DISTINCT doi FROM
      read_parquet('D:/crossref/parquet/{y}/works/*.parquet')""")
    print(y, "준비", f"({time.time()-t0:.0f}초)", flush=True)

print("\n[224종 포함 시 핵심 수치]")
for r in con.execute("""
SELECT count(*) AS 패널,
       count(*) FILTER (WHERE doi NOT IN (SELECT doi FROM cc2023)) AS 미기재2023,
       count(*) FILTER (WHERE doi NOT IN (SELECT doi FROM cc2023) AND doi IN (SELECT doi FROM cc2026)) AS 보완,
       round(100.0*count(*) FILTER (WHERE doi NOT IN (SELECT doi FROM cc2023) AND doi IN (SELECT doi FROM cc2026))
             / count(*) FILTER (WHERE doi NOT IN (SELECT doi FROM cc2023)),2) AS 보완율,
       round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc2023))/count(*),1) AS 기재율2023,
       round(100.0*count(*) FILTER (WHERE doi IN (SELECT doi FROM cc2026))/count(*),1) AS 기재율2026
FROM base WHERE doi IN (SELECT doi FROM in2026)""").fetchall(): print("  ", r)
print(f"총 {time.time()-t0:.0f}초")
