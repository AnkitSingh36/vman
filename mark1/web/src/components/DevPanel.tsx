import { useState } from 'react';
import { FAKE_SCENARIOS, type FakeFaults, type FakeScenario } from '../fake/fakeServer';
import { useEnv } from '../app/context';

/** Fake-backend controls (fake mode only). Lets testers drive failure paths without a server. */
export function DevPanel() {
  const { fake, mode } = useEnv();
  const [, force] = useState(0);
  if (mode !== 'fake' || !fake) return null;
  const set = <K extends keyof FakeFaults>(k: K, v: FakeFaults[K]) => {
    fake.faults[k] = v;
    force((n) => n + 1);
  };
  return (
    <details className="devpanel">
      <summary>Fake backend controls (test only)</summary>
      <label>
        Scenario (applies to new sessions){' '}
        <select
          value={fake.scenario}
          onChange={(e) => {
            fake.scenario = e.target.value as FakeScenario;
            force((n) => n + 1);
          }}
        >
          {FAKE_SCENARIOS.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </label>
      <label className="inline">
        <input type="checkbox" checked={fake.faults.offline} onChange={(e) => set('offline', e.target.checked)} /> Server unreachable
      </label>
      <label className="inline">
        <input type="checkbox" checked={fake.faults.dropNextResponse} onChange={(e) => set('dropNextResponse', e.target.checked)} /> Lose next response (after effect)
      </label>
      <label className="inline">
        <input type="checkbox" checked={fake.faults.fail503Next} onChange={(e) => set('fail503Next', e.target.checked)} /> Next request 503
      </label>
      <label className="inline">
        <input type="checkbox" checked={fake.faults.freezeLeases} onChange={(e) => set('freezeLeases', e.target.checked)} /> Freeze leases (expire guidance)
      </label>
      <label>
        Pending write (ms){' '}
        <input type="number" min={0} step={500} value={fake.faults.pendingWriteMs} onChange={(e) => set('pendingWriteMs', Number(e.target.value))} />
      </label>
      <label>
        Evaluating (ms){' '}
        <input type="number" min={0} step={100} value={fake.faults.evaluatingMs} onChange={(e) => set('evaluatingMs', Number(e.target.value))} />
      </label>
    </details>
  );
}
