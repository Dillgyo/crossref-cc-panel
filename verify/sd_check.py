import csv
sus = set()
with open(r"D:\crossref\missing_dois.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r.get("issn") == "2783-5502": sus.add(r["doi"].lower())
print("2783-5502로 조회된 DOI:", len(sus))
from collections import Counter
c = Counter(); rows = []
with open(r"D:\crossref\raw_check_2026.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["doi"] in sus:
            k = (r["type"], r["ISSN"], r["container"]); c[k] += 1; rows.append(r)
print("원본 파일에서 찾은 수:", len(rows))
for k, v in c.most_common(): print(f"  {v}건 | type={k[0]} | ISSN={k[1]} | {k[2]}")
missing = sus - {r["doi"] for r in rows}
print("원본에서도 못 찾은 DOI:", len(missing), list(missing)[:5])
