"""B10 Read-only API + static dashboard server (fully offline; binds to localhost by default).

Levels of drill-down (D0 -> D7):
  D0 /api/overview                         national view: every entity, SAI, findings, coverage, uncertainty
  D1 /api/entity/{e}                       one CSE: areas, findings with explanations, trend, rank range
  D2 /api/entity/{e}/indicator/{i}         one indicator: value, peer distribution, history, method
  D3 /api/entity/{e}/indicator/{i}/evidence  the exact rows behind it (paged)
  D4 /api/entity/{e}/review-pack(.csv)     what an auditor should inspect next (80% targeted / 20% control)
  D5 /api/entity/{e}/controls              detectors whose alerts are handled weakest
  D6 /api/case/{alert_id}                  single-case timeline: alert -> case -> workflow -> escalation
  D7 /api/lineage/{alert_id}               submission, file, row number, SHA-256 receipt of the source
  +  /api/benchmark, /api/rejects, /api/audit/verify, /api/meta
"""
from __future__ import annotations
import csv, io, json
from pathlib import Path
import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from . import config as C
from .audit import audit, verify

WEB = Path(__file__).parent / "web"
app = FastAPI(title="SOCRIX", version=C.ENGINE_VERSION, docs_url="/api/docs", redoc_url=None)
_cache: dict = {}


def results() -> dict:
    p = C.RESULTS
    if not p.exists():
        raise HTTPException(503, "No score run yet. Run: socrix demo")
    mtime = p.stat().st_mtime
    if _cache.get("mtime") != mtime:
        _cache.update(mtime=mtime, data=json.loads(p.read_text()))
    return _cache["data"]


def _db():
    con = duckdb.connect(str(C.DB_PATH), read_only=True)
    con.execute("SET TimeZone='UTC'")
    return con


def _entity(e: str) -> dict:
    r = results()
    if e not in r["entities"]:
        raise HTTPException(404, f"unknown entity {e}")
    return r["entities"][e]


def _rows(con, sql, params=()):
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, [v.isoformat() if hasattr(v, "isoformat") else v for v in row])) for row in cur.fetchall()]


@app.get("/api/meta")
def meta():
    r = results()
    return r["meta"] | {"catalogue_version": r["meta"]["catalogue"], "indicators": r["catalogue"]}


@app.get("/api/overview")
def overview():
    r = results()
    ents = [{k: v for k, v in e.items() if k in ("entity_id", "sector", "size_band", "sai", "coverage", "areas", "findings",
                                                  "p_rank1", "p_top3", "rank_min", "rank_max", "trend")}
            for e in r["entities"].values()]
    ents.sort(key=lambda x: -(x["sai"] or 0))
    return dict(meta=r["meta"], entities=ents)


@app.get("/api/entity/{e}")
def entity(e: str):
    x = _entity(e)
    return {k: v for k, v in x.items() if k not in ("review_pack", "controls")}


@app.get("/api/entity/{e}/indicator/{i}")
def indicator(e: str, i: str):
    x = _entity(e)
    r = results()
    if i not in x["indicators"]:
        raise HTTPException(404, f"unknown indicator {i}")
    latest = r["meta"]["latest"]
    return dict(entity_id=e, detail=x["indicators"][i], method=r["catalogue"][i],
                history=x["history"].get(i, []), distribution=r["distributions"].get(i, {}).get(latest, []))


@app.get("/api/entity/{e}/indicator/{i}/evidence")
def evidence(e: str, i: str, period: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500)):
    x = _entity(e)                                   # 404 for unknown entity
    if i not in x["indicators"]:
        raise HTTPException(404, f"unknown indicator {i}")
    r = results()
    period = period or r["meta"]["latest"]
    if period not in r["meta"]["periods"]:
        raise HTTPException(404, f"unknown period {period}")
    con = _db()
    try:
        total = con.execute("SELECT count(*) FROM indicator_evidence WHERE entity_id=? AND period=? AND indicator=?",
                            [e, period, i]).fetchone()[0]
        ids = [r[0] for r in con.execute("SELECT evidence FROM indicator_evidence WHERE entity_id=? AND period=? AND indicator=? "
                                         "ORDER BY seq LIMIT ? OFFSET ?", [e, period, i, limit, offset]).fetchall()]
        rows = []
        cat = results()["catalogue"].get(i, {})
        if ids and cat.get("sample_cases"):   # alert-level evidence -> join the alert rows
            q = ",".join("?" * len(ids))
            rows = _rows(con, f"""SELECT a.alert_id, a.severity, a.technique_id, a.detector_id, a.asset_id, a.disposition,
                                  a.analyst, a.created_ts, a.closed_ts,
                                  round(date_diff('second', a.created_ts, a.closed_ts) / 60.0, 1) AS minutes_to_close,
                                  c.case_id, c.note, c.root_cause_code
                                  FROM alerts a LEFT JOIN cases c USING (alert_id) WHERE a.alert_id IN ({q}) ORDER BY a.alert_id""", ids)
        else:                                    # asset / tactic / row-number evidence
            rows = [dict(item=v) for v in ids]
    finally:
        con.close()
    return dict(entity_id=e, indicator=i, period=period, total=total, offset=offset, limit=limit, rows=rows)


@app.get("/api/entity/{e}/review-pack")
def review_pack(e: str):
    return _entity(e)["review_pack"]


@app.get("/api/entity/{e}/review-pack.csv", response_class=PlainTextResponse)
def review_pack_csv(e: str):
    pack = _entity(e)["review_pack"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["entity_id", "alert_id", "reason", "concern", "reviewer_verdict", "reviewer_notes"])
    for it in pack["items"]:
        w.writerow([e, it["alert_id"], it["reason"], it.get("concern", ""), "", ""])
    for ck in pack.get("checklist", []):
        for item in ck["items"]:
            w.writerow([e, item, f"checklist:{ck['indicator']}", "", "", ""])
    audit("review_pack_export", dict(entity=e, items=len(pack["items"])))
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="socrix_review_pack_{e}.csv"'})


@app.get("/api/entity/{e}/controls")
def controls(e: str):
    return _entity(e)["controls"]


@app.get("/api/case/{alert_id}")
def case(alert_id: str):
    con = _db()
    try:
        a = _rows(con, "SELECT * FROM alerts WHERE alert_id=?", [alert_id])
        if not a:
            raise HTTPException(404, "unknown alert")
        c = _rows(con, "SELECT * FROM cases WHERE alert_id=?", [alert_id])
        cid = c[0]["case_id"] if c else None
        wf = _rows(con, "SELECT ts, action, actor FROM workflow WHERE case_id=? ORDER BY ts", [cid]) if cid else []
        es = _rows(con, "SELECT ts, to_tier FROM escalations WHERE case_id=? ORDER BY ts", [cid]) if cid else []
        asset = _rows(con, "SELECT asset_id, criticality, environment, asset_type FROM assets WHERE asset_id=? AND period=?",
                      [a[0]["asset_id"], a[0]["period"]])
        # only indicators that are FINDINGS for this entity-period (evidence lists of non-findings are context, not flags)
        flags = [r[0] for r in con.execute("""SELECT DISTINCT e.indicator FROM indicator_evidence e JOIN indicator_scores s
                 USING (entity_id, period, indicator) WHERE e.evidence=? AND s.status='assessed' AND s.concern >= ?""",
                 [alert_id, C.FINDING_THRESHOLD]).fetchall()]
        context = [r[0] for r in con.execute("SELECT DISTINCT indicator FROM indicator_evidence WHERE evidence=?", [alert_id]).fetchall()
                   if r[0] not in flags]
    finally:
        con.close()
    timeline = [dict(ts=a[0]["created_ts"], event="alert created", detail=f"{a[0]['severity']} {a[0]['technique_id']} on {a[0]['asset_id']}")]
    timeline += [dict(ts=w["ts"], event=w["action"], detail=f"by {w['actor']}") for w in wf]
    timeline += [dict(ts=x["ts"], event="escalated", detail=f"to {x['to_tier']}") for x in es]
    if a[0]["closed_ts"]:
        timeline.append(dict(ts=a[0]["closed_ts"], event="alert closed", detail=f"disposition {a[0]['disposition']}"))
    timeline.sort(key=lambda t: t["ts"] or "")
    return dict(alert=a[0], case=c[0] if c else None, asset=asset[0] if asset else None,
                timeline=timeline, flagged_by=sorted(flags), also_in_evidence_of=sorted(context))


@app.get("/api/lineage/{alert_id}")
def lineage(alert_id: str):
    con = _db()
    try:
        a = _rows(con, "SELECT alert_id, entity_id, period, submission_id, source_file, source_row FROM alerts WHERE alert_id=?", [alert_id])
        if not a:
            raise HTTPException(404, "unknown alert")
        rec = _rows(con, "SELECT file, sha256, rows, received_at FROM receipts WHERE submission_id=?", [a[0]["submission_id"]])
        rej = con.execute("SELECT count(*) FROM rejects WHERE submission_id=?", [a[0]["submission_id"]]).fetchone()[0]
    finally:
        con.close()
    intact, n = verify()
    return dict(record=a[0], receipts=rec, rejected_rows_in_submission=rej,
                audit_chain=dict(intact=intact, entries=n), engine=C.ENGINE_VERSION, catalogue=C.CATALOGUE_VERSION)


@app.get("/api/benchmark")
def benchmark():
    p = C.DATA / "benchmark.json"
    if not p.exists():
        raise HTTPException(404, "no benchmark yet. Run: socrix bench")
    return json.loads(p.read_text())


@app.get("/api/rejects")
def rejects(entity: str | None = None):
    r = results()["rejects_summary"]
    return [x for x in r if entity is None or x["entity_id"] == entity]


@app.get("/api/audit/verify")
def audit_verify():
    intact, n = verify()
    return dict(intact=intact, entries=n)


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/static", StaticFiles(directory=WEB), name="static")
