import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { load, save } from '../lib/store';

const en = {
  app: 'ChainTrack', lang: 'हिंदी', signIn: 'Sign in', signOut: 'Exit', chooseAccount: 'Choose a demo account',
  demoNote: 'Demo accounts only. Real sign-in is added once the team picks the method.',
  home: { chat: 'Record a handover', scan: 'Scan a QR', batch: 'Open a batch', verify: 'Check a record', privacy: 'Privacy' },
  chat: {
    hello: 'Namaste! Tell me what you bought: send a voice note or type, e.g. "4 e-rickshaw batteries from a driver, about 120 kg".',
    privacyLink: 'How we use this', placeholder: 'Type a message', hold: 'Hold to record', recording: 'Recording… release to send',
    listening: 'Listening to your voice note…', uncertain: 'Please check', confirm: 'Correct', edit: 'Change',
    saved: 'Saved. Show these to the next person.', nextHandler: 'Next buyer scans this', seller: 'Seller confirms on their own phone',
    sellerHint: 'Ask the seller to scan this with their phone and press Yes. Do not press it for them.',
    shareLink: 'Or send this link', failed: 'Could not read that. Please try again or type it.', micDenied: 'Microphone not allowed. Please type instead.',
    count: 'Count', weight: 'Weight (kg)', source: 'Bought from', material: 'What', save: 'Save', cancel: 'Cancel',
    offline: 'You are offline. Voice and chat need the internet; the form still works and will send later.',
  },
  src: { DRIVER: 'Driver', HOUSEHOLD: 'Household', TECHNICIAN: 'Technician', RETAIL_EXCHANGE: 'Shop exchange', INSTITUTION: 'Institution', OTHER: 'Other', UNKNOWN: 'Not said' },
  mat: { BATTERY_LEAD_ACID: 'Lead-acid battery', EWASTE_PHONE: 'Mobile phones', AC_REFRIGERANT: 'Air conditioner' },
  batch: {
    title: 'Batch', status: 'Status', events: 'History', weighed: 'weighed', stated: 'stated', ocr: 'from slip', computed: 'computed',
    evidence: 'Evidence attached', noEvidence: 'No evidence', actions: 'Record next step', open: 'Open', idPlaceholder: 'e.g. B-0042',
    TRANSFER: 'Hand over to next buyer', SPLIT: 'Split', MERGE: 'Merge', INTAKE: 'Recycler intake', PROCESS: 'Processing run', OUTPUT: 'Metal output', CORRECTION: 'Correct a mistake',
    verify: 'Check the chain',
  },
  type: { HANDOVER: 'First handover', TRANSFER: 'Handover', SPLIT: 'Split', MERGE: 'Merge', INTAKE: 'Recycler intake', PROCESS: 'Processing', OUTPUT: 'Output', CORRECTION: 'Correction' },
  form: { send: 'Save record', kg: 'Weighed kg', facility: 'Facility', photo: 'Take weigh-slip photo', retake: 'Retake', to: 'Handed to (party ID)',
    children: 'Child weights (kg), one per line', parents: 'Other batches to merge (IDs, one per line)', input: 'Input kg', run: 'Run ID',
    metal: 'Metal', output: 'Output kg', correctsSeq: 'Step number to correct', field: 'Field', newValue: 'Correct value', reason: 'Reason',
    hashNote: 'Photo hashed on this phone before upload; the server records its own receipt time.', queued: 'Saved offline. It will send when you are back online.',
    noUpstream: 'No earlier record for this batch. Intake saved; reviewers will see it.' },
  queue: { waiting_one: '{{count}} record waiting to send', waiting_other: '{{count}} records waiting to send', sendNow: 'Send now' },
  scan: { title: 'Scan the QR on the receipt', manual: 'Or type the batch ID', noCamera: 'Camera not available. Type the batch ID instead.' },
  receipt: { title: 'Receipt', count: 'Count', weight: 'Approx. weight', date: 'Date', chainOk: 'Chain intact: {{n}} of {{n}} records check out',
    chainBad: 'Chain check failed at record {{seq}}', print: 'Print', steps: 'Steps', noNames: 'This receipt shows no names.' },
  confirm: { yes: 'हाँ, मैंने बेचा / Yes, I sold this', no: 'नहीं / No', done: 'Thank you. Recorded.', rejected: 'Recorded that this is not right.',
    used: 'This link was already used.', expired: 'This link has expired.', what: 'Did you sell this?' },
  verify: { title: 'Public check', ok: 'Chain intact: {{checked}} of {{checked}} records check out', bad: 'Chain broken at record {{seq}}',
    reason: 'Reason', digest: 'Latest published daily root', key: 'Public signing key', explain: 'Every record is hashed into the one before it and signed with a key held in AWS KMS. Changing any stored record breaks the chain at that record.' },
  chip: { BOTH_PARTIES_CONFIRMED: 'Seller confirmed on own phone', HANDLER_CONFIRMED: 'Seller confirmed on own phone (some fields)',
    SAME_DEVICE_CONFIRMED: "Confirmed on buyer's phone (not independent)", BUYER_REPORTED: 'Entered by buyer only' },
  err: { generic: 'Something went wrong. Please try again.', forbidden: 'You are not allowed to do this.' },
  privacy: {
    title: 'Privacy', body: [
      'We never ask the seller for a name, Aadhaar, GSTIN or address.',
      'Phone numbers are stored only as a keyed code (HMAC) that cannot be turned back into the number.',
      'Voice notes are deleted within 24 hours; only the text is kept.',
      'Location is off unless you turn it on, and is never more precise than about 5 km.',
      'Records are kept to show that batteries and devices reached a registered recycler.',
    ] },
};

const hi: typeof en = {
  app: 'चेनट्रैक', lang: 'English', signIn: 'साइन इन', signOut: 'बाहर', chooseAccount: 'डेमो खाता चुनें',
  demoNote: 'सिर्फ़ डेमो खाते। असली साइन-इन टीम का फ़ैसला होने के बाद जुड़ेगा।',
  home: { chat: 'ख़रीद दर्ज करें', scan: 'QR स्कैन करें', batch: 'बैच खोलें', verify: 'रिकॉर्ड जाँचें', privacy: 'गोपनीयता' },
  chat: {
    hello: 'नमस्ते! बताइए आपने क्या ख़रीदा: वॉइस नोट भेजें या लिखें, जैसे "चार ई-रिक्शा बैटरी ड्राइवर से, लगभग 120 किलो"।',
    privacyLink: 'हम इसका क्या करते हैं', placeholder: 'संदेश लिखें', hold: 'दबाकर रखें और बोलें', recording: 'रिकॉर्ड हो रहा है… छोड़ें तो भेजें',
    listening: 'आपका वॉइस नोट सुन रहे हैं…', uncertain: 'कृपया जाँचें', confirm: 'सही है', edit: 'बदलें',
    saved: 'दर्ज हो गया। अगले व्यक्ति को यह दिखाएँ।', nextHandler: 'अगला ख़रीदार यह स्कैन करे', seller: 'बेचने वाला अपने फ़ोन से पुष्टि करे',
    sellerHint: 'बेचने वाले से कहें कि अपने फ़ोन से स्कैन करके "हाँ" दबाए। उनकी जगह आप न दबाएँ।',
    shareLink: 'या यह लिंक भेजें', failed: 'समझ नहीं आया। फिर से बोलें या लिखें।', micDenied: 'माइक की अनुमति नहीं है। कृपया लिखें।',
    count: 'संख्या', weight: 'वज़न (किलो)', source: 'किससे लिया', material: 'क्या', save: 'सहेजें', cancel: 'रद्द करें',
    offline: 'इंटरनेट नहीं है। वॉइस और चैट के लिए इंटरनेट चाहिए; फ़ॉर्म चलता रहेगा और बाद में भेजेगा।',
  },
  src: { DRIVER: 'ड्राइवर', HOUSEHOLD: 'घर', TECHNICIAN: 'मिस्त्री', RETAIL_EXCHANGE: 'दुकान एक्सचेंज', INSTITUTION: 'संस्था', OTHER: 'कोई और', UNKNOWN: 'नहीं बताया' },
  mat: { BATTERY_LEAD_ACID: 'लेड-एसिड बैटरी', EWASTE_PHONE: 'मोबाइल फ़ोन', AC_REFRIGERANT: 'एसी' },
  batch: {
    title: 'बैच', status: 'स्थिति', events: 'इतिहास', weighed: 'तौला गया', stated: 'बताया गया', ocr: 'पर्ची से', computed: 'गणना',
    evidence: 'सबूत लगा है', noEvidence: 'कोई सबूत नहीं', actions: 'अगला कदम दर्ज करें', open: 'खोलें', idPlaceholder: 'जैसे B-0042',
    TRANSFER: 'अगले ख़रीदार को दें', SPLIT: 'बाँटें', MERGE: 'मिलाएँ', INTAKE: 'रीसाइक्लर पर आमद', PROCESS: 'प्रोसेसिंग', OUTPUT: 'धातु आउटपुट', CORRECTION: 'ग़लती सुधारें',
    verify: 'चेन जाँचें',
  },
  type: { HANDOVER: 'पहली ख़रीद', TRANSFER: 'हस्तांतरण', SPLIT: 'बँटवारा', MERGE: 'मिलान', INTAKE: 'रीसाइक्लर आमद', PROCESS: 'प्रोसेसिंग', OUTPUT: 'आउटपुट', CORRECTION: 'सुधार' },
  form: { send: 'रिकॉर्ड सहेजें', kg: 'तौला गया किलो', facility: 'प्लांट', photo: 'तौल पर्ची की फ़ोटो लें', retake: 'फिर से लें', to: 'किसे दिया (पार्टी ID)',
    children: 'हिस्सों का वज़न (किलो), हर लाइन में एक', parents: 'मिलाने वाले दूसरे बैच (ID, हर लाइन में एक)', input: 'इनपुट किलो', run: 'रन ID',
    metal: 'धातु', output: 'आउटपुट किलो', correctsSeq: 'किस कदम को सुधारना है', field: 'फ़ील्ड', newValue: 'सही मान', reason: 'कारण',
    hashNote: 'फ़ोटो का हैश इसी फ़ोन पर बनता है; सर्वर अपना समय दर्ज करता है।', queued: 'ऑफ़लाइन सहेजा। इंटरनेट आने पर भेज देंगे।',
    noUpstream: 'इस बैच का पहले का रिकॉर्ड नहीं है। आमद दर्ज हुई; समीक्षक इसे देखेंगे।' },
  queue: { waiting_one: '{{count}} रिकॉर्ड भेजना बाक़ी', waiting_other: '{{count}} रिकॉर्ड भेजना बाक़ी', sendNow: 'अभी भेजें' },
  scan: { title: 'रसीद का QR स्कैन करें', manual: 'या बैच ID लिखें', noCamera: 'कैमरा नहीं मिला। बैच ID लिखें।' },
  receipt: { title: 'रसीद', count: 'संख्या', weight: 'लगभग वज़न', date: 'तारीख़', chainOk: 'चेन सही: {{n}} में से {{n}} रिकॉर्ड ठीक',
    chainBad: 'रिकॉर्ड {{seq}} पर चेन जाँच विफल', print: 'प्रिंट', steps: 'कदम', noNames: 'इस रसीद पर कोई नाम नहीं है।' },
  confirm: { yes: 'हाँ, मैंने बेचा / Yes, I sold this', no: 'नहीं / No', done: 'धन्यवाद। दर्ज हो गया।', rejected: 'दर्ज किया कि यह सही नहीं है।',
    used: 'यह लिंक पहले ही इस्तेमाल हो चुका है।', expired: 'यह लिंक पुराना हो गया है।', what: 'क्या आपने यह बेचा?' },
  verify: { title: 'सार्वजनिक जाँच', ok: 'चेन सही: {{checked}} में से {{checked}} रिकॉर्ड ठीक', bad: 'रिकॉर्ड {{seq}} पर चेन टूटी',
    reason: 'कारण', digest: 'आख़िरी प्रकाशित दैनिक रूट', key: 'सार्वजनिक हस्ताक्षर कुंजी', explain: 'हर रिकॉर्ड पिछले रिकॉर्ड के हैश से जुड़ा है और AWS KMS की कुंजी से हस्ताक्षरित है। किसी भी रिकॉर्ड को बदलने से चेन उसी रिकॉर्ड पर टूट जाती है।' },
  chip: { BOTH_PARTIES_CONFIRMED: 'विक्रेता ने अपने फ़ोन से पुष्टि की', HANDLER_CONFIRMED: 'विक्रेता ने अपने फ़ोन से पुष्टि की (कुछ बातें)',
    SAME_DEVICE_CONFIRMED: 'ख़रीदार के फ़ोन पर पुष्टि (स्वतंत्र नहीं)', BUYER_REPORTED: 'सिर्फ़ ख़रीदार ने दर्ज किया' },
  err: { generic: 'कुछ ग़लत हुआ। फिर से कोशिश करें।', forbidden: 'आपको यह करने की अनुमति नहीं है।' },
  privacy: {
    title: 'गोपनीयता', body: [
      'हम बेचने वाले से नाम, आधार, GSTIN या पता कभी नहीं माँगते।',
      'फ़ोन नंबर सिर्फ़ एक कोड (HMAC) के रूप में रखा जाता है, जिससे नंबर वापस नहीं निकाला जा सकता।',
      'वॉइस नोट 24 घंटे में मिटा दिए जाते हैं; सिर्फ़ लिखा हुआ पाठ रहता है।',
      'लोकेशन तब तक बंद है जब तक आप चालू न करें, और लगभग 5 किमी से ज़्यादा सटीक नहीं।',
      'रिकॉर्ड यह दिखाने के लिए रखे जाते हैं कि बैटरी और डिवाइस पंजीकृत रीसाइक्लर तक पहुँचे।',
    ] },
};

export function initialLang(): 'hi' | 'en' {
  const s = load('oae.lang');
  return s === 'en' || s === 'hi' ? s : 'hi';
}
export function setLang(l: 'hi' | 'en') { save('oae.lang', l); void i18n.changeLanguage(l); document.documentElement.lang = l; }

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, hi: { translation: hi } },
  lng: initialLang(), fallbackLng: 'en', interpolation: { escapeValue: false }, returnObjects: true,
});
document.documentElement.lang = initialLang();
export default i18n;
