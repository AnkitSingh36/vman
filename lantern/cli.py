"""Command line for the Lantern POC.

  python -m lantern.cli demo                      # all scenarios, offline, auto-confirm
  python -m lantern.cli demo --mode gemini        # same, using Gemini Robotics-ER 2 (needs GEMINI_API_KEY)
  python -m lantern.cli run --image samples/nameplate_ME450-21877.png --task "Restart after unplanned stop"
  python -m lantern.cli run --image samples/label_CNT-48812.png --build-order BO-7781 --user ravi.logistics
  python -m lantern.cli run --image samples/drone_UAV-D7-0041.png --site "Tank farm North" --user mikko.pilot
  python -m lantern.cli run --image samples/gauge_TK-102.png --inspect --user mikko.pilot
  python -m lantern.cli audit
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .agent.agents import DEFAULT_MODEL, OfflineAgent, ToolCall
from .app import SCENARIOS, present
from .bridge.tools import Bridge
from .mockvault.seed import build_vault
from .mockvault.vault import MockVault

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
AGENT_ID = "agent.er2-cell-1"


def open_vault(db: str) -> MockVault:
    if db == ":memory:":
        return build_vault()
    path = Path(db)
    if not path.exists():
        return build_vault(str(path))
    return MockVault(str(path))


def make_agent(mode: str, bridge: Bridge, model: str, verbose: bool):
    def show(tc: ToolCall):
        if verbose:
            print(f"  tool> {tc.name}({json.dumps(tc.args)}) -> {tc.result.get('status')}"
                  + (f" / {tc.result.get('decision')}" if tc.result.get("decision") else ""))
    if mode == "offline":
        return OfflineAgent(bridge, on_call=show)
    from .agent.agents import GeminiAgent
    return GeminiAgent(bridge, model=model, on_call=show,
                       on_wait=lambda s: print(f"  rate limited, waiting {s:.0f}s ...", flush=True))


def confirm_fn(auto: bool):
    if auto:
        def _auto(question: str) -> bool:
            print(f"  [auto-confirmed] {question}")
            return True
        return _auto

    def _ask(question: str) -> bool:
        return input(f"  {question} [y/N] ").strip().lower() in ("y", "yes")
    return _ask


def cmd_run(args) -> int:
    vault = open_vault(args.db)
    today = date.fromisoformat(args.today) if args.today else date.today()
    bridge = Bridge(vault, args.user, AGENT_ID, today=today)
    agent = make_agent(args.mode, bridge, args.model, verbose=True)
    result = agent.run(args.image, task=args.task, build_order=args.build_order, site=args.site,
                       inspection=args.inspect)
    outcome = present(result, bridge, confirm_fn(args.auto_confirm), photo_ref=Path(args.image).name)
    print(f"\nOutcome: {outcome}")
    return 0


def cmd_demo(args) -> int:
    today = date.fromisoformat(args.today)
    failures = 0
    scenarios = [sc for sc in SCENARIOS if not args.only or sc.name.startswith(args.only)]
    for sc in scenarios:
        vault = build_vault()  # fresh in-memory vault per scenario
        bridge = Bridge(vault, sc.user, AGENT_ID, today=today)
        agent = make_agent(args.mode, bridge, args.model, verbose=True)
        print("=" * 78)
        print(f"{sc.name}  [{sc.story}]  user={sc.user}  image={sc.image}")
        try:
            result = agent.run(SAMPLES / sc.image, task=sc.task, build_order=sc.build_order, site=sc.site,
                               inspection=sc.inspection)
        except RuntimeError as exc:  # e.g. daily Gemini quota: stop cleanly instead of a traceback
            print(f"\nSTOPPED: {exc}")
            return 2
        got = present(result, bridge, confirm_fn(True), photo_ref=sc.image)
        ok = got == sc.expected
        failures += 0 if ok else 1
        print(f"\nOutcome: {got}   expected: {sc.expected}   {'PASS' if ok else 'CHECK'}")
    print("=" * 78)
    print(f"{len(scenarios) - failures}/{len(scenarios)} scenarios matched the expected outcome.")
    return 0 if failures == 0 else 1


def cmd_audit(args) -> int:
    vault = open_vault(args.db)
    for e in reversed(vault.audit_entries(args.limit)):
        print(f"{e['ts']}  {e['actor']} for {e['on_behalf_of']}  {e['action']}  obj={e['object_id']}  {e['details']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lantern", description="Lantern POC: physical agent + mock M-Files vault")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mode", choices=["offline", "gemini"], default="offline")
    common.add_argument("--model", default=DEFAULT_MODEL)

    r = sub.add_parser("run", parents=[common], help="Run one image through the agent")
    r.add_argument("--image", required=True)
    r.add_argument("--task", help="Maintenance task, e.g. 'Restart after unplanned stop'")
    r.add_argument("--build-order", help="Build order for a logistics check, e.g. BO-7781")
    r.add_argument("--site", help="Site for a drone pre-flight check, e.g. 'Tank farm North'")
    r.add_argument("--inspect", action="store_true", help="Inspection round: read asset tag and gauge")
    r.add_argument("--user", default="anna.tech")
    r.add_argument("--db", default="lantern_poc.db", help="SQLite file (created and seeded if missing)")
    r.add_argument("--today", help="Override today's date (YYYY-MM-DD)")
    r.add_argument("--auto-confirm", action="store_true")
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("demo", parents=[common], help="Run all scenarios with auto-confirm")
    d.add_argument("--only", help="Run only scenarios whose name starts with this, e.g. d or m1")
    d.add_argument("--today", default="2026-10-10", help="Fixed date so certificate checks are repeatable")
    d.set_defaults(func=cmd_demo)

    a = sub.add_parser("audit", help="Show the audit log")
    a.add_argument("--db", default="lantern_poc.db")
    a.add_argument("--limit", type=int, default=40)
    a.set_defaults(func=cmd_audit)

    args = p.parse_args(argv)
    if args.cmd == "run" and not (args.task or args.build_order or args.site or args.inspect):
        p.error("run needs --task (maintenance), --build-order (logistics), --site (drone pre-flight) or --inspect")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
