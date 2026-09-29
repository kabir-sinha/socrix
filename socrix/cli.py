"""socrix command line.

  socrix demo       generate SimSOC data -> ingest -> score -> benchmark (one command, ~30 s)
  socrix generate   write synthetic submissions (--seed)
  socrix ingest     validate + load submissions into DuckDB (receipts, rejects, lineage)
  socrix score      compute indicators, scores, findings, review packs -> data/results.json
  socrix bench      grade the last score run against the SimSOC ground truth
  socrix serve      start the offline dashboard (default http://127.0.0.1:8157)
  socrix export     write a single self-contained HTML report (no server needed)
  socrix verify     check the hash-chained audit log
"""
from __future__ import annotations
import argparse, base64, json, re, sys, time
from pathlib import Path
from . import config as C


def _gen(a):
    from . import simsoc
    p = simsoc.generate(C.SUBMISSIONS, seed=a.seed)
    print(f"SimSOC submissions written to {p} (seed {a.seed})")


def _ingest(a):
    from . import intake
    s = intake.ingest(Path(a.submissions) if getattr(a, "submissions", None) else C.SUBMISSIONS, C.DB_PATH)
    print("Loaded:", ", ".join(f"{k} {v:,}" for k, v in s.items()))


def _score(a):
    from . import pipeline
    t = time.time()
    r = pipeline.run(C.DB_PATH)
    ents = sorted(r["entities"].values(), key=lambda e: -(e["sai"] or 0))
    print(f"Scored {len(ents)} entities for {r['meta']['latest']} in {time.time() - t:.1f}s")
    for e in ents:
        print(f"  {e['entity_id']:<8} SAI {e['sai'] or 0:5.1f}  rank {e['rank_min']}-{e['rank_max']}  findings: {', '.join(e['findings']) or '-'}")


def _bench(a):
    from . import benchmark
    print(benchmark.report(benchmark.run()))


def _serve(a):
    import uvicorn
    print(f"SOCRIX dashboard: http://{a.host}:{a.port}   (API docs: /api/docs)   Ctrl+C to stop")
    uvicorn.run("socrix.api:app", host=a.host, port=a.port, log_level="warning")


def _verify(a):
    from .audit import verify
    ok, n = verify()
    print(f"Audit chain {'INTACT' if ok else 'BROKEN at entry ' + str(n)} ({n} entries)")
    sys.exit(0 if ok else 1)


def export_static(out: Path, evidence_rows: int = 25) -> Path:
    """Self-contained HTML report: dashboard + embedded data for every drill-down level (evidence truncated)."""
    from . import api
    from .audit import audit
    r = api.results()
    data = {"/api/overview": api.overview(), "/api/meta": api.meta(), "/api/rejects": api.rejects(),
            "/api/audit/verify": api.audit_verify()}
    try:
        data["/api/benchmark"] = api.benchmark()
    except Exception:
        pass
    alert_ids = set()
    for e, x in r["entities"].items():
        data[f"/api/entity/{e}"] = api.entity(e)
        data[f"/api/entity/{e}/review-pack"] = api.review_pack(e)
        data[f"/api/entity/{e}/controls"] = api.controls(e)
        alert_ids |= {it["alert_id"] for it in x["review_pack"]["items"]}
        for i in x["indicators"]:
            data[f"/api/entity/{e}/indicator/{i}"] = api.indicator(e, i)
            ev = api.evidence(e, i, None, 0, evidence_rows)  # direct call: pass plain ints
            data[f"/api/entity/{e}/indicator/{i}/evidence"] = ev
            if x["indicators"][i].get("concern") and x["indicators"][i]["concern"] >= C.FINDING_THRESHOLD:
                alert_ids |= {row["alert_id"] for row in ev["rows"] if "alert_id" in row}
    for aid in sorted(alert_ids):
        data[f"/api/case/{aid}"] = api.case(aid)
        data[f"/api/lineage/{aid}"] = api.lineage(aid)
    web = Path(__file__).parent / "web"
    html = (web / "index.html").read_text()
    html = html.replace('<link rel="stylesheet" href="static/style.css">', "")
    css = re.sub(r'url\("fonts/([\w.-]+\.woff2)"\)',   # inline the self-hosted fonts so the report stays offline
                 lambda m: 'url("data:font/woff2;base64,' + base64.b64encode((web / "fonts" / m.group(1)).read_bytes()).decode() + '")',
                 (web / "style.css").read_text())
    html = html.replace("<!--SOCRIX_STATIC_CSS-->", f"<style>{css}</style>")
    payload = json.dumps(data, default=str, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("<!--SOCRIX_STATIC_DATA-->", f"<script>window.SOCRIX_DATA={payload};</script>")
    html = html.replace('<script src="static/app.js"></script>', "")
    html = html.replace("<!--SOCRIX_STATIC_JS-->", f"<script>{(web / 'app.js').read_text()}</script>")
    out.write_text(html)
    audit("static_export", dict(file=out.name, bytes=len(html), cases=len(alert_ids)))
    return out


def _export(a):
    p = export_static(Path(a.out))
    print(f"Static report written: {p} ({p.stat().st_size / 1e6:.1f} MB) — open it in any browser, no server needed")


def _demo(a):
    _gen(a); _ingest(a); _score(a); _bench(a)
    print("\nNext: socrix serve   (or: socrix export)")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="socrix", description="SOCRIX — SOC assurance analytics for NCIIPC (SIH26157)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("demo", _demo), ("generate", _gen)):
        p = sub.add_parser(name); p.add_argument("--seed", type=int, default=C.RANDOM_SEED); p.set_defaults(fn=fn)
    p = sub.add_parser("ingest"); p.add_argument("--submissions", default=None); p.set_defaults(fn=_ingest)
    sub.add_parser("score").set_defaults(fn=_score)
    sub.add_parser("bench").set_defaults(fn=_bench)
    sub.add_parser("verify").set_defaults(fn=_verify)
    p = sub.add_parser("serve"); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8157); p.set_defaults(fn=_serve)
    p = sub.add_parser("export"); p.add_argument("--out", default=str(C.DATA / "socrix_report.html")); p.set_defaults(fn=_export)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
