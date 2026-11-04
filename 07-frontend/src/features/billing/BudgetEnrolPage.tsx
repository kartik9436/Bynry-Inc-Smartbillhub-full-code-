// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-018 (enrolment, eligibility & the level computation)
//           Screens: §05 entry **25.1 `Enrol`** of `05-prototype/04 Billing,
//           As Built.pdf` — p122(mid)–p124(top), read AS IMAGES at scale 2
//           (B14 rule 42). p124 is its commentary; p121–p122(top) are entry 25,
//           the table this screen is reached from.
// Rules:    B14 rule 41 (the product matches the drawing; only a drawing that
//           contradicts a signed rule reaches the PO) · rule 42 (build from the
//           image) · rule 38 (a FORM's construction answers to the UI rules,
//           not the drawing) · rule 33 (five caps, and RATIONALE is zero words
//           on screen) · rule 32 (one sentence per section; no rule id in
//           clerk-facing copy) · rule 31 (no database id is ever a field's
//           visible value) · rule 40 (the page-head title is 32px) · rule 21
//           (Tailwind utilities; this file is on `route-b-migrated.txt`) ·
//           rule 36 (r10 gives the VISUAL STYLE; the kit is how you comply) ·
//           BR-BIL-017 (one live budget status per account; the override bound
//           is measured against the COMPUTED level) · BR-BIL-021 (every
//           parameter is a tenant setting, never defaulted) · BR-RAT-043 +
//           OQ-237 (budget eligibility rides the rate plan's flag, which no
//           endpoint publishes) · CLAUDE.md rule 2 (money 4dp, display 2, and
//           never a float) · hard-won law 2 and its 2026-09-05 mirror
// Tests:    src/features/billing/budgetEnrolPage.dom.test.tsx
// Impacts:  src/App.tsx (the route) · src/features/billing/BudgetBillsTab.tsx
//           (the door, and the free-text panel this replaces) ·
//           07-frontend/src/styles/route-b-migrated.txt · eleven catalogues
// ───────────────────────────────────────────────────────
//
// §05 entry 25.1. The clerk's sentence the drawing opens with: *"Put this
// customer on a flat monthly amount. Show me who they are, the figure, and how
// far I am allowed to move it."*
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS REPLACES, AND WHY IT IS A ROUTE RATHER THAN A PANEL
// ══════════════════════════════════════════════════════════════════════════
// `BudgetBillsTab` carried an inline `Put a customer on budget billing` panel
// whose account field was a free-text box reading *"Paste the account's id from
// its detail page"* — `DEF-BIL-5232`, a database id as the visible value of a
// field, which B14 rule 31 forbids by name. `DEF-BIL-5261` is the same panel's
// commit button overlapping the checkbox label at 1440. Both are closed by this
// screen, and the panel is gone: two ways to enrol would be two answers to one
// question.
//
// It is a ROUTE (`/:tenant/billing/budget/enrol`) and not a panel because the
// drawing gives it a page head of its own — the title becomes `Enrol an
// account`, `Cancel` sits top-right, and the Billing tab strip stays with
// `Budget Bills` active. A door with an ADDRESS is also the only kind a test can
// assert by destination, which is what `DEF-CWP-3925` cost when nothing asked
// whether a control still pointed anywhere.
//
// ══════════════════════════════════════════════════════════════════════════
// TEN FACT ROWS ARE DRAWN AND THE DOCUMENT SAYS NINE, TWICE
// ══════════════════════════════════════════════════════════════════════════
// p123 says *"Nine facts"* and p124 says *"Nine facts, in three bands"*, and
// the page draws `WHO, AND WHERE` 3 + `CAN IT BE LEVELLED` 4 + `WHAT CHANGES
// FOR THEM` 3 = **10**. B14 rule 42 makes the image the specification and the
// prose an index, so TEN rows are built. `CR-103-BRC03`'s step-1 record reached
// the same count off the page at scale 4 and settled it the same way.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE THREE DRAWN FIGURES NO ENDPOINT PUBLISHES — STATED, NEVER INVENTED
// ══════════════════════════════════════════════════════════════════════════
// **NO MONEY ARITHMETIC HAPPENS IN THIS FILE.** Every figure is a decimal
// string the server computed, rendered through `MoneyCell`. Three of the
// drawing's figures are therefore absences with their reason beside them, and
// each carries a defect row rather than a plausible number:
//
//   · **The trailing-twelve TOTAL** (drawn `$936.00`). `GET
//     /budget-billing/{id}/eligibility` serves the twelve per-period actuals
//     and no sum. Adding them here would be a second answer to a figure the
//     server owns — and `compute_level` divides by the tenant's
//     `eligibility_months`, which need not equal the number of actuals read, so
//     a browser-side `total ÷ 12` could disagree with the computed level drawn
//     two rows below it. `DEF-BIL-5313`.
//   · **The override BAND** (drawn `$54.60 – $101.40`). `budget.override_bounds`
//     is written, tested, and has **no caller outside `validate_override`** —
//     hard-won law 2 — so the range reaches no payload. The PERCENTAGE is
//     served (the tenant's own `override_bound_pct`, BR-BIL-021) and is drawn;
//     the range is stated absent. `DEF-BIL-5312`.
//   · **The ageing, the autopay instrument and the next bill.** `aging` is
//     served null with its reason (no module publishes open-invoice due dates),
//     `autopay` is a boolean with no instrument behind it, and an account
//     reaches a cycle by walking unit → route → cycle at run time, which no
//     read publishes. Three stated absences. `DEF-BIL-5314`.
//
// ⚠ **AND THE OVERRIDE FIELD IS DRAWN, RENDERED AND REFUSED WITH ITS REASON.**
// `POST /budget-billing/enrollments` takes `{account_id, plan_offers_budget,
// on_date}` and no override; `enroll` computes the level itself. An override is
// a SECOND write (`POST /budget-billing/{id}/override`) and `validate_override`
// refuses one with no REASON, which this drawing gives no field for. Enrolling
// and then overriding would be two writes on a money path with no rule for the
// half-done state. So the control is drawn and greyed WITH its reason, which is
// the blueprint's own doctrine one page earlier (p121: *"Greyed-with-a-reason
// tells a clerk to enrol one at a time; a missing control tells them the
// product forgot"*), and the button names the figure that will really be
// written. `DEF-BIL-5315`.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHERE THE DRAWING AND B14 DISAGREE — RULE 38, RECORDED, NOT BUILT
// ══════════════════════════════════════════════════════════════════════════
// This is a FORM, so rule 38 puts its CONSTRUCTION under the UI rules while
// WHAT it contains stays the drawing's. Every divergence is copy length under
// rule 33, and no fact, row or control is dropped:
//
//   · **The four captions are RATIONALE and rule 33 gives rationale ZERO words
//     on screen.** *"Nine facts, and each one can change the answer…"*,
//     *"Two tests, and both refuse by name…"*, *"The band is measured against
//     the computed figure, so it does not move when you override"* and the
//     drawn version of *"It reads nine facts and writes none of them"* all say
//     WHY the screen works as it does. They live here, in the register and in
//     the conformance record — which is where rule 33 puts them.
//   · **Band and section headings are trimmed to three words**: `CAN IT BE
//     LEVELLED` → `Can it level`, `WHAT CHANGES FOR THEM` → `What changes`,
//     `IS THIS ACCOUNT ELIGIBLE` → `Eligibility`, and the warning block's
//     `TWO OF THOSE NINE CHANGE WHAT YOU TELL THE CUSTOMER` → `Tell the
//     customer`.
//   · **The two warnings and the footer are cut to six words per sentence.**
//     They are NOT rationale and they stay: *"Arrears are not levelled"* and
//     *"autopay changes"* are facts a clerk says out loud to a customer, and
//     rule 33's own words for a consequence are *never cut below clarity*.
//
// ⚠ **THE AUTOPAY WARNING IS WORDED TO WHAT THE PRODUCT DOES.** The drawing
// says *"From 30 Nov the amount taken becomes the level"*; in this version
// autopay is *"a promise recorded, never a charge"* (`DEF-644`, the reason
// `StatusPill` grew a `title` at all). Printing the drawn sentence would tell a
// clerk money will leave an account when nothing collects. The row carries the
// established qualifier — `customers.account.pill.autopayOnWhy` — and the
// warning says the thing that is true and useful: tell them the amount changes.
//
// ⚠ **`eligible_unavailable` IS NOT RENDERED, AND THE TAB RENDERS IT TODAY.**
// The server's sentence is *"BR-RAT-043 puts budget-billing eligibility on the
// rate PLAN and no endpoint publishes that flag (OQ-237)…"* — two rule ids at a
// clerk, which B14 rule 31 forbids by name and rule 32 repeats. This screen
// states the same absence in its own catalogue words. `DEF-BIL-5316` carries
// the tab's copy of it; nothing here edits that file's panel beyond removing
// the one this screen replaces.
import { useMemo, useState } from "react";
import type { ReactNode } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  enrollInBudgetBilling,
  getBudgetEligibility,
  getBudgetEnrollments,
} from "@/api/billingOpsEndpoints";
import { getAccountDetail, getAccounts } from "@/api/endpoints";
import type { AccountDetail, AccountRow } from "@/api/endpoints";
import { BandHeading } from "@/components/BandHeading";
import { Button } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { AccountServiceChips } from "@/features/customers/accountsListCells";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  BILLING_TABS,
  BILLING_TAB_ALL,
  BILLING_ROUTE,
  BUDGET_TAB_ROUTE,
} from "./billingShared";
import { budgetEligibilityKey } from "./BudgetBillsTab";
import { todayIso } from "./billingOpsShared";

/** The tenant's own budget parameters, read off the list response.
 *
 *  ⚠ **THE BAND PERCENTAGE HAS NO READ OF ITS OWN.** `GET /budget-billing`
 *  serves `parameters` — the whole of `settings_seam.budget_billing()`,
 *  `override_bound_pct` included — and the eligibility read does not. `per: 1`
 *  because this screen wants the parameters and none of the rows; the key sits
 *  under the same `budget-billing` prefix so the tab's own invalidate clears
 *  it. */
export const budgetParametersKey = ["budget-billing", "parameters"] as const;

/**
 * One label/value row of a fact band.
 *
 * Two cells and never three: the drawing's bands are a label column and a value
 * column, and a qualifier (`· 13 months`, `· card ending 4218`) rides INSIDE
 * the value beside the fact it qualifies.
 */
function FactRow(props: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-row items-baseline gap-4 border-b border-b-divider py-2 last:border-b-0 max-sm:flex-col max-sm:items-start max-sm:gap-1">
      <dt className="w-48 shrink-0 font-body text-base leading-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] max-sm:w-auto">
        {props.label}
      </dt>
      <dd className="m-0 font-body text-base leading-normal">{props.children}</dd>
    </div>
  );
}

/**
 * A fact this product does not hold, said in words.
 *
 * ⚠ **NEVER A FABRICATED ZERO AND NEVER A BLANK.** A dash alone is
 * indistinguishable from a figure nobody looked at; the sentence beside it is
 * what tells a clerk the difference between *nothing is owed* and *nobody could
 * ask*. Same posture as `MoneyOrDash`'s null branch one file over.
 */
function NotHeld(props: { children: ReactNode }) {
  return (
    <span
      className="font-body text-base leading-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]"
      role="note"
    >
      {props.children}
    </span>
  );
}

/**
 * Which sentence a section shows when it has no eligibility payload yet.
 *
 * ⚠ **THREE STATES, NOT ONE.** *Nobody has been picked*, *the read is in
 * flight* and *the read came back with nothing* are three different facts and a
 * clerk acts differently on each. Collapsing them into one grey line is
 * `G122`'s defect — the screen that drew the same thing while loading and after
 * fourteen 404s, so nothing on it could say which had happened.
 */
export function eligibilityState(accountId: string, pending: boolean): string {
  if (accountId === "") {
    return "billing.budgetEnrol.absent.pickFirst";
  }
  return pending ? "billing.budgetEnrol.absent.loading" : "billing.budgetEnrol.absent.noRead";
}

/**
 * A two-column table row — `TEST | THIS ACCOUNT` and `BASIS | AMOUNT`.
 *
 * ⚠ **THE LAST CELL IS `cell` AND NOT `amount`, AND THE NAME IS LOAD-BEARING.**
 * It holds an already-rendered node — a `MoneyCell`, a `NotHeld` sentence or a
 * bolded verdict — never a decimal string. Calling it `amount` said the
 * opposite, and `G44` read the name and counted it as a money value reaching a
 * text position raw: 29 untreated to 30, this lane's own. The gate was right
 * about the NAME even though the value was already safe, and a later reader
 * passing a bare `"78.000000"` into a prop called `amount` is precisely the
 * defect it guards.
 */
function VerdictRow(props: { label: ReactNode; basis?: ReactNode; cell: ReactNode }) {
  return (
    <tr className="border-b border-b-divider last:border-b-0">
      <th
        scope="row"
        className="py-2 pr-4 text-left font-body text-base font-normal leading-normal"
      >
        {props.label}
      </th>
      {props.basis !== undefined && (
        <td className="py-2 pr-4 text-right font-body text-base leading-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] [font-feature-settings:'tnum']">
          {props.basis}
        </td>
      )}
      <td className="py-2 text-right font-body text-base leading-normal [font-feature-settings:'tnum']">
        {props.cell}
      </td>
    </tr>
  );
}

/**
 * How the picker names one account — `100612 · Whitlock, R. — 44 Pecan Row`.
 *
 * Every part is nullable, so the label falls back through account # → name →
 * a stated placeholder and NEVER renders empty. An option a clerk can select
 * without knowing whose money they are fixing for a year is the shape of a
 * mis-enrolled customer. (The same rule as
 * `features/billing/oneTimeBill/AccountStep.accountOption` and
 * `PaymentsPage.accountPickerLabel`; restated rather than imported, because
 * both of those files belong to other lanes' diffs today and the rule is what
 * matters, not the function. Pointer corrected 2026-09-30, DEF-BIL-8152.)
 *
 * ⚠ **THE OPTION'S VALUE IS THE ID AND ITS LABEL NEVER IS** — B14 rule 31. A
 * `<option value>` is not rendered text.
 */
export function enrolAccountLabel(account: AccountRow, t: Translator): string {
  const who =
    account.account_no !== null && account.name !== null
      ? `${account.account_no} · ${account.name}`
      : (account.account_no ?? account.name ?? t("billing.budgetEnrol.accountUnnamed"));
  return account.premise !== null ? `${who} — ${account.premise}` : who;
}

/** `Oct 2025 · 13 months` — the calendar date the server served, and the whole
 *  months since. A month count is a calendar derivation and not a money one;
 *  it is computed from the served date rather than asked of a second read. */
export function openSinceMonths(openedAt: string, today: string): number | null {
  const opened = new Date(`${openedAt}T00:00:00Z`);
  const now = new Date(`${today}T00:00:00Z`);
  if (Number.isNaN(opened.getTime()) || Number.isNaN(now.getTime()) || opened > now) {
    return null;
  }
  const months =
    (now.getUTCFullYear() - opened.getUTCFullYear()) * 12 +
    (now.getUTCMonth() - opened.getUTCMonth());
  return now.getUTCDate() >= opened.getUTCDate() ? months : months - 1;
}

export interface BudgetEnrolPageProps {
  client?: ApiClient; // test seam
  locale?: string;
  readOnly?: boolean;
  readOnlyReason?: string;
}

export function BudgetEnrolPage(props: BudgetEnrolPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const toast = useToast();

  const [accountQuery, setAccountQuery] = useState("");
  // ⚠ **THE CHOSEN ACCOUNT LIVES IN THE ADDRESS, NOT IN COMPONENT STATE.**
  // The drawing's breadcrumb gives this screen two entrances — `+ Enrol an
  // account`, which arrives with nobody picked, and *"an ask on screen 25.3"*,
  // which arrives with the account the customer asked about. An address is the
  // only way the second one can hand it over, and it makes the half-filled
  // screen a link a clerk can be sent. `/billing/fix?bill=` is the same shape
  // one tab along.
  const [params, setParams] = useSearchParams();
  const accountId = params.get("account") ?? "";
  const [planFlag, setPlanFlag] = useState(false);
  const blockedReason = props.readOnly === true ? (props.readOnlyReason ?? null) : null;

  // IS-3 — the account search is SERVER-side and a term under two characters is
  // not sent, the same minimum every other search in this product uses. An
  // empty box does not pull a tenant's whole account list into a select.
  const accountsQuery = useQuery({
    queryKey: ["budget-billing", "enrol", "account-picker", accountQuery],
    queryFn: () => getAccounts({ q: accountQuery, per: 50 }, client),
    enabled: accountQuery.trim().length >= 2,
    retry: false,
  });
  const accounts: AccountRow[] = accountsQuery.data?.results ?? [];

  const detailQuery = useQuery({
    queryKey: ["budget-billing", "enrol", "account", accountId],
    queryFn: () => getAccountDetail(accountId, client),
    enabled: accountId !== "",
    retry: false,
  });

  const eligibilityQuery = useQuery({
    queryKey: budgetEligibilityKey(accountId),
    queryFn: () => getBudgetEligibility(accountId, client),
    enabled: accountId !== "",
    retry: false,
  });

  // BR-BIL-021 — the TENANT's own band percentage, or nothing. Never the
  // seeded 30, which would print a figure this tenant never chose.
  const parametersQuery = useQuery({
    queryKey: budgetParametersKey,
    queryFn: () => getBudgetEnrollments({ per: 1 }, client),
    retry: false,
  });

  const enrollMutation = useMutation({
    mutationFn: (planOffersBudget: boolean) =>
      enrollInBudgetBilling(
        {
          account_id: accountId,
          // OQ-237 — the flag is a STAFF STATEMENT, ticked deliberately,
          // because BR-RAT-043 puts it on the rate plan and no endpoint reads
          // it. A hidden `true` would enrol customers on a flat amount their
          // tariff never promised.
          plan_offers_budget: planOffersBudget,
          on_date: todayIso(),
        },
        client,
      ),
  });

  const detail: AccountDetail | undefined = detailQuery.data;
  const eligibility = eligibilityQuery.data;
  const parameters = parametersQuery.data?.parameters;
  const boundPct =
    parameters !== null && parameters !== undefined && parameters["override_bound_pct"] !== undefined
      ? String(parameters["override_bound_pct"])
      : null;

  const openSince = useMemo(() => {
    if (detail?.opened_at === null || detail?.opened_at === undefined) {
      return null;
    }
    return openSinceMonths(detail.opened_at, todayIso());
  }, [detail?.opened_at]);

  // WHAT WILL REALLY BE WRITTEN. `enroll` computes the level itself and the
  // enrolment request carries no amount, so the button names the COMPUTED
  // figure — never the override box's contents, which nothing sends.
  const willPay = eligibility?.computed_level ?? null;
  const willPayCurrency = eligibility?.currency ?? null;
  const canEnrol =
    accountId !== "" &&
    planFlag &&
    willPay !== null &&
    willPayCurrency !== null &&
    eligibility?.already_enrolled === false &&
    blockedReason === null;

  async function enrol(): Promise<void> {
    try {
      await enrollMutation.mutateAsync(planFlag);
      await queryClient.invalidateQueries({ queryKey: ["budget-billing"] });
      toast(t("billing.budget.enrolled"));
      navigate(tenantPath(BUDGET_TAB_ROUTE));
    } catch (error) {
      toast(isApiError(error) ? apiErrorText(error, translate) : t("api.error.unexpected"));
    }
  }

  return (
    <div className="px-4 pt-6 pb-8">
      {/* Rule 2 — ONE page header, declared and not drawn; rule 40 puts its
          title at 32px on every screen. The drawing keeps the Billing tab strip
          under it with `Budget Bills` active, so the clerk can see where they
          are without the breadcrumb becoming a second navigation. */}
      <PageHeader
        title={t("billing.budgetEnrol.title")}
        rollup={t("billing.budgetEnrol.caption")}
        /* ⚠ **THE HEAD'S `Cancel` IS GONE — PO RULING 2026-09-19 (***"cancel
           button should be bottom not on top"***), AND THIS SCREEN WAS THE ONE
           WITH TWO OF THEM.** The footer below already carried an exit to
           `BUDGET_TAB_ROUTE` — the SAME destination this one had — so the page
           drew two controls doing one job, in two places, under two different
           words (`Cancel` up here, `Back` down there). Removing the head one
           is the whole fix: nothing moves to the footer, because the footer
           already had it.
           ⚠ **AND THIS PAGE IS NOT A WIZARD**, which is why it takes no
           `cancel` prop like the four wizards changed alongside it: there is
           no step rail and no `WizardFrame`, so B14 rule 3 does not apply and
           there is no `← Back` for a label to collide with (rule 1). Its
           footer is its own. */
        tabs={BILLING_TABS.map((tab) => ({ id: tab.id, label: t(tab.labelKey) }))}
        activeTabId="budget"
        tabsLabel={t("billing.tabsLabel")}
        onTabSelect={(tab) =>
          navigate(tenantPath(tab.id === BILLING_TAB_ALL ? BILLING_ROUTE : `${BILLING_ROUTE}/${tab.id}`))
        }
      />

      {/* ── 1 · WHO ──────────────────────────────────────────────────────── */}
      <Panel as="section">
        <h3>{t("billing.budgetEnrol.group.who")}</h3>

        <div className="mb-3 flex max-w-[520px] flex-col gap-1">
          <label
            className="font-heading text-sm font-semibold text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]"
            htmlFor="bil-enrol-search"
          >
            {t("billing.budgetEnrol.field.account")}
          </label>
          <input
            id="bil-enrol-search"
            className="input"
            value={accountQuery}
            onChange={(event) => setAccountQuery(event.target.value)}
            placeholder={t("billing.budget.search")}
          />
          <select
            aria-label={t("billing.budgetEnrol.field.accountMatches")}
            className="input"
            value={accountId}
            onChange={(event) => {
              const next = new URLSearchParams(params);
              if (event.target.value === "") {
                next.delete("account");
              } else {
                next.set("account", event.target.value);
              }
              setParams(next, { replace: true });
              // A new account is a new decision: the staff confirmation does
              // not carry over, because it was made about a different plan.
              setPlanFlag(false);
            }}
          >
            <option value="">{t("billing.budgetEnrol.field.accountNone")}</option>
            {accounts.map((account) => (
              // B14 rule 31 — the id is the option's VALUE, which is not
              // rendered text; the LABEL is the number, the name and the address.
              <option key={account.id} value={account.id}>
                {enrolAccountLabel(account, translate)}
              </option>
            ))}
          </select>
          <p className="m-0 font-body text-sm leading-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
            {t("billing.budgetEnrol.field.accountHelp")}
          </p>
        </div>

        {detailQuery.isError && (
          <p className="font-body text-base leading-normal text-accent-700" role="alert">
            {apiErrorText(detailQuery.error, translate)}
          </p>
        )}
        {/* ⚠ PENDING AND ABSENT ARE TWO DIFFERENT SENTENCES, AND A DASH IS
            NEITHER. `G122`'s defect is a screen that drew dashes while it
            loaded and dashes when it failed, so nothing on it could say which
            happened — `tsc`, 75 component cases and 165 gates all green over
            fourteen 404s. This screen is outside that gate's scope (it draws no
            `FactList`) and takes its shape anyway. */}
        {accountId !== "" && detailQuery.isPending && (
          <NotHeld>{t("billing.budgetEnrol.absent.loading")}</NotHeld>
        )}

        {detail !== undefined && (
          <dl className="m-0">
            <BandHeading>{t("billing.budgetEnrol.band.whoWhere")}</BandHeading>
            <FactRow label={t("billing.budgetEnrol.row.account")}>
              {/* The HUMAN-FACING number, never the id — and where an account
                  carries none, that absence is said in words rather than
                  falling back to the id (B14 rule 31, DEF-3158's posture). */}
              {detail.account_no ?? <NotHeld>{t("billing.budget.noAccountNo")}</NotHeld>}
              {detail.name !== null && <span className="ml-1">· {detail.name}</span>}
              {detail.customer_no !== null && detail.customer_no !== undefined && (
                <span className="ml-1">· {detail.customer_no}</span>
              )}
            </FactRow>
            <FactRow label={t("billing.budgetEnrol.row.where")}>
              {/* BR-MET-1161 — the address is the PREMISES' and the unit refines
                  it by LABEL. Two served halves, joined for one line, never a
                  second address. */}
              {detail.premise_address ?? detail.premise ?? (
                <NotHeld>{t("billing.budgetEnrol.absent.address")}</NotHeld>
              )}
              {detail.unit_label !== null && <span className="ml-1">· {detail.unit_label}</span>}
            </FactRow>
            <FactRow label={t("billing.budgetEnrol.row.services")}>
              {/* The letters come from the ONE badge map (`ratingShared`), never
                  a third hand-typed service list — an eleventh service that
                  does not appear on screen fails silently, which is the trap
                  `SignupWizard` and `ratingShared` already cost us twice. */}
              {/* `kind` travels because an EMPTY list means something different
                  on a master account (`DEF-CUS-6295`): its services are the
                  BUILDING's (`BR-CUS-1093`), so nothing here says the address
                  has none recorded — never that this account is mis-set-up.
                  REQUIRED and not optional: a prop nothing passes is dead UI
                  (hard-won law 2), and `tsc` named this second call site the
                  moment it became required. */}
              <span className="inline-flex items-center gap-2">
                <AccountServiceChips
                  services={detail.services}
                  kind={detail.kind}
                  t={translate}
                />
                <span>
                  {detail.services
                    .map((code) => t(`rating.service.${code}`, { defaultValue: code }))
                    .join(" · ")}
                </span>
              </span>
            </FactRow>

            <BandHeading>{t("billing.budgetEnrol.band.canLevel")}</BandHeading>
            <FactRow label={t("billing.budgetEnrol.row.plan")}>
              {detail.unit_plan?.name ?? <NotHeld>{t("billing.budgetEnrol.absent.plan")}</NotHeld>}
              {/* OQ-237 — the drawing's *"offers budget billing"* half. The flag
                  is on the rate PLAN and no endpoint publishes it, so the
                  screen says so in its own words rather than asserting it. The
                  server's own sentence carries two rule ids and is not shown
                  (B14 rule 31). */}
              <span className="ml-1">
                <NotHeld>{t("billing.budgetEnrol.absent.planFlag")}</NotHeld>
              </span>
            </FactRow>
            <FactRow label={t("billing.budgetEnrol.row.status")}>
              <StatusPill tone={detail.status_behavior_class === "billable" ? "success" : "neutral"}>
                {detail.status_name}
              </StatusPill>
            </FactRow>
            <FactRow label={t("billing.budgetEnrol.row.alreadyLevel")}>
              {eligibility === undefined ? (
                <NotHeld>{t("billing.budgetEnrol.absent.pending")}</NotHeld>
              ) : eligibility.already_enrolled ? (
                t("billing.budgetEnrol.value.alreadyYes")
              ) : (
                t("billing.budgetEnrol.value.alreadyNo")
              )}
            </FactRow>
            <FactRow label={t("billing.budgetEnrol.row.openSince")}>
              {detail.opened_at ?? <NotHeld>{t("billing.budgetEnrol.absent.openSince")}</NotHeld>}
              {openSince !== null && (
                <span className="ml-1">
                  · {t("billing.budgetEnrol.value.months", { count: openSince })}
                </span>
              )}
            </FactRow>

            <BandHeading>{t("billing.budgetEnrol.band.whatChanges")}</BandHeading>
            <FactRow label={t("billing.budgetEnrol.row.balanceNow")}>
              {/* ⚠ A DASH, NEVER `0.00`, WHEN NOBODY COULD ASK. Zero means the
                  customer owes nothing from before; the absence means the books
                  could not be reached. A `0.00` here would tell a clerk that a
                  customer in arrears is square, on the screen where they fix
                  what that customer pays for a year. */}
              {eligibility?.open_balance !== null &&
              eligibility?.open_balance !== undefined &&
              eligibility.open_balance_currency !== null ? (
                <MoneyCell
                  amount={eligibility.open_balance}
                  currency={eligibility.open_balance_currency}
                  locale={props.locale}
                />
              ) : (
                <NotHeld>{t("billing.budget.openBalanceUnknown")}</NotHeld>
              )}
              {/* The drawn `· 34 days`. `aging` is served null with its reason:
                  no module publishes open-invoice due dates. DEF-BIL-5314. */}
              <span className="ml-1">
                <NotHeld>{t("billing.budgetEnrol.absent.aging")}</NotHeld>
              </span>
            </FactRow>
            <FactRow label={t("billing.budgetEnrol.row.autopay")}>
              <StatusPill
                tone={detail.autopay ? "success" : "neutral"}
                // DEF-644's established qualifier: the label is right and would
                // mislead alone, because autopay in this version is a promise
                // recorded and nothing collects on it.
                title={detail.autopay ? t("customers.account.pill.autopayOnWhy") : undefined}
              >
                {detail.autopay
                  ? t("customers.accounts.autopay.on")
                  : t("customers.accounts.autopay.off")}
              </StatusPill>
              {/* The drawn `· card ending 4218`. No instrument is served
                  anywhere behind the boolean. DEF-BIL-5314. */}
              {detail.autopay && (
                <span className="ml-1">
                  <NotHeld>{t("billing.budgetEnrol.absent.autopayMethod")}</NotHeld>
                </span>
              )}
            </FactRow>
            <FactRow label={t("billing.budgetEnrol.row.nextBill")}>
              {/* The drawn `30 Nov 2026 · cycle 09-A — the level starts here`.
                  An account reaches a cycle by walking unit → route → cycle at
                  bill-run time and no read publishes that chain, so there is no
                  date and no cycle to draw. DEF-BIL-5314. */}
              <NotHeld>{t("billing.budgetEnrol.absent.nextBill")}</NotHeld>
            </FactRow>
          </dl>
        )}

        {/* ⚠ THE TWO FACTS A CLERK SAYS OUT LOUD. Not rationale — each one is
            something a customer is told on the phone, and getting either wrong
            is a call back. They are rendered whenever the fact behind them is
            TRUE, never as decoration. */}
        {detail !== undefined && (
          <div className="mt-4 flex flex-col gap-2">
            {eligibility?.open_balance !== null &&
              eligibility?.open_balance !== undefined &&
              eligibility.open_balance !== "0" &&
              Number.parseFloat(eligibility.open_balance) !== 0 && (
                <ConsequenceBox
                  tone="check"
                  tag={t("billing.budgetEnrol.warn.tag")}
                  title={t("billing.budgetEnrol.warn.arrearsTitle")}
                  body={t("billing.budgetEnrol.warn.arrears")}
                  data-consequence="budget-enrol-arrears"
                />
              )}
            {detail.autopay && (
              <ConsequenceBox
                tone="check"
                tag={t("billing.budgetEnrol.warn.tag")}
                title={t("billing.budgetEnrol.warn.autopayTitle")}
                body={t("billing.budgetEnrol.warn.autopay")}
                data-consequence="budget-enrol-autopay"
              />
            )}
          </div>
        )}
      </Panel>

      {/* ── 2 · ELIGIBILITY ──────────────────────────────────────────────── */}
      <Panel as="section">
        <h3>{t("billing.budgetEnrol.group.eligible")}</h3>
        {eligibilityQuery.isError && (
          <p className="font-body text-base leading-normal text-accent-700" role="alert">
            {apiErrorText(eligibilityQuery.error, translate)}
          </p>
        )}
        {eligibility === undefined ? (
          <NotHeld>{t(eligibilityState(accountId, eligibilityQuery.isPending))}</NotHeld>
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b-2 border-b-divider">
                <th className="py-2 pr-4 text-left font-heading text-xs font-extrabold uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
                  {t("billing.budgetEnrol.col.test")}
                </th>
                <th className="py-2 text-right font-heading text-xs font-extrabold uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
                  {t("billing.budgetEnrol.col.thisAccount")}
                </th>
              </tr>
            </thead>
            <tbody>
              {/* TEST ONE — answered, and it refuses BY NAME. */}
              <VerdictRow
                label={t("billing.budgetEnrol.test.history", {
                  required: eligibility.required_months ?? "?",
                })}
                cell={
                  eligibility.required_months === null ? (
                    <NotHeld>{t("billing.budgetEnrol.absent.requiredMonths")}</NotHeld>
                  ) : eligibility.months_of_history >= eligibility.required_months ? (
                    t("billing.budgetEnrol.verdict.historyPasses", {
                      months: eligibility.months_of_history,
                    })
                  ) : (
                    <span className="text-accent-700">
                      {t("billing.budgetEnrol.verdict.historyFails", {
                        months: eligibility.months_of_history,
                      })}
                    </span>
                  )
                }
              />
              {/* TEST TWO — OQ-237. The product cannot answer it, so it ASKS,
                  BEFORE the level below. The drawing's own commentary is why
                  this is a step rather than a validation message: *"A clerk who
                  fails at the last field has already chosen a figure."* */}
              <VerdictRow
                label={t("billing.budgetEnrol.test.plan")}
                cell={
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={planFlag}
                      disabled={blockedReason !== null}
                      onChange={(event) => setPlanFlag(event.target.checked)}
                    />
                    <span className="text-left">{t("billing.budget.planFlagConfirm")}</span>
                  </label>
                }
              />
            </tbody>
          </table>
        )}
      </Panel>

      {/* ── 3 · THE LEVEL ────────────────────────────────────────────────── */}
      <Panel as="section">
        <h3>{t("billing.budgetEnrol.group.level")}</h3>
        {eligibility === undefined ? (
          <NotHeld>{t(eligibilityState(accountId, eligibilityQuery.isPending))}</NotHeld>
        ) : (
          <>
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b-2 border-b-divider">
                  <th className="py-2 pr-4 text-left font-heading text-xs font-extrabold uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]" />
                  <th className="py-2 pr-4 text-right font-heading text-xs font-extrabold uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
                    {t("billing.budgetEnrol.col.basis")}
                  </th>
                  <th className="py-2 text-right font-heading text-xs font-extrabold uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
                    {t("billing.budgetEnrol.col.amount")}
                  </th>
                </tr>
              </thead>
              <tbody>
                <VerdictRow
                  label={t("billing.budgetEnrol.level.trailing")}
                  basis={t("billing.budgetEnrol.level.bills", { count: eligibility.bills_read })}
                  // The drawn `$936.00`. The server serves the twelve actuals
                  // and no sum; this file does no money arithmetic. DEF-BIL-5313.
                  cell={<NotHeld>{t("billing.budgetEnrol.absent.trailingTotal")}</NotHeld>}
                />
                <VerdictRow
                  label={<strong>{t("billing.budgetEnrol.level.computed")}</strong>}
                  basis={
                    eligibility.required_months === null
                      ? null
                      : `÷ ${eligibility.required_months}`
                  }
                  cell={
                    willPay !== null && willPayCurrency !== null ? (
                      <strong>
                        <MoneyCell
                          amount={willPay}
                          currency={willPayCurrency}
                          locale={props.locale}
                        />
                      </strong>
                    ) : (
                      <NotHeld>
                        {eligibility.computed_level_unavailable === null
                          ? t("billing.budget.noLevel")
                          : t("billing.budgetEnrol.absent.noLevel")}
                      </NotHeld>
                    )
                  }
                />
                <VerdictRow
                  label={t("billing.budgetEnrol.level.band")}
                  basis={boundPct === null ? null : `± ${boundPct}%`}
                  // The drawn `$54.60 – $101.40`. `budget.override_bounds` has
                  // no caller outside `validate_override` and no payload
                  // carries the range. DEF-BIL-5312.
                  cell={<NotHeld>{t("billing.budgetEnrol.absent.band")}</NotHeld>}
                />
              </tbody>
            </table>

            <div className="mt-4 flex flex-row items-start gap-8 max-sm:flex-col max-sm:gap-4">
              <div className="flex max-w-[280px] flex-col gap-1">
                <label
                  className="font-heading text-sm font-semibold text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]"
                  htmlFor="bil-enrol-override"
                >
                  {t("billing.budgetEnrol.field.override")}
                </label>
                {/* DRAWN, RENDERED AND REFUSED WITH ITS REASON — the
                    blueprint's own doctrine one page earlier. The enrolment
                    request carries no override and an override is a second
                    write needing a REASON this drawing has no field for, so a
                    working box here would promise a figure nothing sends. */}
                <input
                  id="bil-enrol-override"
                  className="input"
                  disabled
                  value=""
                  readOnly
                  title={t("billing.budgetEnrol.field.overrideWhy")}
                  placeholder={t("billing.budgetEnrol.field.overridePlaceholder")}
                />
                <p className="m-0 font-body text-sm leading-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
                  {t("billing.budgetEnrol.field.overrideWhy")}
                </p>
              </div>
              <div className="flex flex-col gap-1">
                <span className="font-heading text-sm font-semibold text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
                  {t("billing.budgetEnrol.field.willPay")}
                </span>
                <span className="font-heading text-h5 font-extrabold leading-body [font-feature-settings:'tnum']">
                  {willPay !== null && willPayCurrency !== null ? (
                    <MoneyCell
                      amount={willPay}
                      currency={willPayCurrency}
                      locale={props.locale}
                    />
                  ) : (
                    <NotHeld>{t("billing.budget.noLevel")}</NotHeld>
                  )}
                </span>
              </div>
            </div>
          </>
        )}
      </Panel>

      {/* ── 4 · WHAT HAPPENS NEXT ────────────────────────────────────────── */}
      <Panel as="section">
        <h3>{t("billing.budgetEnrol.group.next")}</h3>
        <dl className="m-0">
          <FactRow label={t("billing.budgetEnrol.next.everyBill")}>
            {t("billing.budgetEnrol.next.everyBillValue")}
          </FactRow>
          <FactRow label={t("billing.budgetEnrol.next.yearly")}>
            {t("billing.budgetEnrol.next.yearlyValue")}
          </FactRow>
          <FactRow label={t("billing.budgetEnrol.next.unpaid")}>
            {/* PO 2026-08-11, verbatim *"nodrop we chase for payments until
                write off"* — BR-BIL-017's two-missed-payments drop-off is
                SUPERSEDED. Nothing drops anybody, and a clerk enrolling
                somebody should know it before they do it. */}
            {t("billing.budgetEnrol.next.unpaidValue")}
          </FactRow>
        </dl>
      </Panel>

      {/* ── FOOTER ───────────────────────────────────────────────────────── */}
      <div className="mt-4 flex flex-row items-center justify-between gap-3 border-t-2 border-t-accent pt-4 max-sm:flex-col max-sm:items-start">
        <p className="m-0 max-w-measure font-body text-base leading-prose text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
          {t("billing.budgetEnrol.footer")}
        </p>
        <div className="flex items-center gap-2">
          {/* ⚠ **IT SAYS `Cancel` NOW, NOT `Back` (PO 2026-09-19).** It is the
              page's only exit since the head's duplicate went, and it is the
              word the Product Owner asked to find at the bottom. `Back` was
              also the wrong word for what it does: nothing on this page has a
              previous step to go back TO, and `Back` is the step-back word
              everywhere else in the product (`wizard.back`). The key is the
              one the head was already using, so all eleven catalogues
              translate it and no new copy is minted.
              ⚠ `billing.budgetEnrol.back` now has no call site. It is LEFT in
              the catalogues rather than deleted from eleven files in a defect
              fix — an unused key costs nothing and a mass catalogue edit is a
              shared-file rewrite. Recorded so the next reader knows it is
              orphaned rather than missed. */}
          <Button variant="secondary" onClick={() => navigate(tenantPath(BUDGET_TAB_ROUTE))}>
            {t("billing.budgetEnrol.cancel")}
          </Button>
          {/* THE AMOUNT IS IN THE LABEL, as drawn — and it is the COMPUTED
              figure, which is what `enroll` will really write. A button naming
              a number the request does not carry is the shape of a customer
              paying something nobody agreed. */}
          <Button
            variant="primary"
            disabled={!canEnrol}
            title={blockedReason ?? undefined}
            onClick={() => void enrol()}
          >
            {willPay !== null && willPayCurrency !== null
              ? t("billing.budgetEnrol.commit", {
                  // CLAUDE.md rule 2 — DISPLAY 2, through the one formatter, so
                  // the label and the figure two panels up cannot disagree.
                  amount: formatMoney(willPay, willPayCurrency, props.locale),
                })
              : t("billing.budgetEnrol.commitNoAmount")}
          </Button>
        </div>
      </div>
      {eligibility?.already_enrolled === true && (
        <p className="mt-2 font-body text-base leading-normal text-accent-700" role="alert">
          {t("billing.budget.alreadyEnrolled")}
        </p>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-018 · 05-prototype/04 Billing, As Built.pdf §05 entry 25.1 (p122-p124, read as images at scale 2, B14 rule 42) · 04-docs/05-modules/07-billing/conformance/CR-103-BRC03-budget-bills-maintenance.md §25.1 · 14-ui-conventions.md rules 21, 31, 32, 33, 36, 38, 40, 41, 42
// generated: 2026-09-15 by the §05 entry 25.1 build lane
// checklist: A✔ B✔ C✔ D✔(GET /accounts, GET /accounts/{id}, GET /budget-billing, GET /budget-billing/{id}/eligibility, POST /budget-billing/enrollments — all served and mounted) E✔(routed at /:tenant/billing/budget/enrol and linked from the Budget Bills tab) F✔ G✔ H=n/a
// gates: tsc · vitest src/features/billing/budgetEnrolPage.dom.test.tsx · G31 (this file is on src/styles/route-b-migrated.txt) · G15 i18n-parity
// exceptions: E3 [B14 rule 38] the drawing's four RATIONALE captions are not rendered — rule 33 gives rationale zero words on screen; recorded in the conformance file · E3 [rule 38] four headings trimmed to rule 33's three-word cap (CAN IT BE LEVELLED, WHAT CHANGES FOR THEM, IS THIS ACCOUNT ELIGIBLE, TWO OF THOSE NINE CHANGE WHAT YOU TELL THE CUSTOMER) · E3 the trailing-twelve TOTAL and the override BAND RANGE are stated absent, not computed here: this file does no money arithmetic and both figures are the server's (DEF-BIL-5313, DEF-BIL-5312) · E3 the override input is drawn and greyed with its reason — the enrolment request carries no override and an override needs a REASON this drawing has no field for (DEF-BIL-5315) · E3 the ageing, the autopay instrument and the next bill + cycle are stated absent — no endpoint serves any of the three (DEF-BIL-5314) · E3 the server's `eligible_unavailable` sentence is NOT rendered: it carries two rule ids and B14 rule 31 forbids them in clerk-facing copy (DEF-BIL-5316) · E3 the autopay warning is worded to what this version does — autopay is a promise recorded, never a charge (DEF-644)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
