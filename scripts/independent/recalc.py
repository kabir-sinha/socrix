#!/usr/bin/env python3
"""Independent re-implementation of the SOCRIX scoring spec — written by a separate agent from a text
specification WITHOUT access to the engine code. It is a second opinion: every change to the engine must still
match it (scripts/independent/compare.py). Do not "fix" this file to agree with the engine; if they disagree,
decide from the spec (docs/ARCHITECTURE.md) which one is wrong.
Usage: python scripts/independent/recalc.py [data_dir]   (default ./data; writes data/independent_*.csv)"""
import os, sys
import json, math
import numpy as np, pandas as pd, duckdb, yaml
from scipy.stats import binom
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = (sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data')).rstrip('/') + '/'
con = duckdb.connect(D + 'socrix.duckdb', read_only=True)
con.execute("SET TimeZone='UTC'")
q = lambda s: con.execute(s).df()
alerts = q("select alert_id, entity_id, period, created_ts, closed_ts, severity, technique_id, asset_id, disposition, analyst from alerts")
cases = q("select case_id, alert_id, entity_id, period, note, root_cause_code from cases")
wf = q("select case_id, action from workflow")
esc = q("select distinct case_id from escalations")
assets = q("select asset_id, entity_id, period, criticality from assets")
receipts = q("select entity_id, period, file, rows from receipts")
rejects = q("select entity_id, period, file from rejects")
profiles = q("select entity_id, period, sector, size_band from profiles")
cat = yaml.safe_load(open(os.path.join(ROOT, 'socrix', 'catalogue.yaml')))
att = json.load(open(D + 'reference/attack_ref_v19_2.json'))
tech2tac = {t['id']: set(t['tactics']) for t in att['techniques']}

def tactics_of(tid):
    if tid is None or (isinstance(tid, float) and math.isnan(tid)):
        return set()
    if tid in tech2tac:
        return tech2tac[tid]
    return tech2tac.get(tid.split('.')[0], set())

INV = {'enrichment', 'analysis', 'containment', 'remediation'}
REM = {'containment', 'remediation'}
actions = wf.groupby('case_id')['action'].agg(set)
escalated = set(esc.case_id)

# alert-level frame
a = alerts.merge(cases[['alert_id', 'case_id', 'root_cause_code']], on='alert_id', how='left')
a['acts'] = a.case_id.map(actions)
a['has_wf'] = a.acts.notna()
a['acts'] = a.acts.apply(lambda s: s if isinstance(s, set) else set())
a['closed'] = a.closed_ts.notna()
a['rc'] = a.root_cause_code.fillna('').astype(str).str.strip() != ''

def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    v = (p + z*z/(2*n) - z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1 + z*z/n)
    return max(v, 0.0)

keys = profiles[['entity_id', 'period']].drop_duplicates().sort_values(['entity_id', 'period'])
sector = {(r.entity_id, r.period): r.sector for r in profiles.itertuples()}
sizeb = {(r.entity_id, r.period): r.size_band for r in profiles.itertuples()}

# tactic sets for NS-02
tacset = {}
for (e, p), g in a.groupby(['entity_id', 'period']):
    s = set()
    for t in g.technique_id.unique():
        s |= tactics_of(t)
    tacset[(e, p)] = s

rows = []
for e, p in keys.itertuples(index=False):
    A = a[(a.entity_id == e) & (a.period == p)]
    C = cases[(cases.entity_id == e) & (cases.period == p)]
    W = A[A.closed & A.has_wf]
    HC = W[W.severity.isin(['high', 'critical'])]
    crit = assets[(assets.entity_id == e) & (assets.period == p) & (assets.criticality == 'critical')]
    out = {}
    # EG-01
    n = len(HC); k = int(sum(1 for s in HC.acts if not (s & INV)))
    out['EG-01'] = (k, n, wilson(k, n))
    # EG-02
    if n:
        med = float(np.median((HC.closed_ts - HC.created_ts).dt.total_seconds() / 60))
        out['EG-02'] = (0, n, math.log10(max(med, 0.1)))
    else:
        out['EG-02'] = (0, 0, None)
    # EG-03
    ct = W[(W.severity == 'critical') & (W.disposition == 'TP')]
    n = len(ct); k = int((~ct.case_id.isin(escalated)).sum())
    out['EG-03'] = (k, n, wilson(k, n))
    # EG-04
    cc = C.merge(alerts[['alert_id', 'asset_id']], on='alert_id', how='left')
    n = len(cc); k = 0
    if n > 1:
        X = TfidfVectorizer(min_df=1).fit_transform(cc.note.fillna('').tolist())
        S = cosine_similarity(X)
        np.fill_diagonal(S, -1)
        ast = cc.asset_id.to_numpy()
        diff = ast[:, None] != ast[None, :]
        k = int(((S >= 0.90) & diff).any(axis=1).sum())
    out['EG-04'] = (k, n, wilson(k, n))
    # EG-05
    Aw = A[A.has_wf]
    n = k = 0
    for _, g in Aw.groupby(['asset_id', 'technique_id']):
        if len(g) >= 3:
            n += 1
            if not any(s & REM for s in g.acts) and not g.rc.any():
                k += 1
    out['EG-05'] = (k, n, wilson(k, n))
    # EG-07
    fb = W[W.disposition.isin(['FP', 'BP'])]
    n = len(fb); k = int(sum(1 for s in fb.acts if 'enrichment' not in s))
    out['EG-07'] = (k, n, wilson(k, n))
    # NS-01
    alerted = set(A.asset_id)
    n = len(crit); k = int((~crit.asset_id.isin(alerted)).sum())
    out['NS-01'] = (k, n, wilson(k, n))
    # NS-02
    sec = sector[(e, p)]
    peers = [x for x in keys.itertuples(index=False) if x[1] == p and x[0] != e and sector[(x[0], x[1])] == sec]
    if peers:
        cnt = {}
        for pe in peers:
            for t in tacset.get((pe[0], pe[1]), set()):
                cnt[t] = cnt.get(t, 0) + 1
        expected = {t for t, c in cnt.items() if c / len(peers) >= 0.70}
    else:
        expected = set()
    k = len(expected - tacset.get((e, p), set())); n = len(expected)
    out['NS-02'] = (k, n, float(k))
    # NS-03
    n = len(C); k = int((~C.case_id.isin(actions.index)).sum())
    out['NS-03'] = (k, n, wilson(k, n))
    # NS-05
    n = len(crit); k = int(A.asset_id.isin(set(crit.asset_id)).sum())
    out['NS-05'] = (k, n, k / n if n else None)
    # NS-08
    n = int(receipts[(receipts.entity_id == e) & (receipts.period == p) & (receipts.file == 'alerts.csv')].rows.sum())
    k = int(((rejects.entity_id == e) & (rejects.period == p) & (rejects.file == 'alerts.csv')).sum())
    out['NS-08'] = (k, n, wilson(k, n))
    # WL-01
    Ac = A[A.closed].copy()
    n = len(Ac)
    if n:
        Ac['day'] = Ac.closed_ts.dt.tz_convert('UTC').dt.date
        per = Ac.groupby(['analyst', 'day']).size().groupby(level=0).mean()
        out['WL-01'] = (0, n, float(per.max()))
    else:
        out['WL-01'] = (0, 0, None)
    for ind, (k, n, v) in out.items():
        rows.append(dict(entity_id=e, period=p, indicator=ind, k=k, n=n, value=v))

df = pd.DataFrame(rows)
df['min_n'] = df.indicator.map(lambda i: cat[i]['min_n'])
df['status'] = np.where(df.value.isna() | (df.n < df.min_n), 'insufficient', 'assessed')
df['sector'] = [sector[(r.entity_id, r.period)] for r in df.itertuples()]
df['size_band'] = [sizeb[(r.entity_id, r.period)] for r in df.itertuples()]

# NS-01 policy baseline helper
ns01 = df[df.indicator == 'NS-01']

def ns01_policy(r):
    if r.k <= 0:
        return 0.0
    oth = ns01[(ns01.entity_id != r.entity_id) & (ns01.n > 0)]
    same = oth[oth.sector == r.sector]
    base = same if same.entity_id.nunique() >= 5 else oth
    qq = (np.minimum(base.k, 2).sum() + 0.5) / (base.n.sum() + 1)
    pf = binom.sf(r.k - 1, r.n, qq)
    return min(100.0, 60 + 10 * (r.k - 1)) if pf < 0.01 else 0.0

out_cols = {c: [] for c in ['median', 'mad_used', 'modz', 'peer_concern', 'policy_concern', 'concern']}
for r in df.itertuples():
    c = cat[r.indicator]
    if r.status != 'assessed':
        for kk in out_cols: out_cols[kk].append(None)
        continue
    ok = df[(df.indicator == r.indicator) & (df.value.notna()) & (df.n >= df.min_n) & (df.entity_id != r.entity_id)]
    peer = ok[(ok.period == r.period) & (ok.sector == r.sector) & (ok.size_band == r.size_band)]
    if len(peer) < 5:
        peer = ok[ok.period == r.period]
    if len(peer) < 5:
        peer = df[(df.indicator == r.indicator) & (df.entity_id == r.entity_id) & (df.period != r.period) & df.value.notna()]
    vals = peer.value.astype(float).to_numpy()
    if len(vals) == 0:
        med = mad_used = M = None; pc = 0.0
    else:
        med = float(np.median(vals)); mad = float(np.median(np.abs(vals - med)))
        floor = c['mad_floor']
        if c.get('rate', False):
            qn = min(max(med, 1 / (2 * r.n)), 1 - 1 / (2 * r.n))
            floor = max(floor, math.sqrt(qn * (1 - qn) / r.n))
        mad_used = max(mad, floor)
        M = 0.6745 * (r.value - med) / mad_used
        if not c['higher_is_worse']:
            M = -M
        pc = 100 * min(max(M, 0), 7) / 7
    pol = 0.0
    if 'policy' in c['track']:
        if r.indicator == 'NS-01':
            pol = ns01_policy(r)
        elif r.indicator == 'NS-02':
            pol = min(100.0, 50 + 25 * (r.k - 1)) if (r.k > 0 and r.n >= 3) else 0.0
        elif r.indicator == 'EG-03':
            pol = 50.0 if (r.n >= 5 and r.value > 0.10) else 0.0
        elif r.indicator == 'NS-08':
            pol = 60.0 if r.value > 0.05 else 0.0
    for kk, vv in zip(out_cols, [med, mad_used, M, pc, pol, max(pc, pol)]):
        out_cols[kk].append(vv)
for kk, vv in out_cols.items():
    df[kk] = vv

df[['entity_id', 'period', 'indicator', 'k', 'n', 'value', 'status', 'median', 'mad_used', 'modz',
    'peer_concern', 'policy_concern', 'concern']].sort_values(['entity_id', 'period', 'indicator']).to_csv(D + 'independent_scores.csv', index=False)

AREAS = ['Threat Detection', 'Investigation', 'Escalation', 'Incident Response', 'Security Operations',
         'Governance and Oversight', 'Operational Discipline', 'Cyber Resilience']
pm = lambda x: float(np.mean(np.array(x, float) ** 3) ** (1 / 3))
df['area'] = df.indicator.map(lambda i: cat[i]['area'])
ents = []
for (e, p), g in df.groupby(['entity_id', 'period']):
    ga = g[g.status == 'assessed']
    scores = [pm(ga[ga.area == ar].concern) for ar in AREAS if (ga.area == ar).any()]
    finds = sorted(ga[ga.concern >= 50].indicator)
    ents.append(dict(entity_id=e, period=p, sai=pm(scores) if scores else None, coverage=len(scores), findings=';'.join(finds)))
pd.DataFrame(ents).to_csv(D + 'independent_entities.csv', index=False)
print(len(df), len(ents))
