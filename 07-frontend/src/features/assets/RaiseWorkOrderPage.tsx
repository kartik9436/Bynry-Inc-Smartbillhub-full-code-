// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-038 (EP-WRK-07) — the Assets door: one form, four ways in.
//           Screen: WRK-24 — blueprint section 05 screen 27, pages 104-107,
//           FIGURE 42 (redrawn). Figure 41 is the as-built this replaces.
// Change:   CR-092-BRC01 step 2 lane 5 — screen 27 built to figure 42.
// Rules:    BR-WRK-056 (ONE form at `/{tenant}/assets/{assetId}/work-orders/new`;
//           it writes `work_orders.asset_id`; templates filtered by *applies to
//           asset types*) · BR-WRK-006 (an asset is an anchor) · BR-AST-534
//           (a control the state forbids is DISABLED WITH ITS REASON) ·
//           B14 rule 2 (one page header) · rule 4 (`Verb ✓` commits) ·
//           rule 11 (the consequence box) · rule 21 (Tailwind; on
//           route-b-migrated.txt) · rule 31 (no database id is a visible
//           value) · rule 32 (one sentence per section) · rule 36 (the kit) ·
//           rule 38 (the UI rules settle how a form is BUILT) · rule 39
//           (label → input → helper) · rule 41 (the product matches the
//           blueprint) · rule 42 (built from the drawing AS AN IMAGE)
// Tests:    src/features/assets/RaiseWorkOrder.test.tsx
// Impacts:  src/features/work/workEndpoints.ts · src/App.tsx ·
//           src/routing/screenIds.ts · the eight controls that open it
// ───────────────────────────────────────────────────────
//
// ⚠ **ONE FORM, AND EIGHT DOORS ONTO IT — WHICH IS WHY THE FORM IS A ROUTED
// SCREEN AND NOT A MODAL.** `BR-WRK-056` names the action bar, the Maintenance
// history panel and the four `RaiseWorkOrderCheckbox` ticks as ways IN. A modal
// would have to be mounted on every one of those hosts, and the fourth host
// added later would get a slightly different one — which is how a product ends
// up with two raise forms that disagree about which templates apply.
//
// ⚠ **THE DOOR IS NO LONGER MISSING, AND THE BLUEPRINT'S PAGE 106 SAYS IT IS.**
// Figure 41's register reads *"there is no door — the screen is reached by URL
// only, and `BR-WRK-056` names two controls that are not built (`AST-B-02`)"*.
// That was true when the section was measured and was closed on 2026-09-12 by
// `DEF-MET-4965` (`2.237.6`): `AssetDetailPage.RaiseWorkOrderControl` is mounted
// at THREE sites — the header action bar, the Open work panel and the attention
// strip — and `AssetLifecycleTab` opens it from the certification wrench. With
// the four post-commit ticks that is eight ways in. The blueprint paragraph is
// stale, not wrong-at-the-time; it is reported rather than edited here.
//
// ⚠ **THE FIVE-SLOT HEADER IS MOUNTED, NEVER COPIED (hard-won law 2).** All six
// redrawn figures of section 05 carry the caption clause *"THE FIVE-SLOT HEADER
// FROM SCREEN 08 WITH ITS ATTENTION STRIP"*, and `AssetFlowShell` is the one
// place that composes it — kicker · title (the asset NUMBER) · status pill ·
// attention strip · context line. Screens 22-26 already mount it; this is the
// sixth and last. A second composition in this file would be the second copy
// that drifts.
//
// ⚠ **`apps/assets` WRITES NOTHING.** The form posts `POST /work-orders` with
// `asset_id`, which is Work's own door; the assets module gains no line of code
// for this feature and a test asserts that by name. This file lives under
// `features/assets/` because that is where a clerk is standing, not because the
// assets module owns the write.
import { useParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { RaiseWizard } from "@/features/work/raise/RaiseWizard";


/**
 * ⚠ **THERE IS NO SCREEN-BADGE CONSTANT HERE, AND ITS ABSENCE IS THE FIX**
 * (`DEF-MET-4978`). This file exported a `RAISE_WORK_ORDER_SCREEN` naming a
 * badge that had been RETIRED in wave D, while the registry three directories
 * away minted this route its own and said why in as many words. The constant
 * was imported by NOTHING, so the screen rendered the right badge and no user
 * ever saw the wrong one — which is exactly why it survived with `tsc`,
 * eslint, every test and `G29` green over it. A dead constant is not a badge,
 * so there was nothing for `G29` to disagree with.
 *
 * **Deleted rather than corrected, deliberately: a screen id written as a
 * string literal beside its route is a SECOND COPY free to drift** —
 * hard-won law 5 (*one generated file, committed once*) applied to an
 * identifier. The authority is `routing/screenIds.ts`; ask it.
 *
 * ⚠ **AND THE OBVIOUS DONE-TEST WOULD HAVE DESTROYED THE RECORD.** The
 * blueprint's register said done looks like *the retired id greps to nothing*.
 * It was 9 lines in 6 files and only TWO were wrong; the other seven are the
 * retirement ruling itself and two minting precedents. Obeying that grep
 * deletes the reason this cannot recur — **and so does repeating the retired
 * id HERE, which is why this paragraph does not spell it.** `DEF-MET-4978`
 * carries it; `routing/screenIds.ts` is the record.
 */

/**
 * The door's address — a SIBLING of `…/maintenance/new`, which is
 * `BR-WRK-056`'s own words.
 *
 * ⚠ **NO `:tenant` SEGMENT, LIKE EVERY ROUTE CONSTANT IN THIS PRODUCT.**
 * `App.tsx` mounts it under a `:tenant` route and registers it as
 * `ROUTE.slice(1)`. A constant carrying the tenant itself comes out
 * `:tenant/:tenant/assets/…`, matches nothing, and falls through to *"This
 * screen is not built yet"* with `tsc`, every test, the build and `G13` green
 * over it — `DEF-WRK-4051`, which made both of wave H's screens unreachable
 * from the day they shipped.
 */
export function raiseWorkOrderPath(assetId: string): string {
  return `/assets/${assetId}/work-orders/new`;
}

/** The route pattern, for `App.tsx` and for the tests that assert a control's
 *  destination against the ROUTER rather than against the screen registry. */
export const RAISE_WORK_ORDER_ROUTE = "/assets/:assetId/work-orders/new";

/**
 * **THE ASSETS DOOR, NOW THE SAME RAISE ARRIVING FILLED** — `CR-168-BRC10`
 * image 20, ruling 35 (*"the forms should be auto filled by the information"*).
 *
 * ⚠ **FIGURE 42's ONE-PAGE FORM IS RETIRED; `BR-WRK-056` HOLDS.** The address
 * is the same sibling of `…/maintenance/new`, the write is still Work's own
 * (`source: assets`, `asset_ids: [this asset]`), and templates are still the
 * ones that apply to the asset's TYPE and SERVICE (`GET
 * /assets/{id}/work-order-templates`). What changed is the shape: step 1 opens
 * with *From the asset* and the rest is the dispatcher's 1·4b and 1·4c — a
 * schedule, an optional assignee, a confirm — instead of *Template · Raise*.
 * The eight controls that open this address are untouched.
 */
export function RaiseWorkOrderPage(props: { client?: ApiClient }) {
  const { assetId = "" } = useParams();
  return <RaiseWizard origin={{ kind: "asset", assetId }} client={props.client} />;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-038@5e48ae29 (EP-WRK-07) · 10-execution-plan.md wave M task M4
// generated: 2026-09-05 by the CR-070 wave M build lane
// amended:   2026-09-13 by the CR-092-BRC01 step 2 lane 5 (screen 27 built to
//            figure 42: the five-slot header MOUNTED from AssetFlowShell, the
//            kit's SelectField with its helper, the WHAT HAPPENS NEXT box, the
//            ✓ on the commit and the footer order)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc✔ · G27✔ · G31 (this file is on route-b-migrated.txt, so
//        routeBUtilities.test.ts owns its classes) · G13 · i18n ×11
// ⚠ THAT `gates:` LINE IS PROSE AND NOTHING IN THIS REPOSITORY READS IT
//   (`DEF-MET-4975`, where it claimed a vitest run over a file that had never
//   existed on any branch). Hard-won law 1: a comment claiming a guarantee is
//   not the guarantee. `RaiseWorkOrder.test.tsx` exists; what it asserts is
//   what is asserted.
// exceptions: E1 the drawn "Note for the crew" field is NOT built — `create_work_order`
//             writes no `technician_notes`, so the input would be a dead control
//             (hard-won law 2). Reported with this lane, not silently shipped
//           · E2 figure 42 right-aligns the footer; the five sibling action screens
//             and B14 rule 38 put it left, and the rules win
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
