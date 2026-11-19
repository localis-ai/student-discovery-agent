import tseslint from 'typescript-eslint';

const FRAMEWORK_PATTERNS = ['next', 'next/*', 'react', 'react/*', 'server-only'];

export default [
  { ignores: ['dist/**', 'node_modules/**', 'coverage/**', 'src/generated/api/**'] },
  ...tseslint.configs.recommended,
  { rules: { 'no-restricted-imports': ['error', { patterns: FRAMEWORK_PATTERNS }] } },
  {
    // Shared primitives (hashing, cursors, body reading, field schemas, idempotency store) live in src/shared,
    // src/http and src/infrastructure. Other modules reach into experiences only through its public surface:
    // the route registration (app.ts), the activation read model (delivery) and the table (schema barrel).
    files: ['src/**/*.ts'],
    ignores: ['src/modules/experiences/**', 'src/**/*.test.ts'],
    rules: {
      'no-restricted-imports': ['error', {
        patterns: [
          { group: FRAMEWORK_PATTERNS },
          {
            group: [
              '@/modules/experiences/*',
              '!@/modules/experiences/activation',
              '!@/modules/experiences/experiences.routes',
              '!@/modules/experiences/experiences.table',
            ],
            message: 'Not exported by experiences. Shared primitives live in src/shared, src/http and src/infrastructure.',
          },
        ],
      }],
    },
  },
];
