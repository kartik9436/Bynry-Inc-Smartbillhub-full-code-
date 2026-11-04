// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-001 (S14 premises detail — the BR-MET-045 tab set)
//           Screens: S14 (row → detail), links out to S15, S49/S50, S61
// Rules:    BR-MET-045 (Premises detail = Units · Assets · Accounts · Audit) ·
//           BR-MET-003 (services ⊆ the tenant's enabled set) ·
//           BR-MET-036 (occupancy is DERIVED — it renders, it never edits) ·
//           BR-MET-048 (every change is audited SERVER-side) ·
//           BR-SHL-011 (the open tab is URL state, so every tab is linkable) ·
//           BR-SHL-020 (the six A18 states, composed — never re-implemented) ·
//           BR-SHL-034 (dates only through the shared formatter)
// ───────────────────────────────────────────────────────
// S14 detail. Four tabs, and two of them are deliberately not tables of their
// own data:
//
//   · **Accounts** renders the honest "arrives with Accounts" state. The
//     customers module owns no tables in this wave, so an empty accounts table
//     here would assert "this premises has no accounts" — a claim nothing can
//     support. It names what it is waiting for and renders no fields.
//
//   · **Audit** does not re-implement the audit log. BR-MET-048 writes to the
//     ONE `audit_log`, and S61 already reads it with a filter vocabulary that
//     includes entity type + id — so this tab LINKS to that viewer, filtered to
//     this premises. One audit surface, one set of rules about masking.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {useNavigate, useParams, useSearchParams} from "react-router-dom";

import { api } from "@/api/client";
import { CityGisNote, useCityGis } from "@/features/metering/CityGis";
import type { ApiClient } from "@/api/client";
import {
  getAssets,
  getAuditLog,
  getPremisesDetail,
  getPremisesSubmeterReconciliation,
  getPremisesTypes,
} from "@/api/endpoints";
import type {
  AssetRow,
  AuditRow,
  PremisesDetail,
  SubmeterReconciliationRow,
  UnitRow,
} from "@/api/endpoints";
import { ButtonLink } from "@/components/Button";
// ── DEF-4739 · THE TABLE THE BLUEPRINT NAMES ──────────────────────────────
// The Units, Assets and Audit tabs drew `PlainTable` — the small in-panel table
// for a few rows of figures — so the search box, the filter chips, the column
// chooser, the pagination footer and the footer counts were absent from all
// three at once. `09-screen-conformance.md` and the three CR-089 conformance
// files each name `DataTable` + `FilterBar` by name.
import { DataTable } from "@/components/DataTable";
import { CustomFieldsView, useCustomFieldColumns } from "@/components/CustomFields";
import { FilterBar } from "@/components/FilterBar";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableFilterConfig, TableRequestState } from "@/components/tableTypes";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import type { MoneyBasis } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { ServiceChips } from "@/components/ServiceChips";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
// CLAUDE.md hard rule 3 / BR-SHL-023: ONE formatting path for a quantity, and
// it never renders without its unit.
import { UnitCell } from "@/components/UnitCell";
// BR-AST-031's pill + BR-AST-007's derived Test-due chip, in ONE cell the
// registry already draws. The blueprint's Assets frame draws both (`TEST DUE
// 30 SEP`), and a second implementation of a status pill is DEF-348's shape.
import { AssetStatusCell, assetDetailPath, sizeClassName, useSizeClassNames } from "@/features/assets/assetsShared";
import { actorLabel } from "@/features/audit/AuditLogPage";
// DEF-645 / DEF-4740: the sentence and the changed set are the audit module's,
// not this screen's — one presenter for every per-entity tab and for S61
// (BR-AUD-010). The columns below are this screen's arrangement of them.
import {
  AuditEventCell,
  auditEventSentence,
  auditFieldSet,
  auditText,
} from "@/features/audit/auditEvents";
import type { AuditFieldRow } from "@/features/audit/auditEvents";
import { apiErrorText, isPermissionDenied, ordinalDay } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
// CR-070 wave O — the build's panels live in Work, once, and BOTH hosts compose
// them. They were `features/customers/ConnectionDetailPage.tsx`'s until the PO
// ruled that screen one destination too many (§W.10).
import { WorkOrdersTab, useBuild } from "@/features/work/buildViews";
import { PendingBuildLink } from "@/features/work/buildRecord/PendingBuildLink";
import { accountDetailPath } from "@/features/customers/customersShared";
import { useTenantPath } from "@/routing/tenantPath";

import { CommonAreasTab } from "./CommonAreasTab";
import { StatusChangeDialog } from "./StatusChangeDialog";
import { OwnerAccountBlock } from "./OwnerAccount";
import {
  ownerAccountAsked,
  premisesOwnerAccount,
} from "@/features/metering/premisesOwnerContract";
import { PremisesEditModal, premisesTypesQueryKey } from "./PremisesListPage";
import {
  CELL_FULL,
  DASHBOARD_ROUTE,
  Dash,
  GuardedButton,
  PREMISES_PERMISSION,
  unitsAddPath,
  ROLE_SYSTEM_ADMIN,
  useAccessCell,
  useTenantRole,
  MetersCell,
  PREMISES_ROUTE,
  UNITS_ROUTE,
  auditViewerPath,
  detailTabFrom,
  premisesStatusTone,
  useRegional,
  unitDetailPath,
  unitStatusTone,
} from "./meteringShared";
import type { DetailTab, RegionalProps } from "./meteringShared";

// ── Pure pieces ────────────────────────────────────────────────────────────

/**
 * CR-018 Route B: the quiet-text colour, as a utility rather than a class.
 * `.met-muted` next door is the same colour at 45% and adds italics; this is
 * the 65% the prototype uses for a secondary line, written once here so the
 * three sites that need it cannot drift apart.
 */
const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/** The absent style B14 asks for: quiet AND italic, never a zero, never blank. */
const ABSENT = `italic ${MUTED}`;

// ── DEF-4739 · A `DataTable` OVER ROWS THE CLIENT ALREADY HOLDS ────────────
//
// `DataTable` is built for SERVER paging (IS-2), and these three tabs are not
// served that way: the units ride on `GET /premises/{id}`, the assets arrive in
// one `per=200` read that the Assets tile shares, and the audit window is the
// entity's own `AUDIT_TAB_ROWS`. So the search, the filter, the sort and the
// page are applied HERE, over rows that are already in memory, and the table is
// handed the page plus the filtered total — which is exactly what
// `SettingsPortalTips` does with the same component and the same reasons.
//
// ⚠ **THE TOTAL HANDED OVER IS THE FILTERED COUNT, NEVER THE UNFILTERED ONE.**
// A pager offering page 2 of rows nobody fetched is a control that cannot act,
// and the footer count beside it would be answering a different question from
// the rows above it.
//
// Both helpers are PURE and exported so a test drives the arithmetic without a
// browser — the paging boundary is where an off-by-one hides.

/** The rows this page of the table shows, out of the filtered set. */
export function tabRowsForPage<Row>(rows: readonly Row[], state: TableRequestState): Row[] {
  const from = (state.page - 1) * state.per;
  return rows.slice(from, from + state.per);
}

/**
 * Does this row match what was typed? `""` matches everything, which is what
 * `DataTable`'s debouncer sends for anything under IS-3's two-character
 * minimum — so a single letter narrows nothing here, exactly as it narrows
 * nothing on a served list.
 */
export function tabMatches(
  fields: readonly (string | null | undefined)[],
  query: string,
): boolean {
  if (query === "") {
    return true;
  }
  const needle = query.toLowerCase();
  return fields.some((field) => (field ?? "").toLowerCase().includes(needle));
}

/** The request state a tab opens on. Page size is the product's default (50). */
function tabTableState(sort: string): TableRequestState {
  return { q: "", sort, dir: "asc", page: 1, per: DEFAULT_PAGE_SIZE, filters: {} };
}

/**
 * The drawn footer sentence, under the kit's own `1–4 of 4` pager.
 *
 * ⚠ **IT IS A LINE BENEATH THE TABLE RATHER THAN PART OF THE PAGER, AND THAT
 * IS A STATED DIVERGENCE.** The blueprint draws one footer — `Showing 4 of 4 ·
 * 3 occupied, 1 vacant` — and `DataTable`'s pager is the kit's, shared by 27
 * lists; growing a per-screen slot in it to carry one sentence would be a kit
 * change for one tab. The two numbers the drawing asks for are both here and
 * both true; what differs is that they sit on the next line.
 */
// ⚠ **EXPORTED SINCE 2026-09-10.** The unit's Occupancy tab draws the same
// drawn footer sentence and had none, so a landlord asking how long their flat
// stood empty had to read it off the rows by counting. A second copy of this
// two-line component in `UnitDetailPage` is how two footers acquire two type
// scales (`DEF-MET-4766`); one definition, two callers.
export function TabFooterCounts(props: { children: ReactNode }) {
  return (
    <p className={`m-0 text-sm ${MUTED}`} data-tab-footer-counts="">
      {props.children}
    </p>
  );
}


/**
 * The PRM-02 tab set — **r10's FIVE, EXACTLY**: Overview · Units · Common areas
 * · Assets · Audit log.
 *
 * ⚠ **THE SIXTH — `accounts` — IS GONE, AND THE PO REMOVED IT (`DEF-578`,
 * 2026-08-22).** Their words, with five screenshots of r10 PRM-02: *"premises
 * details view does not match with this - look at button positions - look at
 * tabs and details within tabs"*. r10 draws five tabs and `Accounts` is in no
 * r10 drawing of this screen.
 *
 * ⚠ **BR-MET-045 NAMES IT, SO THIS IS A RULE CHANGE AND IT IS RECORDED AS ONE.**
 * The rule read *"Premises detail (Units/Assets/Accounts/Audit tabs) … per
 * PU-16/17"* — a PO walkthrough of the PREVIOUS design. It is AMENDED in
 * `04-docs/05-modules/04-metering/02-business-rules.md`, dated, with the PO's
 * sentence quoted, and CLAUDE.md's standing ruling is the ground: *"where
 * A1–A17's screen description contradicts r10, r10 is right and the spec is
 * stale"*, and r10 is THE reference since 2026-08-16.
 *
 * **Nothing is hidden by the removal.** The tab never listed a premise's
 * accounts — it rendered a stated absence saying `GET /accounts` declares
 * `unit_id` and no `premises_id` (DEF-473), so a premise's accounts are reached
 * through its units. That route is unchanged: the Units tab links every unit to
 * its detail, whose **Account** tab reads `GET /accounts?f.unit_id=`.
 *
 *   · **Overview** was never a "new" tab: it is the premises itself, and it has
 *     always rendered here — outside the strip, above the tabs, which is a
 *     placement the US-SHL-020 conversion reported as a delta and left. r10 puts
 *     it INSIDE the strip as tab one.
 *   · **Common areas** asserts a product capability — a first-class object with
 *     its own meters, its own plan, its own bill line and a MASTER ACCOUNT that
 *     is not a tenant. **The SHAPE is ruled (BR-MET-101, PO 2026-08-21): a
 *     common area IS a unit with a flag** — `is_common_area` is built, served
 *     and drawn on every unit surface — **but the BILL side still is not**, so
 *     the tab keeps stating that absence rather than drawing invented rows.
 */
export const PREMISES_TAB_IDS = [
  "overview",
  "units",
  "common-areas",
  "assets",
  // ── CR-162-BRC10 (2026-10-02) · THE BUILD TAB IS GONE FROM THE PREMISES ──
  //
  // PO, verbatim: *"when we have new connect request -we are traking the
  // progress from detail of new connect hense as shown in screenshot build ta
  // on premises is not required ;when premises is in pending status and if you
  // have new connect request asoscaiated to it then you can show link for
  // request to improve interaction"*. So the request's own page (NCT-02) is
  // the one place progress is tracked and actions are taken; this page keeps a
  // LINK to it in the header while the premises is Pending
  // (`PendingBuildLink`). It superseded CR-070 wave O's "the build comes to the
  // premises" (2026-09-04) at this list's own line. An old `?tab=build`
  // bookmark falls back to the first tab (`detailTabFrom`, BR-SHL-011).
  "work-orders",
  // Audit stays LAST: it is the trail, and a trail reads after the thing it is
  // a trail of.
  "audit",
] as const;
export const TAB_PARAM = "tab";
/** `?order=<id>` — the work-order drawer, opened over the Work orders tab.
 *  The same convention `NCT-02` used before wave O retired it, and the same one
 *  S29 uses over the reads list. */
export const ORDER_PARAM = "order";

export const premisesDetailQueryKey = (id: string) => ["premises", "detail", id] as const;
export const premisesAssetsQueryKey = (id: string) => ["assets", "by-premises", id] as const;

/**
 * The tab strip. `hasBuild` decides whether **Build** is offered at all.
 *
 * ⚠ **A TAB POINTING AT NOTHING IS DEAD UI** (hard-won law 2, `G13`), and
 * "this address has no connection work" is the ORDINARY answer rather than an
 * error — so the tab is absent, not empty. `undefined` means *not known yet*
 * and is treated as absent: offering a tab and then withdrawing it is worse
 * than offering it a moment late.
 */
export function premisesTabs(t: Translator): DetailTab[] {
  return PREMISES_TAB_IDS.map((id) => ({
    id,
    label: t(`metering.premises.tab.${id}`),
  }));
}

/**
 * r10's `UNITS 3 + common` — how many of this premise's units are COMMON AREAS.
 *
 * AMENDED 2026-08-22: this used to read `unit_type === "common_area"`, written
 * while OQ-314 (what a common area IS) was open. BR-MET-101 (PO 2026-08-21,
 * option A) has since ruled: a common area is a UNIT WITH A FLAG, and the flag
 * — `is_common_area`, now served on every unit row — is the queryable fact,
 * because it is what separates a common area from a vacant unit billed to the
 * owner (BR-MET-094). Migration 0016 backfilled rows already typed
 * `common_area`, so the two readings agree on old data; the FLAG wins on new.
 */
export function commonAreaCount(units: readonly UnitRow[]): number {
  return units.filter((unit) => unit.is_common_area).length;
}

/**
 * r10's `OCCUPIED 2 (1 vacant)`, over the rows on this premise.
 *
 * BR-MET-036: occupancy is DERIVED server-side from the active account, so this
 * counts what was served and derives nothing itself. A row whose occupancy is
 * neither `occupied` nor `vacant` (a value this lane does not know) counts
 * towards NEITHER — inventing a bucket for it would move a number.
 */
export function occupancyCounts(units: readonly UnitRow[]): {
  occupied: number;
  vacant: number;
} {
  return {
    occupied: units.filter((unit) => unit.occupancy === "occupied").length,
    vacant: units.filter((unit) => unit.occupancy === "vacant").length,
  };
}

/**
 * **`Silver Creek, TX 78611`** — the town half of an address, on its own.
 *
 * ⚠ **THE STATE AND THE ZIP ARE SEPARATED BY A SPACE, NOT A COMMA, AND THAT IS
 * A CORRECTION (`CR-089` `P4`).** This composed `Katy, TX, 77494`, which is not
 * how a North American address is written anywhere a person would recognise —
 * and `CLAUDE.md`'s first sentence says exactly who this product is for. The
 * agreed drawing writes `Silver Creek, TX 78611`.
 *
 * It is its own function because the property header needs the town WITHOUT the
 * street (the street is the H1) while the Address fact needs both, and B14 rule
 * 2 is one statement per fact: two joins would let the header and the fact list
 * punctuate one address two different ways on one screen.
 */
export function premisesLocality(row: PremisesDetail): string | null {
  const town = [row.city, row.state]
    .filter((part) => part !== null && part !== "")
    .join(", ");
  const withZip = [town, row.postal_code]
    .filter((part) => part !== null && part !== "")
    .join(" ");
  return withZip === "" ? null : withZip;
}

/** The one-line address a header shows. Never the internal uuid. */
export function premisesHeadline(row: PremisesDetail): string {
  return [row.address_line, premisesLocality(row)]
    .filter((part) => part !== null && part !== "")
    .join(", ");
}

/**
 * The eyebrow: **`PREMISE`**, the one word, and nothing else.
 *
 * ⚠ **IT CARRIED `Premise · P-00001 · NORTH DISTRICT · NW` UNTIL 2026-09-09,
 * AND `CR-089`'s AGREED `P4` DRAWING MOVES ALL THREE OF THOSE PARTS
 * (`DEF-MET-4733`).** The number and the town go to the sub-line beneath the
 * H1; the area path goes to the fact list, which already draws **Area** and
 * **Sub-area** as their own rows. So the eyebrow says what KIND of thing this
 * page is about and stops repeating facts the page states properly one line
 * lower — B14 rule 2, one statement per fact.
 *
 * ⚠ **THE STALE COMMENT THIS REPLACES QUOTED r10's `Premise · P-10432 · North
 * district · Route 3` AND CALLED THE LAST SEGMENT A ROUTE. IT IS NOT ONE.**
 * *"Route 3"* there is an **area path segment** — `area_path` is
 * `BR-MET-071`'s `parent · child` join and has never held a route. A reader
 * taking that comment as evidence the route was already on this header would
 * be wrong, and until today the route was on no property screen at all: see
 * `premisesRouteLine`, which is the half `B6` left unbuilt.
 *
 * `row` is kept in the signature so the eyebrow can grow a fact without every
 * call site changing; it is deliberately unread.
 */
export function premisesKicker(row: PremisesDetail, t: Translator): string {
  void row;
  return t("metering.premises.kickerWord");
}

/**
 * r10's H1: `1408 Elm Street` — the STREET line alone. The rest of the address
 * is the Overview's `Address` fact, which is where r10 puts it
 * (`1408 Elm Street, Austin, TX 78704`).
 *
 * A premise with no street line falls back to its number and then to the joined
 * headline: a detail screen must never render a blank H1, and it must never
 * render the internal uuid.
 */
export function premisesTitle(row: PremisesDetail, t: Translator): string {
  return (
    row.address_line ?? row.premise_no ?? premisesHeadline(row) ?? t("metering.premises.noNumber")
  );
}

/**
 * The sub-line: **`P-00080 · Silver Creek, TX 78611 · Apartment complex`** —
 * `CR-089`'s agreed `P4` drawing, in its order. The status pill follows it,
 * drawn by `PageHeader` from `status` and never restated here.
 *
 * ⚠ **IT READ `Apartment complex · owner Creekside Holdings LP` UNTIL
 * 2026-09-09.** Two things moved and one arrived:
 *   · the **number** and the **town** arrive, off the eyebrow, which is now the
 *     one word `PREMISE`;
 *   · the **owner** LEAVES. It is a fact row with an account, a category and a
 *     link (`OwnerAccountBlock`, `DEF-650`), and a bare name repeated in the
 *     header is the second place for one fact to be wrong — B14 rule 2. The
 *     sub-line also drew `owner_manager`, the LEGACY FREE TEXT, so a property
 *     with a typed owner and no legacy string showed no owner in the header at
 *     all while the fact row named one.
 *
 * ⛔ **TWO OF r10's OWN FOUR PARTS ARE STILL NOT DRAWN AND ARE NOT INVENTED.**
 *   · *inside city limits* — SERVED since 2026-08-26 (`DEF-507`) and drawn as
 *     the Overview's **City limits** fact, not repeated here.
 *   · *created Mar 2024 from migration* — the payload carries no created-at and
 *     no provenance at all.
 *
 * Every part is OMITTED when the server did not send it, so a property with no
 * town and no type reads `P-00080` rather than carrying an em-dash into a
 * header; a property with none of the three gets no sub-line at all.
 */
export function premisesSubline(row: PremisesDetail, t: Translator): string | null {
  void t;
  const parts = [row.premise_no, premisesLocality(row), row.premises_type_name].filter(
    (part): part is string => part !== null && part !== "",
  );
  return parts.length === 0 ? null : parts.join(" · ");
}

/**
 * **THE ROUTE AND CYCLE LINE, WHICH IS THE HALF `B6` LEFT UNBUILT.**
 *
 * PO 2026-09-08, verbatim: *"In header we are not shouding Route and Cycle
 * information - **if it is assign or if it nor assign both the thing** and you
 * should add that at the time of creation also - it should be optional"*. Wave
 * `B6` built the CREATION half — the create form draws `Route RT-002 · Cycle
 * CY-002` — and the DISPLAY half was never built: `premises_detail` has served
 * `routes` since that wave and **nothing in this product read it**.
 *
 * ⚠ **THE EYEBROW WAS NOT ALREADY SHOWING THIS.** It showed `area_path`, whose
 * second segment is a SUB-AREA that can be called anything, *"Route 3"*
 * included — see `premisesKicker`. An area is not a route and a reader must not
 * take one for the other.
 *
 * **Both states are drawn, because the ruling names both:**
 *   · on a route with a cycle → `Route RT-002 · Cycle CY-002 — bills on the 12th`
 *   · on a route whose cycle is a draft or unset → `Route RT-002 · no cycle yet`
 *   · on no route at all → **`No route yet`**, which is the sentence the ruling
 *     calls *"if it nor assign"* and is why this returns a string rather than
 *     `null`;
 *   · **`undefined` routes → `null`**, and that is a different fact again: the
 *     payload was never asked for the routes (`PremisesLends` reuses this type
 *     over a list row). Drawing *No route yet* there would state an absence
 *     nobody measured.
 *
 * ⚠ **`— bills on the 12th` IS READ FROM `cycles.bill_day` AND IS OMITTED WHEN
 * THE COLUMN IS NULL.** It is the cycle's DEFAULT day-of-month (`D9`,
 * `OQ-344`), which a bill run may override without rewriting it — so the copy
 * says what the cycle normally does and never what one bill will do. Where no
 * day is set the clause is simply absent: a guessed day on a header is a date a
 * clerk would repeat to a customer.
 *
 * ⚠ **A BUILDING CAN SIT ON MORE THAN ONE ROUTE AND ALL OF THEM ARE NAMED.**
 * `premises_routes` answers per PROPERTY over `BR-MET-083`'s per-unit
 * membership; showing *Route 12* for a building half of which is on Route 14
 * would be worse than showing neither.
 */
export function premisesRouteLine(
  row: PremisesDetail,
  t: Translator,
  language: string,
): string | null {
  if (row.routes === undefined) {
    return null;
  }
  if (row.routes.length === 0) {
    return t("metering.premises.route.none");
  }
  return row.routes
    .map((route) => {
      if (route.cycle_code === null) {
        return t("metering.premises.route.noCycle", { route: route.code });
      }
      const pair = t("metering.premises.route.andCycle", {
        route: route.code,
        cycle: route.cycle_code,
      });
      // The em dash is composed HERE and is not baked into the catalogue value,
      // because the same sentence is drawn standalone on the Billing cycle fact
      // row, where a leading dash would read as a missing word.
      return route.cycle_bill_day === null
        ? pair
        : `${pair} — ${t("metering.premises.route.billsOn", {
            day: ordinalDay(route.cycle_bill_day, language, (key) => t(key)),
          })}`;
    })
    .join(" · ");
}

// ── CR-089 `F3` · THE PROPERTY'S FOUR TILES (`DEF-MET-4733`) ───────────────
//
// PO ruling 2026-09-08, verbatim: *"Kpis you ahve shown on Unit view - these
// KPis will be displayed across all views"*, which `CR-089` `F3` reads as
// **Units · Assets · Owed here · Open work orders** on all six property tabs.
//
// ⚠ **THE STRIP WAS ALREADY IN THE RIGHT PLACE AND THE TILES WERE THE WRONG
// FOUR.** It has rendered OUTSIDE the tab bodies since `US-SHL-020`, so it
// follows a person across every tab and a tab change fetches nothing. What it
// drew was `Units · Occupied · Meters · Master account` — wave F fixed the
// unit's four and could not touch this file, and filed the property's as
// `DEF-MET-4733`. This closes it.
//
// ⚠ **AND THE COST IS MEASURED RATHER THAN ESTIMATED, EXACTLY AS WAVE F's
// WAS.** Nothing here adds an HTTP request:
//   · `Units` was already on `GET /premises/{id}`;
//   · `Assets` reads the rows of `GET /assets?f.premises_id=` — the request
//     the Assets TAB already makes, under the same query key, so React Query
//     serves both from one response. The count was already fetched; the split
//     is counted from rows the browser is holding;
//   · `Owed here` and `Open work orders` ride `GET /premises/{id}`, which the
//     page already requests, and `premises_detail_dict` is untouched so the
//     84-row property LIST pays nothing.
// Two requests on load, as before; **zero on every one of the five tab
// changes**.
//
// ⚠ **EVERY ONE OF THE FOUR HAS AN ABSENCE THAT IS NOT A ZERO** (`DEF-075`,
// `DEF-127`, `DEF-138`). A tile that cannot answer says so; it never prints a
// `0`, a `0.00` or a dash that reads as *nothing here*.

/** Tile 1 — `UNITS 4 · 3 occupied · 1 vacant`. */
export function premisesUnitsTile(premises: PremisesDetail, t: Translator): KpiTile {
  const counts = occupancyCounts(premises.unit_rows);
  return {
    id: "units",
    label: t("metering.premises.kpi.units"),
    // BR-MET-101 — the total is the SERVER's, never re-derived from whatever
    // rows are on screen, and the "+ common" marker rides it where a building
    // has common areas so the two numbers of the split cannot disagree.
    value:
      premises.units_common > 0
        ? t("metering.premises.kpi.unitsSplit", {
            units: premises.units - premises.units_common,
          })
        : premises.units,
    // BR-MET-036: occupancy is DERIVED from the active account, so this counts
    // what was served. A row that is neither occupied nor vacant counts to
    // NEITHER — `occupancyCounts` says why, and inventing a bucket moves a
    // number.
    detail: t("metering.premises.kpi.occupancySplit", {
      occupied: counts.occupied,
      vacant: counts.vacant,
    }),
  };
}

/**
 * Tile 2 — `ASSETS 9 · 4 metered · 5 behind the meter`.
 *
 * ⚠ **THE LABEL WAS `Meters` OVER A COUNT OF EVERY ASSET, WHICH IS THE HALF OF
 * `DEF-MET-4733` A READER COULD SEE.** `GET /assets?f.premises_id=` returns
 * carts, fire lines and PV panels as well as meters, so the number was already
 * right and the word was wrong — the identical mistake wave F fixed on the unit
 * (`DEF-MET-4729`), and this is the PO's own ruling of 2026-09-08: *"Meter =
 * assets"*.
 *
 * ⚠ **THE SPLIT IS `BR-AST-004`'s CATEGORY AND NOT A TYPE-CODE GUESS.** It uses
 * `isMeteredAsset`, the SAME predicate the Assets tab groups by, over the SAME
 * rows — so the tile and the tab beneath it cannot come to disagree. Inferring
 * it from a type code would break the first time a tenant adds a type of their
 * own, which `BR-TEN-036` says they may.
 *
 * ⚠ **`rows` UNDEFINED IS *NOT COUNTED YET*, WHICH IS NOT ZERO.** While the
 * assets request is in flight the tile draws a dash: *"no assets"* and *"not
 * counted"* are different claims and one of them is wrong on every property.
 *
 * ⚠ **THE DRAWING's DETAIL READS `4 metered, all read this cycle` AND THE
 * SECOND CLAUSE IS DELIBERATELY NOT DRAWN.** `last_read` rides sub-meters only
 * on this payload (`DEF-592`), and *read THIS CYCLE* needs the cycle's window
 * as well as a date. Neither is here, so the tile states the split it can
 * measure and claims nothing about reads — a tile asserting every meter was
 * read is exactly the sentence a clerk would act on.
 */
export function premisesAssetsTile(
  rows: readonly AssetRow[] | undefined,
  t: Translator,
): KpiTile {
  if (rows === undefined) {
    return { id: "assets", label: t("metering.premises.kpi.assets"), value: <Dash /> };
  }
  const metered = rows.filter(isMeteredAsset).length;
  return {
    id: "assets",
    label: t("metering.premises.kpi.assets"),
    value: rows.length,
    detail: t("metering.premises.kpi.assetsSplit", {
      metered,
      behind: rows.length - metered,
    }),
  };
}

/**
 * Tile 3 — `OWED HERE $0.00 · across 3 accounts`.
 *
 * ⚠ **THIS TILE REFUSES TO MANUFACTURE A ZERO, AND THAT IS WAVE C's RULING
 * CARRIED UP A LEVEL (`DEF-138`).** `owed_for_units` resolves the OCCUPYING
 * account, so a vacant unit is never measured and a leaver who still owes has a
 * CLOSED account it excludes. A `$0.00` summed over those would say *nothing is
 * owed here* over a real debt — and on a TOTAL that is worse than on a row,
 * because a total reads as complete.
 *
 * So the four states are drawn apart:
 *   · **nothing measured** (`counted: 0`) → *No account here has been billed*,
 *     never a figure;
 *   · **two currencies** → no amount at all; they cannot be added;
 *   · **a figure**, with its currency and its `BR-REP-001` basis, and a detail
 *     line naming HOW MANY accounts it covers — which is what makes a total
 *     readable rather than authoritative;
 *   · and where some units were **not counted**, the detail SAYS SO beside the
 *     figure rather than letting the sum imply it covered the building.
 */
export function premisesOwedHereTile(premises: PremisesDetail, t: Translator): KpiTile {
  const label = t("metering.premises.kpi.owedHere");
  const owed = premises.owed_here;
  // Not asked for at all — a list row reusing this type, or an older payload.
  if (owed === undefined) {
    return { id: "owed-here", label, value: <Dash /> };
  }
  if (owed.mixed_currency) {
    return {
      id: "owed-here",
      label,
      value: (
        <span className="met-qualifier" data-owed-state="mixed-currency">
          {t("metering.premises.kpi.owedMixed")}
        </span>
      ),
      detail: t("metering.premises.kpi.owedAcross", { count: owed.accounts }),
    };
  }
  if (owed.amount === null || owed.currency === null) {
    return {
      id: "owed-here",
      label,
      value: (
        <span className="met-qualifier" data-owed-state="nothing-measured">
          {t("metering.premises.kpi.owedNotMeasured")}
        </span>
      ),
      detail: t("metering.premises.kpi.owedNotCounted", { count: owed.not_counted }),
    };
  }
  return {
    id: "owed-here",
    label,
    money: {
      amount: owed.amount,
      currency: owed.currency,
      // BR-REP-001. `posting` is the basis every balance in this product is
      // summed on, and it is the one `unitOwedTile` forwards from the server
      // for the very same figure — the two tiles must not label one derivation
      // two ways.
      basis: "posting" as MoneyBasis,
    },
    detail:
      owed.not_counted > 0
        ? `${t("metering.premises.kpi.owedAcross", { count: owed.accounts })} · ${t(
            "metering.premises.kpi.owedNotCounted",
            { count: owed.not_counted },
          )}`
        : t("metering.premises.kpi.owedAcross", { count: owed.accounts }),
  };
}

/**
 * Tile 4 — `OPEN WORK ORDER 1 · Meter change · 10 Sep 2026`.
 *
 * The label is SINGULAR at one and plural otherwise, through i18next's own
 * `_one`/`_other` categories rather than an `if` — English is not the only
 * language this ships in and several have more than two forms.
 *
 * ⚠ **`count: null` IS *WORK COULD NOT BE ASKED* AND IS NEVER `0`**
 * (`DEF-075`): a zero says *nobody is coming and nobody needs to*.
 *
 * ⚠ **THE DETAIL NAMES A PROMISED APPOINTMENT, NEVER AN SLA DEADLINE.** The
 * server sends the soonest open order that HAS a `window_start`; where nothing
 * open is booked, `next` is null and the tile says *Nothing booked yet* rather
 * than reaching for `due_at`, which is an internal deadline nobody promised a
 * customer (`BR-WRK-018`).
 *
 * ⚠ **THE DRAWING WRITES `meter change, Thursday` AND THIS DRAWS THE DATE
 * THROUGH `DateCell`.** `BR-SHL-034` puts every displayed date through the ONE
 * formatter in the tenant's own setting, and wave H has just finished
 * collapsing four date shapes on these screens into one (`DEF-MET-4689`); a
 * weekday-only fifth shape invented here would re-open that defect the day it
 * closed. Reported rather than taken quietly.
 */
export function premisesOpenWorkTile(
  premises: PremisesDetail,
  t: Translator,
  timeZone: string,
  dateFormat: RegionalDateFormat,
): KpiTile {
  const work = premises.open_work;
  const count = work?.count ?? null;
  const label = t("metering.premises.kpi.openWork", { count: count ?? 0 });
  if (work === undefined || count === null) {
    return {
      id: "open-work",
      label,
      value: <Dash />,
      detail: work === undefined ? undefined : t("metering.premises.kpi.openWorkUnknown"),
    };
  }
  const next = work.next;
  return {
    id: "open-work",
    label,
    value: count,
    detail:
      next === null ? (
        t("metering.premises.kpi.openWorkNoneBooked")
      ) : (
        <>
          {next.type ?? next.order_no}
          {" · "}
          <DateCell value={next.window_start} timeZone={timeZone} dateFormat={dateFormat} />
        </>
      ),
  };
}

/**
 * r10's Overview draws `Area` and `Sub-area` as TWO facts. The server sends ONE
 * tag plus the box it belongs in (BR-MET-071): `area_code`, `area_name`,
 * `area_parent_code` (*which* box — Area or Sub-area) and `area_path`, the
 * "North district · Route 3" join a human reads.
 *
 * So the split is read off what the server sent and derived from nothing:
 *   · no tag at all            → both null;
 *   · `area_parent_code` null  → the tag IS an area; there is no sub-area;
 *   · `area_parent_code` set   → the tag is the SUB-area, and its parent's NAME
 *     is the leading segment of `area_path`.
 *
 * ⚠ **THE LAST LINE READS A DISPLAY STRING, WHICH IS FRAGILE — `DEF-583`.** The
 * payload carries the parent's CODE and not its name, so the only place the
 * parent's human name exists is inside `area_path`. Splitting it is the correct
 * answer today and the wrong shape: the fix is `area_parent_name` beside the
 * three keys that are already there. Filed, and the fallback here is the CODE
 * rather than a blank, so a re-worded join degrades to something traceable.
 */
export function premisesAreaSplit(row: PremisesDetail): {
  area: string | null;
  subArea: string | null;
} {
  if (row.area_code === null || row.area_name === null) {
    return { area: null, subArea: null };
  }
  if (row.area_parent_code === null) {
    return { area: row.area_name, subArea: null };
  }
  const segments = (row.area_path ?? "").split(" · ");
  return {
    area: segments.length > 1 ? segments[0] : row.area_parent_code,
    subArea: row.area_name,
  };
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface PremisesDetailPageProps extends RegionalProps {
  client?: ApiClient;
}

export function PremisesDetailPage(props: PremisesDetailPageProps) {
  const { t, i18n } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  // DEF-650 — the premises read is what carries the owner's account, so linking
  // one has to invalidate THIS key or the Owner fact keeps rendering the
  // absence it was showing before the click.
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const premisesId = params.premisesId ?? "";
  // CR-162-BRC10 — is there a New Connection at this address? While the
  // premises is Pending the header links to it (`PendingBuildLink`); the Build
  // tab it used to decide is gone (PO 2026-10-02).
  const buildQuery = useBuild("premises", premisesId, client);
  const tabs = premisesTabs(translate);
  const active = detailTabFrom(searchParams.get(TAB_PARAM), tabs);
  const openOrderId = searchParams.get(ORDER_PARAM);
  const [editing, setEditing] = useState(false);
  // CR-089 wave D — the status dialog is opened from the header and owns its
  // own reads, so the page holds one boolean and nothing else.
  const [statusOpen, setStatusOpen] = useState(false);

  // BR-SHL-025: "Full" writes; anything else renders the control DISABLED with
  // its reason. The server refuses regardless — this only saves a round trip.
  const cell = useAccessCell(PREMISES_PERMISSION, client);
  // CR-089 wave D — the STATUS control is the System Admin's alone
  // (`@require_role(SYSTEM_ADMIN)` on the endpoint), and A4's cell grades a
  // SURFACE rather than one act inside it: a Billing Clerk holds Full on
  // Premises/Accounts and may create and edit, and may NOT change a status.
  // Gating this on the cell would offer them a button that can only 403 —
  // US-MET-013's dispute control has the same shape and the same reason.
  const role = useTenantRole(client);
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("metering.rbac.readOnly");
  const typesQuery = useQuery({
    queryKey: premisesTypesQueryKey,
    queryFn: () => getPremisesTypes(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const detailQuery = useQuery({
    queryKey: premisesDetailQueryKey(premisesId),
    queryFn: () => getPremisesDetail(premisesId, client),
    enabled: premisesId !== "",
  });

  // r10's `METERS 5` tile. The registry answers `GET /assets?f.premises_id=`
  // (BR-AST-041's premises filter), which is the same query the Assets tab
  // makes — same key, so React Query serves both from one request rather than
  // this tile adding a second. Summing `unit_rows[].meters` instead would
  // undercount: an asset on the PREMISE rather than on a unit would vanish.
  const assetsQuery = useQuery({
    queryKey: premisesAssetsQueryKey(premisesId),
    queryFn: () => getAssets({ filters: { premises_id: premisesId }, per: 200 }, client),
    enabled: premisesId !== "",
  });
  // ⚠ **THE TILE READS `results`, NOT `count`, FROM 2026-09-09
  // (`DEF-MET-4733`).** It needed only a total while it was labelled *Meters*;
  // `CR-089` `F3` splits it into what BILLS and what does not, and that split is
  // `BR-AST-004`'s category on each ROW. Same request, same query key, same
  // response — the rows were always in it. `premisesAssetsTile` draws a dash
  // while they are undefined: "no assets" and "not counted yet" are different
  // claims and one of them is wrong on every property.

  // DEF-SHL-3964 — HOISTED. This was written five times below, inside
  // `{active === "build" && (…)}` and `{active === "work-orders" && (…)}`.
  // `useRegional` reads a context, so a call inside a conditional branch is a
  // hook whose presence depends on which tab is open — the classic hook-order
  // crash. Read once, unconditionally, before the early returns below.
  const regional = useRegional(props);

  function selectTab(id: string): void {
    const next = new URLSearchParams(searchParams);
    next.set(TAB_PARAM, id);
    // Leaving the Work orders tab closes any drawer that was open over it: a
    // `?order=` left in the URL would re-open a panel over the WRONG tab the
    // next time somebody came back to this link.
    next.delete(ORDER_PARAM);
    setSearchParams(next, { replace: true });
  }

  /** Open or close the work-order drawer. URL state, so a supervisor can send
   *  somebody a link to one job (`BR-SHL-011` — every tab is linkable). */
  function selectOrder(id: string | null): void {
    const next = new URLSearchParams(searchParams);
    if (id === null) {
      next.delete(ORDER_PARAM);
    } else {
      next.set(ORDER_PARAM, id);
    }
    setSearchParams(next, { replace: true });
  }

  if (detailQuery.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }
  if (detailQuery.data === undefined) {
    if (isPermissionDenied(detailQuery.error)) {
      return (
        <PermissionDenied
          helper={t("metering.premises.denied")}
          onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
        />
      );
    }
    // A cross-tenant or unknown id is an indistinguishable 404 server-side —
    // A18 §4 with the server's own reason, never a blank detail shell.
    return (
      <FailedWithRetry
        title={t("metering.premises.detail.failedTitle")}
        reason={apiErrorText(detailQuery.error, translate)}
        onRetry={() => void detailQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(PREMISES_ROUTE))}
      />
    );
  }

  const premises = detailQuery.data;

  return (
    <div className="met-page">
      {/* US-SHL-020: the shared header, in its ruled order — back → kicker → H1
          + status → roll-up → tab strip. The back link's arrow belongs to the
          component (TC-5), so the LABEL here is the destination's own name; the
          catalog's "← Premises" would render a second arrow. */}
      <PageHeader
        backTo={{ to: tenantPath(PREMISES_ROUTE), label: t("metering.premises.title") }}
        // DEF-578 — r10's eyebrow is `Premise · P-10432 · North district ·
        // Route 3`, its H1 is the STREET LINE and its sub-line describes the
        // property. This screen had the number in the H1 and the type in the
        // eyebrow: the same three facts, each in the wrong slot.
        kicker={premisesKicker(premises, translate)}
        title={premisesTitle(premises, translate)}
        // ── CR-089 · THE ROUTE AND CYCLE, ON THE HEADER (PO 2026-09-08) ────
        // *"In header we are not shouding Route and Cycle information - if it
        // is assign or if it nor assign both the thing"*. Wave `B6` built the
        // CREATE half; `premises_detail` has served `routes` since, and NOTHING
        // READ IT. Two lines rather than one: the sub-line describes the
        // property, the route line says who reads it and when it bills, and a
        // person scanning for one is not made to read the other.
        // ── `DEF-MET-6913` · THE UTILITY SERVICES, ON THE HEADER (PO
        //    2026-09-27, live beta v2.352.0) ───────────────────────────────
        // *"On the premises detail page the header should show the utility
        // service chips; this premises has 4 utility services but they are not
        // visible in the header."* The data was there and served all along —
        // `services_available` draws the `Utility services` fact row far down
        // the Overview tab — so the header simply never asked for it.
        //
        // ⚠ **THE BLUEPRINT DRAWS NO CHIP ROW HERE AND THE STANDARD STILL
        // WINS.** `05-prototype/Premises & Units Blueprint 2.pdf` p19 draws
        // PRM-02's header as four lines with `Utility services` left in the
        // fact list below, and B14 rule 44 gives our UI standard the win over
        // the drawing on EVERY screen INCLUDING THE FRAME. The standard here is
        // the product's own: `AccountDetailPage` puts `AccountServiceChips` in
        // exactly this slot of exactly this component, and a property is the
        // other thing in this product that carries a set of services.
        //
        // ⚠ **THE FACT ROW STAYS.** `ServiceWords` below tells `null` (nobody
        // was asked) from `[]` (the clerk answered *none*) in words — `DEF-762`
        // / `CR-036` (h) — and a header cannot say that without printing
        // RATIONALE, which B14 rule 33 puts at zero words on screen. So the
        // chips are ADDITIVE: with no services the header renders nothing at
        // all, no separator and no empty row, and the fact row still answers.
        rollup={
          <>
            {premisesSubline(premises, translate)}
            {premisesRouteLine(premises, translate, i18n.language) !== null && (
              <span className="block" data-testid="premises-route-line">
                {premisesRouteLine(premises, translate, i18n.language)}
              </span>
            )}
            <ServiceChips services={premises.services_available} t={translate} />
            {/* CR-162-BRC10 — a Pending premises links to the New Connection
                that will activate it (the PO's *"show link for request"*). */}
            {premises.status === "pending" && buildQuery.data != null && (
              <PendingBuildLink
                build={buildQuery.data}
                t={translate}
                path={tenantPath}
              />
            )}
          </>
        }
        status={
          <StatusPill tone={premisesStatusTone(premises.status)}>
            {t(`metering.premises.status.${premises.status}`, { defaultValue: premises.status })}
          </StatusPill>
        }
        // B15 §2A: r10's action row is `● Active │ ↓ Export CSV │ ✏ Edit │
        // + Add unit`.
        //
        // ⚠ **`↓ Export CSV` IS DELIBERATELY ABSENT AND THIS IS THE REASON.**
        // The shared `ListExportButton` posts a LIST request state to
        // `POST /exports`; there is no per-premises export anywhere in the
        // product. Wiring it here would put a button labelled "Export CSV" on
        // ONE premise that quietly exported every premise the tenant owns —
        // worse than the missing button, because the file looks right until
        // somebody opens it. Reported, not faked.
        //
        // B14 rule 15 governs the other two: row actions are glyphs, and an
        // ordinary button says a WORD (PO 2026-08-20, *"this only for table
        // actions ; not for buttons"*), so these are words.
        secondaryActions={
          <>
            <GuardedButton
              label={t("metering.action.edit")}
              reason={writeBlockedReason}
              onClick={() => setEditing(true)}
            />
            {/* ── CR-089 wave D · D1 (`PUJ-21`) ──────────────────────────────
                PO 2026-09-08: *"Allow user to cahnge Unit and Premsies status"*.
                This page showed a status pill and offered no way to change it.

                ⚠ **ABSENT FOR ANYONE WHO MAY NOT PRESS IT, NOT GREYED** —
                CR-089's own words, and the one place this control departs from
                `GuardedButton`'s disabled-with-a-reason posture: a control a
                person may NEVER press is not a control, and the Edit button
                beside it already teaches that lesson once per page.
                A role of `null` (the permissions read has not landed, or
                failed) still RENDERS it — BR-SHL-025's honest default is never
                to guess a role, and the endpoint's own 403 is the boundary. */}
            {(role === ROLE_SYSTEM_ADMIN || role === null) && (
              <GuardedButton
                label={t("metering.status.action")}
                reason={null}
                onClick={() => setStatusOpen(true)}
              />
            )}
          </>
        }
        primaryAction={
          <GuardedButton
            label={t("metering.units.action.new")}
            reason={writeBlockedReason}
            variant="primary"
            // ⚠ **THE BUILDING TRAVELS WITH THE PRESS.** This called the bare
            // route until 2026-09-10, so `+ New unit` on `P-00080` opened the
            // wizard with an EMPTY building box and a clerk standing on the
            // address was asked to find it again. `unitsAddPath` has existed
            // since wave E and nothing but a test called it — hard-won law 2.
            onClick={() => navigate(tenantPath(unitsAddPath(premisesId)))}
          />
        }
        // BR-MET-045's tab set is `{id,label}` — which IS a PageHeaderTab, so it
        // is handed over as-is rather than re-shaped. No tab declares a header
        // action: this detail view offers none (BR-SHL-044 (c)).
        tabs={tabs}
        activeTabId={active}
        tabsLabel={t("metering.premises.detail.tabsLabel")}
        onTabSelect={(tab) => selectTab(tab.id)}
      />

      {/* ── CR-089 `F3` · THE FOUR TILES THE RULING NAMES (`DEF-MET-4733`) ──
          `Units · Assets · Owed here · Open work orders`, replacing
          `Units · Occupied · Meters · Master account`. Each builder above says
          what it will and will not claim; the strip itself only orders them.

          ⚠ **MASTER ACCOUNT LEAVES THE STRIP AND DOES NOT LEAVE THE SCREEN.**
          It is the Owner fact's own second line now — `Master account
          A-10442 · Open it →` — where wave B put the party, its category and
          the link. A tile that could only ever read *None yet* in italic, with
          nothing to press, beside an Owner row with a working **Find an
          owner** control saying the same thing, is what the walkthrough
          flagged as `PUJ-11`. */}
      <KPIStrip
        kpis={[
          premisesUnitsTile(premises, translate),
          premisesAssetsTile(assetsQuery.data?.results, translate),
          premisesOwedHereTile(premises, translate),
          premisesOpenWorkTile(premises, translate, regional.timeZone, regional.dateFormat),
        ]}
      />

      {active === "overview" && (
        <PremisesOverviewTab
          premises={premises}
          t={translate}
          client={client}
          // hard-won law 2: a prop nothing passes is dead UI, and the GIS
          // check's date is the one fact on this tab that needs it.
          regional={props}
          onLinked={() => {
            void queryClient.invalidateQueries({
              queryKey: premisesDetailQueryKey(premisesId),
            });
          }}
        />
      )}

      {active === "work-orders" && (
        <WorkOrdersTab
          host="premises"
          hostId={premisesId}
          t={translate}
          timeZone={regional.timeZone}
          dateFormat={regional.dateFormat}
          openOrderId={openOrderId}
          onOpenOrder={selectOrder}
          client={client}
        />
      )}

      {active === "common-areas" && (
        // AMENDED 2026-08-22 — this tab was a whole-tab stated absence citing
        // OQ-314. **OQ-314's second half is now RULED and BUILT** (BR-CUS-068,
        // PO 2026-08-22): the master account is an ordinary `accounts` row with
        // `kind='master'`, `POST /accounts/master` creates it over the
        // premises' common areas, and `GET /accounts?f.kind=master&f.unit_id=`
        // reads it back. So the tab draws what it can now source — the master
        // account, its payer, the common-area rows from `is_common_area`
        // (BR-MET-101) with their meters, plan and status — and keeps a STATED
        // ABSENCE, individually cited, for each r10 figure that still has no
        // source: the one-owner bill (bill assembly prices the anchor unit
        // only), the unallocated percentage (OQ-327, uncomputed anywhere), and
        // per-area coverage (DEF-560, the selector is not published).
        <CommonAreasTab
          premises={premises}
          client={client}
          t={translate}
          writeBlockedReason={writeBlockedReason}
          // `DEF-CUS-9036` — `?request=<id>`: an approved application this
          // owner's master account fulfils. Arrives from the request page.
          serviceRequestId={searchParams.get("request") ?? ""}
          {...regional}
        />
      )}

      {active === "units" && (
        <UnitsTab units={premises.unit_rows} t={translate} premisesId={premises.id} />
      )}
      {active === "assets" && (
        <PremisesAssetsTab
          premisesId={premises.id}
          client={client}
          t={translate}
          regional={props}
        />
      )}
      {active === "audit" && (
        <AuditTab
          entityType="premises"
          entityId={premises.id}
          t={translate}
          regional={props}
        />
      )}

      {editing && (
        <PremisesEditModal
          row={premises}
          types={typesQuery.data ?? []}
          client={client}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            void detailQuery.refetch();
          }}
        />
      )}

      {/* CR-089 wave D · D1 — the counts, the hold and the two required fields
          all live in the dialog; this page only says which record it is on. */}
      {statusOpen && (
        <StatusChangeDialog
          subject="premises"
          id={premises.id}
          name={premisesTitle(premises, translate)}
          client={client}
          onClose={() => setStatusOpen(false)}
          onChanged={() => {
            setStatusOpen(false);
            void detailQuery.refetch();
          }}
          {...regional}
        />
      )}
    </div>
  );
}

// ── Tabs ───────────────────────────────────────────────────────────────────

/**
 * PRM-02's **Overview** — r10's TWO-COLUMN fact grid, in r10's own order:
 *
 *   left   Address · Premise type · Jurisdiction · Services available
 *   right  Area · Sub-area · Owner / manager · Common areas
 *
 * ⚠ **THIS WAS ONE COLUMN OF EIGHT UNRELATED FACTS AND IT RENDERED BROKEN
 * (`DEF-578`, and the layout half is `DEF-584`).** The old markup was a single
 * `.met-facts` `<dl>` — a two-column CSS grid of `<dt>`/`<dd>` pairs — with the
 * jurisdiction stated-absence dropped into it as a full-width `<div>`. A grid
 * item that is neither a `dt` nor a `dd` still takes a CELL, so the label
 * column's `minmax(140px, auto)` grew to the width of that box and every value
 * on the screen was squeezed into a ~90px ribbon down the right-hand edge. The
 * PO's screenshot is of exactly that.
 *
 * So the grid is drawn here in Tailwind (B14 rule 21 · PO 2026-08-22, *"all
 * should be done using tailwind"*): two columns that collapse to one under the
 * ruled breakpoint, each fact a label/value row with its own rule beneath, and
 * a stated absence that is a VALUE in its own row rather than an intruder in
 * the grid.
 *
 * ⛔ **WHAT r10 DRAWS AND THIS DOES NOT, EACH WITH ITS REASON — nothing here is
 * filled with a plausible number.**
 *   · r10's `Jurisdiction` line reads `Inside city limits — no ×1.5
 *     multiplier`. **The first half is drawn (DEF-507 is fixed — the selector
 *     serves the three-state and `jurisdictionText` renders it); the SECOND
 *     half is not.** Whether this premise's plan carries a multiplier, and what
 *     it is, is a rating question this payload has no field for; "no ×1.5
 *     multiplier" beside a jurisdiction is a claim about the RATE, and stating
 *     it from the flag alone would be inventing one.
 *   · `Area` / `Sub-area` as two independent pickers. r10 draws editable
 *     `<select>`s; this is a READ surface and BR-MET-071's tag is changed on
 *     the Edit form, which is the one editor. Rendered as facts.
 *   · r10's `Common areas · Hallway & exterior lighting → master account
 *     MA-1408`. The AREAS are served (BR-MET-101's flag, on `unit_rows`) and
 *     are named here; the → master account half is the Common areas tab's, and
 *     is not repeated as a second, drifting copy.
 *
 * And two facts the old panel drew that r10 does not, both REMOVED rather than
 * kept: `Units` (the KPI tile above says the same number, and B14 rule 2 is
 * about one statement per fact) and `External ref`, which is a column on the
 * premises LIST and a field on the Edit form — dropping it here hides nothing.
 */
/**
 * DEF-507 — BR-RAT-101/102's jurisdiction flag, in a clerk's words.
 *
 * ⚠ **THREE STATES, AND `null` GETS THE DASH — NEVER "Outside city limits".**
 * `null` means nobody has recorded which side of the line this property is on;
 * "Outside" is an ANSWER, and it is the answer that adds the outside-city
 * surcharge to every bill at this address. Writing it here on a guess would put
 * a charge on a customer's bill that no one at the utility ever stated. The
 * rating engine takes the same posture (`resolution.py` applies no multiplier
 * for `None` rather than assuming one), so screen and engine agree.
 *
 * Returns `null` for the unrecorded case so the caller renders the SAME `<Dash />`
 * every other unanswered fact in this grid renders — one vocabulary for "we do
 * not know", not a second sentence invented for this row.
 */
export function jurisdictionText(inside: boolean | null, t: Translator): string | null {
  if (inside === null) {
    return null;
  }
  return inside
    ? t("metering.premises.jurisdiction.inside", { defaultValue: "Inside city limits" })
    : t("metering.premises.jurisdiction.outside", { defaultValue: "Outside city limits" });
}

/**
 * CR-089 wave A `PUJ-10` — the point, as a clerk reads it.
 *
 * ⚠ **THE STRINGS ARE PRINTED, NOT PARSED.** `lat`/`lng` arrive as the stored
 * `NUMERIC(9,6)` strings and go to the screen unchanged: a coordinate put
 * through `Number()` on the way to a `<span>` is a coordinate that can come
 * back with a different last digit, and this figure is quoted down a phone and
 * typed into other systems.
 *
 * `null` on either half is *no point*, not half a point — half a point cannot
 * be drawn and is the same *not placed* to everything that reads it, which is
 * the predicate **Needs a location** uses.
 */
export function pointText(
  lat: string | null,
  lng: string | null,
  t: Translator,
): string | null {
  if (!lat || !lng) {
    return null;
  }
  void t;
  return `${lat}, ${lng}`;
}

/**
 * CR-089 wave A `PUJ-10` — **Checked against GIS**, and which of three states.
 *
 * ⚠ **IT READS THE PAIR, AND READING THE FLAG ALONE WOULD BE WRONG ON EVERY
 * PROPERTY IN THE PRODUCT.** `gis_unchecked` is `NOT NULL DEFAULT false`, so
 * *false* is what all 673 properties hold and what every create that never
 * mentions it gets — it means *nobody has looked*, not *somebody checked*.
 * Drawing **Checked** from that would tell a clerk the whole estate had been
 * verified by a person who does not exist. So a property is **Checked** only
 * where `gis_checked_at` records that somebody pressed the control, and
 * everything else is **Not checked yet** whichever way the boolean sits.
 */
export function gisCheckState(
  premises: Pick<PremisesDetail, "gis_unchecked" | "gis_checked_at">,
): "checked" | "not_yet" {
  return premises.gis_checked_at ? "checked" : "not_yet";
}

export function PremisesOverviewTab(props: {
  premises: PremisesDetail;
  t: Translator;
  client?: ApiClient;
  /** BR-SHL-034 — every displayed date through the ONE formatter, in the
   *  tenant's own setting. Optional, and `{}` is the honest default: with no
   *  prop `useRegional` falls to what the shell published for this tenant,
   *  which is what every other date on this screen already reads. */
  regional?: RegionalProps;
  /** DEF-650 — re-read the premises after a clerk links the owner's account, so
   *  the Owner fact shows the account it just gained rather than the absence it
   *  was rendering a moment ago. OPTIONAL, and the one caller passes it: the
   *  block draws its link control only when this is present, so a read-only
   *  context gets a stated absence and not a dead button (hard-won law 2). */
  onLinked?: () => void;
}) {
  const { t, premises } = props;
  // ⚠ The COPY still comes from `props.t`; only the LANGUAGE TAG is read here,
  // and only so `ordinalDay` can ask `Intl.PluralRules` for this language's own
  // ordinal category. Taking the translator from the hook as well would give
  // this tab a second source of words from its own caller's.
  const { i18n } = useTranslation();
  const { timeZone, dateFormat } = useRegional(props.regional ?? {});
  const area = premisesAreaSplit(premises);
  // GIS Lane D (`DEF-MET-10003`, `DEF-INT-10004`) — the City's facts below are
  // drawn only where a City GIS is in use; a broken one says so in one line.
  const city = useCityGis(props.client ?? api);
  const commons = premises.unit_rows.filter((unit) => unit.is_common_area);
  const routes = premises.routes ?? [];
  return (
    <>
    {/* ── CR-089 `P4` · ONE COLUMN, IN THE AGREED ORDER ───────────────────
        ⚠ **THIS WAS A TWO-COLUMN GRID AND THE AGREED DRAWING IS ONE COLUMN.**
        A two-column fact list makes a reader choose a scan direction, and it
        put *Area* level with *Address* — so the second column's five facts read
        as a separate, lesser list. One column gives the drawing's order, top to
        bottom, and every row the same weight.
        `PremisesFact` already draws label-left/value-right with a rule under
        it, so the change is the removal of the grid rather than new furniture
        (B14 rule 36 — comply through the kit, do not hand-roll beside it). */}
    <section className="pt-2 max-w-[960px]">
        <PremisesFact label={t("metering.premises.col.address")}>
          {premisesHeadline(premises) || <Dash />}
        </PremisesFact>
        {/* ── CR-089 wave A `PUJ-20` · `BR-MET-1163` (PO 2026-09-08) ──────
            *"We will need parcel ID and we will ahve to display them"*, and
            *"you can make reference # = Parcel ID"* — the SAME column, under
            the name of the thing it holds. Its old label, *External / GIS
            ref*, told a clerk nothing about what belonged in it.
            ⚠ **THE LABEL IS `Parcel` FROM 2026-09-09 AND `BR-MET-1163` WRITES
            `Parcel ID`.** The agreed `P4` drawing is the later artefact and is
            followed. The RULE is deliberately NOT amended by this lane —
            renaming a field the PO named is the PO's call, and it is raised for
            them to settle.
            ⚠ **THE VALUE OF THE ONE KEY MOVED, RATHER THAN A SECOND KEY BEING
            MINTED FOR THIS SCREEN.** `metering.premises.field.externalRef` is
            also the create form's and the edit modal's label; a *Parcel* here
            over a *Parcel ID* there would be two words for one field, which is
            `DEF-348`'s shape and what B14 rule 34 exists to prevent. */}
        {/* ⚠ **`Import reference`, AND IT READ `Parcel` UNTIL 2026-10-07
            (`DEF-MET-10008`).** This column is `external_ref` — `BR-MET-403`'s
            import match key, what the utility's OLD software called the
            property. `BR-MET-1173` (PO 2026-09-17) moved the City's parcel to
            its own column, `gis_parcel_id`, and the label stayed behind here,
            so one word named two fields. *Parcel* now names only the City's
            parcel, drawn below where a City is in use. Not a City field, so it
            is never hidden. */}
        <PremisesFact label={t("metering.premises.field.importRef")}>
          {premises.external_ref || <Dash />}
        </PremisesFact>
        {city.showCity && (
          <PremisesFact label={t("metering.premises.field.externalRef")}>
            {premises.gis_parcel_id || <Dash>{t("metering.premises.map.noParcel")}</Dash>}
          </PremisesFact>
        )}
        {/* ── CR-089 wave A `PUJ-10` — WHERE THIS PROPERTY IS ──────────────
            ⚠ **657 of 673 properties have carried a point since CR-028 and no
            screen has ever shown one** — on the one screen whose subject is a
            place.
            ⚠ **NO MAP AND NO DRAGGABLE PIN.** PO 2026-09-08, verbatim: *"we
            dont need this right now - Drag the pin to correct it"*. The
            coordinates are shown as figures and corrected on the edit form.
            ⚠ **THE DRAWING PUTS *placed by the address lookup, 8 Sep 2026*
            BESIDE THE FIGURES AND IT IS NOT DRAWN.** `premises.lat/lng` carry
            no provenance and no timestamp of any kind — there is no
            `point_set_by`, no `point_set_at` and no source column — so who
            placed a pin and when is not a fact this product holds. The GIS
            check below has both and says both. Stated rather than invented,
            exactly as the sub-line already refuses r10's *"created Mar 2024
            from migration"*. */}
        {/* GIS Lane D (`DEF-MET-10003`, PO GIS review gap 9) — the point and
            the GIS check are City facts; a utility with no City GIS is not
            shown them. Nothing is deleted: the columns keep their values. */}
        {city.showCity && (
        <>
        <PremisesFact label={t("metering.premises.point.label")}>
          {pointText(premises.lat, premises.lng, t) ?? (
            <Dash>{t("metering.premises.point.none")}</Dash>
          )}
        </PremisesFact>
        <PremisesFact label={t("metering.premises.gis.label")}>
          {gisCheckState(premises) === "checked" ? (
            <>
              {t("metering.premises.gis.checked")}
              {premises.gis_checked_by ? (
                <>
                  {" · "}
                  {premises.gis_checked_by}
                  {", "}
                </>
              ) : (
                " · "
              )}
              {/* BR-SHL-034: every displayed date, one formatter — the
                  tenant's own setting, never a private one invented here. */}
              <DateCell
                value={premises.gis_checked_at ?? ""}
                timeZone={timeZone}
                dateFormat={dateFormat}
              />
            </>
          ) : (
            <Dash>{t("metering.premises.gis.notYet")}</Dash>
          )}
        </PremisesFact>
        <CityGisNote messageKey={city.brokenKey} />
        </>
        )}
        {/* DEF-507 — the ANSWER, where a paragraph about not having one stood.
            PO 2026-08-26: *"Why Juridiction is showing the in text it should
            shown inside city and outside city"*.
            ⚠ **THE LABEL IS `City limits` FROM 2026-09-09 (`CR-089` `P4`).**
            *Jurisdiction* is a word about law; the value under it reads
            *Inside* or *Outside*, and *inside WHAT* was answerable only by
            already knowing. The stored VALUE and the rule (`BR-RAT-101/102`'s
            outside-city surcharge) are untouched — this is a word, not a
            behaviour. The key keeps its name and changes its TEXT, so
            `JurisdictionField` on the create and edit forms is relabelled by
            the same edit and the three screens cannot disagree. */}
        <PremisesFact label={t("metering.premises.field.jurisdiction")}>
          {jurisdictionText(premises.inside_city_limits, t) ?? <Dash />}
        </PremisesFact>
        {/* PO 2026-08-17. This is where a tag PROVES it stuck: the detail is a
            fresh GET, so a value here survived the round trip rather than
            lingering in the form's own state. */}
        <PremisesFact label={t("metering.premises.col.area")}>
          {area.area ?? <Dash />}
        </PremisesFact>
        <PremisesFact label={t("metering.premises.field.subArea")}>
          {area.subArea ?? <Dash />}
        </PremisesFact>
        {/* ── CR-089 · READ ROUTE AND BILLING CYCLE, AS TWO FACTS ──────────
            The PO's ruling names both and they answer different questions —
            *who walks this address* and *when does it bill* — so they are two
            rows, not one. The header carries the same pair as a summary line;
            these are where a person reads the route's NAME and the days.

            ⚠ **BOTH STATES, WHICH IS THE RULING'S OWN WORDS:** *"if it is
            assign or if it nor assign both the thing"*. An unrouted property
            draws **No route yet** rather than no row, because a missing row
            reads as a screen that forgot to ask.

            ⚠ **`read on the 8th` IS `effective_start_day`, NEVER THE STORED
            `start_day`** (`OQ-340`): the engine anchors on the first run and
            ignores the column, so a stored day is a field that lies to the
            operator. Absent where the frequency has no day-of-month anchor at
            all (Daily · Weekly · Fortnightly), and the row then names the route
            without claiming a day. */}
        <PremisesFact label={t("metering.premises.field.readRoute")}>
          {premises.routes === undefined ? (
            <Dash />
          ) : routes.length === 0 ? (
            <Dash>{t("metering.premises.route.none")}</Dash>
          ) : (
            <span className="flex flex-col gap-1">
              {routes.map((route) => (
                <span key={route.id}>
                  {route.name === null ? route.code : `${route.code} — ${route.name}`}
                  {route.cycle_read_day === null ? null : (
                    <span className={`block font-normal ${MUTED}`}>
                      {t("metering.premises.route.readOn", {
                        day: ordinalDay(route.cycle_read_day, i18n.language, (key) => t(key)),
                      })}
                    </span>
                  )}
                </span>
              ))}
            </span>
          )}
        </PremisesFact>
        {/* ⚠ **`bills on the 12th` IS READ FROM `cycles.bill_day`, NOT
            COMPUTED — AND WAVE `B6`'s NOTE THAT THIS PAYLOAD SERVED NO DUE DAY
            WAS TRUE OF THE PAYLOAD AND NOT OF THE PRODUCT.** The column has
            existed all along: the PO kept it on 2026-08-23 (`D9`) and `OQ-344`
            made it what a run with no typed bill date resolves through. So this
            says what the cycle NORMALLY does; a run may override it and the
            override does not rewrite it. Where the utility set no day, the
            cycle is named and the clause is simply absent — a guessed billing
            day is a date a clerk would repeat to a customer. */}
        <PremisesFact label={t("metering.premises.field.billingCycle")}>
          {premises.routes === undefined ? (
            <Dash />
          ) : routes.filter((route) => route.cycle_code !== null).length === 0 ? (
            <Dash>{t("metering.premises.cycle.none")}</Dash>
          ) : (
            <span className="flex flex-col gap-1">
              {routes
                .filter((route) => route.cycle_code !== null)
                .map((route) => (
                  <span key={route.id}>
                    {route.cycle_name === null
                      ? route.cycle_code
                      : `${route.cycle_code} — ${route.cycle_name}`}
                    {route.cycle_bill_day === null ? (
                      <span className={`block font-normal ${MUTED}`}>
                        {t("metering.premises.cycle.noBillDay")}
                      </span>
                    ) : (
                      <span className={`block font-normal ${MUTED}`}>
                        {t("metering.premises.route.billsOn", {
                          day: ordinalDay(route.cycle_bill_day, i18n.language, (key) => t(key)),
                        })}
                      </span>
                    )}
                  </span>
                ))}
            </span>
          )}
        </PremisesFact>
        {/* ⚠ **THE SERVICES ARE WORDS HERE AND LETTER BADGES EVERYWHERE ELSE,
            AND THAT IS THE AGREED DRAWING (`CR-089` `P4`).** `DEF-439` put
            coloured letter squares in place of full-name chips on a TABLE CELL,
            where three chips wrapped onto two lines; a fact list has one line
            per fact and a badge there makes a reader decode `E W S T` to learn
            what a building buys.
            ⚠ **IT IS NOT A SECOND VOCABULARY.** The words come from
            `rating.service.<code>` — *the* service-name catalogue in this
            product (`DEF-763`), written in each of the eleven languages and the
            same string `ServiceTags` already puts in each badge's `title` and
            accessible name. The badge component is untouched and still draws
            every other screen. */}
        <PremisesFact label={t("metering.premises.col.services")}>
          <ServiceWords services={premises.services_available} t={t} />
        </PremisesFact>
        {/* ── DEF-650 — THE OWNER IS AN ACCOUNT, SHOWN AS ONE ─────────────
            PO 2026-08-27, verbatim: *"you ahve to showall details form
            account"*. This cell used to render `owner_manager`, a string.
            ⚠ **THE LABEL IS `Owner`, NOT `Owner / manager`, FROM 2026-09-09.**
            The drawing splits the two, and the block under this label is
            entirely about the OWNING party — its name, its category, its master
            account as a link, and **Find an owner** where there is none. The
            `/ manager` half becomes its own row below, which is what the
            drawing asks for and what the old label was quietly conflating. */}
        <PremisesFact label={t("metering.premises.col.owner")}>
          <OwnerAccountBlock
            /* ⚠ **THE PREMISES' OWN MASTER ACCOUNT, THROUGH THE ONE READER.**
               This passed `premises.owner` — an owner RECORD — until
               2026-09-22, so the block showed *Needs an owner* on every
               property whose owner nobody had imported (`DEF-MET-6155`).
               `premisesOwnerAccount` applies the ruling's declared precedence:
               `premises.master_account_id` first, the pre-ruling
               `premises_owners.master_account_id` second, and
               `accounts.premises_id` never. */
            account={premisesOwnerAccount(premises)}
            asked={ownerAccountAsked(premises)}
            ownerManager={premises.owner_manager}
            t={t}
            client={props.client}
            onLinked={props.onLinked}
          />
        </PremisesFact>
        {/* ── `Managed by` — DRAWN, AND EMPTY ON EVERY PROPERTY, ON PURPOSE ──
            ⚠ **THIS PRODUCT STORES ONE PARTY PER PROPERTY AND IT IS THE
            OWNER.** `premises.owner` is a single FK to `premises_owners`, whose
            `category` vocabulary INCLUDES *property manager* — so a managing
            agent is recorded today by being the owner record with that
            category, and there is nowhere else to put one.
            ⚠ **`owner_manager` IS NOT IT AND IS NOT BORROWED FOR IT.** Despite
            its name that column holds an OWNER's name: `owner_unmatched` is
            defined as *free text with no typed party*, wave B found 8 properties
            on `brazosbend` holding one, and `premises_owners
            .source_owner_manager` records it as the string an owner was matched
            FROM (`BR-MET-151`). Rendering it under *Managed by* would relabel
            real data as a different fact — which is worse than an empty row,
            because it would read as true.
            So the row states the absence and names where a manager goes today.
            Raised for the PO: a separate managing agent needs a column, and
            that is a ruling rather than a screen change. */}
        <PremisesFact label={t("metering.premises.field.managedBy")}>
          <Dash>{t("metering.premises.managedBy.none")}</Dash>
        </PremisesFact>
        <PremisesFact label={t("metering.premises.kpi.commonAreasLabel")}>
          {commons.length === 0 ? (
            <Dash>{t("metering.premises.commonAreasNone")}</Dash>
          ) : (
            commons.map((unit) => unit.label ?? unit.unit_no ?? "").join(" · ")
          )}
        </PremisesFact>
    </section>
    {/* `CR-161-BRC10` W3 · `DEF-MET-9226` — the Premise page's slot: every
        Premises field placed View (or Input, which implies View) here. Nothing
        at all for a tenant with none. */}
    <CustomFieldsView
      entity="premises"
      screen="PREMISE_PAGE"
      values={premises.custom_data ?? {}}
      formatDate={(iso) => iso}
      client={props.client ?? api}
    />
    {/* BR-MET-125's report. Wired here rather than offered as an optional prop
        nothing passes — hard-won law 2: a component whose caller never supplies
        its data is dead UI that every test still passes. */}
    <SubmeterReconciliationSection
      premisesId={premises.id}
      client={props.client ?? api}
      t={t}
    />
    </>
  );
}

export const submeterReconciliationQueryKey = (premisesId: string) =>
  ["premises", "submeter-reconciliation", premisesId] as const;

/**
 * **BR-MET-125's report — master vs Σ sub-meters, per period.**
 *
 * PO ruling 2026-08-26 (CR-038, closing the Blueprint's Open 9 and OQ-327),
 * verbatim: *"Open 9 - (a) store + report — keeps the door open"*. The worked
 * figure they signed it on: a building's master reads **12,400 kWh**, its two
 * sub-meters total **11,940**, so **460 kWh (3.71%)** is unaccounted for
 * against a **3%** tolerance.
 *
 * ⚠ **IT RENDERS A STORED FIGURE AND COMPUTES NOTHING** — not the gap, not the
 * percentage, not even its rounding (`gap_pct_display` is the server's 2dp
 * string, hard rule 2). That is the point of the ruling: a number recomputed on
 * every render would silently restate a closed month the day a late read
 * landed, and the figure a person quoted last week would change under them.
 *
 * ⚠ **AND IT BILLS NOTHING.** BR-MET-125: *"Billing common areas FROM it is
 * deliberately not built — the stored figure keeps that door open for a future
 * ruling."* There is no charge, no account and no money on this section, and
 * adding one is a PO ruling rather than a screen's initiative.
 *
 * **Three empty states, three different sentences**, because they are three
 * different facts and one shared "no data" line would lie about two of them:
 *   · no master meter on this premises → nothing to reconcile, ever;
 *   · masters but no stored period yet → nothing has been read;
 *   · a stored period that could NOT be computed → the sub-meters that were
 *     not read, BY NAME (a short Σ is never drawn as a bigger gap).
 *
 * ⚠ **IT LIVES ON `Overview`, NOT IN A SIXTH TAB.** r10 draws PRM-02 with five
 * tabs and DEF-578 is the PO removing a sixth; the tab set is theirs, not this
 * lane's. It is also deliberately NOT on `Common areas`, which would imply the
 * link between the gap and a common-area bill that BR-MET-125 says is not
 * built.
 */
export function SubmeterReconciliationSection(props: {
  premisesId: string;
  client: ApiClient;
  t: Translator;
}) {
  const { t } = props;
  const query = useQuery({
    queryKey: submeterReconciliationQueryKey(props.premisesId),
    queryFn: () => getPremisesSubmeterReconciliation(props.premisesId, {}, props.client),
  });

  if (query.isPending) {
    return <LoadingSkeleton variant="table" />;
  }
  const report = query.data;
  if (report === undefined) {
    return null;
  }

  return (
    <section className="mt-8 max-w-[960px]">
      <h3 className="text-base font-bold">{t("metering.premises.submeterRecon.heading")}</h3>
      <p className={`mt-1 text-sm ${MUTED}`}>{t("metering.premises.submeterRecon.intro")}</p>
      {!report.has_masters ? (
        <p className={`mt-3 text-sm ${MUTED}`} data-tracks="no-masters">
          {t("metering.premises.submeterRecon.noMasters")}
        </p>
      ) : report.rows.length === 0 ? (
        <p className={`mt-3 text-sm ${MUTED}`} data-tracks="no-periods">
          {t("metering.premises.submeterRecon.noPeriods")}
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <PlainTable>
            <thead>
              <tr>
                <th>{t("metering.premises.submeterRecon.col.period")}</th>
                <th>{t("metering.premises.submeterRecon.col.master")}</th>
                <th>{t("metering.premises.submeterRecon.col.masterReading")}</th>
                <th>{t("metering.premises.submeterRecon.col.submeterSum")}</th>
                <th>{t("metering.premises.submeterRecon.col.unaccounted")}</th>
                <th>{t("metering.premises.submeterRecon.col.tolerance")}</th>
                <th>{t("metering.premises.submeterRecon.col.status")}</th>
              </tr>
            </thead>
            <tbody>
              {report.rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.period_month}</td>
                  <td>{row.master_asset_no ?? <Dash />}</td>
                  <td>
                    <SubmeterQuantity value={row.master_consumption} unit={row.unit} />
                  </td>
                  <td>
                    <SubmeterQuantity value={row.submeter_sum} unit={row.unit} />
                  </td>
                  <td>
                    {/* The gap and its percentage travel together — 460 kWh
                        means nothing without the 3.71% and vice versa. */}
                    <SubmeterQuantity value={row.gap_quantity} unit={row.unit} />
                    {row.gap_pct_display !== null && (
                      <span className={`ml-2 text-sm ${MUTED}`}>({row.gap_pct_display})</span>
                    )}
                  </td>
                  <td>{row.tolerance_pct_display ?? <Dash />}</td>
                  <td>
                    <SubmeterReconStatus row={row} t={t} />
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}
    </section>
  );
}

/**
 * A stored quantity, or the honest absence of one.
 *
 * `null` is NOT zero. A `not_evaluated` row has no master figure, no Σ and no
 * gap, and drawing `0 kWh` in those cells would state that the building
 * reconciled perfectly — the exact opposite of what happened.
 */
function SubmeterQuantity(props: { value: string | null; unit: string }) {
  if (props.value === null) {
    return <Dash />;
  }
  // CLAUDE.md hard rule 3 — the quantity never renders without its unit, and
  // UnitCell is the ONE formatting path (BR-SHL-023).
  return <UnitCell quantity={props.value} unit={props.unit} />;
}

/**
 * The verdict cell. Four outcomes and each says which it is:
 * within tolerance · over tolerance · not evaluated (with the reason and the
 * unread sub-meters named).
 */
function SubmeterReconStatus(props: { row: SubmeterReconciliationRow; t: Translator }) {
  const { row, t } = props;
  if (row.status === "not_evaluated") {
    const named = row.unresolved_submeters
      .map((sub) => sub.asset_no)
      .filter((assetNo): assetNo is string => assetNo !== null);
    return (
      <span data-tracks="not-evaluated">
        <StatusPill tone="neutral">
          {t("metering.premises.submeterRecon.status.notEvaluated")}
        </StatusPill>
        <span className={`block mt-1 text-sm ${MUTED}`}>
          {t(`metering.premises.submeterRecon.reason.${row.reason ?? "unknown"}`, {
            defaultValue: row.reason ?? "",
          })}
          {named.length > 0 && ` · ${named.join(", ")}`}
        </span>
      </span>
    );
  }
  return row.within_tolerance ? (
    <StatusPill tone="success">
      {t("metering.premises.submeterRecon.status.withinTolerance")}
    </StatusPill>
  ) : (
    <StatusPill tone="warning">
      {t("metering.premises.submeterRecon.status.overTolerance")}
    </StatusPill>
  );
}

/**
 * **`Electric · Water · Sewer · Trash`** — the services a property buys, as
 * WORDS, for the one place `CR-089`'s `P4` drawing asks for words.
 *
 * ⚠ **THIS IS NOT A SECOND SERVICE VOCABULARY AND MUST NEVER BECOME ONE**
 * (`DEF-348`, `DEF-763`). The names are `rating.service.<code>` — THE
 * service-name catalogue in this product, written in each of the eleven
 * languages, and the identical string `ratingShared.ServiceTags` already puts
 * in every badge's `title` and accessible name. There is no map here, no list
 * of eleven codes, and nothing to keep in step when a twelfth service arrives:
 * an unknown code falls through to itself rather than being dropped, so a
 * service this file has never heard of still appears.
 *
 * ⚠ **AND THE BADGES ARE NOT REPLACED ANYWHERE ELSE.** `DEF-439` put coloured
 * letter squares in place of full-name chips on a TABLE CELL, where three chips
 * wrapped onto two lines and the PO photographed it. That reasoning is about
 * density in a grid; a fact list gives one line to one fact, and a badge row
 * there makes a reader decode `E W S T` to learn what a building buys.
 *
 * ⚠ **THREE STATES, NOT TWO (`DEF-762` / `CR-036` (h)).** `null` is a premises
 * **nobody has been asked about**; `[]` is a clerk answering **this address
 * offers nothing**. They are different facts and the same sentence for both is
 * the defect this repeats the guard against.
 */
export function ServiceWords(props: { services: readonly string[] | null; t: Translator }) {
  if (props.services === null) {
    return <span className="met-muted">{props.t("metering.services.notRecorded")}</span>;
  }
  if (props.services.length === 0) {
    return <span className="met-muted">{props.t("metering.services.none")}</span>;
  }
  return (
    <span>
      {props.services
        .map((code) => props.t(`rating.service.${code}`, { defaultValue: code }))
        .join(" · ")}
    </span>
  );
}

/** One row of r10's fact grid: label left, value right, a rule beneath. */
function PremisesFact(props: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-3 border-b border-b-divider text-base">
      <span className={MUTED}>{props.label}</span>
      <span className="font-bold text-right">{props.children}</span>
    </div>
  );
}


/**
 * PRM-02 · **UNITS** — and `CR-089` wave C task `C1` (`PUJ-12`) put money on it.
 *
 * ⚠ **WHAT WAS WRONG.** The tab listed a building's flats — number, label,
 * type, meters, occupancy, status — and carried **no money at all**. So the
 * question a landlord actually rings about, *which of my flats owes
 * something*, could not be answered from the tab that lists them: a clerk had
 * to open each unit in turn and read its Account tab.
 *
 * ⚠ **THE FIGURE IS THE LEDGER'S, NOT `accounts.balance`'s** — see
 * `selectors.unit_owed`. `DEF-138` records what the cached column cost: it is
 * written by nothing, so it answered *nothing owed* for every unit in the
 * estate including one holding an issued, unpaid **108.88**.
 *
 * ⚠ **RIGHT-ALIGNED AND TABULAR, WHICH IS THE POINT OF THE COLUMN.** A column
 * of figures is scanned down, not read across, and proportional digits of
 * different widths defeat that. `61.40` over `0.00` over `1,204.55` line up on
 * the decimal.
 *
 * ⚠ **A VACANT UNIT SAYS WHO PAYS FOR IT, AND THAT SENTENCE IS SIGNED.**
 * `BR-MET-094` (PO 2026-08-21): *"Yes vacant units will be charged we will not
 * option base charges or full billing"* — a vacancy is billed AUTOMATICALLY
 * and it is not a staff choice. `BR-CUS-170` (PO 2026-08-27, closing
 * `OQ-531`): *"when bill is generated for A - we should consider common areas
 * and U6 to U10 base charges"* — the OWNER's master account carries the base
 * charge of every unit with no occupying account, and
 * `billing.gather.base_charge_only_units` is the built path. So *Vacant — base
 * charges bill to the owner* states two ruled facts and invents neither.
 */
function UnitsTab(props: { units: readonly UnitRow[]; t: Translator; premisesId: string }) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  const [state, setState] = useState<TableRequestState>(() => tabTableState("unit"));

  const counts = occupancyCounts(props.units);
  // ── `CR-161-BRC10` W3 · `DEF-MET-9227` / `DEF-MET-9173` ──────────────────
  // The Units tab is where a unit's own fields and its service points' are
  // SHOWN (Part 2 rows 7 and 8): one column per field placed here, after the
  // drawn eight. A service point's cell names the service it belongs to.
  const unitColumns = useCustomFieldColumns<UnitRow>({
    entity: "units",
    screen: "PREMISE_UNITS",
    valuesOf: (unit) => [{ values: unit.custom_data ?? {} }],
  });
  const pointColumns = useCustomFieldColumns<UnitRow>({
    entity: "service_points",
    screen: "PREMISE_UNITS",
    valuesOf: (unit) =>
      Object.entries(unit.service_point_custom_data ?? {}).map(([code, values]) => ({
        prefix: t(`rating.service.${code}`, { defaultValue: code }),
        values,
      })),
  });
  // The tab's own door — the empty state's `+ New unit`. Same building, same
  // path helper as the header's: two doors onto one screen must not disagree
  // about whether the building comes with you.
  const addUnits = () => navigate(tenantPath(unitsAddPath(props.premisesId)));

  // IS-4: the ONE declared dimension this tab has, and it is the one its own
  // footer counts — so the chip a clerk applies and the sentence under the
  // table are answering the same question.
  const filters: TableFilterConfig[] = [
    {
      name: "occupancy",
      label: t("metering.units.col.occupancy"),
      options: [
        { value: "occupied", label: t("metering.units.occupancyFilter.occupied") },
        { value: "vacant", label: t("metering.units.occupancyFilter.vacant") },
      ],
    },
  ];

  const wanted = state.filters.occupancy;
  const filtered = props.units.filter(
    (unit) =>
      (wanted === undefined || wanted === "" || unit.occupancy === wanted) &&
      tabMatches(
        [unit.label, unit.unit_no, unit.occupant, unit.account_no, unit.floor_label],
        state.q,
      ),
  );
  // Default sort is the LABEL, which the blueprint states twice: *"what changes
  // is which of the two the eye meets first, and what the table sorts by."*
  const sorted = [...filtered].sort((a, b) => {
    const dir = state.dir === "desc" ? -1 : 1;
    const left = a.label ?? a.unit_no ?? "";
    const right = b.label ?? b.unit_no ?? "";
    return left.localeCompare(right, undefined, { numeric: true }) * dir;
  });
  const rows = tabRowsForPage(sorted, state);

  const config: TableConfig<UnitRow> = {
    // Its own suffix, so the Units tab's saved column set is not the property
    // list's (`TableConfig.screenId`'s own docstring: two lists that share an id
    // share one stored set).
    screenId: "PRM-02.units",
    getRowId: (unit) => unit.id,
    searchFields: ["label", "unit_no", "occupant", "account_no", "floor_label"],
    searchPlaceholder: "metering.premises.units.search",
    defaultSort: { sort: "unit", dir: "asc" },
    filters,
    columns: [
      {
        // ⚠ **ONE CELL, NOT TWO COLUMNS (`DEF-4740`).** The tab drew `Unit ID`
        // and `Unit` side by side; the blueprint draws ONE column whose label
        // leads in bold with the unit number quiet beneath it, in the same
        // cell — *"Both are shown … what changes is which of the two the eye
        // meets first"*.
        //
        // ⚠ **AND THE NUMBER IS NOT A DATABASE ID.** The blueprint corrects an
        // earlier draft of its own in writing (pages 23 and 25): `unit_no` is
        // *"the number from the tenant's own series — a printed reference, as
        // legitimate as a property number"*, so B14 rule 31 does not reach it.
        key: "unit",
        label: t("metering.units.col.label"),
        identity: true,
        sortable: true,
        cell: (unit) => (
          <span className="block">
            <InlineLinkTo to={tenantPath(unitDetailPath(unit.id))}>
              <span className="font-bold">
                {unit.label ?? unit.unit_no ?? t("metering.units.noNumber")}
              </span>
            </InlineLinkTo>
            {/* BR-MET-101: "Common" in the unit slot — r10's own vocabulary. */}
            {unit.is_common_area && (
              <>
                {" "}
                <StatusPill tone="neutral">{t("metering.units.commonArea")}</StatusPill>
              </>
            )}
            {unit.unit_no !== null && unit.label !== null && (
              <span className={`block text-sm ${MUTED}`} data-unit-no={unit.unit_no}>
                {unit.unit_no}
              </span>
            )}
          </span>
        ),
      },
      {
        key: "type",
        label: t("metering.units.col.type"),
        cell: (unit) =>
          unit.unit_type === null ? (
            <Dash />
          ) : (
            t(`metering.units.type.${unit.unit_type}`, { defaultValue: unit.unit_type })
          ),
      },
      {
        // `DEF-4740` — drawn and absent, with `floor_label` on the row all
        // along. *"Floor is shown, because it is recorded and it is how a
        // person finds a flat in a building."*
        key: "floor",
        label: t("metering.units.col.floor"),
        cell: (unit) =>
          unit.floor_label === null ? (
            <span className={ABSENT}>{t("metering.units.floorNone")}</span>
          ) : (
            unit.floor_label
          ),
      },
      {
        key: "meters",
        label: t("metering.units.col.meters"),
        cell: (unit) => <MetersCell meters={unit.meters} t={t} />,
      },
      {
        // `DEF-4740` — **Occupant replaces Occupancy**, and the blueprint says
        // why: *"a name and its account, not a state word. The state is in the
        // status pill where it belongs."* BR-MET-036 is untouched — occupancy
        // is still DERIVED server-side and still only rendered.
        //
        // ⚠ **A VACANT ROW NEVER DRAWS A DASH HERE** — *"a dash on that row
        // reads as `nothing is billed`, which is the opposite of true"* — so
        // the sentence `BR-MET-094` and `BR-CUS-170` between them ratify moves
        // into this cell, which is where the blueprint draws it.
        key: "occupant",
        label: t("metering.units.col.occupant"),
        cell: (unit) => (
          <OccupantCell
            unit={unit}
            t={t}
            accountHref={(accountId) => tenantPath(accountDetailPath(accountId))}
          />
        ),
      },
      {
        key: "owed",
        label: t("metering.units.col.owed"),
        numeric: true,
        cell: (unit) => <OwedCell unit={unit} t={t} />,
      },
      {
        key: "status",
        label: t("metering.units.col.status"),
        cell: (unit) => (
          <StatusPill tone={unitStatusTone(unit.status)}>
            {t(`metering.units.status.${unit.status}`, { defaultValue: unit.status })}
          </StatusPill>
        ),
      },
      ...unitColumns,
      ...pointColumns,
    ],
  };

  return (
    // ⚠ **NO PROSE ON THIS TAB, AND THAT IS THE DRAWING'S OWN WORDING** —
    // *"Eight columns, one search, no prose"*: no explainer paragraph, no
    // callout, no hint line. The panel heading and the sentence *"Accounts
    // attach to units, not to premises"* both go; the tab strip already names
    // the tab, and B14 rule 32 caps a screen's description budget.
    <section className="flex flex-col gap-3" data-tab="units">
      <DataTable<UnitRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={filtered.length}
        loading={false}
        empty={{
          // The drawn empty state: it OFFERS to add them, and says a property
          // with no units bills nothing.
          title: t("metering.premises.units.emptyTitle"),
          helper: t("metering.premises.units.emptyHelper"),
          ctaLabel: t("metering.units.action.new"),
          // B14 rule 4: the page header already carries this action, so the
          // empty state's copy of it is the secondary tier.
          ctaVariant: "secondary",
          onCta: addUnits,
        }}
        filterBarSlot={<FilterBar filters={filters} state={state} onStateChange={setState} />}
      />
      {props.units.length > 0 && (
        <TabFooterCounts>
          {t("metering.premises.units.footerCounts", {
            occupied: counts.occupied,
            vacant: counts.vacant,
          })}
        </TabFooterCounts>
      )}
      {/* The module's own Units list, filtered to this building. It is not in
          the drawn frame; it is kept because it is the only route that carries
          the premises filter across, and removing a working door is a loss a
          drawing did not ask for (hard-won law 2's mirror). */}
      {props.units.length > 0 && (
        <p className="m-0">
          <InlineLinkTo to={tenantPath(`${UNITS_ROUTE}?f.premises_id=${props.premisesId}`)}>
            {t("metering.premises.openInUnits")}
          </InlineLinkTo>
        </p>
      )}
    </section>
  );
}

/**
 * `DEF-4740`'s Occupant cell — **a name and its account, or who pays while
 * nobody is in it.** Three answers and no dash:
 *
 *   · an occupant → the NAME, with its account number quiet beneath;
 *   · a common area → `BR-MET-101`'s sentence, because telling a clerk a
 *     hallway is *vacant* is the one place those two rows must not read alike;
 *   · a vacancy → `Vacant — base charges bill to the owner`, italic.
 *
 * ⚠ **THE VACANCY SENTENCE IS SIGNED AND STATES TWO RULED FACTS.**
 * `BR-MET-094` (PO 2026-08-21): *"Yes vacant units will be charged we will not
 * option base charges or full billing"* — a vacancy is billed AUTOMATICALLY.
 * `BR-CUS-170` (PO 2026-08-27, closing `OQ-531`): the OWNER's master account
 * carries the base charge of every unit with no occupying account, and
 * `billing.gather.base_charge_only_units` is the built path.
 *
 * ⚠ **IT MOVED HERE FROM THE `Owed` CELL ON 2026-09-10, BY PO RULING**, which
 * is where the blueprint draws it. The money column keeps its own protection —
 * see `OwedCell`.
 */
export function OccupantCell(props: {
  unit: UnitRow;
  t: Translator;
  /** Record links (PO 2026-10-19): where the occupying account opens. Absent,
   *  the account number is plain text. */
  accountHref?: (accountId: string) => string;
}) {
  const { unit, t } = props;
  const href =
    props.accountHref !== undefined && unit.account_id != null && unit.account_id !== ""
      ? props.accountHref(unit.account_id)
      : null;
  // ⚠ **THE ORDER OF THESE THREE IS THE RULE, NOT A STYLE.** A common area is
  // asked about FIRST (`BR-MET-101`) because a hallway is never *occupied* and
  // must never read like a vacant flat; then `occupancy`, which is DERIVED
  // server-side from the active account (`BR-MET-036`) and is the signed fact
  // about whether anybody is in it; and only then the NAME. Branching on
  // whether `occupant` happens to be non-null would let a stale name on a
  // vacated row silence a sentence two ratified rules require.
  if (unit.is_common_area) {
    return (
      <span className={`block text-sm ${ABSENT}`} data-occupant-state="common-area">
        {t("metering.units.account.commonAreaOwnerBilled")}
      </span>
    );
  }
  if (unit.occupancy === "vacant") {
    return (
      <span className={`block text-sm ${ABSENT}`} data-occupant-state="vacant">
        {t("metering.units.owed.vacantOwnerBilled")}
      </span>
    );
  }
  if (unit.occupant !== null) {
    return (
      <span className="block" data-occupant-state="named">
        {/* The NAME opens the account only when there is no number to carry
            the link — the number is the record's handle everywhere else. */}
        {href !== null && unit.account_no === null ? (
          <InlineLinkTo to={href}>{unit.occupant}</InlineLinkTo>
        ) : (
          unit.occupant
        )}
        {unit.account_no !== null && (
          <span className={`block text-sm ${MUTED}`}>
            {href !== null ? (
              <InlineLinkTo to={href}>
                {unit.account_no}
              </InlineLinkTo>
            ) : (
              unit.account_no
            )}
          </span>
        )}
      </span>
    );
  }
  // Occupied and no name served. The vacancy sentence would be FALSE here and
  // a name cannot be invented, so this is the one shape in the column that is
  // simply a gap — and it is drawn as one.
  return (
    <span className="block" data-occupant-state="unnamed">
      <Dash />
    </span>
  );
}

/**
 * `C1`'s cell. **Four answers, and collapsing any two of them would be a lie
 * about money.**
 *
 *   · **a figure**, at 2 dp with its currency, through the ONE `MoneyCell`;
 *   · **nothing measured** — no occupying account, so the books were never
 *     asked. Who pays instead is the `Occupant` cell's sentence;
 *   · **a sentence** when the books could not be ASKED (`balance_unavailable`);
 *   · **a dash** when the payload does not carry the column at all.
 *
 * ⚠ **A VACANT UNIT DOES NOT GET `0.00`, AND THE PO RE-RULED THAT ON
 * 2026-09-10 WHILE MOVING THE SENTENCE OUT OF THIS CELL.** The blueprint draws
 * `Unit 4 · 0.00 · Vacant — base charges bill to the owner`; the ruling keeps
 * the figure half guarded in the same breath — *show `0.00` only when the
 * balance really is zero, never manufactured over a real debt.*
 * `owed_for_units` resolves the **occupying** account (`BR-CUS-055`'s
 * behaviour class), so an unlet unit produces no ledger read at all — and a
 * unit whose tenant moved out **still owing** has a CLOSED account that map
 * deliberately excludes. A manufactured `0.00` there would say *nothing is
 * owed* over a real debt, which is `DEF-138` word for word: that defect is the
 * record of a guard reading a column nobody writes and answering `False` for
 * every unit in the estate, one of which held an unpaid **108.88**. The seam's
 * own contract says it too — *"The caller says vacant, never `0.00`"*.
 *
 * ⚠ **A ZERO THAT IS REAL STILL RENDERS AS `0.00`** — that is the other half
 * of the ruling, and it needs no branch: a let unit whose ledger reads zero
 * comes through `MoneyCell` like any other figure.
 *
 * ⚠ **WHERE THE VACANCY SENTENCE WENT.** `OccupantCell`, above, which is where
 * the blueprint draws it and where a name would otherwise be. It still states
 * the same two ruled facts (`BR-MET-094`, `BR-CUS-170`) and a common area
 * still gets its own sentence rather than the vacancy one (`BR-MET-101`).
 */
export function OwedCell(props: { unit: UnitRow; t: Translator }) {
  const { unit, t } = props;
  const owed = unit.owed;
  // `undefined` = this payload does not carry the column at all. Saying
  // nothing is right; saying `0.00` would be a claim.
  if (owed === undefined) {
    return (
      <span className="block text-right">
        <Dash />
      </span>
    );
  }
  if (owed === null) {
    // ⚠ **THE SENTENCE MOVED TO `OccupantCell`; THE PROTECTION DID NOT MOVE
    // WITH IT (PO ruling 2026-09-10).** The blueprint draws `0.00` on the
    // vacant row and the ruling keeps the guard in the same breath: *"show
    // 0.00 only when the balance really is zero, never manufactured over a
    // real debt."* `owed_for_units` resolves the OCCUPYING account, so an
    // unlet unit produced no ledger read at all — and a unit whose tenant
    // moved out STILL OWING has a CLOSED account that map deliberately
    // excludes. Printing a zero here is `DEF-138` word for word: a guard
    // reading a column nobody writes and answering *nothing owed* for every
    // unit in the estate, one of which held an unpaid 108.88.
    // So the cell says nothing was measured, and the row still says who pays.
    return (
      <span
        className={`block text-right text-sm ${ABSENT}`}
        data-owed-state="no-account"
        title={t("metering.units.owed.notMeasuredWhy")}
      >
        {t("metering.units.owed.notMeasured")}
      </span>
    );
  }
  if (owed.balance === null || owed.balance_currency === null) {
    return (
      <span className={`block text-right text-sm ${MUTED}`} data-owed-state="unreadable">
        {t("metering.units.owed.unreadable")}
      </span>
    );
  }
  return (
    <span className="block text-right tabular-nums" data-owed-state="figure">
      <MoneyCell amount={owed.balance} currency={owed.balance_currency} />
    </span>
  );
}

/**
 * PRM-02 · **ASSETS** — `CR-089` wave C tasks `C3` and `C4` (`PUJ-14`).
 *
 * ⚠ **THE TAB IS CALLED *Assets* AND IT STAYS *Assets*.** We proposed renaming
 * it to *Meters*; the PO reversed it in their own words — *"it will ahve all
 * meter, sub meters, cart, ERu, fire - all kind of assets will be tagged
 * here"* — and `BR-MET-045` already named it Assets. Narrowing it to meters
 * would hide ten of the thirteen types this product ships.
 *
 * ── WHAT WAS WRONG WITH IT ────────────────────────────────────────────────
 * One flat table of seven columns: `Asset # · Asset type · Meter type · Read
 * method · Assigned to · Installed · Status`. **Three of the seven say what
 * kind of thing it is and none says when it was last read.** A trash cart and
 * a water meter were drawn identically, so a clerk standing on a building
 * could not tell at a glance which rows BILL and which are simply things the
 * utility owns — and could not answer *when was this last read*, which is the
 * one question a meter row exists to answer.
 *
 * ── `C3` · TWO GROUPS, FROM THE SERVER'S OWN CATEGORY ─────────────────────
 * `BR-AST-004` already partitions every type onto exactly one of three
 * category tabs, served as `row.tab`, and `/lookups/asset_types` refuses any
 * other value — so the split is READ, never inferred from a type code. The two
 * groups are the two SENTENCES a clerk needs, which is why `sub_meters` joins
 * `meters` rather than standing alone: a sub-meter is read and it bills, and
 * *what bills here* is one question, not two.
 *
 * ── `C4` · A LAST-READ COLUMN THAT CAN SAY *not read*, AND WHY ────────────
 * `last_read` is served for every meter and sub-meter (`selectors
 * .asset_page_rows`, batched into one query). **Behind-the-meter rows carry no
 * such key at all, and that is the point**: `null` would be indistinguishable
 * from *a meter nobody has read yet*, which is a completely different and much
 * more alarming sentence. So the cell says *not read* WITH ITS REASON, and the
 * reason is the type's own billing shape:
 *
 *   · **a fire service line** is priced by its DIAMETER — `CR-063`, PO
 *     2026-09-02: *"Fire as utility Service - Capacity based - this will
 *     behave exactly like trash"*, the size class picks the price and the
 *     count multiplies it. Nothing about it is metered. → *billed on size*.
 *   · **a container / cart** is priced PER CART (`BR-RAT-090`, `OQ-303` closed
 *     2026-08-21: three carts at $15.00 = $45.00). → *billed per cart*.
 *   · **everything else behind the meter** — a backflow preventer, a comms
 *     endpoint, an EV charger — is kit the utility owns and does not read. →
 *     *we own it*.
 *
 * ⚠ **THE TWO NAMED CODES ARE THE ONLY ONES CLAIMED, AND A TENANT'S OWN TYPE
 * FALLS TO THE GENERAL SENTENCE.** `asset_types` is tenant-extensible
 * (`BR-TEN-036`), so a utility may add a type this build has never heard of;
 * saying *billed on size* about it would be inventing a price rule. The
 * general sentence is true of every behind-the-meter asset by definition.
 *
 * ⚠ **`Meter type` AND `Read method` ARE DROPPED FROM THE BEHIND-THE-METER
 * TABLE AND KEPT ON THE METERED ONE.** `BR-AST-044` requires all three
 * classifications on the **asset detail view (S50)** and as list filters — not
 * in every table — and its own amendment makes `meter_type` **UNAVAILABLE on
 * non-measuring types**: setting one on a PV or a battery is REFUSED, never
 * stored. So those two columns are structurally empty on every behind-the-
 * meter row, and two columns of dashes are exactly the noise this task was
 * written to remove.
 */
function PremisesAssetsTab(props: {
  premisesId: string;
  client: ApiClient;
  t: Translator;
  regional: RegionalProps;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  const { timeZone, dateFormat } = useRegional(props.regional);
  const [state, setState] = useState<TableRequestState>(() => tabTableState("asset"));
  const assetsQuery = useQuery({
    queryKey: premisesAssetsQueryKey(props.premisesId),
    queryFn: () =>
      getAssets({ filters: { premises_id: props.premisesId }, per: 200 }, props.client),
  });

  // DEF-RAT-9321 — the Size column prints the size's NAME, never its code.
  const sizeNames = useSizeClassNames(props.client);
  const all: readonly AssetRow[] = assetsQuery.data?.results ?? [];
  const metered = all.filter(isMeteredAsset);
  const behind = all.length - metered.length;
  const read = metered.filter((row) => (row.last_read?.read_at ?? null) !== null).length;
  const stillToRead = metered.length - read;

  // ⚠ **THE TWO GROUPS ARE A DECLARED FILTER, NOT TWO STANDING CHIPS, AND THAT
  // IS A RATIFIED RULE BEATING THE FRAME WHERE THE FRAME DID NOT CONSIDER IT.**
  // The blueprint draws `METERS & SUB-METERS` and `BEHIND THE METER` as chips
  // sitting permanently in the toolbar. `DEF-1700` removed exactly that shape
  // from this product by PO ruling — *"as per our stadard first raw of tookkit
  // is more than suficient"* — because every one of those rows duplicated a
  // dimension the same screen already declared in `TableConfig.filters`. So
  // the split is declared here, the `+ Filter ▾` panel offers it, and applying
  // one puts its chip in the toolbar where B14 rule 12 puts every other.
  const filters: TableFilterConfig[] = [
    {
      name: "group",
      label: t("metering.premises.assets.filter.group"),
      options: [
        { value: "metered", label: t("metering.premises.assets.group.metered") },
        { value: "behind", label: t("metering.premises.assets.group.behind") },
      ],
    },
  ];

  const wanted = state.filters.group;
  const filtered = all.filter((row) => {
    if (wanted === "metered" && !isMeteredAsset(row)) {
      return false;
    }
    if (wanted === "behind" && isMeteredAsset(row)) {
      return false;
    }
    return tabMatches(
      [row.asset_no, row.type_name, row.assigned_to, row.serial_no, row.size_class, sizeClassName(row.size_class, sizeNames)],
      state.q,
    );
  });
  // ⚠ **THE GROUP LEADS THE SORT WHILE NOBODY HAS CHOSEN OTHERWISE**, so the
  // rows that BILL still read first — which is the one thing the drawn group
  // heading rows buy a clerk, and `DataTable` has no group-row capability to
  // draw them with (recorded as a divergence in the conformance file rather
  // than answered by growing the kit for one tab).
  const sorted = [...filtered].sort((a, b) => {
    const dir = state.dir === "desc" ? -1 : 1;
    const group = Number(isMeteredAsset(b)) - Number(isMeteredAsset(a));
    if (group !== 0) {
      return group;
    }
    return a.asset_no.localeCompare(b.asset_no, undefined, { numeric: true }) * dir;
  });
  const rows = tabRowsForPage(sorted, state);

  const config: TableConfig<AssetRow> = {
    screenId: "PRM-02.assets",
    getRowId: (row) => row.id,
    searchFields: ["asset_no", "type_name", "assigned_to", "serial_no", "size_class"],
    searchPlaceholder: "metering.premises.assets.search",
    defaultSort: { sort: "asset", dir: "asc" },
    filters,
    columns: [
      {
        key: "asset",
        label: t("assets.col.asset"),
        identity: true,
        sortable: true,
        cell: (row) => (
          <InlineLinkTo to={tenantPath(assetDetailPath(row.id))}>{row.asset_no}</InlineLinkTo>
        ),
      },
      {
        // *"Three type columns become two — what it is, and the service it
        // belongs to."* `Meter type` and `Read method` are drawn on NEITHER
        // group: `BR-AST-044` puts all three classifications on the asset
        // detail (S50) and in the list filters, not in every table.
        key: "whatItIs",
        label: t("assets.col.whatItIs"),
        cell: (row) => row.type_name,
      },
      {
        // `DEF-4740` — SERVED all along and never drawn. The name comes from
        // `rating.service.<code>`, THE service-name catalogue in this product
        // (see `ServiceWords` — there is no second vocabulary here).
        key: "service",
        label: t("assets.col.service"),
        cell: (row) =>
          row.service === null || row.service === undefined || row.service === "" ? (
            <Dash />
          ) : (
            t(`rating.service.${row.service}`, { defaultValue: row.service })
          ),
      },
      {
        // `DEF-4740` — `BR-AST-500`'s size class, served, with a catalogue key
        // nothing read. The value is the tenant's own code TEXT (`2"`,
        // `Class 200`, `96 gal`), which is what the asset detail already
        // shows: a printed reference, never a database id.
        key: "size",
        label: t("assets.col.size"),
        cell: (row) => sizeClassName(row.size_class, sizeNames) ?? <Dash />,
      },
      {
        // *"Where says which unit, common area or the property itself, in
        // words."* `assigned_to` is the UNIT's label and is `null` exactly
        // when the asset hangs on the property (`assets/selectors.py`), so the
        // null is a fact rather than a gap — drawn italic, as the frame draws
        // it.
        key: "where",
        label: t("assets.col.where"),
        cell: (row) =>
          row.assigned_to === null ? (
            <span className={ABSENT}>{t("metering.premises.assets.whereProperty")}</span>
          ) : (
            row.assigned_to
          ),
      },
      {
        key: "installed",
        label: t("assets.col.installed"),
        cell: (row) =>
          row.install_date === null ? (
            <Dash />
          ) : (
            // BR-SHL-034: every displayed date, one formatter.
            <DateCell value={row.install_date} timeZone={timeZone} dateFormat={dateFormat} />
          ),
      },
      {
        key: "lastRead",
        label: t("assets.col.lastRead"),
        cell: (row) => (
          <LastReadCell asset={row} t={t} timeZone={timeZone} dateFormat={dateFormat} />
        ),
      },
      {
        // The pill AND `BR-AST-007`'s derived Test-due chip, from the registry's
        // own cell — the blueprint draws `TEST DUE 30 SEP` on the backflow
        // preventer, which is the one date on this tab with a deadline on it.
        key: "status",
        label: t("assets.col.status"),
        cell: (row) => <AssetStatusCell row={row} t={t} />,
      },
    ],
  };

  return (
    <section className="flex flex-col gap-3" data-tab="assets">
      <DataTable<AssetRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={assetsQuery.data === undefined ? null : filtered.length}
        loading={assetsQuery.isPending}
        empty={{
          // The drawn empty state: it says the property cannot bill a service
          // until a meter is on a unit, and it LINKS TO THE UNITS.
          title: t("metering.premises.assets.emptyTitle"),
          helper: t("metering.premises.assets.emptyHelper"),
          ctaLabel: t("metering.premises.assets.emptyCta"),
          ctaVariant: "secondary",
          onCta: () => navigate(tenantPath(`${PREMISES_ROUTE}/${props.premisesId}?tab=units`)),
        }}
        filterBarSlot={<FilterBar filters={filters} state={state} onStateChange={setState} />}
      />
      {all.length > 0 && (
        <TabFooterCounts>
          {/* The drawn STATES block: on overdue reads *"the count leads the
              footer"*, so the outstanding clause is written first and is
              absent entirely when there is nothing outstanding. */}
          {stillToRead > 0 && (
            <>
              <span data-assets-still-to-read={String(stillToRead)}>
                {t("metering.premises.assets.footerUnread", { n: stillToRead })}
              </span>
              {" · "}
            </>
          )}
          {t("metering.premises.assets.footerCounts", { read, notRead: behind })}
        </TabFooterCounts>
      )}
    </section>
  );
}

/**
 * `BR-AST-004`'s category, read as the one question this tab asks: **does this
 * thing bill by a reading?** Exported so the test asserts the SAME predicate the
 * screen groups by rather than a second copy of it.
 */
export function isMeteredAsset(row: AssetRow): boolean {
  return row.tab === "meters" || row.tab === "sub_meters";
}

/** The three sentences a behind-the-meter row can carry, keyed by TYPE CODE. */
export const NOT_READ_REASONS: Readonly<Record<string, string>> = {
  fire_line: "metering.premises.assets.notRead.fire",
  container_cart: "metering.premises.assets.notRead.cart",
};
export const NOT_READ_DEFAULT = "metering.premises.assets.notRead.owned";

export function notReadKey(typeCode: string): string {
  return NOT_READ_REASONS[typeCode] ?? NOT_READ_DEFAULT;
}

/**
 * `C4`'s cell. THREE answers, and the difference between them is the whole
 * task:
 *
 *   · a meter with a reading → the DATE, through the shared formatter;
 *   · a meter with none → *no read yet*, which is a fact about this meter and
 *     is worth chasing;
 *   · anything behind the meter → *not read*, with the reason it is not.
 *
 * ⚠ **A DASH WOULD COLLAPSE ALL THREE INTO ONE**, which is what the tab did
 * before this task by having no column at all.
 */
function LastReadCell(props: {
  asset: AssetRow;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { asset, t } = props;
  if (!isMeteredAsset(asset)) {
    return (
      <span className={`text-sm ${MUTED}`} data-not-read={asset.type}>
        {t(notReadKey(asset.type))}
      </span>
    );
  }
  const readAt = asset.last_read?.read_at ?? null;
  if (readAt === null) {
    return (
      <span className={`text-sm ${MUTED}`} data-no-read-yet="">
        {t("metering.premises.assets.noReadYet")}
      </span>
    );
  }
  return (
    <DateCell value={readAt} timeZone={props.timeZone} dateFormat={props.dateFormat} />
  );
}

/**
 * `CR-089` `P9` — **an audit row's three facts, drawn as three columns.**
 *
 *   · `What changed` — the field, in words, or the event when a whole record
 *     arrived at once;
 *   · `From` — what it used to say;
 *   · `To` — what it says now.
 *
 * ⚠ **THE `From` CELL HAS THREE DRAWN FORMS AND THEY ARE DIFFERENT FACTS**, and
 * collapsing any two is the sharpest miss the blueprint records on this screen:
 *
 *   · `—` where the row is a CREATION and there was no previous value at all;
 *   · the previous value, in the ABSENT style, where the field previously HELD
 *     NOTHING — *"a property that had no route now says `None → Route 12`,
 *     which is a different fact from a route being changed"*;
 *   · the previous value, plainly, where there was one.
 *
 * ⚠ **AN ABSENT PREVIOUS VALUE IS NOT AN EMPTY CELL.** `formatAuditValue`
 * already answers `Not set` for a field that held nothing, so the fact reaches
 * this cell as words; what this function adds is the STYLE that separates it
 * from a value somebody typed. An empty cell there would read as *this field
 * has always said Route 12*, which is the opposite of what happened.
 *
 * ⚠ **THE `before === null` BRANCH IS NOT REACHED FROM THE TAB, AND THAT IS
 * WRITTEN DOWN RATHER THAN LEFT TO BE DISCOVERED (law 7, found by breaking it
 * first).** A creation is short-circuited by the `From` column itself to ONE
 * dash for the whole row — because *which fields does a brand-new record have*
 * is not a change — so a fault planted in this branch left the whole-row suite
 * green. It stays because this cell is exported and a create-snapshot
 * `AuditFieldRow` legitimately carries `before: null`, and
 * `PremisesTabFurniture.test.tsx` drives all three forms DIRECTLY so the
 * branch is somewhere a test can actually fail.
 */
export function AuditFromCell(props: { field: AuditFieldRow; t: Translator }) {
  const { field } = props;
  if (field.before === null) {
    // A creation: there was no previous value to have. `Dash` is this repo's
    // "no such fact", and it is deliberately NOT the absent style, which means
    // "there was a field and it was empty".
    return <Dash />;
  }
  // ⚠ **COMPARED THROUGH `auditText`, NOT AGAINST A LITERAL.** `audit.value.*`
  // has no row in any of the eleven catalogues, so `formatAuditValue` renders
  // its ENGLISH FALLBACK and `t("audit.value.notSet")` on its own would answer
  // with the key name. Asking the same helper the formatter asked is the only
  // form of this comparison that stays true if a catalogue row ever lands.
  const empty =
    field.before === auditText(props.t, "audit.value.notSet", "Not set") ||
    field.before === auditText(props.t, "audit.value.none", "None");
  return <span className={empty ? ABSENT : undefined}>{field.before}</span>;
}

/**
 * How many changed fields one row draws before it says how many more there are.
 *
 * ⚠ **A CAP, BECAUSE A CREATION IS A WHOLE SNAPSHOT.** `premises.created`
 * records `premises_detail_dict(row)` — thirty-odd keys — so a cell that
 * stacked every one of them would set the height of its whole row and turn a
 * scannable history into a wall. That is the failure `tableTypes`' own
 * `cell` docstring records the PO finding ten times in one sitting.
 * An UPDATE diffs to the fields that actually moved and is almost always
 * under this, so the cap fires on creations and hardly ever otherwise.
 */
export const AUDIT_ROW_FIELDS = 3;

/** How many of the entity's own rows the tab draws before the "full log" link. */
export const AUDIT_TAB_ROWS = 25;

/**
 * The saved-column key for ONE mount of the shared `AuditTab` (`DEF-MET-4765`).
 *
 * The property's history is `PRM-02` and the unit's is `PRM-03` — A1's own
 * screen ids, which is what `screenId` is for. They were the SAME string until
 * 2026-09-10, so the two histories shared one `table.<screen>.columns`
 * preference and hiding a column on a building hid it on every flat in it.
 *
 * ⚠ **`PRM-02.audit` IS RETURNED FOR EVERYTHING THAT IS NOT A UNIT, ON
 * PURPOSE.** The property's stored key must not move — a renamed key is a
 * clerk's saved layout silently reset — so the default is the string that was
 * already there, and a new entity type gets a row here rather than a silent
 * share.
 */
export function auditScreenId(entityType: string): string {
  return entityType === "unit" ? "PRM-03.audit" : "PRM-02.audit";
}

export const entityAuditQueryKey = (entityType: string, entityId: string) =>
  ["audit-log", "by-entity", entityType, entityId] as const;

/**
 * PRM-02 / PRM-03's **Audit log** tab — the entity's OWN rows, drawn here.
 *
 * ⚠ **THIS TAB USED TO RENDER A LINK AND NO ROWS, AND THAT WAS `DEF-579`** —
 * reported by the PO on 2026-08-22 in their own words: *"in Premises and Unit
 * level Audit log does not point to audit log it should audit log on that
 * perticular unit or premises"*. `BR-AUD-010` is CONFIRMED and says RENDER
 * **and** LINK; the shipped tab did only the second half.
 *
 * ⚠ **AND IT DREW `When · Actor · Action` WITH THE VALUES BEHIND AN EXPAND
 * UNTIL 2026-09-10 (`DEF-4739` · `DEF-4740`).** The blueprint's amber block
 * names that as the problem in so many words: *"the thing a person actually
 * needs — what the value was before — is behind a press, one row at a time."*
 * The drawn frame is **six columns** — `When · Who · What changed · From · To`
 * and the row actions — with **no `Expand` control and no disclosure anywhere
 * in the table**, because *"that is the whole use of an audit log: seeing what
 * a field used to say."* `Actor` becomes `Who` in the same block.
 *
 * ⚠ **IT COSTS NO EXTRA REQUEST.** The values ride on the row itself, served by
 * `audit_page(..., with_values=True)` because the query names an entity.
 *
 * ⚠ **`before`/`after` UNDEFINED FALLS BACK TO THE PRESS AND DRAWS NO
 * ABSENCE.** A payload from before that change — or a caller that did not
 * scope by entity — carries neither key, and *the values were not sent* is not
 * the same claim as *no values were recorded*. Such a row keeps the shared
 * expandable cell in the `What changed` column and leaves `From`/`To` EMPTY
 * rather than asserting a dash into them. It cannot occur on this tab, whose
 * query always names an entity; it is honest rather than reachable.
 *
 * ⚠ **TWO THINGS THE FRAME DOES NOT DRAW ARE KEPT BY PO RULING (2026-09-10):**
 * the `Open the audit log for this record →` link and the `Showing the last 2
 * years` sentence. *"Keep it as it is"* — because the window is bounded by the
 * server (`BR-AUD-006`/`BR-AUD-013`) and an unstated absence reads as *it
 * never happened*. The conformance file is amended to say so rather than the
 * two being deleted.
 *
 * It is still ONE audit surface: the rows come from the same `GET /audit-log`
 * with the same filters the link carries, the sentence is
 * `auditEventSentence`'s and the changed set is `auditFieldSet`'s — so an
 * event cannot be worded two ways (`BR-AUD-010`).
 */
export function AuditTab(props: {
  entityType: string;
  entityId: string;
  t: Translator;
  regional: RegionalProps;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props.regional);
  const [state, setState] = useState<TableRequestState>(() => tabTableState("when"));
  const entriesQuery = useQuery({
    queryKey: entityAuditQueryKey(props.entityType, props.entityId),
    queryFn: () =>
      getAuditLog({
        filters: { entity_type: props.entityType, entity_id: props.entityId },
        per: AUDIT_TAB_ROWS,
      }),
    enabled: props.entityId !== "",
  });

  const fullLog = (
    <ButtonLink
      variant="secondary"
      to={tenantPath(auditViewerPath(props.entityType, props.entityId))}
    >
      {t("metering.audit.openViewer")}
    </ButtonLink>
  );

  if (entriesQuery.data === undefined && !entriesQuery.isPending) {
    // A18 §4 — the server's own reason, and the link still works, so a reader
    // whose tab failed to load is not stranded on this screen.
    return (
      <section className="flex flex-col gap-3">
        <p className={`m-0 text-base ${MUTED}`}>{t("metering.audit.failed")}</p>
        {fullLog}
      </section>
    );
  }

  const all: readonly AuditRow[] = entriesQuery.data?.page.results ?? [];
  // IS-4: the dimension a person actually filters a history by is WHAT
  // HAPPENED, and the options are the events THIS record has — offering an
  // action nothing here recorded is a filter that can only ever empty the list.
  const seen = new Map<string, string>();
  for (const row of all) {
    if (!seen.has(row.action)) {
      seen.set(row.action, auditEventSentence(row.action, t).text);
    }
  }
  const filters: TableFilterConfig[] = [
    {
      name: "action",
      label: t("audit.col.action"),
      options: [...seen].map(([value, label]) => ({ value, label })),
    },
  ];

  const wanted = state.filters.action;
  const filtered = all.filter((row) => {
    if (wanted !== undefined && wanted !== "" && row.action !== wanted) {
      return false;
    }
    const set = auditFieldSet(row.before ?? null, row.after ?? null, t);
    return tabMatches(
      [
        auditEventSentence(row.action, t).text,
        actorLabel(row, t),
        ...set.fields.flatMap((field) => [field.label, field.before, field.after]),
      ],
      state.q,
    );
  });
  const sorted = [...filtered].sort((a, b) => {
    const dir = state.dir === "desc" ? -1 : 1;
    return a.created_at.localeCompare(b.created_at) * dir;
  });
  const rows = tabRowsForPage(sorted, state);

  /** The changed set of ONE row, capped, with what the cap hid. */
  function changed(row: AuditRow): { fields: AuditFieldRow[]; more: number; served: boolean } {
    if (row.before === undefined && row.after === undefined) {
      return { fields: [], more: 0, served: false };
    }
    const set = auditFieldSet(row.before ?? null, row.after ?? null, t);
    return {
      fields: set.fields.slice(0, AUDIT_ROW_FIELDS),
      more: Math.max(0, set.fields.length - AUDIT_ROW_FIELDS),
      served: true,
    };
  }

  /** A creation records a snapshot, so *which fields does a brand-new record
   *  have* is not a change and the column says what HAPPENED instead — which
   *  is exactly what the frame draws on its `Property added` row. */
  const isCreation = (row: AuditRow) => row.before === null || row.before === undefined;

  const config: TableConfig<AuditRow> = {
    // ⚠ **ONE SCREEN ID PER MOUNT, AND IT USED TO BE ONE FOR BOTH
    // (`DEF-MET-4765`).** `screenId` keys `table.<screen>.columns` — the SAVED
    // column order and visibility (`columnPreferenceKey`, `BR-SHL-013`) — and
    // `tableTypes` says so in its own words: *"two lists that share a
    // `screenId` share one saved column set"*. This component is mounted twice,
    // on the PROPERTY's history and on the UNIT's, and both declared
    // `PRM-02.audit`. So a clerk hiding a column on one building's history
    // silently hid it on every unit's history in the tenant, and there was no
    // way to tell from either screen.
    //
    // The property keeps `PRM-02.audit` EXACTLY, so no saved preference moves;
    // only the unit gains its own key. Derived from `entityType` rather than
    // passed as a prop, because a prop is a thing a third mount can forget.
    screenId: auditScreenId(props.entityType),
    getRowId: (row) => row.id,
    searchFields: ["action", "actor", "summary"],
    searchPlaceholder: "metering.premises.audit.search",
    defaultSort: { sort: "when", dir: "asc" },
    filters,
    columns: [
      {
        key: "when",
        label: t("audit.col.when"),
        identity: true,
        sortable: true,
        // BR-SHL-034: an instant renders in the tenant TZ through the ONE
        // formatter.
        cell: (row) => (
          <DateCell value={row.created_at} timeZone={timeZone} dateFormat={dateFormat} withTime />
        ),
      },
      {
        // *"Actor becomes Who, and shows a person's name."* BR-AUD-003: a null
        // actor is a SYSTEM job — named, never blanked. Read through S61's own
        // helper so the two surfaces cannot word it differently.
        key: "who",
        label: t("audit.col.who"),
        cell: (row) => actorLabel(row, t),
      },
      {
        key: "whatChanged",
        label: t("audit.col.whatChanged"),
        cell: (row) => {
          const set = changed(row);
          if (!set.served) {
            // The row cannot fill three columns, so it keeps the shared
            // expandable cell rather than asserting an absence into them.
            return <AuditEventCell row={row} t={t} />;
          }
          if (set.fields.length === 0 || isCreation(row)) {
            return (
              <span data-audit-action={row.action}>{auditEventSentence(row.action, t).text}</span>
            );
          }
          return (
            <span className="block" data-audit-action={row.action}>
              {set.fields.map((field) => (
                <span className="block" key={field.key} data-audit-field={field.key}>
                  {field.label}
                </span>
              ))}
              {set.more > 0 && (
                <span className={`block text-sm ${MUTED}`}>
                  {t("metering.audit.moreFields", { n: set.more })}
                </span>
              )}
            </span>
          );
        },
      },
      {
        key: "from",
        label: t("audit.col.from"),
        cell: (row) => {
          const set = changed(row);
          if (!set.served) {
            return null;
          }
          if (set.fields.length === 0 || isCreation(row)) {
            return <Dash />;
          }
          return (
            <span className="block">
              {set.fields.map((field) => (
                <span className="block" key={field.key} data-audit-from={field.key}>
                  <AuditFromCell field={field} t={t} />
                </span>
              ))}
            </span>
          );
        },
      },
      {
        key: "to",
        label: t("audit.col.to"),
        cell: (row) => {
          const set = changed(row);
          if (!set.served) {
            return null;
          }
          if (set.fields.length === 0) {
            return <Dash />;
          }
          return (
            <span className="block">
              {set.fields.map((field) => (
                <span className="block" key={field.key} data-audit-to={field.key}>
                  {field.after}
                </span>
              ))}
              {set.more > 0 && (
                <span className={`block text-sm ${MUTED}`}>
                  {t("metering.audit.moreFields", { n: set.more })}
                </span>
              )}
            </span>
          );
        },
      },
    ],
  };

  return (
    <section className="flex flex-col gap-3" data-tab="audit">
      <DataTable<AuditRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={entriesQuery.data === undefined ? null : filtered.length}
        loading={entriesQuery.isPending}
        empty={{
          // The drawn "only the creation" state's neighbour: a record with no
          // history at all should not look like an error, and the sentence
          // says which WINDOW was searched rather than claiming "never".
          title: t("metering.audit.emptyTitle"),
          helper: t("metering.audit.empty"),
          // ⚠ **NO CTA, AND ITS ABSENCE IS THE FIX (`DEF-MET-4764`).** This
          // block used to pass `ctaLabel: metering.audit.openViewer` with
          // `onCta: () => undefined`, and `DataTable` hands the whole table
          // region to `EmptyList`, which wires that handler to a LIVE
          // `<Button>`. So an empty history drew *Open the audit log for this
          // record →* **twice**: once as a button that did nothing, and once
          // below as the `fullLog` `ButtonLink` that works. Hard-won law 2's
          // mirror — and B14 rule 4's *"two + Add part buttons"* shape, which
          // `EmptyList`'s own `ctaVariant` docstring already records.
          //
          // The blueprint draws no empty-state control here either (`U9` §13),
          // and the working link BELOW the table is the one PO ruling 2026-09-10
          // kept — *"keep it as it is"*. One door, and it opens.
        }}
        filterBarSlot={<FilterBar filters={filters} state={state} onStateChange={setState} />}
      />
      {/* BR-AUD-010's second half, KEPT BY PO RULING 2026-09-10 ("keep it as it
          is"): the tab is a WINDOW, the wider history and BR-AUD-013's archive
          opt-in live in S61, and the window sentence is what stops a short
          history reading as *nothing ever happened*. */}
      <div className="flex items-center gap-3">
        {fullLog}
        <span className={`text-sm ${MUTED}`}>
          {t(
            entriesQuery.data?.window.window === "archive"
              ? "audit.window.archive"
              : "audit.window.hot",
          )}
        </span>
      </div>
    </section>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-001@947cf31 (story+rules snapshot hash — EP-MET-01 lead story)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-10 (US-SHL-020 conversion — the back link, kicker, title, roll-up, status pill and the BR-MET-045 strip are now the shared PageHeader's)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [US-SHL-020 conversion 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 593 passed / 141 todo across 46 files✔ (567 passed / 138 todo was the pre-conversion baseline) · vite build✔ · run_gates 12 PASS · 0 FAIL · 2 SKIP✔ (G14 prototype-conformance included) · trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ — 296+83 was the pre-W1 baseline and a CONCURRENT Plans & Rates lane is adding to the same suite; this packet contributes 103 passing + 28 todo across 7 files and reduced nothing. The 28 todos are browser-interaction, server/RLS-isolation and unbuilt-neighbour-lane scope, each named in its own test · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: [2026-08-22 PRM-02/PRM-03 conformance lane · DEF-578/579/584] E3 `↓ Export CSV` is NOT on the header: the shared ListExportButton posts a LIST request state and there is no per-premises export, so the button would export every premise the tenant owns under a label naming one — reported, not faked · E3 `+ New unit` keeps the shared label where r10's PRM-02 alone writes `+ Add unit`: r10 itself writes `New unit` three times and `Add unit` once, and fragmenting one action's vocabulary across four screens for one drawing's wording is the DEF-348 shape · E3 the Overview's Jurisdiction line is a STATED ABSENCE (DEF-507): `inside_city_limits` is stored for the outside-city surcharge and `premises_detail_dict` does not serve it · E3 the sub-line drops r10's `inside city limits` (DEF-507) and `created Mar 2024 from migration` (no created-at, no provenance on the payload) · E3 the Area/Sub-area split reads the leading segment of the server's `area_path` because the payload carries the parent's CODE and not its name — DEF-583, with the code as the fallback · E2 the Accounts tab is REMOVED and BR-MET-045 is amended for it, dated, with the PO's sentence quoted; the route it offered is unchanged (Units tab → unit detail → Account tab)
// exceptions: E2 US-SHL-020 — the back link's "←" belongs to PageHeader (TC-5), so the label passed here is `metering.premises.title`; the catalog's `metering.premises.detail.back` ("← Premises") would render a second arrow and is no longer read by this screen. The rendered link is byte-identical to what it was; the key is untouched · E2 the Overview panel is not one of BR-MET-045's four tabs, so with the strip now inside the header it reads BELOW the strip rather than above it — a placement change forced by the ruled skeleton, reported rather than resolved by inventing a fifth tab · E3 BR-MET-045 names the detail views as CONFIRMED but EP-MET-01 §Scope says the detail-view STORIES are "to be allocated in the next authoring pass" — this detail is built under US-MET-001 (whose §1 exit names the row→detail move) and the missing story allocation is reported, not invented · E3 the Accounts tab renders the honest arrives-with state: the customers module owns no tables in W1, and an empty table would assert "no accounts" · E3 the Audit tab LINKS to S61 filtered by entity rather than re-implementing an audit table (US-AUD-005 TC-3/TC-4 rules that a per-entity Audit tab equals S61 filtered to that entity)
// status: VERIFIED-UNRATIFIED (r10 conformance re-verified in Chromium 2026-08-22 — five tabs, r10's header, the two-column Overview and the entity's own audit rows, all photographed)
// ──────────────────────────────────────────────────────────
