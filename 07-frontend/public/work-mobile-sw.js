/* ── Trace ──────────────────────────────────────────────
 * Story:    US-WRK-040 (the phone shell: installable, offline-first) TC-1, TC-4
 * Rules:    BR-WRK-045 (the phone is a WEB app — a manifest, a service worker
 *           and an offline store, served by the staff app's own build) ·
 *           BR-WRK-038 (help opens with no signal) · hard-won law 1
 * Tests:    src/features/work/mobile/serviceWorker.test.ts (the registration
 *           and the scope contract; a browser is what runs this file)
 * ───────────────────────────────────────────────────────
 *
 * The field app's service worker — and it is deliberately the smallest one
 * that can work.
 *
 * ⚠ **WHAT IT CACHES: THE APP SHELL, AND NOT ONE BYTE OF DATA.** The day's
 * jobs, the bundles and the help documents live in IndexedDB
 * (`offlineStore.ts`), written at sync by code that knows what a bundle IS.
 * A service worker caching API responses would be a SECOND store with its own
 * idea of freshness, and the two would disagree about what a technician is
 * standing in front of. So: `GET` for the shell, pass-through for everything
 * else.
 *
 * ⚠⚠ **THE SCOPE IS `/` AND THAT IS THE RISKIEST THING IN THIS FILE.**
 * A service worker's scope is its own directory, and the tenant segment is
 * dynamic (`/{tenant}/work/mobile/`), so there is no fixed directory under the
 * app to serve it from. Registering from the root gives scope `/`, which means
 * this worker sits in front of the STAFF app and the CUSTOMER PORTAL too.
 *
 * **So it is written to be inert for them, by construction rather than by
 * intention:**
 *
 *   1. `fetch` returns early — calling nothing, `respondWith` untouched — for
 *      every request that is not a GET, not same-origin, or is an `/api/`
 *      call. Not calling `respondWith` hands the request straight back to the
 *      browser, which is a true pass-through and not a re-fetch.
 *   2. A NAVIGATION is served from cache ONLY when its path is a field-app
 *      path (`/<tenant>/work/mobile…`). A clerk opening `/brazosbend/billing`
 *      with this worker installed gets the network, exactly as if it were not.
 *   3. A shell ASSET (`/assets/…`, content-hashed and immutable) is served
 *      cache-first because it is byte-identical for every surface — that is
 *      what the hash in its name means — so serving it from cache cannot show
 *      one app another app's code.
 *
 * If this worker ever needs to do more than that, narrow the scope first:
 * serve it from a fixed prefix and register with an explicit `scope`, which
 * needs a `Service-Worker-Allowed` header from `server.mjs`.
 *
 * ⚠ **THE CACHE NAME CARRIES A VERSION AND `activate` DELETES EVERY OTHER
 * ONE.** A shell cached from a previous deploy is how a technician runs last
 * week's bundle against this week's API for a fortnight. `index.html` is
 * served `no-cache` by `server.mjs`, so a network-first navigation picks up a
 * new build the moment there is a signal; the cache is the fallback and never
 * the source of truth.
 */

const CACHE = "sbh-work-mobile-v1";

/** The shell. `/` is here because `index.html` is what every route renders. */
const SHELL = ["/", "/work-mobile.webmanifest", "/work-mobile-icon.svg"];

self.addEventListener("install", (event) => {
  // `skipWaiting` so a technician who reloads gets the new worker rather than
  // waiting for every tab to close — on a phone there is only ever one tab, and
  // a worker stuck in `waiting` is indistinguishable from one that is broken.
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .catch(() => undefined)
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

/** Is this a path of the field app? `/<tenant>/work/mobile…` and nothing else. */
function isFieldAppPath(pathname) {
  return /^\/[^/]+\/work\/mobile(\/|$)/.test(pathname);
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  let url;
  try {
    url = new URL(request.url);
  } catch {
    return;
  }
  // Cross-origin (a font, a CDN) and the API are never this worker's business.
  // Returning without calling `respondWith` is a true pass-through.
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  // Content-hashed shell assets: cache-first. Byte-identical across surfaces.
  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(
      caches.match(request).then(
        (hit) =>
          hit ||
          fetch(request).then((response) => {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => undefined);
            return response;
          }),
      ),
    );
    return;
  }

  // Navigations: network-first, cache as the fallback — and ONLY for the field
  // app. Every other surface is left to the browser.
  if (request.mode === "navigate" && isFieldAppPath(url.pathname)) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put("/", copy)).catch(() => undefined);
          return response;
        })
        .catch(() => caches.match("/").then((hit) => hit || Response.error())),
    );
  }
});
