import examples from '@contracts/examples.json';
import { describe, expect, it, vi } from 'vitest';
import { checkDiagram } from '../src/api/diagram';
import { CommandKeys, stableStringify, withRetry } from '../src/api/commands';
import { ApiError, NetworkError } from '../src/api/client';
import { guidanceHiddenReason, leaseDeadline } from '../src/state/lease';
import type { Diagram, ExplanationInteraction } from '../src/api/types';

const ex = (examples as unknown as { explanation_session: { interaction: ExplanationInteraction } }).explanation_session.interaction;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

describe('diagram guard', () => {
  it('accepts the canonical fixture diagram', () => {
    expect(checkDiagram(ex.diagram, ex.highlights).ok).toBe(true);
  });
  it.each([
    ['dangling edge', (d: Diagram) => (d.edges[0].to_node_id = 'NOPE')],
    ['non-integer coordinate', (d: Diagram) => (d.nodes[0].x = 10.5)],
    ['out of range', (d: Diagram) => (d.nodes[0].y = 1001)],
    ['duplicate node', (d: Diagram) => d.nodes.push({ ...d.nodes[0] })],
    ['no nodes', (d: Diagram) => (d.nodes = [])],
    ['missing source', (d: Diagram) => (d.source = undefined as never)],
  ])('rejects %s', (_n, mutate) => {
    const d = clone(ex.diagram!);
    mutate(d);
    expect(checkDiagram(d, []).ok).toBe(false);
  });
  it('rejects highlights on unknown nodes or without evidence, and highlights without diagram', () => {
    expect(checkDiagram(ex.diagram, [{ node_id: 'GPU', label: 'SUSPECTED', evidence_ids: ['e'] }]).ok).toBe(false);
    expect(checkDiagram(ex.diagram, [{ node_id: 'INPUT', label: 'SUSPECTED', evidence_ids: [] }]).ok).toBe(false);
    expect(checkDiagram(null, ex.highlights).ok).toBe(false);
  });
});

describe('lease', () => {
  const item = (granted: number) => ({ policy_checked_at: '2026-11-10T12:00:00Z', guidance_valid_until: new Date(Date.parse('2026-11-10T12:00:00Z') + granted).toISOString() });
  it('measures from local receipt and caps at 15 s', () => {
    expect(leaseDeadline(item(15_000), 1000)).toBe(16_000);
    expect(leaseDeadline(item(60_000), 1000)).toBe(16_000);
    expect(leaseDeadline(item(5_000), 1000)).toBe(6_000);
  });
  it('malformed/non-positive lease never shows', () => {
    expect(leaseDeadline(item(0), 1000)).toBe(0);
    expect(leaseDeadline({ policy_checked_at: 'x', guidance_valid_until: 'y' }, 1000)).toBe(0);
  });
  it('hide reasons have priority stop > offline > hidden > refresh > expiry', () => {
    const g = { online: true, visible: true, locallyStopped: false, lastRefreshOk: true, nowMs: 0, deadlineMs: 10 };
    expect(guidanceHiddenReason(g)).toBeNull();
    expect(guidanceHiddenReason({ ...g, nowMs: 10 })).toBe('EXPIRED');
    expect(guidanceHiddenReason({ ...g, deadlineMs: null })).toBe('EXPIRED');
    expect(guidanceHiddenReason({ ...g, lastRefreshOk: false })).toBe('REFRESH_FAILED');
    expect(guidanceHiddenReason({ ...g, visible: false, lastRefreshOk: false })).toBe('HIDDEN');
    expect(guidanceHiddenReason({ ...g, online: false, visible: false })).toBe('OFFLINE');
    expect(guidanceHiddenReason({ ...g, online: false, locallyStopped: true })).toBe('STOPPED');
  });
});

describe('command keys and retry', () => {
  it('stable key for identical payload regardless of key order; new key for changed payload', () => {
    const k = new CommandKeys();
    const a = k.keyFor('s', 'answers', { value: 'NO', expected_revision: 7 });
    expect(k.keyFor('s', 'answers', { expected_revision: 7, value: 'NO' })).toBe(a);
    expect(k.keyFor('s', 'answers', { expected_revision: 7, value: 'YES' })).not.toBe(a);
    expect(stableStringify({ b: 1, a: [2, { d: 1, c: 0 }] })).toBe('{"a":[2,{"c":0,"d":1}],"b":1}');
  });
  it('retries network loss and retryable 503, never 409', async () => {
    const sleep = () => Promise.resolve();
    const f = vi.fn().mockRejectedValueOnce(new NetworkError()).mockRejectedValueOnce(new ApiError(503, { code: 'X', message: 'm', request_id: 'r', retryable: true })).mockResolvedValue('ok');
    await expect(withRetry(f, { sleep })).resolves.toBe('ok');
    expect(f).toHaveBeenCalledTimes(3);
    const g = vi.fn().mockRejectedValue(new ApiError(409, null));
    await expect(withRetry(g, { sleep })).rejects.toBeInstanceOf(ApiError);
    expect(g).toHaveBeenCalledTimes(1);
  });
  it('stops retrying when told to (local stop)', async () => {
    const f = vi.fn().mockRejectedValue(new NetworkError());
    let go = true;
    await expect(withRetry(f, { sleep: async () => void (go = false), shouldContinue: () => go })).rejects.toBeInstanceOf(NetworkError);
    expect(f).toHaveBeenCalledTimes(1);
  });
});
