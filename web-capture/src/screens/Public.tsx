import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { get, post, ApiError } from '../lib/api';
import { deviceId } from '../lib/ids';
import { setLang } from '../i18n';
import { ErrorText, Link, useAsync } from '../components/ui';

/** /r/<token>: public, printable, no names. */
export function Receipt({ token }: { token: string }) {
  const { t, i18n } = useTranslation();
  const { data, error, loading } = useAsync(() => get(`/r/${encodeURIComponent(token)}`), [token]);
  if (loading) return <main><p className="muted">…</p></main>;
  if (error) return <main><ErrorText error={error} /></main>;
  const lang = i18n.language as 'hi' | 'en';
  return (
    <main>
      <h2>🧾 {t('receipt.title')} · {data.batch_id}</h2>
      <dl className="kv" style={{ fontSize: 18 }}>
        <dt>{t('chat.material')}</dt><dd>{data.material_label?.[lang]}</dd>
        <dt>{t('receipt.count')}</dt><dd>{data.count ?? '—'}</dd>
        {data.approx_weight_kg != null && <><dt>{t('receipt.weight')}</dt><dd>~{data.approx_weight_kg} kg</dd></>}
        <dt>{t('receipt.date')}</dt><dd>{data.date}</dd>
      </dl>
      <p className={data.chain.ok ? 'ok-big' : 'bad-big'}>
        {data.chain.ok ? '✔ ' + t('receipt.chainOk', { n: data.chain.checked }) : '✖ ' + t('receipt.chainBad', { seq: data.chain.failed_at_seq })}
      </p>
      {data.confirmation && <p>{data.confirmation[lang]}</p>}
      {data.note && <div className="callout">{data.note[lang]}</div>}
      <h2>{t('receipt.steps')}</h2>
      <ol>{data.steps.map((s: any) => <li key={s.seq}>{t(`type.${s.type}`)} · {s.date}{s.by_role ? ` · ${s.by_role}` : ''}</li>)}</ol>
      <p className="small muted">{t('receipt.noNames')}</p>
      <div className="actions no-print">
        <button className="btn secondary" onClick={() => window.print()}>🖨 {t('receipt.print')}</button>
        <Link className="btn secondary" to={`/v/${data.batch_id}`}>🔗 {t('batch.verify')}</Link>
      </div>
    </main>
  );
}

/** /c/<token>: Hindi first, big type, two big buttons, asks for nothing personal. */
export function Confirm({ token }: { token: string }) {
  const { t, i18n } = useTranslation();
  const [result, setResult] = useState<string | null>(null);
  const [err, setErr] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const { data, error, loading } = useAsync(() => get(`/confirm/${encodeURIComponent(token)}`), [token]);
  const lang = i18n.language as 'hi' | 'en';
  async function answer(a: 'yes' | 'no') {
    setBusy(true);
    try { await post(`/confirm/${encodeURIComponent(token)}`, { answer: a, device_id: deviceId() }); setResult(a); }
    catch (e) { setErr(e); } finally { setBusy(false); }
  }
  const langBtn = <button className="btn secondary" style={{ minHeight: 40 }} onClick={() => setLang(lang === 'hi' ? 'en' : 'hi')}>{t('lang')}</button>;
  if (loading) return <main><p className="muted">…</p></main>;
  if (error) {
    const code = (error as ApiError).code;
    return <main>{langBtn}<p className="big">{code === 'TOKEN_USED' ? t('confirm.used') : code === 'TOKEN_EXPIRED' ? t('confirm.expired') : t('err.generic')}</p></main>;
  }
  if (result) return <main><p className="ok-big" style={{ fontSize: 28 }}>{result === 'yes' ? '✔ ' + t('confirm.done') : t('confirm.rejected')}</p></main>;
  return (
    <main style={{ textAlign: 'center' }}>
      <div style={{ textAlign: 'right' }}>{langBtn}</div>
      <p style={{ fontSize: 22, fontWeight: 700, margin: '8px 0' }}>{t('confirm.what')}</p>
      <p style={{ fontSize: 40, fontWeight: 800, margin: '8px 0', lineHeight: 1.15 }}>
        {data.count} {data.unit_label?.[lang]}
      </p>
      <p style={{ fontSize: 22, margin: 0 }}>{data.material_label?.[lang]}</p>
      {data.approx_weight_kg != null && <p style={{ fontSize: 26, fontWeight: 700 }}>~{data.approx_weight_kg} {lang === 'hi' ? 'किलो' : 'kg'}</p>}
      <p className="muted">{data.date}</p>
      <div className="grid" style={{ marginTop: 16 }}>
        <button className="btn green block" style={{ minHeight: 72, fontSize: 20 }} disabled={busy} onClick={() => answer('yes')}>{t('confirm.yes')}</button>
        <button className="btn secondary block" style={{ minHeight: 64, fontSize: 18 }} disabled={busy} onClick={() => answer('no')}>{t('confirm.no')}</button>
      </div>
      <ErrorText error={err} />
      <p className="small muted" style={{ marginTop: 20 }}>{data.purpose?.[lang]} <Link to="/privacy">{t('home.privacy')}</Link></p>
    </main>
  );
}

/** /v/<batch_id>: public chain check. This is where the tamper demo is shown. */
export function Verify({ id }: { id: string }) {
  const { t } = useTranslation();
  const { data, error, loading, reload } = useAsync(() => get(`/verify/${encodeURIComponent(id)}`), [id]);
  if (loading) return <main><p className="muted">…</p></main>;
  if (error) return <main><ErrorText error={error} /></main>;
  return (
    <main>
      <h2>{t('verify.title')} · {data.batch_id}</h2>
      <p className={data.ok ? 'ok-big' : 'bad-big'} style={{ fontSize: 24 }} role="status">
        {data.ok ? '✔ ' + t('verify.ok', { checked: data.checked }) : '✖ ' + t('verify.bad', { seq: data.failed_at_seq })}
      </p>
      {!data.ok && <p>{t('verify.reason')}: <span className="mono">{data.reason}</span></p>}
      <p><button className="btn secondary" onClick={reload}>↻</button></p>
      <div className="callout small">{t('verify.explain')}</div>
      {data.digest && <>
        <h2>{t('verify.digest')}</h2>
        <p className="small">{data.digest.date} · {data.digest.count} events</p>
        <p className="mono">{data.digest.root}</p>
      </>}
      <details><summary>{t('verify.key')}</summary><pre className="mono">{data.public_key_pem}</pre></details>
    </main>
  );
}

export function Privacy() {
  const { t } = useTranslation();
  const lines = t('privacy.body', { returnObjects: true }) as string[];
  return (
    <main>
      <h2>{t('privacy.title')}</h2>
      <ul>{lines.map((l) => <li key={l} style={{ marginBottom: 8 }}>{l}</li>)}</ul>
      <p className="small muted">All data, including text read by Amazon Bedrock, is stored and processed in AWS region {(import.meta.env.VITE_AWS_REGION as string) || 'ap-southeast-2'}{((import.meta.env.VITE_AWS_REGION as string) || 'ap-southeast-2') === 'ap-southeast-2' ? ' (Sydney, Australia), outside India. This demo uses synthetic data only.' : '.'}</p>
    </main>
  );
}
