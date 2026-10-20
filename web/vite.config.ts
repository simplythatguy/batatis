import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The shared design tokens live in ../docs/design/tokens.css; allow Vite to read the repo root.
// /api/* goes to the engine (uvicorn engine.api:app, default http://127.0.0.1:8000); see src/api/client.ts.
const ENGINE = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    fs: { allow: [".."] },
    proxy: { "/api": { target: ENGINE, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") } },
  },
});
