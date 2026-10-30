"""Tests the Gemini function-calling loop with a fake client (no network, no API key)."""
from datetime import date
from types import SimpleNamespace

from lantern.agent.agents import GeminiAgent
from lantern.app import outcome
from lantern.bridge.tools import Bridge
from lantern.cli import SAMPLES
from lantern.mockvault.seed import build_vault


class FakeModels:
    def __init__(self, script):
        self.script = list(script)
        self.seen_contents = []

    def generate_content(self, model, contents, config):
        self.seen_contents.append(len(contents))
        calls, text = self.script.pop(0)
        fcs = [SimpleNamespace(name=n, args=a, id=f"call-{i}") for i, (n, a) in enumerate(calls)]
        return SimpleNamespace(function_calls=fcs, text=text,
                               candidates=[SimpleNamespace(content={"role": "model", "calls": calls})])


def test_loop_executes_tools_and_returns_summary():
    vault = build_vault()
    bridge = Bridge(vault, "anna.tech", "agent.er2-cell-1", today=date(2026, 10, 10))
    script = [
        ([("identify_item", {"identifier": "ME450-21877"})], None),
        ([("check_blockers", {"item_ref": "Equipment:1"}),
          ("get_approved_job", {"item_ref": "Equipment:1", "task": "Restart after unplanned stop"})], None),
        ([], "Identified ME450-21877. Rev C applies after bulletin SB-2026-014."),
    ]
    fake = SimpleNamespace(models=FakeModels(script))
    agent = GeminiAgent(bridge, client=fake)
    res = agent.run(SAMPLES / "nameplate_ME450-21877.png", task="Restart after unplanned stop")
    assert [c.name for c in res.calls] == ["identify_item", "check_blockers", "get_approved_job"]
    assert res.seen["identifier"] == "ME450-21877"
    assert outcome(res) == "ready"
    assert "Rev C" in res.final_text
    assert fake.models.seen_contents == [1, 3, 5]  # history grows: call + response each turn


def test_model_cannot_reach_write_tool():
    vault = build_vault()
    bridge = Bridge(vault, "anna.tech", "agent.er2-cell-1", today=date(2026, 10, 10))
    script = [([("record_evidence", {"item_ref": "Equipment:1", "summary": "x", "result": "done"})], None),
              ([], "done")]
    agent = GeminiAgent(bridge, client=SimpleNamespace(models=FakeModels(script)))
    res = agent.run(SAMPLES / "nameplate_ME450-21877.png", task="Restart after unplanned stop")
    assert res.calls[0].result["status"] == "error"
    assert vault.objects_of_type("Evidence") == []
