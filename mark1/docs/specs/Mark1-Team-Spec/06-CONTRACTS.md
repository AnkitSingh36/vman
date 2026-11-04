# Contract v1 — public API and internal AI port

Sole schema editor: A. Reviewers: J and V. These are normative behavior contracts, not an implemented server. `contracts/session.schema.json` and `contracts/engine-proposal.schema.json` define response envelopes. The included `public-api.openapi.json`, request/catalog schemas and examples are the contract baseline. A-02 must verify framework representation and generated client types before implementation; it cannot silently change these semantics.

## Common conventions

HTTPS for pilot. Authenticated same-origin session/cookie or equivalent server-verified token; choose and record one in A-01. Cookie deployments require CSRF protection on mutations and secure/HttpOnly/SameSite settings. Every ID/reference is authorization-checked. Tenant and actor are obtained from auth, never trusted from body. Timestamps are UTC RFC3339; display in user's local time. Contract version is `1.0`. All mutation bodies forbid unknown fields. All mutations require an `Idempotency-Key` header; session mutations also require integer `expected_revision`. HTTP errors use the envelope from A's spec. Body IDs cannot override URL IDs.

## Public operations

| Operation | Request body (besides common fields) | Response / behavior |
| --- | --- | --- |
| `POST /v1/sessions` | `workflow_id`, `symptom_code`, optional bounded `symptom_text` | 201, Session AWAITING_IDENTITY; only allowlisted workflow/symptom |
| `POST /v1/sessions/{id}/images` | Multipart image file + expected revision + purpose `identity` | 201 `{image_id, session_id, revision, status: STORED}` after safe processing; no model call until authorized data terms; failures do not imply identity |
| `POST /v1/sessions/{id}/identity-candidates` | `expected_revision`, optional session-owned `image_id`, optional `manual_label` | 202 Session EVALUATING; poll GET; engine result becomes AWAITING_IDENTITY with candidates; failure → UNKNOWN; no instructions |
| `POST /v1/sessions/{id}/identity-confirmation` | `expected_revision`, `model_id`, `configuration_id`, optional `serial`, `human_confirmed:true` | 202 Session EVALUATING; confirm only supported model/configuration; bind identity, invalidate old proposals, begin independent policy evaluation |
| `GET /v1/sessions/{id}` | None | 200 current Session; READY must be freshly revalidated before return; include no protected details |
| `POST /v1/sessions/{id}/observations` | `expected_revision`, `check_id`, `check_version`, `observation_code`, `value`, optional session-owned `image_id`, `human_confirmed:true` | 200 persisted Session or 202 RECORD_PENDING; check/value schema must match active check; persist before reevaluation; retry same key |
| `POST /v1/sessions/{id}/outcome` | `expected_revision`, `human_reported_outcome: RESOLVED or UNRESOLVED`, `human_confirmed:true` | RESOLVED → COMPLETED only after persistence; UNRESOLVED → ESCALATED; no model can call this operation |
| `POST /v1/sessions/{id}/stop` | `expected_revision`, `reason_code` | 200 Session ESCALATED after durable stop event; invalidate pending inference |
| `GET /v1/sessions/{id}/events` | Optional pagination cursor | Authorized human/evidence/source summary; paginated immutable records with receipts; not model debug text |

Terminal session mutations return 409 except an authenticated/authorized replay of an already accepted command effect. Replay returns its immutable receipt plus freshly evaluated current Session, never old instructions. Long-running image/AI operations use 202 + GET polling (proposed one-second polling with capped backoff); no WebSocket/SSE required. Background request handling must survive/reconcile restart; use persisted job state or return a controlled UNKNOWN, never fabricate READY. `GET` never submits a new inference, confirmation or physical action.

`identity_candidates` objects contain `model_id`, `configuration_id`, `label_excerpt` and `basis: IMAGE or MANUAL`; they never claim physical truth. Limit candidates to three. Serial is optional and minimized; store only when applicability requires it. Manual labels still need human comparison/confirmation. If no supported match exists, offer escalation, not a closest-model guess.

`value` is typed according to the approved check's observation schema, not arbitrary executable text. Initial v1 forms use string enums only (including YES/NO where appropriate); no numerical instrument interpretation. A-02 freezes code/value constraints, input text bounds and allowed enum sets with V's catalog. Any optional note is evidence only and cannot change prerequisites without an explicitly supported observation.

## Session envelope semantics

Every response conforms to the schema. `revision` is a monotonic integer changed by state-changing events. `identity` is null until confirmed; candidate identities stay in `identity_candidates`. `current_check` is non-null only for READY. `receipt` refers to the last accepted human command, not AI output; a PERSISTED receipt includes a durable record ID. `human_reported_outcome` is never named verified repair. Non-ready responses cannot carry instructions. `reason_code` is safe structured explanation, never arbitrary model prose. Schema validity alone does not establish current authorization; A must enforce runtime invariants.

## Internal port

V implements one module entry point `propose(request) -> EngineProposal`, with cancellation/deadline support in the chosen Python implementation. A calls it; J cannot. V can stub/fake it without running HTTP.

`request` fields (owned/frozen by A): `contract_version`, `request_id`, `session_id`, `based_on_revision`, `context_hash`, `mode` (`IDENTIFY` or `NEXT_CHECK`), `workflow_id`, `confirmed_identity` (null only in IDENTIFY), `manual_label`, `cleared_images` (session-scoped sanitized image bytes/references, never arbitrary URL fetches), `approved_catalog` (check and source ID/version/hash, approved text, prerequisites and observation schemas), `observations` (typed values and provenance), `completed_check_ids`, `remaining_budgets` (turns, calls, wall-time deadline), `model_config_version`, `prompt_version`, `catalog_version`.

A computes `context_hash` over canonical decision-relevant input, excluding transient transport fields. A persists the inference request binding. An engine response must exactly echo request/session/revision/hash; mismatch or late response is rejected. Context binding is a correlation control, not proof the model reasoned correctly. Neither actor nor tenant may be supplied/changed by the model. A passes only authorized material and scopes any V retrieval to that input.

`EngineProposal` kinds:

- IDENTITY_CANDIDATES: up to three candidates from approved supported IDs; no auto-confirmation.
- PROPOSE_CHECK: exactly one approved `check_id` and `check_version`, references to approved sources; no instruction prose.
- ASK_OBSERVATION: a `check_id`, `check_version` and `observation_code` defined by the active catalog and its source references; A must map it to a canonical approved question/check. It is not a loophole for arbitrary checks.
- ESCALATE: safe enum reason `INSUFFICIENT_EVIDENCE`, `UNSUPPORTED`, `CONFLICT`, `EXHAUSTED`, `MODEL_FAILURE`, `BUDGET_EXCEEDED`.

## Source and check authority

Authoring record: source ID/version/hash/title/locator/rights, approved audience, model/configuration applicability, lifecycle and approver; check ID/version, canonical instruction, prerequisites, approved observation schema, stop conditions, source refs and risk/scope tags. V authors, SME signs technical content, A publishes and enforces. Inference cannot approve or mutate these records. A resolves output references against the current catalog, including permission/revocation, before displaying anything.

## Fixtures and change gate

`contracts/examples.json` contains a READY session, a pending session and an engine proposal; all status/error/engine-kind fixtures are included in `contracts/all-fixtures.json` under the same schemas. Contract checks must reject READY without a check, non-ready with a check, pending with PERSISTED receipt, persisted without record ID, stale response binding and additional model instruction fields. J and V consume these exact fixtures rather than copying altered shapes. Public API/schema/examples are a single versioned contract; drift blocks merge.

## Normative operation/state matrix

| Operation | Allowed starting states | Result / special rule |
| --- | --- | --- |
| create | No existing session | AWAITING_IDENTITY |
| image upload, identity candidates, identity confirmation | AWAITING_IDENTITY only | Identity inference temporarily EVALUATING, then AWAITING_IDENTITY; confirmation → EVALUATING |
| GET session/events | Any authorized state | No new inference or human action; refresh current policy before returning READY |
| observation | READY only | Active check/version/observation/value must match; RECORD_PENDING until durable; then EVALUATING |
| outcome | READY or EVALUATING after >=1 durably recorded check observation | No pending write; cancel active inference; persist before COMPLETED/ESCALATED |
| stop or hazard | Any nonterminal state, including RECORD_PENDING | Immediately inhibit future instructions; reconcile pending event; persist stop; no completion or next-check release |
| ordinary mutation while RECORD_PENDING | None | 409; exact authorized command replay allowed |
| ordinary mutation in terminal state | None | 409; exact authorized command replay allowed |

New hazards always take priority over a normal observation/outcome. `/hazards` is a dedicated mutation with expected revision and `hazard_code` enum DAMAGE, LIQUID, SWELLING, HEAT_OR_SMELL, UNSURE. For a valid authorized active session it is accepted even with a stale expected revision: stopping is monotonic, may not change asset identity, and must not be defeated by an inference race. `/stop` has the same monotonic exception. Key/payload conflict is still 409. J locks locally before network acknowledgement. A returns a truthful PENDING or persisted receipt; never releases guidance while reconciliation is unresolved.

Public schemas and examples are illustrative of data structure, but their enum-only observation forms and all state constraints are normative v1 behavior. Richer booleans, numbers, multiple-source display or diagnosis payloads require a contract amendment. Each check displays one canonical primary source; the authoritative catalog may preserve additional references, but A must not omit any safety-critical condition when composing canonical instruction/stop fields.

The Session `receipt` always describes its current latest accepted human command; it must not be overwritten with an older receipt during replay. Successful mutations return `X-Command-Id` and `X-Command-State` headers to identify the original command effect independently of current Session state. `GET /v1/sessions/{id}/commands/{command_id}` returns that authorized command's receipt (`command_id`, `state`, `record_id`); reconciliation may update PENDING to PERSISTED but never create a second effect. Historical receipts contain no instruction snapshots. A command may have committed yet now be inaccessible to a revoked caller; authorization always precedes replay. The image-upload receipt is separate from human-work evidence and obeys the same authorization/replay rules.

Catalog publication rejects duplicate check/version identities, unsupported configuration mappings, cycles, invalid prerequisite values and missing source/approval references. Exactly one required preflight is defined per workflow/configuration. Every physical check must transitively depend on the current approved preflight's CLEAR value; hazard/UNSURE stops before engine choice. No request, model proposal or human outcome can bypass this invariant. Runtime binding/value/prerequisite/expiry checks remain necessary beyond schema validation.

## Hash and clock conventions

Engine request schemas are in `engine-request.schema.json`, with reusable definitions in `catalog.schema.json`. `context_hash` is SHA-256 over UTF-8 JSON of `mode`, `workflow_id`, `confirmed_identity`, `manual_label`, `cleared_images` metadata, `approved_catalog`, `observations`, `completed_check_ids`, `catalog_version`, `prompt_version` and `model_config_version`, serialized by the canonical A-owned serializer: keys sorted recursively, compact separators, no NaN/Infinity, ASCII escapes, integer numeric fields only, input array order preserved. Request ID, deadline, counters and hash itself are excluded. A creates the hash, records the exact serialized bytes and validates the echoed hash; V does not independently reinterpret hashing. Image bytes are represented by their content SHA-256 in metadata; only A-authorized opaque handles can resolve to bytes. Deadline is an absolute UTC RFC3339 `deadline_at`; A also enforces a monotonic wall-clock elapsed deadline. No duration unit is inferred.
