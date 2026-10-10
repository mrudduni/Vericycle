import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { get } from '../lib/api';
import { navigate } from '../lib/router';
import { OpenBatch } from './Batch';

/** QR scan: BarcodeDetector where available, otherwise @zxing/browser loaded only on demand. */
export default function Scan() {
  const { t } = useTranslation();
  const video = useRef<HTMLVideoElement>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let stop = () => {};
    let done = false;
    async function onText(text: string) {
      if (done) return;
      const m = text.match(/\/r\/([A-Za-z0-9_-]{10,40})/);
      if (!m) return;
      done = true;
      try { const r = await get(`/r/${m[1]}`); navigate(`/b/${r.batch_id}`); } catch { done = false; }
    }
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
        stop = () => stream.getTracks().forEach((x) => x.stop());
        const v = video.current!;
        v.srcObject = stream; await v.play();
        const BD = (window as any).BarcodeDetector;
        if (BD) {
          const det = new BD({ formats: ['qr_code'] });
          const loop = async () => {
            if (done || !video.current) return;
            try { const codes = await det.detect(v); if (codes[0]) await onText(codes[0].rawValue); } catch { /* frame not ready */ }
            setTimeout(loop, 250);
          };
          void loop();
        } else {
          const { BrowserQRCodeReader } = await import('@zxing/browser');
          const reader = new BrowserQRCodeReader();
          const ctl = await reader.decodeFromVideoElement(v, (res) => { if (res) void onText(res.getText()); });
          const prev = stop; stop = () => { ctl.stop(); prev(); };
        }
      } catch { setErr(t('scan.noCamera')); }
    })();
    return () => { done = true; stop(); };
  }, [t]);

  return (
    <>
      <main style={{ paddingBottom: 0 }}>
        <h2>{t('scan.title')}</h2>
        {err ? <p className="callout">{err}</p> : <video ref={video} playsInline muted aria-label={t('scan.title')} />}
      </main>
      <OpenBatch />
    </>
  );
}
