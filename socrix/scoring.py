"""B4 peer & policy scoring + B7 Supervisory Attention Index (SAI), findings, coverage, uncertainty.

Exact method (Blueprint Part F):
  value (Wilson LB for rates) -> leave-one-out peer group (sector x size, same period; fallback if < 5)
  -> NIST modified z (oriented, MAD floor) -> peer concern = 100*clip(M,0,7)/7
  -> policy concern (NS-01 empirical binomial silence test, NS-02 expected-absent, EG-03 / NS-08 tolerances)
  -> concern = max(peer, policy) -> area = power mean (p=3) -> SAI = power mean over assessed areas.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from . import config as C
from .indicators import catalogue
from .stats import modified_z, concern_from_modz, power_mean, binomial_se, binomial_sf


def _peer_group(ind: pd.DataFrame, row, profiles: dict, by_ip: dict | None = None,
                by_ie: dict | None = None) -> tuple[list[float], str]:
    # peers must themselves have enough evidence (n >= min_n): a peer too small to judge must not shape the baseline
    min_n = catalogue()[row.indicator]["min_n"]
    pool = by_ip.get((row.indicator, row.period), ind.iloc[0:0]) if by_ip is not None else ind[(ind.indicator == row.indicator) & (ind.period == row.period)]
    same = pool[(pool.entity_id != row.entity_id) & pool.value.notna() & (pool.n >= min_n)]
    sec = profiles[row.entity_id]
    grp = same[same.entity_id.map(lambda e: profiles[e] == sec)]
    if len(grp) >= C.MIN_PEERS:
        return grp.value.tolist(), f"{sec[0]} / {sec[1]} peers (n={len(grp)})"
    if len(same) >= C.MIN_PEERS:
        return same.value.tolist(), f"all sectors (n={len(same)}) — sector group too small"
    hist = by_ie.get((row.indicator, row.entity_id), ind.iloc[0:0]) if by_ie is not None else ind[(ind.indicator == row.indicator) & (ind.entity_id == row.entity_id)]
    own = hist[(hist.period != row.period) & hist.value.notna()]
    return own.value.tolist(), f"own history (n={len(own)})"


def silent_baseline(ind: pd.DataFrame, row, profiles: dict) -> tuple[float | None, str]:
    """Empirical chance that a critical asset is silent in a comparable SOC.
    Pooled over same-sector peers across all periods (leave-one-entity-out), each peer-period's silent
    count winsorised at SILENT_WINSOR (so one broken peer cannot normalise silence), Jeffreys prior.
    Empirical rather than Poisson because real alert counts per asset are over-dispersed."""
    ns01 = ind[ind.indicator == "NS-01"] if "ns01" not in ind.attrs else ind.attrs["ns01"]
    base = ns01[(ns01.entity_id != row.entity_id) & (ns01.n > 0)]
    same = base[base.entity_id.map(lambda e: profiles.get(e, (None,))[0] == profiles[row.entity_id][0])]
    grp, label = (same, "same-sector peers") if same.entity_id.nunique() >= C.MIN_PEERS else (base, "all peers")
    if grp.empty:
        return None, ""
    p = (grp.k.clip(upper=C.SILENT_WINSOR).sum() + 0.5) / (grp.n.sum() + 1.0)
    return float(p), f"{label}, {len(grp)} peer-periods"


def _policy(row, silent_p: float | None, silent_label: str = "") -> tuple[float, str]:
    iid, k, n, v = row.indicator, row.k, row.n, row.value
    if iid == "NS-01" and k > 0 and silent_p is not None:
        p_family = binomial_sf(int(k), int(n), silent_p)   # chance of >= k silent among n assets at the peer rate
        if p_family < C.SILENT_CHANCE:
            return min(100.0, 60.0 + 10.0 * (k - 1)), (f"{k} of {n} critical assets silent; comparable SOCs leave {silent_p:.2%} of critical "
                                                        f"assets silent ({silent_label}), so >= {k} by chance has probability "
                                                        f"{p_family:.4f} < {C.SILENT_CHANCE}")
    if iid == "NS-02" and k > 0 and n >= 3:
        return min(100.0, 50.0 + 25.0 * (k - 1)), f"{k} expected tactic(s) absent"
    if iid == "EG-03" and n >= 5 and v is not None and v > C.ESCALATION_TOLERANCE:
        return 50.0, f"conservative non-escalation rate {v:.1%} exceeds tolerance {C.ESCALATION_TOLERANCE:.0%}"
    if iid == "NS-08" and v is not None and v > C.DATA_QUALITY_TOLERANCE:
        return 60.0, f"conservative reject rate {v:.1%} exceeds tolerance {C.DATA_QUALITY_TOLERANCE:.0%}"
    return 0.0, ""


def score(ind_rows: list[dict], profiles_df: pd.DataFrame) -> pd.DataFrame:
    cat = catalogue()
    ind = pd.DataFrame(ind_rows)
    prof = profiles_df.drop_duplicates("entity_id").set_index("entity_id")
    profiles = {e: (r.sector, r.size_band) for e, r in prof.iterrows()}
    # index once: peer lookups are O(group) instead of O(all rows)  (was quadratic in entities x periods)
    by_ip = {k: g for k, g in ind.groupby(["indicator", "period"])}
    by_ie = {k: g for k, g in ind.groupby(["indicator", "entity_id"])}
    ind.attrs["ns01"] = ind[ind.indicator == "NS-01"]
    out = []
    for row in ind.itertuples():
        meta = cat[row.indicator]
        enough = row.value is not None and not (isinstance(row.value, float) and math.isnan(row.value)) and row.n >= meta["min_n"]
        rec = dict(row._asdict()); rec.pop("Index", None)
        rec.update(name=meta["name"], area=meta["area"], gap=meta["gap"], brief=meta["brief"], track_def=meta["track"])
        if not enough:
            rec.update(status="insufficient evidence", modz=None, median=None, mad=None, peer_concern=None,
                       policy_concern=None, concern=None, track=None, baseline=None, policy_reason="")
            out.append(rec); continue
        peers, baseline = _peer_group(ind, row, profiles, by_ip, by_ie)
        floor = meta["mad_floor"]
        if meta.get("rate") and peers:
            # a gap smaller than binomial sampling noise at the peer median is not an outlier
            floor = max(floor, binomial_se(float(np.median(peers)), int(row.n)))
        m, med, mad = modified_z(row.value, peers, meta["higher_is_worse"], floor)
        peer_c = concern_from_modz(m) if peers else float("nan")
        sp, slabel = silent_baseline(ind, row, profiles) if row.indicator == "NS-01" else (None, "")
        pol_c, why = _policy(row, sp, slabel) if "policy" in meta["track"] else (0.0, "")
        peer_c = 0.0 if math.isnan(peer_c) else peer_c
        conc = max(peer_c, pol_c)
        ratio = (row.value / med) if (med is not None and med == med and med != 0) else None
        rec.update(status="assessed", modz=m, median=med, mad=mad, peer_concern=peer_c, policy_concern=pol_c,
                   concern=conc, track="policy" if pol_c > peer_c else "peer", baseline=baseline,
                   policy_reason=why, silent_baseline=sp, ratio_to_median=ratio)
        out.append(rec)
    return pd.DataFrame(out)


def entity_scores(sc: pd.DataFrame, weights: dict[str, float] | None = None, p: float = C.POWER_MEAN_P) -> pd.DataFrame:
    rows = []
    for (entity, period), g in sc.groupby(["entity_id", "period"]):
        areas = {}
        for area in C.CAPABILITY_AREAS:
            vals = g[(g.area == area) & (g.status == "assessed")].concern.dropna().tolist()
            areas[area] = power_mean(vals, p=p) if vals else None
        assessed = [a for a in C.CAPABILITY_AREAS if areas[a] is not None]
        w = [(weights or {}).get(a, 1.0) for a in assessed]
        sai = power_mean([areas[a] for a in assessed], w, p=p) if assessed else None
        findings = g[(g.concern >= C.FINDING_THRESHOLD)].sort_values("concern", ascending=False)
        rows.append(dict(entity_id=entity, period=period, sai=sai, coverage=len(assessed), areas=areas,
                         findings=findings.indicator.tolist(), n_findings=len(findings),
                         insufficient=g[g.status == "insufficient evidence"].indicator.tolist()))
    return pd.DataFrame(rows)


def rank_stability(es: pd.DataFrame, draws: int = C.UNCERTAINTY_DRAWS, seed: int = C.RANDOM_SEED) -> pd.DataFrame:
    """OECD/JRC-style uncertainty: Dirichlet(1) area weights; also aggregation exponent p in {1,2,3,6}.
    Returns per entity-period: P(rank1), P(top3), rank range across exponents."""
    rng = np.random.default_rng(seed)
    out = []
    for period, g in es.groupby("period"):
        ents = g.entity_id.tolist()
        area_mat = np.array([[ (a[x] if a[x] is not None else np.nan) for x in C.CAPABILITY_AREAS] for a in g.areas])
        top1 = dict.fromkeys(ents, 0); top3 = dict.fromkeys(ents, 0)
        for _ in range(draws):
            w = rng.dirichlet(np.ones(len(C.CAPABILITY_AREAS)))
            s = []
            for row in area_mat:
                mask = ~np.isnan(row)
                ww = w[mask] / w[mask].sum()
                s.append(float(np.sum(ww * row[mask] ** C.POWER_MEAN_P) ** (1 / C.POWER_MEAN_P)))
            order = np.argsort(s)[::-1]
            top1[ents[order[0]]] += 1
            for i in order[:3]:
                top3[ents[i]] += 1
        ranks = {e: [] for e in ents}
        for p in (1.0, 2.0, 3.0, 6.0):
            s = []
            for row in area_mat:
                v = row[~np.isnan(row)]
                s.append(float(np.mean(v ** p) ** (1 / p)))
            for r, i in enumerate(np.argsort(s)[::-1], start=1):
                ranks[ents[i]].append(r)
        for e in ents:
            out.append(dict(entity_id=e, period=period, p_rank1=top1[e] / draws, p_top3=top3[e] / draws,
                            rank_min=min(ranks[e]), rank_max=max(ranks[e])))
    return pd.DataFrame(out)
