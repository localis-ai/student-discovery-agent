import { defineWorkspace } from 'vitest/config';
import { resolve } from 'node:path';

export default defineWorkspace([
  {
    extends: './vitest.config.ts',
    test: {
      name: 'client', environment: 'jsdom', setupFiles: ['./vitest.setup.ts'],
      // Chat component tests drive the in-memory transport; real builds default to the BFF.
      env: { NEXT_PUBLIC_CHAT_MOCK: 'true' },
      include: ['src/**/*.test.{ts,tsx}'],
      exclude: ['src/config/**', 'src/**/*.server.test.ts', 'node_modules/**'],
    },
  },
  {
    extends: './vitest.config.ts',
    resolve: { alias: { '@': resolve(__dirname, './src'), 'server-only': resolve(__dirname, 'tests/helpers/server-only.ts') } },
    test: { name: 'server', environment: 'node', include: ['src/config/**/*.test.ts', 'src/**/*.server.test.ts'] },
  },
]);
