import { useEffect, useState } from 'react';
import { getImpact } from '../lib/api';
import { useT } from '../lib/i18n';
import type { Metric, Source } from '../lib/types';
import { DemoBadge, Err, SourceChip, fmtNum, useSourceDrawer } from '../components/ui';

function InfoButton({ m }: { m: Metric }) {
  const { open } = useSourceDrawer();
  if (m.source_ids.length) return <>{m.source_ids.map((s) => <SourceChip key={s} id={s} />)}</>;
  const pre: Source = { id: m.id, title: m.label, status: 'CITED', date: null, locator: 'Custody ledger count', url: null, value: m.value, note: m.note, demo_value: false };
  return (
    <button type="button" className="chip src" aria-haspopup="dialog" aria-label={`How ${m.label} is counted`} onClick={() => open(m.id, pre)}>
      <span aria-hidden="true">ⓘ</span> how counted
    </button>
  );
}

export default function Impact() {
  const t = useT();
  const [ms, setMs] = useState<Metric[] | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  useEffect(() => { getImpact().then(setMs, setErr); }, []);
  return (
    <main>
      <span className="eyebrow">Public · live</span>
      <h2 style={{ fontSize: 'clamp(34px, 4vw, 52px)', margin: '8px 0 10px' }}>{t('impact')}</h2>
      <p className="muted" style={{ fontSize: 17, maxWidth: 640, marginTop: 0, marginBottom: 28 }}>Public figures from the custody ledger and ClaimGuard runs. Every number opens its source.</p>
      <Err e={err} />
      {!ms && !err && <div className="metrics" role="status" aria-label={t('loading')}>{[0, 1, 2].map((i) => <div key={i} className="skel" style={{ height: 180 }} />)}</div>}
      <div className="metrics">
        {ms?.map((m) => {
          const ratio = m.unit === 'ratio';
          const refrigerant = m.id.startsWith('refrigerant');
          return (
            <article key={m.id} className={`metric ${refrigerant ? 'refrig' : ''}`} data-metric={m.id}>
              <h3>{m.label}</h3>
              <div className="mval"><span>{ratio ? `${Math.round(m.value * 100)}%` : fmtNum(m.value)}</span> {!ratio && <span className="unit">{m.unit}</span>}</div>
              {m.demo_value && <DemoBadge />}
              <p className="small muted">{m.note}</p>
              {refrigerant && (
                <div className="callout" role="note">
                  <strong>No certificate exists for refrigerant, so no claim can be made.</strong> This figure is potential harm that no certificate counts. It is not a claim and it is not a reduction.
                </div>
              )}
              <div className="srcs"><InfoButton m={m} /></div>
            </article>
          );
        })}
      </div>
    </main>
  );
}
