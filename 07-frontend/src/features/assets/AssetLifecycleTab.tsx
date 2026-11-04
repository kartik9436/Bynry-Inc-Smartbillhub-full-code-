// ── Trace ──────────────────────────────────────────────
// Change:   CR-028 AST-W5 T2 (B16 §4.5 · §10-D3 RULED 2026-08-22 →
//           BR-AST-047). ⚠ REBUILT 2026-09-12 by CR-092-BRC01 step 2 lane 1
//           as screens 05a · 05b · 05c (`DEF-MET-4955`): three sub-tabs on the
//           shared DataTable in place of three hand-built stacked tables.
// Rules:    B14 rules 12 (toolbar) · 13 (sort) · 14 (column chooser) ·
//           15 (max two icon row actions) · 16 (pagination footer) ·
//           17 (an empty state on EVERY list) · 19 (this list's own search
//           prompt) · 21 (Tailwind, this file is on route-b-migrated.txt) ·
//           36 (compose the kit; a hand-rolled table where the kit declares
//           one is the breach) · BR-SHL-011 (the sub-tab is URL state) ·
//           BR-SHL-025 (a forbidden action is disabled WITH its reason) ·
//           §10-D3 (NO GL sentence, no depreciation posting, no Cost & Margin
//           link) · BR-AST-007/027 (the due dates are DERIVED) ·
//           hard rule 2 (money 2 dp displayed)
// Impacts:  AssetRegistryPage.tsx (mounts this on ?tab=lifecycle) ·
//           GET /assets/lifecycle (apps/assets/api.py)
// ───────────────────────────────────────────────────────
// AST-01.lifecycle — screens 05a/05b/05c, three sections of ONE read.
//
// ── WHAT THIS REPLACED, AND THE MEASUREMENT THAT SAID SO (`DEF-MET-4955`) ──
//
// Until 2026-09-12 this tab stacked THREE hand-built tables on one page. Walked
// in a browser at 1440: **3 tables · 0 sortable headers · 0 pagination footers ·
// 0 search boxes · 1 row-action control in the whole tab.** That is B14 rules
// 12, 13, 14 and 16 broken on all three at once, and it is rule 36 underneath
// them — the kit declares a table and this file declared a class string, so
// every capability the kit already has had to be missing rather than chosen.
// `G43` could not see any of it: it holds the toolbar contract for lists that
// DECLARE `searchFields` through `TableConfig`, and a hand-built table declares
// none, so it sat outside the gate by construction. A check that reports zero
// over a scope it silently excludes.
//
// ⚠ **AND A FOURTH RULE THE AUDIT MISSED TOO — 17.** `certifications` and
// `warranty_groups` each rendered a `colSpan` empty row; `age_forecast.rows`
// had **no empty branch at all**, so a tenant with nothing recorded got a
// header, no rows and a bare Programme total. The kit's `empty` block makes
// that state impossible to forget, which is the argument for the kit in one
// line.
//
// ── WHAT IS DELIBERATELY DIFFERENT FROM r10, and why ───────────────────────
//   · The "Cost to Finance" panel (Replacements YTD · Repairs YTD ·
//     "Depreciation Aug $22,150" · "Posts to 5300 O&M and 5400 Depreciation"
//     · "Open Cost & Margin →") is NOT drawn — D3 ruled it out: no
//     depreciation engine exists and only the ledger posting service writes
//     journal lines (hard rule 5).
//   · ⚠ **AND ITS RULED REPLACEMENT, THE "Asset value" PANEL, IS NOW GONE TOO
//     — PO INSTRUCTION, 2026-09-11, QUOTING THE PANEL IN FULL: *"remove this -
//     Asset value"*.** It is the ONE field-bearing removal in the whole
//     CR-092 blueprint and it has a stated cost: `buy_value` and
//     `present_value` are computed NOWHERE ELSE in the product, so a person
//     who used them loses them entirely. Recorded rather than let pass as a
//     tidy-up. The server still serves `asset_value`; nothing renders it.
//   · ⚠ **THIS PARAGRAPH USED TO SAY the per-row wrench and the Turn-into-work
//     button "render DISABLED with exactly Work R5 (D7) — never hidden, never
//     built". THAT WAS TRUE WHEN IT WAS WRITTEN AND FALSE FROM `CR-070` WAVE M**
//     (`DEF-MET-4964`): both have been LIVE since that wave and this tab
//     rendered ZERO disabled buttons, measured on screen. The hold was released
//     and the sentence recording it was not — hard-won law 1 in its mirror
//     form, a comment claiming an ABSENCE the code no longer has, read by no
//     gate at all. What is true now: the wrench opens `Work-028` for its row
//     and the panel button opens `Work-026`, and BOTH are gated on
//     `writeBlockedReason` (`DEF-MET-4950` · `BR-SHL-025`).
//
// ── TWO CARRY-OVER DECISIONS THE BLUEPRINT LEFT OPEN, DECIDED HERE ─────────
//
// Screen 05c's carry-over table does not close its own arithmetic: it counts
// ten as-built elements and then lists nine unchanged + one relabelled + one
// removed = eleven. The two it never dispositions are the **Programme total
// row** and the whole **Turn into work** panel. Step 1 recorded it and said
// "whoever builds 05c must decide where those two go". Decided:
//
//   1. **The Programme total survives, beneath the forecast table.** It is a
//      real served pair (`age_forecast.programme.units` / `.cost`) with no
//      other home in the product, and the ONE removal the document instructs
//      is the Asset value panel. It moves out of the table body because a
//      DataTable renders rows and a total is not one — putting it back inside
//      would mean a second table, which is the rule-36 breach this rebuild
//      exists to end.
//   2. **The Turn into work panel survives, on the forecast section.** It is
//      not listed as removed either, its button is live, and the forecast is
//      the section its sentence is about.
//
// ── ONE THING THIS DOES NOT FIX, STATED RATHER THAN LEFT IMPLIED ──────────
//
// The three tables page, sort, search and filter **in the browser** over the
// whole `GET /assets/lifecycle` payload, which takes no page parameter at all.
// That is honest at ten rows and it is `DEF-MET-4962`'s third endpoint; the
// remedy drawing says the same thing in its own words. Bounding that read is
// server work with its own row and is not silently done here.
//
// And the pager is whatever the shared `DataTable` draws — no first/last page
// control is added. Those four shared-table rows are OUT OF SCOPE by PO ruling
// of 2026-09-12 and carry their own CR; four rows reaching 54 lists is not a
// risk to take inside an Assets pass.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAssetLifecycleEveryPage } from "@/api/endpoints";
import type {
  AssetCertRequirement,
  AssetCertificationRow,
  AssetForecastRow,
  AssetWarrantyGroup,
} from "@/api/endpoints";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { MoneyCell } from "@/components/MoneyCell";
import { EyeIcon, WrenchIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { defaultRequestState } from "@/components/tableTypes";
import { clientPage } from "@/components/clientTable";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { GuardedButton, useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { WORK_RULES_ROUTE } from "@/features/work/WorkShell";
import { useTenantPath } from "@/routing/tenantPath";

import { AssetDash, assetDetailPath, useTranslator } from "./assetsShared";
import { raiseWorkOrderPath } from "./RaiseWorkOrderPage";

export const assetLifecycleQueryKey = ["assets", "lifecycle"] as const;

/** The three sections of the Lifecycle tab — screens 05a, 05b, 05c, in the
 *  order the old stacked page put them, because a person who knew where a
 *  table was still knows (the carry-over's own rule for a relabelling). */
export const LIFECYCLE_SECTIONS = ["certifications", "warranty", "forecast"] as const;
export type LifecycleSection = (typeof LIFECYCLE_SECTIONS)[number];

/** BR-SHL-011: the sub-tab is URL state, so every section is linkable and a
 *  refresh lands where the person was. An unknown value is the default rather
 *  than an error — a stale link is not a failure. */
export function sectionFromParam(value: string | null | undefined): LifecycleSection {
  return LIFECYCLE_SECTIONS.includes((value ?? "") as LifecycleSection)
    ? (value as LifecycleSection)
    : "certifications";
}

/** The served status → its pill tone. Overdue is the danger tier; a booked
 *  future date and a comfortably-in-date cadence are calm. */
export const CERT_STATUS_TONE: Record<AssetCertificationRow["status"], StatusTone> = {
  overdue: "danger",
  due_soon: "warning",
  scheduled: "neutral",
  in_date: "success",
};

/** The Requirement cell's copy, from the SERVED derivation (data → words in
 *  exactly one place; the server never hardcodes a per-asset string). */
export function requirementLabel(requirement: AssetCertRequirement, t: Translator): string {
  if (requirement.kind === "periodic_test") {
    return t("assets.lifecycle.req.periodic_test", {
      months: requirement.interval_months ?? 0,
    });
  }
  return t(`assets.lifecycle.req.${requirement.kind}`);
}

/** Months → r10's "N.n yrs" (14.2 yrs) — display only, one decimal. */
export function yearsLabel(months: number, t: Translator): string {
  return t("assets.lifecycle.years", { years: (months / 12).toFixed(1) });
}

/**
 * ── The client-side table pipeline ────────────────────────────────────────
 *
 * ⚠ **MOVED TO THE KIT ON 2026-09-23 (`CR-138-BRC07`, B14 rule 43), AND NOT
 * ONE LINE OF ITS BEHAVIOUR CHANGED.** It was written here, and the payments
 * blueprint's 7·1 Debtors, 7·3a Ladder and 7·3b Write-offs each need exactly
 * it — three more lists whose endpoint takes no page parameter. Copying it
 * would have made four places where *"how does a missing value sort"* gets
 * decided, which is the shape `SelectionToolbar` was extracted to end.
 *
 * It is re-exported under its own name so every importer and every test of
 * this file is byte-for-byte unaffected. The seam note lives with the
 * implementation now: `src/components/clientTable.ts` says in full why this is
 * a STAND-IN for server paging and which task deletes each caller. For this
 * screen that task is `DEF-MET-4962`'s third unbounded read.
 */
export { clientPage };

const PANEL = "border border-divider bg-surface p-4 [&_h3]:m-0 [&_h3]:mb-2 [&_h3]:text-h5";
/** The second-level strip. Tailwind rather than the `settings-tabs` class two
 *  other screens reuse: that class lives in `features/tenancy/SettingsPage.css`,
 *  which only `SettingsPage.tsx` imports — so on the Assets page it would style
 *  NOTHING, which is hard-won law 2 in the form the skill warns about (the
 *  class is in the DOM, every `toContain` passes, and the strip renders bare).
 *  The values are `PageHeader.css`'s own tab rule, so the two levels match. */
const SUBTABS = "mb-4 flex flex-wrap gap-4 border-b border-b-divider";
const SUBTAB =
  "border-0 border-b-2 border-b-transparent bg-transparent py-2 text-btn text-inherit cursor-pointer";
const SUBTAB_ON = "border-b-2 border-b-accent py-2 text-btn font-semibold text-accent cursor-pointer";
/** B14 rule 32: one sentence per section, and rule 18's 80% measure is the
 *  shared `page-header-explainer` rule's job on the tab above this one. */
const SECTION_NOTE =
  "mb-3 mt-0 max-w-measure text-base text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]";

export interface AssetLifecycleTabProps extends RegionalProps {
  writeBlockedReason: string | null;
  client?: ApiClient;
}

export function AssetLifecycleTab(props: AssetLifecycleTabProps) {
  const { t } = useTranslation();
  const translate = useTranslator();
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  const client = props.client ?? api;
  const { timeZone, dateFormat } = useRegional(props);
  const [params, setParams] = useSearchParams();
  const section = sectionFromParam(params.get("section"));

  const view = useQuery({
    queryKey: assetLifecycleQueryKey,
    queryFn: () => getAssetLifecycleEveryPage(client),
    retry: false,
  });

  // ── The three configs ───────────────────────────────────────────────────
  //
  // Declared before the early returns so the request state below is stable
  // across a refetch — a table that reset its page on every poll would lose a
  // person's place silently.
  const certConfig: TableConfig<AssetCertificationRow> = {
    screenId: "AST-01.lifecycle.certifications",
    getRowId: (row) => row.id,
    searchFields: ["asset_no", "premises"],
    searchPlaceholder: "assets.lifecycle.certs.search",
    // Due ASCENDING is the default, because the oldest lapse is the one that
    // decides what a person does next (05a's own words).
    defaultSort: { sort: "due", dir: "asc" },
    filters: [
      {
        name: "status",
        // The column's own key — one word, one string. A second
        // `filter.status` would have been a duplicate AND (in German and
        // Indonesian, where the word IS "Status") a new value identical to the
        // English, which `G15` counts.
        label: t("assets.lifecycle.col.status"),
        options: [
          { value: "overdue", label: t("assets.lifecycle.status.overdue") },
          { value: "due_soon", label: t("assets.lifecycle.filter.due90") },
          { value: "scheduled", label: t("assets.lifecycle.status.scheduled") },
          { value: "in_date", label: t("assets.lifecycle.status.in_date") },
        ],
      },
    ],
    columns: [
      { key: "asset_no", label: t("assets.lifecycle.col.asset"), sortable: true, identity: true,
        cell: (row) => (
          <Link
            className="text-accent-700 no-underline hover:underline focus-visible:underline"
            to={tenantPath(assetDetailPath(row.id))}
          >
            {row.asset_no}
          </Link>
        ) },
      { key: "type_name", label: t("assets.lifecycle.col.type") },
      { key: "premises", label: t("assets.lifecycle.col.premises"),
        cell: (row) => row.premises ?? <AssetDash /> },
      { key: "requirement", label: t("assets.lifecycle.col.requirement"),
        cell: (row) => requirementLabel(row.requirement, translate) },
      { key: "due", label: t("assets.lifecycle.col.due"), sortable: true,
        cell: (row) => (
          <DateCell value={row.due} timeZone={timeZone} dateFormat={dateFormat} />
        ) },
      { key: "status", label: t("assets.lifecycle.col.status"),
        cell: (row) => (
          <StatusPill tone={CERT_STATUS_TONE[row.status]}>
            {row.status === "due_soon"
              ? t("assets.lifecycle.status.due_soon", { days: row.days_until })
              : t(`assets.lifecycle.status.${row.status}`)}
          </StatusPill>
        ) },
      { key: "actions", label: t("assets.col.actions"),
        // B14 rule 15 — TWO icons, which is the cap, not a selection from more.
        cell: (row) => (
          <RowActions>
            <RowAction
              label={t("assets.lifecycle.raiseWork")}
              icon={<WrenchIcon />}
              // BR-SHL-025 (`DEF-MET-4950`): this opens the raise form, which
              // WRITES — so a role without that permission meets it disabled
              // carrying the reason, never live onto a refusal.
              reason={props.writeBlockedReason}
              onClick={() => navigate(tenantPath(raiseWorkOrderPath(row.id)))}
            />
            <RowAction
              label={t("assets.lifecycle.view")}
              icon={<EyeIcon />}
              onClick={() => navigate(tenantPath(assetDetailPath(row.id)))}
            />
          </RowActions>
        ) },
    ],
  };

  const warrantyConfig: TableConfig<AssetWarrantyGroup> = {
    screenId: "AST-01.lifecycle.warranty",
    getRowId: (row) => `${row.type}|${row.supplier}`,
    searchFields: ["supplier", "type_name"],
    searchPlaceholder: "assets.lifecycle.warranty.search",
    defaultSort: { sort: "type_name", dir: "asc" },
    filters: [
      {
        name: "cover",
        label: t("assets.lifecycle.filter.cover"),
        options: [
          { value: "covered", label: t("assets.lifecycle.warranty.covered") },
          { value: "expired", label: t("assets.lifecycle.warranty.expired") },
          { value: "none", label: t("assets.lifecycle.warranty.none") },
        ],
      },
    ],
    columns: [
      { key: "type_name", label: t("assets.lifecycle.col.group"), sortable: true, identity: true },
      { key: "supplier", label: t("assets.lifecycle.col.supplier"), sortable: true },
      { key: "units", label: t("assets.lifecycle.col.units"), numeric: true,
        cell: (row) => row.units.toLocaleString() },
      // Cover ends is the column that answers "what falls out of warranty this
      // year", which is why it sorts (05b's own note).
      { key: "cover_ends", label: t("assets.lifecycle.col.coverEnds"), sortable: true,
        cell: (row) =>
          row.cover_ends !== null ? (
            <DateCell
              value={row.cover_ends}
              timeZone={timeZone}
              dateFormat={dateFormat}
              monthYear
            />
          ) : (
            <AssetDash />
          ) },
      { key: "under_warranty", label: t("assets.lifecycle.col.underWarranty"), numeric: true,
        cell: (row) => row.under_warranty.toLocaleString() },
      { key: "status", label: t("assets.lifecycle.col.status"),
        cell: (row) =>
          row.status !== null ? (
            <StatusPill tone={row.status === "covered" ? "success" : "warning"}>
              {t(`assets.lifecycle.warranty.${row.status}`)}
            </StatusPill>
          ) : (
            <AssetDash />
          ) },
      { key: "actions", label: t("assets.col.actions"),
        cell: (row) => (
          <RowActions>
            <RowAction
              label={t("assets.lifecycle.viewGroup")}
              icon={<EyeIcon />}
              // The drill needs a TAB as well as a type, and the client cannot
              // derive one — a battery group is not on the meters tab. The
              // server carries it (`DEF-MET-4955`), exactly as `stock_view`
              // has carried it for the Inventory drill since CR-028 AST-W5.
              onClick={() => navigate(tenantPath(groupDrillPath(row)))}
            />
          </RowActions>
        ) },
    ],
  };

  const forecastConfig: TableConfig<AssetForecastRow> = {
    screenId: "AST-01.lifecycle.forecast",
    getRowId: (row) => row.type,
    searchFields: ["type_name"],
    searchPlaceholder: "assets.lifecycle.forecast.search",
    defaultSort: { sort: "type_name", dir: "asc" },
    filters: [
      {
        name: "attention",
        // "Replacement" rather than "Attention": it says what the two options
        // are FOR (a budget line), and "Attention" is the same word in French,
        // which would have shipped an untranslated value.
        label: t("assets.lifecycle.filter.replacement"),
        options: [
          { value: "past_life", label: t("assets.lifecycle.col.pastLife") },
          { value: "due12", label: t("assets.lifecycle.filter.due12mo") },
        ],
      },
    ],
    columns: [
      { key: "type_name", label: t("assets.lifecycle.col.group"), sortable: true, identity: true },
      { key: "avg_age_months", label: t("assets.lifecycle.col.avgAge"), sortable: true,
        numeric: true,
        cell: (row) =>
          row.avg_age_months !== null ? yearsLabel(row.avg_age_months, translate) : <AssetDash /> },
      { key: "expected_life_years", label: t("assets.lifecycle.col.expectedLife"), numeric: true,
        cell: (row) =>
          row.expected_life_years !== null ? (
            t("assets.lifecycle.yearsWhole", { years: row.expected_life_years })
          ) : (
            <AssetDash />
          ) },
      { key: "past_life", label: t("assets.lifecycle.col.pastLife"), numeric: true,
        cell: (row) => row.past_life.toLocaleString() },
      { key: "due_within_12mo", label: t("assets.lifecycle.col.due12"), numeric: true,
        cell: (row) => row.due_within_12mo.toLocaleString() },
      // Replacement cost DESCENDING is what makes this a budget tool (05c).
      { key: "replacement_cost", label: t("assets.lifecycle.col.replacementCost"), sortable: true,
        numeric: true,
        cell: (row) => moneyCell(row.replacement_cost, currencyOf(view.data)) },
      { key: "actions", label: t("assets.col.actions"),
        cell: (row) => (
          <RowActions>
            <RowAction
              label={t("assets.lifecycle.viewGroup")}
              icon={<EyeIcon />}
              onClick={() => navigate(tenantPath(groupDrillPath(row)))}
            />
          </RowActions>
        ) },
    ],
  };

  const [certState, setCertState] = useState<TableRequestState>(() =>
    defaultRequestState(certConfig),
  );
  const [warrantyState, setWarrantyState] = useState<TableRequestState>(() =>
    defaultRequestState(warrantyConfig),
  );
  const [forecastState, setForecastState] = useState<TableRequestState>(() =>
    defaultRequestState(forecastConfig),
  );

  if (view.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (view.data === undefined) {
    return (
      <p role="alert" className="text-base">
        {apiErrorText(view.error, translate)}
      </p>
    );
  }
  const data = view.data;
  const currency = data.asset_value.currency;

  const certs = clientPage(data.certifications, certState, {
    search: (row) => [row.asset_no, row.premises ?? ""],
    filter: (row, name, value) => (name === "status" ? row.status === value : true),
    sortValue: (row, key) =>
      key === "due" ? row.due : key === "asset_no" ? row.asset_no : row.asset_no,
  });

  const warranty = clientPage(data.warranty_groups, warrantyState, {
    search: (row) => [row.supplier, row.type_name],
    filter: (row, name, value) =>
      name === "cover" ? (value === "none" ? row.status === null : row.status === value) : true,
    sortValue: (row, key) =>
      key === "supplier"
        ? row.supplier
        : key === "cover_ends"
          ? row.cover_ends
          : row.type_name,
  });

  const forecast = clientPage(data.age_forecast.rows, forecastState, {
    search: (row) => [row.type_name],
    filter: (row, name, value) =>
      name !== "attention"
        ? true
        : value === "past_life"
          ? row.past_life > 0
          : row.due_within_12mo > 0,
    sortValue: (row, key) =>
      key === "avg_age_months"
        ? row.avg_age_months
        : key === "replacement_cost"
          ? row.replacement_cost === null
            ? null
            : Number(row.replacement_cost)
          : row.type_name,
  });

  const selectSection = (next: LifecycleSection) => {
    const copy = new URLSearchParams(params);
    copy.set("section", next);
    setParams(copy, { replace: false });
  };

  return (
    <>
      {/* ── The sub-tab strip · screens 05a/05b/05c · B14 rule 12 ───────────
          The three section titles, in the order the stacked page put them and
          with the same words — the carry-over's rule for a relabelling, so a
          person who knew where a table was still knows. */}
      <div className={SUBTABS} role="tablist" aria-label={t("assets.lifecycle.sectionsLabel")}>
        {LIFECYCLE_SECTIONS.map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            data-section={id}
            aria-selected={id === section}
            className={id === section ? SUBTAB_ON : SUBTAB}
            onClick={() => selectSection(id)}
          >
            {t(SECTION_TITLE_KEY[id])}
          </button>
        ))}
      </div>

      {section === "certifications" && (
        <>
          <p className={SECTION_NOTE}>{t("assets.lifecycle.certs.explainer")}</p>
          <DataTable<AssetCertificationRow>
            config={certConfig}
            state={certState}
            onStateChange={setCertState}
            rows={certs.page}
            totalRows={certs.total}
            // NEVER `view.isFetching`. Reaching this line means `view.data` is
            // defined (the early return above is the only other path), so the
            // table always has rows to draw — and a stale-then-refetch cycle
            // would otherwise blank a populated list behind eight skeleton
            // bars, on a timer, for no reason a person could see. Caught by
            // the SSR test rather than by the browser: in a browser the fetch
            // has settled before anybody looks.
            loading={false}
            // The failed state is the WHOLE tab's, above: this read answers all
            // three sections at once, so a failure has no section to belong to
            // and the early return draws the reason plus Retry for the page.
            // Passing a per-table error here would draw that sentence a second
            // time, in a frame whose toolbar is over nothing.
            error={null}
            filterBarSlot={
              <FilterBar
                filters={certConfig.filters ?? []}
                state={certState}
                onStateChange={setCertState}
              />
            }
            empty={{
              title: t("assets.lifecycle.certsEmpty"),
              helper: t("assets.lifecycle.certsEmptyHelper"),
            }}
          />
        </>
      )}

      {section === "warranty" && (
        <>
          <p className={SECTION_NOTE}>{t("assets.lifecycle.warranty.explainer")}</p>
          <DataTable<AssetWarrantyGroup>
            config={warrantyConfig}
            state={warrantyState}
            onStateChange={setWarrantyState}
            rows={warranty.page}
            totalRows={warranty.total}
            // NEVER `view.isFetching`. Reaching this line means `view.data` is
            // defined (the early return above is the only other path), so the
            // table always has rows to draw — and a stale-then-refetch cycle
            // would otherwise blank a populated list behind eight skeleton
            // bars, on a timer, for no reason a person could see. Caught by
            // the SSR test rather than by the browser: in a browser the fetch
            // has settled before anybody looks.
            loading={false}
            // The failed state is the WHOLE tab's, above: this read answers all
            // three sections at once, so a failure has no section to belong to
            // and the early return draws the reason plus Retry for the page.
            // Passing a per-table error here would draw that sentence a second
            // time, in a frame whose toolbar is over nothing.
            error={null}
            filterBarSlot={
              <FilterBar
                filters={warrantyConfig.filters ?? []}
                state={warrantyState}
                onStateChange={setWarrantyState}
              />
            }
            empty={{
              title: t("assets.lifecycle.warrantyEmpty"),
              helper: t("assets.lifecycle.warrantyEmptyHelper"),
            }}
          />
        </>
      )}

      {section === "forecast" && (
        <>
          <p className={SECTION_NOTE}>{t("assets.lifecycle.forecast.explainer")}</p>
          <DataTable<AssetForecastRow>
            config={forecastConfig}
            state={forecastState}
            onStateChange={setForecastState}
            rows={forecast.page}
            totalRows={forecast.total}
            // NEVER `view.isFetching`. Reaching this line means `view.data` is
            // defined (the early return above is the only other path), so the
            // table always has rows to draw — and a stale-then-refetch cycle
            // would otherwise blank a populated list behind eight skeleton
            // bars, on a timer, for no reason a person could see. Caught by
            // the SSR test rather than by the browser: in a browser the fetch
            // has settled before anybody looks.
            loading={false}
            // The failed state is the WHOLE tab's, above: this read answers all
            // three sections at once, so a failure has no section to belong to
            // and the early return draws the reason plus Retry for the page.
            // Passing a per-table error here would draw that sentence a second
            // time, in a frame whose toolbar is over nothing.
            error={null}
            filterBarSlot={
              <FilterBar
                filters={forecastConfig.filters ?? []}
                state={forecastState}
                onStateChange={setForecastState}
              />
            }
            // B14 rule 17 — the state this table had NO branch for at all
            // (`DEF-MET-4955`): a tenant with no expected life recorded used to
            // get a header, no rows and a bare Programme total.
            empty={{
              title: t("assets.lifecycle.forecastEmpty"),
              helper: t("assets.lifecycle.forecastEmptyHelper"),
            }}
          />
          {/* The Programme total — see the header note for why it survives and
              why it is beside the table rather than inside it. */}
          <div
            className="mt-3 flex flex-wrap items-baseline justify-between gap-2 border-t-2 border-t-divider pt-3"
            data-programme-total=""
          >
            <span className="font-heading font-bold">{t("assets.lifecycle.programme")}</span>
            <span className="font-heading font-bold tabular-nums">
              {data.age_forecast.programme.units.toLocaleString()}
              {" · "}
              {moneyCell(data.age_forecast.programme.cost, currency)}
            </span>
          </div>
          <div className={`${PANEL} mt-4`} data-turn-into-work="">
            <h3>{t("assets.lifecycle.turnIntoWork")}</h3>
            <p className="mb-3 mt-1 text-base">
              {t("assets.lifecycle.exchangeDue", { n: data.age_forecast.programme.units })}
            </p>
            {/* BR-SHL-025 (`DEF-MET-4950`): "Set up an exchange rule" promises
                a write and lands on a screen that would refuse one, so the
                refusal is stated HERE where the person presses. */}
            <GuardedButton
              label={t("assets.lifecycle.raiseProgramme")}
              reason={props.writeBlockedReason}
              variant="secondary"
              onClick={() => navigate(tenantPath(WORK_RULES_ROUTE))}
            />
          </div>
        </>
      )}
    </>
  );
}

/** The section title doubles as its tab label — same words, same order, same
 *  place in the sequence (05a/05b/05c's carry-over disposition, RELABELLED). */
const SECTION_TITLE_KEY: Record<LifecycleSection, string> = {
  certifications: "assets.lifecycle.certsTitle",
  warranty: "assets.lifecycle.warrantyTitle",
  forecast: "assets.lifecycle.forecastTitle",
};

/** One group row → the registry, filtered to that group's assets. The TAB is
 *  served (`DEF-MET-4955`) because a client cannot derive it from the type
 *  code, and a wrong tab is an empty list rather than an error. */
export function groupDrillPath(row: { tab: string; type: string }): string {
  const query = new URLSearchParams();
  query.set("tab", String(row.tab));
  query.set("f.type", row.type);
  return `/assets?${query.toString()}`;
}

/** Hard rule 2 — stored to 4 decimals, DISPLAYED to 2. A null amount, or a
 *  tenant with no currency on record, is the quiet dash and never `$0.00`. */
function moneyCell(amount: string | null, currency: string | null) {
  return amount !== null && currency !== null ? (
    <MoneyCell amount={amount} currency={currency} />
  ) : (
    <AssetDash />
  );
}

function currencyOf(data: { asset_value: { currency: string | null } } | undefined) {
  return data?.asset_value.currency ?? null;
}

export default AssetLifecycleTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-028/B16@2026-08-22 §4.5 + §10-D3/D7 (AST-W5 T2) · REBUILT under
//   CR-092-BRC01 step 2 lane 1 (2026-09-12) against the drawn screens 05a/05b/
//   05c in 04-docs/05-modules/05-assets/wireframes/CR-092-assets-screens.html
//   and the step-1 conformance document beside it
// generated: 2026-08-22 by the CR-028 AST-W5 lane · REBUILT 2026-09-12 by the
//   CR-092 step 2 registry lane (DEF-MET-4955, DEF-MET-4950, DEF-MET-4964)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest · i18n ×11 (19 new keys)
// exceptions: E2 r10's "Cost to Finance" sidebar is NOT drawn — §10-D3 RULED it out (no depreciation engine; hard rule 5) · E2 the "Asset value" panel that REPLACED it is REMOVED on the PO's quoted instruction of 2026-09-11 ("remove this - Asset value"); `asset_value` is still SERVED and now rendered nowhere, and the two figures exist nowhere else in the product — a stated cost, not a tidy-up · E3 search, sort, filter and paging run in the BROWSER over the whole `GET /assets/lifecycle` payload, which takes no page parameter — `DEF-MET-4962`'s third unbounded read, stated rather than silently accepted; `clientPage` is the seam that gets deleted when the endpoint grows params · E3 no first/last-page control is added: those four shared-table rows are OUT OF SCOPE by PO ruling 2026-09-12 and carry their own CR · E2 r10's page sentence "Anything on this page can become a work order in one click" is not rendered — it would be false until Work R5
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
