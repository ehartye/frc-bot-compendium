"""Build the static site from data/ into dist/. Standard library only.

Usage: python tools/build_site.py
"""
import html
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from compendium import BEATS, FUNCTIONS, MATCH, PRIVATE, ROOT, TITLES, empty_beats, examples, robots, seasons, slug

DIST = ROOT / "dist"
E = html.escape
SS = seasons()
RS = {r["id"]: r for r in robots().values()}
TEAMS = defaultdict(list)
for r in RS.values():
    TEAMS[r["team"]].append(r)
QUESTION = {"drive": "How does the robot move?", "acquire": "How does it get a piece, and from where?", "retain": "How does it hold a piece securely?",
            "transfer": "How does a piece move or turn between acquire and deliver?", "position": "How does it reach or aim?", "deliver": "How does the piece leave and score?",
            "endgame": "How does it earn endgame points?", "sense": "How does it know where it and the piece are, and what is automated?",
            "structure": "What packaging, frame or weight choice makes the rest possible?"}
SAY = {"team": "team says", "observer": "observer says", "record": "on record", "inference": "our reading"}
KINDS = {"cad": "CAD", "documents": "Binders, notebooks and documents", "code": "Code", "graphics": "Video and photo pages"}
ART = {  # each season's game piece, drawn
    2023: '<svg viewBox="0 0 100 100" aria-hidden="true"><path d="M33 12h14l17 62H16z" fill="#f2c230"/><path d="M10 74h60v10H10z" fill="#f2c230"/><rect x="60" y="52" width="34" height="32" rx="9" fill="#6a3fa0"/></svg>',
    2024: '<svg viewBox="0 0 100 100" aria-hidden="true"><ellipse cx="50" cy="52" rx="40" ry="26" fill="none" stroke="#f0691c" stroke-width="15"/></svg>',
    2025: '<svg viewBox="0 0 100 100" aria-hidden="true"><circle cx="66" cy="60" r="28" fill="#00a08f"/><rect x="8" y="14" width="64" height="26" rx="4" fill="#fdfdfb" stroke="#14181c" stroke-width="2" transform="rotate(-14 40 27)"/><ellipse cx="13" cy="35" rx="6" ry="13" fill="#aeb3b6" stroke="#14181c" stroke-width="2" transform="rotate(-14 13 35)"/></svg>',
    2026: '<svg viewBox="0 0 100 100" aria-hidden="true"><g fill="#f4d03a" stroke="#8a6a00" stroke-width="1.5"><circle cx="30" cy="66" r="19"/><circle cx="68" cy="68" r="19"/><circle cx="50" cy="35" r="19"/></g></svg>',
}


def page(path, title, body, depth, season=None, desc=""):
    b = "../" * depth
    nav = "".join(f'<a href="{b}{y}/">{y}</a>' for y in SS)
    out = f"""<!doctype html>
<html lang="en" data-alliance="red"{f' data-season="{season}"' if season else ''}>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="stylesheet" href="{b}site.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect y='8' width='32' height='16' rx='5' fill='%23c3142d'/%3E%3C/svg%3E">
<script>try{{document.documentElement.dataset.alliance=localStorage.getItem("alliance")||"red"}}catch{{}}</script></head>
<body><a class="skip" href="#main">Skip to content</a>
<div class="wrap"><div class="bar"><a class="home" href="{b}">FRC bot compendium</a><nav aria-label="Main">{nav}<a href="{b}functions/">By job</a><a href="{b}teams/">Teams</a><a href="{b}about/">About</a></nav><button class="flip" type="button">Flip bumpers to blue</button></div></div>
<main id="main" class="wrap">
{body}
</main>
<footer><div class="wrap"><p>Robots belong to the teams that built them. Pictures load from the sites where teams published them, with a link back; nothing is copied here. This site is not affiliated with or endorsed by FIRST. An example is something to study: check it against your own season's rules before you use the idea.</p><p>For programs: <a href="{b}data/examples.json">examples.json</a>, <a href="{b}data/index.json">index.json</a>, <a href="{b}llms.txt">llms.txt</a>.</p></div></footer>
<script type="module" src="{b}site.js"></script></body></html>
"""
    f = DIST / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(out, encoding="utf-8", newline="\n")


UNSIGNED = re.compile(r"^(?:An?|One|The)? ?(?:unsigned )?(?:thread )?(?:reply|replies|post)(?: that)? reads? as the team's (?:says|say|said)(?: that)?,? ", re.I)


def say(c):
    t = UNSIGNED.sub("", c["text"])
    return t[0].upper() + t[1:] if t != c["text"] else t


def cite(c):
    refs = "".join(f'<sup><a href="#src-{s}">[{s[1:]}]</a></sup>' for s in c["src"])
    if UNSIGNED.match(c.get("text", "")):
        return f'{refs} <span class="tag observer">unsigned reply, likely the team</span>'
    return refs if c["basis"] == "team" else f'{refs} <span class="tag {c["basis"]}">{SAY[c["basis"]]}</span>'


def para(items):
    return "".join(f"<p>{E(say(c))}{cite(c)}</p>" for c in items)


def fact(c):
    return E(say(c)) + (f": <strong>{c['value']} {E(c['unit'])}</strong>" if "value" in c else "") + cite(c)


def pictures(rec):
    return [g for g in rec["assets"].get("graphics", []) if g.get("img")]


def hero(rec):
    ps = pictures(rec)
    return next((p for p in ps if p.get("hero")), None) or next((p for p in ps if p.get("kind") in ("robot-photo", "cad")), None)


def label(rec):
    return f"{rec['team']} {rec['team_name']}"


def has(rec):
    a = rec["assets"]
    fus = any(x.get("format") == "Fusion" for x in a.get("cad", []))
    tags = []
    if fus:
        tags.append('<span class="tag fusion">Fusion CAD</span>')
    elif any(x["state"] != "withheld" for x in a.get("cad", [])):
        tags.append('<span class="tag">CAD</span>')
    for k, t in (("documents", "documents"), ("code", "code")):
        if a.get(k):
            tags.append(f'<span class="tag">{t}</span>')
    if pictures(rec):
        tags.append(f'<span class="tag">{len(pictures(rec))} pictures</span>')
    return "".join(tags)


def ranked(y):
    return sorted((r for r in RS.values() if r["season"] == y), key=lambda r: r["results"]["opr_rank"])


def home():
    lanes = ""
    for y, s in SS.items():
        wall = "".join(f'<a class="bumper" href="{y}/{r["team"]}/" aria-label="{E(label(r))}, {y}">{r["team"]}<small>{E(r["team_name"])}{": " + E(r["robot_name"]) if r.get("robot_name") else ""}</small></a>' for r in ranked(y))
        lanes += f'<section class="lane" data-season="{y}"><header><a href="{y}/">{ART[y]}<div><h2>{y} {s["name"].title()}</h2><span>Ranked 1 to 20</span></div></a></header><div class="wall">{wall}</div></section>'
    opts = "".join(f'<option value="{f}">{f}</option>' for f in FUNCTIONS)
    ys = "".join(f'<option value="{y}">{y}</option>' for y in SS)
    n = sum(len(list(examples(r, SS[r["season"]]))) for r in RS.values())
    body = f"""<div class="lead"><h1>Pick a bumper</h1><p>The top 20 robots of each FRC season from 2023 to 2026: how each one worked, what it gave up, and where its team put the CAD, pictures, binder and code.</p></div>
{lanes}
<h2 id="find">Find a design example</h2><p>Search {n} mechanisms and decisions by the job you are working on.</p>
<form class="finder" data-base=""><input name="q" type="search" placeholder="align without stopping" aria-label="What are you trying to do?"><select name="fn" aria-label="Job"><option value="">Any job</option>{opts}</select><select name="season" aria-label="Season"><option value="">Any season</option>{ys}</select></form>
<ul class="hits" aria-live="polite"></ul>
<noscript><p>Search needs JavaScript. Every example is also listed <a href="functions/">by job</a>.</p></noscript>"""
    page("index.html", "FRC bot compendium", body, 0, desc="Design examples from the top 20 FRC robots of each season, 2023 to 2026.")


def card(r, base):
    h = hero(r)
    pic = f'<figure class="pic keep" style="margin:0 .5rem -.5rem"><img data-hot loading="lazy" referrerpolicy="no-referrer" src="{E(h["img"])}" alt="{E(h["what"])}"></figure>' if h else f'<div class="pic">{ART[r["season"]]}</div>'
    bet = (r["story"].get("bet") or [{}])[0].get("text", "")
    return f'<a class="card" href="{base}{r["season"]}/{r["team"]}/">{pic}<span class="bumper">{r["team"]}</span><strong>{E(r["team_name"])}{": " + E(r["robot_name"]) if r.get("robot_name") else ""}</strong><p>{E(bet)}</p><span class="have">{has(r)}</span></a>'


def season_page(y, s):
    rows = "".join(f'<tr><td>{E(o["label"])}</td><td class="n">{o.get("auto_points", "")}</td><td class="n">{o.get("teleop_points", "")}</td><td>{E(o.get("note", ""))}</td></tr>' for o in s["objectives"])
    pieces = ", ".join(f'{E(p["id"])} ({E(p["shape"])}, {E(p["size"])}, {E(p["compliance"])})' for p in s["pieces"])
    cards = "".join(card(r, "../") for r in ranked(y))
    by = ""
    for f in FUNCTIONS:
        ms = [(r, m) for r in ranked(y) for m in r["functions"] if m["does"][0] == f]
        if ms:
            by += f'<h3 id="{f}">{f.title()}</h3><p class="muted">{QUESTION[f]}</p><div class="scroll"><table><tr><th>Robot</th><th>Mechanism</th><th>Type</th></tr>' + "".join(
                f'<tr><td><a href="{r["team"]}/">{r["team"]}</a></td><td><a href="{r["team"]}/#{slug(m["name"])}">{E(m["name"])}</a></td><td>{E(m["type"])}</td></tr>' for r, m in ms) + "</table></div>"
    res = "".join(f'<tr><td class="n">{r["results"]["opr_rank"]}</td><td><a href="{r["team"]}/">{E(label(r))}</a></td><td>{r["results"]["division"]}</td><td class="n">{r["results"]["division_opr"]:.2f}</td><td class="n">{r["results"]["record"]}</td></tr>' for r in ranked(y))
    body = f"""<div class="season-head">{ART[y]}<h1><span>{y}</span>{s["name"].title()}</h1></div>
<h2>The game</h2><p>Pieces: {pieces}. Scoring is restated from the <a href="{s["manual"]["url"]}">official manual</a>.</p>
<div class="sheet scroll"><table><tr><th>Objective</th><th>Auto</th><th>Later</th><th></th></tr>{rows}</table></div>
<h2>The robots</h2><div class="cards">{cards}</div>
{f'<h2>Compared by job</h2><div class="sheet">{by}</div>' if by else ''}
<h2>Results</h2><div class="sheet scroll"><table><tr><th>Rank</th><th>Team</th><th>Division</th><th>OPR</th><th>Record</th></tr>{res}</table></div><p class="muted" style="margin-top:1rem">Rank is by OPR in the championship division qualification matches. OPR credits points partners scored, so close ranks mean little. <a href="../about/">How the 20 were chosen</a>.</p>"""
    page(f"{y}/index.html", f"{y} {s['name'].title()} - FRC bot compendium", body, 1, y, f"The top 20 robots of {y} {s['name'].title()}.")


def robot_page(r):
    y, s = r["season"], SS[r["season"]]
    h, res, st = hero(r), r["results"], r["story"]
    name = r.get("robot_name")
    if h:
        pic = f'<figure><a class="pic" href="{E(h["url"])}"><img data-hot referrerpolicy="no-referrer" src="{E(h["img"])}" alt="{E(h["what"])}"></a></figure>'
        credit = f'<p class="credit">{E(h["what"])}. Picture: <a href="{E(h["url"])}">{E(r["sources"][h["src"]]["publisher"])}</a></p>'
    else:
        pic = f'<figure><div class="pic">{ART[y]}</div></figure>'
        credit = '<p class="credit">No picture of this robot is cleared to show. Try the video and photo pages below.</p>'
    ein = f'{res["einstein"]["role"].capitalize()}, {res["einstein"]["division"]} alliance' if res.get("einstein") else "No"
    facts = [("Season record", res["record"]), ("Division", f'{res["division"]}, OPR {res["division_opr"]:.2f}'), ("Top 20 rank", str(res["opr_rank"])), ("On Einstein", ein)]
    if r.get("variant"):
        facts.append(("Variant", r["variant"]))
    body = f"""<div class="robot-head"><div class="stand">{pic}<span class="bumper">{r["team"]}</span></div><div><h1>{E(name or label(r))}<span>{E(label(r)) + ', ' if name else ''}<a href="../">{y} {s["name"].title()}</a></span></h1><dl class="facts">{"".join(f"<dt>{E(a)}</dt><dd>{E(b)}</dd>" for a, b in facts)}</dl><p style="margin-top:1rem"><a href="../../teams/{r["team"]}/">Team {r["team"]} in other seasons</a></p>{credit}</div></div>"""
    if res.get("note"):
        body += f'<p class="muted" style="margin-top:1.2rem">{E(res["note"])}</p>'
    if st.get("bet"):
        body += f'<p class="bet">{E(" ".join(c["text"] for c in st["bet"]))}</p><p style="margin-top:.5rem">{"".join(cite(c) for c in st["bet"])}</p>'
    if any(st.get(b) for b in MATCH):
        cells = [b for b in ("auto", "cycle", "endgame") if st.get(b)]
        body += '<h2>The match</h2>'
        if len(cells) == 3:
            body += '<div class="match">' + "".join(f"<div><h3>{TITLES[b]}</h3>{para(st[b])}</div>" for b in cells) + "</div>"
        else:
            body += "".join(f'<div class="sheet" style="margin-bottom:.5rem"><h3>{TITLES[b]}</h3>{para(st[b])}</div>' for b in cells)
        if st.get("fallback"):
            body += f'<div class="sheet"><h3>{TITLES["fallback"]}</h3>{para(st["fallback"])}</div>'
    if r["functions"] or st.get("bet"):
        body += '<p class="muted">Unmarked statements are the team\'s own claims. Tags mark anything else.</p>'
    rest = [b for b in ("demand", "gave_up", "changed", "outcome") if st.get(b)]
    body += f'<h2>The story</h2><div class="beats">' + "".join(f"<div><h3>{TITLES[b]}</h3>{para(st[b])}</div>" for b in rest) + "</div>"
    if r["functions"]:
        done = {f: next((m for m in r["functions"] if f in m["does"]), None) for f in FUNCTIONS}
        path = "".join(f'<li class="on"><a href="#{slug(m["name"])}">{f}</a></li>' if m else f"<li>{f}</li>" for f, m in done.items())
        body += f'<h2>How it works</h2><ol class="path" aria-label="Jobs with a described mechanism">{path}</ol><div class="mechs">'
        for m in r["functions"]:
            body += f'<section class="sheet mech" id="{slug(m["name"])}"><div class="does">{", ".join(m["does"])}</div><h3>{E(m["name"])}</h3><p class="muted">{E(m["type"])}</p>'
            body += "".join(f"<p>{E(say(c))}{cite(c)}</p>" for c in m.get("solves", []))
            body += "<ul>" + "".join(f"<li>{fact(c)}</li>" for c in m["facts"]) + "</ul>" if m["facts"] else ""
            body += "".join(f"<p><strong>Cost:</strong> {E(say(c))}{cite(c)}</p>" for c in m.get("cost", []))
            body += "</section>"
        body += "</div>"
    if r["decisions"]:
        body += "<h2>Decisions</h2>"
        for d in r["decisions"]:
            rows = [("Because", d["because"]), ("Instead of", d.get("instead_of")), ("Cost", d.get("cost"))]
            body += f'<div class="decision" id="decision-{slug(d["choice"])}"><h3>{E(d["choice"])}</h3><div><dl>' + "".join(f"<dt>{a}</dt><dd>{E(b)}</dd>" for a, b in rows if b) + f"</dl>{cite(d)}</div></div>"
    ps = [p for p in pictures(r) if p is not h]
    if ps:
        body += f'<h2>Pictures</h2><div class="gallery">' + "".join(
            f'<figure><a href="{E(p["url"])}"><img data-hot loading="lazy" referrerpolicy="no-referrer" src="{E(p["img"])}" alt="{E(p["what"])}"></a><figcaption>{E(p["what"])}. <a href="{E(p["url"])}">{E(r["sources"][p["src"]]["publisher"])}</a></figcaption></figure>' for p in ps) + "</div>"
    rows = ""
    for k, t in KINDS.items():
        for a in r["assets"].get(k, []):
            if a.get("img"):
                continue
            f = a.get("format", "not stated")
            fmt = f'<span class="tag{" fusion" if f == "Fusion" else ""}">{E(f)}</span>' + (f'<br><span class="muted">holds {E(a["holds"])}</span>' if a.get("holds") else "")
            loc = f'<a href="{E(a["url"])}">{E(a["what"])}</a>' if a.get("url") else E(a["what"])
            state = {"opened": "read for this page", "listed": "not opened by us", "withheld": "not published"}[a["state"]]
            rows += f"<tr><td>{t}</td><td>{fmt}</td><td>{loc}</td><td class='muted'>{state}</td></tr>"
    body += "<h2>Files and links</h2>" + (f'<div class="sheet scroll"><table class="files"><tr><th>Kind</th><th>Format</th><th>Link</th><th>Checked</th></tr>{rows}</table></div>' if rows else "<p>No files or links found.</p>")
    miss = empty_beats(r)
    if miss or not r["functions"]:
        what = [TITLES[b].lower() for b in miss] + ([] if r["functions"] else ["mechanisms"])
        body += f'<h2>What isn\'t public</h2><p>No source found for: {E(", ".join(what))}.</p><p class="muted">Searched: {E("; ".join(r["searched"]))}. Know of one? The team\'s own page is the best place to ask.</p>'
    body += '<h2>Sources</h2><ol class="sources">' + "".join(f'<li id="src-{k}" value="{k[1:]}"><a href="{E(x["url"])}">{E(x["title"])}</a>, {E(x["publisher"])}, read {x["read"]}</li>' for k, x in r["sources"].items()) + "</ol>"
    page(f"{y}/{r['team']}/index.html", f"{r['team']} {name or r['team_name']} ({y}) - FRC bot compendium", body, 2, y, f"{label(r)}'s {y} robot: story, mechanisms, pictures and files.")


def function_pages():
    body = '<div class="season-head" style="grid-template-columns:1fr"><h1>By job</h1></div><p>Every mechanism is filed under the job it does. Pick the step you are working on.</p>'
    for f in FUNCTIONS:
        n = sum(f in m["does"] for r in RS.values() for m in r["functions"])
        body += f'<div class="decision"><h3><a href="{f}/">{f.title()}</a></h3><p>{QUESTION[f]} <span class="muted">{n} examples</span></p></div>'
        rows = ""
        for y in SS:
            es = [e for r in ranked(y) for e in examples(r, SS[y]) if f in e["functions"]]
            if es:
                rows += f"<h2>{y} {SS[y]['name'].title()}</h2><ul class='hits'>" + "".join(
                    f'<li class="sheet" data-season="{y}"><a class="t" href="../../{y}/{e["team"]}/#{e["id"].split("/")[1]}">{E(e["name"])}</a> <span class="muted">{e["team"]} {E(e["robot"] or e["team_name"])}. {E(e["type"])}</span>' + "".join(f"<p>{E(x['text'])}{'' if x['basis'] == 'team' else ' <span class=tag>' + SAY[x['basis']] + '</span>'}</p>" for x in [c for c in e["claims"] if c["part"] == "solves"] + [c for c in e["claims"] if c["part"] == "fact"][:3]) + "".join(f"<p><strong>Cost:</strong> {E(x['text'])}{'' if x['basis'] == 'team' else ' <span class=tag>' + SAY[x['basis']] + '</span>'}</p>" for x in e["claims"] if x["part"] == "cost") + "</li>" for e in es) + "</ul>"
        page(f"functions/{f}/index.html", f"{f.title()} - FRC bot compendium", f'<div class="season-head" style="grid-template-columns:1fr"><h1>{f.title()}</h1></div><p>{QUESTION[f]}</p>{rows or "<p>No examples yet.</p>"}', 2, desc=QUESTION[f])
    page("functions/index.html", "By job - FRC bot compendium", body, 1, desc="Design examples filed by the job they do.")


def team_pages():
    lst = "".join(f'<li><a href="{t}/">{E(label(rs[0]))}</a></li>' for t, rs in sorted(TEAMS.items(), key=lambda kv: int(kv[0])))
    page("teams/index.html", "Teams - FRC bot compendium", f'<div class="season-head" style="grid-template-columns:1fr"><h1>Teams</h1></div><ul class="chips">{lst}</ul>', 1, desc="All teams in the compendium.")
    for t, rs in TEAMS.items():
        rs.sort(key=lambda r: r["season"])
        page(f"teams/{t}/index.html", f"{label(rs[0])} - FRC bot compendium", f'<div class="season-head" style="grid-template-columns:1fr"><h1><span>Team {t}</span>{E(rs[-1]["team_name"])}</h1></div><div class="cards">{"".join(card(r, "../../") for r in rs)}</div><p class="muted" style="margin-top:2rem">Only seasons when this team ranked in the top 20 are listed.</p>', 2, desc=f"{label(rs[0])}'s robots in the compendium.")


def about():
    body = """<div class="season-head" style="grid-template-columns:1fr"><h1>About</h1></div>
<p>The compendium helps people, and programs that help them, find how other teams solved a step of robot design: what they built, why, what it cost, and where to study it.</p>
<h2>How the 20 were chosen</h2><p>For each season, the OPR tables of the eight championship division pages on The Blue Alliance are pooled, and the 20 highest are kept. We recomputed OPR from every division's qualification scores and it matched to two decimals in all 32 divisions. OPR credits partners' points to a robot, and teams that missed the championship cannot appear. The cut is close: the 20th and 21st robots differ by 0.01 in 2024 and 0.04 in 2026.</p>
<h2>How to read a page</h2><p>A statement with only a source number is the team's own claim, not a measurement. Others are tagged. <span class="tag observer">observer says</span> is someone else. <span class="tag record">on record</span> comes from results or rules. <span class="tag inference">our reading</span> is our inference, with its sources.</p><p>Forum threads were read only as far as they were captured: usually the first page plus a few single posts, so a correction further on can be missing. Each claim was checked against its source by a reader who did not write it.</p><p>Parts of the story with no source are listed once under "What isn't public", with where we looked. Not found does not mean it does not exist.</p>
<h2>Pictures and files</h2><p>Pictures load from the sites where they were published and link back there. Each was looked at first, and pictures with recognizable faces were left out. If your team wants something changed or removed, say so and it will be.</p><p>CAD and files are links only. Fusion is marked only when the link is an Autodesk share link. "Not opened by us" means we saw the link on a page but did not open the file.</p>
<h2>Fonts</h2><p>Sofia Sans Extra Condensed, Schibsted Grotesk and Martian Mono, under the SIL Open Font License 1.1.</p>"""
    page("about/index.html", "About - FRC bot compendium", body, 1, desc="How robots were chosen and how to read a page.")
    page("404.html", "Not found - FRC bot compendium", '<div class="lead"><h1>Wrong pit</h1><p>That page is not here. Start from the <a href="/frc-bot-compendium/">wall of bumpers</a>.</p></div>', 0)


def data():
    d = DIST / "data"
    (d / "robots").mkdir(parents=True, exist_ok=True)
    ex = [e for r in RS.values() for e in examples(r, SS[r["season"]])]

    def w(p, o):
        p.write_text(json.dumps(o, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    w(d / "examples.json", ex)
    w(d / "seasons.json", list(SS.values()))
    w(d / "index.json", [{"id": r["id"], "season": r["season"], "team": r["team"], "team_name": r["team_name"], "robot": r.get("robot_name"), "page": f"{r['season']}/{r['team']}/", "record": f"data/robots/{r['id']}.json", "mechanisms": len(r["functions"]), "decisions": len(r["decisions"])} for r in RS.values()])
    for y in SS:
        w(d / f"{y}.json", [e for e in ex if e["season"] == y])
    for r in RS.values():
        w(d / f"robots/{r['id']}.json", r)
    (DIST / "llms.txt").write_text("# FRC bot compendium\n\nDesign examples from the top 20 FRC robots of each season, 2023 to 2026. An example is a precedent to study under its own season's rules, not a design to copy.\n\n## Data\n- data/examples.json: every mechanism and decision. Fields: id, kind, name, type, functions, pieces, serves, solves, facts, cost, basis, sources, season, team, outcome, study (CAD, documents, code, graphics links). claims lists every statement with its part, basis and source URLs: use it to tell a team claim from anyone else's.\n- data/<year>.json: the same for one season. data/seasons.json: pieces and objectives.\n- data/index.json: all robots. data/robots/<year>-<team>.json: one full record.\n\n## Functions\n" + "".join(f"- {f}: {QUESTION[f]}\n" for f in FUNCTIONS) + "\n## Basis\nteam = the team's claim; observer = someone else; record = results or rules; inference = this site's reading.\n", encoding="utf-8")
    (DIST / ".nojekyll").write_text("")


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "site", DIST)
    home()
    for y, s in SS.items():
        season_page(y, s)
    for r in RS.values():
        robot_page(r)
    function_pages()
    team_pages()
    about()
    data()
    files = [p for p in DIST.rglob("*") if p.suffix in (".html", ".json", ".txt")]
    bad = [(p.relative_to(DIST).as_posix(), m[0]) for p in files for m in [PRIVATE.search(p.read_text(encoding="utf-8"))] if m]
    links = sum(len(re.findall(r'href="(?!https?:|#|data:)', p.read_text(encoding="utf-8"))) for p in files if p.suffix == ".html")
    missing = set()
    for p in files:
        if p.suffix != ".html" or p.name == "404.html":
            continue
        for u in re.findall(r'(?:href|src)="(?!https?:|#|data:)([^"#]+)', p.read_text(encoding="utf-8")):
            t = (p.parent / u).resolve()
            if not (t / "index.html" if t.is_dir() else t).exists():
                missing.add(f"{p.relative_to(DIST).as_posix()} -> {u}")
    print(f"{len(files)} files, {links} internal links, {len(missing)} broken, {len(bad)} private matches")
    for x in list(missing)[:5] + bad[:5]:
        print("  ", x)
    raise SystemExit(1 if bad or missing else 0)


if __name__ == "__main__":
    main()
