# SOCRIX

[![Tests](https://github.com/kabir-sinha/socrix/actions/workflows/tests.yml/badge.svg)](https://github.com/kabir-sinha/socrix/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.13-3776AB?logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/runs-fully%20offline%20%C2%B7%20air--gapped-2ea44f)
![SIH 2026](https://img.shields.io/badge/SIH%202026-SIH26157-orange)


**SOC assurance analytics for NCIIPC (SIH 2026 · problem statement SIH26157).**
SOCRIX reads the records that SOCs already keep (alerts, cases, workflow steps, escalations, asset lists), finds where security operations are weak or silent, and explains each weakness in plain words, with the exact rows behind the number.

It is **not** a SOC or SIEM. It does no real-time monitoring or collection and needs no external AI. It runs fully offline and air-gapped, on one laptop.

![SOCRIX national SOC assurance overview](docs/screenshots/audit_a_light_home.png#gh-light-mode-only)
![SOCRIX national SOC assurance overview](docs/screenshots/audit_a_dark_home.png#gh-dark-mode-only)

*Overview dashboard (demo dataset). More views in [docs/screenshots](docs/screenshots). No install needed to look around: download [`SOCRIX_report.html`](SOCRIX_report.html) and open it in any browser.*

## Quick start (about 1 minute)

```bash
python3 -m venv .venv && source .venv/bin/activate      # Python 3.11–3.13
pip install -e ".[dev]"
socrix demo          # demo data -> ingest -> score -> validation report
socrix serve         # open http://127.0.0.1:8157
socrix export        # optional: one self-contained HTML report in data/socrix_report.html
pytest -q            # 60 tests
```

Set your own pseudonymisation key before ingesting anything real: `export SOCRIX_PSEUDONYM_KEY=...` (never commit it).

## What you see

| Level | Screen | Answers |
|---|---|---|
| D0 | Overview heatmap | Which entities should NCIIPC look at first, and in which capability areas? |
| D1 | Entity page | What exactly is wrong here, in one sentence per finding? How sure is the ranking? |
| D2 | Indicator page | How does this entity compare with its peers? Is it getting better or worse? |
| D3 | Evidence table | Which alerts, cases, assets or rows make up the number? |
| D4 | Review pack | Which 20 cases should an auditor open (80% targeted, 20% random control)? CSV export. |
| D5 | Controls | Which detectors' alerts are handled worst? |
| D6 | Case timeline | Alert → acknowledge → … → close, with the case note |
| D7 | Lineage | Submission, file, row number, SHA-256 receipt, audit-chain status |

## How it works

```
submissions (CSV/JSON, any vendor dialect)
  → intake: SHA-256 receipt · dialect mapping · validation · reject log · HMAC pseudonyms · referential integrity
  → DuckDB evidence store (every row keeps submission_id, source_file, source_row)
  → 12 indicators (execution gaps, negative space, workload) mapped to the brief's 8 capability areas
  → scoring: Wilson lower bound · modified z vs peers (NIST, 3.5 ↦ concern 50) · policy rules · power mean p=3
  → findings (concern ≥ 50) · deterministic explanations · review packs · uncertainty (rank ranges)
  → hash-chained audit log · API · offline dashboard · static report
```

The "why" of every threshold is in `socrix/config.py`, and every indicator's definition is in `socrix/catalogue.yaml`. The full method is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Validation

`socrix demo` plants 12 known weaknesses in 16 demo entities (8 Power in the canonical format, 8 BFSI in a second vendor dialect) over 3 months, with 5 entities kept clean. The detection code never reads the ground truth; only `socrix bench` does, after scoring.

- Default seed (26157): 34/34 planted weaknesses found, 0 false positives, 0 findings on clean entities.
- 10 other seeds (`python scripts/seed_sweep.py 1 2 … 10`): recall 336/340 = 98.8%, 0 false positives. All 4 misses had too little evidence, e.g. 1 of 9 critical true positives not escalated.
- Every number was re-derived by an independent re-implementation: 576/576 rows match. Detection-limit curves, 0 false positives at every plant strength, 0 axe accessibility violations, and a 48-entity scale test are in docs/VALIDATION.md §5.

Detection is measured against planted weaknesses with known ground truth; a pilot on live CSE submissions is the next step. Details and the list of issues found and fixed during the build are in [docs/VALIDATION.md](docs/VALIDATION.md).

## Real data

- **Never** use real CSE or employer SOC data. It is confidential critical-infrastructure information.
- The public **Microsoft GUIDE** dataset (CDLA-Permissive-2.0) can be converted with `python -m socrix.adapters.guide GUIDE_Train.csv`. See the docstring for the download steps and the leakage warning. GUIDE has no workflow or asset records, so only part of the catalogue can be assessed; the rest shows as "insufficient evidence", never as zero.

## Design decisions and trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| **Rules and statistics, no machine-learning model deciding findings** | Every finding has to be explainable to an auditor and reproducible offline, with no external AI. | Subtler patterns a model might catch are left for a later "exploratory" lane that never raises findings on its own. |
| **Wilson 95% lower bound for every rate** | A SOC with 3 cases cannot look worse than one with 3,000 just from a small sample. | Conservative: a genuinely weak SOC with little data can stay under the finding line. |
| **Modified z-score against same-sector, same-size peers** (leave-one-out, MAD floor) | Uses the NIST outlier line (3.5), which is robust to the peer group's own outliers; the floor stops sampling noise from being called a weakness. | Needs enough comparable peers; otherwise it falls back to all sectors, then the entity's own history. |
| **Power mean (p = 3) to combine indicators** | One serious weakness is not averaged away by good scores elsewhere (the compensability problem in OECD/JRC composite-indicator guidance). | Scores are less forgiving than a plain average, by design. |
| **Missing is not zero; each weakness counted once** | Too little data shows as "insufficient evidence", and missing workflow records are a single negative-space indicator, not also execution failures. | Coverage shows 7 of the 8 capability areas, because Cyber Resilience has no indicator yet. |
| **DuckDB evidence store with lineage, hash-chained audit log, HMAC pseudonyms** | Every number links back to the file and row it came from, tampering is detectable (`socrix verify`), and identities are stable within a CSE but unlinkable across CSEs. | The pseudonym key must be held outside the repo (`SOCRIX_PSEUDONYM_KEY`). |
| **Blind validation on planted weaknesses, plus an independent re-implementation** | Detection code never reads the ground truth; 576/576 re-derived rows match. | Measured on synthetic submissions; a pilot on live CSE data is the next step. |

## Repository map

```
socrix/            engine: config, schema, simsoc, intake, audit, attack, indicators, scoring, prioritise, pipeline,
                   benchmark, api, cli, catalogue.yaml, web/ (offline dashboard), adapters/guide.py
data/reference/    MITRE ATT&CK Enterprise v19.2 reference (derived offline from the official STIX bundle)
scripts/           build_attack_ref.py (rebuild the reference), seed_sweep.py (robustness), dose_worker.py (detection limits), ui_audit.py (axe + UI checks)
tests/             60 tests (stats, intake, audit tamper, engine regressions, API, GUIDE adapter, static export)
docs/              ARCHITECTURE.md, VALIDATION.md, screenshots/, ui/ (UI_CHANGES.md, before/after screenshots)
SOCRIX_report.html pre-built `socrix export` output (single self-contained file, opens offline in any browser)
```

## Team

Built by **Team AIRIX**, Bennett University, for Smart India Hackathon 2026 (problem statement SIH26157, NTRO/NCIIPC). Team lead: [Kabir Sinha](https://github.com/kabir-sinha).

Sister project: [AIRIX](https://github.com/kabir-sinha/airix), a real-time airfare price index for MoSPI (SIH26056).

## Security

Please report vulnerabilities privately — see [SECURITY.md](SECURITY.md). Do not open public issues for security problems, and never attach real SOC data to an issue or pull request.

## Licence and data notes

All rights reserved during SIH 2026 evaluation. See [NOTICE](NOTICE) for third-party attributions.
