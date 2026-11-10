# Contract 2.0: API and visual investigation port

A is sole editor; V/J review before freeze. Breaking change: `/v2`, interaction states, conversational/media responses, context and diagram/template catalog. No deployed migration or v1 compatibility is claimed. Files here are canonical until A-02 publishes the chosen runtime location; do not hand-maintain duplicate copies.

## Common rules

Authenticated same-origin API; HTTPS for pilot. A-01 chooses secure/HttpOnly/SameSite cookies+CSRF or server-verified tokens. Actor/tenant come from auth. Every ID is scope-checked. UTC RFC3339; integer revisions; unknown mutation fields rejected. All mutations require Idempotency-Key; session mutations expected_revision. Error/receipt semantics in A's spec apply to new operations.

| Method/path (prefix `/v2/sessions`) | Allowed state | Effect |
| --- | --- | --- |
| POST root | No session | AWAITING_IDENTITY |
| GET /{id}, /{id}/events, /{id}/commands/{command_id} | Any authorized | Current revalidated state/history/receipt; no inference |
| POST /{id}/images | AWAITING_IDENTITY, AWAITING_VIEW, READY | Store sanitized image; purpose identity/investigation/observation matches state; no inference |
| POST /{id}/identity-candidates | AWAITING_IDENTITY | IDENTIFY ->candidates or identity view, EVALUATING meanwhile |
| POST /{id}/identity-confirmation | AWAITING_IDENTITY | Human identity ->EVALUATING ->independent preflight |
| POST /{id}/view-responses | AWAITING_VIEW | IMAGE with image ID, UNAVAILABLE or UNSURE; persist ->EVALUATING; identity views run IDENTIFY |
| POST /{id}/answers | AWAITING_ANSWER | Active interaction/question/version+enum answer; persist ->EVALUATING |
| POST /{id}/messages | AWAITING_IDENTITY, EVALUATING, AWAITING_VIEW, AWAITING_ANSWER, EXPLAINING, READY | Persist CHAT/VOICE_TRANSCRIPT human report; invalidate prior inference/output ->EVALUATING; IDENTIFY if unconfirmed, otherwise INVESTIGATE; preflight still enforced |
| POST /{id}/explanation-acks | EXPLAINING | Persist acknowledgement ->EVALUATING; never repair verification |
| POST /{id}/observations | READY | Check/version/value confirmation; pending until durable ->EVALUATING |
| POST /{id}/outcome | READY, EVALUATING, AWAITING_VIEW, AWAITING_ANSWER, EXPLAINING after >=1 durable check observation | No pending write; cancel inference; human RESOLVED ->COMPLETED, UNRESOLVED ->ESCALATED after save |
| POST /{id}/stop or /hazards | Any nonterminal including RECORD_PENDING | Monotonic inhibit/reconcile ->ESCALATED after save; stale revision accepted; key/payload mismatch remains 409 |

Ordinary mutation in RECORD_PENDING/terminal ->409 except authorized same-command replay. Accepted commands have durable event/command records; 202 RECORD_PENDING while required write unresolved. Pending stop may return RECORD_PENDING or UNKNOWN on storage failure with no output, never fabricated saved receipt. Inference result commits only on matching current revision/context. Image upload increments revision but preserves active interaction/check; follow with current-revision response. Conversation can interrupt but never bypass identity/preflight. GET never runs engine.

## Session/interaction

Required `interaction` is null except AWAITING_VIEW/AWAITING_ANSWER/EXPLAINING, which require VIEW/QUESTION/EXPLANATION respectively and no current_check. READY requires current_check, confirmed identity, null interaction and no pending receipt. Unconfirmed AWAITING_VIEW permits identity purpose only. Question/explanation require confirmed identity. Each interaction has ID, template/version, canonical text, exact primary source, current-policy time, expiry, safety/stop fields. VIEW includes purpose/target; QUESTION enum options; EXPLANATION advisory flag, claim/evidence list, optional embedded catalog diagram/highlights. Missing diagram ->null and no highlights. Actual lease order/duration <=15 seconds, ID applicability and claim semantics are runtime validations.

Speech uses current `interaction.text` or check instruction, never extra model audio/prose. Diagram consists of authored nodes/edges, integer normalized positions 0..1000 and exact version/source; no arbitrary external fetch/markup. Historical events remain evidence summaries, not replayable instruction snapshots.

## Catalog, context and proposals

Catalog includes checks, view_templates, question_templates, explanation_templates and diagrams. Every record binds model/config/workflow, source/hash/rights, Approved state and approval record. Questions enum-only; views approved external safe framing. Explanation claim rules bind a required check/version/observation/value and allowed highlight node IDs, with authored SUSPECTED label. Graph node/edge/reference/prerequisite validation is mandatory at publication beyond schema. V authors; A publishes; SME approves real content.

EngineRequest modes IDENTIFY/INVESTIGATE. Include authorized catalog, identity, selected cleared media, durable observations, versions/budgets and required investigation_context: recent human messages, answers, view results, explanation acknowledgements, available evidence IDs, prior interaction template IDs, omitted message count and session counters. Max 20 messages, three frames. Full backend observations remain authoritative even when conversation is truncated. Context contains no raw audio or arbitrary URLs.

Proposal bindings echo contract_version/request_id/session_id/based_on_revision/context_hash. Kinds:

- IDENTITY_CANDIDATES: exact supported candidates, never auto-confirmation.
- REQUEST_VIEW: approved view ID/version and sources; A resolves purpose/target/prompt.
- ASK_QUESTION: question ID/version and sources; A resolves options/wording.
- PROPOSE_CHECK/ASK_OBSERVATION: check ID/version and sources; observation code when applicable.
- EXPLAIN: explanation ID/version, sources, evidence IDs and highlight node IDs. A evaluates authored claim rules and composes canonical explanation; no model-authored diagnosis/instruction text.
- ESCALATE: safe reason enum.

IDENTIFY accepts only candidates/identity view/escalation. INVESTIGATE accepts investigation views/questions/checks/explanations/escalation. A forces preflight independently of model choice. Evidence membership alone cannot justify claims: observation value/provenance/applicability must match. Synthetic R0 suspected subsystem is advisory; real diagnosis requires G4. Unknown user questions can motivate clarification, not invent new permitted physical actions.

## Hash/replay/media

context_hash = SHA-256 of UTF-8 JSON, recursively sorted keys, compact separators, ASCII escapes, no NaN/Infinity, integer numeric inputs, array order preserved. Include mode/workflow_id/confirmed_identity/manual_label/cleared_images/approved_catalog/observations/completed_check_ids/catalog_version/prompt_version/model_config_version/investigation_context. Exclude request/session IDs, revision, deadline, remaining request budget counters and hash; A separately binds these. Session counters inside context are hashed. Image content represented by SHA-256/opaque server handle; no model URL fetch. A records exact bytes; V echoes hash. Absolute UTC deadline plus monotonic elapsed enforcement.

Authenticate/authorize before deduplication, legitimate retry before stale check. Return original X-Command-Id/X-Command-State and fresh current Session; Session.receipt remains latest command. Command receipt endpoint reconciles PENDING ->PERSISTED without duplicate effect. Image receipt separate from physical evidence. Fixed synthetic fixture timestamps/hashes are examples, not current authorizations; fake server must issue fresh leases and binding hashes.
