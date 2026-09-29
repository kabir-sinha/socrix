"""Central configuration. Every threshold used anywhere in SOCRIX lives here (auditable, versioned)."""
from __future__ import annotations
from pathlib import Path
import os

ROOT = Path(os.environ.get("SOCRIX_HOME", Path(__file__).resolve().parent.parent))
DATA = ROOT / "data"
SUBMISSIONS = DATA / "submissions"
REFERENCE = DATA / "reference"
DB_PATH = DATA / "socrix.duckdb"
RESULTS = DATA / "results.json"
AUDIT_LOG = DATA / "audit_log.jsonl"
ATTACK_REF = REFERENCE / "attack_ref_v19_2.json"

# Pseudonymisation key (in deployment this is held by NCIIPC, never shipped with code).
PSEUDONYM_KEY = os.environ.get("SOCRIX_PSEUDONYM_KEY", "demo-key-change-me").encode()

ENGINE_VERSION = "0.1.0"
CATALOGUE_VERSION = "2026.09-mvp12"

# ---- statistics ---------------------------------------------------------------
WILSON_Z = 1.96                 # 95% Wilson interval
MODZ_OUTLIER = 3.5              # NIST/Iglewicz-Hoaglin modified z threshold -> concern 50
MODZ_CAP = 7.0                  # modified z at which concern saturates to 100
FINDING_THRESHOLD = 50.0        # concern >= this becomes a finding
POWER_MEAN_P = 3.0              # aggregation exponent (limits compensability)
MIN_PEERS = 5                   # below this, fall back to sector-wide / own history
SILENT_CHANCE = 0.01            # silent-asset flag only if P(>= k silent | peer silent rate) < 1%
SILENT_WINSOR = 2               # cap each peer-period silent count when pooling the baseline
EXPECTED_TACTIC_SHARE = 0.70    # tactic "expected" if seen by >= 70% of comparable peers
NOTE_SIMILARITY = 0.90          # TF-IDF cosine for near-identical notes
REPEAT_MIN = 3                  # repeat alerts on same asset+technique per period
UNCERTAINTY_DRAWS = 2000        # Dirichlet weight draws for rank stability
TARGETED_SHARE = 0.80           # review pack: 80% targeted / 20% random control
RANDOM_SEED = 26157

# EG-03 policy tolerance: flag if Wilson LB of "critical TP not escalated" exceeds this
ESCALATION_TOLERANCE = 0.10
# NS-08 policy tolerance: flag if Wilson LB of rejected-row share exceeds this
DATA_QUALITY_TOLERANCE = 0.05

CAPABILITY_AREAS = [
    "Threat Detection", "Investigation", "Escalation", "Incident Response",
    "Security Operations", "Governance and Oversight", "Operational Discipline", "Cyber Resilience",
]
