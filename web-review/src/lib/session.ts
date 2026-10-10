import { useSyncExternalStore } from 'react';
import type { Role } from './types';

export interface Session { party_id: string; role: Role; label: string }
export const DEV_AUTH = import.meta.env.VITE_DEV_AUTH === '1';
export const DEV_USERS: Session[] = [
  { party_id: 'AUD-01', role: 'AUDITOR', label: 'AUD-01 · Auditor' },
  { party_id: 'REC-01', role: 'RECYCLER', label: 'REC-01 · Recycler' },
  { party_id: 'PRD-01', role: 'PRODUCER', label: 'PRD-01 · Producer' },
];
const KEY = 'oae-review-dev-user';
const subs = new Set<() => void>();

function readDev(): Session {
  try { const id = localStorage.getItem(KEY); const u = DEV_USERS.find((x) => x.party_id === id); if (u) return u; } catch { /* storage blocked */ }
  return DEV_USERS[0];
}
let current: Session | null = DEV_AUTH ? readDev() : null;

export function getSession(): Session | null { return current; }
export function setSession(s: Session | null) {
  current = s;
  if (DEV_AUTH && s) { try { localStorage.setItem(KEY, s.party_id); } catch { /* storage blocked */ } }
  subs.forEach((f) => f());
}
export function useSession(): Session | null {
  return useSyncExternalStore((f) => { subs.add(f); return () => { subs.delete(f); }; }, getSession);
}
