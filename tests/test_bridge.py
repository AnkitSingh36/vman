from datetime import date

import pytest

from lantern.bridge.tools import Bridge, dispatch
from lantern.mockvault.seed import build_vault

TODAY = date(2026, 10, 10)
AGENT = "agent.er2-cell-1"


@pytest.fixture
def vault():
    return build_vault()


def tech(v):
    return Bridge(v, "anna.tech", AGENT, today=TODAY)


def logi(v):
    return Bridge(v, "ravi.logistics", AGENT, today=TODAY)


def ref(b, ident):
    r = b.identify_item(ident)
    assert r["status"] == "ok", r
    return r["item"]["item_ref"]


def test_latest_approved_revision_used_and_draft_ignored(vault):
    b = tech(vault)
    job = b.get_approved_job(ref(b, "ME450-21877"), "Restart after unplanned stop")
    assert job["status"] == "ok"
    assert job["source"]["revision"] == "C"
    assert any("revision D" in n and "NOT used" in n for n in job["notes"])
    assert job["steps"][3].endswith("above 0.8 bar.")  # verbatim Rev C, not Rev D's 0.6


def test_serial_effectivity_picks_other_procedure(vault):
    b = tech(vault)
    job = b.get_approved_job(ref(b, "me450-19950"), "restart after unplanned stop")
    assert job["source"]["revision"] == "B"


def test_unknown_serial_is_refused_with_close_match_for_human(vault):
    r = tech(vault).identify_item("ME450-21878")
    assert r["status"] == "not_found"
    assert "ME450-21877" in r["close_matches_for_human_review"]


def test_no_procedure_for_other_model(vault):
    b = tech(vault)
    assert b.get_approved_job(ref(b, "MX200-00412"), "Restart after unplanned stop")["status"] == "no_approved_procedure"


def test_blockers_and_bulletin(vault):
    b = tech(vault)
    r1 = b.check_blockers(ref(b, "ME450-21877"))
    assert r1["status"] == "warnings" and r1["warnings"][0]["severity"] == "Minor"
    assert r1["required_first"][0]["source"]["title"].startswith("SB-2026-014")
    r2 = b.check_blockers(ref(b, "ME450-19950"))
    assert r2["status"] == "blocked" and r2["blockers"][0]["type"] == "expired_certificate"
    assert r2["required_first"] == []  # bulletin covers 21500-22500 only


def test_permissions_both_components_and_both_identities(vault):
    # Logistics user cannot read maintenance procedures (class ACL component)
    b = logi(vault)
    assert b.get_approved_job(ref(b, "ME450-21877"), "Restart after unplanned stop")["status"] == "no_approved_procedure"
    # Engineering-only document is invisible to technician and agent
    eng_doc = [o for o in vault.objects_of_class("Engineering analysis")][0]
    assert not vault.can_access("anna.tech", eng_doc, 1)
    assert vault.can_access("eero.engineer", eng_doc, 1)


@pytest.mark.parametrize("container,decision,reason", [
    ("CNT-48812", "hold", "Wrong revision"),
    ("CNT-48807", "hold", "open deviation"),
    ("CNT-48830", "hold", "expired certificate"),
    ("CNT-48841", "cleared", None),
    ("CNT-48850", "cleared", None),
])
def test_logistics_decisions(vault, container, decision, reason):
    b = logi(vault)
    r = b.check_part_for_build(ref(b, container), "BO-7781")
    assert r["decision"] == decision
    if reason:
        assert any(reason in x for x in r["reasons"])


def test_camera_revision_overrides_and_is_flagged(vault):
    b = logi(vault)
    r = b.check_part_for_build(ref(b, "CNT-48850"), "BO-7781", label_revision="A")
    assert r["decision"] == "hold" and r["notes"]


def test_evidence_write_and_audit(vault):
    b = tech(vault)
    e = b.record_evidence("Equipment:1", "Restart done", "done", step=6)
    assert e["status"] == "ok" and e["mock_write"]
    actions = [a["action"] for a in vault.audit_entries()]
    assert "record_evidence" in actions


def test_ai_cannot_call_write_or_unknown_tools(vault):
    b = tech(vault)
    assert dispatch(b, "record_evidence", {"item_ref": "Equipment:1"})["status"] == "error"
    assert dispatch(b, "identify_item", {"wrong": 1})["status"] == "error"
