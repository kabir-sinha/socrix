"""Dashboard audit: axe-core WCAG 2 A/AA + best-practice on every route in light & dark, console errors,
horizontal overflow at 390px, keyboard navigation. Needs: pip install playwright; npm i axe-core; a running `socrix serve`.
Usage: python scripts/ui_audit.py node_modules/axe-core/axe.min.js"""
import json
from playwright.sync_api import sync_playwright
import sys, os
BASE = os.environ.get("SOCRIX_URL", "http://127.0.0.1:8157/")
AXE_PATH = sys.argv[1] if len(sys.argv) > 1 else "node_modules/axe-core/axe.min.js"
AXE = open(AXE_PATH).read()
routes = ["#/", "#/e/PWR-03", "#/e/BFS-06", "#/e/PWR-03/i/EG-01", "#/e/BFS-04/i/NS-02", "#/e/PWR-05/i/NS-01",
          "#/case/PWR-03-2026-08-AL00011", "#/validation", "#/method",
          "#/entities", "#/entities?sector=BFSI&f=1", "#/indicators", "#/review-packs/PWR-03", "#/audit", "#/about"]
report = {"errors": [], "axe": {}, "overflow": [], "keyboard": None}


def goto_ready(pg, r):
    """Navigate, then wait (no fixed sleeps) until the route has finished rendering: the app marks
    <html data-ready="#route">, the page h1 is visible and the first card has rendered."""
    pg.goto(BASE + r)
    pg.wait_for_function("r => document.documentElement.dataset.ready === r", arg=r)
    pg.wait_for_selector("#band h1", state="visible")
    pg.wait_for_selector("#app .card", state="visible")
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ("light", "dark"):
        for w, h in ((1300, 900), (390, 844)):
            pg = b.new_page(viewport={"width": w, "height": h}, color_scheme=scheme)
            pg.on("pageerror", lambda e: report["errors"].append(str(e)))
            pg.on("console", lambda m: m.type == "error" and report["errors"].append(m.text))
            for r in routes:
                goto_ready(pg, r)
                sw = pg.evaluate("document.documentElement.scrollWidth")
                if sw > w + 1: report["overflow"].append((scheme, w, r, sw))
                if w == 1300:
                    pg.add_script_tag(content=AXE)
                    res = pg.evaluate("async () => { const r = await axe.run(document, {runOnly: ['wcag2a','wcag2aa','best-practice']}); return r.violations.map(v => ({id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, sample: v.nodes.slice(0,2).map(n => n.target.join(' ') + ' :: ' + (n.failureSummary||'').slice(0,160))})); }")
                    for v in res:
                        report["axe"].setdefault(f"{v['id']} ({v['impact']})", []).append((scheme, r, v["n"], v["help"], v["sample"]))
                if w == 390 and r in ("#/", "#/e/PWR-03"):
                    pg.screenshot(path=f"docs/screenshots/audit_a_{scheme}_m_{r.replace('#/','').replace('/','_') or 'home'}.png")
                if w == 1300 and r in ("#/", "#/e/PWR-03", "#/e/PWR-03/i/EG-01"):
                    pg.screenshot(path=f"docs/screenshots/audit_a_{scheme}_{r.replace('#/','').replace('/','_') or 'home'}.png", full_page=(r == "#/"))
            pg.close()
    # keyboard: Tab once -> skip link; Enter -> main; Tab (max 20) to the first row; Enter -> an entity route
    pg = b.new_page(viewport={"width": 1300, "height": 900}); goto_ready(pg, "#/")
    pg.keyboard.press("Tab")
    kb = {"skip_link_first": pg.evaluate("document.activeElement.classList.contains('skip')")}
    pg.keyboard.press("Enter")
    kb["skip_moves_focus_to_main"] = pg.evaluate("document.activeElement.id") == "main"
    presses = 0
    while presses < 20 and pg.evaluate("document.activeElement.tagName") != "TR":
        pg.keyboard.press("Tab"); presses += 1
    kb["tabs_to_first_row"] = presses if pg.evaluate("document.activeElement.tagName") == "TR" else None
    pg.keyboard.press("Enter")
    pg.wait_for_function("() => /^#\\/e\\/[^/]+$/.test(location.hash) && document.documentElement.dataset.ready === location.hash", timeout=5000)
    kb["url"] = pg.url
    kb["passed"] = bool(kb["skip_link_first"] and kb["skip_moves_focus_to_main"] and kb["tabs_to_first_row"])
    report["keyboard"] = kb
    b.close()
print(json.dumps({k: v for k, v in report.items() if k != "axe"}, indent=1))
for k, v in report["axe"].items():
    print("AXE", k, "pages:", len(v), "| e.g.", v[0][0], v[0][1], v[0][3]); [print("   ", s) for s in v[0][4]]
ok = not report["errors"] and not report["overflow"] and not report["axe"] and report["keyboard"]["passed"]
print("UI AUDIT", "PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
