import { useSyncExternalStore } from 'react';

const subscribe = (f: () => void) => { window.addEventListener('hashchange', f); return () => window.removeEventListener('hashchange', f); };
export const usePath = () => useSyncExternalStore(subscribe, () => location.hash.replace(/^#/, '') || '/');
export const navigate = (p: string) => { location.hash = p; };
