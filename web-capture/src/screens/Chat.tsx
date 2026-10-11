import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { get, post, uploadEvidence, ApiError } from '../lib/api';
import { deviceId, ulid } from '../lib/ids';
import { Link, QR, Chip } from '../components/ui';
import { Icon } from '../components/Icon';

type Card = {
  draft_id: string; status: 'READY' | 'TRANSCRIBING' | 'FAILED'; transcript?: string; material?: string;
  fields?: { count: number | null; weight_kg: number | null; source_category: string | null; gas_type?: string | null; charge_kg?: number | null };
  weight_basis?: string; uncertain_fields?: string[]; readback?: { en: string; hi: string }; error?: string;
};
type Msg =
  | { id: string; from: 'me'; text: string }
  | { id: string; from: 'bot'; text: string; privacy?: boolean }
  | { id: string; from: 'bot'; card: Card; done?: boolean }
  | { id: string; from: 'bot'; receipt: any };

const SOURCES = ['DRIVER', 'HOUSEHOLD', 'TECHNICIAN', 'RETAIL_EXCHANGE', 'INSTITUTION', 'OTHER', 'UNKNOWN'];
const MATERIALS = ['BATTERY_LEAD_ACID', 'EWASTE_PHONE', 'AC_REFRIGERANT'];
// Off where Amazon Transcribe is unavailable to the deployment; the chat is then typed only.
const VOICE = (import.meta.env.VITE_VOICE as string | undefined) !== 'off';

export default function Chat() {
  const { t, i18n } = useTranslation();
  const [msgs, setMsgs] = useState<Msg[]>([{ id: 'hello', from: 'bot', text: t(VOICE ? 'chat.hello' : 'chat.helloTyped'), privacy: true }]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const bottom = useRef<HTMLDivElement>(null);
  const online = useOnline();

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);
  const add = (m: Msg) => setMsgs((xs) => [...xs, m]);
  const replace = (id: string, m: Msg) => setMsgs((xs) => xs.map((x) => (x.id === id ? m : x)));
  const fail = (e: unknown) => add({ id: ulid(), from: 'bot', text: e instanceof ApiError ? e.message : t('err.generic') });

  async function sendText() {
    const v = text.trim();
    if (!v || busy) return;
    setText(''); setBusy(true);
    add({ id: ulid(), from: 'me', text: v });
    try {
      const card: Card = await post('/chat/messages', { text: v, device_id: deviceId() });
      add({ id: card.draft_id, from: 'bot', card });
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  async function startRec() {
    if (recording || busy) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg', 'audio/mp4'].find((m) => MediaRecorder.isTypeSupported(m)) ?? '';
      const r = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunks.current = [];
      r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      r.onstop = () => { stream.getTracks().forEach((tr) => tr.stop()); void sendVoice(new Blob(chunks.current, { type: (r.mimeType || 'audio/webm').split(';')[0] })); };
      r.start();
      rec.current = r; setRecording(true);
      navigator.vibrate?.(30);
    } catch { add({ id: ulid(), from: 'bot', text: t('chat.micDenied') }); }
  }
  function stopRec() {
    if (!rec.current) return;
    rec.current.stop(); rec.current = null; setRecording(false);
  }

  async function sendVoice(blob: Blob) {
    if (blob.size < 2000) return; // a tap, not a recording
    setBusy(true);
    const me = ulid();
    add({ id: me, from: 'me', text: '🎤 ' + Math.max(1, Math.round(blob.size / 4000)) + 's' });
    try {
      const evidence_id = await uploadEvidence(blob, 'AUDIO');
      let card: Card = await post('/chat/messages', { evidence_id, device_id: deviceId() });
      add({ id: card.draft_id, from: 'bot', card });
      for (let i = 0; i < 60 && card.status === 'TRANSCRIBING'; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        card = await get(`/chat/drafts/${card.draft_id}`);
      }
      replace(card.draft_id, { id: card.draft_id, from: 'bot', card });
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  async function confirm(card: Card, edits: Partial<NonNullable<Card['fields']>> & { material?: string }) {
    setBusy(true);
    try {
      const { material, ...fields } = edits;
      const r = await post(`/chat/drafts/${card.draft_id}/confirm`, { fields, material, device_id: deviceId(), at_device: new Date().toISOString() });
      replace(card.draft_id, { id: card.draft_id, from: 'bot', card, done: true });
      add({ id: ulid(), from: 'me', text: '✅ ' + t('chat.confirm') });
      add({ id: ulid(), from: 'bot', receipt: r });
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  return (
    <div className="chat">
      {!online && <div className="banner" role="status"><Icon name="wifiOff" size={18} /> {t('chat.offline')}</div>}
      <div className="msgs" aria-live="polite">
        {msgs.map((m) => {
          if ('card' in m) return <DraftCard key={m.id} card={m.card} done={m.done} busy={busy} onConfirm={(e) => confirm(m.card, e)} />;
          if ('receipt' in m) return <ReceiptCard key={m.id} r={m.receipt} />;
          return (
            <div key={m.id} className={`bubble ${m.from}`}>
              {m.text}
              {'privacy' in m && m.privacy && <div className="small" style={{ marginTop: 6 }}><Link to="/privacy">{t('chat.privacyLink')}</Link></div>}
            </div>
          );
        })}
        {busy && <div className="bubble bot muted" aria-label="…"><span className="live-dot" /> <span className="live-dot" style={{ animationDelay: '.2s' }} /> <span className="live-dot" style={{ animationDelay: '.4s' }} /></div>}
        <div ref={bottom} />
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); void sendText(); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={recording ? t('chat.recording') : t('chat.placeholder')}
          aria-label={t('chat.placeholder')} lang={i18n.language} enterKeyHint="send" disabled={!online} />
        {text.trim() || !VOICE
          ? <button className="send" type="submit" aria-label="Send" disabled={busy || !text.trim()}><Icon name="send" /></button>
          : <button type="button" className={`mic ${recording ? 'rec' : ''}`} aria-label={t('chat.hold')} title={t('chat.hold')}
              disabled={!online || busy}
              onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); void startRec(); }}
              onPointerUp={stopRec} onPointerCancel={stopRec} onContextMenu={(e) => e.preventDefault()}><Icon name="mic" /></button>}
      </form>
    </div>
  );
}

function DraftCard({ card, done, busy, onConfirm }: { card: Card; done?: boolean; busy: boolean; onConfirm: (edits: any) => void }) {
  const { t, i18n } = useTranslation();
  const [editing, setEditing] = useState(false);
  const f = card.fields ?? { count: null, weight_kg: null, source_category: null };
  const [count, setCount] = useState(f.count ?? '');
  const [kg, setKg] = useState(f.weight_kg ?? '');
  const [src, setSrc] = useState(f.source_category ?? 'UNKNOWN');
  const [mat, setMat] = useState(card.material && card.material !== 'UNKNOWN' ? card.material : '');
  if (card.status === 'TRANSCRIBING') return <div className="bubble bot">🎧 {t('chat.listening')}</div>;
  if (card.status === 'FAILED') return <div className="bubble bot error">{card.error || t('chat.failed')}</div>;
  const unc = new Set(card.uncertain_fields ?? []);
  const needsMaterial = !mat;
  const Q = ({ k }: { k: string }) => (unc.has(k) ? <span className="flag-uncertain"> ? {t('chat.uncertain')}</span> : null);
  const primary = i18n.language === 'hi' ? card.readback?.hi : card.readback?.en;
  const secondary = i18n.language === 'hi' ? card.readback?.en : card.readback?.hi;
  return (
    <div className="bubble bot wide">
      {card.transcript && <p className="small muted" style={{ marginTop: 0 }}>“{card.transcript}”</p>}
      <p style={{ margin: '0 0 8px', fontWeight: 600 }}>{primary}</p>
      <p className="small muted" style={{ marginTop: 0 }}>{secondary}</p>
      {!editing ? (
        <>
          <div className="card-row"><span>{t('chat.material')}<Q k="material" /></span><span className="big" style={{ fontSize: 17 }}>{mat ? t(`mat.${mat}`) : '—'}</span></div>
          <div className="card-row"><span>{t('chat.count')}<Q k="count" /></span><span className="big">{count === '' ? '—' : count}</span></div>
          {mat !== 'AC_REFRIGERANT' && <div className="card-row"><span>{t('chat.weight')}<Q k="weight_kg" /></span><span className="big">{kg === '' ? '—' : kg}</span></div>}
          <div className="card-row"><span>{t('chat.source')}<Q k="source_category" /></span><span style={{ fontWeight: 700 }}>{t(`src.${src}`)}</span></div>
          {!done && (
            <div className="actions">
              <button className="btn secondary" onClick={() => setEditing(true)} disabled={busy}>✏️ {t('chat.edit')}</button>
              <button className="btn green" disabled={busy || needsMaterial || count === ''}
                onClick={() => onConfirm({ count: Number(count), ...(kg === '' ? {} : { weight_kg: Number(kg) }), source_category: src, material: mat })}>
                ✅ {t('chat.confirm')}
              </button>
            </div>
          )}
        </>
      ) : (
        <div>
          <label htmlFor={`m-${card.draft_id}`}>{t('chat.material')}</label>
          <select id={`m-${card.draft_id}`} value={mat} onChange={(e) => setMat(e.target.value)}>
            <option value="">—</option>{MATERIALS.map((m) => <option key={m} value={m}>{t(`mat.${m}`)}</option>)}
          </select>
          <label htmlFor={`c-${card.draft_id}`}>{t('chat.count')}</label>
          <input id={`c-${card.draft_id}`} inputMode="numeric" value={count} onChange={(e) => setCount(e.target.value.replace(/\D/g, ''))} />
          {mat !== 'AC_REFRIGERANT' && <>
            <label htmlFor={`w-${card.draft_id}`}>{t('chat.weight')}</label>
            <input id={`w-${card.draft_id}`} inputMode="decimal" value={kg} onChange={(e) => setKg(e.target.value.replace(/[^\d.]/g, ''))} />
          </>}
          <label htmlFor={`s-${card.draft_id}`}>{t('chat.source')}</label>
          <select id={`s-${card.draft_id}`} value={src} onChange={(e) => setSrc(e.target.value)}>
            {SOURCES.map((s) => <option key={s} value={s}>{t(`src.${s}`)}</option>)}
          </select>
          <div className="actions"><button className="btn" onClick={() => setEditing(false)}>{t('chat.save')}</button></div>
        </div>
      )}
    </div>
  );
}

function ReceiptCard({ r }: { r: any }) {
  const { t } = useTranslation();
  const sellerUrl = r.wa_confirm_link || r.confirm_url;
  return (
    <div className="bubble bot wide">
      <p className="saved"><span className="tick"><Icon name="check" size={18} /></span>{t('chat.saved')}</p>
      <p className="small"><Link to={`/b/${r.batch_id}`}>{r.batch_id}</Link> · <Chip status={r.event?.confirmation?.status ?? 'BUYER_REPORTED'} /></p>
      <div className="qrs">
        <QR url={r.receipt_url} label={'① ' + t('chat.nextHandler')} />
        {sellerUrl && <QR url={sellerUrl} label={'② ' + t('chat.seller')} />}
      </div>
      {sellerUrl && <p className="small">{t('chat.sellerHint')}</p>}
      {r.confirm_url && <p className="small">{t('chat.shareLink')}: <a href={r.confirm_url} className="mono">{r.confirm_url}</a></p>}
      {r.receipt_note && <div className="callout small">{r.receipt_note.hi}<br />{r.receipt_note.en}</div>}
    </div>
  );
}

function useOnline() {
  const [on, set] = useState(navigator.onLine);
  useEffect(() => {
    const a = () => set(true), b = () => set(false);
    window.addEventListener('online', a); window.addEventListener('offline', b);
    return () => { window.removeEventListener('online', a); window.removeEventListener('offline', b); };
  }, []);
  return on;
}
