# Reusable decision, evidence and release register

## Initial decision log

| ID | Decision | Owner | Status / resolution |
| --- | --- | --- | --- |
| D01 | One backend deployment; independent UI and AI module; no required microservices | A | Proposed architecture baseline |
| D02 | A owns contracts/state/policy; V owns AI/catalog authoring; J owns UI | A | Derived from user-provided strengths |
| D03 | Laptop no-power workflow replaces generic industrial first demo | A | Explicit scope change; prior pilot gates do not transfer |
| D04 | R0 only controlled external checks; diagnosis display and learning deferred | A | G4 required for diagnostic increment |
| D05 | Confirm available hours and funding | A | Open; blocks reliable calendar commitment, not synthetic spec work |
| D06 | Confirm actual repo paths/framework/runtime and clean baseline | A | A-01; no fresh repo verification claimed |
| D07 | Choose supported family/source rights/SME and technical check approvals | A | Open; V prepares content; blocks operational pilot |
| D08 | Select auth/tenant model and approved provider/data handling | A | Open; synthetic development only until resolved |
| D09 | Record GitHub handles and branch-protection capability | A | Open; do not infer identities or configure invalid CODEOWNERS |
| D10 | Freeze exact budgets/image pixel limits/SDK versions | A | A-01; proposed limits in file 01 are defaults requiring measured verification |
| D11 | Independent SME/reviewer/customer-admin availability | A | Open; missing role prevents operational pilot |
| D12 | R1 hypothesis schema, sample size, acceptable error criteria | A owns contract; V supplies evaluation proposal | Deferred to G4; no automatic approval |

## Decision change template

Decision ID; date; proposing owner; problem; options; chosen behavior; affected contracts/files/tickets; consumer reviews; test/evaluation impact; rollback; effective version. Ownership transfer also states replacement owner, paths and interval, ensuring only one active writer.

## Initial gate register

| Gate | Status | Implementation lead | Required sign-off |
| --- | --- | --- | --- |
| G0 | UNKNOWN — source/family/rights/contract not accepted yet | A | A + SME/rights owner/customer as applicable |
| G1 | UNKNOWN — implementation tests not run by this pack | A | A + cross-reviewer |
| G2 | UNKNOWN — real-image benchmark absent | V | SME + A + independent reviewer |
| G3 | UNKNOWN — customer environment/operations absent | A | Customer/admin + SME + independent reviewer |
| G4 | NOT ENABLED — hypothesis feature off | V produces evidence; A releases | SME + independent reviewer + A |
| G5 | UNKNOWN — task study absent | A | Customer sponsor + SME |
| G6 | UNKNOWN — buying evidence absent | A | Budget-authorized buyer evidence |

Do not copy old green evidence without an applicability assessment. Each record binds customer/environment, task/device family, repository commit, contract/catalog/prompt/model versions, test date, evaluator, sample size and limitations. A reviewer accepting this specification does not close product gates.

## Evidence record template

- Evidence ID and gate/test IDs:
- Owner and independent witness/reviewer:
- Exact workflow, environment and device/configuration:
- Commit, contract/catalog/model/prompt/deployment versions:
- Predeclared criterion and test/data manifest:
- Run date, command/protocol, sanitized raw result locator:
- Denominator, exclusions, failures, false acceptances and uncertainty:
- Pass/fail/unknown and why:
- Remaining risk, mitigation, reviewer disposition and expiry/retest triggers:

## Release checklist

- [ ] Scope is labeled R0/R1 and diagnosis flag matches passed gates.
- [ ] All current sources, identities and deployment rights are authorized.
- [ ] Clean baseline + owner tests + integration/security evidence attached.
- [ ] No open critical finding, fake live accuracy or false persistence claim.
- [ ] Exact contract/catalog/model/prompt versions and rollback set recorded.
- [ ] Emergency stop, pending recovery, restore and retention/deletion rehearsed.
- [ ] Operators understand physical stop/escalation and no offline continuation.
- [ ] Named required reviewers accept bounded deployment and residual uncertainty.
- [ ] Per-customer impacted gates rerun before any new paid deployment.

## Risk register

| Risk | Owner | Mitigation / trigger |
| --- | --- | --- |
| A overloaded by backend/integration/product roles | A | Fakes/contracts first; narrow scope; replan capacity or transfer whole area explicitly |
| AI invents identity/source/check | V | Typed proposals, held-out eval, uncertainty/refusal; A validates all IDs/lifecycle |
| Model-derived check bypasses restrictions | A | Trusted independent gate and allowlist; adversarial/direct HTTP tests |
| Pending evidence appears complete | A | Durable receipts/idempotency/reconciliation; J renders pending truthfully |
| Customer data leaks through prompts/images | A | Approved provider terms, scoped egress/minimization; V injection tests; J no local raw-image persistence |
| Source knowledge wrong or not applicable | V authors; A publishes | Named SME content approval and version/applicability/lifecycle gates |
| Laptop diagnosis broadens beyond expertise | A | One family/symptom; G4 separate; external checks only; stop/escalate |
| Prototype mistaken for validated product | A | Demo labels, evidence status register, no gate inherited from planning review |

## Rights checklist before G0/G3

Record separate permissions/authority for (1) source storage and display, (2) source/image transmission to the chosen model provider, (3) evaluation images and labels, (4) evidence retention/deletion and backup expiry, and (5) any future training reuse. Each record names the approving rights holder/customer, permitted purpose, data scope, expiration and revocation process. A missing permission blocks that data use, not synthetic development.
