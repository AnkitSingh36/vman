import { useId } from 'react';
import { checkDiagram, HIGHLIGHT_TEXT } from '../api/diagram';
import type { Diagram, Highlight } from '../api/types';

const NODE_W = 210;
const NODE_H = 104;
const PAD = 120;
const EDGE_CHAR_W = 18; // approx. advance per character at the edge-label font size

/**
 * Renders an authored, approved 2D flow/cutaway from validated nodes/edges (0..1000 integer
 * coordinates). Built only from React elements and text nodes: no innerHTML, no external
 * SVG/URLs, no model geometry. This is a diagram, not an internal camera observation.
 */
export function CutawayDiagram({ diagram, highlights }: { diagram: Diagram | null; highlights: Highlight[] }) {
  const uid = useId().replace(/:/g, '');
  const check = checkDiagram(diagram, highlights);

  if (!check.ok) {
    return (
      <div className="diagram-unavailable" role="note" data-testid="diagram-unavailable">
        <strong>Diagram unavailable.</strong> {diagram ? 'The diagram could not be displayed safely; the text explanation above still applies.' : 'No approved diagram applies to this explanation; the text explanation above still applies.'}
      </div>
    );
  }

  const d = check.diagram;
  const byId = new Map(d.nodes.map((n) => [n.node_id, n]));
  const hl = new Map(check.highlights.map((h) => [h.node_id, h]));
  const xs = d.nodes.map((n) => n.x);
  const ys = d.nodes.map((n) => n.y);
  const minX = Math.min(...xs) - NODE_W / 2 - PAD / 2;
  const maxX = Math.max(...xs) + NODE_W / 2 + PAD / 2;
  const minY = Math.min(...ys) - NODE_H / 2 - PAD;
  const maxY = Math.max(...ys) + NODE_H / 2 + PAD;
  const titleId = `dg-title-${uid}`;
  const descId = `dg-desc-${uid}`;
  const arrowId = `dg-arrow-${uid}`;

  return (
    <figure className="diagram" data-testid="diagram">
      <figcaption>
        <strong>{d.title}</strong>
        <span className="small">
          {' '}
          Diagram {d.diagram_id} v{d.version} · Source {d.source.source_id} v{d.source.version} · {d.source.locator}
        </span>
        <span className="badge note">Authored diagram — not an internal camera observation</span>
      </figcaption>
      <svg viewBox={`${minX} ${minY} ${maxX - minX} ${maxY - minY}`} role="img" aria-labelledby={`${titleId} ${descId}`} preserveAspectRatio="xMidYMid meet">
        <title id={titleId}>{d.title}</title>
        <desc id={descId}>
          {d.edges.map((e) => `${byId.get(e.from_node_id)!.label} to ${byId.get(e.to_node_id)!.label}`).join('; ')}
        </desc>
        <defs>
          <marker id={arrowId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" className="dg-arrow" />
          </marker>
        </defs>
        {d.edges.map((e) => {
          const a = byId.get(e.from_node_id)!;
          const b = byId.get(e.to_node_id)!;
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const len = Math.hypot(dx, dy) || 1;
          // Trim line to the node box edges (approximate: half-width along direction).
          const trim = (Math.abs(dx) / len) * (NODE_W / 2) + (Math.abs(dy) / len) * (NODE_H / 2);
          const x1 = a.x + (dx / len) * trim;
          const y1 = a.y + (dy / len) * trim;
          const x2 = b.x - (dx / len) * (trim + 4);
          const y2 = b.y - (dy / len) * (trim + 4);
          return (
            <g key={e.edge_id} data-edge={e.edge_id}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} className="dg-edge" markerEnd={`url(#${arrowId})`} />
              {/* Draw the label only if it fits between the boxes; all edges are also listed as text below. */}
              {e.label.length * EDGE_CHAR_W <= Math.hypot(x2 - x1, y2 - y1) ? (
                <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 22} className="dg-edge-label" textAnchor="middle">
                  {e.label}
                </text>
              ) : null}
            </g>
          );
        })}
        {d.nodes.map((n) => {
          const h = hl.get(n.node_id);
          return (
            <g key={n.node_id} data-node={n.node_id} data-highlight={h?.label ?? ''} className={h ? `dg-node hl-${h.label.toLowerCase()}` : 'dg-node'}>
              <rect x={n.x - NODE_W / 2} y={n.y - NODE_H / 2} width={NODE_W} height={NODE_H} rx={12} />
              <text x={n.x} y={n.y + 17} textAnchor="middle" className="dg-label">
                {n.label}
              </text>
              {h ? (
                <text x={n.x} y={n.y + NODE_H / 2 + 46} textAnchor="middle" className="dg-hl-label">
                  {h.label}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
      {d.edges.length ? (
        <ul className="flow-list small" aria-label="Flow">
          {d.edges.map((e) => (
            <li key={e.edge_id}>
              {byId.get(e.from_node_id)!.label} → {byId.get(e.to_node_id)!.label}: {e.label}
            </li>
          ))}
        </ul>
      ) : null}
      {check.highlights.length ? (
        <ul className="legend" aria-label="Highlights">
          {check.highlights.map((h) => (
            <li key={h.node_id}>
              <span className={`swatch hl-${h.label.toLowerCase()}`} aria-hidden="true" /> {byId.get(h.node_id)!.label}: {HIGHLIGHT_TEXT[h.label]} (evidence {h.evidence_ids.join(', ')})
            </li>
          ))}
        </ul>
      ) : (
        <p className="small muted">No component is highlighted.</p>
      )}
    </figure>
  );
}
