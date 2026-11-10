import allFixtures from '@contracts/all-fixtures.json';
import examples from '@contracts/examples.json';
import requestFixtures from '@contracts/public-request-fixtures.json';
import scenarios from '@contracts/scenario-fixtures.json';
import { describe, expect, it } from 'vitest';
import { assertValidSession, setup, validateRequest, validateSession } from './helpers';
import type { Session } from '../src/api/types';

describe('canonical fixtures (consumer check)', () => {
  it('every all-fixtures session and variant is schema-valid', () => {
    const af = allFixtures as unknown as { sessions: Record<string, unknown>; session_variants: Record<string, unknown> };
    for (const s of [...Object.values(af.sessions), ...Object.values(af.session_variants)]) expect(validateSession(s)).toBe(true);
    expect(Object.keys(af.sessions)).toHaveLength(11);
  });

  it('public request fixtures: positives pass, negatives fail with our validator setup', () => {
    const rf = requestFixtures as unknown as { positive: Record<string, unknown>; negative: { schema: string; payload: unknown }[] };
    for (const [k, v] of Object.entries(rf.positive)) if (k !== 'ImageReceipt') expect(validateRequest(k, v)).toBe(true);
    for (const n of rf.negative) expect(validateRequest(n.schema, n.payload)).toBe(false);
  });

  it('examples are schema-valid sessions', () => {
    for (const v of Object.values(examples as Record<string, unknown>)) if (v && typeof v === 'object' && 'status' in v) expect(validateSession(v)).toBe(true);
  });
});

/** Collapse repeated statuses so asynchronous EVALUATING polling does not matter. */
function collapse(xs: string[]) {
  return xs.filter((x, i) => x !== xs[i - 1]);
}

describe('fake backend + client follow the contract end to end', () => {
  it('visual-investigation journey matches scenario-fixtures expected states', async () => {
    const { controller, rec } = setup();
    await controller.start();
    const st = () => controller.getState().session!;
    await controller.submit('identity-candidates', (s) => ({ expected_revision: s.revision, manual_label: 'DEMO-LAPTOP' }));
    expect(st().identity_candidates[0]).toMatchObject({ model_id: 'DEMO-LAPTOP', configuration_id: 'DEMO-C1', basis: 'MANUAL' });
    await controller.submit('identity-confirmation', (s) => ({ expected_revision: s.revision, model_id: 'DEMO-LAPTOP', configuration_id: 'DEMO-C1', human_confirmed: true }));
    expect(st().current_check?.check_id).toBe('DEMO-PREFLIGHT');
    const obs = (value: string) => (s: Session) => ({ expected_revision: s.revision, check_id: s.current_check!.check_id, check_version: s.current_check!.version, observation_code: s.current_check!.observation_code, value, human_confirmed: true });
    await controller.submit('observations', obs('CLEAR'));
    expect(st().status).toBe('AWAITING_VIEW');
    const fd = new Blob([new Uint8Array([0xff, 0xd8, 0xff])], { type: 'image/jpeg' });
    const img = await controller.uploadImage(fd, 'investigation');
    expect(img).toBeTruthy();
    expect(st().status).toBe('AWAITING_VIEW'); // upload preserves interaction
    const it = st().interaction!;
    await controller.submit('view-responses', (s) => ({ expected_revision: s.revision, interaction_id: it.interaction_id, template_id: it.template_id, template_version: it.template_version, result: 'IMAGE', image_id: img, human_confirmed: true }));
    expect(st().status).toBe('AWAITING_ANSWER');
    const q = st().interaction!;
    await controller.submit('answers', (s) => ({ expected_revision: s.revision, interaction_id: q.interaction_id, template_id: q.template_id, template_version: q.template_version, value: 'NO', human_confirmed: true }));
    expect(st().current_check?.check_id).toBe('DEMO-OBSERVE');
    await controller.submit('observations', obs('OFF'));
    expect(st().status).toBe('EXPLAINING');
    const ex = st().interaction!;
    expect(ex.kind === 'EXPLANATION' && ex.diagram?.diagram_id).toBe('DEMO-POWER-FLOW');
    await controller.submit('explanation-acks', (s) => ({ expected_revision: s.revision, interaction_id: ex.interaction_id, template_id: ex.template_id, template_version: ex.template_version, acknowledged: true }));
    expect(st().status).toBe('ESCALATED');

    const seen = collapse(rec.sessions.map((s) => s.status).filter((s) => s !== 'EVALUATING'));
    const expected = collapse((scenarios as unknown as { scenarios: { id: string; expected_states: string[] }[] }).scenarios.find((s) => s.id === 'visual-investigation')!.expected_states.filter((s) => s !== 'EVALUATING'));
    expect(seen).toEqual(expected);
    for (const s of rec.sessions) assertValidSession(s);
  });

  it('fake leases are fresh and at most 15 seconds', async () => {
    const { controller } = setup();
    await controller.start();
    await controller.submit('identity-candidates', (s) => ({ expected_revision: s.revision, manual_label: 'DEMO-LAPTOP' }));
    await controller.submit('identity-confirmation', (s) => ({ expected_revision: s.revision, model_id: 'DEMO-LAPTOP', configuration_id: 'DEMO-C1', human_confirmed: true }));
    const c = controller.getState().session!.current_check!;
    const granted = Date.parse(c.guidance_valid_until) - Date.parse(c.policy_checked_at);
    expect(granted).toBeLessThanOrEqual(15_000);
    expect(Math.abs(Date.parse(c.policy_checked_at) - Date.now())).toBeLessThan(5_000);
  });
});
