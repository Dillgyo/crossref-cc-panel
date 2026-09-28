import os
﻿import json, urllib.parse, urllib.request
MAIL = os.environ.get("CROSSREF_MAILTO", "")   # 바꾸세요
for doi in ["10.22501/ruu.889932", "10.22501/ruu.240675"]:
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}?mailto={MAIL}"
    req = urllib.request.Request(url, headers={"User-Agent": f"check (mailto:{MAIL})"})
    with urllib.request.urlopen(req, timeout=30) as r:
        m = json.load(r)["message"]
    print(doi)
    print("  type:", m.get("type"))
    print("  ISSN:", m.get("ISSN"))
    print("  issn-type:", m.get("issn-type"))
    print("  issued:", m.get("issued"))
    print("  published:", m.get("published"))
    print("  container:", m.get("container-title"))
    print("  member:", m.get("member"), "| created:", str(m.get("created",{}).get("date-time"))[:10])
