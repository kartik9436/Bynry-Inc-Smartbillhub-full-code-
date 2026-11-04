// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-003 (EP-CWP-02) · US-CWP-002. Screen: CWP-002 at
//           `/{tenant}/portal/pay`
// Rules:    CR-068 §11c (one page per CWP screen) · BR-CWP-005 (the tenant is
//           the first path segment) · CR-068 R8 (a portal that is OFF shows
//           the holding page on EVERY route — `GuestPage` is where that is
//           checked, which is why this page composes it rather than
//           `GuestFrame`)
// Tests:    src/portal/guest/QuickPay.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import type { ApiClient } from "@/api/client";

import { GuestPage } from "./GuestPage";
import { QuickPayFindBill } from "./QuickPay";

/**
 * `CWP-002` — one route, and **no bill number in the address**.
 *
 * ⚠ **THE PAIR IS POSTED, NEVER PUT IN A URL.** A bill number and the postcode
 * of somebody's home in a query string end up in access logs, in browser
 * history and in a `Referer` header — the same reasoning `POST /public/track`
 * writes down one endpoint over. So this address carries nothing at all and
 * the form is the only way in.
 */
export function QuickPayPage(props: { client?: ApiClient }) {
  return (
    <GuestPage client={props.client}>
      <QuickPayFindBill client={props.client} />
    </GuestPage>
  );
}
