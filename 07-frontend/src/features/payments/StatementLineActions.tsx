// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-10694 (lockbox audit LBX-05)
//           · DEF-PAY-10785/10786/10787/10788 (P1 a1-3, a2-2, a2-3, P2)
// Rulings:  decision log 2026-10-31 "Twelve open payment questions answered
//           (PO)" — P1 a1-3 · a2-2 · a2-3, P2 = A ·
//           decision log 2026-10-30 "Lockbox audit: what is fixed, what is
//           not, and three answers (PO)" — Q1 = A, batch decision G3 RULED ·
//           2026-10-30 "NSF penalty can be unticked with a reason; a bounce is
//           reversed from three places (PO)" — Q1 (untick with a reason) and
//           Q2 (a) (Match to payment reverses it, in one step)
// Screens:  S38 (Import a statement — the FIX column) · S37's statement
// ───────────────────────────────────────────────────────
// A statement line the bank took OUT gets two actions, and these are the two
// forms behind them. Built as a COMPONENT (B14 rule 43); TWO screens open them:
// the import review's FIX column (`BankImportWizard.tsx`) and, since P2 = A
// (PO 2026-10-31), Reconciliation's *Lines nobody has explained*
// (`ReconciliationStatementPage.tsx`) for a line still unexplained after the
// import. ⚠ This header claimed the second screen from 2026-10-30, when only
// the first imported these forms (DEF-PAY-10788) — a comment is not wiring.
//
//   * **Match to payment** — finds the cheque by amount, cheque number and
//     date. The search opens on the cheque number in the line's own words
//     (P1 a2-3, served as `search_hint`), and the Bank memo is shown
//     pre-filled from the line for the clerk to edit (P1 a2-2, ≤ 60). If it was already reversed by hand the match links to that
//     reversal; if not, it is reversed here, reason *Returned by the bank*,
//     with the NSF fee charged unless the clerk unticks it and says why. The
//     returned amount then moves from the holding account to cash.
//   * **Bank fee** — posts the line to Bank fees against cash, or links it to
//     the fee a Reverse already posted, so one fee is in the books once.
//
// Uses only the kit and stylesheet classes that exist; no Tailwind utility.
import { useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  explainBankFeeLine,
  getFeeCandidates,
  getReturnCandidates,
  matchReturnedLine,
} from "@/api/bankRecEndpoints";
import type { LinePostingResult } from "@/api/bankRecEndpoints";
import { CheckboxField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { MoneyCell } from "@/components/MoneyCell";

import { NsfFeeLine } from "./reverseNsfFee";

/** The facts of the line a form is about — read off the review or the statement. */
export interface MoneyOutLine {
  bank_line_id: string;
  reference: string | null;
  posted_on: string | null;
  amount: string | null;
  /** P1 a2-3 — the cheque number in the line's text (`4102`), served. */
  search_hint?: string | null;
}

/** The reversal service's limit on the Bank memo (LBX-04, `BANK_MEMO_MAX`). */
export const BANK_MEMO_MAX = 60;

/**
 * P1 a1-3 (PO 2026-10-31) — what a matched returned line says it was matched
 * to: `RET1029-01 → Clara Castillo · AC-2026-00003`. The account NUMBER, never
 * an id (B14 rule 31); a part the server could not name is left out rather
 * than drawn blank. Null when neither part is known.
 */
export function matchedToText(
  reference: string | null | undefined,
  customerName: string | null | undefined,
  accountNo: string | null | undefined,
): string | null {
  const whom = [customerName ?? "", accountNo ?? ""].filter((part) => part !== "").join(" · ");
  if (whom === "") {
    return null;
  }
  return reference ? `${reference} → ${whom}` : whom;
}

const PASS = { safeParse: () => ({ success: true as const, data: {} }) } as never;

function unexpected(): FormSubmitOutcome {
  return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
}

function refused(error: unknown): FormSubmitOutcome {
  return isApiError(error) ? { ok: false, error: formErrorEnvelope(error) } : unexpected();
}

function LineFacts(props: { line: MoneyOutLine; currency: string; locale?: string }) {
  const { t } = useTranslation();
  return (
    <p className="pay-resolve-facts">
      <span>
        {t("payments.deposits.col.date")}: {props.line.posted_on ?? ""}
      </span>
      <span>
        {t("payments.col.amount")}:{" "}
        <MoneyCell amount={props.line.amount ?? "0"} currency={props.currency} locale={props.locale} />
      </span>
    </p>
  );
}

/** Match a returned line to its payment — reversing it, once, if nobody has. */
export function MatchReturnForm(props: {
  line: MoneyOutLine;
  currency: string;
  locale?: string;
  client?: ApiClient;
  onClose: () => void;
  onDone: (result: LinePostingResult) => void;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  // P1 a2-3 — opens on the line's cheque number and searches straight away.
  const [search, setSearch] = useState(props.line.search_hint ?? "");
  const [paymentId, setPaymentId] = useState("");
  const [chargeFee, setChargeFee] = useState(true);
  const [waiveReason, setWaiveReason] = useState("");
  // P1 a2-2 — the bank's words, pre-filled from the line, the clerk's to edit.
  const [bankMemo, setBankMemo] = useState((props.line.reference ?? "").slice(0, BANK_MEMO_MAX));

  const candidates = useQuery({
    queryKey: ["payments", "return-candidates", props.line.bank_line_id, search] as const,
    queryFn: () => getReturnCandidates(props.line.bank_line_id, search, client),
    retry: false,
  });
  const rows = candidates.data ?? [];
  const picked = rows.find((row) => row.payment_id === paymentId);
  const reversesNow = picked !== undefined && !picked.already_reversed;

  async function submit(): Promise<FormSubmitOutcome> {
    if (picked === undefined) {
      return {
        ok: false,
        error: { code: "", message_key: "payments.bankrec.payment_required" },
      };
    }
    if (reversesNow && !chargeFee && waiveReason.trim() === "") {
      return {
        ok: false,
        error: { code: "", message_key: "payments.deposits.lines.waiveReasonRequired" },
      };
    }
    if (reversesNow && bankMemo.trim().length > BANK_MEMO_MAX) {
      return {
        ok: false,
        error: { code: "", message_key: "payments.reverse.bankMemoTooLong" },
      };
    }
    try {
      const result = await matchReturnedLine(
        props.line.bank_line_id,
        {
          payment_id: picked.payment_id,
          // BR-TEN-043 — the caller names the moment; the server reads no clock.
          occurred_at: new Date().toISOString(),
          ...(reversesNow && !chargeFee
            ? { nsf_fee_waived: true, nsf_fee_waive_reason: waiveReason.trim() }
            : {}),
          // A link to a hand reversal reverses nothing, so it carries no memo.
          ...(reversesNow ? { bank_memo: bankMemo.trim() } : {}),
        },
        client,
      );
      props.onDone(result);
      return { ok: true };
    } catch (error) {
      return refused(error);
    }
  }

  return (
    <FormModal
      title={t("payments.deposits.lines.matchTitle")}
      kicker={props.line.reference ?? t("payments.deposits.noReference")}
      schema={PASS}
      values={{}}
      submitLabel={t("payments.deposits.lines.matchSubmit")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <LineFacts line={props.line} currency={props.currency} locale={props.locale} />
      <TextField
        id="return_search"
        label={t("payments.deposits.lines.search")}
        value={search}
        onChange={setSearch}
      />
      {candidates.isSuccess && rows.length === 0 ? (
        <p className="pay-absent" role="note">
          {t("payments.deposits.lines.noCandidates")}
        </p>
      ) : (
        <SelectField
          id="payment_id"
          label={t("payments.deposits.lines.payment")}
          value={paymentId}
          onChange={setPaymentId}
          required
          placeholder={t("payments.deposits.lines.paymentPrompt")}
          options={rows.map((row) => ({
            value: row.payment_id,
            // Cheque and account NUMBERS, never an id (B14 rule 31).
            label: [
              row.cheque ?? row.payment_no ?? "",
              row.account_no ?? "",
              row.posted_on,
              row.already_reversed ? t("payments.deposits.lines.alreadyReversed") : "",
            ]
              .filter((part) => part !== "")
              .join(" · "),
          }))}
        />
      )}
      {reversesNow && (
        <>
          <p className="pay-form-note" role="note">
            {t("payments.deposits.lines.reversesNow")}
          </p>
          {/* W2 (`DEF-PAY-10766`, PO 2026-10-30): the fee BEFORE Match ✓ —
              "+$30.00 NSF fee" or that the plan sets none — the Reverse
              dialog's own line and the server's own quote, priced on the
              bank's return date (the line's), which is the date the reversal
              uses. */}
          <NsfFeeLine
            paymentId={picked.payment_id}
            reason="nsf"
            returnedOn={props.line.posted_on ?? ""}
            client={client}
          />
          <TextField
            id="return_bank_memo"
            label={t("payments.reverse.bankMemo")}
            value={bankMemo}
            onChange={setBankMemo}
          />
          <CheckboxField
            id="charge_nsf_fee"
            label={t("payments.deposits.lines.chargeNsf")}
            checked={chargeFee}
            onChange={setChargeFee}
          />
          {!chargeFee && (
            <TextField
              id="nsf_fee_waive_reason"
              label={t("payments.deposits.lines.waiveReason")}
              value={waiveReason}
              onChange={setWaiveReason}
              required
            />
          )}
        </>
      )}
    </FormModal>
  );
}

/** Post the bank's fee line to Bank fees — or link it to a fee already posted. */
export function BankFeeForm(props: {
  line: MoneyOutLine;
  currency: string;
  locale?: string;
  client?: ApiClient;
  onClose: () => void;
  onDone: (result: LinePostingResult) => void;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [linkTo, setLinkTo] = useState("");
  const candidates = useQuery({
    queryKey: ["payments", "fee-candidates", props.line.bank_line_id] as const,
    queryFn: () => getFeeCandidates(props.line.bank_line_id, client),
    retry: false,
  });
  const rows = candidates.data ?? [];

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const result = await explainBankFeeLine(
        props.line.bank_line_id,
        {
          occurred_at: new Date().toISOString(),
          ...(linkTo === "" ? {} : { payment_id: linkTo }),
        },
        client,
      );
      props.onDone(result);
      return { ok: true };
    } catch (error) {
      return refused(error);
    }
  }

  return (
    <FormModal
      title={t("payments.deposits.lines.feeTitle")}
      kicker={props.line.reference ?? t("payments.deposits.noReference")}
      schema={PASS}
      values={{}}
      submitLabel={t("payments.deposits.lines.feeSubmit")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <LineFacts line={props.line} currency={props.currency} locale={props.locale} />
      <p className="pay-form-note" role="note">
        {t("payments.deposits.lines.feePostsTo")}
      </p>
      {rows.length > 0 && (
        <SelectField
          id="fee_link"
          label={t("payments.deposits.lines.feeLink")}
          value={linkTo}
          onChange={setLinkTo}
          placeholder={t("payments.deposits.lines.feeLinkNone")}
          options={rows.map((row) => ({
            value: row.payment_id,
            label: [row.cheque ?? row.payment_no ?? "", row.reversed_on].join(" · "),
          }))}
        />
      )}
    </FormModal>
  );
}
