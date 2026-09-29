"""SimSOC — synthetic Supervisory Data Submissions with planted, labelled weaknesses.

Generates 16 CSEs (8 Power, 8 BFSI) x 3 monthly periods. Each weakness archetype is planted in a
known entity/period and recorded in ground_truth.json. Detection code never reads this file —
only socrix.benchmark does (blind-evaluation discipline, Blueprint Part H/V1).

Two submission dialects are emitted (canonical CSV and a vendor-style export with renamed
fields and numeric severities) to exercise the mapping layer (FR2).
"""
from __future__ import annotations
import json, random, shutil
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
from . import config as C
from . import attack

PERIODS = ["2026-06", "2026-07", "2026-08"]
_PER_SECTOR = int(__import__("os").environ.get("SOCRIX_ENTITIES_PER_SECTOR", "8"))   # scale tests only
POWER = [f"PWR-{i:02d}" for i in range(1, _PER_SECTOR + 1)]
BFSI = [f"BFS-{i:02d}" for i in range(1, _PER_SECTOR + 1)]
ENTITIES = POWER + BFSI

# Planted archetypes: (entity, periods or None=all, archetype, indicators that should fire)
PLANTS = [
    ("PWR-03", None, "A1 alerts closed without investigation", ["EG-01"]),
    ("PWR-03", None, "A3 critical true-positives not escalated", ["EG-03"]),
    ("BFS-05", ["2026-08"], "A2 implausibly fast closures", ["EG-02"]),
    ("BFS-02", None, "A4 template-driven investigation notes", ["EG-04"]),
    ("PWR-06", None, "A5 repeat alerts without remediation", ["EG-05"]),
    ("BFS-07", None, "A6 FP/BP closures without enrichment", ["EG-07"]),
    ("PWR-05", None, "A7 silent critical assets", ["NS-01"]),
    ("BFS-04", None, "A8 expected ATT&CK tactics absent", ["NS-02"]),
    ("PWR-08", None, "A9 cases closed with no workflow records", ["NS-03"]),
    ("BFS-06", None, "A10 unexpectedly low activity", ["NS-05"]),   # NS-01 may co-fire (graded as related)
    ("PWR-02", None, "A11 poor submission quality", ["NS-08"]),
    ("BFS-08", None, "A12 implausible analyst workload", ["WL-01"]),
]
CLEAN = ["PWR-01", "PWR-04", "PWR-07", "BFS-01", "BFS-03"]

# Plant strength multiplier for detection-limit studies (1.0 = default demo data, byte-identical).
DOSE = float(__import__("os").environ.get("SOCRIX_DOSE", "1.0"))

NOTE_TEMPLATES = [
    "Reviewed process tree on {asset}; parent {h1} spawned {h2}; hash not on allow-list; isolated host and raised ticket.",
    "Checked sign-in events for {user} on {asset}; source {h1} matched corporate VPN pool; user confirmed activity; benign.",
    "Correlated proxy logs for {asset}; domain {h1} first seen 2 days ago; blocked at gateway; notified owner.",
    "Scheduled task {h1} on {asset} created by admin {user}; matched change record {h2}; benign positive.",
    "Sandbox detonation of {h1} from {asset} returned clean; no lateral movement in 24h window; closed.",
    "Lateral SMB from {asset} to {h1} traced to backup job {h2}; confirmed with infra team; benign.",
    "Credential dump signature on {asset}; LSASS access by {h1}; reset {user} credentials; escalated to IR.",
]
BOILERPLATE = "Alert reviewed. No malicious activity observed. Closing as per SOP."
TIERS = ["L2", "IR", "CISO"]


def _technique_pool(rng: random.Random) -> list[str]:
    """Pick ~3 real techniques per commonly-observed ATT&CK v19.2 tactic."""
    wanted = ["TA0001", "TA0002", "TA0003", "TA0004", "TA0005", "TA0006", "TA0007", "TA0008", "TA0011", "TA0010", "TA0040"]
    pool = []
    techs = attack.ref()["techniques"]
    for tac in wanted:
        cands = [t["id"] for t in techs if tac in t["tactics"] and "." not in t["id"] and t["data_components"]]
        rng.shuffle(cands)
        # keep techniques whose *only* tactic is this one, so missing-tactic plants are clean
        solo = [c for c in cands if attack.tactics_for(c) == [tac]]
        pool += (solo or cands)[:3]
    return pool


def _plant(entity: str, period: str) -> set[str]:
    return {a.split(" ")[0] for e, per, a, _ in PLANTS if e == entity and (per is None or period in per)}


def _entity_period(entity: str, period: str, pool: list[str], seed: int) -> dict[str, pd.DataFrame]:
    rng = random.Random(seed); nrng = np.random.default_rng(seed)
    plants = _plant(entity, period)
    sector = "Power" if entity.startswith("PWR") else "BFSI"
    envs = ["IT", "OT"] if sector == "Power" else ["IT", "Cloud"]
    crit = [f"{entity}-C{j:03d}" for j in range(40)]
    normal = [f"{entity}-A{j:04d}" for j in range(600)]
    assets = pd.DataFrame({"asset_id": crit + normal, "entity_id": entity,
                           "criticality": ["critical"] * 40 + ["normal"] * 600,
                           "environment": [envs[j % 2] for j in range(640)],
                           "asset_type": ["server"] * 40 + ["endpoint"] * 600})
    silent = set(crit[:max(1, round(3 * DOSE))]) if "A7" in plants else set()
    live_crit = [a for a in crit if a not in silent]
    scale = (1 - 0.55 * DOSE) if "A10" in plants else 1.0
    n_alerts = int(nrng.poisson(900 * scale))
    tech_pool = pool
    if "A8" in plants:  # remove Credential Access (TA0006) and Lateral Movement (TA0008)
        tech_pool = [t for t in pool if not set(attack.tactics_for(t)) & {"TA0006", "TA0008"}]
    analysts = [f"analyst-{i:02d}" for i in range(10)]
    detectors = [f"DET-{i:03d}" for i in range(25)]
    start = datetime.strptime(period + "-01", "%Y-%m-%d")
    alerts, cases, wf, esc = [], [], [], []
    # recurring (asset, technique) pairs: baseline ~15 pairs, remediated 85% of the time
    recur_pairs = [(rng.choice(normal), rng.choice(tech_pool)) for _ in range(15)]
    extra_pairs = [(rng.choice(normal), rng.choice(tech_pool)) for _ in range(round(25 * DOSE))] if "A5" in plants else []
    plan = []
    for pair in recur_pairs:
        rem = rng.random() < 0.85
        plan += [(pair, rem)] * 4
    for pair in extra_pairs:
        plan += [(pair, False)] * 4
    total = max(n_alerts, len(plan))
    for k in range(total):
        aid = f"{entity}-{period}-AL{k:05d}"
        if k < len(plan):
            (asset, tech), remediated = plan[k]
            sev = "high"
        else:
            asset = rng.choice(live_crit) if rng.random() < 0.28 else rng.choice(normal)
            tech = rng.choice(tech_pool)
            sev = rng.choices(["low", "medium", "high", "critical"], [0.45, 0.33, 0.16, 0.06])[0]
            remediated = None
        disp = rng.choices(["TP", "BP", "FP"], [0.2, 0.45, 0.35])[0]
        created = start + timedelta(minutes=rng.randrange(0, 29 * 24 * 60))
        hc = sev in ("high", "critical")
        ack_only = hc and ("A1" in plants and rng.random() < 0.40 * DOSE or rng.random() < 0.03)
        no_wf = "A9" in plants and rng.random() < 0.30 * DOSE
        fp_no_enrich = disp in ("BP", "FP") and (("A6" in plants and rng.random() < 0.55 * DOSE) or rng.random() < 0.05)
        if ack_only:
            ttc = rng.randint(2, 6)
        elif hc and "A2" in plants and (DOSE >= 1 or rng.random() < DOSE):
            ttc = rng.randint(3, 9)
        else:
            ttc = int(max(20, nrng.lognormal(np.log(140 if hc else 90), 0.5)))
        closed = created + timedelta(minutes=ttc)
        analyst = "analyst-00" if ("A12" in plants and rng.random() < 0.45 * DOSE) else rng.choice(analysts)
        alerts.append(dict(alert_id=aid, entity_id=entity, created_ts=created, closed_ts=closed, severity=sev,
                           technique_id=tech, detector_id=rng.choice(detectors), asset_id=asset,
                           disposition=disp, analyst=analyst))
        cid = aid.replace("-AL", "-CS")
        template = "A4" in plants and rng.random() < 0.50 * DOSE or rng.random() < 0.03
        note = BOILERPLATE if template else rng.choice(NOTE_TEMPLATES).format(
            asset=asset, user=f"u{rng.randrange(9999)}", h1=f"{rng.getrandbits(40):x}", h2=f"{rng.getrandbits(32):x}")
        rc = ("RC-" + str(rng.randrange(1, 12))) if (disp == "TP" and remediated is not False and rng.random() < 0.6) else ""
        cases.append(dict(case_id=cid, entity_id=entity, alert_id=aid, opened_ts=created, closed_ts=closed, note=note, root_cause_code=rc))
        if no_wf:
            continue
        t = created + timedelta(minutes=1)
        wf.append(dict(case_id=cid, ts=t, action="acknowledged", actor=analyst))
        steps = []
        if not ack_only and not (fp_no_enrich and disp in ("BP", "FP")):
            steps += ["enrichment", "analysis"]
        if disp == "TP" and remediated is not False and not ack_only:
            steps += ["containment"] if rng.random() < 0.5 else ["remediation"]
        if remediated is True:
            steps += ["remediation"]
        for s in steps:
            t = t + timedelta(minutes=max(1, ttc // (len(steps) + 2)))
            wf.append(dict(case_id=cid, ts=t, action=s, actor=analyst))
        if sev == "critical" and disp == "TP":
            miss = ("A3" in plants and rng.random() < 0.60 * DOSE) or rng.random() < 0.03
            if not miss:
                esc.append(dict(case_id=cid, ts=t + timedelta(minutes=1), to_tier=rng.choice(TIERS)))
                wf.append(dict(case_id=cid, ts=t + timedelta(minutes=1), action="escalated", actor=analyst))
        wf.append(dict(case_id=cid, ts=closed, action="closed", actor=analyst))
    alerts = pd.DataFrame(alerts)
    if "A11" in plants:  # corrupt ~10% of rows (closed before created / missing severity)
        idx = alerts.sample(frac=0.10 * DOSE, random_state=seed).index
        half = len(idx) // 2
        alerts.loc[idx[:half], "closed_ts"] = alerts.loc[idx[:half], "created_ts"] - timedelta(hours=2)
        alerts.loc[idx[half:], "severity"] = None
    return {"alerts": alerts, "cases": pd.DataFrame(cases), "workflow": pd.DataFrame(wf),
            "escalations": pd.DataFrame(esc, columns=["case_id", "ts", "to_tier"]), "assets": assets,
            "profile": {"entity_id": entity, "sector": sector, "size_band": "Large", "declared_24x7": True,
                        "dialect": "canonical" if sector == "Power" else "vendorB"}}


def _write_vendor_b(alerts: pd.DataFrame, path: Path) -> None:
    rev_sev = {"low": "1", "medium": "2", "high": "3", "critical": "4"}
    rev_disp = {"TP": "TruePositive", "BP": "BenignPositive", "FP": "FalsePositive"}
    out = pd.DataFrame({
        "AlertID": alerts.alert_id, "Org": alerts.entity_id, "Created": alerts.created_ts, "Closed": alerts.closed_ts,
        "Sev": alerts.severity.map(rev_sev), "MitreTechnique": alerts.technique_id, "RuleID": alerts.detector_id,
        "AssetID": alerts.asset_id, "Verdict": alerts.disposition.map(rev_disp), "AnalystName": alerts.analyst})
    out.to_csv(path, index=False)


def generate(out_dir: Path = C.SUBMISSIONS, seed: int = C.RANDOM_SEED) -> Path:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    rng = random.Random(seed)
    pool = _technique_pool(rng)
    for pi, period in enumerate(PERIODS):
        for ei, entity in enumerate(ENTITIES):
            d = _entity_period(entity, period, pool, seed + pi * 1000 + ei)
            folder = out_dir / period / entity
            folder.mkdir(parents=True, exist_ok=True)
            if d["profile"]["dialect"] == "vendorB":
                _write_vendor_b(d["alerts"], folder / "alerts.csv")
            else:
                d["alerts"].to_csv(folder / "alerts.csv", index=False)
            d["cases"].to_json(folder / "cases.json", orient="records", date_format="iso")
            d["workflow"].to_csv(folder / "workflow.csv", index=False)
            d["escalations"].to_csv(folder / "escalations.csv", index=False)
            d["assets"].to_csv(folder / "assets.csv", index=False)
            (folder / "profile.json").write_text(json.dumps(d["profile"]))
    truth = {"generator": "SimSOC", "seed": seed, "periods": PERIODS, "clean_entities": CLEAN,
             "technique_pool": pool,
             "plants": [{"entity": e, "periods": per or PERIODS, "archetype": a, "indicators": ind} for e, per, a, ind in PLANTS]}
    (out_dir.parent / "ground_truth.json").write_text(json.dumps(truth, indent=1))
    return out_dir
