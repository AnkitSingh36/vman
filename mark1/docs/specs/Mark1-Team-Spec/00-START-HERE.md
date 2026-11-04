# Mark-1: three-developer implementation pack

Version: 1.0 | 4 November 2026 (India) | Status: proposed implementation specification, independently reviewed; no product release gate closed.

## What we are building

Mark-1 is a human-in-the-loop assistant for physical troubleshooting. In the first laptop workflow, a person identifies a laptop that will not turn on, provides observations, follows a supported external check, reports the result, and receives the next permitted check or an escalation. The person performs all physical actions. Mark-1 records observations, sources, decisions and human confirmations.

The long-term vision includes diagnosis, learning from verified repairs, overlays and additional equipment. These are separately gated increments, not claims about the current prototype. PAaaS is a positioning choice here, not a certification.

## The division

| Developer | Sole implementation responsibility | Delivers to the others |
| --- | --- | --- |
| A — Ankit | Trusted backend, policy, authentication, database, public and internal contracts, deployment, end-to-end integration | Stable API and fixtures to J; scoped requests/catalog access to V |
| V — Viditya (spelling supplied by user) | AI perception, retrieval, next-check recommendation, model provider integration, offline AI evaluation | A typed recommendation to A; never direct operational instructions to J |
| J | Phone-friendly web UI, camera/upload UX, confirmations, source display, frontend tests | A client that renders server-authorized states and submits human observations |

Skill percentages provided by the user describe strengths, not available working hours. J's backend knowledge is useful for integration review; V's backend knowledge stays inside the AI module. A does not implement their modules by default.

Single code ownership prevents competing implementations. Reviews, contract discussions and integration are deliberately collaborative. Nobody edits another owner's area without an explicit transfer recorded in the ownership register.

## Read these files

1. `01-PRODUCT-AND-ARCHITECTURE.md`: scope, architecture, state and trust rules.
2. `02-OWNERSHIP-AND-HANDOFFS.md`: paths, interfaces, PR rules, existing-code mapping.
3. `03-A-BACKEND-SPEC.md`, `04-V-AI-SPEC.md`, `05-J-FRONTEND-SPEC.md`: individual work instructions and acceptance criteria.
4. `06-CONTRACTS.md` and `contracts/`: OpenAPI definition, request/catalog/response schemas, every state/error fixture and runnable schema checks.
5. `07-VALIDATION-AND-RELEASE.md`: tests, evidence gates, evaluation and release controls.
6. `08-DELIVERY-AND-OPERATIONS.md`: sequence, dependencies, support, privacy and decisions.
7. `09-BACKLOG.csv`: assignable tickets with dependencies and acceptance evidence.
8. `10-ELEPHANT-GOLDFISH-REVIEW.md`: independent review findings and resolutions.
9. `11-GATE-AND-DECISION-REGISTER.md`: reusable evidence and decision templates.

Downloadable ZIP contains all files, including schemas and example payloads. Markdown files are also supplied individually. These are design artifacts; they do not create GitHub issues, modify a repository, deploy a service, or contact teammates.

## Start together, then work independently

On the first shared session, A freezes contract v1 and publishes mock responses; V freezes the supported check/source catalog; J confirms every screen state against those mocks. Then J builds against fixtures, V against the AI port, and A against a deterministic fake engine. A owns the integrated demo.

## Basis and limits

This pack uses the user's team descriptions, laptop example, visible Mark-1 discussion and the current `Vman-Amber-to-Green-Plan.md` read on 4 November 2026. That plan reviewed repository commit `8bd2f05eda8500897775678f9a6842145569be65`. No fresh repository inspection or live model/customer validation was performed for this pack. Proposed paths below are a target layout, not a report of files already present.

The earlier plan intentionally excluded diagnosis from its first industrial pilot. This pack makes an explicit scope change: R0 is a laptop-specific controlled-check demonstration; R1 adds evaluated diagnostic hypotheses in a supervised pilot only after its additional gates pass. The earlier industrial/customer green status does not transfer to laptops. All release criteria in this pack are proposed thresholds, not achieved results or safety standards.
