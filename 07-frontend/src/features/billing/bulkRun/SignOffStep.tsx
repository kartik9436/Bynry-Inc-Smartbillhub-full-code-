// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bill run, step 3 Sign off
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/25…31-signoff-*.png ·
//           inventory.md §5
// Story:    US-BIL-039 (TC-1 … TC-8)
// Plan:     15-bulk-bill-run-build-plan.md A8 · B19 · F14 · F19 (Failed to draft)
// Rules:    changes rows 37, 40, 42 · BR-BIL-058 (five separate confirmations)
//           · CLAUDE.md rules 2 (money shows 2 decimals) and 3 (usage with its
//           unit) · B14 rules 21, 32, 33, 43, 44
// Defects:  DEF-BIL-8220 (the sign-off summary — closed here)
// ───────────────────────────────────────────────────────
/**
 * SIGN OFF — WHAT THE DRAFTS ADD UP TO, WHAT IS NOT IN THE RUN, AND THE FIVE
 * CONFIRMATIONS.
 *
 * Every figure is SERVED by `GET /billing/runs/{id}/sign-off-summary`
 * (DEF-BIL-8220, changes row 37): the run summary; who is billed — accounts
 * regular and master, units on their own account and through a master, each
 * adding back to Scope's figure; usage and charges per service with the usage
 * and base split, taxes, fees and credits; payments and balances with how the
 * amount due will be paid; by customer type; and the waived bases. A section
 * whose figures do not add back says so — the server computes `reconciles`,
 * the screen never re-adds money. A figure the server cannot state is `null`
 * and shows as a dash, never as a zero.
 */
import type { ReactNode } from "react";

import type { CheckSummary, SignOffSummary } from "@/api/bulkRunEndpoints";
import type { Translator } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";
import type { BillRunBreakRow } from "@/features/billing/billRunEndpoints";
import { Button } from "@/components/Button";
import { StatusPill } from "@/components/StatusPill";

import {
  CollapsiblePanel,
  FactCards,
  PanelAside,
  RUN_TABLE,
  ServiceLabel,
  SidePanel,
  TableScroll,
  count,
  day,
  money,
} from "./bulkRunShared";
import type { FactCardItem, RunFormat } from "./bulkRunShared";
import { TAGS, fixScreenOf } from "./bulkRunTaxonomy";
import type { NotInRunFilter } from "./NotInRunList";

export const CONFIRMATIONS = ["compliance", "email_mandate", "sms_mandate", "autopay_mandate", "final"] as const;
export type Confirmation = (typeof CONFIRMATIONS)[number];

/** The tag a break's reason belongs to, for its name and where it is fixed. */
export function breakTag(reason: string): string | null {
  return TAGS.find((tag) => tag.codes.includes(reason))?.id ?? null;
}

function curOf(summary: SignOffSummary, fmt: RunFormat): RunFormat {
  return { ...fmt, currency: summary.currency ?? fmt.currency };
}

/** The line a section shows when its served figures do not add back. */
function NoReconcile(props: { reconciles: boolean; name: string; t: Translator }) {
  if (props.reconciles) return null;
  return (
    <p className="m-0 mt-2 text-base font-semibold text-danger-700" role="alert" data-no-reconcile={props.name}>
      {props.t("billing.bulkRun.signOff.noReconcile")}
    </p>
  );
}

export function RunSummaryPanel(props: { summary: SignOffSummary | null; dueDate: string | null; fmt: RunFormat }) {
  const { summary, fmt } = props;
  const { t } = fmt;
  const cur = summary === null ? fmt : curOf(summary, fmt);
  const run = summary?.run_summary ?? null;
  const items: FactCardItem[] = [
    {
      id: "bills",
      label: t("billing.bulkRun.signOff.bills"),
      value: count(run?.bills ?? null),
      note: run === null ? undefined : t("billing.bulkRun.signOff.ofAccounts", { accounts: count(run.accounts_to_bill) }),
    },
    { id: "charges", label: t("billing.bulkRun.signOff.charges"), value: run === null ? "—" : money(run.this_run_charges, cur) },
    // DEF-BIL-8682 — the PAYMENTS applied, as money, with how many beneath
    // (D1 25: "$31,902.40 · 2,118 payments"). Where the server has no split
    // the merged figure stays, with its accounts. Shown, never recomputed.
    paymentsTile(summary, cur, t),
    {
      id: "due",
      label: t("billing.bulkRun.signOff.amountDue"),
      value: money(run?.amount_due ?? null, cur),
      note: props.dueDate === null ? undefined : t("billing.bulkRun.signOff.dueOn", { due: day(props.dueDate, fmt) }),
    },
  ];
  return (
    <Panel
      as="section"
      title={t("billing.bulkRun.signOff.runSummary")}
      aria-label={t("billing.bulkRun.signOff.runSummary")}
      trailing={<PanelAside>{t("billing.bulkRun.signOff.draftsAside")}</PanelAside>}
      data-run-panel-section="run-summary"
    >
      <div className="mt-3">
        <FactCards name="run-summary" items={items} />
      </div>
    </Panel>
  );
}

function SeeLink(props: { onPress: () => void; t: Translator; name: string }) {
  return (
    <button
      type="button"
      className="cursor-pointer border-0 bg-transparent p-0 font-semibold text-accent-700 underline"
      onClick={props.onPress}
      data-see={props.name}
    >
      {props.t("billing.bulkRun.see")}
    </button>
  );
}

function Row(props: { label: ReactNode; value: ReactNode; see?: ReactNode; total?: boolean; indent?: boolean; name?: string }) {
  return (
    <tr {...(props.total === true ? { "data-total": "" } : {})} {...(props.name === undefined ? {} : { "data-who-row": props.name })}>
      <th scope="row" className={props.indent === true ? "pl-6" : undefined}>
        {props.label}
      </th>
      <td data-num="">{props.value}</td>
      <td>{props.see}</td>
    </tr>
  );
}

export function WhoIsBilled(props: { summary: SignOffSummary | null; onSee: (filter: NotInRunFilter) => void; t: Translator }) {
  const { t } = props;
  if (props.summary === null) return null;
  const accounts = props.summary.who_is_billed.accounts;
  const units = props.summary.who_is_billed.units;
  const see = (name: NotInRunFilter) => <SeeLink name={name} t={t} onPress={() => props.onSee(name)} />;
  return (
    <CollapsiblePanel
      id="who-is-billed"
      title={t("billing.bulkRun.signOff.whoIsBilled")}
      toggleLabel={t("billing.bulkRun.signOff.whoIsBilled")}
      aside={<PanelAside>{t("billing.bulkRun.signOff.whoAside", { accounts: count(accounts.billed) })}</PanelAside>}
    >
      <div className="grid grid-cols-2 gap-4">
        <div>
          <TableScroll>
            <PlainTable className={RUN_TABLE} data-run-table="who-accounts">
              <thead>
                <tr>
                  <th scope="col">{t("billing.bulkRun.signOff.accounts")}</th>
                  <th scope="col" data-num="">{t("billing.bulkRun.col.count")}</th>
                  <th scope="col"><span className="sr-only">{t("billing.bulkRun.see")}</span></th>
                </tr>
              </thead>
              <tbody>
                <Row total name="to-bill" label={t("billing.bulkRun.signOff.accountsToBill")} value={count(accounts.to_bill)} />
                <Row total name="billed" label={t("billing.bulkRun.signOff.billed")} value={count(accounts.billed)} />
                <Row indent name="regular" label={t("billing.bulkRun.signOff.regular")} value={count(accounts.regular)} />
                <Row indent name="master" label={t("billing.bulkRun.signOff.master")} value={count(accounts.master)} />
                <Row total name="not-billed" label={t("billing.bulkRun.signOff.notBilled")} value={count(accounts.not_billed)} />
                <Row indent name="blocked" label={t("billing.bulkRun.signOff.blocked")} value={count(accounts.blocked)} see={see("blocked")} />
                <Row indent name="held" label={t("billing.bulkRun.signOff.held")} value={count(accounts.held)} see={see("held")} />
                <Row indent name="nothing" label={t("billing.bulkRun.signOff.nothing")} value={count(accounts.nothing_to_bill)} see={see("nothing")} />
                <Row indent name="left-out" label={t("billing.bulkRun.signOff.leftOut")} value={count(accounts.left_out)} see={see("left_out")} />
                <Row indent name="waived" label={t("billing.bulkRun.signOff.waivedRow")} value={count(accounts.waived ?? 0)} />
                <Row indent name="failed" label={t("billing.bulkRun.signOff.failedToDraftRow")} value={count(accounts.failed_to_draft)} />
              </tbody>
            </PlainTable>
          </TableScroll>
          <NoReconcile reconciles={accounts.reconciles} name="accounts" t={t} />
        </div>
        <div>
          <TableScroll>
            <PlainTable className={RUN_TABLE} data-run-table="who-units">
              <thead>
                <tr>
                  <th scope="col">{t("billing.bulkRun.signOff.units")}</th>
                  <th scope="col" data-num="">{t("billing.bulkRun.col.count")}</th>
                  <th scope="col"><span className="sr-only">{t("billing.bulkRun.see")}</span></th>
                </tr>
              </thead>
              <tbody>
                <Row total name="in-cycle" label={t("billing.bulkRun.signOff.unitsInCycle")} value={count(units.in_cycle)} />
                <Row total name="units-billed" label={t("billing.bulkRun.signOff.unitsBilled")} value={count(units.billed)} />
                <Row indent name="own" label={t("billing.bulkRun.signOff.ownAccount")} value={count(units.own_account)} />
                <Row indent name="through-master" label={t("billing.bulkRun.signOff.throughMaster")} value={count(units.through_master)} />
                <Row total name="units-not-billed" label={t("billing.bulkRun.signOff.notBilled")} value={count(units.not_billed)} />
                <Row indent name="account-not-billed" label={t("billing.bulkRun.signOff.accountNotBilled")} value={count(units.account_not_billed)} />
                <Row indent name="units-nothing" label={t("billing.bulkRun.signOff.nothing")} value={count(units.nothing_to_bill)} />
                <Row indent name="nobody" label={t("billing.bulkRun.signOff.nobody")} value={count(units.nobody_to_bill)} see={see("nobody")} />
              </tbody>
            </PlainTable>
          </TableScroll>
          <NoReconcile reconciles={units.reconciles} name="units" t={t} />
        </div>
      </div>
    </CollapsiblePanel>
  );
}

export function UsageAndCharges(props: { summary: SignOffSummary | null; fmt: RunFormat }) {
  const { fmt } = props;
  const { t } = fmt;
  if (props.summary === null) return null;
  const cur = curOf(props.summary, fmt);
  const usage = props.summary.usage_and_charges;
  const signed = (amount: string) => (Number(amount) < 0 ? `−${money(amount.replace("-", ""), cur)}` : money(amount, cur));
  return (
    <CollapsiblePanel
      id="usage-and-charges"
      title={t("billing.bulkRun.signOff.usageCharges")}
      toggleLabel={t("billing.bulkRun.signOff.usageCharges")}
      aside={
        <PanelAside>
          {t("billing.bulkRun.signOff.usageAside", { count: usage.services.length, amount: money(usage.this_run_charges, cur) })}
        </PanelAside>
      }
    >
      <TableScroll>
        <PlainTable className={RUN_TABLE} data-run-table="usage">
          <thead>
            <tr>
              <th scope="col">{t("billing.bulkRun.col.service")}</th>
              <th scope="col" data-num="">{t("billing.bulkRun.col.bills")}</th>
              <th scope="col" data-num="">{t("billing.bulkRun.col.usage")}</th>
              <th scope="col" data-num="">{t("billing.bulkRun.col.usageCharges")}</th>
              <th scope="col" data-num="">{t("billing.bulkRun.col.baseCharges")}</th>
              <th scope="col" data-num="">{t("billing.bulkRun.col.total")}</th>
            </tr>
          </thead>
          <tbody>
            {usage.services.map((row) => (
              <tr key={row.service_code} data-usage-service={row.service_code}>
                <th scope="row">
                  <ServiceLabel code={row.service_code} t={t} />
                </th>
                <td data-num="">{count(row.bills)}</td>
                <td data-num="">
                  {row.usage.length === 0
                    ? "—"
                    : row.usage.map((one) => `${Number(one.quantity).toLocaleString("en-US")} ${one.unit}`).join(" · ")}
                </td>
                <td data-num="">{money(row.usage_charges, cur)}</td>
                <td data-num="">{money(row.base_charges, cur)}</td>
                <td data-num="">{money(row.total, cur)}</td>
              </tr>
            ))}
            <tr data-total="">
              <th scope="row">{t("billing.bulkRun.signOff.services")}</th>
              <td data-num="" />
              <td data-num="" />
              <td data-num="" />
              <td data-num="" />
              <td data-num="">{money(usage.services_subtotal, cur)}</td>
            </tr>
            <tr data-usage-other="taxes">
              <th scope="row">{t("billing.bulkRun.signOff.taxes")}</th>
              <td data-num="" />
              <td data-num="" />
              <td data-num="" />
              <td data-num="" />
              <td data-num="">{signed(usage.other.taxes)}</td>
            </tr>
            <tr data-usage-other="fees">
              <th scope="row">{t("billing.bulkRun.signOff.fees")}</th>
              <td data-num="" />
              <td data-num="" />
              <td data-num="" />
              <td data-num="" />
              <td data-num="">{signed(usage.other.fees)}</td>
            </tr>
            <tr data-usage-other="credits">
              <th scope="row">{t("billing.bulkRun.signOff.credits")}</th>
              <td data-num="" />
              <td data-num="" />
              <td data-num="" />
              <td data-num="" />
              <td data-num="">{signed(usage.other.credits_and_adjustments)}</td>
            </tr>
            <tr data-total="">
              <th scope="row">{t("billing.bulkRun.signOff.charges")}</th>
              <td data-num="">{count(props.summary.run_summary.bills)}</td>
              <td data-num="" />
              <td data-num="" />
              <td data-num="" />
              <td data-num="">{money(usage.this_run_charges, cur)}</td>
            </tr>
          </tbody>
        </PlainTable>
      </TableScroll>
      <NoReconcile reconciles={usage.reconciles} name="usage" t={t} />
    </CollapsiblePanel>
  );
}

function paymentsTile(summary: SignOffSummary | null, cur: RunFormat, t: Translator): FactCardItem {
  const pay = summary?.payments_and_balances ?? null;
  const run = summary?.run_summary ?? null;
  const label = t("billing.bulkRun.signOff.paymentsApplied");
  if (pay !== null && hasSplit(pay)) {
    return {
      id: "payments",
      label,
      value: money(pay.payments_applied ?? null, cur),
      note: t("billing.bulkRun.signOff.paymentsCount", { count: pay.payments_count ?? 0 }),
    };
  }
  return {
    id: "payments",
    label,
    value: money(pay?.payments_and_credits_applied ?? null, cur),
    note:
      run === null || run.payments_applied === null || run.payments_applied === undefined
        ? undefined
        : t("billing.bulkRun.signOff.paymentsAccounts", { count: run.payments_applied }),
  };
}

/** DEF-BIL-8682 — the server parted the payments from the credits. */
function hasSplit(pay: SignOffSummary["payments_and_balances"]): boolean {
  return (
    pay.payments_applied !== null &&
    pay.payments_applied !== undefined &&
    pay.credits_applied !== null &&
    pay.credits_applied !== undefined
  );
}

/** DEF-BIL-8720 — some bill holds back part of a payment plan as not yet due. */
function hasPlanLater(pay: SignOffSummary["payments_and_balances"]): boolean {
  const later = pay.plan_not_yet_due;
  return later !== null && later !== undefined && Number(later) !== 0;
}

/** A figure taken off the balance, written `−$1.00`; `$0.00` stays unsigned. */
function minus(amount: string | null | undefined, cur: RunFormat): string {
  if (amount === null || amount === undefined) return "—";
  return Number(amount) === 0 ? money("0", cur) : `−${money(amount, cur)}`;
}

/** In the drawing's order (D1 28). */
const HOW_PAID = ["autopay", "plan_instalment", "level_pay", "credit_covers", "by_due_date"] as const;

export function PaymentsAndBalances(props: {
  summary: SignOffSummary | null;
  fmt: RunFormat;
  /** Record links (PO 2026-10-19): where a credit-covered account opens. */
  accountHref?: (accountId: string) => string;
}) {
  const { fmt } = props;
  const { t } = fmt;
  if (props.summary === null) return null;
  const cur = curOf(props.summary, fmt);
  const pay = props.summary.payments_and_balances;
  const paid = pay.payments_and_credits_applied;
  return (
    <CollapsiblePanel
      id="payments-balances"
      title={t("billing.bulkRun.signOff.payments")}
      toggleLabel={t("billing.bulkRun.signOff.payments")}
      aside={<PanelAside>{t("billing.bulkRun.signOff.dueAside", { amount: money(pay.amount_due, cur) })}</PanelAside>}
    >
      <div className="grid grid-cols-2 gap-4">
        <TableScroll>
          <PlainTable className={RUN_TABLE} data-run-table="balances">
            <thead>
              <tr>
                <th scope="col">{t("billing.bulkRun.col.balance")}</th>
                <th scope="col" data-num="">{t("billing.bulkRun.col.amount")}</th>
              </tr>
            </thead>
            <tbody>
              <Row name="previous" label={t("billing.bulkRun.signOff.previousBalance")} value={money(pay.previous_balance, cur)} />
              {hasSplit(pay) ? (
                <>
                  {/* DEF-BIL-8682 — payments apart from credits, each with how
                      many (D1 28); the two add back to the merged figure. */}
                  <Row
                    name="paid"
                    label={
                      <>
                        {t("billing.bulkRun.signOff.paymentsApplied")}{" "}
                        <span className="font-normal text-neutral-700">{count(pay.payments_count ?? null)}</span>
                      </>
                    }
                    value={minus(pay.payments_applied, cur)}
                  />
                  <Row
                    name="credits"
                    label={
                      <>
                        {t("billing.bulkRun.signOff.creditsApplied")}{" "}
                        <span className="font-normal text-neutral-700">{count(pay.credits_count ?? null)}</span>
                      </>
                    }
                    value={minus(pay.credits_applied, cur)}
                  />
                </>
              ) : (
                <Row name="paid" label={t("billing.bulkRun.signOff.paymentsCredits")} value={minus(paid, cur)} />
              )}
              <Row name="charges" label={t("billing.bulkRun.signOff.charges")} value={money(pay.this_run_charges, cur)} />
              {/* DEF-BIL-8720 — BR-BIL-1061: the part of a payment plan not yet
                  due is not asked, on the bill or here ($62 + $45 = $107, $225
                  later). Drawn only when a bill holds some back, so the table
                  foots; the figure is the server's, never worked out here. */}
              {hasPlanLater(pay) ? (
                <Row name="plan-later" label={t("billing.bulkRun.signOff.planNotYetDue")} value={minus(pay.plan_not_yet_due ?? null, cur)} />
              ) : null}
              <Row total name="due" label={t("billing.bulkRun.signOff.amountDue")} value={money(pay.amount_due, cur)} />
            </tbody>
          </PlainTable>
        </TableScroll>
        <TableScroll>
          <PlainTable className={RUN_TABLE} data-run-table="how-paid">
            <thead>
              <tr>
                <th scope="col">{t("billing.bulkRun.signOff.howPaid")}</th>
                <th scope="col" data-num="">{t("billing.bulkRun.col.accounts")}</th>
                <th scope="col" data-num="">{t("billing.bulkRun.col.amount")}</th>
              </tr>
            </thead>
            <tbody>
              {HOW_PAID.map((bucket) => {
                const figure = pay.how_paid?.[bucket] ?? null;
                return (
                  <tr key={bucket} data-how-paid={bucket}>
                    <th scope="row">{t(`billing.bulkRun.signOff.paid.${bucket}`)}</th>
                    <td data-num="">{count(figure?.bills ?? null)}</td>
                    <td data-num="">{money(figure?.amount ?? null, cur)}</td>
                  </tr>
                );
              })}
            </tbody>
          </PlainTable>
        </TableScroll>
      </div>
      {(pay.credit_covers_bills?.count ?? 0) > 0 && (
        <div className="mt-4" data-credit-covers={pay.credit_covers_bills?.count}>
          <h3 className="m-0 font-heading text-md font-semibold">{t("billing.bulkRun.signOff.paid.credit_covers")}</h3>
          <TableScroll>
            <PlainTable className={`${RUN_TABLE} mt-2`} data-run-table="credit-covers">
              <thead>
                <tr>
                  <th scope="col">{t("billing.bulkRun.col.account")}</th>
                  <th scope="col" data-num="">{t("billing.bulkRun.col.total")}</th>
                  <th scope="col" data-num="">{t("billing.bulkRun.col.credit")}</th>
                  <th scope="col" data-num="">{t("billing.bulkRun.col.leftAfter")}</th>
                </tr>
              </thead>
              <tbody>
                {(pay.credit_covers_bills?.results ?? []).map((row) => (
                  <tr key={row.account_id} data-credit-covers-row={row.account_no ?? ""}>
                    <th scope="row">
                      {row.account_no === null ? (
                        "—"
                      ) : props.accountHref !== undefined ? (
                        <a href={props.accountHref(row.account_id)} target="_blank" rel="noreferrer" className="text-accent-700 underline">
                          {row.account_no}
                        </a>
                      ) : (
                        row.account_no
                      )}
                    </th>
                    <td data-num="">{money(row.bill_total, cur)}</td>
                    <td data-num="">{money(row.credit, cur)}</td>
                    <td data-num="">{money(row.left_after, cur)}</td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </TableScroll>
        </div>
      )}
      <NoReconcile reconciles={pay.reconciles} name="payments" t={t} />
    </CollapsiblePanel>
  );
}

/** DEF-BIL-8683 — a customer type is the catalogue's word for the stored class
 *  code (`rating.customerClass.*`, the words Plans & Rates uses); a code the
 *  catalogue does not know is written as words, never printed raw. */
export function customerTypeWord(category: string | null, t: Translator): string {
  if (category === null || category === "") return "—";
  const plain = category.replace(/_/g, " ");
  return t(`rating.customerClass.${category}`, { defaultValue: plain.charAt(0).toUpperCase() + plain.slice(1) });
}

export function ByCustomerType(props: { summary: SignOffSummary | null; fmt: RunFormat }) {
  const { fmt } = props;
  const { t } = fmt;
  if (props.summary === null) return null;
  const cur = curOf(props.summary, fmt);
  const rows = props.summary.by_customer_type;
  return (
    <CollapsiblePanel
      id="by-customer-type"
      title={t("billing.bulkRun.signOff.byType")}
      toggleLabel={t("billing.bulkRun.signOff.byType")}
      defaultOpen={false}
      aside={<PanelAside>{t("billing.bulkRun.signOff.typesAside", { count: rows.length })}</PanelAside>}
    >
      <TableScroll>
        <PlainTable className={RUN_TABLE} data-run-table="by-type">
          <thead>
            <tr>
              <th scope="col">{t("billing.bulkRun.col.customerType")}</th>
              <th scope="col" data-num="">{t("billing.bulkRun.col.bills")}</th>
              <th scope="col" data-num="">{t("billing.bulkRun.col.charges")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.category ?? "none"}>
                <th scope="row">{customerTypeWord(row.category, t)}</th>
                <td data-num="">{count(row.bills)}</td>
                <td data-num="">{money(row.amount, cur)}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </TableScroll>
    </CollapsiblePanel>
  );
}

/** A warning the Check found that still stands: its tag, its words, its accounts. */
export interface StandingWarning {
  code: string;
  label_key: string;
  count: number;
}

/** DEF-BIL-8684 — the Check's WARNING tags with accounts on them. A warning
 *  never blocks, so its accounts are billed; Sign off and Send must still say
 *  so (D1 25, 31: *"14 bills: Electric base $0.00. See"*). The count is the
 *  Check's own, never recomputed here. */
export function standingWarnings(check: CheckSummary | null): StandingWarning[] {
  if (check === null) return [];
  return check.categories.flatMap((category) =>
    category.tags
      .filter((tag) => tag.severity === "warning" && tag.count > 0)
      .map((tag) => ({ code: tag.code, label_key: tag.label_key, count: tag.count })),
  );
}

/** How many lines Sign off's warnings note draws — and so what Send counts. */
export function warningLineCount(breaks: number, summary: SignOffSummary | null, standing: readonly StandingWarning[]): number {
  return standing.length + (breaks > 0 ? 1 : 0) + ((summary?.waived ?? []).length > 0 ? 1 : 0);
}

/** The amber note under Not in this run: each warning with where it is seen —
 *  the Check's standing warnings (DEF-BIL-8684), the waived bases (fixed-charge
 *  case 2, PO 2026-09-30) with their served total and each account, and the
 *  bills that failed to draft. */
export function SignOffWarnings(props: {
  breaks: number;
  summary: SignOffSummary | null;
  standing?: readonly StandingWarning[];
  onSeeTag?: (code: string) => void;
  onSeeBreaks: () => void;
  onSeeWaived: () => void;
  fmt: RunFormat;
  /** Record links (PO 2026-10-19): where a waived account's number opens. */
  accountHref?: (accountId: string) => string;
}) {
  const { fmt } = props;
  const { t } = fmt;
  const waived = props.summary?.waived ?? [];
  const standing = props.standing ?? [];
  const cur = props.summary === null ? fmt : curOf(props.summary, fmt);
  const lines = warningLineCount(props.breaks, props.summary, standing);
  if (lines === 0) return null;
  return (
    <div className="bg-warning-100 px-4 py-3 text-base text-warning-700" role="status" data-signoff-warnings="">
      <p className="m-0 font-heading font-semibold">{t("billing.bulkRun.signOff.warnings", { count: lines })}</p>
      <ul className="m-0 mt-1 list-disc pl-5">
        {standing.map((warning) => (
          <li key={warning.code} data-warning-line={`tag-${warning.code}`}>
            {t("billing.bulkRun.signOff.tagLine", { count: warning.count, tag: t(warning.label_key, { defaultValue: warning.code }) })}{" "}
            <button
              type="button"
              className="cursor-pointer border-0 bg-transparent p-0 font-semibold text-inherit underline"
              onClick={() => props.onSeeTag?.(warning.code)}
              data-see={`tag-${warning.code}`}
            >
              {t("billing.bulkRun.see")}
            </button>
          </li>
        ))}
        {waived.length > 0 && (
          <li data-warning-line="waived">
            {t("billing.bulkRun.signOff.waivedLine", { count: waived.length })}{" "}
            <span data-waived-total="">{t("billing.bulkRun.signOff.waivedTotal", { amount: money(props.summary?.waived_total ?? null, cur) })}</span>{" "}
            <button
              type="button"
              className="cursor-pointer border-0 bg-transparent p-0 font-semibold text-inherit underline"
              onClick={props.onSeeWaived}
              data-see="waived"
            >
              {t("billing.bulkRun.see")}
            </button>
            <ul className="m-0 mt-1 list-none p-0" data-waived-list="">
              {waived.map((row) => (
                <li key={row.account_no} data-waived-account={row.account_no}>
                  {props.accountHref !== undefined && row.account_id != null ? (
                    <a href={props.accountHref(row.account_id)} target="_blank" rel="noreferrer" className="text-accent-700 underline">
                      {row.account_no}
                    </a>
                  ) : (
                    row.account_no
                  )}{" "}
                  · {money(row.amount, { ...cur, currency: row.currency })}
                </li>
              ))}
            </ul>
          </li>
        )}
        {props.breaks > 0 && (
          <li>
            {t("billing.bulkRun.signOff.failedToDraft", { count: props.breaks })}{" "}
            <button
              type="button"
              className="cursor-pointer border-0 bg-transparent p-0 font-semibold text-inherit underline"
              onClick={props.onSeeBreaks}
              data-see="breaks"
            >
              {t("billing.bulkRun.seeBreaks")}
            </button>
          </li>
        )}
      </ul>
    </div>
  );
}

export function FailedToDraftPanel(props: {
  breaks: readonly BillRunBreakRow[];
  retried: ReadonlySet<string>;
  working: boolean;
  onRetry: (accountId: string) => void;
  onClose: () => void;
  fixHref: (tagId: string | null, accountId: string) => string;
  t: Translator;
}) {
  const { t } = props;
  return (
    <SidePanel
      name="failed-to-draft"
      kicker={t("billing.bulkRun.signOff.billsKicker")}
      title={
        <>
          {t("billing.bulkRun.signOff.failedTitle")} <span className="text-base text-neutral-700">{count(props.breaks.length)}</span>
        </>
      }
      note={t("billing.bulkRun.signOff.failedNote")}
      closeLabel={t("billing.bulkRun.close")}
      onClose={props.onClose}
    >
      <TableScroll>
        <PlainTable className={RUN_TABLE} data-run-table="failed-to-draft">
          <thead>
            <tr>
              <th scope="col">{t("billing.bulkRun.col.account")}</th>
              <th scope="col">{t("billing.bulkRun.col.whatFailed")}</th>
              <th scope="col">{t("billing.bulkRun.col.fixIn")}</th>
              <th scope="col">{t("billing.bulkRun.col.action")}</th>
            </tr>
          </thead>
          <tbody>
            {props.breaks.map((row) => {
              const tag = breakTag(row.reason);
              const screen = tag === null ? "accounts" : fixScreenOf(tag);
              const done = props.retried.has(row.account_id);
              return (
                <tr key={row.id}>
                  <td className="font-heading font-semibold">
                    {/* Record links (PO 2026-10-19): the account, in a new tab. */}
                    <a href={props.fixHref(null, row.account_id)} target="_blank" rel="noreferrer" className="text-accent-700 underline">
                      {row.account_no}
                    </a>
                  </td>
                  <td>{tag === null ? t("billing.bulkRun.signOff.couldNotDraft") : t(`billing.bulkRun.tag.${tag}.name`)}</td>
                  <td>
                    <a href={props.fixHref(tag, row.account_id)} target="_blank" rel="noreferrer" className="text-accent-700 underline">
                      {t(`billing.bulkRun.screen.${screen}`)} ↗
                    </a>
                  </td>
                  <td>
                    {done ? (
                      <StatusPill tone="success">{t("billing.bulkRun.signOff.drafted")}</StatusPill>
                    ) : (
                      <Button size="sm" disabled={props.working || row.retryable === false} onClick={() => props.onRetry(row.account_id)}>
                        {t("billing.bulkRun.retry")}
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </PlainTable>
      </TableScroll>
    </SidePanel>
  );
}

export function SignOffConfirmations(props: {
  ticked: ReadonlySet<Confirmation>;
  onToggle: (confirmation: Confirmation) => void;
  disabled: boolean;
  t: Translator;
}) {
  const { t } = props;
  return (
    <Panel as="section" title={t("billing.bulkRun.signOff.title")} aria-label={t("billing.bulkRun.signOff.title")} data-run-panel-section="confirmations">
      <fieldset className="m-0 mt-3 flex flex-col gap-2 border-0 p-0">
        <legend className="sr-only">{t("billing.bulkRun.signOff.title")}</legend>
        {CONFIRMATIONS.map((confirmation) => (
          <label key={confirmation} className="flex items-center gap-3 text-base">
            <input
              type="checkbox"
              checked={props.ticked.has(confirmation)}
              disabled={props.disabled}
              onChange={() => props.onToggle(confirmation)}
              data-confirmation={confirmation}
            />
            {t(`billing.bulkRun.signOff.confirm.${confirmation}`)}
          </label>
        ))}
      </fieldset>
    </Panel>
  );
}
