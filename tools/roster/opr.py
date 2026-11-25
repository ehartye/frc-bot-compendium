"""Parse TBA championship division pages: OPR table, qual matches (recompute OPR as a cross-check)."""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
DIVS = ["arc", "cur", "dal", "gal", "hop", "joh", "mil", "new"]
YEARS = [2023, 2024, 2025, 2026]


def fetch(key):
    f = OUT / f"{key}.html"
    if not f.exists() or f.stat().st_size < 200000:
        req = urllib.request.Request(
            f"https://www.thebluealliance.com/event/{key}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            f.write_bytes(r.read())
        time.sleep(1)
    return f.read_text(encoding="utf-8", errors="replace")


def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


if __name__ == "__main__":
    sample = fetch("2026dal")
    i = sample.find("coprSelector")
    j = sample.find("<table", i)
    print("around OPR:", re.sub(r"\s+", " ", sample[i:i + 300]))
    for m in re.finditer(r"OPR", sample):
        ctx = re.sub(r"\s+", " ", sample[max(0, m.start() - 80): m.start() + 160])
        print("--", ctx)
    print("TABLE:", re.sub(r"\s+", " ", sample[j:j + 1800]))
    k = sample.find("/match/2026dal_qm1\"")
    print("MATCH:", re.sub(r"\s+", " ", sample[k - 600:k + 2600]))
