# Claude Code prompts: continuing SOCRIX on the Mac

**How to use this:** open the `SOCRIX` folder in VS Code, start Claude Code in the terminal (`claude`), and paste one prompt at a time, in order. Claude Code reads `CLAUDE.md` automatically. After each prompt, check that `pytest -q` is green (it includes the engine-vs-independent comparison) and commit (`git add -A && git commit -m "..."`) before moving to the next.

**Priority for the idea round (deadline 30 Sep):** only prompts 0 and 7 are needed. The idea submission is the PPT, and the working prototype is a bonus. Prompts 1–6 are for the finals build.

---

### Prompt 0: set up and verify (do this first, ~5 min)
```
Set up this repo on my Mac and prove it works. Create a Python 3.12 or 3.13 venv in .venv, install with
pip install -e ".[dev]", run pytest -q, then socrix demo, then start socrix serve in the background and
fetch /api/overview and /api/benchmark with curl to confirm they return JSON, and run
python scripts/independent/compare.py (must report 0 mismatches). Initialise git with a
.gitignore that excludes .venv, __pycache__, data/* except data/reference/, and *.duckdb. Make the first
commit. Report the test count, the benchmark recall/precision, and anything that failed with its fix.
Do not change engine logic in this step.
```

### Prompt 1: Cyber Resilience indicators (coverage from 7/8 to 8/8)
```
Read CLAUDE.md, docs/ARCHITECTURE.md and socrix/catalogue.yaml. The Cyber Resilience capability area has
no indicator, so coverage is 7/8. Add an optional submission file exercises.csv (exercise_id, entity_id,
type in {backup_restore, dr_failover, ir_tabletop}, planned_date, executed_date, outcome in {pass, partial,
fail, not_run}, findings_closed_ratio) to schema.py with validation and a dialect entry. Add two indicators
following the "Adding an indicator" checklist in CLAUDE.md:
  CR-01 share of planned resilience exercises not run or failed in the period (rate, Wilson LB, higher is worse,
        peer+policy: policy concern 60 if any backup_restore exercise was not run)
  CR-02 median days between an exercise and closure of its findings (lower is better, peer track)
Missing exercises.csv must give status "insufficient evidence", never zero. Extend SimSOC to generate
exercises for every entity and plant one new archetype (A13: backup restores never run) on one entity that
has no other plant. Keep all 5 clean entities clean. Update the dashboard only if something breaks. Run
pytest and scripts/seed_sweep.py 1 2 3 4 5: 0 false positives required. Add regression tests and a
VALIDATION.md entry.
```

### Prompt 2: reviewer feedback loop (the brief's "validation against expert manual review")
```
Implement the reviewer loop. The review pack CSV (socrix/api.py review_pack_csv) has columns reviewer_verdict
and reviewer_notes. Add: (1) socrix feedback import <csv> — validates verdicts in {confirmed, not_an_issue,
unclear}, stores them in a DuckDB table review_feedback with reviewer pseudonym, timestamp and an audit entry;
(2) per-indicator reviewed precision = confirmed / (confirmed + not_an_issue) among targeted items, plus the
confirmed rate among random-control items (an estimate of what the engine misses); (3) a "Reviewer
feedback" section on the Validation page and /api/feedback. Never change thresholds automatically — show a
suggestion only. Add a SimSOC helper that auto-fills verdicts from ground truth, so the loop can be demoed
and tested. Tests + VALIDATION.md entry.
```

### Prompt 3: exploratory anomaly lane (clearly labelled, never a finding on its own)
```
Add an "exploratory" lane using scikit-learn IsolationForest over per-entity-period indicator vectors
(values only, standardised with median/MAD). Output an exploratory score per entity-period and the top 3
contributing indicators (permutation-based). Display it on the entity page in a separate, clearly labelled
"Exploratory signal — not a finding" box. It must never change SAI, findings or review packs. Fixed
random_state from config. Document the six ML disclosures the brief asks for (data, features, model,
validation, limitations, human oversight) in docs/ARCHITECTURE.md §6. Tests: determinism, and no effect on
findings.
```

### Prompt 4: real public data trial (GUIDE)
```
I have downloaded Microsoft GUIDE (GUIDE_Train.csv) into ~/Downloads. Run python -m socrix.adapters.guide on
it. If the column check fails, fix the mapping in socrix/adapters/guide.py to match the real header (print
the header first). Ingest into a separate SOCRIX_HOME (not ./data), score, and write docs/GUIDE_TRIAL.md:
orgs used, rows loaded and rejected with reasons, which indicators could be assessed versus insufficient,
top findings with explanations, and honest limitations (no workflow/asset data; incident-level labels;
group splits by OrgId+IncidentId). Do not commit any GUIDE data.
```

### Prompt 5: air-gapped installer
```
Make SOCRIX installable on a machine with no internet. Add scripts/make_offline_bundle.sh that builds a
wheelhouse (pip download for the target platforms macOS arm64, Linux x86_64 and Windows amd64, Python 3.12)
plus the SOCRIX wheel, and scripts/install_offline.sh / .ps1 that install from it with --no-index. Add an
optional Dockerfile (python:3.12-slim, non-root user, EXPOSE 8157, no network at runtime). Test the Linux
path inside Docker with --network none: demo, serve and the curl checks must work. Document in the README.
```

### Prompt 6: hardening pass
```
Act as a strict reviewer of this repo against CLAUDE.md. Look for: any runtime network call, any path where
missing data becomes 0, any user-controlled string rendered without escaping in socrix/web/app.js, SQL built
by string formatting with user input in api.py, unbounded query parameters, and finding explanations
that do not match the numbers on the page. Fix what you find, add a test for each, and list the fixes in
docs/VALIDATION.md. Then run pytest, the seed sweep, python scripts/independent/compare.py, and
python scripts/ui_audit.py node_modules/axe-core/axe.min.js (npm i axe-core first): 0 axe violations,
no console errors, no overflow at 390px.
```

### Prompt 7: submission assets (screenshots and demo path)
```
Start socrix serve and use Playwright (headless Chromium) to capture 1600x1000 PNG screenshots into
docs/screenshots/: overview, entity PWR-03, indicator PWR-03/EG-01 (peer plot visible), case timeline from
the first EG-01 evidence row, validation page, and the BFS-04 NS-02 page (missing ATT&CK tactics). Then write
docs/DEMO_SCRIPT.md: a 2-minute click path (overview → worst entity → finding → evidence → case → lineage →
validation), with one sentence of narration per step, in plain English.
```
