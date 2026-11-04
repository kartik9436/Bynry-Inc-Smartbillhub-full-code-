// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-013 (EP-CWP-04) TC-1 — a draft that survives a closed tab.
//           Screens: CWP-047 · CWP-009
// Rules:    US-CWP-013 §2 (*"A draft holds no allocated number until submit"*
//           — so the thing in the URL is a capability, NOT a reference) ·
//           BR-CWP-028 (a reference is what a guest is given at the END)
// Tests:    src/portal/guest/StartService.test.tsx
// ───────────────────────────────────────────────────────
/**
 * THE DRAFT LINK'S TOKEN — 122 bits from the browser's own CSPRNG.
 *
 * ⚠ **IT IS NOT A REFERENCE AND IS NEVER SHOWN AS ONE.** The applicant has
 * been promised nothing yet; the token is only how they get back to their own
 * typing. `SR-26-nnnn` is allocated at submit and is the first thing this
 * journey shows anybody.
 *
 * ⚠ **AND IT IS GENERATED HERE RATHER THAN ASKED FOR.** A round trip to mint
 * an id before the first keystroke would put a network call between a person
 * and the first box on the form; a `PUT` to a token the browser chose is one
 * call, made when they have actually typed something.
 *
 * `crypto.randomUUID` exists in every browser this product supports and in
 * jsdom; the fallback is for a server-render pass, where nothing is typed.
 */
export function newDraftToken(): string {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi !== undefined && typeof cryptoApi.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }
  return `d${Date.now().toString(36)}${Math.random().toString(36).slice(2, 14)}`;
}
