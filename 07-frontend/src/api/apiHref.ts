// ── Trace ──────────────────────────────────────────────
// Change:  CR-144-BRC07 (FB6) — the API moves to its own origin, so every URL
//          the app hands to a BROWSER (an `href`, an `<iframe src>`, a
//          `window.open`) has to carry that origin. These bypass `client.ts`
//          entirely, which is exactly why they were missed.
// Rules:   PO 2026-09-28 (two hosts) · B14 rule 43 (a shared behaviour is a
//          shared function, never seventeen copies) · hard-won law 2's mirror
//          (nothing in this repo fetches an `href`, so a broken one is silent).
// Tests:   src/api/apiHref.test.ts · scripts/checkBundleHost.mjs (the built
//          bundle actually contains this build's host and no other's).
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS, AND WHY NO SUITE WOULD HAVE CAUGHT THE BUG
// ══════════════════════════════════════════════════════════════════════════
// Seventeen sites in twelve files wrote `` `/api${tenantPath(…)}` `` by hand.
// Every one of them is a DOWNLOAD or a NEW TAB — a route sheet, a reading
// sheet, a bill PDF, a period pack, a remittance receipt, a plan agreement, a
// year's documents as a zip, a bill-layout preview in an iframe. That is the
// one shape with no test in this repository: `tsc` sees a string, eslint sees a
// string, and no unit test and no walkthrough ever FETCHES an `href`.
//
// The day the API moved, all seventeen would have opened
// `https://app.bynry.com/api/…` — the STATIC host, which answers `index.html`
// for an unknown path. So the clerk would not even get an error: they would get
// a new tab containing the application, with everything green everywhere.
//
// ⚠ `src/features/customers/closeOutEndpoints.ts` LOOKS like one of these and
// IS NOT. It imports `api` from the client and goes through it, so it already
// travels to the right origin. Changing it would be the mirror-image defect.

import { API_PREFIX, DEFAULT_BASE_URL } from "./client";

/**
 * THE ONE HELPER. A path that already carries its tenant segment — normally
 * `tenantPath("/routes/17/route-sheet")` — becomes the absolute URL a browser
 * can be handed.
 *
 *     apiHref(tenantPath(`/routes/${id}/route-sheet`))
 *     // build with an API origin →  https://api-smart360.bynry.com/api/brazosbend/routes/17/route-sheet
 *     // same-origin build        →  /api/brazosbend/routes/17/route-sheet
 *
 * It composes exactly what `apiPath()` composes for a fetch — `API_PREFIX` then
 * the tenant-carrying path — with the build's origin in front, so a link and a
 * fetch of the same endpoint can never disagree about where the API is.
 *
 * ⚠ IT TAKES THE PATH **AFTER** THE `/api` PREFIX AND ADDS THE PREFIX ITSELF.
 * Passing a path that already begins `/api` would build `/api/api/…`; the
 * helper refuses that rather than silently doubling it, because a 404 on a
 * download reaches a person as an empty tab.
 *
 * ⚠ AND IT IS NOT `apiPath()`. That one is the FETCH transport: it throws when
 * a tenant-scoped path has no tenant in scope, and it decides the tenant for
 * you. Callers here have already built their tenant-relative address through
 * `tenantPath`, which is the one place the app knows the URL's shape.
 */
export function apiHref(pathWithTenant: string): string {
  if (pathWithTenant.startsWith(API_PREFIX)) {
    throw new Error(
      `apiHref() was given a path that already begins "${API_PREFIX}": ` +
        `"${pathWithTenant}". Pass the path AFTER the prefix — the helper adds it.`,
    );
  }
  const path = pathWithTenant.startsWith("/") ? pathWithTenant : `/${pathWithTenant}`;
  return `${DEFAULT_BASE_URL}${API_PREFIX}${path}`;
}

/**
 * A link the SERVER wrote — a job's `result_link`, a report run's `file` —
 * made into the address a browser can be handed (DEF-TEN-9189).
 *
 * The server answers these as `/api/exports/{id}/file`: a path on ITS host with
 * no host in it. With the app and the API on two origins (app-dev.bynry.com and
 * api-smart360-dev.bynry.com) a plain `<a href>` resolves that path against the
 * APP's host, which answers its own `index.html`, and the browser saved it as
 * `file.htm`. Measured on the dev host 2026-10-02: the same path with the API
 * origin in front downloaded the CSV.
 *
 * The origin is this build's `VITE_API_BASE_URL` — the value every fetch
 * already uses, set per environment in `.env.dev`, `.env.sandbox` and
 * `.env.production` — so a link and a fetch can never point at different hosts.
 * A link that already carries a scheme (a signed storage URL) is returned
 * untouched, and a same-origin build (base `""`) keeps the path exactly as the
 * server wrote it.
 */
export function serverLinkHref(link: string, baseUrl: string = DEFAULT_BASE_URL): string {
  if (/^[a-z][a-z0-9+.-]*:/i.test(link) || link.startsWith("//")) {
    return link;
  }
  const path = link.startsWith("/") ? link : `/${link}`;
  return `${baseUrl}${path}`;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-144-BRC07 (deployment — three builds, one API origin)
// generated: 2026-09-28 by lane DEP-FRONTEND
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
