# Speech and camera browser matrix (J-04 / AR-04)

Owner: J | Status: **template — not yet tested on devices.** Target browsers are open decision D08 (A-01).

Implementation under test: `mark1/web/src/speech/speech.ts`, `ChatPanel.tsx`, `common.tsx` (`ReadAloud`), `CameraCapture.tsx`.

## Disclosure used in the consent dialog (proposed, needs A approval)

> Your browser converts speech to text. Depending on the browser, audio may be processed by the browser vendor's service. This app does not upload audio; you will see and can edit the text before sending. Use fictional demo content only.

## Per device/browser checks

Mark each cell Pass / Fail / N/A with date and build commit.

| # | Check | iOS Safari | Android Chrome | Android Samsung Internet | Desktop Edge | Desktop Chrome |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Speech recognition supported (mic button shown) | | | | | |
| 2 | Consent dialog shown before first listen | | | | | |
| 3 | Mic permission denied → alert, typing works | | | | | |
| 4 | Transcript editable before Send; channel VOICE_TRANSCRIPT | | | | | |
| 5 | Nothing sent without explicit Send | | | | | |
| 6 | Read-aloud speaks only current interaction/check text | | | | | |
| 7 | Stop speech / Mute cancel immediately | | | | | |
| 8 | Lease expiry cancels playing + queued speech | | | | | |
| 9 | Offline cancels speech and stops listening | | | | | |
| 10 | Background (tab switch/lock) cancels speech; resume re-checks before showing | | | | | |
| 11 | Stop button cancels speech and listening | | | | | |
| 12 | Unsupported → "type instead" text, no broken control | | | | | |
| 13 | Live camera preview (environment camera) | | | | | |
| 14 | Camera denied → Choose photo works | | | | | |
| 15 | Snapshot re-encoded JPEG (no EXIF) ≤ 2048 px | | | | | |

Automated coverage already in `npm test`: consent + editable transcript + explicit send (fake adapter), unsupported fallback, read-aloud cancel on hide/context change, stop cancels speech, lease expiry hides guidance. Real-device behaviour (vendor processing, cancellation timing) can only be proven on the devices above.
