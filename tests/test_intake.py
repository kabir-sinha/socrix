import json
import duckdb
import pandas as pd
from socrix import intake, schema as Sch


def test_validate_rejects_with_reason_not_silently():
    df = pd.DataFrame(dict(alert_id=["a", "b", "c", "c"], entity_id="X", created_ts=["2026-08-01T00:00:00Z"] * 4,
                           closed_ts=["2026-08-01T01:00:00Z", "2026-07-01T00:00:00Z", "", "2026-08-01T02:00:00Z"],
                           severity=["high", "high", "banana", "low"], technique_id="T1566", detector_id="D",
                           asset_id="A", disposition="TP", analyst="u", source_row=[1, 2, 3, 4]))
    valid, rej = intake._validate("alerts", df)
    assert "reject_reason" in rej.columns                         # regression: '_reason' was renamed by itertuples
    reasons = dict(zip(rej.source_row, rej.reject_reason))
    assert reasons == {2: "closed_before_created", 3: "invalid_severity", 4: "duplicate_alert_id"}
    assert list(valid.alert_id) == ["a"]


def test_pseudonym_stable_keyed_and_entity_scoped():
    a = intake.pseudonym("E1", "alice")
    assert a == intake.pseudonym("E1", "alice") and a != intake.pseudonym("E2", "alice")
    assert a.startswith("p_") and "alice" not in a
    assert intake.pseudonym("E1", None) is None


def test_referential_integrity_and_counts(built):
    C = built["C"]
    con = duckdb.connect(str(C.DB_PATH), read_only=True)
    q = lambda s: con.execute(s).fetchone()[0]
    assert q("SELECT count(*) FROM cases c WHERE NOT EXISTS (SELECT 1 FROM alerts a WHERE a.alert_id=c.alert_id)") == 0
    assert q("SELECT count(*) FROM workflow w WHERE NOT EXISTS (SELECT 1 FROM cases c WHERE c.case_id=w.case_id)") == 0
    assert q("SELECT count(*) FROM escalations e WHERE NOT EXISTS (SELECT 1 FROM cases c WHERE c.case_id=e.case_id)") == 0
    # every submitted alert row is either loaded or in the reject log (nothing silently dropped)
    submitted = q("SELECT sum(rows) FROM receipts WHERE file='alerts.csv'")
    loaded = q("SELECT count(*) FROM alerts")
    rejected = q("SELECT count(*) FROM rejects WHERE file='alerts.csv'")
    assert submitted == loaded + rejected
    # analysts are pseudonymised
    assert q("SELECT count(*) FROM alerts WHERE analyst NOT LIKE 'p_%'") == 0
    con.close()


def test_vendor_dialect_mapped(built):
    C = built["C"]
    con = duckdb.connect(str(C.DB_PATH), read_only=True)
    sev = {r[0] for r in con.execute("SELECT DISTINCT severity FROM alerts WHERE entity_id LIKE 'BFS-%'").fetchall()}
    disp = {r[0] for r in con.execute("SELECT DISTINCT disposition FROM alerts WHERE entity_id LIKE 'BFS-%'").fetchall()}
    con.close()
    assert sev <= set(Sch.SEVERITIES) and disp <= set(Sch.DISPOSITIONS)


def test_timestamps_survive_non_utc_host(built):   # regression: DuckDB 'Asia/Calcutta' ZoneInfoNotFoundError
    from socrix import pipeline
    t = pipeline.load(built["C"].DB_PATH)
    assert str(t["alerts"].created_ts.dt.tz) == "UTC"
