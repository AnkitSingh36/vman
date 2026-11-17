import { useEffect, useRef, useState } from 'react';
import { useControllerState, useEnv, useNow } from './app/context';
import { DevPanel } from './components/DevPanel';
import { StatusBanner, StopBar } from './components/Chrome';
import { SessionScreen, statusLabel } from './components/SessionScreen';
import type { HistoricalPrompt } from './components/ChatPanel';
import { guidanceKey } from './state/lease';

function readHashSession(): string | null {
  const m = /(?:^|[#&])s=([^&]+)/.exec(window.location.hash);
  return m ? decodeURIComponent(m[1]) : null;
}

export function App({ onReset }: { onReset: () => void }) {
  const { controller, mode } = useEnv();
  const st = useControllerState();
  useNow(250);
  const [symptom, setSymptom] = useState('');
  const [history, setHistory] = useState<HistoricalPrompt[]>([]);
  const lastShown = useRef<{ key: string; kind: string; text: string } | null>(null);

  // Browser lifecycle -> controller (offline/background hide + cancel speech; refresh on resume).
  useEffect(() => {
    const on = () => controller.setOnline(true);
    const off = () => controller.setOnline(false);
    const vis = () => controller.setVisible(document.visibilityState !== 'hidden');
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    document.addEventListener('visibilitychange', vis);
    const hide = () => controller.setVisible(false);
    window.addEventListener('pagehide', hide);
    const resumeId = readHashSession();
    if (resumeId && !controller.getState().session) void controller.resume(resumeId);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
      document.removeEventListener('visibilitychange', vis);
      window.removeEventListener('pagehide', hide);
    };
  }, [controller]);

  // Session id lives only in the URL fragment (no browser storage) so reload can resume.
  const sid = st.session?.session_id;
  useEffect(() => {
    if (sid && st.lastRefreshOk) window.history.replaceState(null, '', `#s=${encodeURIComponent(sid)}`);
  }, [sid, st.lastRefreshOk]);

  // Track superseded prompts as historical (memory only; never spoken).
  const s = st.session;
  const key = guidanceKey(s);
  useEffect(() => {
    const prev = lastShown.current;
    if (prev && prev.key !== key) setHistory((h) => [...h, { key: prev.key, kind: prev.kind, text: prev.text }]);
    if (s && key) {
      const text = s.interaction?.text ?? s.current_check?.instruction ?? '';
      const kind = s.interaction?.kind ?? (s.current_check ? 'CHECK' : '');
      lastShown.current = { key, kind, text };
    } else lastShown.current = null;
  }, [key, s]);

  const hidden = controller.hiddenReason();
  const busy = !!st.pending || st.locallyStopped;

  const newSession = () => {
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
    onReset();
  };

  return (
    <div className="app">
      <header className="top">
        <h1>Mark-1</h1>
        <p className="badge demo">Synthetic demo · {mode === 'fake' ? 'fake backend (UI test double)' : 'connected backend'}</p>
        {s?.status ? (
          <p className="status" aria-live="polite">
            Status: <strong data-testid="status">{statusLabel(s.status)}</strong>
            {s.identity ? (
              <span className="small">
                {' '}
                · {s.identity.model_id} / {s.identity.configuration_id} (human-confirmed)
              </span>
            ) : null}
          </p>
        ) : null}
      </header>

      <StopBar />
      <StatusBanner hidden={hidden} />

      <main>
        {!s ? (
          <section className="panel" aria-labelledby="start-h">
            <h2 id="start-h">Start an investigation</h2>
            <p>Supported in this demo: fictional DEMO-LAPTOP, symptom “no power”. Use fictional demo content only.</p>
            <label htmlFor="symptom">Describe the problem (optional)</label>
            <textarea id="symptom" value={symptom} maxLength={1000} rows={2} onChange={(e) => setSymptom(e.target.value)} />
            <button type="button" className="primary" disabled={!!st.pending} onClick={() => void controller.start(symptom.trim() || undefined)}>
              Start: device has no power
            </button>
          </section>
        ) : s.status ? (
          <SessionScreen session={s} hidden={hidden} busy={busy} history={history} onNew={newSession} />
        ) : (
          <section className="panel">
            <h2>Loading current state…</h2>
          </section>
        )}
      </main>

      <footer>
        <DevPanel />
        <p className="small muted">
          The camera is the eye; a person performs every physical action. Suspected causes are advisory and unverified. <a href="?gallery">State gallery</a>
        </p>
      </footer>
    </div>
  );
}
