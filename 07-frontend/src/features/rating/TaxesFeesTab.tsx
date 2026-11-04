// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-009 (the Taxes & fees catalog + the New/Edit Tax or Fee form)
//           Screens: S9 (Taxes & fees tab), S13
// Rules:    BR-RAT-005 (tax base = usage + base ONLY; fees and late are never taxed) ·
//           BR-RAT-006 (exemption is account-level, regardless of service) ·
//           BR-RAT-025 (D8: plans attach jurisdictions; rate_override NULL = the
//           jurisdiction rate) · BR-RAT-036 (three computation forms; the taxable-base
//           selector can express ONLY usage + base — the prototype's "Fees" and
//           "tax-on-tax" boxes are REMOVED; taxes never compound) · BR-RAT-042 (the
//           per-unit "applies above N units" threshold is MARGINAL) · BR-TEN-037
//           (jurisdictions are tenant-entered — there is no global registry) ·
//           BR-SHL-010/011/012/020/025/032/033/034
// ───────────────────────────────────────────────────────
// S9's Taxes & fees tab. **THE FORM BEHIND IT IS NO LONGER HERE.**
//
// ⚠ **REBUILT 2026-10-03 FROM IMAGES 01–03 (CR-165-BRC10 task 5,
// DEF-RAT-9274, P21–P28).** Columns: Tax or fee · Version · Applies to · Rate ·
// From · To · GL account · Premises · Status · open. No paragraph above the
// table; an over-20% banner whose count is the SERVER's (`taxListParts.tsx`);
// the row's one action opens the details page — the pencil to the edit door
// is gone, because it put a live tax's rate in an editable box. The toolbar is
// the kit's `+ Filter` (PO 2026-10-03, *"filter and not button for filters"*),
// which supersedes the drawn All · Active · Draft · Ended buttons. Its cells
// live in `taxListParts.tsx` (B14 rule 43). The two "Pure pieces" below are
// kept for their other readers: `taxRateDisplay` (the details page) and
// `taxAppliesToCell` (its tests).
//
// ⚠ THE E2 EXCEPTION THIS FILE CARRIED IS CLOSED (CR-013 P4, 2026-08-21). It
// read: *"US-RAT-009 models S13 as a FOUR-STEP guided form; the shared kit has
// ONE modal form and no modal wizard shell, so the steps render as labelled
// sections."* The PO answered it — **"Wizards for each type - no modal;"** — so
// S13 is `TaxWizard.tsx`, a full-page four-step route, and this tab holds the
// two DOORS to it: `+ New tax or fee` and the row's pencil. Nothing here opens
// a modal any more, and nothing points at one (hard-won law 2).
//
// The one thing this screen must NOT be able to express: a taxable base that
// includes fees, or a tax on a tax. B4.2 forbids both and BR-RAT-036 removed
// the prototype's checkboxes for them — so there are exactly two base toggles
// below (usage, base), the field says why, and the server refuses any other key
// as unknown. That is the difference between a rule and a habit.
//
// Rates are decimal STRINGS. `rate` is stored as a FRACTION (0.0625 = 6.25 %)
// and is shown and edited as that fraction with the fact stated on the field —
// multiplying by 100 on screen would be client-side money arithmetic on a value
// the engine reads verbatim.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { JURISDICTION_LEVELS, getTaxes, getTenantServices } from "@/api/endpoints";
import type { TaxRow } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { DataTable } from "@/components/DataTable";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { formatRateNumber } from "@/components/MoneyCell";
import { FailedWithRetry, PermissionDenied } from "@/components/StateFrame";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type {
  TableConfig,
  TableFilterConfig,
  TableRequestState,
} from "@/components/tableTypes";
import { ListExportButton } from "@/features/exports/ListExportButton";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import { EyeIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { useTenantPath } from "@/routing/tenantPath";

import { TAX_WIZARD_NEW_ROUTE, definitionPath } from "./definitionDetail";
import { DASHBOARD_ROUTE, GuardedButton, activatedServiceOptions } from "./ratingShared";
import type { RatingTabRender, Translator } from "./ratingShared";
import {
  OverTwentyBanner,
  TAX_LIST_STATUSES,
  TAX_OVER_20_FILTER,
  TaxAppliesToCell,
  TaxDateCell,
  TaxGlCell,
  TaxNameCell,
  TaxPremisesCell,
  TaxRateCell,
  TaxStatusCell,
  TaxVersionTag,
} from "./taxListParts";
import type { TaxListResult, TaxListRow } from "./taxListParts";

// ── Pure pieces ────────────────────────────────────────────────────────────

/**
 * DEF-387 / BR-RAT-103 — CR-013 part 4's landing column is
 * *"Status (Active/Draft/Scheduled/Expired)"*, and `inactive` is the fifth
 * value the product already had (IS-1 deactivate-first). Mirrors
 * `apps/rating/selectors.TAX_STATUSES`.
 *
 * ⚠ THE SCREEN INVENTORY'S OWN NOTE IS WORTH KEEPING IN VIEW: taxes are
 * *"a FOURTH status set, and it is a different one again"* — four objects, four
 * vocabularies, each with a reason. Anything that unifies them is wrong.
 */
export const TAX_STATUSES = ["active", "draft", "scheduled", "expired", "inactive"] as const;

// `taxFieldsFor`, `taxSchema` and `NEW_JURISDICTION` moved to `TaxWizard.tsx`
// with the form they belong to (CR-013 P4). They are the FORM's rules, and a
// catalog that still exported them would be the second home this repo keeps
// filing defects about.

/**
 * THE `Applies to` CELL — services, customer classes AND the premises scope.
 *
 * ⚠ THE LAST TWO ARE DEF-292, AND THE CELL IS HALF OF ITS FIX. Both qualifiers
 * have been writable, seedable and ENFORCED since 2026-08-18 and appeared on no
 * screen, so *"the ruled City Franchise Fee, which applies 'inside city limits
 * only', can never be given a city and reaches nobody, for ever."* The wizard is
 * where they are set; this is where an unscopeable tax becomes VISIBLE in the
 * list instead of silently inert — which is what the defect's own prevention
 * line asks for.
 *
 * A scope switched on with no place named is rendered as exactly that, because
 * the engine fails closed on it: the tax reaches nobody until it is filled in.
 */
export function taxAppliesToCell(row: TaxRow, t: Translator): string {
  const parts: string[] = [
    // An empty list means EVERY service (the server filters that way too).
    row.applies_to_services.length === 0
      ? t("rating.taxes.allServices")
      : row.applies_to_services
          .map((code) => t(`rating.service.${code}`, { defaultValue: code }))
          .join(", "),
  ];
  if (row.applies_to_customer_classes.length > 0) {
    parts.push(
      row.applies_to_customer_classes
        .map((code) => t(`rating.taxWiz.classes.${code}`, { defaultValue: code }))
        .join(", "),
    );
  }
  if (row.premises_scope_kind !== null && row.premises_scope_kind !== "") {
    const mechanism = t(`rating.taxWiz.scope.kind.${row.premises_scope_kind}`, {
      defaultValue: row.premises_scope_kind,
    });
    const place = (row.premises_scope_value ?? "").trim();
    parts.push(
      place === ""
        ? t("rating.taxes.scopeCellUnset", { mechanism })
        : t("rating.taxes.scopeCell", { mechanism, place }),
    );
  }
  return parts.join(" · ");
}

/**
 * The Rate column. Like the charge amount, this returns a KEY plus the raw
 * server strings — the catalog assembles the sentence and nothing is scaled.
 */
export function taxRateDisplay(row: TaxRow): { key: string; params: Record<string, unknown> } {
  // BR-RAT-087 / DEF-291 / DEF-364: the server's display string, not the stored
  // fraction. This line is why the Taxes screen read "0.062500 of the taxable
  // base" instead of "6.25% of the taxable base".
  if (row.kind === "flat_per_bill") {
    return { key: "rating.taxes.rate.flat", params: { amount: row.flat_amount ?? "—" } };
  }
  if (row.kind === "per_unit") {
    return {
      key: "rating.taxes.rate.perUnit",
      // A per-unit CHARGE is a unit price (PO 2026-10-02): up to four places,
      // so `0.002500` reads `0.0025` and no longer its six stored places.
      params: {
        amount: row.per_unit_amount === null ? "—" : formatRateNumber(row.per_unit_amount),
        unit: row.per_unit_uom ?? "—",
      },
    };
  }
  return { key: "rating.taxes.rate.percent", params: { rate: row.rate_display ?? "—" } };
}

/**
 * The `+ Filter` set (B14 rule 12), plus `over_20`, which is declared so the
 * banner's `Show them` survives in the URL but is never offered in the
 * `+ Filter` panel — see `TAX_FILTER_PANEL`.
 */
export function taxListFilters(
  t: Translator,
  serviceOptions: { value: string; label: string }[],
): TableFilterConfig[] {
  return [
    {
      name: "status",
      label: t("rating.col.status"),
      options: TAX_LIST_STATUSES.map((value) => ({ value, label: t(`rating.status.${value}`) })),
    },
    { name: "service", label: t("rating.filter.service"), options: serviceOptions },
    {
      name: "level",
      label: t("rating.taxes.jurisdictionLabel"),
      options: JURISDICTION_LEVELS.map((value) => ({
        value,
        label: t(`rating.taxes.level.${value}`),
      })),
    },
    {
      name: TAX_OVER_20_FILTER,
      label: t("rating.taxes.list.overTwenty"),
      options: [{ value: "1", label: t("rating.taxes.list.overTwenty") }],
    },
  ];
}

/** What `+ Filter` offers. `over_20` is set only by the banner, which renders
 *  only once the server serves the count — so the panel never offers a filter
 *  the server cannot answer yet. */
export function taxFilterPanel(filters: readonly TableFilterConfig[]): TableFilterConfig[] {
  return filters.filter((filter) => filter.name !== TAX_OVER_20_FILTER);
}

export function taxTableConfig(
  t: Translator,
  serviceOptions: { value: string; label: string }[],
  cells: {
    name: (row: TaxListRow) => ReactNode;
    version: (row: TaxListRow) => ReactNode;
    appliesTo: (row: TaxListRow) => ReactNode;
    rate: (row: TaxListRow) => ReactNode;
    from: (row: TaxListRow) => ReactNode;
    to: (row: TaxListRow) => ReactNode;
    gl: (row: TaxListRow) => ReactNode;
    premises: (row: TaxListRow) => ReactNode;
    status: (row: TaxListRow) => ReactNode;
    open: (row: TaxListRow) => ReactNode;
  },
): TableConfig<TaxListRow> {
  return {
    screenId: "S9.taxes",
    // CR-165 images 01–03, in the drawn order. The Remittance and Filing-form
    // columns are gone: filing is shown read-only on the details page, which is
    // where the PO's ruling put it (CR-165 README, ruled point 3).
    columns: [
      {
        key: "name",
        label: t("rating.taxes.col.jurisdiction"),
        sortable: true,
        identity: true,
        cell: cells.name,
      },
      { key: "version", label: t("rating.taxes.list.col.version"), cell: cells.version },
      { key: "applies_to_services", label: t("rating.taxes.col.appliesTo"), cell: cells.appliesTo },
      {
        key: "rate",
        label: t("rating.taxes.col.rate"),
        sortable: true,
        numeric: true,
        cell: cells.rate,
      },
      { key: "effective_from", label: t("rating.taxes.list.col.from"), cell: cells.from },
      { key: "effective_to", label: t("rating.taxes.list.col.to"), cell: cells.to },
      { key: "gl_account_code", label: t("rating.taxes.list.col.gl"), cell: cells.gl },
      {
        key: "premises_reached",
        label: t("rating.taxes.list.col.premises"),
        numeric: true,
        cell: cells.premises,
      },
      { key: "status", label: t("rating.col.status"), cell: cells.status },
      { key: "actions", label: "", locked: true, cell: cells.open },
    ],
    getRowId: (row) => row.id,
    // B14 rule 19 — `tax_list` filters `Q(name) | Q(jurisdiction__authority)`,
    // so the prompt names both, in the drawing's words (image 01).
    searchFields: ["name", "authority"],
    searchPlaceholder: "rating.taxes.list.search",
    // ⚠ PO 2026-10-03, verbatim: *"on list view of Tax - ensure you ahve filter
    // and not button for filters- follow our toolkkit standard"* — this
    // SUPERSEDES the All · Active · Draft · Ended buttons images 01–03 draw.
    // The toolbar is the kit's (B14 rule 12): `[Search] [All | chips ×]
    // [+ Filter ▾] … [▦]`. Every filter here is one `tax_list` narrows on the
    // SERVER (`selectors.TAX_FILTERS`) so no page is filtered on its own
    // (NFR-3). Customer class is NOT offered: the list endpoint cannot filter
    // by it, and a filter that narrowed only the page would lie.
    filters: taxListFilters(t, serviceOptions),
    defaultSort: { sort: "name", dir: "asc" },
  };
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface TaxesFeesTabProps {
  readOnly: boolean;
  client?: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** US-SHL-020 addendum r2 — `+ New tax or fee` opens this tab's own state. */
  render: RatingTabRender;
}

export function TaxesFeesTab(props: TaxesFeesTabProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const [searchParams, setSearchParams] = useSearchParams();

  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  // DEF-RAT-5691 — the tenant's OWN services, never the platform catalogue.
  const serviceOptions = activatedServiceOptions(servicesQuery.data);

  const regional = { timeZone: props.timeZone, dateFormat: props.dateFormat };
  const config = taxTableConfig(translate, serviceOptions, {
    // CR-013 row 14 / BR-RAT-084: the identity cell opens the shared definition
    // detail — reading is not a write, so it is a link for every role.
    name: (row) => <TaxNameCell row={row} to={tenantPath(definitionPath("tax", row.id))} />,
    version: (row) => <TaxVersionTag version={row.version} />,
    appliesTo: (row) => <TaxAppliesToCell row={row} />,
    rate: (row) => <TaxRateCell row={row} />,
    from: (row) => <TaxDateCell value={row.effective_from} {...regional} />,
    to: (row) => <TaxDateCell value={row.effective_to} openEnd {...regional} />,
    gl: (row) => <TaxGlCell row={row} />,
    premises: (row) => <TaxPremisesCell row={row} />,
    status: (row) => <TaxStatusCell status={row.status} />,
    // ⚠ P28 — THE PENCIL IS GONE AND IT IS NOT COMING BACK HERE. It opened the
    // wizard's edit door with the rate box live on a tax in force. The row's
    // ONE action opens the details page, where Edit offers the three ruled
    // verbs (name and filing · a new rate from a date · fix a mistake).
    // Deactivate left with it: Retire lives in the details page's More menu.
    open: (row) => (
      <RowActions>
        <RowAction
          label={t("rating.taxes.list.open")}
          icon={<EyeIcon />}
          onClick={() => navigate(tenantPath(definitionPath("tax", row.id)))}
        />
      </RowActions>
    ),
  });

  const state = parseTableParams(searchParams, config);
  const listQuery = useQuery({
    queryKey: queryKeys.taxes(serializeTableParams(state, config).toString()),
    // The round-2 fields ride on the same reply; see `TaxListResult`.
    queryFn: async (): Promise<TaxListResult> =>
      getTaxes(
        {
          q: state.q,
          filters: state.filters,
          sort: state.sort,
          dir: state.dir,
          page: state.page,
          per: state.per,
        },
        client,
      ),
  });

  function setState(next: TableRequestState): void {
    setSearchParams(serializeTableParams(next, config), { replace: true });
  }

  function setFilter(name: string, value: string | null): void {
    const filters = { ...state.filters };
    if (value === null) {
      delete filters[name];
    } else {
      filters[name] = value;
    }
    setState({ ...state, filters, page: 1 });
  }

  // Both failures keep the header and strip — see ChargeCodesTab for why.
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
              title={t("rating.taxes.failedTitle")}
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
        action: (
          <GuardedButton
            readOnly={props.readOnly}
            readOnlyReason={t("rating.readOnlyReason")}
            variant="primary"
            // PO ruling 2026-08-20: *"Wizards for each type - no modal;"* — the
            // primary action is NAVIGATION, to TAX-02's own route.
            onClick={() => navigate(tenantPath(TAX_WIZARD_NEW_ROUTE))}
          >
            {t("rating.taxes.new")}
          </GuardedButton>
        ),
        body: (
          <div className="rating-tab">
            {/* P21 — no paragraph above the table (images 01–03 draw none). */}
            <OverTwentyBanner
              count={listQuery.data?.over_20_count}
              showing={state.filters[TAX_OVER_20_FILTER] === "1"}
              onShow={() => setFilter(TAX_OVER_20_FILTER, "1")}
              onShowAll={() => setFilter(TAX_OVER_20_FILTER, null)}
            />

            <DataTable<TaxListRow>
              config={config}
              state={state}
              onStateChange={setState}
              // NFR-3 — ONE page, the server's; the total is the server's count.
              rows={listQuery.data?.results ?? []}
              totalRows={listQuery.data?.count ?? null}
              loading={listQuery.isPending}
              filterBarSlot={
                <FilterBar
                  filters={taxFilterPanel(config.filters ?? [])}
                  state={state}
                  onStateChange={setState}
                />
              }
              downloadSlot={
                // EP-RAT-03's capability row: CSV (IS-9). A money table — audited
                // server-side (BR-SHL-016).
                <ListExportButton resource="taxes" state={state} client={client} />
              }
              empty={{
                title: t("rating.taxes.emptyTitle"),
                helper: t("rating.taxes.emptyHelper"),
                ctaLabel: t("rating.taxes.new"),
                ctaVariant: "secondary",
                onCta: () => {
                  if (!props.readOnly) {
                    navigate(tenantPath(TAX_WIZARD_NEW_ROUTE));
                  }
                },
              }}
            />
          </div>
        ),
      })}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-009@7d1a8ef (story+rules snapshot hash — EP-RAT-03)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — S9 Taxes & fees + S13) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [list-export lane 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E2 CLOSED (CR-013 P4, 2026-08-21) — US-RAT-009 models S13 as a FOUR-STEP guided form and it IS one: `TaxWizard.tsx`, a full-page route, per the PO's *"Wizards for each type - no modal;"*. This tab holds the two doors and no modal · E2 US-RAT-009 TC-7 expects the per-unit "applies above" field to BLOCK the save pending OQ-054, but OQ-054 is CLOSED→BR-RAT-042 (MARGINAL) and the server now accepts and stores the threshold — the field is therefore live with the marginal semantics stated on it, and the superseded TC is reported · E3 CLOSED (list-export lane 2026-08-10): EP-RAT-03's CSV export for this tab is WIRED to POST /exports (a MONEY table, so the server writes the BR-SHL-016 audit row); the produced file still has no download route — `result_link` is a `file://` artifact path (IS-11/reports W5) · E3 the liability-GL field renders as an ArrivesWith note — no endpoint serves a chart of accounts (ledger module unbuilt) · E4 the percent rate is edited as the stored FRACTION with the fact on the field, never scaled by 100 on screen
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
