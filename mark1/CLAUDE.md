# Mark-1 project context and rules

## Current baseline

Use `docs/specs/Mark1-Team-Spec/00-START-HERE.md` and its split specifications/contracts, version 2.0, 10 November 2026. They supersede the previous BIOS/overheating/10-day/learning-first plan. The A-owned local backend now lives in the nested `mark1/server/` package. V/J implementation and pilot acceptance remain pending.

R0: visual investigation on one fictional laptop/no-power scenario set, selected camera snapshots, contextual questions, voice/chat, source-backed 2D cutaway, advisory suspected subsystem, approved external checks and durable human observations. Camera is the eye; AI investigates; approved knowledge comes through a trusted bridge; backend authorizes; human acts. The cutaway is a diagram, not internal camera sight. Streaming/tracked AR/learning/autonomy are deferred.

## Hard rules

- Never connect to a real M-Files vault or M-Files MCP. Local mock only.
- Fictional/generated data only. Never send real customer images/documents to a provider.
- Preserve `../lantern/**` reference POC; do not modify it to implement Mark-1.
- A owns backend/contracts/state/policy/integration; V owns AI/prompts/provider/knowledge/diagram authoring; J owns frontend/capture/chat/voice/diagram rendering. No cross-owner implementation without recorded transfer.
- Tools exposed to models are read-only. Evidence/state writes are app-only after the relevant human command/confirmation.
- User+configured-agent permissions, exact applicability, lifecycle, hazards/preflight and prerequisites are deterministic backend rules; they never learn.
- Instructions and spoken guidance come from current authorized canonical catalog/template text, not raw model prose.
- Explicit human identity confirmation; no closest-match auto-selection or guessed service tag.
- No disassembly, battery handling, electrical probing, firmware flashing, bypass, remote execution or autonomous physical action.
- All machine-specific checks/questions/views/graphs belong in data/metadata, not hardcoded laptop policy.
- Never claim a suspected cause, human completion or persisted evidence is independently verified repair.
- Stop/expiry/offline invalidates visible guidance/highlights and speech. Retries cannot replay revoked instructions or duplicate logical evidence.
- Provider keys stay server-side in .env/config and are never committed.

## Implementation map

The outer `mark1/` directory is the project root; the nested `mark1/` directory is the single Python import root. A-owned backend source is nested `mark1/server/**`. Canonical contracts remain under `docs/specs/Mark1-Team-Spec/contracts/`, with no duplicate schema copy. See `docs/product/baseline-and-decisions.md` for the implemented path/stack choices. Prefer existing FastAPI/SQLite direction; J reviews web stack; V proposes configurable evaluated model. No model-specific live API is required for A's independent stub milestone.

Run contract checks per `docs/specs/Mark1-Team-Spec/contracts/README.md`. Rebuild combined spec with `python docs/specs/build_team_spec.py` from this directory. Schema checks validate artifacts, not runtime or product gates. Real pilot permissions, SME/source rights, browser speech consent, capacity and deployed versions remain explicit open decisions.

Use a new task branch for changes; the earlier direct-main specification commit was a one-time user exception. Backend startup/demo/tests are documented in `docs/product/operations.md`. Preserve the fake/production boundary and report A-08 real V/J integration and pilot hardening as pending.
