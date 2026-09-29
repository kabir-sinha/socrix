"""Adapter: Microsoft GUIDE (Kaggle 'microsoft-security-incident-prediction', CDLA-Permissive-2.0) -> SOCRIX submissions.

GUIDE is real, anonymised SOC triage data (6.1k orgs). It has alerts, MITRE techniques and incident grades
(TruePositive / BenignPositive / FalsePositive) but NO workflow steps, escalations or asset inventory, so it
exercises intake, dialect mapping and the technique/disposition indicators (NS-02, EG-03 partially), not the full catalogue.

Download it yourself on a machine with internet (the build workspace cannot reach Kaggle):
    kaggle datasets download -d Microsoft/microsoft-security-incident-prediction
Then:
    python -m socrix.adapters.guide GUIDE_Train.csv --orgs 16 --out data/submissions_guide
    socrix ingest --submissions data/submissions_guide && socrix score

Leakage warning: GUIDE rows of one incident share its grade. Never split train/test by row; group by (OrgId, IncidentId).
Column names below are those published with the dataset; the adapter checks them and stops with a clear message if they differ.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

NEEDED = ["OrgId", "IncidentId", "AlertId", "Timestamp", "DetectorId", "MitreTechniques", "IncidentGrade"]
GRADE = {"TruePositive": "TP", "BenignPositive": "BP", "FalsePositive": "FP"}


def convert(csv: Path, out: Path, orgs: int = 16, min_alerts: int = 300) -> Path:
    head = pd.read_csv(csv, nrows=0).columns.tolist()
    missing = [c for c in NEEDED if c not in head]
    if missing:
        raise SystemExit(f"GUIDE columns not found: {missing}. Header was: {head[:25]} ... — update NEEDED/mapping.")
    df = pd.read_csv(csv, usecols=NEEDED + [c for c in ("DeviceId", "Category") if c in head], low_memory=False)
    df["Timestamp"] = pd.to_datetime(df.Timestamp, utc=True, errors="coerce")
    df["period"] = df.Timestamp.dt.strftime("%Y-%m")
    period = df.period.value_counts().idxmax()                    # busiest month, one period per org
    top = df[df.period == period].groupby("OrgId").size()
    chosen = top[top >= min_alerts].sort_values(ascending=False).head(orgs).index
    for org in chosen:
        g = df[(df.OrgId == org) & (df.period == period)].drop_duplicates("AlertId")
        ent = f"GDE-{int(org):05d}"
        d = out / period / ent
        d.mkdir(parents=True, exist_ok=True)
        tech = g.MitreTechniques.fillna("").astype(str).str.split(";").str[0]
        alerts = pd.DataFrame(dict(
            alert_id=[f"{ent}-{a}" for a in g.AlertId], entity_id=ent, created_ts=g.Timestamp.dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            closed_ts="", severity="high", technique_id=tech, detector_id=g.DetectorId.astype(str),
            asset_id=g.get("DeviceId", pd.Series("unknown", index=g.index)).astype(str),
            disposition=g.IncidentGrade.map(GRADE).fillna(""), analyst=""))
        alerts.to_csv(d / "alerts.csv", index=False)
        (d / "cases.json").write_text("[]")
        for f, cols in (("workflow.csv", "case_id,ts,action,actor"), ("escalations.csv", "case_id,ts,to_tier"),
                        ("assets.csv", "asset_id,entity_id,criticality,environment,asset_type")):
            (d / f).write_text(cols + "\n")
        (d / "profile.json").write_text(json.dumps(dict(entity_id=ent, sector="GUIDE", size_band="Org", dialect="canonical",
                                                        source="Microsoft GUIDE (CDLA-Permissive-2.0)")))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv"); ap.add_argument("--orgs", type=int, default=16); ap.add_argument("--out", default="data/submissions_guide")
    a = ap.parse_args()
    print("written to", convert(Path(a.csv), Path(a.out), a.orgs))
