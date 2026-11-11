# Mark-1

A phone-friendly visual investigation assistant. The camera supplies selected views, the AI asks useful questions and chooses evidence, and a trusted bridge supplies applicable approved machine knowledge. A human controls the camera and performs every physical action.

## Current implementation baseline

[Team specification 2.0](docs/specs/Mark1-Team-Spec/00-START-HERE.md) is authoritative for the current build. R0 demonstrates one fictional laptop/no-power scenario set with guided camera snapshots, chat, speech with text fallback, a source-backed 2D cutaway/flow explanation, an advisory suspected subsystem and approved external checks with durable human observations.

The cutaway is a known machine diagram, not internal camera vision. Continuous streaming, tracked AR, verified-repair learning, training gym and autonomy remain later increments. Real diagnostic claims require separate evaluation; synthetic demonstrations are not a validated repair service.

## Status

The local A-owned backend is implemented with a deterministic integration stub. It provides authenticated API commands, policy/knowledge checks, durable evidence, safe image handling and an advisory diagram workflow. V's production AI and J's frontend are not included. No product release gate is closed. See [delivery plan](PLAN.md), [contracts](docs/specs/Mark1-Team-Spec/contracts/README.md) and [decision register](docs/specs/Mark1-Team-Spec/11-GATE-AND-DECISION-REGISTER.md).

## Work packages

- [A - Ankit](docs/specs/Mark1-Team-Spec/03-A-BACKEND-SPEC.md): API/auth, bridge/policy, state/evidence/media, contract validation, deployment and integration. Build independently against an engine stub.
- [V - Viditya](docs/specs/Mark1-Team-Spec/04-V-AI-SPEC.md): perception, investigation, retrieval/provider, knowledge/diagram authoring and evaluation.
- [J](docs/specs/Mark1-Team-Spec/05-J-FRONTEND-SPEC.md): camera/chat/voice, diagram renderer, phone screens and recovery.

[Backlog](docs/specs/Mark1-Team-Spec/09-BACKLOG.csv) assigns one owner per ticket. The chosen package/runtime and remaining dependencies are recorded in [backend decisions](docs/product/baseline-and-decisions.md). See [runbook and consumer handoff](docs/product/operations.md) for authentication, recovery, backup and V/J integration.

## Run the local backend

From this `mark1/` project directory:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.lock.txt
.venv/Scripts/python.exe -m pip install --no-deps --no-build-isolation -e .
.venv/Scripts/python.exe -m mark1.server init
.venv/Scripts/python.exe -m uvicorn mark1.server.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Use the generated bearer token in `http://127.0.0.1:8000/docs`. For an offline scripted journey, run `.venv/Scripts/python.exe -m mark1.server.testing.demo`. Tests: `.venv/Scripts/python.exe -m pytest -q`. No model key or real vault is needed.

Only one local worker and source-checkout/editable installation are supported. Demo mode refuses pilot configuration. The stub does not interpret images or diagnose real devices; the generated snapshot is an API/media demonstration.

## Data boundary

All development data is fictional/generated. Never connect to a real M-Files vault/MCP or send real customer images/documents to a model in this repository. Existing Lantern code is reference only. See [project rules](CLAUDE.md).
