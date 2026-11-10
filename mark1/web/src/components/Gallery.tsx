import allFixtures from '@contracts/all-fixtures.json';
import examples from '@contracts/examples.json';
import { useMemo } from 'react';
import type { ApiErrorBody, Session } from '../api/types';
import { AppProvider, MuteProvider, useEnv } from '../app/context';
import { ApiClient, type Transport } from '../api/client';
import { SessionController } from '../state/controller';
import { NoSpeech } from '../speech/speech';
import { SessionScreen, statusLabel } from './SessionScreen';

const af = allFixtures as unknown as { sessions: Record<string, Session>; session_variants: Record<string, Session>; errors: Record<string, ApiErrorBody> };
const ex = examples as unknown as Record<string, Session | string>;

const inert: Transport = { send: () => Promise.reject(new Error('gallery is read-only')) };

/**
 * J-01 state inventory: renders every canonical v2 state/variant fixture through the real panels,
 * read-only. Fixture leases are historical; the gallery bypasses lease hiding and says so.
 */
export function Gallery() {
  const parent = useEnv();
  const env = useMemo(() => ({ ...parent, controller: new SessionController({ api: new ApiClient(inert) }), speech: new NoSpeech(), readOnly: true }), [parent]);
  const filter = (new URLSearchParams(window.location.search).get('gallery') ?? '').toLowerCase();
  const all: { id: string; session: Session }[] = [
    ...Object.entries(af.sessions).map(([k, v]) => ({ id: `all-fixtures/${k}`, session: v })),
    ...Object.entries(af.session_variants).map(([k, v]) => ({ id: `variant/${k}`, session: v })),
    ...Object.entries(ex)
      .filter(([, v]) => typeof v === 'object' && v !== null && 'status' in (v as object))
      .map(([k, v]) => ({ id: `examples/${k}`, session: v as Session })),
  ];
  // ?gallery=<text> shows only fixtures whose id or status contains <text>.
  const items = filter ? all.filter((i) => `${i.id} ${i.session.status}`.toLowerCase().includes(filter)) : all;
  return (
    <AppProvider env={env}>
      <MuteProvider>
        <div className="app gallery">
          <header className="top">
            <h1>State gallery (J-01)</h1>
            <p className="badge demo">Read-only · canonical contract fixtures · lease hiding bypassed · no commands sent</p>
            <p>
              <a href="./">Back to app</a>
            </p>
          </header>
          <nav aria-label="Fixtures">
            <ul className="toc">
              {items.map((i) => (
                <li key={i.id}>
                  <a href={`#${i.id}`}>
                    {i.id} — {statusLabel(i.session.status)}
                  </a>
                </li>
              ))}
              <li>
                <a href="#errors">Errors</a>
              </li>
            </ul>
          </nav>
          {items.map((i) => (
            <article key={i.id} id={i.id} className="gallery-item">
              <h2 className="gallery-id">
                {i.id} <span className="badge">{i.session.status}</span>
              </h2>
              <SessionScreen session={i.session} hidden={null} busy={false} history={[]} onNew={() => undefined} />
            </article>
          ))}
          <article id="errors" className="gallery-item">
            <h2 className="gallery-id">Error fixtures</h2>
            <ul>
              {Object.entries(af.errors).map(([code, e]) => (
                <li key={code}>
                  <code>{code}</code> {e.code} · retryable: {String(e.retryable)}
                </li>
              ))}
            </ul>
          </article>
        </div>
      </MuteProvider>
    </AppProvider>
  );
}
