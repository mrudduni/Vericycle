// Public front door: the story, live numbers from the ledger, a batch lookup, and the way into each app.
import { useEffect, useRef, useState } from 'react';
import { getImpact } from '../lib/api';
import { useLang } from '../lib/i18n';
import { useSession } from '../lib/session';
import type { Metric } from '../lib/types';
import { Icon, type IconName } from '../components/Icon';
import { DemoBadge, fmtNum } from '../components/ui';

export const CAPTURE_WEB = ((import.meta.env.VITE_CAPTURE_WEB_URL as string | undefined) ?? '').replace(/\/$/, '');
const CAPTURE_API = ((import.meta.env.VITE_CAPTURE_API_URL as string | undefined) ?? '').replace(/\/$/, '');

interface VerifyResult { batch_id: string; ok: boolean; checked: number; failed_at_seq: number | null; reason: string | null }

const C = {
  en: {
    eyebrow: 'Proof of recycling for batteries and e-waste in India',
    h1a: 'Recycling you can', h1b: 'check', h1c: ', from the very first handover.',
    lede: 'India certifies recycling from documents the recycler uploads about itself. Vericycle records the first handover on a phone, chains every transfer with a signature, and checks each recycling claim against arithmetic and evidence.',
    ctaReview: 'Review claims', ctaCollector: 'Open the collector app', ctaVerify: 'Verify a batch',
    t1: 'Every number cites its source', t2: 'No informal worker is ever named', t3: 'AI explains, never decides',
    liveLedger: 'Live from the ledger', chainOk: (n: number) => `Chain intact: ${n} of ${n} signed records check out`,
    chainBad: (s: number | null) => `Chain broken at record ${s}`, signed: 'Each record is hash-chained and signed with AWS KMS.',
    example: 'Example · claim C-105', exTitle: 'Photo light contradicts its timestamp',
    exBody: 'Stamped 20:22 IST in Hapur, about an hour after sunset, yet the photo shows hard sun shadows.',
    observed: 'Observed', limit: 'Limit', exObs: 'Direct sun', exLim: 'Sun below horizon',
    impactEyebrow: 'Live impact', impactH: 'What the custody ledger shows right now',
    impactP: 'Counted from signed records and ClaimGuard runs. Figures marked DEMO VALUE use a placeholder parameter, and say so.',
    howEyebrow: 'How it works', howH: 'From a scrap dealer’s phone to an auditor’s desk',
    howP: 'Four steps, one shared record. Nobody has to trust anybody’s spreadsheet.',
    steps: [
      { i: 'chat', h: 'Record the handover', p: 'A collector types or says what they bought, in Hindi or English. The seller confirms on their own phone, without giving a name.', by: 'Collector · seller' },
      { i: 'link', h: 'Chain the custody', p: 'Every transfer, split and intake is a new event: hash-chained, signed with KMS, and digested daily into write-once storage.', by: 'Aggregator · recycler' },
      { i: 'file', h: 'Submit the claim', p: 'The recycler claims tonnage for a period and cites the batches, photos, weigh slips and power bills behind it.', by: 'Recycler' },
      { i: 'scale', h: 'Check it, in the open', p: 'Nine rules test capacity, mass balance, energy, custody, photo light and duplicates. Each flag shows observed value, limit and source.', by: 'Auditor · producer' },
    ] as { i: IconName; h: string; p: string; by: string }[],
    verifyEyebrow: 'Public verification', verifyH: 'Check any batch yourself',
    verifyP: 'Anyone holding a receipt can verify that its custody chain has not been edited. No sign-in, no personal data.',
    placeholder: 'Batch ID, e.g. B-0042', check: 'Check', tryOne: 'Try:', openFull: 'Open the full public record',
    idle: 'Enter a batch ID to recompute its hash chain and check every KMS signature, live.',
    notFound: 'No batch with that ID.', unreachable: 'Could not reach the ledger right now.',
    doorsEyebrow: 'Get started', doorsH: 'Choose your door',
    doors: [
      { i: 'scale', tag: 'Auditors · producers · recyclers', h: 'Review dashboard', p: 'Rule results, three separate scores, custody lineage, and a printable report for every claim.', go: 'Sign in to review' },
      { i: 'phone', tag: 'Collectors · aggregators', h: 'Collector app', p: 'A Hindi-first phone app that works offline: record a purchase, hand over a batch, print a receipt.', go: 'Open on your phone' },
      { i: 'leaf', tag: 'Everyone', h: 'Impact', p: 'Lead traced to registered recyclers, batteries with a first-handover record, and the refrigerant harm nobody counts.', go: 'See the numbers' },
    ] as { i: IconName; tag: string; h: string; p: string; go: string }[],
    prEyebrow: 'What we refuse to do', prH: 'Eight rules we built the product around',
    principles: [
      ['Consistency, not certification', 'A claim that passes is “consistent with available data”. We never certify anything.'],
      ['Missing data is not wrongdoing', 'Every rule can answer INSUFFICIENT EVIDENCE, and says what would resolve it.'],
      ['No source, no rule', 'Every limit comes from a cited document. Placeholders wear a DEMO VALUE badge.'],
      ['Three scores, never blended', 'Physical consistency, traceability and evidence quality stay separate. There is no single blended score.'],
      ['One-sided is never witnessed', 'Each field shows who stated it and who confirmed it, and on whose phone.'],
      ['Informal workers stay safe', 'No names, IDs or addresses. Phone numbers exist only as keyed hashes.'],
      ['AI explains, never decides', 'Models read text and explain flags with citations. They cannot raise or clear one.'],
      ['History is append-only', 'Corrections are new signed events. Nothing is overwritten.'],
    ],
    awsEyebrow: 'Built on AWS', awsH: 'Serverless, signed and auditable',
  },
  hi: {
    eyebrow: 'भारत में बैटरी और ई-कचरे की रीसाइक्लिंग का सबूत',
    h1a: 'रीसाइक्लिंग जिसे आप', h1b: 'जाँच', h1c: ' सकें, पहले हैंडओवर से ही।',
    lede: 'भारत में रीसाइक्लिंग का प्रमाण उन्हीं कागज़ों से बनता है जो रीसाइक्लर ख़ुद अपलोड करता है। Vericycle पहला हैंडओवर फ़ोन पर दर्ज करता है, हर ट्रांसफ़र को हस्ताक्षर से जोड़ता है, और हर दावे को हिसाब और सबूत से जाँचता है।',
    ctaReview: 'दावों की समीक्षा', ctaCollector: 'कलेक्टर ऐप खोलें', ctaVerify: 'बैच जाँचें',
    t1: 'हर आँकड़े का स्रोत', t2: 'किसी असंगठित कामगार का नाम नहीं', t3: 'AI समझाता है, फ़ैसला नहीं करता',
    liveLedger: 'लेजर से लाइव', chainOk: (n: number) => `चेन सही: ${n} में से ${n} हस्ताक्षरित रिकॉर्ड ठीक`,
    chainBad: (s: number | null) => `रिकॉर्ड ${s} पर चेन टूटी`, signed: 'हर रिकॉर्ड हैश-चेन से जुड़ा और AWS KMS से हस्ताक्षरित है।',
    example: 'उदाहरण · दावा C-105', exTitle: 'फ़ोटो की रोशनी उसके समय से मेल नहीं खाती',
    exBody: 'हापुड़ में 20:22 IST का समय, सूर्यास्त के लगभग एक घंटे बाद, फिर भी फ़ोटो में तेज़ धूप की छाया।',
    observed: 'देखा गया', limit: 'सीमा', exObs: 'सीधी धूप', exLim: 'सूरज क्षितिज के नीचे',
    impactEyebrow: 'लाइव प्रभाव', impactH: 'कस्टडी लेजर अभी क्या दिखाता है',
    impactP: 'हस्ताक्षरित रिकॉर्ड और ClaimGuard जाँच से गिना गया। DEMO VALUE वाले आँकड़े अस्थायी मान पर आधारित हैं, और यह साफ़ लिखा है।',
    howEyebrow: 'यह कैसे काम करता है', howH: 'कबाड़ी के फ़ोन से ऑडिटर की मेज़ तक',
    howP: 'चार कदम, एक साझा रिकॉर्ड। किसी को किसी की स्प्रेडशीट पर भरोसा नहीं करना पड़ता।',
    steps: [
      { i: 'chat', h: 'हैंडओवर दर्ज करें', p: 'कलेक्टर हिंदी या अंग्रेज़ी में लिखता या बोलता है कि क्या ख़रीदा। विक्रेता अपने फ़ोन से पुष्टि करता है, नाम दिए बिना।', by: 'कलेक्टर · विक्रेता' },
      { i: 'link', h: 'कस्टडी की चेन', p: 'हर ट्रांसफ़र, बँटवारा और आमद एक नई घटना है: हैश-चेन, KMS हस्ताक्षर, और रोज़ाना न मिटने वाले स्टोरेज में सार।', by: 'एग्रीगेटर · रीसाइक्लर' },
      { i: 'file', h: 'दावा जमा करें', p: 'रीसाइक्लर किसी अवधि का टन-भार दावा करता है और उसके पीछे के बैच, फ़ोटो, तौल पर्ची और बिजली बिल बताता है।', by: 'रीसाइक्लर' },
      { i: 'scale', h: 'खुलेआम जाँच', p: 'नौ नियम क्षमता, द्रव्यमान संतुलन, बिजली, कस्टडी, फ़ोटो की रोशनी और दोहराव जाँचते हैं। हर फ़्लैग देखा गया मान, सीमा और स्रोत दिखाता है।', by: 'ऑडिटर · उत्पादक' },
    ] as { i: IconName; h: string; p: string; by: string }[],
    verifyEyebrow: 'सार्वजनिक जाँच', verifyH: 'कोई भी बैच ख़ुद जाँचें',
    verifyP: 'रसीद रखने वाला कोई भी देख सकता है कि उसकी कस्टडी चेन बदली नहीं गई। न साइन इन, न निजी जानकारी।',
    placeholder: 'बैच ID, जैसे B-0042', check: 'जाँचें', tryOne: 'आज़माएँ:', openFull: 'पूरा सार्वजनिक रिकॉर्ड खोलें',
    idle: 'बैच ID लिखें: हम उसकी हैश-चेन दोबारा गिनेंगे और हर KMS हस्ताक्षर अभी जाँचेंगे।',
    notFound: 'इस ID का कोई बैच नहीं।', unreachable: 'अभी लेजर तक नहीं पहुँच पाए।',
    doorsEyebrow: 'शुरू करें', doorsH: 'अपना रास्ता चुनें',
    doors: [
      { i: 'scale', tag: 'ऑडिटर · उत्पादक · रीसाइक्लर', h: 'समीक्षा डैशबोर्ड', p: 'नियमों के नतीजे, तीन अलग स्कोर, कस्टडी वंशावली, और हर दावे की छपने लायक रिपोर्ट।', go: 'समीक्षा के लिए साइन इन' },
      { i: 'phone', tag: 'कलेक्टर · एग्रीगेटर', h: 'कलेक्टर ऐप', p: 'हिंदी में, बिना इंटरनेट भी चलने वाला फ़ोन ऐप: ख़रीद दर्ज करें, बैच सौंपें, रसीद छापें।', go: 'फ़ोन पर खोलें' },
      { i: 'leaf', tag: 'सभी के लिए', h: 'प्रभाव', p: 'पंजीकृत रीसाइक्लर तक पहुँचा सीसा, पहले हैंडओवर वाली बैटरियाँ, और वह रेफ़्रिजरेंट नुक़सान जिसे कोई नहीं गिनता।', go: 'आँकड़े देखें' },
    ] as { i: IconName; tag: string; h: string; p: string; go: string }[],
    prEyebrow: 'हम क्या नहीं करते', prH: 'आठ नियम जिन पर यह उत्पाद बना है',
    principles: [
      ['संगति, प्रमाणन नहीं', 'पास हुआ दावा “उपलब्ध डेटा के अनुरूप” है। हम किसी चीज़ को सत्यापित या असली नहीं कहते।'],
      ['डेटा की कमी धोखा नहीं', 'हर नियम “पर्याप्त प्रमाण नहीं” कह सकता है, और बताता है कि क्या चाहिए।'],
      ['स्रोत नहीं, तो नियम नहीं', 'हर सीमा किसी उद्धृत दस्तावेज़ से आती है। अस्थायी मानों पर DEMO VALUE का बिल्ला है।'],
      ['तीन स्कोर, कभी मिलाए नहीं', 'भौतिक संगति, ट्रेसेबिलिटी और प्रमाण की गुणवत्ता अलग रहते हैं। कोई “धोखा स्कोर” नहीं।'],
      ['एकतरफ़ा, गवाह नहीं', 'हर फ़ील्ड बताता है किसने कहा और किसने पुष्टि की, और किसके फ़ोन से।'],
      ['असंगठित कामगार सुरक्षित', 'न नाम, न पहचान-पत्र, न पता। फ़ोन नंबर सिर्फ़ कुंजी वाले हैश के रूप में।'],
      ['AI समझाता है, फ़ैसला नहीं', 'मॉडल पाठ पढ़ते और फ़्लैग समझाते हैं, उद्धरण के साथ। वे फ़्लैग उठा या हटा नहीं सकते।'],
      ['इतिहास सिर्फ़ जुड़ता है', 'सुधार नई हस्ताक्षरित घटनाएँ हैं। कुछ भी मिटाया नहीं जाता।'],
    ],
    awsEyebrow: 'AWS पर बना', awsH: 'सर्वरलेस, हस्ताक्षरित और जाँचने योग्य',
  },
};

const AWS_SERVICES = ['Lambda', 'API Gateway', 'DynamoDB', 'KMS signatures', 'S3 Object Lock', 'Step Functions', 'EventBridge',
  'AVP · Cedar policies', 'Cognito', 'Bedrock + Guardrails', 'Amplify Hosting', 'CloudWatch + X-Ray', 'CDK + cdk-nag'];

function useCountUp(target: number | null, ms = 1200) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (target === null) return;
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { setV(target); return; }
    let raf = 0; const t0 = performance.now();
    const tick = (t: number) => { const k = Math.min(1, (t - t0) / ms); setV(target * (1 - Math.pow(1 - k, 3))); if (k < 1) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return v;
}

function Stat({ m }: { m: Metric }) {
  const ratio = m.unit === 'ratio';
  const target = ratio ? m.value * 100 : m.value;
  const v = useCountUp(target);
  const shown = Number.isInteger(target) ? Math.round(v) : Math.round(v * 10) / 10;
  return (
    <div className={`stat ${m.id.startsWith('refrigerant') ? 'warn' : ''}`}>
      <div className="v">{ratio ? `${Math.round(v)}%` : fmtNum(shown)}{!ratio && <span className="u">{m.unit}</span>}</div>
      <div className="l">{m.label}</div>
      <div className="n">{m.demo_value ? <DemoBadge /> : 'Counted from signed records'}</div>
    </div>
  );
}

async function verifyBatch(id: string): Promise<VerifyResult> {
  const r = await fetch(`${CAPTURE_API}/verify/${encodeURIComponent(id)}`);
  if (r.status === 404) throw new Error('404');
  if (!r.ok) throw new Error(String(r.status));
  return r.json() as Promise<VerifyResult>;
}

function ChainNodes({ n, bad }: { n: number; bad: number | null }) {
  const k = Math.max(1, Math.min(n || 1, 6));
  return (
    <div className="chain" aria-hidden="true">
      {Array.from({ length: k }).map((_, i) => (
        <span key={i} style={{ display: 'contents' }}>
          {i > 0 && <span className="bar" />}
          <span className={`node ${bad !== null && i + 1 >= bad ? 'bad' : ''}`}><Icon name={bad !== null && i + 1 >= bad ? 'alert' : 'check'} size={16} /></span>
        </span>
      ))}
    </div>
  );
}

export default function Landing() {
  const lang = useLang();
  const c = C[lang];
  const session = useSession();
  const [metrics, setMetrics] = useState<Metric[] | null>(null);
  const [hero, setHero] = useState<VerifyResult | null>(null);
  const [q, setQ] = useState('');
  const [res, setRes] = useState<{ state: 'idle' | 'busy' | 'ok' | 'err'; data?: VerifyResult; msg?: string }>({ state: 'idle' });
  const lookupRef = useRef<HTMLElement>(null);

  useEffect(() => { getImpact().then(setMetrics, () => setMetrics([])); }, []);
  useEffect(() => { if (CAPTURE_API) verifyBatch('B-0042').then(setHero, () => undefined); }, []);

  const run = async (id: string) => {
    const v = id.trim().toUpperCase();
    if (!v) return;
    setQ(v); setRes({ state: 'busy' });
    try { setRes({ state: 'ok', data: await verifyBatch(v) }); }
    catch (e) { setRes({ state: 'err', msg: (e as Error).message === '404' ? c.notFound : c.unreachable }); }
  };
  const toLookup = () => lookupRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });

  return (
    <main>
      <section className="hero">
        <div className="wrap">
          <div className="rise">
            <span className="eyebrow">{c.eyebrow}</span>
            <h1>{c.h1a} <em>{c.h1b}</em>{c.h1c}</h1>
            <p className="lede">{c.lede}</p>
            <div className="ctas">
              <a className="btn lg" href={session ? '#/' : '#/signin'}>{c.ctaReview}<Icon name="arrow" /></a>
              {CAPTURE_WEB && <a className="btn lg secondary" href={CAPTURE_WEB} target="_blank" rel="noreferrer"><Icon name="phone" />{c.ctaCollector}</a>}
              <button className="btn lg ghost" style={{ paddingLeft: 12, paddingRight: 12, border: 0 }} onClick={toLookup}><Icon name="shield" />{c.ctaVerify}</button>
            </div>
            <div className="trust">
              <span><Icon name="file" />{c.t1}</span><span><Icon name="lock" />{c.t2}</span><span><Icon name="spark" />{c.t3}</span>
            </div>
          </div>
          <div className="hero-stack" aria-label="Live examples">
            <div className="float a">
              <div className="fh"><span className="t"><span className="live-dot" />{c.liveLedger}</span><span className="pill mono">B-0042</span></div>
              {hero ? (
                <>
                  <div className="big">{hero.ok ? c.chainOk(hero.checked) : c.chainBad(hero.failed_at_seq)}</div>
                  <ChainNodes n={hero.checked} bad={hero.ok ? null : hero.failed_at_seq} />
                </>
              ) : (
                <><div className="skel" style={{ height: 64, marginBottom: 10 }} /><div className="skel" style={{ height: 34 }} /></>
              )}
              <p className="small muted" style={{ margin: '8px 0 0' }}>{c.signed}</p>
            </div>
            <div className="float b">
              <div className="fh"><span className="t">{c.example}</span><span className="chip out hard"><span aria-hidden="true">▲</span> FLAG · HARD</span></div>
              <h3 style={{ fontSize: 18, margin: '0 0 6px' }}><span className="rid mono" style={{ fontSize: 12, padding: '3px 8px', borderRadius: 8, background: 'var(--paper-2)', marginRight: 8 }}>R5</span>{c.exTitle}</h3>
              <p className="small" style={{ margin: 0, color: 'var(--ink-2)' }}>{c.exBody}</p>
              <dl className="obsrow"><div><dt>{c.observed}</dt><dd>{c.exObs}</dd></div><div><dt>{c.limit}</dt><dd>{c.exLim}</dd></div></dl>
            </div>
          </div>
        </div>
      </section>

      <section className="band">
        <div className="wrap">
          <div className="head"><span className="eyebrow">{c.impactEyebrow}</span><h2>{c.impactH}</h2><p>{c.impactP}</p></div>
          <div className="stats">
            {metrics === null && Array.from({ length: 4 }).map((_, i) => <div key={i} className="stat"><div className="skel" style={{ height: 48, width: '60%' }} /><div className="skel" style={{ height: 16, width: '80%' }} /></div>)}
            {metrics?.slice(0, 4).map((m) => <Stat key={m.id} m={m} />)}
          </div>
          <p style={{ marginTop: 16 }}><a href="#/impact" className="strong">{lang === 'hi' ? 'सभी आँकड़े और उनके स्रोत' : 'All figures and their sources'} →</a></p>
        </div>
      </section>

      <section className="band tint">
        <div className="wrap">
          <div className="head"><span className="eyebrow">{c.howEyebrow}</span><h2>{c.howH}</h2><p>{c.howP}</p></div>
          <div className="steps">
            {c.steps.map((s, i) => (
              <article className="step" key={s.h}>
                <span className="num">0{i + 1}</span>
                <div className="bub"><Icon name={s.i} /></div>
                <h3>{s.h}</h3><p>{s.p}</p><div className="by">{s.by}</div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="band" ref={lookupRef} id="verify">
        <div className="wrap lookup">
          <div>
            <span className="eyebrow">{c.verifyEyebrow}</span>
            <h2 style={{ fontSize: 'clamp(30px, 3.6vw, 46px)', margin: '10px 0 12px', lineHeight: 1.08 }}>{c.verifyH}</h2>
            <p style={{ color: 'var(--ink-2)', fontSize: 17.5, margin: '0 0 24px' }}>{c.verifyP}</p>
            <form className="searchbox" onSubmit={(e) => { e.preventDefault(); void run(q); }}>
              <Icon name="search" />
              <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={c.placeholder} aria-label={c.placeholder} autoCapitalize="characters" spellCheck={false} />
              <button className="btn" disabled={!CAPTURE_API || res.state === 'busy'}>{c.check}</button>
            </form>
            <div className="examples"><span className="small muted">{c.tryOne}</span>
              {['B-0042', 'B-0046', 'P-0101', 'A-0001'].map((id) => <button key={id} className="chip mono" onClick={() => void run(id)}>{id}</button>)}
            </div>
          </div>
          <div className="result" aria-live="polite">
            {res.state === 'idle' && <div className="seal"><span className="ring"><Icon name="shield" /></span><p className="muted" style={{ margin: 0 }}>{c.idle}</p></div>}
            {res.state === 'busy' && <><div className="skel" style={{ height: 64, marginBottom: 14 }} /><div className="skel" style={{ height: 34 }} /></>}
            {res.state === 'err' && <div className="seal"><span className="ring bad"><Icon name="alert" /></span><h3>{res.msg}</h3></div>}
            {res.state === 'ok' && res.data && (
              <>
                <div className="seal">
                  <span className={`ring ${res.data.ok ? '' : 'bad'}`}><Icon name={res.data.ok ? 'check' : 'alert'} /></span>
                  <div><span className="pill mono">{res.data.batch_id}</span><h3 style={{ marginTop: 6 }}>{res.data.ok ? c.chainOk(res.data.checked) : c.chainBad(res.data.failed_at_seq)}</h3></div>
                </div>
                <ChainNodes n={res.data.checked} bad={res.data.ok ? null : res.data.failed_at_seq} />
                {!res.data.ok && res.data.reason && <p className="small mono error">{res.data.reason}</p>}
                {CAPTURE_WEB && <p style={{ marginBottom: 0 }}><a href={`${CAPTURE_WEB}/v/${encodeURIComponent(res.data.batch_id)}`} target="_blank" rel="noreferrer" className="strong">{c.openFull} ↗</a></p>}
              </>
            )}
          </div>
        </div>
      </section>

      <section className="band tint">
        <div className="wrap">
          <div className="head"><span className="eyebrow">{c.doorsEyebrow}</span><h2>{c.doorsH}</h2></div>
          <div className="doors">
            {c.doors.map((d, i) => {
              const href = i === 0 ? (session ? '#/' : '#/signin') : i === 1 ? (CAPTURE_WEB || '#/welcome') : '#/impact';
              const ext = i === 1 && !!CAPTURE_WEB;
              return (
                <a key={d.h} className={`door ${i === 0 ? 'primary' : ''}`} href={href} {...(ext ? { target: '_blank', rel: 'noreferrer' } : {})}>
                  <div className="bub"><Icon name={d.i} /></div>
                  <span className="tag">{d.tag}</span>
                  <h3>{d.h}</h3><p>{d.p}</p>
                  <span className="go">{d.go}<Icon name={ext ? 'ext' : 'arrow'} size={18} /></span>
                </a>
              );
            })}
          </div>
        </div>
      </section>

      <section className="band">
        <div className="wrap">
          <div className="head"><span className="eyebrow">{c.prEyebrow}</span><h2>{c.prH}</h2></div>
          <div className="principles">
            {c.principles.map(([h, p], i) => <div className="principle" key={h}><span className="k">P{i + 1}</span><h4>{h}</h4><p>{p}</p></div>)}
          </div>
        </div>
      </section>

      <section className="band tint" style={{ borderBottom: 0 }}>
        <div className="wrap">
          <div className="head" style={{ marginBottom: 24 }}><span className="eyebrow">{c.awsEyebrow}</span><h2>{c.awsH}</h2></div>
          <div className="aws">{AWS_SERVICES.map((s) => <span className="pill" key={s}>{s}</span>)}</div>
        </div>
      </section>
    </main>
  );
}
