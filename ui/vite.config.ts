import { defineConfig } from 'vite';
import { cpSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
export default defineConfig({
  plugins: [{name:'copy-desktop-ui',apply:'build',closeBundle(){
    cpSync(fileURLToPath(new URL('./static/',import.meta.url)),fileURLToPath(new URL('../runtime/static/',import.meta.url)),{recursive:true});
  }}],
  server: { proxy: { '/api': {target:'http://127.0.0.1:8765',changeOrigin:true}, '/media': {target:'http://127.0.0.1:8765',changeOrigin:true} } },
  build: { outDir: 'static', emptyOutDir: true }
});
