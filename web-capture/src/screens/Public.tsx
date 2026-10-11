import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { get, post, ApiError } from '../lib/api';
import { deviceId } from '../lib/ids';
import { setLang } from '../i18n';
import { ErrorText, Link, useAsync } from '../components/ui';
import { Icon } from '../components/Icon';

function ChainLine({ n, bad }: { n: number; bad: number | null }) {
  const k = Math.max(1, Math.min(n || 1, 7));
  return (
    <div className="chainline" aria-hidden="true">
      {Array.from({ length: k }).map((_, i) => {
        const broken = bad !== null && i + 1 >= bad;
        return <span key={i} style={{ display: 'contents' }}>{i > 0 && <i />}<b className={broken ? 'bad' : ''}><Icon name={broken ? 'alert' : 'check'} size={14} /></b></span>;
      })}
    </div>
  );
}

/** /r/<token>: public, printable, no names. */
export function Receipt({ token }: { token: string }) {
  const { t, i18n } = useTranslation();
  const { data, error, loading } = useAsync(() => get(`/r/${encodeURIComponent(token)}`), [token]);
  if (loading) return <main><p className="muted">…</p></main>;
  if (error) return <main><ErrorText error={error} /></main>;
  const lang = i18n.language as 'hi' | 'en';
  return (
    <main>
      <span className="eyebrow">{t('receipt.title')}</span>
      <h2 className="mono" style={{ fontSize: 30, marginTop: 4 }}>{data.batch_id}</h2>
      <div className="ticket">
      <dl className="kv" style={{ fontSize: 18 }}>
        <dt>{t('chat.material')}</dt><dd>{data.material_label?.[lang]}</dd>
        <dt>{t('receipt.count')}</dt><dd>{data.count ?? '—'}</dd>
        {data.approx_weight_kg != null && <><dt>{t('receipt.weight')}</dt><dd>~{data.approx_weight_kg} kg</dd></>}
        <dt>{t('receipt.date')}</dt><dd>{data.date}</dd>
      </dl>
      </div>
      <div className="seal">
        <span className={`ring ${data.chain.ok ? '' : 'bad'}`}><Icon name={data.chain.ok ? 'check' : 'alert'} /></span>
        <p className={data.chain.ok ? 'ok-big' : 'bad-big'}>
          {data.chain.ok ? t('receipt.chainOk', { n: data.chain.checked }) : t('receipt.chainBad', { seq: data.chain.failed_at_seq })}
        </p>
        <ChainLine n={data.chain.checked} bad={data.chain.ok ? null : data.chain.failed_at_seq} />
      </div>
      {data.confirmation && <p>{data.confirmation[lang]}</p>}
      {data.note && <div className="callout">{data.note[lang]}</div>}
      <h2>{t('receipt.steps')}</h2>
      <ol>{data.steps.map((s: any) => <li key={s.seq}>{t(`type.${s.type}`)} · {s.date}{s.by_role ? ` · ${s.by_role}` : ''}</li>)}</ol>
      <p className="small muted">{t('receipt.noNames')}</p>
      <div className="actions no-print">
        <button className="btn secondary" onClick={() => window.print()}><Icon name="print" />{t('receipt.print')}</button>
        <Link className="btn secondary" to={`/v/${data.batch_id}`}><Icon name="shield" />{t('batch.verify')}</Link>
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
  if (result) return <main><div className="seal"><span className="ring"><Icon name="check" /></span><p className="ok-big" style={{ fontSize: 28 }}>{result === 'yes' ? '✔ ' + t('confirm.done') : t('confirm.rejected')}</p></div></main>;
  return (
    <main style={{ textAlign: 'center' }}>
      <div style={{ textAlign: 'right' }}>{langBtn}</div>
      <p className="confirm-q" style={{ fontSize: 28, margin: '8px 0' }}>{t('confirm.what')}</p>
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
      <span className="eyebrow">{t('verify.title')}</span>
      <h2 className="mono" style={{ fontSize: 30, marginTop: 4 }}>{data.batch_id}</h2>
      <div className="seal">
        <span className={`ring ${data.ok ? '' : 'bad'}`}><Icon name={data.ok ? 'check' : 'alert'} /></span>
        <p className={data.ok ? 'ok-big' : 'bad-big'} role="status">
          {data.ok ? '✔ ' + t('verify.ok', { checked: data.checked }) : '✖ ' + t('verify.bad', { seq: data.failed_at_seq })}
        </p>
        <ChainLine n={data.checked} bad={data.ok ? null : data.failed_at_seq} />
        {!data.ok && <p className="small" style={{ margin: 0 }}>{t('verify.reason')}: <span className="mono">{data.reason}</span></p>}
        <button className="btn secondary" style={{ minHeight: 42 }} onClick={reload} aria-label="Check again"><Icon name="refresh" size={17} />{t('verify.again')}</button>
      </div>
      <div className="callout small" style={{ display: 'flex', gap: 10 }}><Icon name="link" size={18} style={{ color: 'var(--forest)', marginTop: 2 }} /><span>{t('verify.explain')}</span></div>
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
