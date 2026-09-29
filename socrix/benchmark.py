"""Validation harness (brief: 'validated against expert manual review').

Blind discipline: the detection code (intake/indicators/scoring/pipeline) never opens
ground_truth.json. Only this module reads it, and only AFTER a score run, to grade the output.

Grading unit = (entity, period, indicator) finding.
  * TP       planted weakness flagged by its expected indicator
  * related  flagged by an indicator that is a known co-manifestation of a planted weakness on the
             same entity (e.g. no-investigation closures also show up as no-enrichment closures).
             Counted separately; not a false positive, not a detection.
  * FP       any other finding (includes every finding on a clean entity)
  * FN       planted (entity, period, indicator) not flagged
"""
from __future__ import annotations
import json
import duckdb
from . import config as C

# Weaknesses that genuinely co-manifest (same underlying behaviour, different lens).
RELATED = {
    "EG-01": {"EG-07", "EG-02", "EG-03"},
    "EG-07": {"EG-01", "EG-02"},
    "EG-03": {"EG-01"},
    "NS-05": {"NS-01"},
    "NS-01": {"NS-05"},
    "WL-01": {"EG-02"},
}


def run(db_path=C.DB_PATH, gt_path=C.DATA / "ground_truth.json") -> dict:
    gt = json.loads(gt_path.read_text())
    con = duckdb.connect(str(db_path), read_only=True)
    sc = con.execute("SELECT entity_id, period, indicator, concern, status FROM indicator_scores").df()
    insufficient = {(r.entity_id, r.period, r.indicator) for r in sc.itertuples() if r.status != "assessed"}
    con.close()
    flagged = {(r.entity_id, r.period, r.indicator) for r in sc.itertuples()
               if r.status == "assessed" and r.concern is not None and r.concern >= C.FINDING_THRESHOLD}
    expected = {}
    for p in gt["plants"]:
        for per in p["periods"]:
            for iid in p["indicators"]:
                expected[(p["entity"], per, iid)] = p["archetype"]
    tp = sorted(k for k in expected if k in flagged)
    fn = sorted(k for k in expected if k not in flagged)
    abstained = [k for k in fn if k in insufficient]      # engine said "insufficient evidence" instead of guessing
    related, fp = [], []
    for k in sorted(flagged - set(expected)):
        e, per, iid = k
        planted_here = {i for (e2, p2, i) in expected if e2 == e and p2 == per}
        if any(iid in RELATED.get(i, set()) for i in planted_here):
            related.append(k)
        else:
            fp.append(k)
    clean_fp = [k for k in fp if k[0] in gt["clean_entities"]]
    # per-archetype recall
    arche = {}
    for k, a in expected.items():
        d = arche.setdefault(a, {"expected": 0, "detected": 0})
        d["expected"] += 1
        d["detected"] += k in flagged
    n_pred = len(tp) + len(fp)
    out = dict(
        periods=gt["periods"], planted=len(expected), detected=len(tp), missed=len(fn),
        recall=len(tp) / len(expected) if expected else None,
        precision=len(tp) / n_pred if n_pred else None,
        related=len(related), false_positives=len(fp), clean_entity_false_positives=len(clean_fp),
        archetypes=[dict(archetype=a, **d, recall=d["detected"] / d["expected"]) for a, d in sorted(arche.items())],
        abstained=len(abstained), abstained_list=[list(k) for k in abstained],
        missed_list=[list(k) for k in fn], fp_list=[list(k) for k in fp], related_list=[list(k) for k in related],
        clean_entities=gt["clean_entities"],
    )
    (C.DATA / "benchmark.json").write_text(json.dumps(out, indent=1))
    return out


def report(b: dict) -> str:
    lines = [f"Planted weaknesses (entity x period x indicator): {b['planted']}",
             f"Detected: {b['detected']}  Missed: {b['missed']} (of which abstained for insufficient evidence: {b['abstained']})  Recall: {b['recall']:.1%}",
             f"False positives: {b['false_positives']} (on clean entities: {b['clean_entity_false_positives']})  "
             f"Precision: {b['precision']:.1%}  Related co-findings: {b['related']}", ""]
    for a in b["archetypes"]:
        lines.append(f"  {a['archetype']:<45} {a['detected']}/{a['expected']}")
    if b["missed_list"]:
        lines.append("Missed: " + ", ".join("/".join(k) for k in b["missed_list"]))
    if b["fp_list"]:
        lines.append("False positives: " + ", ".join("/".join(k) for k in b["fp_list"]))
    if b["related_list"]:
        lines.append("Related: " + ", ".join("/".join(k) for k in b["related_list"]))
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(run()))
