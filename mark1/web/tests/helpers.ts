import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import sessionSchema from '@contracts/session.schema.json';
import investigationSchema from '@contracts/investigation.schema.json';
import openapi from '@contracts/public-api.openapi.json';
import { ApiClient, type Transport } from '../src/api/client';
import { FakeServer, type FakeFaults, type FakeScenario } from '../src/fake/fakeServer';
import { SessionController } from '../src/state/controller';
import type { Session } from '../src/api/types';

export const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
ajv.addSchema(investigationSchema as object);
ajv.addSchema(sessionSchema as object);
export const validateSession = ajv.getSchema('https://schemas.mark1.invalid/v2/session.schema.json')!;

const components = (openapi as unknown as { components: { schemas: Record<string, object> } }).components.schemas;
const requestValidators = new Map<string, ReturnType<typeof ajv.compile>>();
export function validateRequest(component: string, body: unknown): boolean {
  let v = requestValidators.get(component);
  if (!v) {
    v = ajv.compile(components[component]);
    requestValidators.set(component, v);
  }
  return v(body) as boolean;
}

export const OP_COMPONENT: Record<string, string> = {
  'identity-candidates': 'IdentityCandidates',
  'identity-confirmation': 'ConfirmIdentity',
  observations: 'Observation',
  outcome: 'Outcome',
  stop: 'Stop',
  hazards: 'Hazard',
  'view-responses': 'ViewResponse',
  answers: 'Answer',
  messages: 'Message',
  'explanation-acks': 'ExplanationAck',
};

export function assertValidSession(s: unknown): asserts s is Session {
  if (!validateSession(s)) {
    throw new Error(`Session does not match contract: ${JSON.stringify(validateSession.errors?.slice(0, 3))}\n${JSON.stringify(s)}`);
  }
}

/** Transport wrapper that records requests and validates every body/response against the contract. */
export class RecordingTransport implements Transport {
  requests: { method: string; path: string; key?: string; json?: unknown }[] = [];
  sessions: Session[] = [];
  constructor(readonly inner: Transport) {}
  async send(req: Parameters<Transport['send']>[0]) {
    this.requests.push({ method: req.method, path: req.path, key: req.headers['Idempotency-Key'], json: req.json });
    const op = req.path.split('/')[4];
    if (req.method === 'POST' && op && OP_COMPONENT[op]) {
      if (!validateRequest(OP_COMPONENT[op], req.json)) throw new Error(`Request ${op} violates contract: ${JSON.stringify(req.json)}`);
    }
    if (req.method === 'POST' && req.path === '/v2/sessions' && !validateRequest('CreateSession', req.json)) throw new Error('bad CreateSession');
    const res = await this.inner.send(req);
    if (res.status < 300 && res.body && typeof res.body === 'object' && 'contract_version' in (res.body as object)) {
      assertValidSession(res.body);
      this.sessions.push(res.body as Session);
    }
    return res;
  }
  posts(op: string) {
    return this.requests.filter((r) => r.method === 'POST' && r.path.endsWith(`/${op}`));
  }
}

export function setup(opts: { scenario?: FakeScenario; faults?: Partial<FakeFaults> } = {}) {
  const fake = new FakeServer({ scenario: opts.scenario, faults: { evaluatingMs: 0, latencyMs: 0, ...opts.faults } });
  const rec = new RecordingTransport(fake);
  const invalidations: string[] = [];
  const controller = new SessionController({
    api: new ApiClient(rec),
    setTimer: () => null,
    clearTimer: () => undefined,
    sleep: () => Promise.resolve(),
    onInvalidate: (r) => invalidations.push(r),
  });
  return { fake, rec, controller, invalidations };
}

export const tick = () => new Promise((r) => setTimeout(r, 0));
