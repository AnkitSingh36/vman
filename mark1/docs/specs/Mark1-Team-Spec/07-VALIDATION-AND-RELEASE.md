# Validation and release gates

Criteria below are proposed. No tests, photo benchmark, pilot or customer payment is claimed complete by this specification. Specification schema checks and Goldfish reviews are recorded separately.

## Test ownership

| ID / requirement | Implementation test owner | Reviewer / witness | Required observable result |
| --- | --- | --- | --- |
| T01 skipped checks and direct HTTP bypass | A | V | No check text until independent policy passes |
| T02 withdrawn/obsolete/superseded vs Draft | A | V + SME | Revoked release denied; still-authorized release not wrongly revoked by draft alone |
| T03 hidden restriction/denied policy service | A | V | Generic BLOCKED or UNKNOWN, no protected detail leakage |
| T04 actor/tenant/asset/configuration/source binding | A | V | Forged/mismatched/stale requests rejected |
| T05 timeout, duplicate key, key payload mismatch, restart | A | J | One logical evidence event; pending never shown saved; current revision returned |
| T06 simultaneous tabs, late inference, stop during inference | A | J + V | One valid transition; terminal state never revived |
| T07 provider refusal/malformed output/budget exhaustion | V | A | Explicit handled failure; no unsupported check/instruction |
| T08 image/document prompt injection, unscoped lookup | V (engine) + A (separate egress tests) | Cross-review by other owner | No unauthorized tool/lookup/output/data transfer; separate test paths |
| T09 identity, wrong-valid model, unsupported configuration | V | SME + A | Record raw extraction and post-confirmation errors separately |
| T10 denied camera, offline/reload, pending receipt, accessibility | J | A | Manual fallback, no stale continuation or false success |
| T11 integrated no-power happy path and each failure branch | A | J + V | Trace from input to scoped source/check, observation and durable receipt |
| T12 backups, restore, policy kill switch, deletion | A | V + independent reviewer | Restore verified; stop/recovery rehearsed; deletion evidence recorded |
| T13 hypotheses/next-check value and escalation (R1 only) | V | SME independent of engine tuning | Held-out results and uncertainty accepted; wrong recommendations cannot bypass catalog |

Rows with two modules contain separate tests owned within each module; no shared test file has two writers. A owns end-to-end acceptance wiring. Existing prior tests are rerun with declared dependencies in a clean environment; do not inherit the old pass count as a new result.

## Gates

| Gate | Accountable implementation lead | Evidence / proposed condition |
| --- | --- | --- |
| G0 scope, rights and contracts | A | One laptop family/symptom, authorized sources and images, SME-approved checks, frozen v1 contract, data terms, operator/stop boundaries; demo remains synthetic until authorized |
| G1 deterministic policy and persistence | A | T01–T06 pass; no open critical bypass/false evidence result; output cannot carry raw operational model advice |
| G2 perception and engine | V | At least 100 held-out images with varied readable/unreadable/near-match cases; zero accepted wrong assets/configurations in that set; >=90% usable coverage on readable supported images; all unknown/unreadable cases refuse or request confirmation; per-condition and pre-/post-human results reported; T07–T09 pass |
| G3 supervised pilot environment | A | Real auth, tenant permissions, lifecycle, storage, authorized provider use, retention, recovery, T10–T12; customer/admin + SME + independent reviewer accept this bounded environment |
| G4 diagnostic increment | V delivers evidence; A controls release | Separate hypothesis contract/feature flag, held-out no-power cases, independent SME labels, calibrated-claim limits, next-check/escalation results and no unsafe/out-of-scope action acceptance; predeclare sample size/targets before tuning; T13 passes |
| G5 user value and cost | A | At least 30 matched task pairs, >=20% lower median task completion time without observed worsening of errors, tail time or supervisor effort; costs include setup/support/model; report uncertainty and all attempts |
| G6 commercial validation | A | Five buyer interviews across >=3 buying organizations, two independent scoped pilot commitments and one paying customer; actual measured economics support next bounded deployment |

R0 developer demonstration: synthetic/licensed test catalog, frozen contracts, integrated deterministic controls and truthful labels; no customer-green claim. R1 controlled-check pilot requires G0–G3. Diagnostic hypotheses must remain disabled until G4 also passes. G5–G6 support a next bounded paid deployment, and its own impacted G0–G4 must be satisfied. No broad rollout or autonomy is authorized by passing these gates.

G2's finite sample is not proof of a zero real-world error rate. Human confirmation helps but is itself fallible. Record correction rate, refusal and coverage separately to avoid hiding bad extraction behind operator fixes. Identity must be tied to applicability, not merely a matching database row.

## Evaluation protocol

V prepares a manifest of held-out cases, sources, expected identity/allowed next checks, stop labels and independent repair/SME reference where relevant. Split by device/session/source families to avoid near-duplicate leakage. Lock the evaluation set before prompt tuning. Record model/provider/prompt/catalog/contract versions, sample counts, excluded cases, exact-match results, accepted wrong-valid IDs, refusal, coverage, escalation and unsupported-source outputs. Report latency median/tail and per-run actual usage costs; do not invent provider prices.

For R1 diagnostic planning, choose sample size and acceptance target with the SME based on severity and workflow before evaluation; until specified and met, G4 is UNKNOWN. This is an explicit future gate, not a zero-decision implementation ticket for hypothesis display.

Value study: counterbalance existing-process and Mark-1 ordering where feasible; pair comparable tasks, count failed/refused attempts and supervisor time, specify start/stop timing and tail statistic before collection, record learning/order effects and uncertainty. Small samples cannot establish safety. A owns study records; the SME validates technical outcomes. No paid claim without actual payment evidence.

## Release decision

A attaches test run IDs, commit/config/catalog/model hashes and open limitations to the gate register. Module owners do not self-certify domain safety. Named external SME/customer/admin/independent reviewer roles must be filled before an operational pilot. They are not assumed to exist. If unavailable, stay at developer demo. Any severe incident, source withdrawal, permission uncertainty, policy outage, model/data-term change or failed persistence stops impacted work; rerun affected gates after remediation.

## Identity acceptance metrics and freshness regressions

Count raw exact candidates, explicit unreadable/unsupported abstentions, wrong-valid candidates, human corrections, and final backend-accepted asset/configuration as separate numerators and denominators. Ordinary mandatory human confirmation is not an abstention. Unreadable/unsupported test inputs must elicit explicit uncertainty/refusal, not confident fabricated candidates. Zero accepted wrong IDs means zero wrong final backend acceptances in the held-out set after the entire workflow; also report raw engine errors to expose reliance on human correction.

T05 additionally tests original-command retry after source revocation and after terminal stop: command effect/receipt is stable but current guidance is absent. T06/T10 include idle-screen expiry, background/resume, lost polling, stale hazard/stop during inference and pending writes. T01 requires preflight before any physical check, and HAZARD/UNSURE causes deterministic stop. A schema pass does not replace these runtime tests.
