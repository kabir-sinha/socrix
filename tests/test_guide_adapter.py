"""Regressions found while wiring the GUIDE adapter: a clean submission (0 rejects) crashed ingest, and data with
no workflow records crashed the engine / made EG-05 look like 'no remediation' when nothing was recorded at all."""
import os, shutil, tempfile, importlib
from pathlib import Path
import numpy as np
import pandas as pd


def test_guide_like_submission_end_to_end(built, tmp_path):
    from socrix.adapters import guide
    from socrix import intake, pipeline, indicators, scoring
    n = 3000
    df = pd.DataFrame(dict(OrgId=np.repeat([1, 2, 3, 4, 5, 6], n // 6), IncidentId=np.arange(n) // 3, AlertId=range(n),
                           Timestamp=["2024-06-0%dT10:00:00.000Z" % (i % 9 + 1) for i in range(n)], DetectorId=np.arange(n) % 20,
                           MitreTechniques=["T1566;T1078", "T1021", ""] * 1000,
                           IncidentGrade=["TruePositive", "BenignPositive", "FalsePositive"] * 1000, DeviceId=np.arange(n) % 50))
    df.to_csv(tmp_path / "g.csv", index=False)
    subs = guide.convert(tmp_path / "g.csv", tmp_path / "subs", orgs=6, min_alerts=100)
    db = tmp_path / "g.duckdb"
    s = intake.ingest(subs, db)                               # must not crash with zero rejects
    assert s["alerts"] == n and s["rejects"] == 0
    rows = indicators.compute_all(pipeline.load(db))         # must not crash with zero workflow rows
    by = {(r["entity_id"], r["indicator"]): r for r in rows}
    for org in ("GDE-00001", "GDE-00006"):
        assert by[(org, "EG-05")]["n"] == 0                  # nothing recorded -> cannot judge remediation
        assert by[(org, "EG-01")]["n"] == 0


def test_guide_rejects_wrong_header(tmp_path):
    from socrix.adapters import guide
    pd.DataFrame(dict(a=[1])).to_csv(tmp_path / "bad.csv", index=False)
    try:
        guide.convert(tmp_path / "bad.csv", tmp_path / "o")
        assert False, "should have stopped"
    except SystemExit as e:
        assert "GUIDE columns not found" in str(e)
