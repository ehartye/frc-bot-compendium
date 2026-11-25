"""Check compendium records and render a robot's story.

Usage: python tools/compendium.py check
       python tools/compendium.py story 2023-254
       python tools/compendium.py find [--function F] [--season Y] [--piece P] [--serves O] [--text WORDS] [--limit N]
"""
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUNCTIONS = ["drive", "acquire", "retain", "transfer", "position", "deliver", "endgame", "sense", "structure"]
BASES = {"team", "observer", "record", "inference"}
ASSET_STATES = {"opened", "listed", "withheld"}
BEATS = {"bet": 35, "demand": 70, "auto": 60, "cycle": 60, "endgame": 60, "fallback": 60,
         "gave_up": 70, "changed": 70, "outcome": 50}
TITLES = {"bet": "The bet", "demand": "The demand", "auto": "Auto", "cycle": "Cycle", "endgame": "Endgame",
          "fallback": "Fallback", "gave_up": "What it gave up", "changed": "What changed", "outcome": "The outcome"}
MATCH = ("auto", "cycle", "endgame", "fallback")
PRIVATE = re.compile(r"\[\[|wiki/(?:sources|authored|concepts)|raw/clippings|(?<![A-Za-z])[A-Za-z]:\\\\|wiki-vault|\.wiki-\w+|[\w.+-]+@[\w-]+\.(?:com|org|net|edu|us)\b")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def seasons():
    return {s["year"]: s for s in map(load, sorted((ROOT / "data/seasons").glob("*.json")))}


def robots():
    return {p: load(p) for p in sorted((ROOT / "data/robots").glob("*/*.json"))}


def claims(rec):
    for beat, items in rec["story"].items():
        for c in items:
            yield f"story.{beat}", c
    for f in rec["functions"]:
        for c in f["facts"] + f.get("solves", []) + f.get("cost", []):
            yield f"functions.{f['name']}", c
    for d in rec["decisions"]:
        yield f"decisions.{d['choice'][:30]}", d


def check_robot(path, rec, all_seasons):
    errs = []
    say = lambda m: errs.append(f"{path.relative_to(ROOT).as_posix()}: {m}")
    if rec["id"] != f"{rec['season']}-{rec['team']}" or path.parent.name != str(rec["season"]) or path.stem != rec["team"]:
        say("id, season, team and path disagree")
    season = all_seasons.get(rec["season"])
    if not season:
        say(f"no season record for {rec['season']}")
        return errs
    objectives = {o["id"] for o in season["objectives"]}
    pieces = {x["id"] for x in season["pieces"]}
    ids = [e["id"] for e in examples(rec, season)]
    if len(ids) != len(set(ids)):
        say("two examples share an id")
    src = rec["sources"]
    for sid, s in src.items():
        if not all(s.get(k) for k in ("title", "url", "publisher", "read")) or not s["url"].startswith("https://"):
            say(f"source {sid} needs title, https url, publisher, read")
    used = set()
    for where, c in claims(rec):
        if c.get("basis") not in BASES:
            say(f"{where}: basis missing or unknown")
        if not c.get("src"):
            say(f"{where}: no sources")
        for sid in c.get("src", []):
            used.add(sid)
            if sid not in src:
                say(f"{where}: unknown source {sid}")
        if "value" in c and not c.get("unit"):
            say(f"{where}: value without unit")
    res = rec.get("results") or {}
    if not all(k in res for k in ("division", "division_opr", "opr_rank", "record", "src")):
        say("results incomplete")
    for sid in res.get("src", []):
        used.add(sid)
        if sid not in src:
            say(f"results cite unknown source {sid}")
    for beat, items in rec["story"].items():
        if beat not in BEATS:
            say(f"unknown beat {beat}")
            continue
        words = sum(len(c["text"].split()) for c in items)
        if words > BEATS[beat]:
            say(f"beat {beat} has {words} words, limit {BEATS[beat]}")
    for f in rec["functions"]:
        for x in f["does"]:
            if x not in FUNCTIONS:
                say(f"unknown function {x}")
        for o in f.get("serves", []):
            if o not in objectives:
                say(f"{f['name']} serves unknown objective {o}")
        for x in f.get("pieces", []):
            if x not in pieces:
                say(f"{f['name']} handles unknown piece {x}")
    for kind in ("cad", "graphics", "documents", "code"):
        for a in rec["assets"].get(kind, []):
            if a["state"] not in ASSET_STATES:
                say(f"asset state {a['state']}")
            if a["src"] not in src:
                say(f"asset cites unknown source {a['src']}")
            used.add(a["src"])
            if a.get("format") == "Fusion" and not re.search(r"a360\.co|autodesk360\.com", a.get("url", "")):
                say("Fusion format without an Autodesk link")
    if missing_searches(rec):
        say("beats without evidence but no searches listed")
    for sid in set(src) - used:
        say(f"source {sid} is never cited")
    if PRIVATE.search(json.dumps(rec, ensure_ascii=False)):
        say("contains a vault path, wikilink or machine path")
    return errs


def empty_beats(rec):
    return [b for b in BEATS if not rec["story"].get(b)]


def missing_searches(rec):
    return bool(empty_beats(rec)) and not rec.get("searched")


def cite(c):
    tag = {"team": "team says", "observer": "observer", "record": "record", "inference": "our inference"}[c["basis"]]
    return f" _({tag}; {', '.join(c['src'])})_"


def story(rec, season):
    out = [f"# {rec['season']} {season['name']}: {rec['team']} {rec['team_name']}" + (f" - {rec['robot_name']}" if rec.get("robot_name") else ""), ""]
    for b in BEATS:
        items = rec["story"].get(b)
        if b == "auto":
            out += (["## The match", ""] if any(rec["story"].get(m) for m in MATCH) else [])
        if not items:
            continue
        head = "###" if b in MATCH else "##"
        out += [f"{head} {TITLES[b]}", "", " ".join(c["text"] + cite(c) for c in items), ""]
    if rec["functions"]:
        out += ["## How it works", "", "| Function | Mechanism | Type | Facts |", "|---|---|---|---|"]
        for fn in FUNCTIONS:
            for f in rec["functions"]:
                if fn == f["does"][0]:
                    facts = "; ".join(c["text"] + (f" ({c['value']} {c['unit']})" if "value" in c else "") + cite(c) for c in f["facts"])
                    out.append(f"| {', '.join(f['does'])} | {f['name']} | {f['type']} | {facts} |")
        out.append("")
    if rec["decisions"]:
        out += ["## Decisions", ""]
        for d in rec["decisions"]:
            out.append(f"- **{d['choice']}** because {d['because']}" + (f", instead of {d['instead_of']}" if d.get("instead_of") else "")
                       + (f". Cost: {d['cost']}" if d.get("cost") else "") + cite(d))
        out.append("")
    rows = [(k, a) for k in ("cad", "graphics", "documents", "code") for a in rec["assets"].get(k, [])]
    if rows:
        out += ["## Where to find it", "", "| Kind | Format | Location | State | Source |", "|---|---|---|---|---|"]
        for k, a in rows:
            loc = f"[{a['what']}]({a['url']})" if a.get("url") else a["what"]
            out.append(f"| {k} | {a.get('format', 'not stated')} | {loc} | {a['state']} | {a['src']} |")
        out.append("")
    if empty_beats(rec):
        out += ["## What isn't public", "", "No source found for: " + ", ".join(TITLES[b].lower() for b in empty_beats(rec)) + ". Searched: " + "; ".join(rec["searched"]) + ".", ""]
    out += ["## Sources", ""] + [f"- {sid}: [{s['title']}]({s['url']}), {s['publisher']}, read {s['read']}" for sid, s in rec["sources"].items()]
    return "\n".join(out)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def examples(rec, season):
    """Every mechanism and decision in a robot record, as one retrievable design example."""
    piece = {x["id"]: x for x in season["pieces"]}
    outcome = [c["text"] for c in rec["story"].get("outcome", [])]
    study = [{"kind": k, **{x: a[x] for x in ("what", "format", "url", "state") if x in a}}
             for k in ("cad", "documents", "code", "graphics") for a in rec["assets"].get(k, [])]
    base = {"season": rec["season"], "game": season["name"], "team": rec["team"], "team_name": rec["team_name"],
            "robot": rec.get("robot_name"), "outcome": outcome, "study": study}
    for f in rec["functions"]:
        stated = [c for c in f.get("solves", []) + f["facts"] + f.get("cost", [])]
        yield {"id": f"{rec['id']}/{slug(f['name'])}", "kind": "mechanism", "name": f["name"], "type": f["type"], "functions": f["does"],
               "pieces": [piece[x] for x in f.get("pieces", []) if x in piece], "serves": f.get("serves", []),
               "solves": [c["text"] for c in f.get("solves", [])],
               "facts": [c["text"] + (f": {c['value']} {c['unit']}" if "value" in c else "") for c in f["facts"]],
               "cost": [c["text"] for c in f.get("cost", [])],
               "claims": [{"part": p, "text": c["text"] + (f": {c['value']} {c['unit']}" if "value" in c else ""), "basis": c["basis"],
                           "sources": [rec["sources"][s]["url"] for s in c["src"]]}
                          for p, cs in (("solves", f.get("solves", [])), ("fact", f["facts"]), ("cost", f.get("cost", []))) for c in cs],
               "basis": sorted({c["basis"] for c in stated}),
               "sources": sorted({rec["sources"][s]["url"] for c in stated for s in c["src"]}), **base}
    for d in rec["decisions"]:
        yield {"id": f"{rec['id']}/decision-{slug(d['choice'])}", "kind": "decision", "name": d["choice"], "functions": [], "pieces": [], "serves": [],
               "solves": [d["because"]], "instead_of": d.get("instead_of"), "cost": [d["cost"]] if d.get("cost") else [],
               "claims": [{"part": "decision", "text": d["choice"] + " because " + d["because"], "basis": d["basis"],
                           "sources": [rec["sources"][s]["url"] for s in d["src"]]}],
               "basis": [d["basis"]], "sources": sorted({rec["sources"][s]["url"] for s in d["src"]}), **base}


STOP = set("a an the of to and or in for without with while from at on by how it its is".split())


def stem(w):
    for s in ("ing", "ed", "es", "s", "e"):
        if w.endswith(s) and len(w) - len(s) >= 3:
            return w[: -len(s)]
    return w


def hit(w, text):
    return re.search(rf"\b{re.escape(stem(w))}(?:s|es|ed|ing|e|er|ers|ning|ming)?\b", text)


def texts(e):
    """What an example is about (name, type, problem) and everything else it says."""
    strong = " ".join([e["name"], e.get("type") or "", *e["solves"]]).lower()
    return strong, " ".join([*e.get("facts", []), *e["cost"], e.get("instead_of") or ""]).lower()


def find(args):
    opts = dict(zip(args[::2], args[1::2]))
    unknown = set(opts) - {"--function", "--season", "--piece", "--serves", "--text", "--limit"}
    if unknown or len(args) % 2 or opts.get("--function", FUNCTIONS[0]) not in FUNCTIONS:
        raise SystemExit(f"bad options {sorted(unknown) or args}; functions: {', '.join(FUNCTIONS)}")
    words = [w for w in dict.fromkeys(re.findall(r"[a-z0-9]+", opts.get("--text", "").lower())) if w not in STOP]
    phrase = " ".join(opts.get("--text", "").lower().split())
    ss, pool = seasons(), []
    for rec in robots().values():
        pool += examples(rec, ss[rec["season"]])
    docs = [(e, *texts(e)) for e in pool]
    idf = {w: math.log(1 + len(docs) / (1 + sum(bool(hit(w, strong) or hit(w, weak)) for _, strong, weak in docs))) for w in words}
    hits = []
    for e, strong, weak in docs:
        if "--function" in opts and opts["--function"] not in e["functions"]:
            continue
        if "--season" in opts and str(e["season"]) != opts["--season"]:
            continue
        if "--piece" in opts and not any(opts["--piece"] in (x["id"], *x["shape"].split()) for x in e["pieces"]):
            continue
        if "--serves" in opts and opts["--serves"] not in e["serves"]:
            continue
        found = [w for w in words if hit(w, strong) or hit(w, weak)]
        if words and not found:
            continue
        name = f"{e['name']} {e.get('type') or ''}".lower()
        score = sum(idf[w] * (4 if hit(w, name) else 3 if hit(w, strong) else 1) for w in found) * (len(found) / len(words) if words else 1)
        if len(words) > 1 and phrase in f"{strong} {weak}":
            score *= 3
        hits.append((score, "team" in e["basis"], bool(e["cost"]), e))
    hits.sort(key=lambda h: h[:3], reverse=True)
    for *_, e in hits[: int(opts.get("--limit", 5))]:
        print(json.dumps(e, ensure_ascii=False))
    if not hits:
        print(json.dumps({"none": "no example matches", "records": len(robots())}))


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("check", "story", "find"):
        raise SystemExit(__doc__)
    ss = seasons()
    if sys.argv[1] == "check":
        errs = []
        for p, rec in robots().items():
            errs += check_robot(p, rec, ss)
            n = len(BEATS) - len(empty_beats(rec))
            print(f"{rec['id']}: {n}/{len(BEATS)} beats, {len(rec['functions'])} mechanisms, {len(rec['decisions'])} decisions")
        print("\n".join(errs) or "all records pass")
        raise SystemExit(1 if errs else 0)
    if sys.argv[1] == "find":
        return find(sys.argv[2:])
    for rec in robots().values():
        if rec["id"] == sys.argv[2]:
            print(story(rec, ss[rec["season"]]))
            return
    raise SystemExit(f"no record {sys.argv[2]}")


if __name__ == "__main__":
    main()
