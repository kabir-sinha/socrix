"""B1 Intake & validation + B2 canonical evidence store (DuckDB).

For every submission file: SHA-256 receipt -> dialect mapping -> validation -> reject log
(nothing silently dropped) -> keyed pseudonymisation of people -> load with lineage columns.
"""
from __future__ import annotations
import hashlib, hmac, json
from datetime import datetime, timezone
from pathlib import Path
import duckdb
import pandas as pd
from . import config as C
from . import schema as S
from .audit import audit


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pseudonym(entity: str, value) -> str | None:
    """Keyed HMAC-SHA256: stable within a CSE, unlinkable across CSEs, irreversible without the key."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    return "p_" + hmac.new(C.PSEUDONYM_KEY, f"{entity}:{value}".encode(), hashlib.sha256).hexdigest()[:12]


def _read(path: Path) -> pd.DataFrame:
    if path.suffix == ".json":
        return pd.read_json(path, orient="records", dtype=False)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _map_alerts(df: pd.DataFrame, dialect: str) -> pd.DataFrame:
    d = S.DIALECTS[dialect]
    if d["alerts"]:
        df = df.rename(columns=d["alerts"])
    if d.get("severity_map"):
        df["severity"] = df["severity"].astype(str).map(d["severity_map"]).fillna(df["severity"])
    if d.get("disposition_map"):
        df["disposition"] = df["disposition"].map(d["disposition_map"]).fillna(df["disposition"])
    return df


def _validate(table: str, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (valid_rows, rejected_rows_with_reason)."""
    df = df.copy()
    df["reject_reason"] = ""
    for col in S.REQUIRED[table]:
        if col not in df.columns:
            df[col] = None
        bad = df[col].isna() | (df[col].astype(str).str.strip().isin(["", "None", "nan", "NaT"]))
        df.loc[bad & (df.reject_reason == ""), "reject_reason"] = f"missing_{col}"
    for tcol in [c for c in df.columns if c.endswith("_ts") or c == "ts"]:
        parsed = pd.to_datetime(df[tcol].replace({"": None}), errors="coerce", utc=True, format="mixed")
        unparsable = parsed.isna() & df[tcol].notna() & (df[tcol].astype(str).str.strip() != "")
        df.loc[unparsable & (df.reject_reason == ""), "reject_reason"] = f"bad_timestamp_{tcol}"
        df[tcol] = parsed
    if table == "alerts":
        df.loc[(df.reject_reason == "") & ~df.severity.isin(S.SEVERITIES), "reject_reason"] = "invalid_severity"
        order = df.closed_ts.notna() & df.created_ts.notna() & (df.closed_ts < df.created_ts)
        df.loc[order & (df.reject_reason == ""), "reject_reason"] = "closed_before_created"
        dup = df.alert_id.duplicated(keep="first")
        df.loc[dup & (df.reject_reason == ""), "reject_reason"] = "duplicate_alert_id"
    if table == "workflow":
        df.loc[(df.reject_reason == "") & ~df.action.isin(S.ACTIONS), "reject_reason"] = "invalid_action"
    rejected = df[df.reject_reason != ""].copy()
    valid = df[df.reject_reason == ""].drop(columns="reject_reason")
    return valid, rejected


def ingest(sub_dir: Path = C.SUBMISSIONS, db_path: Path = C.DB_PATH) -> dict:
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path)); con.execute("SET TimeZone='UTC'")
    frames = {t: [] for t in S.CANONICAL}
    receipts, rejects, profiles = [], [], []
    for period_dir in sorted(p for p in sub_dir.iterdir() if p.is_dir()):
        period = period_dir.name
        for ent_dir in sorted(p for p in period_dir.iterdir() if p.is_dir()):
            profile = json.loads((ent_dir / "profile.json").read_text())
            entity = profile["entity_id"]
            submission_id = f"{entity}:{period}"
            profiles.append(dict(profile, period=period))
            files = {"alerts": "alerts.csv", "cases": "cases.json", "workflow": "workflow.csv",
                     "escalations": "escalations.csv", "assets": "assets.csv"}
            for table, fname in files.items():
                path = ent_dir / fname
                if not path.exists():
                    continue
                df = _read(path)
                receipts.append(dict(submission_id=submission_id, entity_id=entity, period=period, file=fname,
                                     sha256=sha256(path), rows=len(df),
                                     received_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))
                if table == "alerts":
                    df = _map_alerts(df, profile.get("dialect", "canonical"))
                df["source_row"] = range(1, len(df) + 1)
                valid, rej = _validate(table, df)
                for r in rej.itertuples():
                    rejects.append(dict(submission_id=submission_id, entity_id=entity, period=period, file=fname,
                                        source_row=int(r.source_row), reason=r.reject_reason))
                valid = valid.assign(entity_id=entity, period=period, submission_id=submission_id, source_file=fname)
                if table == "alerts":
                    valid["analyst"] = [pseudonym(entity, v) for v in valid.analyst]
                if table == "workflow":
                    valid["actor"] = [pseudonym(entity, v) for v in valid.actor]
                frames[table].append(valid)
    for t, fr in frames.items():
        df = pd.concat(fr, ignore_index=True) if fr else pd.DataFrame(columns=S.CANONICAL[t])
        for c in [c for c in df.columns if c.endswith("_ts") or c == "ts"]:
            df[c] = pd.to_datetime(df[c], utc=True)
        con.register("tmp", df)
        con.execute(f"CREATE TABLE {t} AS SELECT * FROM tmp")
        con.unregister("tmp")
    meta_cols = {"receipts": ["submission_id", "entity_id", "period", "file", "sha256", "rows", "received_at"],
                 "rejects": ["submission_id", "entity_id", "period", "file", "source_row", "reason"],
                 "profiles": ["entity_id", "sector", "size_band", "dialect", "period"]}
    for name, rows in (("receipts", receipts), ("rejects", rejects), ("profiles", profiles)):
        # explicit columns: a perfectly clean submission has zero rejects and must still load
        df = pd.DataFrame(rows, columns=None if rows else meta_cols[name])
        if name == "rejects":
            df = df.astype({"submission_id": str, "entity_id": str, "period": str, "file": str, "reason": str}).astype({"source_row": "int64"})
        con.register("tmp", df); con.execute(f"CREATE TABLE {name} AS SELECT * FROM tmp"); con.unregister("tmp")
    # Referential integrity: cases must point at a valid alert; workflow/escalations at a valid case.
    for child, key, parent, pkey, fname in (("cases", "alert_id", "alerts", "alert_id", "cases.json"),
                                            ("workflow", "case_id", "cases", "case_id", "workflow.csv"),
                                            ("escalations", "case_id", "cases", "case_id", "escalations.csv")):
        con.execute(f"""INSERT INTO rejects SELECT submission_id, entity_id, period, '{fname}', source_row,
                        'orphan_{key}' FROM {child} c WHERE NOT EXISTS
                        (SELECT 1 FROM {parent} p WHERE p.{pkey} = c.{key})""")
        con.execute(f"DELETE FROM {child} c WHERE NOT EXISTS (SELECT 1 FROM {parent} p WHERE p.{pkey} = c.{key})")
    summary = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in list(S.CANONICAL) + ["receipts", "rejects"]}
    con.close()
    audit("ingest", summary)
    return summary
