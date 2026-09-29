"""Compare the engine's indicator_scores with the independent re-implementation. Exit 1 on any mismatch."""
import os, sys, subprocess, json
import duckdb, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = (sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data")).rstrip("/") + "/"
subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "independent", "recalc.py"), D], check=True)
a = pd.read_csv(D + "independent_scores.csv")
b = duckdb.connect(D + "socrix.duckdb", read_only=True).execute(
    "select entity_id, period, indicator, k, n, value, median, modz, peer_concern, policy_concern, concern, status from indicator_scores").df()
m = a.merge(b, on=["entity_id", "period", "indicator"], suffixes=("_i", "_e"), how="outer", indicator=True)
bad = {"missing_rows": int((m._merge != "both").sum())}
for c in ["k", "n", "value", "median", "modz", "peer_concern", "policy_concern", "concern"]:
    x, y = m[c + "_i"], m[c + "_e"]
    bad[c] = int((~(((x - y).abs() <= 1e-6 + 1e-6 * y.abs()) | (x.isna() & y.isna()))).sum())
res = json.load(open(D + "results.json"))
ents = pd.read_csv(D + "independent_entities.csv")
latest = res["meta"]["latest"]
bad["entities"] = sum(1 for r in ents[ents.period == latest].itertuples()
                      if abs(res["entities"][r.entity_id]["sai"] - r.sai) > 1e-6
                      or sorted(res["entities"][r.entity_id]["findings"]) != (sorted(str(r.findings).split(";")) if isinstance(r.findings, str) else []))
print(f"{len(m)} rows compared; mismatches: {bad}")
sys.exit(1 if any(bad.values()) else 0)
