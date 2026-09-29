"""Rebuild data/reference/attack_ref_v19_2.json from MITRE's official STIX bundle (run once, online).

Usage:
  curl -L -o enterprise-attack-19.2.json \
    https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-19.2.json
  python scripts/build_attack_ref.py enterprise-attack-19.2.json
"""
import json, sys
from pathlib import Path

src = sys.argv[1] if len(sys.argv) > 1 else "enterprise-attack-19.2.json"
b = json.load(open(src)); objs = b["objects"]
ext = lambda o: next((r["external_id"] for r in o.get("external_references", []) if r.get("source_name") == "mitre-attack"), None)
live = lambda o: not o.get("revoked") and not o.get("x_mitre_deprecated")
byid = {o["id"]: o for o in objs}
matrix = [o for o in objs if o["type"] == "x-mitre-matrix"][0]
tac = [{"id": ext(byid[t]), "name": byid[t]["name"], "short": byid[t]["x_mitre_shortname"]} for t in matrix["tactic_refs"]]
short2id = {t["short"]: t["id"] for t in tac}
dc = {o["id"]: {"id": ext(o), "name": o["name"]} for o in objs if o["type"] == "x-mitre-data-component" and live(o)}
an = {o["id"]: [r["x_mitre_data_component_ref"] for r in o.get("x_mitre_log_source_references", [])] for o in objs if o["type"] == "x-mitre-analytic" and live(o)}
ds = {o["id"]: o.get("x_mitre_analytic_refs", []) for o in objs if o["type"] == "x-mitre-detection-strategy" and live(o)}
tech = {}
for o in objs:
    if o["type"] == "attack-pattern" and live(o):
        tech[o["id"]] = {"id": ext(o), "name": o["name"],
                         "tactics": [short2id[k["phase_name"]] for k in o.get("kill_chain_phases", [])
                                     if k.get("kill_chain_name") == "mitre-attack" and k["phase_name"] in short2id],
                         "data_components": set()}
for r in objs:
    if r["type"] == "relationship" and r["relationship_type"] == "detects" and r["source_ref"] in ds and r["target_ref"] in tech:
        for a in ds[r["source_ref"]]:
            for d in an.get(a, []):
                if d in dc:
                    tech[r["target_ref"]]["data_components"].add(dc[d]["id"])
coll = [o for o in objs if o["type"] == "x-mitre-collection"][0]
out = {"attack_version": coll.get("x_mitre_version", "19.2"), "source": Path(src).name, "tactics": tac,
       "data_components": sorted(dc.values(), key=lambda x: x["id"]),
       "techniques": sorted([dict(t, data_components=sorted(t["data_components"])) for t in tech.values()], key=lambda x: x["id"])}
dst = Path(__file__).resolve().parent.parent / "data" / "reference" / "attack_ref_v19_2.json"
json.dump(out, open(dst, "w"), indent=0)
print(f"wrote {dst}: {len(tac)} tactics, {len(out['techniques'])} techniques, {len(dc)} data components")
