import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { get } from '../lib/api';
import { getSession, type Role } from '../lib/session';
import { Chip, ErrorText, Link, useAsync } from '../components/ui';
import { navigate } from '../lib/router';
import { Icon } from '../components/Icon';

const ACTIONS: Record<Role, string[]> = {
  COLLECTOR: ['TRANSFER', 'CORRECTION'],
  AGGREGATOR: ['TRANSFER', 'SPLIT', 'MERGE', 'CORRECTION'],
  RECYCLER: ['INTAKE', 'PROCESS', 'OUTPUT', 'CORRECTION'],
  AUDITOR: [], PRODUCER: [],
};

export function fieldText(name: string, fv: any, t: (k: string) => string): string {
  const v = fv?.value;
  if (v === null || v === undefined) return '—';
  if (name === 'source_category') return t(`src.${v}`);
  if (name === 'child_weights_kg' && typeof v === 'object') return Object.entries(v).map(([k, x]) => `${k}: ${x} kg`).join(', ');
  if (typeof v === 'object') return JSON.stringify(v);
  const basis = fv.basis ? ` (${t(`batch.${String(fv.basis).toLowerCase()}`)})` : '';
  return `${v}${fv.unit ? ' ' + fv.unit : ''}${name.endsWith('_kg') ? basis : ''}`;
}

export default function Batch({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const s = getSession();
  const { data, error, loading } = useAsync(() => get(`/batches/${encodeURIComponent(id)}`), [id]);
  if (!s) return <main><p>{t('signIn')}…</p><Link className="btn" to="/">{t('signIn')}</Link></main>;
  if (loading) return <main><p className="muted">…</p></main>;
  if (error) return <main><ErrorText error={error} /></main>;
  const closed = ['SPLIT', 'MERGED'].includes(data.status);
  return (
    <main>
      <div className="batch-head">
      <span className="eyebrow">{t('batch.title')}</span>
      <div className="id">{data.batch_id}</div>
      <dl className="kv">
        <dt>{t('chat.material')}</dt><dd>{t(`mat.${data.material}`)}</dd>
        <dt>{t('batch.status')}</dt><dd>{data.status}</dd>
        {data.parent_batch_ids?.length > 0 && <><dt>←</dt><dd>{data.parent_batch_ids.map((p: string) => <Link key={p} to={`/b/${p}`}>{p} </Link>)}</dd></>}
        {data.child_batch_ids?.length > 0 && <><dt>→</dt><dd>{data.child_batch_ids.map((c: string) => <Link key={c} to={`/b/${c}`}>{c} </Link>)}</dd></>}
      </dl>
      </div>
      {data.anomalies?.length > 0 && (
        <div className="callout" role="note" style={{ borderColor: 'var(--oae-flag-soft)', marginTop: 12 }}>
          {data.anomalies.map((a: any, i: number) => (
            <div key={i} style={{ color: 'var(--oae-flag-soft)', fontWeight: 600 }}>⚠ #{a.seq}: {a.text[i18n.language === 'hi' ? 'hi' : 'en']}</div>
          ))}
        </div>
      )}
      <h2>{t('batch.events')}</h2>
      <ol className="timeline">
        {data.view.map((ev: any) => (
          <li key={ev.seq}>
            <div style={{ fontWeight: 700 }}>{ev.seq}. {t(`type.${ev.type}`)} <span className="muted small" style={{ fontWeight: 450 }}>{ev.at_server?.slice(0, 16).replace('T', ' ')}</span></div>
            <div className="evt">
            {ev.confirmation && <div style={{ margin: '4px 0' }}><Chip status={ev.confirmation.chip ? chipKey(ev.confirmation) : ev.confirmation.status} /></div>}
            <div className="small">
              {ev.type === 'CORRECTION' ? <CorrectionLine f={ev.fields} /> :
                Object.entries(ev.fields).map(([k, fv]: any) => <div key={k}><span className="muted">{k}:</span> {fieldText(k, fv, t)}</div>)}
            </div>
            <div className="small muted" style={{ marginTop: 6 }}>{ev.evidence_badge === 'EVIDENCE_ATTACHED' ? '📎 ' + t('batch.evidence') : '○ ' + t('batch.noEvidence')}</div>
            </div>
          </li>
        ))}
      </ol>
      {!closed && ACTIONS[s.role].length > 0 && (
        <>
          <h2>{t('batch.actions')}</h2>
          <div className="grid">
            {ACTIONS[s.role].map((a) => <button key={a} className="btn secondary block" onClick={() => navigate(`/b/${data.batch_id}/${a.toLowerCase()}`)}>{t(`batch.${a}`)}</button>)}
          </div>
        </>
      )}
      <p style={{ marginTop: 20 }}><Link className="btn secondary block" to={`/v/${data.batch_id}`}><Icon name="shield" />{t('batch.verify')}</Link></p>
    </main>
  );
}

function CorrectionLine({ f }: { f: any }) {
  const { t } = useTranslation();
  const reason = f.reason?.value, field = f.field?.value, nv = f.new_value?.value;
  if (reason === 'HANDLER_CONFIRMED' && nv && typeof nv === 'object') {
    const own = nv.confirmation_channel !== 'SAME_DEVICE';
    return <div>{own ? '✔' : '⚠'} {t(own ? 'chip.BOTH_PARTIES_CONFIRMED' : 'chip.SAME_DEVICE_CONFIRMED')}: <b>{field}</b> (#{f.corrects_seq?.value})</div>;
  }
  if (reason === 'HANDLER_REJECTED') return <div>✖ {t('confirm.rejected')} (#{f.corrects_seq?.value})</div>;
  return <div>#{f.corrects_seq?.value} <b>{field}</b> → {typeof nv === 'object' ? JSON.stringify(nv) : String(nv)} · {reason}</div>;
}

function chipKey(c: any): string {
  if (c.status === 'BUYER_REPORTED' && Object.values(c.field_status ?? {}).includes('SAME_DEVICE_CONFIRMED')) return 'SAME_DEVICE_CONFIRMED';
  return c.status;
}

export function OpenBatch() {
  const { t } = useTranslation();
  const [v, setV] = useState('');
  return (
    <main>
      <h2>{t('home.batch')}</h2>
      <form onSubmit={(e) => { e.preventDefault(); if (v.trim()) navigate(`/${getSession() ? 'b' : 'v'}/${v.trim().toUpperCase()}`); }}>
        <input value={v} onChange={(e) => setV(e.target.value)} placeholder={t('batch.idPlaceholder')} aria-label={t('batch.idPlaceholder')} autoCapitalize="characters" style={{ fontFamily: 'var(--f-mono)', fontSize: 18 }} />
        <p><button className="btn block"><Icon name="search" />{t('batch.open')}</button></p>
      </form>
    </main>
  );
}
