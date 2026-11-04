// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-001 (the Plans list: columns, search, filters, sort, row actions) ·
//           US-RAT-003 (lifecycle + versioning maintenance from the row actions)
//           Screens: S9 (Plans tab) → S10
// Rules:    BR-RAT-012/027 (base charges are the SERVER's derived Σ) · BR-RAT-024 (service
//           vocabulary ⊆ the tenant catalog) · BR-RAT-025 (plan-as-bundle) · BR-RAT-030
//           (draft → published → archived; only published plans are assignable) ·
//           BR-RAT-031 (publishing is the gate — no approve control exists, as-modified) ·
//           BR-RAT-037 (a published plan is never edited in place — a new version with a
//           reason) · BR-SHL-010 (the capability row IS the table config) · BR-SHL-011
//           (q/sort/dir/page/per/f.<name> URL grammar) · BR-SHL-012 (the six A18 states) ·
//           BR-SHL-020 (plain-language failure) · BR-SHL-025 (a forbidden control renders
//           disabled WITH its reason) · BR-SHL-032 (a confirm NAMES the action) ·
//           BR-SHL-034 (dates via the shared formatter)
// ───────────────────────────────────────────────────────
// The S9 Plans tab.
//
// ⚠ **REBUILT 2026-10-03 FROM IMAGES 01–03 (CR-167-BRC10 round 2 task 6,
// DEF-RAT-9333).** Columns: Plan (name, and `CODE · Class` under it) · Version
// · Services · Schedules · Base charges · Units · From · To · Status · open.
// No paragraph above the table (the plans explainer is retired from every
// catalogue). The row's one action OPENS the plan; the four lifecycle actions
// that sat on every row moved to where the drawing puts them (CR-167 §5.3) and
// the confirm dialog went with them. Cells live in `planListParts.tsx` (B14
// rule 43). The paragraphs below are this file's history.
//
// What is deliberately ABSENT from this file: any control called Approve. The
// board-approval workflow was REMOVED (BR-RAT-031 as-modified, PO R5-1) —
// approval happens outside the system — so publishing IS the gate. A disabled
// "Approve" button would imply a permission could unlock it; none can, and the
// API has no route behind it. The test suite scans the rendered DOM for one.
//
// The money law here: `base_charges` is a decimal STRING the server already
// summed (BR-RAT-027). This file renders it through MoneyCell and never adds
// two bases together — the Σ on screen is the Σ the server computed.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { PLAN_STATUSES, getPlans, getTenantServices } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { DataTable } from "@/components/DataTable";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { MoneyCell } from "@/components/MoneyCell";
import { FailedWithRetry, PermissionDenied } from "@/components/StateFrame";
import { EyeIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { ListExportButton } from "@/features/exports/ListExportButton";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  DASH,
  PlanNameCell,
  PlanVersionTag,
  planListClasses,
  planListSchedules,
  planListUnits,
} from "./planListParts";
import type { PlanListRow } from "./planListParts";
import {
  activatedServiceOptions,
  DASHBOARD_ROUTE,
  GuardedButton,
  PLANS_RATES_ROUTE,
  planStatusTone,
  RatingStatusPill,
  ServiceTags,
} from "./ratingShared";
import type { RatingTabRender, Translator } from "./ratingShared";
import { TaxDateCell } from "./taxListParts";
import { planDetailRoute } from "./planDetail/planDetailModel";

// ── Routes into S10 ────────────────────────────────────────────────────────

/**
 * `plan_services.currency` is per SERVICE row, and `GET /plans` serves the
 * derived Σ as a bare amount with no currency beside it (it sums amounts, not
 * currencies). Every tenant's plan-service rows default to USD server-side and
 * BR-TEN-042 locks a tenant to one currency, so the list echoes that default
 * rather than inventing a per-row guess. GAP reported: the list row should
 * carry the Σ's currency.
 */
export const PLAN_BASE_CURRENCY = "USD";

export const NEW_PLAN_ROUTE = `${PLANS_RATES_ROUTE}/plans/new`;

// PLN-02, the plan DETAIL — what the list's name and its one open action both
// reach (CR-167 images 01, 24). Its address is `planDetailRoute`, ONE helper:
// this file carried a second, unencoded copy (`planRoute`) until the record-
// links lane (2026-10-19) merged the two.

/** PLN-03 in edit mode — one segment below the detail, reached from the detail's Edit. */
export function planEditRoute(planId: string): string {
  return `${PLANS_RATES_ROUTE}/plans/${planId}/edit`;
}

// ── Pure pieces (provable without a browser or a network) ──────────────────

/**
 * Images 01–03's nine columns plus the open action, in the drawn order:
 * Plan · Version · Services · Schedules · Base charges · Units · From · To ·
 * Status · ›.
 *
 * ⚠ **EVERY SORTABLE HEAD IS A SORT THE SERVER RUNS (NFR-3)** — CR-167 §7.3's
 * `name · version · units · effective_from · effective_to · status`. Base
 * charges is NOT sortable, by ruling (`BR-RAT-1040`, closing `DEF-RAT-6927`):
 * the figure is a walk, not a column. DO NOT ADD `sortable: true` BACK.
 *
 * ⚠ **NO ACCOUNTS COLUMN.** A plan attaches to UNITS (PO ruling 2 on the
 * drawing: *"Units, not Accounts, because a plan attaches to units"*).
 *
 * ⚠ **THE ROW'S LIFECYCLE ACTIONS HAVE MOVED, NOT GONE (CR-167 §5.3):** New
 * version → the details page's Edit (L10); Archive → details · Retire (L11);
 * Publish a draft → the draft's Review · *Publish plan* (L12); Delete a draft →
 * the details page, on a draft only (L13).
 */
export function planTableConfig(
  t: Translator,
  serviceOptions: { value: string; label: string }[],
  cells: {
    name: (row: PlanListRow) => JSX.Element;
    version: (row: PlanListRow) => JSX.Element;
    services: (row: PlanListRow) => JSX.Element;
    schedules: (row: PlanListRow) => JSX.Element | string;
    base: (row: PlanListRow) => JSX.Element;
    units: (row: PlanListRow) => JSX.Element | string;
    from: (row: PlanListRow) => JSX.Element;
    to: (row: PlanListRow) => JSX.Element;
    status: (row: PlanListRow) => JSX.Element;
    open: (row: PlanListRow) => JSX.Element;
  },
): TableConfig<PlanListRow> {
  return {
    screenId: "S9.plans",
    columns: [
      {
        key: "name",
        label: t("rating.plans.col.plan"),
        sortable: true,
        identity: true,
        cell: cells.name,
      },
      { key: "version", label: t("rating.plans.list.col.version"), sortable: true, cell: cells.version },
      { key: "services", label: t("rating.plans.list.col.services"), cell: cells.services },
      {
        key: "schedules",
        label: t("rating.plans.list.col.schedules"),
        numeric: true,
        cell: cells.schedules,
      },
      { key: "base_charges", label: t("rating.plans.col.base"), numeric: true, cell: cells.base },
      {
        key: "units",
        label: t("rating.plans.col.units"),
        sortable: true,
        numeric: true,
        cell: cells.units,
      },
      {
        key: "effective_from",
        label: t("rating.plans.list.col.from"),
        sortable: true,
        cell: cells.from,
      },
      { key: "effective_to", label: t("rating.plans.list.col.to"), sortable: true, cell: cells.to },
      { key: "status", label: t("rating.plans.col.status"), sortable: true, cell: cells.status },
      { key: "actions", label: "", locked: true, cell: cells.open },
    ],
    getRowId: (row) => row.id,
    searchFields: ["name", "code"], // server-side, `Q(name) | Q(code)`
    // B14 rule 19 (DEF-510): names the two fields the server searches.
    searchPlaceholder: "rating.plans.searchPlaceholder",
    filters: [
      {
        name: "status",
        label: t("rating.plans.filter.status"),
        options: PLAN_STATUSES.map((status) => ({
          value: status,
          label: t(`rating.plan.status.${status}`),
        })),
      },
      { name: "service", label: t("rating.filter.service"), options: serviceOptions },
    ],
    defaultSort: { sort: "name", dir: "asc" },
  };
}

/** The table's request state → the list wrapper's params. One translation. */
export function planParamsFrom(state: TableRequestState) {
  return {
    q: state.q,
    filters: state.filters,
    sort: state.sort,
    dir: state.dir,
    page: state.page,
    per: state.per,
  };
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface PlansTabProps {
  readOnly: boolean;
  client?: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** US-SHL-020 addendum r2 — the tab hands its own button up to the frame. */
  render: RatingTabRender;
}

export function PlansTab(props: PlansTabProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const [searchParams, setSearchParams] = useSearchParams();

  // BR-RAT-024: the filter vocabulary is the tenant's own service catalog.
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  // DEF-RAT-5691 — the tenant's OWN services, never the platform catalogue.
  const serviceOptions = activatedServiceOptions(servicesQuery.data);

  const regional = { timeZone: props.timeZone, dateFormat: props.dateFormat };
  const everyClass = t("rating.plan.customerClassEvery");

  const config = planTableConfig(translate, serviceOptions, {
    name: (row) => (
      <PlanNameCell
        row={row}
        to={tenantPath(planDetailRoute(row.id))}
        classes={planListClasses(row, everyClass)}
      />
    ),
    version: (row) => <PlanVersionTag version={row.version} />,
    services: (row) => <ServiceTags services={row.services} />,
    schedules: (row) => String(planListSchedules(row)),
    // BR-RAT-1040: the server's figure, rendered — never re-computed. `null`
    // means the figure cannot be stated, which is a dash and never $0.00.
    base: (row) =>
      row.base_charges === null ? (
        <span>{DASH}</span>
      ) : (
        <MoneyCell amount={row.base_charges} currency={PLAN_BASE_CURRENCY} />
      ),
    units: (row) => String(planListUnits(row)),
    from: (row) => <TaxDateCell value={row.effective_from} {...regional} />,
    to: (row) => <TaxDateCell value={row.effective_to} openEnd {...regional} />,
    // DEF-RAT-9319's lesson: a status word never breaks inside itself.
    status: (row) => (
      <span className="break-keep">
        <RatingStatusPill tone={planStatusTone(row.status)} stem="rating.plan.status" value={row.status} />
      </span>
    ),
    // B14 rule 15: one icon with an accessible name, and it OPENS the plan.
    open: (row) => (
      <RowActions>
        <RowAction
          label={t("rating.plans.list.open")}
          icon={<EyeIcon />}
          onClick={() => navigate(tenantPath(planDetailRoute(row.id)))}
        />
      </RowActions>
    ),
  });

  const state = parseTableParams(searchParams, config);
  const listKey = serializeTableParams(state, config).toString();

  const listQuery = useQuery({
    queryKey: queryKeys.plans(listKey),
    queryFn: () => getPlans(planParamsFrom(state), client),
  });
  const rows: PlanListRow[] = listQuery.data?.results ?? [];


  function setState(next: TableRequestState): void {
    setSearchParams(serializeTableParams(next, config), { replace: true });
  }

  // Both failures keep the header and strip, so the user can move elsewhere.
  if (listQuery.data === undefined && listQuery.isError) {
    if (isPermissionDenied(listQuery.error)) {
      return (
        <>
          {props.render({
            body: (
              <PermissionDenied
                helper={t("rating.denied")}
                onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
              />
            ),
          })}
        </>
      );
    }
    return (
      <>
        {props.render({
          body: (
            <FailedWithRetry
              title={t("rating.plans.failedTitle")}
              reason={apiErrorText(listQuery.error, translate)}
              onRetry={() => void listQuery.refetch()}
              onDownloadReport={() => undefined}
              onCancel={() => void listQuery.refetch()}
            />
          ),
        })}
      </>
    );
  }

  return (
    <>
      {props.render({
        // BR-SHL-025 / US-RAT-001 TC-6: a Clerk sees it, disabled, with why.
        action: (
          <GuardedButton
            readOnly={props.readOnly}
            readOnlyReason={t("rating.readOnlyReason")}
            variant="primary"
            onClick={() => navigate(tenantPath(NEW_PLAN_ROUTE))}
          >
            {t("rating.plans.new")}
          </GuardedButton>
        ),
        body: (
          // Image 01 draws no paragraph above the table. DEF-RAT-9341's lesson:
          // every header word stays whole in Japanese and Korean.
          <div className="flex flex-col gap-3 min-w-0 [&_thead_th]:break-keep" data-plan-list="">
            <DataTable<PlanListRow>
              config={config}
              state={state}
              onStateChange={setState}
              rows={rows}
              totalRows={listQuery.data?.count ?? null}
              loading={listQuery.isPending}
              filterBarSlot={
                <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
              }
              downloadSlot={
                // Plans are a MONEY table, so the server writes the BR-SHL-016
                // audit row — this control neither asks for that nor could
                // suppress it.
                <ListExportButton resource="plans" state={state} client={client} />
              }
              empty={{
                title: t("rating.plans.emptyTitle"),
                helper: t("rating.plans.emptyHelper"),
                ctaLabel: t("rating.plans.new"),
                ctaReason: props.readOnly ? t("rating.readOnlyReason") : undefined,
                onCta: () => navigate(tenantPath(NEW_PLAN_ROUTE)),
              }}
            />
          </div>
        ),
      })}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-001@6304a38 (story+rules snapshot hash — EP-RAT-01; co-story US-RAT-003@6304a38)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — S9 Plans tab) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [list-export lane 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E3 `GET /plans` serves the derived base at NUMERIC(18,6) STORAGE precision ("30.500000") while US-RAT-001 §5 says "display 2dp"; MoneyCell renders a decimal string exactly as received and never re-rounds (CLAUDE.md #2), so the column shows six places — reported as an API gap (the list row should carry the display-rounded Σ) rather than rounded on screen · E3 CLOSED (list-export lane 2026-08-10): EP-RAT-01's CSV export is WIRED to POST /exports (a MONEY table — the server writes the BR-SHL-016 audit row); the produced file still has no download route (`result_link` is a `file://` artifact path, IS-11/reports W5), so the completed state names the file · E3 SUPERSEDED 2026-08-21 (DEF-421/DEF-471): `GET /lookups/account_types` does NOT 404 — it serves four classes — and `PLAN_FILTERS` already carries `customer_class`, so the matrix's customer-class filter is undeclared rather than unavailable · E4 the derived base Σ is rendered in USD because `GET /plans` serves no currency beside it — reported as an API gap rather than guessed per row
// amended: 2026-10-03 CR-167-BRC10 round 2 task 6 — rebuilt from images 01–03 (DEF-RAT-9333); the row actions and their confirm moved to the details page and the draft's Review (§5.3)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
