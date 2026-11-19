# Mark-1 web client (J)

Phone web app for the R0 synthetic visual investigation: camera snapshots, identity confirmation, view/question/explanation/check panels, chat, push-to-talk voice, read-aloud, 2D cutaway renderer, stop/hazard, recovery and summary.

Owner: J (`mark1/web/**`). It consumes A's v2 contract; it never talks to a model or vault and applies no applicability policy.

> Synthetic demo only. Fictional data. No real M-Files, customer images or documents.

## Requirements

- Node.js 20+ (tested with 22.18.0) and npm.
- For `npm run e2e`: an installed Microsoft Edge or Google Chrome (no browser download).

## Commands (run from `mark1/web`)

| Command | What it does |
| --- | --- |
| `npm ci` | Install the exact locked dependencies |
| `npm run dev` | Start the app with the in-browser **fake backend** at http://localhost:5173 (use `--host` URL on a phone in the same network) |
| `npm run dev:real` | Start the app against A's backend; `/v2` is proxied to `MARK1_BACKEND_URL` (default `http://127.0.0.1:8000`) |
| `npm test` | Unit, contract-conformance and UI tests (Vitest + jsdom) |
| `npm run typecheck` | TypeScript strict check |
| `npm run build` | Type-check and production build to `dist/` |
| `npm run e2e` | With `npm run dev` running: drives the full phone journey in Edge/Chrome and writes screenshots to `e2e/out/` |

## Where to verify

- http://localhost:5173/ — live app (fake mode). Open **Fake backend controls** at the bottom to switch scenario (main path, unreadable label, diagram unavailable) or inject faults (server unreachable, lost response, 503, frozen leases, pending write, evaluation delay).
- http://localhost:5173/?gallery — every canonical state/variant fixture from `contracts/all-fixtures.json` and `examples.json` rendered by the real panels (read-only). Filter with `?gallery=explaining`, `?gallery=identity_view`, etc.
- Browser devtools → Network → Offline: guidance, highlights and speech are hidden/cancelled; Stop still works locally.
- `npm test` output: 57 tests incl. schema validation of every fake response and request body against the canonical contract.

## Modes

| Mode | Transport | Use |
| --- | --- | --- |
| fake (default) | `src/fake/fakeServer.ts` in the browser | UI development and tests before A's server exists |
| real (`--mode real`) | `fetch` same-origin `/v2` with an in-memory bearer token | Integration with A's backend (A-08) |

The fake backend is a **UI test double**, not A's engine stub or a production engine/catalog. Its text, checks, templates and diagram come from A's canonical synthetic catalog (`contracts/request-fixtures.json`), imported read-only via the `@contracts` alias, and it issues fresh leases, revisions and receipts. Its next-step logic mirrors `scenario-fixtures.json` only so the UI can be exercised.

## Layout

```
src/api/types.ts          Contract 2.0 types (mirror of A's schemas)
src/api/client.ts         Transport, HTTP client, Idempotency-Key, X-Command-Id/State, errors
src/api/commands.ts       Stable key per intent, retry with same key/payload
src/api/diagram.ts        Renderer guard (integer 0..1000, no dangling edges/unknown highlights)
src/state/lease.ts        Lease deadline (<=15 s from local receipt), hide reasons
src/state/controller.ts   Session controller: polling, freshness, commands, local stop, history
src/speech/speech.ts      Browser speech adapter (recognition -> editable text; read-aloud)
src/fake/fakeServer.ts    In-browser fake backend (test double)
src/components/*          Panels: identity, camera, view, question, explanation, cutaway, check, chat, stop, summary, gallery
tests/*                   Vitest suites (contract, controller/failure paths, units, UI)
e2e/journey.mjs           Browser journey (playwright-core, installed Edge/Chrome)
```

## Behaviour guarantees (spec 05)

- Panel is chosen only from `status`; `AWAITING_VIEW`/`AWAITING_ANSWER`/`EXPLAINING`/`READY` show exactly their interaction/check; anything else shows no guidance.
- Refresh every 5 s (1 s while `EVALUATING`/`RECORD_PENDING`). Guidance, highlights and speech are hidden/cancelled on lease expiry, refresh failure, background, offline or stop; on resume the current state is fetched before anything is shown again. Before every submission the current state is re-fetched and the command is aborted if the step changed.
- One stable Idempotency-Key per intentional command (op + exact payload); exact retries reuse key and payload; a changed answer is a new key. Lost responses are retried with the same key; if still unknown the UI says **not confirmed saved** and reconciles on reconnect. Keys are memory-only.
- Stop / Report hazard is on every active screen, takes effect locally immediately (hides guidance, cancels speech and camera), is never blocked by a pending command, and is re-sent with the same key when the connection returns.
- Voice: consent dialog, push-to-talk, editable transcript, explicit Send as `VOICE_TRANSCRIPT`; no audio upload. Read-aloud speaks only `interaction.text` / `check.instruction`, with stop and mute. Unsupported browsers fall back to typing.
- Images: only user-selected JPEG/PNG ≤ 10 MiB; snapshots are re-encoded via canvas (metadata stripped, ≤ 2048 px provisional). Live preview never leaves the device.
- Diagram: React-built SVG from validated authored nodes/edges only, labelled “authored diagram — not an internal camera observation”, source/version shown, SUSPECTED highlight with legend; invalid/missing diagram → explicit text fallback. All text is rendered as text.
- No browser storage: session id lives only in the URL fragment so reload can resume.

## Open dependencies

See [J contract review](../docs/ux/J-contract-review.md) and [UX state inventory](../docs/ux/J-01-journey-and-states.md).

## Connect to FastAPI locally

From `D:\vman\mark1`, using the installed backend environment:

```powershell
.venv/Scripts/python.exe -m mark1.server init
.venv/Scripts/python.exe -m uvicorn mark1.server.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Keep the generated demo bearer token private. In a second terminal:

```powershell
cd D:\vman\mark1\web
npm.cmd ci
npm.cmd run dev:real
```

Open `http://localhost:5173`, paste the token into **Demo bearer token**, and select **Use demo token**. The token is never placed in browser storage, the URL, source code or a `VITE_*` build variable. Re-enter it after reload; the session ID in the URL fragment resumes the session. If a token is rejected, reload and enter a valid token. Authentication is checked by the server on each API call.

Start the no-power investigation, type `DEMO-LAPTOP` in **Label text**, then **Look up** and explicitly confirm `DEMO-C1`. The server stub does not read identity photos. Continue with preflight `CLEAR`, upload the supplied fictional `e2e/fictional-frame.png` for the requested investigation view, answer `NO`, observe `OFF`, and continue from the advisory diagram to the summary.

The dev proxy forwards `/v2` to `http://127.0.0.1:8000`; set `MARK1_BACKEND_URL` in a local environment file for another backend address. This is a development connection, not production hosting. Phone camera access needs a secure HTTPS origin; a LAN HTTP URL is not sufficient for the camera test matrix.

To run the browser journey against isolated FastAPI/SQLite automatically (installed Edge/Chrome and the backend `.venv` required):

```powershell
npm.cmd run e2e:real
```

The runner starts its own backend and Vite on loopback ports 18761/15173, issues a temporary token, verifies unauthenticated requests are rejected, and checks durable events plus authenticated reload/resume. It shuts down both servers and deletes its temporary database. Override `MARK1_PYTHON`, `E2E_BACKEND_PORT`, `E2E_WEB_PORT`, or `E2E_CHANNEL` when needed. Screenshots go to ignored `e2e/out/` and do not capture the token entry.

This proves a browser-to-backend journey with a deterministic engine. Live AI, phone camera/speech acceptance and pilot gates remain pending. The separately reported prerequisite-withdrawal defect remains open.
