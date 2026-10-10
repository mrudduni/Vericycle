// Run: start scripts/chaintrack/local_api.py and 'npx vite' in web-capture, then: node tests/chaintrack/e2e/flow.mjs
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const W = 'http://localhost:5173';
const shots = process.env.SHOTS || '/tmp/oae-shots'; require('fs').mkdirSync(shots, { recursive: true });
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const phone = { viewport: { width: 360, height: 740 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: 'hi-IN' };
const log = (...a) => console.log('•', ...a);
const noHScroll = async (p, name) => { const w = await p.evaluate(() => document.documentElement.scrollWidth); if (w > 360) throw new Error(`${name}: horizontal scroll ${w}px`); };

// 1. collector records via chat
const col = await browser.newContext(phone);
const p = await col.newPage();
p.on('pageerror', (e) => console.log('PAGEERROR', e.message));
await p.goto(W);
await p.getByText('Battery dealer · COL-118').click();
await p.screenshot({ path: `${shots}/01-home.png` });
await p.getByText('ख़रीद दर्ज करें').click();
await p.getByLabel('संदेश लिखें').fill('chaar e-rickshaw battery driver se li, lagbhag assi kilo');
await p.getByLabel('Send').click();
await p.getByText('क्या यह सही है?').waitFor();
await noHScroll(p, 'chat');
await p.screenshot({ path: `${shots}/02-draft-card.png` });
await p.getByRole('button', { name: /सही है/ }).click();
await p.getByText('दर्ज हो गया').waitFor();
await p.waitForTimeout(300);
await p.screenshot({ path: `${shots}/03-receipt-card.png`, fullPage: true });
const confirmUrl = await p.locator('a.mono').getAttribute('href');
const batchId = (await p.locator('.bubble a[href^="/b/"]').first().textContent()).trim();
log('batch', batchId, 'confirm', confirmUrl);
await noHScroll(p, 'receipt card');

// 2. seller confirms on their own phone (separate browser context = different device_id)
const seller = await browser.newContext(phone);
const sp = await seller.newPage();
await sp.goto(confirmUrl.replace(/^https?:\/\/[^/]+/, W));
await sp.getByText('क्या आपने यह बेचा?').waitFor();
await noHScroll(sp, 'confirm');
await sp.screenshot({ path: `${shots}/04-confirm.png` });
await sp.getByRole('button', { name: /हाँ, मैंने बेचा/ }).click();
await sp.getByText('धन्यवाद').waitFor();
log('seller confirmed');

// 3. batch view shows the chip
await p.goto(`${W}/b/${batchId}`);
await p.getByText('विक्रेता ने अपने फ़ोन से पुष्टि की').first().waitFor();
await p.screenshot({ path: `${shots}/05-batch.png`, fullPage: true });
log('chip ok');

// 4. collector transfer while OFFLINE -> queued -> online -> synced exactly once
await p.getByRole('button', { name: 'अगले ख़रीदार को दें' }).click();
await p.getByLabel('तौला गया किलो').fill('78');
await p.getByLabel('किसे दिया (पार्टी ID)').fill('AGG-01');
await col.setOffline(true);
await p.getByRole('button', { name: 'रिकॉर्ड सहेजें' }).click();
await p.getByText('ऑफ़लाइन सहेजा').waitFor();
await p.getByText('1 रिकॉर्ड भेजना बाक़ी').waitFor();
await p.screenshot({ path: `${shots}/06-offline-queued.png` });
await col.setOffline(false);
await p.evaluate(() => window.dispatchEvent(new Event('online')));
await p.getByText('1 रिकॉर्ड भेजना बाक़ी').waitFor({ state: 'detached', timeout: 10000 });
const evs = await (await fetch(`http://localhost:8787/batches/${batchId}`, { headers: { 'x-dev-party': 'AUD-01', 'x-dev-role': 'AUDITOR' } })).json();
const transfers = evs.events.filter((e) => e.type === 'TRANSFER').length;
log('events after sync', evs.events.map((e) => e.type).join(','), 'transfers=', transfers);
if (transfers !== 1) throw new Error('offline event not synced exactly once');

// 5. recycler intake (no camera in headless: form without photo)
const rec = await browser.newContext(phone);
const rp = await rec.newPage();
await rp.goto(W);
await rp.getByText('Lead recycler · REC-01').click();
await rp.goto(`${W}/b/${batchId}/intake`);
await rp.getByLabel('तौला गया किलो').fill('77');
await rp.getByRole('button', { name: 'रिकॉर्ड सहेजें' }).click();
await rp.getByText('रीसाइक्लर आमद').first().waitFor();
await rp.screenshot({ path: `${shots}/07-after-intake.png`, fullPage: true });
log('intake ok');

// 6. aggregator cannot do intake (button not offered; API would 403)
// 7. public receipt and verify
const pub = await browser.newContext({ ...phone, locale: 'en-IN' });
const pp = await pub.newPage();
const tok = evs.receipt_token;
await pp.goto(`${W}/r/${tok}`);
await pp.getByText(/Chain intact|चेन सही/).waitFor();
await noHScroll(pp, 'receipt');
await pp.screenshot({ path: `${shots}/08-receipt.png`, fullPage: true });
await pp.goto(`${W}/v/B-0042`);
await pp.getByText(/Chain intact|चेन सही/).waitFor();
await pp.screenshot({ path: `${shots}/09-verify.png`, fullPage: true });
// 8. confirm link single use
await sp.goto(confirmUrl.replace(/^https?:\/\/[^/]+/, W));
await sp.getByText(/पहले ही इस्तेमाल|already used/).waitFor();
log('token single-use ok');
// 9. tap target sizes
const small = await p.evaluate(() => [...document.querySelectorAll('button, a.btn, .tile, input, select')]
  .filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.height < 40; }).map((e) => e.outerHTML.slice(0, 60)));
log('controls under 40px tall:', small.length, small.slice(0, 3));
await browser.close();
log('ALL OK');
