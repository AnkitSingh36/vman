# CLAUDE.md — Project Mark-1

Context for Claude Code working in this folder.

## What this is
A phone-camera AI assistant that works like an experienced engineer standing next to you. A person
points a phone at a device. Mark-1:
1. Recognises the exact unit (brand/model from the image, then service tag).
2. Uses ONLY approved company knowledge from an M-Files-like vault, always the version that applies
   to that exact unit (board revision, software version).
3. Reasons about what is wrong (belief over causes), picks the most useful next check, talks the
   person through it.
4. Shows guidance on the camera view (blinking key, highlighted part, "x-ray" blueprint overlay).
5. Guides approved steps one by one; a person always does the action and confirms.
6. Learns from confirmed cases, practises in a simulated training gym, and earns autonomy per task
   from its proven record.

Positioning: the AI decides WHAT to look up and HOW to reason; the vault says WHAT IS TRUE; fixed
guardrails say WHAT IS ALLOWED.

Mark-1 is a fresh build. The earlier POC lives at `..\vman` — READ it for patterns (mock vault,
bridge, Gemini loop), never modify it.

## Hard rules
- Never connect to a real M-Files vault or the M-Files MCP server. Use the local mock vault (SQLite).
- All data is fictional. No real customer data. Never send real customer documents or images to Gemini.
- Guardrails never learn: approved-revision selection, permissions (person AND agent, all ACL
  components must grant), hazard rules, preconditions, human confirmation for critical steps.
- AI tools are read-only. Writes (evidence, deviations, case records, autonomy promotions) are
  app-only and happen only after a person confirms. They must never appear in the tool declarations
  or the dispatcher exposed to the model.
- The agent never clicks, flashes firmware or acts physically by itself. The demo stops before any
  real BIOS flash.
- Instructions shown to the user come from vault results, never from model-written text.
- Exact identifier matches only; unknown or ambiguous -> refuse and ask a person.
- Machine-agnostic code: no laptop logic in code; everything comes from vault data and metadata.
- `.env` holds `GEMINI_API_KEY` and is never committed.

## Architecture
```
phone camera -> Planner (Gemini Robotics-ER 2, function calling)
             -> Learning engine -> Guardrails -> Mock vault
             Person answers, confirms, corrects.
```
- Planner is pluggable: Gemini (default model id `gemini-robotics-er-2-preview`, configurable,
  google-genai SDK), offline simulation for tests, possibly a Microsoft Foundry model later.
- Executor is pluggable: `SimulatedExecutor` now, `RhoAlphaExecutor` stub for later.
- Learning engine (pure functions, unit-tested): Bayes belief; information-gain/cost next check with
  stop at tau = 0.90 and escalation to a person; counts with document prior (a0 = 1 + m*l_docs,
  b0 = 1 + m*(1 - l_docs)); training gym (reward = correct - lambda*cost; accuracy, effort, Brier);
  per-unit baseline + CUSUM (k = sigma/2, h = 5 sigma); earned autonomy via Wilson lower bound
  (levels 0 suggest, 1 decide+confirm, 2 decide+inform, 3 act alone; promotion needs threshold,
  minimum n and a recorded person approval); blueprint graph G=(V,E) for power/dependency
  propagation with plain-word explanations.
- Mock vault: object types, classes, properties (built-in IDs 0 Name, 100 Class, 38 Workflow,
  39 State; custom from 1000), versions, workflows/states (Draft, In review, Approved, Obsolete),
  named ACLs with components, users/groups (person + agent identities), audit log of every read/write.
- Web app: FastAPI + single static HTML/JS page, no build step, phone-friendly.

## Layout
`mark1/vault`, `mark1/bridge`, `mark1/engine`, `mark1/gym`, `mark1/planner`, `mark1/executor`,
`mark1/webapp`, `scripts/`, `samples/`, `tests/`, `docs/`. See PLAN.md for the 10-day build plan.

## Commands
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest -q          # offline tests
```
More commands (demo, gym, webapp) are added as the plan steps land.

## Status
Skeleton only. Next: step 1 of PLAN.md. Source docs expected in `docs/`:
`Project-Mark-1-Mathematics.pdf`, `mark1_learning_reference.py`.
