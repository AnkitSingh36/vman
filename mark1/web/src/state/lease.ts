import { MAX_LEASE_MS, type Check, type Interaction, type Session } from '../api/types';

/**
 * Local deadline for showing an interaction/check.
 *
 * Uses the server-declared lease length (guidance_valid_until - policy_checked_at), capped at the
 * contract maximum of 15 s, measured from when *this client* received the payload. This avoids
 * trusting a skewed device clock and never extends a lease beyond what the server granted.
 * Malformed or non-positive leases yield 0 (never shown).
 */
export function leaseDeadline(item: Pick<Check | Interaction, 'policy_checked_at' | 'guidance_valid_until'>, receivedAtMs: number): number {
  const granted = Date.parse(item.guidance_valid_until) - Date.parse(item.policy_checked_at);
  if (!Number.isFinite(granted) || granted <= 0) return 0;
  return receivedAtMs + Math.min(granted, MAX_LEASE_MS);
}

export function sessionLeaseDeadline(s: Session, receivedAtMs: number): number | null {
  const item = s.interaction ?? s.current_check;
  return item ? leaseDeadline(item, receivedAtMs) : null;
}

export type HideReason = 'EXPIRED' | 'OFFLINE' | 'HIDDEN' | 'STOPPED' | 'REFRESH_FAILED' | 'CONTEXT_CHANGED';

export interface Gate {
  online: boolean;
  visible: boolean;
  locallyStopped: boolean;
  lastRefreshOk: boolean;
  nowMs: number;
  deadlineMs: number | null;
}

/** Returns null when actionable guidance may be shown, else the reason it must be hidden. */
export function guidanceHiddenReason(g: Gate): HideReason | null {
  if (g.locallyStopped) return 'STOPPED';
  if (!g.online) return 'OFFLINE';
  if (!g.visible) return 'HIDDEN';
  if (!g.lastRefreshOk) return 'REFRESH_FAILED';
  if (g.deadlineMs === null || g.nowMs >= g.deadlineMs) return 'EXPIRED';
  return null;
}

/** Stable identity of what is being shown: changing it must cancel speech and re-key the UI. */
export function guidanceKey(s: Session | null): string | null {
  if (!s) return null;
  if (s.interaction) return `${s.session_id}:${s.status}:${s.interaction.interaction_id}:${s.interaction.template_id}@${s.interaction.template_version}`;
  if (s.current_check) return `${s.session_id}:${s.status}:${s.current_check.check_id}@${s.current_check.version}`;
  return null;
}

export const HIDE_MESSAGES: Record<HideReason, string> = {
  EXPIRED: 'Guidance expired. Checking current state…',
  OFFLINE: 'Offline. Guidance hidden until the connection returns and the state is re-checked.',
  HIDDEN: 'App was in the background. Re-checking current state…',
  STOPPED: 'Stopped. No further guidance will be shown.',
  REFRESH_FAILED: 'Could not confirm current state. Guidance hidden; retrying…',
  CONTEXT_CHANGED: 'Session changed. Showing current state only.',
};
