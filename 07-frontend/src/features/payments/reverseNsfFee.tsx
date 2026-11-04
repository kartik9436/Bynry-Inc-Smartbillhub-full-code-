// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-PAY-10698 (the NSF penalty a bounce never charged) ·
//           DEF-PAY-10699 (LBX-04 — the bank's own words on a reversal)
// Ruling:   PO 2026-10-30 — the fee is added automatically and shown before
//           Confirm; the clerk may untick it WITH a reason; the bank's words
//           are labelled "Bank memo" (≤ 60 characters), one per payment.
// Screens:  S35 Reverse (single) · the Payments list's bulk Reverse
// ───────────────────────────────────────────────────────
/**
 * The NSF penalty line and the Bank memo, shared by the single and the bulk
 * Reverse dialogs so the two cannot come to say different things.
 *
 * ⚠ **EVERY FIGURE IS THE SERVER'S.** `GET /payments/{id}/nsf-fee` is billing's
 * own quote — the account → its unit → that unit's plan → the plan's NSF code
 * — and it is the SAME computation the reversal runs, so "+$30.00 NSF fee"
 * before Confirm is what the fee bill carries. Nothing here adds or prices.
 *
 * Written in Tailwind and listed on `route-b-migrated.txt` in the same commit
 * (B14 rule 21); the two dialogs that use it stay on `payments.css`.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { getNsfFeeQuote } from "@/api/endpoints";
import type { NsfFeeQuote, PaymentRow } from "@/api/endpoints";
import { CheckboxField, TextField } from "@/components/FormModal";
import { formatMoney } from "@/components/MoneyCell";
import type { Translator } from "@/features/tenancy/settingsShared";

/** LBX-04's ceiling, the server's `reversal.BANK_MEMO_MAX`. */
export const BANK_MEMO_MAX = 60;

/** The words for a quote — "+$30.00 NSF fee", or why there is none. */
export function nsfFeeText(quote: NsfFeeQuote | undefined, t: Translator): string {
  if (quote === undefined) {
    return t("payments.reverse.nsfFee.loading");
  }
  if (quote.status === "charged" && quote.amount !== null && quote.currency !== null) {
    return t("payments.reverse.nsfFee.charged", {
      amount: formatMoney(quote.amount, quote.currency),
    });
  }
  switch (quote.status) {
    case "nsf_fee_ambiguous_on_plan":
      return t("payments.reverse.nsfFee.ambiguous");
    case "nsf_fee_no_plan":
      return t("payments.reverse.nsfFee.noPlan");
    case "nsf_fee_cannot_be_priced":
      return t("payments.reverse.nsfFee.cannotPrice");
    default:
      return t("payments.reverse.nsfFee.notSet");
  }
}

/** The quote is asked only for a bounce with a date — the fee is priced on
 *  the bank's return date, and a staff reason charges none. */
function enabledFor(reason: string, returnedOn: string): boolean {
  return reason === "nsf" && returnedOn !== "";
}

export function useNsfFeeQuote(
  paymentId: string,
  reason: string,
  returnedOn: string,
  client: ApiClient,
) {
  return useQuery({
    queryKey: ["payments", "nsf-fee", paymentId, returnedOn],
    queryFn: () => getNsfFeeQuote(paymentId, returnedOn, client),
    enabled: enabledFor(reason, returnedOn),
    retry: false,
  });
}

/** The tick, and — only when it is unticked — the reason it needs. */
export function NsfFeeChoice(props: {
  idPrefix: string;
  charge: boolean;
  onCharge: (value: boolean) => void;
  waiveReason: string;
  onWaiveReason: (value: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      <CheckboxField
        id={`${props.idPrefix}charge_nsf_fee`}
        label={t("payments.reverse.nsfFee.charge")}
        checked={props.charge}
        onChange={props.onCharge}
      />
      {!props.charge && (
        <TextField
          id="nsf_fee_waive_reason"
          label={t("payments.reverse.nsfFee.waiveReason")}
          value={props.waiveReason}
          onChange={props.onWaiveReason}
          required
        />
      )}
    </>
  );
}

/** Single Reverse — one line under the reason: "+$30.00 NSF fee". Asks only
 *  once there is a bounce and a date to price on, so a dialog with no date
 *  asks the server nothing. */
export function NsfFeeLine(props: {
  paymentId: string;
  reason: string;
  returnedOn: string;
  client: ApiClient;
}) {
  if (!enabledFor(props.reason, props.returnedOn)) {
    return null;
  }
  return <NsfFeeLineQuoted {...props} />;
}

function NsfFeeLineQuoted(props: {
  paymentId: string;
  reason: string;
  returnedOn: string;
  client: ApiClient;
}) {
  const { t } = useTranslation();
  const quote = useNsfFeeQuote(props.paymentId, props.reason, props.returnedOn, props.client);
  return (
    <p data-nsf-fee={quote.data?.status ?? "loading"} className="my-2 text-base font-semibold">
      {nsfFeeText(quote.data, (key, params) => t(key, params))}
    </p>
  );
}

/** One payment's fee cell — its own query, mounted only when there is a date. */
function NsfFeeCell(props: { paymentId: string; returnedOn: string; client: ApiClient }) {
  const { t } = useTranslation();
  const quote = useNsfFeeQuote(props.paymentId, "nsf", props.returnedOn, props.client);
  return (
    <td className="py-2" data-nsf-fee={quote.data?.status ?? "loading"}>
      {nsfFeeText(quote.data, (key, params) => t(key, params))}
    </td>
  );
}

/**
 * Bulk Reverse — one row per payment that will run: its number, its own NSF
 * fee, and its own Bank memo (*"one per payment in bulk"*, PO 2026-10-30).
 */
export function BulkNsfFeeTable(props: {
  rows: readonly PaymentRow[];
  reason: string;
  returnedOn: string;
  client: ApiClient;
  chargeFee: boolean;
  memos: Record<string, string>;
  onMemo: (paymentId: string, value: string) => void;
  label: (row: PaymentRow) => string;
}) {
  const { t } = useTranslation();
  const showFee = props.chargeFee && enabledFor(props.reason, props.returnedOn);
  if (props.rows.length === 0) {
    return null;
  }
  return (
    <table className="my-2 w-full border-collapse text-base" data-bulk-nsf-fee="">
      <thead>
        <tr className="border-b border-divider text-left text-xs uppercase tracking-wide">
          <th className="py-2">{t("payments.bulk.col.payment")}</th>
          {showFee && <th className="py-2">{t("payments.bulk.col.nsfFee")}</th>}
          <th className="py-2">{t("payments.bulk.col.bankMemo")}</th>
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row, index) => (
          <tr key={row.id} className="border-b border-divider">
            <td className="py-2">{props.label(row)}</td>
            {showFee && (
              <NsfFeeCell paymentId={row.id} returnedOn={props.returnedOn} client={props.client} />
            )}
            <td className="py-2">
              <TextField
                id={`bank_memo_${index}`}
                label={t("payments.reverse.bankMemo")}
                value={props.memos[row.id] ?? ""}
                onChange={(value) => props.onMemo(row.id, value)}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
