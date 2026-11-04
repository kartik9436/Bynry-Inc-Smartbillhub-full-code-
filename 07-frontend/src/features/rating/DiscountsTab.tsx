// ── Trace ──────────────────────────────────────────────
// Change:   CR-013 part 3 — DIS-01, the Discounts landing tab. Row 10 of the
//           16-surface inventory (`09-screen-inventory.md` §18): *"the tab does
//           not exist; the 6 tables do"*.
//           Screens: PLN-01.discounts
// Rules:    BR-RAT-068 (an OVERLAY, never an edit to the rate) · BR-RAT-069
//           (AVAILABLE ≠ GRANTED — `Plans` and `Enrolled` are two different
//           numbers and only one of them reduces a bill) · BR-RAT-072 (four
//           statuses, one of them set by a BILL RUN) · BR-RAT-079 (restricted
//           proof — this list carries no document and no account) · BR-RAT-084
//           (the code opens the shared definition detail) · BR-RAT-087 /
//           DEF-364 (money and percent render from the SERVER's `*_display`
//           string) · BR-SHL-010/011 (the declared sort and filter vocabulary) ·
//           BR-SHL-012 (the A18 states) · BR-SHL-020 (plain-language failure) ·
//           BR-SHL-025 (a forbidden control is present and disabled WITH its
//           reason) · B14 rule 21 (new UI is Tailwind, no new stylesheet class)
// ───────────────────────────────────────────────────────
//
// ⚠ **REBUILT 2026-10-03 FROM IMAGES 01–04 (CR-166-BRC10 round 2 task 5,
// DEF-RAT-9290, D14–D18).** Columns: Code · Discount · Type · Value ·
// Eligibility · Verification · From · To · Plans · Enrolled · Status · open.
// No paragraph above the table (the tab's explainer is retired from every
// catalogue); the Value cell prints the server's `$25.00` / `15%`; the row's
// one action OPENS the details page — the pencil to the edit door is gone, as
// on Taxes & fees, because it put a live discount's value in an editable box;
// the toolbar is the kit's search · All · `+ Filter ▾` with removable chips ·
// columns, filtering on Status and Type IN THE SERVER (NFR-3). Its cells live
// in `discountListParts.tsx` (B14 rule 43). The paragraphs below are this
// file's history and say what was true when each was written.
//
// ⚠ **NO CSV BUTTON YET, AND THAT IS `DEF-1005` STILL, NOT AN OVERSIGHT.**
// `POST /exports` registers no `discounts` resource (`apps/rating/exports.py`
// `register()`), so a button here would be a control wired to a 404 (hard-won
// law 2). The day the back end registers it, `downloadSlot` takes a
// `ListExportButton resource="discounts"` exactly as `TaxesFeesTab` does.
//
// ⚠ SIX TABLES SHIPPED ON 2026-08-19 AND THIS TAB DID NOT EXIST. That is the
// whole reason this file is here, and it is hard-won law 2 at its largest scale
// in the repo so far: `0009_cr013_discounts.py` created `discounts`,
// `discount_versions`, `plan_discount_rules`, `discount_enrolments`,
// `discount_enrolment_documents` and `discount_grants`; the write services, the
// five statuses, the five types and the R6 pricing door were all built and
// tested; `apps/rating/api.py` served eighteen handlers and not one of them was
// a discount; and a utility could not see a single row.
//
// ⚠ THIS TAB MAKES SIX WHERE r10 DRAWS FIVE, AND THAT IS REPORTED, NOT SOLVED.
// What is built is `Plans · Rate schedules · Charge codes · Taxes & fees · RATE
// CHANGES`; what r10 draws is `… · DISCOUNTS`. `RateChangesTab` is real and
// wired and the drawing has no counterpart for it. §18 is explicit that neither
// the addition nor the removal is decided, and that r10's rate detail carries a
// `Versions & filings` tab which may be where rate changes belong. **Nothing
// here removes or moves Rate changes** — see the note on `RATING_TABS`.
//
// ⚠ IT WAS A READ-ONLY SURFACE ON PURPOSE FOR ONE DAY, AND IT IS NOT ANY MORE
// (amended 2026-08-21 by the DIS-02 lane). What this paragraph said: *"`+ New
// discount` renders present and DISABLED with its reason, because DIS-02 — the
// five-step wizard of §18 row 12 — is not built and `apps/rating/api.py` exposes
// no discount write ... There is deliberately no row-actions column: every action
// r10 offers on this row (Edit, Duplicate, Retire) is that wizard's, and a column
// of three permanently-disabled icons would be noise where an honest absence is
// information."*
//
// **Every clause of that was true and every clause has stopped being true.**
// `DiscountWizard.tsx` is DIS-02, `POST /discounts` and `POST
// /discounts/{id}/versions` are mounted, and this tab now carries **three doors
// to it** — the header button, the empty-state CTA and a row-actions column —
// all three spelled through `definitionWizardPath` so none can drift into a
// hand-typed path. The catalogue key that carried the old reason
// (`rating.discounts.wizardPending`) is **deleted from all eleven locales**
// rather than left unused, because a disabled control carrying a reason that has
// stopped being true reads as a decision (hard-won law 1) and an orphaned string
// is one copy-paste from being read out loud again.
//
// ⚠ **THE ROW-ACTIONS COLUMN CARRIES ONE ICON, NOT THREE, AND THE OLD ARGUMENT
// IS WHY.** Duplicate and Retire still have no route on ANY definition kind, so
// the paragraph above was right about them and is still right: a column of two
// permanently-disabled icons beside one working one would be noise. Only `Edit`
// is drawn.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DISCOUNT_TYPES, getDiscounts } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { DataTable } from "@/components/DataTable";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { FailedWithRetry, PermissionDenied } from "@/components/StateFrame";
import { EyeIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { definitionPath, definitionWizardPath } from "./definitionDetail";
import {
  DASH,
  DISCOUNT_LIST_STATUSES,
  DiscountCodeCell,
  DiscountStatusCell,
  DiscountValueCell,
  discountListEnrolled,
  discountListLabel,
} from "./discountListParts";
import type { DiscountListRow } from "./discountListParts";
import { DASHBOARD_ROUTE, GuardedButton } from "./ratingShared";
import type { RatingTabRender, Translator } from "./ratingShared";
import { TaxDateCell } from "./taxListParts";

// ── Pure pieces ────────────────────────────────────────────────────────────

/**
 * What a cell renders when the server served no figure: an em-dash, never a
 * zero and never a plausible-looking number. A charge waiver is served
 * `value_display: null` because it removes the WHOLE of what its scope
 * selected; `0.00` there would tell a utility the programme waives nothing.
 */
export const NO_VALUE = DASH;

/**
 * Images 01–04's eleven columns plus the open action, in the drawn order.
 *
 * ⚠ ONLY TWO ARE SORTABLE, AND THE REST ARE NOT AN OVERSIGHT. Type, Value,
 * Eligibility, Verification and the dates live on `discount_versions`, and
 * Plans and Enrolled are computed counts, so the server declares no sort for
 * them (`DISCOUNT_SORTS` is `code · name · status`) rather than ordering by
 * something else behind a live-looking arrow (BR-SHL-010).
 *
 * ⚠ TWO FILTERS, BOTH THE SERVER'S (NFR-3). Image 02 offers Status and Type;
 * the round-2 contract filters `f.status` and `f.type` in the database. A
 * filter applied to the rows on screen would be a page-two lie.
 */
export function discountTableConfig(
  t: Translator,
  cells: {
    code: (row: DiscountListRow) => ReactNode;
    type: (row: DiscountListRow) => ReactNode;
    value: (row: DiscountListRow) => ReactNode;
    eligibility: (row: DiscountListRow) => ReactNode;
    verification: (row: DiscountListRow) => ReactNode;
    from: (row: DiscountListRow) => ReactNode;
    to: (row: DiscountListRow) => ReactNode;
    enrolled: (row: DiscountListRow) => ReactNode;
    status: (row: DiscountListRow) => ReactNode;
    open: (row: DiscountListRow) => ReactNode;
  },
): TableConfig<DiscountListRow> {
  return {
    screenId: "S9.discounts",
    columns: [
      {
        key: "code",
        label: t("rating.discounts.col.code"),
        sortable: true,
        identity: true,
        cell: cells.code,
      },
      { key: "name", label: t("rating.discounts.col.name"), sortable: true },
      { key: "type", label: t("rating.discounts.col.type"), cell: cells.type },
      { key: "value", label: t("rating.discounts.col.value"), numeric: true, cell: cells.value },
      {
        key: "eligibility",
        label: t("rating.discounts.col.eligibility"),
        cell: cells.eligibility,
      },
      // ⚠ DEF-RAT-9319 (CR-166 task 9): OFF BY DEFAULT, in ▦ Columns. Measured
      // in Chromium at 1440: the twelve columns need 1,196px and the list has
      // 1,120px, so the table scrolled sideways and Status sat under the pinned
      // open icon. The floor is set by single-word headers in the kit's header
      // tier (VERIFICATION alone holds 129px) and by dates, which cannot wrap;
      // image 01 does not fit its own width either (its › column is cut at the
      // right edge). Verification is the widest header and the one fact the
      // details page shows beside the rest, so it is the one column a clerk
      // turns on rather than one the list cannot do without.
      {
        key: "verification",
        label: t("rating.discounts.col.verification"),
        cell: cells.verification,
        defaultVisible: false,
      },
      { key: "effective_from", label: t("rating.discounts.list.col.from"), cell: cells.from },
      { key: "effective_to", label: t("rating.discounts.list.col.to"), cell: cells.to },
      // ⚠ THE TWO COUNTS SIT SIDE BY SIDE BECAUSE THEY ARE NOT THE SAME NUMBER
      // (BR-RAT-069). `Plans` is how many plans OFFER the discount; `Enrolled`
      // is how many accounts actually GET it.
      { key: "plans", label: t("rating.discounts.col.plans"), numeric: true },
      {
        key: "enrolled",
        label: t("rating.discounts.col.enrolled"),
        numeric: true,
        cell: cells.enrolled,
      },
      { key: "status", label: t("rating.col.status"), cell: cells.status },
      { key: "actions", label: "", locked: true, cell: cells.open },
    ],
    getRowId: (row) => row.id,
    searchFields: ["code", "name"],
    searchPlaceholder: "rating.discounts.list.search",
    filters: [
      {
        name: "status",
        label: t("rating.col.status"),
        options: DISCOUNT_LIST_STATUSES.map((value) => ({
          value,
          label: t(`rating.discounts.status.${value}`),
        })),
      },
      {
        name: "type",
        label: t("rating.discounts.col.type"),
        options: DISCOUNT_TYPES.map((value) => ({
          value,
          label: t(`rating.discounts.type.${value}`),
        })),
      },
    ],
    defaultSort: { sort: "code", dir: "asc" },
  };
}

/**
 * The `Value` text. It is `value_display` and **nothing else** (BR-RAT-087):
 * the server owns the unit AND the symbol — `$25.00`, `15%` — beside the
 * tenant's currency. A branch here would be a second copy of that rule, in the
 * layer least able to be tested against the money it describes.
 */
export function discountValueText(row: Pick<DiscountListRow, "value_display">): string {
  return row.value_display ?? NO_VALUE;
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface DiscountsTabProps {
  readOnly: boolean;
  client?: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** US-SHL-020 addendum r2 — the tab hands its own button up to the frame. */
  render: RatingTabRender;
}

export function DiscountsTab(props: DiscountsTabProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const [searchParams, setSearchParams] = useSearchParams();

  const regional = { timeZone: props.timeZone, dateFormat: props.dateFormat };
  const config = discountTableConfig(translate, {
    // BR-RAT-084: the code opens the details page. A LINK, not a button: a
    // read-only role may read a definition.
    code: (row) => (
      <DiscountCodeCell row={row} to={tenantPath(definitionPath("discount", row.id))} />
    ),
    // DEF-RAT-9319: `break-keep` — Japanese and Korean break between any two
    // characters, so a squeezed column read 定/率 one character per line.
    type: (row) => (
      <span className="break-keep">
        {row.type === null ? DASH : t(`rating.discounts.type.${row.type}`, { defaultValue: row.type })}
      </span>
    ),
    value: (row) => <DiscountValueCell row={row} />,
    // A contract `{value,label}` reads its label; an older server's free text
    // is already words.
    eligibility: (row) => discountListLabel(row.eligibility, (text) => text),
    verification: (row) =>
      discountListLabel(row.verification, (code) =>
        t(`rating.discounts.verification.${code}`, { defaultValue: code }),
      ),
    from: (row) => <TaxDateCell value={row.effective_from ?? null} {...regional} />,
    // `No end` only when the server SAID there is none; a server that has not
    // landed the field yet reads a dash, never a promise of forever.
    to: (row) =>
      row.effective_to === undefined ? (
        DASH
      ) : (
        <TaxDateCell value={row.effective_to} openEnd {...regional} />
      ),
    enrolled: (row) => String(discountListEnrolled(row)),
    status: (row) => (
      <span className="break-keep">
        <DiscountStatusCell status={row.status} />
      </span>
    ),
    // B14 rule 15: one icon with an accessible name, and it OPENS the details
    // page (D16). Editing is the details page's own decision, by status.
    open: (row) => (
      <RowActions>
        <RowAction
          label={t("rating.discounts.list.open")}
          icon={<EyeIcon />}
          onClick={() => navigate(tenantPath(definitionPath("discount", row.id)))}
        />
      </RowActions>
    ),
  });

  const state = parseTableParams(searchParams, config);
  const listQuery = useQuery({
    queryKey: queryKeys.discounts(serializeTableParams(state, config).toString()),
    queryFn: () =>
      getDiscounts(
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

  // A failed read still goes back through the render prop, so the page keeps
  // its header and tab strip and the user can move somewhere else.
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
              title={t("rating.discounts.failedTitle")}
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

  const rows: DiscountListRow[] = listQuery.data?.results ?? [];

  return (
    <>
      {props.render({
        action: (
          <GuardedButton
            readOnly={props.readOnly}
            readOnlyReason={t("rating.readOnlyReason")}
            variant="primary"
            onClick={() => navigate(tenantPath(definitionWizardPath("discount", null)))}
          >
            {t("rating.discounts.new")}
          </GuardedButton>
        ),
        body: (
          // D14 — no paragraph above the table (images 01–04 draw none).
          // DEF-RAT-9341: every header word stays whole — Japanese and Korean
          // break between any two characters, so a squeezed header read
          // プラ/ン and ステータ/ス (the cells' half was DEF-RAT-9319).
          <div className="flex flex-col gap-3 min-w-0 [&_thead_th]:break-keep" data-discount-list="">
            <DataTable<DiscountListRow>
              config={config}
              state={state}
              onStateChange={setState}
              rows={rows}
              totalRows={listQuery.data?.count ?? null}
              loading={listQuery.isPending}
              filterBarSlot={
                <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
              }
              empty={{
                title: t("rating.discounts.emptyTitle"),
                helper: t("rating.discounts.emptyHelper"),
                ctaLabel: t("rating.discounts.new"),
                ctaReason: props.readOnly ? t("rating.readOnlyReason") : undefined,
                onCta: () => navigate(tenantPath(definitionWizardPath("discount", null))),
              }}
            />
          </div>
        ),
      })}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-013 part 3 VERBATIM (12-governance/11-change-requests.md) · 09-screen-inventory.md §1 + §18 row 10 · BR-RAT-068/069/072/079/084/087 · B14 rule 21
// generated: 2026-08-21 by the CR-013 discounts read-API lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest src/features/rating/ 184 passed / 19 todo across 8 files✔ (162+19 was the pre-lane baseline; this lane adds Discounts.test.tsx with 22) · vitest src/styles/routeBUtilities.test.ts✔ · vitest src/i18n/locales.test.ts✔ · g31_declared_classes PASS (0 undeclared, baseline 0)✔ · g29_screen_ids PASS (no new route — `plans-rates/:tab` already resolves `discounts` to PLN-01.discounts through `subIdFrom`, so screen_id_baseline.txt is unchanged)✔ · g27_translation_keys PASS✔ · g18_i18n_call_sites unchanged from the pre-lane tree (same 2 findings, neither in this lane)✔ · pytest 06-backend/tests/test_us_rat_charges_taxes.py + test_cr013_discount_reads.py 43 passed / 3 skipped✔
// exceptions: [AMENDED 2026-08-21 by the DIS-02 lane] E2 and its twin are CLOSED — they read *"`+ New discount` is drawn DISABLED with its reason: DIS-02 (§18 row 12) is not built and `apps/rating/api.py` exposes no discount write"* and *"NO row-actions column, because every action r10 draws on this row belongs to that same wizard"*. DIS-02 is built and both write routes are mounted, so all three doors are live and the actions column is drawn with ONE icon; Duplicate and Retire stay absent because neither has a route on any definition kind, which is the surviving half of the original argument · E4 — no CSV export: `POST /exports` has no `discounts` resource and adding one is a backend change this lane did not make, so the button is absent rather than present-and-broken · E1 — the tab makes SIX where r10 draws FIVE; the Rate changes tab is untouched and the question is the Product Owner's (§18)
// amended: 2026-10-03 CR-166-BRC10 round 2 task 5 — rebuilt from images 01–04 (D14–D17, DEF-RAT-9290); the single pencil is gone (the row opens the details page); E4 (no CSV) stands on DEF-1005
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
