import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { SourceRef } from '../api/types';
import { HIDE_MESSAGES, type HideReason } from '../state/lease';
import { useEnv, useMute } from '../app/context';

export function SourceLine({ source, label = 'Source' }: { source: SourceRef; label?: string }) {
  return (
    <p className="source">
      {label}: <span>{source.source_id}</span> v<span>{source.version}</span> · <span>{source.locator}</span>
    </p>
  );
}

export function SafetyBlock({ notice, stops }: { notice: string; stops: string[] }) {
  return (
    <div className="safety" role="note" aria-label="Safety">
      <strong>Safety:</strong> <span>{notice}</span>
      <ul>
        {stops.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
    </div>
  );
}

/** Placeholder shown instead of actionable guidance when it must be hidden. */
export function HiddenGuidance({ reason }: { reason: HideReason }) {
  return (
    <div className="hidden-guidance" role="status" data-testid="guidance-hidden">
      {HIDE_MESSAGES[reason]}
    </div>
  );
}

/** Moves focus to the panel heading when the active step changes (screen readers + keyboard). */
export function PanelHeading({ children, focusKey }: { children: ReactNode; focusKey: string }) {
  const ref = useRef<HTMLHeadingElement>(null);
  const { readOnly } = useEnv();
  useEffect(() => {
    if (!readOnly) ref.current?.focus();
  }, [focusKey, readOnly]);
  return (
    <h2 tabIndex={-1} ref={ref}>
      {children}
    </h2>
  );
}

/**
 * Read the *current authorised* text aloud. Cancels on hide/context change/unmount.
 * Only interaction.text or check.instruction is passed in; nothing else is spoken.
 */
export function ReadAloud({ text, guidanceKey, hidden }: { text: string; guidanceKey: string; hidden: boolean }) {
  const { speech } = useEnv();
  const { muted, setMuted } = useMute();
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    if (hidden || muted) {
      speech.cancel();
      setSpeaking(false);
    }
  }, [hidden, muted, speech]);

  useEffect(() => {
    return () => {
      speech.cancel();
    };
  }, [guidanceKey, speech]);

  if (!speech.synthesisSupported) return <p className="muted small">Read-aloud is not available in this browser.</p>;
  return (
    <div className="read-aloud">
      <button
        type="button"
        disabled={hidden || muted}
        onClick={() => {
          if (speech.speak(text, () => setSpeaking(false))) setSpeaking(true);
        }}
      >
        {speaking ? 'Speaking…' : 'Read aloud'}
      </button>
      <button
        type="button"
        onClick={() => {
          speech.cancel();
          setSpeaking(false);
        }}
        disabled={!speaking}
      >
        Stop speech
      </button>
      <label className="inline">
        <input type="checkbox" checked={muted} onChange={(e) => setMuted(e.target.checked)} /> Mute
      </label>
    </div>
  );
}

export function ConfirmBox({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  return (
    <label className="confirm">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} /> {children}
    </label>
  );
}
