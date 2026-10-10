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
export const runCheck = (id: string) => call<Run>(`/claims/${encodeURIComponent(id)}/check`, { method: 'POST', body: {} });
export const postReview = (id: string, action: ReviewAction, note: string) =>
  call<unknown>(`/claims/${encodeURIComponent(id)}/reviews`, { method: 'POST', body: { action, note: note || undefined } });
export const getImpact = () => call<{ metrics: Metric[] }>('/impact', { auth: false }).then((d) => d.metrics);
export const getSource = (id: string) => call<Source>(`/sources/${encodeURIComponent(id)}`, { auth: false });
