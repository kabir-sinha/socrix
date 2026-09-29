# SOCRIX: Architecture (2 pages)

## 1. Problem → design constraints (SIH26157)
NCIIPC needs to know whether each CSE's SOC is actually working, not just whether it exists. It has to do this from submitted records, with no live access, no SIEM, no real-time collection, and no external AI. Every conclusion must be explainable and traceable, and must hold up against expert manual review.

This gives SOCRIX five rules:
1. **Evidence first.** Every number links to its rows.
2. **Missing is not zero.** Too little data means "insufficient evidence".
3. **Each weakness is counted once.** Missing records are negative space (NS-03); they are not also execution failures.
4. **Compare like with like.** Peers share sector and size, with leave-one-out.
5. **Fully offline and deterministic.**

## 2. Components

| Block | Module | What it guarantees |
|---|---|---|
| B1 Intake | `intake.py`, `schema.py` | SHA-256 receipt per file; vendor dialect → canonical; validation with a reason per rejected row; nothing silently dropped (submitted = loaded + rejected, tested); referential integrity (orphans → reject log); HMAC-SHA256 pseudonyms (stable within a CSE, unlinkable across CSEs) |
| B2 Evidence store | DuckDB (`data/socrix.duckdb`) | Lineage columns on every row (`submission_id`, `source_file`, `source_row`); UTC everywhere |
| B3 Indicators | `indicators.py`, `catalogue.yaml` | 12 MVP indicators, each with direction, unit, minimum n, track (peer / peer+policy) and brief reference |
| B4 Reference | `attack.py`, `data/reference/` | ATT&CK Enterprise v19.2: 15 tactics (incl. TA0005 Stealth, TA0112 Defense Impairment); technique → tactics; sub-technique falls back to base |
| B5 Scoring | `scoring.py`, `stats.py` | See §3 |
| B6 Uncertainty | `scoring.rank_stability` | Dirichlet(1) weights × p ∈ {1,2,3,6} → rank range, P(rank 1), P(top 3) |
| B7 Explanations | `prioritise.explain` | Fixed templates: count, conservative rate, peer median, modified z, baseline, policy rule |
| B8 Prioritisation | `prioritise.py` | Review pack (80% targeted by concern, 20% random control) + checklist; weakest-handled detectors |
| B9 Audit | `audit.py` | Hash-chained JSONL (ingest, score runs, exports); `socrix verify`; tamper test |
| B10 Delivery | `api.py`, `web/`, `cli.py` | Read-only API, D0–D7 dashboard with no CDN, single-file static report |
| Validation | `benchmark.py`, `simsoc.py` | Blind grading against planted ground truth; multi-seed sweep |

## 3. Scoring method
- **Rates:** Wilson 95% lower bound, so small samples can't look extreme.
- **Peer comparison:** oriented modified z, M = 0.6745·(x − median)/MAD (Iglewicz and Hoaglin; NIST/SEMATECH), against same-sector, same-size peers, leave-one-out; a peer counts only if its own sample meets the indicator's minimum n. The fallback is all sectors, then the entity's own history. MAD is floored at max(catalogue floor, binomial standard error at the peer median for this n), so a gap smaller than sampling noise is never an outlier.
- **Concern:** 100·clip(M, 0, 7)/7, so M = 3.5 (the NIST outlier line) maps to 50.
- **Policy track:** concern = max(peer, policy).
  - **NS-01 (silent critical assets):** the empirical share of silent critical assets among same-sector peers across periods, each peer-period's silent count capped at 2, with a Jeffreys prior. The binomial tail P(≥ k silent of n) must be < 1%. Empirical rather than Poisson, because alert counts are over-dispersed.
  - **NS-02:** 50 + 25·(k − 1) per expected tactic absent.
  - **EG-03:** 50 if the conservative non-escalation rate is > 10%.
  - **NS-08:** 60 if the conservative reject rate is > 5%.
- **Aggregation:** power mean with p = 3 over indicators into areas, and over areas into the SAI. This limits compensability (OECD/JRC composite-indicator guidance), so one serious weakness is not averaged away.
- **Findings and coverage:** a finding is concern ≥ 50. Coverage is the number of the 8 capability areas with assessed evidence; Cyber Resilience has no MVP indicator, so it shows as 7/8.

## 4. Indicator catalogue (MVP 12)

| ID | Area | Measures |
|---|---|---|
| EG-01 | Investigation | High/critical closed with no investigative step* |
| EG-02 | Investigation | Implausibly fast closure (log10 median minutes) |
| EG-03 | Escalation | Critical TPs with no escalation record* |
| EG-04 | Operational Discipline | Near-identical notes on different assets (TF-IDF cosine ≥ 0.9) |
| EG-05 | Incident Response | Recurring asset+technique (≥ 3) with no remediation or root cause* |
| EG-07 | Investigation | FP/BP closures with no enrichment* |
| NS-01 | Threat Detection | Silent critical assets |
| NS-02 | Threat Detection | ATT&CK tactics seen by ≥ 70% of peers but absent |
| NS-03 | Investigation | Cases with no workflow records |
| NS-05 | Security Operations | Alerts per critical asset (low = worse) |
| NS-08 | Governance and Oversight | Rejected submission rows |
| WL-01 | Security Operations | Busiest analyst's closures per active day |

\* Judged only on cases that have workflow records. Cases with no records at all are NS-03.

## 5. Security and deployment
- Localhost bind by default; read-only API; no outbound calls; no CDN; no AI model.
- The pseudonym key comes from `SOCRIX_PSEUDONYM_KEY` (held by NCIIPC), never from the repo.
- Everything runs on one laptop. On a MacBook Pro (Apple M5), 41k alerts and 166k workflow rows score in 2.3 seconds; 3× that volume (48 CSEs) scores in under 9 seconds, with peak memory under 1 GB for the full run. On a 2-CPU cloud workspace the same runs take about 7.5 and 27 seconds (docs/VALIDATION.md §5.4).

## 6. Roadmap (post-MVP)
- Remaining catalogue items: Cyber Resilience indicators (backup/restore drills, DR tests) and exercise-evidence ingestion.
- Isolation Forest and change-point lanes, flagged as "exploratory", never used for findings without a rule.
- Reviewer feedback loop: review-pack CSV verdicts → precision per indicator → threshold tuning.
- Multi-period trend alerts; per-sector catalogues (Power OT versus BFSI).
