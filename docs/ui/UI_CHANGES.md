# SOCRIX UI redesign — AIRIX family, formal and minimal

Branch `ui-family`. UI only: no change to the engine, API responses, scoring, catalogue or any number.
`api.py` and every engine file are untouched.

## Who the screens are for
- **NCIIPC / NTRO supervisory analysts.** They review many critical-sector entities from submitted records and need to know
  where to look first, why, and what to open next. The design gives them a ranked **priority review queue**, a **sector summary**,
  a count of **entities with a finding per capability area**, sortable/searchable tables, one-click **review packs**,
  and a **Print / Save as PDF** entity report (auditors print; the PDF is the formal deliverable).
- **Auditors / reviewers.** Evidence rows, case timelines with durations, SHA-256 receipts with a copy button, and an alert lookup.
- **SIH evaluators.** Identity strip, About page (PS ID, title, owner, team), method in five steps, validation with detection limits,
  and an explicit honesty statement. The look is official-grade; the identity is clearly student-built.

## What changed and why

### 1. AIRIX family resemblance (rebuilt in plain CSS/JS)
- Fixed 240px left sidebar with grouped navigation (Assurance · Evidence · Assessment quality · About);
  active item = left accent bar + tinted background. Main content capped at 1280px.
- Navy page-header band on every page: breadcrumb (amber, the AIRIX signature), title, one-line description,
  and on the Overview a hero figure (**15 findings**) with Entities assessed 16 · Entities with findings 11 · Validation recall 100.0% · Audit chain Intact.
- Theme toggle top-right, persisted to `localStorage["socrix-theme"]`; an inline `<head>` script applies it before first paint (no flash).
- Sortable tables (`aria-sort`, button headers), entity search, whole-row click-through, tabular numbers.
- Segmented controls for view toggles (sector, sort order).
- **Not copied from AIRIX:** tiny all-caps labels, decorative corner ticks, three font families, monospace numbers,
  two-hue muddy colour scale, inconsistent decimals, missing mobile navigation, low-contrast muted text.

### 2. Design system (UX4G conventions)
- Every colour is a CSS token with a light and a dark set; rules reference tokens only (the print block overrides tokens).
- Fonts self-hosted in `socrix/web/fonts/` (latin woff2): **Noto Sans** 400/500/600 for UI, **IBM Plex Mono** 400/500 for identifiers only
  (alert/case/asset/detector/ATT&CK IDs, entity IDs, indicator codes, hashes). SIL OFL 1.1 licences included.
  `cli.export_static` inlines them as base64 `data:` URLs, so the single-file report keeps its fonts offline.
- Type scale only: Hero 56/60 · Heading XL 32/36 · Heading M 20/28 · Body L 18/24 · Body M 16/24 · Body S 14/20 · Label M 12/16.
  Nothing below 12px; no all-caps labels.
- Colours exactly as specified (primary `#0b3d6e` / `#8cb8ea`, band navy, amber only in the band and the Prototype badge).
  The validated one-hue concern scale (`--c0…--c4`, `--t0…--t4`, h0–h4) is unchanged; its legend is now a compact horizontal key.
- 8px grid, 8px radius, 1px borders, no shadows, 24px card padding (16px mobile), 24px gaps, 44px table rows.

### 3. Identity
- `SITE` object at the top of `app.js` is the single source: SOCRIX · SOC Risk & Assurance Index · Team AIRIX · Team ID 153754 ·
  Bennett University · Smart India Hackathon 2026 · SIH26157 · “Supervisory Analytics Tool for SOC Assessment (SAT-SA)” (title confirmed
  against the published SIH 2026 problem-statement list) · NTRO / NCIIPC.
- Identity strip, sidebar wordmark + “SIH26157 · NTRO / NCIIPC” + Prototype badge, three-column footer with “Data as of” from `/api/meta`,
  and page titles `<Page> · SOCRIX — SIH26157`.
- No emblem, flag or agency logos; agencies named as text only; footer states it is not an official product.

### 4. Navigation and new views (client-side, from existing endpoints)
- **Entities** `#/entities` — sortable, searchable; sector segmented control; “Only entities with findings”; state kept in the URL hash.
- **Indicators** `#/indicators` — catalogue from `/api/meta` + entities flagged per indicator (from `/api/overview`) with links to each entity’s indicator page.
- **Review packs** `#/review-packs/<entity>` — entity dropdown, reuses the entity page’s pack + detector components, CSV download
  (server: the API CSV; static report: the same columns generated in the browser).
- **Audit & lineage** `#/audit` — chain status, alert lookup → `#/case/<id>`, how a number is traced, evidence-store row counts
  (`meta.counts`), rejected rows by entity.
- **About** `#/about` — PS, what SOCRIX does, method in five steps, honesty statement, team.
- **Quick search** in the header (“Go to entity or alert ID”; `/` or Ctrl/Cmd+K) with ARIA combobox semantics.
- **Mobile (<768px):** sidebar becomes a drawer (menu button, focus trap, Esc/scrim/navigation close, close button); smaller band; hero 40px.
- Skip link, landmarks (`header`, `nav`, `main`, `footer`, labelled identity region), visible focus ring everywhere, live-region page announcements.

### 5. Page enhancements
- **Overview:** priority review queue, sector summary, entities-with-a-finding per capability area, heatmap with sector + sort segmented
  controls, rank-range info tooltip + `<details>`.
- **Entity:** band with ID (Plex Mono), sector · size, SAI, findings, rank range, P(top 3), coverage; finding cards (code chip, name, concern badge,
  sentence, “Peers · History · N evidence rows →”, brief ref); near-threshold list; 8px capability tracks with right-aligned values;
  sortable indicator table; review pack with concern column; **Print / Save as PDF** with an A4 print stylesheet (no chrome, light scale,
  page breaks, footer with product, team, PS ID, data-as-of and URL hash).
- **Indicator:** band stats; strip plot with legend + “How to read this”; sticky-header evidence table (scrolls within 640px), 44px rows,
  pager links with `aria-label`s.
- **Case & lineage:** “13 Aug 2026, 05:20 UTC” times, “+1 min” step durations, time to close, SHA-256 in Plex Mono with a copy button, flag chips.
- **Validation:** KPI cards kept; archetype table with inline bars (natural sort); **Detection limits** table hard-coded from `docs/VALIDATION.md` §5.2 with its source noted.
- **Method:** six short sections (Rates, Peer comparison, Concern, Aggregation, Uncertainty, Explanations), each a Plex Mono formula + one plain line.
- **All pages:** one formatter module (`fmtIdx`, `fmtPct`, `fmtInt` en-IN, `fmtDate`, `fmtDateTime`, `fmtPeriod`, `fmtConcern`), skeleton loading
  (after 120ms, server mode only), calm API-down notice (“Can’t reach the SOCRIX API. Start it with `socrix serve`.”), empty states,
  transitions ≤150ms and none under `prefers-reduced-motion`.

### 6. Charts
- One shared style: 12px muted ticks, 1px gridlines, 2px lines, ≥8px markers, tooltip on hover **and** keyboard focus
  (each point is focusable with an `aria-label`), summary `aria-label` on the chart group, legend under every chart,
  and the “self” dot keeps its text label.

## Before / after
Screens at 1440×900 and 390×844, light and dark, in `docs/ui/before/` and `docs/ui/after/` (`scripts/ui_shots.py`).

| Page | Before | After |
|---|---|---|
| Overview | [before](before/overview__desktop_light.png) · [mobile](before/overview__mobile_light.png) · [dark](before/overview__desktop_dark.png) | [after](after/overview__desktop_light.png) · [mobile](after/overview__mobile_light.png) · [dark](after/overview__desktop_dark.png) |
| Entity (D1) PWR-03 | [before](before/e_PWR-03__desktop_light.png) · [mobile](before/e_PWR-03__mobile_light.png) · [dark](before/e_PWR-03__desktop_dark.png) | [after](after/e_PWR-03__desktop_light.png) · [mobile](after/e_PWR-03__mobile_light.png) · [dark](after/e_PWR-03__desktop_dark.png) |
| Indicator (D2/D3) PWR-03 · EG-01 | [before](before/e_PWR-03_i_EG-01__desktop_light.png) · [mobile](before/e_PWR-03_i_EG-01__mobile_light.png) · [dark](before/e_PWR-03_i_EG-01__desktop_dark.png) | [after](after/e_PWR-03_i_EG-01__desktop_light.png) · [mobile](after/e_PWR-03_i_EG-01__mobile_light.png) · [dark](after/e_PWR-03_i_EG-01__desktop_dark.png) |
| Indicator BFS-04 · NS-02 | [before](before/e_BFS-04_i_NS-02__desktop_light.png) · [mobile](before/e_BFS-04_i_NS-02__mobile_light.png) · [dark](before/e_BFS-04_i_NS-02__desktop_dark.png) | [after](after/e_BFS-04_i_NS-02__desktop_light.png) · [mobile](after/e_BFS-04_i_NS-02__mobile_light.png) · [dark](after/e_BFS-04_i_NS-02__desktop_dark.png) |
| Case & lineage (D6/D7) | [before](before/case_PWR-03-2026-08-AL00011__desktop_light.png) · [mobile](before/case_PWR-03-2026-08-AL00011__mobile_light.png) · [dark](before/case_PWR-03-2026-08-AL00011__desktop_dark.png) | [after](after/case_PWR-03-2026-08-AL00011__desktop_light.png) · [mobile](after/case_PWR-03-2026-08-AL00011__mobile_light.png) · [dark](after/case_PWR-03-2026-08-AL00011__desktop_dark.png) |
| Validation | [before](before/validation__desktop_light.png) · [mobile](before/validation__mobile_light.png) · [dark](before/validation__desktop_dark.png) | [after](after/validation__desktop_light.png) · [mobile](after/validation__mobile_light.png) · [dark](after/validation__desktop_dark.png) |
| Method | [before](before/method__desktop_light.png) · [mobile](before/method__mobile_light.png) · [dark](before/method__desktop_dark.png) | [after](after/method__desktop_light.png) · [mobile](after/method__mobile_light.png) · [dark](after/method__desktop_dark.png) |
| Entities (new) | — | [after](after/entities__desktop_light.png) · [mobile](after/entities__mobile_light.png) · [dark](after/entities__desktop_dark.png) |
| Indicators (new) | — | [after](after/indicators__desktop_light.png) · [mobile](after/indicators__mobile_light.png) · [dark](after/indicators__desktop_dark.png) |
| Review packs (new) | — | [after](after/review-packs_PWR-03__desktop_light.png) · [mobile](after/review-packs_PWR-03__mobile_light.png) · [dark](after/review-packs_PWR-03__desktop_dark.png) |
| Audit & lineage (new) | — | [after](after/audit__desktop_light.png) · [mobile](after/audit__mobile_light.png) · [dark](after/audit__desktop_dark.png) |
| About (new) | — | [after](after/about__desktop_light.png) · [mobile](after/about__mobile_light.png) · [dark](after/about__desktop_dark.png) |

## Verification (29 Sep 2026)
| Check | Result |
|---|---|
| `pytest -q` | **61 passed** |
| `python scripts/independent/compare.py` | 576 rows compared, **0 mismatches** |
| `python scripts/ui_audit.py axe.min.js` (axe-core 4.13, 16 routes × light/dark, 1300px + 390px) | **0 violations**, no console errors, no overflow at 390px, keyboard: Tab reaches a row and Enter navigates |
| `socrix export` + `python scripts/export_offline_check.py` (Playwright `set_offline(True)`) | all 11 views render, Noto Sans 400/500/600 + Plex Mono 400/500 loaded, `document.fonts.check` true, **0 requests** leave the page, 0 errors |
| Functional (Playwright) | drawer opens, traps focus, closes on Esc and navigation; `/` and Ctrl+K focus search; combobox arrows/Enter; alert ID → case; theme persists across reload; entity filters written to the hash; review-pack dropdown; unknown entity → calm notice |

`scripts/ui_audit.py`: route list extended with the new views; the keyboard check now allows up to 80 Tab presses
(skip link, sidebar, search and the band come before the first table row).

## On-screen numbers unchanged
Checked by rendering the old UI (baseline commit) and the new UI over the **same** exported data and comparing every number in the
page text. No value changed. The only differences are formatting or placement:
- period labels `2026-08` → `Aug 2026`;
- the modified-z note (0.6745, 3.5, n=7) moved into the collapsed “How to read this” `<details>`;
- new chart axis ticks (0/50/100) and the “Finding threshold (50)” legend;
- the review-pack table now shows each case’s concern (already in `/api/entity/{e}/review-pack`, previously not displayed);
- band stats repeat figures already on the page.
Counts now use en-IN grouping (e.g. 1,65,574 workflow steps).
Indicator-specific units are unchanged on purpose (e.g. NS-05 and WL-01 medians keep 2 decimals, `6.30`, `3.67`) because rounding them would change the figure.


### PWR-03

| Figure | Before | After |
|---|---|---|
| SOC Assurance Index (0–100, higher = more concern) | 53.5 | |
| findings | 3 | |
| rank range · P(top 3) 62.4% | 1–4 | |
| capability areas with evidence | 7/8 | |
| Header band (after) | | SAI (0–100): 53.5 · Findings: 3 · Rank range: 1–4 · P(top 3): 62.4% · Coverage: 7/8 areas |
| Area: Threat Detection | 0 | 0 |
| Area: Investigation | 76 | 76 |
| Area: Escalation | 86 | 86 |
| Area: Incident Response | 20 | 20 |
| Area: Security Operations | 7 | 7 |
| Area: Governance and Oversight | 0 | 0 |
| Area: Operational Discipline | 0 | 0 |
| Area: Cyber Resilience | n/a | n/a |
| EG-01 count · value · peer median · concern | 74/222 · 27.5% · 3.0% · 100 | 74/222 · 27.5% · 3.0% · 100 |
| EG-02 count · value · peer median · concern | n=222 · 89 min · 134 min · 34 | n=222 · 89 min · 134 min · 34 |
| EG-03 count · value · peer median · concern | 10/16 · 38.6% · 0.0% · 86 | 10/16 · 38.6% · 0.0% · 86 |
| EG-04 count · value · peer median · concern | 26/903 · 2.0% · 2.5% · 0 | 26/903 · 2.0% · 2.5% · 0 |
| EG-05 count · value · peer median · concern | 5/17 · 13.3% · 3.7% · 20 | 5/17 · 13.3% · 3.7% · 20 |
| EG-07 count · value · peer median · concern | 94/689 · 11.3% · 4.2% · 89 | 94/689 · 11.3% · 4.2% · 89 |
| NS-01 count · value · peer median · concern | 0/40 · 0.0% · 0.0% · 0 | 0/40 · 0.0% · 0.0% · 0 |
| NS-02 count · value · peer median · concern | 0 of 11 expected · 0 · 0 · 0 | 0 of 11 expected · 0 · 0 · 0 |
| NS-03 count · value · peer median · concern | 0/903 · 0.0% · 0.0% · 0 | 0/903 · 0.0% · 0.0% · 0 |
| NS-05 count · value · peer median · concern | 252 alerts / 40 assets · 6.30 · 5.70 · 0 | 252 alerts / 40 assets · 6.30 · 5.70 · 0 |
| NS-08 count · value · peer median · concern | 0/903 · 0.0% · 0.0% · 0 | 0/903 · 0.0% · 0.0% · 0 |
| WL-01 count · value · peer median · concern | n=903 · 4.1 · 3.67 · 9 | n=903 · 4.1 · 3.67 · 9 |
| Card heading | Review pack — what to inspect next (20 cases) | Review pack · 20 cases |
| Card heading | Detectors with the weakest handling | Detectors with the weakest handling |
| Detector row | DET-013 33 7 21.2% | DET-013 33 7 21.2% |
| Detector row | DET-014 36 7 19.4% | DET-014 36 7 19.4% |
| Detector row | DET-008 35 6 17.1% | DET-008 35 6 17.1% |
| Detector row | DET-024 30 5 16.7% | DET-024 30 5 16.7% |
| Detector row | DET-002 32 5 15.6% | DET-002 32 5 15.6% |
| Detector row | DET-009 32 5 15.6% | DET-009 32 5 15.6% |
| Detector row | DET-012 33 5 15.2% | DET-012 33 5 15.2% |
| Detector row | DET-022 33 5 15.2% | DET-022 33 5 15.2% |
| Detector row | DET-019 47 7 14.9% | DET-019 47 7 14.9% |
| Detector row | DET-011 43 6 14.0% | DET-011 43 6 14.0% |

### BFS-04

| Figure | Before | After |
|---|---|---|
| SOC Assurance Index (0–100, higher = more concern) | 31.2 | |
| findings | 1 | |
| rank range · P(top 3) 0.5% | 9–11 | |
| capability areas with evidence | 7/8 | |
| Header band (after) | | SAI (0–100): 31.2 · Findings: 1 · Rank range: 9–11 · P(top 3): 0.5% · Coverage: 7/8 areas |
| Area: Threat Detection | 60 | 60 |
| Area: Investigation | 5 | 5 |
| Area: Escalation | 0 | 0 |
| Area: Incident Response | 0 | 0 |
| Area: Security Operations | 1 | 1 |
| Area: Governance and Oversight | 0 | 0 |
| Area: Operational Discipline | 10 | 10 |
| Area: Cyber Resilience | n/a | n/a |
| EG-01 count · value · peer median · concern | 18/247 · 4.7% · 3.6% · 9 | 18/247 · 4.7% · 3.6% · 9 |
| EG-02 count · value · peer median · concern | n=247 · 136 min · 132 min · 0 | n=247 · 136 min · 132 min · 0 |
| EG-03 count · value · peer median · concern | 0/9 · 0.0% · 0.7% · 0 | 0/9 · 0.0% · 0.7% · 0 |
| EG-04 count · value · peer median · concern | 31/903 · 2.4% · 1.9% · 10 | 31/903 · 2.4% · 1.9% · 10 |
| EG-05 count · value · peer median · concern | 3/18 · 5.8% · 10.9% · 0 | 3/18 · 5.8% · 10.9% · 0 |
| EG-07 count · value · peer median · concern | 46/715 · 4.9% · 4.6% · 2 | 46/715 · 4.9% · 4.6% · 2 |
| NS-01 count · value · peer median · concern | 0/40 · 0.0% · 0.0% · 0 | 0/40 · 0.0% · 0.0% · 0 |
| NS-02 count · value · peer median · concern | 2 of 11 expected · 2 · 0 · 75 | 2 of 11 expected · 2 · 0 · 75 |
| NS-03 count · value · peer median · concern | 0/903 · 0.0% · 0.0% · 0 | 0/903 · 0.0% · 0.0% · 0 |
| NS-05 count · value · peer median · concern | 256 alerts / 40 assets · 6.40 · 5.92 · 0 | 256 alerts / 40 assets · 6.40 · 5.92 · 0 |
| NS-08 count · value · peer median · concern | 0/903 · 0.0% · 0.0% · 0 | 0/903 · 0.0% · 0.0% · 0 |
| WL-01 count · value · peer median · concern | n=903 · 3.7 · 3.62 · 1 | n=903 · 3.7 · 3.62 · 1 |
| Card heading | Review pack — what to inspect next (20 cases) | Review pack · 20 cases |
| Card heading | Detectors with the weakest handling | Detectors with the weakest handling |
| Detector row | DET-008 47 6 12.8% | DET-008 47 6 12.8% |
| Detector row | DET-004 33 3 9.1% | DET-004 33 3 9.1% |
| Detector row | DET-014 44 4 9.1% | DET-014 44 4 9.1% |
| Detector row | DET-011 46 4 8.7% | DET-011 46 4 8.7% |
| Detector row | DET-006 36 3 8.3% | DET-006 36 3 8.3% |
| Detector row | DET-017 36 3 8.3% | DET-017 36 3 8.3% |
| Detector row | DET-016 39 3 7.7% | DET-016 39 3 7.7% |
| Detector row | DET-024 26 2 7.7% | DET-024 26 2 7.7% |
| Detector row | DET-003 27 2 7.4% | DET-003 27 2 7.4% |
| Detector row | DET-021 31 2 6.5% | DET-021 31 2 6.5% |

### PWR-05

| Figure | Before | After |
|---|---|---|
| SOC Assurance Index (0–100, higher = more concern) | 33.2 | |
| findings | 1 | |
| rank range · P(top 3) 4.1% | 8–8 | |
| capability areas with evidence | 7/8 | |
| Header band (after) | | SAI (0–100): 33.2 · Findings: 1 · Rank range: 8–8 · P(top 3): 4.1% · Coverage: 7/8 areas |
| Area: Threat Detection | 63 | 63 |
| Area: Investigation | 5 | 5 |
| Area: Escalation | 0 | 0 |
| Area: Incident Response | 0 | 0 |
| Area: Security Operations | 4 | 4 |
| Area: Governance and Oversight | 0 | 0 |
| Area: Operational Discipline | 10 | 10 |
| Area: Cyber Resilience | n/a | n/a |
| EG-01 count · value · peer median · concern | 14/257 · 3.3% · 3.0% · 3 | 14/257 · 3.3% · 3.0% · 3 |
| EG-02 count · value · peer median · concern | n=257 · 129 min · 134 min · 3 | n=257 · 129 min · 134 min · 3 |
| EG-03 count · value · peer median · concern | 0/8 · 0.0% · 2.2% · 0 | 0/8 · 0.0% · 2.2% · 0 |
| EG-04 count · value · peer median · concern | 35/922 · 2.7% · 2.2% · 10 | 35/922 · 2.7% · 2.2% · 10 |
| EG-05 count · value · peer median · concern | 2/17 · 3.3% · 13.3% · 0 | 2/17 · 3.3% · 13.3% · 0 |
| EG-07 count · value · peer median · concern | 48/742 · 4.9% · 4.2% · 8 | 48/742 · 4.9% · 4.2% · 8 |
| NS-01 count · value · peer median · concern | 3/40 · 2.6% · 0.0% · 80 | 3/40 · 2.6% · 0.0% · 80 |
| NS-02 count · value · peer median · concern | 0 of 11 expected · 0 · 0 · 0 | 0 of 11 expected · 0 · 0 · 0 |
| NS-03 count · value · peer median · concern | 0/922 · 0.0% · 0.0% · 0 | 0/922 · 0.0% · 0.0% · 0 |
| NS-05 count · value · peer median · concern | 219 alerts / 40 assets · 5.47 · 5.75 · 5 | 219 alerts / 40 assets · 5.47 · 5.75 · 5 |
| NS-08 count · value · peer median · concern | 0/922 · 0.0% · 0.0% · 0 | 0/922 · 0.0% · 0.0% · 0 |
| WL-01 count · value · peer median · concern | n=922 · 3.7 · 3.89 · 0 | n=922 · 3.7 · 3.89 · 0 |
| Card heading | Review pack — what to inspect next (20 cases) | Review pack · 20 cases |
| Card heading | Detectors with the weakest handling | Detectors with the weakest handling |
| Detector row | DET-019 38 5 13.2% | DET-019 38 5 13.2% |
| Detector row | DET-021 25 3 12.0% | DET-021 25 3 12.0% |
| Detector row | DET-018 38 4 10.5% | DET-018 38 4 10.5% |
| Detector row | DET-004 31 3 9.7% | DET-004 31 3 9.7% |
| Detector row | DET-013 22 2 9.1% | DET-013 22 2 9.1% |
| Detector row | DET-012 34 3 8.8% | DET-012 34 3 8.8% |
| Detector row | DET-017 34 3 8.8% | DET-017 34 3 8.8% |
| Detector row | DET-014 35 3 8.6% | DET-014 35 3 8.6% |
| Detector row | DET-015 49 4 8.2% | DET-015 49 4 8.2% |
| Detector row | DET-003 45 3 6.7% | DET-003 45 3 6.7% |


## Skipped / notes
- `api.py` and engine files untouched; no network access added (fonts are local, inlined in the export).
- `tests/test_api.py::test_web_assets_make_no_external_requests` iterated `web/` non-recursively and called `read_text()` on every entry,
  so adding `web/fonts/` made it crash. It now walks `web/` recursively and checks every `.html/.css/.js` file (stricter than before);
  the binary woff2 files and OFL licence texts are skipped. Logged as issue 30 in `docs/VALIDATION.md`.
- `pyproject.toml` package data now includes `web/fonts/*`.
- Each `socrix export` adds an audit-log entry, so the “audit chain entries” count rose from 2 to 5 during this work (chain intact).
- `SOCRIX_report.html` at the repo root was regenerated with the new UI.
- Chart points are focusable (`role="img"` inside a labelled `role="group"`), which adds tab stops on indicator pages; this is the price of focus tooltips.
