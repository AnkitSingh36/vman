import { ApiError, NetworkError } from './client';

export function newKey(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c?.randomUUID) return c.randomUUID();
  const b = new Uint8Array(16);
  c?.getRandomValues?.(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('') || `k-${Date.now()}-${Math.random()}`;
}

/** Deterministic JSON (sorted keys) used only to recognise an identical intent locally. */
export function stableStringify(v: unknown): string {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return `[${v.map(stableStringify).join(',')}]`;
  const o = v as Record<string, unknown>;
  return `{${Object.keys(o)
    .sort()
    .filter((k) => o[k] !== undefined)
    .map((k) => `${JSON.stringify(k)}:${stableStringify(o[k])}`)
    .join(',')}}`;
}

/**
 * Stable key per intentional command.
 * - Same op + identical payload (incl. expected_revision) => same key (double tap / exact retry).
 * - Changed payload (e.g. a different answer) => new key, i.e. a new action.
 * Keys are kept in memory only. Browser-storage persistence of pending keys needs A's agreed
 * scope/expiry (spec 05) and is intentionally not enabled.
 */
export class CommandKeys {
  private map = new Map<string, string>();

  keyFor(scope: string, op: string, payload: unknown): string {
    const sig = `${scope}|${op}|${stableStringify(payload)}`;
    let k = this.map.get(sig);
    if (!k) {
      k = newKey();
      this.map.set(sig, k);
    }
    return k;
  }

  /** Forget keys once the effect is acknowledged or the session revision moved on. */
  clear(): void {
    this.map.clear();
  }

  get size(): number {
    return this.map.size;
  }
}

export interface RetryOptions {
  attempts?: number;
  baseDelayMs?: number;
  /** Abort retries (e.g. local stop superseded an ordinary command). */
  shouldContinue?: () => boolean;
  sleep?: (ms: number) => Promise<void>;
  onRetry?: (attempt: number, err: unknown) => void;
}

const defaultSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/**
 * Run `send(key)` and retry *with the same key and payload* when the response was lost or the
 * server reports a retryable dependency failure. Never retries 4xx conflicts/validation.
 */
export async function withRetry<T>(send: () => Promise<T>, opts: RetryOptions = {}): Promise<T> {
  const attempts = opts.attempts ?? 4;
  const sleep = opts.sleep ?? defaultSleep;
  let last: unknown;
  for (let i = 0; i < attempts; i++) {
    if (i > 0 && opts.shouldContinue && !opts.shouldContinue()) break;
    try {
      return await send();
    } catch (e) {
      last = e;
      const retryable = e instanceof NetworkError || (e instanceof ApiError && e.status === 503 && e.retryable);
      if (!retryable || i === attempts - 1) throw e;
      opts.onRetry?.(i + 1, e);
      await sleep((opts.baseDelayMs ?? 400) * 2 ** i);
    }
  }
  throw last;
}
