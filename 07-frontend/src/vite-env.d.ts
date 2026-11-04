/// <reference types="vite/client" />

// Build-time deployment configuration (Vite inlines every `import.meta.env.VITE_*`
// read into the bundle, so these are facts of the BUILD, not of the running page).
// Each variable is declared here so it is typed at its single reading site
// instead of arriving as `any` off the `[key: string]` index signature.
//
// `VITE_TENANT_HOST_SUFFIX` was deleted with the cross-host handoff it existed
// for: since the PO's 2026-08-10 path-tenancy ruling a tenant lives at
// `/{tenant}` on the origin the browser is already on, so the app composes
// tenant addresses from `window.location`.
//
// ⚠ THE API NO LONGER LIVES ON THAT ORIGIN (CR-144-BRC07, PO 2026-09-28). The
// bundle is static files on S3 behind a CDN with no Node server, and the
// browser calls a SEPARATE API host — so `VITE_API_BASE_URL` below is back to
// being a build-time fact. The TENANT still travels in the PATH; only the
// ORIGIN moved.
//
// When one is needed again: declare it below, document it in
// 07-frontend/README.md §Deployment configuration, and carry it in
// 07-frontend/.env.example.

interface ImportMetaEnv {
  /**
   * CR-016 addendum (PO 2026-08-19) — the screen-id tag the PO asked for *"for
   * time bing"*. Set to `off` (any case) at BUILD time to remove the visible
   * bottom-right tag from every screen in the product:
   *
   *     VITE_SCREEN_ID_TAG=off npm run build
   *
   * Anything else, including absent, leaves it on. This is the ONE switch —
   * read in exactly one place, `src/routing/screenIds.ts`.
   *
   * ⚠ It does NOT govern `data-screen-id` / `data-screen-a1` on `<body>`. Those
   * are what the e2e suite and DEF-137's coverage gate read, and turning off a
   * diagnostic must not take the harness's handle with it. See
   * `components/ScreenIdTag.tsx`.
   *
   * ⚠ AND IT IS A BUILD-TIME VALUE, so hard-won law 4 applies verbatim: editing
   * a `.env` on a host that has already been built changes nothing until the
   * bundle is rebuilt.
   */
  readonly VITE_SCREEN_ID_TAG?: string;

  /**
   * CR-144-BRC07 (PO 2026-09-28) — THE ORIGIN EVERY API CALL GOES TO.
   *
   * A bare origin, scheme and host only, no trailing slash and no path:
   * `https://api-smart360-dev.bynry.com`. `src/api/client.ts` appends its own
   * `/api/{tenant}/…` to it, so a trailing slash would build a double one.
   *
   * Empty means SAME-ORIGIN, which is correct for `npm run dev` and for the
   * local docker-compose stack where `server.mjs` proxies `/api`. It is REFUSED
   * for the three deployed modes — `vite.config.ts` throws rather than build a
   * bundle that would call its own static host and fail every screen at once
   * (hard-won law 3).
   *
   * ⚠ BAKED IN AT BUILD TIME, like every `VITE_*`. Editing `.env.production` on
   * a host that already has a bundle changes nothing (hard-won law 4).
   *
   * Read in exactly ONE place in the app: `DEFAULT_BASE_URL` in
   * `src/api/client.ts`. Links that bypass the client go through
   * `apiHref()` in `src/api/apiHref.ts`, which reads the same constant.
   */
  readonly VITE_API_BASE_URL?: string;

  /**
   * CR-144-BRC07 — which environment this bundle is: `dev`, `sandbox` or
   * `production`. For display and diagnostics only.
   *
   * ⚠ NOTHING MAY BRANCH ON IT. A bundle that behaves differently by name is a
   * bundle nobody can test — the environment that matters is the one the API
   * origin points at, and that is a single value already.
   */
  readonly VITE_APP_ENV?: string;

  /**
   * CR-169-BRC10 (PO 2026-10-04) — THIS ENVIRONMENT'S PostHog project key.
   *
   * Supplied by the deployment pipeline's per-environment settings and NEVER
   * committed (it is public once built, by PostHog's design, but a committed
   * key is one copy-paste from the wrong environment). EMPTY OR ABSENT MEANS
   * ANALYTICS IS OFF — local, compose and test builds send nothing (law 3).
   *
   * `vite.config.ts` (`resolvePosthogConfig`) REFUSES the build when a dev or
   * sandbox key equals the production key, compared by the fingerprint in
   * `VITE_POSTHOG_PROD_KEY_FINGERPRINT`. Read in ONE place:
   * `src/analytics/config.ts`. Baked in at build time (law 4).
   */
  readonly VITE_POSTHOG_KEY?: string;

  /** CR-169-BRC10 — the ingest host. Only `https://us.i.posthog.com` (PO answer 2). */
  readonly VITE_POSTHOG_HOST?: string;

  /**
   * CR-169-BRC10 — the web host(s) this bundle may send from, comma-separated
   * (`app-dev.bynry.com`). On any other host the bundle sends nothing, so a dev
   * bundle uploaded to the production bucket cannot reach the dev project from
   * production pages. Read in `src/analytics/config.ts`.
   */
  readonly VITE_POSTHOG_EXPECTED_HOSTS?: string;

  /**
   * CR-169-BRC10 — the first 16 hex characters of the SHA-256 of the
   * PRODUCTION key. Read by the BUILD only (`scripts/deployConfig.mjs`), never
   * by the app: a fingerprint is not the key, so it may be committed.
   */
  readonly VITE_POSTHOG_PROD_KEY_FINGERPRINT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
