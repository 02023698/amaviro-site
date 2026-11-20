# amaviro.app

The Amaviro website, served by GitHub Pages from `docs/`.

- `design/` — the five pages as designed (the source).
- `site.json` — what changes: publisher, support email, TestFlight and App Store links, the latest beta.
- `tools/build.py` — builds `docs/` from the design: `python3 tools/build.py` (macOS; reads each page's data with JavaScriptCore).

Change `site.json` or a design page, run the build, commit and push. The site updates in a minute or two.
