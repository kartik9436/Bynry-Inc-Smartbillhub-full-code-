// ── Trace ──────────────────────────────────────────────
// Change:  CR-144-BRC07 (FB3, FB7, FB10) — the product moves to static files on
//          S3 behind a CDN. There is no Node server in production, so the
//          browser calls a SEPARATE API host and the page-security policy that
//          `server.mjs` used to set as a header has to travel in the document.
// Rules:   PO 2026-09-28 (two hosts; "I dont want to get locked in with the cdn
//          from an cloud provider later if I move out from this cloud I dont
//          want this to be a blocker") · CLAUDE.md hard-won law 3 (defaults fail
//          closed — the unsafe option must be the one you type) · law 5 (ONE
//          generated source; derive, never copy).
// Tests:   scripts/checkBundleHost.mjs (FB10) · src/api/apiHref.test.ts (FB11) ·
//          scripts/deployConfig.test.mjs (this file's own unit cases).
// ───────────────────────────────────────────────────────
//
// SHARED BY `vite.config.ts` AND THE BUNDLE CHECK, so the rule that decides a
// build and the rule that checks its output are one statement rather than two
// that can drift.

import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

/**
 * The modes that produce a DEPLOYED bundle. Each has a committed `.env.<mode>`
 * and each is uploaded to a static host that serves no API — so each MUST name
 * its API origin.
 *
 * ⚠ `development` (the `npm run dev` server) and `test` are deliberately NOT
 * here: both are same-origin, the dev server proxies `/api`, and an empty base
 * URL is the correct answer for them.
 */
export const DEPLOYED_MODES = ["dev", "sandbox", "production"];

/** The API origin each deployed mode must carry — the PO's table, 2026-09-28. */
export const EXPECTED_API_ORIGIN = {
  dev: "https://api-smart360-dev.bynry.com",
  sandbox: "https://api-smart360-sandbox.bynry.com",
  production: "https://api-smart360.bynry.com",
};

/**
 * THE FAIL-CLOSED CHECK (FB3, hard-won law 3).
 *
 * Returns the API base URL for this mode, or THROWS. A build that silently fell
 * back to a relative URL would produce a bundle that calls its own static host:
 * every screen fails at once, in production, with nothing red anywhere in CI.
 * So the unsafe option is the one you have to type — and there is no way to
 * type it, because an empty value is refused for every deployed mode.
 *
 * A trailing slash is refused rather than trimmed: `client.ts` appends
 * `/api/...` itself, so `https://host/` would build `https://host//api/...`,
 * which is a different path to some servers and an open invitation to the next
 * reader to "fix" it in the wrong place.
 */
export function resolveApiBaseUrl(mode, env) {
  const raw = env.VITE_API_BASE_URL;
  const value = typeof raw === "string" ? raw.trim() : "";
  if (!DEPLOYED_MODES.includes(mode)) {
    return value; // same-origin by construction
  }
  if (value === "") {
    throw new Error(
      `VITE_API_BASE_URL is empty or missing for mode "${mode}".\n` +
        `A deployed bundle is served from a static host that answers no API, so a\n` +
        `relative base URL makes every screen in the product fail at once and nothing\n` +
        `in CI goes red. Set it in 07-frontend/.env.${mode} — for example\n` +
        `  VITE_API_BASE_URL=${EXPECTED_API_ORIGIN[mode] ?? "https://api.example.com"}`,
    );
  }
  if (value.endsWith("/")) {
    throw new Error(
      `VITE_API_BASE_URL must not end with "/" (mode "${mode}", value "${value}").\n` +
        `src/api/client.ts appends its own "/api/..." path to it.`,
    );
  }
  if (!/^https?:\/\/[^/]+$/.test(value)) {
    throw new Error(
      `VITE_API_BASE_URL must be a bare ORIGIN — scheme and host only, no path\n` +
        `(mode "${mode}", value "${value}").`,
    );
  }
  return value;
}

/**
 * CR-169-BRC10 — PostHog US cloud, the PO's answer 2. The ONLY ingest host a
 * build may name. Its recorder-asset sibling is on the page policy beside it.
 */
export const POSTHOG_INGEST_HOST = "https://us.i.posthog.com";

/** First 16 hex characters of SHA-256 — `config/product_analytics.py` spells it the same. */
export function keyFingerprint(key) {
  return createHash("sha256").update(key, "utf8").digest("hex").slice(0, 16);
}

/**
 * CR-169-BRC10 §2 row 4(a) — THE BUILD-TIME LOCK BETWEEN ENVIRONMENTS.
 *
 * PO 2026-10-04: *"Data from one environment must NEVER be sent to another
 * environment's PostHog project."* Returns `{ key, host, expectedHosts }` for
 * this mode, or THROWS:
 *
 *   * no key → `{ key: "" }`: analytics is OFF, in every mode (law 3);
 *   * a key with no `VITE_POSTHOG_PROD_KEY_FINGERPRINT` → refused, because the
 *     build cannot then prove the key is not production's;
 *   * a non-production mode whose key IS the production key → refused;
 *   * the production mode whose key is NOT the production key → refused;
 *   * a key with no expected web host → refused (it could never send, and a
 *     silent no-op is a broken deploy that looks healthy);
 *   * an ingest host other than PostHog US cloud → refused.
 *
 * The run-time half — send only on the expected host — is `src/analytics/config.ts`.
 */
export function resolvePosthogConfig(mode, env) {
  const key = typeof env.VITE_POSTHOG_KEY === "string" ? env.VITE_POSTHOG_KEY.trim() : "";
  if (key === "") {
    return { key: "", host: POSTHOG_INGEST_HOST, expectedHosts: "" };
  }
  const host = (env.VITE_POSTHOG_HOST ?? "").trim() || POSTHOG_INGEST_HOST;
  if (host !== POSTHOG_INGEST_HOST) {
    throw new Error(
      `VITE_POSTHOG_HOST must be ${POSTHOG_INGEST_HOST} (PostHog US cloud, PO 2026-10-04); got "${host}".`,
    );
  }
  const expectedHosts = (env.VITE_POSTHOG_EXPECTED_HOSTS ?? "").trim();
  if (expectedHosts === "") {
    throw new Error(
      `VITE_POSTHOG_KEY is set for mode "${mode}" but VITE_POSTHOG_EXPECTED_HOSTS is empty.\n` +
        `The bundle sends only from the web host(s) named there, so with none it would\n` +
        `never send — a deploy that looks healthy and records nothing.`,
    );
  }
  const prodFingerprint = (env.VITE_POSTHOG_PROD_KEY_FINGERPRINT ?? "").trim().toLowerCase();
  if (!/^[0-9a-f]{16}$/.test(prodFingerprint)) {
    throw new Error(
      `VITE_POSTHOG_KEY is set for mode "${mode}" but VITE_POSTHOG_PROD_KEY_FINGERPRINT is missing\n` +
        `or not 16 hex characters. Without it this build cannot prove its key is not the\n` +
        `PRODUCTION key. It is the first 16 hex of sha256(<production key>).`,
    );
  }
  const isProductionKey = keyFingerprint(key) === prodFingerprint;
  if (mode === "production" && !isProductionKey) {
    throw new Error(
      `The production build's VITE_POSTHOG_KEY is not the PRODUCTION key (its fingerprint does not\n` +
        `match VITE_POSTHOG_PROD_KEY_FINGERPRINT). Production data would go to another project.`,
    );
  }
  if (mode !== "production" && isProductionKey) {
    throw new Error(
      `The "${mode}" build carries the PRODUCTION key in VITE_POSTHOG_KEY. A ${mode} bundle must\n` +
        `never send to the production PostHog project (PO 2026-10-04). Use ${mode}'s own key.`,
    );
  }
  return { key, host, expectedHosts };
}

/**
 * THE BASE PAGE-SECURITY POLICY, READ OUT OF `server.mjs` RATHER THAN COPIED.
 *
 * ⚠ ONE GENERATED SOURCE (hard-won law 5). The policy already lives twice —
 * `server.mjs` and `06-backend/apps/integrations/page_policy.py` — because a
 * Node process cannot import a Python module, and `server.test.mjs` asserts
 * those two are byte-identical. A THIRD literal here would be the same drift
 * one file further along, so this parses `server.mjs` exactly as that test
 * does. Change the policy in the two places that already own it and this
 * follows with no edit.
 */
export async function readBasePolicyDirectives(
  serverMjs = fileURLToPath(new URL("../server.mjs", import.meta.url)),
) {
  const source = await readFile(serverMjs, "utf8");
  const block = source.match(/const BASE_POLICY = \[([\s\S]*?)\]\.join\("; "\);/);
  if (!block) {
    throw new Error(`BASE_POLICY not found in ${serverMjs} — the shape moved`);
  }
  const directives = [...block[1].matchAll(/"([^"]+)"/g)].map(([, one]) => one);
  if (directives.length < 6) {
    throw new Error("parsed too few directives from server.mjs — the shape moved");
  }
  return directives;
}

/**
 * The directives the API's own origin must be added to once it stops being
 * `'self'`.
 *
 * ⚠ **TWO OF THESE FOUR ARE NOT IN THE BRIEF AND ARE NOT OPTIONAL.** The brief
 * named `connect-src` (every fetch) and `img-src` (every served image). But
 * `DEF-INT-4410` put `frame-src` and `object-src` at `'self'` precisely because
 * the two screens that put a bill in front of a person EMBED an API URL:
 * `BillDetailPage` and `BillLayoutTab` frame `/api/{tenant}/…/document.pdf`, and
 * the portal's `DocumentPreview` shows it in an `<object>`. The day the API
 * moves to its own origin those stop being `'self'`, and leaving them out would
 * reproduce DEF-INT-4410 exactly — an empty grey box saying the content is
 * blocked, us blocking us, on the bill screen.
 *
 * `frame-ancestors` is NOT here on purpose: it governs who may frame THIS
 * document, and nothing changes about that.
 */
export const API_ORIGIN_DIRECTIVES = ["connect-src", "img-src", "frame-src", "object-src"];

/**
 * The base policy with the API origin added to the four directives above.
 * An empty origin (same-origin build) returns the base unchanged.
 *
 * ⚠ NO `*` IS ADDED AND NOTHING IS TIDIED. `'unsafe-inline'` on `style-src`
 * stays: the Leaflet map needs it. `style-src`'s and `font-src`'s Google Fonts
 * hosts stay: they are this product's own webfont (`DEF-INT-4261`), and without
 * them every screen renders in the fallback font, silently.
 */
export function policyWithApiOrigin(directives, apiOrigin) {
  if (apiOrigin === "") {
    return directives.join("; ");
  }
  return directives
    .map((directive) => {
      const name = directive.split(" ")[0];
      return API_ORIGIN_DIRECTIVES.includes(name) ? `${directive} ${apiOrigin}` : directive;
    })
    .join("; ");
}

/**
 * THE DEFAULT BASEMAP TILE ORIGIN — `DEF-INT-7430`, option (a), 2026-10-04.
 *
 * The baked meta policy is served to EVERY tenant and a meta policy
 * INTERSECTS with any header rather than being replaced by one, so a host that
 * is not named here can never be drawn from, whatever the API's per-tenant
 * policy says. Until this constant existed the meta tag named no tile host at
 * all, and both maps (Assets AST-03, Work WRK-09) were refused every tile on
 * every build.
 *
 * ⚠ **IT IS THE SHIPPED DEFAULT AND NOTHING BROADER** — no `https:`, no `*`,
 * no second host. The Esri egress is an ACCEPTED exposure (B16 §10-D6 for
 * Assets; decision log 2026-10-04 *"THE WORK MAP SHOWS AN ESRI STREET MAP"* for
 * Work). It must equal `06-backend/apps/integrations/live_calls.py`'s
 * `ESRI_TILE_HOST`, which is where the map actually gets its host from;
 * `src/api/pagePolicyTiles.test.ts` reads that file and fails if they drift.
 * It is a literal rather than a read because the Docker build context is
 * `07-frontend/` alone and cannot see the backend.
 *
 * ⚠ **WHAT IT DOES NOT FIX:** a tenant that points its basemap at its OWN tile
 * server is still refused on a static host. That is option (b) — the static
 * host sends a per-tenant header and the meta tag goes — and it stays open in
 * `DEF-INT-7430`.
 */
export const DEFAULT_TILE_ORIGIN = "https://server.arcgisonline.com";

/**
 * The policy the build bakes into `index.html`: the base, the API origin on
 * its four directives, and the default tile origin on `img-src` only.
 */
export function bakedPagePolicy(directives, apiOrigin) {
  return policyWithApiOrigin(directives, apiOrigin)
    .split("; ")
    .map((directive) =>
      directive.split(" ")[0] === "img-src" ? `${directive} ${DEFAULT_TILE_ORIGIN}` : directive,
    )
    .join("; ");
}

/**
 * The Vite plugin that writes the policy into `index.html` (`vite.config.ts`
 * registers it). Kept here, in plain JS, so a test can drive it directly.
 */
export function pagePolicyPlugin(apiBaseUrl) {
  return {
    name: "smartbillhub-page-policy",
    async transformIndexHtml(html) {
      const directives = await readBasePolicyDirectives();
      const policy = bakedPagePolicy(directives, apiBaseUrl);
      const meta = `<meta http-equiv="Content-Security-Policy" content="${policy}" />`;

      // ⚠ **INSERTED AFTER THE CHARSET META, NOT BEFORE IT, AND THAT IS NOT
      // TIDINESS.** Vite's `head-prepend` puts a tag FIRST, which pushed
      // `<meta charset>` down by the whole length of the policy — ~600 bytes
      // today. **A browser only looks for the charset declaration in the first
      // 1024 bytes**; past that it guesses the encoding and every non-ASCII
      // character in the document is mojibake. It fitted, with ~380 bytes to
      // spare, so nothing would have gone wrong TODAY — and the next host
      // added to the policy is what would have broken it, on a page that
      // builds and serves perfectly. The policy still precedes every element
      // that FETCHES anything, which is the only ordering it needs.
      //
      // It throws rather than falling back: a policy silently not inserted is
      // a page with no policy at all, which looks exactly like a page with one.
      const charset = html.match(/<meta[^>]+charset[^>]*>/i);
      if (charset === null) {
        throw new Error("index.html has no <meta charset> to place the security policy after");
      }
      return html.replace(charset[0], `${charset[0]}\n    ${meta}`);
    },
  };
}
