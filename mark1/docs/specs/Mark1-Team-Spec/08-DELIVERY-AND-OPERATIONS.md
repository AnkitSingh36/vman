# Delivery sequence and operations

## Planning assumptions

Three developers; availability and budget unspecified. Use effort ranges as planning estimates, not dates/promises. One shared integration window per workday when active. No new customer connector, advanced diagnosis display, AR or learning in the initial thin slice. A owns all schedule decisions and records actual capacity after kickoff. SME/customer availability may dominate elapsed time.

## Dependency schedule

| Stage | A | V | J | Exit |
| --- | --- | --- | --- | --- |
| 0: align (1–2 focused days estimate) | Repo/dependency baseline, scope/rights, contracts/fakes | Draft synthetic check catalog and engine examples | Screen/state prototype using examples | A-01/A-02 + V-01 + J-01 contracts aligned; unresolved pilot decisions recorded |
| 1: independent build (roughly 4–7 focused days per developer estimate) | State/auth/policy/evidence using fake V | Perception/retrieval/next-check using frozen port | Capture/confirmation/guidance using frozen API fixtures | Owner tests and all status/error fixtures pass |
| 2: integrate (roughly 2–4 focused days estimate) | Own integrated API, security and recovery | Replace fake engine, fix AI binding failures | Replace API mocks, fix UX/retry failures | One full synthetic no-power session plus failure matrix demonstrated |
| 3: evaluate/harden (estimate only after baseline) | Gate evidence, staging/ops, independent review | Held-out evaluation and model/data cards | Usability/mobile/accessibility acceptance | Developer-demo criteria satisfied; G0–G3 evaluated for bounded pilot |
| 4: R1 and value study (depends on evidence/access) | Pilot operations, measurements and commercial interviews | Separately gated hypotheses/diagnostic evaluation | R1 display only after contract amendment | G4 if hypotheses enabled; G5/G6 assessed, never assumed |

Stage estimates are not additive calendar commitments and exclude unknown access/SME waits. If the team is part-time, schedule proportionally to confirmed working capacity. Work can start independently only after its input contract/fixture exists. A is not allocated full-time simultaneously to every role; defer nonessential connectors/advanced work if capacity is exceeded.

## Daily integration protocol

Each owner posts ticket state, contract version, demonstrated behavior, blocker and next handoff in the project record. No message is sent by this specification. A resolves shared-contract blockers first; discussion cannot authorize an unsafe shortcut. Weekly (or each milestone) demonstrate one complete workflow rather than three isolated modules. Every defect has one owner determined by the failing boundary, not whoever first sees it.

## Configuration and secrets

A controls deployment config: environment, contract/catalog version, enabled workflow, diagnosis flag (off in R0), provider/model/prompt versions, request budgets, file limits, retention and emergency stop. V provides model requirements; J gets only public endpoint/config. No keys in repo, client, screenshots or exported reports. Model changes rerun relevant tests. Use synthetic images until source and provider rights are established.

## Observability

Record correlation/session/inference/command IDs, state transitions, latency, result codes, catalog/model/prompt versions, tool/budget counts, persistence reconciliation and safe error category. Do not log raw images, serials, access tokens or document content by default. Track wrong-identity acceptance, refusal/coverage, unsupported candidate rejection, escalations, pending-write age, provider error and actual usage cost. A owns telemetry; V owns engine metrics; J owns sanitized UX error events sent through A.

## Data handling and retention

A documents who can view images, sources, observations and evidence; V only processes the scoped subset; J receives authorized display fields. Default R0 uses synthetic data only. For R1, A records approved retention periods, lawful/contractual basis and provider terms with the customer/admin before collection. Prefer dropping raw images after the approved short retention period; retain minimized audit references only as authorized. Deletion must cover objects, database references, derived copies and backup expiry policy; explain any required audit retention. No training reuse without separate rights and an approved evaluation plan.

## Runbook

1. Incident or unsafe/unknown behavior: operator stops physical work and escalates; J shows stop state; A disables impacted workflow/model via server kill switch.
2. Preserve minimal authorized correlation/evidence; never paste sensitive payloads into public issues.
3. A diagnoses policy/storage/auth; V diagnoses provider/perception/reasoning; J diagnoses capture/display/retry. Each fixes its own module.
4. Pending writes reconcile by idempotency key before retry; do not manually mark complete. Lost authorization or withdrawn sources invalidates active guidance.
5. Restore only a compatible server/schema/catalog set. A rehearses restore/migration and documents rollback; destructive migrations need a tested recovery strategy. Do not roll back to revoked content or authorization state.
6. Rerun impacted gates; independent SME/reviewer approval is needed where pilot conditions changed. Inform operators of accepted limits before resuming.

## Future-work ownership

| Increment | V | A | J |
| --- | --- | --- | --- |
| Bayesian/information-gain diagnosis | Algorithm, calibration and benchmark | State/source/policy integration | Hypothesis and evidence views |
| Verified-repair learning | Learning pipeline and leakage controls | Rights, labels store, version promotion/audit | Expert confirmation UX |
| Training gym | Simulator/evaluations | Reproducible execution and release boundaries | Optional result dashboard |
| Drift/CUSUM | Detection method and false-alarm evaluation | Authorized telemetry and alert workflow | Alert display |
| AR guidance | Perception/coordinate proposals | Session/budget/policy binding | Camera overlay rendering |
| Equipment/customer expansion | New domain evaluation/catalog | Connector/auth/lifecycle and customer gates | Supported-device UX |

These are deferred increments, not parallel first-sprint deliverables. Physical autonomous actuation needs a separate architecture and task-specific safety case.

## Capacity commitment rule

The 4–7-day module range is a provisional planning placeholder, not an implementation commitment. Stage 0 must separately estimate A's policy/persistence work and A's operations/integration work, and confirm each person's available hours before setting dates. If capacity does not fit, keep R0 synthetic and defer connector/ops/diagnostic work; do not overlap module ownership to force a date.
