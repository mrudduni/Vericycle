import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { getSource } from '../lib/api';
import { useT } from '../lib/i18n';
import type { Confirmation, Outcome, Severity, Source } from '../lib/types';

export const fmtNum = (v: unknown): string => {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') return v.toLocaleString('en-IN', { maximumFractionDigits: 3 });
  if (Array.isArray(v)) return `[${v.map(fmtNum).join(', ')}]`;
  if (typeof v === 'object') {
    return Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k} ${fmtNum(x)}`).join(', ');
  }
  return String(v);
};
export const fmtDate = (s: string | null | undefined) => (s ? s.slice(0, 10) : '—');
export const fmtDateTime = (s: string | null | undefined) => (s ? s.slice(0, 16).replace('T', ' ') : '—');
export const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`);
export const productLabel = (p: string) => p.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

/* ---------- outcome chip: icon + word, never colour alone ---------- */
const OUTCOME: Record<Outcome, { icon: string; word: string; plain: string }> = {
  PASS: { icon: '○', word: 'PASS', plain: 'consistent with available data' },
  FLAG: { icon: '▲', word: 'FLAG', plain: 'inconsistent with data' },
  INSUFFICIENT_EVIDENCE: { icon: '◔', word: 'INSUFFICIENT EVIDENCE', plain: 'not enough evidence' },
  INCONCLUSIVE: { icon: '?', word: 'INCONCLUSIVE', plain: 'could not be decided' },
};
export const outcomeInfo = (o: Outcome) => OUTCOME[o];
export function OutcomeChip({ outcome, severity }: { outcome: Outcome; severity: Severity }) {
  const o = OUTCOME[outcome];
  const cls = outcome === 'FLAG' ? (severity === 'HARD' ? 'hard' : 'soft') : outcome === 'PASS' ? 'pass' : outcome === 'INSUFFICIENT_EVIDENCE' ? 'insuff' : 'incon';
  return <span className={`chip out ${cls}`}><span aria-hidden="true">{o.icon}</span> {o.word}</span>;
}

export function FlagCounts({ hard, soft }: { hard: number; soft: number }) {
  const t = useT();
  if (!hard && !soft) return <span className="chip out pass"><span aria-hidden="true">○</span> {t('noFlags')}</span>;
  return (
    <span className="flagcounts">
      {hard > 0 && <span className="chip out hard"><span aria-hidden="true">▲</span> {hard} HARD</span>}
      {soft > 0 && <span className="chip out soft"><span aria-hidden="true">▲</span> {soft} SOFT</span>}
    </span>
  );
}

export function DemoBadge() {
  const t = useT();
  return <span className="chip demo" title="Placeholder value used for the demo, not a measured or cited figure">{t('demo')}</span>;
}

/* ---------- confirmation chips ---------- */
export type ConfStyle = 'solid' | 'dashed' | 'dotted' | 'none';
export function confInfo(conf: Confirmation, sameDevice: boolean): { style: ConfStyle; icon: string; word: string } {
  if (conf === 'BOTH_PARTIES_CONFIRMED') return { style: 'solid', icon: '●●', word: 'Both parties confirmed' };
  if (conf === 'HANDLER_CONFIRMED') return { style: 'solid', icon: '●', word: 'Handler confirmed' };
  if (conf === 'BUYER_REPORTED' && sameDevice) return { style: 'dotted', icon: '⚠', word: 'Same device, not witnessed' };
  if (conf === 'BUYER_REPORTED') return { style: 'dashed', icon: '◌', word: 'Buyer reported' };
  return { style: 'none', icon: '·', word: 'Recorded by party' };
}
export function ConfChip({ conf, sameDevice }: { conf: Confirmation; sameDevice: boolean }) {
  const c = confInfo(conf, sameDevice);
  return <span className={`chip conf ${c.style}`}><span aria-hidden="true">{c.icon}</span> {c.word}</span>;
}

/* ---------- source drawer ---------- */
interface DrawerApi { open: (id: string, pre?: Source) => void }
const DrawerCtx = createContext<DrawerApi>({ open: () => undefined });
export const useSourceDrawer = () => useContext(DrawerCtx);

export function SourceDrawerHost({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ id: string; pre?: Source } | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const open = useCallback((id: string, pre?: Source) => { opener.current = document.activeElement as HTMLElement | null; setState({ id, pre }); }, []);
  const close = useCallback(() => { setState(null); opener.current?.focus(); }, []);
  return (
    <DrawerCtx.Provider value={{ open }}>
      {children}
      {state && <SourceDrawer id={state.id} pre={state.pre} onClose={close} />}
    </DrawerCtx.Provider>
  );
}

function SourceDrawer({ id, pre, onClose }: { id: string; pre?: Source; onClose: () => void }) {
  const t = useT();
  const [src, setSrc] = useState<Source | null>(pre ?? null);
  const [err, setErr] = useState<string | null>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    setSrc(pre ?? null); setErr(null);
    if (!pre) getSource(id).then(setSrc, (e: Error) => setErr(e.message));
  }, [id, pre]);
  useEffect(() => { closeBtn.current?.focus(); }, []);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [onClose]);
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <header>
          <h2 id="drawer-title">{t('source')}</h2>
          <button ref={closeBtn} className="btn secondary" style={{ minHeight: 38 }} onClick={onClose}>{t('close')}</button>
        </header>
        {err && <p className="error" role="alert">{err}</p>}
        {!src && !err && <p className="muted">{t('loading')}</p>}
        {src && (
          <div className="srcbody">
            <h3>{src.title}</h3>
            <p>
              <span className={`chip ${src.status === 'CITED' ? 'cited' : 'demo'}`}>{src.status === 'CITED' ? 'CITED' : 'DEMO VALUE'}</span>{' '}
              <span className="mono small muted">{src.id}</span>
            </p>
            <dl className="kv">
              <dt>Date</dt><dd>{src.date ?? '—'}</dd>
              <dt>Locator</dt><dd>{src.locator ?? '—'}</dd>
              {src.value !== null && src.value !== undefined && (<><dt>Value</dt><dd className="mono">{typeof src.value === 'object' ? JSON.stringify(src.value) : String(src.value)}</dd></>)}
              <dt>URL</dt><dd>{src.url ? <a href={src.url} target="_blank" rel="noreferrer noopener">{src.url}</a> : 'No public URL recorded'}</dd>
            </dl>
            {src.note && <div className="callout"><strong>Note</strong><p className="pre">{src.note}</p></div>}
          </div>
        )}
      </aside>
    </>
  );
}

export function SourceChip({ id, sources }: { id: string; sources?: Record<string, Source> }) {
  const { open } = useSourceDrawer();
  const s = sources?.[id];
  return (
    <button type="button" className="chip src" onClick={() => open(id, s)} aria-haspopup="dialog" aria-label={`Open source ${s?.title ?? id}`}>
      <span aria-hidden="true">ⓘ</span> <span className="mono">{id}</span>
    </button>
  );
}

export function Err({ e }: { e: Error | null }) {
  return e ? <p className="error" role="alert"><span aria-hidden="true">⚠</span> {e.message}</p> : null;
}
