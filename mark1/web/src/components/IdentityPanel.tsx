import { useState } from 'react';
import type { Session } from '../api/types';
import { useEnv } from '../app/context';
import { CameraCapture, type CapturedFrame } from './CameraCapture';
import { ConfirmBox, PanelHeading } from './common';

const REASONS: Record<string, string> = {
  NO_SUPPORTED_MATCH: 'No exact supported match. Check the label and try again, or retake the photo. The app never guesses the closest match.',
  IDENTITY_UNREADABLE: 'The label could not be used. Try a clearer photo or type the label.',
};

export function IdentityPanel({ session, busy, suspend }: { session: Session; busy: boolean; suspend: boolean }) {
  const { controller, readOnly } = useEnv();
  const [frame, setFrame] = useState<CapturedFrame | null>(null);
  const [label, setLabel] = useState('');
  const [chosen, setChosen] = useState<number | null>(null);
  const [checked, setChecked] = useState(false);
  const disabled = busy || !!readOnly;

  const sendImage = async () => {
    if (!frame) return;
    const imageId = await controller.uploadImage(frame.blob, 'identity');
    if (!imageId) return;
    const ok = await controller.submit('identity-candidates', (s) => ({ expected_revision: s.revision, image_id: imageId }));
    if (ok) setFrame(null);
  };

  const sendLabel = async () => {
    const v = label.trim();
    if (!v) return;
    await controller.submit('identity-candidates', (s) => ({ expected_revision: s.revision, manual_label: v.slice(0, 160) }));
  };

  const confirm = async () => {
    if (chosen === null || !checked) return;
    const c = session.identity_candidates[chosen];
    const ok = await controller.submit(
      'identity-confirmation',
      (s) => ({ expected_revision: s.revision, model_id: c.model_id, configuration_id: c.configuration_id, human_confirmed: true }),
      (s) => s.identity_candidates.some((x) => x.model_id === c.model_id && x.configuration_id === c.configuration_id),
    );
    if (ok) {
      setChosen(null);
      setChecked(false);
    }
  };

  const reason = session.reason_code ? REASONS[session.reason_code] : null;

  return (
    <section className="panel" aria-labelledby="identity-h">
      <PanelHeading focusKey={`identity-${session.revision}`}>
        <span id="identity-h">Identify the device</span>
      </PanelHeading>
      {reason ? <p role="alert" className="warn">{reason}</p> : null}

      {session.identity_candidates.length > 0 ? (
        <fieldset className="candidates">
          <legend>Supported matches — compare with the physical label</legend>
          {session.identity_candidates.map((c, i) => (
            <label key={`${c.model_id}-${c.configuration_id}`} className="candidate">
              <input type="radio" name="candidate" checked={chosen === i} onChange={() => setChosen(i)} disabled={disabled} />
              <span>
                <strong>{c.model_id}</strong> / {c.configuration_id}
                <br />
                <span className="small">
                  {c.basis === 'IMAGE' ? 'Read from your photo (model interpretation)' : 'From the label you typed'}: “{c.label_excerpt}”
                </span>
              </span>
            </label>
          ))}
          <ConfirmBox checked={checked} onChange={setChecked}>
            I compared the model and configuration with the physical label on the device.
          </ConfirmBox>
          <button type="button" className="primary" onClick={confirm} disabled={disabled || chosen === null || !checked}>
            Confirm identity
          </button>
        </fieldset>
      ) : null}

      <h3>Photograph the label</h3>
      <CameraCapture instruction="Frame the device label so the model and configuration are readable. Do not open or move the device." onFrame={setFrame} disabled={disabled} suspend={suspend} />
      <button type="button" onClick={sendImage} disabled={disabled || !frame}>
        Send selected photo
      </button>

      <h3>Or type the label</h3>
      <label htmlFor="manual-label">Label text</label>
      <div className="row">
        <input id="manual-label" value={label} maxLength={160} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. DEMO-LAPTOP" disabled={disabled} />
        <button type="button" onClick={sendLabel} disabled={disabled || !label.trim()}>
          Look up
        </button>
      </div>
      <p className="small muted">Typing the label identifies the device only; it does not count as a photo for the investigation.</p>
    </section>
  );
}
