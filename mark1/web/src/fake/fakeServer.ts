/**
 * In-browser FAKE backend for J's UI development and tests (spec 02: "J uses A's all-state
 * fixtures"). It is a UI test double, NOT A's engine stub, NOT a production engine/catalog,
 * and it makes no policy decisions that the real client relies on.
 *
 * Content (check/template text, diagram, sources) is read from A's canonical synthetic catalog in
 * contracts/request-fixtures.json so nothing is hand-copied. Leases, revisions, command receipts
 * and hashes are freshly issued, as contracts/README.md requires of any stub.
 */
import requestFixtures from '@contracts/request-fixtures.json';
import errorFixtures from '@contracts/all-fixtures.json';
import { NetworkError, type Transport, type TransportRequest, type TransportResponse } from '../api/client';
import { stableStringify } from '../api/commands';
import {
  IMAGE_MAX_BYTES,
  MAX_LEASE_MS,
  TERMINAL_STATUSES,
  type Check,
  type Diagram,
  type EventPage,
  type IdentityCandidate,
  type Interaction,
  type Receipt,
  type Session,
  type SessionEvent,
  type Status,
} from '../api/types';

// ---------- canonical synthetic catalog (A-owned fixture) ----------
interface CatSource { source_id: string; version: string; locator: string }
interface CatCheck { check_id: string; version: string; kind: string; instruction: string; safety_notice: string; stop_conditions: string[]; observation_code: string; options: string[]; stop_values: string[]; source: CatSource; model_id: string; configuration_id: string }
interface CatView { template_id: string; version: string; text: string; purpose: 'IDENTITY' | 'INVESTIGATION'; target_node_id: string | null; safety_notice: string; stop_conditions: string[]; source: CatSource }
interface CatQuestion { template_id: string; version: string; text: string; options: string[]; safety_notice: string; stop_conditions: string[]; source: CatSource }
interface CatExplanation { template_id: string; version: string; text: string; safety_notice: string; stop_conditions: string[]; source: CatSource; claim_rule: { check_id: string; allowed_values: string[] }; diagram_id: string; diagram_version: string; allowed_highlight_node_ids: string[] }
interface CatDiagram { diagram_id: string; version: string; title: string; nodes: Diagram['nodes']; edges: Diagram['edges']; source: CatSource }
interface Catalog { checks: CatCheck[]; view_templates: CatView[]; question_templates: CatQuestion[]; explanation_templates: CatExplanation[]; diagrams: CatDiagram[] }

const CATALOG = (requestFixtures as unknown as { identify_request: { approved_catalog: Catalog } }).identify_request.approved_catalog;
const ERRORS = (errorFixtures as unknown as { errors: Record<string, { code: string; message: string; retryable: boolean }> }).errors;
const WORKFLOW_ID = 'demo-laptop-no-power';
const src = (s: CatSource) => ({ source_id: s.source_id, version: s.version, locator: s.locator });
const byKind = (k: string) => CATALOG.checks.find((c) => c.kind === k)!;
const viewByPurpose = (p: 'IDENTITY' | 'INVESTIGATION') => CATALOG.view_templates.find((v) => v.purpose === p)!;
const SUPPORTED = { model_id: byKind('PREFLIGHT').model_id, configuration_id: byKind('PREFLIGHT').configuration_id };

export type FakeScenario = 'visual-investigation' | 'unreadable-label' | 'diagram-unavailable';
export const FAKE_SCENARIOS: { id: FakeScenario; label: string }[] = [
  { id: 'visual-investigation', label: 'Visual investigation (main path)' },
  { id: 'unreadable-label', label: 'Unreadable label (identity view first)' },
  { id: 'diagram-unavailable', label: 'Diagram unavailable (text-only explanation)' },
];

export interface FakeFaults {
  /** Apply the next mutation but lose its response (client must retry with same key). */
  dropNextResponse: boolean;
  /** Next request fails with retryable 503 without effect. */
  fail503Next: boolean;
  /** All requests fail as if the network were down. */
  offline: boolean;
  /** Stop renewing leases (client must hide guidance when it lapses). */
  freezeLeases: boolean;
  /** Observations stay RECORD_PENDING this long before persisting. */
  pendingWriteMs: number;
  /** Time spent in EVALUATING. */
  evaluatingMs: number;
  /** Artificial latency per request. */
  latencyMs: number;
}

export const DEFAULT_FAULTS: FakeFaults = {
  dropNextResponse: false,
  fail503Next: false,
  offline: false,
  freezeLeases: false,
  pendingWriteMs: 0,
  evaluatingMs: 900,
  latencyMs: 120,
};

type DistOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;
type StoredInteraction = DistOmit<Interaction, 'policy_checked_at' | 'guidance_valid_until'>;
type StoredCheck = Omit<Check, 'policy_checked_at' | 'guidance_valid_until'>;

interface Evidence {
  preflight?: string;
  overview?: string;
  overviewAttempts: number;
  question?: string;
  indicator?: string;
  ack?: boolean;
  identityViewDone?: boolean;
}

interface FakeSession {
  id: string;
  revision: number;
  status: Status;
  identity: Session['identity'];
  candidates: IdentityCandidate[];
  check: StoredCheck | null;
  interaction: StoredInteraction | null;
  receipt: Receipt | null;
  outcome: Session['human_reported_outcome'];
  reason: string | null;
  ev: Evidence;
  images: Map<string, string>; // image_id -> purpose
  events: SessionEvent[];
  leaseIssuedAt: number;
  timer?: ReturnType<typeof setTimeout>;
  seq: number;
  checkObservations: number;
}

interface StoredCommand {
  sessionId?: string;
  payloadHash: string;
  status: number;
  commandId: string;
  state: 'PENDING' | 'PERSISTED';
  imageReceipt?: unknown;
}

const ALLOWED_FIELDS: Record<string, string[]> = {
  sessions: ['workflow_id', 'symptom_code', 'symptom_text'],
  'identity-candidates': ['expected_revision', 'image_id', 'manual_label'],
  'identity-confirmation': ['expected_revision', 'model_id', 'configuration_id', 'serial', 'human_confirmed'],
  observations: ['expected_revision', 'check_id', 'check_version', 'observation_code', 'value', 'image_id', 'human_confirmed'],
  outcome: ['expected_revision', 'human_reported_outcome', 'human_confirmed'],
  stop: ['expected_revision', 'reason_code'],
  hazards: ['expected_revision', 'hazard_code'],
  'view-responses': ['expected_revision', 'interaction_id', 'template_id', 'template_version', 'result', 'image_id', 'human_confirmed'],
  answers: ['expected_revision', 'interaction_id', 'template_id', 'template_version', 'value', 'human_confirmed'],
  messages: ['expected_revision', 'text', 'channel', 'human_confirmed'],
  'explanation-acks': ['expected_revision', 'interaction_id', 'template_id', 'template_version', 'acknowledged'],
};

const MESSAGE_STATES: Status[] = ['AWAITING_IDENTITY', 'EVALUATING', 'AWAITING_VIEW', 'AWAITING_ANSWER', 'EXPLAINING', 'READY'];
const OUTCOME_STATES: Status[] = ['READY', 'EVALUATING', 'AWAITING_VIEW', 'AWAITING_ANSWER', 'EXPLAINING'];

class HttpFail extends Error {
  constructor(readonly status: number, readonly currentRevision?: number) {
    super(String(status));
  }
}

export class FakeServer implements Transport {
  scenario: FakeScenario;
  faults: FakeFaults;
  private sessions = new Map<string, FakeSession>();
  private commands = new Map<string, StoredCommand>();
  private nextId = 1;
  readonly now: () => number;

  constructor(opts: { scenario?: FakeScenario; faults?: Partial<FakeFaults>; now?: () => number } = {}) {
    this.scenario = opts.scenario ?? 'visual-investigation';
    this.faults = { ...DEFAULT_FAULTS, ...opts.faults };
    this.now = opts.now ?? (() => Date.now());
  }

  reset(): void {
    for (const s of this.sessions.values()) clearTimeout(s.timer);
    this.sessions.clear();
    this.commands.clear();
  }

  // ---------------- Transport ----------------
  async send(req: TransportRequest): Promise<TransportResponse> {
    if (this.faults.latencyMs > 0) await new Promise((r) => setTimeout(r, this.faults.latencyMs));
    if (this.faults.offline) throw new NetworkError('fake offline');
    if (this.faults.fail503Next) {
      this.faults.fail503Next = false;
      return this.errorResponse(503);
    }
    let res: TransportResponse;
    try {
      res = await this.route(req);
    } catch (e) {
      if (e instanceof HttpFail) return this.errorResponse(e.status, e.currentRevision);
      throw e;
    }
    if (req.method === 'POST' && this.faults.dropNextResponse) {
      this.faults.dropNextResponse = false;
      throw new NetworkError('fake: response lost after effect applied');
    }
    return res;
  }

  private errorResponse(status: number, currentRevision?: number): TransportResponse {
    const e = ERRORS[String(status)] ?? { code: 'ERROR', message: 'Synthetic user-safe example.', retryable: false };
    const body: Record<string, unknown> = { ...e, request_id: `fake-req-${this.nextId++}` };
    if (currentRevision !== undefined) body.current_revision = currentRevision;
    return { status, headers: {}, body };
  }

  private async route(req: TransportRequest): Promise<TransportResponse> {
    const url = new URL(req.path, 'http://fake.invalid');
    const parts = url.pathname.split('/').filter(Boolean); // v2 sessions {id} {op} {sub}
    if (parts[0] !== 'v2' || parts[1] !== 'sessions') throw new HttpFail(404);
    const key = req.headers['Idempotency-Key'];

    if (parts.length === 2) {
      if (req.method !== 'POST') throw new HttpFail(404);
      return this.idempotent('create', 'sessions', key, req.json, () => this.create(req.json as Record<string, unknown>));
    }
    const s = this.sessions.get(decodeURIComponent(parts[2]));
    if (!s) throw new HttpFail(404);
    if (parts.length === 3 && req.method === 'GET') return this.ok(200, this.view(s));
    const op = parts[3];
    if (req.method === 'GET') {
      if (op === 'events') return this.ok(200, { events: s.events, next_cursor: null } satisfies EventPage);
      if (op === 'commands' && parts[4]) {
        const c = [...this.commands.values()].find((x) => x.commandId === decodeURIComponent(parts[4]));
        if (!c) throw new HttpFail(404);
        return this.ok(200, { command_id: c.commandId, state: c.state, record_id: c.state === 'PERSISTED' ? `record-${c.commandId}` : null });
      }
      throw new HttpFail(404);
    }
    if (op === 'images') return this.uploadImage(s, key, req.form);
    if (!(op in ALLOWED_FIELDS)) throw new HttpFail(404);
    return this.idempotent(s.id, op, key, req.json, () => this.mutate(s, op, req.json as Record<string, unknown>));
  }

  private ok(status: number, body: unknown, headers: Record<string, string> = {}): TransportResponse {
    return { status, headers, body };
  }

  /** Authenticate -> dedupe legitimate retry -> stale check (contract order). */
  private async idempotent(
    scope: string,
    op: string,
    key: string | undefined,
    body: unknown,
    apply: () => { status: number; session: FakeSession; state: 'PENDING' | 'PERSISTED' },
  ): Promise<TransportResponse> {
    if (!key) throw new HttpFail(422);
    const cmdKey = `${scope}|${op}|${key}`;
    const hash = stableStringify(body);
    const prior = this.commands.get(cmdKey);
    if (prior) {
      if (prior.payloadHash !== hash) throw new HttpFail(409);
      const s = prior.sessionId ? this.sessions.get(prior.sessionId) : undefined;
      if (!s) throw new HttpFail(404);
      return this.ok(prior.status, this.view(s), { 'x-command-id': prior.commandId, 'x-command-state': prior.state });
    }
    if (body === null || typeof body !== 'object' || Array.isArray(body)) throw new HttpFail(422);
    for (const f of Object.keys(body as object)) if (!ALLOWED_FIELDS[op].includes(f)) throw new HttpFail(422);
    const commandId = `cmd-${this.nextId++}`;
    this.pendingCommandId = commandId;
    const r = apply();
    const stored: StoredCommand = { sessionId: r.session.id, payloadHash: hash, status: r.status, commandId, state: r.state };
    this.commands.set(cmdKey, stored);
    return this.ok(r.status, this.view(r.session), { 'x-command-id': commandId, 'x-command-state': r.state });
  }

  private pendingCommandId = '';

  // ---------------- view with fresh leases ----------------
  private view(s: FakeSession): Session {
    const now = this.now();
    if (!this.faults.freezeLeases) s.leaseIssuedAt = now;
    const checked = new Date(s.leaseIssuedAt).toISOString();
    const until = new Date(s.leaseIssuedAt + MAX_LEASE_MS).toISOString();
    return {
      contract_version: '2.0',
      session_id: s.id,
      revision: s.revision,
      status: s.status,
      workflow_id: WORKFLOW_ID,
      identity: s.identity,
      identity_candidates: s.candidates,
      current_check: s.check ? { ...s.check, policy_checked_at: checked, guidance_valid_until: until } : null,
      receipt: s.receipt,
      human_reported_outcome: s.outcome,
      reason_code: s.reason,
      interaction: s.interaction ? ({ ...s.interaction, policy_checked_at: checked, guidance_valid_until: until } as Interaction) : null,
    };
  }

  // ---------------- commands ----------------
  private create(body: Record<string, unknown>) {
    if (body.workflow_id !== WORKFLOW_ID || body.symptom_code !== 'NO_POWER') throw new HttpFail(422);
    const id = `fake-session-${this.nextId++}`;
    const s: FakeSession = {
      id, revision: 0, status: 'AWAITING_IDENTITY', identity: null, candidates: [], check: null, interaction: null,
      receipt: null, outcome: null, reason: null, ev: { overviewAttempts: 0 }, images: new Map(), events: [],
      leaseIssuedAt: this.now(), seq: 0, checkObservations: 0,
    };
    this.sessions.set(id, s);
    this.event(s, 'SESSION_CREATED', `Symptom reported: NO_POWER${body.symptom_text ? ' (with description)' : ''}`);
    s.receipt = { command_id: this.pendingCommandId, state: 'PERSISTED', record_id: `record-${this.pendingCommandId}` };
    return { status: 201, session: s, state: 'PERSISTED' as const };
  }

  private mutate(s: FakeSession, op: string, b: Record<string, unknown>) {
    const terminal = TERMINAL_STATUSES.includes(s.status);
    const isStop = op === 'stop' || op === 'hazards';
    if (terminal) throw new HttpFail(409);
    if (s.status === 'RECORD_PENDING' && !isStop) throw new HttpFail(409);
    if (typeof b.expected_revision !== 'number') throw new HttpFail(422);
    if (!isStop && b.expected_revision !== s.revision) throw new HttpFail(409, s.revision);
    const cmd = this.pendingCommandId;
    const persisted = () => ({ command_id: cmd, state: 'PERSISTED' as const, record_id: `record-${cmd}` });

    switch (op) {
      case 'stop':
      case 'hazards': {
        if (op === 'stop' && !['USER_STOP', 'UNSUPPORTED', 'OTHER'].includes(String(b.reason_code))) throw new HttpFail(422);
        if (op === 'hazards' && !['DAMAGE', 'LIQUID', 'SWELLING', 'HEAT_OR_SMELL', 'UNSURE'].includes(String(b.hazard_code))) throw new HttpFail(422);
        this.event(s, op === 'stop' ? 'STOP_RECORDED' : 'HAZARD_REPORTED', op === 'stop' ? `Stop: ${b.reason_code}` : `Hazard reported: ${b.hazard_code}`);
        this.finish(s, 'ESCALATED', op === 'stop' ? String(b.reason_code) : `HAZARD_${b.hazard_code}`);
        s.receipt = persisted();
        return { status: 200, session: s, state: 'PERSISTED' as const };
      }
      case 'messages': {
        if (!MESSAGE_STATES.includes(s.status)) throw new HttpFail(409);
        const text = String(b.text ?? '');
        if (!text || text.length > 2000 || !['CHAT', 'VOICE_TRANSCRIPT'].includes(String(b.channel)) || b.human_confirmed !== true) throw new HttpFail(422);
        this.event(s, 'MESSAGE_RECORDED', `Human report (${b.channel === 'CHAT' ? 'chat' : 'voice transcript'}): ${text.slice(0, 160)}`);
        s.receipt = persisted();
        // Invalidate prior output; re-evaluate (IDENTIFY if unconfirmed, else INVESTIGATE).
        this.evaluate(s, () => (s.identity ? this.nextInvestigationStep(s, true) : this.identifyResult(s, 'keep')));
        return { status: 200, session: s, state: 'PERSISTED' as const };
      }
      case 'identity-candidates': {
        this.need(s, 'AWAITING_IDENTITY');
        const label = typeof b.manual_label === 'string' ? b.manual_label : undefined;
        const image = typeof b.image_id === 'string' ? b.image_id : undefined;
        if (!label && !image) throw new HttpFail(422);
        if (image && s.images.get(image) !== 'identity') throw new HttpFail(404);
        this.event(s, 'IDENTITY_INPUT_RECORDED', label ? `Manual label entered: ${label}` : 'Identity image submitted');
        s.receipt = persisted();
        this.evaluate(s, () => {
          if (image && this.scenario === 'unreadable-label' && !s.ev.identityViewDone) return this.serveIdentityView(s);
          return this.identifyResult(s, label ? { label } : { image: true });
        });
        return { status: 200, session: s, state: 'PERSISTED' as const };
      }
      case 'identity-confirmation': {
        this.need(s, 'AWAITING_IDENTITY');
        if (b.human_confirmed !== true) throw new HttpFail(422);
        if (b.model_id !== SUPPORTED.model_id || b.configuration_id !== SUPPORTED.configuration_id) throw new HttpFail(422);
        s.identity = { model_id: SUPPORTED.model_id, configuration_id: SUPPORTED.configuration_id, human_confirmed: true };
        s.candidates = [];
        this.event(s, 'IDENTITY_CONFIRMED', `Human confirmed ${SUPPORTED.model_id} / ${SUPPORTED.configuration_id} against physical label`);
        s.receipt = persisted();
        this.evaluate(s, () => this.nextInvestigationStep(s, false));
        return { status: 200, session: s, state: 'PERSISTED' as const };
      }
      case 'view-responses': {
        this.need(s, 'AWAITING_VIEW');
        const it = this.matchInteraction(s, b, 'VIEW');
        const result = String(b.result);
        if (!['IMAGE', 'UNAVAILABLE', 'UNSURE'].includes(result) || b.human_confirmed !== true) throw new HttpFail(422);
        if (result === 'IMAGE') {
          const purpose = (it as { purpose?: string }).purpose === 'IDENTITY' ? 'identity' : 'investigation';
          if (typeof b.image_id !== 'string' || s.images.get(b.image_id) !== purpose) throw new HttpFail(422);
        } else if (b.image_id !== null) throw new HttpFail(422);
        this.event(s, 'VIEW_RESPONSE_RECORDED', `View ${it.template_id}: ${result}`, [it.source]);
        s.receipt = persisted();
        if ((it as { purpose?: string }).purpose === 'IDENTITY') {
          s.ev.identityViewDone = true;
          this.evaluate(s, () => (result === 'IMAGE' ? this.identifyResult(s, { image: true }) : this.identifyResult(s, 'none')));
        } else {
          if (result === 'IMAGE') s.ev.overview = 'IMAGE';
          else s.ev.overviewAttempts += 1;
          this.evaluate(s, () => this.nextInvestigationStep(s, true));
        }
        return { status: 200, session: s, state: 'PERSISTED' as const };
      }
      case 'answers': {
        this.need(s, 'AWAITING_ANSWER');
        const it = this.matchInteraction(s, b, 'QUESTION');
        if (b.human_confirmed !== true || !(it as { options?: string[] }).options!.includes(String(b.value))) throw new HttpFail(422);
        s.ev.question = String(b.value);
        this.event(s, 'ANSWER_RECORDED', `Answer to ${it.template_id}: ${b.value}`, [it.source]);
        s.receipt = persisted();
        this.evaluate(s, () => this.nextInvestigationStep(s, false));
        return { status: 200, session: s, state: 'PERSISTED' as const };
      }
      case 'explanation-acks': {
        this.need(s, 'EXPLAINING');
        const it = this.matchInteraction(s, b, 'EXPLANATION');
        if (b.acknowledged !== true) throw new HttpFail(422);
        s.ev.ack = true;
        this.event(s, 'EXPLANATION_ACKNOWLEDGED', `Explanation ${it.template_id} acknowledged (not repair verification)`, [it.source]);
        s.receipt = persisted();
        this.evaluate(s, () => this.nextInvestigationStep(s, false));
        return { status: 200, session: s, state: 'PERSISTED' as const };
      }
      case 'observations': {
        this.need(s, 'READY');
        const c = s.check!;
        if (b.check_id !== c.check_id || b.check_version !== c.version || b.observation_code !== c.observation_code) throw new HttpFail(409);
        if (b.human_confirmed !== true || !c.options.includes(String(b.value))) throw new HttpFail(422);
        const value = String(b.value);
        const cat = CATALOG.checks.find((x) => x.check_id === c.check_id)!;
        const apply = () => {
          if (cat.kind === 'PREFLIGHT') s.ev.preflight = value;
          else {
            s.ev.indicator = value;
            s.checkObservations += 1;
          }
          this.event(s, 'OBSERVATION_RECORDED', `Human-confirmed ${c.observation_code} = ${value}`, [c.source]);
        };
        if (this.faults.pendingWriteMs > 0) {
          s.check = null;
          s.status = 'RECORD_PENDING';
          s.reason = 'EVIDENCE_PENDING';
          s.receipt = { command_id: cmd, state: 'PENDING', record_id: null };
          s.revision++;
          s.timer = setTimeout(() => {
            if (s.status !== 'RECORD_PENDING') return; // stop overrode the pending write
            apply();
            const stored = [...this.commands.values()].find((x) => x.commandId === cmd);
            if (stored) stored.state = 'PERSISTED';
            s.receipt = persisted();
            s.reason = null;
            this.evaluate(s, () => this.afterObservation(s, cat, value));
          }, this.faults.pendingWriteMs);
          return { status: 202, session: s, state: 'PENDING' as const };
        }
        apply();
        s.receipt = persisted();
        this.evaluate(s, () => this.afterObservation(s, cat, value));
        return { status: 200, session: s, state: 'PERSISTED' as const };
      }
      case 'outcome': {
        if (!OUTCOME_STATES.includes(s.status) || s.checkObservations < 1) throw new HttpFail(409);
        const o = String(b.human_reported_outcome);
        if (!['RESOLVED', 'UNRESOLVED'].includes(o) || b.human_confirmed !== true) throw new HttpFail(422);
        this.event(s, 'OUTCOME_REPORTED', `Human-reported outcome: ${o} (not a verified repair)`);
        s.outcome = o as 'RESOLVED' | 'UNRESOLVED';
        s.receipt = persisted();
        this.finish(s, o === 'RESOLVED' ? 'COMPLETED' : 'ESCALATED', o === 'RESOLVED' ? null : 'HUMAN_UNRESOLVED');
        return { status: 200, session: s, state: 'PERSISTED' as const };
      }
    }
    throw new HttpFail(404);
  }

  private uploadImage(s: FakeSession, key: string | undefined, form?: FormData): TransportResponse {
    if (!key || !form) throw new HttpFail(422);
    const file = form.get('file');
    const purpose = String(form.get('purpose') ?? '');
    const rev = Number(form.get('expected_revision'));
    const fileSig = file instanceof Blob ? `${file.size}:${file.type}` : 'none';
    const cmdKey = `${s.id}|images|${key}`;
    const hash = stableStringify({ purpose, rev, fileSig });
    const prior = this.commands.get(cmdKey);
    if (prior) {
      if (prior.payloadHash !== hash) throw new HttpFail(409);
      return this.ok(201, prior.imageReceipt, { 'x-command-id': prior.commandId, 'x-command-state': 'PERSISTED' });
    }
    if (!(file instanceof Blob)) throw new HttpFail(422);
    if (!['image/jpeg', 'image/png'].includes(file.type)) throw new HttpFail(415);
    if (file.size > IMAGE_MAX_BYTES) throw new HttpFail(413);
    if (!['AWAITING_IDENTITY', 'AWAITING_VIEW', 'READY'].includes(s.status)) throw new HttpFail(409);
    if (rev !== s.revision) throw new HttpFail(409, s.revision);
    const expected =
      s.status === 'AWAITING_IDENTITY' ? 'identity'
      : s.status === 'READY' ? 'observation'
      : (s.interaction as { purpose?: string })?.purpose === 'IDENTITY' ? 'identity' : 'investigation';
    if (purpose !== expected) throw new HttpFail(422);
    const imageId = `image-${this.nextId++}`;
    s.images.set(imageId, purpose);
    s.revision++; // preserves active interaction/check
    this.event(s, 'IMAGE_STORED', `Image received (${purpose}); not physical evidence`);
    const receipt = { image_id: imageId, session_id: s.id, revision: s.revision, status: 'STORED' };
    const commandId = `cmd-${this.nextId++}`;
    this.commands.set(cmdKey, { sessionId: s.id, payloadHash: hash, status: 201, commandId, state: 'PERSISTED', imageReceipt: receipt });
    return this.ok(201, receipt, { 'x-command-id': commandId, 'x-command-state': 'PERSISTED' });
  }

  // ---------------- fake engine/policy (synthetic only) ----------------
  private need(s: FakeSession, st: Status) {
    if (s.status !== st) throw new HttpFail(409);
  }

  private matchInteraction(s: FakeSession, b: Record<string, unknown>, kind: Interaction['kind']): StoredInteraction {
    const it = s.interaction;
    if (!it || it.kind !== kind || b.interaction_id !== it.interaction_id || b.template_id !== it.template_id || b.template_version !== it.template_version) throw new HttpFail(409);
    return it;
  }

  /** EVALUATING for a while, then commit the result if nothing superseded this run. */
  private evaluate(s: FakeSession, next: () => void) {
    clearTimeout(s.timer);
    s.status = 'EVALUATING';
    s.check = null;
    s.interaction = null;
    s.revision++;
    const run = ++s.seq;
    const done = () => {
      if (run !== s.seq || TERMINAL_STATUSES.includes(s.status)) return; // superseded or stopped
      const before = s.revision;
      next();
      if (s.revision === before) s.revision++;
    };
    if (this.faults.evaluatingMs <= 0) done();
    else s.timer = setTimeout(done, this.faults.evaluatingMs);
  }

  private finish(s: FakeSession, status: Status, reason: string | null) {
    clearTimeout(s.timer);
    s.seq++;
    s.status = status;
    s.check = null;
    s.interaction = null;
    s.candidates = [];
    s.reason = reason;
    s.revision++;
    if (status !== 'COMPLETED') this.event(s, 'SESSION_' + status, `Session ${status.toLowerCase()}${reason ? `: ${reason}` : ''}`);
  }

  private interactionId(s: FakeSession) {
    return `interaction-${s.id}-${this.nextId++}`;
  }

  private serveIdentityView(s: FakeSession) {
    const v = viewByPurpose('IDENTITY');
    s.status = 'AWAITING_VIEW';
    s.interaction = { kind: 'VIEW', interaction_id: this.interactionId(s), template_id: v.template_id, template_version: v.version, text: v.text, source: src(v.source), safety_notice: v.safety_notice, stop_conditions: v.stop_conditions, purpose: 'IDENTITY', target_node_id: null };
  }

  private identifyResult(s: FakeSession, input: { label?: string; image?: boolean } | 'none' | 'keep') {
    s.status = 'AWAITING_IDENTITY';
    if (input === 'keep') return;
    if (input === 'none') {
      s.candidates = [];
      s.reason = 'IDENTITY_UNREADABLE';
      return;
    }
    const norm = (input.label ?? '').trim().toUpperCase().replace(/\s+/g, ' ');
    const exact = input.image || norm === SUPPORTED.model_id || norm === `${SUPPORTED.model_id} / ${SUPPORTED.configuration_id}` || norm === `${SUPPORTED.model_id} ${SUPPORTED.configuration_id}`;
    if (!exact) {
      s.candidates = []; // exact matches only; never closest-valid guess
      s.reason = 'NO_SUPPORTED_MATCH';
      return;
    }
    s.reason = null;
    s.candidates = [{ ...SUPPORTED, label_excerpt: input.image ? `${SUPPORTED.model_id} ${SUPPORTED.configuration_id} (fake simulated read)` : (input.label ?? '').slice(0, 160), basis: input.image ? 'IMAGE' : 'MANUAL' }];
  }

  private serveCheck(s: FakeSession, c: CatCheck) {
    s.status = 'READY';
    s.check = { check_id: c.check_id, version: c.version, instruction: c.instruction, observation_code: c.observation_code, options: c.options, source: src(c.source), safety_notice: c.safety_notice, stop_conditions: c.stop_conditions };
  }

  private afterObservation(s: FakeSession, c: CatCheck, value: string) {
    if (c.stop_values.includes(value)) {
      this.finish(s, 'ESCALATED', c.kind === 'PREFLIGHT' ? 'PREFLIGHT_STOP' : 'UNSURE_OBSERVATION');
      return;
    }
    this.nextInvestigationStep(s, false);
  }

  /** Deterministic synthetic plan mirroring scenario-fixtures.json "visual-investigation". */
  private nextInvestigationStep(s: FakeSession, _reissue: boolean) {
    const ev = s.ev;
    if (ev.preflight === undefined) return this.serveCheck(s, byKind('PREFLIGHT'));
    if (ev.overview === undefined) {
      if (ev.overviewAttempts >= 3) {
        this.finish(s, 'ESCALATED', 'VIEW_ATTEMPTS_EXHAUSTED');
        return;
      }
      const v = viewByPurpose('INVESTIGATION');
      s.status = 'AWAITING_VIEW';
      s.interaction = { kind: 'VIEW', interaction_id: this.interactionId(s), template_id: v.template_id, template_version: v.version, text: v.text, source: src(v.source), safety_notice: v.safety_notice, stop_conditions: v.stop_conditions, purpose: 'INVESTIGATION', target_node_id: v.target_node_id };
      return;
    }
    if (ev.question === undefined) {
      const q = CATALOG.question_templates[0];
      s.status = 'AWAITING_ANSWER';
      s.interaction = { kind: 'QUESTION', interaction_id: this.interactionId(s), template_id: q.template_id, template_version: q.version, text: q.text, source: src(q.source), safety_notice: q.safety_notice, stop_conditions: q.stop_conditions, options: q.options };
      return;
    }
    if (ev.indicator === undefined) return this.serveCheck(s, byKind('OBSERVATION'));
    const ex = CATALOG.explanation_templates[0];
    const claimHolds = ex.claim_rule.allowed_values.includes(ev.indicator);
    if (ev.question === 'YES' && ev.indicator === 'OFF') {
      this.finish(s, 'ESCALATED', 'CONTRADICTORY_EVIDENCE');
      return;
    }
    if (claimHolds && !ev.ack) {
      const d = CATALOG.diagrams.find((x) => x.diagram_id === ex.diagram_id && x.version === ex.diagram_version);
      const withDiagram = this.scenario !== 'diagram-unavailable' && d;
      s.status = 'EXPLAINING';
      s.interaction = {
        kind: 'EXPLANATION', interaction_id: this.interactionId(s), template_id: ex.template_id, template_version: ex.version, text: ex.text, source: src(ex.source), safety_notice: ex.safety_notice, stop_conditions: ex.stop_conditions,
        advisory: true,
        claims: [{ label: 'SUSPECTED', text: 'Synthetic suspected input stage; cause unconfirmed.', evidence_ids: ['ev-indicator'] }],
        diagram: withDiagram ? { diagram_id: d.diagram_id, version: d.version, title: d.title, nodes: d.nodes, edges: d.edges, source: src(d.source) } : null,
        highlights: withDiagram ? ex.allowed_highlight_node_ids.map((n) => ({ node_id: n, label: 'SUSPECTED' as const, evidence_ids: ['ev-indicator'] })) : [],
      };
      return;
    }
    this.finish(s, 'ESCALATED', claimHolds ? 'SUPPORTED_CHECKS_EXHAUSTED' : 'NO_SUPPORTED_EXPLANATION');
  }

  private event(s: FakeSession, type: string, assertion: string | null, refs: CatSource[] | { source_id: string; version: string; locator: string }[] = []) {
    s.events.push({ record_id: `record-${s.id}-${s.events.length + 1}`, session_id: s.id, event_type: type, created_at: new Date(this.now()).toISOString(), human_assertion: assertion, source_refs: refs.map(src) });
  }

  // ---------- helpers for the dev panel ----------
  sessionIds(): string[] {
    return [...this.sessions.keys()];
  }
}
