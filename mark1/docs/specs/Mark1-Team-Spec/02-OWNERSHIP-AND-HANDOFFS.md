# Ownership and handoff contract

## Rule

Every production file, shared artifact and backlog ticket has exactly one implementation owner. An approver is a reviewer, not a second writer. Never solve a blocked dependency by creating a competing API, model client, schema or persistence layer.

## Proposed repository paths

| Path / concern | Sole owner | Reviewer / consumer |
| --- | --- | --- |
| `mark1/web/**` including web manifest/lockfile/frontend mocks/component tests | J | A reviews integration; V reviews AI-state wording |
| `mark1/server/**` HTTP, sessions, auth, policy, catalog repository, evidence, migrations | A | V reviews AI binding; J reviews API usability |
| `mark1/ai/**` OCR/perception adapter, retrieval ranking, next-check engine, prompts/provider client | V | A reviews security/contract; J reviews display needs |
| `mark1/contracts/**` canonical schemas, fixtures, operation definitions, generated-client configuration | A | Both V and J review before freeze |
| `mark1/knowledge/**` source manifest, versioned checks, applicability/observation metadata, AI eval data | V | A validates lifecycle; SME approves technical content |
| `mark1/tests/integration/**`, `mark1/tests/security/**` | A | Relevant module owner reviews |
| `mark1/ai/tests/**`, `mark1/ai/evals/**` | V | A reviews integrity; SME labels cases |
| `mark1/web/**/tests/**` | J | A reviews contract use |
| Root Python dependencies, lockfiles, CI, deployment, database, environments, monitoring | A | V requests AI dependencies through A |
| `mark1/docs/product/**`, `mark1/docs/contracts/**`, release/gate/decision logs | A | V and J review affected decisions |
| `mark1/docs/ai/**` and source/data/model cards | V | A + SME |
| `mark1/docs/ux/**` and screen/error-state inventory | J | A + V |

Existing `lantern/app.py`, `lantern/bridge/**`, `lantern/mockvault/**`, root `tests/**` and CLI remain A-owned. Existing `lantern/agent/**` becomes V-owned if reused. A must not edit that agent area as part of policy fixes; adapt it in A's caller or request V's ticket. `mark1/` source skeleton was previously reported but has not been freshly inspected here; A-01 reconciles actual paths before assigning tickets. Existing docs outside these new namespaces default to A. No rename/rebuild is required merely to match this proposed layout.

## Shared-boundary decisions

| Boundary | Producer owner | Consumer owner | How change happens |
| --- | --- | --- | --- |
| Public API, sessions, evidence receipts | A | J | A edits contract; J reviews usability; fixtures released before frontend changes |
| Internal inference request/response | A owns schema, V owns implementation | A ↔ V | V proposes requirement; A publishes schema version and fixture |
| Approved source/check catalog | V authors data; A publishes/enforces it | A and V | V provides immutable candidate + SME approval evidence; A validates and activates version |
| UX wording | J owns generic UI text; A owns policy message codes; V owns hypothesis labels | All | Structured codes and approved templates; no model-written imperative text |
| Model/version configuration | V proposes tested model; A deploys credentials/config | V | A records deployed version; provider changes require impacted evaluation |

V's source authoring is distinct from A's catalog storage/migrations. Only A publishes authoritative catalog state. J displays sources received through A and must not maintain a second applicability table.

## Contract change protocol

1. Requestor opens one change ticket: producer/consumers, reason, schema diff, fixture, backward compatibility, migration, impacted tests.
2. A is sole contract editor. J and V review relevant changes; no implementation against an unmerged draft.
3. Freeze v1 before parallel implementation. Additive optional fields are compatible only if old clients still validate and behave correctly; otherwise bump contract version and migrate both consumers together.
4. A checks in fixtures/schema first. J and V generate or consume types; generated files are not hand-edited.
5. Cross-boundary bug: consumer records failing payload/test, producer fixes its own module. Ownership transfer is explicit in the decision log with start/end, affected paths, and replacement owner. Never two simultaneous owners.

## Branches and review

Use short-lived branches `a/<ticket>`, `v/<ticket>`, `j/<ticket>`. Merge contracts → module implementations → integration → release evidence. A owns final integration and tags; J and V merge their module work only after the designated cross-review and checks. Root/shared changes go through A. Keep one PR focused on one owner area; split cross-area fixes into dependent PRs. A publishes a proposed CODEOWNERS mapping and configures protected-branch checks only after actual team GitHub usernames are supplied; initials are not valid substitute handles. No GitHub account or invitation is inferred.

## Handoff checklist

Each ticket hands over: contract version, changed owner paths, runnable/local verification instructions, sanitized request/response example, error cases, remaining limitations, linked source/evaluation evidence and reviewer. Provider keys and customer material never enter fixtures. Reviewer feedback returns to owner. A reviewer may stop a release but does not silently take implementation ownership.

## Preventing A from becoming a bottleneck

A-01/A-02 are the first critical path. Publish stable fakes early and timebox schema discussion to one shared session. V and J continue against frozen contracts while A completes persistence/policy. Avoid new pilot integrations until the laptop thin slice passes. If A's measured capacity cannot meet the plan, reduce scope or explicitly transfer one whole owner area; do not ask all three to edit the backend.

## Test doubles and catalog schemas

A owns `mark1/server/testing/engine_stub.py` to unblock server integration. V owns `mark1/ai/tests/fakes.py` to test provider/AI behavior. They consume shared fixtures and the same port; neither is a second production engine. A owns all schema files, including catalog and engine requests; V owns the corresponding knowledge records. A-02 publishes the pack's complete contract baseline before module branches begin.
