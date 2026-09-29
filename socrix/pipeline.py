"""End-to-end run: DuckDB evidence -> indicators -> scores -> SAI/findings/uncertainty -> review packs -> results.json.
Every run is recorded in the hash-chained audit log with the engine/catalogue versions and input receipts."""
from __future__ import annotations
import json, math
import duckdb
import numpy as np
import pandas as pd
from . import attack, config as C, indicators as I, scoring as SC, prioritise as P
from .audit import audit


def load(db_path=C.DB_PATH) -> dict[str, pd.DataFrame]:
    con = duckdb.connect(str(db_path), read_only=True); con.execute("SET TimeZone='UTC'")
    t = {name: con.execute(f"SELECT * FROM {name}").df() for name in
         ("alerts", "cases", "workflow", "escalations", "assets", "rejects", "receipts", "profiles")}
    con.close()
    return t


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, pd.Timestamp):
        return o.isoformat()
    return o


def run(db_path=C.DB_PATH) -> dict:
    data = load(db_path)
    ind_rows = I.compute_all(data)
    sc = SC.score(ind_rows, data["profiles"])
    sc["explanation"] = [P.explain(r) for r in sc.itertuples()]
    es = SC.entity_scores(sc)
    stab = SC.rank_stability(es)
    es = es.merge(stab, on=["entity_id", "period"], how="left")
    periods = sorted(es.period.unique())
    latest = periods[-1]
    prof = data["profiles"].drop_duplicates("entity_id").set_index("entity_id")
    entities = {}
    al = data["alerts"]
    sc_by_e = {k: g for k, g in sc.groupby("entity_id")}
    al_by_ep = {k: g for k, g in al.groupby(["entity_id", "period"])}
    for e in sorted(es.entity_id.unique()):
        e_rows = es[es.entity_id == e].sort_values("period")
        cur = e_rows[e_rows.period == latest].iloc[0]
        sc_e = sc_by_e[e]
        sce = sc_e[sc_e.period == latest]
        al_e = al_by_ep.get((e, latest), al.iloc[0:0])
        a_ids = al_e.alert_id.tolist()
        noinv = set(sce[sce.indicator == "EG-01"].evidence.iloc[0]) if len(sce[sce.indicator == "EG-01"]) else set()
        nonen = set(sce[sce.indicator == "EG-07"].evidence.iloc[0]) if len(sce[sce.indicator == "EG-07"]) else set()
        entities[e] = dict(
            entity_id=e, sector=prof.loc[e, "sector"], size_band=prof.loc[e, "size_band"],
            sai=cur.sai, coverage=int(cur.coverage), areas=cur.areas, findings=cur.findings,
            p_rank1=cur.p_rank1, p_top3=cur.p_top3, rank_min=int(cur.rank_min), rank_max=int(cur.rank_max),
            trend=[dict(period=r.period, sai=r.sai, n_findings=int(r.n_findings)) for r in e_rows.itertuples()],
            indicators={r.indicator: {k: getattr(r, k) for k in (
                "indicator", "name", "area", "gap", "brief", "status", "k", "n", "value", "display", "median", "mad",
                "modz", "peer_concern", "policy_concern", "concern", "track", "baseline", "policy_reason", "explanation")}
                | {"evidence_count": len(r.evidence) if isinstance(r.evidence, list) else 0}
                for r in sce.itertuples()},
            history={iid: [dict(period=r.period, value=r.value, concern=r.concern)
                           for r in sc_e[sc_e.indicator == iid].sort_values("period").itertuples()]
                     for iid in I.catalogue()},
            review_pack=P.review_pack(sce, budget=20, all_alerts=a_ids),
            controls=P.control_ranking(al_e, noinv, nonen),
        )
    # peer distributions for the indicator view
    dist = {}
    for (iid, per), g in sc[sc.status == "assessed"].groupby(["indicator", "period"]):
        dist.setdefault(iid, {})[per] = [dict(entity_id=r.entity_id, value=r.value, concern=r.concern) for r in g.itertuples()]
    receipts = data["receipts"]
    results = dict(
        meta=dict(engine=C.ENGINE_VERSION, catalogue=C.CATALOGUE_VERSION, attack=attack.version(),
                  periods=periods, latest=latest, power_mean_p=C.POWER_MEAN_P, finding_threshold=C.FINDING_THRESHOLD,
                  uncertainty_draws=C.UNCERTAINTY_DRAWS, capability_areas=C.CAPABILITY_AREAS,
                  counts={k: int(len(v)) for k, v in data.items()}),
        entities=entities, distributions=dist,
        catalogue=I.catalogue(),
        rejects_summary=data["rejects"].groupby(["entity_id", "period", "reason"]).size().reset_index(name="rows").to_dict("records"),
        receipts=receipts[["submission_id", "file", "sha256", "rows"]].to_dict("records"),
    )
    results = _clean(results)
    C.RESULTS.write_text(json.dumps(results, default=str))
    # persist scores for SQL access / lineage
    con = duckdb.connect(str(db_path)); con.execute("SET TimeZone='UTC'")
    flat = sc.drop(columns=["evidence"]).copy()
    for col in flat.columns:
        if flat[col].map(lambda v: isinstance(v, (list, dict, set))).any():
            flat[col] = flat[col].map(lambda v: json.dumps(_clean(v), default=str) if isinstance(v, (list, dict, set)) else v)
    con.execute("DROP TABLE IF EXISTS indicator_scores")
    con.register("tmp", flat); con.execute("CREATE TABLE indicator_scores AS SELECT * FROM tmp"); con.unregister("tmp")
    ev = sc[["entity_id", "period", "indicator", "evidence"]].explode("evidence").dropna()
    ev["seq"] = range(len(ev))          # preserve the engine's evidence order (e.g. quietest asset / fastest closure first)
    con.execute("DROP TABLE IF EXISTS indicator_evidence")
    con.register("tmp", ev); con.execute("CREATE TABLE indicator_evidence AS SELECT * FROM tmp"); con.unregister("tmp")
    con.close()
    top = sorted(entities.values(), key=lambda x: -(x["sai"] or 0))[:5]
    audit("score_run", dict(latest=latest, receipts_sha256=sorted(receipts.sha256.tolist())[:3] + ["..."],
                            top=[(t["entity_id"], round(t["sai"] or 0, 1)) for t in top]))
    return results
