"""The engine must agree, row for row, with the independent re-implementation (written blind from the spec)."""
import subprocess, sys
from pathlib import Path


def test_engine_matches_independent_reimplementation(built):
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, str(root / "scripts" / "independent" / "compare.py"), str(built["C"].DATA)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "mismatches: {'missing_rows': 0" in r.stdout
