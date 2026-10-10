import { COGNITO, idToken } from './auth';
import { DEV_AUTH, getSession } from './session';
import type { ClaimDetail, ClaimRow, Metric, ReviewAction, Run, Source } from './types';

const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? (DEV_AUTH ? 'http://127.0.0.1:8788' : '')).replace(/\/$/, '');

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}

async function call<T>(path: string, opts: { method?: string; body?: unknown; auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers['content-type'] = 'application/json';
  if (opts.auth !== false) {
    const s = getSession();
    if (DEV_AUTH && s) { headers['X-Dev-Role'] = s.role; headers['X-Dev-Party'] = s.party_id; }
    else if (COGNITO) { const t = await idToken(); if (t) headers.authorization = `Bearer ${t}`; }
  }
  let r: Response;
  try {
    r = await fetch(BASE + path, { method: opts.method ?? 'GET', headers, body: opts.body === undefined ? undefined : JSON.stringify(opts.body) });
  } catch {
    throw new ApiError('NETWORK', 'Could not reach the review API.', 0);
  }
  const j = (await r.json().catch(() => null)) as (T & { error?: { code: string; message: string } }) | null;
  if (!r.ok) throw new ApiError(j?.error?.code ?? 'ERROR', j?.error?.message ?? `Request failed (${r.status})`, r.status);
  return j as T;
}

export const listClaims = () => call<{ claims: ClaimRow[] }>('/claims').then((d) => d.claims);
export const getClaim = (id: string) => call<ClaimDetail>(`/claims/${encodeURIComponent(id)}`);
type CheckStart = Run | { status: 'RUNNING'; execution_id: string };

/** Runs ClaimGuard. Solo stages answer with the run; the Step Functions workflow answers 202 and the run appears on the claim. */
export async function runCheck(id: string, previousRanAt?: string | null): Promise<void> {
  const r = await call<CheckStart>(`/claims/${encodeURIComponent(id)}/check`, { method: 'POST', body: {} });
  if (!('status' in r) || r.status !== 'RUNNING') return;
  for (let i = 0; i < 40; i++) {
    await new Promise((res) => setTimeout(res, 1000));
    const d = await getClaim(id);
    if (d.run && d.run.ran_at !== previousRanAt) return;
  }
  throw new ApiError('TIMEOUT', 'ClaimGuard is still running. Reload in a moment to see the result.', 0);
}
export const postReview = (id: string, action: ReviewAction, note: string) =>
  call<unknown>(`/claims/${encodeURIComponent(id)}/reviews`, { method: 'POST', body: { action, note: note || undefined } });
export const getImpact = () => call<{ metrics: Metric[] }>('/impact', { auth: false }).then((d) => d.metrics);
export const getSource = (id: string) => call<Source>(`/sources/${encodeURIComponent(id)}`, { auth: false });
