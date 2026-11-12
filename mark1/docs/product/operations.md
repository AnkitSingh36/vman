# Local backend operations and handoff

11 November 2026. Synthetic developer use only. Run one worker from an editable source checkout. These instructions do not authorize a real vault, live model or operational repair pilot.

## Install and run on Windows

From `D:\vman\mark1`:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.lock.txt
.venv/Scripts/python.exe -m pip install --no-deps --no-build-isolation -e .
.venv/Scripts/python.exe -m mark1.server init
.venv/Scripts/python.exe -m uvicorn mark1.server.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

The environment already created during implementation can be reused. `init` prints a newly generated demo token once and its hash for later revocation. Store the token privately; do not commit it, put it in URLs or share terminal screenshots. There is no default token. Optional `.env` settings are documented in `.env.example`; provider credentials are unnecessary.

Open `http://127.0.0.1:8000/docs` and use **Authorize** with that token. The Swagger definition is generated from the canonical OpenAPI document with schema references expanded. `/health` reports synthetic-demo mode. API responses include `X-Mark1-Mode: synthetic-demo-only` and `Cache-Control: no-store`.

The development lock includes `httpx`, pytest and the optional Google SDK used by the original Lantern tests. Runtime dependencies are separately listed in `pyproject.toml`. A clean installation can require Internet access to the package registry; running the stub and tests makes no model/vault calls.

## Verify

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m mark1.server.testing.demo
.venv/Scripts/python.exe docs/specs/Mark1-Team-Spec/contracts/validate-contracts.py
.venv/Scripts/python.exe docs/specs/Mark1-Team-Spec/contracts/validate-hashes.py
```

From the repository root, rerun the unchanged Lantern tests with `mark1/.venv/Scripts/python.exe -m pytest -q tests`. The scripted demo exercises real HTTP handlers through the in-process ASGI test client, uploads a generated image and prints the flow through an advisory diagram to escalation. It creates and cleans a temporary database and never prints its token. It does not perform visual perception or a real repair.

## Sessions, retries and restart

Create `/v2/sessions` with a supported workflow/symptom and a stable `Idempotency-Key`. Every later mutation also supplies the current `expected_revision`. Use the returned command headers to reconcile at `/v2/sessions/{id}/commands/{command_id}`. Reuse the original key and identical payload after a lost response. Changed payloads/new stale commands return 409. GET current state before continuing.

Human commands commit locally before another inference is scheduled. This local store has no external write acknowledgement to wait for; `RECORD_PENDING` is reserved by the contract for unresolved authoritative writes. A 202 EVALUATING response can have a PERSISTED human-command receipt: it means the human report was saved and AI evaluation is still pending. On 503, do not assume the command failed or saved; reconcile using the same key.

Stop the server normally with Ctrl+C. On startup, interrupted EVALUATING/RECORD_PENDING sessions become terminal UNKNOWN instead of resuming old instructions. Start a new session after a terminal state. Do not run multiple workers/processes against this demo database: startup reconciliation assumes one backend owner.

## Kill switch, permissions and revocation

These are local operator commands, never public/model tools:

```powershell
.venv/Scripts/python.exe -m mark1.server policy demo-org demo-laptop-no-power BLOCKED
.venv/Scripts/python.exe -m mark1.server policy demo-org demo-laptop-no-power UNAVAILABLE
.venv/Scripts/python.exe -m mark1.server access demo-org demo-agent workflow:demo-laptop-no-power DENY
.venv/Scripts/python.exe -m mark1.server withdraw source:DEMO-GUIDE:2
```

Use only the action appropriate to the incident. BLOCKED/UNAVAILABLE are observed on the next serve/submit. Their recovery is an explicit local authority change, followed by a **new** session; stopped sessions do not revive. Workflow grant denial returns 403, while protected restrictions use generic reasons. Token revocation uses `revoke-token TOKEN_HASH` with the hash printed by init, never the raw bearer token.

Withdrawn/Obsolete/Superseded records cannot be reapproved through the CLI. Republishing the same catalog cannot undo withdrawal. A new approved record must use a new version and pass publication checks. `publish CATALOG_JSON MANIFEST_JSON` accepts only synthetic approval/rights records; the manifest lists `source_id`, `version` and source `file` paths relative to itself. V owns actual knowledge authoring. Both catalog and individual approved record versions are immutable, and source hashes must match exact supplied bytes.

J must independently hide active prompts/highlights and cancel speech on stop, offline, backgrounding, failed refresh or <=15-second lease expiry. The backend cannot recall previously shown/heard content. A known hazard requires an immediate local user stop even before server acknowledgement.

## Backup, restore and deletion

```powershell
.venv/Scripts/python.exe -m mark1.server backup out/backup.sqlite
```

Backup refuses an existing destination and verifies SQLite integrity. Stop the server before restoring. Restore into a new file, keep the original, and verify it before any replacement. To inspect a restored copy without overwriting the current database:

```powershell
$env:MARK1_DB = 'out/backup.sqlite'
.venv/Scripts/python.exe -m uvicorn mark1.server.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Startup recovery still applies, including in restored copies. Restore does not authorize stale sources or grants: reconcile current withdrawals, kill-switch state and token revocations before use. Automated external authority reconciliation is not implemented; this is one reason production restoration remains gated.

For a terminal demo session, `erase-session SESSION_ID --confirm-id SESSION_ID` deletes its events, image bytes, inference requests and session/message content in one operator transaction. Minimal command hashes, scope/IDs and authority audit records remain as declared replay tombstones; a retried create for the erased session returns 404 instead of recreating it. Normal application events are append-only. SQLite secure-delete is enabled; this is not a guarantee of forensic erasure on the underlying disk. Backups and filesystem snapshots must expire separately under the operator's retention policy. There is no automatic timer or production retention approval yet.

## Consumer handoffs

J consumes the published API, fixtures, bearer authentication and command reconciliation rules. Camera/voice/browser testing is J-owned. No frontend is included here.

V supplies an engine object with `model_config_version`, `prompt_version` and an async `propose(request)` method. Inject it into `create_app(settings, engine)`; there is no provider selected by this backend. The request is deep-copied before handoff and must be echoed with its binding fields. Only A may resolve media via `service.resolve_image(token, inference_id, cleared_handle)`, while that inference/context is current. This resolver is not a public URL or tenant-wide lookup. V's adapter must use approved egress/data terms and bounded provider/tool calls; the supplied 8-turn/16-call request budget is not proof of metered live execution.

Do not use `asyncio.run` or a blocking provider client inside the engine coroutine. The adapter must cooperate with cancellation; a noncooperative/CPU-blocking adapter has not been evaluated and needs process isolation or different execution design before integration.
