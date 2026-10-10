import { useEffect, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { qrSvg } from '../lib/qr';
import { all, flush } from '../lib/queue';
import { navigate } from '../lib/router';

export function Link({ to, children, className }: { to: string; children: ReactNode; className?: string }) {
  return <a href={to} className={className} onClick={(e) => { e.preventDefault(); navigate(to); }}>{children}</a>;
}

export function QR({ url, label }: { url: string; label: string }) {
  return (
    <figure style={{ margin: 0 }}>
      <div className="qr" role="img" aria-label={label} dangerouslySetInnerHTML={{ __html: qrSvg(url) }} />
      <figcaption className="small" style={{ marginTop: 6, fontWeight: 600 }}>{label}</figcaption>
    </figure>
  );
}

const CHIP_KIND: Record<string, ['ok' | 'weak' | 'none', string]> = {
  BOTH_PARTIES_CONFIRMED: ['ok', '✔✔'], HANDLER_CONFIRMED: ['ok', '✔'],
  SAME_DEVICE_CONFIRMED: ['weak', '⚠'], BUYER_REPORTED: ['none', '✎'],
};

/** Confirmation chip: icon plus text, never colour alone (CONTRACT §3). */
export function Chip({ status }: { status: string }) {
  const { t } = useTranslation();
  const [kind, icon] = CHIP_KIND[status] ?? ['none', '•'];
  return <span className={`chip ${kind}`}><span aria-hidden="true">{icon}</span>{t(`chip.${status}`)}</span>;
}

export function QueueBanner() {
  const { t } = useTranslation();
  const [n, setN] = useState(0);
  useEffect(() => {
    const refresh = () => { void all().then((j) => setN(j.length)); };
    refresh();
    window.addEventListener('oae-queue', refresh);
    window.addEventListener('online', refresh);
    window.addEventListener('offline', refresh);
    return () => { window.removeEventListener('oae-queue', refresh); window.removeEventListener('online', refresh); window.removeEventListener('offline', refresh); };
  }, []);
  if (!n) return null;
  return (
    <div className="banner" role="status">
      <span>⏳ {t('queue.waiting', { count: n })}</span>
      {navigator.onLine && <button className="btn secondary" style={{ minHeight: 40 }} onClick={() => void flush()}>{t('queue.sendNow')}</button>}
    </div>
  );
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): { data?: T; error?: any; loading: boolean; reload: () => void } {
  const [state, set] = useState<{ data?: T; error?: any; loading: boolean }>({ loading: true });
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    set((s) => ({ ...s, loading: true }));
    fn().then((data) => live && set({ data, loading: false }), (error) => live && set({ error, loading: false }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n]);
  return { ...state, reload: () => setN((x) => x + 1) };
}

export function ErrorText({ error }: { error: any }) {
  const { t } = useTranslation();
  if (!error) return null;
  return <p className="error" role="alert">⚠ {error.status === 403 ? t('err.forbidden') : (error.message || t('err.generic'))}</p>;
}
