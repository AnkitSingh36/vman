"""Turns an agent run into what a person sees and confirms.

Everything shown as an instruction comes from bridge results (the vault), not from model text.
Evidence is written only after a person confirms.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .agent.agents import AgentResult
from .bridge.tools import Bridge

Confirm = Callable[[str], bool]


@dataclass
class Scenario:
    name: str
    story: str
    image: str
    user: str
    task: str | None = None
    build_order: str | None = None
    site: str | None = None
    inspection: bool = False
    expected: str = ""


SCENARIOS = [
    Scenario("m1-restart-new-serial", "manufacturing", "nameplate_ME450-21877.png", "anna.tech",
             task="Restart after unplanned stop", expected="ready"),
    Scenario("m2-expired-certificate", "manufacturing", "nameplate_ME450-19950.png", "anna.tech",
             task="Restart after unplanned stop", expected="blocked"),
    Scenario("m3-unknown-serial", "manufacturing", "nameplate_ME450-21878.png", "anna.tech",
             task="Restart after unplanned stop", expected="not_identified"),
    Scenario("l1-wrong-revision", "logistics", "label_CNT-48812.png", "ravi.logistics", build_order="BO-7781",
             expected="hold"),
    Scenario("l2-batch-on-hold", "logistics", "label_CNT-48807.png", "ravi.logistics", build_order="BO-7781",
             expected="hold"),
    Scenario("l3-expired-certificate", "logistics", "label_CNT-48830.png", "ravi.logistics", build_order="BO-7781",
             expected="hold"),
    Scenario("l4-cleared", "logistics", "label_CNT-48850.png", "ravi.logistics", build_order="BO-7781",
             expected="cleared"),
    Scenario("d1-mission-go", "drone inspection", "drone_UAV-D7-0041.png", "mikko.pilot",
             site="Tank farm North", expected="go"),
    Scenario("d2-expired-permit", "drone inspection", "drone_UAV-D7-0041.png", "mikko.pilot",
             site="Tank farm South", expected="no_go"),
    Scenario("d3-operator-not-qualified", "drone inspection", "drone_UAV-D7-0041.png", "sara.pilot",
             site="Tank farm North", expected="no_go"),
    Scenario("d4-gauge-out-of-limits", "drone inspection", "gauge_TK-102.png", "mikko.pilot",
             inspection=True, expected="out_of_limits"),
    Scenario("d5-gauge-within-limits", "drone inspection", "gauge_TK-101.png", "mikko.pilot",
             inspection=True, expected="within_limits"),
]


def outcome(result: AgentResult) -> str:
    """Overall outcome, derived from vault results only."""
    ident = result.last("identify_item")
    if not ident or ident.get("status") != "ok":
        return "not_identified"
    mission = result.last("check_mission_readiness")
    if mission is not None:
        return mission.get("decision", mission.get("status", "unknown"))
    reading = result.last("evaluate_reading")
    if reading is not None:
        return reading.get("status", "unknown")
    if result.last("get_inspection_criteria") is not None:
        return result.last("get_inspection_criteria").get("status", "unknown")
    part = result.last("check_part_for_build")
    if part is not None:
        return part.get("decision") or part.get("status", "unknown")
    blockers = result.last("check_blockers")
    if blockers and blockers.get("status") == "blocked":
        return "blocked"
    job = result.last("get_approved_job")
    if job and job.get("status") == "ok":
        return "ready"
    return job.get("status", "unknown") if job else "unknown"


def present(result: AgentResult, bridge: Bridge, confirm: Confirm, out: Callable[[str], None] = print,
            photo_ref: str | None = None) -> str:
    """Show the vault-backed answer, collect confirmations, record evidence. Returns the outcome."""
    out(f"\nMode: {result.mode}")
    if result.seen:
        out(f"Agent read: {result.seen}")
    if result.final_text:
        out(f"Agent summary: {result.final_text}")
    status = outcome(result)
    ident = result.last("identify_item")

    if status == "not_identified":
        out("\nSTOP: item not identified in the vault.")
        if ident and ident.get("close_matches_for_human_review"):
            out(f"Close matches for a person to check: {ident['close_matches_for_human_review']}")
        return status

    item = ident["item"]
    out(f"\nItem: {item['title']} ({item['item_ref']})")

    mission = result.last("check_mission_readiness")
    if mission is not None:
        return _present_mission(mission, item, result, bridge, confirm, out, photo_ref)
    if result.last("get_inspection_criteria") is not None:
        return _present_reading(result, item, bridge, confirm, out, photo_ref, status)

    part = result.last("check_part_for_build")
    if part is not None:
        rif = part.get("revision_in_force", {})
        out(f"Build order: {part['build_order']['title']}")
        out(f"Revision in force: Rev {rif.get('revision')} ({rif.get('source', {}).get('ref')}) "
            f"{'- ' + rif['change_note'] if rif.get('change_note') else ''}")
        for n in part.get("notes", []):
            out(f"Note: {n}")
        out(f"\nDECISION: {part['decision'].upper()}")
        for r in part.get("reasons", []):
            out(f"  - {r}")
        verb = "move to sequencing" if part["decision"] == "cleared" else "put on hold and notify quality"
        if confirm(f"Person confirms: {verb}?"):
            ev = bridge.record_evidence(item["item_ref"], f"Logistics check {part['decision']} for "
                                        f"{part['build_order']['title']}", result=part["decision"],
                                        photo_ref=photo_ref, note="; ".join(part.get("reasons", [])) or None,
                                        source_document=rif.get("source", {}).get("ref"))
            out(f"Evidence recorded: {ev.get('evidence_ref')} (mock vault)")
        return status

    blockers = result.last("check_blockers") or {}
    for b in blockers.get("blockers", []):
        out(f"BLOCKER: {b['type'].replace('_', ' ')} - {b.get('title') or b.get('message')}")
    for w in blockers.get("warnings", []):
        out(f"Warning: {w['type'].replace('_', ' ')} - {w['title']} ({w.get('severity')}, {w.get('state')})")
    if status == "blocked":
        out("\nSTOP: work is blocked. A person must resolve the blockers first.")
        return status

    job = result.last("get_approved_job") or {}
    if job.get("status") != "ok":
        out(f"\nSTOP: {job.get('message', 'no approved job')}")
        return status

    for req in blockers.get("required_first", []):
        src = req["source"]
        out(f"\nREQUIRED FIRST: {src['title']} (Rev {src['revision']}, {src['ref']}, approved {src['approved_date']})")
        for s in req["steps"]:
            out(f"  {s}")
        if not confirm("Person confirms the bulletin steps are done?"):
            out("Stopped before the main procedure.")
            return "stopped"
        bridge.record_evidence(item["item_ref"], f"Completed {src['title']}", result="done", photo_ref=photo_ref,
                               source_document=src["ref"])

    src = job["source"]
    out(f"\nAPPROVED PROCEDURE: {src['title']}")
    out(f"Source: {src['ref']}, Rev {src['revision']}, approved by {src['approved_by']} on {src['approved_date']}")
    for n in job.get("notes", []):
        out(f"Note: {n}")
    for i, step in enumerate(job["steps"], start=1):
        out(f"  {step}")
        if not confirm(f"Person confirms step {i} is done?"):
            bridge.record_evidence(item["item_ref"], f"{src['title']} stopped at step {i}", result="stopped",
                                   step=i, photo_ref=photo_ref, source_document=src["ref"])
            out(f"Stopped at step {i}. Evidence recorded.")
            return "stopped"
        bridge.record_evidence(item["item_ref"], f"{src['title']} step {i}", result="done", step=i,
                               photo_ref=photo_ref, source_document=src["ref"])
    out("All steps confirmed. Evidence recorded in the mock vault.")
    return status


def _present_mission(mission, item, result, bridge, confirm, out, photo_ref) -> str:
    out(f"Site: {mission['site']}   Operator: {mission['operator']}")
    for c in mission["checks"]:
        out(f"  [{'OK' if c['ok'] else 'NO'}] {c['check'].replace('_', ' ')}: {c['detail']}")
    for n in mission.get("notes", []):
        out(f"Note: {n}")
    decision = mission["decision"]
    out(f"\nDECISION: {decision.replace('_', '-').upper()}")
    if decision == "go":
        src = mission["plan_source"]
        out(f"Approved route: {src['title']} Rev {src['revision']} ({src['ref']}, approved {src['approved_date']})")
        for step in mission["plan_steps"]:
            out(f"  {step}")
        if confirm("Person authorizes launch?"):
            ev = bridge.record_evidence(item["item_ref"], f"Pre-flight GO for {mission['site']}", result="go",
                                        photo_ref=photo_ref, source_document=src["ref"])
            out(f"Launch authorized. Evidence recorded: {ev.get('evidence_ref')} (mock vault)")
        else:
            out("Launch not authorized by the person.")
            return "not_authorized"
    else:
        out("Do not launch. Reasons:")
        for r in mission["reasons"]:
            out(f"  - {r}")
        if confirm("Person acknowledges the no-go?"):
            ev = bridge.record_evidence(item["item_ref"], f"Pre-flight NO-GO for {mission['site']}", result="no_go",
                                        photo_ref=photo_ref, note="; ".join(mission["reasons"]))
            out(f"No-go recorded: {ev.get('evidence_ref')} (mock vault)")
    return decision


def _present_reading(result, item, bridge, confirm, out, photo_ref, status) -> str:
    crit = result.last("get_inspection_criteria")
    if crit.get("status") != "ok":
        out(f"\nSTOP: {crit.get('message')}")
        return status
    for c in crit["criteria"]:
        src = c["source"]
        out(f"Approved criteria: {src['title']} Rev {src['revision']} ({src['ref']}, approved {src['approved_date']})")
        for line in c["checklist"]:
            out(f"  {line}")
    reading = result.last("evaluate_reading")
    if reading is None:
        out("\nSTOP: the agent did not report a gauge reading. A person must read the gauge.")
        return "no_reading"
    if reading.get("status") not in ("within_limits", "out_of_limits"):
        out(f"\nSTOP: {reading.get('message')}")
        return status
    out(f"\nReading: {reading['measurement_point']} = {reading['value']} {reading['unit']} "
        f"(limits {reading['limit_min']} to {reading['limit_max']} {reading['unit']})")
    out(f"RESULT: {reading['status'].replace('_', ' ').upper()}")
    if not confirm("Person confirms the reading matches the photo?"):
        out("Reading not confirmed. Nothing recorded.")
        return "not_confirmed"
    ev = bridge.record_evidence(item["item_ref"], f"{reading['measurement_point']} reading {reading['value']} "
                                f"{reading['unit']}", result=reading["status"], photo_ref=photo_ref,
                                source_document=reading["source"]["ref"])
    out(f"Evidence recorded: {ev.get('evidence_ref')} (mock vault)")
    if reading["status"] == "out_of_limits":
        if confirm("Person approves raising a deviation?"):
            dev = bridge.draft_deviation(item["item_ref"],
                                         f"{reading['measurement_point']} on {item['title']} out of limits: "
                                         f"{reading['value']} {reading['unit']}", severity="Major",
                                         note=f"Evidence {ev.get('evidence_ref')}; limits {reading['limit_min']}"
                                              f"-{reading['limit_max']} {reading['unit']}")
            out(f"Deviation raised: {dev.get('deviation_ref')} (mock vault). Quality is notified.")
    return reading["status"]
