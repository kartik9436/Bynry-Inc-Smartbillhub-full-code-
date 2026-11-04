// ── Trace ──────────────────────────────────────────────
// Change:   decision log 2026-10-22 *"One-time link secrets travel in the URL
//           FRAGMENT, not the query string"* (coordinator, lane MERGE-ACCESS)
// Used by:  features/identity/SetPasswordPage.tsx (staff set-password link) ·
//           portal/signin/ForgotPassword.tsx (customer portal reset link)
// Tests:    routing/linkSecret.test.ts
// ───────────────────────────────────────────────────────
/**
 * READ A ONE-TIME LINK'S SECRET FROM THE ADDRESS, ONCE, AND SAY HOW TO TAKE IT
 * OFF THE ADDRESS BAR.
 *
 * Emailed one-time links put their secret in the FRAGMENT (`#token=…`), which a
 * browser never sends to a server — so no web server, proxy or CDN log ever
 * holds it. Links emailed before that change carry it in the QUERY
 * (`?token=…`) and stay valid for their lifetime, so both are read and **the
 * fragment wins** where both carry a value.
 *
 * `strippedLocation` is what the address bar should show afterwards: the same
 * path, every OTHER query parameter kept, no fragment. Callers replace history
 * with it, so neither Back nor a shared screenshot of the bar holds the secret.
 */

export interface AddressParts {
  search: string;
  hash: string;
}

function paramsOf(raw: string, lead: "?" | "#"): URLSearchParams {
  return new URLSearchParams(raw.startsWith(lead) ? raw.slice(1) : raw);
}

/** The values of `keys`, fragment first, then query; a missing key is absent. */
export function readLinkSecret<K extends string>(
  location: AddressParts,
  keys: readonly K[],
): Partial<Record<K, string>> {
  const fragment = paramsOf(location.hash, "#");
  const query = paramsOf(location.search, "?");
  const found: Partial<Record<K, string>> = {};
  for (const key of keys) {
    const value = fragment.get(key) || query.get(key);
    if (value) {
      found[key] = value;
    }
  }
  return found;
}

/** True when the address still carries any of `keys` in either place. */
export function carriesLinkSecret(location: AddressParts, keys: readonly string[]): boolean {
  const fragment = paramsOf(location.hash, "#");
  const query = paramsOf(location.search, "?");
  return keys.some((key) => fragment.has(key) || query.has(key));
}

/** The address with `keys` removed from the query and the fragment dropped. */
export function strippedLocation(
  location: AddressParts,
  keys: readonly string[],
): { search: string; hash: string } {
  const query = paramsOf(location.search, "?");
  for (const key of keys) {
    query.delete(key);
  }
  const rest = query.toString();
  return { search: rest ? `?${rest}` : "", hash: "" };
}
