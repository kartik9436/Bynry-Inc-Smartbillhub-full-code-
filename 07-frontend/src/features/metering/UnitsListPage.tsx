// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-002 (S15 Units list tab — derived occupancy, meters cell, delete guard)
//           Screens: S15 (Premises → Units tab, or a premise row scoped by `f.premises_id`)
// Rules:    BR-MET-002 (a unit belongs to exactly ONE premise; accounts attach to units) ·
//           BR-MET-003 (services ⊆ the tenant's enabled set) ·
//           BR-MET-036 (occupancy is DERIVED from the active account — NEVER settable) ·
//           BR-MET-037 (Delete only when never referenced; otherwise deactivate) ·
//           BR-MET-040/041/042 (plan assignment: single + bulk; a direct edit on an
//           OCCUPIED unit is an override the SERVER warns about and this screen shows) ·
//           BR-MET-046 (a unit NEVER moves between premises — no such control exists) ·
//           BR-MET-047 (deactivation blockers are NAMED) · BR-MET-048 (audited server-side) ·
//           BR-SHL-010/011/012 (the ONE table framework, its URL grammar, the A18 states) ·
//           BR-SHL-025 (server-authoritative RBAC) · BR-SHL-032 (confirms name the action) ·
//           BR-SHL-033 (the premises and plan pickers are LONG lists → searchable)
// ───────────────────────────────────────────────────────
// S15 — the units registry.
//
// The load-bearing absences on this screen, each for a stated reason:
//
//   · **No occupancy control.** BR-MET-036 makes occupancy a derived display;
//     `OccupancyCell` is a pill with no `onChange`, the edit form has no
//     occupancy field, and `PATCH /units/{id}` refuses one outright. Three
//     independent places would have to change to break the rule.
//
//   · **No premises control on a unit.** BR-MET-046: a unit never moves. The
//     premises renders as a LINK to its own detail — navigation, not
//     assignment — and the API answers 409 BIZ-IMMUTABLE to anything else.
//
//   · **No client-side plan-override decision.** BR-MET-042 lets a direct
//     unit-level plan edit through on an OCCUPIED unit as an error-correction
//     override; the SERVER decides that and returns the warning, which this
//     screen renders verbatim. It never predicts it.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {useNavigate, useSearchParams} from "react-router-dom";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  assignUnitPlan,
  bulkAssignUnitPlans,
  deleteUnit,
  getPremises,
  getTenantServices,
  getUnitPlanOptions,
  getUnits,
} from "@/api/endpoints";
import type {
  PremisesRow,
  ServerWarning,
  UnitPlanAssignment,
  UnitPlanOption,
  UnitRow,
} from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { createdAgeColumns } from "@/components/createdAgeColumns";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DataTable } from "@/components/DataTable";
import { FilterBar, toggleFilterOption } from "@/components/FilterBar";
import {
  CheckboxField,
  DatePickerField,
  FormModal,
  SearchSelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { PAGE_SIZES, parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableFilterConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { InlineLinkTo, RefusalStrip } from "@/components/Surfaces";
import { MoneyCell } from "@/components/MoneyCell";
import { Note } from "@/components/TextBits";
import { ListExportButton } from "@/features/exports/ListExportButton";
import {
  apiErrorText,
  isPermissionDenied,
  refusalOf,
  RefusalNotice,
} from "@/features/tenancy/settingsShared";
import type { Refusal, Translator } from "@/features/tenancy/settingsShared";
import { EyeIcon, PencilIcon, PowerIcon, SwapIcon, TagIcon, TrashIcon } from "@/components/icons";
import { RowAction, RowActionLink, RowActions, RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { useTenantPath } from "@/routing/tenantPath";

import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";

import { MoveUnitModal } from "./MoveUnitModal";
import { StatusChangeDialog } from "./StatusChangeDialog";
// ⚠ **ONE EDIT FORM, REACHED FROM BOTH DOORS (`DEF-MET-4731` CLOSED).** This
// file used to declare a SECOND, private `UnitEditModal` below its plan modal —
// same endpoint, five of the same fields, a common-area control the unit page's
// form did not have and no plan block, which the unit page's form did. The
// blueprint says the pencil *"opens the same form"* and it did not. It does now.
import { UnitEditModal, unitFormTitle } from "./UnitEditModal";
import { enabledServiceRows } from "./ServicesAvailableField";
import { MissingServicesChip } from "./MissingServicesChip";
// ⚠ **THE OCCUPANT CELL IS THE PROPERTY TAB'S, IMPORTED RATHER THAN COPIED.**
// The same fact — who is in this unit, or the sentence that says nobody is and
// who pays for it — is drawn on two screens, and B14 rule 34 asks for one pair
// of words per fact across the product. A second implementation here would be
// two wordings and two sets of branches waiting to disagree; `BR-MET-101`'s
// common-area sentence and `BR-MET-094`/`BR-CUS-170`'s vacancy sentence are
// both decided in that one function.
import { OccupantCell } from "./PremisesDetailPage";
import { accountDetailPath } from "@/features/customers/customersShared";
import { toEnvelope } from "./PremisesListPage";
import {
  CELL_FULL,
  DASHBOARD_ROUTE,
  Dash,
  GuardedButton,
  MeterCountCell,
  OccupancyCell,
  PREMISES_PERMISSION,
  PREMISES_ROUTE,
  ServiceTags,
  isDenied,
  premisesDetailPath,
  resolveRegional,
  useRegional,
  unitDetailPath,
  unitStatusTone,
  useAccessCell,
} from "./meteringShared";
import type { RegionalProps } from "./meteringShared";

// ── Pure pieces ────────────────────────────────────────────────────────────

/**
 * The page size `Select all {n}` asks for while it walks (`DEF-TEN-5840`).
 *
 * ⚠ **DERIVED FROM `PAGE_SIZES` RATHER THAN WRITTEN AS `1000`, BECAUSE THE
 * SERVER CLAMPS TO EXACTLY THAT CEILING.** `core.pagination.clamp_page_size`
 * rounds any `per` DOWN to the largest allowed size not above it and caps the
 * whole thing at the top of the set — silently, never as an error. A literal
 * here would be a second copy of the server's ceiling, free to drift out of
 * step with it and to turn one request into forty without saying so.
 */
const SELECT_ALL_PER = PAGE_SIZES[PAGE_SIZES.length - 1];

/** US-MET-002 §5: the five ratified unit types (the server's own set). */
export const UNIT_TYPES = [
  "residential",
  "residential_submetered",
  "commercial",
  "commercial_master",
  "common_area",
] as const;

/**
 * The occupancy filter's vocabulary. "sub_metered" rides in the SAME `occupancy`
 * param because the server accepts it there (`units_list`) — the capability row
 * names one control offering All / Occupied / Vacant / Sub-metered, and this is
 * that control, not three.
 */
export const OCCUPANCY_FILTER_VALUES = ["occupied", "vacant", "sub_metered"] as const;

/**
 * BR-MET-100's filter vocabulary. "unplanned" is the value the rule exists
 * for — the units that will never appear on a bill while looking complete on
 * every screen; "planned" is its complement so the control can partition
 * rather than only carve. Both are values `units_list` accepts on `f.plan`.
 */
export const PLAN_FILTER_VALUES = ["unplanned", "planned"] as const;

/**
 * B14 rule 19 — *"Search placeholders read 'Search {entities}…' per module"* —
 * and r10 writes this list's own sentence at `SMARTBillHub.dc.html` line 690:
 * **"Search premises, units, meters…"**. It is the truth about the endpoint:
 * `searchFields` below is premise · label · meter_no, and the server resolves
 * the meter number through the assets registry (US-MET-002 TC-4). The screen
 * said "Search this list", which told a clerk holding a meter number nothing
 * about whether typing it would work. DEF-510 named this screen and this
 * sentence; it is the one being paid.
 */
export const UNITS_SEARCH_PLACEHOLDER_KEY = "metering.units.searchPlaceholder";

/**
 * ⚠ **RESOLVED HERE, NOT PASSED BLIND, AND THAT IS DELIBERATE (hard-won law 3:
 * defaults fail closed).** `DataTable` calls `t()` on `searchPlaceholder` with
 * NO `defaultValue`, so a key that has not reached the eleven catalogues yet
 * renders **its own name** — `metering.units.searchPlaceholder` — into the box,
 * in front of the user, on every locale at once. This lane may not edit the
 * catalogues (the key ships through `scratchpad/newkeys-UNITSUI.json` and
 * `10-scripts/i18n_fanin.py`), so the window between the two commits is real.
 * Falling back to the shared prompt for that window costs a stale sentence;
 * not falling back costs a key name on screen.
 *
 * It is a no-op the moment the fan-in lands, and it deletes itself the day
 * `TableConfig.searchPlaceholder` learns to take a default.
 */
export function unitsSearchPlaceholderKey(t: Translator): string | undefined {
  return t(UNITS_SEARCH_PLACEHOLDER_KEY) === UNITS_SEARCH_PLACEHOLDER_KEY
    ? undefined
    : UNITS_SEARCH_PLACEHOLDER_KEY;
}

export const unitsQueryKey = (query: string) => ["units", query] as const;
export const unitPremisesPickerKey = ["premises", "picker"] as const;
/** DEF-114: the picker reads PLANS, so its cache key says plans. A key still
 *  naming `rate-schedules` would have survived the fix and quietly served the
 *  rating screens' cached tariff pages into this picker. */
export const unitPlanOptionsKey = ["plans", "unit-plan-picker"] as const;

export function unitsTableConfig(
  t: Translator,
  premisesOptions: { value: string; label: string }[],
  /** BR-MET-003 · the TENANT's enabled services, and nothing else. Empty until
   *  `GET /settings/services` answers — `chipFilters` drops the group while it
   *  is, so the panel never draws a heading over nothing. */
  serviceOptions: { value: string; label: string }[],
  cells: {
    select: (row: UnitRow) => JSX.Element;
    unitNo: (row: UnitRow) => JSX.Element;
    premise: (row: UnitRow) => JSX.Element;
    owed: (row: UnitRow) => JSX.Element;
    label: (row: UnitRow) => JSX.Element;
    // The column KEY is the server's sort name (`type`); the data field is
    // `unit_type` and its LABEL is a catalog key — the renderer bridges both.
    type: (row: UnitRow) => JSX.Element;
    services: (row: UnitRow) => JSX.Element;
    offered: (row: UnitRow) => JSX.Element;
    missing: (row: UnitRow) => JSX.Element;
    meters: (row: UnitRow) => JSX.Element;
    occupancy: (row: UnitRow) => JSX.Element;
    occupant: (row: UnitRow) => JSX.Element;
    status: (row: UnitRow) => JSX.Element;
    actions: (row: UnitRow) => JSX.Element;
  },
  // `DEF-MET-10164` — zone + format for Created and Age (see the premises
  // config: the page passes `useRegional`'s answer; a pure caller may omit).
  regional?: { timeZone: string; dateFormat: RegionalDateFormat },
): TableConfig<UnitRow> {
  return {
    screenId: "S15",
    columns: [
      // BR-MET-041's bulk plan assignment needs a selection column; DataTable
      // has no built-in selection yet (US-SHL-006 §deferred), so the checkbox
      // is a CELL in this screen's own config rather than a second table.
      // ⚠ **THE FRAME DRAWS NO `Select` COLUMN AND THIS ONE STAYS — RECORDED,
      // NOT SILENTLY FOLLOWED.** `CR-089-p050` §12 lists *"No `Select` column
      // and no bulk-action bar"* among the drawn absences. `BR-MET-041` is a
      // SIGNED rule that requires bulk plan assignment, and this checkbox is
      // the only control that reaches it, so removing the column would cut a
      // ratified capability to match a drawing. That is a decision for the
      // Product Owner rather than for this lane; the divergence is written into
      // the conformance file beside the frame it departs from.
      { key: "select", label: t("metering.units.col.select"), cell: cells.select },
      // ── THE DRAWN ORDER: `Unit` FIRST, `Address` SECOND ───────────────────
      // ⚠ **THIS PAIR WAS THE OTHER WAY ROUND UNTIL 2026-09-10, AND SWAPPING
      // THEM BACK REVERSES A SHIPPED CHANGE ON PURPOSE.** Wave E read `E1`'s
      // task sentence — *"the units list is scanned by address"* — and put the
      // address first. The blueprint's own frame (page 51) draws `Unit ⇅` as
      // column one and `Address ⇅` as column two, and `CR-089-p050`'s preamble
      // rules the tie: *"Where the teal block or a commitment sentence
      // disagrees with the frame, the frame wins"* (PO, 2026-09-10). The
      // property's own Units tab already draws `Unit` first, so the two lists
      // of units in this product now open the same way.
      //
      // **What the wave-E change actually fixed is untouched and is the part
      // that mattered:** the SERIES NUMBER no longer leads. The unit's label
      // leads column one with `U-01144` quiet beneath it, and the street leads
      // column two with the premise number quiet beneath THAT. Both facts are
      // still on the row and both columns are still sortable. `unit_no` is not
      // a database id — it is a printed reference off the tenant's own series
      // (B14 rule 31 is about ids, and this is not one).
      {
        key: "unit_no",
        label: t("metering.units.col.unit"),
        sortable: true,
        identity: true,
        cell: cells.unitNo,
      },
      {
        key: "address",
        label: t("metering.premises.col.address"),
        sortable: true,
        cell: cells.premise,
      },
      { key: "type", label: t("metering.units.col.type"), sortable: true, cell: cells.type },
      // r10 calls this column "Unit" — the label WITHIN the premise (`Unit A`,
      // `Suite 200`, `Master`, `Apt 101`). ⚠ **AVAILABLE, NOT DEFAULT, SINCE
      // CR-089 wave E, AND THE CAPABILITY IS INTACT.** The label now LEADS the
      // identity column two places to the left, so a second column drawing the
      // same word on a row that already has nine is the duplication B14 rule 32
      // refuses. It stays declared and stays sortable — sorting a building's
      // units by `Apt 101 … Apt 110` is a real thing to want and `unit_no` does
      // not answer it — so the column chooser still offers it. Deleting it
      // would be a capability cut this CR did not ask for; the `occupancy`
      // column below is here on exactly the same reasoning.
      {
        key: "label",
        label: t("metering.units.col.unitLabel"),
        sortable: true,
        cell: cells.label,
        defaultVisible: false,
      },
      { key: "services", label: t("metering.units.col.services"), cell: cells.services },
      // ── THE RETIRED GAP BLOCK'S TWO FACTS, AS COLUMNS (PO 2026-09-28) ────
      // PO, verbatim: *"the Units "Missing services" block — filter or leave
      // it. - filter"*, and on the columns: *an `Offered here` column · a
      // `Missing` column · show/hide like any other*. Both labels are the
      // block's own, already ratified and already in eleven catalogues, so the
      // words a clerk reads did not change when the block did.
      //
      // ⚠ **`Offered here` DRAWS THE SAME VALUES AS THE DRAWN `Services`
      // COLUMN TWO PLACES UP, AND IT IS DECLARED HIDDEN FOR THAT REASON.**
      // `row.services` is what the ADDRESS offers (`DEF-755`), which is what
      // *Offered here* meant in the block — so a second DEFAULT column would
      // draw one fact twice on a row that already has ten (B14 rule 32) and
      // would add a column the `U1` frame does not draw (rule 41). It is
      // DECLARED rather than dropped because the PO ratified it by name and a
      // lane is not the place that decision gets reversed; the overlap is
      // written into the conformance file and put to them in plain English.
      {
        key: "offered",
        label: t("metering.units.gaps.col.offered"),
        cell: cells.offered,
        defaultVisible: false,
      },
      // ⚠ **`Missing` IS THE ONE NEW FACT AND IT IS VISIBLE BY DEFAULT.** The
      // block it replaces was on screen whenever anything was short, and
      // `DEF-MET-6796` exists because the shortfall was INVISIBLE. A column
      // that has to be switched on to be seen would lose exactly what the
      // defect was filed about. It is empty on a whole unit, which is the
      // ordinary row and draws a quiet dash rather than a badge.
      { key: "missing", label: t("metering.units.gaps.col.missing"), cell: cells.missing },
      // The frame draws a COUNT here, not the asset numbers — see
      // `MeterCountCell`, and see `CR-089-p050`'s contradiction 2, which
      // records that the property's Units tab draws something else again in a
      // column of the same name.
      { key: "meters", label: t("metering.units.col.meters"), cell: cells.meters },

      // ⚠ **OCCUPANCY IS AVAILABLE, NOT DEFAULT, AND THE CAPABILITY IS INTACT.**
      // r10's eight columns fold occupancy INTO Status — a vacant unit reads
      // `Vacant` there — so a default Occupancy column would draw the same fact
      // twice on a row that already has eight. It stays in the column chooser
      // rather than being deleted, because BR-MET-036's derived pill is ratified
      // display and removing it would be a capability cut this CR did not ask
      // for. B15 §3.2 lists eight columns and this is the ninth.
      {
        key: "occupancy",
        label: t("metering.units.col.occupancy"),
        cell: cells.occupancy,
        defaultVisible: false,
      },
      // ⚠ **`Occupant`, NOT `Occupant / Account`.** The frame's own note: the
      // account is still IN the cell, quiet, beneath the name — a header naming
      // both halves of one cell is the kind of double-labelling B14 rule 32
      // refuses. The property's Units tab was corrected to the same word on
      // 2026-09-10 and this is the second of the two lists.
      { key: "occupant", label: t("metering.units.col.occupant"), cell: cells.occupant },
      // ⚠ **THE FIRST MONEY THIS SCREEN HAS EVER CARRIED (`E1`/`PUJ-22`).**
      // 1,109 units and not one figure: a clerk scanning a building for arrears
      // opened each unit in turn. `numeric` is what right-aligns it and gives it
      // tabular numerals, so a column of figures reads as a column.
      { key: "owed", label: t("metering.units.col.owed"), numeric: true, cell: cells.owed },
      { key: "status", label: t("metering.units.col.status"), cell: cells.status },
      // ── `DEF-MET-10164` · **Created** and **Age** — the UNIT's OWN date ──
      // PO: *"a unit added in 2015 to a 1996 building is 11 yrs"*. The same
      // shared pair the Premises list draws; both headers send `sort=created`.
      ...createdAgeColumns<UnitRow>(
        t,
        (row) => row.created_at,
        regional ?? resolveRegional({}, null, import.meta.env.MODE),
      ),
      { key: "floor_label", label: t("metering.units.col.floor"), defaultVisible: false },
      {
        key: "square_feet",
        label: t("metering.units.col.squareFeet"),
        numeric: true,
        defaultVisible: false,
      },
      { key: "actions", label: t("metering.col.actions"), cell: cells.actions },
    ],
    getRowId: (row) => row.id,
    // IS-3: premise (no/address), unit label, meter no — the server resolves the
    // meter number through the assets registry (US-MET-002 TC-4).
    searchFields: ["premise", "label", "meter_no"],
    // B14 rule 19 · r10 line 690 — see UNITS_SEARCH_PLACEHOLDER_KEY above.
    searchPlaceholder: unitsSearchPlaceholderKey(t),
    filters: [
      {
        name: "occupancy",
        label: t("metering.units.filter.occupancy"),
        options: OCCUPANCY_FILTER_VALUES.map((value) => ({
          value,
          label: t(`metering.units.occupancyFilter.${value}`),
        })),
      },
      // BR-MET-100 (PO 2026-08-21, option B): an unplanned unit must be
      // COUNTED AND FINDABLE — "the Units tab carries a filter that lists
      // them". The server takes both values on `f.plan` (`units_list`);
      // "planned" is the complement so the one control partitions.
      {
        name: "plan",
        label: t("metering.units.filter.plan"),
        options: PLAN_FILTER_VALUES.map((value) => ({
          value,
          label: t(`metering.units.planFilter.${value}`),
        })),
      },
      // BR-SHL-033: the premises list is LONG, so it is rendered by the
      // searchable control in the filter panel below — declared here so it
      // round-trips through the URL like every other filter.
      { name: "premises_id", label: t("metering.units.filter.premise"), options: premisesOptions },
      // ⚠ **THIS READ `options: []` AND DREW A DEAD GROUP (DEF-782).** The
      // `+ Filter ▾` panel rendered the legend "Service" with nothing under it,
      // on every units list in the product — declared furniture over a
      // capability the screen could not offer, which is the opposite of what
      // BR-SHL-010 asks for. `GET /settings/services` is the tenant's own
      // enabled set (BR-MET-003) and `ServicesAvailableField` already reads it
      // in this module, so the vocabulary is not invented here.
      { name: "service", label: t("metering.units.filter.service"), options: serviceOptions },
      // ── `missing_services` — PO ruling 2026-09-28 ──────────────────────
      // *"the Units "Missing services" block — filter or leave it. - filter"*.
      // It is declared HERE, with the four that were already there, so it
      // round-trips through `f.missing_services` exactly like them, AND-combines
      // with them on the server, and leaves a removable chip (B14 rule 12,
      // IS-4). The server honours it in SQL (`selectors._short_of_offer`), so
      // this is not a control over nothing.
      //
      // One option rather than a partition: *not short* is the ordinary state
      // of a units list and the `Services` column already says so row by row,
      // so a complement would be a second way to ask for the default view.
      {
        name: "missing_services",
        label: t("metering.units.gaps.heading"),
        options: [{ value: "yes", label: t("metering.units.gaps.filterYes") }],
      },
    ],
    // The frame, column 1: *"Sortable, and the default sort is the LABEL"*. It
    // was `unit_no`, which ordered a building's flats by the series number they
    // happened to be minted in rather than by what is written on their doors.
    // `label` is one of `UNIT_SORTS`' own names, so this is a default moving
    // inside a vocabulary the server already publishes.
    defaultSort: { sort: "label", dir: "asc" },
  };
}

/**
 * What `FilterBar` is handed (B14 rule 12 — *"Filters are removable chips"*).
 *
 * Every declared filter EXCEPT `premises_id` goes through unchanged. That one is
 * special twice over and both halves are the rule, not a preference:
 *
 *  · **While it is applied it must be a CHIP.** A units list opened from a
 *    premise (`/premises/units?f.premises_id=…`, the link CR-023 P0 promises
 *    keeps working) showed a handful of rows out of 1,247 with nothing on screen
 *    saying which premise, and no control to drop the scope. That is exactly the
 *    state DEF-442 called the chips load-bearing for.
 *  · **Its option list must never reach the panel.** BR-SHL-033: 1,247 premises
 *    are a type-ahead, never a scroll — and B14 rule 9 refuses a wall of
 *    checkboxes outright. So the chip carries the ONE applied option, which is
 *    all the chip's label needs and all its ✕ needs to untick.
 *
 * Pure, so both halves are provable without a browser.
 */
export function chipFilters(
  declared: readonly TableFilterConfig[],
  state: TableRequestState,
  premisesOptions: { value: string; label: string }[],
): TableFilterConfig[] {
  const applied = state.filters.premises_id;
  return declared.flatMap((filter) => {
    if (filter.name !== "premises_id") {
      // A group with no options is a legend over nothing — the `service`
      // filter drew exactly that until its vocabulary was wired, and it draws
      // it again for the seconds before `GET /settings/services` answers, and
      // permanently for a role that may not read it. BR-SHL-010: what cannot
      // be offered is not rendered.
      return filter.options.length === 0 ? [] : [filter];
    }
    if (applied === undefined) {
      return []; // nothing applied → no group, no 1,247 checkboxes, no empty legend
    }
    const option = premisesOptions.find((o) => o.value === applied);
    return [{ ...filter, options: option === undefined ? [] : [option] }];
  });
}

export function unitsParamsFrom(state: TableRequestState) {
  return {
    q: state.q,
    sort: state.sort,
    dir: state.dir,
    page: state.page,
    per: state.per,
    filters: state.filters,
  };
}

/** BR-SHL-033: a long picker's options, labelled the way a human searches. */
export function premisesPickerOptions(
  rows: readonly PremisesRow[] | undefined,
): { value: string; label: string }[] {
  // ⚠ **THE ADDRESS LEADS, AND THIS WAS FOUND BY LOOKING AT THE SCREEN.** The
  // label read `P-00001 · 1408 Bluestem Ln`, so the add-units wizard's own
  // *Search premises* box — whose frame draws `412 Cypress Row` — showed a
  // property CODE first, which is not what anybody types into it and not what
  // is written on a work order. It is the same correction the units list's
  // address cell and the building card each got; the number has not left.
  return (rows ?? []).map((row) => ({
    value: row.id,
    label: [row.address_line, row.premise_no].filter((part) => part).join(" · "),
    search: [row.external_ref, row.city, row.owner_manager].filter((part) => part).join(" "),
    // ⚠ **THE PARCEL IS SEARCHABLE AND NOT DRAWN (`DEF-MET-4804`).** The
    // add-units picker's own help says *"By address, property number or
    // parcel"* and the label holds only the first two, so a clerk typing a
    // parcel got `No matching options` — a written promise the control could
    // never keep, and indistinguishable from "that property does not exist".
    // It rides in `search` rather than in the label because the frame draws the
    // label as a street address and a deed reference in front of every clerk,
    // to serve a minority of searches, is a worse screen.

  }));
}

/**
 * The Assign-plan picker's options (DEF-114).
 *
 * A PLAN is the bundle across a unit's services (PO ruling 2026-08-11), so the
 * label carries the plan's own code and every service it covers — not one
 * service, which is what a rate SCHEDULE would have. A plan covering nothing
 * still renders: `plan_ref` would accept it and hiding it would leave the clerk
 * with an option list that disagrees with the endpoint all over again.
 */
export function planPickerOptions(
  rows: readonly UnitPlanOption[] | undefined,
): { value: string; label: string }[] {
  return (rows ?? []).map((row) => {
    const services = (row.services ?? []).join(", ");
    return {
      value: row.id,
      label: services === "" ? `${row.name} · ${row.code}` : `${row.name} · ${services}`,
    };
  });
}

/**
 * BR-MET-042: the server's override warning, rendered from its CODE. Returns
 * null for everything else — this screen never invents a warning the server did
 * not raise, and never suppresses one it did.
 */
export function planOverrideWarningKey(warning: ServerWarning | null): string | null {
  if (warning === null) {
    return null;
  }
  return warning.code === "unit_plan_override_on_occupied_unit"
    ? "metering.units.plan.overrideWarning"
    : "metering.units.plan.genericWarning";
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface UnitsListPageProps extends RegionalProps {
  client?: ApiClient;
}

type UnitAction =
  | { kind: "edit"; row: UnitRow }
  | { kind: "move"; row: UnitRow } // BR-MET-095 (CR-024)
  // ⚠ **`status`, NOT `deactivate` — `DEF-MET-4761`.** The row action used to
  // open a plain `ConfirmDialog` that posted `POST /units/{id}/deactivate` with
  // no date, no reason and no dependency check, beside a dialog that demands
  // all three. Two doors, one of them recording nothing.
  | { kind: "status"; row: UnitRow }
  | { kind: "delete"; row: UnitRow }
  | { kind: "plan"; row: UnitRow }
  | { kind: "bulkPlan" };

export function UnitsListPage(props: UnitsListPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  // `DEF-MET-10164` — the tenant's zone and format, for Created and Age.
  const regional = useRegional(props);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [pending, setPending] = useState<UnitAction | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  /** True while `Select all {n}` is walking — the button disables itself so two
   *  presses cannot race to two different selections. */
  const [selectingAll, setSelectingAll] = useState(false);
  const [planNotice, setPlanNotice] = useState<string | null>(null);

  const cell = useAccessCell(PREMISES_PERMISSION, client);
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("metering.rbac.readOnly");

  // BR-SHL-033: the premises picker is a long list. Its rows also label the
  // filter chip, so it is fetched even when the picker itself is closed.
  const premisesQuery = useQuery({
    queryKey: unitPremisesPickerKey,
    queryFn: () => getPremises({ per: 500 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const premisesOptions = premisesPickerOptions(premisesQuery.data?.results);

  // BR-MET-003: a unit's services are a subset of the TENANT's enabled set, so
  // the filter's vocabulary is that set — never a list derived from whichever
  // rows happen to be on this page, which would offer a different set per page.
  // Reference data, so it rides the shared reference staleness and never
  // retries: a role that cannot read Settings gets no group, not a spinner.
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const serviceOptions = enabledServiceRows(servicesQuery.data).map((row) => ({
    value: row.service,
    label: row.name,
  }));

  const config = unitsTableConfig(translate, premisesOptions, serviceOptions, {
    select: (row) => (
      <input
        type="checkbox"
        aria-label={t("metering.units.selectRow", { unit: unitLabel(row, translate) })}
        checked={selected.includes(row.id)}
        onChange={(event) =>
          setSelected(
            event.target.checked ? [...selected, row.id] : selected.filter((id) => id !== row.id),
          )
        }
      />
    ),
    // ── CR-089 wave E · `E1`/`PUJ-22` — THE LABEL LEADS, THE NUMBER SITS
    //    BENEATH IT. ─────────────────────────────────────────────────────────
    // `Unit 1` is what a clerk, a tenant and a work order all call this space;
    // `U-01144` is what the tenant's own series called it once. Both are here,
    // and the order between them is the whole of this task: the series number
    // used to be the first thing on the row and the label was three columns
    // away. Nothing is hidden — the number is the second line, in the same
    // qualifier voice the Occupant cell uses for its account number.
    // A unit with no label falls back to its number as the lead rather than
    // drawing an em-dash over a number that is right there.
    unitNo: (row) => (
      <span>
        <InlineLinkTo to={tenantPath(unitDetailPath(row.id))}>
          {row.label ?? row.unit_no ?? t("metering.units.noNumber")}
        </InlineLinkTo>
        {row.is_common_area && (
          <>
            {" "}
            <StatusPill tone="neutral">{t("metering.units.commonArea")}</StatusPill>
          </>
        )}
        {row.label !== null && row.unit_no !== null && (
          <span className="block met-qualifier">{row.unit_no}</span>
        )}
      </span>
    ),
    // r10 prints BOTH parts: `P-10432 · 1408 Elm St`. The id alone is not
    // enough for a clerk holding a work order, and the address alone does not
    // match what they typed into the search box.
    //
    // ⚠ IT IS STILL A LINK AND STILL NOT A PICKER. BR-MET-046 is
    // SUPERSEDED-REFINED by BR-MET-095 — a unit CAN be moved now — but the move
    // is a deliberate, dated, audited act behind the ⇄ row action, never a
    // dropdown on a list row that reassigns a unit on a stray click.
    // ⚠ **THE TWO PARTS SWAPPED PLACES (`E1`/`PUJ-22`) AND NEITHER LEFT.** r10
    // prints both, and it printed them `P-10432 · 1408 Elm St` — a property code
    // first, which is not what anybody types into the search box above and not
    // what is written on a work order. The street leads now and the premise
    // number is the second line. Searching by either still works (`units_list`
    // matches `premise_no` and `address_line`), which is `E2`.
    premise: (row) => (
      <span>
        <InlineLinkTo to={tenantPath(premisesDetailPath(row.premises_id))}>
          {row.premise_address ?? row.premise_no ?? t("metering.premises.noNumber")}
        </InlineLinkTo>
        {row.premise_address !== null && row.premise_no !== null && (
          <span className="block met-qualifier">{row.premise_no}</span>
        )}
      </span>
    ),
    // ── CR-089 wave E · `E1`/`PUJ-22` — WHAT THIS UNIT OWES ─────────────────
    // ⚠ **FOUR STATES, AND `0.00` IS ONLY ONE OF THEM.** DEF-127 is the defect
    // where an absence was rendered as a zero and a clerk read a settled
    // account off a book nobody could ask; every branch here exists so that
    // cannot happen on this column:
    //   · no occupying account  → the unit owes nothing because nothing is
    //     billed to it; the base charges are the owner's (`BR-CUS-1010`). A
    //     dash with the sentence on it, never `0.00`;
    //   · the books could not be asked → said in words, never a figure;
    //   · `BR-CUS-510`'s not-yet-billable zero → the accounts list's own word
    //     for it, read from the accounts list's own key so the two screens
    //     cannot end up with two words for one fact (B14 rule 34);
    //   · a real figure → `MoneyCell`, which is the ONE display path for money
    //     in this product (BR-SHL-023) and the only thing allowed to round it.
    owed: (row) => {
      // `undefined` and `null` are one answer here — see `UnitRow.owed`.
      const owed = row.owed ?? null;
      if (owed === null) {
        // ⚠ **`Not measured`, AND IT IS A RULING RATHER THAN A CHOICE MADE
        // HERE.** The Product Owner ruled this on the property's Units tab on
        // 2026-09-10 — the vacancy SENTENCE moves to the `Occupant` cell, and
        // the money column keeps its protection: *"show `0.00` only when the
        // balance really is zero, never manufactured over a real debt."* No
        // occupying account means no ledger read happened at all, and a unit
        // whose tenant moved out STILL OWING has a closed account
        // `owed_for_units` deliberately excludes — so a zero here is `DEF-138`
        // word for word. The same fact reaches a clerk in the same words on
        // both lists of units (B14 rule 34); a dash said nothing at all and
        // hid its one sentence inside a tooltip.
        return (
          <Note as="span" title={t("metering.units.owed.notMeasuredWhy")}>
            {t("metering.units.owed.notMeasured")}
          </Note>
        );
      }
      if (owed.balance === null || owed.balance_unavailable.length > 0) {
        return (
          <Note as="span" title={t("metering.units.owed.unreadableWhy")}>
            {t("metering.units.owed.unreadable")}
          </Note>
        );
      }
      if (owed.balance_not_yet_billable) {
        // The accounts list's own word and the accounts list's own explanation,
        // read from the accounts list's own keys. Two screens showing one fact
        // about one account must not end up with two words for it (B14 rule 34),
        // and a second key here is a second wording waiting to drift.
        return (
          <Note as="span" title={t("customers.accounts.balance.awaitingWhy")}>
            {t("customers.accounts.balance.awaiting")}
          </Note>
        );
      }
      return <MoneyCell amount={owed.balance} currency={owed.balance_currency ?? ""} />;
    },
    // BR-MET-101: the flag "must be visible everywhere it matters" — it is the
    // one thing separating a common area from a vacant unit billed to the
    // owner (BR-MET-094). r10's vocabulary for the unit slot is "Common"
    // (its asset table's Unit column), so the pill says that word here.
    label: (row) => (
      <span>
        {row.label === null ? <Dash /> : <span>{row.label}</span>}
        {row.is_common_area && (
          <>
            {" "}
            <StatusPill tone="neutral">{t("metering.units.commonArea")}</StatusPill>
          </>
        )}
      </span>
    ),
    // The frame draws two values in this column — `Residential` and
    // `Common area` — so a common area says what it is HERE rather than only
    // through a pill beside its label. `BR-MET-101` makes the FLAG the fact and
    // `unit_type` the legacy typing, so the flag is asked first: a common area
    // typed `residential` by an old import is still a common area.
    type: (row) =>
      row.is_common_area ? (
        <span>{t("metering.units.type.common_area")}</span>
      ) : row.unit_type === null ? (
        <Dash />
      ) : (
        <span>{t(`metering.units.type.${row.unit_type}`, { defaultValue: row.unit_type })}</span>
      ),
    services: (row) => <ServiceTags services={row.services} t={translate} />,
    // Both read the row the server already sends. `missing_services` is
    // derived ONCE, in `selectors.unit_list_dict`, rather than subtracted here
    // — the retired block kept its own copy of this arithmetic and two
    // derivations of one fact is `DEF-127`'s shape even when both agree.
    offered: (row) => <ServiceTags services={row.services} t={translate} />,
    // ⚠ **AN EMPTY `Missing` CELL IS A WHOLE UNIT AND MUST NOT READ *"No
    // services"*.** `ServiceTags` says that for `[]` because on the `Services`
    // column it means the address offers nothing — the right sentence there and
    // the opposite of the truth here, where empty means *nothing is missing*.
    // A quiet dash is what the rest of this module draws for a cell with no
    // fact in it, and B14 rule 33 puts the explanation at ZERO words.
    missing: (row) =>
      (row.missing_services ?? []).length === 0 ? (
        <span className="met-muted">—</span>
      ) : (
        <ServiceTags services={row.missing_services ?? []} t={translate} />
      ),
    meters: (row) => <MeterCountCell meters={row.meters} t={translate} />,
    occupancy: (row) => <OccupancyCell occupancy={row.occupancy} />,
    // ⚠ **THE VACANCY SENTENCE IS THE CELL'S VISIBLE TEXT NOW, NOT A `title=`.**
    // The frame is explicit — *"On a vacant unit it reads `Vacant — base charges
    // bill to the owner`, muted italic, as the cell's visible text"* — and this
    // column drew a bare `—` with that sentence hidden in a tooltip a keyboard
    // never reaches. See the import: the branch order is `OccupantCell`'s and
    // is a rule rather than a style.
    // Record links (PO 2026-10-19): the occupant's account number opens it.
    occupant: (row) => (
      <OccupantCell
        unit={row}
        t={translate}
        accountHref={(accountId) => tenantPath(accountDetailPath(accountId))}
      />
    ),
    // BR-MET-100: a unit with no plan renders its missing plan as a VISIBLE
    // GAP, never an empty cell. r10's units table (line 699) draws no Plan
    // column, so the gap rides in Status — the column that already folds
    // occupancy into itself — as a worded warning chip beside the status pill.
    // An unplanned unit "does not fail — it simply never appears on a bill",
    // which is exactly what a status column exists to say.
    status: (row) => (
      <span>
        <StatusPill tone={unitStatusTone(row.status)}>
          {t(`metering.units.status.${row.status}`, { defaultValue: row.status })}
        </StatusPill>
        {row.rate_plan_id === null && (
          <>
            {" "}
            <StatusPill tone="warning">{t("metering.units.plan.missing")}</StatusPill>
          </>
        )}
      </span>
    ),
    // ── THREE GLYPHS AND AN OVERFLOW, WHICH IS THE FRAME AND ALSO THE RULE ──
    // The frame draws `👁 ✎ …`, *"three and no more"*, and B14 rule 15 has
    // ended *"Max 2 visible, then `…`"* since it was written. This cell drew
    // FIVE — edit, plan, move, out of service, delete — because the product had
    // no `…` to put anything behind. It has one now (`RowActionsMore`), so the
    // two acts a clerk does from a list stay on the row and the three that
    // change what a unit IS sit one press away, where a stray click cannot
    // reach them.
    //
    // ⚠ **NOTHING IS REMOVED.** Every action that was on this row is still on
    // this row; three of them moved behind the ellipsis. A capability cut would
    // need a ruling, and the frame does not ask for one.
    actions: (row) => (
      <RowActions>
        {/* The eye the frame draws first, and it is a LINK: middle-click and
            "open in new tab" are a real loss on a row a clerk wants to open
            beside the one they are reading. `PremisesListPage` draws the same
            glyph the same way. */}
        <RowActionLink
          label={t("metering.units.action.open")}
          icon={<EyeIcon />}
          to={tenantPath(unitDetailPath(row.id))}
        />
        <RowAction
          label={t("metering.action.edit")}
          icon={<PencilIcon />}
          reason={writeBlockedReason}
          onClick={() => setPending({ kind: "edit", row })}
        />
        <RowActionsMore label={t("table.rowActions.more")}>
          {/* A plan is a thing ATTACHED to the unit, which is what a tag is. The
              swap arrows would read as moving the unit itself. */}
          <RowMenuAction
            label={t("metering.units.action.assignPlan")}
            icon={<TagIcon />}
            reason={writeBlockedReason}
            onClick={() => setPending({ kind: "plan", row })}
          />
          {/* BR-MET-095 (CR-024, PO 2026-08-21): *"please ensure move units works
              in Units … bascially user has put a unit in wrong premises they want
              to move it to correct premises."* The swap glyph is r10's own for
              this action on PRM-02's Units tab and PRM-03's header. B14 rule 15:
              an icon with an accessible NAME, from the one vocabulary. */}
          <RowMenuAction
            label={t("metering.units.action.move")}
            icon={<SwapIcon />}
            reason={writeBlockedReason}
            onClick={() => setPending({ kind: "move", row })}
          />
          {/* BR-MET-1164 · `PUJ-48` — the ONE way out of service, from either
              door. `StatusChangeDialog` names what is still live on the unit,
              links each of those, and requires the date and the reason that the
              audit row is the only record of. */}
          <RowMenuAction
            label={t("metering.action.deactivate")}
            icon={<PowerIcon />}
            reason={writeBlockedReason}
            onClick={() => setPending({ kind: "status", row })}
          />
          {/* BR-MET-037: the server probes accounts · assets · reads at commit;
              a unit that already has meters is visibly guarded here so the rule
              is learnable, and the refusal below is what actually governs. */}
          <RowMenuAction
            label={t("metering.action.delete")}
            icon={<TrashIcon />}
            danger
            reason={
              row.meters.length === 0 && row.account_no === null
                ? writeBlockedReason
                : t("metering.units.deleteBlockedHint")
            }
            onClick={() => setPending({ kind: "delete", row })}
          />
        </RowActionsMore>
      </RowActions>
    ),
  }, regional);

  const state = parseTableParams(searchParams, config);
  function setState(next: TableRequestState): void {
    setSearchParams(serializeTableParams(next, config), { replace: true });
    setSelected([]); // a different result set makes the old selection meaningless
  }

  const listQuery = useQuery({
    queryKey: unitsQueryKey(serializeTableParams(state, config).toString()),
    queryFn: () => getUnits(unitsParamsFrom(state), client),
  });
  /** Every unit the FILTERS match — what `Select all` states and collects.
   *  `results.length` is the page and would understate both. */
  const totalUnits = listQuery.data?.count ?? 0;

  /**
   * **`Select all {n}` — EVERY MATCHING UNIT, WALKED FROM THE SERVER**
   * (`DEF-TEN-5840`).
   *
   * ⚠ **IT CANNOT BE ONE REQUEST, AND THE ROUTE WIZARD'S VERSION IS NOT
   * COPYABLE.** `GET /routes/premises-picker` carries no maximum on `per`, so
   * that screen omits `per` and gets the whole match set back at once.
   * `GET /units` is an ordinary paginated list: `core.pagination.clamp_page_size`
   * CLAMPS `per` to 1,000 and does it SILENTLY — asking for 40,000 is answered
   * with 1,000 and asking for nothing is answered with fifty. Copying the
   * one-request shape here would have put fifty ids behind a button reading
   * `Select all 3,412`.
   *
   * ⚠ **BOUNDED BY THE SERVER'S OWN `count`, NEVER BY A GUESS**, so a total
   * that moves under the walk terminates it instead of spinning. A failure
   * leaves the selection UNTOUCHED rather than half-applied — a half-selected
   * bulk plan assignment is money on the wrong units.
   */
  async function selectEveryMatchingUnit(): Promise<void> {
    setSelectingAll(true);
    try {
      const ids: string[] = [];
      for (let page = 1; ; page += 1) {
        const body = await getUnits(
          { ...unitsParamsFrom(state), page, per: SELECT_ALL_PER },
          client,
        );
        for (const row of body.results) {
          ids.push(row.id);
        }
        if (body.results.length === 0 || ids.length >= body.count) {
          break;
        }
      }
      setSelected([...new Set(ids)]);
    } catch (error: unknown) {
      setRefusal(refusalOf(error, translate));
    } finally {
      setSelectingAll(false);
    }
  }

  function afterWrite(messageKey: string, params?: Record<string, unknown>): void {
    setPending(null);
    setRefusal(null);
    void queryClient.invalidateQueries({ queryKey: ["units"] });
    void queryClient.invalidateQueries({ queryKey: ["premises"] });
    fireToast(t(messageKey, params));
  }

  const remove = useMutation({
    mutationFn: (row: UnitRow) => deleteUnit(row.id, client),
    onSuccess: (_void, variables) =>
      afterWrite("metering.units.toast.deleted", { unit: unitLabel(variables, translate) }),
    onError: (error: unknown) => setRefusal(refusalOf(error, translate)),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("metering.units.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (listQuery.data === undefined && listQuery.isError && isPermissionDenied(listQuery.error)) {
    return (
      <PermissionDenied
        helper={t("metering.units.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  return (
    <>
      {/* ⚠ **NO PAGE HEADER HERE ANY MORE — CR-023 P0.** This screen is a TAB
          BODY: `PremisesTabsPage` owns the one head, and r10's `h1` reads
          **Premises** on this tab too (line 630). It used to retitle the page to
          "Units", which is the single thing that made these read as two screens
          rather than as one page with a strip. */}
      <RefusalNotice refusal={refusal} />
      {planNotice !== null && (
        <RefusalStrip role="alert">
          {planNotice}
        </RefusalStrip>
      )}

      {/* BR-MET-041: multi-select + plan + effective date, one audited batch.
          ── `DEF-TEN-5840` · `Select all {n}` AND THE BAR THAT HOLDS IT ──────
          ⚠ **THE BAR USED TO APPEAR ONLY ONCE SOMETHING WAS ALREADY TICKED**,
          which makes a select-all control unreachable from the state it exists
          to get you out of. It now shows whenever the list has rows, so the
          way to select 3,412 units is not to tick 3,412 boxes. PO, 2026-09-19:
          *"this is in premises/unit, route and cycle creation context"*.
          ⚠ **`Select all` MEANS EVERY MATCHING UNIT, NOT THE FIFTY ON SCREEN.**
          This list is server-paginated (`NFR-3`), so a header checkbox ticking
          the visible page under a filter matching 3,412 would leave a clerk
          believing they had selected 3,412 and assigning a plan to fifty —
          silently, with a green screen. The label therefore states the SERVER'S
          total and the walk collects exactly that many.
          ── `CR-176-BRC10` · `DEF-MET-10035` — ONLY ONCE A UNIT IS TICKED ──
          ⚠ **THE PO RULED THE OTHER WAY ON 2026-10-09 AND THAT RULING WINS.**
          *"the Units list's selection bar shows only once a unit is ticked (no
          '0 unit(s) selected')"*. `DEF-TEN-5840`'s reach survives it: tick any
          one row and the bar, `Select all {n}` with it, appears — the way to
          3,412 units is one tick and one press, never 3,412 ticks. Decision log
          2026-10-09 records the reconciliation. */}
      {selected.length > 0 && (
        <div className="met-counts" role="status">
          <span>{t("metering.units.bulk.selected", { count: selected.length })}</span>
          <Button
            variant="secondary"
            disabled={selectingAll || totalUnits === 0}
            onClick={() => {
              void selectEveryMatchingUnit();
            }}
          >
            {t("settings.routes.wizard.selectAllMatching", { count: totalUnits })}
          </Button>
          <GuardedButton
            label={t("metering.units.bulk.assignPlan")}
            reason={writeBlockedReason}
            onClick={() => setPending({ kind: "bulkPlan" })}
          />
          <Button variant="ghost" onClick={() => setSelected([])}>
            {t("metering.units.bulk.clear")}
          </Button>
        </div>
      )}

      {/* ── THE GAP BLOCK STOOD HERE AND IS DELETED (PO 2026-09-28) ────────
          `<UnitServiceGaps premisesId={…} client={client} />` — a second table
          above this one, with its own pager, its own columns and its own read.
          PO, verbatim: *"the Units "Missing services" block — filter or leave
          it. - filter"*. It is DELETED rather than hidden: two doors onto one
          set of 60 units is how they drift apart, and in the block those units
          could be combined with neither the search nor the filters, could not
          be paged with the list, and could not be SELECTED for the bulk bar
          above — which is the one thing a clerk wants to do with a list of
          units that are short. The filter is in `config.filters`, the two
          facts are columns, and the count is on the toolbar. */}

      <DataTable<UnitRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={listQuery.data?.results ?? []}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending}
        error={
          listQuery.isError && listQuery.data === undefined
            ? {
                reason: apiErrorText(listQuery.error, translate),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        filterBarSlot={
          // ⚠ **THIS WAS `<div className="met-filters">` AND THAT ONE CLASS COST
          // THE SCREEN ITS TOOLBAR (PO 2026-08-26).** `.met-filters` is a GRID
          // with `width: 100%` (metering.css) — dropped into `.table-toolbar`'s
          // flex row it claimed the whole line, stretched the premises picker to
          // 554px and pushed the segment and the export onto a THIRD row. r10
          // draws PRM-01U's controls as ONE `.toolbar` line
          // (`SMARTBillHub.dc.html` line 690) and B14 rule 12 writes that grammar
          // down: `[Search…] [All | filter chips ×] [+ Filter ▾] … [▦ Columns]`.
          // A fragment hands the toolbar TWO ordinary flex children instead, so
          // the row stays a row. The class itself stays declared — two other
          // metering screens still use it inside a FORM, where a grid is right.
          <>
            <FilterBar
              // `premises_id` is handed to FilterBar ONLY once it is applied, and
              // then with the ONE option that is applied. That is what makes the
              // applied premise a REMOVABLE CHIP, which is the half of B14 rule 12
              // this screen was missing entirely: a units list scoped by
              // `?f.premises_id=` showed 3 rows of 1,247 and said nothing about
              // why, and the only way back was the browser's Back button.
              // BR-SHL-033 keeps the SETTING of it in the type-ahead beside this
              // — 1,247 premises can never be a checkbox list (B14 rule 9).
              filters={chipFilters(config.filters ?? [], state, premisesOptions)}
              state={state}
              onStateChange={setState}
            />
            {/* ── THE COUNT, WHETHER OR NOT THE FILTER IS ON (PO 2026-09-28) ──
                `DEF-MET-6796` exists because the shortfall was INVISIBLE, and a
                filter nobody switches on is invisible in the same way — so the
                figure sits on the toolbar, where the eye lands, rather than
                inside a `+ Filter ▾` panel that is closed by default. It is the
                SAME value the panel edits (`state.filters.missing_services`),
                so the two controls cannot drift apart the way the block and the
                list did. */}
            <MissingServicesChip
              count={listQuery.data?.service_gap_count ?? null}
              on={state.filters.missing_services !== undefined}
              onToggle={() => setState(toggleFilterOption(state, "missing_services", "yes"))}
              t={translate}
            />
            {/* BR-SHL-033: a long list is type-ahead searchable, never a scroll.
                Toolbar scale, not form scale: the field's label is `sr-only`, so
                the control is one 36px input carrying r10's own placeholder
                voice ("Any premise") with its accessible name intact. B14 rule
                21 — utilities only, no stylesheet rule added.

                ⚠ **IT IS ABSENT WHILE A PREMISE IS APPLIED, AND THAT IS THE
                POINT.** `SearchSelectField` seeds its displayed text ONCE, from
                the option matching `value` — and this picker's options arrive
                from a SECOND request that has not landed on first render, so on
                a `?f.premises_id=`-scoped list the box settled on its
                placeholder and read **"Any premise"** while the list was scoped
                to one. Two controls, one fact, and the one a clerk could see
                said the opposite of the truth. The chip above is now that fact;
                its ✕ brings the picker back. One control per fact, and the row
                stays one row in BOTH states. */}
            {state.filters.premises_id === undefined && (
            <div className="w-52 shrink-0 [&>.field>label]:sr-only!">
              <SearchSelectField
                id="f.premises_id"
                label={t("metering.units.filter.premise")}
                value={state.filters.premises_id ?? ""}
                options={premisesOptions}
                placeholder={t("metering.units.filter.premisePlaceholder")}
                onChange={(value) => {
                  const filters = { ...state.filters };
                  if (value === "") {
                    delete filters.premises_id;
                  } else {
                    filters.premises_id = value;
                  }
                  setState({ ...state, filters, page: 1 });
                }}
              />
            </div>
            )}
          </>
        }
        // ⚠ **THERE IS NO SECOND TOOLBAR ROW ON THIS SCREEN ANY MORE
        //    (DEF-1700, PO 2026-08-27).** r10's All · Occupied · Vacant ·
        //    Sub-metered segment used to sit here — first in `downloadSlot`,
        //    then in `dimensionsSlot` after DEF-1085 built that slot for it.
        //    The Product Owner photographed the result and ruled: *"as per our
        //    stadard first raw of tookkit is more than suficient ... I can see
        //    it in unit also"*. `occupancy` was ALREADY a declared
        //    `TableConfig.filter` over the SAME `OCCUPANCY_FILTER_VALUES`,
        //    writing the same `f.occupancy` param — so the segment was pure
        //    duplication and every one of its four cells is still reachable
        //    from `+ Filter`, including Sub-metered.
        downloadSlot={
          <>
            {/* US-MET-002's capability row declares "Export: CSV (IS-9)". The
                premises filter travels in `state.filters` like every other one,
                so a premise-scoped view exports exactly the units it shows. */}
            <ListExportButton resource="units" state={state} client={client} />
          </>
        }
        // ⚠ **THE DRAWN EMPTY STATE POINTS AT PROPERTIES, NOT AT THIS SCREEN'S
        //    OWN CREATE.** The frame's STATES block, verbatim: *"Says a
        //    property must exist first, and links to the property list."* It
        //    used to offer `+ New unit` over a tenant with no properties — a
        //    button onto a wizard whose first required box would have had
        //    nothing to put in it — under two sentences about CSV imports that
        //    B14 rule 32's one-sentence budget does not allow.
        empty={{
          title: t("metering.units.emptyTitle"),
          helper: t("metering.units.emptyNeedsPremises"),
          ctaLabel: t("metering.units.emptyOpenPremises"),
          onCta: () => navigate(tenantPath(PREMISES_ROUTE)),
        }}
      />

      <p className="settings-audit-line">{t("metering.auditLine")}</p>

      {pending?.kind === "status" && (
        <StatusChangeDialog
          subject="unit"
          id={pending.row.id}
          // ⚠ **THE LABEL, LIKE THE OTHER TWO DIALOGS.** A browser walk read
          // `Take U-00101-A out of service?` beside an edit form titled `Edit
          // Unit B` — one unit, two names, on two dialogs a clerk opens from
          // the same row. `unitLabel` puts the series number first, which is
          // right for a TOAST (it is the reference they quote) and wrong for a
          // title they read to check they have the right flat.
          name={unitFormTitle(pending.row, translate)}
          client={client}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          onClose={() => setPending(null)}
          onChanged={(status) =>
            afterWrite(
              status === "inactive"
                ? "metering.units.toast.deactivated"
                : "metering.units.toast.reactivated",
              { unit: unitLabel(pending.row, translate) },
            )
          }
        />
      )}
      {pending?.kind === "delete" && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): delete a unit.
          confirmVariant="danger"
          title={t("metering.units.confirm.deleteTitle", {
            unit: unitLabel(pending.row, translate),
          })}
          consequence={t("metering.units.confirm.deleteBody")}
          confirmLabel={t("metering.units.confirm.deleteAction")}
          working={remove.isPending}
          onConfirm={() => remove.mutate(pending.row)}
          onCancel={() => setPending(null)}
        />
      )}
      {pending?.kind === "edit" && (
        <UnitEditModal
          unit={pending.row}
          client={client}
          regional={props}
          onClose={() => setPending(null)}
          onSaved={(warningKey) => {
            // BR-MET-042's override sentence, in the SAME strip the plan modal
            // uses — one place a plan warning ever appears on this screen.
            setPlanNotice(warningKey === null ? null : t(warningKey));
            afterWrite("metering.units.toast.saved", { unit: unitLabel(pending.row, translate) });
          }}
        />
      )}
      {pending?.kind === "plan" && (
        <UnitPlanModal
          client={client}
          unitIds={[pending.row.id]}
          title={t("metering.units.plan.title", { unit: unitLabel(pending.row, translate) })}
          regional={props}
          onClose={() => setPending(null)}
          onAssigned={(warningKey) => {
            setPlanNotice(warningKey === null ? null : t(warningKey));
            afterWrite("metering.units.toast.planAssigned", {
              unit: unitLabel(pending.row, translate),
            });
          }}
        />
      )}
      {pending?.kind === "bulkPlan" && (
        <UnitPlanModal
          client={client}
          unitIds={selected}
          title={t("metering.units.plan.bulkTitle", { count: selected.length })}
          regional={props}
          onClose={() => setPending(null)}
          onAssigned={(warningKey) => {
            setPlanNotice(warningKey === null ? null : t(warningKey));
            setSelected([]);
            afterWrite("metering.units.toast.planBulkAssigned", { count: selected.length });
          }}
        />
      )}
      {/* BR-MET-095 (CR-024): the move the PO asked for, as a MODAL from the row
          — *"you can have a modal for that"*. */}
      {pending?.kind === "move" && (
        <MoveUnitModal
          client={client}
          unit={pending.row}
          onClose={() => setPending(null)}
          onMoved={(premise) => {
            const moved = pending.row;
            afterWrite("metering.units.toast.moved", {
              unit: unitLabel(moved, translate),
              premise,
            });
          }}
        />
      )}
    </>
  );
}

export function unitLabel(row: UnitRow, t: Translator): string {
  return row.unit_no ?? row.label ?? t("metering.units.noNumber");
}

// ── Plan assignment (BR-MET-040/041/042 · BR-CUS-014) ──────────────────────

export function UnitPlanModal(props: {
  client: ApiClient;
  unitIds: string[];
  title: string;
  regional: RegionalProps;
  onClose: () => void;
  onAssigned: (warningKey: string | null) => void;
}) {
  const { t } = useTranslation();
  const { dateFormat } = useRegional(props.regional);
  const [values, setValues] = useState({
    tariff_id: "",
    effective_from: "",
    plan_locked: false,
    reason: "",
  });

  const plansQuery = useQuery({
    queryKey: unitPlanOptionsKey,
    queryFn: () => getUnitPlanOptions({ per: 500 }, props.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      let warning: ServerWarning | null = null;
      if (props.unitIds.length === 1) {
        const result: UnitPlanAssignment = await assignUnitPlan(
          props.unitIds[0],
          {
            tariff_id: values.tariff_id,
            effective_from: values.effective_from === "" ? undefined : values.effective_from,
            plan_locked: values.plan_locked,
            reason: values.reason === "" ? undefined : values.reason,
          },
          props.client,
        );
        warning = result.warning;
      } else {
        const result = await bulkAssignUnitPlans(
          {
            unit_ids: props.unitIds,
            tariff_id: values.tariff_id,
            effective_from: values.effective_from === "" ? undefined : values.effective_from,
            plan_locked: values.plan_locked,
            reason: values.reason === "" ? undefined : values.reason,
          },
          props.client,
        );
        // BR-MET-042 in bulk: ANY overridden unit raises the warning for the
        // batch — the screen must not swallow one because the rest were clean.
        warning = result.units.find((unit) => unit.warning !== null)?.warning ?? null;
      }
      props.onAssigned(planOverrideWarningKey(warning));
      return { ok: true };
    } catch (error) {
      return { ok: false, error: toEnvelope(error) };
    }
  }

  return (
    <FormModal
      title={props.title}
      kicker={t("metering.kicker")}
      schema={z.object({
        tariff_id: z.string().trim().min(1, t("metering.units.plan.planRequired")),
        effective_from: z.string(),
        plan_locked: z.boolean(),
        reason: z.string(),
      })}
      values={values}
      submitLabel={t("metering.units.plan.save")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      {/* BR-SHL-033: the plan list is long → the searchable control. */}
      <SearchSelectField
        id="tariff_id"
        label={t("metering.units.plan.plan")}
        required
        value={values.tariff_id}
        options={planPickerOptions(plansQuery.data?.results)}
        placeholder={t("metering.units.plan.planPlaceholder")}
        onChange={(value) => setValues({ ...values, tariff_id: value })}
        help={plansQuery.isError ? t("metering.units.plan.planListUnavailable") : undefined}
      />
      {/* BR-SHL-033: every date field is a picker with easy manual entry. */}
      <DatePickerField
        id="effective_from"
        label={t("metering.units.plan.effectiveFrom")}
        value={values.effective_from}
        dateFormat={dateFormat}
        onChange={(value) => setValues({ ...values, effective_from: value })}
        help={t("metering.units.plan.effectiveFromHelp")}
      />
      <CheckboxField
        id="plan_locked"
        label={t("metering.units.plan.locked")}
        checked={values.plan_locked}
        onChange={(checked) => setValues({ ...values, plan_locked: checked })}
      />
      <TextField
        id="reason"
        label={t("metering.units.plan.reason")}
        value={values.reason}
        onChange={(value) => setValues({ ...values, reason: value })}
        help={t("metering.units.plan.reasonHelp")}
      />
      {/* BR-MET-042: the OVERRIDE path is stated up front; the server decides
          whether this edit IS one and returns the warning we then show. */}
      <Note>{t("metering.units.plan.overrideNote")}</Note>
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-002@947cf31 (story+rules snapshot hash — EP-MET-01; co-story US-MET-001@947cf31)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-10 (US-SHL-020 conversion — S15 renders the SAME declared strip S14 does, with the Units tab active)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [US-SHL-020 conversion 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 593 passed / 141 todo across 46 files✔ (567 passed / 138 todo was the pre-conversion baseline) · vite build✔ · run_gates 12 PASS · 0 FAIL · 2 SKIP✔ (G14 prototype-conformance included) · [list-export lane 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ — 296+83 was the pre-W1 baseline and a CONCURRENT Plans & Rates lane is adding to the same suite; this packet contributes 103 passing + 28 todo across 7 files and reduced nothing. The 28 todos are browser-interaction, server/RLS-isolation and unbuilt-neighbour-lane scope, each named in its own test · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E2 US-SHL-020 — no kicker: the prototype's head for this screen (UtilityBilling.html line 713) is an H1 and its roll-up, and `metering.kicker` sat above an H1 that already said "Units" (DEF-021) · E2 `metering.units.accountsAttachToUnits` is no longer rendered as a subtitle here — it is verbatim the last clause of `metering.premises.explainer.units`, the prototype's own sentence for the slot below the strip, so rendering both would have printed one sentence twice on one screen. No copy is lost and the catalog key (still used by the S14 detail's Units tab) is untouched · E2 "Import CSV" is NOT drawn on this route although the prototype shows it on both tabs: it opens the PREMISES importer and US-MET-002's capability row declares no CSV import for units — reported, not invented · E3 CLOSED (list-export lane 2026-08-10): US-MET-002's CSV export (IS-9) is WIRED to POST /exports and carries the premises filter with the rest of the state; the produced file still has no download route (`result_link` is a `file://` artifact path — IS-11/reports W5), so the completed state names it rather than linking it · E3 the Service filter has NO option list: the tenant's enabled-service set is served by `GET /settings/services`, a System-Admin-only read, so a Clerk would get an empty dropdown; it stays a declared filter driven by the URL until a role-safe service list exists — reported · E4 the "Sub-metered" choice rides in the `occupancy` filter param because that is where the server accepts it (`units_list`), matching the capability row's single All/Occupied/Vacant/Sub-metered control · E4 bulk selection is this screen's own checkbox column: FE-02 DataTable declares bulk selection as a later packet, and BR-MET-041 needs it now
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
