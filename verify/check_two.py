"""두 수치 확인
1. AIP Publishing(member 317)의 연도판별 기재율 (원고: 15.8%, 0.7%, 0.6%, 96.1%)
2. 2026년판 추출에서 빠진 9,181건의 상태를 양 극단으로 가정한 보완율 (원고: 5.69–5.86%)
실행: py D:\\crossref-cc-panel\\verify\\check_two.py
결과: D:\\crossref\\check_two_out.txt
"""
import traceback

OUT = "D:/crossref/check_two_out.txt"
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
        con.execute(f"CREATE VIEW a AS SELECT * FROM read_parquet('{P}')")

        log("[0. 패널 파일 구성]")
        cols = [r[0] for r in con.execute("DESCRIBE a").fetchall()]
        log("  열: " + ", ".join(cols))
        for r in con.execute("SELECT in26, count(*) FROM a GROUP BY 1 ORDER BY 1").fetchall():
            log(f"  in26={r[0]}: {r[1]:,}")

        log("\n[1. AIP Publishing (member 317), 패널 in26=1]")
        r = con.execute("""SELECT count(*), any_value(publisher),
              round(100.0*avg(cc23),1), round(100.0*avg(cc24),1),
              round(100.0*avg(cc25),1), round(100.0*avg(cc26),1),
              count(*) FILTER (WHERE cc23=1 AND cc24=0 AND cc25=0 AND cc26=1)
            FROM a WHERE in26=1 AND CAST(member AS VARCHAR)='317'""").fetchone()
        log(f"  출판사 {r[1]}, 패널 {r[0]:,}건")
        log(f"  기재율 2023 {r[2]}%  2024 {r[3]}%  2025 {r[4]}%  2026 {r[5]}%")
        log(f"  1001 패턴 {r[6]:,}건   (원고: 15.8, 0.7, 0.6, 96.1 / 2,612)")
        r = con.execute("""SELECT count(*) FILTER (WHERE in24=1), count(*) FILTER (WHERE in25=1)
            FROM a WHERE in26=1 AND CAST(member AS VARCHAR)='317'""").fetchone()
        log(f"  레코드 존재 2024년판 {r[0]:,}  2025년판 {r[1]:,}")

        log("\n[2. 2026년판에서 빠진 DOI의 양 극단 가정]")
        n, k = con.execute("""SELECT count(*) FILTER (WHERE cc23=0), count(*) FILTER (WHERE cc23=0 AND cc26=1)
            FROM a WHERE in26=1""").fetchone()
        ex, m = con.execute("SELECT count(*), count(*) FILTER (WHERE cc23=0) FROM a WHERE coalesce(in26,0)=0").fetchone()
        log(f"  패널 2023년판 미기재 {n:,}, 보완 {k:,}, 보완율 {100.0*k/n:.4f}%")
        log(f"  빠진 DOI {ex:,}건 (원고 9,181), 그중 2023년판 미기재 {m:,}건")
        if ex:
            lo = 100.0*k/(n+m); hi = 100.0*(k+m)/(n+m)
            log(f"  모두 미기재로 남았다고 가정  {lo:.4f}%  -> {lo:.2f}%")
            log(f"  모두 보완되었다고 가정       {hi:.4f}%  -> {hi:.2f}%   (원고 5.69–5.86%)")
        else:
            log("  패널 파일에 빠진 DOI가 없음. 다른 입력이 필요함")
        log("\n완료")
    except Exception:
        log("오류")
        log(traceback.format_exc())
