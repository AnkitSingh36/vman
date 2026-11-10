# V - Viditya: investigator and knowledge package

Version 2.0. Own perception, investigation strategy, scoped retrieval, provider, knowledge/diagram authoring and evaluation. No workflow writes, permission grants or direct instructions to J.

| Ticket | Deliverable | Acceptance |
| --- | --- | --- |
| V-01 | Fictional no-power catalog: preflight/checks, views/questions/explanations, diagrams, labeled scenarios | Versioned IDs, applicability, sources/rights/approval fields, external-only scope |
| V-02 | Identity/frame perception | Glare/crop/wrong-valid/unknown handling; no auto-confirmation or invented serial; frame evidence binding |
| V-03 | Read-only scoped retrieval | Only A-provided subset; missing/conflicting coverage escalates |
| V-04 | Investigation loop | Useful evidence requests, contextual answers, contradiction/no-progress handling |
| V-05 | Provider adapter/parsing/cancellation/fakes | Structured output; retries within original deadlines/budgets; no silent fallback |
| V-06 | Flow/cutaway and advisory explanation selection | Approved components/template, evidence-for/missing evidence, SUSPECTED label |
| V-07 | Held-out evaluation/model/data cards | Denominators, errors, useful camera requests, grounding, escalation, latency/cost |
| V-08 | Real-family/diagnostic pilot proposal | SME-reviewed content, independent evaluation and G4 gate |

## Port and strategy

Implement `propose(request) -> EngineProposal` with cancellation. Modes IDENTIFY/INVESTIGATE. Kinds IDENTITY_CANDIDATES, REQUEST_VIEW, ASK_QUESTION, PROPOSE_CHECK, ASK_OBSERVATION, EXPLAIN, ESCALATE. Return IDs/source/evidence bindings only; no arbitrary instruction/speech, URL, SVG or database mutation. A owns schema and authorization.

IDENTIFY: supported candidates, approved identity-view request or escalation. INVESTIGATE: choose next useful view, question, check, explanation or escalation from accepted evidence and missing information. Free user text can motivate a structured confirmation but never satisfy a physical prerequisite. Image interpretations remain interpretations. Avoid repeated requests without new evidence; max attempts/session limits enforced by A.

## Knowledge/diagram authoring

Version safe label/overview/external-component views, approved prompts, scope and stop wording. Questions have enum options and references. Explanation templates have canonical factual text, required observation/value claim rules, allowed highlight nodes and advisory labels. A publishes; SME signs real technical content. Synthetic content/source hashes match fixture text and approval IDs are visibly demo-only.

A versioned 2D component graph carries integer normalized coordinates 0..1000, canonical labels/directed flow edges and sources. It is authored structure, not measured current or internal camera vision. Missing applicable diagram cannot be fabricated. V authors graph; J renders; A validates/publishes.

Provide branching synthetic scenarios: distinguishable external observation, unreadable identity, absent diagram, contradictory report, unsupported view and insufficient evidence. R0 exposes authored synthetic suspected-subsystem explanation; real causal claims remain G4-controlled. No online learning, training gym or autonomy promotion.

## Security/evaluation

OCR/documents/chat/transcripts are untrusted data. Never follow embedded instructions/fetch URLs; tools read-only and ID-scoped. A supplies cleared opaque media; no tenant-wide search or direct vault/client-model channel. Provider refusal/invalid response/budget exhaustion returns handled failure/escalation.

Freeze held-out device/session/scenario splits before tuning. Compare static approved checklist and deterministic next-check baseline. Report raw exact identity, wrong-valid candidates, human corrections/final errors, refusal/coverage, useful/unsafe/redundant camera requests, evidence-grounded explanations, correct diagram/node mapping, contradiction/escalation, turns, median/tail latency and actual costs. Include all failed/excluded attempts. Independent SME reference labels required for real correctness claims. Never present confidence as calibrated probability without evidence.
