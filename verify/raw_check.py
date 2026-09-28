import gzip, json, os, sys, tarfile, time, csv
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

TAR = r"D:\crossref\March_2026_Public_Data_File_from_Crossref.tar"
OUT = r"D:\crossref\raw_check_2026.csv"
TARGETS = [b"10.22501/ruu.", b"10.13165/sd-"]   # RUUKKU, 2783-5502 저널

def scan(name, raw):
    data = gzip.decompress(raw)
    if not any(t in data for t in TARGETS):
        return []
    hits = []
    lines = data.splitlines() if name.endswith(".jsonl.gz") else None
    recs = []
    if lines is not None:
        for ln in lines:
            if any(t in ln for t in TARGETS):
                recs.append(json.loads(ln))
    else:
        recs = [r for r in json.loads(data).get("items", []) if any(t.decode() in (r.get("DOI") or "") for t in TARGETS)]
    for r in recs:
        doi = (r.get("DOI") or "").lower()
        if not any(t.decode() in doi for t in TARGETS): continue
        dp = lambda k: str((r.get(k) or {}).get("date-parts"))
        hits.append([doi, r.get("type"), ";".join(r.get("ISSN") or []),
                     json.dumps(r.get("issn-type") or []), ";".join(r.get("container-title") or []),
                     dp("issued"), dp("published"), r.get("member"),
                     str((r.get("created") or {}).get("date-time"))[:10]])
    return hits

def members(p):
    with tarfile.open(p, mode="r|") as tar:
        for m in tar:
            if m.isfile() and (m.name.endswith(".json.gz") or m.name.endswith(".jsonl.gz")):
                yield m.name, tar.extractfile(m).read(), m.offset_data + m.size

if __name__ == "__main__":
    total = os.path.getsize(TAR); t0 = time.time(); last = t0; found = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        pend = set()
        for name, raw, off in members(TAR):
            pend.add(ex.submit(scan, name, raw))
            if len(pend) >= 12:
                done, pend = wait(pend, return_when=FIRST_COMPLETED)
                for f in done: found += f.result()
            if time.time() - last > 60:
                last = time.time(); pct = off/total
                print(f"진행 {pct:.1%} | 찾은 레코드 {len(found)} | 남은 시간 약 {(time.time()-t0)/pct*(1-pct)/60:.0f}분", flush=True)
        for f in pend: found += f.result()
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["doi","type","ISSN","issn_type","container","issued","published","member","created"])
        w.writerows(found)
    print(f"\n완료: {len(found)}건 저장 -> {OUT}")
    import collections
    for pre in ["10.22501/ruu.", "10.13165/sd-"]:
        rs = [r for r in found if r[0].startswith(pre)]
        c = collections.Counter(("ISSN 있음" if r[2] else "ISSN 없음", r[1]) for r in rs)
        print(f"\n[{pre}] 총 {len(rs)}건")
        for k, v in c.most_common(): print(f"   {k}: {v}")
        for r in rs[:3]: print("   예:", r[0], "| type:", r[1], "| ISSN:", r[2] or "(없음)", "| container:", r[4])
