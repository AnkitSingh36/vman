# J — phone-friendly frontend

## Own

All web screens, camera/file capture, manual fallback, client state rendering, structured observations, accessibility, frontend API wrapper and UI tests. Consume A's API; do not implement policy, source applicability, evidence storage or model/provider requests.

## Screens and behavior

| Screen | Required behavior | Important failure state |
| --- | --- | --- |
| Start | Show supported workflow and demo/pilot label; collect symptom | Unsupported task cannot continue |
| Identify | Snapshot/upload or manual label entry; show candidate and explicit confirmation | Camera denial, unreadable label, unknown model; manual fallback |
| Review identity | Show exact model/configuration and ask user to compare physical label | No automatic confirmation from model confidence |
| Guided check | One server-authorized check, canonical instruction, source/version, approved observation form | BLOCKED/UNKNOWN/ESCALATED hides next actions |
| Save result | Submit structured human observation with expected revision and stable idempotency key | Pending/timeout is not saved; retry reconciles same command |
| Summary | Distinguish human-reported resolved/unresolved from durable evidence status; show references | Missing receipt does not display a success tick |
| Session recovery | Fetch authoritative server state, reconcile pending submission, refresh policy | Offline or stale tab cannot continue from cached READY |

No unrestricted chat is needed for R0. Symptom text is untrusted input; observations use catalog-defined fields/options. Do not turn user text, OCR or AI text into HTML. External/source links must be authorized URLs supplied by A; render safely.

## Tasks

1. **J-01 state inventory and prototype.** Produce compact wireframes and a state-to-screen table; use A's fake responses for every state. Show clear text labels as well as colors. Design for a phone used beside a laptop; avoid an overlay/video requirement.
2. **J-02 capture + identity.** Camera permission flow, image preview/retake, upload feedback, manual fallback and explicit human identity confirmation. Client limits help UX; A still validates all bytes.
3. **J-03 guidance + observations.** Render canonical server-supplied check/source and structured observation controls. No inferred authorization from missing fields or a model message. Display pending and blocked states unambiguously.
4. **J-04 retry + recovery.** One stable idempotency key per intentional action; preserve only minimal pending command metadata securely across transient failure, never assume a fresh key is a retry. On reload, GET authoritative session and reconcile through A. Stale revision prompts refresh; no automatic resubmit of a different payload.
5. **J-05 summary + UI checks.** Show durable receipt and explicitly human-reported outcome; keyboard labels/focus, mobile layout, screen-reader state updates and clear escalation. Component and API-fixture tests cover all states. Submit J's UX acceptance evidence to A.

## Data/security boundaries

Use same-origin authenticated requests; no provider keys/client secrets/local authorization flags. Do not store raw images, source documents or full sessions in browser persistent storage. If minimal pending-key persistence is needed, agree its scope/expiry with A. Clear it after confirmed receipt/logout. Do not log images, serials, tokens or document excerpts in console/analytics. Connectivity loss marks displayed guidance stale and disables progression pending server revalidation. Logout removes private client state.

## Acceptance

- A new user can complete the fake-engine happy path without instructions from the developers.
- Every API status/error has an explicit usable screen; camera denial is recoverable.
- Double tap, slow response, reload and lost response never show false completion or create a second intentional command.
- Withdrawing authorization, catalog update, stale session, outage or unknown identity stops the next action visibly.
- Model prose cannot become HTML or operational guidance. Sources, human-confirmation labels and saved/pending distinction remain visible.
- J's frontend works against fixtures while A/V continue implementation; switching to real API requires only configured endpoint/auth, not a second business-rule layer.

J can review backend API design using their backend experience. Any implementation outside `mark1/web/**` returns to its owner.

## Freshness, hazards and stop

Poll active visible sessions every five seconds; hide instructions on refresh failure, 15-second lease expiry, tab backgrounding or loss of connectivity. On focus/resume, fetch current state before restoring guidance. Always show canonical safety notice/stop conditions and a Report hazard / Stop control. Reporting a hazard locks the UI immediately, including offline, then reconciles with A using the same command key. Do not let a pending ordinary observation override a local stop. The backend remains authoritative; the UI cannot guarantee immediate remote-revocation detection.
