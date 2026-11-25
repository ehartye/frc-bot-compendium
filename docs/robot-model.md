# Robot model and story format

Status: version 1, approved by the owner on 2026-11-25. Tested on four robots before approval. The functions, the six beats, the evidence rules and the record shape are frozen; a change needs the owner. All robots get a page, including those with almost nothing public.

## Who this is for

The main reader is a model helping a student design a robot with agent-frc. At some step it needs to ask "who has solved this before, how, what did it cost them, and where can I look at it?" The compendium answers with **design examples**. People can browse the same records as a website, organized by season.

An example is a precedent to study, not a design to copy. It shows what one team did under one season's rules. A model must check its own season's rules and requirements before using an idea.

## Two records

**Season record** (`data/seasons/<year>.json`): the game pieces with their shape and size, the phases of a match, and the scoring objectives, each with an id. FIRST manuals are cited by link and restated in our words.

**Robot record** (`data/robots/<year>/<team>.json`): one robot in one season.

| Part | What it holds |
|---|---|
| Identity and results | Team, robot name, variant, championship rank and record. A robot outside the championship top 20 carries `results.added` (why and rank) and a note; one that did not play in a championship division has no division or rank |
| Story | Six beats, the same for every robot |
| Mechanisms | Each filed under the functions it performs, with the problem it solves, its facts and its cost |
| Decisions | What the team chose, why, instead of what, and what it cost |
| Assets | Where CAD, graphics, documents and code are, with format and whether we opened it |

## Functions

Function names follow the stages agent-frc already uses to walk one game piece through a match, so a model can search with the words of the step it is on.

| Function | Question it answers |
|---|---|
| `drive` | How does the robot move? |
| `acquire` | How does it get a piece, and from where? |
| `retain` | How does it hold a piece securely? |
| `transfer` | How does a piece move or turn between acquire and deliver? |
| `position` | How does it reach or aim? |
| `deliver` | How does the piece leave and score? |
| `endgame` | How does it earn endgame points? |
| `sense` | How does it know where it and the piece are, and what is automated? |
| `structure` | What packaging, frame or weight choice makes the rest possible? |

Mechanism types and archetypes stay free text. They will be frozen from what the sources say once all robots are read.

## Design examples

Every mechanism and every decision is one example with a stable id, such as `2025-254/end-effector`. An example carries:

- the function, season, game pieces and objectives it serves
- the problem it solves and the solution, in the team's terms
- its numbers, with units
- what it cost
- how good the evidence is, and how the robot placed
- where to study it: CAD, binder, code, video

A model finds examples in two ways:

1. Run `python tools/compendium.py find --function deliver --text "align without stopping"`. Results are JSON, best match first. It matches words, with more weight on rare words and on a mechanism's name and the problem it solves; it does not know that two phrases mean the same thing, so try the terms teams use.
2. Fetch the published index by URL when it has no checkout: https://ehartye.github.io/frc-bot-compendium/llms.txt lists the files.

## The story: six beats, in this order

Word limits keep robots comparable.

| Beat | Question | Limit (words) |
|---|---|---|
| 1. The bet | What one idea was this robot built around? | 35 |
| 2. The demand | Which of the season's objectives did the team put first, and why? | 70 |
| 3. The match | Auto, one full cycle from acquire to reset, endgame, and the fallback | 60 each |
| 4. What it gave up | What the bet cost: capability, time, weight, risk | 70 |
| 5. What changed | Redesigns, removed mechanisms, lessons during or after the season | 70 |
| 6. The outcome | What happened on the field, from the record | 50 |

A beat with no evidence gets no heading. The page lists those beats once, in "What isn't public", with the searches that were run.

## Evidence rules

Every statement carries a basis and its sources.

| Basis | Meaning |
|---|---|
| `team` | The team said it |
| `observer` | Someone else said it (a commenter, interviewer or reporter) |
| `record` | A results service or rules document records it |
| `inference` | Our reading. It must name the sources it rests on |

- A fact with a number carries its unit.
- "The team says it does not publish this" is different from "we did not find it", and each is recorded as what it is.
- An asset is a location, a format, and one of: `opened`, `listed` (seen on a page, not opened) or `withheld` (the team says it does not publish it). Nothing is downloaded or rehosted.
- Fusion is claimed only when the link is an Autodesk share link.

## Sources

A statement cites a source id from the record's own source table: title, public URL, publisher and date read. Records never contain private paths or notes.

The records in this repository are the originals, and the website is rendered from them.

## Still open

- Whether mechanism types and archetypes reduce to short lists (after all robots are read).
- Whether partner and alliance roles need their own field or stay in the match beat.
- How to show one robot that was rebuilt mid-season: version 1 uses the "what changed" beat and a `variant` field.
- How agent-frc reaches the index: a pointer in its design skills is a change to that plugin, not to this repository.
