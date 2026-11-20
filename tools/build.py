#!/usr/bin/env python3
"""Builds amaviro.app from the design pages (design/*.dc.html) into docs/, which GitHub Pages serves.

    python3 tools/build.py

- Each page's text and lists come from its own data code, run in Apple's JavaScriptCore (tools/page-data.swift).
- Templates (sc-for, sc-if, {{…}}) become plain HTML; no framework, nothing to download but the fonts.
- The Home page's feature tour and letter globe get small scripts of their own.
- site.json holds what changes: publisher, support email, TestFlight and App Store links, the latest beta.
"""
import html, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "site.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "docs")
DOMAIN = CFG["domain"]

PAGES = [  # design file, output path, address
    ("Main.dc.html", "index.html", "/"),
    ("Features.dc.html", "features/index.html", "/features/"),
    ("Plus.dc.html", "plus/index.html", "/plus/"),
    ("Support.dc.html", "support/index.html", "/support/"),
    ("Legal.dc.html", "privacy/index.html", "/privacy/"),
]
LINKS = {"Main.dc.html": "/", "Features.dc.html": "/features/", "Plus.dc.html": "/plus/",
         "Support.dc.html": "/support/", "Legal.dc.html": "/privacy/"}

# MARK: Data and templates

def page_data(design_path):
    r = subprocess.run(["swift", os.path.join(ROOT, "tools/page-data.swift"), design_path], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Reading {design_path} failed:\n{r.stderr}")
    return json.loads(r.stdout or "{}")

def lookup(expr, ctx):
    expr = expr.strip()
    if expr in ("true", "false"):
        return expr == "true"
    v = ctx
    for part in expr.split("."):
        v = v.get(part) if isinstance(v, dict) else None
    return v

def subst(text, ctx):
    def one(m):
        v = lookup(m.group(1), ctx)
        if v is None: return ""
        if isinstance(v, bool): return "true" if v else "false"
        return html.escape(str(v), quote=True)
    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", one, text)

OPEN = re.compile(r"<sc-(for|if)\b([^>]*)>")

def attr(attrs, name):
    m = re.search(name + r'="\{\{\s*([^}]+?)\s*\}\}"', attrs) or re.search(name + r'="([^"]*)"', attrs)
    return m.group(1) if m else None

def close_of(t, start, kind):
    """The end of the body and of the closing tag for a <sc-kind> opened before `start` (nested ones counted)."""
    depth, pos = 1, start
    pat = re.compile(r"<sc-%s\b[^>]*>|</sc-%s>" % (kind, kind))
    while True:
        m = pat.search(t, pos)
        if not m: sys.exit(f"Unclosed <sc-{kind}>")
        depth += -1 if m.group(0).startswith("</") else 1
        if depth == 0: return m.start(), m.end()
        pos = m.end()

def render(t, ctx, tour_current):
    out, pos = [], 0
    while True:
        m = OPEN.search(t, pos)
        if not m:
            out.append(subst(t[pos:], ctx)); break
        out.append(subst(t[pos:m.start()], ctx))
        kind, attrs = m.group(1), m.group(2)
        body_end, close_end = close_of(t, m.end(), kind)
        body = t[m.end():body_end]
        if kind == "for":
            var = attr(attrs, "as")
            for item in (lookup(attr(attrs, "list"), ctx) or []):
                out.append(render(body, {**ctx, var: item}, tour_current))
        else:
            cond = attr(attrs, "value")
            if cond.startswith("show."):
                # A tour panel: every one is on the page; the tour script shows one at a time.
                name = cond.split(".", 1)[1]
                hidden = "" if name == tour_current else " hidden"
                out.append(f'<div class="tour-panel" data-panel="{name}"{hidden}>' + render(body, ctx, tour_current) + "</div>")
            elif cond == "t.showProgress":
                out.append(render(body, ctx, tour_current))  # shown on the current tab by CSS
            elif lookup(cond, ctx):
                out.append(render(body, ctx, tour_current))
        pos = close_end
    return "".join(out)

# MARK: Page scripts

TOUR_CSS = (".tour-panel{display:contents}.tour-panel[hidden]{display:none}"
            ".tour-tab:not(.on) .tour-progress,.tour.manual .tour-progress{display:none}")
TOUR_JS = """<script>
// The feature tour: moves on every 7 seconds until a feature is picked. Panels restart their animation when shown.
(() => {
  const root = document.querySelector('.tour'); if (!root) return;
  const tabs = [...root.querySelectorAll('.tour-tab')], panels = [...root.querySelectorAll('.tour-panel')];
  let i = Math.max(0, tabs.findIndex(t => t.classList.contains('on'))), manual = false;
  function show(k) {
    i = k;
    tabs.forEach((t, n) => { t.classList.toggle('on', n === k); t.setAttribute('aria-selected', String(n === k)); });
    panels.forEach(p => { p.hidden = p.dataset.panel !== tabs[k].dataset.tab; });
    const bar = tabs[k].querySelector('.tour-progress');
    if (bar) { bar.style.animation = 'none'; void bar.offsetWidth; bar.style.animation = ''; }
  }
  tabs.forEach((t, n) => t.addEventListener('click', () => { manual = true; root.classList.add('manual'); show(n); }));
  setInterval(() => { if (!manual && !document.hidden) show((i + 1) % tabs.length); }, 7000);
})();
</script>"""

NAV_JS = """<script>
// Support and Beta share this page: the header marks Beta while you're at the beta section (from the Beta link, or
// scrolled there), and Support elsewhere, so only one is ever highlighted.
(() => {
  const links = [...document.querySelectorAll('.links a')];
  const support = links.find(a => a.getAttribute('href') === '/support/');
  const beta = links.find(a => a.getAttribute('href') === '#beta' || a.getAttribute('href') === '/support/#beta');
  const section = document.getElementById('beta');
  if (!support || !beta || !section) return;
  function mark(atBeta) {
    for (const [a, on] of [[support, !atBeta], [beta, atBeta]]) {
      a.classList.toggle('on', on);
      if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    }
  }
  const io = new IntersectionObserver(es => { for (const e of es) mark(e.isIntersecting); }, { rootMargin: '-45% 0px -45% 0px' });
  io.observe(section);
  mark(location.hash === '#beta');
})();
</script>"""

def method_source(script, name):
    """A method's text from the design's component class (braces counted)."""
    i = script.find(name + "() {")
    if i < 0: return None
    depth, j = 0, script.index("{", i)
    while True:
        c = script[j]
        depth += (c == "{") - (c == "}")
        j += 1
        if depth == 0: return script[i:j]

# MARK: Placeholders and links

def fix_links(page):
    def one(m):
        url = m.group(1)
        for design, path in LINKS.items():
            if url.startswith(design):
                rest = url[len(design):]
                if design == "Legal.dc.html" and rest == "#terms": return 'href="/privacy/#terms"'
                return f'href="{path}{rest}"'
        if url.startswith("assets/"): return f'href="/{url}"'
        return m.group(0)
    page = re.sub(r'href="([^"]*)"', one, page)
    return re.sub(r'src="assets/', 'src="/assets/', page)

def must(page, old, new, file):
    if old not in page: sys.exit(f"{file}: expected text not found:\n{old[:120]}")
    return page.replace(old, new)

def contact_link():
    return f'<a href="mailto:{CFG["supportEmail"]}">{CFG["supportEmail"]}</a>' if CFG["supportEmail"] else None

def fill(page, design):
    page = page.replace("[PUBLISHER NAME]", html.escape(CFG["publisher"]))
    page = page.replace("[2 working days]", html.escape(CFG["responseTime"]))
    email = CFG["supportEmail"]
    if design == "Main.dc.html":
        if CFG["appStoreURL"]:
            page = page.replace('<a class="btn btn-primary" href="#">', f'<a class="btn btn-primary" href="{CFG["appStoreURL"]}">', 1)
        else:
            # Before launch: the beta is the way in.
            page = re.sub(r'<a class="btn btn-primary" href="#">.*?</a>\s*<a class="btn btn-outline" href="Support\.dc\.html#beta">Join the TestFlight Beta</a>',
                          '<a class="btn btn-primary" href="Support.dc.html#beta">Join the Beta</a>\n'
                          '        <span class="btn btn-outline" style="cursor:default;color:#979D97">Coming Soon to the App Store</span>',
                          page, count=1, flags=re.S)
        page = page.replace('<a href="mailto:[SUPPORT EMAIL]">Contact</a>',
                            f'<a href="mailto:{email}">Contact</a>' if email else '<a href="Support.dc.html#contact">Contact</a>')
    if design == "Features.dc.html" and not CFG["appStoreURL"]:
        page = must(page, '<a class="btn btn-primary" href="Main.dc.html#download">Download on the App Store</a>',
                    '<a class="btn btn-primary" href="Support.dc.html#beta">Join the Beta</a>', design)
    if design == "Support.dc.html":
        if email:
            page = page.replace("mailto:[SUPPORT EMAIL]", f"mailto:{email}")
        else:
            page = must(page, '<a class="btn btn-primary" href="mailto:[SUPPORT EMAIL]">Email Support</a>', "", design)
        page = page.replace('<aside class="card"', '<aside id="contact" class="card"', 1)
        if CFG["testflightURL"]:
            page = page.replace("[TESTFLIGHT PUBLIC LINK]", CFG["testflightURL"])
        else:
            page = must(page, '<a class="btn btn-primary" href="[TESTFLIGHT PUBLIC LINK]">Join the Beta on TestFlight</a>',
                        '<span class="btn btn-outline" style="cursor:default;color:#979D97">Public Beta Link Coming Soon</span>', design)
        beta = CFG["latestBeta"]
        page = page.replace("BETA [N]", f"BETA {beta['number']}")
        page = re.sub(r"<li>\[What's new, from docs/betas/BETA-N\.md\]</li>\s*<li>\[What's fixed\]</li>\s*<li>\[Please test\]</li>",
                      "\n          ".join(f"<li>{html.escape(x)}</li>" for x in beta["items"]), page, count=1)
        page = page.replace('<a href="#beta" style="font-size:15px">All beta notes</a>', "")
    if design == "Legal.dc.html":
        page = page.replace("[DATE]", html.escape(CFG["privacyUpdated"]))
        contact = (f'{html.escape(CFG["publisher"])} · {contact_link()}' if email
                   else f'{html.escape(CFG["publisher"])} · In the app: Settings, About Amaviro, Contact Support.')
        page = must(page, f"<p>{html.escape(CFG['publisher'])}, [ADDRESS] · <a href=\"mailto:[SUPPORT EMAIL]\">[SUPPORT EMAIL]</a></p>",
                    f"<p>{contact}</p>", design)
    left = re.findall(r"\[[A-Z][A-Z ]+\]", page)
    if left: sys.exit(f"{design}: placeholders left: {sorted(set(left))}")
    return page

# MARK: Building a page

def build(design, address):
    src = open(os.path.join(ROOT, "design", design), encoding="utf-8").read()
    data = page_data(os.path.join(ROOT, "design", design))
    title = re.search(r"<title>(.*?)</title>", src, re.S).group(1).strip()
    helmet = re.search(r"<helmet>(.*?)</helmet>", src, re.S).group(1)
    body = re.search(r"</helmet>(.*?)</x-dc>", src, re.S).group(1)
    body = body.replace('onClick="{{t.pick}}"', 'data-tab="{{t.id}}" type="button"')
    tour_current = (data.get("current") or {}).get("id")
    page = render(body, data, tour_current)
    script = ""
    if design == "Main.dc.html":
        helmet = helmet.replace("</style>", TOUR_CSS + "</style>", 1)
        globe = method_source(re.search(r'data-dc-script[^>]*>(.*?)</script>', src, re.S).group(1), "startGlobe")
        script = TOUR_JS + "\n<script>\n// The letter globe, as in the app: drag to spin.\n(() => { const o = {\n" + globe + "\n}; o.startGlobe(); })();\n</script>"
    if design == "Support.dc.html":
        script = NAV_JS
    page = fix_links(fill(page, design))
    helmet = fix_links(helmet)
    url = f"https://{DOMAIN}{address}"
    desc = html.escape(CFG["description"])
    head = f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(html.unescape(title))}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#080B08">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Amaviro">
<meta property="og:title" content="{html.escape(html.unescape(title))}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="https://{DOMAIN}/assets/logo-512.png">
<meta name="twitter:card" content="summary">
{helmet.strip()}
<style>html{{scroll-padding-top:84px}}@media (max-width:720px){{html{{scroll-padding-top:112px}}}}</style>
</head>
<body>
"""
    return head + page.strip() + "\n" + script + "\n</body>\n</html>\n"

def write(rel, text):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(text)

def main():
    built = {}
    for design, rel, address in PAGES:
        built[design] = build(design, address)
        write(rel, built[design])
        print(f"{address:12} {len(built[design]) // 1024} KB")
    # /terms: the Terms of Use are part of the privacy page.
    write("terms/index.html", f'<!doctype html><meta charset="utf-8"><title>Terms of Use · Amaviro</title>'
          f'<meta http-equiv="refresh" content="0; url=/privacy/#terms"><link rel="canonical" href="https://{DOMAIN}/privacy/#terms">'
          f'<a href="/privacy/#terms">Terms of Use</a>\n')
    # Not found: the Support page's look, with a short message.
    sup = built["Support.dc.html"]
    a, b = sup.index("</header>") + len("</header>"), sup.index("<footer")
    missing = ('\n  <section style="position:relative;max-width:1200px;margin:0 auto;padding:96px 24px 140px;display:flex;flex-direction:column;gap:18px">\n'
               '    <span class="lbl" style="color:#EDEBE5">Not found</span>\n'
               '    <h1 style="margin:0;font-size:56px;line-height:1.05;letter-spacing:-.025em;font-weight:700">This page isn\'t here.</h1>\n'
               '    <p style="margin:0;font-size:19px;line-height:1.5;max-width:560px">It may have moved. Try the home page, or Support.</p>\n'
               '    <div style="display:flex;flex-wrap:wrap;gap:12px;padding-top:8px"><a class="btn btn-primary" href="/">Home</a>'
               '<a class="btn btn-outline" href="/support/">Support</a></div>\n  </section>\n\n  ')
    write("404.html", (sup[:a] + missing + sup[b:]).replace("<title>Amaviro — Support</title>", "<title>Not Found · Amaviro</title>")
          .replace('class="on" aria-current="page" ', ""))
    for f in os.listdir(os.path.join(ROOT, "static/assets")):
        data = open(os.path.join(ROOT, "static/assets", f), "rb").read()
        os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
        open(os.path.join(OUT, "assets", f), "wb").write(data)
    write("CNAME", DOMAIN + "\n")
    write(".nojekyll", "")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: https://{DOMAIN}/sitemap.xml\n")
    urls = "".join(f"  <url><loc>https://{DOMAIN}{a}</loc></url>\n" for _, _, a in PAGES)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
    print("Built into docs/")

main()
