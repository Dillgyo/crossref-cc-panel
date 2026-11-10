"""그림 3: 보완 상위 다섯 출판사와 그 밖의 출판사의 deposited 월 분포 (소형 다중 그림).
입력: figs/top5_by_month.csv (verify/calc_all.py 25번), figs/fig2_monthly_backfill.csv (05_tables.py)
실행: py verify\\fig3_by_publisher.py [ko|en]
"""
import csv, collections, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import os
ROOT = os.environ.get('CROSSREF_ROOT', 'D:/crossref')
lang = sys.argv[1] if len(sys.argv) > 1 else 'ko'
plt.rcParams['font.family'] = ['Noto Sans CJK KR', 'Malgun Gothic']
plt.rcParams['axes.unicode_minus'] = False
TOP5 = ROOT + '/figs/top5_by_month.csv'
ALL = ROOT + '/figs/fig2_monthly_backfill.csv'
months = [r[0] for r in list(csv.reader(open(ALL, encoding='utf-8-sig')))[1:]]
alln = {r[0]: int(r[1]) for r in list(csv.reader(open(ALL, encoding='utf-8-sig')))[1:]}
rows = list(csv.DictReader(open(TOP5, encoding='utf-8-sig')))
order = [('2373', 'Editorial CSIC'), ('317', 'AIP Publishing'), ('297', 'Springer'),
         ('276', 'Wolters Kluwer'), ('2399', 'OpenEdition')]
per = {m: collections.Counter() for m, _ in order}
tot = collections.Counter()
for r in rows:
    tot[r['member']] += int(r['n'])
    per[r['member']][r['ym']] += int(r['n'])
rest = {ym: alln[ym] - sum(per[m][ym] for m, _ in order) for ym in months}
rest_total = 167779 - sum(tot.values())
T = {'ko': dict(rest='그 밖의 출판사', n='보완 {:,}건', peak='최다 {} · {:.1f}%',
                x='CC가 처음 관찰된 연도판의 deposited 월', y='보완 건수'),
     'en': dict(rest='All other publishers', n='{:,} filled records', peak='peak {} · {:.1f}%',
                x='Deposited month of the first snapshot in which CC was observed', y='Filled records')}[lang]
panels = [(name, [per[m][ym] for ym in months], tot[m]) for m, name in order]
panels.append((T['rest'], [rest[ym] for ym in months], rest_total))
BLUE, INK, INK2, GRID = '#2a78d6', '#0b0b0b', '#52514e', '#dddcd8'
fig, axes = plt.subplots(len(panels), 1, figsize=(7.2, 9.0), sharex=True)
x = range(len(months))
for ax, (name, vals, n) in zip(axes, panels):
    ax.bar(x, vals, width=0.78, color=BLUE, linewidth=0)
    pk = max(range(len(vals)), key=lambda i: vals[i])
    head = f"{name}   " + T['n'].format(n)
    if name != T['rest']:
        head += "   " + T['peak'].format(months[pk], 100 * vals[pk] / n)
    ax.set_title(head, loc='left', fontsize=9.5, color=INK, pad=4)
    ax.spines[['top', 'right']].set_visible(False)
    ax.spines[['left', 'bottom']].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=8, length=2)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6); ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f'{int(v):,}'))
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3, integer=True))
ticks = [i for i, m in enumerate(months) if m[5:] in ('01', '04', '07', '10')]
axes[-1].set_xticks(ticks); axes[-1].set_xticklabels([months[i] for i in ticks], rotation=90, fontsize=8)
axes[-1].set_xlabel(T['x'], fontsize=9.5, color=INK)
fig.supylabel(T['y'], fontsize=9.5, color=INK)
fig.tight_layout(h_pad=0.8)
fig.savefig(ROOT + f'/figs/fig3_deposit_month_by_publisher_{lang}.png', dpi=300)
fig.savefig(ROOT + f'/figs/fig3_deposit_month_by_publisher_{lang}.pdf')
print('rest_total', rest_total, 'rest_in_window', sum(rest.values()), 'pre_window', 167779 - sum(alln.values()))
