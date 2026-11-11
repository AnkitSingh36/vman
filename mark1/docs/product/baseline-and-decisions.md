# Backend baseline and implementation decisions

11 November 2026 | Branch: `a/mark1-backend-r0`

Implementation began from local main commit `1a537770bd1093a61d8571775ceb245e7f8420f2` and the proposed team specification 2.0. The separate architecture-review PR has not been assumed merged or approved. This record describes the local synthetic backend milestone, not a release-gate acceptance.

## Package and ownership

The existing outer `mark1/` directory remains the project root and its nested `mark1/` directory remains the only Python package. A-owned source is `mark1/mark1/server/**`; tests are `mark1/tests/**`. V's AI/knowledge and J's web modules have not been implemented or edited. `lantern/**` is unchanged.

The canonical contracts remain in `mark1/docs/specs/Mark1-Team-Spec/contracts/` and are loaded directly by the backend. There is no separately edited contract copy. Source-checkout/editable installation is supported; a standalone application wheel containing the external specification assets is not claimed.

## Chosen local defaults

| Concern | Decision |
| --- | --- |
| Runtime | Tested on Windows, Python 3.13.7; package requires Python >=3.11 |
| HTTP | FastAPI 0.162.2, uvicorn 0.54.0; one worker, loopback bind |
| Store | Standard-library SQLite, explicit transactions, closed connections and schema-version check |
| Auth | Opaque generated bearer tokens; SHA-256 token hashes in SQLite; no seeded/shared default secret or cookie auth |
| Scope | Token-bound tenant, actor and configured agent; explicit grants for user and agent |
| Data | Synthetic catalog from A's existing integration fixtures; no real vault/provider or customer data |
| Media | JPEG/PNG, <=10 MiB encoded, <=16 million decoded pixels, downsample longest side to <=2048, store reconstructed JPEG pixels without original metadata |
| Freshness | Reauthorize on serve/submit/replay; new lease <=15 seconds; J must implement polling, hiding and speech cancellation |
| Execution | Async engine port with immutable persisted request binding; max 60-second wall deadline, 24 inferences/session, 3 failed views/template |
| Request budgets | Port supplies 8 turns/16 calls; the deterministic stub performs one local proposal. Real provider/tool metering must be integrated with V before live-provider use |
| Input/storage limits | JSON body <=16 KiB, chat/transcript <=2000 characters, 100 messages/session, 32 images/session, 100 sessions/actor; demo cleanup is operator-controlled |
| Recovery | Interrupted inference becomes terminal UNKNOWN on startup; GET never restarts inference |

Relative `MARK1_DB` environment values resolve from the outer Mark-1 project directory. `--database` CLI paths are explicit operator paths. Demo mode is mandatory; `MARK1_MODE=pilot` fails startup.

Dependencies are declared in `pyproject.toml`. `requirements-dev.lock.txt` records the tested full development environment, including the optional Google SDK needed by the unchanged Lantern regression tests. The backend does not import that SDK or make model calls. The old matplotlib/learning dependencies were removed from the backend runtime requirements because those modules are deferred.

The OpenAPI authentication scheme now records the bearer-token decision allowed by A-01. Payload shapes and contract version remain 2.0. Owner review/freeze is still pending; this implementation is concrete review evidence, not a declaration of contract acceptance.

## What is implemented and what remains

| Ticket | Local result | Remaining boundary |
| --- | --- | --- |
| A-01 | Package/runtime/auth/limits and baseline recorded | Team hours, real sources/SME, browser selection and pilot environment remain open |
| A-02 | Canonical schemas consumed, all-state fixtures retained, A-owned stub supplied | V/J contract review and unresolved architecture refinements remain pending |
| A-03 | Auth/scoping, sessions/events/receipts, revisions and restart handling | Production identity management is not implemented |
| A-04 | Mock publication/bridge, lifecycle, user+agent access and source/graph validation | V's production catalog/SME approval and real connectors are absent |
| A-05 | Human commands, atomic local writes, replay and conflict handling | No external authoritative evidence store; no claim of external persistence |
| A-06 | Media normalization/cleared handles, context hashing, session/deadline limits | Live model egress/provider/tool metering requires V integration |
| A-07 | Independent preflight, proposal/source/evidence checks, canonical text/diagram and fresh leases | Browser-side stop/voice behavior belongs to J |
| A-08 | Stub-driven API journey and adversarial integration tests | Real V/J end-to-end integration cannot be completed without their modules |
| A-09 | Local backup/restore, policy/revocation/erasure commands and runbook | Pilot operations, hosting, rights and independent acceptance remain incomplete |

The flow-only explanation, typed visual-finding lifecycle and correction/contradiction amendment remain open design work. R0 implements the existing claim-bound explanation schema. Messages are human reports and cannot overwrite confirmed observations; to correct a physical observation, stop and create a new session until a correction contract is agreed. The stub does not understand or diagnose images, free text or speech.

Author-run test and startup results are recorded in [backend verification](backend-verification.md). No independent gate acceptance is implied.
