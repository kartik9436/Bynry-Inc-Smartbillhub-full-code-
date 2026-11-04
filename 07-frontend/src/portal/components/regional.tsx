// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CWP-3994 — the tenant's date format and time zone reached the
//           staff app and not the portal, so every portal date rendered as a
//           raw `2026-08-14` where the drawing reads `31 Aug 2026`.
// Rules:    IS-8 (Settings → Regional & Formats feeds every date) ·
//           BR-SHL-023 (ONE formatting path) · hard-won law 3 (defaults fail
//           closed) · hard-won law 5 (one source, never a second copy)
// Tests:    src/portal/components/regional.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// THE WIRE BETWEEN THE PORTAL'S PAYLOAD AND THE PRODUCT'S ONE DATE FORMATTER.
//
// ⚠ **THIS FILE ADDS NO PROVIDER, NO CONTEXT AND NO FORMATTER.** All three
// exist: `components/TenantRegional.tsx` holds the context and its provider,
// `ShellWithSession.tenantRegionalOf` validates the stored string against the
// seven formats this build can draw, and `components/DateCell.formatDate` is
// the function that formats 83 staff screens. A second one of any of them is
// how a product ends up telling one customer two different stories about one
// date, and this repo has that shape twice already (two `TwoCol`s, two
// `formatQuantity`s). What was missing was the WIRE, and this is only that.
//
// ⚠ **WHY THE PORTAL COULD NOT SIMPLY BE PUT INSIDE THE EXISTING PROVIDER.**
// `ShellWithSession` is the staff shell and `/{tenant}/portal` is its SIBLING
// in `App.tsx` — not a descendant — so no amount of consuming the context from
// a portal screen would have found one. And moving the portal underneath it is
// not available either: that shell publishes from `GET /shell/display`, a
// staff-session read (`ShellDisplayRead` — every signed-in TENANT role),
// while the portal authenticates as `IsPortalCustomer` and would 403 on
// mount. The values ride on the portal's own front payload instead.
//
// ⚠ **THIS SENTENCE USED TO SAY `GET /settings/regional`, `an AnyTenantRole
// read`, AND BOTH HALVES WERE WRONG (`DEF-SHL-4283`, corrected 2026-09-06).**
// That endpoint was never `AnyTenantRole`: it is
// `SettingsReadAnyWriteSystemAdmin`, `{system_admin, executive}`, and a
// Billing Clerk reading it got `403 AUTH-002` — which is `DEF-SHL-4272`, a
// lockout that made the whole staff product unusable for that role for
// sixteen days. Nothing in THIS file was ever affected, and that is exactly
// why the sentence rotted unnoticed: a comment about somebody else's read is
// a claim nothing checks.
//
// ⚠ **AN UNSET SETTING PUBLISHES NOTHING, RATHER THAN PUBLISHING A GUESS.**
// The context's own value for *not known* is `null`, and its docstring says
// why: a default here is a plausible wrong answer, which is the defect and not
// the cure. `DEF-SHL-3964` fell through to `MM/DD/YYYY` and `UTC` on every
// screen in the product, forever, with no crash and no blank to notice. So
// when the tenant has not set a format this renders its children with the
// context left at `null`, and `usePortalDate` below hands back the server's
// own string unchanged — which declines to state a format rather than
// inventing one.
import type { ReactNode } from "react";

import { formatDate } from "@/components/DateCell";
import { tenantRegionalOf } from "@/components/ShellWithSession";
import { TenantRegionalProvider, useTenantRegional } from "@/components/TenantRegional";

import type { PortalFront } from "../api/guestClient";

/**
 * Publishes the tenant's Regional settings to every portal screen below.
 *
 * There are exactly TWO callers and they are the two frames every portal
 * screen passes through — `PortalShell` (signed in) and `GuestFrame` (not).
 * That is the same argument `ShellWithSession` makes for being the single
 * caller on the staff side: the frame is the one component the whole surface
 * goes through, so a screen cannot be born outside it.
 */
export function PortalRegionalProvider(props: { front: PortalFront; children: ReactNode }) {
  const regional = tenantRegionalOf(props.front.regional);
  if (regional === null) {
    // Not set, or set to a string this build cannot draw. Publish nothing.
    return <>{props.children}</>;
  }
  return <TenantRegionalProvider value={regional}>{props.children}</TenantRegionalProvider>;
}

/**
 * `(value) => string` for a date or an instant on a portal screen.
 *
 * ⚠ **IT RETURNS THE SERVER'S OWN STRING WHEN THE TENANT HAS SET NO FORMAT,
 * AND THAT IS NOT THE OLD BUG WEARING A HAT.** The old behaviour rendered
 * `2026-08-14` *while a format was set and being ignored*; this renders it only
 * when no drawable format exists to use. Declining to state a format is
 * honest; inventing `MM/DD/YYYY` for a utility in Berlin is the thing that
 * shipped a five-hour error to a Texas customer.
 *
 * `withTime` renders the instant in the tenant's zone — the half of `IS-8`
 * that made a payment taken at 7pm local show as the next day.
 */
export function usePortalDate(): (value: string | null | undefined, withTime?: boolean) => string {
  const regional = useTenantRegional();
  return (value, withTime = false) => {
    if (value === null || value === undefined || value === "") return "";
    if (regional === null) return value;
    return formatDate(value, regional.timeZone, regional.dateFormat, withTime);
  };
}
