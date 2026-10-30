# CLAUDE.md — Project Lantern POC (vman)

Context for Claude Code working in this folder.

## What this is
A proof of concept: a physical agent (camera, drone or robot) with a general-purpose brain
(Google Gemini Robotics-ER 2) asks a **mock M-Files vault** what is official and approved for the
exact item it sees, then a person confirms and the app records evidence.

Positioning: the model decides what to look up; M-Files says what is true.

## Hard rules for this project
- **Never connect to a real M-Files vault or the M-Files MCP server.** The vault is a local SQLite
  mock (`lantern/mockvault`). Real vaults may contain sensitive papers.
- **All data is fictional.** Do not add real customer, product or person names.
- **Never send real customer documents or images to Gemini.** Use the generated samples only.
- Keep the bridge rules intact (see below). Any new AI tool must be read-only.
- Write tools (`record_evidence`, `draft_deviation`) are app-only, called after a person confirms.
  They must never appear in `TOOL_DECLARATIONS` or `dispatch`.

## Bridge rules (lantern/bridge/tools.py)
1. Identity comes from the session (user + agent), never from model arguments.
2. Every read checks ACL components for BOTH user and agent (all components must grant).
3. Only released/approved versions are used; newer drafts are reported in `notes` but ignored.
4. Exact identifier matches only; unknown/ambiguous -> refuse, offer close matches for a person.
5. Steps and criteria are returned verbatim with source (ref, revision, approver, date).
6. Numeric decisions (limits, dates, effectivity) are made in the bridge, not by the model.

## Commands
```bash
python -m pytest -q                       # 42 tests, offline
python -m lantern.cli demo                # 12 scenarios, offline simulation, auto-confirm
python -m lantern.cli demo --only d       # drone scenarios only (m, l, d prefixes)
python -m lantern.cli demo --mode gemini  # needs GEMINI_API_KEY
python -m lantern.cli run --image samples/gauge_TK-102.png --inspect --user mikko.pilot --today 2026-10-10
python -m lantern.cli audit
python scripts/make_samples.py            # regenerate sample images
```
Use `--today 2026-10-10` for repeatable certificate/permit checks with the sample data.

## Layout
- `lantern/mockvault/vault.py` — SQLite mock: object types, classes, properties (built-in IDs 0, 100, 38, 39),
  versions, workflows/states, named ACLs + components, audit log.
- `lantern/mockvault/seed.py` — fictional structure and data (manufacturing, logistics, drone inspection).
- `lantern/bridge/tools.py` — AI tools + app-only writes + `TOOL_DECLARATIONS` + `dispatch`.
- `lantern/agent/agents.py` — `GeminiAgent` (function-calling loop) and `OfflineAgent` (simulated perception
  from the sidecar `.json` next to each image).
- `lantern/app.py` — what a person sees and confirms; `SCENARIOS`.
- `lantern/cli.py` — command line.
- `tests/` — bridge rules, drone features, end-to-end scenarios, Gemini loop with a fake client.

## Scenarios
m1–m3 manufacturing (restart engine), l1–l4 logistics (part revision for build order),
d1–d5 drone inspection (pre-flight go/no-go, gauge readings).

## Status and next steps
- Gemini mode is untested against the live API. First task: run `demo --mode gemini` and record
  identifier and gauge-read accuracy.
- Ideas: phone-camera web UI; simulated robot-arm skill stubs; drone-to-ground-robot hand-off;
  repair verification loop (finding -> approved repair procedure -> re-inspection).
