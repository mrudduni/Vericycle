import { useEffect, useMemo, useState } from 'react';
import { listClaims } from '../lib/api';
import { useT } from '../lib/i18n';
import { navigate } from '../lib/router';
import { useSession } from '../lib/session';
import type { ClaimRow } from '../lib/types';
import { Err, FlagCounts, fmtDate, fmtDateTime, pct, productLabel } from '../components/ui';
import { Icon, type IconName } from '../components/Icon';

const HOW_KEY = 'oae-review-how-dismissed';
const readDismissed = () => { try { return localStorage.getItem(HOW_KEY) === '1'; } catch { return false; } };
export const productIcon = (p: string): IconName => (p.includes('BATTER') ? 'battery' : p.includes('PHONE') || p.includes('EWASTE') ? 'phone' : p.includes('REFRIG') || p.startsWith('AC') ? 'snow' : 'box');

function Meter({ v }: { v: number | null }) {
  if (v === null) return <span className="muted">—</span>;
  return (
    <span className="meter" aria-label={`Coverage ${pct(v)}`}>
      <span className="track"><span style={{ width: `${Math.round(v * 100)}%` }} /></span>
      <span className="pct">{pct(v)}</span>
    </span>
  );
}

export default function ClaimList() {
  const t = useT();
  const session = useSession();
  const [rows, setRows] = useState<ClaimRow[] | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  const [product, setProduct] = useState('');
  const [sel, setSel] = useState(0);
  const [how, setHow] = useState(!readDismissed());

  useEffect(() => { listClaims().then(setRows, setErr); }, []);
  const shown = useMemo(() => {
    const r = (rows ?? []).filter((c) => !product || c.product === product);
    return r.sort((a, b) => b.flags.hard - a.flags.hard || b.flags.soft - a.flags.soft || a.claim_id.localeCompare(b.claim_id));
  }, [rows, product]);
  const products = useMemo(() => [...new Set((rows ?? []).map((c) => c.product))], [rows]);
  const kpi = useMemo(() => {
    const r = rows ?? [];
    const cov = r.map((c) => c.coverage).filter((x): x is number => x !== null);
    const med = cov.length ? cov.reduce((a, b) => a + b, 0) / cov.length : null;
    return {
      total: r.length, run: r.filter((c) => c.has_run).length,
      hard: r.filter((c) => c.flags.hard > 0).length, soft: r.filter((c) => c.flags.soft > 0 && !c.flags.hard).length, med,
    };
  }, [rows]);

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === 'j') setSel((s) => Math.min(s + 1, shown.length - 1));
      else if (e.key === 'k') setSel((s) => Math.max(s - 1, 0));
      else if (e.key === 'Enter' && tag !== 'A' && tag !== 'BUTTON' && shown[sel]) navigate(`/claims/${shown[sel].claim_id}`);
    };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [shown, sel]);
  useEffect(() => { setSel(0); }, [product]);

  const dismiss = () => { setHow(false); try { localStorage.setItem(HOW_KEY, '1'); } catch { /* storage blocked */ } };

  return (
    <main>
      <div className="dash-head">
        <div>
          <span className="eyebrow">{t('overview')}{session ? ` · ${session.party_id}` : ''}</span>
          <h2>{t('reviewQueue')}</h2>
        </div>
        <label className="inline">{t('filterProduct')}
          <select value={product} onChange={(e) => setProduct(e.target.value)}>
            <option value="">{t('allProducts')}</option>
            {products.map((p) => <option key={p} value={p}>{productLabel(p)}</option>)}
          </select>
        </label>
      </div>

      <section className="kpis" aria-label={t('overview')}>
        <div className="kpi"><div className="l"><Icon name="layers" size={16} />{t('claimsChecked')}</div><div className="v">{rows ? `${kpi.run}/${kpi.total}` : '—'}</div><div className="s">{t('claimsOf')}</div></div>
        <div className="kpi hard"><div className="l"><Icon name="alert" size={16} />{t('hardFlags')}</div><div className="v">{rows ? kpi.hard : '—'}</div><div className="s">{t('claimsOf')} {t('breakLimit')}</div></div>
        <div className="kpi soft"><div className="l"><Icon name="help" size={16} />{t('softFlags')}</div><div className="v">{rows ? kpi.soft : '—'}</div><div className="s">{t('claimsOf')} {t('needsLook')}</div></div>
        <div className="kpi"><div className="l"><Icon name="link" size={16} />{t('avgCoverage')}</div><div className="v">{rows ? pct(kpi.med) : '—'}</div><div className="s">{t('linked')}</div></div>
      </section>

      {how && (
        <section className="callout how" aria-label={t('howTitle')}>
          <Icon name="help" />
          <div><strong>{t('howTitle')}</strong><p>{t('how1')} {t('how2')} {t('how3')}</p></div>
          <button className="btn secondary" onClick={dismiss}>{t('dismiss')}</button>
        </section>
      )}

      <div className="toolbar">
        <p className="small muted" style={{ margin: 0 }}>{t('sortedHint')}</p>
        <p className="small muted kbd-hint" style={{ margin: 0 }}>Keyboard: <kbd>j</kbd> / <kbd>k</kbd> move, <kbd>Enter</kbd> open.</p>
      </div>
      <Err e={err} />
      {!rows && !err && (
        <div className="tablecard" role="status" aria-label={t('loading')}>
          {Array.from({ length: 5 }).map((_, i) => <div key={i} style={{ padding: 18, borderBottom: '1px solid var(--line)' }}><div className="skel" style={{ height: 18, width: `${60 + (i % 3) * 12}%` }} /></div>)}
        </div>
      )}
      {rows && (
        <div className="tablecard">
          <table className="claims">
            <thead>
              <tr><th scope="col">{t('claim')}</th><th scope="col">{t('product')}</th><th scope="col">{t('recycler')}</th><th scope="col">{t('period')}</th><th scope="col">{t('flags')}</th><th scope="col">{t('coverage')}</th><th scope="col">{t('lastRun')}</th><th scope="col"><span className="sr-only">Open</span></th></tr>
            </thead>
            <tbody>
              {shown.map((c, i) => (
                <tr key={c.claim_id} className={`${i === sel ? 'sel' : ''} ${c.flags.hard ? 'st-hard' : c.flags.soft ? 'st-soft' : 'st-ok'}`} aria-selected={i === sel} onClick={() => navigate(`/claims/${c.claim_id}`)}>
                  <td data-label={t('claim')}><a href={`#/claims/${c.claim_id}`} className="mono strong">{c.claim_id}</a></td>
                  <td data-label={t('product')}><span className="prod"><Icon name={productIcon(c.product)} />{productLabel(c.product)}</span></td>
                  <td data-label={t('recycler')}><span className="pill mono">{c.recycler_party_id}</span></td>
                  <td data-label={t('period')} className="small">{fmtDate(c.period_start)} → {fmtDate(c.period_end)}</td>
                  <td data-label={t('flags')}>{c.has_run ? <FlagCounts hard={c.flags.hard} soft={c.flags.soft} /> : <span className="muted">{t('notRun')}</span>}</td>
                  <td data-label={t('coverage')}><Meter v={c.coverage} /></td>
                  <td data-label={t('lastRun')} className="small muted">{fmtDateTime(c.last_run_at)}</td>
                  <td className="chev" aria-hidden="true"><Icon name="arrow" size={18} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
