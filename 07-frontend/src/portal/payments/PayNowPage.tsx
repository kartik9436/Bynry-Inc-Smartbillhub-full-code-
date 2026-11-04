// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-045 (EP-CWP-09). Screen: CWP-038 at
//           `/{tenant}/portal/pay-now`
// Change:   CR-085 step 2 lane 6 — the signed-in pay journey is THREE screens
//           (PO 2026-09-11: *"it should be 3 screens - confirmed"*), split IN
//           PLACE (*"ii). Your ruling was about the shape, not the
//           addresses."*). The shell this page used to declare inline now lives
//           in `payNowFlow.tsx` so that all three pages stand in ONE copy of it.
// Rules:    CR-068 §11c (one page per route) · BR-CWP-047 (nothing here is
//           cached) · BR-CWP-010 (the account is the switcher's, resolved once)
//           · B14 rule 31 (no account id in the address)
// Tests:    src/portal/payments/PayNow.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx — ⚠ **NOT TOUCHED BY THIS
//           LANE.** Six routes were registered there once, before four lanes
//           started, because two lanes committing one file means the second
//           silently reverts the first (hard-won law 11). The TWO NEW
//           ADDRESSES this split needs — `/pay-now/check` and `/pay-now/done` —
//           are reported to the merge lane and added centrally.
// ───────────────────────────────────────────────────────
import type { ApiClient } from "@/api/client";

import { PayNowShell } from "./payNowFlow";
import { PayNowView } from "./PayNow";

/**
 * `CWP-038` inside the signed-in shell.
 *
 * ⚠ **NO ACCOUNT ID IN THE ADDRESS** (B14 rule 31). The switcher knows which
 * account is being paid, and the id travels in the API path where the server
 * intersects it with the session's set (`BR-CWP-010`) — never in a browser bar,
 * where it would be a database id on screen.
 */
export function PayNowPage(props: { client?: ApiClient }) {
  return (
    <PayNowShell client={props.client}>
      {(accountId) => <PayNowView accountId={accountId} />}
    </PayNowShell>
  );
}
