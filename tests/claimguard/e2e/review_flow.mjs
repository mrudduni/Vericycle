// End-to-end check of web-review against the real local Review API.
//   1. services/claimguard/.venv/Scripts/python.exe scripts/claimguard/local_review_api.py --port 8788
//   2. cd web-review && npm run build && npm run preview      (build uses .env.local with VITE_DEV_AUTH=1)
//   3. node tests/claimguard/e2e/review_flow.mjs
// Env: REVIEW_URL (default http://localhost:4173), PLAYWRIGHT_PATH, CHROME_PATH, SHOTS (default web-review/screenshots).
// Exits non-zero on the first failed check.
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../..');
const W = process.env.REVIEW_URL || 'http://localhost:4173';
const shots = process.env.SHOTS || path.join(root, 'web-review', 'screenshots');
fs.mkdirSync(shots, { recursive: true });

let failures = 0;
const ok = (cond, msg) => { if (cond) console.log('  ok  ', msg); else { failures++; console.log('  FAIL', msg); } };
const log = (m) => console.log('\n' + m);

const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const p = await ctx.newPage();
const pageErrors = [];
p.on('pageerror', (e) => pageErrors.push(e.message));
const shot = (name, full = true) => p.screenshot({ path: path.join(shots, name + '.png'), fullPage: full });
const noHScroll = async (name, w) => {
  const sw = await p.evaluate(() => document.documentElement.scrollWidth);
  ok(sw <= w, `${name}: no horizontal scroll at ${w}px (scrollWidth ${sw})`);
};
const openClaim = async (id) => { await p.goto(`${W}/#/claims/${id}`); await p.locator('.rules').waitFor(); };
const rule = (id) => p.locator(`article.rule[data-rule="${id}"]`);

try {
  log('1. claim list');
  await p.goto(W + '/');
  await p.locator('table.claims tbody tr').first().waitFor();
  const rows = await p.locator('table.claims tbody tr').count();
  ok(rows === 9, `9 demo claims listed (got ${rows})`);
  const firstTwo = await p.locator('table.claims tbody tr td:first-child').allInnerTexts();
  ok(firstTwo[0].trim() === 'C-102', `C-102 (HARD flag) sorted first (got ${firstTwo[0].trim()})`);
  ok((await p.locator('table.claims tbody tr').first().innerText()).includes('HARD'), 'HARD flag shown as text with the chip');
  ok(await p.getByText('How to read this').isVisible(), '"How to read this" strip shown on first visit');
  await shot('01-claim-list-dismissible-strip');
  await p.getByRole('button', { name: 'Dismiss' }).click();
  await p.reload(); await p.locator('table.claims tbody tr').first().waitFor();
  ok((await p.getByText('How to read this').count()) === 0, 'strip stays dismissed after reload (localStorage)');
  await p.keyboard.press('j');
  ok((await p.locator('tr.sel td').first().innerText()).trim() !== firstTwo[0].trim(), 'j moves the selection');
  await p.keyboard.press('k');
  ok((await p.locator('tr.sel td').first().innerText()).trim() === firstTwo[0].trim(), 'k moves it back');
  await p.keyboard.press('Enter');
  await p.locator('.rules').waitFor();
  ok(p.url().endsWith('/claims/C-102'), 'Enter opens the selected claim');
  await p.goto(W + '/'); await p.locator('table.claims tbody tr').first().waitFor();
  const opts = await p.getByLabel('Filter by product').locator('option').allInnerTexts();
  ok(opts.length >= 3, `product filter has options (${opts.join(' | ')})`);
  await p.getByLabel('Filter by product').selectOption({ index: 2 });
  ok((await p.locator('table.claims tbody tr').count()) < 9, 'product filter narrows the list');
  await noHScroll('list', 1280);

  log('2. C-102: R1 FLAG HARD with erratum toggle');
  await openClaim('C-102');
  const r1 = rule('R1');
  ok((await r1.getAttribute('data-outcome')) === 'FLAG', 'R1 outcome FLAG');
  ok((await r1.innerText()).includes('HARD'), 'R1 shows severity HARD');
  ok((await r1.locator('.formula').innerText()).includes('26400'), 'formula_rendered shown in monospace block');
  ok((await p.locator('#erratum').count()) === 0, 'erratum hidden by default');
  await p.getByRole('button', { name: 'Show the CPCB erratum' }).click();
  const erratum = await p.locator('#erratum').innerText();
  ok(erratum.includes('46,200 t') && erratum.includes('26,400 t'), 'erratum callout names 46,200 t and 26,400 t');
  const headings = await p.locator('.score h3').allInnerTexts();
  ok(headings.length === 3 && /Physical/.test(headings[0]) && /Traceability/.test(headings[1]) && /Evidence/.test(headings[2]), `three separate score bars (${headings.join(' | ')})`);
  ok((await p.locator('.disclaimer').innerText()).trim() === 'A claim that passes is consistent with the available data. It is not certified as genuine.', 'disclaimer line present');
  await r1.getByRole('button', { name: /Open source/ }).first().click();
  const drawer = p.getByRole('dialog');
  await drawer.waitFor();
  ok((await drawer.innerText()).includes('CPCB guidance on recycler capacity'), 'source chip opens the drawer with the source title');
  ok((await drawer.innerText()).includes('CITED'), 'drawer shows source status');
  await shot('02-c102-erratum-drawer');
  await p.keyboard.press('Escape');
  ok((await p.getByRole('dialog').count()) === 0, 'Escape closes the drawer');
  await shot('02b-c102-detail');

  log('3. C-105b: R5 INCONCLUSIVE');
  await openClaim('C-105b');
  ok((await rule('R5').getAttribute('data-outcome')) === 'INCONCLUSIVE', 'R5 outcome INCONCLUSIVE');
  ok((await rule('R5').innerText()).includes('What would resolve this'), 'INCONCLUSIVE card shows "What would resolve this"');
  await shot('03-c105b-inconclusive');

  log('4. C-108: INSUFFICIENT, zero FLAGs');
  await openClaim('C-108');
  const outcomes = await p.locator('article.rule').evaluateAll((els) => els.map((e) => e.getAttribute('data-outcome')));
  ok(!outcomes.includes('FLAG'), `no FLAG cards (${outcomes.join(',')})`);
  ok(outcomes.includes('INSUFFICIENT_EVIDENCE'), 'has INSUFFICIENT_EVIDENCE cards');
  ok((await p.locator('article.rule.insufficient_evidence').first().innerText()).includes('What would resolve this'), 'INSUFFICIENT card shows next action callout');
  await shot('04-c108-insufficient');

  log('5. C-101 lineage chips');
  await openClaim('C-101');
  await p.locator('.lineage svg[role=img]').waitFor();
  const ev1 = p.locator('li[data-batch="B-0041"][data-seq="1"]');
  ok((await ev1.innerText()).includes('Handler confirmed'), 'B-0041 HANDOVER chip: Handler confirmed');
  const ev3 = p.locator('li[data-batch="B-0043"][data-seq="1"]');
  ok((await ev3.innerText()).includes('Same device, not witnessed'), 'B-0043 HANDOVER chip: Same device, not witnessed');
  ok((await p.locator('li[data-batch="B-0042"][data-seq="1"]').innerText()).includes('Buyer reported'), 'B-0042 HANDOVER chip: Buyer reported');
  ok((await p.locator('.lineage svg g[data-conf="dotted"]').count()) >= 1, 'SVG has a dotted (same-device) node');
  ok((await p.locator('.lineage svg g[data-conf="dashed"]').count()) >= 1, 'SVG has a dashed (buyer-reported) node');
  ok((await p.locator('.legend').innerText()).includes('Dotted'), 'legend present');
  await shot('05-c101-lineage');

  log('6. review actions and recycler response');
  await p.locator('#note').fill('e2e: please send the weighbridge slips');
  await p.getByRole('button', { name: 'Request evidence' }).click();
  await p.locator('.trail li').first().waitFor();
  await p.waitForFunction(() => document.querySelector('.trail li')?.textContent?.includes('weighbridge slips'));
  ok(true, 'auditor action with its note appears first in the trail');
  await p.getByLabel('Role').selectOption('REC-01');
  await p.locator('#resp').waitFor();
  await p.locator('#resp').fill('e2e: slips attached');
  await p.getByRole('button', { name: 'Send response' }).click();
  await p.waitForFunction(() => document.querySelector('.trail li')?.textContent?.includes('slips attached'));
  ok(true, 'recycler response is first in the trail (newest first)');
  await p.getByLabel('Role').selectOption('AUD-01');

  log('7. impact (public route)');
  const pub = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  await pub.goto(W + '/#/impact');
  await pub.locator('.metric').first().waitFor();
  ok((await pub.locator('.metric').count()) >= 5, 'metric cards rendered');
  const rtext = await pub.locator('.metric.refrig').innerText();
  ok(rtext.includes('No certificate exists for refrigerant'), 'refrigerant card states no certificate exists');
  ok((await pub.locator('.metric .chip.demo').count()) >= 1, 'DEMO VALUE badge on demo metrics');
  await pub.locator('.metric.refrig .chip.src').first().click();
  await pub.getByRole('dialog').waitFor();
  ok(true, 'ⓘ on refrigerant card opens source drawer');
  await pub.screenshot({ path: path.join(shots, '06-impact-drawer.png'), fullPage: true });
  await pub.keyboard.press('Escape');
  await pub.locator('.metric[data-metric="batteries_recorded"] .chip.src').click();
  ok((await pub.getByRole('dialog').innerText()).includes('Batteries with a first-handover record'), 'count metric ⓘ opens a drawer too');
  await pub.close();

  log('8. responsive');
  for (const w of [1024, 390]) {
    await p.setViewportSize({ width: w, height: 900 });
    await p.goto(W + '/'); await p.locator('table.claims tbody tr').first().waitFor();
    await noHScroll('list', w);
    if (w === 390) await shot('07-list-390');
    await openClaim('C-101'); await p.locator('.lineage svg[role=img]').waitFor();
    await noHScroll('detail C-101', w);
    if (w === 390) await shot('08-detail-390');
    else await shot('08-detail-1024');
    await p.goto(W + '/#/impact'); await p.locator('.metric').first().waitFor();
    await noHScroll('impact', w);
  }

  log('9. wording rule on source files and rendered UI');
  const banned = /verified|genuine|fraud/gi;
  const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]);
  const hits = [];
  for (const f of walk(path.join(root, 'web-review', 'src'))) {
    const t = fs.readFileSync(f, 'utf8').replace('It is not certified as genuine.', '');
    if (banned.test(t)) hits.push(f);
  }
  ok(hits.length === 0, `no banned words in web-review/src (${hits.join(', ') || 'clean'})`);
  await openClaim('C-101');
  const rendered = (await p.locator('body').innerText()).replace('It is not certified as genuine.', '');
  const m = rendered.match(banned);
  ok(!m, `no banned words in the rendered page (${m ? m.join(',') : 'clean'})`);
  await p.setViewportSize({ width: 1280, height: 900 });

  ok(pageErrors.length === 0, `no uncaught page errors ${pageErrors.join('; ')}`);
} catch (e) {
  failures++;
  console.log('  FAIL', 'exception:', e.message);
  await p.screenshot({ path: path.join(shots, 'failure.png'), fullPage: true }).catch(() => {});
}
await browser.close();
console.log(failures ? `\n${failures} check(s) failed` : '\nall checks passed');
process.exit(failures ? 1 : 0);
