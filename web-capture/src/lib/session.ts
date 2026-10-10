import { load, save } from './store';

export type Role = 'COLLECTOR' | 'AGGREGATOR' | 'RECYCLER' | 'AUDITOR' | 'PRODUCER';
export interface Session { party_id: string; role: Role; label: string; cognito?: boolean }

// Demo accounts (CONTRACT §8). Real sign-in (Cognito) replaces the picker once the method is chosen.
export const DEMO_PARTIES: Session[] = [
  { party_id: 'COL-118', role: 'COLLECTOR', label: 'Battery dealer · COL-118' },
  { party_id: 'COL-207', role: 'COLLECTOR', label: 'Phone exchange counter · COL-207' },
  { party_id: 'COL-330', role: 'COLLECTOR', label: 'AC technician · COL-330' },
  { party_id: 'AGG-01', role: 'AGGREGATOR', label: 'Aggregator · AGG-01' },
  { party_id: 'REC-01', role: 'RECYCLER', label: 'Lead recycler · REC-01' },
  { party_id: 'REC-02', role: 'RECYCLER', label: 'E-waste recycler · REC-02' },
  { party_id: 'AUD-01', role: 'AUDITOR', label: 'Auditor · AUD-01' },
];

export function getSession(): Session | null {
  try { const s = load('oae.session'); return s ? JSON.parse(s) as Session : null; } catch { return null; }
}
export function setSession(s: Session | null): void {
  save('oae.session', s ? JSON.stringify(s) : null);
  window.dispatchEvent(new Event('oae-session'));
}
