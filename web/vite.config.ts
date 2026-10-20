import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The shared design tokens live in ../docs/design/tokens.css; allow Vite to read the repo root.
export default defineConfig({
  plugins: [react()],
  server: { fs: { allow: [".."] } },
});
