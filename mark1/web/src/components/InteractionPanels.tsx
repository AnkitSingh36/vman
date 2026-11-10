import { useState } from 'react';
import type { Check, ExplanationInteraction, QuestionInteraction, Session, ViewInteraction } from '../api/types';
import { useEnv } from '../app/context';
import type { HideReason } from '../state/lease';
import { CameraCapture, type CapturedFrame } from './CameraCapture';
import { ConfirmBox, HiddenGuidance, PanelHeading, ReadAloud, SafetyBlock, SourceLine } from './common';
import { CutawayDiagram } from './CutawayDiagram';

interface Common {
  session: Session;
  hidden: HideReason | null;
  busy: boolean;
  gKey: string;
}

/** Ensures the command targets exactly the interaction the user saw. */
const sameInteraction = (id: string) => (s: Session) => s.interaction?.interaction_id === id;
const sameCheck = (c: Check) => (s: Session) => s.current_check?.check_id === c.check_id && s.current_check.version === c.version;

// ---------------- VIEW ----------------
export function ViewPanel({ session, hidden, busy, gKey }: Common) {
  const { controller, readOnly } = useEnv();
  const it = session.interaction as ViewInteraction;
  const [frame, setFrame] = useState<CapturedFrame | null>(null);
  const disabled = busy || !!hidden || !!readOnly;
  const purpose = it.purpose === 'IDENTITY' ? 'identity' : 'investigation';

  const respond = async (result: 'IMAGE' | 'UNAVAILABLE' | 'UNSURE') => {
    let imageId: string | null = null;
    if (result === 'IMAGE') {
      if (!frame) return;
      imageId = await controller.uploadImage(frame.blob, purpose);
      if (!imageId) return;
    }
    const ok = await controller.submit(
      'view-responses',
      (s) => ({ expected_revision: s.revision, interaction_id: it.interaction_id, template_id: it.template_id, template_version: it.template_version, result, image_id: imageId, human_confirmed: true }),
      sameInteraction(it.interaction_id),
    );
    if (ok) setFrame(null);
  };

  return (
    <section className="panel" aria-labelledby="view-h">
      <PanelHeading focusKey={gKey}>
        <span id="view-h">{it.purpose === 'IDENTITY' ? 'Show the label' : 'Show a view'}</span>
      </PanelHeading>
      {hidden ? (
        <HiddenGuidance reason={hidden} />
      ) : (
        <>
          <p className="guidance" data-testid="guidance-text">{it.text}</p>
          <SourceLine source={it.source} />
          <ReadAloud text={it.text} guidanceKey={gKey} hidden={!!hidden} />
          <CameraCapture onFrame={setFrame} disabled={disabled} suspend={!!hidden} />
          <div className="row">
            <button type="button" className="primary" disabled={disabled || !frame} onClick={() => respond('IMAGE')}>
              Send selected snapshot
            </button>
            <button type="button" disabled={disabled} onClick={() => respond('UNAVAILABLE')}>
              Can't show this view
            </button>
            <button type="button" disabled={disabled} onClick={() => respond('UNSURE')}>
              Not sure
            </button>
          </div>
        </>
      )}
      <SafetyBlock notice={it.safety_notice} stops={it.stop_conditions} />
    </section>
  );
}

// ---------------- QUESTION ----------------
export function QuestionPanel({ session, hidden, busy, gKey }: Common) {
  const { controller, readOnly } = useEnv();
  const it = session.interaction as QuestionInteraction;
  const [value, setValue] = useState<string | null>(null);
  const disabled = busy || !!hidden || !!readOnly;

  const submit = async () => {
    if (!value) return;
    await controller.submit(
      'answers',
      (s) => ({ expected_revision: s.revision, interaction_id: it.interaction_id, template_id: it.template_id, template_version: it.template_version, value, human_confirmed: true }),
      sameInteraction(it.interaction_id),
    );
  };

  return (
    <section className="panel" aria-labelledby="q-h">
      <PanelHeading focusKey={gKey}>
        <span id="q-h">Question</span>
      </PanelHeading>
      {hidden ? (
        <HiddenGuidance reason={hidden} />
      ) : (
        <>
          <fieldset>
            <legend className="guidance" data-testid="guidance-text">{it.text}</legend>
            {it.options.map((o) => (
              <label key={o} className="option">
                <input type="radio" name={`q-${it.interaction_id}`} value={o} checked={value === o} onChange={() => setValue(o)} disabled={disabled} /> {o}
              </label>
            ))}
          </fieldset>
          <SourceLine source={it.source} />
          <ReadAloud text={it.text} guidanceKey={gKey} hidden={!!hidden} />
          <button type="button" className="primary" onClick={submit} disabled={disabled || !value}>
            Submit answer
          </button>
          <p className="small muted">Your answer is saved as your report. It is not a confirmed physical observation.</p>
        </>
      )}
      <SafetyBlock notice={it.safety_notice} stops={it.stop_conditions} />
    </section>
  );
}

// ---------------- EXPLANATION ----------------
export function ExplanationPanel({ session, hidden, busy, gKey }: Common) {
  const { controller, readOnly } = useEnv();
  const it = session.interaction as ExplanationInteraction;
  const disabled = busy || !!hidden || !!readOnly;

  const ack = async () => {
    await controller.submit(
      'explanation-acks',
      (s) => ({ expected_revision: s.revision, interaction_id: it.interaction_id, template_id: it.template_id, template_version: it.template_version, acknowledged: true }),
      sameInteraction(it.interaction_id),
    );
  };

  return (
    <section className="panel" aria-labelledby="ex-h">
      <PanelHeading focusKey={gKey}>
        <span id="ex-h">How it works and what is suspected</span>
      </PanelHeading>
      {it.advisory ? <p className="badge advisory">Advisory · synthetic · cause unconfirmed</p> : null}
      {hidden ? (
        <HiddenGuidance reason={hidden} />
      ) : (
        <>
          <p className="guidance" data-testid="guidance-text">{it.text}</p>
          <ul className="claims">
            {it.claims.map((c, i) => (
              <li key={i}>
                <span className="badge suspected">{c.label}</span> {c.text}
                <span className="small muted"> Evidence: {c.evidence_ids.join(', ')}</span>
              </li>
            ))}
          </ul>
          <SourceLine source={it.source} />
          <ReadAloud text={it.text} guidanceKey={gKey} hidden={!!hidden} />
          <CutawayDiagram diagram={it.diagram} highlights={it.highlights} />
          <button type="button" className="primary" onClick={ack} disabled={disabled}>
            Continue
          </button>
          <p className="small muted">Continuing records that you saw this explanation. It does not verify any repair.</p>
        </>
      )}
      <SafetyBlock notice={it.safety_notice} stops={it.stop_conditions} />
    </section>
  );
}

// ---------------- CHECK / PREFLIGHT (READY) ----------------
export function CheckPanel({ session, hidden, busy, gKey }: Common) {
  const { controller, readOnly } = useEnv();
  const c = session.current_check as Check;
  const [value, setValue] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const disabled = busy || !!hidden || !!readOnly;

  const submit = async () => {
    if (!value || !confirmed) return;
    await controller.submit(
      'observations',
      (s) => ({ expected_revision: s.revision, check_id: c.check_id, check_version: c.version, observation_code: c.observation_code, value, human_confirmed: true }),
      sameCheck(c),
    );
  };

  return (
    <section className="panel" aria-labelledby="check-h">
      <PanelHeading focusKey={gKey}>
        <span id="check-h">Approved check</span>
      </PanelHeading>
      {hidden ? (
        <HiddenGuidance reason={hidden} />
      ) : (
        <>
          <fieldset>
            <legend className="guidance" data-testid="guidance-text">{c.instruction}</legend>
            {c.options.map((o) => (
              <label key={o} className="option">
                <input type="radio" name={`c-${c.check_id}`} value={o} checked={value === o} onChange={() => setValue(o)} disabled={disabled} /> {o}
              </label>
            ))}
          </fieldset>
          <SourceLine source={c.source} />
          <ReadAloud text={c.instruction} guidanceKey={gKey} hidden={!!hidden} />
          <ConfirmBox checked={confirmed} onChange={setConfirmed}>
            I made this observation myself and the value above is what I saw.
          </ConfirmBox>
          <button type="button" className="primary" onClick={submit} disabled={disabled || !value || !confirmed}>
            Save observation
          </button>
        </>
      )}
      <SafetyBlock notice={c.safety_notice} stops={c.stop_conditions} />
    </section>
  );
}
