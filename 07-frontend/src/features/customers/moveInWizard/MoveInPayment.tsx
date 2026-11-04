// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.31 (lane MVI-WIZ-BILL) — the Billing step's
//           Payment, from images 41, 43 and 44: *Pay now* / *Add to bill*, the
//           method fields, and the line that says what goes on the first bill.
// Rules:    J4 (decision log 2026-10-05 *"MOVE-IN REDESIGN P1.12–P1.16"* (4)):
//           money taken at the counter is an ADVANCE on the first bill —
//           $150.00 + $25.00 + $40.00 = $215.00; $100.00 by check →
//           *"$115.00 goes on the first bill."* · OQ-BIL-12788 CLOSED (a) (no
//           tax) · CLAUDE.md hard rule 2 (the typed amount travels as the
//           clerk's characters; nothing here parses it into a number) · B14
//           rules 33, 43, 44 · PO 2026-09-29 (*check*, never *cheque*)
// Server:   `payment` on POST …/move-in (§9.MONEY) · GET /payments (its
//           `methods`, the tenant's tenders)
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { getPayments } from "@/api/endpoints";
import { REFERENCE_STALE_MS } from "@/api/queryClient";
import { AffixField } from "@/components/AffixField";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { formatMoney, formatMoneyInput } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { SegmentedControl } from "@/components/SegmentedControl";
import { methodOptions } from "@/features/payments/paymentsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { referenceLabel } from "../NewConnectChargesStep";
import { feesTotal, isZero, onFirstBill } from "./billingModel";
import type { BillingProblem, PaymentMode, StepBillingOwn } from "./billingModel";

export function MoveInPayment(props: {
  own: StepBillingOwn;
  set: (next: StepBillingOwn) => void;
  ready: boolean;
  currency: string;
  dateFormat: RegionalDateFormat;
  /** The tenant's today — the drawn default for *Received*. */
  today: string;
  problems: readonly BillingProblem[];
  tried: boolean;
  client: ApiClient;
  t: Translator;
}) {
  const { own, set, t } = props;
  const pay = own.payment;
  const methods = useQuery({
    queryKey: ["payments", "move-in-methods"],
    queryFn: () => getPayments({ per: 1 }, props.client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const total = props.ready ? feesTotal(own) : null;
  const shown = (amount: string) => formatMoney(amount, props.currency);
  const error = (problem: BillingProblem, key: string) =>
    props.tried && props.problems.includes(problem) ? t(key) : undefined;

  function patch(next: Partial<StepBillingOwn["payment"]>): void {
    set({ ...own, payment: { ...pay, ...next } });
  }

  // Image 41 *"All fees paid now. Receipt prints on complete."* · image 43
  // *"$115.00 goes on the first bill."* · image 44 *"$215.00 goes on the first
  // bill."* — each a FACT of ≤ 6 words (B14 rule 33).
  let line: string | null = null;
  if (total !== null && !isZero(total)) {
    const left = onFirstBill(own);
    if (left !== null) {
      line =
        pay.mode === "pay_now" && isZero(left)
          ? t("customers.moveIn.payment.allPaid")
          : t("customers.moveIn.payment.onFirstBill", { amount: shown(left) });
    }
  }

  return (
    <Panel
      as="section"
      title={t("customers.moveIn.payment.title")}
      trailing={
        total === null ? undefined : (
          <span className="text-base text-neutral-700" data-payment-fees-total="">
            {t("customers.moveIn.payment.feesTotal", { amount: shown(total) })}
          </span>
        )
      }
      data-move-in-payment={pay.mode}
    >
      <SegmentedControl
        purpose="choice"
        name="move-in-payment"
        label={t("customers.moveIn.payment.title")}
        active={pay.mode}
        onSelect={(id) => patch({ mode: id as PaymentMode })}
        segments={[
          { id: "pay_now", label: t("customers.moveIn.payment.payNow") },
          { id: "add_to_bill", label: t("customers.moveIn.payment.addToBill") },
        ]}
        className="mb-5"
      />
      {pay.mode === "pay_now" && (
        <div className="grid grid-cols-4 gap-x-6 gap-y-5" data-payment-fields="">
          <SelectField
            id="move_in_payment_method"
            label={t("customers.moveIn.payment.method")}
            required
            value={pay.methodCode}
            onChange={(methodCode) => patch({ methodCode })}
            placeholder={t("customers.moveIn.payment.methodChoose")}
            options={methodOptions(methods.data?.methods ?? [])}
            error={error("payment_method", "customers.moveIn.payment.methodRequired")}
          />
          <AffixField
            id="move_in_payment_amount"
            label={t("customers.moveIn.payment.amount")}
            required
            affix="$"
            side="start"
            // Untouched shows the whole total (image 41) — the server's own
            // 4-place figure at 2 places, the way a clerk types money.
            value={pay.amount === "" && total !== null ? formatMoneyInput(total) : pay.amount}
            onChange={(amount) => patch({ amount })}
            error={
              error("payment_amount", "customers.moveIn.payment.amountRequired") ??
              error("payment_more", "customers.moveIn.payment.moreThanFees")
            }
          />
          <TextField
            id="move_in_payment_reference"
            label={referenceLabel(t, pay.methodCode)}
            value={pay.confirmation}
            onChange={(confirmation) => patch({ confirmation })}
          />
          <DatePickerField
            id="move_in_payment_received"
            label={t("customers.moveIn.payment.received")}
            required
            value={pay.receivedOn}
            prefill={props.today}
            dateFormat={props.dateFormat}
            onChange={(receivedOn) => patch({ receivedOn })}
            error={error("payment_received", "customers.moveIn.payment.receivedRequired")}
          />
        </div>
      )}
      {line !== null && (
        <p className="mt-4 mb-0 text-base text-neutral-700" data-payment-line="">
          {line}
        </p>
      )}
    </Panel>
  );
}
