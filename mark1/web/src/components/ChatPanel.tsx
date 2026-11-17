import { useEffect, useRef, useState } from 'react';
import { MESSAGE_MAX_CHARS } from '../api/types';
import { useControllerState, useEnv } from '../app/context';

export interface HistoricalPrompt {
  key: string;
  kind: string;
  text: string;
}

let consentGiven = false; // memory only, per page load

export function ChatPanel({ enabled, history, suspendVoice }: { enabled: boolean; history: HistoricalPrompt[]; suspendVoice: boolean }) {
  const { controller, speech, readOnly } = useEnv();
  const st = useControllerState();
  const [text, setText] = useState('');
  const [fromVoice, setFromVoice] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState('');
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [askConsent, setAskConsent] = useState(false);
  const stopRef = useRef<(() => void) | null>(null);

  // Stop/offline/background: stop listening immediately.
  useEffect(() => {
    if (suspendVoice && stopRef.current) {
      stopRef.current();
      stopRef.current = null;
      setListening(false);
      setInterim('');
    }
  }, [suspendVoice]);
  useEffect(() => () => stopRef.current?.(), []);

  const startListening = () => {
    if (!consentGiven) {
      setAskConsent(true);
      return;
    }
    setVoiceError(null);
    setListening(true);
    stopRef.current = speech.listen({
      onInterim: (t) => setInterim(t),
      onFinal: (t) => {
        setInterim('');
        setText((prev) => (prev ? `${prev} ${t}` : t).slice(0, MESSAGE_MAX_CHARS));
        setFromVoice(true);
      },
      onError: (code) => setVoiceError(code === 'not-allowed' ? 'Microphone permission was denied. You can type instead.' : code === 'no-speech' ? 'No speech was heard. Try again or type.' : 'Voice input stopped. You can type instead.'),
      onEnd: () => {
        setListening(false);
        setInterim('');
        stopRef.current = null;
      },
    });
  };

  const stopListening = () => {
    stopRef.current?.();
  };

  const send = async () => {
    const ok = await controller.sendMessage(text, fromVoice ? 'VOICE_TRANSCRIPT' : 'CHAT');
    if (ok) {
      setText('');
      setFromVoice(false);
    }
  };

  const disabled = !enabled || !!readOnly || !!st.pending || st.locallyStopped;

  return (
    <section className="panel chat" aria-labelledby="chat-h">
      <h2 id="chat-h">Conversation</h2>
      {history.length ? (
        <details>
          <summary>Earlier steps ({history.length}) — historical, not current guidance</summary>
          <ol className="history">
            {history.map((h) => (
              <li key={h.key} className="historical">
                <span className="badge">Historical</span> <span className="small">{h.kind}</span> {h.text}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
      <ol className="messages" aria-live="polite">
        {st.messages.map((m) => (
          <li key={m.localId} className="msg-user">
            <span className="badge report">Your report{m.channel === 'VOICE_TRANSCRIPT' ? ' (voice transcript)' : ''} — not a confirmed observation</span>
            <span className="msg-text">{m.text}</span>
            <span className="small muted"> {m.saved === true ? 'Saved' : m.saved === 'FAILED' ? 'Not saved' : 'Sending…'}</span>
          </li>
        ))}
      </ol>

      <label htmlFor="chat-input">Describe what you see or ask a question</label>
      <textarea
        id="chat-input"
        value={text}
        maxLength={MESSAGE_MAX_CHARS}
        rows={3}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
        aria-describedby="chat-count"
      />
      {interim ? <p className="small muted" aria-live="polite">Hearing: {interim}</p> : null}
      <div className="row">
        <span id="chat-count" className="small muted">
          {text.length}/{MESSAGE_MAX_CHARS}
          {fromVoice ? ' · from voice — edit before sending' : ''}
        </span>
      </div>
      <div className="row">
        <button type="button" className="primary" onClick={send} disabled={disabled || !text.trim()}>
          Send
        </button>
        {speech.recognitionSupported ? (
          listening ? (
            <button type="button" onClick={stopListening} aria-pressed="true">
              Stop listening
            </button>
          ) : (
            <button type="button" onClick={startListening} disabled={disabled || suspendVoice}>
              Talk
            </button>
          )
        ) : (
          <span className="small muted">Voice input is not supported in this browser — typing works.</span>
        )}
      </div>
      {voiceError ? <p role="alert">{voiceError}</p> : null}
      <p className="small muted">Messages are saved as your report. They never count as a confirmed check.</p>

      {askConsent ? (
        <div role="dialog" aria-modal="true" aria-labelledby="consent-h" className="dialog">
          <h3 id="consent-h">Use voice input?</h3>
          <p>
            Your browser converts speech to text. Depending on the browser, audio may be processed by the browser vendor's
            service. This app does not upload audio; you will see and can edit the text before sending. Use fictional demo
            content only.
          </p>
          <div className="row">
            <button
              type="button"
              className="primary"
              onClick={() => {
                consentGiven = true;
                setAskConsent(false);
                startListening();
              }}
            >
              Allow voice input
            </button>
            <button type="button" onClick={() => setAskConsent(false)}>
              Type instead
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function _resetConsentForTests() {
  consentGiven = false;
}
