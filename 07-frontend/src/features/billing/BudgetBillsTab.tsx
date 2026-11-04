// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-018 (enrolment, eligibility & the level computation) ·
//           US-BIL-019 (the budget bill: variance on every bill, settle-up) ·
//           US-BIL-020 (re-level, override ±30%, off-budget as a staff act)
//           Screens: S30 (Budget Bills tab)
// Rules:    BR-BIL-017 (one live status per account; the ±30% bound is measured
//           against the COMPUTED level; ⚠ the automatic drop-off is SUPERSEDED
//           — PO 2026-08-11 *"nodrop we chase for payments until write off"*) ·
//           BR-BIL-021 (every parameter is a tenant setting, never defaulted) ·
//           BR-BIL-011 (the monthly posting is the ACTUALS posting) ·
//           BR-RAT-043 (budget billing rides the plan flag — OQ-237) ·
//           BR-SHL-020 · BR-SHL-023 (one money path) · BR-SHL-025 ·
//           CLAUDE.md rule 2 (every money figure with its CHAR(3))
// ───────────────────────────────────────────────────────
// S30's Budget Bills tab. `budget.py` + `budget_service.py` are 60KB of
// finance-signed arithmetic and an append-only event ledger, and
// `budget_service.enroll` had NO CALLER outside tests: a utility could not put
// one customer on a flat monthly amount.
//
// ══════════════════════════════════════════════════════════════════════════
// THE THREE FIGURES THAT ARE NEVER COLLAPSED INTO ONE
// ══════════════════════════════════════════════════════════════════════════
// `level` (computed), `level_override` (the staff figure) and `effective_level`
// (what the customer actually pays) are three columns and three cells here.
// BR-BIL-017 measures the ±30% bound against the COMPUTED level, so a screen
// showing only "what they pay" would leave a clerk typing an override with no
// way to know the bound — and chaining overrides against each other is how three
// audited 30% steps walk a level to twice what the trailing twelve months say.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THE PROTOTYPE OFFERS THAT THIS DOES NOT, AND WHY EACH IS NAMED
// ══════════════════════════════════════════════════════════════════════════
//   · **"All eligible residential (312)" and "Import list from CSV".** Neither
//     ships. Enrolment fixes what a customer pays every month for a year, and
//     eligibility rides the rate PLAN's budget flag (BR-RAT-043) which no
//     endpoint publishes — OQ-237. A bulk action over 312 accounts whose
//     eligibility nothing can read would enrol people at a level nobody looked
//     at. One account at a time, with the number shown first.
//   · **"Cap increases at 15% year-over-year" and "opt-in only".** Both are
//     tenant SETTINGS under BR-BIL-021 and the settings surface that writes
//     them is S69's, not this tab's. Drawing the checkboxes here would offer a
//     control that saves nowhere.
//
// ══════════════════════════════════════════════════════════════════════════
// 2026-09-14 · THE LIST IS NOW §05 SCREEN 25's TABLE (`CR-103-BRC03`)
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THIS FILE CITED THE PROTOTYPE FOR ITS STRUCTURE AND CITED THE BLUEPRINT
// ZERO TIMES.** Its packet line still names
// `05-prototype/UtilityBilling.html §Billing "Budget Bills" lines 3421-3466` —
// r9, which is DELETED (`DEF-610`). The drawn specification is
// `05-prototype/04 Billing, As Built.pdf` §05 entry 25, p121–p122, read AS
// IMAGES (B14 rule 42), and it is what the table below is built to.
//
// **MAINTENANCE, not build** (`12-governance/22-product-maintenance-process.md`):
// a clerk could already do this task, so the screen was reproduced in a browser
// first, every write path and refusal below is REUSED unchanged, and only the
// list's STRUCTURE moved. The record is
// `04-docs/05-modules/07-billing/conformance/CR-103-BRC03-budget-bills-maintenance.md`.
//
// ⚠ **THE VARIANCE SIGN IS THE ENGINE'S AND NOT THE DRAWING'S.** p125 draws
// `+$212.80 → Collect`; ❄️ B5/WE-8/GT-24 is the other way round —
// `variance_movement` is `level − actual`, so a POSITIVE balance means the
// levels collected more than the customer used and the utility CREDITS it
// (`budget.settle_up`'s own words). Every figure in that drawing is an
// illustration (B14 rule 37). **Nothing here flips a sign.**
//
// ⚠ **NOTHING ON THIS SCREEN DROPS ANYBODY AUTOMATICALLY.** PO 2026-08-11,
// verbatim *"nodrop we chase for payments until write off"* — BR-BIL-017's
// two-missed-payments drop-off is SUPERSEDED. "Remove from budget" is a staff
// act with a name on it, and the variance balance is CARRIED, never dropped.
//
// ══════════════════════════════════════════════════════════════════════════
// 2026-09-15 · WHAT A CLERK READS ABOUT THE ABSENCES, AND WHERE THE WHY WENT
// (`DEF-BIL-5339` · `DEF-BIL-5340`, MAINTENANCE under `CR-103-BRC03`)
// ══════════════════════════════════════════════════════════════════════════
// The Product Owner photographed this tab reading `BR-RAT-043`, `OQ-237`,
// `OQ-142`, `budget_service.enroll` and `budget.settle_up_gl_account` — two
// sites printed the server's own sentences unchanged: the `parameters_
// unavailable` note under the list title, and every bullet of `GapNotes`. The
// 2026-09-15 fix for `DEF-BIL-5316` removed the enrol panel and the ONE render
// site inside it; it touched neither the server sentences nor G28's parked
// baseline that held three of them, and the settings sentence is built by
// `str(BillingConfigError)` in a file G28 never reads. So this looked handled.
//
// **The stated absences STAY. Only the reasoning moved — here, and to the
// register.** A clerk still learns, in six words or fewer each (B14 rule 33):
//   · *Plan eligibility is not shown here. Confirm it when enrolling.* — the
//     plan's budget flag belongs to RATING (BR-RAT-043) and no endpoint
//     publishes it; the enrol form asks the clerk to confirm it; where it is
//     read from is `OQ-237`, still OPEN.
//   · *Settle-up amounts are shown, not posted.* — the settle-up line's GL
//     account is `OQ-142`, still OPEN, so the posting stops at the boundary
//     (`budget.settle_up_gl_account` raises) and the figure is shown anyway
//     because the customer needs to know it.
//   · *Enrol accounts one at a time. No list import.* — the prototype's "All
//     eligible residential (312)" and "Import list from CSV" are not built:
//     no account records which plan it is on, so there is no set to iterate
//     (the `DEF-476` correction), and a bulk enrolment at a level nobody
//     looked at is the wrong kind of convenience.
//   · *Nobody leaves budget billing automatically.* — the drop-off rule is
//     SUPERSEDED (PO 2026-08-11, above).
//   · *Budget settings could not be read.* — only when tenancy's settings read
//     is not published; never the seeded defaults (BR-BIL-021).
//   · **Yearly cap — Set in Settings, not here.** — the 15% year-over-year cap
//     and opt-in are tenant SETTINGS on S69, so a checkbox here would save
//     nowhere. This was the "Three things this screen does not do" note; the
//     count is DROPPED, not derived, because this note now states one thing
//     and the server list's heading already derives its own count.
// The words come from the catalogues through the server's `message_key`
// (G32 checks every key resolves, G33 caps each at six words a sentence), the
// rule stays on `data-br-ref` for support, and `budgetBillsClerkCopy.dom.test`
// reads the RENDERED tab and fails on any id or identifier in it.
//
// **And an empty list says which set it is** (`DEF-BIL-5340`): this list is
// accounts ALREADY on budget billing, so an account that exists and is not
// enrolled has no row here by design. The kit's "No results for '…'." alone
// let a clerk conclude the search was dead — and with nobody enrolled the
// default `Status` chip made it read "No results for ''.", because the chip
// counts as a filter and the "Nobody is on budget billing" block could never
// render (law 2, dead UI). The note under the list names the set and carries
// the enrol door; the kit's own zero-state now has a sentence for the no-term
// case (`states.zeroResults.filtered`).
import { useMemo, useState } from "react";
import type { ReactNode } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getBudgetEnrollments,
  overrideBudgetLevel,
  relevelBudgetAccount,
  removeFromBudgetBilling,
} from "@/api/billingOpsEndpoints";
import type { BudgetStatusRow, BudgetSummary } from "@/api/billingOpsEndpoints";
import { ButtonLink } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { formatMonthYear } from "@/components/DateCell";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { FilterBar } from "@/components/FilterBar";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { RowAction, RowActions } from "@/components/RowActions";
import { PencilIcon, PowerIcon, WrenchIcon } from "@/components/icons";
import { MoneyCell } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { useRegional } from "@/features/metering/meteringShared";
import { useToast } from "@/components/Toast";
import { Panel } from "@/components/Panel";
import { accountDetailPath } from "@/features/customers/customersShared";
import { ArrivesWith, apiErrorText } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";
import type { Translator } from "@/features/tenancy/settingsShared";

import { GapNotes, todayIso } from "./billingOpsShared";
import {
  BUDGET_ASKS_ROUTE,
  BUDGET_ENROL_ROUTE,
  BUDGET_FORECAST_ROUTE,
} from "./billingShared";

export const budgetListKey = (status: string) => ["budget-billing", status] as const;
export const budgetEligibilityKey = (accountId: string) =>
  ["budget-billing", "eligibility", accountId] as const;

/**
 * One money cell of the drawn table, or the absence that is not `0.00`.
 *
 * §05 screen 25 draws `COMPUTED · OVERRIDE · THEY PAY` as three cells and the
 * document's own rule row says why: *"The ±30% bound is measured against the
 * computed figure, so hiding it is how an override gets typed blind."* This is
 * the shared renderer for all three, so they cannot drift apart.
 *
 * ⚠ **A DASH IS NOT A ZERO.** `null` means the server could not compute the
 * figure; `0.00` is a real, chooseable monthly amount. Printing one for the
 * other tells a clerk a customer pays nothing.
 *
 * Exported so `BillingSurfaces.test.tsx` pins the money rule on the cell the
 * table actually draws (it pinned the deleted `LevelCell` until
 * `DEF-GOV-10106`).
 */
export function MoneyOrDash(props: {
  amount: string | null | undefined;
  currency: string;
  locale?: string;
  strong?: boolean;
}) {
  if (props.amount === null || props.amount === undefined) {
    return <span aria-hidden="true">—</span>;
  }
  const cell = <MoneyCell amount={props.amount} currency={props.currency} locale={props.locale} />;
  return props.strong === true ? <strong>{cell}</strong> : cell;
}

/**
 * What the table needs from the screen around it.
 *
 * ⚠ **`accountHref` HOLDS AN ADDRESS AND IS NAMED FOR ONE.** A prop called
 * `account` on a table helper is how a later reader comes to pass a raw
 * identifier into a cell that renders it; the name is the guard.
 */
interface BudgetTableView {
  locale?: string;
  /** IS-8 — the tenant's zone, for the one cell that carries a date. */
  timeZone: string;
  /** Where the ACCOUNT cell's link goes, tenant prefix already applied. */
  accountHref: (row: BudgetStatusRow) => string;
}

/**
 * §05 screen 25's table — the eight drawn columns, on the shared `DataTable`.
 *
 * ⚠ **IT IS THE SHARED TABLE AND NOT A HAND-ROLLED ONE, AND THAT IS THE WHOLE
 * POINT OF THE CHANGE.** The list this replaces was a `PlainTable` with a
 * two-button segment above it: no search, no filter chips, no column chooser,
 * no pagination footer, and every row the server had. B14 rule 12 (toolbar),
 * rule 16 (pagination on every list table) and `NFR-3` (universal server
 * pagination) are all satisfied by composing the kit rather than by anything
 * written here — which is `r10`'s own reasoning for having one table.
 *
 * ⚠ **`RE-LEVEL` CARRIES A MONTH AND NOT A DRIFT PERCENTAGE, DELIBERATELY.**
 * The drawing puts *"Drifted 14%"* in this column; the server explains on every
 * row why it does not answer that, and the cell states the absence rather than
 * approximating a figure that decides what a customer pays.
 */
function budgetTableConfig(
  t: Translator,
  view: BudgetTableView,
  actions: (row: BudgetStatusRow) => ReactNode,
): TableConfig<BudgetStatusRow> {
  const { locale } = view;
  return {
    screenId: "S30.budget",
    searchFields: ["account_no", "customer_name", "address"],
    // B14 rule 19 — THIS list's own prompt, naming what it matches. The drawn
    // placeholder is the contract and the server's three search legs are the
    // same three.
    searchPlaceholder: "billing.budget.search",
    filters: [
      {
        name: "status",
        label: t("billing.budget.filter.statusLabel"),
        options: [
          { value: "enrolled", label: t("billing.budget.filter.enrolled") },
          { value: "off_budget", label: t("billing.budget.filter.off_budget") },
        ],
      },
      {
        name: "relevel",
        label: t("billing.budget.filter.relevelLabel"),
        options: [{ value: "due", label: t("billing.budget.filter.relevelDue") }],
      },
    ],
    defaultSort: { sort: "enrolled_on", dir: "desc" },
    getRowId: (row) => row.account_id,
    columns: [
      {
        key: "account",
        label: t("billing.budget.col.account"),
        identity: true,
        cell: (row) => (
          <>
            {/* B14 rule 31 / DEF-3158 — the HUMAN-FACING number, never the id.
                A row whose account has no number states that in words.

                ⚠ **AND IT IS A LINK — `DEF-BIL-5325`.** p121 draws the number
                in the accent, the way this document draws every door, and the
                Bills tab one over has opened the same account through
                `accountDetailPath` since it shipped. The tie-out that called
                this column built compared the VALUE and never asked whether the
                affordance was there — hard-won law 2's mirror, a fact drawn as
                a door and rendered as text. The id rides the `href`, where it
                is not a visible value and rule 31 is not engaged; that is the
                same place the Bills tab puts it. */}
            <InlineLinkTo to={view.accountHref(row)}>
              {row.account_no ?? t("billing.budget.noAccountNo")}
            </InlineLinkTo>
            <span className="block text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
              {row.customer_name ?? t("billing.budget.noCustomerName")}
            </span>
          </>
        ),
      },
      {
        key: "status",
        label: t("billing.budget.col.status"),
        cell: (row) => (
          <StatusPill tone={row.status === "enrolled" ? "success" : "neutral"}>
            {t(`billing.budget.filter.${row.status}`, { defaultValue: row.status })}
          </StatusPill>
        ),
      },
      {
        key: "computed",
        label: t("billing.budget.col.computed"),
        numeric: true,
        cell: (row) => <MoneyOrDash amount={row.level} currency={row.currency} locale={locale} />,
      },
      {
        key: "override",
        label: t("billing.budget.col.override"),
        numeric: true,
        cell: (row) => (
          <MoneyOrDash amount={row.level_override} currency={row.currency} locale={locale} />
        ),
      },
      {
        key: "they_pay",
        label: t("billing.budget.col.theyPay"),
        numeric: true,
        // The one the customer actually pays, drawn bold — it is the column a
        // clerk answers the phone from.
        cell: (row) => (
          <MoneyOrDash
            amount={row.effective_level}
            currency={row.currency}
            locale={locale}
            strong
          />
        ),
      },
      {
        key: "actual_to_date",
        label: t("billing.budget.col.actualToDate"),
        numeric: true,
        cell: (row) =>
          row.actual_to_date === null || row.actual_to_date === undefined ? (
            <span className="text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
              {t("billing.budget.noActual")}
            </span>
          ) : (
            <MoneyCell amount={row.actual_to_date} currency={row.currency} locale={locale} />
          ),
      },
      {
        key: "variance",
        label: t("billing.budget.col.variance"),
        numeric: true,
        // SIGNED, with its currency. ⚠ The engine's convention is B5's own and
        // it is the OPPOSITE of the sign the drawing illustrates: a POSITIVE
        // balance means the levels collected more than the customer used, so
        // the utility CREDITS it (`budget.settle_up`, ❄️ GT-24). Nothing here
        // flips it.
        cell: (row) => <MoneyOrDash amount={row.variance_balance} currency={row.currency} locale={locale} />,
      },
      {
        key: "relevel",
        label: t("billing.budget.col.relevel"),
        cell: (row) => {
          if (row.relevel_due_on === null || row.relevel_due_on === undefined) {
            return (
              <span className="text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
                {t("billing.budget.noRelevel")}
              </span>
            );
          }
          return row.relevel_is_due === true ? (
            <strong className="text-accent-700">{t("billing.budget.relevelDueNow")}</strong>
          ) : (
            // `DEF-BIL-5324` — p121 draws `Jan 2027`; this printed `2027-01`.
            // `formatMonthYear` is the product's one month-year formatter
            // (BR-SHL-023) and takes its month NAME from `Intl`, so this cell
            // needs no catalogue entry and cannot go stale when a language is
            // added. The value is date-only, so the zone is never consulted.
            <>{formatMonthYear(row.relevel_due_on, view.timeZone, locale)}</>
          );
        },
      },
      {
        key: "actions",
        label: t("billing.budget.col.actions"),
        cell: actions,
      },
    ],
  };
}

/**
 * §05 screen 25's four tiles — `ENROLLED · CARRYING A SHORTFALL · DUE TO
 * RE-LEVEL · ASKS WAITING`.
 *
 * ⚠ **EVERY DETAIL LINE IS EITHER A FACT OR THE REASON THERE IS NONE.** The
 * drawing's own detail lines are `of 1,284 accounts`, `$4,912.60 to settle`,
 * `drifted past 10%` and `from the portal · screen 25.3`. Three of the four
 * are built; the differences are deliberate and each is recorded:
 *
 *   · **`drifted past 10%` is not this tile's fact.** `budget.relevel_due` has
 *     TWO gates — the cadence and a drift breach — and only the cadence is
 *     stored. The tile counts what is stored and names the cadence in the
 *     tenant's own months (B14 rule 37: the `10%` is an illustration anyway).
 *   · **`screen 25.3` is an internal reference** and B14 rule 31 keeps one off
 *     a clerk's screen. The tile carries the reason the queue cannot be
 *     counted instead.
 */
function budgetKpis(
  t: Translator,
  summary: BudgetSummary | undefined,
  locale: string | undefined,
): KpiTile[] {
  const dash = "—";
  const muted = "text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]";
  return [
    {
      id: "enrolled",
      label: t("billing.budget.kpi.enrolled"),
      value: summary === undefined ? dash : summary.enrolled,
      detail:
        summary === undefined ? undefined : summary.accounts_total === null ? (
          <span className={muted}>{t("billing.budget.kpi.enrolledOfAbsent")}</span>
        ) : (
          t("billing.budget.kpi.enrolledOf", { total: summary.accounts_total })
        ),
    },
    {
      id: "shortfall",
      label: t("billing.budget.kpi.shortfall"),
      value: summary === undefined ? dash : summary.shortfall_accounts,
      detail:
        summary === undefined ? undefined : summary.shortfall_amount !== null &&
          summary.shortfall_currency !== null ? (
          <>
            <MoneyCell
              amount={summary.shortfall_amount}
              currency={summary.shortfall_currency}
              locale={locale}
            />{" "}
            {t("billing.budget.kpi.shortfallDetail")}
          </>
        ) : summary.shortfall_currencies.length > 1 ? (
          // CLAUDE.md rule 2 — two currencies do not add. The COUNT is still
          // true and the total is withheld rather than invented.
          <span className={muted}>{t("billing.budget.kpi.shortfallMixed")}</span>
        ) : undefined,
    },
    {
      id: "relevel",
      label: t("billing.budget.kpi.relevel"),
      value: summary === undefined || summary.relevel_due === null ? dash : summary.relevel_due,
      detail:
        summary === undefined ? undefined : summary.relevel_cadence_months === null ? (
          <span className={muted}>{t("billing.budget.kpi.relevelAbsent")}</span>
        ) : (
          t("billing.budget.kpi.relevelDetail", { months: summary.relevel_cadence_months })
        ),
    },
    {
      id: "asks",
      label: t("billing.budget.kpi.asks"),
      // ⚠ ALWAYS A DASH TODAY, AND THE TILE IS DRAWN RATHER THAN DROPPED. The
      // queue is real — a customer can ask for level pay from the portal — and
      // a missing tile would tell a clerk the product forgot about it.
      // `title` carries the server's own reason without spending a word of the
      // screen's budget on it (B14 rule 33: rationale is zero words on screen).
      value:
        summary === undefined || summary.asks_waiting === null ? (
          <span title={summary?.asks_waiting_unavailable ?? undefined}>{dash}</span>
        ) : (
          summary.asks_waiting
        ),
      detail:
        summary !== undefined && summary.asks_waiting === null ? (
          <span className={muted}>{t("billing.budget.kpi.asksAbsent")}</span>
        ) : undefined,
    },
  ];
}

/** The two things an override needs, mirroring the server's own VAL codes. */
function overrideSchema(t: Translator) {
  return z.object({
    override: z.string().trim().min(1, t("billing.budget.amount_required")),
    reason: z.string().trim().min(1, t("billing.budget.reason_required")),
  });
}

/** `100377 · Ridge Coffee Co.` — who this override lands on, in their words. */
function overrideAccountLabel(row: BudgetStatusRow, t: Translator): string {
  const who = row.customer_name ?? t("billing.budget.noCustomerName");
  return `${row.account_no ?? t("billing.budget.noAccountNo")} · ${who}`;
}

/**
 * The override, ASKED ABOUT ONE ROW — `DEF-BIL-5262`.
 *
 * ═════════════════════════════════════════════════════════════════════════
 * WHAT STOOD HERE, AND WHY A DIALOG REPLACES IT
 * ═════════════════════════════════════════════════════════════════════════
 * Two bare inputs sat UNDER the table with no row attached: a clerk typed an
 * amount and a reason into the page, and only the pencil they clicked
 * afterwards decided which customer it landed on. The register row is blunt
 * about the cost — *"a clerk cannot see which account they will change"* — and
 * an override fixes what somebody pays for a year.
 *
 * ⚠ **THE DRAWING DOES NOT DRAW THAT FORM, AND IT DOES NOT DRAW THIS ONE
 * EITHER.** p121 draws the table and no override anywhere on the screen, and no
 * actions column either. So the drawing does not answer where a clerk overrides
 * an ENROLLED account's level; entry 25.1 answers only the enrolment moment, and
 * its own override box is greyed because an enrolment request carries no
 * override (`DEF-BIL-5315`). Deleting the capability was the other reading and
 * it is worse: it takes a live write off the product to satisfy a silence. So
 * the CONTROL is the drawing's (a row action) and the FORM is built to our own
 * rules, which is exactly the split B14 rule 38 makes.
 *
 * ⚠ **THE COMPUTED FIGURE IS IN THE DIALOG ON PURPOSE.** p122's own rule row:
 * *"The ±30% bound is measured against the computed figure, so hiding it is how
 * an override gets typed blind."* BR-BIL-017 measures the bound against the
 * COMPUTED level, never the current one, so the dialog that takes the new figure
 * has to show the one it will be judged against.
 */
function OverrideLevelModal(props: {
  row: BudgetStatusRow;
  t: Translator;
  locale?: string;
  onClose: () => void;
  onCommit: (values: { override: string; reason: string }) => Promise<FormSubmitOutcome>;
}) {
  const { row, t } = props;
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  return (
    <FormModal
      title={t("billing.budget.overrideTitle")}
      kicker={overrideAccountLabel(row, t)}
      schema={overrideSchema(t)}
      values={{ override: amount, reason }}
      submitLabel={t("billing.budget.overrideAction")}
      onSubmit={() => props.onCommit({ override: amount.trim(), reason: reason.trim() })}
      onClose={props.onClose}
    >
      <p className="m-0 text-base text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
        {t("billing.budget.col.computed")}{" "}
        <MoneyOrDash amount={row.level} currency={row.currency} locale={props.locale} strong />
      </p>
      {/* `numeric` gives the decimal keypad and tabular figures and still hands
          the server a raw STRING — never `Number(...)`, which NUMERIC(18,6)
          does not survive (CLAUDE.md rule 2). */}
      <TextField
        id="override"
        label={t("billing.budget.field.override")}
        value={amount}
        onChange={setAmount}
        numeric
        required
      />
      <TextField
        id="reason"
        label={t("billing.budget.field.overrideReason")}
        value={reason}
        onChange={setReason}
        required
      />
    </FormModal>
  );
}

export interface BudgetBillsTabProps {
  client?: ApiClient; // test seam
  locale?: string;
  readOnly?: boolean;
  readOnlyReason?: string;
}

export function BudgetBillsTab(props: BudgetBillsTabProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const toast = useToast();
  const tenantPath = useTenantPath();
  // The shell's publication, never `GET /settings/regional` — that route is
  // Admin-only and a billing clerk meets a refusal on it (`DEF-SHL-4283`).
  // DEF-SHL-3964: `useRegional` and no hand-written fallback (DEF-SHL-9122).
  const { timeZone } = useRegional({});

  // §05 screen 25's toolbar state. The two-button `On budget billing / Taken
  // off` segment this replaces is now the `Status` filter chip — the same two
  // values, on B14 rule 12's toolbar instead of beside it, so the screen has
  // one filter mechanism rather than two.
  const [state, setState] = useState<TableRequestState>({
    q: "",
    sort: "enrolled_on",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: { status: "enrolled" },
  });
  const status = state.filters.status ?? "";
  // `DEF-BIL-5262` — WHICH ROW is being overridden, rather than two boxes
  // floating under the table with no account attached to them.
  const [overrideRow, setOverrideRow] = useState<BudgetStatusRow | null>(null);
  const blockedReason = props.readOnly === true ? (props.readOnlyReason ?? null) : null;

  const listQuery = useQuery({
    queryKey: budgetListKey(
      `${status}|${state.filters.relevel ?? ""}|${state.q}|${state.page}|${state.per}`,
    ),
    queryFn: () =>
      getBudgetEnrollments(
        {
          status,
          relevel: state.filters.relevel,
          q: state.q,
          page: state.page,
          per: state.per,
        },
        client,
      ),
    retry: false,
  });
  const relevelMutation = useMutation({
    mutationFn: (row: BudgetStatusRow) =>
      relevelBudgetAccount(row.account_id, { on_date: todayIso() }, client),
  });
  const overrideMutation = useMutation({
    mutationFn: (input: { row: BudgetStatusRow; override: string; reason: string }) =>
      overrideBudgetLevel(
        input.row.account_id,
        // A DECIMAL STRING, straight from the input. Never `Number(...)`:
        // NUMERIC(18,6) does not survive an IEEE double and the server refuses
        // a float outright (CLAUDE.md rule 2).
        { override: input.override, reason: input.reason, on_date: todayIso() },
        client,
      ),
  });
  const removeMutation = useMutation({
    mutationFn: (row: BudgetStatusRow) =>
      removeFromBudgetBilling(
        row.account_id,
        { reason: t("billing.budget.removeReason"), on_date: todayIso() },
        client,
      ),
  });

  async function refresh(): Promise<void> {
    await queryClient.invalidateQueries({ queryKey: ["budget-billing"] });
  }

  const data = listQuery.data;
  const summary = data?.summary;

  // §05 screen 25's four tiles. Each is DERIVED from the served summary, and
  // each absent member renders the reason rather than a `0` — the tile that
  // says `0` says *nobody*, and the one that says `—` says *nobody could ask*.
  const kpis = useMemo(
    () => budgetKpis(translate, summary, props.locale),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [summary, t, props.locale],
  );

  // §05 screen 25's row actions — UNCHANGED. The three verbs, their icons,
  // their disabled reasons and their toasts are exactly what shipped; only the
  // table around them moved. `RowActions` keeps B14 rule 15 (icons with
  // tooltips, never text links) and G37 reads them there.
  const rowActions = (row: BudgetStatusRow) => (
            <RowActions>
              <RowAction
                label={t("billing.budget.relevelAction")}
                icon={<WrenchIcon />}
                reason={blockedReason}
                onClick={async () => {
                  const outcome = await relevelMutation.mutateAsync(row);
                  await refresh();
                  // "We looked and it was fine" is the fact J09 step 5
                  // asks for (US-BIL-020 TC-1) — reporting it as an error
                  // would train a clerk to ignore the one that matters.
                  toast(
                    outcome.changed
                      ? t("billing.budget.releveled")
                      : t("billing.budget.relevelUnchanged"),
                  );
                }}
              />
              <RowAction
                label={t("billing.budget.overrideAction")}
                icon={<PencilIcon />}
                /* `DEF-BIL-5262` — it OPENS THE ASK rather than committing one
                   typed somewhere else on the page. The old reason read *"Type
                   an amount and a reason first"*, which disabled the pencil on
                   every row until a clerk had filled boxes that named no
                   account; the dialog asks for both with the account at its
                   head, and the kit validates them where they are typed. */
                reason={blockedReason}
                onClick={() => setOverrideRow(row)}
              />
              <RowAction
                label={t("billing.budget.removeAction")}
                icon={<PowerIcon />}
                danger
                reason={
                  blockedReason ??
                  (row.status !== "enrolled" ? t("billing.budget.notEnrolled") : null)
                }
                onClick={async () => {
                  const outcome = await removeMutation.mutateAsync(row);
                  await refresh();
                  // The CARRIED balance is named, with its currency: a
                  // customer coming off the programme still owes (or is
                  // owed) it, and a bare "removed" would let it vanish.
                  toast(
                    t("billing.budget.removed", {
                      amount: outcome.variance_balance_carried,
                      currency: outcome.currency,
                    }),
                  );
                }}
              />
            </RowActions>
  );

  const tableConfig = budgetTableConfig(
    translate,
    {
      locale: props.locale,
      timeZone,
      accountHref: (row) => tenantPath(accountDetailPath(row.account_id)),
    },
    rowActions,
  );

  return (
    <div className="flex flex-col gap-4">
      <p className="m-0 mb-4 max-w-measure text-base leading-prose text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
        {t("billing.budget.explainer")}
      </p>

      {/* §05 screen 25's KPI band, above the toolbar exactly as drawn. It is
          the shared `KPIStrip` — one visual decision for every tile in the
          product (B14 rule 36). */}
      <KPIStrip kpis={kpis} loading={listQuery.isPending} />

      {/* ══════════════════════════════════════════════════════════════════
          THE DOOR TO §05 ENTRY 25.1, AND THE PANEL IT REPLACES
          ══════════════════════════════════════════════════════════════════
          What stood here: `Put a customer on budget billing` — a free-text box
          reading *"Paste the account's id from its detail page"* with the
          eligibility read, the plan-flag tick and the commit button under it.

          It goes for three filed reasons and one drawn one. `DEF-BIL-5232`: a
          database id was the visible value of a field, which B14 rule 31
          forbids by name, and the One-time bill tab beside it has picked an
          account properly all along. `DEF-BIL-5261`: at 1440 the commit button
          overlapped the checkbox label beside it and cut the sentence
          mid-word — and that row's own prevention note says the fix *"rides
          that wave rather than patching the current stacking"*. This is that
          wave. `DEF-BIL-5316`: the panel rendered the SERVER's own
          `eligible_unavailable` sentence verbatim — *"BR-RAT-043 puts
          budget-billing eligibility on the rate PLAN and no endpoint publishes
          that flag (OQ-237)"* — so two rule ids reached a clerk, which B14 rule
          31 forbids and rule 32 repeats. A server sentence written for an
          engineer is not screen copy; the enrol form states the same absence in
          its own catalogue words.

          ⚠ **THAT THIRD ID IS NAMED HERE BECAUSE ITS ROW NAMES THIS FILE.**
          `G67 fix-leaves-a-trace` counts a closed row whose named file never
          mentions the id, and it rose by one when this panel was removed: the
          fix was real and the trace was in the NEW file, so a lane grepping
          `BudgetBillsTab.tsx` for `DEF-BIL-5316` would have found nothing and
          concluded it was never made.

          And the drawing puts the control HERE and the form on its own page:
          §05 entry 25 draws `+ Enrol an account` as an action, and 25.1 draws
          what it opens, with a page head of its own. Two ways to enrol would be
          two answers to one question, so the panel does not survive beside it.

          ⚠ **IT IS A LINK AND NOT A BUTTON** — the destination is an ADDRESS, so
          middle-click and "open in new tab" work, and a test can assert the door
          by where it points. `DEF-CWP-3925` is what the alternative costs: eight
          controls over live screens, and nothing anywhere asking whether a door
          still pointed at anything. */}
      {/* ⚠ **TWO DOORS, AND THE SECOND ONE IS §05 ENTRY 25.3.** The drawing
          gives the asks queue a page head of its own and reaches it from this
          tab — *"Billing › Budget Bills · service requests raised from the
          portal"*. It is a LINK for the reason the enrol door is: a destination
          with an ADDRESS is the only kind a test can assert and the only kind
          middle-click opens. `budgetAsksPage.dom.test.tsx` asserts this one by
          where it points, not by its words. */}
      <div className="flex justify-end gap-2">
        {/* §05 entry 25.2's door. A LINK for the same reason the enrol and
            asks doors are: the destination is an ADDRESS, so a test can assert
            it by where it points rather than by what it is called. The
            forecast writes nothing, so it is secondary. */}
        <ButtonLink variant="secondary" to={tenantPath(BUDGET_FORECAST_ROUTE)}>
          {t("billing.settleUp.door")}
        </ButtonLink>
        <ButtonLink variant="secondary" to={tenantPath(BUDGET_ASKS_ROUTE)}>
          {t("billing.budgetAsks.door")}
        </ButtonLink>
        <ButtonLink variant="primary" to={tenantPath(BUDGET_ENROL_ROUTE)}>
          {t("billing.budgetEnrol.door")}
        </ButtonLink>
      </div>

      <Panel as="section">
        <h3>{t("billing.budget.listTitle")}</h3>
        {/* The TENANT's own parameters, or the reason they cannot be read —
            never the ratified defaults, which would print figures no tenant
            chose (BR-BIL-021). ⚠ THE REASON IS A CATALOGUE SENTENCE FOR THE
            SERVER'S `message_key`, and the rule sits on `data-br-ref` for
            support (`DEF-BIL-5339`): until 2026-09-15 this printed the settings
            seam's own refusal — a dotted module path and a rule id — verbatim. */}
        {data?.parameters_unavailable !== null && data?.parameters_unavailable !== undefined && (
          <p
            className="font-body text-base leading-normal font-normal tracking-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] [&[role=alert]]:text-accent-700"
            role="note"
            data-br-ref={data.parameters_unavailable.br_ref}
          >
            {data.parameters_unavailable.message_key !== undefined
              ? t(data.parameters_unavailable.message_key)
              : data.parameters_unavailable.detail}
          </p>
        )}
        {/* ══════════════════════════════════════════════════════════════════
            §05 SCREEN 25's TABLE — THE SHARED `DataTable`, NOT A SECOND ONE.
            ══════════════════════════════════════════════════════════════════
            What this replaced: a `PlainTable` with a two-button segment above
            it, six columns, EVERY row the server held and no footer. The
            toolbar (B14 rule 12), the pagination footer (rule 16), the column
            chooser, the loading, empty and failed states and `NFR-3`'s
            server-side paging all arrive by composing the kit — none of them
            is written here, which is the point of having one table.

            ⚠ **THE `Status` SEGMENT DID NOT DISAPPEAR, IT MOVED.** Its two
            values are the `Status` filter chip in the toolbar. A screen with a
            segment AND a filter panel has two ways to say one thing, which is
            the shape `DEF-1700` removed from four other screens. */}
        <DataTable<BudgetStatusRow>
          config={tableConfig}
          state={state}
          onStateChange={setState}
          rows={data?.results ?? []}
          totalRows={data?.count ?? null}
          loading={listQuery.isPending}
          error={
            listQuery.isError
              ? {
                  reason: apiErrorText(listQuery.error, translate),
                  onRetry: () => void listQuery.refetch(),
                }
              : null
          }
          empty={{
            title: t("billing.budget.empty"),
            helper: t("billing.budget.emptyHelper"),
          }}
          filterBarSlot={
            <FilterBar
              filters={tableConfig.filters ?? []}
              state={state}
              onStateChange={setState}
            />
          }
        />
        {/* ══════════════════════════════════════════════════════════════════
            WHICH SET AN EMPTY LIST IS — `DEF-BIL-5340`
            ══════════════════════════════════════════════════════════════════
            This list holds accounts ALREADY on budget billing, so an account
            that exists and is not enrolled correctly has no row — and the kit's
            zero-results line alone (*"No results for 'AC-2026-00038'."*) let a
            clerk conclude the search was dead. The line under it names the set
            (with a term: what was searched; without: what is listed) and
            carries the enrol door as an INLINE LINK to the same address as the
            button above, so a clerk who searched for someone to enrol is one
            click from doing it. It is a link and not a second button for the
            reason the doors above are: an address a test can assert. */}
        {!listQuery.isPending && !listQuery.isError && data?.count === 0 && (
          <p
            className="m-0 mt-3 text-center text-base leading-prose text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]"
            role="note"
            data-bil="search-scope"
          >
            {state.q === "" ? t("billing.budget.listScope") : t("billing.budget.searchScope")}{" "}
            <InlineLinkTo to={tenantPath(BUDGET_ENROL_ROUTE)}>{t("billing.budgetEnrol.door")}</InlineLinkTo>
          </p>
        )}
      </Panel>

      {/* ══════════════════════════════════════════════════════════════════
          THE ONE ABSENCE THE SERVER LIST DOES NOT CARRY — `DEF-BIL-5339`
          ══════════════════════════════════════════════════════════════════
          Until 2026-09-15 this read "Three things this screen does not do" —
          a COUNT typed by hand over a list whose length the server decides —
          and its paragraph explained WHY bulk enrolment and a list import are
          absent, which is rationale, and rule 33 gives rationale zero words
          on screen. Both of those absences are now the server's own bullets
          under the list below (`billing.budget.gap.oneAtATime`), whose heading
          derives its count from the list's length, so this note states the
          one thing that is NOT a server gap: the yearly-increase cap is a
          tenant SETTING (BR-BIL-021) written on Settings, not here. The
          reasoning is in this file's header. `DEF-476` is the row that first
          corrected the reason recorded here, and stays on the element. */}
      <ArrivesWith
        title={t("billing.budget.awaitsTitle")}
        message={t("billing.budget.awaits")}
        tracks="DEF-476"
      />
      <GapNotes gaps={data?.unavailable ?? []} t={translate} />

      {/* `DEF-BIL-5262` — the override, asked about ONE account. It mounts only
          while a row is chosen, so the screen carries no form nobody has
          pointed at. */}
      {overrideRow !== null && (
        <OverrideLevelModal
          row={overrideRow}
          t={translate}
          locale={props.locale}
          onClose={() => setOverrideRow(null)}
          onCommit={async (values) => {
            try {
              await overrideMutation.mutateAsync({ row: overrideRow, ...values });
            } catch (error) {
              // The server is authoritative: its refusal renders INSIDE the
              // dialog, beside the figures that caused it, rather than as a
              // toast over a form the clerk can no longer see.
              return isApiError(error)
                ? { ok: false as const, error: formErrorEnvelope(error) }
                : { ok: false as const, error: { code: "", message_key: "api.error.unexpected" } };
            }
            await refresh();
            setOverrideRow(null);
            toast(t("billing.budget.overridden"));
            return { ok: true as const };
          }}
        />
      )}
    </div>
  );
}

export default BudgetBillsTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-018@b3f81d0 (sources: 04-docs/05-modules/07-billing/06-epics/EP-BIL-05-budget-billing.md US-BIL-018/019/020 §1/§3/§5 · 07-billing/02-business-rules.md BR-BIL-011/017/021 · 07-billing/08-worked-examples.md WE-8 · 05-prototype/UtilityBilling.html §Billing "Budget Bills" lines 3421-3466 · 06-backend/apps/billing/budget_api.py; co-packets US-BIL-019, US-BIL-020)
// generated: 2026-08-16 by story-coder (billing SURFACE lane — S30's Budget Bills tab)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the browser check failed against the tab before it existed. Verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: E3 [law 6, prototype diff] the prototype's "All eligible residential (312)" and "Import list from CSV" are NOT ported. ⚠ AMENDED 2026-08-21 (DEF-476): the reason recorded here was that no endpoint publishes the plan's budget flag (OQ-237) and `GET /plans` HAS served `budget_billing` since rating/selectors.py:420 — half of OQ-237 is answered. What actually blocks a bulk enrolment is that no account records which plan it is on, so there is no set to iterate. One account at a time, with the number shown first · E3 the prototype's "Cap increases at 15% YoY" and "opt-in only" checkboxes are tenant SETTINGS under BR-BIL-021 and belong to S69 — drawing them here would offer a control that saves nowhere · E3 the plan-budget flag is a STAFF CONFIRMATION on screen, not a hidden `true` · E3 `level`, `level_override` and `effective_level` are three cells, never collapsed: the ±30% bound is measured against the COMPUTED level · E3 a null level renders as a stated absence and NEVER as 0.00 · E3 the override travels as a decimal STRING, never `Number(...)` · E3 nothing here drops an account automatically — BR-BIL-017's drop-off is SUPERSEDED (PO 2026-08-11)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
