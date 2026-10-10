import { useT } from '../lib/i18n';
import type { Lineage as LineageT, LineageEvent } from '../lib/types';
import { ConfChip, confInfo, fmtDateTime, fmtNum } from './ui';

const isSameDevice = (e: LineageEvent) => Object.values(e.fields).some((f) => f.status === 'SAME_DEVICE_CONFIRMED') && !Object.values(e.fields).some((f) => f.status === 'HANDLER_CONFIRMED');
const dash = { solid: undefined, dashed: '7 5', dotted: '1.5 5', none: undefined } as const;

function Legend() {
  const t = useT();
  const items = [
    { s: 'solid' as const, label: 'Solid: handler or both parties confirmed' },
    { s: 'dashed' as const, label: 'Dashed: buyer reported only' },
    { s: 'dotted' as const, label: '⚠ Dotted: same device, not witnessed' },
  ];
  return (
    <ul className="legend" aria-label={t('legend')}>
      {items.map((i) => (
        <li key={i.s}>
          <svg width="44" height="12" aria-hidden="true"><line x1="2" y1="6" x2="42" y2="6" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeDasharray={dash[i.s]} /></svg>
          {i.label}
        </li>
      ))}
    </ul>
  );
}

export default function LineageView({ lineage }: { lineage: LineageT }) {
  const t = useT();
  const nodes = lineage.nodes;
  if (!nodes.length) return <p className="muted">No custody batches are cited by this claim.</p>;
  const maxEv = Math.max(...nodes.map((n) => n.events.length), 1);
  const rowH = 78, x0 = 190, step = 130;
  const W = x0 + maxEv * step, H = nodes.length * rowH + 16;
  const y = (i: number) => 16 + i * rowH + 26;
  const idx = new Map(nodes.map((n, i) => [n.batch_id, i]));
  return (
    <div className="lineage">
      <Legend />
      <div className="svgwrap">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Lineage graph: one row per batch, one dot per event" style={{ width: '100%', minWidth: Math.min(W, 560), height: 'auto' }}>
          {lineage.edges.map((e, i) => {
            const a = idx.get(e.from), b = idx.get(e.to);
            if (a === undefined || b === undefined) return null;
            const ya = y(a), yb = y(b), cx = 8 + Math.abs(a - b) * 4;
            return (
              <g key={i} className="edge">
                <path d={`M 20 ${ya + 18} C ${cx} ${ya + 40}, ${cx} ${yb - 40}, 20 ${yb - 18}`} fill="none" stroke="currentColor" strokeWidth="2" />
                <text x="26" y={(ya + yb) / 2} fontSize="11" fill="currentColor">{e.kind}{e.weight_kg ? ` ${fmtNum(e.weight_kg)} kg` : ''}</text>
              </g>
            );
          })}
          {nodes.map((n, i) => (
            <g key={n.batch_id} transform={`translate(0 ${y(i)})`}>
              <rect x="30" y="-18" width="118" height="36" rx="8" className="gnode" />
              <text x="89" y="-2" textAnchor="middle" fontSize="13" fontWeight="700" className="gtxt">{n.batch_id}</text>
              <text x="89" y="12" textAnchor="middle" fontSize="10" className="gtxt">{n.status}</text>
              {n.events.length > 1 && <line x1={x0} y1="0" x2={x0 + (n.events.length - 1) * step} y2="0" stroke="currentColor" strokeOpacity=".35" strokeWidth="2" />}
              {n.events.map((e, k) => {
                const c = confInfo(e.confirmation, isSameDevice(e));
                const cx = x0 + k * step;
                return (
                  <g key={e.seq} data-conf={c.style}>
                    <circle cx={cx} cy="0" r="11" className="gdot" fill={c.style === 'none' ? 'transparent' : 'var(--oae-bg)'} stroke="currentColor" strokeWidth={c.style === 'none' ? 1.5 : 3.5} strokeDasharray={dash[c.style]} strokeLinecap="round" />
                    {c.style === 'dotted' && <text x={cx + 14} y="-10" fontSize="14" fill="var(--oae-flag-soft)" aria-hidden="true">⚠</text>}
                    <text x={cx} y="30" textAnchor="middle" fontSize="11" className="gtxt">{e.seq}. {e.type}</text>
                    <text x={cx} y="43" textAnchor="middle" fontSize="10" className="gtxt gmute">{e.weight_kg !== null ? `${fmtNum(e.weight_kg)} kg` : ''}</text>
                  </g>
                );
              })}
            </g>
          ))}
        </svg>
      </div>
      <h4 className="sr-only">Event details</h4>
      {nodes.map((n) => (
        <section key={n.batch_id} className="batch" aria-label={`Batch ${n.batch_id}`}>
          <h4><span className="mono">{n.batch_id}</span> <span className="small muted">{n.material.replace(/_/g, ' ').toLowerCase()} · {n.status}</span></h4>
          <ul className="events">
            {n.events.map((e) => (
              <li key={e.seq} data-batch={n.batch_id} data-seq={e.seq}>
                <span className="mono">#{e.seq} {e.type}</span>
                <span className="small muted">{fmtDateTime(e.at_server)} · {e.actor_party_id}{e.weight_kg !== null ? ` · ${fmtNum(e.weight_kg)} kg` : ''}{e.basis ? ` (${e.basis.toLowerCase()})` : ''}</span>
                <ConfChip conf={e.confirmation} sameDevice={isSameDevice(e)} />
                {Object.entries(e.fields).map(([name, f]) => (
                  <span key={name} className="chip field" title={`${name}: ${f.status}, channel ${f.channel}`}>
                    <span aria-hidden="true">{f.status === 'HANDLER_CONFIRMED' ? '●' : f.status === 'SAME_DEVICE_CONFIRMED' ? '⚠' : '◌'}</span> {name}: {f.status.replace(/_/g, ' ').toLowerCase()}
                  </span>
                ))}
                <span className="chip ev-badge">{e.evidence_ids.length ? 'Evidence attached' : 'No evidence attached'}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
