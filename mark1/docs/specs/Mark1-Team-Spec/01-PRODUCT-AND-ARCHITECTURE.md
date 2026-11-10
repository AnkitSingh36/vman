# Product and architecture: visual investigation

Version 2.0 | 10 November 2026

## Practical experience

The user opens a phone web app beside a supported device and describes the symptom. The agent inspects a selected frame, requests the label or a better angle, retrieves applicable knowledge, asks contextual questions and chooses further evidence. Text/optional speech, camera preview and a separate 2D flow/cutaway panel explain the suspected subsystem. It requests an approved external check, waits for a human observation, then continues or escalates.

Example R0 path: identify fictional DEMO-LAPTOP/DEMO-C1; confirm identity; hazard preflight; request a wider external view; ask about a supplied fictional indicator; show an approved power-flow diagram with a suspected input-stage location; offer a supported check or escalate. Branch on unreadable views, uncertainty and conflicting evidence. Camera appearance alone never establishes an internal electrical failure.

| Release | Required experience | Boundary |
| --- | --- | --- |
| R0 visual demo | One fictional model/no-power scenario set; camera follow-up; contextual questions; chat; speech input/output with visible fallback; source-backed 2D cutaway and advisory suspected subsystem; external checks and durable history | Synthetic/generated material; no customer operational use; failure handling demonstrated |
| R1 supervised pilot | Technically approved real family/catalog and evaluated investigator in an authorized environment | G0-G3; real diagnostic explanation additionally G4; real vault prohibited under current repo rules |
| R2 expansion | Streaming, tracked AR, more equipment, verified-repair learning, separately evaluated | No automatic autonomy or universal diagnosis |

No disassembly, battery handling, energized probing, mains measurement, flashing, bypass or remote execution. View requests must not ask for internal access, moving running machinery or another unapproved operation. Machine-specific behavior is catalog metadata, not hardcoded policy.

## Loop

1. Authenticate, select supported workflow and describe symptom.
2. Capture/upload a snapshot or enter a label. Before confirmation, only identity-oriented safe view requests are allowed.
3. AI returns exact supported candidates or requests another view; human confirms model/configuration against label.
4. A scopes knowledge/permissions and independently requires hazard preflight. CLEAR is a human report, not guarantee; HAZARD/UNSURE stops.
5. V receives authorized catalog, selected frames, accepted evidence and recent messages; proposes a view, question, explanation, check or escalation.
6. A validates and resolves canonical text/diagram. J displays one active interaction; voice reads that same authorized text.
7. Save human response before the next inference. Free chat never silently becomes a confirmed prerequisite. End on human-reported outcome or escalation.

## Architecture and trust

Phone web client -> A authenticated HTTP API -> A state/policy/mock knowledge bridge -> V investigation module -> configured multimodal provider. One backend deployment and transactional store; no mandatory microservices, agent swarm, vector service or live stream. A supplies a bounded authorized catalog; V ranks within it. A may refresh knowledge on a subsequent context-bound turn. Model tools are read-only; writes/confirmations are app-only.

A owns readiness/policy; V proposes IDs/source/evidence bindings, not instructions or approvals; J renders A's output, never direct model/vault content. Bridge checks user and configured agent access, exact applicability, current lifecycle and hidden restrictions. Missing policy ->UNKNOWN. Withdrawal/obsolescence/supersession revokes with no historical approved fallback; a Draft successor alone does not revoke valid content.

## Language and evidence

R0 uses context-selected approved view/question/explanation templates. Free text and corrected voice transcripts are bounded untrusted human reports. An unknown question triggers clarification/escalation. Composed canonical explanations describe flow, evidence and suspected location without asserting verified cause or calibrated probability. Arbitrary model prose is not displayed/spoken; expanding generative language requires a new evaluated contract.

Distinguish HUMAN_REPORT, HUMAN_CONFIRMED_OBSERVATION and IMAGE_OBSERVATION evidence. Image interpretations remain model interpretations. OBSERVED/REPORTED/SUSPECTED/UNKNOWN highlights retain provenance; A evaluates authored claim rules, not merely source membership. Conflicting evidence produces uncertainty. A completion click never verifies repair.

## Cutaway ('x-ray')

An approved schematic/cutaway has immutable version, component node/edge IDs, source references and 2D coordinates expressed as integer 0..1000, normalized by renderer. It represents authored machine structure, not camera penetration or measured current. Highlights reference catalog nodes and display evidence/uncertainty. No model-supplied coordinates/HTML/SVG/URLs or invented geometry. Missing applicable diagram ->explicit unavailable/text explanation. Separate panel needs no camera tracking; moving aligned overlays are deferred.

## State, freshness and interruptions

Statuses: AWAITING_IDENTITY, EVALUATING, AWAITING_VIEW, AWAITING_ANSWER, EXPLAINING, READY, RECORD_PENDING, BLOCKED, UNKNOWN, ESCALATED, COMPLETED. READY carries one check. The three new interaction states carry exactly one VIEW/QUESTION/EXPLANATION respectively. Other states have neither. Unconfirmed AWAITING_VIEW permits IDENTITY purpose only. EVALUATING runs IDENTIFY or INVESTIGATE; GET never initiates inference. Terminal BLOCKED/UNKNOWN/ESCALATED/COMPLETED never revive; restart after UNKNOWN means a new session.

Reauthorize every served interaction/check and submitted result. Foreground refresh every five seconds, lease <=15 seconds. Hide prompts/highlights and cancel queued/playing speech on expiry, failed refresh, background/offline, stop or changed context. Refresh on focus before restoring. Already heard speech cannot be recalled. Historical text is visibly non-actionable and never spoken as current guidance. Retry returns immutable command effect plus fresh current state, never old instructional snapshots.

## Media, voice and budgets

Local live preview; transmit explicit user-selected JPEG/PNG frames, not continuous video. Max 10 MiB each, three selected frames/inference; server verifies signature/type/dimensions, rejects bombs and strips metadata. A-01 freezes pixel/downsampling limits. No raw audio/video persistence or arbitrary runtime document uploads.

Push-to-talk yields an editable transcript with explicit Send; backend accepts text, not audio. J owns browser speech adapter and typed/text fallback. Browser speech processing/consent must be documented; adding hosted speech requires new rights/API design. Speak only the current authorized text, with mute/stop.

Chat/transcripts <=2000 characters; newest 20 relevant human messages per inference, explicit omitted count. Full authoritative observations remain available to backend prerequisites. Provisional per-inference caps: 8 model turns, 16 scoped calls, 60 seconds; per-session 24 inferences, three unsuccessful captures per view template. Atomic enforcement, retries within original budgets, no repeats without new evidence. Freeze measured limits A-01; exhaustion escalates.
