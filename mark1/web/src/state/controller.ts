import { ApiClient, ApiError, NetworkError } from '../api/client';
import { CommandKeys, withRetry } from '../api/commands';
import {
  REFRESH_INTERVAL_MS,
  TERMINAL_STATUSES,
  type HazardCode,
  type ImagePurpose,
  type Session,
  type SessionEvent,
  type SessionOp,
  type StopReason,
} from '../api/types';
import { guidanceHiddenReason, guidanceKey, sessionLeaseDeadline, type HideReason } from './lease';

export type PendingPhase = 'SENDING' | 'RETRYING' | 'UNCONFIRMED' | 'RECORD_PENDING';

export interface PendingCommand {
  op: SessionOp | 'images' | 'create';
  key: string;
  phase: PendingPhase;
  commandId: string | null;
}

export interface SentMessage {
  localId: number;
  text: string;
  channel: 'CHAT' | 'VOICE_TRANSCRIPT';
  saved: boolean | 'FAILED';
}

export type StopPhase = 'IDLE' | 'SENDING' | 'WAITING_FOR_CONNECTION' | 'ACKNOWLEDGED';

export interface ControllerState {
  session: Session | null;
  receivedAtMs: number;
  online: boolean;
  visible: boolean;
  lastRefreshOk: boolean;
  locallyStopped: boolean;
  stopPhase: StopPhase;
  pending: PendingCommand | null;
  notice: string | null;
  messages: SentMessage[];
  events: SessionEvent[] | null;
}

export interface ControllerDeps {
  api: ApiClient;
  now?: () => number;
  setTimer?: (fn: () => void, ms: number) => unknown;
  clearTimer?: (h: unknown) => void;
  sleep?: (ms: number) => Promise<void>;
  /** Called whenever visible guidance must stop (speech cancel, camera stop). */
  onInvalidate?: (reason: HideReason | 'CONTEXT_CHANGED') => void;
}

const USER_ERRORS: Record<number, string> = {
  401: 'Your sign-in has ended. Sign in again to continue.',
  403: 'You are not authorized for this session or step.',
  404: 'This session or item is not available.',
  409: 'This step changed or is no longer available. Showing the current state.',
  413: 'That image is too large (max 10 MiB).',
  415: 'Only JPEG or PNG images can be sent.',
  422: 'That input was not accepted.',
  429: 'The attempt limit was reached for this step.',
  503: 'The service is temporarily unavailable.',
};

export function userMessageFor(e: unknown): string {
  if (e instanceof ApiError) return USER_ERRORS[e.status] ?? 'The request was not accepted.';
  if (e instanceof NetworkError) return 'Connection problem. The result is not confirmed.';
  return 'Something went wrong.';
}

/**
 * Client session controller (no React). Owns freshness, polling, command keys, retries and local
 * stop. It renders only what A's API returns; it never infers readiness or applies policy.
 */
export class SessionController {
  private state: ControllerState = {
    session: null,
    receivedAtMs: 0,
    online: typeof navigator === 'undefined' ? true : navigator.onLine !== false,
    visible: typeof document === 'undefined' ? true : document.visibilityState !== 'hidden',
    lastRefreshOk: false,
    locallyStopped: false,
    stopPhase: 'IDLE',
    pending: null,
    notice: null,
    messages: [],
    events: null,
  };
  private listeners = new Set<() => void>();
  private keys = new CommandKeys();
  private pollHandle: unknown = null;
  private leaseHandle: unknown = null;
  private refreshing: Promise<void> | null = null;
  private lastGuidanceKey: string | null = null;
  private unconfirmed: { op: SessionOp; body: object; key: string } | null = null;
  private stopRequest: { op: 'stop' | 'hazards'; body: Record<string, unknown>; key: string } | null = null;
  private msgSeq = 0;
  private inFlight = false;
  private disposed = false;
  readonly now: () => number;
  private readonly setTimer: (fn: () => void, ms: number) => unknown;
  private readonly clearTimer: (h: unknown) => void;

  constructor(private readonly deps: ControllerDeps) {
    this.now = deps.now ?? (() => Date.now());
    this.setTimer = deps.setTimer ?? ((fn, ms) => setTimeout(fn, ms));
    this.clearTimer = deps.clearTimer ?? ((h) => clearTimeout(h as ReturnType<typeof setTimeout>));
  }

  // ---------- store ----------
  getState = (): ControllerState => this.state;
  subscribe = (fn: () => void): (() => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  private set(patch: Partial<ControllerState>) {
    this.state = { ...this.state, ...patch };
    const key = guidanceKey(this.state.session);
    if (key !== this.lastGuidanceKey) {
      if (this.lastGuidanceKey !== null) this.deps.onInvalidate?.('CONTEXT_CHANGED');
      this.lastGuidanceKey = key;
    }
    this.listeners.forEach((l) => l());
  }

  /** Why actionable guidance must be hidden right now (null = may show). */
  hiddenReason(nowMs = this.now()): HideReason | null {
    const s = this.state;
    return guidanceHiddenReason({
      online: s.online,
      visible: s.visible,
      locallyStopped: s.locallyStopped,
      lastRefreshOk: s.lastRefreshOk,
      nowMs,
      deadlineMs: s.session ? sessionLeaseDeadline(s.session, s.receivedAtMs) : null,
    });
  }

  get isTerminal(): boolean {
    return !!this.state.session && TERMINAL_STATUSES.includes(this.state.session.status);
  }

  // ---------- lifecycle ----------
  async start(symptomText?: string): Promise<void> {
    const body = { workflow_id: 'demo-laptop-no-power', symptom_code: 'NO_POWER' as const, ...(symptomText ? { symptom_text: symptomText.slice(0, 1000) } : {}) };
    const key = this.keys.keyFor('create', 'create', body);
    this.set({ pending: { op: 'create', key, phase: 'SENDING', commandId: null }, notice: null });
    try {
      const r = await withRetry(() => this.deps.api.createSession(body, key), {
        sleep: this.deps.sleep,
        onRetry: () => this.set({ pending: { op: 'create', key, phase: 'RETRYING', commandId: null } }),
      });
      this.keys.clear();
      this.accept(r.data);
      this.set({ pending: null });
      this.schedulePoll();
    } catch (e) {
      this.set({ pending: null, notice: userMessageFor(e) });
    }
  }

  /** Resume an existing session id (e.g. after reload); always fetches current state first. */
  async resume(sessionId: string): Promise<void> {
    this.set({ session: { session_id: sessionId } as Session, lastRefreshOk: false });
    await this.refresh();
    this.schedulePoll();
  }

  dispose(): void {
    this.disposed = true;
    this.clearTimer(this.pollHandle);
    this.clearTimer(this.leaseHandle);
    this.listeners.clear();
  }

  setOnline(online: boolean): void {
    if (online === this.state.online) return;
    if (!online) {
      this.deps.onInvalidate?.('OFFLINE');
      this.set({ online: false, lastRefreshOk: false });
      return;
    }
    this.set({ online: true });
    void this.reconcileAfterReconnect();
  }

  setVisible(visible: boolean): void {
    if (visible === this.state.visible) return;
    if (!visible) {
      this.deps.onInvalidate?.('HIDDEN');
      this.set({ visible: false, lastRefreshOk: false });
      return;
    }
    // Refresh on focus before restoring guidance.
    this.set({ visible: true, lastRefreshOk: false });
    void this.refresh().then(() => this.schedulePoll());
  }

  private async reconcileAfterReconnect() {
    if (this.stopRequest && this.state.stopPhase !== 'ACKNOWLEDGED') await this.sendStop();
    await this.refresh();
    if (this.unconfirmed && !this.state.locallyStopped) {
      const u = this.unconfirmed;
      await this.runCommand(u.op, u.body, u.key);
    }
    this.schedulePoll();
  }

  // ---------- refresh / polling ----------
  refresh(): Promise<void> {
    const sid = this.state.session?.session_id;
    if (!sid) return Promise.resolve();
    if (this.refreshing) return this.refreshing;
    this.refreshing = (async () => {
      try {
        const s = await this.deps.api.getSession(sid);
        this.accept(s);
        await this.reconcilePendingReceipt();
      } catch (e) {
        if (e instanceof NetworkError || (e instanceof ApiError && e.status >= 500)) {
          if (this.state.lastRefreshOk) this.deps.onInvalidate?.('REFRESH_FAILED');
          this.set({ lastRefreshOk: false });
        } else if (!this.state.session?.status && e instanceof ApiError && (e.status === 404 || e.status === 403)) {
          // Resume of a session that does not exist / is not ours: back to start, nothing shown.
          this.set({ session: null, lastRefreshOk: false, notice: 'That session is not available. Start a new one.' });
        } else {
          this.deps.onInvalidate?.('REFRESH_FAILED');
          this.set({ lastRefreshOk: false, notice: userMessageFor(e) });
        }
      } finally {
        this.refreshing = null;
      }
    })();
    return this.refreshing;
  }

  private accept(s: Session) {
    const prev = this.state.session;
    if (prev && prev.session_id === s.session_id && s.revision !== prev.revision) this.keys.clear();
    this.set({ session: s, receivedAtMs: this.now(), lastRefreshOk: true });
    this.scheduleLeaseCheck();
  }

  private schedulePoll() {
    this.clearTimer(this.pollHandle);
    if (this.disposed || !this.state.session || this.isTerminal) return;
    if (!this.state.visible || !this.state.online) return;
    const st = this.state.session.status;
    const fast = st === 'EVALUATING' || st === 'RECORD_PENDING' || this.state.pending?.phase === 'RECORD_PENDING';
    this.pollHandle = this.setTimer(() => {
      void this.refresh().then(() => this.schedulePoll());
    }, fast ? 1000 : REFRESH_INTERVAL_MS);
  }

  /** When the lease lapses, notify (hide + cancel speech) and re-check immediately. */
  private scheduleLeaseCheck() {
    this.clearTimer(this.leaseHandle);
    const s = this.state.session;
    if (!s) return;
    const deadline = sessionLeaseDeadline(s, this.state.receivedAtMs);
    if (deadline === null) return;
    const ms = Math.max(0, deadline - this.now());
    this.leaseHandle = this.setTimer(() => {
      if (this.disposed) return;
      this.deps.onInvalidate?.('EXPIRED');
      this.listeners.forEach((l) => l());
      void this.refresh();
    }, ms + 5);
  }

  private async reconcilePendingReceipt() {
    const p = this.state.pending;
    const s = this.state.session;
    if (!p || p.phase !== 'RECORD_PENDING' || !p.commandId || !s) return;
    try {
      const r = await this.deps.api.getCommand(s.session_id, p.commandId);
      if (r.state === 'PERSISTED') {
        this.set({ pending: null, notice: 'Saved.' });
        await this.loadEventsIfTerminal();
      }
    } catch {
      /* keep pending; never claim saved */
    }
  }

  // ---------- commands ----------
  /**
   * Submit a human command. Fetches current state first; aborts if the visible guidance changed.
   * The same intent (op + identical payload) always uses the same Idempotency-Key.
   */
  async submit(op: SessionOp, build: (s: Session) => object, guard?: (s: Session) => boolean): Promise<boolean> {
    if (this.state.locallyStopped || this.state.pending || this.inFlight) return false;
    this.inFlight = true; // synchronous lock: a double tap cannot pass before pending is set
    try {
      return await this.submitLocked(op, build, guard);
    } finally {
      this.inFlight = false;
    }
  }

  private async submitLocked(op: SessionOp, build: (s: Session) => object, guard?: (s: Session) => boolean): Promise<boolean> {
    const before = guidanceKey(this.state.session);
    await this.refresh();
    const s = this.state.session;
    if (!s || !this.state.lastRefreshOk) {
      this.set({ notice: 'Could not confirm the current state. Nothing was sent.' });
      return false;
    }
    if (guidanceKey(s) !== before || (guard && !guard(s))) {
      this.set({ notice: 'This step changed before it was sent. Review the current step.' });
      return false;
    }
    const body = build(s);
    const key = this.keys.keyFor(s.session_id, op, body);
    return this.runCommand(op, body, key);
  }

  private async runCommand(op: SessionOp, body: object, key: string): Promise<boolean> {
    const s = this.state.session!;
    this.set({ pending: { op, key, phase: 'SENDING', commandId: null }, notice: null });
    try {
      const r = await withRetry(() => this.deps.api.command(s.session_id, op, body, key), {
        sleep: this.deps.sleep,
        shouldContinue: () => !this.state.locallyStopped,
        onRetry: () => this.set({ pending: { op, key, phase: 'RETRYING', commandId: null } }),
      });
      this.unconfirmed = null;
      this.accept(r.data);
      if (r.commandState === 'PENDING' || r.data.status === 'RECORD_PENDING') {
        this.set({ pending: { op, key, phase: 'RECORD_PENDING', commandId: r.commandId } });
      } else {
        this.set({ pending: null });
      }
      await this.loadEventsIfTerminal();
      this.schedulePoll();
      return true;
    } catch (e) {
      if (e instanceof NetworkError || (e instanceof ApiError && e.status === 503)) {
        // Unknown outcome: keep key+payload in memory to reconcile; never show as saved.
        this.unconfirmed = { op, body, key };
        this.set({ pending: { op, key, phase: 'UNCONFIRMED', commandId: null }, notice: userMessageFor(e) });
        return false;
      }
      this.unconfirmed = null;
      this.set({ pending: null, notice: userMessageFor(e) });
      if (e instanceof ApiError && e.status === 409) await this.refresh();
      return false;
    }
  }

  /** Manual retry for an unconfirmed command: exact same key and payload. */
  async retryUnconfirmed(): Promise<void> {
    if (!this.unconfirmed || this.state.locallyStopped) return;
    const u = this.unconfirmed;
    this.set({ pending: null });
    await this.runCommand(u.op, u.body, u.key);
  }

  async sendMessage(text: string, channel: 'CHAT' | 'VOICE_TRANSCRIPT'): Promise<boolean> {
    const trimmed = text.trim();
    if (!trimmed || trimmed.length > 2000) return false;
    const localId = ++this.msgSeq;
    this.set({ messages: [...this.state.messages, { localId, text: trimmed, channel, saved: false }] });
    const ok = await this.submit('messages', (s) => ({ expected_revision: s.revision, text: trimmed, channel, human_confirmed: true }));
    this.set({ messages: this.state.messages.map((m) => (m.localId === localId ? { ...m, saved: ok ? true : 'FAILED' } : m)) });
    return ok;
  }

  /** Upload a user-selected frame; returns image_id. Does not advance the investigation. */
  async uploadImage(blob: Blob, purpose: ImagePurpose): Promise<string | null> {
    if (this.state.locallyStopped || this.state.pending || this.inFlight) return null;
    this.inFlight = true;
    try {
      return await this.uploadLocked(blob, purpose);
    } finally {
      this.inFlight = false;
    }
  }

  private async uploadLocked(blob: Blob, purpose: ImagePurpose): Promise<string | null> {
    await this.refresh();
    const s = this.state.session;
    if (!s || !this.state.lastRefreshOk) {
      this.set({ notice: 'Could not confirm the current state. Nothing was sent.' });
      return null;
    }
    const key = this.keys.keyFor(s.session_id, 'images', { purpose, rev: s.revision, size: blob.size, type: blob.type });
    this.set({ pending: { op: 'images', key, phase: 'SENDING', commandId: null }, notice: null });
    try {
      const r = await withRetry(() => this.deps.api.uploadImage(s.session_id, blob, purpose, s.revision, key), {
        sleep: this.deps.sleep,
        shouldContinue: () => !this.state.locallyStopped,
      });
      this.set({ pending: null });
      await this.refresh(); // upload increments revision; follow with current-revision response
      return r.data.image_id;
    } catch (e) {
      this.set({ pending: null, notice: userMessageFor(e) });
      return null;
    }
  }

  // ---------- stop / hazard (local first, never blocked by pending) ----------
  stop(reason: StopReason = 'USER_STOP'): Promise<void> {
    return this.localStop('stop', { reason_code: reason });
  }

  reportHazard(code: HazardCode): Promise<void> {
    return this.localStop('hazards', { hazard_code: code });
  }

  private async localStop(op: 'stop' | 'hazards', payload: Record<string, unknown>) {
    if (!this.state.session || this.isTerminal) return;
    this.deps.onInvalidate?.('STOPPED');
    if (!this.stopRequest) {
      const body = { expected_revision: this.state.session.revision, ...payload };
      this.stopRequest = { op, body, key: this.keys.keyFor(this.state.session.session_id, op, body) };
    }
    this.set({ locallyStopped: true, stopPhase: 'SENDING' });
    await this.sendStop();
  }

  private async sendStop() {
    const sr = this.stopRequest;
    const s = this.state.session;
    if (!sr || !s) return;
    if (!this.state.online) {
      this.set({ stopPhase: 'WAITING_FOR_CONNECTION' });
      return;
    }
    this.set({ stopPhase: 'SENDING' });
    try {
      const r = await withRetry(() => this.deps.api.command(s.session_id, sr.op, sr.body, sr.key), {
        attempts: 6,
        sleep: this.deps.sleep,
      });
      this.unconfirmed = null;
      this.accept(r.data);
      this.set({ stopPhase: 'ACKNOWLEDGED', pending: null });
      await this.loadEventsIfTerminal();
    } catch (e) {
      if (e instanceof NetworkError || (e instanceof ApiError && e.status >= 500)) {
        this.set({ stopPhase: 'WAITING_FOR_CONNECTION' });
        return;
      }
      // Terminal already (e.g. 409): state is authoritative; local stop remains.
      await this.refresh();
      this.set({ stopPhase: this.isTerminal ? 'ACKNOWLEDGED' : 'WAITING_FOR_CONNECTION' });
    }
  }

  /** Retry a stop that is waiting for connectivity (same key/payload). */
  retryStop(): Promise<void> {
    return this.sendStop();
  }

  // ---------- history ----------
  async loadEvents(): Promise<void> {
    const sid = this.state.session?.session_id;
    if (!sid) return;
    try {
      const all: SessionEvent[] = [];
      let cursor: string | undefined;
      for (let i = 0; i < 20; i++) {
        const page = await this.deps.api.getEvents(sid, cursor);
        all.push(...page.events);
        if (!page.next_cursor) break;
        cursor = page.next_cursor;
      }
      this.set({ events: all });
    } catch {
      /* history is optional */
    }
  }

  private async loadEventsIfTerminal() {
    if (this.isTerminal) await this.loadEvents();
  }

  clearNotice(): void {
    this.set({ notice: null });
  }
}
