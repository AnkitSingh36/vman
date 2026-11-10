// TypeScript mirror of contract 2.0 (session.schema.json, investigation.schema.json,
// public-api.openapi.json). A owns the contract; this file only consumes it.
// Conformance is tested against the canonical schemas in tests/contract.test.ts.

export const CONTRACT_VERSION = '2.0';

export type Status =
  | 'AWAITING_IDENTITY'
  | 'EVALUATING'
  | 'READY'
  | 'RECORD_PENDING'
  | 'BLOCKED'
  | 'UNKNOWN'
  | 'ESCALATED'
  | 'COMPLETED'
  | 'AWAITING_VIEW'
  | 'AWAITING_ANSWER'
  | 'EXPLAINING';

export const TERMINAL_STATUSES: readonly Status[] = ['BLOCKED', 'UNKNOWN', 'ESCALATED', 'COMPLETED'];

export interface SourceRef {
  source_id: string;
  version: string;
  locator: string;
}

export interface Identity {
  model_id: string;
  configuration_id: string;
  human_confirmed: true;
}

export interface IdentityCandidate {
  model_id: string;
  configuration_id: string;
  label_excerpt: string;
  basis: 'IMAGE' | 'MANUAL';
}

export interface Check {
  check_id: string;
  version: string;
  instruction: string;
  observation_code: string;
  options: string[];
  source: SourceRef;
  policy_checked_at: string;
  safety_notice: string;
  stop_conditions: string[];
  guidance_valid_until: string;
}

export type CommandState = 'PENDING' | 'PERSISTED';

export interface Receipt {
  command_id: string;
  state: CommandState;
  record_id: string | null;
}

interface InteractionBase {
  interaction_id: string;
  template_id: string;
  template_version: string;
  text: string;
  source: SourceRef;
  policy_checked_at: string;
  guidance_valid_until: string;
  safety_notice: string;
  stop_conditions: string[];
}

export interface ViewInteraction extends InteractionBase {
  kind: 'VIEW';
  purpose: 'IDENTITY' | 'INVESTIGATION';
  target_node_id: string | null;
}

export interface QuestionInteraction extends InteractionBase {
  kind: 'QUESTION';
  options: string[];
}

export interface DiagramNode {
  node_id: string;
  label: string;
  x: number;
  y: number;
}

export interface DiagramEdge {
  edge_id: string;
  from_node_id: string;
  to_node_id: string;
  label: string;
}

export interface Diagram {
  diagram_id: string;
  version: string;
  title: string;
  nodes: DiagramNode[];
  edges: DiagramEdge[];
  source: SourceRef;
}

export type HighlightLabel = 'OBSERVED' | 'REPORTED' | 'SUSPECTED' | 'UNKNOWN';

export interface Highlight {
  node_id: string;
  label: HighlightLabel;
  evidence_ids: string[];
}

export interface Claim {
  label: 'SUSPECTED';
  text: string;
  evidence_ids: string[];
}

export interface ExplanationInteraction extends InteractionBase {
  kind: 'EXPLANATION';
  advisory: true;
  claims: Claim[];
  diagram: Diagram | null;
  highlights: Highlight[];
}

export type Interaction = ViewInteraction | QuestionInteraction | ExplanationInteraction;

export interface Session {
  contract_version: '2.0';
  session_id: string;
  revision: number;
  status: Status;
  workflow_id: string;
  identity: Identity | null;
  identity_candidates: IdentityCandidate[];
  current_check: Check | null;
  receipt: Receipt | null;
  human_reported_outcome: 'RESOLVED' | 'UNRESOLVED' | null;
  reason_code: string | null;
  interaction: Interaction | null;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  request_id: string;
  retryable: boolean;
  current_revision?: number;
}

export interface ImageReceipt {
  image_id: string;
  session_id: string;
  revision: number;
  status: 'STORED';
}

export interface SessionEvent {
  record_id: string;
  session_id: string;
  event_type: string;
  created_at: string;
  human_assertion: string | null;
  source_refs: SourceRef[];
}

export interface EventPage {
  events: SessionEvent[];
  next_cursor: string | null;
}

// ---- Request bodies (OpenAPI components) ----
export interface CreateSessionBody {
  workflow_id: string;
  symptom_code: 'NO_POWER';
  symptom_text?: string;
}
export interface IdentityCandidatesBody {
  expected_revision: number;
  image_id?: string;
  manual_label?: string;
}
export interface ConfirmIdentityBody {
  expected_revision: number;
  model_id: string;
  configuration_id: string;
  serial?: string;
  human_confirmed: true;
}
export interface ObservationBody {
  expected_revision: number;
  check_id: string;
  check_version: string;
  observation_code: string;
  value: string;
  image_id?: string;
  human_confirmed: true;
}
export interface OutcomeBody {
  expected_revision: number;
  human_reported_outcome: 'RESOLVED' | 'UNRESOLVED';
  human_confirmed: true;
}
export type StopReason = 'USER_STOP' | 'UNSUPPORTED' | 'OTHER';
export interface StopBody {
  expected_revision: number;
  reason_code: StopReason;
}
export type HazardCode = 'DAMAGE' | 'LIQUID' | 'SWELLING' | 'HEAT_OR_SMELL' | 'UNSURE';
export interface HazardBody {
  expected_revision: number;
  hazard_code: HazardCode;
}
export interface ViewResponseBody {
  expected_revision: number;
  interaction_id: string;
  template_id: string;
  template_version: string;
  result: 'IMAGE' | 'UNAVAILABLE' | 'UNSURE';
  image_id: string | null;
  human_confirmed: true;
}
export interface AnswerBody {
  expected_revision: number;
  interaction_id: string;
  template_id: string;
  template_version: string;
  value: string;
  human_confirmed: true;
}
export interface MessageBody {
  expected_revision: number;
  text: string;
  channel: 'CHAT' | 'VOICE_TRANSCRIPT';
  human_confirmed: true;
}
export interface ExplanationAckBody {
  expected_revision: number;
  interaction_id: string;
  template_id: string;
  template_version: string;
  acknowledged: true;
}

export type ImagePurpose = 'identity' | 'investigation' | 'observation';

/** Session mutation operations (path segment under /v2/sessions/{id}/). */
export type SessionOp =
  | 'identity-candidates'
  | 'identity-confirmation'
  | 'view-responses'
  | 'answers'
  | 'messages'
  | 'explanation-acks'
  | 'observations'
  | 'outcome'
  | 'stop'
  | 'hazards';

export const MESSAGE_MAX_CHARS = 2000;
export const IMAGE_MAX_BYTES = 10 * 1024 * 1024;
export const IMAGE_TYPES = ['image/jpeg', 'image/png'] as const;
/** Contract: lease <= 15 s; foreground refresh every 5 s. */
export const MAX_LEASE_MS = 15_000;
export const REFRESH_INTERVAL_MS = 5_000;
