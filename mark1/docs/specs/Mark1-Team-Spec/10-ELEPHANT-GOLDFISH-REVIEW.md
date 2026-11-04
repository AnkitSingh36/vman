# Elephant–Goldfish specification review

Method: adapted manual Elephant–Goldfish workflow. The context-rich author drafted this pack; two independent fresh-context reviewers received only the self-contained files and their review instructions. A third fresh reviewer checks the revised pack. This does not claim the Google plugin is installed or that a Google-hosted model was used.

Review scope: completeness, ownership, independent implementation, contracts, trust boundaries, feasible delivery and release evidence. This is a design review, not customer authorization, safety certification, repository implementation testing or product-green evidence.

## Record

| Fresh review | Finding | Author resolution |
| --- | --- | --- |
| Technical contracts | Boolean/enum observation mismatch | Standardized v1 on string enums in prose, catalog, public schema and requests |
| Both reviewers | Exact historical Session replay could resend revoked guidance | Immutable command effect/receipt separated from freshly authorized Session; added command-receipt endpoint and headers; replay-after-revocation tests required |
| Delivery/operations | No bounded READY refresh/expiry | Five-second foreground refresh, at most fifteen-second lease, immediate local invalidation on refresh failure/background/offline; per-step backend revalidation retained |
| Delivery/operations | Hazard preflight and reporting undefined | Mandatory approved preflight, canonical safety/stop fields, deterministic hazard stop and stale-revision monotonic stop exception |
| Technical contracts | Operation/state ambiguity and pending evidence | Normative operation matrix, explicit terminal states including UNKNOWN, pending-write blocking and stop reconciliation |
| Technical contracts | Prose-only internal request/catalog | Added machine-readable EngineRequest and scoped Catalog schemas plus IDENTIFY/NEXT_CHECK fixtures and hashing conventions |
| Technical contracts | Observation code could map to multiple checks | ASK_OBSERVATION now binds check ID/version as well as observation code |
| Technical contracts | Public request/error/state fixtures incomplete | Added OpenAPI 3.1 definition, all session/engine-kind/error fixtures and public-body checks |
| Technical ownership | Both A and V appeared to own the same fake | A server integration stub and V AI-module test doubles have distinct paths/purposes; shared contract fixtures |
| Delivery/capacity | A workload under-estimated | Stage 0 requires actual per-owner hours and separate policy/persistence/ops estimates; ranges are provisional; scope reduction before overlap |
| Delivery/evaluation | Human correction could conceal extraction failures | Separate raw candidates, explicit abstentions, corrections and final acceptance denominators; confirmation is not counted as refusal |
| Delivery/rights | Authorized data needs purpose-specific authority | Separate display, provider-transmission, evaluation, retention and future-training rights checklist |

## Artifact verification

Executed `contracts/validate-contracts.ps1`: 44 positive/negative schema fixture checks passed, covering response states, engine kinds, catalog/request shapes, public request bodies and error payloads. Checked 24 uniquely assigned backlog tickets and resolved dependency IDs. JSON artifacts parse successfully. These checks do not run application code, evaluate AI accuracy, exercise live APIs, or close product gates.

Final fresh review: **PASS for a useful three-person implementation specification; no remaining material design blocker identified.** The reviewer independently reran the 44 schema checks. Two small cleanup suggestions were accepted: added canonical-hash golden fixtures with a runnable validator, and an equality check that prevents the embedded request/catalog schemas drifting. Both checks passed. These additions do not imply the backend's runtime serializer is already implemented. No product gate is closed by this design review.

## Source basis

The current `Vman-Amber-to-Green-Plan.md` was read in full for this specification. The author also attempted to retrieve the previously referenced official Google article at https://opensource.googleblog.com/2026/10/introducing-elephant-goldfish-model-plugin.html ; access failed during this task, so no newly verified claims about the article are made. The workflow implemented here is explicitly described above and evidenced by the review records.
