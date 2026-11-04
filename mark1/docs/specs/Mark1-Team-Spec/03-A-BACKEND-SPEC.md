# A — Ankit: trusted backend and integration

## Own

API, schema authority, authentication, session state, storage/migrations, catalog publication, current-policy enforcement, source lifecycle, evidence, secure model egress boundary, deployment, observability, end-to-end release evidence. A is final technical integrator, not a substitute frontend/AI developer.

## Build in this order

1. **A-01 baseline and decisions.** Freshly inspect the repo and applicable instructions; record commit/runtime/dependencies, existing tests, reusable Lantern components, final paths and framework. Resolve pilot laptop family, workflow/source owner, provider-data permission, human reviewer, budgets, limits and team capacity. Use synthetic data while permissions are unresolved.
2. **A-02 contracts and mocks.** Publish schemas from this pack in the repository contract area, define full public session envelopes, implement the A-owned deterministic server integration stub at `mark1/server/testing/engine_stub.py` and response fixtures for all UI states. Own the one canonical public API definition. Fix contract ambiguities before parallel implementation.
3. **A-03 state/storage/auth.** Durable sessions, immutable event log, catalog revisions, image metadata, observations, inference runs and idempotency table. Tenant/actor scope every read/write. Reject unauthenticated, cross-session and stale commands. R0 local seeded identity must be visibly demo-only, unreachable in R1 deployment.
4. **A-04 trusted policy.** Bind confirmed identity/task, recheck current permissions/restrictions per check and confirmation, validate candidate check/source/prerequisites, fail closed, enforce workflow/tool allowlists, reject stale or late model outputs and prevent raw model advice reaching UI.
5. **A-05 evidence and lifecycle.** Atomically persist human observation, evidence event, session revision and idempotency result. Reconcile timeout/restart. Distinguish human assertion, pending write and persisted receipt. Implement withdrawal/supersession with no historical approval fallback.
6. **A-06 integrate/security.** Replace fake engine with V's port. A controls scoped engine input and allowlisted egress; V owns provider logic. Enforce file input limits, redaction, permissions, per-request budget and generic protected restriction blocks. Wire J's client to HTTP layer.
7. **A-07 release/ops.** Environment management, reproducible checks, backup/restore exercise, data retention/deletion, sanitized logs, kill switch, rollback and release-gate evidence. No secrets in client or logs.

## Storage contract

One transactional store initially. Minimum entities: sessions (tenant, actor, asset/configuration, workflow, status, revision), events (append-only, human assertion/source/policy/request references), observations, catalog/check versions and applicability, image objects, inference runs (model/prompt/catalog versions, duration, outcome), idempotency commands (key, request hash, status, result). IDs must be opaque and authorization-checked; unguessability is not authorization.

Use a transactional outbox only if an external evidence system is required. R0 local durable storage suffices; do not introduce distributed writes prematurely. If R1 uses an external vault, a local commit is not proof of external success: keep RECORD_PENDING until the required authoritative system acknowledges, reconcile by stable key and stop progression on uncertain/denied writes.

## Idempotency and concurrency

Every mutation requires `Idempotency-Key` and `expected_revision`. Scope keys by tenant + actor + session + operation; creation uses tenant + actor + operation. Store a canonical request hash. Same key/same payload replays the original immutable command receipt/effect together with freshly authorized current Session state; never replay stored check instructions; same key/different payload is 409. A stale revision with a fresh key is 409. Transactional compare-and-update prevents two tabs completing different checks. Authenticate/authorize access first, then deduplicate before stale-revision rejection for legitimate retries. Previously authorized effects do not grant current read access. Active inference IDs bind revision, asset, catalog and policy context; discard late results when any changes. Persisted receipts never imply independent physical verification.

## Error taxonomy

401 unauthenticated; 403 unauthorized; 404 nonexistent or inaccessible object (no enumeration); 409 revision/key/state conflict; 413 too large; 415 unsupported media; 422 malformed/unsupported request; 429 budget/rate limit; 503 required service unavailable. Known restrictions return a valid session with BLOCKED, not a fabricated system outage. Response error envelope contains stable `code`, user-safe `message`, `request_id`, `retryable` and optional `current_revision`. All error responses suppress actionable instructions.

## Acceptance

- Direct HTTP callers cannot bypass policy even without using the frontend or engine.
- All historical Lantern failures from the prior plan have regression coverage: skipped blocker call, obsolete fallback, hidden critical restriction, uncontrolled final text.
- Same session/check submission retried after timeout/restart creates exactly one logical observation/evidence event.
- Wrong organization, forged actor, mismatched asset/source, stale catalog/permission, source withdrawal and model-selected excluded checks stop progression.
- One offline demo works with fake V and J fixtures; then an integrated demo works with V's real adapter in an authorized environment.
- Backup restore, kill switch and pending-state recovery are demonstrated before R1.

## Do not own

Do not build the React screens, prompt design, image reading engine, retrieval ranking, diagnostic algorithm or AI evaluation dataset. File bugs/contract changes to J/V. A may inspect and review all areas.
