import type { Session } from '../api/types';
import { TERMINAL_STATUSES } from '../api/types';
import type { HideReason } from '../state/lease';
import { guidanceKey } from '../state/lease';
import { ChatPanel, type HistoricalPrompt } from './ChatPanel';
import { OutcomePanel, SummaryPanel } from './Chrome';
import { IdentityPanel } from './IdentityPanel';
import { CheckPanel, ExplanationPanel, QuestionPanel, ViewPanel } from './InteractionPanels';

const MESSAGE_STATES = ['AWAITING_IDENTITY', 'EVALUATING', 'AWAITING_VIEW', 'AWAITING_ANSWER', 'EXPLAINING', 'READY'];

const STATUS_TEXT: Record<string, string> = {
  AWAITING_IDENTITY: 'Identify device',
  EVALUATING: 'Evaluating',
  AWAITING_VIEW: 'View requested',
  AWAITING_ANSWER: 'Question',
  EXPLAINING: 'Explanation',
  READY: 'Check',
  RECORD_PENDING: 'Saving',
  BLOCKED: 'Blocked',
  UNKNOWN: 'Unknown',
  ESCALATED: 'Escalated',
  COMPLETED: 'Completed',
};

export function statusLabel(s: Session['status']) {
  return STATUS_TEXT[s] ?? s;
}

/**
 * Renders exactly one active interaction for the server-declared status.
 * Panels are selected only by `status`; readiness is never inferred from missing fields.
 */
export function SessionScreen({
  session,
  hidden,
  busy,
  history,
  onNew,
}: {
  session: Session;
  hidden: HideReason | null;
  busy: boolean;
  history: HistoricalPrompt[];
  onNew: () => void;
}) {
  const gKey = guidanceKey(session) ?? `${session.session_id}:${session.status}`;
  const terminal = TERMINAL_STATUSES.includes(session.status);
  const k = session.interaction?.kind;

  let main: JSX.Element;
  switch (session.status) {
    case 'AWAITING_IDENTITY':
      main = <IdentityPanel key={session.session_id} session={session} busy={busy} suspend={hidden === 'STOPPED' || hidden === 'OFFLINE' || hidden === 'HIDDEN'} />;
      break;
    case 'AWAITING_VIEW':
      main = k === 'VIEW' ? <ViewPanel key={gKey} session={session} hidden={hidden} busy={busy} gKey={gKey} /> : <Invalid />;
      break;
    case 'AWAITING_ANSWER':
      main = k === 'QUESTION' ? <QuestionPanel key={gKey} session={session} hidden={hidden} busy={busy} gKey={gKey} /> : <Invalid />;
      break;
    case 'EXPLAINING':
      main = k === 'EXPLANATION' ? <ExplanationPanel key={gKey} session={session} hidden={hidden} busy={busy} gKey={gKey} /> : <Invalid />;
      break;
    case 'READY':
      main = session.current_check ? <CheckPanel key={gKey} session={session} hidden={hidden} busy={busy} gKey={gKey} /> : <Invalid />;
      break;
    case 'EVALUATING':
      main = (
        <section className="panel" aria-busy="true">
          <h2 tabIndex={-1}>Evaluating…</h2>
          <p>Reviewing the saved information. No guidance is shown until the next step is authorized.</p>
          <div className="spinner" aria-hidden="true" />
        </section>
      );
      break;
    case 'RECORD_PENDING':
      main = (
        <section className="panel" aria-busy="true">
          <h2 tabIndex={-1}>Saving your observation</h2>
          <p data-testid="record-pending">Not yet saved. Nothing else will be shown until it is saved.</p>
          {session.receipt ? <p className="small">Command {session.receipt.command_id}: pending</p> : null}
        </section>
      );
      break;
    default:
      main = terminal ? <SummaryPanel session={session} onNew={onNew} /> : <Invalid />;
  }

  return (
    <>
      {main}
      {!terminal ? <OutcomePanel session={session} busy={busy} /> : null}
      {!terminal && MESSAGE_STATES.includes(session.status) ? (
        <ChatPanel enabled={!busy} history={history} suspendVoice={!!hidden && hidden !== 'EXPIRED'} />
      ) : null}
    </>
  );
}

function Invalid() {
  return (
    <section className="panel" role="alert">
      <h2>Unexpected state</h2>
      <p>The server state did not match the contract. No guidance is shown.</p>
    </section>
  );
}
