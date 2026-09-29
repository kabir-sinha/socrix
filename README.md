# SOCRIX

[![Tests](https://github.com/kabir-sinha/socrix/actions/workflows/tests.yml/badge.svg)](https://github.com/kabir-sinha/socrix/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.13-3776AB?logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/runs-fully%20offline%20%C2%B7%20air--gapped-2ea44f)
![SIH 2026](https://img.shields.io/badge/SIH%202026-SIH26157-orange)

**SOC assurance analytics for NCIIPC (SIH 2026 · SIH26157, NTRO/NCIIPC)**

SOCRIX reads the records security operations centres already keep (alerts, cases, workflow steps, escalations, asset lists), finds where operations are weak or silent, and explains each weakness in plain words, with the exact rows behind the number. It is not a SOC or SIEM: it runs fully offline and air-gapped on one laptop, with no external AI.

![SOCRIX national SOC assurance overview](docs/screenshots/audit_a_light_home.png#gh-light-mode-only)
![SOCRIX national SOC assurance overview](docs/screenshots/audit_a_dark_home.png#gh-dark-mode-only)

*Overview dashboard (demo dataset). To look around without installing anything, download [`SOCRIX_report.html`](SOCRIX_report.html) and open it in a browser.*

## What it does

- **Ingests** submissions in any vendor format, with a SHA-256 receipt, validation and a reject log for every file
- **Measures** 12 indicators across the brief's 8 capability areas, comparing each entity with its peers
- **Explains** every finding in one sentence, down to the alerts, cases and rows behind it
- **Prioritises** audits with review packs of the cases an auditor should open first
- **Proves** its own integrity with a hash-chained audit log that detects tampering

## How it works

```
Submissions → intake & validation → DuckDB evidence store → 12 indicators → peer scoring → findings & explanations → dashboard, API, report
```

Python · pandas · DuckDB · scikit-learn · FastAPI · vanilla JS (no CDN) · pytest. Full method in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Validation

The demo plants 12 known weaknesses in 16 entities from two sectors and two vendor formats, with 5 entities kept clean. The detection code never sees the ground truth.

- **34/34** planted weaknesses found on the default seed, with **0 false positives**
- **98.8% recall** (336/340) across 10 further seeds, still 0 false positives
- **576/576** numbers matched by an independent re-implementation

Measured on synthetic submissions; a pilot on live data is the next step. Details in [docs/VALIDATION.md](docs/VALIDATION.md).

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

## Quick start

<details>
<summary>Setup and commands (about 1 minute)</summary>

```bash
python3 -m venv .venv && source .venv/bin/activate      # Python 3.11–3.13
pip install -e ".[dev]"
socrix demo      # generate demo data, ingest, score
socrix serve     # open the dashboard
pytest -q
```

Never use real CSE or employer SOC data.

</details>

## Repository map

```
socrix/            engine, API, CLI and offline dashboard
data/reference/    MITRE ATT&CK Enterprise v19.2 reference
scripts/           robustness, detection-limit and UI checks
tests/             automated tests
docs/              architecture, validation, screenshots
```

## Team

Built by **Team AIRIX**, Bennett University, for Smart India Hackathon 2026 (SIH26157, NTRO/NCIIPC). Team lead: [Kabir Sinha](https://github.com/kabir-sinha).

Also by Team AIRIX: [AIRIX](https://github.com/kabir-sinha/airix), a real-time airfare price index for MoSPI (SIH26056).

## Security

Please report vulnerabilities privately — see [SECURITY.md](SECURITY.md). Never attach real SOC data to an issue or pull request.

## Licence

All rights reserved during SIH 2026 evaluation. See [NOTICE](NOTICE) for third-party attributions.
