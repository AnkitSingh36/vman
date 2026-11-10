# J-01 Phone journey and v2 state inventory

Owner: J | Contract 2.0 | 11 November 2026 | Synthetic R0 only.

The live rendering of every canonical fixture is the **state gallery**: `npm run dev` in `mark1/web`, then open `http://localhost:5173/?gallery`. Screens below are wireframes of what the implemented panels show.

## Journey (main synthetic path)

```
Start ──► Identify ──► Confirm identity ──► Preflight ──► View ──► Question ──► Check ──► Explanation ──► Summary
 symptom   photo/label  radio + "I compared   CLEAR /      snapshot  enum        ON/OFF/   2D cutaway +   escalated /
           (camera or   with physical label"  HAZARD /     or can't  answer      UNSURE +  SUSPECTED      completed +
           manual)                            UNSURE       / unsure              confirm   + Continue     history
                                                   │
                                                   └─ HAZARD/UNSURE ─► Escalated (no further prompt, diagram or speech)
Stop / Report hazard available on every non-terminal screen ─► Escalated
```

## Phone wireframes

```
┌──────────────────────────────┐   ┌──────────────────────────────┐   ┌──────────────────────────────┐
│ Mark-1   [Synthetic demo]    │   │ Status: View requested       │   │ Status: Explanation          │
│ Status: Identify device      │   │ [Stop] [Report hazard]       │   │ [Stop] [Report hazard]       │
│ [Stop] [Report hazard]       │   │ ┌ Show a view ─────────────┐ │   │ ┌ How it works… ───────────┐ │
│ ┌ Identify the device ─────┐ │   │ │ <interaction.text>       │ │   │ │ (Advisory·cause unconf.) │ │
│ │ ○ DEMO-LAPTOP / DEMO-C1  │ │   │ │ Source: DEMO-GUIDE v2    │ │   │ │ <interaction.text>       │ │
│ │   read from photo (model │ │   │ │ [Read aloud][Stop][Mute] │ │   │ │ • SUSPECTED <claim>      │ │
│ │   interpretation)        │ │   │ │ [Open camera][Choose…]   │ │   │ │ ┌ diagram vN · source ──┐│ │
│ │ ☐ I compared with label  │ │   │ │ [Send selected snapshot] │ │   │ │ │[Input]──►[Ctrl]──►[Dsp]││ │
│ │ [Confirm identity]       │ │   │ │ [Can't show][Not sure]   │ │   │ │ │ SUSPECTED              ││ │
│ │ Photograph the label     │ │   │ │ Safety: …                │ │   │ │ └ not camera vision ────┘│ │
│ │ Or type the label […][⏎] │ │   │ └──────────────────────────┘ │   │ │ [Continue]               │ │
│ └──────────────────────────┘ │   │ ▸ Finish: report outcome     │   │ └──────────────────────────┘ │
│ ┌ Conversation ────────────┐ │   │ ┌ Conversation ────────────┐ │   │ Offline/expired: text,       │
│ │ [text…] 0/2000 [Send][🎤]│ │   │ │ Earlier steps (historical)│ │   │ options, diagram replaced by │
│ └──────────────────────────┘ │   │ │ Your report — not confirmed│ │   │ "Guidance hidden…"; safety  │
└──────────────────────────────┘   └──────────────────────────────┘   │ and Stop remain              │
                                                                     └──────────────────────────────┘
```

## State inventory

| Status | Shown | Actions | Hidden when |
| --- | --- | --- | --- |
| (no session) | Start: supported demo + optional symptom text | Start | — |
| AWAITING_IDENTITY | Candidates (basis IMAGE = model interpretation / MANUAL), reason (`NO_SUPPORTED_MATCH`, `IDENTITY_UNREADABLE`), camera, manual label | Upload identity photo → identity-candidates; manual label; confirm (radio + physical-label checkbox) | Camera stopped on stop/offline/background |
| EVALUATING | "Evaluating…", no guidance | Chat, Stop, Hazard, Outcome (server decides) | — |
| AWAITING_VIEW (IDENTITY purpose) | "Show the label", interaction text, source | Snapshot+Send, Can't show, Not sure | Lease expiry, offline, background, refresh failure, stop |
| AWAITING_VIEW (INVESTIGATION) | "Show a view", interaction text, source | same | same |
| AWAITING_ANSWER | Question legend + enum radios, source, "answer is your report" | Submit answer | same |
| EXPLAINING | Advisory badge, text, SUSPECTED claims+evidence, source, cutaway or "Diagram unavailable" | Continue (ack, "not repair verification") | same (incl. highlights) |
| READY | "Approved check" (preflight or observation), enum radios, source | Value + "I made this observation" → Save | same |
| RECORD_PENDING | "Saving your observation — not yet saved" | Stop/Hazard only | — |
| BLOCKED / UNKNOWN / ESCALATED / COMPLETED | Terminal summary, reason, outcome, receipt (saved vs not), history labelled historical | Start new session | No guidance ever |

## Cross-cutting states

| Condition | UI |
| --- | --- |
| Sending / retrying same key | Banner "Sending…" / "retrying the same request"; actions disabled |
| Unknown result (lost response) | "Not confirmed saved…" + Retry now (same key/payload); auto-reconcile on reconnect |
| 409 stale / step changed | "This step changed…" and current state shown; nothing re-sent automatically |
| 401/403/404/413/415/422/429/503 | User-safe message, no guidance or protected details |
| Offline | Banner; guidance hidden; speech/camera/voice stopped; Stop locks locally and queues |
| Background / resume | Hidden while backgrounded; current state fetched before restore |
| Lease expiry | "Guidance expired. Checking current state…"; speech cancelled |
| Local stop | Immediate hide + speech cancel; "Stopped on this device… will retry" until server ack |
| Reload | Session id from URL fragment → GET current state; unknown id → start screen |
| Speech unsupported / denied / no consent | Typing fallback text; no mic button / alert; "Type instead" |
| Camera denied / unsupported | Alert + "Choose photo" file picker |

## Accessibility

Focus moves to each new active panel heading; status/pending/notice are live regions; all controls are native buttons/radios/checkboxes with labels and ≥ 44 px targets; diagram has `<title>`/`<desc>`, a text flow list and a highlight legend (colour + dash pattern + text); `prefers-color-scheme` and `prefers-reduced-motion` respected. Screen-reader and keyboard walkthrough on target phones is still to be recorded (J-07).
