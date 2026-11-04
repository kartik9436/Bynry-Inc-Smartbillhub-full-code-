// ── Trace ──────────────────────────────────────────────
// Screens:  S21 · ACC-02 tabs 2–5 (Bills · Payments · Credits · Payment plan)
// Drawing:  04-docs/05-modules/03-customers/blueprint/02-account-detail.md
//           lines 523–860 — ACC-T02 · ACC-T03 · ACC-T04 · ACC-T05
// Rules:    B14 rule 41 (the product matches the drawing) · B14 rule 33 (on-screen
//           text is capped by what it is for; RATIONALE is zero words on screen) ·
//           B14 rule 36 (build from the kit) · B14 rule 31 (no database id on screen)
// Checks:   10-scripts/render-checks/acc02-tab-conformance.mjs, TAB=bills|payments|
//           credits|plan, against 10-scripts/render-checks/drawn/acc02-<tab>.json
// ───────────────────────────────────────────────────────
//
// THE FOUR MONEY TABS OF THE ACCOUNT SCREEN, DRAWN AS THE BLUEPRINT DRAWS THEM.
//
// ⚠ **WHY THESE FOUR MOVED OUT OF `accountDetailTabs.tsx`.** Three lanes are
// building this screen at once by the PO's own model, and that file already
// holds Meters, Usage, Adjustments, Notes and Audit — every one of them another
// lane's. A shared file edited by three lanes is hard-won law 11 mechanism two
// waiting to happen (a whole-file blob silently reverting a sibling), and the
// cheapest defence is that each lane writes in a file of its own.
//
// ⚠ **EVERY GROUP CARRIES `data-overview-group`, AND THE TAB CARRIES
// `data-account-overview`.** jsdom computes no layout, so no vitest case in this
// repository can say a screen LOOKS like its drawing (hard-won law 6). The
// browser census selects on exactly those two hooks; a group without one is
// invisible to it, which reads as a clean pass rather than as a gap.
//
// ⚠ **THE RATIONALE SENTENCES THAT USED TO BE HERE ARE NOW COMMENTS, AND THAT
// IS B14 RULE 33 BEING OBEYED RATHER THAN TIDIED.** The rule: *RATIONALE — why
// the product works this way, why a control is absent — is ZERO WORDS ON
// SCREEN*. The Product Owner pasted three of them back out of the running
// product on 2026-09-13, so this is enforcement by example and not a reading:
//
//   · *"Columns this tab cannot show"* + *"The design also shows the usage
//     behind each bill on this tab…"* — the bills tab. What it was explaining:
//     the blueprint's own ANNOTATION panel beside the drawing says the design
//     shows usage per bill; usage is summed from meter reads and no module
//     publishes that summary, so the drawn bills table has eight columns and
//     none of them is usage. Nothing is missing from the screen — the sentence
//     was the blueprint talking about the product, printed onto the product.
//   · *"The design shows a held deposit among the payments…"* — the payments
//     tab. `accounts.deposit_on_file` is written by nothing (`DEF-177`) and
//     whether a held deposit IS a payment row is an open modelling question
//     (B18 §5.2.2). So no deposit row is invented; that is the whole of it.
//   · the bills list's past-due paragraph — past-due needs each open bill's due
//     date against the utility's own clock, and billing publishes neither per
//     account, so `past_due` is served null and the status pill says `Issued`.
//
// None of the three changed what a clerk can DO. Each was an explanation, and
// an explanation belongs in the code and in the register.

import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getNotices, getPaymentPlans } from "@/api/endpoints";
import type {
  AccountDetail,
  PaymentPlanInstallmentView,
  PaymentPlanRow,
} from "@/api/endpoints";
import { ButtonLink } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { AccountBillsTab } from "@/features/billing/BillsListPage";
import { billDetailPath } from "@/features/billing/billingShared";
import { Fact, FactList } from "@/features/metering/meteringShared";
import { ArrivesWith } from "@/features/tenancy/settingsShared";
import { PaymentsTable } from "@/features/payments/PaymentsPage";
import { accountPlanKey } from "@/features/payments/paymentsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import type { AccountAgeingCells } from "./accountsListCells";
import { accountCreditNotesKey, getAccountCreditNotes } from "./creditNoteEndpoints";
import { Dash, NotRecorded } from "./customersShared";
import { blockedSentence } from "./PaymentPlanSchedule";

/** Quieter than data, never blank — the same weight `Dash` renders at. */
const MUTED = "text-neutral-600";

// ── The column the drawing runs these groups down ──────────────────────────

/**
 * The tab body, hooked for the browser census.
 *
 * ONE column, not the Overview's two: the blueprint draws every one of these
 * four tabs as a single full-width stack, because a table wants the width. The
 * census reads `root.children` as columns and a group's `colIndex` as which one
 * it sits in, so a single child div is the whole of "the left column".
 */
export function AccountTabGroups(props: { children: ReactNode }) {
  return (
    <div data-account-overview="" className="mt-4 grid grid-cols-1 items-start gap-4">
      <div className="flex min-w-0 flex-col gap-4">{props.children}</div>
    </div>
  );
}

// ── Tab 2 · Bills — ACC-T02 ────────────────────────────────────────────────

/**
 * ACC-T02: one table, nine columns, newest issue date first.
 *
 * The columns are billing's own (`billsTableConfig(…, "account")`) and match the
 * drawing already — Bill # · Cycle · Issue date · Due date · Subtotal · Tax ·
 * Total · Status · the row actions. It is billing's table and not a copy
 * (BR-CUS-034 forbids a customers read-model of a bill), so the draft-number
 * rule and the derived past-due state have one implementation.
 *
 * `All bills →` moves into the heading row, where the drawing puts a group's
 * control and where the Overview's HISTORY group already puts this same link.
 */
export function AccountBillsGroup(props: {
  accountId: string;
  client?: ApiClient;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  return (
    <AccountTabGroups>
      <Panel
        as="section"
        tone="group"
        data-overview-group="bills"
        title={props.t("customers.account.tab.bills")}
      >
        <AccountBillsTab
          accountId={props.accountId}
          client={props.client}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      </Panel>
    </AccountTabGroups>
  );
}

// ── Tab 3 · Payments — ACC-T03 ─────────────────────────────────────────────

/**
 * ACC-T03: expandable rows, each opening onto what the money met.
 *
 * The columns are the payments module's own S33 set, scoped by `f.account_id`.
 * **`Account` and `Customer` are hidden here and that is the drawing**: the
 * account is the page you are standing on, and its number is already in the
 * header three lines above. `paymentsTableConfig` takes a scope for it, exactly
 * as `billsTableConfig` has since the Bills tab landed.
 */
export function AccountPaymentsGroup(props: {
  accountId: string;
  client?: ApiClient;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  state: Parameters<typeof PaymentsTable>[0]["state"];
  onStateChange: Parameters<typeof PaymentsTable>[0]["onStateChange"];
  emptyCtaReason: string | null;
  onEmptyCta: () => void;
}) {
  return (
    <AccountTabGroups>
      <Panel
        as="section"
        tone="group"
        data-overview-group="payments"
        title={props.t("customers.account.tab.payments")}
      >
        <PaymentsTable
          accountId={props.accountId}
          client={props.client}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          state={props.state}
          onStateChange={props.onStateChange}
          emptyCtaReason={props.emptyCtaReason}
          onEmptyCta={props.onEmptyCta}
        />
        {/* ⚠ **THE FACT STAYS AND THE EXPLANATION GOES (B14 rule 33, PO
            2026-09-13).** This said *"The design shows a held deposit among the
            payments. Nothing writes the deposit register yet, and whether a held
            deposit belongs in this list has not been decided…"* — 39 words the
            Product Owner pasted back out of the running product. A stated
            absence is a FACT and gets six words; the reason for it is RATIONALE
            and gets zero. It now reads *Deposits are not listed here.* over
            *The deposit shows on Overview.*, which is the one thing a clerk can
            act on — where to go and look.

            **The reason, which is what belongs here.** r10 and the blueprint
            both draw a held DEPOSIT row among the payments. Nothing in this
            product writes `accounts.deposit_on_file` (`DEF-177` — the register
            and the books can only disagree once a deposit is taken), and B18
            §5.2.2 flags the shape itself as *"a modelling claim to confirm"*:
            whether a held deposit IS a payment row is a decision, not a
            rendering. So the tab lists payments and invents no row. */}
        <ArrivesWith
          title={props.t("customers.account.arrives.depositRowTitle")}
          message={props.t("customers.account.arrives.depositRow")}
          tracks="DEF-177"
        />
      </Panel>
    </AccountTabGroups>
  );
}

// ── Tab 4 · Credits — ACC-T04 ──────────────────────────────────────────────

/**
 * ACC-T04: every credit note on this account, each beside the bill it corrected.
 *
 * ⚠ **THE COLUMN HEADINGS ARE DRAWN EVEN WHEN THERE IS NOTHING UNDER THEM**,
 * which is this repository's own pattern for a list whose rows have not arrived
 * (the Adjustments and Documents tabs do the same). The shared `DataTable`
 * REPLACES its table with an empty block, so a screen using it cannot show a
 * clerk what the list will hold — and the browser census, which reads the drawn
 * columns off the rendered group, would be measuring a table that is not there.
 *
 * ⚠ **`STATUS` IS DRAWN AND NOTHING HOLDS IT.** `billing.CreditNote` has
 * `credit_note_no`, `amount`, `currency`, `reason`, `issued_at` and the original
 * invoice — and no status column anywhere. The drawing's `Applied` could be
 * derived from "has a bill", but that would be this screen INVENTING what
 * applied means, in a module that does not own the word. The cell states the
 * absence instead (`DEF-CUS-5149`).
 */
export function AccountCreditsGroup(props: {
  accountId: string;
  client?: ApiClient;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** `DEF-PAY-10707` — the account's held credit, drawn ABOVE the credit
   *  notes in the same column (`AccountHeldCreditGroup`). */
  heldCredit?: ReactNode;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const query = useQuery({
    queryKey: accountCreditNotesKey(props.accountId),
    queryFn: () => getAccountCreditNotes(props.accountId, props.client ?? api),
    retry: false,
    enabled: props.accountId !== "",
  });
  const rows = query.data?.credit_notes ?? [];
  // ⚠ **THE TWO LONG SENTENCES ARE REPLACED, NOT REWORDED IN PLACE.** B14 rule
  // 33 caps a FACT at six words; `customers.account.credits.empty` is eight
  // ("This account has never been given a credit.") and `…credits.failed` is
  // seven. Both keys stay in the catalogues — another screen may still hold
  // them — and this tab reads the short pair instead.
  const emptyWord = query.isPending
    ? t("customers.account.credits.loading")
    : query.data === undefined
      ? t("customers.account.credits.unreadable")
      : t("customers.account.credits.none");
  return (
    <AccountTabGroups>
      {props.heldCredit}
      <Panel
        as="section"
        tone="group"
        data-overview-group="credits"
        title={t("customers.account.tab.credits")}
      >
        <div className="overflow-x-auto">
          <PlainTable>
            <thead>
              <tr>
                {/* The drawn order: number, date, reason, the bill it corrected,
                    the money, the state. The three that already have words in
                    billing's own catalogue reuse them rather than minting a
                    second name for one concept (B14 rule 34's reasoning). */}
                {/* ⚠ **`Credit note #` AND NOT BILLING'S `Credit note`.** The
                    drawing heads this column with the `#`, exactly as `Bill #`,
                    `Payment #` and `Plan #` do everywhere else in this product —
                    the column holds a NUMBER, and the three that already say so
                    are why a clerk reads it that way. S28's bill-detail panel
                    keeps its own word; changing a key two screens share to fix
                    one of them is how a shared string starts drifting. */}
                <th>{t("customers.account.credits.col.creditNoteNo")}</th>
                <th>{t("billing.bill.col.issued")}</th>
                <th>{t("billing.bill.col.reason")}</th>
                <th>{t("customers.account.credits.col.againstBill")}</th>
                <th>{t("billing.bill.col.amount")}</th>
                <th>{t("billing.bills.col.status")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className={MUTED}>
                    {emptyWord}
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {/* rule 31: the number, or the fact that there is none —
                          never the row's id. A historic note has no number and
                          CS-37 does not back-fill one. */}
                      {row.credit_note_no ?? <Dash>{t("billing.bill.creditNoteNoNumber")}</Dash>}
                    </td>
                    <td>
                      {row.issued_at !== null ? (
                        <DateCell
                          value={row.issued_at}
                          timeZone={props.timeZone}
                          dateFormat={props.dateFormat}
                        />
                      ) : (
                        <Dash />
                      )}
                    </td>
                    <td>{row.reason ?? <Dash />}</td>
                    <td>
                      {row.invoice_id !== null && row.invoice_no !== null ? (
                        <InlineLinkTo to={tenantPath(billDetailPath(row.invoice_id))}>
                          {row.invoice_no}
                        </InlineLinkTo>
                      ) : (
                        <Dash>{t("customers.account.credits.noBill")}</Dash>
                      )}
                    </td>
                    <td className="tabular-nums">
                      <MoneyCell amount={row.amount} currency={row.currency} />
                    </td>
                    <td>
                      <NotRecorded
                        label={t("customers.account.credits.statusAbsent")}
                        why={t("customers.account.credits.statusWhy")}
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </PlainTable>
        </div>
        {query.data?.truncated === true && (
          <p className={`m-0 mt-2 text-sm ${MUTED}`}>
            {t("customers.account.credits.truncated", { count: query.data.count })}
          </p>
        )}
      </Panel>
    </AccountTabGroups>
  );
}

// ── Tab 5 · Payment plan — ACC-T05 ─────────────────────────────────────────
//
// ⚠ **THE ADDRESS IS `?tab=plan`, NEVER `?tab=paymentplan`** — the blueprint
// records that a link built by guessing from the label lands on Overview.
//
// Three drawn groups, and all three render whatever the account holds:
//   1 · what is running now, with the three arrears facts a clerk weighs before
//       agreeing a plan, and the one control that opens the wizard;
//   2 · every earlier plan on this account;
//   3 · how the selected plan ran, instalment by instalment.

/** `4 × $321.00` — the drawn INSTALMENTS cell, off the plan's own rows. */
function instalmentShape(plan: PaymentPlanRow, t: Translator): ReactNode {
  const first = plan.installments[0];
  if (first === undefined) {
    return <Dash />;
  }
  return t("customers.account.plan.col.shape", {
    n: plan.installment_count,
    amount: formatMoney(first.amount, first.currency ?? plan.currency),
  });
}

/** `Completed 03/08/2026` — the drawn OUTCOME cell. The status word is the
 *  server's (`proposed · agreement_sent · active · closed`); there is no `void`
 *  and no `defaulted`, so no screen may offer either. */
function planOutcome(plan: PaymentPlanRow, t: Translator): string {
  const word = t(`customers.account.plan.status.${plan.status}`, {
    defaultValue: t("customers.account.plan.status.unknown"),
  });
  return plan.closed_on === null
    ? word
    : t("customers.account.plan.outcomeOn", { word, on: plan.closed_on });
}

function InstalmentState(props: { row: PaymentPlanInstallmentView; t: Translator }) {
  const { row, t } = props;
  const unpaid = row.paid_posted_on === null || row.paid_posted_on === undefined;
  // THREE states, not two. `on_time` is `null` until a payment meets the row —
  // never `false`, which would read as late on a row nobody has paid yet.
  return (
    <StatusPill tone={unpaid ? "neutral" : row.on_time === false ? "warning" : "success"}>
      {unpaid
        ? t("customers.account.plan.state.outstanding")
        : row.on_time === false
          ? t("customers.account.plan.state.late")
          : t("customers.account.plan.state.met")}
    </StatusPill>
  );
}

/**
 * The `Dunning so far` read — notices SENT on this account (`DEF-PAY-10655`).
 *
 * `GET /notices` serves sends AND skips together, on purpose (J4 step 2): the
 * ladder writes a skip on every pass it does not step, and the past-due
 * reminder one per channel it could not use (`DEF-PAY-10651`). Counting them
 * all told a clerk "3 notices issued" for an account sent ONE letter.
 */
export function dunningNoticesParams(accountId: string): {
  filters: Record<string, string>;
  per: number;
} {
  return { filters: { account_id: accountId, outcome: "sent" }, per: 50 };
}

export function AccountPlanGroups(props: {
  /** ⚠ **THE AGEING KEYS ARE SERVED AND `AccountDetail` DOES NOT DECLARE THEM**
   *  — `accountsListCells.tsx` types them beside the cell that draws them and
   *  its own note records that `endpoints.ts` belongs to another lane. The
   *  intersection is assignable from `AccountDetail`, so nothing casts. */
  detail: AccountDetail & Partial<AccountAgeingCells>;
  client?: ApiClient;
  t: Translator;
}) {
  const { t, detail } = props;
  const tenantPath = useTenantPath();
  const query = useQuery({
    queryKey: accountPlanKey(detail.id),
    queryFn: () => getPaymentPlans(detail.id, props.client ?? api),
    retry: false,
    enabled: detail.id !== "",
  });
  /**
   * ⚠ **`GET /notices` WAS SERVED AND NOBODY CALLED IT.** `notice_history_for`
   * has published the collection ladder's record since 2026-08-16 and this file
   * is its first reader on the account screen — a defect rather than a gap. It
   * answers the drawing's `Dunning so far`. The DISCONNECT half of the drawn
   * sentence is not drawn: `GET /disconnects` ignores `f.account_id` (it
   * answers the whole worklist), so there is no per-account case read to show.
   */
  const notices = useQuery({
    queryKey: ["accounts", "notices", detail.id, "sent"],
    queryFn: () => getNotices(dunningNoticesParams(detail.id), props.client ?? api),
    retry: false,
    enabled: detail.id !== "",
  });

  const context = query.data;
  const live = context?.live_plan ?? null;
  const plans = context?.plans ?? [];
  // The plan whose instalments the third group draws: the live one, else the
  // most recent. The drawing shows a CLOSED plan opened on an account with no
  // live plan, which is exactly this fallback.
  const shown = live ?? plans[0] ?? null;
  const unreadable = context?.plans_unavailable ?? null;

  return (
    <AccountTabGroups>
      {/* ── 1 · What is running now ─────────────────────────────────────── */}
      <Panel
        as="section"
        tone="group"
        data-overview-group="plan-now"
        title={
          live === null
            ? t("customers.account.plan.noneRunning")
            : t("customers.account.plan.oneRunning")
        }
        trailing={
          <span className={`text-sm ${MUTED}`}>
            {live === null
              ? t("customers.account.plan.noneLive")
              : t("customers.account.plan.paidOfTotal", {
                  paid: formatMoney(live.paid_to_date, live.currency),
                  total: formatMoney(live.spread, live.currency),
                })}
          </span>
        }
      >
        <FactList>
          <Fact label={t("customers.account.plan.field.arrears")}>
            {context?.balance !== null && context?.balance !== undefined ? (
              <MoneyCell amount={context.balance} currency={context.currency ?? "USD"} />
            ) : (
              <Dash />
            )}
          </Fact>
          {/* The account's own ageing, not a second count of it: the header tile
              and the accounts list both read `ageing_days_past_due`, and a
              screen that recomputed "oldest unpaid" here would be a second
              definition of how overdue this customer is. */}
          <Fact label={t("customers.account.plan.field.oldestUnpaid")}>
            {detail.ageing_days_past_due !== null && detail.ageing_days_past_due !== undefined ? (
              t("customers.account.plan.daysValue", { count: detail.ageing_days_past_due })
            ) : (
              <NotRecorded
                label={t("customers.account.plan.oldestUnpaidAbsent")}
                why={t("customers.account.plan.oldestUnpaidWhy")}
                ruleRef="BR-CUS-016"
              />
            )}
          </Fact>
          <Fact label={t("customers.account.plan.field.dunning")}>
            {notices.isPending ? (
              <Dash />
            ) : notices.data === undefined || notices.data.available !== true ? (
              <NotRecorded
                label={t("customers.account.plan.dunningAbsent")}
                why={t("customers.account.plan.dunningWhy")}
              />
            ) : (
              /* ⚠ **A COUNT OF ZERO GETS A WORD, NOT A DIGIT.** `0 notices
                 issued` is true and reads as a gap in the data rather than as
                 a fact about this customer — nobody has chased them. */
              notices.data.count === 0 ? (
                t("customers.account.plan.noticesNone")
              ) : (
                t("customers.account.plan.noticesValue", { count: notices.data.count })
              )
            )}
          </Fact>
        </FactList>
        {/* The one control the drawing puts on this tab. It NAVIGATES, so it is
            a link that renders as a button — middle-click and "open in new tab"
            keep working. Disabled with its reason when the server says so
            (BR-SHL-025), never silently missing. */}
        <p className="m-0 mt-3">
          {context?.can_propose === false ? (
            <ButtonLink
              variant="primary"
              to={tenantPath(`/accounts/${detail.id}/payment-plan`)}
              aria-disabled="true"
              title={blockedSentence(context, t) ?? undefined}
            >
              {t("customers.account.plan.propose")}
            </ButtonLink>
          ) : (
            <ButtonLink variant="primary" to={tenantPath(`/accounts/${detail.id}/payment-plan`)}>
              {t("customers.account.plan.propose")}
            </ButtonLink>
          )}
        </p>
      </Panel>

      {/* ── 2 · Earlier plans on this account ───────────────────────────── */}
      <Panel
        as="section"
        tone="group"
        data-overview-group="plan-history"
        title={t("customers.account.plan.earlier")}
      >
        <div className="overflow-x-auto">
          <PlainTable>
            <thead>
              <tr>
                <th>{t("customers.account.plan.col.planNo")}</th>
                <th>{t("customers.account.plan.col.opened")}</th>
                <th>{t("customers.account.plan.col.spread")}</th>
                <th>{t("customers.account.plan.col.instalments")}</th>
                <th>{t("customers.account.plan.col.outcome")}</th>
              </tr>
            </thead>
            <tbody>
              {plans.length === 0 ? (
                <tr>
                  <td colSpan={5} className={MUTED}>
                    {/* ⚠ THREE DIFFERENT FACTS AND NOT ONE (DEF-127): still
                        reading · could not be read · never agreed a plan. The
                        middle one covers both a failed request and the
                        server's own `plans_unavailable`, because both mean the
                        record could not be opened — which is not the same
                        statement as "this customer has never had a plan". */}
                    {query.isPending
                      ? t("customers.account.plan.loading")
                      : query.data === undefined || unreadable !== null
                        ? t("customers.account.plan.unreadable")
                        : t("customers.account.plan.none")}
                  </td>
                </tr>
              ) : (
                plans.map((plan) => (
                  <tr key={plan.id}>
                    {/* ⚠ **A PLAN HAS NO NUMBER AND B14 RULE 31 FORBIDS THE ID.**
                        The drawing reads `PP-2512-0004`; `PaymentPlan` carries no
                        such column, so the cell says so rather than printing a
                        uuid at a clerk (`DEF-CUS-5150`). */}
                    <td>
                      <NotRecorded
                        label={t("customers.account.plan.planNoAbsent")}
                        why={t("customers.account.plan.planNoWhy")}
                        ruleRef="BR-CUS-044"
                      />
                    </td>
                    <td>{plan.proposed_on ?? <Dash />}</td>
                    <td className="tabular-nums">
                      <MoneyCell amount={plan.spread} currency={plan.currency} />
                    </td>
                    <td>{instalmentShape(plan, t)}</td>
                    <td>{planOutcome(plan, t)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </PlainTable>
        </div>
      </Panel>

      {/* ── 3 · How that plan ran ───────────────────────────────────────── */}
      <Panel
        as="section"
        tone="group"
        data-overview-group="plan-instalments"
        title={t("customers.account.plan.howItRan")}
      >
        {/* PO 2026-08-11 (OQ-138), carried wherever a plan is drawn: the plan
            spreads the ARREARS and this month's bill is still due and still
            chased. Believing otherwise IS DEF-061. */}
        {shown?.current_bill_still_due === true && (
          <p className={`m-0 mb-3 text-base ${MUTED}`}>
            {t("customers.account.plan.currentBillStillDue")}
          </p>
        )}
        <div className="overflow-x-auto">
          <PlainTable>
            <thead>
              <tr>
                <th>{t("customers.account.plan.col.seq")}</th>
                <th>{t("customers.account.plan.col.due")}</th>
                <th>{t("customers.account.plan.col.instalment")}</th>
                <th>{t("customers.account.plan.col.paidOn")}</th>
                <th>{t("customers.account.plan.col.state")}</th>
              </tr>
            </thead>
            <tbody>
              {shown === null || shown.installments.length === 0 ? (
                <tr>
                  <td colSpan={5} className={MUTED}>
                    {t("customers.account.plan.noInstalments")}
                  </td>
                </tr>
              ) : (
                [...shown.installments]
                  .sort((a, b) => a.seq - b.seq)
                  .map((row) => (
                    <tr key={row.seq}>
                      <td>{row.seq}</td>
                      <td>{row.due_date}</td>
                      <td className="tabular-nums">
                        <MoneyCell
                          amount={row.amount}
                          currency={row.currency ?? shown.currency}
                        />
                      </td>
                      <td>{row.paid_posted_on ?? <Dash />}</td>
                      <td>
                        <InstalmentState row={row} t={t} />
                      </td>
                    </tr>
                  ))
              )}
            </tbody>
          </PlainTable>
        </div>
      </Panel>
    </AccountTabGroups>
  );
}
