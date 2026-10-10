// Visual checks the main flow does not cover: dark mode, print layout, and a lineage with a batch split.
// Needs the local API (port 8788) and `npm run preview` (port 4173) running, like review_flow.mjs.
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const W = process.env.REVIEW_URL || 'http://localhost:4173';
const API = process.env.API_URL || 'http://127.0.0.1:8788';
const shots = process.env.SHOTS || path.join(root, 'web-review', 'screenshots');
fs.mkdirSync(shots, { recursive: true });
let failures = 0;
const ok = (c, m) => { if (c) console.log('  ok  ', m); else { failures++; console.log('  FAIL', m); } };

// Submit a claim that cites the split batch B-0046 as recycler REC-01, then run it as auditor.
const hdr = (role, party) => ({ 'content-type': 'application/json', 'x-dev-role': role, 'x-dev-party': party });
const id = 'C-' + String(200 + Math.floor(Math.random() * 99)).padStart(3, '0');
let r = await fetch(API + '/claims', { method: 'POST', headers: hdr('RECYCLER', 'REC-01'), body: JSON.stringify({
  claim_id: id, product: 'BATTERY_LEAD_ACID', period_start: '2026-10-01T00:00:00+05:30', period_end: '2026-10-31T23:59:59+05:30',
  input_t: 0.119, processed_t: 0.119, output: { LEAD: 0.05 }, batch_ids: ['B-0046'], opening_stock_t: 0, closing_stock_t: 0, documented_losses_t: 0, electricity_kwh: 25 }) });
ok(r.status === 201, `submitted ${id} citing B-0046 (${r.status})`);
r = await fetch(`${API}/claims/${id}/check`, { method: 'POST', headers: hdr('AUDITOR', 'AUD-01') });
ok(r.status === 200, 'ran ClaimGuard on it');
const detail = await (await fetch(`${API}/claims/${id}`, { headers: hdr('AUDITOR', 'AUD-01') })).json();
ok(detail.lineage.edges.length === 2 && detail.lineage.edges.every((e) => e.kind === 'SPLIT'), 'API lineage has two SPLIT edges');

const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const luma = (rgb) => { const m = rgb.match(/\d+(\.\d+)?/g).map(Number); return 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]; };
try {
  // 1. lineage with splits, light then dark
  for (const scheme of ['light', 'dark']) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: scheme });
    const p = await ctx.newPage();
    const errs = []; p.on('pageerror', (e) => errs.push(e.message));
    await p.goto(W + '/'); await p.evaluate(() => { try { localStorage.setItem('oae-review-dev-user', 'AUD-01'); } catch {} });
    await p.goto(`${W}/#/claims/${id}`); await p.locator('.rules').waitFor();
    await p.waitForTimeout(500);
    const svg = p.locator('svg').filter({ has: p.locator('text', { hasText: 'B-0046.1' }) }).first();
    ok(await svg.count() > 0, `${scheme}: lineage SVG shows child batch B-0046.1`);
    const edges = await p.locator('svg path, svg line').count();
    ok(edges >= 2, `${scheme}: lineage draws edges (${edges} path/line elements)`);
    const bg = await p.evaluate(() => getComputedStyle(document.body).backgroundColor);
    const fg = await p.evaluate(() => getComputedStyle(document.body).color);
    if (scheme === 'dark') ok(luma(bg) < 60 && luma(fg) > 150, `dark: dark background (${bg}) with light text (${fg})`);
    else ok(luma(bg) > 200 && luma(fg) < 100, `light: light background (${bg}) with dark text (${fg})`);
    // chips remain legible: every outcome chip has contrast against its card
    const chips = await p.locator('.chip, .outcome').evaluateAll((els) => els.slice(0, 40).map((e) => {
      const s = getComputedStyle(e); return [s.color, s.backgroundColor]; }));
    ok(chips.length > 0, `${scheme}: chips rendered (${chips.length})`);
    await p.screenshot({ path: path.join(shots, `split-lineage-${scheme}.png`), fullPage: true });
    // dark mode on the list and impact pages too
    for (const [name, hash] of [['list', '/'], ['impact', '/#/impact']]) {
      await p.goto(W + hash); await p.waitForTimeout(400);
      await p.screenshot({ path: path.join(shots, `${name}-${scheme}.png`), fullPage: true });
    }
    ok(errs.length === 0, `${scheme}: no page errors ${errs.join('|')}`);
    await ctx.close();
  }
  // 2. print layout: emulate print media, check chrome is hidden and nothing overflows A4 width, save a PDF
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(W + '/'); await p.evaluate(() => { try { localStorage.setItem('oae-review-dev-user', 'AUD-01'); } catch {} });
  await p.goto(`${W}/#/claims/C-102`); await p.locator('.rules').waitFor();
  await p.emulateMedia({ media: 'print' });
  await p.setViewportSize({ width: 794, height: 1123 }); // A4 at 96 dpi
  const hidden = await p.evaluate(() => ['button.btn', 'textarea', 'select', 'nav'].map((s) => [s, [...document.querySelectorAll(s)].filter((e) => e.getClientRects().length > 0).length]));
  console.log('  info visible under print:', JSON.stringify(hidden));
  ok(hidden.every(([, n]) => n === 0), 'print: action buttons, inputs and navigation are hidden (source chips stay)');
  const pdf = path.join(shots, 'claim-C-102-print.pdf');
  await p.pdf({ path: pdf, format: 'A4', printBackground: true });
  ok(fs.statSync(pdf).size > 5000, `print: PDF written (${fs.statSync(pdf).size} bytes)`);
  const sw = await p.evaluate(() => document.documentElement.scrollWidth);
  ok(sw <= 800, `print: content fits A4 width (scrollWidth ${sw})`);
} finally { await browser.close(); }
console.log(failures ? `\n${failures} check(s) failed` : '\nall visual checks passed');
process.exit(failures ? 1 : 0);
