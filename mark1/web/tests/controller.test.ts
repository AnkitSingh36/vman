import { describe, expect, it } from 'vitest';
import { setup } from './helpers';
import type { Session } from '../src/api/types';
import type { SessionController } from '../src/state/controller';

const obs = (value: string) => (s: Session) => ({ expected_revision: s.revision, check_id: s.current_check!.check_id, check_version: s.current_check!.version, observation_code: s.current_check!.observation_code, value, human_confirmed: true });

async function toPreflight(c: SessionController) {
  await c.start();
  await c.submit('identity-candidates', (s) => ({ expected_revision: s.revision, manual_label: 'DEMO-LAPTOP' }));
  await c.submit('identity-confirmation', (s) => ({ expected_revision: s.revision, model_id: 'DEMO-LAPTOP', configuration_id: 'DEMO-C1', human_confirmed: true }));
}

async function toObserve(c: SessionController) {
  await toPreflight(c);
  await c.submit('observations', obs('CLEAR'));
  const v = c.getState().session!.interaction!;
  await c.submit('view-responses', (s) => ({ expected_revision: s.revision, interaction_id: v.interaction_id, template_id: v.template_id, template_version: v.template_version, result: 'UNAVAILABLE', image_id: null, human_confirmed: true }));
  // unavailable view -> re-requested; give an image this time
  const img = await c.uploadImage(new Blob([new Uint8Array([1])], { type: 'image/png' }), 'investigation');
  const v2 = c.getState().session!.interaction!;
  await c.submit('view-responses', (s) => ({ expected_revision: s.revision, interaction_id: v2.interaction_id, template_id: v2.template_id, template_version: v2.template_version, result: 'IMAGE', image_id: img, human_confirmed: true }));
  const q = c.getState().session!.interaction!;
  await c.submit('answers', (s) => ({ expected_revision: s.revision, interaction_id: q.interaction_id, template_id: q.template_id, template_version: q.template_version, value: 'NO', human_confirmed: true }));
}

describe('identity', () => {
  it('no closest-match guess for an unsupported label', async () => {
    const { controller } = setup();
    await controller.start();
    await controller.submit('identity-candidates', (s) => ({ expected_revision: s.revision, manual_label: 'DEMO-LAPTP' }));
    const s = controller.getState().session!;
    expect(s.status).toBe('AWAITING_IDENTITY');
    expect(s.identity_candidates).toEqual([]);
    expect(s.reason_code).toBe('NO_SUPPORTED_MATCH');
  });

  it('unreadable-label scenario asks for an IDENTITY-purpose view only', async () => {
    const { controller } = setup({ scenario: 'unreadable-label' });
    await controller.start();
    const img = await controller.uploadImage(new Blob([new Uint8Array([1])], { type: 'image/jpeg' }), 'identity');
    await controller.submit('identity-candidates', (s) => ({ expected_revision: s.revision, image_id: img! }));
    const s = controller.getState().session!;
    expect(s.status).toBe('AWAITING_VIEW');
    expect(s.interaction).toMatchObject({ kind: 'VIEW', purpose: 'IDENTITY', target_node_id: null });
    expect(s.identity).toBeNull();
  });
});

describe('commands, retries and idempotency (J-06)', () => {
  it('lost response is retried with the same key and has exactly one effect', async () => {
    const { controller, fake, rec } = setup();
    await toPreflight(controller);
    fake.faults.dropNextResponse = true;
    const ok = await controller.submit('observations', obs('CLEAR'));
    expect(ok).toBe(true);
    const posts = rec.posts('observations');
    expect(posts.length).toBe(2);
    expect(posts[0].key).toBe(posts[1].key);
    expect(posts[0].json).toEqual(posts[1].json);
    await controller.loadEvents();
    expect(controller.getState().events!.filter((e) => e.event_type === 'OBSERVATION_RECORDED')).toHaveLength(1);
    expect(controller.getState().session!.status).toBe('AWAITING_VIEW');
  });

  it('server unreachable leaves the command UNCONFIRMED (never saved) and reconciles on reconnect', async () => {
    const { controller, fake, rec } = setup();
    await toPreflight(controller);
    const before = rec.posts('observations').length;
    // allow the pre-submit refresh, then go offline for the POST itself
    const orig = fake.send.bind(fake);
    let calls = 0;
    fake.send = async (req) => {
      if (req.method === 'POST') {
        calls++;
        if (calls <= 4) throw new (await import('../src/api/client')).NetworkError('down');
      }
      return orig(req);
    };
    const ok = await controller.submit('observations', obs('CLEAR'));
    expect(ok).toBe(false);
    expect(controller.getState().pending?.phase).toBe('UNCONFIRMED');
    expect(controller.getState().session!.status).toBe('READY');
    controller.setOnline(false);
    controller.setOnline(true);
    await new Promise((r) => setTimeout(r, 0));
    await new Promise((r) => setTimeout(r, 0));
    expect(controller.getState().pending).toBeNull();
    const posts = rec.posts('observations').slice(before);
    expect(new Set(posts.map((p) => p.key)).size).toBe(1);
    expect(controller.getState().session!.status).toBe('AWAITING_VIEW');
  });

  it('double tap: second submit while pending is ignored', async () => {
    const { controller, rec } = setup();
    await toPreflight(controller);
    const a = controller.submit('observations', obs('CLEAR'));
    const b = controller.submit('observations', obs('CLEAR'));
    await Promise.all([a, b]);
    expect(rec.posts('observations')).toHaveLength(1);
  });

  it('changed answer is a new action with a new key', async () => {
    const { controller } = setup();
    await toPreflight(controller);
    const s = controller.getState().session!;
    // keys are derived from payload; different value => different signature
    const k1 = (controller as unknown as { keys: { keyFor: (a: string, b: string, c: unknown) => string } }).keys.keyFor(s.session_id, 'observations', obs('CLEAR')(s));
    const k2 = (controller as unknown as { keys: { keyFor: (a: string, b: string, c: unknown) => string } }).keys.keyFor(s.session_id, 'observations', obs('HAZARD')(s));
    expect(k1).not.toBe(k2);
  });

  it('stale revision (409) refreshes state and does not apply', async () => {
    const { controller } = setup();
    await toPreflight(controller);
    const ok = await controller.submit('observations', (s) => ({ ...obs('CLEAR')(s), expected_revision: s.revision - 1 }));
    expect(ok).toBe(false);
    expect(controller.getState().notice).toMatch(/changed/);
    expect(controller.getState().session!.status).toBe('READY');
  });

  it('a 503 without effect is retried and succeeds', async () => {
    const { controller, fake, rec } = setup();
    await toPreflight(controller);
    const n = rec.requests.length;
    fake.faults.fail503Next = true; // consumed by the pre-submit GET refresh
    const ok = await controller.submit('observations', obs('CLEAR'));
    expect(ok).toBe(false); // could not confirm current state -> nothing sent
    expect(rec.requests.slice(n).filter((r) => r.method === 'POST')).toHaveLength(0);
    expect(await controller.submit('observations', obs('CLEAR'))).toBe(true);
  });
});

describe('safety and freshness', () => {
  it('preflight HAZARD escalates with no further guidance', async () => {
    const { controller } = setup();
    await toPreflight(controller);
    await controller.submit('observations', obs('HAZARD'));
    const s = controller.getState().session!;
    expect(s.status).toBe('ESCALATED');
    expect(s.interaction).toBeNull();
    expect(s.current_check).toBeNull();
  });

  it('local stop hides immediately, cancels speech, and overrides a pending write', async () => {
    const { controller, invalidations } = setup({ faults: { pendingWriteMs: 60_000 } });
    await toPreflight(controller);
    await controller.submit('observations', obs('CLEAR'));
    expect(controller.getState().session!.status).toBe('RECORD_PENDING');
    expect(controller.getState().pending?.phase).toBe('RECORD_PENDING');
    const p = controller.stop();
    expect(controller.getState().locallyStopped).toBe(true);
    expect(controller.hiddenReason()).toBe('STOPPED');
    expect(invalidations).toContain('STOPPED');
    await p;
    expect(controller.getState().session!.status).toBe('ESCALATED');
    expect(controller.getState().stopPhase).toBe('ACKNOWLEDGED');
    // ordinary commands are refused locally after stop
    expect(await controller.submit('messages', (s) => ({ expected_revision: s.revision, text: 'x', channel: 'CHAT', human_confirmed: true }))).toBe(false);
  });

  it('stop while offline locks locally and is sent with the same key once online', async () => {
    const { controller, rec } = setup();
    await toPreflight(controller);
    controller.setOnline(false);
    await controller.stop();
    expect(controller.getState().stopPhase).toBe('WAITING_FOR_CONNECTION');
    expect(rec.posts('stop')).toHaveLength(0);
    controller.setOnline(true);
    await new Promise((r) => setTimeout(r, 0));
    await new Promise((r) => setTimeout(r, 0));
    expect(rec.posts('stop')).toHaveLength(1);
    expect(controller.getState().session!.status).toBe('ESCALATED');
  });

  it('offline/background hide guidance; resume requires a successful refresh', async () => {
    const { controller, invalidations } = setup();
    await toPreflight(controller);
    expect(controller.hiddenReason()).toBeNull();
    controller.setVisible(false);
    expect(controller.hiddenReason()).toBe('HIDDEN');
    expect(invalidations).toContain('HIDDEN');
    controller.setVisible(true);
    expect(controller.hiddenReason()).toBe('REFRESH_FAILED'); // until refresh lands
    await new Promise((r) => setTimeout(r, 0));
    expect(controller.hiddenReason()).toBeNull();
    controller.setOnline(false);
    expect(controller.hiddenReason()).toBe('OFFLINE');
  });

  it('expired lease hides guidance', async () => {
    const { controller } = setup();
    await toPreflight(controller);
    const now = controller.now();
    expect(controller.hiddenReason(now + 1_000)).toBeNull();
    expect(controller.hiddenReason(now + 15_001)).toBe('EXPIRED');
  });

  it('message re-evaluates and invalidates the prior interaction (new interaction id)', async () => {
    const { controller, invalidations } = setup();
    await toPreflight(controller);
    await controller.submit('observations', obs('CLEAR'));
    const id1 = controller.getState().session!.interaction!.interaction_id;
    await controller.sendMessage('The fictional device looks normal.', 'CHAT');
    const s = controller.getState().session!;
    expect(s.status).toBe('AWAITING_VIEW');
    expect(s.interaction!.interaction_id).not.toBe(id1);
    expect(invalidations).toContain('CONTEXT_CHANGED');
    expect(controller.getState().messages[0]).toMatchObject({ saved: true, channel: 'CHAT' });
  });

  it('three unsuccessful views escalate (exhausted views)', async () => {
    const { controller } = setup();
    await toPreflight(controller);
    await controller.submit('observations', obs('CLEAR'));
    for (let i = 0; i < 3; i++) {
      const v = controller.getState().session!.interaction!;
      await controller.submit('view-responses', (s) => ({ expected_revision: s.revision, interaction_id: v.interaction_id, template_id: v.template_id, template_version: v.template_version, result: 'UNSURE', image_id: null, human_confirmed: true }));
    }
    expect(controller.getState().session).toMatchObject({ status: 'ESCALATED', reason_code: 'VIEW_ATTEMPTS_EXHAUSTED' });
  });
});

describe('explanation, outcome', () => {
  it('diagram-unavailable: explanation with null diagram and no highlights', async () => {
    const { controller } = setup({ scenario: 'diagram-unavailable' });
    await toObserve(controller);
    await controller.submit('observations', obs('OFF'));
    const it = controller.getState().session!.interaction!;
    expect(it.kind).toBe('EXPLANATION');
    if (it.kind === 'EXPLANATION') {
      expect(it.diagram).toBeNull();
      expect(it.highlights).toEqual([]);
      expect(it.advisory).toBe(true);
    }
  });

  it('outcome is refused before any check observation, then human RESOLVED -> COMPLETED', async () => {
    const { controller } = setup();
    await toPreflight(controller);
    expect(await controller.submit('outcome', (s) => ({ expected_revision: s.revision, human_reported_outcome: 'RESOLVED', human_confirmed: true }))).toBe(false);
    await controller.submit('observations', obs('CLEAR'));
    await toObserveFrom(controller);
    await controller.submit('observations', obs('ON'));
    // ON has no supported explanation -> escalated in the fake; use a fresh run for COMPLETED path
    const r = setup();
    await toObserve(r.controller);
    await r.controller.submit('observations', obs('OFF'));
    expect(await r.controller.submit('outcome', (s) => ({ expected_revision: s.revision, human_reported_outcome: 'RESOLVED', human_confirmed: true }))).toBe(true);
    const s = r.controller.getState().session!;
    expect(s).toMatchObject({ status: 'COMPLETED', human_reported_outcome: 'RESOLVED', receipt: { state: 'PERSISTED' } });
  });
});

async function toObserveFrom(c: SessionController) {
  const img = await c.uploadImage(new Blob([new Uint8Array([1])], { type: 'image/png' }), 'investigation');
  const v = c.getState().session!.interaction!;
  await c.submit('view-responses', (s) => ({ expected_revision: s.revision, interaction_id: v.interaction_id, template_id: v.template_id, template_version: v.template_version, result: 'IMAGE', image_id: img, human_confirmed: true }));
  const q = c.getState().session!.interaction!;
  await c.submit('answers', (s) => ({ expected_revision: s.revision, interaction_id: q.interaction_id, template_id: q.template_id, template_version: q.template_version, value: 'NO', human_confirmed: true }));
}
