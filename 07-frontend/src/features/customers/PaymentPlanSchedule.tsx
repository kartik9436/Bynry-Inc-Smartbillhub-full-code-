// ── Trace ──────────────────────────────────────────────
// Change:   PO 2026-10-11, decision log *"DEBTORS DETAIL … SHOWS THE PAYMENT
//           PLAN'S INSTALMENTS"* — PO, verbatim: *"images are correct - you can
//           proceed with fix"*. The instalment table that lived inside
//           `PaymentPlanWizard.tsx` (`PlanPanel` / `ScheduleRows`) moved here
//           so the Debtors detail screen draws THE SAME table rather than a
//           second copy of it (B14 rule 43).
// Rules:    B14 rule 21 (Tailwind utilities only — listed in
//           `styles/route-b-migrated.txt`) · 31 · 32 (no rule id on screen) ·
//           33 · 43 · 44 · CLAUDE.md hard rule 2 (every amount at 2 places,
//           with its currency) · BR-SHL-023 (the tenant's date format) ·
//           BR-PAY-021 (on-time is `paid_posted_on ≤ due_date`)
// Tests:    src/features/customers/PaymentPlanWizard.test.tsx ·
//           src/features/payments/debtorScreens.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * ONE instalment table, two screens: the account's Payment plan window and
 * the Debtors detail (7·2). Drawn as: the status pill · *"Paid $X of $Y · N of
 * M met"* · the three counts (paid · missed · upcoming) · the missed line ·
 * the table `# · Due · Amount · Left · Status`.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * LEFT, AND WHY IT IS DERIVED RATHER THAN SERVED
 * ══════════════════════════════════════════════════════════════════════════
 * `GET /accounts/{id}/payment-plans` serves each persisted instalment's
 * `amount` and `paid_posted_on`, and nothing else about money. An instalment
 * is met WHOLE — `plans.record_installment_payment` stamps `paid_posted_on`
 * and the plan's own `paid_to_date` is the sum of the amounts of exactly the
 * stamped rows. So the amount still owed on an instalment is its `amount`
 * when unstamped and `0.00` when stamped — the same arithmetic the server's
 * `paid_to_date` already does, read off the same two fields. Nothing is
 * invented: there is no part-paid figure on an instalment to lose.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE THREE COUNTS, AND WHY *MISSED* IS THE SERVER'S LIST
 * ══════════════════════════════════════════════════════════════════════════
 * · **paid** — instalments met (`paid_posted_on` set), the same count the
 *   progress line's *"N of M met"* reads.
 * · **missed** — the server's `missed_installment_seqs`, which is
 *   `plans.outstanding_installments`' rule (due BEFORE the business date and
 *   not met by its due date). The Debtors tile's *"1 missed"* is the length of
 *   that same rule's answer, so reading the list here is what makes the two
 *   agree. ⚠ A plan whose instalment was paid LATE counts it both as paid and
 *   as missed — that is the server's own reading (BR-PAY-021: a late payment
 *   does not make an instalment on time), and a count here that quietly
 *   disagreed with the tile would be a second definition of *missed*.
 * · **upcoming** — not met and not in the missed list.
 */
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type {
  PaymentPlanContext,
  PaymentPlanInstallmentView,
  PaymentPlanRow,
} from "@/api/endpoints";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { TextField } from "@/components/FormModal";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";

/** The query key both screens read the account's plans under — one cache. */
export const paymentPlansKey = (accountId: string) =>
  ["accounts", "payment-plans", accountId] as const;

/**
 * The sentence a clerk reads when a new plan cannot be proposed.
 *
 * The SERVER's catalogue key where it sends one — PO 2026-10-11: *"This
 * account already has a plan."*, which replaced a sentence ending
 * *"(BR-CUS-043 / A3)"* (B14 rule 32: no rule id in clerk-facing copy). The
 * other reasons have no keyed sentence yet and are quoted as before. Here
 * rather than in the wizard because the account's Plan tab says it too.
 */
export function blockedSentence(
  context: PaymentPlanContext,
  t: (key: string, params?: Record<string, unknown>) => string,
): string | null {
  if (context.can_propose) return null;
  const key = context.cannot_propose_reason_key ?? null;
  return key !== null
    ? t(key)
    : t("customers.paymentPlan.cannotPropose", { reason: context.cannot_propose_reason ?? "" });
}

/** What a persisted instalment still owes: its amount, or `0.00` once met.
 *  See this file's header — an instalment is met whole. */
export function instalmentLeft(row: PaymentPlanInstallmentView): string {
  return row.paid_posted_on ? "0.00" : row.amount;
}

export interface PlanCounts {
  paid: number;
  missed: number;
  upcoming: number;
}

/** paid · missed · upcoming — see this file's header for each definition. */
export function planCounts(plan: PaymentPlanRow): PlanCounts {
  const missed = new Set(plan.missed_installment_seqs);
  let paid = 0;
  let upcoming = 0;
  for (const row of plan.installments) {
    if (row.paid_posted_on) paid += 1;
    else if (!missed.has(row.seq)) upcoming += 1;
  }
  return { paid, missed: missed.size, upcoming };
}

/** *"3 and 4"* in the reader's own language. `Intl.ListFormat` where the
 *  runtime has it; a comma join where it does not, which degrades rather
 *  than lies — `FixABillTab.joinReasons`' rule. */
export function joinSeqs(seqs: readonly number[], language: string): string {
  const words = seqs.map(String);
  try {
    return new Intl.ListFormat(language, { type: "conjunction" }).format(words);
  } catch {
    return words.join(", ");
  }
}

const NUM = "[&&]:text-right tabular-nums";

export interface PaymentPlanScheduleTableProps {
  rows: PaymentPlanInstallmentView[];
  currency: string;
  dateFormat: RegionalDateFormat;
  /** A PERSISTED plan: draw the Status column, and *Left* is what each
   *  instalment still owes. Off on the wizard's step-2 preview, where *Left*
   *  is the server's `remaining` after the row and nothing can be outstanding
   *  on a schedule nobody has signed. */
  showState?: boolean;
  /** The server's missed list — an unmet row in it wears the danger tone. */
  missedSeqs?: readonly number[];
  /** Step 2's editable amounts. */
  onEdit?: (seq: number, amount: string) => void;
  edits?: Record<number, string>;
}

/** The table: `# · Due · Amount · Left · Status`. */
export function PaymentPlanScheduleTable(props: PaymentPlanScheduleTableProps) {
  const { t } = useTranslation();
  const { rows, currency, dateFormat } = props;
  const missed = new Set(props.missedSeqs ?? []);
  const on = (value: string) => formatDate(value, "UTC", dateFormat);
  return (
    <div className="overflow-x-auto">
      {/* `data-plan-schedule` is the hook `e2e/S24-payment-plan.spec.ts`
          locates rows by — it replaced the `.cus-plan-schedule` class, which
          rule 21 retires with the stylesheet rule it named. */}
      <PlainTable data-plan-schedule="">
        <thead>
          <tr>
            <th scope="col">{t("customers.paymentPlan.col.seq")}</th>
            <th scope="col">{t("customers.paymentPlan.col.dueDate")}</th>
            <th scope="col" className={NUM}>
              {/* CLAUDE.md rule 2 — step 2's amounts are INPUTS with no symbol,
                  so the CHAR(3) goes on the column head. */}
              {t("customers.paymentPlan.col.amount")}
              {props.onEdit !== undefined ? ` (${currency})` : ""}
            </th>
            <th scope="col" className={NUM}>{t("customers.paymentPlan.col.remaining")}</th>
            {props.showState === true && (
              <th scope="col" className={NUM}>{t("customers.paymentPlan.col.state")}</th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            let left: ReactNode = null;
            if (props.showState === true) {
              left = <MoneyCell amount={instalmentLeft(row)} currency={currency} />;
            } else if (row.remaining !== undefined) {
              left = <MoneyCell amount={row.remaining} currency={currency} />;
            }
            const paidOn = row.paid_posted_on ?? null;
            const tone: StatusTone =
              paidOn === null
                ? missed.has(row.seq)
                  ? "danger"
                  : "neutral"
                : row.on_time === false
                  ? "warning"
                  : "success";
            return (
              <tr key={row.seq}>
                <td className="tabular-nums">{row.seq}</td>
                <td className="tabular-nums whitespace-nowrap">{on(row.due_date)}</td>
                <td className={NUM}>
                  {props.onEdit === undefined ? (
                    <MoneyCell amount={row.amount} currency={currency} />
                  ) : (
                    <TextField
                      id={`installment-${row.seq}`}
                      label={t("customers.paymentPlan.col.amount")}
                      value={props.edits?.[row.seq] ?? row.amount}
                      numeric
                      onChange={(value) => props.onEdit?.(row.seq, value)}
                    />
                  )}
                </td>
                <td className={NUM}>
                  {left}
                  {row.final === true && (
                    <StatusPill tone="neutral">{t("customers.paymentPlan.finalRow")}</StatusPill>
                  )}
                </td>
                {props.showState === true && (
                  <td className={NUM}>
                    {/* THREE states, not two: `on_time` is `null` until a
                        payment meets the row — never `false` (BR-PAY-021). */}
                    <StatusPill tone={tone}>
                      {paidOn === null
                        ? t("customers.paymentPlan.state.outstanding")
                        : row.on_time === false
                          ? t("customers.paymentPlan.state.paidLate", { on: on(paidOn) })
                          : t("customers.paymentPlan.state.paid", { on: on(paidOn) })}
                    </StatusPill>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </PlainTable>
    </div>
  );
}

export interface PlanInstalmentsProps {
  plan: PaymentPlanRow;
  dateFormat: RegionalDateFormat;
}

/** A persisted plan: pill · progress · counts · missed line · table. */
export function PlanInstalments(props: PlanInstalmentsProps) {
  const { t, i18n } = useTranslation();
  const { plan } = props;
  const counts = planCounts(plan);
  const missed = plan.missed_installment_seqs;
  return (
    <div className="grid gap-3" data-plan-summary="">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <StatusPill tone={plan.status === "active" ? "success" : "warning"}>
          {t(`customers.paymentPlan.status.${plan.status}`)}
        </StatusPill>
        <span className="text-sm" data-plan-progress="">
          {t("customers.paymentPlan.progress", {
            paid: formatMoney(plan.paid_to_date, plan.currency),
            total: formatMoney(plan.spread, plan.currency),
            met: counts.paid,
            count: plan.installment_count,
          })}
        </span>
        <span className="flex flex-wrap gap-2" data-plan-counts="">
          <StatusPill tone="success">
            {t("customers.paymentPlan.count.paid", { count: counts.paid })}
          </StatusPill>
          <StatusPill tone={counts.missed > 0 ? "danger" : "neutral"}>
            {t("customers.paymentPlan.count.missed", { count: counts.missed })}
          </StatusPill>
          <StatusPill tone="neutral">
            {t("customers.paymentPlan.count.upcoming", { count: counts.upcoming })}
          </StatusPill>
        </span>
      </div>
      {missed.length > 0 && (
        // PO 2026-08-11 — a miss is CHASED, never a drop-off; a PART-PAID
        // instalment is still a missed one (OQ-139). Plural-aware since
        // 2026-10-11: "Installments 3 and 4 were missed."
        <p className="m-0 text-sm text-danger-700" role="note" data-plan-missed="">
          {t("customers.paymentPlan.missed", {
            count: missed.length,
            seqs: joinSeqs(missed, i18n.language || "en"),
          })}
        </p>
      )}
      <PaymentPlanScheduleTable
        rows={plan.installments}
        currency={plan.currency}
        dateFormat={props.dateFormat}
        missedSeqs={missed}
        showState
      />
    </div>
  );
}
