import type {
  ApiErrorBody,
  CommandState,
  CreateSessionBody,
  EventPage,
  ImagePurpose,
  ImageReceipt,
  Receipt,
  Session,
  SessionOp,
} from './types';

/** Raw transport so the same client runs against A's server or the in-browser fake. */
export interface TransportRequest {
  method: 'GET' | 'POST';
  path: string;
  headers: Record<string, string>;
  json?: unknown;
  form?: FormData;
}
export interface TransportResponse {
  status: number;
  headers: Record<string, string>;
  body: unknown;
}
export interface Transport {
  send(req: TransportRequest): Promise<TransportResponse>;
}

/** HTTP error with the contract's user-safe body. Messages never carry guidance. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ApiErrorBody | null,
  ) {
    super(body?.code ?? `HTTP_${status}`);
  }
  get retryable(): boolean {
    return this.body?.retryable ?? (this.status === 503 || this.status === 429);
  }
}

/** The response was lost (offline, timeout, reset). Outcome is unknown; retry with the same key. */
export class NetworkError extends Error {
  constructor(cause?: unknown) {
    super('NETWORK_UNAVAILABLE');
    this.cause = cause;
  }
}

export interface CommandResult<T = Session> {
  httpStatus: number;
  data: T;
  commandId: string | null;
  commandState: CommandState | null;
}

export class HttpTransport implements Transport {
  constructor(
    private readonly base = '',
    private readonly timeoutMs = 20_000,
    /** A-01 chooses cookie+CSRF or tokens; inject the agreed header here. */
    private readonly authHeaders: () => Record<string, string> = () => ({}),
  ) {}

  async send(req: TransportRequest): Promise<TransportResponse> {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), this.timeoutMs);
    try {
      const headers: Record<string, string> = { Accept: 'application/json', ...this.authHeaders(), ...req.headers };
      let body: BodyInit | undefined;
      if (req.form) body = req.form;
      else if (req.json !== undefined) {
        headers['Content-Type'] = 'application/json';
        body = JSON.stringify(req.json);
      }
      const res = await fetch(this.base + req.path, {
        method: req.method,
        headers,
        body,
        credentials: 'same-origin',
        cache: 'no-store',
        signal: ctrl.signal,
      });
      const out: Record<string, string> = {};
      res.headers.forEach((v, k) => (out[k.toLowerCase()] = v));
      const text = await res.text();
      let parsed: unknown = null;
      if (text) {
        try {
          parsed = JSON.parse(text);
        } catch {
          parsed = null;
        }
      }
      return { status: res.status, headers: out, body: parsed };
    } catch (e) {
      throw new NetworkError(e);
    } finally {
      clearTimeout(timer);
    }
  }
}

function asError(res: TransportResponse): ApiError {
  const b = res.body as Partial<ApiErrorBody> | null;
  const body = b && typeof b.code === 'string' ? (b as ApiErrorBody) : null;
  return new ApiError(res.status, body);
}

function commandHeaders(res: TransportResponse): Pick<CommandResult, 'commandId' | 'commandState'> {
  const state = res.headers['x-command-state'];
  return {
    commandId: res.headers['x-command-id'] ?? null,
    commandState: state === 'PENDING' || state === 'PERSISTED' ? state : null,
  };
}

const enc = encodeURIComponent;

export class ApiClient {
  constructor(readonly transport: Transport) {}

  private async ok<T>(req: TransportRequest, okStatuses: number[]): Promise<CommandResult<T>> {
    const res = await this.transport.send(req);
    if (!okStatuses.includes(res.status)) throw asError(res);
    return { httpStatus: res.status, data: res.body as T, ...commandHeaders(res) };
  }

  createSession(body: CreateSessionBody, idempotencyKey: string) {
    return this.ok<Session>(
      { method: 'POST', path: '/v2/sessions', headers: { 'Idempotency-Key': idempotencyKey }, json: body },
      [201, 200],
    );
  }

  async getSession(id: string): Promise<Session> {
    return (await this.ok<Session>({ method: 'GET', path: `/v2/sessions/${enc(id)}`, headers: {} }, [200])).data;
  }

  async getEvents(id: string, cursor?: string): Promise<EventPage> {
    const q = cursor ? `?cursor=${enc(cursor)}` : '';
    return (await this.ok<EventPage>({ method: 'GET', path: `/v2/sessions/${enc(id)}/events${q}`, headers: {} }, [200]))
      .data;
  }

  async getCommand(id: string, commandId: string): Promise<Receipt> {
    return (
      await this.ok<Receipt>(
        { method: 'GET', path: `/v2/sessions/${enc(id)}/commands/${enc(commandId)}`, headers: {} },
        [200],
      )
    ).data;
  }

  command(id: string, op: SessionOp, body: object, idempotencyKey: string) {
    return this.ok<Session>(
      {
        method: 'POST',
        path: `/v2/sessions/${enc(id)}/${op}`,
        headers: { 'Idempotency-Key': idempotencyKey },
        json: body,
      },
      [200, 202],
    );
  }

  uploadImage(
    id: string,
    file: Blob,
    purpose: ImagePurpose,
    expectedRevision: number,
    idempotencyKey: string,
  ) {
    const form = new FormData();
    form.append('file', file, file.type === 'image/png' ? 'frame.png' : 'frame.jpg');
    form.append('expected_revision', String(expectedRevision));
    form.append('purpose', purpose);
    return this.ok<ImageReceipt>(
      { method: 'POST', path: `/v2/sessions/${enc(id)}/images`, headers: { 'Idempotency-Key': idempotencyKey }, form },
      [201],
    );
  }
}
