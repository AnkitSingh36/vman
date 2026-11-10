import { useEffect, useState } from 'react';
import type { HazardCode, Session } from '../api/types';
import { useControllerState, useEnv } from '../app/context';
import type { HideReason } from '../state/lease';
import { HIDE_MESSAGES } from '../state/lease';
import { ConfirmBox } from './common';

const HAZARDS: { code: HazardCode; label: string }[] = [
  { code: 'DAMAGE', label: 'Visible damage' },
  { code: 'LIQUID', label: 'Liquid' },
  { code: 'SWELLING', label: 'Swelling' },
  { code: 'HEAT_OR_SMELL', label: 'Heat or smell' },
  { code: 'UNSURE', label: 'Unsure / other concern' },
];

/** Stop and Report hazard — available from every active screen; never blocked by pending work. */
export function StopBar() {
  const { controller, readOnly } = useEnv();
  const st = useControllerState();
  const [open, setOpen] = useState(false);
  if (!st.session || controller.isTerminal) return null;

  return (
    <div className="stopbar" role="region" aria-label="Stop controls">
      <button type="button" className="danger" onClick={() => void controller.stop('USER_STOP')} disabled={readOnly || st.locallyStopped}>
        Stop
      </button>
      <button type="button" className="danger outline" onClick={() => setOpen((o) => !o)} aria-expanded={open} disabled={readOnly || st.locallyStopped}>
        Report hazard
      </button>
      {open && !st.locallyStopped ? (
        <div className="hazards" role="group" aria-label="Hazard type">
          {HAZARDS.map((h) => (
            <button key={h.code} type="button" className="danger outline" onClick={() => void controller.reportHazard(h.code)}>
              {h.label}
            </button>
          ))}
        </div>
      ) : null}
      {st.locallyStopped ? (
        <p role="status" className="stop-status">
          {st.stopPhase === 'ACKNOWLEDGED'
            ? 'Stop saved.'
            : st.stopPhase === 'WAITING_FOR_CONNECTION'
              ? 'Stopped on this device. Stop not yet confirmed by the server — will retry when connected.'
              : 'Stopping…'}
          {st.stopPhase === 'WAITING_FOR_CONNECTION' ? (
            <button type="button" onClick={() => void controller.retryStop()}>
              Retry now
            </button>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}

const PENDING_TEXT = {
  SENDING: 'Sending…',
  RETRYING: 'Connection problem — retrying the same request…',
  UNCONFIRMED: 'Not confirmed saved. The same request will be retried when the connection returns.',
  RECORD_PENDING: 'Saving — not yet saved.',
} as const;

export function StatusBanner({ hidden }: { hidden: HideReason | null }) {
  const { controller } = useEnv();
  const st = useControllerState();
  return (
    <div className="banners" aria-live="polite">
      {!st.online ? <p className="banner offline">{HIDE_MESSAGES.OFFLINE}</p> : null}
      {st.pending ? (
        <p className={`banner pending ${st.pending.phase.toLowerCase()}`} data-testid="pending-banner">
          {PENDING_TEXT[st.pending.phase]}
          {st.pending.phase === 'UNCONFIRMED' ? (
            <button type="button" onClick={() => void controller.retryUnconfirmed()}>
              Retry now
            </button>
          ) : null}
        </p>
      ) : null}
      {hidden && hidden !== 'STOPPED' && hidden !== 'OFFLINE' && st.session?.interaction ? <p className="banner info">{HIDE_MESSAGES[hidden]}</p> : null}
      {st.notice ? (
        <p className="banner notice" role="alert">
          {st.notice}{' '}
          <button type="button" className="link" onClick={() => controller.clearNotice()}>
            Dismiss
          </button>
        </p>
      ) : null}
    </div>
  );
}

const OUTCOME_STATES = ['READY', 'EVALUATING', 'AWAITING_VIEW', 'AWAITING_ANSWER', 'EXPLAINING'];

/** Human-reported outcome. The server decides whether it is allowed yet (>=1 saved check). */
export function OutcomePanel({ session, busy }: { session: Session; busy: boolean }) {
  const { controller, readOnly } = useEnv();
  const [choice, setChoice] = useState<'RESOLVED' | 'UNRESOLVED' | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  useEffect(() => {
    setConfirmed(false);
  }, [choice]);
  if (!OUTCOME_STATES.includes(session.status)) return null;
  return (
    <details className="panel outcome">
      <summary>Finish: report the outcome</summary>
      <fieldset>
        <legend>What is the situation now?</legend>
        <label className="option">
          <input type="radio" name="outcome" checked={choice === 'RESOLVED'} onChange={() => setChoice('RESOLVED')} /> The problem is resolved
        </label>
        <label className="option">
          <input type="radio" name="outcome" checked={choice === 'UNRESOLVED'} onChange={() => setChoice('UNRESOLVED')} /> Not resolved — escalate
        </label>
      </fieldset>
      <ConfirmBox checked={confirmed} onChange={setConfirmed}>
        This is my own report. I understand it is not a verified repair.
      </ConfirmBox>
      <button
        type="button"
        disabled={busy || !!readOnly || !choice || !confirmed}
        onClick={() => void controller.submit('outcome', (s) => ({ expected_revision: s.revision, human_reported_outcome: choice!, human_confirmed: true }))}
      >
        Save outcome
      </button>
      <p className="small muted">Available after at least one check has been saved.</p>
    </details>
  );
}

const TERMINAL_TEXT: Record<string, { title: string; body: string }> = {
  COMPLETED: { title: 'Completed — human-reported resolution', body: 'You reported the problem as resolved. This is your report, not a verified repair.' },
  ESCALATED: { title: 'Escalated', body: 'This session has ended and needs a person to follow up. No further guidance will be shown.' },
  BLOCKED: { title: 'Blocked', body: 'This workflow is not available for this device or account. No guidance can be shown.' },
  UNKNOWN: { title: 'Status unknown', body: 'Current policy or storage could not be confirmed. No guidance is shown. Start a new session to try again.' },
};

export function SummaryPanel({ session, onNew }: { session: Session; onNew: () => void }) {
  const { controller } = useEnv();
  const st = useControllerState();
  const t = TERMINAL_TEXT[session.status];
  useEffect(() => {
    if (!st.events) void controller.loadEvents();
  }, [controller, st.events]);
  return (
    <section className="panel summary" aria-labelledby="sum-h">
      <h2 id="sum-h" tabIndex={-1}>
        {t?.title ?? session.status}
      </h2>
      <p>{t?.body}</p>
      {session.reason_code ? <p className="small">Reason: {session.reason_code}</p> : null}
      {session.human_reported_outcome ? <p className="small">Human-reported outcome: {session.human_reported_outcome}</p> : null}
      {session.receipt ? (
        <p className="small">
          Last command {session.receipt.command_id}: {session.receipt.state === 'PERSISTED' ? `saved (${session.receipt.record_id})` : 'not yet saved'}
        </p>
      ) : null}
      <h3>History (historical record — not instructions)</h3>
      {st.events === null ? (
        <p className="small muted">Loading history…</p>
      ) : st.events.length === 0 ? (
        <p className="small muted">No events.</p>
      ) : (
        <ol className="events">
          {st.events.map((e) => (
            <li key={e.record_id} className="historical">
              <span className="small muted">{new Date(e.created_at).toLocaleTimeString()}</span> <code>{e.event_type}</code>{' '}
              {e.human_assertion ? <span>{e.human_assertion}</span> : null}
              {e.source_refs.length ? <span className="small muted"> · {e.source_refs.map((s) => `${s.source_id} v${s.version} ${s.locator}`).join(', ')}</span> : null}
            </li>
          ))}
        </ol>
      )}
      <button type="button" className="primary" onClick={onNew}>
        Start a new session
      </button>
    </section>
  );
}
