"""
추출 결과 점검 스크립트

사용법
  python check_snapshot.py <시점 폴더>
예시
  python check_snapshot.py D:\\crossref\\parquet\\2023

하는 일
  1. 행 수, DOI 중복, 빈 값 비율, 출판연도 범위 출력
  2. 라이선스 종류 분포, CC 기재 논문 비율 출력
  3. 엑셀로 열어볼 수 있는 표본 CSV 2개 저장 (시점 폴더 안 check 폴더)
"""
import csv
import os
import sys

import duckdb


def main():
    root = sys.argv[1]
    snap = os.path.basename(os.path.normpath(root))
    works = os.path.join(root, "works", "*.parquet").replace("\\", "/")
    lics = os.path.join(root, "licenses", "*.parquet").replace("\\", "/")
    out = os.path.join(root, "check")
    tmp = os.path.join(root, "_tmp")
    os.makedirs(out, exist_ok=True)
    os.makedirs(tmp, exist_ok=True)

    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='4GB'")
    con.execute(f"SET temp_directory='{tmp.replace(chr(92), '/')}'")
    con.execute(f"CREATE VIEW w AS SELECT * FROM read_parquet('{works}')")
    con.execute(f"CREATE VIEW l AS SELECT * FROM read_parquet('{lics}')")

    def one(sql):
        return con.execute(sql).fetchone()

    def table(title, sql):
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        print(f"\n[{title}]")
        print("  " + " | ".join(cols))
        for r in rows:
            print("  " + " | ".join("" if v is None else f"{v:,}" if isinstance(v, int) and abs(v) >= 10000 else str(v) for v in r))

    print(f"===== {snap} 점검 =====")

    n_w, n_doi = one("SELECT count(*), count(DISTINCT doi) FROM w")
    n_l = one("SELECT count(*) FROM l")[0]
    print(f"\n[1. 행 수]")
    print(f"  논문 표 {n_w:,}행 (서로 다른 DOI {n_doi:,}개, 중복 {n_w - n_doi:,})")
    print(f"  라이선스 표 {n_l:,}행")

    table("2. 빈 값 비율(%)", """
        SELECT round(100.0*count(*) FILTER (WHERE member IS NULL)/count(*), 2)     AS member,
               round(100.0*count(*) FILTER (WHERE publisher IS NULL)/count(*), 2)  AS publisher,
               round(100.0*count(*) FILTER (WHERE issued IS NULL)/count(*), 2)     AS issued,
               round(100.0*count(*) FILTER (WHERE published IS NULL)/count(*), 2)  AS published,
               round(100.0*count(*) FILTER (WHERE created IS NULL)/count(*), 2)    AS created,
               round(100.0*count(*) FILTER (WHERE deposited IS NULL)/count(*), 2)  AS deposited
        FROM w""")

    table("3. 출판연도 범위와 deposited 최신값", """
        SELECT min(pub_year) AS 최소연도, max(pub_year) AS 최대연도,
               max(deposited) AS 가장_최근_deposited
        FROM w""")

    table("4. 출판연도별 논문 수 (2000·2010·2015·2020 이후)", """
        SELECT CASE WHEN pub_year < 2010 THEN '2000-2009'
                    WHEN pub_year < 2015 THEN '2010-2014'
                    WHEN pub_year < 2020 THEN '2015-2019'
                    ELSE '2020-' END AS 구간,
               count(*) AS 논문수
        FROM w GROUP BY 1 ORDER BY 1""")

    table("5. content-version 분포 (라이선스 표)", """
        SELECT coalesce(content_version, '(없음)') AS content_version,
               count(*) AS 행수,
               count(*) FILTER (WHERE url ILIKE '%creativecommons.org%') AS CC주소
        FROM l GROUP BY 1 ORDER BY 2 DESC""")

    n_cc = one("""
        SELECT count(DISTINCT doi) FROM l
        WHERE url ILIKE '%creativecommons.org%'
          AND coalesce(content_version, '') IN ('vor', 'am', 'unspecified')""")[0]
    n_any = one("SELECT count(*) FROM w WHERE n_license > 0")[0]
    print("\n[6. 라이선스 보유 논문]")
    print(f"  라이선스 하나라도 있음 {n_any:,}건 ({100 * n_any / n_w:.1f}%)")
    print(f"  CC 기재(vor·am·unspecified) {n_cc:,}건 ({100 * n_cc / n_w:.1f}%)")

    table("7. 논문 수 상위 10개 출판사", """
        SELECT member, any_value(publisher) AS publisher, count(*) AS 논문수
        FROM w GROUP BY member ORDER BY 3 DESC LIMIT 10""")

    # 표본 CSV (엑셀용, 한글 깨짐 방지 utf-8-sig)
    def save(path, sql):
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.writer(f)
            wr.writerow(cols)
            wr.writerows(cur.fetchall())

    con.execute("CREATE TEMP TABLE s AS SELECT * FROM w USING SAMPLE 1000 ROWS")
    p1 = os.path.join(out, f"sample_works_{snap}.csv")
    p2 = os.path.join(out, f"sample_licenses_{snap}.csv")
    save(p1, "SELECT * FROM s")
    save(p2, "SELECT l.* FROM l JOIN s USING (doi) ORDER BY doi")
    print("\n[8. 표본 저장]")
    print(f"  {p1}")
    print(f"  {p2}")

    con.close()
    try:
        os.rmdir(tmp)
    except OSError:
        pass
    print("\n점검 끝")


if __name__ == "__main__":
    main()
