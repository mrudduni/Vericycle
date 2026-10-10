import { useEffect, useMemo, useState } from 'react';
import { listClaims } from '../lib/api';
import { useT } from '../lib/i18n';
import { navigate } from '../lib/router';
import type { ClaimRow } from '../lib/types';
import { Err, FlagCounts, fmtDate, fmtDateTime, pct, productLabel } from '../components/ui';

const HOW_KEY = 'oae-review-how-dismissed';
const readDismissed = () => { try { return localStorage.getItem(HOW_KEY) === '1'; } catch { return false; } };

export default function ClaimList() {
  const t = useT();
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
      {how && (
        <section className="callout how" aria-label={t('howTitle')}>
          <div className="row"><strong>{t('howTitle')}</strong><button className="btn secondary" onClick={dismiss}>{t('dismiss')}</button></div>
          <p>{t('how1')} {t('how2')} {t('how3')}</p>
        </section>
      )}
      <div className="row between">
        <h2>{t('claims')}</h2>
        <label className="inline">{t('filterProduct')}
          <select value={product} onChange={(e) => setProduct(e.target.value)}>
            <option value="">{t('allProducts')}</option>
            {products.map((p) => <option key={p} value={p}>{productLabel(p)}</option>)}
          </select>
        </label>
      </div>
      <p className="small muted kbd-hint">Keyboard: <kbd>j</kbd> / <kbd>k</kbd> move, <kbd>Enter</kbd> open.</p>
      <Err e={err} />
      {!rows && !err && <p className="muted" role="status">{t('loading')}</p>}
      {rows && (
        <table className="claims">
          <thead>
            <tr><th scope="col">{t('claim')}</th><th scope="col">{t('recycler')}</th><th scope="col">{t('product')}</th><th scope="col">{t('period')}</th><th scope="col">{t('flags')}</th><th scope="col">{t('coverage')}</th><th scope="col">{t('lastRun')}</th></tr>
          </thead>
          <tbody>
            {shown.map((c, i) => (
              <tr key={c.claim_id} className={i === sel ? 'sel' : ''} aria-selected={i === sel} onClick={() => navigate(`/claims/${c.claim_id}`)}>
                <td data-label={t('claim')}><a href={`#/claims/${c.claim_id}`} className="mono strong">{c.claim_id}</a></td>
                <td data-label={t('recycler')}>{c.recycler_party_id}</td>
                <td data-label={t('product')}>{productLabel(c.product)}</td>
                <td data-label={t('period')}>{fmtDate(c.period_start)} to {fmtDate(c.period_end)}</td>
                <td data-label={t('flags')}>{c.has_run ? <FlagCounts hard={c.flags.hard} soft={c.flags.soft} /> : <span className="muted">{t('notRun')}</span>}</td>
                <td data-label={t('coverage')}>{pct(c.coverage)}</td>
                <td data-label={t('lastRun')}>{fmtDateTime(c.last_run_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
