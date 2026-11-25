"""Build the top-20-by-championship-division-OPR rosters from TBA pages, with a recomputed cross-check."""
import csv
import io
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import importlib.util

spec = importlib.util.spec_from_file_location("opr", Path(__file__).parent / "opr.py")
opr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(opr)

DATA = Path(sys.argv[1])
NAMES = {"arc": "Archimedes", "cur": "Curie", "dal": "Daly", "gal": "Galileo",
         "hop": "Hopper", "carv": "Carver", "roe": "Roebling", "tur": "Turing", "joh": "Johnson", "mil": "Milstein", "new": "Newton"}


def solve(rows, teams):
    """Least squares by normal equations with Gaussian elimination (stdlib only)."""
    n = len(teams)
    ix = {t: i for i, t in enumerate(teams)}
    a = [[0.0] * (n + 1) for _ in range(n)]
    for ts, score in rows:
        for t in ts:
            for u in ts:
                a[ix[t]][ix[u]] += 1
            a[ix[t]][n] += score
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(a[r][c]))
        if abs(a[p][c]) < 1e-9:
            return None
        a[c], a[p] = a[p], a[c]
        for r in range(n):
            if r != c and a[r][c]:
                f = a[r][c] / a[c][c]
                for k in range(c, n + 1):
                    a[r][k] -= f * a[c][k]
    return {t: a[ix[t]][n] / a[ix[t]][ix[t]] for t in teams}


def alliances(page):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", page)
    txt = opr.strip(t)
    return txt


cad = {}
sheet = DATA.parent / "sheet.csv"  # optional: community CAD index
with open(sheet, encoding="utf-8-sig", newline="") if sheet.exists() else io.StringIO("Team #,Year\n") as fh:
    for r in csv.DictReader(fh):
        cad.setdefault((r["Team #"].strip(), r["Year"].strip()), []).append(
            {k: r[k] for k in ("Description", "Format", "Link")})

result = {}
for y in opr.YEARS:
    pool, check = [], {}
    for d in opr.divisions(y):
        key = f"{y}{d}"
        page = opr.fetch(key)
        m = re.search(r"const coprs = JSON\.parse\('(.*?)'\)", page, re.S)
        data = json.loads(m.group(1).encode().decode("unicode_escape") if "\\u" in m.group(1) else m.group(1))
        names = {}
        for tm in re.finditer(r'href="/team/(\d+)/%d"[^>]*>(.*?)</a>' % y, page, re.S):
            pass
        for team, val in data["OPR"]:
            pool.append((float(val), team, key))
        # names: team list entries carry number and name text
        for tm in re.finditer(r'<a href="/team/(\d+)/%d">\s*\1\s*<' % y, page):
            names.setdefault(tm.group(1), None)
        # quals
        rows, teams = [], set()
        for block in re.finditer(r'<tr class="visible-lg">(.*?)</tr>', page, re.S):
            b = block.group(1)
            if f"/match/{key}_qm" not in b:
                continue
            red = re.findall(r'<td[^>]*class="red[^"]*">.*?/team/(\d+)/', b, re.S)
            blue = re.findall(r'<td[^>]*class="blue[^"]*">.*?/team/(\d+)/', b, re.S)
            rs = re.search(r'class="redScore[^"]*"[^>]*>(.*?)</td>', b, re.S)
            bs = re.search(r'class="blueScore[^"]*"[^>]*>(.*?)</td>', b, re.S)
            if len(red) == 3 and len(blue) == 3 and rs and bs:
                rn = re.findall(r"\d+", opr.strip(rs.group(1)))
                bn = re.findall(r"\d+", opr.strip(bs.group(1)))
                if rn and bn:
                    rows.append((red, int(rn[-1])))
                    rows.append((blue, int(bn[-1])))
                    teams.update(red + blue)
        mine = solve(rows, sorted(teams)) if rows else None
        if mine:
            diff = [abs(mine[t] - v) for t, v in ((t, float(v)) for t, v in data["OPR"]) if t in mine]
            check[key] = (len(rows), len(teams), round(max(diff), 2))
        else:
            check[key] = (len(rows), len(teams), None)
    pool.sort(reverse=True)
    print(y, "pooled", len(pool), "| cross-check (alliance rows, teams, max abs diff):", check)
    top = []
    for i, (v, t, k) in enumerate(pool[:25], 1):
        top.append({"rank": i, "team": t, "opr": round(v, 2), "division": NAMES[k[4:]], "event": k,
                    "cad": cad.get((t, str(y)), [])})
        if i <= 22:
            print(f"  {i:2d} {t:>5} {v:7.2f} {NAMES[k[4:]]:<11} cad={len(cad.get((t, str(y)), []))}")
    result[y] = top

teams20 = {}
for y, top in result.items():
    for r in top[:20]:
        teams20.setdefault(r["team"], []).append(y)
print("distinct teams:", len(teams20), "bots:", sum(len(v) for v in teams20.values()))
for t, ys in sorted(teams20.items(), key=lambda kv: (-len(kv[1]), int(kv[0]))):
    print(t, ys)
(DATA.parent / "roster.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
