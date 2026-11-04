// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-040 TC-1 (*"the manifest offers Add to home screen; the
//           service worker registers"*) · TC-4 (airplane mode after first load)
// Rules:    BR-WRK-045 (the phone is a web app — installable, offline-first)
// Tests:    src/features/work/mobile/serviceWorker.test.ts
// ───────────────────────────────────────────────────────

/** Where the worker and the manifest are served from. Root, because a service
 *  worker's scope is its own directory and the tenant segment is dynamic — see
 *  `public/work-mobile-sw.js` for the whole argument and how it is made safe. */
export const FIELD_SW_URL = "/work-mobile-sw.js";
export const FIELD_MANIFEST_URL = "/work-mobile.webmanifest";

/**
 * Register the field app's service worker, and put the manifest link in the
 * document so the browser offers *Add to home screen*.
 *
 * ⚠ **IT NEVER THROWS AND NEVER BLOCKS THE APP.** A service worker is refused
 * outright on an insecure origin, in some private modes, and by policy on
 * managed handsets; the manifest link is refused by nothing but can still fail
 * on a locked-down DOM. **None of that should stop a technician seeing their
 * day** — the app works without either, it simply is not installable and does
 * not open offline. So every path here degrades quietly, and the ONE thing that
 * is not quiet is the sync marker, which goes on telling the truth about when
 * the phone last reached the server.
 *
 * ⚠ **THE MANIFEST LINK IS ADDED HERE RATHER THAN IN `index.html`.** One
 * `index.html` serves the staff app, the customer portal and this, so a
 * `<link rel="manifest">` in it would offer to install the FIELD app to a
 * billing clerk who opened the dashboard — with the field app's name and icon.
 */
export async function registerFieldServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  addManifestLink();
  try {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return null;
    return await navigator.serviceWorker.register(FIELD_SW_URL);
  } catch {
    return null;
  }
}

function addManifestLink(): void {
  try {
    if (typeof document === "undefined") return;
    if (document.querySelector('link[rel="manifest"]')) return;
    const link = document.createElement("link");
    link.rel = "manifest";
    link.href = FIELD_MANIFEST_URL;
    document.head.appendChild(link);
  } catch {
    /* a locked-down DOM: the app still runs, it is simply not installable */
  }
}
