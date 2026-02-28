import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['apps/mobile/hooks/__tests__/**/*.test.ts'],
  },
});
