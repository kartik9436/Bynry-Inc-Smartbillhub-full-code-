// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-010 (EP-CWP-03) — Track anything. Screens: CWP-012
// Rules:    BR-CWP-005 · BR-CWP-007 · CR-068 §11c · CR-068 R8 (a portal that
//           is OFF shows the holding page and nothing else, on EVERY route) ·
//           B14 rule 36
// Defects:  DEF-CWP-4851 — this screen served in full at a utility that had
//           not switched its portal on.
// Tests:    src/portal/guest/TrackAnything.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";

import { GuestPage } from "./GuestPage";
import { TrackAnything } from "./TrackAnything";

/**
 * ⚠ **`GuestPage` AND NOT `GuestFrame` — `DEF-CWP-4851`.** This page read the
 * front payload only to draw the frame from it and never looked at
 * `is_live`, so a switched-off utility served the whole lookup form. The
 * switch is read once, in `GuestPage`, and every screen that composes it
 * inherits the answer.
 */
export function TrackPage(props: { client?: ApiClient }) {
  const client = props.client ?? api;
  return (
    <GuestPage client={client}>
      <TrackAnything client={client} />
    </GuestPage>
  );
}
