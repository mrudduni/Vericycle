import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/inter';
import '@fontsource-variable/fraunces/opsz.css';
import '@fontsource-variable/noto-sans-devanagari';
import '@fontsource-variable/jetbrains-mono';
import './i18n';
import './theme.css';
import './styles.css';
import App from './App';
import { flush } from './lib/queue';

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);

if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => { void navigator.serviceWorker.register('/sw.js'); });
}
void flush();
