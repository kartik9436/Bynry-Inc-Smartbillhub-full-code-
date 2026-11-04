// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-004 (S50 header + Overview — the full specification set) ·
//           US-AST-005 (Reads tab — SERVED, CR-028 AST-W2 T4 / DEF-475) ·
//           US-AST-006 (Assignment history · Maintenance & repairs · Audit tabs) ·
//           US-AST-007/008/009 (the header's lifecycle actions) ·
//           US-SHL-020 (the one page header — this screen's conversion)
//           Screens: S50 / AST-02 (asset # click on S49; S16 in A1's
//           platform-shell numbering), links out to S53–S55 and S61
// Change:   CR-028 AST-W2 (B16 §5.1/§5.1b, 2026-08-22) — ONE detail template,
//           EVERY kind: header sub-line to r10 (service · ×trimmed ·
//           installed Mon YYYY · seat), Specifications absorb the
//           classification panel (the repeated panel is REMOVED — §4.8's
//           measured drift), THREE Overview panels (Assignment w/ the LIVE
//           account leg · Warranty & supplier · Lifecycle), the Reads tab
//           served with BR-AST-029's net fold, Audit INLINE (BR-AUD-010 /
//           DEF-579's premises pattern), names not uuids (T6), maintenance
//           cost captured NEVER posted (§10-D3), device tab sets: plain
//           device FOUR tabs + Test & certification panel, exporting
//           inverter FIVE tabs w/ an Export tab reading its LINKED NET
//           METER's records (§5.1b A/B).
// Change:   CR-028 AST-W4 (2026-08-22) — the header/panel lifecycle actions
//           NAVIGATE to the AST-06/07/08 full-page routes (the modals are
//           deleted); the Warranty & supplier panel gains the Present value
//           row (T4 — the server's straight-line book value as of today).
// Rules:    BR-AST-006 (the header's action set is the SERVER's, by state) ·
//           BR-AST-007 ("Test due" is a DERIVED chip beside an unchanged status) ·
//           BR-AST-014 (the extended spec fields are capture-only) ·
//           BR-AST-015 (register digits bound read entry; default 9) ·
//           BR-AST-016/025 (no money on any read surface; quantities carry units) ·
//           BR-AST-017 (assignment history is append-only, non-overlapping) ·
//           BR-AST-018 (maintenance is append-only — corrections are new entries) ·
//           BR-AST-019 + BR-AUD-010 (the Audit tab RENDERS audit_log for this
//           asset AND links to S61; read-only) ·
//           BR-AST-026 (three identifiers; the internal uuid is never displayed) ·
//           BR-AST-029 (a net cycle is TWO typed records — folded per date here) ·
//           BR-AST-030 (retire is terminal — a retired asset offers View only) ·
//           BR-AST-039 (the header carries the LIVE billing chain) ·
//           BR-AST-044 (ALL THREE classifications on this detail view) ·
//           BR-AST-047 (valuation captured on the record; NO finance link — D3/D4) ·
//           BR-SHL-011 (the open tab is URL state) · BR-SHL-034 (one date formatter) ·
//           BR-SHL-025 (a role without write sees the control disabled WITH its reason) ·
//           BR-SHL-044 (the one page-header skeleton, and its three properties)
// ───────────────────────────────────────────────────────
// S50 — one asset, in full, whatever its kind.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  deleteAsset,
  getAsset,
  getAssetAssignments,
  getAssetMaintenance,
  getAssetReads,
} from "@/api/endpoints";
import type { AssetDetail, AssetReadRow } from "@/api/endpoints";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CustomFieldsView } from "@/components/CustomFields";
// `AST-B-19` — the ONE pagination footer for a list that is not the shared
// `DataTable`, and the same four `table.pager.*` keys `DataTable` itself uses.
import { ListPager } from "@/components/ListPager";
import type { PageSize } from "@/components/tableTypes";
import { EyeIcon, PencilIcon, TrashIcon } from "@/components/icons";
import {
  RowAction,
  RowActionLink,
  RowActions,
  RowActionsMore,
  RowMenuAction,
} from "@/components/RowActions";
import { DateCell } from "@/components/DateCell";
import { formatMoney, MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { UnitCell } from "@/components/UnitCell";
import {
  CELL_FULL,
  DASHBOARD_ROUTE,
  GuardedButton,
  PREMISES_PERMISSION,
  isDenied,
  premisesDetailPath,
  useRegional,
  unitDetailPath,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { PeakQuantity, isPeakChannel } from "@/features/metering/demandShared";
// Screen 09 gap `09-3` — the reads STATUS is a pill, and the words are the
// ones Meter Reads already ships. `readsShared` owns both, which is why this
// is an import and not a second tone map (`DEF-MET-4969`'s own lesson: before
// repeating an exception that says a vocabulary does not exist, grep the
// catalogue — `metering.reads.status.*` holds 24 words in all eleven).
import { CountedReadingPill, ReadStatusCell } from "@/features/metering/readsShared";
import { AuditTab } from "@/features/metering/PremisesDetailPage";
import { apiErrorText, isPermissionDenied, refusalOf, RefusalNotice } from "@/features/tenancy/settingsShared";
import type { Refusal, Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  ASSETS_ROUTE,
  EMPTY_BILLING_CHAIN,
  AssetContextLine,
  AssetDash,
  AssetStatusCell,
  assetDetailPath,
  assetEditPath,
  assetMaintenanceNewPath,
  assetReassignPath,
  assetRetirePath,
  channelLabel,
  hasAction,
  isMeasuringCategory,
  offersConnectionSize,
  repairActionKey,
  serviceLabel,
  sizeClassName,
  trimDecimalZeros,
  useSizeClassNames,
} from "./assetsShared";
import { listAssetWorkOrders } from "@/features/work/workEndpoints";
import type { AssetWorkOrderRow } from "@/features/work/workEndpoints";
import { accountDetailPath } from "@/features/customers/customersShared";
import { isOpenOrder } from "@/features/work/buildViews";
import { workOrderStateTone } from "@/features/work/OrdersPage";
import { WORK_ORDERS_ROUTE } from "@/features/work/WorkShell";
import { Button, ButtonLink } from "@/components/Button";
import { raiseWorkOrderPath } from "./RaiseWorkOrderPage";
// CR-038 W5 task 8 — the trailing-12-month strip at the head of the Reads tab.
import { AssetUsageStrip } from "./AssetUsageStrip";
// `AST-B-25` — the five per-panel edit dialogs, screens 16–21.
import { AssetPanelEditDialog } from "./AssetPanelEdits";

// ── Pure pieces ────────────────────────────────────────────────────────────

/** The five S50 tabs a MEASURING asset shows (EP-AST-02 §Scope, r10 AST-02). */
export const ASSET_DETAIL_TABS = [
  "overview",
  "reads",
  "assignments",
  "work",
  "audit",
] as const;

/**
 * Screen 12 gap `12-1` — the merged tab's address is `?tab=work`, and
 * `?tab=maintenance` still opens it.
 *
 * ⚠ **THE ALIAS IS THE POINT, NOT A KINDNESS.** The old id is in live
 * bookmarks, in this repository's own walkthroughs and in whatever a beta
 * tester has open right now; a rename that answers those with the Overview
 * pane is a screen that silently lost a link. `assetDetailTabFrom` maps it and
 * `selectTab` writes only the new id, so the address a person copies from the
 * bar is always the current one.
 */
const LEGACY_TAB_IDS: Record<string, string> = { maintenance: "work" };

/** Every tab id any kind can own — `export` is §5.1b (B)'s inverter tab. */
const ALL_DETAIL_TABS: readonly string[] = [...ASSET_DETAIL_TABS, "export"];

export const TAB_PARAM = "tab";

export const assetDetailQueryKey = (id: string) => ["assets", "detail", id] as const;
// ⚠ **THE PAGE IS PART OF THE KEY (`AST-B-19`).** A key that ignores it makes
// React Query answer page 2 from page 1's cache entry, so the footer moves and
// the rows do not — which looks exactly like a server that ignores `?page=`.
// The default argument keeps every existing caller's key byte-identical.
export const assetAssignmentsQueryKey = (id: string, page = 1, per = 50) =>
  ["assets", "assignments", id, page, per] as const;
export const assetMaintenanceQueryKey = (id: string, page = 1, per = 50) =>
  ["assets", "maintenance", id, page, per] as const;
export const assetReadsQueryKey = (id: string, page = 1, per = 50) =>
  ["assets", "reads", id, page, per] as const;

/**
 * CR-028 AST-W2 T8 (B16 §5.1b): ONE template, EVERY kind — the tab SET is
 * what varies, the structure never does.
 *   · measuring (meters · sub-meters): the five tabs, unchanged;
 *   · exporting inverter (a device whose linked meter is a NET meter): FIVE,
 *     an Export tab replacing Reads — it reads the LINKED meter's records;
 *   · plain device: FOUR — no Reads tab at all (a device stores no read, and
 *     a dead tab is Premises-style drift).
 */
export function assetDetailTabsFor(
  asset: Pick<AssetDetail, "tab" | "linked_meter">,
): string[] {
  if (asset.tab !== "behind_the_meter") {
    return [...ASSET_DETAIL_TABS];
  }
  if (asset.linked_meter !== null && asset.linked_meter.net_metering) {
    return ["overview", "export", "assignments", "work", "audit"];
  }
  return ["overview", "assignments", "work", "audit"];
}

/** The open tab is URL state (BR-SHL-011); a tab another KIND owns falls back
 *  to Overview rather than rendering a dead pane. */
export function assetDetailTabFrom(
  raw: string | null,
  allowed: readonly string[] = ALL_DETAIL_TABS,
): string {
  const asked = LEGACY_TAB_IDS[raw ?? ""] ?? raw ?? "";
  return allowed.includes(asked) ? asked : "overview";
}

/**
 * Screen 12 gap `12-3` — the two sub-tabs, and which one the URL asks for.
 *
 * `BR-SHL-011`: a sub-tab is URL state, so both halves are linkable and a
 * refresh lands where the person was. `Open work` is the default because it is
 * the half you can act on — figure 19's own caption. An unknown value is the
 * default rather than an error; a stale link is not a failure. The pattern is
 * `AssetLifecycleTab`'s `sectionFromParam`, copied rather than reinvented.
 */
export const WORK_SECTIONS = ["open", "history"] as const;
export type WorkSection = (typeof WORK_SECTIONS)[number];
export const WORK_SECTION_PARAM = "section";

export function workSectionFrom(raw: string | null | undefined): WorkSection {
  return WORK_SECTIONS.includes((raw ?? "") as WorkSection) ? (raw as WorkSection) : "open";
}

/** BR-AST-015: the stored value, or the ruled default of 9 when unspecified. */
export const DEFAULT_REGISTER_DIGITS = 9;

export function registerDigitsOf(value: number | null): number {
  return value ?? DEFAULT_REGISTER_DIGITS;
}

/** Hard rule 2: percentages DISPLAY at 2 dp (stored 6). Decimal STRING in,
 *  half-up over the exact value — the MoneyCell technique, no float math. */
export function displayPct(value: string): string {
  try {
    const formatter = new Intl.NumberFormat(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      // B4.4 ❄️ half-up at display.
      roundingMode: "halfExpand",
    } as Intl.NumberFormatOptions) as unknown as { format: (value: string) => string };
    return `${formatter.format(value)}%`;
  } catch {
    return `${value}%`;
  }
}

/** The Lifecycle panel's Age — "2 yrs 5 mo" from the served month count. */
export function ageParts(ageMonths: number): { years: number; months: number } {
  return { years: Math.floor(ageMonths / 12), months: ageMonths % 12 };
}

// ── Shared styling (Tailwind — B14 r21) ────────────────────────────────────

const SECTION =
  "mb-4 border border-divider bg-surface p-4 [&_h3]:m-0 [&_h3]:mb-2 [&_h3]:text-h5";
const FACTS =
  "m-0 grid grid-cols-[minmax(150px,auto)_1fr] gap-x-3 gap-y-2 text-base [&_dt]:font-heading [&_dt]:font-semibold [&_dt]:text-[color-mix(in_srgb,var(--color-text)_65%,transparent)] [&_dd]:m-0";
const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";
/** The in-page link, once. Five call sites wrote this identical string out by
 *  hand and a sixth was about to (`DEF-MET-4967`'s work-order number), which is
 *  how a screen ends up with two kinds of link that nobody chose. */
const LINK =
  "cursor-pointer border-0 p-0 text-left text-accent-700 no-underline hover:underline focus-visible:underline";
/** The SECOND-LEVEL strip, byte-for-byte `AssetLifecycleTab`'s (screens
 *  05a–05c). Two strips in one module that look different are two strips a
 *  person has to learn, so the values are shared rather than re-chosen — and
 *  they are `PageHeader.css`'s own tab rule, so the two LEVELS match too. */
const SUBTABS = "mb-4 flex flex-wrap gap-4 border-b border-b-divider";
const SUBTAB =
  "border-0 border-b-2 border-b-transparent bg-transparent py-2 text-btn text-inherit cursor-pointer";
const SUBTAB_ON = "border-b-2 border-b-accent py-2 text-btn font-semibold text-accent cursor-pointer";
const TABLE =
  "w-full border-collapse text-table [&_td]:border-b [&_td]:border-b-divider [&_td]:p-2 [&_td]:text-left [&_td]:align-top [&_th]:border-b [&_th]:border-b-divider [&_th]:p-2 [&_th]:text-left [&_th]:align-top [&_th]:font-heading [&_th]:text-table-header [&_th]:uppercase [&_th]:tracking-table-header";

// ── BR-WRK-056's door, on the asset's own screen ───────────────────────────
//
// `BR-WRK-056` is CONFIRMED and reads: *"The Assets door is ONE form with four
// ways in … the action bar, the Maintenance history panel and the four
// `RaiseWorkOrderCheckbox` ticks … all post it."* The four ticks were built at
// `CR-070` wave M and **the two on this screen never were** — `DEF-MET-4965`.
//
// ⚠ **WHY THIS IS NOT GATED BY `hasAction()`, WHICH IS HOW EVERY OTHER CONTROL
// IN THIS HEADER WORKS.** Three reasons, and the third is the one that decides
// it — the engineering half `BR-AST-534` deliberately left open:
//
//   1. `row_actions()` is the ASSETS module's vocabulary, and this door is
//      `apps/work`'s. `apps/work/asset_door.py` states its whole design as
//      *"`apps/assets/**` gains no line of code at all — which is a stronger
//      statement than 'assets writes nothing to work_orders', and it is the
//      one a grep test can prove"*. A `raise_work_order` verb minted in
//      `apps/assets/selectors.py` would put Work's vocabulary in Assets'
//      mouth and weaken that test's premise.
//   2. `row_actions()` feeds `asset_dict()`, which is the LIST row too. The
//      verb would be served on every registry row, where nothing renders it —
//      a served fact with no reader, which is hard-won law 2's own shape.
//   3. **`hasAction()` HIDES what the state forbids, and `BR-AST-534` says
//      this control is never hidden.** PO, 2026-09-12: *"a) Show it disabled,
//      with the reason"*. A mechanism whose only move is to remove the control
//      cannot express a rule whose whole content is that the control stays.
//
// So the refusal is derived from the fact the payload already carries —
// `behavior_class`, the same string `row_actions()` itself branches on — and
// no server change is made. Recorded in `12-governance/02-decision-log.md`.

/** `terminal` is `selectors.TERMINAL`, served on every asset payload. */
const TERMINAL_BEHAVIOR = "terminal";

/**
 * Why this asset may not have a job raised against it, or null.
 *
 * ⚠ **THE STATE REASON WINS OVER THE ROLE REASON, and that is a choice.** Both
 * can be true at once — a View-only clerk looking at a retired meter. One
 * control carries one sentence, and the STATE one is true for every role and
 * does not change when permissions do, so it is the one a person is shown.
 */
export function raiseWorkRefusal(
  asset: Pick<AssetDetail, "behavior_class">,
  writeBlockedReason: string | null,
  t: Translator,
): string | null {
  if (asset.behavior_class === TERMINAL_BEHAVIOR) {
    return t("assets.raiseWork.retiredReason");
  }
  return writeBlockedReason;
}

/**
 * The control itself — a LINK when it is allowed, a disabled button when it is
 * not.
 *
 * ⚠ **A LINK RATHER THAN `GuardedButton`'s navigate, and `Button.tsx` gives the
 * reason in its own words:** *"It is a link because it NAVIGATES; making it a
 * button would break middle-click and the browser's own open-in-new-tab."*
 * It also means the destination is IN THE MARKUP, so a test can assert the
 * address instead of asserting that a label exists — which is the assertion
 * `DEF-WRK-4051` was missing when two shipped screens pointed at nothing.
 */
function RaiseWorkOrderControl(props: {
  asset: AssetDetail;
  reason: string | null;
  t: Translator;
}) {
  const tenantPath = useTenantPath();
  const label = props.t("assets.lifecycle.raiseWork");
  if (props.reason !== null) {
    // `BR-AST-534` / `BR-SHL-025`: shown, disabled, carrying its reason.
    return (
      <Button variant="secondary" disabled title={props.reason}>
        {label}
      </Button>
    );
  }
  return (
    <ButtonLink variant="secondary" to={tenantPath(raiseWorkOrderPath(props.asset.id))}>
      {label}
    </ButtonLink>
  );
}

// `serviceLabel` MOVED to `assetsShared` with the context line that uses it —
// the Fact row below and that line are two callers of one answer, and the
// `rating.service.*` namespace is exactly the thing `DEF-763` cost by being
// typed in more than one place.

// ── The screen ─────────────────────────────────────────────────────────────

export interface AssetDetailPageProps extends RegionalProps {
  client?: ApiClient;
  today?: string;
}

// CR-028 AST-W4: repair / retire / reassign left this union — they are
// full-page screens now (AST-06/07/08) and every control below NAVIGATES.
type DetailAction = "delete";

export function AssetDetailPage(props: AssetDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  // DEF-RAT-9321 — the connection size prints as its NAME, never its code.
  const sizeNames = useSizeClassNames(client);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [pending, setPending] = useState<DetailAction | null>(null);
  // `AST-B-25` — which panel's pencil is open. One at a time; `null` = none.
  const [editing, setEditing] = useState<AssetOverviewPanel | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const assetId = params.assetId ?? "";
  const { timeZone, dateFormat } = useRegional(props);

  const cell = useAccessCell(PREMISES_PERMISSION, client);
  const writeBlockedReason = cell === CELL_FULL || cell === null ? null : t("assets.rbac.readOnly");

  const assetQuery = useQuery({
    queryKey: assetDetailQueryKey(assetId),
    queryFn: () => getAsset(assetId, client),
    enabled: assetId !== "",
  });

  const remove = useMutation({
    mutationFn: (asset: AssetDetail) => deleteAsset(asset.id, client),
    onSuccess: (_void, variables) => {
      setPending(null);
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
      fireToast(t("assets.toast.deleted", { asset: variables.asset_no }));
      navigate(tenantPath(ASSETS_ROUTE));
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, translate)),
  });

  function selectTab(id: string): void {
    const next = new URLSearchParams(searchParams);
    next.set(TAB_PARAM, id);
    setSearchParams(next, { replace: true });
  }

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("assets.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (assetQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (assetQuery.data === undefined) {
    if (isPermissionDenied(assetQuery.error)) {
      return (
        <PermissionDenied
        helper={t("assets.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
      );
    }
    // US-AST-004 TC-6: a direct URL to a non-existent (or cross-tenant) asset
    // gets the A18 failed state — never a blank detail shell.
    return (
      <FailedWithRetry
        title={t("assets.detail.failedTitle")}
        reason={apiErrorText(assetQuery.error, translate)}
        onRetry={() => void assetQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(ASSETS_ROUTE))}
      />
    );
  }

  const asset = assetQuery.data;
  // BR-AST-534 — computed once and passed to BOTH doors, so the header and the
  // Maintenance panel cannot end up refusing for different reasons.
  const raiseReason = raiseWorkRefusal(asset, writeBlockedReason, translate);
  const measuring = isMeasuringCategory(asset.tab);
  const device = asset.tab === "behind_the_meter";
  const tabs = assetDetailTabsFor(asset);
  const active = assetDetailTabFrom(searchParams.get(TAB_PARAM), tabs);

  // US-SHL-020 / BR-SHL-044: the tab strip is the header's; NONE of the tabs
  // declares a primary action (every control here is page-level, BR-AST-006).
  // Screen 12 gap `12-2` — ONE label, on every kind. The device variant
  // ("Tests & maintenance") predates the merge: figure 12 draws a backflow
  // preventer's own tab strip and it reads `Work & maintenance` like every
  // other kind's, so the fork is removed rather than renamed.
  const headerTabs = tabs.map((id) => ({
    id,
    label: t(`assets.detail.tab.${id}`),
  }));

  // ── The PLACE LINE · screen 08 gap `08-2` · page 36, header rule 1 ───────
  //
  // Quoted, because the order is the specification: *"the place line leading
  // with the **address** and carrying the **account**, which is served today
  // and shown nowhere · and the multiplier **gone** from it, because a ×1 is
  // configuration rather than identity."*
  //
  // It read `Water · ×1 · installed Feb 2024 · assigned to 118 Bayou Bend Dr ·
  // Unit A` — service first, a multiplier that belongs to the Measurement
  // panel, no account at all, and the two extra words *assigned to* that say
  // nothing an address does not already say. It now reads, in figure 10's own
  // order: **address · unit · account · service · Installed Mon YYYY**.
  //
  // ⚠ **IT IS COMPOSED IN `assetsShared` AND MOUNTED HERE — IT WAS WRITTEN
  // TWICE UNTIL 2026-09-13.** This screen built it inline and `AssetFlowShell`
  // built it again for Reassign, Log repair and the three Retire steps, so
  // figure 10's line and figure 31's line — the SAME line — had two authors
  // and had already drifted in four places. The one that showed: this copy did
  // not default `billing_chain`, so a payload without it replaced the whole
  // detail screen with *"Cannot read properties of undefined"* while every
  // flow screen rendered normally. Everything the line knows — the inventory
  // test, the fallback order, the account leg, the separator — now lives in
  // `AssetContextLine` and its docstring carries the reasoning.

  return (
    <div className="px-4 pt-6 pb-8">
      {/* CR-018 Route B: `.ast-page .page-header { margin-bottom: 16px }` and
          `.ast-page .page-header h1 { font-size: var(--text-h2); margin: 0 }`
          were descendant rules reaching into the shared PageHeader. Route B has
          no parent selector, so they travel onto a wrapper holding only the
          header — the one `<h1>` beneath it is PageHeader's own. */}
      <div className="mb-4 [&_h1]:m-0 [&_h1]:text-h2">
        <PageHeader
          backTo={{ to: tenantPath(ASSETS_ROUTE), label: t("shell.nav.assets") }}
          // BR-AST-026: the kicker names the asset by its KIND — the internal
          // uuid appears nowhere on this page. A device kicker is its DEVICE
          // TYPE ("Backflow preventer"): the meter-type leg is null on
          // non-measuring kinds and filters out.
          //
          // ⚠ **THE ASSET NUMBER IS NOT IN IT (screen 08 gap `08-1`).** Page 36
          // states the header rule in four numbered lines and the first reads
          // *"the number once, in the title"*. It was in both, adjacent — the
          // kicker read `Meter · M-4022 · AMR` directly above an `<h1>` reading
          // `M-4022` — and a fact said twice makes neither copy authoritative.
          // The title carries the COMPLETE value, which is the test for the
          // difference between a summary and a repeat. Screen 13's own figure
          // draws the old kicker; it is an AS-BUILT drawing of this same fault,
          // so fixing it here fixes that one too.
          kicker={[asset.type_name, asset.meter_type_name]
            .filter((part): part is string => part !== null)
            .join(" · ")}
          title={asset.asset_no}
          rollup={
            <span className="block text-base">
              {/* `AST-B-22` — the strip sits between the pill and the place
                  line, exactly where screen 08 draws it, and renders NOTHING
                  when nothing is due. */}
              <AttentionStrip
                asset={asset}
                regional={props}
                t={translate}
                raiseReason={raiseReason}
              />
              <AssetContextLine asset={asset} t={translate} regional={{ timeZone, dateFormat }} />
            </span>
          }
          status={<AssetStatusCell row={asset} t={translate} />}
          secondaryActions={
            <>
              {/* BR-WRK-056's first way in, and the drawing's own order —
                  `Raise work order · Reassign · Log repair · Retire` (screen 08,
                  Figure 10). It renders on EVERY tab because `TC-3` asserts the
                  header action block is byte-identical across them, and it is
                  outside `hasAction` on purpose — see `raiseWorkRefusal`. */}
              <RaiseWorkOrderControl asset={asset} reason={raiseReason} t={translate} />
              {/* BR-AST-006: the header offers exactly what the state allows —
                  a retired asset (BR-AST-030) therefore shows none of these. */}
              {(hasAction(asset, "reassign") || hasAction(asset, "assign")) && (
                <GuardedButton
                  label={
                    hasAction(asset, "assign")
                      ? t("assets.action.assign")
                      : t("assets.action.reassign")
                  }
                  reason={writeBlockedReason}
                  // AST-06 is a full-page screen (CR-028 W4) — NAVIGATE.
                  onClick={() => navigate(tenantPath(assetReassignPath(asset.id)))}
                />
              )}
              {hasAction(asset, "log_repair") && (
                <GuardedButton
                  label={t(repairActionKey(asset))}
                  reason={writeBlockedReason}
                  onClick={() => navigate(tenantPath(assetMaintenanceNewPath(asset.id)))}
                />
              )}
              {hasAction(asset, "retire") && (
                <GuardedButton
                  label={t("assets.action.retire")}
                  danger
                  reason={writeBlockedReason}
                  onClick={() => navigate(tenantPath(assetRetirePath(asset.id)))}
                />
              )}
              {/* ── `…` · screen 08 gap `08-3` — EDIT AND DELETE LIVE HERE ──
                  Page 41 states the action set in one sentence: *"Raise work
                  order … Then Reassign, Log repair, Retire, and Edit and Delete
                  under the overflow."* Six visible buttons is what it replaces,
                  and the retired-header frame is the proof the drawing means it
                  — that state draws the `…` box and nothing else, which is only
                  coherent if Edit and Delete are inside it.

                  ⚠ **`RowActionsMore` IS THE KIT'S, NOT A NEW COMPONENT.** B14
                  rule 15's *"Max 2 visible, then `…`"* already has an
                  implementation — a `<details>` disclosure that opens on Enter
                  and on Space, closes on Escape and renders open-able markup to
                  a static suite. Hand-rolling a header menu beside it would be
                  the second dialog rule 36 forbids. Its own docstring says a
                  menu holding ONE item is *"a button wearing a costume"*, and
                  that is true here too: when the server's action set offers
                  neither verb the whole control is absent rather than empty.

                  ⚠ **THE INVENTORY FRAME ON PAGE 36 DRAWS THESE TWO INLINE**
                  (`Assign` · `Edit` · `Delete`, no `…`). Two frames of one
                  drawing, so B14 rule 37 applies: the prose is the enumeration
                  and the frame is the illustration, and the shape both agree on
                  is that the two verbs are reachable. Recorded, not followed
                  silently. */}
              {(hasAction(asset, "edit") || hasAction(asset, "delete")) && (
                <RowActionsMore label={t("table.rowActions.more")}>
                  {hasAction(asset, "edit") && (
                    <RowMenuAction
                      label={t("assets.action.edit")}
                      icon={<PencilIcon />}
                      reason={writeBlockedReason}
                      /* `AST-B-12`'s door is unchanged — a full-page screen
                         since `CR-028` W4, so this NAVIGATES. */
                      onClick={() => navigate(tenantPath(assetEditPath(asset.id)))}
                    />
                  )}
                  {hasAction(asset, "delete") && (
                    <RowMenuAction
                      label={t("assets.action.delete")}
                      icon={<TrashIcon />}
                      danger
                      reason={writeBlockedReason}
                      onClick={() => setPending("delete")}
                    />
                  )}
                </RowActionsMore>
              )}
            </>
          }
          tabs={headerTabs}
          activeTabId={active}
          tabsLabel={t("assets.detail.tabsLabel")}
          onTabSelect={(tab) => selectTab(tab.id)}
        />
      </div>

      <RefusalNotice refusal={refusal} />

      {/* CR-028 AST-W2 T3: the repeated Classification panel is REMOVED — the
          three BR-AST-044 classifications live INSIDE Specifications now
          (B16 §4.8's measured drift: "Classification panel repeated above
          every tab (not in r10)"). */}

      {active === "overview" && (
        <OverviewTab
          asset={asset}
          measuring={measuring}
          device={device}
          regional={props}
          sizeNames={sizeNames}
          t={translate}
          canWriteReason={writeBlockedReason}
          onReassign={() => navigate(tenantPath(assetReassignPath(asset.id)))}
          onEdit={setEditing}
        />
      )}
      {active === "reads" && (
        <ReadsTab asset={asset} client={client} regional={props} t={translate} />
      )}
      {active === "export" && asset.linked_meter !== null && (
        <ExportTab asset={asset} client={client} regional={props} t={translate} />
      )}
      {active === "assignments" && (
        <AssignmentsTab assetId={asset.id} client={client} regional={props} t={translate} />
      )}
      {active === "work" && (
        <WorkTab
          asset={asset}
          client={client}
          regional={props}
          t={translate}
          canWriteReason={writeBlockedReason}
          raiseReason={raiseReason}
          onLog={() => navigate(tenantPath(assetMaintenanceNewPath(asset.id)))}
        />
      )}
      {active === "audit" && (
        <section className={SECTION}>
          <h3>{t("assets.detail.tab.audit")}</h3>
          {/* BR-AST-019 + BR-AUD-010 (CONFIRMED — render AND link): the tab is
              a read-only WINDOW into the one audit_log, scoped to this asset,
              drawn by the SAME component premises/units/accounts use
              (DEF-579's fix; PO on assets: "We did that in Cr23"). */}
          <AuditTab entityType="asset" entityId={asset.id} t={translate} regional={props} />
        </section>
      )}

      {/* CR-028 AST-W4: the repair / retire / reassign MODALS are gone — the
          header buttons and panels above navigate to AST-06/07/08. */}
      {/* `AST-B-25` — the pencil's dialog. One modal, five panels, and the
          Measurement one carries a second step (screen 18) rather than a
          second dialog, so Back returns the typed values. */}
      {editing !== null && (
        <AssetPanelEditDialog
          asset={asset}
          panel={editing}
          client={client}
          regional={props}
          t={translate}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void queryClient.invalidateQueries({ queryKey: assetDetailQueryKey(asset.id) });
            fireToast(t("assets.panel.saved", { asset: asset.asset_no }));
          }}
        />
      )}

      {pending === "delete" && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): delete an asset.
          confirmVariant="danger"
          title={t("assets.confirm.deleteTitle", { asset: asset.asset_no })}
          consequence={t("assets.confirm.deleteBody")}
          confirmLabel={t("assets.confirm.deleteAction")}
          working={remove.isPending}
          onConfirm={() => remove.mutate(asset)}
          onCancel={() => setPending(null)}
        />
      )}
    </div>
  );
}

// ── Overview — the SIX panels screen 08 draws (CR-092 wave C lane 1) ───────
//
// ⚠ **THIS REPLACES FOUR PANELS WITH SIX, AND THE CUT IS THE WHOLE POINT.**
// The as-built drew `Specifications` (23 rows mixing identity, metering
// configuration, physical build, install facts, location and end-of-life),
// `Assignment`, `Warranty & supplier` and `Lifecycle`. Screen 08 cuts the same
// facts by the QUESTION each answers: `Assignment` · `What's due` ·
// `Measurement` · `Device` · `Cost & value` · `Lifecycle`. **Not one row is
// renamed and not one fact is removed** — only the panel names change, and the
// blueprint's own carry-over table reconciles every one of the 38.
//
// ⚠ **THE PANEL SET IS DERIVED, NEVER WRITTEN PER SCREEN** (`AST-R-08`'s twin
// of `assetDetailTabsFor`). A new kind changes `assetOverviewPanelsFor` and
// nothing else. **The ORDER is fixed and does not vary by kind** (`AST-R-11`):
// a kind that skips a panel closes the gap, it never reorders, so somebody who
// learns this screen on a meter does not have to re-learn it on a device.
//
// ⚠ **TWO FACTS STOP BEING SAID TWICE** (`AST-R-09`): the asset number is the
// title and no longer also a row, and the status is the pill and no longer also
// row 21 of Specifications. Saying a fact twice makes neither copy
// authoritative, and the header carries the COMPLETE value in both cases —
// which is the test for the difference between a summary and a repeat.

/** Every Overview panel any kind can own, in the ONE order they are read. */
export const ASSET_OVERVIEW_PANELS = [
  "assignment",
  "due",
  "measurement",
  "device",
  "cost",
  "lifecycle",
] as const;

export type AssetOverviewPanel = (typeof ASSET_OVERVIEW_PANELS)[number];

/**
 * `AST-R-08` for panels: ONE function decides the set, from the asset.
 *
 * ⚠ **ONLY `measurement` VARIES, AND THAT IS `AST-R-04` RATHER THAN A CHOICE:**
 * multiplier, unit of measure, register digits and read method belong to
 * measuring kinds — the same reasoning that gives a plain device no Reads tab,
 * applied one level down. An exporting inverter keeps the panel for its export
 * capacity alone: a capacity in kW, never money (`BR-AST-025`).
 *
 * ⚠ **EVERY OTHER PANEL IS PRESENT ON EVERY KIND, AND THE DRAWING'S OWN
 * SUB-METER FRAME DISAGREES.** Figure 11 draws a sub-meter with FOUR panels,
 * omitting `What's due` and `Cost & value`; the blueprint's per-kind table in
 * the same document says `What's due ✏ 2 fields` and `Cost & value ✏ 6` on all
 * four kinds, and `AST-R-03` says absence by DATA is DRAWN as a dash while only
 * absence by KIND is silent. The table carries a per-kind enumeration that can
 * be re-read and the frame does not, so the table wins — and the divergence is
 * FILED rather than followed silently (`DEF-MET-5001`).
 */
export function assetOverviewPanelsFor(
  asset: Pick<AssetDetail, "tab" | "export_capacity_kw">,
): AssetOverviewPanel[] {
  const measures =
    isMeasuringCategory(asset.tab) ||
    (asset.export_capacity_kw !== null && asset.export_capacity_kw !== undefined);
  return ASSET_OVERVIEW_PANELS.filter((panel) => panel !== "measurement" || measures);
}

/**
 * `AST-B-22` — the header earns its attention strip.
 *
 * ⚠ **PRESENT ONLY WHEN SOMETHING NEEDS DOING, ABSENT OTHERWISE, AND THE
 * ABSENCE IS THE FEATURE.** A meter whose test is eleven days overdue looked
 * exactly like a healthy one until you scrolled to the fifth panel. Silence
 * when healthy costs nothing and is what makes the strip worth reading when it
 * appears — so this returns `null` on a healthy asset and the caller draws
 * nothing at all, rather than an empty bar.
 *
 * ⚠ **THE SPECIFICATION SAYS FIVE SERVED FIELDS AND THEY ARE FOUR.**
 * `asset_dict()["next_test"]` and `lifecycle.certification_due` are **the same
 * call** — `next_test_date(asset)` — served under two names on one payload, so
 * a condition written over both writes one condition twice
 * (`CR-092-lane2-detail-step1.md` §2.4). The four are `test_due`,
 * `certification_due`, `warranty_covered` and `status`.
 *
 * ⚠ **TWO REGISTERS, AND THE DRAWING IS EXPLICIT ABOUT WHY.** An OVERDUE test
 * carries the one control that resolves it; an EXPIRED warranty carries none,
 * because there is nothing to *do* about it. A strip where every line offers a
 * button is a strip where the button means nothing.
 */
export function assetAttention(
  asset: Pick<AssetDetail, "test_due" | "valuation" | "lifecycle">,
): { key: "testOverdue" | "warrantyEnded"; date: string | null; raise: boolean } | null {
  if (asset.test_due) {
    return { key: "testOverdue", date: asset.lifecycle.certification_due, raise: true };
  }
  if (asset.valuation.warranty_covered === false) {
    return { key: "warrantyEnded", date: asset.valuation.warranty_end, raise: false };
  }
  return null;
}

/** The strip itself. Drawn at 8×12 on a 3px rule, per screen 08's spacing.
 *
 *  ⚠ **EXPORTED 2026-09-13 AND THE EXPORT IS THE WHOLE FIX.** All six redrawn
 *  figures of blueprint section 05 (screens 22–27) carry the caption clause
 *  *"THE FIVE-SLOT HEADER FROM SCREEN 08 WITH ITS ATTENTION STRIP"*, and the
 *  strip was correct, tested and **module-private**, so five sixths of the
 *  action screens could not reach it: a person reassigning a meter whose test
 *  is eleven days overdue saw no sign of it while they acted. `AssetFlowShell`
 *  MOUNTS this one — it does not copy it (hard-won law 2), which is why this is
 *  one keyword and not a second component. */
export function AttentionStrip(props: {
  asset: AssetDetail;
  regional: RegionalProps;
  t: Translator;
  raiseReason: string | null;
}) {
  const { asset, t } = props;
  const { timeZone, dateFormat } = useRegional(props.regional);
  const attention = assetAttention(asset);
  if (attention === null) {
    return null;
  }
  const danger = attention.raise;
  // ⚠ ALL THREE OF THIS STRIP'S ALARMED DECLARATIONS RENDERED NOTHING UNTIL
  // 2026-09-12, SO THE DANGER STATE DREW EXACTLY THE CALM ONE (DEF-SHL-5088).
  // A tone here is a SCALE and never a bare word: the border and the text each
  // asked for the bare word, which generates no rule at all, and the tint asked
  // for a bare custom property this repo declares nowhere — which COMPILES and
  // is then dropped by the browser. That is why the class check could name two
  // of the three and not the third, and why a second guard now reads the
  // properties an arbitrary value names. The step-500 rule with a step-100 fill
  // is the house idiom for this shape; the retire wizard's warning strip is the
  // worked example.
  //
  // ⚠ AND THIS COMMENT IS OUT HERE RATHER THAN INSIDE THE className
  // EXPRESSION, WHICH IS NOT TIDINESS. The extractor reads every quoted and
  // backticked fragment inside a className expression as a class this file asks
  // for, so an explanation written in there is reported as the very defect it
  // explains — measured twice while fixing this line. Same rule as
  // components/Button.tsx's: describe the shape, and keep the prose outside.
  return (
    <span
      data-attention={attention.key}
      className={
        "mb-2 flex flex-wrap items-center gap-2 border-l-[3px] py-2 pl-3 text-base " +
        (danger
          ? "border-l-danger-500 bg-danger-100 text-danger-700"
          : `border-l-divider bg-surface ${MUTED}`)
      }
    >
      {/* B14 rule 33: a FACT caps at six words. Two, then a date. */}
      <span className="font-semibold">
        {danger && "⚠ "}
        {t(`assets.attention.${attention.key}`)}
      </span>
      {attention.date !== null && (
        <>
          <span aria-hidden="true">·</span>
          <DateCell value={attention.date} timeZone={timeZone} dateFormat={dateFormat} />
        </>
      )}
      {/* The drawing's own split: the overdue line carries the control that
          resolves it — the SAME destination `BR-WRK-056` already names — and
          the quieter line carries none. */}
      {attention.raise && (
        <RaiseWorkOrderControl asset={asset} reason={props.raiseReason} t={t} />
      )}
    </span>
  );
}

/** The pencil, once. `AST-B-25`: it opens the edit form AT THIS GROUP, never a
 *  page holding every fact about the asset. `BR-SHL-025` through `RowAction`:
 *  a clerk without write sees it disabled WITH its reason, never hidden, and a
 *  RETIRED asset shows none at all — `update_asset` opens by testing
 *  `STAGE_TERMINAL` and refusing before it validates anything, so a pencil
 *  there would be a control that cannot work (hard-won law 2's mirror). */
function PanelPencil(props: {
  panel: AssetOverviewPanel;
  t: Translator;
  reason: string | null;
  onEdit: (panel: AssetOverviewPanel) => void;
}) {
  return (
    <RowActions>
      <RowAction
        label={props.t(`assets.panel.edit.${props.panel}`)}
        icon={<PencilIcon />}
        reason={props.reason}
        testId={`edit-${props.panel}`}
        onClick={() => props.onEdit(props.panel)}
      />
    </RowActions>
  );
}

/** One panel frame — heading left, its pencil right. */
function OverviewPanel(props: {
  title: string;
  pencil?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <section className={SECTION}>
      <div className="mb-2 flex items-start justify-between gap-3">
        <h3 className="!mb-0">{props.title}</h3>
        {props.pencil}
      </div>
      <dl className={FACTS} data-asset-facts="">
        {props.children}
      </dl>
      {props.footer}
    </section>
  );
}

function Fact(props: { label: string; children: ReactNode }) {
  return (
    <>
      <dt>{props.label}</dt>
      <dd>{props.children}</dd>
    </>
  );
}

function OverviewTab(props: {
  asset: AssetDetail;
  measuring: boolean;
  device: boolean;
  regional: RegionalProps;
  sizeNames: ReadonlyMap<string, string>;
  t: Translator;
  canWriteReason: string | null;
  onReassign: () => void;
  onEdit: (panel: AssetOverviewPanel) => void;
}) {
  const { asset, t } = props;
  const panels = assetOverviewPanelsFor(asset);
  // ⚠ **A RETIRED ASSET SHOWS NO PENCIL AT ALL, AND THAT IS NOT A STYLE
  // CHOICE.** `update_asset` opens by testing `STAGE_TERMINAL` and raising
  // `BIZ_IMMUTABLE` **before it validates anything**, and `row_actions`
  // answers `["view"]` for the same state — so a pencil there is a control
  // that cannot work, which hard-won law 2's mirror says is worse than an
  // absent one. The server and the screen read the SAME action set, so they
  // cannot drift apart.
  const editable = hasAction(asset, "edit");
  const pencilFor = (panel: AssetOverviewPanel): ReactNode =>
    editable ? (
      <PanelPencil panel={panel} t={t} reason={props.canWriteReason} onEdit={props.onEdit} />
    ) : undefined;
  const body: Record<AssetOverviewPanel, ReactNode> = {
    assignment: (
      <AssignmentPanel
        key="assignment"
        asset={asset}
        t={t}
        canWriteReason={props.canWriteReason}
        onReassign={props.onReassign}
      />
    ),
    due: (
      <DuePanel
        key="due"
        asset={asset}
        regional={props.regional}
        t={t}
        pencil={pencilFor("due")}
      />
    ),
    measurement: (
      <MeasurementPanel
        key="measurement"
        asset={asset}
        measuring={props.measuring}
        sizeNames={props.sizeNames}
        t={t}
        pencil={pencilFor("measurement")}
      />
    ),
    device: <DevicePanel key="device" asset={asset} measuring={props.measuring} t={t} pencil={pencilFor("device")} />,
    cost: (
      <CostValuePanel
        key="cost"
        asset={asset}
        regional={props.regional}
        t={t}
        pencil={pencilFor("cost")}
      />
    ),
    lifecycle: (
      <LifecyclePanel
        key="lifecycle"
        asset={asset}
        regional={props.regional}
        t={t}
        pencil={pencilFor("lifecycle")}
      />
    ),
  };
  // Screen 08's two columns: the first three panels left, the rest right. The
  // ORDER within the reading sequence is `ASSET_OVERVIEW_PANELS` and the split
  // point moves with the set, so a kind missing Measurement closes the gap
  // instead of leaving a hole (`AST-R-11`).
  const half = Math.ceil(panels.length / 2);
  return (
    <>
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-4 max-md:grid-cols-1">
        <div className="flex flex-col">{panels.slice(0, half).map((id) => body[id])}</div>
        <div className="flex flex-col">{panels.slice(half).map((id) => body[id])}</div>
      </div>
      {/* `CR-161-BRC10` W3 · `DEF-AST-9171` — Asset detail's slot: every asset
          field placed View here. Nothing at all for a tenant with none. */}
      <CustomFieldsView
        entity="assets"
        screen="S50"
        values={asset.custom_data ?? {}}
        formatDate={(iso) => iso}
      />
    </>
  );
}

/** BR-AST-039: the LIVE billing chain Premises → Unit → active Account —
 *  the account leg is customers' own row now, never a fabricated name.
 *
 *  ⚠ **NO PENCIL, ON ANY KIND, AND THE PANEL SAYS SO.** Premises, unit and
 *  account are not typed on this screen: they change through Reassign, which
 *  mints a service point and takes a final read. A pencil here would offer a
 *  shortcut that corrupts the chain. */
function AssignmentPanel(props: {
  asset: AssetDetail;
  t: Translator;
  canWriteReason: string | null;
  onReassign: () => void;
}) {
  const { asset, t } = props;
  const tenantPath = useTenantPath();
  // ⚠ **THE SECOND READ OF `billing_chain` ON THIS SCREEN, AND IT WAS THE ONE
  // STILL THROWING.** The header's read was defended on 2026-09-13 and this
  // one was not, so a payload with no chain simply moved the blank page's
  // error from `premises_id` to `account` — measured in a browser, not
  // inferred. Every row below already states its own absence, so the empty
  // chain draws *Inventory (unassigned)* and two dashes rather than a stack
  // trace.
  const chain = asset.billing_chain ?? EMPTY_BILLING_CHAIN;
  const account = chain.account;
  // Only a behind-the-meter device has one; a meter's `linked_meter` is null
  // and a sub-meter's relationship is its master, above.
  const linkedMeter = asset.tab === "behind_the_meter" ? asset.linked_meter : null;
  return (
    <OverviewPanel
      title={t("assets.detail.assignment")}
      footer={
        <>
          {asset.net_metering && (
            <p className={`m-0 mt-3 text-sm ${MUTED}`}>{t("assets.assignment.netMetering")}</p>
          )}
          {(hasAction(asset, "reassign") || hasAction(asset, "assign")) && (
            <div className="mt-3">
              <GuardedButton
                label={
                  hasAction(asset, "assign")
                    ? t("assets.action.assign")
                    : t("assets.action.reassign")
                }
                reason={props.canWriteReason}
                onClick={props.onReassign}
              />
            </div>
          )}
        </>
      }
    >
      {asset.service != null && (
        <Fact label={t("assets.col.service")}>{serviceLabel(asset.service, t)}</Fact>
      )}
      {/* `AST-R-07` — every kind names what it hangs off, and names it as a
          LINK. `parent_asset_id` has been served all along while the cell was
          plain text: a dead end with the id sitting right beside it.

          ⚠ **A DEVICE HANGS OFF A DIFFERENT THING AND THE LABEL NOW SAYS SO
          (screen 08 gap `08-6`).** Figure 11 gives a sub-meter `Parent master`;
          figure 12 gives a backflow preventer `Linked meter  W-5001 →`. They
          are not the same relationship — one is a metering hierarchy, the other
          is the meter a device sits behind — and the row read `Parent / master`
          for both because `parent_asset_no` happened to serve both. `linked_meter`
          is its own served object and has never been read on this panel. */}
      {linkedMeter !== null ? (
        <Fact label={t("assets.chain.linkedMeter")}>
          <Link className={LINK} to={tenantPath(assetDetailPath(linkedMeter.id))}>
            {linkedMeter.asset_no}
          </Link>
        </Fact>
      ) : (
        asset.parent_asset_no !== null && (
          <Fact label={t("assets.col.parent")}>
            {asset.parent_asset_id != null ? (
              <Link className={LINK} to={tenantPath(assetDetailPath(asset.parent_asset_id))}>
                {asset.parent_asset_no}
              </Link>
            ) : (
              asset.parent_asset_no
            )}
          </Fact>
        )
      )}
      <Fact label={t("assets.chain.premises")}>
        {chain.premises_id === null ? (
          <span className={`italic ${MUTED}`}>{t("assets.inventoryUnassigned")}</span>
        ) : (
          <Link className={LINK} to={tenantPath(premisesDetailPath(chain.premises_id))}>
            {chain.premise_no ?? chain.premise_address}
          </Link>
        )}
      </Fact>
      <Fact label={t("assets.chain.unit")}>
        {chain.unit_id === null ? (
          <AssetDash />
        ) : (
          <Link className={LINK} to={tenantPath(unitDetailPath(chain.unit_id))}>
            {/* DEF-SHL-6348 — words, never the id (B14 rule 31). */}
            {chain.unit_label ?? t("metering.units.noNumber")}
          </Link>
        )}
      </Fact>
      {/* The chain ran Premises → Unit → DEAD END, and the dead end was the
          money. The id is on the payload; only the anchor is new. */}
      <Fact label={t("assets.chain.account")}>
        {account === null ? (
          <AssetDash />
        ) : (
          <Link className={LINK} to={tenantPath(accountDetailPath(account.id))}>
            {[account.account_no, account.customer_name].filter((part) => part).join(" · ")}
          </Link>
        )}
      </Fact>
      {/* ⚠ **THE ROW IS DRAWN EVEN WHEN THERE ARE NONE (gap `08-5`)**, and the
          distinction is `AST-R-03`'s: absence by KIND is silent, absence by
          DATA is STATED. A meter with no sub-meters is a meter that was ASKED
          and has none — figure 10 draws exactly that, a dash — while a device,
          which cannot have any, is a kind and keeps its silence. Omitting the
          row made the two look identical. */}
      {asset.tab !== "behind_the_meter" && (
        <Fact label={t("assets.chain.subAssets")}>
          {asset.sub_assets.length === 0 ? (
            <AssetDash />
          ) : (
            asset.sub_assets.map((child, index) => (
              <span key={child.id}>
                {index > 0 && ", "}
                <Link className={LINK} to={tenantPath(`${ASSETS_ROUTE}/${child.id}`)}>
                  {child.asset_no}
                </Link>
              </span>
            ))
          )}
        </Fact>
      )}
    </OverviewPanel>
  );
}

/**
 * `What's due` — the things that FALL DUE, gathered from three as-built panels.
 *
 * Test & certification came whole; the warranty DATE came from `Warranty &
 * supplier` while its TERM stayed with the money; certification due and the
 * replacement forecast came out of Lifecycle. Each is a thing that expires, and
 * a person who opens an asset asking *does anything need doing* reads one
 * panel instead of three.
 *
 * ⚠ **ONE NEXT-DUE ROW, NOT THE TWO THE FRAME DRAWS.** Figure 10 draws `Next
 * due` and `Certification due` as separate rows. They are ONE served fact:
 * `next_test_date()` returns the explicit `certification_due` column when it is
 * captured and the `BR-AST-007` derivation otherwise, and both keys on the
 * payload are that same call. Drawing both would print one value twice, or a
 * value and a dash that read as two facts — `AST-R-09` exactly. Filed rather
 * than followed (`DEF-MET-5001`).
 */
function DuePanel(props: {
  asset: AssetDetail;
  regional: RegionalProps;
  t: Translator;
  pencil?: ReactNode;
}) {
  const { asset, t } = props;
  const { timeZone, dateFormat } = useRegional(props.regional);
  const specs = asset.specs;
  const valuation = asset.valuation;
  const rollup = asset.cost_rollup;
  return (
    <OverviewPanel title={t("assets.detail.duePanel")} pencil={props.pencil}>
      <Fact label={t("assets.testCert.requirement")}>
        {specs.test_interval_months === null ? (
          <AssetDash />
        ) : (
          t("assets.due.everyMonths", { months: specs.test_interval_months })
        )}
      </Fact>
      <Fact label={t("assets.spec.lastTest")}>
        {specs.last_test_date === null ? (
          <AssetDash />
        ) : (
          <DateCell value={specs.last_test_date} timeZone={timeZone} dateFormat={dateFormat} />
        )}
      </Fact>
      <Fact label={t("assets.testCert.nextDue")}>
        {asset.lifecycle.certification_due === null ? (
          <AssetDash />
        ) : (
          <span className="inline-flex flex-wrap items-center gap-2">
            <DateCell
              value={asset.lifecycle.certification_due}
              timeZone={timeZone}
              dateFormat={dateFormat}
            />
            {asset.test_due && (
              <StatusPill tone="danger">{t("assets.lifecycle.overdue")}</StatusPill>
            )}
          </span>
        )}
      </Fact>
      {/* Gap `08-8` — figures 10 and 12 both label this row `Warranty ends`.
          It is a NEW key rather than a re-wording of `assets.valuation.coverEnds`,
          which the retire wizard and the add wizard also print; changing a
          shared value to fix one panel is how two screens quietly stop
          agreeing. Those two still read `Cover ends` and it is reported. */}
      <Fact label={t("assets.valuation.warrantyEnds")}>
        {valuation.warranty_end === null ? (
          <AssetDash />
        ) : (
          <span className="inline-flex flex-wrap items-center gap-2">
            <DateCell value={valuation.warranty_end} timeZone={timeZone} dateFormat={dateFormat} />
            {valuation.warranty_covered === true && (
              <StatusPill tone="success">{t("assets.valuation.covered")}</StatusPill>
            )}
            {valuation.warranty_covered === false && (
              <StatusPill tone="danger">{t("assets.valuation.expired")}</StatusPill>
            )}
          </span>
        )}
      </Fact>
      <Fact label={t("assets.lifecycle.replacementForecast")}>
        {asset.lifecycle.replacement_year ?? <AssetDash />}
      </Fact>
      {/* `AST-B-16`'s second served fact. `0` here is a MEASUREMENT — the query
          ran and found no open job — so it renders as a number and not a dash;
          an absent rollup (an older payload) is the dash. */}
      <Fact label={t("assets.due.openWorkOrders")}>
        {rollup === undefined ? <AssetDash /> : <span data-open-work="">{rollup.open_work_orders}</span>}
      </Fact>
    </OverviewPanel>
  );
}

/**
 * `Measurement` — everything that decides what a reading MEANS.
 *
 * ⚠ **CONNECTION SIZE MOVED HERE OUT OF THE DEVICE GROUP, AND IT IS A DECISION
 * RATHER THAN TIDINESS.** All five of `BILLING_AFFECTING_FIELDS` —
 * `multiplier`, `unit`, `net_metering`, `service`, `size_class` — now sit in
 * ONE panel, so exactly one pencil on this screen can restate what a reading
 * means and one confirmation covers it. Left in Device, two panels would each
 * need the same warning and a person could meet it from either.
 *
 * ⚠ **ALLOCATION BELONGS TO SUB-METERS ONLY** (`AST-R-05`), and a null share
 * means *metered, not allocated* — served as null and NEVER as a zero, which
 * would read as *allocated nothing*.
 */
function MeasurementPanel(props: {
  asset: AssetDetail;
  measuring: boolean;
  sizeNames: ReadonlyMap<string, string>;
  t: Translator;
  pencil?: ReactNode;
}) {
  const { asset, t } = props;
  const specs = asset.specs;
  const sub = asset.tab === "sub_meters";
  return (
    <OverviewPanel title={t("assets.detail.measurementPanel")} pencil={props.pencil}>
      {props.measuring && (
        <Fact label={t("assets.col.readMethod")}>{asset.read_method_name ?? <AssetDash />}</Fact>
      )}
      {offersConnectionSize(asset.tab, asset.service) && (
        <Fact label={t("assets.col.sizeClass")}>
          {/* ⛔ BR-AST-530 / BR-AST-500 — the two absences are DIFFERENT
              sentences, which is the whole reason this is not a bare dash: a
              null that renders as an em-dash reads as *not recorded* when it
              can equally mean *the product cannot record it*. NOT RECORDED is a
              lawful state and it says what it costs. */}
          {sizeClassName(asset.size_class, props.sizeNames) ?? (
            <span className={`italic ${MUTED}`}>{t("assets.sizeClassUnrecorded")}</span>
          )}
        </Fact>
      )}
      {props.measuring && (
        <>
          <Fact label={t("assets.form.multiplier")}>
            {/* r10 draws ×10, never 10.000000 — display trimming only. */}
            {t("assets.multiplierShort", { multiplier: trimDecimalZeros(asset.multiplier) })}
          </Fact>
          <Fact label={t("assets.form.uom")}>{asset.unit ?? <AssetDash />}</Fact>
          {/* BR-AST-015: the stored value or the ruled default of 9 — and the
              copy says which, so nobody reads a default as data. */}
          <Fact label={t("assets.spec.registerDigits")}>
            {registerDigitsOf(specs.register_digits)}
            {specs.register_digits === null && (
              <span className={`italic ${MUTED}`}> {t("assets.spec.registerDigitsDefault")}</span>
            )}
          </Fact>
        </>
      )}
      {sub && (
        <>
          <Fact label={t("assets.spec.allocationShare")}>
            {specs.allocation_share_pct != null ? (
              // Hard rule 2: a percentage DISPLAYS at 2 dp.
              displayPct(specs.allocation_share_pct)
            ) : (
              <span className={`italic ${MUTED}`}>{t("assets.spec.allocationShareMetered")}</span>
            )}
          </Fact>
          {/* `AST-B-27` — the four ratified words, and the first these values
              have ever had on a screen. PO 2026-09-12: *"this is correct -
              build it"*. The CODE is never shown (B14 rule 31). */}
          <Fact label={t("assets.spec.allocationRule")}>
            {specs.allocation_rule != null && specs.allocation_rule !== "" ? (
              t(`assets.allocationRule.${specs.allocation_rule}`, {
                defaultValue: specs.allocation_rule,
              })
            ) : (
              <AssetDash />
            )}
          </Fact>
          <Fact label={t("assets.spec.lossTolerance")}>
            {specs.loss_tolerance_pct != null ? (
              displayPct(specs.loss_tolerance_pct)
            ) : (
              <AssetDash />
            )}
          </Fact>
        </>
      )}
      {asset.export_capacity_kw != null && (
        // `AST-R-06`: a capacity in kW, never money (`BR-AST-025`).
        <Fact label={t("assets.col.exportCapacity")}>
          {t("assets.exportCapacityKw", { kw: trimDecimalZeros(asset.export_capacity_kw) })}
        </Fact>
      )}
    </OverviewPanel>
  );
}

/** `Device` — what the thing IS. Everything here is descriptive and none of it
 *  restates anything, which is why this pencil carries no confirmation and no
 *  pill: a person learns that this panel is the safe one. */
function DevicePanel(props: {
  asset: AssetDetail;
  measuring: boolean;
  t: Translator;
  pencil?: ReactNode;
}) {
  const { asset, t } = props;
  const specs = asset.specs;
  const meterType = asset.classifications.meter_type;
  return (
    <OverviewPanel title={t("assets.detail.devicePanel")} pencil={props.pencil}>
      <Fact label={t("assets.col.assetType")}>
        {asset.classifications.asset_type.name}
        {asset.net_metering && (
          /* r10's Type fold: "Meter · net (bidirectional)". */
          <span className={MUTED}> · {t("assets.spec.netFold")}</span>
        )}
      </Fact>
      <Fact label={t("assets.col.meterType")}>
        {meterType !== null ? (
          meterType.name
        ) : props.measuring ? (
          <span className={`italic ${MUTED}`}>{t("assets.meterTypeUnclassified")}</span>
        ) : (
          <span className={`italic ${MUTED}`}>{t("assets.meterTypeNotApplicable")}</span>
        )}
      </Fact>
      {/* `AST-R-15` is about CAPTURE, not display: two columns are two fields
          on the FORM, and displaying them joined here is good density. */}
      <Fact label={t("assets.form.manufacturerModel")}>
        {[asset.manufacturer, asset.model].filter((part) => part).join(" · ") || <AssetDash />}
      </Fact>
      <Fact label={t("assets.col.serial")}>{asset.serial_no ?? <AssetDash />}</Fact>
      {/* Served on every row since the module shipped and rendered NOWHERE —
          a column with a reader and no writer, which is hard-won law 2 in a
          third form. The asset import writes it; no screen ever did. */}
      <Fact label={t("assets.spec.externalRef")}>
        <span data-external-ref="">{asset.external_ref ?? <AssetDash />}</span>
      </Fact>
      <Fact label={t("assets.spec.formClass")}>{specs.form_class ?? <AssetDash />}</Fact>
      <Fact label={t("assets.spec.firmware")}>{specs.firmware_version ?? <AssetDash />}</Fact>
      <Fact label={t("assets.spec.seal")}>{specs.seal_no ?? <AssetDash />}</Fact>
    </OverviewPanel>
  );
}

/**
 * `Cost & value` — what was paid, what it is worth now, and what it has cost to
 * keep running. `BR-AST-047` / §10-D3: every figure here is CAPTURED, displayed
 * at 2 dp from its stored 4, and posted NOWHERE.
 */
function CostValuePanel(props: {
  asset: AssetDetail;
  regional: RegionalProps;
  t: Translator;
  pencil?: ReactNode;
}) {
  const { asset, t } = props;
  const { timeZone, dateFormat } = useRegional(props.regional);
  const valuation = asset.valuation;
  const rollup = asset.cost_rollup;
  const currency = rollup?.currency ?? valuation.currency;
  return (
    <OverviewPanel title={t("assets.detail.costPanel")} pencil={props.pencil}>
      <Fact label={t("assets.supplier")}>{valuation.supplier ?? <AssetDash />}</Fact>
      <Fact label={t("assets.valuation.purchaseCost")}>
        {valuation.purchase_cost !== null && valuation.currency !== null ? (
          <MoneyCell amount={valuation.purchase_cost} currency={valuation.currency} />
        ) : (
          <AssetDash />
        )}
      </Fact>
      {/* `DEF-MET-4972` — the date every figure below is computed from, drawn
          nowhere in the product until wave B lane 3 put it here. Its remaining
          half — that it could not be CORRECTED from any screen — is this wave's
          `Edit · Cost & value` dialog. */}
      <Fact label={t("assets.valuation.purchaseDate")}>
        <span data-purchase-date="">
          {valuation.purchase_date === null || valuation.purchase_date === undefined ? (
            <AssetDash />
          ) : (
            <DateCell value={valuation.purchase_date} timeZone={timeZone} dateFormat={dateFormat} />
          )}
        </span>
      </Fact>
      {/* The SERVER's straight-line book value as of today — the same
          computation retire records at D4. The quiet dash when no cost or no
          life is on record; never an invented figure. */}
      <Fact label={t("assets.valuation.presentValue")}>
        <span data-present-value="">
          {valuation.present_value != null && valuation.currency !== null ? (
            <MoneyCell amount={valuation.present_value} currency={valuation.currency} />
          ) : (
            <AssetDash />
          )}
        </span>
      </Fact>
      {/* Served since CR-028 and named nowhere, while the present value it
          decides WAS shown — the same shape as the purchase date. */}
      <Fact label={t("assets.valuation.depreciationMethod")}>
        {valuation.depreciation_method != null && valuation.depreciation_method !== "" ? (
          t(`assets.depreciation.${valuation.depreciation_method}`, {
            defaultValue: valuation.depreciation_method,
          })
        ) : (
          <AssetDash />
        )}
      </Fact>
      {/* r10 and screen 08 both draw a Warranty term; NO COLUMN STORES ONE, so
          it is the honest dash and it is NOT on the edit form either — a term
          derived from two dates nobody signed would be worse than an absence.
          Filed as `DEF-MET-5002`. */}
      <Fact label={t("assets.valuation.warrantyTerm")}>
        <AssetDash />
      </Fact>
      {/* `AST-B-21`, and the PO's own words: ONE lifetime figure, both halves
          named beneath. The halves are two different arithmetics on two tables
          in two modules and neither knew about the other until this landed. */}
      <Fact label={t("assets.cost.lifetime")}>
        {rollup?.lifetime != null && currency !== null ? (
          <span data-lifetime-cost="">
            <MoneyCell amount={rollup.lifetime} currency={currency} />
            <span className={`mt-1 block text-sm ${MUTED}`}>
              {t("assets.cost.repairsHalf")}{" "}
              {rollup.maintenance != null ? (
                <MoneyCell amount={rollup.maintenance} currency={currency} />
              ) : (
                <AssetDash />
              )}
              {" · "}
              {t("assets.cost.jobsHalf")}{" "}
              {rollup.work != null ? (
                <MoneyCell amount={rollup.work} currency={currency} />
              ) : (
                <AssetDash />
              )}
            </span>
          </span>
        ) : (
          <AssetDash />
        )}
      </Fact>
      {/* ⚠ **BOTH ROWS ARE DRAWN, DASHED UNTIL THE ASSET IS RETIRED (gap
          `08-9`)**, and it is `AST-R-03` again: figure 10 draws `Book value —`
          and `Treatment —` on a LIVE meter, marked `NEW`, because the pair is
          absent by DATA rather than by kind. Rendering them only when non-null
          made a panel that grows two rows at retirement, which reads as a
          layout bug rather than as a fact arriving. */}
      <Fact label={t("assets.valuation.bookValue")}>
        {valuation.book_value_amount != null && valuation.currency !== null ? (
          <MoneyCell amount={valuation.book_value_amount} currency={valuation.currency} />
        ) : (
          <AssetDash />
        )}
      </Fact>
      <Fact label={t("assets.valuation.treatment")}>
        {valuation.book_value_treatment != null ? (
          t(`assets.retire.treatment.${valuation.book_value_treatment}`, {
            defaultValue: valuation.book_value_treatment,
          })
        ) : (
          <AssetDash />
        )}
      </Fact>
    </OverviewPanel>
  );
}

/** `Lifecycle` — when it went in, how old it is, how long it should last, and
 *  where a technician will actually find it. Every figure the SERVER's. */
function LifecyclePanel(props: {
  asset: AssetDetail;
  regional: RegionalProps;
  t: Translator;
  pencil?: ReactNode;
}) {
  const { asset, t } = props;
  const { timeZone, dateFormat } = useRegional(props.regional);
  const lifecycle = asset.lifecycle;
  return (
    <OverviewPanel title={t("assets.detail.lifecyclePanel")} pencil={props.pencil}>
      <Fact label={t("assets.col.installed")}>
        {asset.install_date === null ? (
          <AssetDash />
        ) : (
          <DateCell value={asset.install_date} timeZone={timeZone} dateFormat={dateFormat} />
        )}
      </Fact>
      <Fact label={t("assets.lifecycle.age")}>
        {lifecycle.age_months === null ? (
          <AssetDash />
        ) : lifecycle.age_months < 12 ? (
          t("assets.lifecycle.ageMonths", { months: lifecycle.age_months })
        ) : (
          t("assets.lifecycle.ageYears", ageParts(lifecycle.age_months))
        )}
      </Fact>
      <Fact label={t("assets.lifecycle.expectedLife")}>
        {lifecycle.expected_life_years === null ? (
          <AssetDash />
        ) : (
          t("assets.lifecycle.expectedLifeYears", { years: lifecycle.expected_life_years })
        )}
      </Fact>
      {/* `Location note`, never `address` — the address lives on the premises
          and is walked to (hard rule 8). This is where a technician will
          actually find it in the yard. */}
      <Fact label={t("assets.spec.locationNote")}>{asset.specs.location_note ?? <AssetDash />}</Fact>
      {asset.retire_date !== null && (
        <>
          <Fact label={t("assets.spec.retiredOn")}>
            <DateCell value={asset.retire_date} timeZone={timeZone} dateFormat={dateFormat} />
            {asset.retire_reason !== null && (
              <span className={`italic ${MUTED}`}>
                {" "}
                {t(`assets.retire.reason.${asset.retire_reason}`, {
                  defaultValue: asset.retire_reason,
                })}
              </span>
            )}
          </Fact>
          <Fact label={t("assets.spec.replacedBy")}>{asset.replaced_by ?? <AssetDash />}</Fact>
        </>
      )}
    </OverviewPanel>
  );
}

// ── Reads (SERVED — CR-028 AST-W2 T4, DEF-475 closed) ──────────────────────

function ReadRows(props: {
  rows: AssetReadRow[];
  showExport: boolean;
  regional: RegionalProps;
  t: Translator;
}) {
  const { t } = props;
  const { timeZone, dateFormat } = useRegional(props.regional);
  // ⚠ **DRAWN ONLY WHEN THERE IS SOMETHING TO TELL APART**, which is the same
  // reasoning the Export column already follows: a flat meter's read log would
  // otherwise carry a column repeating one word on every row. On a time-of-use
  // or demand meter four rows share one date and nothing said which register
  // each was — screen 09, Figure 15.
  const channels = new Set(
    props.rows.map((row) => row.channel).filter((channel) => channel != null && channel !== ""),
  );
  const showChannel = channels.size > 1;
  return (
    <div className="overflow-x-auto">
      <table className={TABLE}>
        <thead>
          <tr>
            <th>{t("assets.reads.date")}</th>
            {showChannel && <th>{t("assets.reads.channel")}</th>}
            <th>{t("assets.reads.reading")}</th>
            <th>{t("assets.reads.import")}</th>
            {props.showExport && <th>{t("assets.reads.export")}</th>}
            <th>{t("assets.reads.source")}</th>
            <th>{t("assets.reads.status")}</th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.read_id ?? row.date ?? ""}>
              <td>
                {row.date === null ? (
                  <AssetDash />
                ) : (
                  <DateCell value={row.date} timeZone={timeZone} dateFormat={dateFormat} />
                )}
              </td>
              {showChannel && <td>{channelLabel(row.channel, t) ?? <AssetDash />}</td>}
              <td>{row.reading !== null ? trimDecimalZeros(row.reading) : <AssetDash />}</td>
              <td>
                {/* CLAUDE.md rule 3: a quantity NEVER travels without its
                    unit — a number whose unit did not arrive is a dash, not
                    a bare figure a reader must guess at.
                    ⚠ BR-MET-051 — this table holds one row per RECORD, so a
                    demand meter's peak (BR-MET-049: "demand → +demand record")
                    sits directly under its own energy row. kW is not kWh and
                    the two are never added, so a peak is MARKED.
                    ✅ BR-MET-143 (2026-08-27, DEF-797) — it no longer falls
                    back to the raw register. This comment used to end
                    "`consumption` on a demand row is BR-MET-019's delta
                    between two maxima, which nothing bills"; a maximum register
                    now commits BR-MET-051's own VALUE, in the register's own
                    unit (kW), so both rows read the served consumption and only
                    their units differ. */}
                {isPeakChannel(row.channel) ? (
                  <PeakQuantity
                    quantity={row.consumption === null ? null : trimDecimalZeros(row.consumption)}
                    unit={row.unit}
                    t={t}
                  />
                ) : row.consumption !== null && row.unit !== null ? (
                  <UnitCell quantity={trimDecimalZeros(row.consumption)} unit={row.unit} />
                ) : (
                  <AssetDash />
                )}
              </td>
              {props.showExport && (
                <td>
                  {row.export !== null && row.export_unit !== null ? (
                    <UnitCell quantity={trimDecimalZeros(row.export)} unit={row.export_unit} />
                  ) : (
                    <AssetDash />
                  )}
                </td>
              )}
              <td data-read-source-event={row.event ?? ""}>
                {row.source ?? <AssetDash />}
                {/* DEF-WRK-10184 — BR-MET-128's event beside the source: a
                    field move-out reading reads *manual · Move-out*, never as a
                    new connection. Nothing for an ordinary read. */}
                {(row.event ?? null) !== null &&
                  ` · ${t(`metering.reads.event.${row.event ?? ""}`, { defaultValue: row.event ?? "" })}`}
              </td>
              {/* ⚠ **A PILL, AND THE WORDS ARE NOT INVENTED HERE (gap `09-3`).**
                  Figure 13 draws a green outlined `Committed`; this cell printed
                  the served CODE verbatim, under an exception claiming no signed
                  vocabulary maps a read status to display words. `DEF-MET-4969`
                  retired the identical claim about the CHANNEL column three
                  hours after it was written, by grepping the catalogue —
                  `metering.reads.status.*` ships 24 words in all eleven
                  languages and six Meter Reads files already resolve them.
                  `ReadStatusCell` is that resolution PLUS the tone, so this is
                  an import and not a second tone map. A code the catalogue does
                  not cover still renders verbatim, which is the honest fallback
                  rather than a blank. */}
              <td>
                <div className="flex flex-wrap items-center gap-2">
                  {row.status === null ? (
                    <AssetDash />
                  ) : (
                    <ReadStatusCell status={row.status} t={t} />
                  )}
                  {/* BR-MET-1189 — two readings of this register on this
                      date: which one counts. Nothing draws for a lone read. */}
                  <CountedReadingPill counts={row.counts} t={t} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReadsTab(props: {
  asset: AssetDetail;
  client: ApiClient;
  regional: RegionalProps;
  t: Translator;
}) {
  const { asset, t } = props;
  // `AST-B-19` — the fold is in the QUERY, not in the browser. `per` is the
  // house default and the pager offers the house sizes; neither is invented
  // here (`components/tableTypes.ts` owns both).
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const query = useQuery({
    queryKey: assetReadsQueryKey(asset.id, page, per),
    queryFn: () => getAssetReads(asset.id, props.client, { page, per }),
    placeholderData: (previous) => previous,
  });
  if (query.isPending) {
    return <LoadingSkeleton variant="table" />;
  }
  return (
    <>
      {/* CR-038 W5 task 8 — the trailing-12-month strip, PER REGISTER. PO:
          *"We ahve to calcualet last 12 month consumption from these readings
          and display it on account and meters"*. It sits ABOVE the read log
          because it is the answer to the question a clerk opens this tab
          with; the individual readings underneath are the evidence for it.
          `client` is PASSED (G13 — an optional prop nothing passes is dead
          UI, and this whole task existed because the meter half was not
          wired at all). */}
      <AssetUsageStrip assetId={asset.id} client={props.client} t={t} />
      {/* ⚠ A WITNESS, NOT A STYLE HOOK. A walkthrough has to be able to say it
          ARRIVED at the read log rather than that navigation did not throw
          (`DEF-WRK-4051`), and this tab's own heading is a translated string
          that changes with the catalogue. `cr070-l-the-offline-day-and-the-read.mjs`
          reads it to prove `BR-WRK-003` on the SCREEN a supervisor uses — which
          is where `DEF-MET-4101` was found and where nothing else was looking. */}
      <section className={SECTION} data-asset-reads="">
        <h3>{t("assets.detail.tab.reads")}</h3>
        {query.data === undefined ? (
          // A18 §4: a failed read says so — DISTINCT from "no reads yet".
          <p className={`m-0 text-base ${MUTED}`}>{t("assets.reads.failed")}</p>
        ) : query.data.rows.length === 0 ? (
          // The honest empty DEF-475 blocked on: the server can now make this
          // claim about ONE meter, so the screen may repeat it.
          <p className={`m-0 text-base ${MUTED}`}>{t("assets.reads.empty")}</p>
        ) : (
          <>
            {/* BR-AST-029: the net pair arrives FOLDED per date; a flat meter
                draws no Export column at all — a column of dashes on a meter
                that cannot export would read as "measured nothing", which
                nobody did. */}
            <ReadRows
              rows={query.data.rows}
              showExport={asset.net_metering}
              regional={props.regional}
              t={t}
            />
            {/* B14 rule 16 through the kit's own footer — `ListPager` is the
                one implementation for a list that is not `DataTable`, and
                these three panels are hand-built tables (`DEF-MET-4968`,
                open: `AST-B-23` converts them). It uses the same four
                `table.pager.*` keys and `table-pager*` classes `DataTable`
                uses, so every footer in the product stays one thing.
                ⚠ The TOTAL is read DATES, not rows — `asset_reads` folds a
                typed pair into one row per date, so a three-register meter
                serves three rows for one date and the count would otherwise
                disagree with the list on purpose.
                ⚠ `DEF-AST-9691` — AND SO THE FOOTER SAYS DATES. It read
                *1–4 of 4* under five rows on E-5000 (two readings kept on one
                day, `BR-MET-1189`), a count that disagreed with the table in
                the table's own words. */}
            <ListPager
              total={query.data.total}
              rangeKey="assets.reads.pagerRange"
              sizeKey="assets.reads.pagerSize"
              page={page}
              per={per}
              onPage={setPage}
              onPer={(next: PageSize) => {
                setPer(next);
                setPage(1);
              }}
            />
          </>
        )}
      </section>
    </>
  );
}

/** §5.1b (B): the inverter's Export tab — the LINKED NET METER's export
 *  records, READ-ONLY, headed "Measured by M-XXXX · net →". Never a
 *  device-stored read: a device has no register (BR-AST-044 refusal). */
function ExportTab(props: {
  asset: AssetDetail;
  client: ApiClient;
  regional: RegionalProps;
  t: Translator;
}) {
  const { asset, t } = props;
  const tenantPath = useTenantPath();
  const meter = asset.linked_meter;
  const { timeZone, dateFormat } = useRegional(props.regional);
  const [exportPage, setExportPage] = useState(1);
  const [exportPer, setExportPer] = useState<PageSize>(50);
  const query = useQuery({
    queryKey: assetReadsQueryKey(meter?.id ?? "", exportPage, exportPer),
    queryFn: () =>
      getAssetReads(meter?.id ?? "", props.client, { page: exportPage, per: exportPer }),
    enabled: meter !== null,
    placeholderData: (previous) => previous,
  });
  if (meter === null) {
    return null;
  }
  if (query.isPending) {
    return <LoadingSkeleton variant="table" />;
  }
  // `AST-B-19` — `.rows` off the page. ⚠ THE EXPORT FILTER RUNS OVER ONE PAGE,
  // which is a real narrowing and is said out loud rather than hidden: a meter
  // whose exporting dates fall outside the current page shows fewer rows here
  // than a reader expects. `AST-B-23` converts these hand-built panels to the
  // shared table, where a filter belongs in the query; until then the footer
  // below is how a clerk reaches the rest.
  const rows = (query.data?.rows ?? []).filter((row) => row.export !== null);
  return (
    <section className={SECTION}>
      <h3>{t("assets.detail.tab.export")}</h3>
      <p className={`m-0 mb-3 text-sm ${MUTED}`}>
        {t("assets.export.measuredBy")}{" "}
        <Link
          className={LINK}
          to={tenantPath(assetDetailPath(meter.id))}
        >
          {t("assets.export.open", { meter: meter.asset_no })}
        </Link>
      </p>
      {query.data === undefined ? (
        <p className={`m-0 text-base ${MUTED}`}>{t("assets.reads.failed")}</p>
      ) : rows.length === 0 ? (
        <p className={`m-0 text-base ${MUTED}`}>{t("assets.export.empty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className={TABLE}>
            <thead>
              <tr>
                <th>{t("assets.reads.date")}</th>
                <th>{t("assets.reads.export")}</th>
                <th>{t("assets.reads.source")}</th>
                <th>{t("assets.reads.status")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.export_read_id ?? row.read_id ?? row.date ?? ""}>
                  <td>
                    {row.date === null ? (
                      <AssetDash />
                    ) : (
                      <DateCell value={row.date} timeZone={timeZone} dateFormat={dateFormat} />
                    )}
                  </td>
                  <td>
                    {row.export !== null && row.export_unit !== null ? (
                      <UnitCell quantity={trimDecimalZeros(row.export)} unit={row.export_unit} />
                    ) : (
                      <AssetDash />
                    )}
                  </td>
                  <td>{row.source ?? <AssetDash />}</td>
                  <td>{row.status ?? <AssetDash />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {/* ⚠ **THIS FOOTER WAS MISSING AND THE PAGE STATE ABOVE WAS DEAD
          (`DEF-AST-5117`).** `AST-B-19` moved this panel onto the paged reader
          and gave it `exportPage`/`exportPer`, and then only the Reads panel
          got a control that sets them — so this tab read page 1 for ever,
          exactly the fault the specification was written to remove, and
          `eslint --max-warnings 0` said so at the raise site ("setExportPage is
          assigned a value but never used"). Hard-won law 2 in its purest form:
          state nothing sets is dead UI, and every test passed over it.
          ⚠ The TOTAL is the meter's READ count, not the count of exporting
          rows: the filter above runs over one page (stated there too), so the
          range reads "1–50 of 412" while the table shows the exporting few of
          those fifty. `AST-B-23`'s conversion to the shared table is what moves
          the filter into the query and makes the two agree. */}
      {query.data !== undefined && (
        <ListPager
          total={query.data.total}
          page={exportPage}
          per={exportPer}
          onPage={setExportPage}
          onPer={(next: PageSize) => {
            setExportPer(next);
            setExportPage(1);
          }}
        />
      )}
    </section>
  );
}

// ── History tabs ───────────────────────────────────────────────────────────

function AssignmentsTab(props: {
  assetId: string;
  client: ApiClient;
  regional: RegionalProps;
  t: Translator;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props.regional);
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const query = useQuery({
    queryKey: assetAssignmentsQueryKey(props.assetId, page, per),
    queryFn: () => getAssetAssignments(props.assetId, props.client, { page, per }),
    placeholderData: (previous) => previous,
  });

  if (query.isPending) {
    return <LoadingSkeleton variant="table" />;
  }
  const rows = query.data?.rows ?? [];
  return (
    <section className={SECTION}>
      <h3>{t("assets.detail.tab.assignments")}</h3>
      {/* BR-AST-017: append-only, non-overlapping — a correction closes a row
          and opens a new one, so nothing on this tab is editable. */}
      <p className={`m-0 mb-3 text-sm ${MUTED}`}>{t("assets.assignments.appendOnly")}</p>
      {rows.length === 0 ? (
        <p className={`m-0 mb-3 text-sm ${MUTED}`}>{t("assets.assignments.empty")}</p>
      ) : (
        <table className={TABLE}>
          <thead>
            <tr>
              <th>{t("assets.assignments.from")}</th>
              <th>{t("assets.assignments.to")}</th>
              <th>{t("assets.assignments.premises")}</th>
              <th>{t("assets.assignments.unit")}</th>
              <th>{t("assets.assignments.by")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <DateCell value={row.from_date} timeZone={timeZone} dateFormat={dateFormat} />
                </td>
                <td>
                  {/* Gap `11-5` — figure 17 draws a green outlined pill in the
                      TO cell, which is how every other state in the product is
                      drawn. A `<strong>` was the only bold word on the screen
                      and read as emphasis rather than as a state. */}
                  {row.to_date === null ? (
                    <StatusPill tone="success">{t("assets.assignments.current")}</StatusPill>
                  ) : (
                    <DateCell value={row.to_date} timeZone={timeZone} dateFormat={dateFormat} />
                  )}
                </td>
                {/* ⚠ **HALF OF GAP `11-4`, AND THE OTHER HALF IS BLOCKED.**
                    Figure 17 draws PREMISE and UNIT as links. `unit_id` is on
                    every row, so the unit leg is reachable and is built here.
                    **`premises_id` is NOT on the row** — `AssetAssignmentRow`
                    carries `premise_address` as text and nothing to address —
                    so the premise cell stays text rather than becoming a link
                    built from a guess. Reported, not worked around. */}
                <td>{row.premise_address ?? <AssetDash />}</td>
                <td>
                  {row.unit_label === null ? (
                    <AssetDash />
                  ) : (
                    <Link className={LINK} to={tenantPath(unitDetailPath(row.unit_id))}>
                      {row.unit_label}
                    </Link>
                  )}
                </td>
                {/* CR-028 AST-W2 T6: `by` is the resolved display NAME (or the
                    literal "System") — the server's, never a uuid rendered. */}
                <td>{row.by}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {/* `DEF-AST-5117` — the other half of `AST-B-19` on this panel. The state
          above was set by nothing until this footer existed, so an asset with a
          long history showed its newest 50 moves and no way to reach the rest.
          BR-AST-017 serves this history newest-first, which is why page one is
          the useful one and why the absence was easy to miss. */}
      {query.data !== undefined && (
        <ListPager
          total={query.data.total}
          page={page}
          per={per}
          onPage={setPage}
          onPer={(next: PageSize) => {
            setPer(next);
            setPage(1);
          }}
        />
      )}
    </section>
  );
}

/**
 * The jobs still outstanding on this asset — screen 12's `Open work` panel.
 *
 * ⚠ **THE ROWS WERE ALREADY ON THIS SCREEN AND WERE THROWN AWAY**
 * (`DEF-MET-4967`). `listAssetWorkOrders` has exactly one consumer and that
 * consumer read only `maintenance_index`, so a full list round trip was paid
 * for on every Maintenance tab open with 100% of its row payload discarded.
 * Nothing here adds a call.
 *
 * ⚠ **`isOpenOrder` IS IMPORTED AND NOT RE-TYPED.** `planned · in_progress ·
 * blocked` is `metering_seam.OPEN_WORK_ORDER_STATES` on the server and
 * `OPEN_ORDER_STATES` in `buildViews`, and a third hand-typed copy here is how
 * a list quietly stops agreeing with itself (the eleventh-service lesson).
 */
function OpenWorkPanel(props: {
  rows: readonly AssetWorkOrderRow[];
  regional: RegionalProps;
  t: Translator;
  asset: AssetDetail;
  raiseReason: string | null;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props.regional);
  const open = props.rows.filter((row) => isOpenOrder(row));
  return (
    <section className={SECTION}>
      <h3>{t("assets.work.openTitle")}</h3>
      {/* The drawing's own two sentences — six words and five (B14 rule 33),
          and the second is the one that matters: this panel is a READ of
          Work's table, and nothing here writes one. */}
      <p className={`m-0 mb-3 text-sm ${MUTED}`}>{t("assets.work.sentence")}</p>
      {open.length === 0 ? (
        <p className={`m-0 mb-3 text-sm ${MUTED}`}>{t("assets.work.empty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className={TABLE}>
            <thead>
              <tr>
                <th>{t("assets.work.orderNo")}</th>
                <th>{t("assets.work.type")}</th>
                <th>{t("assets.work.state")}</th>
                <th>{t("assets.work.raised")}</th>
                {/* `BR-WRK-018`'s internal deadline, named as a COMMITMENT and
                    never as a promise to a customer — `window_start` is the
                    appointment and is a different fact, so the two are never
                    printed as one column. */}
                <th>{t("assets.work.due")}</th>
                <th>{t("assets.maintenance.technician")}</th>
                {/* Gap `12-5` — figure 18 draws an ACTIONS cell holding an eye
                    and a two-way arrow. **Only the eye is built.** The arrow is
                    a REASSIGN, which is Work's own verb on Work's own screen,
                    and this tab writes nothing into `apps/work` — `G78` fails a
                    foreign write and `asset_door.py` states the design as
                    *"`apps/assets/**` gains no line of code at all"*. A glyph
                    with no destination is a dead control, which costs more than
                    a missing one (hard-won law 2's mirror). Reported. */}
                <th>{t("assets.col.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {open.map((row) => (
                <tr key={row.id}>
                  {/* B14 rule 31: the ORDER NUMBER, never the uuid — and the
                      route keys on the NUMBER too, so the link carries no id
                      either. Figure 18 draws this cell as a link. */}
                  <td>
                    {row.order_no === null ? (
                      <AssetDash />
                    ) : (
                      <Link
                        className={LINK}
                        to={tenantPath(`${WORK_ORDERS_ROUTE}/${row.order_no}`)}
                      >
                        {row.order_no}
                      </Link>
                    )}
                  </td>
                  <td>{row.type}</td>
                  <td>
                    {/* The same pill and the same tone the Orders queue draws,
                        imported rather than re-derived — two colour maps for
                        one state set is how a screen starts disagreeing with
                        the module that owns the fact. */}
                    <StatusPill tone={workOrderStateTone(row.state)}>
                      {t(`work.orders.state.${row.state}`, { defaultValue: row.state })}
                    </StatusPill>
                  </td>
                  <td>
                    {row.raised_at === null ? (
                      <AssetDash />
                    ) : (
                      <DateCell value={row.raised_at} timeZone={timeZone} dateFormat={dateFormat} />
                    )}
                  </td>
                  <td>
                    {row.due_at === null ? (
                      <AssetDash />
                    ) : (
                      <DateCell value={row.due_at} timeZone={timeZone} dateFormat={dateFormat} />
                    )}
                  </td>
                  {/* ⚠ **THE DRAWING SHOWS A DASH HERE AND THE PRODUCT SAYS
                      "Nobody yet", AND THE PRODUCT WINS.** `dispatch._holder`
                      is explicit — *"None … is what Work-007 draws as a RED
                      pill reading Unassigned rather than as an empty cell. A
                      blank cell reads as a bug"* — and the premises and
                      account tabs already print this exact key. A second
                      wording for one fact is the drift, not the fix; the
                      divergence from Figure 18 is filed rather than followed. */}
                  <td>{row.technician?.name ?? t("work.orders.atPlace.nobody")}</td>
                  <td>
                    {/* B14 rule 15: an ICON with a tooltip, never a text link —
                        and the route keys on the NUMBER, so no uuid travels. */}
                    <RowActions>
                      <RowActionLink
                        label={t("assets.work.view")}
                        icon={<EyeIcon />}
                        reason={
                          row.order_no === null ? t("assets.work.viewUnavailable") : null
                        }
                        to={tenantPath(`${WORK_ORDERS_ROUTE}/${row.order_no ?? ""}`)}
                      />
                    </RowActions>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {/* `BR-WRK-056`'s second way in on this screen, and the drawing puts it
          HERE — under Open work, because that is the panel it adds a row to. */}
      <div className="mt-3">
        <RaiseWorkOrderControl asset={props.asset} reason={props.raiseReason} t={t} />
      </div>
    </section>
  );
}

/**
 * The jobs FINISHED on this asset — the History half's first table
 * (`DEF-AST-9686`, `DEF-AST-9691`'s walk).
 *
 * ⚠ **A JOB LEFT THIS SCREEN THE MOMENT IT WAS DONE.** `OpenWorkPanel` draws
 * open states only — correctly, it is *what is outstanding* — and the History
 * half drew the maintenance log alone, so WO-0050 (a re-read sent from Reads)
 * was visible while it was open and nowhere once R. Patel closed it and Dana
 * accepted it. A clerk on the meter could not see that the visit happened.
 * These are the SAME rows the page already fetched, the complement of
 * `isOpenOrder`; nothing here adds a call.
 *
 * ⚠ **THE ROWS ARE THE SERVER'S FIRST PAGE, NEWEST FIRST** (`NFR-3`: the
 * read is paged). Where the asset has more jobs than one page holds the line
 * under the table says how many of how many — a count, never a silent cut.
 */
function DoneWorkPanel(props: {
  rows: readonly AssetWorkOrderRow[];
  total: number;
  regional: RegionalProps;
  t: Translator;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props.regional);
  const done = props.rows.filter((row) => !isOpenOrder(row));
  return (
    <section className={SECTION} data-testid="asset-done-work">
      <h3>{t("assets.work.doneTitle")}</h3>
      {done.length === 0 ? (
        <p className={`m-0 mb-3 text-sm ${MUTED}`}>{t("assets.work.doneEmpty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className={TABLE}>
            <thead>
              <tr>
                <th>{t("assets.work.orderNo")}</th>
                <th>{t("assets.work.type")}</th>
                <th>{t("assets.work.state")}</th>
                <th>{t("assets.work.completed")}</th>
                <th>{t("assets.maintenance.technician")}</th>
              </tr>
            </thead>
            <tbody>
              {done.map((row) => (
                <tr key={row.id}>
                  <td>
                    {row.order_no === null ? (
                      <AssetDash />
                    ) : (
                      <Link className={LINK} to={tenantPath(`${WORK_ORDERS_ROUTE}/${row.order_no}`)}>
                        {row.order_no}
                      </Link>
                    )}
                  </td>
                  <td>{row.type}</td>
                  <td>
                    {/* Accepted is the office's word on a finished job — it is
                        what tells a clerk the visit counted (`BR-MET-110`). */}
                    <StatusPill tone={workOrderStateTone(row.state)}>
                      {row.accepted_at !== null
                        ? t("work.orders.acceptance.accepted")
                        : t(`work.orders.state.${row.state}`, { defaultValue: row.state })}
                    </StatusPill>
                  </td>
                  <td>
                    {row.completed_at === null ? (
                      <AssetDash />
                    ) : (
                      <DateCell value={row.completed_at} timeZone={timeZone} dateFormat={dateFormat} />
                    )}
                  </td>
                  <td>{row.technician?.name ?? <AssetDash />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {props.total > props.rows.length ? (
        <p className={`m-0 mt-2 text-sm ${MUTED}`}>
          {t("assets.work.pageOf", { shown: props.rows.length, total: props.total })}
        </p>
      ) : null}
    </section>
  );
}

/**
 * ── Screen 12 · `Work & maintenance`, the MERGE ───────────────────────────
 *
 * ⚠ **TWO TABS ANSWERED ONE QUESTION AND THIS IS THE ONE TAB.** The grey rail
 * on page 58 states the problem: `asset_maintenance.cost` was summed here while
 * `work_order_cost_lines` was totalled on Work's performance tab, and
 * *"reaches the ASSET: NOWHERE"*. Two tabs could show two costs and both look
 * correct; one tab cannot, which the document calls *"the strongest argument
 * for the merge"*.
 *
 * ⚠ **THE MERGE IS TWO SUB-TABS, NOT TWO STACKED PANELS.** Before this the tab
 * drew `Open work` and then `Maintenance history` one under the other with no
 * strip and no URL state, so a person could not link to either half and had to
 * scroll past the outstanding jobs to reach the history. `Open work` is the
 * default — figure 19's caption: *"the half you can act on, so it is the half
 * you land on"* — and `BR-SHL-011` makes the choice URL state like every other
 * tab in the product.
 *
 * ⚠ **NOTHING HERE WRITES ACROSS A MODULE BOUNDARY AND NOTHING NEEDS TO.**
 * `GET /assets/{id}/work-orders` is mounted by `apps/work`; the cost rollup
 * travels the other way through `apps/assets/seams.py` into
 * `apps/work/asset_door.py`. `G78` fails a foreign write and none is proposed.
 */
function WorkTab(props: {
  asset: AssetDetail;
  client: ApiClient;
  regional: RegionalProps;
  t: Translator;
  canWriteReason: string | null;
  raiseReason: string | null;
  onLog: () => void;
}) {
  const { asset, t } = props;
  const { timeZone, dateFormat } = useRegional(props.regional);
  const [searchParams, setSearchParams] = useSearchParams();
  const section = workSectionFrom(searchParams.get(WORK_SECTION_PARAM));
  /* `DEF-AST-5117` — THIS PANEL DID NOT EVEN ASK FOR A PAGE. `AST-B-19` gave
     `assetMaintenanceQueryKey` its `(id, page, per)` shape and
     `getAssetMaintenance` its `{page, per}` argument, and this call site passed
     neither — so it took the server's default first page and the `total` beside
     the rows was fetched and discarded. `placeholderData` keeps the table on
     screen while the next page arrives, which is what stops a pager flashing a
     skeleton on every press. */
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const query = useQuery({
    queryKey: assetMaintenanceQueryKey(asset.id, page, per),
    queryFn: () => getAssetMaintenance(asset.id, props.client, { page, per }),
    placeholderData: (previous) => previous,
  });

  // `BR-WRK-056` — the Work-order column is a READ that Work publishes, and it
  // is a SEPARATE call on purpose: `apps/assets` serves no Work data and
  // `apps/work` serves no Assets data, so the join happens on this screen
  // rather than by one module reaching into the other's tables.
  const workOrders = useQuery({
    queryKey: ["assets", asset.id, "work-orders"],
    queryFn: () => listAssetWorkOrders(asset.id, props.client),
  });
  const workOrderIndex = workOrders.data?.maintenance_index ?? {};
  const workOrderRows = workOrders.data?.rows ?? [];

  const rows = query.data?.rows ?? [];
  const lifetime = query.data?.lifetime_cost ?? null;
  const currency = query.data?.currency ?? null;
  const rollup = asset.cost_rollup;
  const logKey =
    repairActionKey(asset) === "assets.action.logTest"
      ? "assets.maintenance.logTest"
      : "assets.maintenance.log";

  function selectSection(next: WorkSection): void {
    const copy = new URLSearchParams(searchParams);
    copy.set(WORK_SECTION_PARAM, next);
    setSearchParams(copy, { replace: false });
  }

  return (
    <>
      {/* ── The second-level strip · figure 18 · `BR-SHL-011` ───────────────
          The same shape and the same three class strings `AssetLifecycleTab`
          uses for screens 05a–05c, so a person who has learned one second-level
          strip in this module has learned both. */}
      <div className={SUBTABS} role="tablist" aria-label={t("assets.work.sectionsLabel")}>
        {WORK_SECTIONS.map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            data-section={id}
            aria-selected={id === section}
            className={id === section ? SUBTAB_ON : SUBTAB}
            onClick={() => selectSection(id)}
          >
            {t(id === "open" ? "assets.work.openTitle" : "assets.work.historyTab")}
          </button>
        ))}
      </div>

      {section === "open" ? (
        <OpenWorkPanel
          rows={workOrderRows}
          regional={props.regional}
          t={t}
          asset={asset}
          raiseReason={props.raiseReason}
        />
      ) : query.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : (
        <>
        <DoneWorkPanel
          rows={workOrderRows}
          total={workOrders.data?.total ?? workOrderRows.length}
          regional={props.regional}
          t={t}
        />
        <section className={SECTION}>
          <h3>{t("assets.maintenance.historyTitle")}</h3>
          {/* BR-AST-018: append-only. There is no edit or delete on any row
              here, and the API defines no verb for one — corrections are new
              entries. */}
          <p className={`m-0 mb-3 text-sm ${MUTED}`}>{t("assets.maintenance.appendOnly")}</p>
          {rows.length === 0 ? (
            <p className={`m-0 mb-3 text-sm ${MUTED}`}>{t("assets.maintenance.empty")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className={TABLE}>
                <thead>
                  <tr>
                    <th>{t("assets.maintenance.date")}</th>
                    {/* ⚠ **`RECORD`, NOT `TYPE` (gap `12-6`, the half that is
                        buildable).** Figure 19 draws a pill per row naming the
                        KIND OF RECORD — `Job raised · Job completed · Repair
                        logged · Test logged` — *"so no row has to be inferred
                        from which columns are filled"* (page 61). The column
                        read `Type` and carried `asset_maintenance.kind` as bare
                        text, which says what was DONE and not what KIND OF ROW
                        this is.

                        ⚠ **THE OTHER HALF — INTERLEAVING WORK-ORDER EVENTS INTO
                        THIS LIST — IS NOT BUILT, AND NOT BECAUSE IT IS HARD.**
                        The maintenance list is SERVER-PAGED and the work-order
                        list is not, so merging them in the browser makes the
                        footer below print a total that is true of neither list:
                        *"1–50 of 84"* over a page holding 50 entries plus
                        however many jobs happened to arrive. That is the
                        `NFR-3` shape `DEF-PAY-4221` already names four times.
                        It needs `apps/work` to publish its events as history
                        rows on a paged read; reported, not worked around. */}
                    <th>{t("assets.maintenance.record")}</th>
                    <th>{t("assets.maintenance.detail")}</th>
                    <th>{t("assets.maintenance.technician")}</th>
                    {/* The Work order COLUMN r10 draws — LIVE since CR-070 wave M.
                        ⚠ **IT IS A READ OF `work_orders.asset_id`, NOT A COLUMN ON
                        `asset_maintenance`** (`BR-WRK-056`), and the per-row link is
                        BY DATE because the schema has none and may not grow one: a
                        repair is paired with the job belonging to the same day, and
                        a row with no job on its date keeps its dash — which is
                        exactly r10's own third row (the 2024 commissioning test).
                        The reasoning is in `apps/work/asset_door.py`. */}
                    <th>{t("assets.maintenance.workOrder")}</th>
                    <th>{t("assets.maintenance.cost")}</th>
                    <th>{t("assets.maintenance.outcome")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <DateCell value={row.date} timeZone={timeZone} dateFormat={dateFormat} />
                      </td>
                      <td>
                        <StatusPill tone="neutral">
                          {t(`assets.maintenance.record.${row.kind}`, {
                            // A kind the catalogue has no sentence for still
                            // names itself rather than rendering as silence.
                            defaultValue: t(`assets.maintenance.kind.${row.kind}`, {
                              defaultValue: row.kind,
                            }),
                          })}
                        </StatusPill>
                      </td>
                      <td>{row.detail}</td>
                      {/* T6: the resolved NAME. ⚠ **NO RAW ID WHEN NONE RESOLVES
                          (`DEF-SHL-6348`).** This printed `tech_user_id` for a
                          removed user under BR-IDN-030's posture; B14 rule 31 is
                          the ratified rule and forbids it — the absence is said
                          in words and the id rides on `title` for support. */}
                      <td title={row.technician ? undefined : (row.tech_user_id ?? undefined)}>
                        {row.technician ?? (row.tech_user_id ? t("metering.premises.owner.unnamed") : <AssetDash />)}
                      </td>
                      <td>
                        {/* The ORDER NUMBER, never the uuid — B14 rule 31. */}
                        {workOrderIndex[String(row.date).slice(0, 10)] ?? <AssetDash />}
                      </td>
                      <td>
                        {/* §10-D3: the cost is CAPTURED and shown at 2 dp — and
                            posted NOWHERE. No GL account, no "posts to O&M". */}
                        {row.cost !== null && currency !== null ? (
                          <MoneyCell amount={row.cost} currency={currency} />
                        ) : (
                          <AssetDash />
                        )}
                      </td>
                      <td>{row.resulting_status ?? <AssetDash />}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {/* `DEF-AST-5117` — the footer this panel never had. It sits ABOVE the
              cost line on purpose: the sums are the SERVER's over every entry,
              not over the page, so they belong with the panel rather than with
              the rows and must not read as the page's total. */}
          {query.data !== undefined && (
            <ListPager
              total={query.data.total}
              page={page}
              per={per}
              onPage={setPage}
              onPer={(next: PageSize) => {
                setPer(next);
                setPage(1);
              }}
            />
          )}
          {/* ── The foot · gap `12-9` and gap `12-7`, one row ──────────────
              Figure 19 puts `Log repair / maintenance` BELOW the table, on the
              left, with the cost line on the right of the same line. It sat
              above the table, which put a write control between a person and
              the rows they came to read.

              ⚠ **THREE FIGURES, NOT ONE (gap `12-7`).** `AST-B-21` is built —
              one honest lifetime with both halves named — and it renders on
              screen 08's `Cost & value` panel, where figure 10 does not draw
              it. Figure 19 draws it HERE, and the reason the merge exists is
              that only this tab can show both halves at once. It is MIRRORED
              rather than moved: *"a remedy never loses anything"*, and the
              Overview row is not in any gap table. An older payload with no
              rollup keeps the single server sum it always had. */}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              {hasAction(asset, "log_repair") && (
                <GuardedButton
                  label={t(logKey)}
                  reason={props.canWriteReason}
                  onClick={props.onLog}
                />
              )}
            </div>
            {rollup !== undefined && rollup.lifetime != null && (rollup.currency ?? currency) !== null ? (
              <p className={`m-0 text-base ${MUTED}`} data-work-cost-foot="">
                {t("assets.cost.loggedOnAsset")}{" "}
                <span className="font-semibold text-text">
                  {rollup.maintenance != null ? (
                    <MoneyCell amount={rollup.maintenance} currency={(rollup.currency ?? currency) as string} />
                  ) : (
                    <AssetDash />
                  )}
                </span>
                {" · "}
                {t("assets.cost.jobsOnAsset")}{" "}
                <span className="font-semibold text-text">
                  {rollup.work != null ? (
                    <MoneyCell amount={rollup.work} currency={(rollup.currency ?? currency) as string} />
                  ) : (
                    <AssetDash />
                  )}
                </span>
                {" · "}
                {t("assets.cost.lifetimeFoot")}{" "}
                <span className="font-semibold text-text">
                  <MoneyCell amount={rollup.lifetime} currency={(rollup.currency ?? currency) as string} />
                </span>
              </p>
            ) : (
              lifetime !== null &&
              currency !== null && (
                // The SERVER's sum — B16 §7's "Lifetime maintenance $119.40"
                // line, with the D3 posting sentence deliberately absent.
                // ⚠ EVERY entry, not this page's.
                <p className="m-0 text-base font-semibold">
                  {t("assets.maintenance.lifetime", { amount: formatMoney(lifetime, currency) })}
                </p>
              )
            )}
          </div>
        </section>
        </>
      )}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-004@9f23548 (story+rules snapshot hash — EP-AST-02 detail; co-story US-AST-006@9f23548; co-packet US-SHL-020@9941789 — EP-SHL-01, the page-header conversion) + CR-028 AST-W2 (B16 §5.1/§5.1b · §10 rulings D3/D7 · §4.8 Details row)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 (path-tenancy · US-SHL-020 conversion) · REWRITTEN 2026-08-22 by the CR-028 AST-W2 lane: header sub-line to r10 (service · ×trimmed · installed Mon YYYY · seat; sub-meters name their MASTER; inventory reads "In inventory · unassigned"); the repeated Classification panel REMOVED — BR-AST-044's three classifications live inside Specifications (with r10's net fold and the sub-meter Parent/master link + allocation share); THREE sidebar panels (Assignment w/ the LIVE account leg + panel Reassign/Assign · Warranty & supplier w/ MoneyCell at 2 dp + Covered/Expired pill · Lifecycle w/ age/life/cert-due/forecast) + the device Test & certification panel; the Reads tab SERVED (DEF-475 closed — BR-AST-029's fold, honest empty ≠ failed); the Export tab reading the LINKED net meter (§5.1b B); Audit INLINE via the shared AuditTab (BR-AUD-010/DEF-579, "We did that in Cr23"); Maintenance history with Technician NAMES, the Work-order text column (all dashes until Work R5 — §10-D7), Cost at 2 dp and the server's lifetime line — NO GL sentence anywhere (§10-D3) · AMENDED 2026-09-12 by the CR-092-BRC01 step 2 lane 2: `BR-WRK-056`'s two missing doors built (header + the Maintenance tab's Open work panel), gated OUTSIDE `row_actions()` on `behavior_class` so `BR-AST-534` can show the control DISABLED with its reason on a retired asset rather than hiding it — the engineering half the ruling left open, reasoned in the decision log; the work-order list RENDERED instead of fetched and discarded (`AssetWorkOrderRow` is now `ScopedWorkOrderRow` by alias, and `priority` is deliberately NOT added because `_scoped_row` is shared with the premises and account tabs); a Channel column on the read log when a meter has more than one register, in words
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the CR-028 AST-W2 lane report (tsc · eslint --max-warnings 0 · vitest run quoted there) · 2026-09-12: tsc✔ eslint --max-warnings 0✔ vitest src/features/assets 208 passed/12 todo/0 failed across 10 files, rebased onto the tip · 38 of 38 browser checks at 1280 AND 1440 (`10-scripts/cr092_lane2_asset_detail_walkthrough.mjs`, against 57 rows this lane seeded because 0 of 65 work orders on this database carried an `asset_id`)
// exceptions: E3 the Reads/Export Source and Status cells render the served CODES verbatim (`import` · `ok`) — no signed vocabulary maps THOSE two to display words and none is invented here; reported. ⚠ **THE REGISTER WAS NOT ONE OF THEM AND THIS EXCEPTION USED TO SAY IT WAS (`DEF-MET-4969`, 2026-09-12)** — `metering.reads.channel.*` ships seven words in all eleven catalogues and six files in Meter Reads already resolve them, so `tou_on` reached a clerk for as long as this screen existed, under a comment claiming an absence. **Before repeating an exception that says a vocabulary does not exist, grep the catalogue.** · ✅ **E3 RETIRED (`DEF-MET-4965`/`DEF-MET-4967`, 2026-09-12): the Work order column is no longer all dashes and Work is no longer R5.** It read *"all dashes because NO column stores one (Work is R5, OQ-249)"*; `apps/work` ships with 27 migrations, `work_orders.asset_id` is a column, and `apps/work/asset_door.py` is named for the door this screen now hangs — twice, per `BR-WRK-056`'s four ways in · E4 the Warranty term row is a stated dash: no term is stored and deriving one from purchase→cover dates is a rule nobody signed · E2 the LogMaintenanceModal does not yet capture the new `cost` field the API accepts — the full-page AST-07 conversion is AST-W4 T2's, reported not smuggled in
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
