import type { Diagram, Highlight, HighlightLabel } from './types';

/**
 * Defensive client-side checks before rendering an authored diagram.
 * A validates/publishes diagrams; this is only a renderer guard so a malformed payload is never
 * drawn with invented geometry. Any failure -> the panel shows the text explanation only.
 */
export type DiagramCheck =
  | { ok: true; diagram: Diagram; highlights: Highlight[] }
  | { ok: false; reason: string };

const LABELS: readonly HighlightLabel[] = ['OBSERVED', 'REPORTED', 'SUSPECTED', 'UNKNOWN'];
const isCoord = (v: unknown) => typeof v === 'number' && Number.isInteger(v) && v >= 0 && v <= 1000;
const isText = (v: unknown) => typeof v === 'string' && v.length > 0;

export function checkDiagram(diagram: Diagram | null, highlights: Highlight[]): DiagramCheck {
  if (!diagram) return highlights.length ? { ok: false, reason: 'Highlights without a diagram' } : { ok: false, reason: 'No authorized diagram' };
  if (!isText(diagram.diagram_id) || !isText(diagram.version) || !isText(diagram.title)) return { ok: false, reason: 'Missing diagram identity' };
  if (!diagram.source || !isText(diagram.source.source_id) || !isText(diagram.source.version)) return { ok: false, reason: 'Missing diagram source' };
  if (!Array.isArray(diagram.nodes) || diagram.nodes.length < 1 || diagram.nodes.length > 100) return { ok: false, reason: 'Invalid node count' };
  if (!Array.isArray(diagram.edges) || diagram.edges.length > 200) return { ok: false, reason: 'Invalid edge count' };

  const nodeIds = new Set<string>();
  for (const n of diagram.nodes) {
    if (!isText(n.node_id) || !isText(n.label)) return { ok: false, reason: 'Invalid node' };
    if (!isCoord(n.x) || !isCoord(n.y)) return { ok: false, reason: `Invalid position for ${n.node_id}` };
    if (nodeIds.has(n.node_id)) return { ok: false, reason: `Duplicate node ${n.node_id}` };
    nodeIds.add(n.node_id);
  }
  const edgeIds = new Set<string>();
  for (const e of diagram.edges) {
    if (!isText(e.edge_id) || !isText(e.label)) return { ok: false, reason: 'Invalid edge' };
    if (edgeIds.has(e.edge_id)) return { ok: false, reason: `Duplicate edge ${e.edge_id}` };
    if (!nodeIds.has(e.from_node_id) || !nodeIds.has(e.to_node_id)) return { ok: false, reason: `Dangling edge ${e.edge_id}` };
    edgeIds.add(e.edge_id);
  }
  for (const h of highlights) {
    if (!nodeIds.has(h.node_id)) return { ok: false, reason: `Highlight references unknown node ${h.node_id}` };
    if (!LABELS.includes(h.label)) return { ok: false, reason: 'Unknown highlight label' };
    if (!Array.isArray(h.evidence_ids) || h.evidence_ids.length === 0) return { ok: false, reason: 'Highlight without evidence' };
  }
  return { ok: true, diagram, highlights };
}

export const HIGHLIGHT_TEXT: Record<HighlightLabel, string> = {
  OBSERVED: 'Observed (human-confirmed)',
  REPORTED: 'Reported (not confirmed)',
  SUSPECTED: 'Suspected — advisory, cause unconfirmed',
  UNKNOWN: 'Unknown',
};
