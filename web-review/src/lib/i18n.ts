// Static UI labels only. Server text (rule explanations, notes, sources) is never translated.
import { useSyncExternalStore } from 'react';

type Lang = 'en' | 'hi';
const en = {
  app: 'OpenAEye Review', claims: 'Claims', impact: 'Impact', lang: 'हिन्दी', print: 'Print report', signOut: 'Sign out',
  claim: 'Claim', recycler: 'Recycler', product: 'Product', period: 'Period', flags: 'Flags', coverage: 'Coverage', lastRun: 'Last run',
  allProducts: 'All products', filterProduct: 'Filter by product', noFlags: 'No flags', notRun: 'Not run',
  howTitle: 'How to read this', dismiss: 'Dismiss',
  how1: 'PASS means the numbers are consistent with the available data; it is a grey result, not an approval.',
  how2: 'FLAG means the claim is inconsistent with data: a HARD flag breaks a physical limit, a SOFT flag needs a closer look.',
  how3: 'INSUFFICIENT means there is not enough evidence to decide, and the card says what would resolve it.',
  physical: 'Physical consistency', traceability: 'Traceability coverage', evidenceQuality: 'Evidence quality',
  runClaimGuard: 'Run ClaimGuard', running: 'Running...',
  observed: 'Observed', limit: 'Limit', severity: 'Severity', resolve: 'What would resolve this', demo: 'DEMO VALUE',
  showErratum: 'Show the CPCB erratum', hideErratum: 'Hide the CPCB erratum',
  evidence: 'Evidence', batches: 'Cited batches and lineage', trail: 'Review trail', noTrail: 'No review actions yet.',
  accept: 'Accept', request: 'Request evidence', escalate: 'Escalate', note: 'Note (optional)',
  recyclerView: 'Recycler view', respond: 'Your response', sendResponse: 'Send response',
  legend: 'Legend', back: 'All claims', source: 'Source', close: 'Close', ruleResults: 'Rule results',
  loading: 'Loading...', role: 'Role',
} as const;
export type Key = keyof typeof en;
const hi: Partial<Record<Key, string>> = {
  app: 'OpenAEye समीक्षा', claims: 'दावे', impact: 'प्रभाव', lang: 'English', print: 'रिपोर्ट छापें', signOut: 'साइन आउट',
  claim: 'दावा', recycler: 'रिसाइक्लर', product: 'उत्पाद', period: 'अवधि', flags: 'फ़्लैग', coverage: 'कवरेज', lastRun: 'आख़िरी जाँच',
  allProducts: 'सभी उत्पाद', filterProduct: 'उत्पाद से छाँटें', noFlags: 'कोई फ़्लैग नहीं', notRun: 'जाँच नहीं हुई',
  howTitle: 'इसे कैसे पढ़ें', dismiss: 'बंद करें',
  how1: 'PASS का मतलब है कि आँकड़े उपलब्ध डेटा के अनुरूप हैं; यह स्लेटी नतीजा है, मंज़ूरी नहीं।',
  how2: 'FLAG का मतलब है कि दावा डेटा से मेल नहीं खाता: HARD फ़्लैग भौतिक सीमा तोड़ता है, SOFT फ़्लैग पर और नज़र चाहिए।',
  how3: 'INSUFFICIENT का मतलब है कि फ़ैसले के लिए पर्याप्त प्रमाण नहीं है; कार्ड बताता है कि क्या चाहिए।',
  physical: 'भौतिक संगति', traceability: 'ट्रेसेबिलिटी कवरेज', evidenceQuality: 'प्रमाण की गुणवत्ता',
  runClaimGuard: 'ClaimGuard चलाएँ', running: 'चल रहा है...', observed: 'देखा गया', limit: 'सीमा', severity: 'गंभीरता',
  resolve: 'इसे क्या सुलझाएगा', showErratum: 'CPCB की गलती दिखाएँ', hideErratum: 'CPCB की गलती छिपाएँ',
  evidence: 'प्रमाण', batches: 'उद्धृत बैच और वंशावली', trail: 'समीक्षा का क्रम', noTrail: 'अभी कोई समीक्षा कार्रवाई नहीं।',
  accept: 'स्वीकार करें', request: 'प्रमाण माँगें', escalate: 'ऊपर भेजें', note: 'टिप्पणी (वैकल्पिक)',
  recyclerView: 'रिसाइक्लर दृश्य', respond: 'आपका उत्तर', sendResponse: 'उत्तर भेजें', legend: 'संकेत', back: 'सभी दावे',
  source: 'स्रोत', close: 'बंद करें', ruleResults: 'नियम के नतीजे', loading: 'लोड हो रहा है...', role: 'भूमिका',
};
let lang: Lang = 'en';
try { if (localStorage.getItem('oae-review-lang') === 'hi') lang = 'hi'; } catch { /* storage blocked */ }
const subs = new Set<() => void>();
export function toggleLang() {
  lang = lang === 'en' ? 'hi' : 'en';
  try { localStorage.setItem('oae-review-lang', lang); } catch { /* storage blocked */ }
  document.documentElement.lang = lang;
  subs.forEach((f) => f());
}
export function useT(): (k: Key) => string {
  const l = useSyncExternalStore((f) => { subs.add(f); return () => { subs.delete(f); }; }, () => lang);
  return (k) => (l === 'hi' ? hi[k] : undefined) ?? en[k];
}
document.documentElement.lang = lang;
