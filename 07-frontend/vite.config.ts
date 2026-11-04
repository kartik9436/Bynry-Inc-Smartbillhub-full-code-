import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// @ts-expect-error — a plain .mjs module shared with the Node-run bundle check;
// it has no .d.ts on purpose, because duplicating its types would be the second
// copy hard-won law 5 is about.
import { pagePolicyPlugin, resolveApiBaseUrl, resolvePosthogConfig } from "./scripts/deployConfig.mjs";

// CR-018 Phase 0 · Tailwind v4 is wired here but reaches NO screen yet.
// `@tailwindcss/vite` only transforms a stylesheet that itself contains a
// Tailwind at-rule (`@import "tailwindcss"`, `@theme`, `@apply`). The app's
// entry sheet — src/styles/global.css — contains none, and nothing imports
// src/styles/tailwind.css, so this plugin currently emits ZERO BYTES into the
// app bundle.
//
// PROVED, AND PROVED THE ONLY WAY THAT HOLDS IN A SHARED TREE: at one commit,
// in an isolated worktree, built twice with nothing changed but this line. Both
// builds emit `index-DSjCOfdd.css`, 125.25 kB, sha256 6ab0e6ad…85f123ed —
// byte-identical with the plugin and without it.
// ⚠ Do NOT re-verify by comparing against a hash recorded on another day. The
// first attempt did, cited 125.21 kB / 06c80632…, and the number moved — because
// another lane edited SignupWizard.css, which has nothing to do with Tailwind.
// A bundle hash is a fact about the whole tree, not about one change.
//
// Phase 1 is what adds the import, deliberately, with a walkthrough; importing
// the theme sheet pulls in Preflight, which resets every base element.

// ── CR-144-BRC07 · THE PAGE-SECURITY POLICY MOVES INTO THE DOCUMENT ─────────
//
// `server.mjs` was the ONLY thing setting `Content-Security-Policy` on
// `index.html`, and **there is no Node server on S3**. So the policy is baked
// into the document per build, as a `<meta http-equiv>` tag, with this build's
// API origin added to the four directives that stop being `'self'` the day the
// API moves to its own host.
//
// ⚠ **HSTS CANNOT GO IN A META TAG** and no attempt is made to put it there —
// a browser ignores `Strict-Transport-Security` outside a real response header.
// The static host sends it. That is an infrastructure note (README §Deploying
// to S3), not code.
//
// ⚠ **WHAT A META TAG CANNOT DO, STATED RATHER THAN DISCOVERED.** `server.mjs`
// asked the API for a PER-TENANT policy and widened `img-src` with that
// tenant's registered basemap tile host (`DEF-INT-4287`). A document baked once
// and served to every tenant cannot do that, and a meta policy INTERSECTS with
// any header the static host later adds rather than being replaced by it — so
// the asset map's tiles are refused on a static host until that host is given a
// tile origin of its own. Recorded, not silently accepted: `DEF-INT-7430`.
// ⚠ **PARTLY FIXED 2026-10-04 (option (a)):** the baked tag now names the
// DEFAULT Esri tile origin on `img-src` (`deployConfig.DEFAULT_TILE_ORIGIN`),
// so both maps draw on the shipped default. A tenant's OWN tile server is
// still refused here; that is option (b), and it stays open.
// The plugin itself lives in `scripts/deployConfig.mjs` (moved 2026-10-04,
// `DEF-INT-7430`) so `src/api/pagePolicyTiles.test.ts` can drive the exact code
// that writes the tag without importing this Node-only file into `src/`.

export default defineConfig(({ mode }) => {
  // `loadEnv(mode, cwd, "")` reads `.env`, `.env.<mode>` and their `.local`
  // siblings. The empty prefix is deliberate: the check below has to be able to
  // see an ABSENT variable, and the default prefix would hide anything not
  // named VITE_.
  const env = loadEnv(mode, process.cwd(), "");

  // ⚠ FAIL CLOSED (hard-won law 3). This THROWS for `dev`, `sandbox` and
  // `production` when VITE_API_BASE_URL is missing, empty, trailing-slashed or
  // not a bare origin — the build stops with a sentence naming the file to fix.
  // It returns "" for the dev server and the test run, which are same-origin.
  const apiBaseUrl: string = resolveApiBaseUrl(mode, env);

  // CR-169-BRC10 · THE POSTHOG LOCK BETWEEN ENVIRONMENTS. THROWS when a dev or
  // sandbox build carries the production key (compared by fingerprint), when a
  // production build carries any other, and when a key arrives without the
  // fingerprint or the expected web host. No key → "" → analytics OFF.
  const posthog: { key: string; host: string; expectedHosts: string } = resolvePosthogConfig(mode, env);

  return {
    plugins: [tailwindcss(), react(), pagePolicyPlugin(apiBaseUrl)],
    // The one place the API origin becomes a fact of the bundle. It is read at
    // exactly one site in the app (`src/api/client.ts`'s DEFAULT_BASE_URL).
    define: {
      "import.meta.env.VITE_API_BASE_URL": JSON.stringify(apiBaseUrl),
      // The CHECKED values, so what the bundle carries is what the lock above
      // approved. Read in one place: `src/analytics/config.ts`.
      "import.meta.env.VITE_POSTHOG_KEY": JSON.stringify(posthog.key),
      "import.meta.env.VITE_POSTHOG_HOST": JSON.stringify(posthog.host),
      "import.meta.env.VITE_POSTHOG_EXPECTED_HOSTS": JSON.stringify(posthog.expectedHosts),
    },
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    // `DEF-DEP-10115` — one chunk per locale. The eleven catalogues are ~20 MB
    // of a ~24 MB bundle, and minifying them as ONE chunk is what took the
    // image build past its host's memory (exit 137, 2026-10-13). They are
    // still imported eagerly, so every chunk loads at start-up exactly as
    // before; only the build handles them one at a time.
    build: {
      reportCompressedSize: false,
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            const match = /\/i18n\/locales\/([^/]+)\.json$/.exec(id);
            return match ? `locale-${match[1]}` : undefined;
          },
        },
      },
    },
  };
});
