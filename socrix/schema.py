"""Canonical data model (OCSF-aligned in spirit) + per-CSE mapping dialects.

The Supervisory Data Submission (one per CSE per period) contains these tables.
Only `alerts` and `cases` are mandatory; others degrade gracefully (indicators return
'insufficient evidence' instead of 0).
"""
from __future__ import annotations

SEVERITIES = ["low", "medium", "high", "critical"]
DISPOSITIONS = ["TP", "BP", "FP"]
ACTIONS = ["acknowledged", "enrichment", "analysis", "containment", "remediation", "escalated", "closed"]
INVESTIGATIVE = {"enrichment", "analysis", "containment", "remediation"}
REMEDIAL = {"containment", "remediation"}

CANONICAL = {
    "alerts": ["alert_id", "entity_id", "created_ts", "closed_ts", "severity", "technique_id",
               "detector_id", "asset_id", "disposition", "analyst"],
    "cases": ["case_id", "entity_id", "alert_id", "opened_ts", "closed_ts", "note", "root_cause_code"],
    "workflow": ["case_id", "ts", "action", "actor"],
    "escalations": ["case_id", "ts", "to_tier"],
    "assets": ["asset_id", "entity_id", "criticality", "environment", "asset_type"],
}
REQUIRED = {
    "alerts": ["alert_id", "entity_id", "created_ts", "severity"],
    "cases": ["case_id", "alert_id"],
    "workflow": ["case_id", "ts", "action"],
    "escalations": ["case_id", "ts"],
    "assets": ["asset_id", "criticality"],
}

# Mapping dialects: vendor field -> canonical field. A new CSE is onboarded by adding a dialect.
DIALECTS = {
    "canonical": {"alerts": {}, "severity_map": None},
    "vendorB": {
        "alerts": {"AlertID": "alert_id", "Org": "entity_id", "Created": "created_ts", "Closed": "closed_ts",
                   "Sev": "severity", "MitreTechnique": "technique_id", "RuleID": "detector_id",
                   "AssetID": "asset_id", "Verdict": "disposition", "AnalystName": "analyst"},
        "severity_map": {"1": "low", "2": "medium", "3": "high", "4": "critical"},
        "disposition_map": {"TruePositive": "TP", "BenignPositive": "BP", "FalsePositive": "FP"},
    },
}
