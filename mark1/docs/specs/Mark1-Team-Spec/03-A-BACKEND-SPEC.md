# A - Ankit: trusted backend package

Version 2.0. Complete the local backend against a deterministic engine, independent of V/J. Own API/contracts, authentication, state, bridge/policy, publication, media/evidence and integration. Do not implement V's investigator/prompts/production diagram data or J's UI.

| Ticket | Deliverable | Observable acceptance |
| --- | --- | --- |
| A-01 | Baseline/decisions, single package layout, isolated reproducible runtime | Old/new scope reconciled; auth/limits selected; clean baseline recorded |
| A-02 | v2 contracts, engine stub, all-state fixtures, server test catalog | Full view/question/explanation/check path without real AI/UI; V/J review before freeze |
| A-03 | Transactional sessions/auth/event/command ledger | Actor/tenant isolation, stale/concurrent tabs and restart reconciliation |
| A-04 | Mock knowledge bridge, lifecycle and catalog publication | User+agent permission, exact applicability, withdrawal and hidden restrictions fail closed |
| A-05 | Messages, answers, view responses, explanation acknowledgements and observations | Exactly one effect per retry; no inference before durable save; chat cannot satisfy check prerequisites |
| A-06 | Media/transcript/context/hash/budget boundary | Session-owned frames; no raw audio/video; edited transcript stored as human report |
| A-07 | Independent interaction/claim/diagram validator and preflight | Unknown IDs, forged evidence, unsupported claims, stale diagrams and model prose rejected |
| A-08 | Integrate real V/J with full regression matrix | Camera -> scoped knowledge -> question -> cutaway -> check -> durable outcome |
| A-09 | Local runbook and pilot hardening | Reproducible stub demo, backup/restore, kill switch, retention/deletion evidence |

## Storage/state

One transactional database: sessions; append-only events; observations; messages; view attempts/responses; images; catalog/lifecycle/rights/approvals; inference runs; interactions; idempotency commands. Opaque IDs still require scope authorization. Bind inference to revision, identity, catalog, frame/transcript hashes, accepted evidence, model/prompt versions. Persist human command/event/revision atomically before inference. Image storage alone does not advance investigation; view-response commits linkage. An image receipt is not physical observation evidence.

Only one current inference. User input cancels/invalidates old inference/output before reevaluation. Restart reconciles persisted jobs or yields controlled UNKNOWN. Stop/hazard overrides normal output including pending writes; no write ->no next instruction. External authoritative evidence store, if later required, keeps RECORD_PENDING until its acknowledgement; local commit is not external success. No distributed outbox needed for R0 local storage.

## Bridge/publication

Validate permissions/lifecycle at publication, serving, submission and replay. Only approved source/graph/templates within asset/config/workflow scope. Resolve template IDs to canonical text. Claim rules bind required durable observation/value, required provenance and uncertainty label; evidence membership alone is insufficient. Real diagnosis disabled until G4. R0 synthetic suspected subsystem is visibly advisory.

Reject duplicate IDs/versions, prerequisite cycles/invalid values, dangling graph edges, foreign component references, invalid positions, missing sources/rights/approvals and undeclared claims. Physical/view/question investigation after identity requires preflight CLEAR. Pre-identity views are IDENTITY-purpose safe framing only. Missing diagram yields explicit unavailable/text explanation; missing safety knowledge blocks. Preserve draft-vs-withdrawal distinction and no obsolete fallback.

## Commands/errors

Mutations require Idempotency-Key and expected_revision; create omits revision. Scope keys tenant+actor+session+operation (creation tenant+actor+operation); hash canonical payload. Authenticate/authorize before deduplication, then deduplicate legitimate retries before stale checks. Same key/different payload or fresh stale command ->409. Transactional compare-and-update prevents double effect. Replay returns original command headers plus fresh current Session; Session.receipt stays latest command. Pending never has durable record ID. No historic instruction snapshots.

401 unauthenticated; 403 unauthorized; 404 absent/inaccessible; 409 conflict; 413 size; 415 media; 422 request; 429 limits; 503 dependency unavailable. Restriction yields BLOCKED, policy unavailable UNKNOWN, both without actionable output. Errors suppress guidance/protected details. Truthful pending/UNKNOWN on storage uncertainty, never false saved/completed.

## Completion boundary

Local milestone: API, stub, synthetic test catalog, contract and isolation/policy/media/retry/recovery checks, startup instructions and scripted HTTP journey. No model key/frontend/SME needed for this milestone. V production knowledge/AI, J speech/camera UI and real pilot permissions remain separate handoffs. A test catalog is never production technical approval.
