"""B8 prioritisation (entities, controls, processes, review packs) + B9 deterministic explanations.
No LLM, no external model: explanation text comes from fixed templates (brief §5(v))."""
from __future__ import annotations
import math, random
import pandas as pd
from . import config as C
from .indicators import catalogue


def fmt_value(r) -> str:
    if r.value is None or (isinstance(r.value, float) and math.isnan(r.value)):
        return "n/a"
    if r.indicator == "EG-02":
        return f"{10 ** r.value:.0f} min"
    if r.indicator in ("NS-02",):
        return f"{int(r.value)}"
    if r.indicator in ("NS-05", "WL-01"):
        return f"{r.value:.2f}"
    return f"{r.value:.1%}"


def fmt_median(r) -> str:
    if r.median is None or (isinstance(r.median, float) and math.isnan(r.median)):
        return "n/a"
    if r.indicator == "EG-02":
        return f"{10 ** r.median:.0f} min"
    if r.indicator in ("NS-02", "NS-05", "WL-01"):
        return f"{r.median:.2f}"
    return f"{r.median:.1%}"


def explain(r) -> str:
    """One finding -> one plain-English sentence with numbers, baseline, track and evidence count."""
    meta = catalogue()[r.indicator]
    display = r.display if isinstance(r.display, str) else fmt_value(r)
    base = meta["template"].format(k=r.k, n=r.n, display=display)
    if r.status != "assessed":
        return f"{meta['name']}: insufficient evidence (n={r.n} < {meta['min_n']})."
    parts = [base[0].upper() + base[1:] + "."]
    if r.indicator not in ("EG-02", "NS-05", "WL-01", "NS-02"):
        parts.append(f"Conservative estimate {fmt_value(r)} vs peer median {fmt_median(r)}")
    else:
        parts.append(f"Value {fmt_value(r)} vs peer median {fmt_median(r)}")
    if r.modz is not None and not math.isnan(r.modz):
        parts[-1] += f" (modified z {r.modz:.1f}; {r.baseline})."
    if r.track == "policy" and r.policy_reason:
        parts.append(f"Policy rule: {r.policy_reason}.")
    if r.indicator == "NS-02" and isinstance(r.missing, list) and r.missing:
        parts.append("Missing: " + ", ".join(r.missing) + ".")
    parts.append(f"Concern {r.concern:.0f}/100.")
    return " ".join(parts)


def review_pack(sc_entity: pd.DataFrame, budget: int = 20, seed: int = C.RANDOM_SEED,
                all_alerts: list[str] | None = None) -> dict:
    """80% targeted across case-level findings (proportional to concern), 20% random control.
    Asset/coverage findings become an inspection checklist, not case samples."""
    cat = catalogue()
    rng = random.Random(seed)
    f = sc_entity[(sc_entity.concern >= C.FINDING_THRESHOLD)]
    case_level = f[f.indicator.map(lambda i: cat[i]["sample_cases"])]
    checklist = []
    for r in f[~f.indicator.map(lambda i: cat[i]["sample_cases"])].itertuples():
        items = r.evidence if isinstance(r.evidence, list) else []
        checklist.append(dict(indicator=r.indicator, name=r.name, items=items[:20]))
    targeted_n = int(round(budget * C.TARGETED_SHARE)) if len(case_level) else 0
    control_n = budget - targeted_n
    items, taken = [], set()
    if targeted_n:
        tot = case_level.concern.sum()
        alloc = {r.indicator: int(round(targeted_n * r.concern / tot)) for r in case_level.itertuples()}
        diff = targeted_n - sum(alloc.values())
        if diff:
            alloc[max(alloc, key=alloc.get)] += diff
        for r in case_level.itertuples():
            pool = [e for e in (r.evidence or []) if e not in taken]
            for e in rng.sample(pool, min(alloc[r.indicator], len(pool))):
                items.append(dict(alert_id=e, reason=f"targeted:{r.indicator}", concern=round(float(r.concern), 1)))
                taken.add(e)
    pool = [a for a in (all_alerts or []) if a not in taken]
    for e in rng.sample(pool, min(control_n, len(pool))):
        items.append(dict(alert_id=e, reason="random-control", concern=None))
    return dict(budget=budget, targeted=sum(1 for i in items if i["reason"] != "random-control"),
                control=sum(1 for i in items if i["reason"] == "random-control"), items=items, checklist=checklist)


def control_ranking(alerts: pd.DataFrame, noinv_ids: set[str], nonenrich_ids: set[str], top: int = 10) -> list[dict]:
    """FR10 'controls': detectors whose alerts are most often closed without investigation/enrichment."""
    g = alerts.groupby("detector_id").alert_id.agg(list)
    rows = []
    for det, ids in g.items():
        n = len(ids)
        bad = sum(1 for i in ids if i in noinv_ids or i in nonenrich_ids)
        if n >= 10:
            rows.append(dict(detector_id=det, alerts=n, weak_handling=bad, share=bad / n))
    return sorted(rows, key=lambda r: -r["share"])[:top]
