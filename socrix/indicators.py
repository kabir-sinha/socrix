"""B3 Indicator engine — MVP 12. Each indicator returns, per entity-period:
k, n, value (Wilson lower bound for rates), display, evidence (row ids), extra.
Indicators never return 0 for missing evidence: they return value=None with status 'insufficient evidence'.
"""
from __future__ import annotations
import math
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from . import attack, config as C, schema as S
from .stats import wilson_lower

HC = ("high", "critical")


@lru_cache(maxsize=1)
def catalogue() -> dict:
    return yaml.safe_load((Path(__file__).parent / "catalogue.yaml").read_text())


def _res(k, n, value, display=None, evidence=None, **extra):
    meta = dict(k=int(k), n=int(n), value=None if value is None or (isinstance(value, float) and math.isnan(value)) else float(value),
                display=display, evidence=[] if evidence is None else list(evidence)[:5000])
    meta.update(extra)
    return meta


def compute_all(data: dict[str, pd.DataFrame]) -> list[dict]:
    """data: canonical tables (all entities, all periods). Returns list of indicator rows."""
    al, cs, wf, esc, assets, rej, rec = (data[k] for k in ("alerts", "cases", "workflow", "escalations", "assets", "rejects", "receipts"))
    wf_actions = wf.groupby("case_id").action.agg(set)
    esc_cases = set(esc.case_id)
    wf_cases = set(wf_actions.index)          # built once (was rebuilt per entity-period: O(E x N))
    al = al.merge(cs[["alert_id", "case_id"]], on="alert_id", how="left")   # link via submitted keys, not naming
    al["actions"] = al.case_id.map(wf_actions)
    al["tactics"] = al.technique_id.map(lambda t: tuple(attack.tactics_for(t)))
    # per-alert flags computed once (vectorised) instead of per group
    has_wf = al.actions.map(lambda s: isinstance(s, set)).astype(bool)
    al["remedial"] = al.actions.map(lambda s: isinstance(s, set) and bool(s & S.REMEDIAL)).astype(bool)
    rc = cs.set_index("alert_id").root_cause_code if "root_cause_code" in cs else pd.Series(dtype=object)
    al["has_rc"] = al.alert_id.map(rc).fillna("").astype(str).str.strip().ne("")
    al["has_wf"] = has_wf
    # split every table by (entity, period) ONCE: avoids O(entities x rows) re-filtering
    split = lambda df: {k: g for k, g in df.groupby(["entity_id", "period"])} if len(df) else {}
    cs_by, as_by, rj_by, rc_by = split(cs), split(assets), split(rej), split(rec)
    empty = lambda df: df.iloc[0:0]
    rows = []
    groups = list(al.groupby(["entity_id", "period"]))
    tactic_sets = {key: set(t for ts in g.tactics for t in ts) for key, g in groups}
    for (entity, period), a in groups:
        c = cs_by.get((entity, period), empty(cs))
        ea = as_by.get((entity, period), empty(assets))
        crit_assets = ea[ea.criticality == "critical"].asset_id
        closed_all = a[a.closed_ts.notna()]
        # execution-gap indicators judge only cases that HAVE workflow records;
        # cases with no records are negative space (NS-03), counted once, not twice
        closed = closed_all[closed_all.actions.map(lambda s: isinstance(s, set)).astype(bool)]
        hc = closed[closed.severity.isin(HC)]
        acts = hc.actions.map(lambda s: s if isinstance(s, set) else set())
        no_inv = hc[acts.map(lambda s: not (s & S.INVESTIGATIVE)).astype(bool)]
        out = {}
        # EG-01
        out["EG-01"] = _res(len(no_inv), len(hc), wilson_lower(len(no_inv), len(hc)), evidence=no_inv.alert_id)
        # EG-02 (median minutes, log10)
        mins = (hc.closed_ts - hc.created_ts).dt.total_seconds() / 60
        med = float(mins.median()) if len(mins) else float("nan")
        fastest = hc.assign(m=mins).nsmallest(200, "m").alert_id
        out["EG-02"] = _res(0, len(hc), math.log10(max(med, 0.1)) if len(mins) else None,
                            display=f"{med:.0f} min" if len(mins) else None, evidence=fastest, median_minutes=med)
        # EG-03
        ctp = closed[(closed.severity == "critical") & (closed.disposition == "TP")]
        noesc = ctp[~ctp.case_id.isin(esc_cases)]
        out["EG-03"] = _res(len(noesc), len(ctp), wilson_lower(len(noesc), len(ctp)), evidence=noesc.alert_id)
        # EG-04 near-duplicate notes on different assets
        notes = c.merge(a[["alert_id", "asset_id"]], on="alert_id", how="left")
        k4, ev4 = 0, []
        if len(notes) >= 2:
            tf = TfidfVectorizer(min_df=1).fit_transform(notes.note.fillna(""))
            sim = cosine_similarity(tf, dense_output=False)
            sim.setdiag(0); sim.eliminate_zeros()
            assets_arr = notes.asset_id.to_numpy()
            dup = np.zeros(len(notes), dtype=bool)
            coo = sim.tocoo()
            m = (coo.data >= C.NOTE_SIMILARITY) & (assets_arr[coo.row] != assets_arr[coo.col])
            dup[coo.row[m]] = True
            k4 = int(dup.sum()); ev4 = notes.alert_id[dup]
        out["EG-04"] = _res(k4, len(notes), wilson_lower(k4, len(notes)), evidence=ev4)
        # EG-05 recurring (asset, technique) pairs without remediation or root cause
        # only alerts whose case has workflow records: "no remediation" cannot be judged from missing records (that is NS-03)
        aw = a[a.has_wf]
        pg = aw.groupby(["asset_id", "technique_id"]).agg(n=("alert_id", "size"), rem=("remedial", "any"), rc=("has_rc", "any"))
        rec_pairs = pg[pg.n >= C.REPEAT_MIN]
        bad = rec_pairs[~rec_pairs.rem & ~rec_pairs.rc]
        bad_keys = set(bad.index)
        ev5 = aw[[k in bad_keys for k in zip(aw.asset_id, aw.technique_id)]].alert_id if len(bad_keys) else []
        out["EG-05"] = _res(len(bad), len(rec_pairs), wilson_lower(len(bad), len(rec_pairs)), evidence=ev5)
        # EG-07 FP/BP closures with no enrichment
        fpbp = closed[closed.disposition.isin(["FP", "BP"])]
        fa = fpbp.actions.map(lambda s: s if isinstance(s, set) else set())
        noen = fpbp[fa.map(lambda s: "enrichment" not in s).astype(bool)]
        out["EG-07"] = _res(len(noen), len(fpbp), wilson_lower(len(noen), len(fpbp)), evidence=noen.alert_id)
        # NS-01 silent critical assets (peer rate test applied in scoring)
        seen = set(a.asset_id)
        silent = [x for x in crit_assets if x not in seen]
        crit_alerts = int(a.asset_id.isin(set(crit_assets)).sum())
        out["NS-01"] = _res(len(silent), len(crit_assets), wilson_lower(len(silent), len(crit_assets)),
                            evidence=silent, silent_assets=silent)
        # NS-05 alerts per critical asset
        rate = crit_alerts / len(crit_assets) if len(crit_assets) else None
        per_asset = a[a.asset_id.isin(set(crit_assets))].asset_id.value_counts().reindex(list(crit_assets), fill_value=0).sort_values(kind="stable")
        out["NS-05"] = _res(crit_alerts, len(crit_assets), rate, display=f"{rate:.2f}" if rate is not None else None,
                            evidence=[f"{x} ({c} alerts)" for x, c in per_asset.items()])
        # NS-03 cases with no workflow records
        nowf = c[~c.case_id.isin(wf_cases)]
        out["NS-03"] = _res(len(nowf), len(c), wilson_lower(len(nowf), len(c)), evidence=nowf.alert_id)
        # NS-08 rejected alert rows
        er = rc_by.get((entity, period), empty(rec))
        submitted = er[er.file == "alerts.csv"].rows.sum()
        ej = rj_by.get((entity, period), empty(rej))
        rj = ej[ej.file == "alerts.csv"]
        out["NS-08"] = _res(len(rj), int(submitted), wilson_lower(len(rj), int(submitted)) if submitted else None,
                            evidence=[f"row {r}" for r in rj.source_row], reasons=rj.reason.value_counts().to_dict())
        # WL-01 busiest analyst: mean cases closed per active day
        cl = closed_all.assign(day=closed_all.closed_ts.dt.date)
        per = cl.groupby(["analyst", "day"]).size().groupby("analyst").mean()
        top = per.idxmax() if len(per) else None
        out["WL-01"] = _res(0, len(cl), float(per.max()) if len(per) else None,
                            display=f"{per.max():.1f}" if len(per) else None,
                            evidence=cl[cl.analyst == top].alert_id if top else [], analyst=top)
        for iid, r in out.items():
            rows.append(dict(entity_id=entity, period=period, indicator=iid, **r))
    # NS-02 expected-but-absent tactics (needs peer information; peers = same sector, same period)
    sector = data["profiles"].drop_duplicates("entity_id").set_index("entity_id").sector.to_dict()
    for (entity, period), _ in groups:
        peers = [key for key in tactic_sets if key[1] == period and key[0] != entity and sector.get(key[0]) == sector.get(entity)]
        counts = {}
        for key in peers:
            for t in tactic_sets[key]:
                counts[t] = counts.get(t, 0) + 1
        expected = sorted(t for t, v in counts.items() if len(peers) and v / len(peers) >= C.EXPECTED_TACTIC_SHARE)
        missing = [t for t in expected if t not in tactic_sets[(entity, period)]]
        names = attack.tactic_names()
        rows.append(dict(entity_id=entity, period=period, indicator="NS-02",
                         **_res(len(missing), len(expected), float(len(missing)),
                                evidence=[f"{t} {names.get(t, '')}" for t in missing],
                                missing=[f"{t} {names.get(t, '')}" for t in missing],
                                expected=[f"{t} {names.get(t, '')}" for t in expected])))
    return rows
