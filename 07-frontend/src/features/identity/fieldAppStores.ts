// ── Trace ──────────────────────────────────────────────
// Change:  CR-187-BRC10 T-55 — the native field app (`field-app/`) replaces the
//          web field app; `FieldAppNotice`'s button is repointed at the app
//          stores IN THE CHANGE THAT SHIPS THE NATIVE APP (decision log
//          2026-10-21, twelve conflicts, #9), and not before.
// Rules:   hard-won law 2 (a hold carries the test that fires when it expires) ·
//          BR-WRK-043 (technicians use the mobile app only).
// ───────────────────────────────────────────────────────
/**
 * THE TWO STORE ADDRESSES OF THE NATIVE FIELD APP — empty today, on purpose.
 *
 * The native app has not shipped, so `FieldAppNotice`'s *Open the field app*
 * still points at the web field app's sign-in (`FIELD_APP_SIGN_IN`,
 * `/{tenant}/work/mobile/signin`). That is a HOLD, and it is held by
 * `FieldAppNotice.hold.dom.test.tsx`, which asserts both halves:
 *   - these two strings are empty, and
 *   - the routed button's address is the web field app's sign-in.
 *
 * The day either address is written here, that test goes RED and names what
 * to change: point `FieldAppNotice` at the store for the visitor's platform
 * (or both), retire or keep the web door per T-72, and then update the test's
 * expected destination. Writing a URL here and nothing else is exactly the
 * half-done repoint the hold exists to catch.
 *
 * The addresses come from the store consoles once the listings exist
 * (App Store Connect → the app's Apple ID; Play Console → the package name) —
 * they are the PO's to supply, never guessed.
 */
export const FIELD_APP_STORE_URLS = {
  /** e.g. `https://apps.apple.com/app/id<Apple ID>` — supplied by the PO. */
  appStore: "",
  /** e.g. `https://play.google.com/store/apps/details?id=<package>` — supplied by the PO. */
  googlePlay: "",
} as const;
