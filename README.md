# FRC bot compendium

Site: https://ehartye.github.io/frc-bot-compendium/

Design examples from the top 20 FRC robots of each season, 2022 to 2026, and 26 more that were strong all season: what each one was built around, how it worked, what it cost, and where its team published the CAD, pictures, binder and code. It is meant for people designing a robot and for programs helping them.

- `data/robots/<year>/<team>.json`: one record per robot. `data/seasons/<year>.json`: the game.
- `data/roster.json`: the championship OPR ranking (`tools/roster/roster.py`). `data/added.json`: the robots it misses (`tools/roster/season.py`).
- `docs/robot-model.md`: what a record holds and the evidence rules.
- `python tools/compendium.py find --function deliver --text "shoot on the move"`: search the examples (functions: drive, acquire, retain, transfer, position, deliver, endgame, sense, structure). It matches words, so use the terms teams use.
- `python tools/compendium.py check`: check every record.
- `python tools/build_site.py`: build the site into `dist/`.

Python 3.14, standard library only.

Robots belong to the teams that built them. Pictures are loaded from where teams published them; nothing is copied here. Not affiliated with or endorsed by FIRST. To have something changed or removed, open an issue.

Fonts in `site/fonts` are Anybody, Hanken Grotesk, JetBrains Mono and Sofia Sans Extra Condensed, under the SIL Open Font License 1.1 (`site/fonts/OFL.txt`).

The code and text in this repository are under the MIT License (see `LICENSE`). It does not cover the robots, or the pictures, CAD, code and documents that teams published and this site links to.
