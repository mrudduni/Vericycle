// localStorage wrapped in try/catch: private windows and blocked storage must not break the app.
export function load(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
export function save(key: string, value: string | null): void {
  try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch { /* ignore */ }
}
