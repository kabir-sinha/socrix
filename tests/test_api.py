import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(built):
    from socrix.api import app
    return TestClient(app)


ENDPOINTS = ["/", "/static/app.js", "/static/style.css", "/api/meta", "/api/overview", "/api/entity/PWR-03",
             "/api/entity/PWR-03/indicator/EG-01", "/api/entity/PWR-03/indicator/EG-01/evidence",
             "/api/entity/PWR-03/review-pack", "/api/entity/PWR-03/review-pack.csv", "/api/entity/PWR-03/controls",
             "/api/benchmark", "/api/rejects", "/api/audit/verify"]


@pytest.mark.parametrize("path", ENDPOINTS)
def test_endpoint_ok(client, path):
    assert client.get(path).status_code == 200


def test_unknown_entity_404(client):
    assert client.get("/api/entity/NOPE").status_code == 404
    assert client.get("/api/case/NOPE").status_code == 404


def test_evidence_alert_rows_serialise_timestamps(client):   # regression: pytz missing -> 500
    j = client.get("/api/entity/PWR-03/indicator/EG-01/evidence?limit=3").json()
    assert j["total"] > 0 and j["rows"][0]["alert_id"] and "+00:00" in j["rows"][0]["created_ts"]


@pytest.mark.parametrize("e,i", [("PWR-05", "NS-01"), ("BFS-04", "NS-02"), ("PWR-02", "NS-08")])
def test_non_alert_evidence_not_empty(client, e, i):          # regression: asset ids were routed to the alert join
    j = client.get(f"/api/entity/{e}/indicator/{i}/evidence").json()
    assert j["total"] > 0 and len(j["rows"]) > 0 and "item" in j["rows"][0]


def test_numeric_row_order(client):
    rows = [r["item"] for r in client.get("/api/entity/PWR-02/indicator/NS-08/evidence?limit=500").json()["rows"]]
    nums = [int(r.split()[1]) for r in rows]
    assert nums == sorted(nums)


def test_case_flags_only_findings(client, built):            # regression: non-finding indicators listed as flags
    ev = client.get("/api/entity/PWR-03/indicator/EG-01/evidence?limit=1").json()["rows"][0]["alert_id"]
    c = client.get(f"/api/case/{ev}").json()
    findings = set(built["results"]["entities"]["PWR-03"]["findings"])
    assert "EG-01" in c["flagged_by"] and set(c["flagged_by"]) <= findings
    assert c["timeline"][0]["event"] == "alert created"


def test_lineage_has_receipt(client):
    ev = client.get("/api/entity/PWR-03/indicator/EG-01/evidence?limit=1").json()["rows"][0]["alert_id"]
    l = client.get(f"/api/lineage/{ev}").json()
    assert len(l["receipts"]) == 5 and all(len(r["sha256"]) == 64 for r in l["receipts"])
    assert l["audit_chain"]["intact"]


def test_meta_keeps_catalogue_version(client):               # regression: version string was overwritten
    m = client.get("/api/meta").json()
    assert m["catalogue_version"] == "2026.09-mvp12" and "EG-01" in m["indicators"]


def test_static_export_is_self_contained(built, tmp_path):
    from socrix.cli import export_static
    p = export_static(tmp_path / "r.html")
    html = p.read_text()
    assert "window.SOCRIX_DATA=" in html and 'src="static/' not in html and 'href="static/' not in html
    assert "http://" not in html.split("window.SOCRIX_DATA=")[0] and "https://" not in html.split("window.SOCRIX_DATA=")[0]


@pytest.mark.parametrize("url,code", [
    ("/api/entity/PWR-03'%20OR%20'1'='1/indicator/EG-01/evidence", 404),        # SQL-injection-shaped entity
    ("/api/entity/PWR-03/indicator/EG-01/evidence?period=2026-08'%20OR%201=1--", 404),
    ("/api/case/x'%3B%20DROP%20TABLE%20alerts%3B--", 404),
    ("/api/entity/PWR-03/indicator/EG-01/evidence?offset=-5", 422),               # regression: was a 500
    ("/api/entity/PWR-03/indicator/EG-01/evidence?limit=0", 422),
    ("/api/entity/PWR-03/indicator/EG-01/evidence?limit=100000", 422),
    ("/api/entity/PWR-03/indicator/ZZ-99/evidence", 404),                         # regression: was an empty 200
    ("/static/../../socrix/config.py", 404),
    ("/static/%2e%2e/%2e%2e/pyproject.toml", 404),
])
def test_hostile_inputs_are_rejected(client, built, url, code):
    import duckdb
    assert client.get(url).status_code == code
    con = duckdb.connect(str(built["C"].DB_PATH), read_only=True)
    assert con.execute("SELECT count(*) FROM alerts").fetchone()[0] > 0          # nothing was dropped
    con.close()


def test_api_is_read_only(client):
    for path in ("/api/overview", "/api/entity/PWR-03", "/api/audit/verify"):
        assert client.post(path).status_code == 405
        assert client.delete(path).status_code == 405


def test_web_assets_make_no_external_requests():
    from pathlib import Path
    import re
    web = Path(__file__).resolve().parent.parent / "socrix" / "web"
    for f in web.iterdir():
        assert not re.search(r"https?://(?!127\.0\.0\.1)", f.read_text()), f.name


def test_dashboard_escape_function():
    """esc() is what every data value passes through in app.js. The end-to-end browser attack test
    (malicious note/detector/asset in a real submission) is scripts/ui_audit.py --xss."""
    import shutil, subprocess
    from pathlib import Path
    if not shutil.which("node"):
        pytest.skip("node not installed")
    js = (Path(__file__).resolve().parent.parent / "socrix" / "web" / "app.js").read_text()
    line = next(l for l in js.splitlines() if l.startswith("const esc ="))
    out = subprocess.run(["node", "-e", line + ';process.stdout.write(esc(`<img src=x onerror="a()">\'&`))'],
                         capture_output=True, text=True).stdout
    assert out == "&lt;img src=x onerror=&quot;a()&quot;&gt;&#39;&amp;"
