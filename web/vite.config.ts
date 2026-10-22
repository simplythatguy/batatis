import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";

// vite.config.ts is typechecked with `types: ["vite/client"]`, which does not include Node.
declare const process: { cwd(): string };

// The shared design tokens live in ../docs/design/tokens.css; allow Vite to read the repo root.
// /api/* is proxied to VITE_ENGINE_URL, or http://127.0.0.1:8000 when that is unset.
// src/api/client.ts reads the same variable and calls that origin directly when it is set.
/**
 * docs/design/tokens.css starts with a Google Fonts @import (Inter + JetBrains Mono) that the eval HTML
 * artifacts in evals/ui-artifacts rely on, so the file keeps it. The app bundles its own fonts
 * (@fontsource-variable/inter, geist-mono), so the app's copy drops that one remote request.
 */
function dropRemoteTokenFonts(): Plugin {
  return {
    name: "batatis:drop-remote-token-fonts",
    enforce: "pre",
    transform(code, id) {
      if (!id.split("?")[0].endsWith("/docs/design/tokens.css")) return null;
      return { code: code.replace(/@import url\("https:\/\/fonts\.googleapis\.com[^"]*"\);\s*/g, ""), map: null };
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const ENGINE = env.VITE_ENGINE_URL ?? "http://127.0.0.1:8000";
  return {
    plugins: [dropRemoteTokenFonts(), react()],
    server: {
      fs: { allow: [".."] },
      proxy: { "/api": { target: ENGINE, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") } },
    },
  };
});
