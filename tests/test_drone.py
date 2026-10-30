from datetime import date

import pytest

from lantern.bridge.tools import Bridge, dispatch
from lantern.mockvault.seed import build_vault

TODAY = date(2026, 10, 10)
AGENT = "agent.er2-cell-1"


@pytest.fixture
def vault():
    return build_vault()


def bridge(v, user="mikko.pilot", today=TODAY):
    return Bridge(v, user, AGENT, today=today)


def ref(b, ident):
    r = b.identify_item(ident)
    assert r["status"] == "ok", r
    return r["item"]["item_ref"]


def failed(r):
    return {c["check"] for c in r["checks"] if not c["ok"]}


def test_go_when_everything_valid_and_draft_plan_ignored(vault):
    b = bridge(vault)
    r = b.check_mission_readiness("Tank farm North", ref(b, "UAV-D7-0041"))
    assert r["decision"] == "go" and not failed(r)
    assert r["plan_source"]["revision"] == "3"
    assert any("revision 4" in n for n in r["notes"])


def test_expired_permit_is_no_go(vault):
    b = bridge(vault)
    r = b.check_mission_readiness("Tank farm South", ref(b, "UAV-D7-0041"))
    assert r["decision"] == "no_go" and failed(r) == {"valid_work_permit"}


def test_operator_identity_comes_from_session(vault):
    b = bridge(vault, user="sara.pilot")
    r = b.check_mission_readiness("Tank farm North", ref(b, "UAV-D7-0041"))
    assert failed(r) == {"operator_qualified"}


def test_unknown_site_and_wrong_drone(vault):
    b = bridge(vault)
    r = b.check_mission_readiness("Tank farm East", ref(b, "TK-101"))
    assert {"approved_inspection_plan", "valid_work_permit", "drone_identified"} <= failed(r)


def test_drone_certificate_expiry_by_date(vault):
    b = bridge(vault, today=date(2027, 2, 1))
    r = b.check_mission_readiness("Tank farm North", ref(b, "UAV-D7-0041"))
    assert "drone_certificate" in failed(r)


def test_open_deviation_on_drone_blocks(vault):
    b = bridge(vault)
    drone = ref(b, "UAV-D7-0041")
    vault.create_object(104, "Nonconformance", "NC-2026-130 Rotor 3 vibration", {
        "Related equipment": [int(drone.split(":")[1])], "Severity": "Major"}, state="Open")
    r = b.check_mission_readiness("Tank farm North", drone)
    assert "drone_open_deviations" in failed(r)


@pytest.mark.parametrize("value,unit,status", [
    (7.4, "bar", "out_of_limits"), (3.1, "bar", "within_limits"), (6.0, "bar", "within_limits"),
    (0.4, "bar", "out_of_limits"), (3.1, "psi", "refused"),
])
def test_reading_evaluated_by_bridge(vault, value, unit, status):
    b = bridge(vault)
    assert b.evaluate_reading(ref(b, "TK-102"), "PI-102", value, unit)["status"] == status


def test_unknown_measurement_point_refused(vault):
    b = bridge(vault)
    assert b.evaluate_reading(ref(b, "TK-102"), "PI-999", 3.0, "bar")["status"] == "no_approved_criteria"


def test_deviation_is_app_only(vault):
    b = bridge(vault)
    tank = ref(b, "TK-102")
    assert dispatch(b, "draft_deviation", {"item_ref": tank, "title": "x", "severity": "Major"})["status"] == "error"
    assert b.draft_deviation(tank, "PI-102 out of limits", "Major")["status"] == "ok"
    assert b.check_blockers(tank)["status"] == "blocked"
