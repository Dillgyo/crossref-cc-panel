"""표 1 '2023년판에서 논문 확인' 행 확인 (원고: 11,955종, 8,294,247건)
실행: py D:\\crossref-cc-panel\\verify\\check_table1.py
결과: D:\\crossref\\check_table1_out.txt
"""
import traceback

OUT = "D:/crossref/check_table1_out.txt"
P = "D:/crossref/parquet"
DOAJ = "D:/crossref-cc-panel/data/doaj_panel_journals.csv"

with open(OUT, "w", encoding="utf-8") as f:
    def log(s=""):
        f.write(s + "\n"); f.flush()
    try:
        import duckdb
        con = duckdb.connect()
        for q in ["SET threads=4", "SET memory_limit='6GB'",
                  "SET preserve_insertion_order=false", "SET temp_directory='D:/crossref/_tmp'"]:
            con.execute(q)
        con.execute(f"""CREATE TABLE j AS SELECT row_number() OVER () jid,
              "Journal ISSN (print version)" p, "Journal EISSN (online version)" e,
              CAST("OA start" AS INT) oa
            FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true)""")
        con.execute("""CREATE TABLE ji AS SELECT DISTINCT jid, upper(trim(issn)) issn, greatest(oa, 2003) min_year
            FROM j, UNNEST([p, e]) t(issn) WHERE issn IS NOT NULL AND trim(issn) <> ''""")
        log(f"모집단 저널 {con.execute('SELECT count(*) FROM j').fetchone()[0]:,} (원고 13,806)")

        con.execute(f"""CREATE TABLE m AS
            SELECT DISTINCT w.doi, w.pub_year, ji.jid, ji.min_year
            FROM (SELECT doi, pub_year, upper(trim(s)) issn
                  FROM read_parquet('{P}/2023/works/*.parquet'), UNNEST(str_split(issn, ';')) t(s)) w
            JOIN ji USING (issn)""")

        def row(label, cond):
            r = con.execute(f"SELECT count(DISTINCT jid), count(DISTINCT doi) FROM m WHERE {cond}").fetchone()
            log(f"  {label:<40} 저널 {r[0]:>7,}   논문 {r[1]:>10,}")

        log("\n[2023년판에서 논문 확인 — 정의별]")
        row("출판연도 조건 없음", "TRUE")
        row("출판연도 2023년 이하", "pub_year <= 2023")
        row("출판연도 2003~2023년", "pub_year BETWEEN 2003 AND 2023")
        log("  (원고 11,955종, 8,294,247건)")

        log("\n[저널별 출판연도 하한 적용 — 대조용]")
        row("하한 이상, 2023년 이하", "pub_year >= min_year AND pub_year <= 2023")
        log("  (원고 11,949종, 7,225,064건)")
        log("\n완료")
    except Exception:
        log("오류")
        log(traceback.format_exc())
