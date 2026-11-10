/// <reference types="vitest" />
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

// Canonical v2 contract artifacts are owned by A. They are imported read-only from
// the spec pack so the web client never hand-maintains duplicate copies.
const contractsDir = fileURLToPath(
  new URL('../docs/specs/Mark1-Team-Spec/contracts', import.meta.url),
);

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backend = env.MARK1_BACKEND_URL || 'http://127.0.0.1:8000';
  return {
    plugins: [react()],
    resolve: { alias: { '@contracts': contractsDir } },
    server: {
      host: true,
      port: 5173,
      fs: { allow: ['..'] },
      // Real mode: same-origin /v2 calls are proxied to A's backend (cookies stay same-origin).
      proxy: mode === 'real' ? { '/v2': { target: backend, changeOrigin: false } } : undefined,
    },
    build: { sourcemap: true },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./tests/setup.ts'],
      include: ['tests/**/*.test.{ts,tsx}'],
    },
  };
});
