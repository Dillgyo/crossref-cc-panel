"""
그림 1~3을 그린다. 05_tables.py가 저장한 CSV를 입력으로 받는다.

실행
  python 06_figures.py            한국어 라벨
  python 06_figures.py en         영어 라벨

입력  D:/crossref/figs/fig1_year_by_snapshot.csv
      D:/crossref/figs/fig2_monthly_backfill.csv
      D:/crossref/figs/fig3_journal_backfill.csv
출력  같은 폴더에 PNG(300dpi)와 PDF

그림 2는 라이선스가 처음 확인된 스냅숏의 deposited 월로 집계한 데이터를 쓴다.
그림 3은 DOAJ 저널 단위로 묶은 데이터를 쓴다. 두 가지 형태를 모두 저장하므로
원고에 쓸 쪽을 고르면 된다.

색은 두 계열용으로 대비를 확인한 파랑(#2a78d6)과 주황(#eb6834)이다. 인쇄와 흑백
복사에서도 구분되도록 선 모양과 표식을 함께 달리 하였다.
"""
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator

ROOT = os.environ.get("CROSSREF_ROOT", "D:/crossref")
FIGS = os.environ.get("CROSSREF_FIGS", f"{ROOT}/figs")

LANG = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("FIG_LANG", "ko")).lower()

SERIES_1 = "#2a78d6"   # 파랑
SERIES_2 = "#eb6834"   # 주황
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#d9d8d4"

# ------------------------------------------------------------
# 글꼴
# ------------------------------------------------------------
def pick_font(candidates):
    from matplotlib import font_manager
    have = {f.name for f in font_manager.fontManager.ttflist}
    for c in candidates:
        if c in have:
            return c
    return None


if LANG == "ko":
    fam = pick_font(["Malgun Gothic", "NanumGothic", "AppleGothic", "Noto Sans CJK KR"])
    if fam is None:
        print("[경고] 한글 글꼴을 찾지 못했습니다. 라벨이 사각형으로 나올 수 있습니다.")
        print("       영어 라벨로 그리려면: python 06_figures.py en")
    else:
        plt.rcParams["font.family"] = fam
else:
    fam = pick_font(["Arial", "Helvetica", "DejaVu Sans"])
    if fam:
        plt.rcParams["font.family"] = fam

plt.rcParams.update({
    "axes.unicode_minus": False,
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "axes.edgecolor": INK_2,
    "axes.linewidth": 0.8,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "text.color": INK,
    "axes.labelcolor": INK,
    "figure.dpi": 100,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# ------------------------------------------------------------
# 라벨
# ------------------------------------------------------------
L = {
    "ko": {
        "f1_x": "출판연도", "f1_y": "CC 라이선스 기재율 (%)",
        "f1_s1": "2023년판", "f1_s2": "2026년판",
        "f2_x": "후속 등록 월", "f2_y": "보완 건수",
        "f3_x": "저널 단위 보완율", "f3_y": "저널 수 (로그 눈금)",
        "b_zero": "0%", "b_1": "0% 초과\n~5%", "b_2": "5~25%", "b_3": "25~50%",
        "b_4": "50~75%", "b_5": "75~95%", "b_6": "95% 초과",
        "t_zero": "0%", "t_last": "95~100%",
    },
    "en": {
        "f1_x": "Publication year", "f1_y": "Records with CC license metadata (%)",
        "f1_s1": "2023 file", "f1_s2": "2026 file",
        "f2_x": "Deposit month", "f2_y": "Added CC license metadata (records)",
        "f3_x": "Journal-level addition rate", "f3_y": "Journals (log scale)",
        "b_zero": "0%", "b_1": ">0-5%", "b_2": "5-25%", "b_3": "25-50%",
        "b_4": "50-75%", "b_5": "75-95%", "b_6": ">95%",
        "t_zero": "0%", "t_last": "95-100%",
    },
}[LANG if LANG in ("ko", "en") else "ko"]


def read(name):
    p = f"{FIGS}/{name}.csv"
    if not os.path.exists(p):
        print(f"[중단] 입력 파일이 없습니다: {p}")
        print("       먼저 05_tables.py를 실행하십시오.")
        sys.exit(1)
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def tidy(ax):
    """격자와 축을 뒤로 물린다."""
    ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def save(fig, name):
    for ext in ("png", "pdf"):
        p = f"{FIGS}/{name}.{ext}"
        fig.savefig(p)
        print("  저장:", p)
    plt.close(fig)


# ------------------------------------------------------------
# 그림 1. 출판연도별 기재율 (2023년판 대 2026년판)
# ------------------------------------------------------------
rows = read("fig1_year_by_snapshot")
yr = [int(r["출판연도"]) for r in rows]
v23 = [float(r["y2023"]) for r in rows]
v26 = [float(r["y2026"]) for r in rows]

fig, ax = plt.subplots(figsize=(6.5, 3.6))
tidy(ax)
ax.plot(yr, v23, color=SERIES_1, linewidth=2, linestyle="-",
        marker="o", markersize=4, label=L["f1_s1"], zorder=3)
ax.plot(yr, v26, color=SERIES_2, linewidth=2, linestyle="--",
        marker="s", markersize=4, label=L["f1_s2"], zorder=3)
ax.set_xlabel(L["f1_x"])
ax.set_ylabel(L["f1_y"])
ax.set_ylim(0, 100)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
ax.set_xticks([y for y in yr if y % 2 == 1])
# 계열이 둘이므로 범례를 두고, 마지막 점에 직접 라벨도 붙인다.
ax.legend(frameon=False, loc="lower right")
ax.set_xlim(min(yr) - 0.6, max(yr) + 1.8)
for v, col, dy in ((v26, SERIES_2, 5), (v23, SERIES_1, -10)):
    ax.annotate(f"{v[-1]:.1f}", (yr[-1], v[-1]), textcoords="offset points",
                xytext=(7, dy), color=col, fontsize=9)
save(fig, f"fig1_coverage_by_year_{LANG}")

# ------------------------------------------------------------
# 그림 2. 보완 레코드의 후속 등록 월 분포
# ------------------------------------------------------------
rows = read("fig2_monthly_backfill")
months = [r["등록월"] for r in rows]
cnt = [int(r["보완건수"]) for r in rows]

fig, ax = plt.subplots(figsize=(6.5, 3.4))
tidy(ax)
ax.bar(range(len(months)), cnt, color=SERIES_1, width=0.78, zorder=3)
ax.set_xlabel(L["f2_x"])
ax.set_ylabel(L["f2_y"])
ax.set_xticks(range(len(months)))
ax.set_xticklabels(months, rotation=90)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
# 상위 3개월만 직접 라벨 (모든 막대에 숫자를 붙이지 않는다)
for i in sorted(range(len(cnt)), key=lambda k: cnt[k], reverse=True)[:3]:
    ax.annotate(f"{cnt[i]:,}", (i, cnt[i]), ha="center", va="bottom",
                textcoords="offset points", xytext=(0, 2), fontsize=8, color=INK_2)
save(fig, f"fig2_deposit_month_{LANG}")

# ------------------------------------------------------------
# 그림 3. 저널 단위 보완율 분포 (두 형태)
# ------------------------------------------------------------
rows = read("fig3_journal_backfill")
rate = [float(r["보완율"]) for r in rows if r["보완율"] not in ("", None)]

# (가) 구간 막대 — 표 6과 같은 구간에 0% 초과 구간을 더 나눈 형태
edges = [(0, 0), (0, 5), (5, 25), (25, 50), (50, 75), (75, 95), (95, 100)]
labels = [L["b_zero"], L["b_1"], L["b_2"], L["b_3"], L["b_4"], L["b_5"], L["b_6"]]
counts = []
for lo, hi in edges:
    if lo == 0 and hi == 0:
        counts.append(sum(1 for v in rate if v == 0))
    else:
        counts.append(sum(1 for v in rate if lo < v <= hi))

fig, ax = plt.subplots(figsize=(6.0, 3.4))
tidy(ax)
ax.bar(range(len(counts)), counts, color=SERIES_1, width=0.72, zorder=3)
ax.set_yscale("log")
ax.set_xlabel(L["f3_x"])
ax.set_ylabel(L["f3_y"])
ax.set_xticks(range(len(labels)))
ax.set_xticklabels(labels)
ax.yaxis.set_major_locator(LogLocator(base=10))
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
# 로그 눈금에서는 막대 길이를 눈으로 비교하기 어려우므로 값을 모두 적는다
for i, c in enumerate(counts):
    if c > 0:
        ax.annotate(f"{c:,}", (i, c), ha="center", va="bottom",
                    textcoords="offset points", xytext=(0, 2), fontsize=8, color=INK_2)
save(fig, f"fig3_addition_rate_bins_{LANG}")

# (나) 20구간 히스토그램
fig, ax = plt.subplots(figsize=(6.0, 3.4))
tidy(ax)
ax.hist(rate, bins=[i * 5 for i in range(21)], color=SERIES_1,
        edgecolor="white", linewidth=0.5, zorder=3)
ax.set_yscale("log")
ax.set_xlabel(L["f3_x"] + " (%)")
ax.set_ylabel(L["f3_y"])
ax.set_xlim(0, 100)
ax.set_xticks([0, 20, 40, 60, 80, 100])
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
save(fig, f"fig3_addition_rate_hist_{LANG}")

print(f"\n완료. 저널 {len(rate):,}종, 보완 월 {len(months)}개월, 출판연도 {len(yr)}개.")
print("그림 3은 구간 막대(bins)와 히스토그램(hist) 두 형태를 저장하였다.")
