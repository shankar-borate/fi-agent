import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  base: '/fi/',
  build: {
    outDir: 'dist',
    target: 'es2020',
  },
  server: {
    port: 5173,
    proxy: {
      '/fi/api': 'http://localhost:8000',
      '/fi/ws':  { target: 'ws://localhost:8000', ws: true },
    },
  },
});
