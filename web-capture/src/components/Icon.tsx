// Small stroke icon set (24px grid, 1.75 stroke). Shared with web-capture; keep the copies identical.
import type { CSSProperties } from 'react';

const P: Record<string, string> = {
  arrow: 'M5 12h14M13 6l6 6-6 6',
  back: 'M19 12H5M11 18l-6-6 6-6',
  ext: 'M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5',
  check: 'M5 12.5l4.2 4.2L19 7',
  shield: 'M12 3l7.5 3v5.6c0 4.6-3.2 8.3-7.5 9.4-4.3-1.1-7.5-4.8-7.5-9.4V6L12 3zM8.6 12.2l2.4 2.4 4.4-4.6',
  link: 'M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1',
  scale: 'M12 4v16M7 20h10M5 8h14M5 8l-2.5 6a3 3 0 0 0 5 0L5 8zm14 0l-2.5 6a3 3 0 0 0 5 0L19 8z',
  camera: 'M4 8.5A1.5 1.5 0 0 1 5.5 7h2l1.5-2h6l1.5 2h2A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5v-9zM12 16.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z',
  file: 'M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM14 3v5h5M9 13h6M9 17h6',
  eye: 'M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  leaf: 'M5 19c0-8 5-13 15-14-1 10-6 15-14 15M5 19c3-4 6-7 10-9',
  battery: 'M4 8h14a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1zM21 11v2M7 11v2M10.5 11v2',
  phone: 'M8 3h8a1.5 1.5 0 0 1 1.5 1.5v15A1.5 1.5 0 0 1 16 21H8a1.5 1.5 0 0 1-1.5-1.5v-15A1.5 1.5 0 0 1 8 3zM11 18h2',
  snow: 'M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9M9.5 4.5L12 7l2.5-2.5M9.5 19.5L12 17l2.5 2.5',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4',
  spark: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3zM19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2z',
  users: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20c.6-3.6 3.2-6 6.5-6s5.9 2.4 6.5 6M16 4.5a3.5 3.5 0 0 1 0 6.5M18 14c2 .7 3.2 2.8 3.5 6',
  lock: 'M6 11h12a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1zM8 11V8a4 4 0 1 1 8 0v3',
  alert: 'M12 4l9 16H3l9-16zM12 10v4.5M12 17.5v.01',
  help: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5v.7M12 17v.01',
  print: 'M7 9V3h10v6M7 17H5a1 1 0 0 1-1-1v-5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5a1 1 0 0 1-1 1h-2M7 14h10v7H7v-7z',
  refresh: 'M20 11a8 8 0 0 0-14.6-4.6L4 8M4 4v4h4M4 13a8 8 0 0 0 14.6 4.6L20 16M20 20v-4h-4',
  globe: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3.5 9h17M3.5 15h17M12 3c2.5 2.6 3.7 5.6 3.7 9s-1.2 6.4-3.7 9c-2.5-2.6-3.7-5.6-3.7-9s1.2-6.4 3.7-9z',
  chat: 'M4 18.5V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H7.5L4 20.5v-2zM8 9h8M8 12.5h5',
  box: 'M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3zM4 7.5l8 4.5 8-4.5M12 12v9',
  qr: 'M4 4h6v6H4V4zM14 4h6v6h-6V4zM4 14h6v6H4v-6zM14 14h2v2h-2zM18 14h2v2M14 18h2M18 18h2v2h-2',
  bolt: 'M13 3L5 13.5h6L10 21l8-10.5h-6L13 3z',
  layers: 'M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5M3 17.5l9 5 9-5',
  sun: 'M12 16.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9zM12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4',
  out: 'M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 16l4-4-4-4M14 12H4',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4.5 20.5c.8-3.8 3.8-6 7.5-6s6.7 2.2 7.5 6',
  mic: 'M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3',
  send: 'M4 12l16-8-6 16-2.5-6.5L4 12z',
  edit: 'M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4',
  clip: 'M20 11.5l-8.3 8.3a5 5 0 0 1-7-7L13 4.5a3.3 3.3 0 0 1 4.7 4.7l-8.3 8.3a1.7 1.7 0 0 1-2.4-2.4L14.5 7.5',
  wifiOff: 'M3 3l18 18M8.5 16.5a5 5 0 0 1 7 0M5 13a10 10 0 0 1 4.5-2.6M19 13a10 10 0 0 0-2.2-1.6M2 9.5a15 15 0 0 1 4.6-2.9M22 9.5A15 15 0 0 0 11 5.2M12 20h.01',
};
export type IconName = keyof typeof P;

export function Icon({ name, size, className, style, title }: { name: IconName; size?: number; className?: string; style?: CSSProperties; title?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={size ?? 20} height={size ?? 20} className={`ic ${className ?? ''}`} style={style}
      fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden={title ? undefined : true} role={title ? 'img' : undefined} aria-label={title}>
      <path d={P[name]} />
    </svg>
  );
}

/** Brand mark: an eye whose iris is a chain link. */
export function Mark({ size = 30 }: { size?: number }) {
  return (
    <svg viewBox="0 0 40 40" width={size} height={size} aria-hidden="true" className="mark">
      <rect width="40" height="40" rx="11" fill="var(--forest-fill)" />
      <path d="M6.5 20S11.5 11.5 20 11.5 33.5 20 33.5 20 28.5 28.5 20 28.5 6.5 20 6.5 20z" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinejoin="round" />
      <rect x="13.2" y="17.2" width="8.2" height="5.6" rx="2.8" fill="none" stroke="#e6c873" strokeWidth="2" />
      <rect x="18.6" y="17.2" width="8.2" height="5.6" rx="2.8" fill="none" stroke="#fff" strokeWidth="2" />
    </svg>
  );
}
