import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Unit/component tests live next to the code they test (src/**/*.test.ts[x]).
//
// ⚠ THE DEFAULT ENVIRONMENT IS `node`, DELIBERATELY, AND IT MUST STAY THAT WAY
// (DEF-523, 2026-08-22). 200+ existing suites are `renderToStaticMarkup`
// first-paint tests that neither need nor want a DOM; switching the default to
// jsdom would slow every one of them and can change their behavior (globals,
// timers, `window`). Interactive suites OPT IN per file with the pragma on
// line 1:
//
//     // @vitest-environment jsdom
//
// VERIFIED on vitest 2.1.9 in this repo: the pragma is read per-file (vitest
// docs "environment" — docblock/comment style), the opted-in file gets a real
// DOM + @testing-library/user-event, and every file without it still runs in
// `node`. The first such suite is
// src/features/metering/ImportWorkflowPage.dom.test.tsx — use its `.dom.test.tsx`
// naming for interactive suites so the two layers stay visibly distinct.
// There is deliberately NO global setupFiles: `@testing-library/jest-dom/vitest`
// is imported by the jsdom files themselves, so the static suites' `expect`
// stays untouched.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
