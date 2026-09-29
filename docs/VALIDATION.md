# Validation & build verification log

## 1. What is validated
The brief asks for validation against expert manual review. On synthetic data, the "expert" is the planted ground truth, `data/ground_truth.json`, which SimSOC writes. Only `benchmark.py` reads it, after scoring. The detection modules never open it.

The grading unit is the finding, keyed as (entity, period, indicator):
- **Detected:** a planted weakness flagged by its expected indicator.
- **Related:** another indicator flagged on the same entity for the same behaviour. For example, alerts closed with no investigation also show as FP closures with no enrichment. These are counted separately: not a hit, and not a false positive.
- **Abstained:** the engine said "insufficient evidence" instead of guessing.
- **False positive:** any other finding, including every finding on the 5 clean entities.

## 2. Results

| Run | Recall | False positives | Clean-entity FPs |
|---|---|---|---|
| Default seed 26157 | 34/34 (100%) | 0 | 0 |
| Seeds 1–10 (`scripts/seed_sweep.py`) | 336/340 (98.8%) | 0 | 0 |

The 4 misses on the other seeds, each checked by hand:
- Seed 7, PWR-03 EG-03 (2026-06): 1 of 9 critical TPs not escalated. That is too weak to call.
- Seed 7, PWR-03 EG-03 (2026-08): n = 4, below the minimum n of 5, so the engine abstained correctly.
- Seed 10, PWR-03 EG-03 (2026-08): 2 of 7 not escalated, modified z 0.6.
- Seed 1, PWR-06 EG-05 (2026-06): modified z 2.99, just under the 3.5 line, because the peer spread was wide.

This is honest behaviour for small samples. Synthetic results show the engine behaves as designed; they are not evidence of accuracy on real SOCs.

## 3. Issues found and fixed during the build
Each fix is locked in by a regression test in `tests/`.

| # | Symptom | Root cause | Fix | Test |
|---|---|---|---|---|
| 1 | `AttributeError` in validation | pandas `itertuples` renames columns that start with `_` | Column renamed to `reject_reason` | `test_validate_rejects_with_reason_not_silently` |
| 2 | Cases pointing at rejected alerts | No referential integrity | Orphans → reject log, then deleted | `test_referential_integrity_and_counts` |
| 3 | DuckDB `ZoneInfoNotFoundError: Asia/Calcutta` | Host timezone leaked into DuckDB | `SET TimeZone='UTC'` on every connection; tests run with `TZ=Asia/Kolkata` | `test_timestamps_survive_non_utc_host` |
| 4 | "Truth value of a Series is ambiguous" | `evidence or []` on a Series | Explicit `None` check | covered by the engine tests |
| 5 | Wrong case linkage | IDs guessed by string replace | Merge on `cases.alert_id` | `test_case_flags_only_findings` |
| 6 | PWR-08 flagged 4× for one weakness | Cases with no workflow counted as EG-01, EG-07 and EG-03 too | Execution-gap indicators judge only cases with workflow; NS-03 owns missing records | `test_regression_no_double_count_of_missing_workflow` |
| 7 | Clean PWR-04 flagged EG-05 (concern 82) | k = 8, n = 17 noise against a tight MAD | MAD floored at the binomial standard error for rate indicators | `test_regression_pwr04_eg05_small_n_not_flagged` |
| 8 | NS-01 false positives on single silent assets, then on k = 2 in the seed sweep | Per-asset Poisson test (a) ignored multiple assets and (b) under-estimated silence, because alert counts are over-dispersed | Binomial tail over n assets with an empirical, winsorised, Jeffreys-prior peer rate (a trimmed-peer variant was tried first and still produced 4 false positives) | `test_regression_single_silent_asset_not_flagged` + sweep |
| 9 | API evidence endpoint returned 500 | DuckDB needs `pytz` for timezone-aware timestamps | `pytz` added to dependencies | `test_evidence_alert_rows_serialise_timestamps` |
| 10 | NS-01 evidence empty in the UI | Asset IDs were routed to the alert join | Routing by the catalogue `sample_cases` flag | `test_non_alert_evidence_not_empty` |
| 11 | Chart median (3.2%) disagreed with the text (3.0%) | Browser recomputed the median over all entities | Chart uses the engine's baseline median | visual check |
| 12 | Case page listed below-threshold indicators as "flagged" | Joined evidence without the score | Only findings are shown as flags; the others appear as "also counted in" | `test_case_flags_only_findings` |
| 13 | Method page lost the catalogue version | `/api/meta` overwrote the key | Separate `catalogue_version` and `indicators` keys | `test_meta_keeps_catalogue_version` |
| 14 | A finding (NS-05) had no evidence rows | Indicator emitted none | Evidence is every critical asset with its alert count, quietest first | `test_every_finding_has_explanation_and_evidence` |
| 15 | Area value shown as 8e-16 | Floating-point noise in the power mean | Rounded to 9 decimals | `test_power_mean_limits_dilution_and_skips_nan` |
| 16 | NS-08 row list out of order ("row 103" before "row 11") | Text sort | Evidence stored with an explicit sequence | `test_numeric_row_order` |
| 17 | A clean submission (0 rejects) crashed ingest | Empty DataFrame had no columns | Explicit schemas for receipts, rejects and profiles | `test_guide_like_submission_end_to_end` |
| 18 | No workflow data crashed the engine; EG-05 then judged "no remediation" from nothing | `.apply` on an empty Series returned a DataFrame; EG-05 scope | `.map` with bool masks; EG-05 only over alerts with workflow | same |
| 19 | Tooling (not product): `seed_sweep.py` import error; `pkill -f` killed its own shell | Script path; the pattern matched the command itself | `sys.path` insert; PID-safe kill loop | n/a |
| 20 | Peer baselines included peers whose own sample was below min_n | Peer filter checked only for a non-null value | Peers must meet the indicator's min_n (found by the independent re-implementation) | independent diff, §5.1 |
| 21 | White text on "finding" heat cells was 2.53:1; dark-mode steps indistinguishable; the scale went grey→yellow→red | Hand-picked colours | Single-hue OKLCH scale, lightness-monotone, validated; per-step text colour ≥ 5.2:1 in both themes | `scripts/ui_audit.py` (axe) |
| 22 | Concern chips invisible (white on grey, 1.13:1) after 21 | `.chip` rule overrode the scale classes | Higher-specificity `.chip.hN` rules | axe |
| 23 | Mobile overview scrolled sideways (758px on a 390px screen) after 21 | Absolutely positioned screen-reader labels escaped the scroll box | `.scroll { position: relative }`; entity column pinned | ui_audit overflow check |
| 24 | Charts had no text alternative | SVG `role=img` without a label | `aria-label` with the actual values | axe `svg-img-alt` |
| 25 | Clickable table rows unreachable by keyboard | `<tr onclick>` only | `tabindex`, `role=link`, Enter/Space, focus ring | ui_audit keyboard check |
| 26 | Red/green/amber chip text 3.7–4.47:1 | Tints too dark | Darker status colours, lighter tints | axe |
| 27 | `offset=-5` returned 500 | No bound on the query parameter | `ge=0`, `ge=1` / `le=500` | `test_hostile_inputs_are_rejected` |
| 28 | Unknown entity, indicator or period on the evidence endpoint returned an empty 200 | No validation | 404s | same |
| 29 | Scoring cost grew with entities² (3× data took 4.3× longer) | Tables re-filtered per entity; a 127k-element set rebuilt 144×; per-row peer lookups over the whole table | Tables split once; set built once; EG-05 vectorised; peer and history lookups indexed. Output identical to the independent calculation | §5.4 |
| 30 | `test_web_assets_make_no_external_requests` crashed with `IsADirectoryError` once `web/fonts/` existed | The test read every entry of `web/` as text, non-recursively | Walks `web/` recursively and checks every `.html/.css/.js` file; binary fonts and licence texts skipped | same test |

## 5. Verification pass 2 (29 Sep 2026)

### 5.1 Independent recalculation
A separate agent re-implemented every indicator and score from a written specification, without access to the engine code, and read the same evidence snapshot.
- 576 indicator rows (16 entities × 3 periods × 12 indicators), compared on k, n, value, peer median, modified z, peer concern, policy concern and concern: **0 mismatches**.
- SAI, findings and coverage for every entity: identical.
- This comparison surfaced issue 20. It was re-run after every later change, including the performance rewrite, still with 0 mismatches.

### 5.2 Detection limits (dose-response)
Every planted weakness was scaled to a fraction of its default strength (`SOCRIX_DOSE`), over 3 seeds per dose. A dose of 1.0 reproduces the demo data byte for byte (SHA-256 identical).

| Archetype | 0.15 | 0.25 | 0.50 | 0.75 |
|---|---|---|---|---|
| A1 no-investigation closures | 1/9 | 3/9 | 9/9 | 9/9 |
| A2 fast closures | 0/3 | 0/3 | 3/3 | 3/3 |
| A3 no escalation | 0/9 | 1/9 | 4/9 | 8/9 |
| A4 template notes | 9/9 | 9/9 | 9/9 | 9/9 |
| A5 unremediated repeats | 1/9 | 1/9 | 2/9 | 8/9 |
| A6 no enrichment | 9/9 | 9/9 | 9/9 | 9/9 |
| A7 silent critical assets | 0/9 | 0/9 | 1/9 | 1/9 |
| A8 missing tactics | 9/9 | 9/9 | 9/9 | 9/9 |
| A9 no workflow | 9/9 | 9/9 | 9/9 | 9/9 |
| A10 low activity | 0/9 | 0/9 | 0/9 | 7/9 |
| A11 data quality | 0/9 | 0/9 | 9/9 | 9/9 |
| A12 workload | 0/9 | 4/9 | 9/9 | 9/9 |
| **False positives (all runs)** | **0** | **0** | **0** | **0** |

How to read the known limits:
- **A7:** fewer than 3 silent assets out of 40 is statistically plausible by chance, so it is not flagged; ≥ 3 is flagged.
- **A10:** an activity drop of less than about 30% sits inside normal peer variation.
- **A3:** with 10–16 critical true positives a month, partial non-escalation lacks the evidence to call.
- **A2:** EG-02 is median-based, so it detects systemic speed-ups; partial ones are caught by EG-01 when steps are skipped.
- **A11:** reject rates below the 5% tolerance are, by policy, not a finding.

Below-threshold signals (concern 35–49) are shown on each entity page as "Near threshold — worth a look".

**Finding-threshold sensitivity** (all periods): 45 findings at a threshold of 40, 43 at 50 (the default), 42 at 55 and 41 at 70. Clean entities: 1 at 40 or 45, 0 at 50 and above.

### 5.3 UI, colour, accessibility
- **axe-core 4.13:** WCAG 2 A/AA plus best practice on 9 routes × light/dark → **0 violations**. Re-run after the UI redesign (`docs/ui/UI_CHANGES.md`) on 16 routes × light/dark → **0 violations**.
- **No page errors or console errors;** no horizontal overflow at 390px.
- **Keyboard:** Tab reaches the rows and Enter drills down.
- **Concern scale:** checked with the dataviz validator (single hue, monotone lightness, adjacent ΔL ≥ 0.06). The low end deliberately recedes on the heatmap.
- **Identity is never shown by colour alone:** the red "self" dot also carries a text label.

### 5.4 Security, robustness, scale
- **XSS:** HTML/JS payloads were placed in a case note, a detector name and an asset ID of a real submission. They were not executed on the live server or in the static report; they display as text.
- **Hostile inputs:** SQL-injection-shaped paths and parameters, path traversal and unbounded paging all return 404/422, and the tables stay intact. POST and DELETE return 405. The web assets make no external requests. All covered by tests.
- **Scale:** 48 entities (127k alerts, 525k workflow rows, 92k asset rows). Ingest 12.5s; score 26.6s (was 47.4s); peak memory 0.85 GB. Still 34/34 detected with **0 false positives across 43 additional clean entities**. At 16 entities, scoring takes 7.5s (was 11.3s).

## 6. How to re-run everything
```bash
pytest -q                                   # 60 tests
socrix demo                                 # default-seed benchmark
python scripts/seed_sweep.py 1 2 3 4 5 6 7 8 9 10
SOCRIX_DOSE=0.5 SOCRIX_HOME=/tmp/d python scripts/dose_worker.py 1     # one detection-limit run
socrix serve & python scripts/ui_audit.py node_modules/axe-core/axe.min.js   # needs playwright + npm i axe-core
```
