# V — AI, knowledge and recommendation engine

## Own

Perception, supported identity extraction, source preparation, retrieval ranking, bounded next-check reasoning, model/provider adapter, prompts, AI-module tests, labeled evaluation design and model/data cards. Backend work is confined to this AI module; no public API, workflow database, auth or evidence implementation.

## Inputs and outputs

Consume the immutable inference request defined in `06-CONTRACTS.md`: confirmed scope, consent-cleared image references, approved authorized checks/source excerpts, prior structured observations, already completed checks, contract/catalog/prompt/model versions, budgets and execution ID.

Return an `EngineProposal` conforming to `contracts/engine-proposal.schema.json`. Kinds: `IDENTITY_CANDIDATES`, `PROPOSE_CHECK`, `ASK_OBSERVATION`, `ESCALATE`. Return IDs and source references; A retrieves canonical instruction text and performs final checks. No raw generated instruction text, readiness, evidence receipts, authorization decisions, commands or actor overrides.

## Tasks

1. **V-01 catalog + fake implementation.** Prepare one supported no-power workflow using synthetic or licensed documentation. Each check: immutable ID/version, supported models/configurations, prerequisites, approved observation question/options, authored instruction text, risk class, stop conditions, source ID/version/locator/hash, approval status and reviewer/date. Deliver fixtures for every engine kind. A owns schema and publication; V owns data authoring.
2. **V-02 perception.** Optional image snapshot → identity candidates and evidence locators; return ambiguity/unsupported states honestly. No invented serial number or false precision. Manual confirmation remains required. Demonstrate similar valid IDs, glare, cropped labels, unknown families and injected text. Image absence must still support manual entry.
3. **V-03 retrieval.** Use A's already scoped current approved subset; rank relevant sources/checks within it. Never retrieve another tenant, asset family or hidden restriction. Empty/conflicting coverage escalates. Small catalog first; no vector service unless a measured retrieval need justifies it.
4. **V-04 next-check engine.** Pick one supported check with satisfied catalog prerequisites, request one supported observation or escalate. Prevent loops and redundant checks. R0 may rank hypotheses internally to choose checks but cannot expose causal diagnosis as a product conclusion. Model output is an untrusted proposal; A revalidates it.
5. **V-05 provider and budgets.** Configurable provider/model, server-only keys supplied by A, structured response parsing, schema validation, timeout/cancellation and bounded retry. Retries count against the original deadline/call budget and do not mutate sessions. Keep V-owned provider/engine test doubles at `mark1/ai/tests/fakes.py` for AI tests. These do not duplicate A's server integration stub; A can later consume V's real module or a shared fixture through the frozen port.
6. **V-06 evaluation + R1 proposal.** Freeze held-out cases before tuning, report by condition/model family, exact identity/refusal/coverage, valid next-check rate, escalation quality, unsupported-source rate, latency and actual tokens/cost. Only then propose a separately evaluated hypothesis schema/feature flag for R1. V does not self-approve that release.

## Prompt and data security

Document and image instructions are data, never system instructions. Scope tool requests to the current session's provided allowed IDs. Do not expose internal prompts, secrets, protected restrictions or unrelated source text. Never call external URLs found in a label/document. Minimize image transmission; use only consent-cleared references after A authorizes provider handling. Model fallbacks must not silently change provider or data terms.

## Diagnosis and future learning

R1 hypotheses require a future contract amendment: ranked possible causes with evidence-for/against, uncertainty and a labeled advisory status; confidence scores must not be described as calibrated probabilities without evaluation. SME-approved actions remain the only displayable checks. A model saying "fixed" does not end a job.

Later Bayesian diagnosis/information-gain selection, verified-repair learning, training gym and drift monitoring remain V-owned algorithm work. A owns persistence, promotion controls and audit; J owns visualization. No online self-training or automatic autonomy promotion in R0/R1. Verified cause needs an SME-defined independent confirmation label distinct from a user completion click.

## Acceptance and handoff

- Valid schema on every response or explicit handled failure; unknown IDs/sources rejected before handoff.
- All evaluation cases keep request/catalog/asset binding intact; no actionable advice outside catalog.
- Provider failure/malformed response/malicious source/exhausted budget cannot turn into a successful check.
- Held-out results include denominators, excluded/unreadable cases, false acceptance, refusal, coverage and costs, not just average accuracy.
- Deliver prompt/model/catalog versions, sanitized examples, fake engine, evaluation instructions and known limitations to A; source/uncertainty labels to J through the contract.

V may ask J for how a result will be displayed, but never ships a second frontend or direct browser-to-model connection.
