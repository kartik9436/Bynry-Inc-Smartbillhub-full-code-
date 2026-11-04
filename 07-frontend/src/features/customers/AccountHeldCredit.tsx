// ── Trace ──────────────────────────────────────────────
// Screens:  S21 · ACC-T04 Credits tab — the "Held credit" group
// Defect:   DEF-PAY-10707 (tester L2-01, 2026-10-30) — money paid beyond the bill
//           was booked to customer credit and shown nowhere on the account
// Rules:    BR-PAY-012 (unapplied money → account credit) · BR-PAY-041 (signed,
//           never floored) · US-PAY-002 TC-1 (a deposit is never credit) ·
//           BR-PAY-031 (Apply now is a reapply: new allocation rows, nothing
//           posted) · BR-PAY-014 (Refund is the one refund path, two people) ·
//           B14 rules 15 · 31 · 33
// ───────────────────────────────────────────────────────
//
// WHAT THE ACCOUNT HOLDS FOR THE CUSTOMER, ONE ROW PER PAYMENT THAT BUILT IT.
//
// Farid Delacroix paid **$170.00 on a $165.00 bill**: the bill was met and the
// books credited **$5.00** to `2400 Customer credit`. The Credits tab listed
// only billing's credit notes, so it said *"No credits"*. This group reads
// `GET /accounts/{id}/credit-sources` — payments' own list, which already
// excludes deposits — and offers the two things a clerk does with that money:
//
//   * **Refund** — the existing raise form (`RaiseRefundModal`), with this
//     account and payment filled in. Nothing is paid out here: a refund is
//     raised, then approved by a second person, exactly as from Refunds.
//   * **Apply now** — the existing reapply (`POST /payments/{id}/reapply`) with
//     `release: []`, so the payment's held part goes onto an open bill and
//     nothing it already meets moves. Disabled, with its reason, while the
//     account has no open bill.
//
// No sum is computed here: `contributed` is the server's figure per row and
// `refundable` its figure for the account (the two diverge after a refund, on
// purpose — `account_credit_sources`' docstring).

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccountCreditSources, reapplyPayment } from "@/api/endpoints";
import type { CreditSourceRow, OpenBillRow } from "@/api/endpoints";
import { DateCell, todayInZone } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { DollarIcon, RollBackIcon } from "@/components/icons";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { PlainTable } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { amountForInput } from "@/features/payments/depositsShared";
import { RaiseRefundModal } from "@/features/payments/RefundsPage";
import { sumDecimalStrings, useOpenBills } from "@/features/payments/paymentsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

const MUTED = "text-neutral-600";

/** The same key `RefundDetailPage` reads, so a refund raised there refreshes this. */
export const heldCreditKey = (accountId: string) =>
  ["payments", "credit-sources", accountId] as const;

/** The smaller of two decimal strings, without a float (hard rule 2). */
export function smallerAmount(a: string, b: string): string {
  const negated = b.startsWith("-") ? b.slice(1) : `-${b}`;
  const diff = sumDecimalStrings([a, negated]);
  return diff !== null && diff.startsWith("-") ? a : b;
}

export function AccountHeldCreditGroup(props: {
  accountId: string;
  accountNo: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
  client?: ApiClient;
}) {
  const { t } = props;
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const toast = useToast();
  const [refunding, setRefunding] = useState<CreditSourceRow | null>(null);
  const [applying, setApplying] = useState<CreditSourceRow | null>(null);
  const query = useQuery({
    queryKey: heldCreditKey(props.accountId),
    queryFn: () => getAccountCreditSources(props.accountId, client),
    retry: false,
    enabled: props.accountId !== "",
  });
  const rows = query.data?.sources ?? [];
  const bills = useOpenBills(props.accountId, client, rows.length > 0);
  const openBills = (bills.data?.bills ?? []).filter(
    (bill) => bill.invoice_id !== null && bill.open_balance !== null,
  );
  const applyBlocked =
    bills.data === undefined
      ? t("customers.account.heldCredit.billsLoading")
      : openBills.length === 0
        ? t("customers.account.heldCredit.noOpenBill")
        : null;

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["payments"] });
    void queryClient.invalidateQueries({ queryKey: ["customers"] });
  }

  const emptyWord = query.isPending
    ? t("customers.account.heldCredit.loading")
    : query.isError
      ? t("customers.account.heldCredit.unreadable")
      : t("customers.account.heldCredit.none");

  return (
    <Panel
      as="section"
      tone="group"
      data-overview-group="held-credit"
      title={t("customers.account.heldCredit.title")}
    >
      <div className="overflow-x-auto">
        <PlainTable>
          <thead>
            <tr>
              <th>{t("customers.account.heldCredit.col.payment")}</th>
              <th>{t("customers.account.heldCredit.col.paidOn")}</th>
              <th>{t("customers.account.heldCredit.col.paid")}</th>
              <th>{t("customers.account.heldCredit.col.held")}</th>
              <th>
                <span className="sr-only">{t("customers.account.heldCredit.col.actions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className={MUTED} data-held-credit-empty="">
                  {emptyWord}
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.payment_id} data-held-credit-row="">
                  <td>{row.payment_no ?? t("payments.row.noNumber")}</td>
                  <td>
                    <DateCell
                      value={row.posted_at}
                      timeZone={props.timeZone}
                      dateFormat={props.dateFormat}
                    />
                  </td>
                  <td className="tabular-nums">
                    <MoneyCell amount={row.amount} currency={row.currency} />
                  </td>
                  <td className="tabular-nums">
                    <MoneyCell amount={row.contributed} currency={row.currency} />
                  </td>
                  <td>
                    <RowActions>
                      <RowAction
                        label={t("customers.account.heldCredit.refund")}
                        icon={<RollBackIcon />}
                        onClick={() => setRefunding(row)}
                      />
                      <RowAction
                        label={t("customers.account.heldCredit.applyNow")}
                        icon={<DollarIcon />}
                        reason={applyBlocked}
                        onClick={() => setApplying(row)}
                      />
                    </RowActions>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </PlainTable>
      </div>
      {refunding !== null && (
        <RaiseRefundModal
          client={client}
          dateFormat={props.dateFormat}
          preset={{
            accountId: props.accountId,
            accountNo: props.accountNo,
            currency: refunding.currency,
            paymentId: refunding.payment_id,
            // DEF-PAY-10771 — the wire carries six places; the box shows 5.00.
            amount: amountForInput(refunding.contributed),
          }}
          onClose={() => setRefunding(null)}
          onRaised={(_creditAfter, _currency, created) => {
            setRefunding(null);
            toast(
              created ? t("payments.refunds.raisedToast") : t("payments.refunds.replayToast"),
            );
            refresh();
          }}
        />
      )}
      {applying !== null && (
        <ApplyHeldCreditModal
          client={client}
          source={applying}
          bills={openBills}
          timeZone={props.timeZone}
          t={t}
          onClose={() => setApplying(null)}
          onApplied={() => {
            setApplying(null);
            toast(t("customers.account.heldCredit.appliedToast"));
            refresh();
          }}
        />
      )}
    </Panel>
  );
}

function applySchema(t: Translator) {
  return z.object({
    invoice_id: z.string().min(1, t("customers.account.heldCredit.billRequired")),
    reason: z.string().trim().min(1, t("customers.account.heldCredit.reasonRequired")),
  });
}

/**
 * Apply ONE payment's held part to ONE open bill.
 *
 * The amount is the smaller of what the payment holds and what the bill still
 * asks — never typed, because the service refuses more than either and a
 * smaller figure would leave a remainder the clerk did not choose.
 */
export function ApplyHeldCreditModal(props: {
  client: ApiClient;
  source: CreditSourceRow;
  bills: readonly OpenBillRow[];
  timeZone: string;
  t: Translator;
  onClose: () => void;
  onApplied: () => void;
}) {
  const { t, source } = props;
  const [invoiceId, setInvoiceId] = useState(props.bills[0]?.invoice_id ?? "");
  const [reason, setReason] = useState("");
  const bill = props.bills.find((one) => one.invoice_id === invoiceId) ?? null;
  const amount =
    bill?.open_balance != null ? smallerAmount(source.contributed, bill.open_balance) : null;

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    if (amount === null) {
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
    try {
      await reapplyPayment(
        source.payment_id,
        {
          targets: [{ invoice_id: invoiceId, amount }],
          // Release NOTHING: only the held part moves; what the payment
          // already meets stays where it is.
          release: [],
          reason: reason.trim(),
          on_date: todayInZone(props.timeZone),
        },
        props.client,
      );
      props.onApplied();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("customers.account.heldCredit.applyTitle")}
      kicker={source.payment_no ?? t("payments.row.noNumber")}
      schema={applySchema(t)}
      values={{ invoice_id: invoiceId, reason }}
      submitLabel={t("customers.account.heldCredit.applySubmit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <SelectField
        id="invoice_id"
        label={t("customers.account.heldCredit.applyTo")}
        value={invoiceId}
        onChange={setInvoiceId}
        options={props.bills.map((one) => ({
          value: one.invoice_id ?? "",
          label: one.number,
        }))}
        required
      />
      {amount !== null && bill !== null && (
        <p className="m-0 text-base" data-apply-amount="">
          {t("customers.account.heldCredit.applies")}{" "}
          <MoneyCell amount={amount} currency={bill.currency ?? source.currency} />
        </p>
      )}
      <TextField
        id="reason"
        label={t("payments.reapply.why")}
        value={reason}
        onChange={setReason}
        required
      />
    </FormModal>
  );
}
