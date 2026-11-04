// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-001 (S14 premises list + roll-up) · US-MET-002 (S15 units) ·
//           US-MET-003/US-MET-004 (S16 guided + bulk add) · US-MET-005 (S26/S27 ops views)
//           Screens: S14, S15, S16, S26, S27
// Rules:    BR-MET-034 (premises types are Reference data — never a hardcoded enum) ·
//           BR-MET-036 (occupancy is DERIVED from the active account — never settable) ·
//           BR-MET-037 (delete guards) · BR-MET-045 (the detail tab sets) ·
//           BR-MET-046 (a unit never leaves its premises) ·
//           BR-SHL-025 (RBAC from GET /me/permissions — the server is authoritative) ·
//           BR-SHL-034 (every displayed date goes through the shared formatter) ·
//           BR-SHL-020 (plain-language failure; the six A18 states exist once)
// ───────────────────────────────────────────────────────
// The pieces S14/S15/S16/S26/S27 share. They live here rather than in one of the
// screens so no screen has to import another (and so the routes below have ONE
// definition — a path typed twice is a dead link waiting to happen).
//
// Three laws are enforced by CONSTRUCTION in this file, not by discipline:
//
//   1. **Occupancy renders, it never edits** (BR-MET-036). `OccupancyCell` is a
//      pill — there is no occupancy input in this lane at all, and the API
//      refuses an `occupancy` field, so a future edit that adds one fails at
//      the server before it fails in review.
//
//   2. **A unit never moves premises** (BR-MET-046). Nothing here builds a
//      premises control for a unit edit; the premises shows as a LINK to its
//      own detail, which is a navigation, not an assignment.
//
//   3. **Permission cells come from the server** (BR-SHL-025). `useAccessCell`
//      reads the caller's own A4 row; a "—" hides, a "View" disables WITH the
//      reason, and every endpoint still enforces its own gate underneath.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getLookupEntries, getMyPermissions } from "@/api/endpoints";
import type { LookupEntry, MyPermissions } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { SelectField } from "@/components/FormModal";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { PageHeaderTab } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import { useTenantRegional } from "@/components/TenantRegional";
import type { TenantRegional } from "@/components/TenantRegional";
import type { StatusTone } from "@/components/StatusPill";
import type { Translator } from "@/features/tenancy/settingsShared";
// CR-023 §9.7 — the service letter squares have ONE owner. See `ServiceTags`.
import { ServiceTags as ServiceSquares } from "@/features/rating/ratingShared";

import "./metering.css";
import { Button,  type ButtonSize, type ButtonVariant } from "@/components/Button";

// ── Routes (the AppShell sidebar's own paths — SHELL_NAV `premises`) ───────
// BR-SHL-001 gives the section `/premises` with children `/premises` and
// `/premises/units`. Everything below hangs off those two so the breadcrumb and
// the active-nav highlight keep working (breadcrumbFor matches by prefix).
//
// Every constant and helper here is TENANT-RELATIVE (PO 2026-08-10 path
// tenancy): the screen that navigates puts it through `tenantPath()`, which is
// the ONE place a tenant segment is ever written.

export const PREMISES_ROUTE = "/premises";
export const UNITS_ROUTE = "/premises/units";
/** CR-023 PRM-04 — the THIRD tab of the one Premises page. */
export const PREMISES_IMPORTS_ROUTE = "/premises/imports";
export const PREMISES_ADD_ROUTE = "/premises/new"; // S16 — the guided add wizard
/**
 * The two live bulk paths the head's `↑ Import …` buttons open (US-MET-004).
 *
 * ⚠ **RE-POINTED 2026-08-21 (`DEF-520`) — THESE NOW OPEN THE FIVE-STAGE
 * RUNNER.** They used to carry `?mode=premises_csv|units_csv` into
 * `AddPremisesWizard`, the stateless v1 path (`POST /premises/imports` +
 * `/commit`: two steps, no run row, no receipt, no rollback — B15 §7A). The
 * comment that stood here said *"re-point both the day the runner lands"*, and
 * the runner landed: twelve components, four endpoints and 39 tests were on the
 * branch while these two constants still pointed at the old wizard, so the PO
 * deployed, clicked Import, and got it. **That is the whole of `DEF-520`** —
 * hard-won law 2, in two lines of routing.
 *
 * ONE runner, TWO routes, and the route is the only thing that carries the
 * target (`BR-MET-096`, PO 2026-08-21: *"same process for premises and Unit -
 * only at tranform stage we differntate field"*).
 */
export const PREMISES_IMPORT_ROUTE = "/premises/import";
export const UNITS_IMPORT_ROUTE = "/premises/units/import";
/**
 * ⚠ **RE-POINTED 2026-09-09 (CR-089 wave E, `E3`/`PUJ-23`).** This used to be
 * `${PREMISES_ADD_ROUTE}?mode=units_pattern` — the S16 four-way *"How many?"*
 * chooser — and pressing **+ New unit** on a building therefore FORGOT the
 * building: step 2's first required box was an empty *Premise* picker, so a
 * clerk standing on `P-00043` was asked to find it again out of seventy-nine
 * addresses. `AddUnitsWizard` starts by naming the building and takes the one
 * you came from on `?premises=`.
 *
 * `AddPremisesWizard`'s `units_pattern` mode is UNCHANGED and still reachable
 * from its own mode chooser; nothing was deleted from a wave-B file.
 */
export const UNITS_ADD_ROUTE = "/premises/units/new";

/** The same screen, carrying the building the clerk pressed from (`E3`). */
export function unitsAddPath(premisesId?: string): string {
  return premisesId === undefined || premisesId === ""
    ? UNITS_ADD_ROUTE
    : `${UNITS_ADD_ROUTE}?premises=${encodeURIComponent(premisesId)}`;
}
export const READS_ROUTES_ROUTE = "/reads/routes"; // S26
export const READS_CYCLES_ROUTE = "/reads/cycles"; // S27
export const DASHBOARD_ROUTE = "/dashboard";

export function premisesDetailPath(premisesId: string): string {
  return `${PREMISES_ROUTE}/${encodeURIComponent(premisesId)}`;
}

export function unitDetailPath(unitId: string): string {
  return `${UNITS_ROUTE}/${encodeURIComponent(unitId)}`;
}

/**
 * **A CYCLE'S OPERATIONAL DETAIL — Meter Reads blueprint entry 20**,
 * `/:tenant/reads/cycles/:cycleId`, opened by a row on entry 15's list.
 *
 * ⚠ **IT LIVES HERE, BESIDE ITS TWO SIBLINGS, BECAUSE TWO SCREENS BUILD IT.**
 * Entry 15 (`ReadCyclesTab`) builds the link and entry 20 mounts the route, and
 * a path helper declared inside either one is a helper the other has to copy —
 * which is hard-won law 5 in miniature, and is how a row comes to open nothing
 * after somebody moves a route. `premisesDetailPath` and `unitDetailPath` above
 * are here for exactly that reason.
 *
 * ⚠ **THE CYCLE'S DEFINITION IS STILL SETTINGS' AND KEEPS ITS OWN PATH.**
 * `routesCyclesShared.cycleDetailPath` points at
 * `/settings/reference-data/routes-cycles/cycles/{id}` and opens a different
 * screen answering a different question — BR-MET-011's split, narrowed by the
 * PO on 2026-09-14: the DEFINITION is configured there, the reading WORK is
 * done here. Neither is a stale copy of the other.
 */
export function readCycleDetailPath(cycleId: string): string {
  return `${READS_CYCLES_ROUTE}/${encodeURIComponent(cycleId)}`;
}

/**
 * The Audit tab (BR-MET-045 / BR-AST-019) is not a second audit implementation:
 * it is the S61 viewer filtered to this entity. The filter names are the ONE
 * `f.<name>` vocabulary `AUDIT_FILTERS` declares, so the link lands on a real,
 * shareable, already-built screen instead of an empty per-entity table.
 */
export function auditViewerPath(entityType: string, entityId: string): string {
  const params = new URLSearchParams();
  params.set("f.entity_type", entityType);
  params.set("f.entity_id", entityId);
  return `/audit-log?${params.toString()}`;
}

// ── The S14/S15 tab strip (US-SHL-020 · BR-SHL-044) ────────────────────────
// The prototype draws Premises and Units as ONE screen with two tabs (line 713);
// this app routes them separately, so the strip spans two routes and each page
// renders it with its own `activeTabId` and navigates on select. Declaring it
// once here is what keeps the two headers identical — a second copy would be
// the same defect US-SHL-020 exists to remove (DEF-021).

export interface PremisesStripTab {
  id: string;
  /** TENANT-RELATIVE (PO 2026-08-10) — the navigating screen adds the tenant. */
  path: string;
  labelKey: string;
  /**
   * The `h1` this tab puts on the shared head.
   *
   * ⚠ **THE HEADING FOLLOWS THE TAB FROM 2026-09-10, BY PO RULING, AND THAT
   * REVERSES A SIGNED RULE.** `CR-023` P0 / `B15` §3 signed *"`h1` reads
   * **Premises** on ALL THREE TABS — the Units tab included"*, read off r10
   * line 630, and the Units tab was retitled to match it. The Product Owner was
   * shown the drawn frame and the shipped screen side by side and ruled the
   * other way — verbatim: *"Should the units list say Units or Premises at the
   * top? The drawing says Units with its own subtitle. - t should say Unit"*.
   * **The old sentence is left standing above rather than deleted**: it was
   * signed, and the next reader needs to see that it was overturned rather than
   * missed. The spelling is the drawing's plural, because a list of many is
   * titled in the plural everywhere else in this product.
   */
  titleKey: string;
  /**
   * The one line between the title and the tab strip.
   *
   * `undefined` → the shared roll-up sentence goes there, which is what r10
   * draws on the Premises and Imports tabs. A key → that string instead, which
   * is what the Units frame draws, and the frame lists the roll-up among its
   * stated absences.
   */
  subtitleKey?: string;
  /**
   * BR-SHL-044 (b): the guidance belongs to the TAB, and sits below the strip.
   *
   * `null` → this tab draws NO explainer. The units frame's own cognitive-load
   * budget is *"Nine columns, one search, no prose"* and it lists prose of any
   * kind among its drawn absences, so its one sentence is the subtitle above
   * the strip and there is not a second one below it.
   */
  explainerKey: string | null;
}

export const PREMISES_TAB_PREMISES = "premises";
export const PREMISES_TAB_UNITS = "units";
export const PREMISES_TAB_IMPORTS = "imports";

export const PREMISES_TAB_STRIP: readonly PremisesStripTab[] = [
  {
    id: PREMISES_TAB_PREMISES,
    path: PREMISES_ROUTE,
    labelKey: "metering.premises.title",
    titleKey: "metering.premises.title",
    // DEF-MET-5835 — the 27-word explainer is GONE, and it is deleted rather
    // than shortened because it was RATIONALE (B14 rule 33: *why the product
    // works this way* is ZERO words on screen). It read *"A premise is a
    // physical property or address. Each premise may contain one or more units
    // (apartments, suites, sub-metered spaces) — those live in the Units tab."*
    // Every clause of it is either a definition a clerk does not need or a
    // pointer at the `Units` TAB that is drawn two lines above it, which is
    // rule 32's *a row never repeats what its own control offers*.
    //
    // PO, 2026-09-19: *"On premsies list page reduce this text - A premise is a
    // physical property or address..."*. Three authorities agree on zero rather
    // than fewer: the blueprint's own stated absence for this screen is *"No
    // prose on the screen at all — a list explains itself or it is the wrong
    // list."* (`CR-089-p005-property-list.md` §Cognitive-load budget), rule 33
    // puts rationale at zero, and the Units tab below already draws `null` for
    // exactly this reason.
    explainerKey: null,
    // ── `DEF-MET-5855` · THE DRAWN SUBTITLE, WHERE THE ROLL-UP WAS ──────────
    // ⚠ **THE BLUEPRINT DRAWS A SUBTITLE HERE AND NO ROLL-UP, AND IT SAYS SO
    // TWICE.** `CR-089-p005-property-list.md` §Header: *"No roll-up sentence is
    // drawn. The line under the title is the subtitle above and nothing else."*
    // §Tiles: *"None. The screen draws no stat tiles and no KPI strip."* The
    // string below is page 6's own, read AS AN IMAGE (B14 rule 42), and B14
    // rule 41 makes the drawing the specification.
    //
    // ⚠ **WHAT THE FOUR COUNTS COST, MEASURED RATHER THAN ASSUMED, BECAUSE
    // REMOVING THEM TAKES SOMETHING A CLERK HAS TODAY.** The head read
    // `79 premises · 130 + 1 common units · 62 vacant · 4 pending activation`,
    // and the drawing's own home for a count is the chip and the footer —
    // *"the chip reads `Not placed ×` and the count in the footer is the size
    // of the job"*. **Walked in a browser on 2026-09-19, every figure was
    // already there and the numbers are IDENTICAL, not merely close:** the
    // Premises footer reads `79`; `Status = Pending` narrows it to `4`; the
    // Units tab's footer reads `131`; `Occupancy = Vacant` narrows it to `62`.
    //
    // ⚠ **ONE FIGURE HAS NO CHIP AND IS NAMED RATHER THAN GLOSSED: the
    // `+ 1 common` SPLIT.** The units list offers Occupancy, Plan, Premise and
    // Service and no common-area filter, so that one number is reachable only
    // on the Imports tab, where the roll-up still draws because no blueprint
    // plate covers that tab. Filed as `OQ-MET-12484` rather than half-built
    // here; only the screen the blueprint draws moves.
    subtitleKey: "metering.premises.listSubtitle",
  },
  {
    id: PREMISES_TAB_UNITS,
    path: UNITS_ROUTE,
    labelKey: "metering.units.title",
    // The tab word and the heading word are the same word, so they are the same
    // key: two spellings of `Units` on one screen is how one of them drifts.
    titleKey: "metering.units.title",
    subtitleKey: "metering.units.listSubtitle",
    explainerKey: null,
  },
  // CR-023 · r10 draws THREE tabs on this page and the third did not exist here
  // at all. Its own route keeps `/premises/units` resolving unchanged, which is
  // the property TC-24 asserts (857 lines of screen and live deep links).
  {
    id: PREMISES_TAB_IMPORTS,
    path: PREMISES_IMPORTS_ROUTE,
    labelKey: "metering.imports.title",
    titleKey: "metering.premises.title",
    explainerKey: "metering.premises.explainer.imports",
  },
];

/**
 * CR-023 §3 — the head's SECONDARY actions, which change with the tab, and the
 * ONE oddity r10 has that a lane must not tidy away.
 *
 * r10's own markup (`SMARTBillHub.dc.html` line 631-637) renders, in the page
 * head: `↑ Import units` on the Units tab, `↑ Import premises` on **both** the
 * Premises tab and the Imports tab. The Imports tab then draws BOTH import
 * buttons AGAIN in its own toolbar with the emphasis the other way round —
 * `↑ Import units` secondary, `↑ Import premises` PRIMARY. B15 §9.8: *"Do not
 * 'fix' r10's duplicated import buttons."* So they are duplicated here too, and
 * this comment is why, so the next reader does not delete one as a mistake.
 */
export function premisesHeadSecondary(args: {
  t: Translator;
  activeTabId: string;
  writeBlockedReason: string | null;
  onImportPremises: () => void;
  onImportUnits: () => void;
}): ReactNode {
  if (args.activeTabId === PREMISES_TAB_UNITS) {
    return (
      <GuardedButton
        label={args.t("metering.units.action.import")}
        reason={args.writeBlockedReason}
        onClick={args.onImportUnits}
      />
    );
  }
  return (
    // ⚠ **`↑ Import`, NOT `↑ Import premises` — the blueprint's own head, and
    // a DIFFERENT KEY rather than a shortened one.** On the Imports tab the two
    // buttons sit side by side (`↑ Import units` beside this one), so the long
    // form is what tells them apart there and `metering.premises.action.import`
    // keeps its words for that screen. Here the tab strip already says which
    // list you are on, so the qualifier is a word the head repeats.
    <GuardedButton
      label={args.t("metering.premises.action.importShort")}
      reason={args.writeBlockedReason}
      onClick={args.onImportPremises}
    />
  );
}

/**
 * The page head's roll-up sentence — r10's own line, verbatim in shape:
 * `428 premises · 1,247 units · 34 vacant · 12 pending activation`.
 *
 * ⚠ **IT REPLACES THE KPI STRIP THAT USED TO CARRY THESE FOUR NUMBERS**, and
 * that was reported as a delta by the US-SHL-020 conversion in 2026-08-10's own
 * trailer: *"the prototype's roll-up line is the counts sentence; this app
 * serves those counts as the KPIStrip … placement delta reported, not changed"*.
 * CR-023 is the ask that changes it, so the note is now closed rather than
 * repeated. The counts are the SERVER's (`GET /premises` → `rollup`); nothing
 * here adds up rows.
 *
 * A count the server has not sent yet renders as an em-dash inside the same
 * sentence rather than as a zero — "0 vacant" and "not counted yet" are
 * different claims, and one of them is a promise.
 */
export function premisesRollupLine(
  t: Translator,
  rollup:
    | { premises: number; units: number; common?: number; vacant: number; pending_activation: number }
    | undefined,
): ReactNode {
  const n = (value: number | undefined): string => (value === undefined ? CELL_NONE : String(value));
  // BR-MET-101: when the tenant has common areas the units figure is the
  // SPLIT — "N + M common" — because a common area counted silently among the
  // units would be indistinguishable from a place somebody lives. N is
  // total − M, a subtraction of two SERVER numbers (`units` stays the total so
  // no existing reader moves). `common` is optional so a cached pre-flag
  // payload still renders the plain line rather than crashing the header.
  const common = rollup?.common ?? 0;
  return (
    <span className="tabular-nums">
      {common > 0
        ? t("metering.premises.rollupLineCommon", {
            premises: n(rollup?.premises),
            units: n(rollup === undefined ? undefined : rollup.units - common),
            common: String(common),
            vacant: n(rollup?.vacant),
            pending: n(rollup?.pending_activation),
          })
        : t("metering.premises.rollupLine", {
            premises: n(rollup?.premises),
            units: n(rollup?.units),
            vacant: n(rollup?.vacant),
            pending: n(rollup?.pending_activation),
          })}
    </span>
  );
}

/*
 * ⛔ **`SegmentedFilter` WAS DELETED HERE ON 2026-08-27 (DEF-1700), AND THIS
 *    NOTE IS THE STAMPED r10 DIVERGENCE B14 REQUIRES.**
 *
 * It drew r10's toolbar segment (`.seg` / `.seg-opt`) as a list filter, and
 * three screens rendered four of them: Premises (six premises types), Units
 * (All · Occupied · Vacant · Sub-metered) and Reads (routes, statuses). Every
 * one of those dimensions was ALSO declared in the same screen's
 * `TableConfig.filters`, from the same option source, writing the same
 * `f.<name>` URL param — so each chip row was a second control over a fact the
 * `+ Filter` panel beside it already offered.
 *
 * The Product Owner ruled against the second row on 2026-08-27: *"as per our
 * stadard first raw of tookkit is more than suficient"*. **r10 draws these
 * segments and B14 wins over r10** (CLAUDE.md's reference rule), so the
 * divergence is recorded rather than followed — here, in
 * `05-prototype/r10-2026-08-16/UI-RULES.md`, and in the decision log.
 *
 * `.seg` / `.seg-opt` are NOT orphaned: `SegmentedField` (`components/FormModal`)
 * is the FORM control of the same family and still declares them, so G31's
 * ceiling is untouched.
 */

/**
 * BR-SHL-044 (a): the primary action is per-TAB, and the SAME slot renders
 * "+ New premise" then "+ New unit" as the user moves across. Both actions are
 * declared on BOTH routes on purpose — the law is then true by construction
 * rather than because each page remembered to configure its own half.
 *
 * Both are plain navigations into the S16 wizard, so config is the right route
 * here; the render-prop route (Plans & Rates) exists for tabs whose action
 * state lives in the tab BODY, and nothing on S14/S15 does.
 */
export function premisesStripTabs(args: {
  t: Translator;
  /** BR-SHL-025: null = allowed; a string renders the control disabled WITH it. */
  writeBlockedReason: string | null;
  onNewPremise: () => void;
  onNewUnit: () => void;
}): PageHeaderTab[] {
  const actionFor: Record<string, { labelKey: string; onClick: () => void }> = {
    [PREMISES_TAB_PREMISES]: {
      labelKey: "metering.premises.action.new",
      onClick: args.onNewPremise,
    },
    [PREMISES_TAB_UNITS]: { labelKey: "metering.units.action.new", onClick: args.onNewUnit },
    // ⚠ THE IMPORTS TAB HAS NO PRIMARY, AND THAT IS r10's OWN DRAWING, NOT AN
    // OMISSION: `prem_showPremises` is false there, so its head carries the
    // secondary `↑ Import premises` ALONE. BR-SHL-044 (c) already allows an
    // empty primary slot without the layout shifting, which is exactly the case
    // this is. The Imports toolbar carries both import buttons instead (§3).
  };
  return PREMISES_TAB_STRIP.map((tab) => {
    const action = actionFor[tab.id];
    return {
      id: tab.id,
      label: args.t(tab.labelKey),
      explainer: tab.explainerKey === null ? undefined : args.t(tab.explainerKey),
      primaryAction:
        action === undefined ? undefined : (
          <GuardedButton
            label={args.t(action.labelKey)}
            reason={args.writeBlockedReason}
            variant="primary"
            onClick={action.onClick}
          />
        ),
    };
  });
}

// ── RBAC (BR-SHL-025) ──────────────────────────────────────────────────────

// The A4 row that governs BOTH premises/units and — for want of its own row —
// the assets registry. A4 has NO assets permission (the grid predates the
// module), so this lane gates on the closest ratified row and lets the SERVER
// refuse the System-Admin-only actions (BR-AST-032 retire/delete). Reported.
export const PREMISES_PERMISSION = "premises_accounts";

export const CELL_NONE = "—";
export const CELL_VIEW = "View";
export const CELL_FULL = "Full";

/** The caller's OWN A4 cell for `code`; null while the read has not answered. */
export function accessCell(
  permissions: MyPermissions | null | undefined,
  code: string,
): string | null {
  // ⊕ `DEF-MET-9238` — an answer with no rows is an answer nobody can read,
  // which is the null case below (offer the control; the 403 is the boundary),
  // never a crash of the whole page.
  if (permissions === null || permissions === undefined || !Array.isArray(permissions.permissions)) {
    return null;
  }
  return permissions.permissions.find((row) => row.code === code)?.access ?? CELL_NONE;
}

/**
 * BR-SHL-025: UI-gating convenience ONLY. A null cell (the read has not landed,
 * or failed) hides nothing — each endpoint's own 403 is then the boundary, and
 * that is the honest default: never guess a role, never grant one.
 */
export function useAccessCell(code: string, client: ApiClient = api): string | null {
  const query = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  return accessCell(query.data, code);
}

/**
 * The caller's own role CODE, or null while `/me/permissions` has not answered.
 *
 * Added 2026-08-16 with the US-MET-013 dispute surface, and it exists because
 * the A4 matrix cannot answer the question the OQ-043 closure asks. That
 * closure gives ONE act — clearing a dispute — to the **System Admin** alone,
 * and A4's nine rows grade a SURFACE (Premises/Accounts, Reads & Billing, …),
 * not a single action inside one. Gating the Clear control on the Reads cell
 * would offer it to every Billing Clerk, who would then meet a 403.
 *
 * BR-SHL-025 still holds both ways: this decides only whether the control is
 * offered or drawn disabled with its reason, and a null answer offers it — the
 * server's own @require_role(SYSTEM_ADMIN) is the boundary either way.
 */
export const ROLE_SYSTEM_ADMIN = "system_admin";

/**
 * The second role OQ-042's closure names, added by CR-038 W7.
 *
 * Verbatim from the closure: *"supervisor = SysAdmin/Executive"*. It is a
 * CONSTANT beside `ROLE_SYSTEM_ADMIN` above and not a literal at the call site
 * for the reason that comment already gives: this is the only place in the
 * frontend that had ever needed to name a role by hand, and two files each
 * spelling `"executive"` is how a role rename becomes a silent permission
 * change. The same BR-SHL-025 caveat applies unchanged — the server's
 * `@require_role(SYSTEM_ADMIN, EXECUTIVE)` is the boundary either way.
 */
export const ROLE_EXECUTIVE = "executive";

/**
 * The third role a screen has had to name by hand, added by `CR-141-BRC07`.
 *
 * *Correct check number* on a refund is Admin or Billing Clerk — who writes
 * the check corrects its number (`BR-PAY-1071` as amended 2026-09-03). A
 * CONSTANT here beside the other two, for their reason: a role spelled as a
 * literal in two files is how a rename becomes a silent permission change. The
 * same BR-SHL-025 caveat applies — the server's `@require_role(SYSTEM_ADMIN,
 * BILLING_CLERK)` is the boundary either way.
 */
export const ROLE_BILLING_CLERK = "billing_clerk";

/**
 * The fourth, added by `DEF-IDN-10365` (`CR-187-BRC10`): Settings › Users offers
 * *New app code* only on a field technician's row, because only that role
 * claims the native app with one. A CONSTANT here for the reason above.
 */
export const ROLE_FIELD_TECHNICIAN = "field_technician";

export function useTenantRole(client: ApiClient = api): string | null {
  const query = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  return query.data?.role ?? null;
}

/** True when the server says this role may only look. */
export function isReadOnly(cell: string | null): boolean {
  return cell === CELL_VIEW;
}

/** True when the server marks the whole surface "—" (A18 §6, BR-SHL-003). */
export function isDenied(cell: string | null): boolean {
  return cell === CELL_NONE;
}

// ── Regional formatting (IS-8 · BR-SHL-023 · BR-SHL-034) ───────────────────
//
// ⚠ THIS BLOCK WAS THE DEFECT (DEF-SHL-3964, 2026-09-05). It read:
//
//     timeZone: props.timeZone ?? SEED_TIME_ZONE,      // "UTC"
//     dateFormat: props.dateFormat ?? SEED_DATE_FORMAT // "MM/DD/YYYY"
//
// …and the comment above it said the real values "arrive with US-SHL-013's
// formatting service". They never arrived. `RegionalProps` is OPTIONAL, the
// root that renders every one of these screens set neither field, and so all
// 83 date-rendering screens took the seed. The PO changed the format and the
// zone on Settings → Regional, watched the preview on that page change (it
// reads its own draft), and watched nothing else in the product change at all.
//
// THE FALLBACK IS WHY IT SURVIVED FOR THE LIFE OF THE PRODUCT: there was no
// crash, no blank cell and no raw key — just a plausible date in the wrong
// format and a timestamp five or six hours out. Every test passed because
// every test that renders a date passes the format it then asserts.
//
// So the resolution is now props → CONTEXT, and there is no third step. The
// seed constants below are still exported — the seeder and tests that want to
// name a format on purpose use them — but no rendering path can reach them by
// writing `??` any more (hard-won law 3: the unsafe option must be the one you
// type).

export interface RegionalProps {
  timeZone?: string;
  dateFormat?: RegionalDateFormat;
}

/** What `provision_tenant` writes for a tenant with no state to derive from.
 *  NOT a display fallback — see the block comment above. */
export const SEED_TIME_ZONE = "UTC";
/** The first entry of the server's `DATE_FORMATS`, i.e. what a new US tenant is
 *  seeded with. NOT a display fallback — see the block comment above. */
export const SEED_DATE_FORMAT: RegionalDateFormat = "MM/DD/YYYY";

/** The message a screen fails with when nobody has said what tenant it is. */
export const REGIONAL_UNPUBLISHED =
  "The tenant's regional settings are not published. A screen is being rendered " +
  "outside <TenantRegionalProvider> (ShellWithSession publishes it for the whole " +
  "app) and no timeZone/dateFormat prop was supplied either. DEF-SHL-3964.";

/**
 * The tenant's time zone and date format for this screen.
 *
 * ⚠ THIS IS A HOOK. It reads a React context, so it obeys the rules of hooks:
 * call it unconditionally, at the top of a component, never inside `&&` in JSX
 * and never after an early `return`. It is named `useRegional` rather than the
 * old `regionalOf` precisely so that `react-hooks/rules-of-hooks` — which is
 * `error` in this project's eslint config — polices all 82 call sites for you.
 * Six of them were already in an illegal position when this landed and were
 * hoisted in the same commit.
 *
 * Resolution order, and there are only two steps:
 *   1. an explicitly supplied prop — a screen that genuinely has its own value
 *      (an import preview showing a file's own dates, say) still wins;
 *   2. what `ShellWithSession` published from `GET /shell/display`.
 *      (It read `GET /settings/regional` until 2026-09-06. That endpoint is
 *      Admin/Executive, so a Billing Clerk got 403 and the shell refused to
 *      draw ANY screen for sixteen days — `DEF-SHL-4272`. Nothing in this
 *      file changed; the route under it did.)
 *
 * There is deliberately no step 3. `ShellWithSession` renders no routed screen
 * until step 2 can answer, so in the product this cannot throw; outside the
 * shell it means a test has not said which tenant it is testing.
 */
export function useRegional(props: RegionalProps): {
  timeZone: string;
  dateFormat: RegionalDateFormat;
} {
  return resolveRegional(props, useTenantRegional(), import.meta.env.MODE);
}

/**
 * `useRegional` without the hook, so the PRODUCTION branch can be asserted.
 *
 * ⚠ **THE `mode` ARGUMENT IS THE HONEST PART OF THIS AND IS WORTH READING.**
 * Under `vite build` the seed pair below is not merely unused — Vite replaces
 * `import.meta.env.MODE` with the literal `"production"`, the comparison is
 * statically false, and the whole branch is stripped from the bundle. So in
 * the shipped product there is NO fallback: a screen rendered outside
 * `<TenantRegionalProvider>` with no explicit prop fails loudly instead of
 * drawing a plausible wrong date, which is what hard-won law 3 asks for.
 *
 * ⚠ **AND UNDER TEST IT DOES FALL BACK, WHICH IS A REAL WEAKNESS, STATED.**
 * 86 test files render a date-bearing screen without saying which tenant they
 * are testing; they inherited the old seed default and every one of them was
 * green while the product was broken. Making them all declare a tenant is the
 * right end state and it is an 86-file sweep of shared files, so it is filed
 * as its own defect rather than smuggled into this one. What closes the gap
 * MEANWHILE is `components/regionalReachesTheScreen.dom.test.tsx`, which mounts
 * the real routes through the real shell and reads the rendered date against a
 * tenant setting — the check that could have caught DEF-SHL-3964 and the only
 * one in the repo that can.
 *
 * Passing `mode` explicitly (rather than reading `import.meta.env` in here) is
 * what lets that file assert `resolveRegional({}, null, "production")` THROWS.
 * A branch nobody can execute in a test is a branch nobody has checked.
 */
export function resolveRegional(
  props: RegionalProps,
  published: TenantRegional | null,
  mode: string,
): { timeZone: string; dateFormat: RegionalDateFormat } {
  const timeZone = props.timeZone ?? published?.timeZone;
  const dateFormat = props.dateFormat ?? published?.dateFormat;
  if (timeZone !== undefined && dateFormat !== undefined) {
    return { timeZone, dateFormat };
  }
  if (mode === "test") {
    // PER FIELD, not both. A first draft returned the seed PAIR here and threw
    // away a `timeZone` a caller had genuinely supplied — `SettingsUsersTab`'s
    // own test passes the zone and not the format, and it went red on
    // `08/09/2026 14:02` where it had always read `09:02`. Whatever the caller
    // said still wins; only the gap is filled.
    return { timeZone: timeZone ?? SEED_TIME_ZONE, dateFormat: dateFormat ?? SEED_DATE_FORMAT };
  }
  throw new Error(REGIONAL_UNPUBLISHED);
}

// ── Status vocabularies (labels from the catalog, tones from A12) ──────────

/** US-MET-001 §5: draft | pending | active | inactive — the server's own set. */
export function premisesStatusTone(status: string): StatusTone {
  if (status === "active") {
    return "success";
  }
  if (status === "pending" || status === "draft") {
    return "warning";
  }
  return "neutral";
}

/**
 * US-MET-002 §5: the unit's status is DISPLAY ONLY — computed from the account
 * status plus derived occupancy. There is no stored unit-status column, so
 * there is nothing here for a control to write to.
 */
export function unitStatusTone(status: string): StatusTone {
  if (status === "active") {
    return "success";
  }
  if (status === "pending") {
    return "warning";
  }
  if (status === "inactive" || status === UNIT_STATUS_MARKED_DISCONNECT) {
    return "danger";
  }
  return "neutral"; // vacant, and any account status this lane does not know
}

/**
 * r10's FOURTH unit status — and it is REAL, which was checked before it was
 * drawn (B15 §3.2's warning: *"Check what the product derives before assuming
 * it exists"*).
 *
 * `apps/metering/selectors._unit_status` returns the ACCOUNT's status code
 * verbatim, and `marked_disconnect` is one of BR-CUS-055's five seeded statuses
 * (`apps/customers/services.py`: `("marked_disconnect", "Marked disconnect",
 * CLASS_BILLABLE)` — billable, because the customer is still consuming until
 * the cut). So a unit whose account is marked for disconnect has ALWAYS
 * derived this status; it had no label and no tone, so it rendered the raw
 * string `marked_disconnect` in a neutral pill.
 *
 * ⛔ **THE GENERAL CASE IS STILL BROKEN AND IS FILED — DEF-508.** The status
 * lookup is tenant Reference data and RENAMEABLE (US-CUS-020 TC-3 adds "Legal
 * hold"), and the units payload serves the CODE with no `status_name` beside
 * it, so a tenant that renames a status still sees its code. The label added
 * here is the PLATFORM SEED's own name, quoted, not a name this lane invented —
 * and the real fix is the server serving `status_name`, which is another
 * module's file.
 */
export const UNIT_STATUS_MARKED_DISCONNECT = "marked_disconnect";

/**
 * BR-MET-036 made visible: occupancy is a DERIVED pill. This component takes no
 * `onChange`, and no caller can give it one — that is the rule's teeth on the
 * screen side (the API's refusal of an `occupancy` field is the other half).
 */
export function OccupancyCell(props: { occupancy: string }) {
  const { t } = useTranslation();
  const known = props.occupancy === "occupied" || props.occupancy === "vacant";
  return (
    <StatusPill tone={props.occupancy === "occupied" ? "success" : "neutral"}>
      {known ? t(`metering.occupancy.${props.occupancy}`) : props.occupancy}
    </StatusPill>
  );
}

/**
 * BR-MET-003: the service tags a premises/unit carries. Codes render through
 * the catalog when known and VERBATIM when not — a tenant-enabled service this
 * catalog has not met is still real data, and hiding it would lose it.
 */
export function ServiceTags(props: { services: readonly string[] | null; t: Translator }) {
  // ⚠ **THREE STATES, NOT TWO (DEF-762 / CR-036 (h)).** `null` is what the
  // server sends for a premises **nobody has been asked about**; `[]` is a
  // clerk's answer that this address **offers nothing**. Both used to arrive
  // here as `[]` and both printed "No services", so a clerk could not tell which
  // addresses still needed attention — the exact distinction the no-backfill
  // rule exists to protect, lost at the last inch.
  //
  // Units pass a plain array (`unit.services` is not nullable), so they take the
  // second branch and nothing about them changes.
  if (props.services === null) {
    return (
      <span className="met-muted">
        {props.t("metering.services.notRecorded", { defaultValue: "Not recorded" })}
      </span>
    );
  }
  if (props.services.length === 0) {
    return <span className="met-muted">{props.t("metering.services.none")}</span>;
  }
  // ⚠ ONE BADGE COMPONENT FOR THE WHOLE PRODUCT (CR-023 §9.7, DEF-439).
  // This used to draw `.met-tag met-tag-<service>` — a full-name chip, the
  // exact shape the PO photographed on Plans and called a defect: three
  // services wrapped onto two lines where r10 draws three coloured letter
  // squares. `features/rating/ratingShared` already owns those squares, with
  // the ten-service letter map, the token colours and the accessible name; a
  // second implementation here would be a second vocabulary, which is what
  // DEF-348 cost us for icons. The ten `.met-tag-<service>` colour rules this
  // left behind are DELETED from metering.css rather than left as dead CSS
  // (DEF-460's shape) — and `.met-tag` itself followed on 2026-08-26 (CR-038
  // W5): its last renderer, the S29 detail, draws its tag row as utilities.
  //
  // `t` is unused now and stays in the signature on purpose: every caller
  // passes it, the rating component owns its own `useTranslation`, and
  // rewriting six call sites to drop one prop is churn with no reader.
  return <ServiceSquares services={props.services} />;
}

/**
 * US-MET-002 TC-1: the meters cell, each number with its (sub)/(master)
 * qualifier. The qualifier is the SERVER's (it knows the parent links); this
 * only renders it.
 */
/**
 * `S15` col 5 — **HOW MANY METERS**, which is what the units list's frame
 * draws in this column.
 *
 * ⚠ **A COUNT AND NOT THE NUMBERS, AND THE TWO ARE BOTH RIGHT ON DIFFERENT
 * SCREENS.** `MetersCell` below prints `M-4021, M-4022 (sub)` and stays exactly
 * as it is: the property's own Units tab and the common-areas tab draw it, and
 * on a list of one building's units the asset numbers are what a clerk is
 * holding. On the estate-wide units list they are 1,109 rows of serial numbers
 * nobody scans, and the frame asks the question the column is actually for:
 * *does this unit have meters on it, and how many*.
 *
 * `none` in the absence style rather than `0`, for the reason `DEF-075` records
 * once already: a nought reads as a measured quantity and this is an absence.
 */
/**
 * `S16` Add units · Details §4 row 6 — the shared spaces the frame's
 * *"Or add a common area instead"* picker offers.
 *
 * ⚠ **ONE LIST, DECLARED ONCE, AND THAT IS THE WHOLE REASON IT IS HERE.** The
 * eleven-service list is typed out by hand in two places in this product, so an
 * eleventh service does not appear on screen on its own AND IT FAILS SILENTLY.
 * The picker, any test that asserts what it offers, and anything that later
 * wants the same list read this constant rather than repeating the six names.
 *
 * The names are the blueprint's own (page 55) and the CODES are ours: the
 * server stores the chosen name as the unit's LABEL, so nothing here is an enum
 * the database knows about. That is why this is a suggestion list and not a
 * lookup — a clerk with a shared space nobody drew can still type its name in
 * the naming fold.
 */
export const COMMON_AREA_KINDS = [
  "laundry",
  "corridor",
  "car_park",
  "pool",
  "lift",
  "landscape_irrigation",
] as const;

export function MeterCountCell(props: {
  meters: readonly { id: string | null; asset_no: string | null; qualifier: string | null }[];
  t: Translator;
}) {
  if (props.meters.length === 0) {
    return <span className="met-muted">{props.t("metering.meters.none")}</span>;
  }
  // Tabular numerals so a column of counts lines up, the same way the numbers
  // themselves do in `MetersCell`.
  return <span className="tabular-nums">{props.meters.length}</span>;
}

export function MetersCell(props: {
  meters: readonly { id: string | null; asset_no: string | null; qualifier: string | null }[];
  t: Translator;
}) {
  if (props.meters.length === 0) {
    return <span className="met-muted">{props.t("metering.meters.none")}</span>;
  }
  return (
    // CR-023 §3.2 col 6 and §9.6: r10 draws the Meters cell in SMALLER type with
    // tabular numerals (`font-feature-settings:tnum`) so `M-4021, M-4022` and
    // `M-4204 (sub)` line up down the column. Tailwind utilities — rule 21, and
    // `.met-meters` keeps the spacing it already had.
    <span className="met-meters text-sm tabular-nums">
      {props.meters.map((meter, index) => (
        <span key={meter.id ?? `${meter.asset_no}-${index}`}>
          {index > 0 && ", "}
          {meter.asset_no}
          {meter.qualifier !== null && (
            <span className="met-qualifier">
              {" "}
              {props.t(`metering.meters.qualifier.${meter.qualifier}`, {
                defaultValue: meter.qualifier,
              })}
            </span>
          )}
        </span>
      ))}
    </span>
  );
}

// ── Page furniture ─────────────────────────────────────────────────────────

export interface DetailTab {
  id: string;
  label: string;
}

/**
 * BR-MET-045's tab sets, rendered as URL state (`?tab=`) so every tab of every
 * detail view is linkable — the same posture the S8 frame takes. An unknown tab
 * falls back to the first rather than erroring (BR-SHL-011's spirit).
 */
export function detailTabFrom(raw: string | null, tabs: readonly DetailTab[]): string {
  if (raw !== null && tabs.some((tab) => tab.id === raw)) {
    return raw;
  }
  return tabs[0].id;
}

// `DetailTabs` used to live here and drew its own strip. US-SHL-020 deleted it:
// both detail views now hand this same `DetailTab[]` straight to the shared
// `PageHeader` (a `{id,label}` IS a `PageHeaderTab`), so the tab strip on a
// detail screen and the tab strip on a list screen can no longer drift apart.

/** A named key/value block — the Overview panels of every detail view. */
export function FactList(props: { children: ReactNode }) {
  return <dl className="met-facts">{props.children}</dl>;
}

export function Fact(props: { label: string; children: ReactNode }) {
  return (
    <>
      <dt>{props.label}</dt>
      <dd>{props.children}</dd>
    </>
  );
}

/** A value the server did not send. Visibly quieter than data, never blank. */
export function Dash(props: { children?: ReactNode }) {
  return <span className="met-muted">{props.children ?? "—"}</span>;
}

/**
 * BR-SHL-025: a control this role may not use renders DISABLED WITH ITS REASON
 * — never silently missing, so nobody hunts for a button that was hidden.
 */
export function GuardedButton(props: {
  label: string;
  reason: string | null; // null = allowed
  working?: boolean;
  danger?: boolean;
  /**
   * The button VARIANT from the shared kit. Defaults to the secondary every row
   * action uses; the page header's ONE primary slot passes `variant="primary"`
   * (US-SHL-020), so a guarded control keeps its disabled-with-reason behaviour
   * wherever it renders instead of the header growing an unguarded button.
   *
   * ⚠ CR-018 Phase 3 CHANGED THIS PROP FROM `className` TO `variant`, and that
   * is the migration, not a tidy-up. a raw class string handed this
   * component a CLASS STRING to concatenate — a string it could not check, from
   * a caller that could have typed `btn-primry` and had every gate pass. The
   * prop is now a union of five names and a wrong one does not compile.
   */
  variant?: ButtonVariant;
  /**
   * The SIZE tier. Row actions inside `.ast-row-actions` / `.met-row-actions`
   * pass `"row"`, because those two stylesheets used to impose that padding
   * from the PARENT and Route B has no parent selector. See `buttonKit.ts` for
   * why there are four tiers and B14 says two.
   */
  size?: ButtonSize;
  onClick: () => void;
}) {
  // DEF-344 (fixed 2026-08-22, W15 — the visual pass CR-018 §6 deferred to):
  // `danger` now speaks the kit's own vocabulary. `.met-danger`'s REST pixels
  // (text danger-700, border danger-500) were byte-identical to the kit's
  // `danger` variant; the only divergence was hover, where the local copy
  // stayed flat and B14 rule 6 says the commit tier FILLS — so the swap
  // changes nothing at rest and adopts the ratified hover. The stylesheet
  // rule is deleted in this same commit.
  const variant = props.variant ?? (props.danger === true ? "danger" : "secondary");
  const size = props.size ?? "default";
  if (props.reason !== null) {
    return (
      <Button variant={variant} size={size} disabled title={props.reason}>
        {props.label}
      </Button>
    );
  }
  return (
    <Button
      variant={variant}
      size={size}
      disabled={props.working === true}
      onClick={props.onClick}
    >
      {props.label}
    </Button>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// AREA + SUB-AREA — the two controls the PO asked for, 2026-08-17:
// *"when we add premises you should allow to select areas and sub areas on
// premises"*.
//
// It lives HERE and not on either screen because there are two screens — the
// S16 guided add and the S14 edit modal — and a picker written twice is a
// picker that disagrees with itself the first time a rule changes. Both call
// this; neither owns it.
//
// ⚠ TWO CONTROLS, **ONE** STORED COLUMN. `premises.area_id` holds a single
// reference, and BR-MET-066b makes a sub-area a row whose parent is an area —
// so a premises tagged to a sub-area is by construction inside its parent, and
// `areaPayloadCode` below is the whole of the mapping: the sub-area if one is
// chosen, otherwise the area. Nothing else in the client may compute it.
// ══════════════════════════════════════════════════════════════════════════

/** The pair of codes the two dropdowns hold. `sub` is "" when none is chosen. */
export interface AreaSelection {
  top: string;
  sub: string;
}

export const NO_AREA: AreaSelection = { top: "", sub: "" };

/** THE mapping from two controls to the one column. */
export function areaPayloadCode(selection: AreaSelection): string {
  return selection.sub !== "" ? selection.sub : selection.top;
}

/**
 * Re-open the pair from what the server stored (BR-MET-071).
 *
 * The server sends `area_code` AND `area_parent_code` precisely so this does not
 * have to guess: a bare code cannot tell the client which of the two boxes it
 * belongs in, and a client that guessed would put every sub-area in the Area box
 * and quietly re-tag the premises to its parent on the next save.
 */
export function areaSelectionFrom(row: {
  area_code?: string | null;
  area_parent_code?: string | null;
}): AreaSelection {
  const code = row.area_code ?? "";
  const parent = row.area_parent_code ?? "";
  if (code === "") {
    return NO_AREA;
  }
  return parent === "" ? { top: code, sub: "" } : { top: parent, sub: code };
}

export const areaLookupQueryKey = ["lookups", "areas", "premises-picker"] as const;

/** Only ACTIVE rows are offerable — BR-TEN-034 deactivates rather than deletes,
 *  and a retired district must stop appearing on new work while the premises
 *  already tagged to it keep their tag. */
export function topLevelAreas(entries: readonly LookupEntry[]): LookupEntry[] {
  return entries.filter((entry) => entry.active && entry.is_sub_area !== true);
}

export function subAreasOf(entries: readonly LookupEntry[], parentCode: string): LookupEntry[] {
  if (parentCode === "") {
    return [];
  }
  return entries.filter(
    (entry) =>
      entry.active &&
      entry.is_sub_area === true &&
      String(entry.parent_code ?? "").toLowerCase() === parentCode.toLowerCase(),
  );
}

/**
 * BR-MET-138 / BR-MET-066c — the S14 **Area** filter's options, as a TREE that
 * a flat option list can still tell the truth about.
 *
 * ⚠ **A PICKER THAT FLATTENS A TREE SILENTLY IS HOW SOMEBODY FILTERS THE WRONG
 * DISTRICT.** The filter panel takes `{value,label}[]` and cannot indent, so
 * the hierarchy has to live in the LABEL — and the label it lives in is the
 * one the server already publishes for every tagged premises: `area_path`,
 * `"North district · NW"`. One string for one concept, on the chip, in the
 * option list and in the table cell, so a person reading the chip and a person
 * reading the row are reading the same words (r10's own `"South · SE"`).
 *
 * **ORDER IS THE OTHER HALF.** Each district is followed immediately by its own
 * sub-areas; a list sorted by code alone would interleave `EAST-SE` between
 * `EAST` and `IND` only by accident of spelling, and one renamed code would
 * scatter the tree.
 *
 * The two levels do DIFFERENT things when picked, and that is the server's
 * rule, not this list's: a district returns the premises in it AND in its
 * sub-areas (BR-MET-072), a sub-area returns only its own.
 */
export function areaFilterOptions(
  entries: readonly LookupEntry[],
): { value: string; label: string }[] {
  const options: { value: string; label: string }[] = [];
  for (const top of topLevelAreas(entries)) {
    options.push({ value: top.code, label: top.name });
    for (const sub of subAreasOf(entries, top.code)) {
      options.push({ value: sub.code, label: `${top.name} · ${sub.name}` });
    }
  }
  return options;
}

/**
 * The two selects. Rendered by S16 step 1 and by the S14 edit modal.
 *
 * The Sub-area box is present but EMPTY-and-disabled until an area is chosen,
 * rather than appearing out of nowhere: a control that materialises when you
 * touch its neighbour is a control people do not find. When the chosen area has
 * no sub-areas, it says so in its own help text and points at Settings — which
 * is the honest answer, because until 2026-08-17 no screen in this product could
 * create one (DEF-221) and most tenants have none.
 */
export function AreaFields(props: {
  value: AreaSelection;
  onChange: (next: AreaSelection) => void;
  client?: ApiClient;
  idPrefix?: string;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const prefix = props.idPrefix ?? "";
  const areasQuery = useQuery({
    queryKey: areaLookupQueryKey,
    queryFn: () => getLookupEntries("areas", { per: 200 }, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const entries: LookupEntry[] = areasQuery.data?.results ?? [];
  const tops = topLevelAreas(entries);
  const subs = subAreasOf(entries, props.value.top);
  return (
    <>
      <SelectField
        id={`${prefix}area_code`}
        label={t("metering.premises.field.area")}
        value={props.value.top}
        placeholder={t("metering.premises.field.areaPlaceholder")}
        options={tops.map((area) => ({ value: area.code, label: area.name }))}
        // Changing the AREA clears the sub-area: keeping "South · SE" selected
        // under "North" would post a code that contradicts the box above it.
        onChange={(value) => props.onChange({ top: value, sub: "" })}
        help={t("metering.premises.field.areaHelp")}
      />
      <SelectField
        id={`${prefix}sub_area_code`}
        label={t("metering.premises.field.subArea")}
        value={props.value.sub}
        placeholder={t("metering.premises.field.subAreaPlaceholder")}
        options={subs.map((area) => ({ value: area.code, label: area.name }))}
        onChange={(value) => props.onChange({ ...props.value, sub: value })}
        help={
          props.value.top === ""
            ? t("metering.premises.field.subAreaPickAreaFirst")
            : subs.length === 0
              ? t("metering.premises.field.subAreaNone")
              : t("metering.premises.field.subAreaHelp")
        }
      />
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-001@947cf31 (story+rules snapshot hash — EP-MET-01 lead story; co-packet EP-MET-02@14f767b)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-10 (US-SHL-020 conversion — the S14/S15 tab strip moved here as config, `DetailTabs` deleted, `GuardedButton` given a variant class)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ — 296+83 was the pre-W1 baseline and a CONCURRENT Plans & Rates lane is adding to the same suite; this packet contributes 103 passing + 28 todo across 7 files and reduced nothing. The 28 todos are browser-interaction, server/RLS-isolation and unbuilt-neighbour-lane scope, each named in its own test · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔ · [US-SHL-020 conversion 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 593 passed / 141 todo across 46 files✔ (567 passed / 138 todo was the pre-conversion baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 12 PASS · 0 FAIL · 2 SKIP✔ (G14 prototype-conformance now included)
// exceptions: E2 US-SHL-020 — `DetailTabs` is DELETED (both detail views hand their `{id,label}` tab set straight to the shared PageHeader) but `PageHead` is KEPT: the S16 wizard and the S26/S27 ops views still render it and neither screen is in US-SHL-020's set (S9 · S14 · S15 · S21 · S30 · S32 · S49 · S50). Only `.met-tabs` left metering.css; `.met-head*` is still live · E4 `GuardedButton` grew an optional variant `className` so the header's ONE primary slot can carry the primary variant and still be the guarded control — BR-SHL-025's disabled-with-reason travels with the button rather than the header growing an ungated one · E4 the strip's accessible name reuses `metering.kicker` ("Premises & units"): there is no `metering.tabsLabel` key and the catalogs are outside this lane · E3 A4 (BR-IDN-014) has NO assets permission row — this lane gates premises, units AND assets on `premises_accounts` (the closest ratified row) and lets the server refuse the System-Admin-only asset actions (BR-AST-032); reported, not invented · E4 [CLOSED 2026-09-05, DEF-SHL-3964] tenant TZ + date format no longer fall back to a seed: `useRegional` resolves an explicitly supplied prop, then the pair `ShellWithSession` publishes from `GET /settings/regional`, and nothing else
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
