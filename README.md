# Lantern POC (vman): physical agent + mock M-Files vault

A proof of concept for Project Lantern. A camera-equipped agent with a general-purpose brain
(Gemini Robotics-ER 2) looks at a real item, asks a **mock M-Files vault** what is official and
approved for that exact item, and shows the answer with its source. A person confirms each step
and the app records evidence.

> No real vault is used. The mock vault is a local SQLite database that copies the *structure* of
> M-Files (object types, classes, properties, versions, workflow states, ACL components), based on
> internal Confluence documentation. All data is fictional.

## The idea in one line

The model decides **what to look up**. M-Files says **what is true**. The app only shows
instructions that came from the vault, never instructions written by the model.

```
 camera image ──► Gemini Robotics-ER 2 ──tool calls──► Bridge ──► Mock vault (SQLite)
                  (reads label, plans)                 (rules)     (approved knowledge)
                          │                               ▲
                          ▼                               │
                 app shows vault result ──person confirms──┘ record_evidence (app only)
```

## Two hero stories

| Story | Scenario | What the vault decides |
|---|---|---|
| Manufacturing | `m1` ME450-21877, restart after unplanned stop | Mandatory bulletin first, then Rev C steps verbatim. Newer Rev D draft is ignored. Minor deviation shown as a warning. |
| Manufacturing | `m2` ME450-19950 | Blocked: inspection certificate expired. No steps shown. |
| Manufacturing | `m3` ME450-21878 (not in vault) | Refused. Close match offered for a person to confirm. No guessing. |
| Logistics | `l1` container CNT-48812 for BO-7781 | Hold: label is Rev A, Rev B in force from 2026-10-01 (ECO-5521). |
| Logistics | `l2` CNT-48807 | Hold: open Major nonconformance on the batch. |
| Logistics | `l3` CNT-48830 | Hold: certificate of conformity expired. |
| Logistics | `l4` CNT-48850 | Cleared for sequencing. |

### Drone inspection

| Scenario | What the vault decides |
|---|---|
| `d1` pre-flight, Tank farm North, mikko.pilot | GO: approved route Rev 3 (Rev 4 draft ignored), valid permit, drone certificate valid, operator qualified |
| `d2` pre-flight, Tank farm South | NO-GO: work permit expired |
| `d3` pre-flight, sara.pilot | NO-GO: operator qualification expired (operator comes from the session, not the model) |
| `d4` gauge PI-102 on TK-102 reads 7.4 bar | OUT OF LIMITS (0.5–6.0 bar). Evidence filed; deviation raised after a person approves |
| `d5` gauge PI-101 on TK-101 reads 3.1 bar | WITHIN LIMITS. Evidence filed |

Drone AI tools: `check_mission_readiness`, `get_inspection_criteria`, `evaluate_reading` (the bridge, not the model,
compares the reading with the approved limits). App-only write: `draft_deviation`.

## Rules the bridge enforces

1. **Identity comes from the session, not the model.** Every read is checked for both the human
   user and the agent identity.
2. **ACL components.** As in M-Files, the class component and the object component must both grant access.
3. **Approved versions only.** The newest version in a released state is used; newer drafts are reported but ignored.
4. **Exact matches only.** Unknown or ambiguous identifiers are refused.
5. **Verbatim steps with source:** document, version, revision, approver and approval date.
6. **No AI write access.** `record_evidence` is not an AI tool. The app calls it after a person confirms.
7. **Audit log** of every lookup and write: actor, on behalf of whom, what, when.

## How it maps to M-Files concepts

| M-Files concept | In the mock vault |
|---|---|
| Object types | Document (0), Equipment, Part, Batch, Deviation, Certificate, Build order, Evidence, Permit, Qualification |
| Classes | Maintenance procedure, Service bulletin, Engineering analysis, Engine, Purchased part, Incoming batch, Nonconformance, Certificate, Build order, Field evidence |
| Built-in properties | Name or title (0), Class (100), Workflow (38), State (39) |
| Custom properties | IDs from 1000: Serial number, Revision, Effective from, Valid until, Related equipment, … |
| Lookups | `lookup` and `multilookup` property types holding object IDs |
| Versions | Every change is a new version; history is kept |
| Workflows | Document control, Part release, Deviation handling, Evidence review |
| Named ACLs and components | Class "automatic" component + object component, all must grant |
| Users and groups | Technician, logistics operator, quality, engineering, physical agent |

## Setup

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python scripts/make_samples.py        # regenerate sample images (already included)
python -m pytest -q                   # 42 tests, no network needed
```

## Run

Offline mode needs no API key. It simulates perception from the `.json` file next to each image
and runs the same tool plan. It is clearly labelled as a simulation.

```bash
python -m lantern.cli demo                                   # all 12 scenarios, auto-confirm
python -m lantern.cli demo --only d                          # drone scenarios only
python -m lantern.cli run --image samples/nameplate_ME450-21877.png \
    --task "Restart after unplanned stop" --today 2026-10-10   # asks you to confirm each step
python -m lantern.cli run --image samples/label_CNT-48812.png \
    --build-order BO-7781 --user ravi.logistics --today 2026-10-10
python -m lantern.cli run --image samples/drone_UAV-D7-0041.png \
    --site "Tank farm North" --user mikko.pilot --today 2026-10-10
python -m lantern.cli run --image samples/gauge_TK-102.png --inspect --user mikko.pilot --today 2026-10-10
python -m lantern.cli audit                                  # audit log of the local DB
```

Gemini mode uses Gemini Robotics-ER 2 to read the image and decide which tools to call:

```bash
export GEMINI_API_KEY=...            # restricted key from Google AI Studio
python -m lantern.cli demo --mode gemini
python -m lantern.cli run --mode gemini --image samples/nameplate_ME450-21877.png \
    --task "Restart after unplanned stop" --today 2026-10-10
```

Override the model with `--model` or `LANTERN_MODEL`. `--today 2026-10-10` keeps certificate
checks repeatable with the sample data. `run` stores data in `lantern_poc.db` (created and seeded if missing).

## Project layout

```
lantern/
  mockvault/vault.py   SQLite mock of the vault: structure, versions, workflows, ACLs, audit
  mockvault/seed.py    Fictional structure and data for both stories
  bridge/tools.py      The four AI tools, the app-only evidence writer, tool declarations
  agent/agents.py      Gemini ER 2 function-calling loop and the offline simulation
  app.py               What a person sees and confirms; scenarios
  cli.py               Command line
scripts/make_samples.py  Fictional nameplates and labels
samples/                 Images + sidecar JSON for offline mode
tests/                   Bridge rules, drone features, end-to-end scenarios, Gemini loop with a fake client
CLAUDE.md                Context and rules for Claude Code
```

## Limits (honest list)

- **Gemini mode has not been run against the live API yet.** The loop is tested with a fake client
  and builds real `google-genai` request objects, but reading accuracy on these images is unmeasured.
- Gemini Robotics-ER 2 is a **preview** model. Expect changes.
- Images and prompts go to Google in Gemini mode. Use only the fictional samples until data terms are approved.
- The mock vault copies M-Files structure, not its API, search, or permission edge cases
  (pseudo-users, metadata-driven permissions).
- Writes are local only. The real M-Files MCP beta is read-only.

## Next steps

1. Run `demo --mode gemini` and measure identifier-read accuracy on 20–30 varied photos.
2. Add a small web UI (phone camera → result → confirm).
3. Add skill stubs for a simulated arm so the same job package drives robot actions.
