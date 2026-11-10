# J review of contract 2.0 (UI consumer)

Owner: J | Reviewed: `06-CONTRACTS.md`, `contracts/*.json`, `12-ARCHITECTURE-EXPLAINED-AND-OPEN-GAPS.md` (branch `docs/mark1-architecture-review`) | 11 November 2026

This is J's consumer review requested before freeze (spec 02/10). It does not edit A's contract. The web client in `mark1/web` is built against contract 2.0 as published; the items below are requests or questions, not adopted changes.

## Consumed as-is (works for the UI)

- Status-driven rendering with exactly one interaction/check; terminal states with no output.
- `guidance_valid_until - policy_checked_at` as lease length; client measures from local receipt and caps at 15 s (no device-clock trust).
- Idempotency-Key + `expected_revision`; replay returns `X-Command-Id`/`X-Command-State` plus fresh Session.
- Stop/hazard accepted with stale revision.
- Diagram as authored nodes/edges with integer 0..1000 positions; null diagram ⇒ no highlights.
- All 11 states, both variants and all error fixtures render (see `?gallery`); every fake response and every client request body validates against the canonical schemas in `mark1/web/tests`.

## Requests / questions for A

| # | Item | Why the UI needs it | Proposed |
| --- | --- | --- | --- |
| J-R1 | **Outcome availability** is a server rule (">= 1 durable check observation") that the client cannot see | Otherwise the UI offers "Report outcome" and gets 409, or J would have to copy policy | Add `outcome_allowed: boolean` (or `allowed_commands: [...]`) to Session |
| J-R2 | **Pending-key persistence** scope/expiry (spec 05 "only by A-agreed scope/expiry") | Without it, a reload during an unconfirmed command loses the key; a re-tap creates a new key (possible duplicate logical evidence) | Agree: sessionStorage `{session_id, op, key, payload-hash}` cleared on receipt/logout/30 min — or confirm server dedupes per interaction/check version so memory-only is enough |
| J-R3 | **Auth/CSRF** (A-01) | Client sends same-origin cookies; needs header name/token source if cookie+CSRF is chosen | Publish header + how to obtain token; `HttpTransport` already accepts an auth-header hook |
| J-R4 | **Image upload returns no Session** | Client must GET after upload to learn the new revision before the view response | Fine as is; confirm, or return Session/revision in `ImageReceipt` (it already has `revision`) |
| J-R5 | **Pixel limits** (D08) | Client downsizes to 2048 px provisionally | Publish max dimensions/megapixels |
| J-R6 | **reason_code vocabulary** | UI maps `NO_SUPPORTED_MATCH`, `IDENTITY_UNREADABLE` to help text; others shown raw | Publish an enum of user-facing reason codes |
| J-R7 | **AR-01 flow-only explanation** | Schema requires `advisory: true` and ≥ 1 SUSPECTED claim; a pure "how it works" explanation cannot be represented | Renderer already handles empty claims and would hide the advisory badge if `advisory: false` |
| J-R8 | **AR-02 visual finding** | UI needs finding text, frame reference (thumbnail served by A), uncertainty and confirm/correct commands | J will add a "Model saw…" card with Confirm / Correct / Not sure once the shape is defined |
| J-R9 | **AR-03 corrections** | No command to correct an earlier answer/observation; today the user can only add a chat report | Define correction command + which states allow it; J adds "Change answer" in history |
| J-R10 | **Event `human_assertion` for messages** | Events may echo transcript text; UI shows it in history | Confirm whether message text belongs in events or only a summary |
| J-R11 | **Target browsers + speech consent wording** (D08/AR-04) | Needed to run and publish the matrix | Name browsers/devices; approve wording in `speech-browser-matrix.md` |

## UX notes for V (content)

- Interaction `text` is shown and spoken verbatim; keep it short (< 200 chars) and phone-readable.
- Diagram node labels are drawn at fixed size; labels over ~14 characters will crowd at phone width. Edge labels are drawn only when they fit and are always listed as text below the diagram.
- `target_node_id` on VIEW is not displayed yet (no diagram in VIEW); tell J if it should highlight a node in a mini-diagram.
