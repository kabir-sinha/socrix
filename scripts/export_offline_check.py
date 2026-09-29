"""Open the single-file report with networking disabled: every view renders, fonts load, no request leaves the page.
Usage: python scripts/export_offline_check.py data/socrix_report.html"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

f = Path(sys.argv[1] if len(sys.argv) > 1 else "data/socrix_report.html").resolve()
routes = ["#/", "#/entities", "#/indicators", "#/e/PWR-03", "#/e/PWR-03/i/EG-01", "#/case/PWR-03-2026-08-AL00011",
          "#/review-packs/BFS-04", "#/audit", "#/validation", "#/method", "#/about"]
bad, requests, errors = [], [], []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); ctx.set_offline(True)
    pg = ctx.new_page()
    pg.on("request", lambda r: not r.url.startswith(("file:", "data:", "blob:")) and requests.append(r.url))
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
    for r in routes:
        pg.goto(f.as_uri() + r); pg.wait_for_timeout(500)
        h1 = pg.inner_text("#band h1")
        if not h1 or "could not" in h1.lower() or "can’t" in h1.lower(): bad.append((r, h1))
    pg.evaluate("document.fonts.ready")
    fonts = pg.evaluate("""[...document.fonts].filter(x => x.status === 'loaded').map(x => x.family + ' ' + x.weight)""")
    check = pg.evaluate("""document.fonts.check('16px "Noto Sans"') && document.fonts.check('16px "IBM Plex Mono"')""")
    b.close()
print({"views_failed": bad, "external_requests": requests, "errors": errors, "fonts_loaded": sorted(set(fonts)), "fonts_check": check})
sys.exit(1 if bad or requests or errors or not check else 0)
