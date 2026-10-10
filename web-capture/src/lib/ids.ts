import { load, save } from './store';

const CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

/** ULID made on the device; used as the Idempotency-Key for every POST. */
export function ulid(): string {
  let t = Date.now();
  let time = '';
  for (let i = 0; i < 10; i++) { time = CROCKFORD[t % 32] + time; t = Math.floor(t / 32); }
  const rnd = crypto.getRandomValues(new Uint8Array(16));
  let r = '';
  for (let i = 0; i < 16; i++) r += CROCKFORD[rnd[i] % 32];
  return time + r;
}

let memDevice: string | null = null;
/** Random per-install device id (SHAURYA.md 3.6): same id on the confirm page means SAME_DEVICE. */
export function deviceId(): string {
  const existing = load('oae.device_id') || memDevice;
  if (existing) return existing;
  const id = 'dev-' + ulid();
  memDevice = id;
  save('oae.device_id', id);
  return id;
}
