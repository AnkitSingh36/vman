# J - camera, conversation, voice and cutaway frontend

Version 2.0. Own `mark1/web/**` screens/API wrapper/UI tests. Consume A's API/fixtures; no direct model/vault, client policy or copied applicability rules.

| Screen/panel | Behavior |
| --- | --- |
| Start/identity | Demo label/supported symptom; camera capture/retake; manual fallback; explicit model/config physical-label confirmation |
| Investigation camera | Local live preview; canonical request/target/safety text; user-selected snapshot submission; unavailable/unsure response |
| Conversation | Bounded chat; approved assistant text; enum questions; sources; distinguish report from confirmed observation |
| Voice | Push-to-talk ->editable transcript ->explicit Send; optional current-text read-aloud; mute/stop and typed fallback |
| Cutaway | Separate 2D flow panel, source/version, canonical labels, suspected/evidence highlight; 'diagram, not internal camera observation' |
| Check/preflight | One authorized check, safety/stop conditions, enum answer and human confirmation |
| Recovery/summary | Pending vs saved, command reconciliation, human-reported outcome and historical evidence |

No continuous video upload or tracked AR in R0. Missing camera/speech/diagram has explicit fallback; manual identity does not count as a supplied investigative image.

| Ticket | Deliverable | Evidence |
| --- | --- | --- |
| J-01 | Wireframes/all-state inventory | Phone journey and every pending/error/terminal state |
| J-02 | Capture/identity/view response | Denied permission, retake, cancel/unavailable, explicit send |
| J-03 | Chat/structured answers | Sources, report/confirmation distinction, stale interaction rejection |
| J-04 | Speech adapter UX | Editable transcript, consent, stop/mute, unsupported-browser fallback |
| J-05 | 2D diagram renderer | Correct graph/version/labels and grounded highlight; no invented alignment |
| J-06 | Retry/freshness/local stop | Double tap, lost response, reload, background/resume, speech cancellation |
| J-07 | Summary/mobile/accessibility/integration | Focus/keyboard/screen-reader states; fake/real backend modes |

## State and safety

AWAITING_VIEW shows VIEW; AWAITING_ANSWER shows QUESTION; EXPLAINING shows explanation+Continue; READY shows check/preflight. No readiness inferred from missing fields. Refresh visible active session every five seconds; hide active prompts/highlights and cancel speech on lease expiry <=15 seconds, refresh failure, background/offline or stop. Fetch current state on resume/before submission. Repeat speech only while authorized; no model commentary spoken. Safety text remains visible. Already heard speech cannot be recalled.

Browser speech support/processing varies: test named target mobile browsers and disclose approved processing/consent; typing/text always available. No raw audio upload or secret hosted speech fallback. Speak `interaction.text` or approved check text only. Never let pending ordinary response override local stop. Report hazard/Stop remains available from every active screen, locks immediately offline, cancels speech/capture and reconciles same command key.

Stable key per intentional command; exact retry preserves key/payload; changed answer is a new action. Minimal pending-key persistence only by A-agreed scope/expiry, clear on receipt/logout. Never persist raw images/audio/sources/full sessions in browser storage or log private payloads. Render text as text; graph accepts validated nodes/edges, never arbitrary HTML/SVG/URLs. Source/history views are labeled historical and cannot replay old physical guidance as current.
