"""Screenshot every dashboard route at desktop (1440x900) and mobile (390x844), light and dark.
Needs a running `socrix serve` (or SOCRIX_URL pointing at an exported report) and `pip install playwright`.
Usage: python scripts/ui_shots.py docs/ui/after [extra routes...]"""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.environ.get("SOCRIX_URL", "http://127.0.0.1:8157/")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/ui/after")
ROUTES = ["#/", "#/e/PWR-03", "#/e/PWR-03/i/EG-01", "#/e/BFS-04/i/NS-02", "#/case/PWR-03-2026-08-AL00011",
          "#/validation", "#/method"] + sys.argv[2:]
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    for scheme in ("light", "dark"):
        for tag, (w, h) in (("desktop", (1440, 900)), ("mobile", (390, 844))):
            pg = b.new_page(viewport={"width": w, "height": h}, color_scheme=scheme)
            for r in ROUTES:
                pg.goto(BASE + r); pg.wait_for_timeout(800)
                name = r.replace("#/", "").replace("/", "_") or "overview"
                pg.screenshot(path=str(OUT / f"{name}__{tag}_{scheme}.png"), full_page=True)
            pg.close()
    b.close()
print(f"{len(ROUTES) * 4} screenshots -> {OUT}")
