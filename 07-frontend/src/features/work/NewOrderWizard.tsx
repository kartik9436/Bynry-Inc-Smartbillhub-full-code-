// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-028 (the three-step New order wizard — Job & location ·
//           Schedule & crew · Confirm) TC-1..TC-6.  Screens: sub-screen of
//           Work-007 (`WM-20`, undrawn — r10's `WRK-12`)
// Rules:    BR-WRK-024 (source stamped *Dispatcher*) · BR-WRK-006 (an anchor
//           is required — premises, account or asset) · BR-WRK-008 (picking a
//           template on step 1 gives the order its copies) · B14 rules 3 (a
//           three-stage flow uses the stepper, not a page head) · 11 (a
//           consequence box before the commit) · 21 (Tailwind utilities; this
//           file is on route-b-migrated.txt in the commit that creates it) ·
//           31 (no database id is a visible value) · 32 (one sentence per
//           section) · 33 (a refusal caps at five or six words)
// Tests:    src/features/work/NewOrderWizard.test.tsx
// Impacts:  src/features/work/workEndpoints.ts · OrdersPage.tsx (its
//           `+ New work order` is released in the commit that lands this) ·
//           src/routing/screenIds.ts (WRK-12) · src/App.tsx (one route)
// ───────────────────────────────────────────────────────
//
// ⚠ **THREE STEPS, ONE WRITE** (`US-WRK-028` TC-4, the `BR-MET-112` shape).
// Nothing is written until Confirm: close the tab on step 2 and there is no
// row, no number burned from the `WO-` series and nothing for a dispatcher to
// wonder about. The frame keeps the entered state so Back loses nothing.
//
// ⚠ **THIS IS A THIRD DOOR ONTO ONE RAISE, NOT A SECOND WRITE.** `POST
// /work-orders` is what `commit_connection`, the five customer flows and the
// terminal already use (`07-endpoints.md` §1 row 14), so the wizard inherits
// `BR-WRK-008`'s copy, `BR-WRK-018`'s promise and `BR-WRK-006`'s anchor refusal
// without restating any of them. A wizard with its own write would be three
// rules to keep in step instead of none.
//
// ⚠ **B14 RULE 3 — A THREE-STEP FLOW GETS THE STEP BAR AND NOT A PAGE HEAD.**
// `WizardFrame` draws the numbered rail; this file draws no `PageHeader`.
//
// ⚠ **THE TEMPLATE PICKER OFFERS PUBLISHED TEMPLATES ONLY, AND THE SERVER
// REFUSES A DRAFT ANYWAY** (`US-WRK-032` TC-4). Both halves on purpose: the
// filtered list is why a clerk never meets the refusal, and the refusal is why
// a stale list cannot raise an order against a bundle that is still moving.
import { useSearchParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";

import { WORK_ORDERS_ROUTE } from "./WorkShell";
import { RaiseWizard } from "./raise/RaiseWizard";

/** r10's own badge for the new-order wizard — `WM-20` records it as a
 *  sub-screen of `Work-007`, so it carries r10's `WRK-12` and no `Work-` id. */
export const NEW_ORDER_WIZARD_SCREEN = "WRK-12";

/**
 * The address that RELEASES `OrdersPage`'s `empty.cta` hold.
 *
 * ⚠ **NO `/:tenant` — see `OrderDetailPage`'s note and `DEF-WRK-4051`.**
 * `App.tsx` registers this as `ROUTE.slice(1)` under a `:tenant` parent, so a
 * constant carrying the prefix matches nothing at all.
 */
export const NEW_ORDER_WIZARD_ROUTE = `${WORK_ORDERS_ROUTE}/new`;

/** The SCREEN-REGISTRY spelling, which DOES carry the tenant. */
export const NEW_ORDER_WIZARD_SCREEN_PATH = `/:tenant${WORK_ORDERS_ROUTE}/new`;

/** The raise opened on ONE building — what a premises page's *Raise work
 *  here* links to (`DEF-WRK-4752`). No tenant prefix, like every route constant. */
export function newOrderOnPremisesPath(premisesId: string): string {
  return `${NEW_ORDER_WIZARD_ROUTE}?premises=${encodeURIComponent(premisesId)}`;
}

export function newOrderWizardPath(tenant: string): string {
  return `/${tenant}${WORK_ORDERS_ROUTE}/new`;
}

/**
 * **THE DISPATCHER'S DOOR ONTO THE ONE RAISE** — `CR-168-BRC10` images 14–18.
 *
 * ⚠ **THE BODY MOVED TO `raise/RaiseWizard.tsx` AND THIS FILE KEPT ITS
 * ADDRESS.** Three doors open one raise (ruling 35), so the wizard is one
 * component and each door says only what arrives filled. This one reads
 * `?premises=` — the Premises and Account pages' *Raise work here* carries the
 * building (`DEF-WRK-4752`), so a clerk never types the address they were
 * already looking at.
 *
 * ⚠ **WHAT THIS FILE USED TO DRAW IS RETIRED BY A DEFECT AND THREE RULINGS:**
 * a free-text Premises asking for a uuid and a free-text Job type
 * (`DEF-WRK-9572`), a flat template list, a Due text box and an Area select
 * (ruling 24: the job takes its building's).
 */
export function NewOrderWizard(props: { client?: ApiClient }) {
  const [params] = useSearchParams();
  const premisesId = params.get("premises") ?? undefined;
  return <RaiseWizard origin={{ kind: "work", premisesId }} client={props.client} />;
}
