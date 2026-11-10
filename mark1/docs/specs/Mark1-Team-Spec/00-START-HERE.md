# Mark-1: visual investigation implementation pack

Version 2.0 | 10 November 2026 (India) | Proposed specification; implementation and product gates unverified.

## Product baseline

Mark-1 is a human-in-the-loop visual investigation assistant. The camera is its eye; the AI investigates; a permission-enforcing bridge supplies applicable approved machine knowledge from an M-Files-like vault. The agent requests useful views and contextual answers, retrieves evidence, explains machine flow using a cutaway diagram, highlights a suspected subsystem, and proposes permitted checks. The human controls the camera and performs every physical action.

R0 must demonstrate this investigation experience, not merely a sequential checklist: one fictional laptop model/configuration, no-power symptom, selected camera snapshots, voice/chat, a source-backed 2D cutaway and a small branching scenario set. Real M-Files access remains prohibited in this repository; use the local mock and synthetic data.

## Read and implement

1. `01-PRODUCT-AND-ARCHITECTURE.md`: scope, experience, trust and state model.
2. `02-OWNERSHIP-AND-HANDOFFS.md`: owners, integration and dependencies.
3. `03-A-BACKEND-SPEC.md`: Ankit's independently buildable backend package.
4. `04-V-AI-SPEC.md`: Viditya's investigator, perception and knowledge package.
5. `05-J-FRONTEND-SPEC.md`: J's camera, chat, speech and diagram package.
6. `06-CONTRACTS.md` and `contracts/`: normative v2 operations, schemas, fixtures and checks.
7. `07-VALIDATION-AND-RELEASE.md`: evaluation and evidence gates.
8. `08-DELIVERY-AND-OPERATIONS.md`, `09-BACKLOG.csv`: delivery order and tickets.
9. `10-ELEPHANT-GOLDFISH-REVIEW.md`, `11-GATE-AND-DECISION-REGISTER.md`: review status and decisions.
10. [12-ARCHITECTURE-EXPLAINED-AND-OPEN-GAPS.md](12-ARCHITECTURE-EXPLAINED-AND-OPEN-GAPS.md): architecture diagram, design patterns and open refinements before implementation freeze.

Split files and machine-readable contracts are authoritative. The combined sibling document is a distribution copy assembled from these Markdown files.

| Owner | Implements | Independent development substitute |
| --- | --- | --- |
| A - Ankit | API/auth, bridge/policy, state/evidence, media boundary, publication, deployment/integration | Deterministic engine stub and synthetic server test catalog |
| V - Viditya | Perception, investigation, retrieval, knowledge/diagram authoring, model adapter/evaluation | Frozen requests and AI-owned provider fakes |
| J | Phone UI, capture/chat, speech UX, diagram renderer, recovery/accessibility | Frozen API fixtures |

A can complete the local backend without V's engine or J's screens. Integrated experience requires both. V/J contract review is needed before branches rely on the frozen interface. A does not implement their modules by default.

## Change from v1

Camera requests, dialogue, voice and cutaway explanations move into R0. Synthetic advisory suspected-subsystem explanations are enabled; real-world diagnosis remains separately gated. Streaming video, tracked AR, learning and autonomy remain later increments. Contract 2.0 and `/v2` replace the v1 design. No deployed migration, independent v2 review or passed product gate is claimed.
