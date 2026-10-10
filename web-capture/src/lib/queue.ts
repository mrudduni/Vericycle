// Offline queue (F2): events made offline wait in IndexedDB with their Idempotency-Key and are sent
// once on reconnect. The server replays the first result for a repeated key, so each syncs exactly once.
import { post, uploadEvidence, isNetworkError } from './api';
import { ulid } from './ids';

export interface QueuedJob {
  id: string;           // also the Idempotency-Key
  path: string;
  body: any;
  photo?: Blob;         // weigh slip taken offline; uploaded first, then linked
  photoKind?: string;
  batchId?: string;
  created: number;
}

const DB = 'oae-queue', STORE = 'jobs';
let memory: QueuedJob[] = [];   // fallback when IndexedDB is unavailable

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE, { keyPath: 'id' });
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const req = fn(db.transaction(STORE, mode).objectStore(STORE));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function all(): Promise<QueuedJob[]> {
  try { return (await tx('readonly', (s) => s.getAll())) as QueuedJob[]; } catch { return memory; }
}
async function put(j: QueuedJob) { try { await tx('readwrite', (s) => s.put(j)); } catch { memory = [...memory.filter((x) => x.id !== j.id), j]; } }
async function del(id: string) { try { await tx('readwrite', (s) => s.delete(id)); } catch { memory = memory.filter((x) => x.id !== id); } }

function changed() { window.dispatchEvent(new Event('oae-queue')); }

/** Try to send now; if the network is down, keep it for later. Returns the server response or null if queued. */
export async function sendOrQueue(job: Omit<QueuedJob, 'id' | 'created'>): Promise<any | null> {
  const full: QueuedJob = { ...job, id: ulid(), created: Date.now() };
  if (!navigator.onLine) { await put(full); changed(); return null; }
  try {
    return await run(full);
  } catch (e) {
    if (!isNetworkError(e)) throw e;
    await put(full); changed();
    return null;
  }
}

async function run(j: QueuedJob): Promise<any> {
  const body = { ...j.body };
  if (j.photo) {
    const ev = await uploadEvidence(j.photo, j.photoKind ?? 'PHOTO', j.batchId);
    body.evidence_ids = [...(body.evidence_ids ?? []), ev];
  }
  return post(j.path, body, j.id);
}

let flushing = false;
export async function flush(): Promise<number> {
  if (flushing || !navigator.onLine) return 0;
  flushing = true;
  let sent = 0;
  try {
    for (const j of (await all()).sort((a, b) => a.created - b.created)) {
      try { await run(j); await del(j.id); sent++; }
      catch (e) { if (isNetworkError(e)) break; await del(j.id); /* rejected by server: drop, it will never succeed */ }
    }
  } finally { flushing = false; changed(); }
  return sent;
}

window.addEventListener('online', () => { void flush(); });
