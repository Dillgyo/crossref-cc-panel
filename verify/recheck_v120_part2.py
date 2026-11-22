"""
재검증 2부: 4.3절 변동 분해와 순열, 그림 3의 104건·97건.
Claude가 verify/variance.py와 GPT 질의를 보지 않고, 원고(보충자료 S3.2 서술)와
크로스체크 결과 3차의 정의만 따라 새로 작성했다.

실행
    python verify/recheck_v120_part2.py   (numpy 필요)
    (자료 위치는 CROSSREF_ROOT, 출력 위치는 CROSSREF_OUT으로 바꿀 수 있다)

출력
    화면과 recheck2_out.txt

정의
  분석 단위   2023년판 미기재이면서 member가 있는 DOI를 DOAJ 저널(ISSN 연결)과 짝지은 행.
              한 DOI가 두 저널에 연결되면 두 행이 된다.
  y           2026년판 보완 여부(1/0)
  귀속 1안    각 저널을 그 저널 행이 가장 많은 member(최빈 member)에 배정한다.
              동률이면 member 문자열이 작은 쪽. 원고 확정안(저자 결정)이다.
  귀속 2안    각 행의 원래 member를 유지하고, (member, 저널) 칸을 저널로 본다.
  분해        SS_total = SS_출판사간 + SS_출판사내 저널간 + SS_저널내
              세 항을 모두 직접 계산하고, 합이 SS_total과 같은지 확인한다.
  순열        1안 귀속을 고정하고, 각 출판사 안에서 y를 무작위로 섞은 뒤
              (저널 크기와 출판사별 보완 수가 보존됨) 출판사내 저널간 몫을 다시 구한다.
              시드 0–9, 10회. 원고는 10회 범위 "0.12–0.14%"로 적었으므로 최솟값과 최댓값을 비교한다.
              (난수 생성 방식이 다르면 소수 둘째 자리가 달라질 수 있다.)
"""
import os
import time

import duckdb

try:
    import numpy as np
except ImportError:
    np = None

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
P = f"{ROOT}/parquet"
DOAJ = f"{ROOT}/doaj_panel_journals.csv"
TMP = f"{ROOT}/_tmp"
OUTDIR = os.environ.get("CROSSREF_OUT", os.path.dirname(os.path.abspath(__file__)))
OUT = f"{OUTDIR}/recheck2_out.txt"
os.makedirs(TMP, exist_ok=True)
os.makedirs(OUTDIR, exist_ok=True)

logf = open(OUT, "w", encoding="utf-8")
T0 = time.time()
RESULT = {"일치": 0, "불일치": 0}


def log(s=""):
    print(s, flush=True)
    logf.write(s + "\n")
    logf.flush()


def chk(label, val, exp, nd=None):
    if exp is None:
        log(f"  {label}: {val:,}" if isinstance(val, int) else f"  {label}: {val}")
        return
    v = round(val, nd) if nd is not None else val
    ok = (v == exp)
    RESULT["일치" if ok else "불일치"] += 1
    shown = f"{v:,}" if isinstance(v, int) and not isinstance(v, bool) else f"{v}"
    log(f"  {label}: {shown}  " + ("[일치]" if ok else f"[불일치 기대 {exp}]"))


def one(q):
    return con.execute(q).fetchone()


con = duckdb.connect()
for q in ["SET threads=4", "SET memory_limit='6GB'",
          "SET preserve_insertion_order=false", f"SET temp_directory='{TMP}'"]:
    con.execute(q)

con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{P}/state_panel.parquet') WHERE in26=1")
con.execute(f"CREATE VIEW w2023 AS SELECT * FROM read_parquet('{P}/2023/works/*.parquet')")

# ---------------------------------------------------------------------------
log("=" * 72)
log("H. 그림 3에서 뺀 104건과 97건 (4.3절 그림 3 설명, 5.3절)")
log("=" * 72)
con.execute("""CREATE TABLE b AS
SELECT doi, dep23, dep26,
       CASE WHEN cc24=1 THEN 2024 WHEN cc25=1 THEN 2025 ELSE 2026 END fv,
       CASE WHEN cc24=1 THEN dep24 WHEN cc25=1 THEN dep25 ELSE dep26 END depfv
FROM s WHERE cc23=0 AND cc26=1""")
chk("보완 레코드", one("SELECT count(*) FROM b")[0], 167779)
chk("첫 CC 관찰판의 deposited가 2023-04-01 이전", one("SELECT count(*) FROM b WHERE depfv < '2023-04-01'")[0], 104)
chk("그중 첫 관찰판 deposited > 2023년판 deposited",
    one("SELECT count(*) FROM b WHERE depfv < '2023-04-01' AND depfv > dep23")[0], 104)
chk("그중 두 끝판 deposited 전진 (dep26 > dep23)",
    one("SELECT count(*) FROM b WHERE depfv < '2023-04-01' AND dep26 > dep23")[0], 104)
chk("† 그중 2026년판 deposited도 2023-04-01 이전",
    one("SELECT count(*) FROM b WHERE depfv < '2023-04-01' AND dep26 < '2023-04-01'")[0], 97)
r = con.execute("""SELECT fv, count(*) FROM b WHERE depfv < '2023-04-01' GROUP BY fv ORDER BY fv""").fetchall()
chk("첫 CC 관찰판별 (2024/2025/2026)", tuple(k for _, k in r), (9, 56, 39))

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("I. 4.3절 변동 분해 (보충자료 S3.2)")
log("=" * 72)
con.execute(f"""CREATE TABLE jrow AS
SELECT row_number() OVER () jid,
       upper(trim("Journal ISSN (print version)")) p,
       upper(trim("Journal EISSN (online version)")) e
FROM read_csv_auto('{DOAJ}', header=true, all_varchar=true)""")
con.execute("""CREATE TABLE j2i AS SELECT jid, issn FROM jrow, UNNEST([p, e]) t(issn)
               WHERE issn IS NOT NULL AND trim(issn) <> ''""")
con.execute("""CREATE TABLE base AS
SELECT doi, member, cc26 y FROM s
WHERE cc23=0 AND member IS NOT NULL AND trim(member) <> ''""")
con.execute("""CREATE TABLE r AS
SELECT DISTINCT w.doi, m.jid
FROM (SELECT doi, upper(trim(t.s)) issn FROM w2023, UNNEST(str_split(issn, ';')) t(s)
      WHERE doi IN (SELECT doi FROM base)) w
JOIN j2i m USING (issn)""")
con.execute("CREATE TABLE rows AS SELECT r.doi, r.jid, b.member, b.y FROM r JOIN base b USING (doi)")
chk("분석 대상 고유 DOI (미기재 중 member 있음)", one("SELECT count(DISTINCT doi) FROM rows")[0], 2943021)
chk("참고: 저널에 연결되지 않은 미기재 DOI",
    one("SELECT count(*) FROM base WHERE doi NOT IN (SELECT doi FROM r)")[0], None)
chk("DOI–저널 행", one("SELECT count(*) FROM rows")[0], 2943755)
chk("저널 수", one("SELECT count(DISTINCT jid) FROM rows")[0], 9947)
chk("둘 이상의 member에 걸친 저널",
    one("SELECT count(*) FROM (SELECT jid FROM rows GROUP BY jid HAVING count(DISTINCT member) > 1)")[0], 304)
con.execute("""CREATE TABLE modal AS
SELECT jid, member mm FROM (
  SELECT jid, member, row_number() OVER (PARTITION BY jid ORDER BY count(*) DESC, member) rk
  FROM rows GROUP BY jid, member) WHERE rk = 1""")
ties = one("""WITH c AS (SELECT jid, member, count(*) n FROM rows GROUP BY 1, 2),
  mx AS (SELECT jid, max(n) mn FROM c GROUP BY 1)
SELECT count(*) FROM (SELECT c.jid FROM c JOIN mx ON c.jid = mx.jid AND c.n = mx.mn
                      GROUP BY c.jid HAVING count(*) > 1)""")[0]
log(f"    최빈 member가 동률인 저널: {ties}개 (member 문자열이 작은 쪽으로 배정)")
con.execute("CREATE TABLE rows1 AS SELECT r.*, m.mm FROM rows r JOIN modal m USING (jid)")
chk("원래 member와 최빈 member가 다른 행", one("SELECT count(*) FROM rows1 WHERE member <> mm")[0], 30083)


def decompose(pub, cell, tag):
    """pub: 출판사 열, cell: 저널 칸을 정의하는 열 목록(문자열)."""
    q = f"""
    WITH g AS (SELECT avg(y) gm FROM rows1),
         pm AS (SELECT {pub} pk, avg(y) pmean, count(*) pn FROM rows1 GROUP BY 1),
         cm AS (SELECT {pub} pk, {cell} ck, avg(y) cmean, count(*) cn FROM rows1 GROUP BY 1, 2)
    SELECT
      (SELECT sum(power(y - gm, 2)) FROM rows1, g) sst,
      (SELECT sum(pn * power(pmean - gm, 2)) FROM pm, g) ssp,
      (SELECT sum(cn * power(cmean - pmean, 2)) FROM cm JOIN pm USING (pk)) ssj,
      (SELECT sum(power(r.y - cm.cmean, 2)) FROM rows1 r
         JOIN cm ON cm.pk = r.{pub} AND cm.ck = {cell.replace('jid', 'r.jid').replace('member', 'r.member')}) ssw
    """
    sst, ssp, ssj, ssw = one(q)
    log(f"    [{tag}] SS_total {sst:,.2f} = 출판사간 {ssp:,.2f} + 출판사내 저널간 {ssj:,.2f} + 저널내 {ssw:,.2f}")
    chk(f"[{tag}] 세 항의 합과 총제곱합의 차이(절대값<1e-6×SST)", abs(sst - ssp - ssj - ssw) < 1e-6 * sst, True)
    return 100 * ssp / sst, 100 * ssj / sst, 100 * ssw / sst


a1 = decompose("mm", "jid", "1안 최빈 member")
chk("† 1안 출판사간(%)", a1[0], 47.03, 2)
chk("† 1안 출판사내 저널간(%)", a1[1], 25.71, 2)
chk("† 1안 저널내(%)", a1[2], 27.27, 2)
a2 = decompose("member", "jid", "2안 원래 member")
chk("2안 출판사간(%)", a2[0], 47.09, 2)
chk("2안 출판사내 저널간(%)", a2[1], 25.78, 2)
chk("2안 저널내(%)", a2[2], 27.13, 2)

# ---------------------------------------------------------------------------
log("\n" + "=" * 72)
log("J. 순열 비교 (1안 귀속, 출판사 안에서 y를 섞음, 10회)")
log("=" * 72)
if np is None:
    log("    numpy가 없어 건너뜀 (pip install numpy 후 다시 실행)")
else:
    arr = con.execute("""SELECT dense_rank() OVER (ORDER BY mm) - 1 p,
                                dense_rank() OVER (ORDER BY jid) - 1 j, y
                         FROM rows1 ORDER BY p, j""").fetchnumpy()
    p_ = np.asarray(arr["p"], dtype=np.int64)
    j_ = np.asarray(arr["j"], dtype=np.int64)
    y_ = np.asarray(arr["y"], dtype=np.float64)
    n = len(y_)
    gm = y_.mean()
    sst = ((y_ - gm) ** 2).sum()
    pn = np.bincount(p_)
    pmean = np.bincount(p_, weights=y_) / pn
    jn = np.bincount(j_)
    jp = np.zeros(len(jn), dtype=np.int64)
    jp[j_] = p_                               # 1안에서 저널은 한 출판사에만 속한다
    bounds = np.r_[0, np.cumsum(pn)]          # 행이 p 순으로 정렬되어 있음

    def ssj_of(y):
        jmean = np.bincount(j_, weights=y, minlength=len(jn)) / jn
        return (jn * (jmean - pmean[jp]) ** 2).sum()

    chk("순열 전 출판사내 저널간(%) (1안과 같아야 함)", 100 * ssj_of(y_) / sst, round(a1[1], 2), 2)
    vals = []
    for seed in range(10):
        rng = np.random.default_rng(seed)
        yy = y_.copy()
        for k in range(len(pn)):
            lo, hi = bounds[k], bounds[k + 1]
            if hi - lo > 1:
                yy[lo:hi] = rng.permutation(yy[lo:hi])
        vals.append(100 * ssj_of(yy) / sst)
        log(f"    시드 {seed}: {vals[-1]:.4f}%")
    med = float(np.median(vals))
    log(f"    범위 {min(vals):.4f}–{max(vals):.4f}%, 중앙값 {med:.4f}%")
    chk("순열 최솟값(%), 원고 '0.12–0.14%'", min(vals), 0.12, 2)
    chk("순열 최댓값(%), 원고 '0.12–0.14%'", max(vals), 0.14, 2)

log("\n" + "=" * 72)
log(f"요약: 일치 {RESULT['일치']}  불일치 {RESULT['불일치']}  ({time.time() - T0:.0f}초)")
log("=" * 72)
