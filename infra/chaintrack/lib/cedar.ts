import * as fs from 'fs';
import * as path from 'path';

/** Split policies/*.cedar into single statements (Verified Permissions stores one policy per resource). */
export function loadCedarPolicies(dir: string): { id: string; statement: string }[] {
  const out: { id: string; statement: string }[] = [];
  for (const file of fs.readdirSync(dir).filter((f) => f.endsWith('.cedar')).sort()) {
    const text = fs.readFileSync(path.join(dir, file), 'utf8')
      .split('\n').filter((l) => !l.trim().startsWith('//')).join('\n');
    for (const raw of text.split(/;\s*(?:\n|$)/)) {
      const statement = raw.trim();
      if (!statement) continue;
      const m = statement.match(/@id\("([^"]+)"\)/);
      if (!m) throw new Error(`Cedar policy in ${file} has no @id: ${statement.slice(0, 60)}`);
      out.push({ id: m[1], statement: statement + ';' });
    }
  }
  return out;
}
