"""4.3절 '424개 출판사 가운데 288곳(67.9%), 중앙값 0.0%' 의 근거 확인.
실행: D:\\crossref-cc-panel 에서  py verify\\check_288.py
결과: D:\\crossref\\check_288_out.txt  (화면 출력 없이 파일에만 기록)
"""
import traceback

OUT = "D:/crossref/check_288_out.txt"
P = "D:/crossref/parquet/state_panel.parquet"

with open(OUT, "w", encoding="utf-8") as f:
    def log(s=""):
        f.write(s + "\n"); f.flush()
    try:
        import duckdb
        con = duckdb.connect()
        for q in ["SET threads=4", "SET memory_limit='6GB'",
                  "SET preserve_insertion_order=false", "SET temp_directory='D:/crossref/_tmp'"]:
            con.execute(q)
        con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{P}') WHERE in26=1")
        con.execute("""CREATE TABLE t AS SELECT member,
              count(*) FILTER (WHERE cc23=0) n,
              count(*) FILTER (WHERE cc23=0 AND cc26=1) k
            FROM s GROUP BY member""")

        log("[미기재 하한별 출판사 수, 보완 0인 곳, 중앙값]")
        log("  하한 | 출판사 | 보완0 | 보완0비율 | 중앙값")
        for lo in [1, 10, 50, 100, 200, 500, 1000, 10000]:
            r = con.execute(f"""SELECT count(*), count(*) FILTER (WHERE k=0),
                  round(100.0*count(*) FILTER (WHERE k=0)/count(*),1),
                  round(median(100.0*k/n),2) FROM t WHERE n>={lo}""").fetchone()
            log(f"  {lo:>6,} | {r[0]:,} | {r[1]:,} | {r[2]} | {r[3]}")

        log("\n[424 또는 288이 나오는 하한 탐색 (1~5,000)]")
        rows = con.execute("""WITH g AS (SELECT range lo FROM range(1,5001))
            SELECT lo, (SELECT count(*) FROM t WHERE n>=lo) c,
                   (SELECT count(*) FROM t WHERE n>=lo AND k=0) z FROM g""").fetchall()
        hit = [r for r in rows if r[1] == 424 or r[2] == 288]
        if hit:
            for r in hit[:20]:
                log(f"  하한 {r[0]:,}: 출판사 {r[1]:,}, 보완0 {r[2]:,}")
        else:
            log("  해당 없음")

        log("\n[참고: 2023년 미기재가 있는 출판사 전체]")
        r = con.execute("SELECT count(*), count(*) FILTER (WHERE k=0) FROM t WHERE n>0").fetchone()
        log(f"  출판사 {r[0]:,}, 보완0 {r[1]:,}")
        log("\n완료")
    except Exception:
        log("오류")
        log(traceback.format_exc())
