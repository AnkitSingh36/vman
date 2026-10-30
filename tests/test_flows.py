from datetime import date

import pytest

from lantern.agent.agents import OfflineAgent
from lantern.app import SCENARIOS, present
from lantern.bridge.tools import Bridge
from lantern.cli import SAMPLES
from lantern.mockvault.seed import build_vault


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s.name for s in SCENARIOS])
def test_offline_scenarios(sc):
    vault = build_vault()
    bridge = Bridge(vault, sc.user, "agent.er2-cell-1", today=date(2026, 10, 10))
    result = OfflineAgent(bridge).run(SAMPLES / sc.image, task=sc.task, build_order=sc.build_order,
                                      site=sc.site, inspection=sc.inspection)
    lines = []
    assert present(result, bridge, confirm=lambda q: True, out=lines.append) == sc.expected


def test_person_can_stop_and_evidence_records_stop():
    vault = build_vault()
    bridge = Bridge(vault, "anna.tech", "agent.er2-cell-1", today=date(2026, 10, 10))
    result = OfflineAgent(bridge).run(SAMPLES / "nameplate_ME450-21877.png", task="Restart after unplanned stop")
    answers = iter([True, True, False])  # bulletin ok, step 1 ok, step 2 refused
    out = present(result, bridge, confirm=lambda q: next(answers), out=lambda s: None)
    assert out == "stopped"
    ev = [vault.latest_version(o) for o in vault.objects_of_type("Evidence")]
    assert any(e.properties.get("Result") == "stopped" and e.properties.get("Step") == 2 for e in ev)
