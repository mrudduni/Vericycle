import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getSession } from '../lib/session';
import { sendOrQueue } from '../lib/queue';
import { ApiError } from '../lib/api';
import { navigate } from '../lib/router';
import { ErrorText } from '../components/ui';

const METALS = ['LEAD', 'COPPER', 'ALUMINIUM', 'IRON', 'GOLD'];

export default function EventForm({ id, type }: { id: string; type: string }) {
  const { t } = useTranslation();
  const s = getSession();
  const T = type.toUpperCase();
  const [v, setV] = useState<Record<string, string>>({ facility_id: s?.party_id ?? '', metal: 'LEAD' });
  const [photo, setPhoto] = useState<Blob | null>(null);
  const [err, setErr] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: any) => setV({ ...v, [k]: e.target.value });

  function body(): any {
    const num = (k: string) => Number(v[k]);
    switch (T) {
      case 'TRANSFER': return { counterparty_party_id: v.to || null, fields: { weight_kg: num('weight_kg') } };
      case 'INTAKE': return { fields: { weight_kg: num('weight_kg'), facility_id: v.facility_id } };
      case 'SPLIT': return { fields: { child_weights_kg: (v.children ?? '').split(/\s+/).filter(Boolean).map(Number) } };
      case 'MERGE': return { parent_batch_ids: (v.parents ?? '').split(/\s+/).filter(Boolean).map((x) => x.toUpperCase()), fields: { weight_kg: num('weight_kg') } };
      case 'PROCESS': return { fields: { input_kg: num('input_kg'), run_id: v.run_id } };
      case 'OUTPUT': return { fields: { metal: v.metal, output_kg: num('output_kg') } };
      case 'CORRECTION': return { fields: { corrects_seq: num('corrects_seq'), field: v.field, new_value: v.new_value, reason: v.reason } };
    }
    return {};
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null); setMsg(null);
    try {
      const r = await sendOrQueue({
        path: `/batches/${encodeURIComponent(id)}/events`,
        body: { type: T, at_device: new Date().toISOString(), ...body() },
        photo: photo ?? undefined, photoKind: 'WEIGH_SLIP', batchId: id,
      });
      if (r === null) { setMsg(t('form.queued')); return; }
      if (r.warnings?.some((w: any) => w.code === 'NO_UPSTREAM_EVENT')) setMsg(t('form.noUpstream'));
      else navigate(T === 'MERGE' ? `/b/${r.batch_id}` : `/b/${id}`);
    } catch (e2) { setErr(e2 instanceof ApiError ? e2 : { message: t('err.generic') }); } finally { setBusy(false); }
  }

  const kg = <><label htmlFor="kg">{t('form.kg')}</label><input id="kg" required inputMode="decimal" value={v.weight_kg ?? ''} onChange={set('weight_kg')} /></>;
  return (
    <main>
      <h2>{t(`batch.${T}`)} · {id}</h2>
      <form onSubmit={submit}>
        {T === 'TRANSFER' && <>{kg}<label htmlFor="to">{t('form.to')}</label><input id="to" value={v.to ?? ''} onChange={set('to')} placeholder="AGG-01" /></>}
        {T === 'INTAKE' && <>{kg}<label htmlFor="fac">{t('form.facility')}</label><input id="fac" value={v.facility_id} onChange={set('facility_id')} />
          <Camera onPhoto={setPhoto} /></>}
        {T === 'SPLIT' && <><label htmlFor="ch">{t('form.children')}</label><textarea id="ch" required inputMode="decimal" value={v.children ?? ''} onChange={set('children')} placeholder={'60\n58'} /></>}
        {T === 'MERGE' && <><label htmlFor="pa">{t('form.parents')}</label><textarea id="pa" required value={v.parents ?? ''} onChange={set('parents')} />{kg}</>}
        {T === 'PROCESS' && <><label htmlFor="in">{t('form.input')}</label><input id="in" required inputMode="decimal" value={v.input_kg ?? ''} onChange={set('input_kg')} />
          <label htmlFor="run">{t('form.run')}</label><input id="run" required value={v.run_id ?? ''} onChange={set('run_id')} /></>}
        {T === 'OUTPUT' && <><label htmlFor="me">{t('form.metal')}</label><select id="me" value={v.metal} onChange={set('metal')}>{METALS.map((m) => <option key={m}>{m}</option>)}</select>
          <label htmlFor="out">{t('form.output')}</label><input id="out" required inputMode="decimal" value={v.output_kg ?? ''} onChange={set('output_kg')} /></>}
        {T === 'CORRECTION' && <><label htmlFor="cs">{t('form.correctsSeq')}</label><input id="cs" required inputMode="numeric" value={v.corrects_seq ?? ''} onChange={set('corrects_seq')} />
          <label htmlFor="fi">{t('form.field')}</label><input id="fi" required value={v.field ?? ''} onChange={set('field')} placeholder="weight_kg" />
          <label htmlFor="nv">{t('form.newValue')}</label><input id="nv" required value={v.new_value ?? ''} onChange={set('new_value')} />
          <label htmlFor="re">{t('form.reason')}</label><input id="re" required value={v.reason ?? ''} onChange={set('reason')} /></>}
        <ErrorText error={err} />
        {msg && <p className="callout" role="status">{msg}</p>}
        <p><button className="btn green block" disabled={busy}>{t('form.send')}</button></p>
      </form>
    </main>
  );
}

/** In-app camera (F2): capture to canvas, the blob is hashed with WebCrypto before upload. */
function Camera({ onPhoto }: { onPhoto: (b: Blob | null) => void }) {
  const { t } = useTranslation();
  const video = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [shot, setShot] = useState<string | null>(null);
  useEffect(() => () => stream?.getTracks().forEach((x) => x.stop()), [stream]);
  async function start() {
    try {
      const st = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1600 } } });
      setStream(st); setShot(null); onPhoto(null);
      requestAnimationFrame(() => { if (video.current) { video.current.srcObject = st; void video.current.play(); } });
    } catch { alertless(); }
  }
  function alertless() { setShot(null); }
  function take() {
    const vid = video.current; if (!vid) return;
    const c = document.createElement('canvas');
    c.width = vid.videoWidth; c.height = vid.videoHeight;
    c.getContext('2d')!.drawImage(vid, 0, 0);
    c.toBlob((b) => { if (b) { onPhoto(b); setShot(URL.createObjectURL(b)); } }, 'image/jpeg', 0.85);
    stream?.getTracks().forEach((x) => x.stop()); setStream(null);
  }
  return (
    <div style={{ marginTop: 12 }}>
      {stream && <><video ref={video} playsInline muted /><p><button type="button" className="btn block" onClick={take}>📸</button></p></>}
      {shot && <img src={shot} className="photo" alt="" />}
      {!stream && <p><button type="button" className="btn secondary block" onClick={start}>📷 {shot ? t('form.retake') : t('form.photo')}</button></p>}
      <p className="small muted">{t('form.hashNote')}</p>
    </div>
  );
}
