// ── Trace ──────────────────────────────────────────────
// Change:  CR-006 (PO 2026-08-16) — SET-05 landing, two stacked tables.
//          ⚠ REBUILT BY CR-029 RC-W3-T1/T2 (PO 2026-08-23) — Routes | Cycles
//          SUB-TABS on the shared DataTable, the ruled schedule columns, the
//          service SET, route chips and the landing coverage sentence.
// Design:  04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §3, §4
// Story:   US-MET-006 (EP-MET-02 §Stories)  Screens: S8 · SET-05 · SET-05.cycles
// Rules:   BR-MET-008 (unique code; deactivate-first, delete audit-locked while
//          referenced) · BR-MET-009 (cycle delete audit-lock) · BR-MET-010 (one
//          cycle per route — assigning MOVES it) · BR-MET-073 (route service ·
//          area · notes) · BR-MET-075 (meters on route = available − excluded) ·
//          BR-MET-076 (the Draft pill; drafts affect nothing) · BR-MET-077 (the
//          cycle's day-of-month DEFAULTS) · BR-MET-078 (NO money on this
//          surface) · BR-MET-079 (reads history refuses delete) · BR-MET-080
//          (the coverage flag) · BR-MET-035b (System Admin only; everyone else
//          read-only WITH the reason) · BR-SHL-011 (URL grammar — the open
//          sub-tab is URL state) · BR-SHL-025 (server-computed access) ·
//          BR-SHL-032 (a confirm names its action)
// CR-029:  D6 (NO Reader column) · D7 (server-side pagination + sorting) ·
//          D9 (bill/due day are CYCLE DEFAULTS) · D10 (a route serves a service
//          SET) · D13 (a cycle is DERIVED at bill-run time)
// B14:     rule 4 (`+ Noun`) · 5 (two button sizes) · 6 (danger tier) ·
//          12 (toolbar) · 13 (sort) · 14 (column selector) · 15 (ICON row
//          actions) · 16 (pagination footer) · 17 (empty state) · 18 (80%) ·
//          20 (one table type) · 21 (Tailwind, NO stylesheet class)
// ───────────────────────────────────────────────────────
/**
 * S8 → Routes & Cycles, SET-05 and SET-05.cycles.
 *
 * ⚠ **WHAT CR-029 CHANGED AND WHY EACH CHANGE IS A RULING, NOT A PREFERENCE.**
 *
 *   · **Two stacked tables became two SUB-TABS.** B17 §4's target row for this
 *     screen: *"Routes | Cycles **sub-tabs**, each with its own toolbar and
 *     pager"*. The stack was fine at seven routes and unusable at seven
 *     hundred, and the open tab is URL state (BR-SHL-011) so a link opens the
 *     half it was sent about.
 *
 *   · **Hand-rolled `<table className="settings-table">` became the shared
 *     `DataTable`.** DEF-223 measured four B14 rules broken here in Chromium —
 *     no ⇅ sort affordance (rule 13), no ▦ column selector (rule 14), a table
 *     type at 14px against the ratified 13.5 (rule 20), and three button sizes
 *     (rule 5). Four rules, one cause: this screen re-implemented the table.
 *     The shared component carries all four by construction.
 *
 *   · **NO READER COLUMN, and the fixture proves the column is not merely
 *     empty.** The upgraded prototype draws one; the PO ruled D6 *"not
 *     required"*. `routes.assigned_to` is untouched and unwritten from the UI.
 *
 *   · **The cycle's three schedule columns are the ruled model** — Frequency ·
 *     Start day · Days to complete (B17 §2). The legacy `read_day_from–to`
 *     pair is not a column here any more; it is a DERIVED window, and the
 *     detail screen is where it is explained.
 *
 * **NO MONEY REACHES THIS FILE** (BR-MET-078), and CR-029 hardens that: the
 * cycles table shows no bill amount, no fee and no BALANCE, because a route and
 * a cycle are grouping only.
 *
 * ⚠ **B14 RULE 21 — THIS FILE ADDS NO CLASS TO ANY STYLESHEET.** It carried ten
 * bespoke `settings-*` names from `SettingsPage.css` before CR-029; the regions
 * this task rewrote are Tailwind utilities and the file now names none of them.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  deactivateRoute,
  deleteCycle,
  deleteRoute,
  getCycleCoverage,
  getCyclesPage,
  getRoutesPage,
} from "@/api/endpoints";
import type { CycleRow, RouteRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { ListExportButton } from "@/features/exports/ListExportButton";
import { PencilIcon, PowerIcon, TrashIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { SelectionToolbar } from "@/components/SelectionToolbar";
import { StatusPill } from "@/components/StatusPill";
import { RoutesReadFormatDialog } from "@/features/metering/ReadFormatPointer";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { Kicker } from "@/components/TextBits";
import { useTenantPath } from "@/routing/tenantPath";

import {
  CYCLE_FREQUENCY_WORDS,
  ChipList,
  RC_DESC,
  RC_MUTED,
  StartDayCell,
  coverageSentenceKey,
  cycleDetailPath,
  cycleWizardPath,
  effectiveStartDay,
  frequencyLabel,
  routeDetailPath,
  routeWizardPath,
} from "./routesCyclesShared";
import {
  RefusalNotice,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "./settingsShared";
import type { Refusal, Translator } from "./settingsShared";

// ── Pure pieces ────────────────────────────────────────────────────────────

/** Counts from the unwired W2 reads lane are null — "—", never a fake 0. */
export function orDash(value: number | null, dash: string): string {
  return value === null ? dash : String(value);
}

/**
 * BR-MET-076 — the pill tone. **DRAFT IS NOT INACTIVE.** Inactive means "this
 * used to run and no longer does" and keeps its history; draft means "this has
 * never run" and touches nothing. Rendering them alike would tell a utility
 * that a route it is still writing is a route it has retired.
 */
export function lifecycleTone(status: string): "success" | "warning" | "neutral" {
  if (status === "active") {
    return "success";
  }
  if (status === "draft") {
    return "warning";
  }
  return "neutral";
}

/**
 * SET-05 verbatim: *"Deactivating a route in an active cycle → warning:
 * 'Route SCW-R2 is in cycle SCW-M — reads scheduled Sep 1–5 will skip 388
 * premises.'"*
 *
 * Built from the ROW's own facts and the cycle's stored DEFAULTS, and it is
 * deliberately not built at all when the route is on no cycle: a warning that
 * fires on every deactivation teaches the user to click through it.
 */
export function deactivationImpact(
  route: RouteRow,
  cycles: readonly CycleRow[],
): { cycle: string; from: number | null; to: number | null; premises: number } | null {
  if (route.cycle_code === null) {
    return null;
  }
  const cycle = cycles.find((row) => row.id === route.cycle_id) ?? null;
  return {
    cycle: route.cycle_code,
    // ⚠ CR-029 D2 — the START DAY, and since W5-T2 there is nothing else to
    // fall back TO: `read_day_from`/`read_day_to` were dropped by metering
    // 0021. The window this sentence quotes is derived from the two fields the
    // cycle actually holds.
    //
    // ⚠ **AND IT IS THE EFFECTIVE DAY, NOT THE STORED ONE (OQ-340).** This
    // sentence warns a user what reads they are about to skip; quoting a
    // window the cycle does not actually run would name the wrong dates in a
    // destructive confirmation, which is the worst place in the product to be
    // approximately right.
    from: cycle === null ? null : effectiveStartDay(cycle).day,
    to:
      cycle !== null && effectiveStartDay(cycle).day !== null && cycle.days_to_complete != null
        ? (effectiveStartDay(cycle).day as number) + cycle.days_to_complete - 1
        : null,
    premises: route.premises,
  };
}

/**
 * BR-MET-077 — "1st–3rd of month", DERIVED, never a date.
 *
 * ⚠ **IT READ `read_day_from`–`read_day_to` UNTIL W5-T2** and those columns are
 * gone (metering 0021). The same sentence now comes from the two fields B17 §2
 * rules — *"start day + N days IS the read window"*, INCLUSIVE — so a cycle
 * created through the wizard has a label where it used to show an em-dash. The
 * end day CLAMPS at 31 for the reason the server's own check clamps: a window
 * opening on the 29th with 5 days runs into the next month, and a day-of-month
 * label cannot say so. The cycle DETAIL shows the real dates.
 */
export function readWindowLabel(cycle: CycleRow, dash: string): string {
  // ⚠ **THE EFFECTIVE DAY (OQ-340), NOT THE STORED ONE.** On the PO's own
  // figure — start day 1, first run 15 Sep — the stored number would draw
  // "1–3" beside a cycle that reads on the 15th, and the two cells would
  // disagree with each other on the same row.
  const start = effectiveStartDay(cycle).day;
  if (start === null || cycle.days_to_complete === null) {
    return dash;
  }
  return `${start}–${Math.min(31, start + cycle.days_to_complete - 1)}`;
}

/**
 * BR-SHL-011's fallback law, one level down: the open sub-tab is `?rc=`, and an
 * unknown value falls back to Routes rather than erroring or blanking.
 */
export type RoutesCyclesSubTab = "routes" | "cycles";

export function routesCyclesSubTabFrom(raw: string | null | undefined): RoutesCyclesSubTab {
  return raw === "cycles" ? "cycles" : "routes";
}

export const ROUTES_CYCLES_SUB_TAB_PARAM = "rc";

// The query keys. Both carry the request state so a page change is a new
// fetch and not a silent cache hit on the wrong window.
export const routesPageKey = ["routes", "page"] as const;
export const cyclesPageKey = ["cycles", "page"] as const;

/** The full key, request state included — a page change is a NEW fetch and
 *  never a silent cache hit on the wrong window. Exported so a test seeds the
 *  same key the screen reads rather than a near-miss that renders a skeleton. */
export function routesPageKeyFor(state: TableRequestState): readonly unknown[] {
  return [...routesPageKey, state];
}

export function cyclesPageKeyFor(state: TableRequestState): readonly unknown[] {
  return [...cyclesPageKey, state];
}

/** CR-045 wave D · D.6 (DEF-1702) — the key the ROUTES sub-tab's cycle
 *  VOCABULARY is cached under. Deliberately carries no request state: the
 *  option list a filter panel offers must not move when the user filters
 *  something, and `cyclesPageKeyFor` would make it do exactly that. */
export const cycleVocabularyKey = ["cycles", "vocabulary"] as const;

/** The request shape that vocabulary is fetched with — page 1, code order, no
 *  search and no filters, which is the complete list the server will serve in
 *  one page. It is a `defaultSort` carrier and nothing else, so it declares no
 *  columns: `defaultRequestState` reads `defaultSort` and no other key. */
const CYCLE_VOCABULARY_CONFIG = {
  screenId: "SET-05.cycles.vocabulary",
  getRowId: (row: CycleRow) => row.id,
  defaultSort: { sort: "code", dir: "asc" },
  columns: [],
} satisfies TableConfig<CycleRow>;
export const landingCoverageKey = ["cycles", "coverage", "landing"] as const;

// ── The tab ────────────────────────────────────────────────────────────────

export interface RoutesCyclesTabProps {
  readOnly: boolean;
  client?: ApiClient;
  dateFormat?: RegionalDateFormat; // IS-8; supplied by the US-SHL-013 wiring
}

/* ⚠ THERE IS NO `subTab` PROP, AND G13 IS THE REASON (hard-won law 2).
 * The first draft took the open sub-tab as an optional prop with a URL
 * fallback — and `SettingsPage` never passed it, so the prop existed to be set
 * by tests and by nothing else: *"a component with an optional prop that
 * nothing passes is dead UI"*. G13 named it on the commit that added it.
 * The URL is the ONE source (BR-SHL-011), which is what the rest of this
 * product does and what makes a link to the Cycles half work at all. */

type RouteAction = { route: RouteRow; kind: "deactivate" | "delete" } | null;

export function RoutesCyclesTab(props: RoutesCyclesTabProps) {
  const { t } = useTranslation();
  // ⚠ `useCallback`, because the two table configs are memoised on it: a fresh
  // closure per render rebuilds both column sets on every keystroke, and the
  // linter is right that the memo would then be doing nothing.
  const translate: Translator = useCallback((key, params) => t(key, params), [t]);
  const client = props.client ?? api;
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const [search, setSearch] = useSearchParams();

  const active = routesCyclesSubTabFrom(search.get(ROUTES_CYCLES_SUB_TAB_PARAM));

  const [routeAction, setRouteAction] = useState<RouteAction>(null);
  // CR-192-BRC10 (MQ-033 task 11) — the routes ticked for one *Set read
  // format* move. Whole rows, because the dialog narrows its picker to the
  // selection's one shared service when there is one.
  const [pickedRoutes, setPickedRoutes] = useState<RouteRow[]>([]);
  const [formatDialog, setFormatDialog] = useState(false);
  const [cycleDelete, setCycleDelete] = useState<CycleRow | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const readOnlyTitle = props.readOnly ? t("settings.readOnlyReason") : undefined;
  const dash = t("settings.unwiredCount");

  // ── The two capability rows (BR-SHL-010) ────────────────────────────────
  // ── CR-045 wave D · D.6 + D.7 (DEF-1702) — the two filter vocabularies ──
  //
  // ⚠ **BOTH DIMENSIONS ON BOTH TABLES ARE APPLIED BY THE SERVER, AND THAT IS
  //    THE WHOLE POINT OF THE TASK.** `FilterBar` edits `state.filters`;
  //    `getRoutesPage`/`getCyclesPage` go through `listPage`, which serializes
  //    every entry as `f.<name>` (BR-SHL-011); `selectors.routes_queryset` and
  //    `selectors.cycles_queryset` AND-combine them in SQL. A control that
  //    narrowed the rows already in the browser would show a subset of a
  //    subset — worse than the bare toolbar this defect is about.
  //
  // Every label and every option word below ALREADY EXISTS in all eleven
  // catalogues: this screen's own column headings and value pills are the same
  // vocabulary, so the wave adds no i18n key here at all.
  const lifecycleFilterOptions = useMemo(
    () =>
      // BR-MET-076's three, in lifecycle order. On CYCLES this is the STORED
      // `status` column, which the row exposes as `lifecycle_status` and the
      // table draws under the Status heading — NOT `CycleRow.status`, which is
      // the operational progress of the current period and is not filterable.
      (["draft", "active", "inactive"] as const).map((code) => ({
        value: code,
        label: t(`settings.routes.status.${code}`),
      })),
    [t],
  );

  // D.7's vocabulary — the eight business words (B17 §2). The SERVER folds each
  // onto both generations of the spelling (`schedule.business_frequency` +
  // `LEGACY_FREQUENCIES`), so sending "Monthly" also matches a row still
  // holding CR-006's `monthly`. Sending the word rather than the enum is what
  // makes that fold reachable — there is one mapping, on the server.
  const frequencyFilterOptions = useMemo(
    () =>
      CYCLE_FREQUENCY_WORDS.map((word) => ({
        value: word,
        label: t(`settings.cycles.frequency.${word.toLowerCase()}`),
      })),
    [t],
  );

  // D.6's `cycle` vocabulary. `routes_queryset` matches `cycle__code__iexact`
  // OR `cycle_id`, so the CODE is the value — it is what the Cycle column
  // already shows and what reads honestly inside a chip.
  //
  // ⚠ **ITS OWN QUERY, ON ITS OWN STABLE KEY, AND NOT `cyclesQuery`.** That one
  // is keyed on `cycleState`, so the moment a user filtered the CYCLES table
  // the ROUTES table's cycle vocabulary would shrink to the filtered set and
  // options would start disappearing from a panel on another sub-tab.
  const cycleOptionsQuery = useQuery({
    queryKey: cycleVocabularyKey,
    queryFn: () => getCyclesPage(defaultRequestState(CYCLE_VOCABULARY_CONFIG), client),
    enabled: active === "routes",
  });
  const cycleFilterOptions = useMemo(
    () =>
      (cycleOptionsQuery.data?.rows ?? []).map((row) => ({
        value: row.code,
        label: row.code,
      })),
    [cycleOptionsQuery.data],
  );

  // ⚠ EVERY COLUMN KEY IS THE SERVED FIELD'S OWN NAME. `DataTable`'s accessor
  // is `row[col.key]` and the sort adapter compares the same field, so a key
  // that drifted from the field would sort a column by nothing at all — the
  // silent kind of bug this repo files as "the check cannot fail".
  const routeConfig: TableConfig<RouteRow> = useMemo(
    () => ({
      screenId: "SET-05",
      getRowId: (row) => row.id,
      searchFields: ["code", "name"],
      searchPlaceholder: "settings.routes.searchPlaceholder",
      // CR-045 wave D · D.6 — `ROUTE_FILTERS` already carries both
      // ("cycle", "type", "status", "service", "area"), so this is the
      // FRONTEND half of a leg the server has answered since CR-006.
      filters: [
        {
          name: "cycle",
          label: t("settings.routes.col.cycle"),
          options: cycleFilterOptions,
        },
        {
          name: "status",
          label: t("settings.routes.col.status"),
          options: lifecycleFilterOptions,
        },
      ],
      defaultSort: { sort: "code", dir: "asc" },
      columns: [
        // CR-192-BRC10 — DataTable has no built-in selection, so the checkbox
        // is a CELL, exactly as the reads list and the asset register do it.
        {
          key: "select",
          label: t("metering.reads.col.select"),
          cell: (row) => (
            <input
              type="checkbox"
              aria-label={t("settings.readFormats.bulk.selectRoute", { code: row.code })}
              checked={pickedRoutes.some((picked) => picked.id === row.id)}
              disabled={props.readOnly}
              title={readOnlyTitle}
              onChange={(event) =>
                setPickedRoutes((current) =>
                  event.target.checked
                    ? [...current, row]
                    : current.filter((picked) => picked.id !== row.id),
                )
              }
            />
          ),
        },
        {
          key: "code",
          label: t("settings.routes.col.routeNo"),
          identity: true,
          sortable: true,
          cell: (row) => (
            <Link className="text-accent underline" to={tenantPath(routeDetailPath(row.id))}>
              {row.code}
            </Link>
          ),
        },
        { key: "name", label: t("settings.routes.col.name"), sortable: true },
        {
          key: "route_type",
          label: t("settings.routes.col.type"),
          sortable: true,
          cell: (row) =>
            row.route_type === null ? dash : t(`settings.routes.type.${row.route_type}`),
        },
        {
          // CR-029 D10 — *"yes it will be multi service"*. RT-001 is
          // "Water + Electric", so the cell is a chip LIST and not a word.
          key: "services",
          label: t("settings.routes.col.services"),
          cell: (row) => (
            <ChipList
              items={row.services}
              empty={<span className={RC_MUTED}>{t("settings.routes.wizard.serviceAll")}</span>}
            />
          ),
        },
        {
          key: "area_code",
          label: t("settings.routes.col.area"),
          sortable: true,
          cell: (row) => row.area_name ?? row.area_code ?? dash,
        },
        {
          key: "members",
          label: t("settings.routes.col.members"),
          numeric: true,
          sortable: true,
          cell: (row) =>
            t("settings.routes.membersCell", { premises: row.premises, units: row.units }),
        },
        // BR-MET-075: this is available MINUS exclusions.
        { key: "meters", label: t("settings.routes.col.meters"), numeric: true, sortable: true },
        {
          key: "cycle_code",
          label: t("settings.routes.col.cycle"),
          sortable: true,
          cell: (row) =>
            row.cycle_id === null || row.cycle_code === null ? (
              <span className={RC_MUTED}>{dash}</span>
            ) : (
              <Link className="text-accent underline" to={tenantPath(cycleDetailPath(row.cycle_id))}>
                {row.cycle_code}
              </Link>
            ),
        },
        {
          key: "status",
          label: t("settings.routes.col.status"),
          sortable: true,
          cell: (row) => (
            <StatusPill tone={lifecycleTone(row.status)}>
              {t(`settings.routes.status.${row.status}`)}
            </StatusPill>
          ),
        },
        {
          key: "actions",
          label: t("settings.reference.col.actions"),
          cell: (row) => (
            <RowActions>
              <RowAction
                label={t("settings.routes.editAction", { code: row.code })}
                icon={<PencilIcon />}
                reason={readOnlyTitle ?? null}
                onClick={() => navigate(tenantPath(routeWizardPath(row.id)))}
              />
              <RowAction
                label={t("settings.reference.deactivate")}
                icon={<PowerIcon />}
                reason={
                  readOnlyTitle ??
                  (row.status !== "active" ? t("settings.routes.alreadyInactive") : null)
                }
                onClick={() => setRouteAction({ route: row, kind: "deactivate" })}
              />
              {/* B14 rule 6 — the DANGER tier lives on the CONFIRM inside the
                  dialog; the row action is its ghost sibling. */}
              <RowAction
                label={t("settings.reference.delete")}
                icon={<TrashIcon />}
                hint={t("settings.routes.deleteTooltip")}
                reason={readOnlyTitle ?? null}
                danger
                onClick={() => setRouteAction({ route: row, kind: "delete" })}
              />
            </RowActions>
          ),
        },
      ],
    }),
    [
      t,
      dash,
      readOnlyTitle,
      navigate,
      tenantPath,
      cycleFilterOptions,
      lifecycleFilterOptions,
      pickedRoutes,
      props.readOnly,
    ],
  );

  const cycleConfig: TableConfig<CycleRow> = useMemo(
    () => ({
      screenId: "SET-05.cycles",
      getRowId: (row) => row.id,
      searchFields: ["code", "name"],
      searchPlaceholder: "settings.cycles.searchPlaceholder",
      // CR-045 wave D · D.7 — `status` was already served; `frequency` is the
      // leg this wave added (`selectors.cycles_queryset`), and it is the one
      // dimension SET-05.cycles most obviously offers: the column was
      // SORTABLE and not filterable.
      filters: [
        {
          name: "frequency",
          label: t("settings.cycles.col.frequency"),
          options: frequencyFilterOptions,
        },
        {
          name: "status",
          label: t("settings.routes.col.status"),
          options: lifecycleFilterOptions,
        },
      ],
      defaultSort: { sort: "code", dir: "asc" },
      columns: [
        {
          key: "code",
          label: t("settings.cycles.col.cycleNo"),
          identity: true,
          sortable: true,
          cell: (row) => (
            <Link className="text-accent underline" to={tenantPath(cycleDetailPath(row.id))}>
              {row.code}
            </Link>
          ),
        },
        { key: "name", label: t("settings.cycles.col.name"), sortable: true },
        {
          // B17 §2 — one of eight business words. `frequencyLabel` folds the
          // legacy spellings so a row written before RC-W1 renders a WORD and
          // not the raw catalogue key it used to render.
          key: "frequency",
          label: t("settings.cycles.col.frequency"),
          sortable: true,
          cell: (row) => frequencyLabel(row.frequency, translate, dash),
        },
        {
          key: "start_day",
          label: t("settings.cycles.col.startDay"),
          numeric: true,
          // ⚠ SORTS ON THE STORED COLUMN, because that is the only one the
          // server can order by — `effective_start_day` is derived per row and
          // has no index behind it. Stated rather than silently mismatched:
          // for the cycles whose two days disagree, the sort is by the stored
          // number while the cell shows the effective one.
          sortable: true,
          cell: (row) => <StartDayCell cycle={row} t={translate} dash={dash} />,
        },
        {
          key: "days_to_complete",
          label: t("settings.cycles.col.daysToComplete"),
          numeric: true,
          sortable: true,
          cell: (row) => orDash(row.days_to_complete, dash),
        },
        {
          key: "routes",
          label: t("settings.cycles.col.routes"),
          cell: (row) => (
            <ChipList items={row.routes} empty={<span className={RC_MUTED}>{dash}</span>} />
          ),
        },
        // BR-MET-078 — the LAST numeric column on this table is a COUNT of
        // accounts. There is no balance, no amount and no fee, and the suite
        // asserts their absence rather than trusting the reviewer's eye.
        { key: "accounts", label: t("settings.cycles.col.accounts"), numeric: true, sortable: true },
        {
          key: "lifecycle_status",
          label: t("settings.routes.col.status"),
          sortable: true,
          cell: (row) => (
            <StatusPill tone={lifecycleTone(row.lifecycle_status)}>
              {t(`settings.routes.status.${row.lifecycle_status}`)}
            </StatusPill>
          ),
        },
        {
          key: "actions",
          label: t("settings.reference.col.actions"),
          cell: (row) => (
            <RowActions>
              <RowAction
                label={t("settings.cycles.editAction", { code: row.code })}
                icon={<PencilIcon />}
                reason={readOnlyTitle ?? null}
                onClick={() => navigate(tenantPath(cycleWizardPath(row.id)))}
              />
              <RowAction
                label={t("settings.reference.delete")}
                icon={<TrashIcon />}
                hint={t("settings.cycles.deleteTooltip")}
                reason={readOnlyTitle ?? null}
                danger
                onClick={() => setCycleDelete(row)}
              />
            </RowActions>
          ),
        },
      ],
    }),
    // eslint-disable-next-line -- the two filter vocabularies join the memo:
    // a stale closure here would freeze the panel's options at first render.
    [
      t,
      translate,
      dash,
      readOnlyTitle,
      navigate,
      tenantPath,
      frequencyFilterOptions,
      lifecycleFilterOptions,
    ],
  );

  const [routeState, setRouteState] = useState<TableRequestState>(() =>
    defaultRequestState(routeConfig),
  );
  const [cycleState, setCycleState] = useState<TableRequestState>(() =>
    defaultRequestState(cycleConfig),
  );

  const routesQuery = useQuery({
    queryKey: routesPageKeyFor(routeState),
    queryFn: () => getRoutesPage(routeState, client),
    enabled: active === "routes",
  });
  const cyclesQuery = useQuery({
    queryKey: cyclesPageKeyFor(cycleState),
    queryFn: () => getCyclesPage(cycleState, client),
    enabled: active === "cycles",
  });
  // BR-MET-080 — the landing coverage sentence. No route ids: the question is
  // "how many accounts sit on NO cycle at all", tenant-wide.
  const coverageQuery = useQuery({
    queryKey: landingCoverageKey,
    queryFn: () => getCycleCoverage([], client),
    enabled: active === "cycles",
  });

  function refreshAll(): void {
    void queryClient.invalidateQueries({ queryKey: routesPageKey });
    void queryClient.invalidateQueries({ queryKey: cyclesPageKey });
    void queryClient.invalidateQueries({ queryKey: landingCoverageKey });
  }

  const routeMutation = useMutation({
    mutationFn: (input: { route: RouteRow; kind: "deactivate" | "delete" }) =>
      input.kind === "deactivate"
        ? deactivateRoute(input.route.id, client).then(() => undefined)
        : deleteRoute(input.route.id, client),
    onSuccess: (_result, input) => {
      refreshAll();
      setRouteAction(null);
      setRefusal(null);
      fireToast(
        t(input.kind === "deactivate" ? "settings.routes.deactivated" : "settings.routes.deleted", {
          code: input.route.code,
        }),
      );
    },
    onError: (error: unknown) => {
      // BR-MET-008/079: "412 meters on this route — deactivate instead" and
      // "1,204 reads reference this route" are the SERVER's sentences, with
      // the SERVER's counts. This screen renders the refusal; it never
      // pre-judges which guard will fire.
      setRouteAction(null);
      setRefusal(refusalOf(error, translate));
    },
  });

  const cycleMutation = useMutation({
    mutationFn: (cycle: CycleRow) => deleteCycle(cycle.id, client),
    onSuccess: (_void, cycle) => {
      refreshAll();
      setCycleDelete(null);
      setRefusal(null);
      fireToast(t("settings.cycles.deleted", { code: cycle.code }));
    },
    onError: (error: unknown) => {
      setCycleDelete(null);
      setRefusal(refusalOf(error, translate));
    },
  });

  const pageQuery = active === "routes" ? routesQuery : cyclesQuery;
  if (pageQuery.data === undefined && isPermissionDenied(pageQuery.error)) {
    return <SettingsDenied helper={t("settings.denied.tab")} />;
  }

  const impact =
    routeAction === null
      ? null
      : deactivationImpact(routeAction.route, cyclesQuery.data?.rows ?? []);

  function selectSubTab(next: RoutesCyclesSubTab): void {
    const params = new URLSearchParams(search);
    params.set(ROUTES_CYCLES_SUB_TAB_PARAM, next);
    setSearch(params, { replace: true });
  }

  // B14 rule 21 — utilities. The sub-tab strip is a real `role="tablist"`, the
  // same shape the Configure strip above it uses, so the two read as one thing.
  const subTabClass = (id: RoutesCyclesSubTab): string =>
    [
      "cursor-pointer border-none bg-transparent px-3 py-2 text-btn font-semibold",
      id === active
        ? "border-b-2 border-b-accent text-accent"
        : `border-b-2 border-b-transparent ${RC_MUTED}`,
    ].join(" ");

  return (
    <div className="flex flex-col gap-4">
      <RefusalNotice refusal={refusal} />

      <div
        className="flex gap-1 border-b border-b-divider"
        role="tablist"
        aria-label={t("settings.routesCycles.subTabsLabel")}
      >
        {(["routes", "cycles"] as const).map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={id === active}
            className={subTabClass(id)}
            onClick={() => selectSubTab(id)}
          >
            {t(`settings.routesCycles.subTab.${id}`)}
          </button>
        ))}
      </div>

      <div className="flex items-start justify-between gap-4">
        <div>
          <Kicker>{t(active === "routes" ? "settings.routes.kicker" : "settings.cycles.kicker")}</Kicker>
          <p className={RC_DESC}>
            {t(active === "routes" ? "settings.routes.lede" : "settings.cycles.lede")}
          </p>
          {/* BR-MET-080 · D13 — the landing coverage sentence, and it names what
              the accounts LACK. There is no "Assign a cycle" anywhere in this
              product: an account's cycle is DERIVED account → unit → route →
              cycle at bill-run time, so the remedy is to ROUTE them. */}
          {active === "cycles" && coverageQuery.data !== undefined && (
            <p className={`${RC_DESC} mt-1`} data-rc="coverage-sentence">
              {t(coverageSentenceKey(coverageQuery.data.uncovered_accounts), {
                count: coverageQuery.data.uncovered_accounts,
              })}
            </p>
          )}
        </div>
        {/* B14 rule 4 — `+ Noun` opens a creator. W3-T5: it NAVIGATES now, so
            the wizard has a URL and a refresh mid-flow keeps the step. */}
        <Button
          variant="primary"
          disabled={props.readOnly}
          title={readOnlyTitle}
          onClick={() =>
            navigate(
              tenantPath(active === "routes" ? routeWizardPath(null) : cycleWizardPath(null)),
            )
          }
        >
          {t(active === "routes" ? "settings.routes.add" : "settings.cycles.add")}
        </Button>
      </div>

      {/* ⚠ **`key` IS THE FIX FOR A DEFECT, NOT A LINT TIDY-UP (W5-T8).**
          Both branches put a `DataTable` at the same position under the same
          parent, so React reconciles them as ONE component and keeps its
          state — including `internalVisible`, which `DataTable` initialises
          ONCE from `defaultVisibleColumns(config)`. Landing on Routes and
          clicking Cycles therefore carried the ROUTES column keys into the
          cycles table, whose own defensive line then dropped every key it does
          not declare (BR-SHL-024). The result was the INTERSECTION — Cycle # ·
          Name · Actions — six of B17 §4's nine columns gone, on the only path
          a user actually takes. Found in Chromium by the W5-T8 walkthrough;
          every suite was green because each renders one sub-tab.
          A distinct `key` makes them two components, which is what they are.
          `SettingsRoutesCyclesSubTabs.dom.test.tsx` holds it. */}
      {/* CR-192-BRC10 (MQ-033 task 11) — one *Set read format* move for the
          ticked routes (`PUT routes/read-format`), in the kit's selection row. */}
      {active === "routes" && pickedRoutes.length > 0 && (
        <SelectionToolbar
          label={t("settings.readFormats.bulk.selected", { n: pickedRoutes.length })}
          count={t("settings.readFormats.bulk.selected", { n: pickedRoutes.length })}
        >
          <Button variant="secondary" size="sm" onClick={() => setFormatDialog(true)}>
            {t("settings.readFormats.bulk.open")}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setPickedRoutes([])}>
            {t("settings.readFormats.bulk.clear")}
          </Button>
        </SelectionToolbar>
      )}
      {formatDialog && (
        <RoutesReadFormatDialog
          routeIds={pickedRoutes.map((route) => route.id)}
          services={[...new Set(pickedRoutes.flatMap((route) => route.services))]}
          client={client}
          onClose={() => setFormatDialog(false)}
          onDone={(updated) => {
            setFormatDialog(false);
            setPickedRoutes([]);
            fireToast(t("settings.readFormats.bulk.done", { n: updated }));
          }}
        />
      )}
      {active === "routes" ? (
        <DataTable
          key="routes"
          config={routeConfig}
          // CR-045 wave D · D.6 (DEF-1702) — G45's other half. Declaring
          // `filters` without passing this slot is dead configuration: it
          // type-checks, renders nothing and every test passes, which is the
          // exact shape DEF-1701 was filed for on four other screens.
          filterBarSlot={
            <FilterBar
              filters={offerableFilters(routeConfig.filters ?? [])}
              state={routeState}
              onStateChange={setRouteState}
            />
          }
          // ── CR-045 wave E (DEF-1707) ─────────────────────────────────────
          // ⚠ **THE `routes` EXPORT RESOURCE HAS EXISTED ALL ALONG AND NOTHING
          //    DREW ITS BUTTON.** `apps/metering/exports.register()` registers
          //    it beside premises, units and reads, and
          //    `test_be_list_export_routes_and_cycles_columns` already proves
          //    the produced BYTES — header row and values, read back off the
          //    written file. The capability was real, byte-proven, and
          //    unreachable: the DEF-1701 shape, one slot over.
          //
          //    It posts THIS table's request state, so a filtered list exports
          //    filtered (BR-SHL-016 — the server re-does nothing about the cap
          //    or the file). The export vocabulary is registered FROM
          //    `ROUTE_FILTERS`, the same tuple the list endpoint reads, so an
          //    export can never honour a filter the list ignores.
          downloadSlot={
            <ListExportButton resource="routes" state={routeState} client={client} />
          }
          state={routeState}
          onStateChange={setRouteState}
          rows={routesQuery.data?.rows ?? []}
          totalRows={routesQuery.data?.total ?? null}
          loading={routesQuery.isPending}
          error={
            routesQuery.data === undefined && routesQuery.error != null
              ? {
                  reason: apiErrorText(routesQuery.error, translate),
                  onRetry: () => void routesQuery.refetch(),
                }
              : null
          }
          empty={{
            title: t("settings.routes.emptyTitle"),
            helper: t("settings.routes.emptyBody"),
            ctaLabel: t("settings.routes.add"),
            ctaReason: readOnlyTitle ?? null,
            onCta: () => navigate(tenantPath(routeWizardPath(null))),
          }}
        />
      ) : (
        <DataTable
          key="cycles"
          config={cycleConfig}
          // CR-045 wave D · D.7 (DEF-1702) — the second table's own slot. G45
          // COUNTS declarations against passes precisely because this file has
          // two of each: a `"filterBarSlot" in text` check would go green with
          // this one missing.
          filterBarSlot={
            <FilterBar
              filters={offerableFilters(cycleConfig.filters ?? [])}
              state={cycleState}
              onStateChange={setCycleState}
            />
          }
          // CR-045 wave E — the `cycles` resource, registered in the same call
          // and proved by the same test. Its export vocabulary comes from
          // `CYCLE_FILTERS`, which gained `frequency` in this same wave, so the
          // Frequency chip narrows the FILE as well as the screen.
          downloadSlot={
            <ListExportButton resource="cycles" state={cycleState} client={client} />
          }
          state={cycleState}
          onStateChange={setCycleState}
          rows={cyclesQuery.data?.rows ?? []}
          totalRows={cyclesQuery.data?.total ?? null}
          loading={cyclesQuery.isPending}
          error={
            cyclesQuery.data === undefined && cyclesQuery.error != null
              ? {
                  reason: apiErrorText(cyclesQuery.error, translate),
                  onRetry: () => void cyclesQuery.refetch(),
                }
              : null
          }
          empty={{
            title: t("settings.cycles.emptyTitle"),
            helper: t("settings.cycles.emptyBody"),
            ctaLabel: t("settings.cycles.add"),
            ctaReason: readOnlyTitle ?? null,
            onCta: () => navigate(tenantPath(cycleWizardPath(null))),
          }}
        />
      )}

      {routeAction !== null && (
        // BR-SHL-032: the confirm button names the action. B14 rule 6: the
        // shared dialog renders a destructive confirm in the danger tier.
        <ConfirmDialog
          // B14 rule 6 (DEF-718): BOTH actions this dialog serves — deactivate and delete — are destructive.
          confirmVariant="danger"
          title={t(
            routeAction.kind === "deactivate"
              ? "settings.routes.deactivateTitle"
              : "settings.routes.deleteTitle",
            { code: routeAction.route.code },
          )}
          consequence={
            routeAction.kind === "deactivate" && impact !== null
              ? t(
                  impact.from === null
                    ? "settings.routes.deactivateInCycleNoWindow"
                    : "settings.routes.deactivateInCycle",
                  {
                    code: routeAction.route.code,
                    cycle: impact.cycle,
                    from: impact.from,
                    to: impact.to,
                    premises: impact.premises,
                  },
                )
              : t(
                  routeAction.kind === "deactivate"
                    ? "settings.routes.deactivateBody"
                    : "settings.routes.deleteBody",
                  { code: routeAction.route.code, members: routeAction.route.members },
                )
          }
          confirmLabel={t(
            routeAction.kind === "deactivate"
              ? "settings.routes.deactivateAction"
              : "settings.routes.deleteAction",
            { code: routeAction.route.code },
          )}
          working={routeMutation.isPending}
          onConfirm={() => routeMutation.mutate(routeAction)}
          onCancel={() => setRouteAction(null)}
        />
      )}

      {cycleDelete !== null && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): delete a cycle.
          confirmVariant="danger"
          title={t("settings.cycles.deleteTitle", { code: cycleDelete.code })}
          consequence={t("settings.cycles.deleteBody", { code: cycleDelete.code })}
          confirmLabel={t("settings.cycles.deleteAction", { code: cycleDelete.code })}
          working={cycleMutation.isPending}
          onConfirm={() => cycleMutation.mutate(cycleDelete)}
          onCancel={() => setCycleDelete(null)}
        />
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-006 (SET-05/06/07) — the five PO rulings of 2026-08-16 · REBUILT by CR-029 RC-W3-T1/T2 (B17 §7)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane); REWRITTEN 2026-08-17 for CR-006; REBUILT 2026-08-23 for CR-029 RC-W3
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest (SettingsRoutesCyclesTab.test.tsx + SettingsRoutesCycles.cr029.test.tsx)
// [CR-029 RC-W6b 2026-08-23] AMENDED — **OQ-340 AND OQ-341 ARE RULED, AND BOTH RULINGS LAND ON THIS SCREEN AS HONESTY WORK.** OQ-340 (*"A: first window 15–17 Sep (start day becomes decorative)"*): the engine anchors on the FIRST RUN and deliberately does NOT rewrite `cycles.start_day`, so the stored day can describe nothing the product does. The Start-day column, `readWindowLabel` and the deactivate confirmation's quoted window all render `effective_start_day` (SERVED — `period_engine.effective_start_day`; nothing here computes a day) and SAY that the saved number is not the one used, rather than silently swapping it: hiding the swap would hide that the operator's own field is being ignored. OQ-341 (*"you give warning and if user override; let them do it"* — the PO amended their own option B inside the ruling): `schedule_warning` is rendered as a translated sentence keyed on its CODE, BESIDE the real overlapping windows and never instead of them. RED-first proven by breaking each: `effectiveStartDay` returning the stored day fails four assertions (*expected 'Starts…1…' to contain '15'*, *expected '1–3' to be '15–17'*), and `scheduleWarningKey` returning null fails the warning's.
// exceptions: E3 [CR-029 RC-W3] `GET /routes` and `GET /cycles` do NOT paginate or sort server-side — D7 rules that they should and that half is a BACKEND task, reported. `getRoutesPage`/`getCyclesPage` send the BR-SHL-011 params and read the response SHAPE, so the pager's "Showing 1–50 of N" is true today and the client-side window disappears with nothing edited here the day the endpoint lands · E3 the landing coverage sentence calls `GET /cycles/coverage` with NO route ids, which is the tenant-wide "on no cycle" count; the uncovered LIST has no endpoint (SET-07D states that absence) · E4 three row actions rather than "max 2 + overflow" — r10's SET-05 draws edit and deactivate and delete is the third the capability matrix declares; an overflow menu for one item is a click for nothing · E3 NO browser walkthrough has happened for this rebuild (hard-won law 6)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
