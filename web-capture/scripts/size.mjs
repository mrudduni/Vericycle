// Fails if the initial JS (entry chunk + its static imports) is over 200 KB gzipped (SHAURYA.md 3.7).
import { readFileSync, readdirSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
const html = readFileSync('dist/index.html', 'utf8');
const entry = [...html.matchAll(/(?:src|href)="\/(assets\/[^"]+\.js)"/g)].map((m) => m[1]);
let total = 0;
for (const f of entry) { const n = gzipSync(readFileSync('dist/' + f)).length; total += n; console.log(f, (n / 1024).toFixed(1), 'KB gz'); }
const lazy = readdirSync('dist/assets').filter((f) => f.endsWith('.js') && !entry.includes('assets/' + f));
for (const f of lazy) console.log('(lazy)', f, (gzipSync(readFileSync('dist/assets/' + f)).length / 1024).toFixed(1), 'KB gz');
console.log('initial JS total', (total / 1024).toFixed(1), 'KB gz');
if (total > 200 * 1024) { console.error('over budget'); process.exit(1); }
