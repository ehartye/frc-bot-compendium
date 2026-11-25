"""Find strong robots that a championship-only ranking misses.

Usage: python tools/roster/season.py CACHE [--write]

Reads every official event's match scores from public Blue Alliance event pages (cached in CACHE as rows, one request every
1.2 s), then:
1. OPR and its standard error from each championship division's qualification matches.
2. A season rating: each robot's share of its alliance's score, updated match by match over all earlier qualification matches.
3. A blended rating for championship robots: the season rating predicts championship OPR, and the two are averaged by how
   uncertain each is.
Added robots are those in the blended top 20 but not the OPR top 20, plus those in the season's top 20 that did not play in a
championship division. The ratings see scoring only. --write saves data/added.json.
"""
import html
import json
import math
import random
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

YEARS = [2022, 2023, 2024, 2025, 2026]
NAMES = {"arc": "Archimedes", "cur": "Curie", "dal": "Daly", "gal": "Galileo", "hop": "Hopper", "carv": "Carver", "roe": "Roebling",
         "tur": "Turing", "joh": "Johnson", "mil": "Milstein", "new": "Newton"}
DIVS = {2022: ["carv", "gal", "hop", "new", "roe", "tur"]}  # six divisions that year; eight since
TOP = 20


def divisions(year):
    return DIVS.get(year, ["arc", "cur", "dal", "gal", "hop", "joh", "mil", "new"])


def get(url):
    for k in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
        except OSError as e:
            if "404" in str(e):
                return ""
            time.sleep(20 * (k + 1))
    raise SystemExit(f"could not read {url}")


def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def fetch(year, cache):
    """Events of the official weeks, with every played match as [key, red teams, red score, blue teams, blue score]."""
    done = cache / f"{year}-complete"
    if not done.exists():
        keys = {}
        for part in re.split(r"<h2[^>]*>", get(f"https://www.thebluealliance.com/events/{year}"))[1:]:
            head = strip(part.split("</h2>")[0])
            if not re.search(r"preseason|offseason", head, re.I):
                for k, n in re.findall(rf'/event/({year}[a-z0-9]+)" title="([^"]*)"', part):
                    keys.setdefault(k, (head, html.unescape(n)))
        for k, (head, name) in keys.items():
            f = cache / f"{k}.json"
            if f.exists():
                continue
            rows = []
            for block in re.finditer(r'<tr class="visible-lg">(.*?)</tr>', get(f"https://www.thebluealliance.com/event/{k}"), re.S):
                b = block[1]
                m = re.search(rf"/match/{k}_(\w+?)\"", b)
                red, blue = (re.findall(rf'<td[^>]*class="{c}[^"]*">.*?/team/(\w+)/', b, re.S) for c in ("red", "blue"))
                rs, bs = (re.search(rf'class="{c}Score[^"]*"[^>]*>(.*?)</td>', b, re.S) for c in ("red", "blue"))
                if m and len(red) >= 3 and len(blue) >= 3 and rs and bs:
                    rn, bn = re.findall(r"\d+", strip(rs[1])), re.findall(r"\d+", strip(bs[1]))
                    if rn and bn:
                        rows.append([m[1], red[:3], int(rn[-1]), blue[:3], int(bn[-1])])
            f.write_text(json.dumps({"key": k, "name": name, "week": head, "rows": rows}), encoding="utf-8")
            time.sleep(1.2)
        done.write_text("")
    evs = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(cache.glob(f"{year}*.json"))]
    return [e for e in evs if e["rows"]]


def week(e):
    m = re.search(r"Week (\d+)", e["week"])
    return int(m[1]) if m else 9 if re.search("champ", e["week"], re.I) else 8


def quals(e):
    return sorted((m for m in e["rows"] if re.fullmatch(r"qm\d+", m[0])), key=lambda m: int(m[0][2:]))


def inverse(a):
    n = len(a)
    m = [r[:] + [float(i == j) for j in range(n)] for i, r in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        d = m[c][c]
        m[c] = [x / d for x in m[c]]
        for r in range(n):
            if r != c and m[r][c]:
                f = m[r][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [r[n:] for r in m]


def opr(e):
    """Least-squares share of the alliance score for each team, with its standard error."""
    rows = [x for m in quals(e) for x in ((m[1], m[2]), (m[3], m[4]))]
    teams = sorted({t for r, _ in rows for t in r})
    ix, n = {t: i for i, t in enumerate(teams)}, len(teams)
    ata, atb = [[0.0] * n for _ in teams], [0.0] * n
    for r, s in rows:
        for t in r:
            atb[ix[t]] += s
            for u in r:
                ata[ix[t]][ix[u]] += 1
    inv = inverse(ata)
    x = [sum(a * b for a, b in zip(r, atb)) for r in inv]
    sig = math.sqrt(sum((s - sum(x[ix[t]] for t in r)) ** 2 for r, s in rows) / (len(rows) - n))
    return {t: (x[i], sig * math.sqrt(inv[i][i])) for t, i in ix.items()}


def rate(events, r, cnt):
    for e in events:
        for m in quals(e):
            red, blue = sum(r[t] for t in m[1]), sum(r[t] for t in m[3])
            for ts, p, s in ((m[1], red, m[2]), (m[3], blue, m[4])):
                for t in ts:
                    c = cnt[t]
                    r[t] += (0.5 if c <= 6 else 0.5 - (c - 6) / 30 if c <= 12 else 0.3) * (s - p) / 3
                    cnt[t] += 1


def blend(pool, before):
    xs, ys = [before[t] for t in pool], [pool[t][0] for t in pool]
    n, mx, my = len(xs), sum(xs) / len(xs), sum(ys) / len(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    res2 = sum((y - my - b * (x - mx)) ** 2 for x, y in zip(xs, ys)) / n
    tau2 = max(1e-6, res2 - sum(se ** 2 for _, se in pool.values()) / n)  # real spread around the season's prediction
    out = {}
    for t, (o, se) in pool.items():
        p = my + b * (before[t] - mx)
        out[t] = p + tau2 / (tau2 + se ** 2) * (o - p)
    return out


def season(year, cache):
    evs = fetch(year, cache)
    ch = {f"{year}{d}": d for d in divisions(year)}
    earlier = sorted((e for e in evs if e["key"] not in ch and not e["key"].startswith(f"{year}cmptx")), key=lambda e: (week(e), e["key"]))
    champ = [e for e in evs if e["key"] in ch]
    first = [s for e in earlier if week(e) == 1 for m in quals(e) for s in (m[2], m[4])]
    start = sum(first) / len(first) / 3
    r, cnt = defaultdict(lambda: start), defaultdict(int)
    rate(earlier, r, cnt)
    before = defaultdict(lambda: start, r)
    rate(champ, r, cnt)
    pool, div = {}, {}
    for e in champ:
        o = opr(e)
        pool |= o
        div |= {t: NAMES[ch[e["key"]]] for t in o}
    bl = blend(pool, before)
    by_opr = sorted(pool, key=lambda t: -pool[t][0])
    by_blend = sorted(bl, key=lambda t: -bl[t])
    by_season = sorted((t for t in r if cnt[t] >= 8), key=lambda t: -r[t])
    rank = lambda order, t: order.index(t) + 1
    added = [{"season": year, "team": t, "why": "blended", "blended_rank": rank(by_blend, t), "season_rank": rank(by_season, t),
              "opr_rank": rank(by_opr, t), "division": div[t], "division_opr": round(pool[t][0], 2)}
             for t in by_blend[:TOP] if t not in by_opr[:TOP]]
    added += [{"season": year, "team": t, "why": "season", "blended_rank": None, "season_rank": rank(by_season, t), "opr_rank": None,
               "division": None, "division_opr": None} for t in by_season[:TOP] if t not in pool]
    play = [m for e in evs if e["key"] in ch or e["key"] == f"{year}cmptx" for m in e["rows"]
            if not m[0].startswith("qm") and m[2] != m[4] and all(t in pool for t in m[1] + m[3])]

    def right(q):
        return [(sum(q[t] for t in m[1]) > sum(q[t] for t in m[3])) == (m[2] > m[4]) for m in play]

    print(f"{year}: {len(earlier)} events and {len(champ)} championship divisions, {len(by_season)} robots; OPR top {TOP} in blended top {TOP}: "
          f"{sum(t in by_blend[:TOP] for t in by_opr[:TOP])}; blended rank {TOP} is {100 * bl[by_blend[TOP - 1]] / bl[by_blend[0]]:.0f}% of rank 1")
    return added, right({t: pool[t][0] for t in pool}), right(bl)


def main():
    cache = Path(sys.argv[1])
    cache.mkdir(parents=True, exist_ok=True)
    added, by_o, by_b = [], [], []
    for y in YEARS:
        a, o, b = season(y, cache)
        added += a
        by_o += o
        by_b += b
    for x in added:
        print(x)
    random.seed(5)
    n, gain = len(by_o), [b - o for b, o in zip(by_b, by_o)]
    d = sorted(sum(random.choices(gain, k=n)) / n for _ in range(2000))
    print(f"held-out championship playoff matches: {n}; winner picked by OPR {100 * sum(by_o) / n:.1f}%, blended {100 * sum(by_b) / n:.1f}%; "
          f"difference {100 * sum(gain) / n:+.1f} points, 95% range {100 * d[50]:+.1f} to {100 * d[1950]:+.1f}")
    if "--write" in sys.argv:
        out = Path(__file__).resolve().parents[2] / "data/added.json"
        out.write_text(json.dumps(added, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
