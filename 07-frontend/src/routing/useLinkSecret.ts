// ── Trace ──────────────────────────────────────────────
// Change:   decision log 2026-10-22 *"One-time link secrets travel in the URL
//           FRAGMENT, not the query string"* (coordinator, lane MERGE-ACCESS)
// Used by:  features/identity/SetPasswordPage.tsx · portal/signin/ForgotPassword.tsx
// Tests:    routing/linkSecret.test.ts (the pure half) · the two pages' own tests
// ───────────────────────────────────────────────────────
/**
 * The page-side half of `linkSecret`: hold a one-time link's secret in state
 * and take it off the address bar.
 *
 * ⚠ **IT RE-READS ON EVERY LOCATION CHANGE, NOT ONLY ON MOUNT.** A link that
 * differs from the page already open only by its FRAGMENT does not reload the
 * document — pasting the emailed link into the tab that is already showing
 * *Forgot your password?* is a same-document navigation. Reading once on mount
 * (what a query-string link could get away with, because changing the query
 * reloads) left that person on the ask form with the secret sitting in the
 * address bar. Found by the merge walk on 2026-10-22.
 *
 * The secret is held after the address is cleaned, so the replace never
 * switches the screen back to "no link".
 */
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { carriesLinkSecret, readLinkSecret, strippedLocation } from "@/routing/linkSecret";

export function useLinkSecret<K extends string>(keys: readonly K[]): Partial<Record<K, string>> {
  const location = useLocation();
  const navigate = useNavigate();
  const [held, setHeld] = useState(() => readLinkSecret(location, keys));
  useEffect(() => {
    if (!carriesLinkSecret(location, keys)) {
      return;
    }
    setHeld(readLinkSecret(location, keys));
    navigate(
      { pathname: location.pathname, ...strippedLocation(location, keys) },
      { replace: true },
    );
  }, [keys, location, navigate]);
  return held;
}
