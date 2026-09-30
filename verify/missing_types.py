"""
2023년 미기재 2,944,831건이 실제로 어떤 상태인지 세 유형으로 나눈다.

배경
  3.3절의 판정 규칙에서 '미기재'는 서로 다른 세 상태를 함께 담는다.

    A  라이선스 항목이 아예 없다
    B  라이선스 항목은 있으나 creativecommons.org URL이 없다
    C  CC URL은 있으나 인정하지 않는 content-version(tdm 등)에만 붙어 있다

  세 상태는 필요한 보완 작업이 서로 다르다. A는 정보의 추가, B는 라이선스 내용이나
  URL 표기의 확인, C는 적용 버전의 확인이 필요하다. 보완 167,779건이 어느 유형에서
  나왔는지에 따라 '보완'이라는 말의 실제 내용도 달라진다.

  4.9절의 민감도 분석에서 tdm을 인정하면 초기 미기재가 275만 건으로 줄어든다고
  보고하였으므로 C의 규모는 약 19만 건으로 이미 짐작할 수 있다. 이 스크립트는
  그 값을 정확히 내고, A와 B를 처음으로 구분한다.

실행
  python missing_types.py

입력
  D:/crossref/parquet/state_panel.parquet
  D:/crossref/parquet/2023/licenses/*.parquet

출력
  D:/crossref/missing_types_out.txt
"""
import os

import duckdb

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
P = os.environ.get("CROSSREF_PARQUET", f"{ROOT}/parquet")
OUT = os.environ.get("CROSSREF_MT_OUT", f"{ROOT}/missing_types_out.txt")
TMP = os.environ.get("CROSSREF_TMP", f"{ROOT}/_tmp")
os.makedirs(TMP, exist_ok=True)

logf = open(OUT, "w", encoding="utf-8")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    logf.write(s + "\n")
    logf.flush()


con = duckdb.connect()
for q in ["SET threads=4", "SET memory_limit='6GB'",
          "SET preserve_insertion_order=false", f"SET temp_directory='{TMP}'"]:
    con.execute(q)

# 본문 3.3절의 판정 규칙
CCQ = ("url ILIKE '%creativecommons.org%' "
       "AND coalesce(content_version,'') IN ('vor','am','unspecified')")

EXPECTED = {"미기재_전체": 2944831, "보완_전체": 167779,
            "A 라이선스 항목 없음": 2478640,
            "B 비CC URL만 있음": 274303,
            "C CC URL이 비인정 버전에만": 191888}


def check(key, v):
    if key not in EXPECTED:
        return f"{v:,}"
    return f"{v:,}  " + ("일치" if v == EXPECTED[key] else f"불일치 (원고 {EXPECTED[key]:,})")


con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1")
con.execute(f"CREATE VIEW l23 AS SELECT * FROM read_parquet('{P}/2023/licenses/*.parquet')")

# 2023년 미기재 레코드
con.execute("CREATE TABLE miss AS SELECT doi, cc26 FROM s WHERE cc23 = 0")

# 각 DOI의 2023년 라이선스 항목 성격
con.execute(f"""CREATE TABLE lic23 AS
SELECT doi,
       count(*) n_rows,
       count(*) FILTER (WHERE url ILIKE '%creativecommons.org%') n_cc
FROM l23 WHERE doi IN (SELECT doi FROM miss) GROUP BY doi""")

con.execute("""CREATE TABLE typed AS
SELECT m.doi, m.cc26,
       CASE WHEN l.doi IS NULL OR l.n_rows = 0 THEN 'A 라이선스 항목 없음'
            WHEN l.n_cc = 0                    THEN 'B 비CC URL만 있음'
            ELSE                                    'C CC URL이 비인정 버전에만'
       END AS 유형
FROM miss m LEFT JOIN lic23 l USING (doi)""")

n_miss = con.execute("SELECT count(*) FROM typed").fetchone()[0]
n_add = con.execute("SELECT count(*) FROM typed WHERE cc26 = 1").fetchone()[0]

log("=" * 74)
log("2023년 미기재의 구성")
log("=" * 74)
log(f"\n  미기재 전체  {check('미기재_전체', n_miss)}")
log(f"  그중 보완    {check('보완_전체', n_add)}")
log(f"\n  판정 규칙: {CCQ}")

cur = con.execute("""
SELECT 유형, count(*) 건수,
       round(100.0*count(*)/(SELECT count(*) FROM typed), 2) 미기재내비중,
       count(*) FILTER (WHERE cc26=1) 보완,
       round(100.0*count(*) FILTER (WHERE cc26=1)/count(*), 2) 유형별보완율,
       round(100.0*count(*) FILTER (WHERE cc26=1)
             /(SELECT count(*) FROM typed WHERE cc26=1), 2) 보완내비중
FROM typed GROUP BY 1 ORDER BY 1""")
log("\n[유형별]")
log("  " + " | ".join(d[0] for d in cur.description))
for r in cur.fetchall():
    log("  " + " | ".join(f"{v:,}" if isinstance(v, int) else str(v) for v in r))

log("""
  읽는 법
    미기재내비중   2023년 미기재 가운데 이 유형이 차지하는 몫
    유형별보완율   이 유형 안에서 2026년까지 보완된 비율
    보완내비중     보완 167,779건 가운데 이 유형에서 나온 몫
""")

log("=" * 74)
log("C 유형의 내역 — 어떤 content-version에 CC가 붙어 있었나")
log("=" * 74)
cur = con.execute("""
SELECT coalesce(l.content_version, '(값 없음)') content_version,
       count(DISTINCT l.doi) DOI수
FROM l23 l JOIN typed t ON t.doi = l.doi AND t.유형 = 'C CC URL이 비인정 버전에만'
WHERE l.url ILIKE '%creativecommons.org%'
GROUP BY 1 ORDER BY 2 DESC""")
log("  " + " | ".join(d[0] for d in cur.description))
for r in cur.fetchall():
    log("  " + " | ".join(f"{v:,}" if isinstance(v, int) else str(v) for v in r))
log("\n  4.9절은 tdm을 인정하면 초기 미기재가 275만 건으로 줄어든다고 보고하였다.")
log("  위 tdm 행의 DOI 수가 그 차이와 맞아야 한다.")

log("\n" + "=" * 74)
log("B 유형의 내역 — 어떤 URL이 들어 있었나 (상위 15개 도메인)")
log("=" * 74)
cur = con.execute("""
SELECT regexp_extract(lower(l.url), '^https?://([^/]+)', 1) 도메인,
       count(DISTINCT l.doi) DOI수
FROM l23 l JOIN typed t ON t.doi = l.doi AND t.유형 = 'B 비CC URL만 있음'
GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
log("  " + " | ".join(d[0] for d in cur.description))
for r in cur.fetchall():
    log("  " + " | ".join(f"{v:,}" if isinstance(v, int) else str(v) for v in r))

log("\n" + "=" * 74)
log("원고에 넣을 문장의 재료")
log("=" * 74)
rows = con.execute("""
SELECT 유형, count(*), count(*) FILTER (WHERE cc26=1) FROM typed GROUP BY 1 ORDER BY 1""").fetchall()
log("")
for t, n, a in rows:
    log(f"  {t:<24} {n:>10,}건 ({100.0*n/n_miss:>5.1f}%)   "
        f"보완 {a:>8,}건 ({100.0*a/n if n else 0:>5.2f}%)")
log(f"\n  보완 {n_add:,}건의 출처별 비중")
for t, n, a in rows:
    log(f"    {t:<24} {100.0*a/n_add:>5.1f}%")

log("\n" + "=" * 74)
log("원고 값과의 대조")
log("=" * 74)
log("")
ok = True
for t, n, _ in rows:
    log(f"  {t:<24} {check(t, n)}")
    ok &= (t not in EXPECTED or n == EXPECTED[t])
log(f"\n  {'모든 값이 원고와 일치한다.' if ok else '불일치가 있다. 위 행을 확인한다.'}")

log(f"\n완료. 결과: {OUT}")
logf.close()
