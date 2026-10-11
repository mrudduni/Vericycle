import { useEffect, useState } from 'react';
import { useT } from '../lib/i18n';
import type { Scores } from '../lib/types';
import { fmtNum, pct } from './ui';

function Ring({ v, color, label }: { v: number | null; color: string; label: string }) {
  const r = 32, c = 2 * Math.PI * r;
  const [shown, setShown] = useState(0);
  useEffect(() => { const id = requestAnimationFrame(() => setShown(v ?? 0)); return () => cancelAnimationFrame(id); }, [v]);
  return (
    <svg viewBox="0 0 76 76" role="img" aria-label={`${label} ${pct(v)}`}>
      <circle cx="38" cy="38" r={r} fill="none" strokeWidth="8" className="bgc" />
      <circle cx="38" cy="38" r={r} fill="none" strokeWidth="8" strokeLinecap="round" className="fg" stroke={color}
        strokeDasharray={c} strokeDashoffset={c * (1 - Math.max(0, Math.min(1, shown)))} />
    </svg>
  );
}

/** Three separate scores. There is deliberately no combined score anywhere. */
export default function ScoreBars({ scores }: { scores: Scores }) {
  const t = useT();
  const q = scores.evidence_quality;
  const total = q.handler_confirmed + q.same_device_confirmed + q.buyer_reported;
  const w = (n: number) => (total ? `${(n / total) * 100}%` : '0%');
  return (
    <section className="scores" aria-label="Scores">
      <div className="score">
        <h3>{t('physical')}</h3>
        <div className="gauge">
          <Ring v={scores.physical_consistency} color="var(--ink-2)" label={t('physical')} />
          <div className="big">{pct(scores.physical_consistency)}</div>
        </div>
        <p className="small muted">
          {scores.physical_consistency === null ? 'Not computed.' : 'Share of physical checks consistent with the data.'}
          {scores.physical_capped_by_hard_flag && <> <strong style={{ color: 'var(--hard)' }}>Capped because a HARD flag is present.</strong></>}
        </p>
      </div>
      <div className="score">
        <h3>{t('traceability')}</h3>
        <div className="gauge">
          <Ring v={scores.traceability_coverage} color="var(--forest-2)" label={t('traceability')} />
          <div className="big">{pct(scores.traceability_coverage)}</div>
        </div>
        <p className="small muted">{fmtNum(scores.covered_kg)} kg of {fmtNum(scores.claimed_kg)} kg claimed is linked to recorded handovers.</p>
      </div>
      <div className="score">
        <h3>{t('evidenceQuality')}</h3>
        <div className="big" style={{ margin: '10px 0 2px' }}>{total} <span className="small">confirmations</span></div>
        <div className="bar stack" role="img" aria-label={`${q.handler_confirmed} handler confirmed, ${q.same_device_confirmed} same device, ${q.buyer_reported} buyer reported`}>
          <span className="seg hc" style={{ width: w(q.handler_confirmed) }} />
          <span className="seg sd" style={{ width: w(q.same_device_confirmed) }} />
          <span className="seg br" style={{ width: w(q.buyer_reported) }} />
        </div>
        <ul className="small qlist">
          <li><span className="sw hc" aria-hidden="true" /> {q.handler_confirmed} handler confirmed</li>
          <li><span className="sw sd" aria-hidden="true" /> ⚠ {q.same_device_confirmed} same device, not witnessed</li>
          <li><span className="sw br" aria-hidden="true" /> {q.buyer_reported} buyer reported</li>
        </ul>
      </div>
    </section>
  );
}
