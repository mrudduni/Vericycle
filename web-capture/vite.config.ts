import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: { target: 'es2020', sourcemap: false, chunkSizeWarningLimit: 200 },
  server: { host: true, port: 5173 },
});
