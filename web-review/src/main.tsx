import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/inter';
import '@fontsource-variable/fraunces/opsz.css';
import '@fontsource-variable/fraunces/opsz-italic.css';
import '@fontsource-variable/noto-sans-devanagari';
import '@fontsource-variable/jetbrains-mono';
import './theme.css';
import './styles.css';
import App from './App';

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
