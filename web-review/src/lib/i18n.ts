// Static UI labels only. Server text (rule explanations, notes, sources) is never translated.
import { useSyncExternalStore } from 'react';

type Lang = 'en' | 'hi';
const en = {
  app: 'Vericycle Review', reviewSub: 'Claim review', claims: 'Claims', impact: 'Impact', lang: 'हिन्दी', print: 'Print report', signOut: 'Sign out',
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
  signIn: 'Sign in', signInHint: 'Use the demo account your team gave you.', tagline: 'Proof of recycling', about: 'About',
  collectorApp: 'Collector app', footer: 'Vericycle · consistency, not certification. A passing claim is consistent with available data; it is not a certificate.',
  footerData: 'Demo data is synthetic · AWS ap-southeast-2', overview: 'Overview', claimsChecked: 'Claims checked', hardFlags: 'Hard flags',
  softFlags: 'Soft flags', avgCoverage: 'Average coverage', claimsOf: 'claims', needsLook: 'need a closer look', breakLimit: 'break a physical limit',
  linked: 'of claimed tonnage linked to handovers', reviewQueue: 'Review queue', sortedHint: 'Sorted by severity: hard flags first.',
  consistentRules: 'rules consistent with available data', showConsistent: 'Show', hideConsistent: 'Hide',
  vHard: 'Inconsistent with data', vSoft: 'Needs a closer look', vOk: 'Consistent with available data', vNone: 'Not checked yet',
  vHardP: 'At least one physical limit is broken. A reviewer decides what happens next.',
  vSoftP: 'Nothing physically impossible, but something is unusual. Ask for the evidence named below.',
  vOkP: 'No rule found an inconsistency. This is not a certificate.',
} as const;
export type Key = keyof typeof en;
const hi: Partial<Record<Key, string>> = {
  app: 'Vericycle समीक्षा', reviewSub: 'दावों की समीक्षा', claims: 'दावे', impact: 'प्रभाव', lang: 'English', print: 'रिपोर्ट छापें', signOut: 'साइन आउट',
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
  signIn: 'साइन इन', signInHint: 'टीम से मिला डेमो खाता इस्तेमाल करें।', tagline: 'रीसाइक्लिंग का सबूत', about: 'परिचय',
  collectorApp: 'कलेक्टर ऐप', footer: 'Vericycle · संगति, प्रमाणन नहीं। पास हुआ दावा उपलब्ध डेटा के अनुरूप है; वह कभी “सत्यापित” नहीं कहलाता।',
  footerData: 'डेमो डेटा काल्पनिक है · AWS ap-southeast-2', overview: 'सारांश', claimsChecked: 'जाँचे गए दावे', hardFlags: 'HARD फ़्लैग',
  softFlags: 'SOFT फ़्लैग', avgCoverage: 'औसत कवरेज', claimsOf: 'दावे', needsLook: 'पर और नज़र चाहिए', breakLimit: 'भौतिक सीमा तोड़ते हैं',
  linked: 'दावा किया गया वज़न हैंडओवर से जुड़ा', reviewQueue: 'समीक्षा सूची', sortedHint: 'गंभीरता के क्रम में: HARD फ़्लैग पहले।',
  consistentRules: 'नियम उपलब्ध डेटा के अनुरूप', showConsistent: 'दिखाएँ', hideConsistent: 'छिपाएँ',
  vHard: 'डेटा से मेल नहीं खाता', vSoft: 'और नज़र चाहिए', vOk: 'उपलब्ध डेटा के अनुरूप', vNone: 'अभी जाँच नहीं हुई',
  vHardP: 'कम से कम एक भौतिक सीमा टूटी है। आगे क्या होगा, यह समीक्षक तय करेगा।',
  vSoftP: 'कुछ असंभव नहीं, पर कुछ असामान्य है। नीचे बताया गया प्रमाण माँगें।',
  vOkP: 'किसी नियम को असंगति नहीं मिली। यह प्रमाणपत्र नहीं है।',
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
export function useLang(): Lang {
  return useSyncExternalStore((f) => { subs.add(f); return () => { subs.delete(f); }; }, () => lang);
}
export function useT(): (k: Key) => string {
  const l = useLang();
  return (k) => (l === 'hi' ? hi[k] : undefined) ?? en[k];
}
document.documentElement.lang = lang;
