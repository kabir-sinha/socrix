# SOCRIX — notes for Claude Code

SIH 2026 · SIH26157 (NTRO/NCIIPC). SOC assurance analytics over submitted SOC records. Team AIRIX.

## Hard rules (never break)
- **Offline and air-gapped.** No network calls at runtime, no CDN in `socrix/web/`, no external AI/LLM, no telemetry.
- **No real CSE/employer SOC data, ever.** Use SimSOC (`socrix demo`) or public Microsoft GUIDE via `socrix/adapters/guide.py`.
- **Never commit `SOCRIX_PSEUDONYM_KEY`** or anything in `data/` except `data/reference/`.
- **Missing ≠ zero.** Too little data → status "insufficient evidence", concern `None`.
- **Each weakness counted once.** Execution-gap indicators judge only cases with workflow records; missing records belong to NS-03.
- **Blind validation.** Only `benchmark.py` may read `data/ground_truth.json`.
- **Every threshold lives in `socrix/config.py`**; every indicator definition in `socrix/catalogue.yaml`.

## Commands
```bash
pip install -e ".[dev]"
pytest -q                          # must stay green (60+ tests)
socrix demo && socrix serve        # http://127.0.0.1:8157
python scripts/seed_sweep.py 1 2 3 4 5 6 7 8 9 10   # robustness: expect ~99% recall, 0 FP
socrix export                      # single-file HTML report
python scripts/independent/compare.py   # engine vs blind re-implementation: must be 0 mismatches
```

If you change a formula on purpose, update the spec (docs/ARCHITECTURE.md) AND scripts/independent/recalc.py in the
same commit, and say so — never silently edit the independent script to make a failing comparison pass.

## Adding an indicator (checklist)
1. `catalogue.yaml` entry: name, area, gap, unit, `higher_is_worse`, `mad_floor`, `min_n`, track, brief ref, `sample_cases`, template, `rate: true` if it is a proportion.
2. Compute it in `indicators.compute_all` with `_res(k, n, value, display, evidence)`. Rates use `wilson_lower`. Evidence must be non-empty whenever it can become a finding.
3. If policy-tracked, add the rule to `scoring._policy` and put its threshold in `config.py`.
4. Plant a matching archetype in `simsoc.py` (and clean controls stay clean), then run `pytest` and the seed sweep: 0 false positives on clean entities.
5. Add a regression test and a line in `docs/VALIDATION.md`.

## Layout
`socrix/` config · schema · simsoc · intake · audit · attack · indicators · scoring · prioritise · pipeline · benchmark · api · cli · web/ · adapters/
`docs/` ARCHITECTURE.md (2-page architecture deliverable) · VALIDATION.md
