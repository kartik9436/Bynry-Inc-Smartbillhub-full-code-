import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// Throwaway build for the CR-018 Phase 0 token proof. Separate root, separate
// out dir, no React, nothing under src/ pulled in except the theme itself.
// Deleted with the rest of tailwind-specimen/ at the end of Phase 3.
export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  base: "./",
  plugins: [tailwindcss()],
  build: { outDir: "dist-specimen", emptyOutDir: true },
});
