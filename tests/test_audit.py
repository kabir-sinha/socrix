import json
from socrix import audit as A, config as C


def test_chain_intact_after_run(built):
    ok, n = A.verify()
    assert ok and n >= 2


def test_tamper_is_detected(built):
    lines = C.AUDIT_LOG.read_text().splitlines()
    original = C.AUDIT_LOG.read_text()
    try:
        e = json.loads(lines[0]); e["detail"] = {"tampered": True}
        lines[0] = json.dumps(e)
        C.AUDIT_LOG.write_text("\n".join(lines) + "\n")
        ok, _ = A.verify()
        assert not ok
    finally:
        C.AUDIT_LOG.write_text(original)
    assert A.verify()[0]
