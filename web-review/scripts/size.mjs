// Fails if the initial JS (entry chunk + its static imports) is over 150 KB gzipped.
import { readFileSync, readdirSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
const BUDGET = 150 * 1024;
const html = readFileSync('dist/index.html', 'utf8');
const entry = [...html.matchAll(/(?:src|href)="\/(assets\/[^"]+\.js)"/g)].map((m) => m[1]);
let total = 0;
for (const f of entry) { const n = gzipSync(readFileSync('dist/' + f)).length; total += n; console.log(f, (n / 1024).toFixed(1), 'KB gz'); }
const lazy = readdirSync('dist/assets').filter((f) => f.endsWith('.js') && !entry.includes('assets/' + f));
for (const f of lazy) console.log('(lazy)', f, (gzipSync(readFileSync('dist/assets/' + f)).length / 1024).toFixed(1), 'KB gz');
console.log('initial JS total', (total / 1024).toFixed(1), 'KB gz (budget 150)');
if (total > BUDGET) { console.error('over budget'); process.exit(1); }
