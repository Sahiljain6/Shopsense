import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './tests/frontend', use: { baseURL: 'http://localhost:3000' } });
