# Ownership, dependencies and handoffs

Version 2.0. Every file/artifact/ticket has one implementation owner. Reviews are collaborative; transfer records paths, interval and replacement owner. Never create competing APIs, providers, catalog stores or workflow databases.

| Area / target path | Sole owner | Consumer/reviewer |
| --- | --- | --- |
| `mark1/server/**` | A | V/J boundary review |
| `mark1/contracts/**` and spec contracts | A | V/J before freeze |
| `mark1/tests/integration/**`, `mark1/tests/security/**` | A | Relevant owner |
| `mark1/ai/**`, prompts/provider/retrieval, AI tests/evals | V | A/SME |
| `mark1/knowledge/**`, templates, diagrams/graph, sources/scenario labels | V authors | A publishes; SME approves real content |
| `mark1/web/**`, camera/chat/speech/diagram renderer/UI tests | J | A integration, V content UX |
| Mark-1 root dependencies/locks/CI/deployment | A | V requests AI dependencies; J owns web lockfile |
| Product/contracts/gate docs | A | Affected owners |
| AI/data/model cards | V | A/SME |
| UX/accessibility docs | J | A/V |

Target paths are not existing implementation claims. A-01 reconciles nested `mark1/mark1/**` skeleton with one Python package/import layout. Do not create two package roots. Preserve `lantern/**` reference POC without modification. Reuse patterns with regressions, not inherited trust; machine behavior stays in metadata.

## Independent work

A owns `server/testing/engine_stub.py` and synthetic server-only test catalog. V owns `ai/tests/fakes.py` and production knowledge authoring. J uses A's all-state fixtures. Shared fixtures are canonical; these doubles are not competing production engines/catalogs.

A can complete local API/auth/state/bridge/evidence/media/interaction validation without V/J. Live AI integration needs V; full phone UX needs J; pilot content needs V+SME/rights. Contract freeze needs their review, not completed modules. Label substituted demos truthfully.

## Handoffs and changes

A -> J: public API, auth/demo setup, all states/errors, command reconciliation, media/speech rules. A -> V: hashed immutable request, scoped catalog/opaque media, budgets/cancellation and strict proposal schema. V -> A: typed proposals, reviewed sources/templates/diagram, versioned model/prompts/evaluation. V -> J only through A: canonical text, labels/graph IDs. J -> A: API-fixture/mobile/speech/accessibility evidence and failing payloads.

A edits contract/schema/fixtures first with compatibility/migration and consumer reviews. 2.0 `/v2` is breaking. Do not implement against unmerged drafts. V authors immutable catalog; A publishes lifecycle; J never copies applicability policy. Short branches `a/<ticket>`, `v/<ticket>`, `j/<ticket>`; merge contracts -> modules -> integration -> evidence. A owns tags/shared configuration. Actual GitHub handles needed before CODEOWNERS/branch rules. No messages/issues/deployments are created by this document.
