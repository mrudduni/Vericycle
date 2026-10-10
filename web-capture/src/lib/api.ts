import { getSession } from './session';
import { ulid } from './ids';
import { idToken } from './auth';

export const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || 'http://localhost:8787';
const DEV_AUTH = (import.meta.env.VITE_DEV_AUTH ?? '1') === '1' && !import.meta.env.VITE_USER_POOL_ID;

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

async function authHeaders(): Promise<Record<string, string>> {
  const s = getSession();
  if (!s) return {};
  if (s.cognito) {
    const tok = await idToken().catch(() => null);
    return tok ? { authorization: `Bearer ${tok}` } : {};
  }
  return DEV_AUTH ? { 'x-dev-party': s.party_id, 'x-dev-role': s.role } : {};
}

async function parse(res: Response): Promise<any> {
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const e = body?.error ?? {};
    throw new ApiError(res.status, e.code ?? 'HTTP_' + res.status, e.message ?? res.statusText);
  }
  return body;
}

export async function get<T = any>(path: string): Promise<T> {
  return parse(await fetch(API + path, { headers: await authHeaders() }));
}

/** POST with an Idempotency-Key. Pass the key in to retry the same logical request safely. */
export async function post<T = any>(path: string, body: unknown, key: string = ulid()): Promise<T> {
  return parse(await fetch(API + path, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'idempotency-key': key, ...(await authHeaders()) },
    body: JSON.stringify(body),
  }));
}

export async function sha256Hex(blob: Blob): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** Hash on the device, get a pre-signed URL that S3 only accepts if the bytes match the hash, upload. */
export async function uploadEvidence(blob: Blob, kind: string, batchId?: string): Promise<string> {
  const sha256 = await sha256Hex(blob);
  const p = await post('/evidence/presign', { kind, content_type: blob.type, size_bytes: blob.size, sha256, batch_id: batchId });
  const url = p.upload_url.startsWith('/') ? API + p.upload_url : p.upload_url;
  const res = await fetch(url, { method: 'PUT', headers: p.headers, body: blob });
  if (!res.ok) throw new ApiError(res.status, 'UPLOAD_FAILED', 'Upload failed. Please try again.');
  return p.evidence_id as string;
}

export function isNetworkError(e: unknown): boolean {
  return e instanceof TypeError || (e instanceof ApiError && e.status >= 502);
}
