"""Engine behaviour, including regressions for every false positive found during the build."""
CLEAN = {"PWR-01", "PWR-04", "PWR-07", "BFS-01", "BFS-03"}


def test_every_plant_detected_no_false_positives(built):
    b = built["bench"]
    assert b["missed"] == 0, b["missed_list"]
    assert b["false_positives"] == 0, b["fp_list"]
    assert b["clean_entity_false_positives"] == 0


def test_clean_entities_have_no_findings(built):
    for e in CLEAN:
        assert built["results"]["entities"][e]["findings"] == [], e


def test_regression_pwr04_eg05_small_n_not_flagged(built):   # was concern 82 on k=8/n=17 noise
    assert "EG-05" not in built["results"]["entities"]["PWR-04"]["findings"]


def test_regression_no_double_count_of_missing_workflow(built):  # PWR-08 used to also fire EG-01/EG-07/EG-03
    assert built["results"]["entities"]["PWR-08"]["findings"] == ["NS-03"]


def test_regression_single_silent_asset_not_flagged(built):   # PWR-06 flagged NS-01 on one silent asset
    assert "NS-01" not in built["results"]["entities"]["PWR-06"]["findings"]


def test_insufficient_evidence_is_never_zero(built):
    for e in built["results"]["entities"].values():
        for i in e["indicators"].values():
            if i["status"] != "assessed":
                assert i["concern"] is None


def test_every_finding_has_explanation_and_evidence(built):
    for e in built["results"]["entities"].values():
        for f in e["findings"]:
            ind = e["indicators"][f]
            assert ind["explanation"] and str(ind["k"]) in ind["explanation"]
            assert ind["evidence_count"] > 0


def test_review_pack_split(built):
    p = built["results"]["entities"]["PWR-03"]["review_pack"]
    assert len(p["items"]) == 20 and p["targeted"] == 16 and p["control"] == 4
    assert len({i["alert_id"] for i in p["items"]}) == 20


def test_attack_v19_tactics(built):
    from socrix import attack
    names = attack.tactic_names()
    assert names["TA0005"] == "Stealth" and "TA0112" in names and len(names) == 15
    assert attack.tactics_for("T1566.001") == attack.tactics_for("T1566")   # sub-technique falls back to base
