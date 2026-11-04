// ── Trace ──────────────────────────────────────────────
// Change:   CR-163-BRC10 item 2 (lane NC-B, 2026-10-02) — *"Add fees after
//           submission, until approval: pick a one-time charge code, qty,
//           amount (price from the charge code where it has one)"*.
// Rules:    CLAUDE.md hard rule 4 (the server raises a NEW issued bill; the
//           quote is never edited) · hard rule 2 (nothing here multiplies or
//           rounds — the server prices) · hard rule 3 (a count travels with
//           what it counts) · BR-BIL-020 (a figure is typed only for a code
//           priced "entered when used") · BR-BIL-024 (the clerk picks the terms;
//           none is defaulted) · B14 rules 7, 31, 33, 43, 44
// Tests:    src/features/work/buildRecord/BuildAddFeeDialog.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PRICE SHOWN IS THE CATALOGUE'S OWN DISPLAY STRING, READ ONLY.** A
// code that states its price is charged at that price times the count, and
// BILLING multiplies (`fee_bill.charge_code_line`); this form never shows a
// product it computed. A code priced *entered when used* takes the clerk's
// amount for the whole case, and no count.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCharges } from "@/api/endpoints";
import type { ChargeRow } from "@/api/endpoints";
import { todayInZone } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { startingAmount } from "@/components/moneyMath";
import type { Translator } from "@/features/customers/newConnectShared";

import { addConnectionFee } from "../workEndpoints";

/** A code this door can raise: a FLAT price, or *entered when used*, and a GL
 *  account either way (billing refuses a code with none before it spends a
 *  number). The same reading `NewConnectChargesStep.canBeRaisedOnItsOwn` takes
 *  for flat codes, widened by the one rule billing's single-code door honours. */
export function canBeAddedAfterSubmission(row: ChargeRow): boolean {
  // Item 2: "a one-time charge code" — never a recurring base or a penalty.
  if (row.gl_account_id === null || row.charge_type !== "one_time") {
    return false;
  }
  const rule = row.amount_rule ?? "flat";
  return (rule === "flat" && row.amount !== null) || rule === "per_case";
}

export const FEE_BASES = ["per unit", "per meter", "per premise"] as const;
export const FEE_TERMS = ["7", "15", "30", "60", "90"] as const;

const FEE_SCHEMA = z
  .object({ code: z.string().min(1), date: z.string().min(1), terms: z.string().min(1) })
  .passthrough();

export interface AddFeeChoice {
  code: string;
  perCase: boolean;
  quantity: string;
  basis: string;
  amount: string;
  date: string;
  terms: string;
}

/** The posted body — exported so a test asserts what TRAVELS. Money and counts
 *  stay strings (hard rule 2); a priced code sends no amount at all. */
export function addFeeBody(choice: AddFeeChoice) {
  return choice.perCase
    ? {
        charge_code: choice.code,
        amount: choice.amount.trim(),
        posting_date: choice.date,
        due_days: Number(choice.terms),
      }
    : {
        charge_code: choice.code,
        quantity: choice.quantity.trim(),
        basis: choice.basis,
        posting_date: choice.date,
        due_days: Number(choice.terms),
      };
}

export function BuildAddFeeDialog(props: {
  t: Translator;
  connectionId: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  onClose: () => void;
  /** Called with the NEW bill's number once the server has issued it. */
  onAdded: (invoiceNo: string | null) => void;
}) {
  const { t } = props;
  const client = props.client ?? api;
  const [code, setCode] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [basis, setBasis] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");
  const [terms, setTerms] = useState("");

  const charges = useQuery({
    queryKey: ["charges", "active", "add-fee"],
    queryFn: () => getCharges({ per: 200, filters: { status: "active" } }, client),
    retry: false,
  });
  const offered = useMemo(
    () => (charges.data?.results ?? []).filter(canBeAddedAfterSubmission),
    [charges.data],
  );
  const picked = offered.find((row) => row.code === code) ?? null;
  const perCase = picked !== null && picked.amount_rule === "per_case";

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const made = await addConnectionFee(
        props.connectionId,
        addFeeBody({ code, perCase, quantity, basis, amount, date, terms }),
        client,
      );
      props.onAdded(made.invoice_no ?? null);
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
      title={t("customers.build.fee.title", { defaultValue: "Add fee" })}
      schema={FEE_SCHEMA}
      values={{ code, date, terms }}
      submitLabel={t("customers.build.fee.submit", { defaultValue: "Add fee" })}
      onClose={props.onClose}
      onSubmit={submit}
    >
      <SelectField
        id="build-fee-code"
        label={t("customers.build.fee.charge", { defaultValue: "Charge" })}
        required
        value={code}
        onChange={(next) => {
          setCode(next);
          // DEF-RAT-9807 — an *entered when used* code's amount box starts at
          // its default (`BR-RAT-1054` AMENDED 2026-10-06); blank when it has
          // none. The clerk may change it; what they end with is billed.
          const row = offered.find((one) => one.code === next);
          setAmount(row !== undefined && row.amount_rule === "per_case" ? startingAmount(row.amount) : "");
        }}
        options={[
          { value: "", label: t("customers.build.raise.pick", { defaultValue: "Choose…" }) },
          ...offered.map((row) => ({ value: row.code, label: `${row.code} · ${row.name}` })),
        ]}
      />
      {picked !== null && !perCase && (
        <>
          <TextField
            id="build-fee-each"
            label={t("customers.build.charges.col.each", { defaultValue: "Each" })}
            value={picked.amount_display ?? ""}
            onChange={() => undefined}
            readOnly
            numeric
          />
          <TextField
            id="build-fee-quantity"
            label={t("customers.build.charges.col.qty", { defaultValue: "Qty" })}
            required
            numeric
            value={quantity}
            onChange={setQuantity}
          />
          <SelectField
            id="build-fee-basis"
            label={t("customers.build.fee.basis", { defaultValue: "Counted per" })}
            required
            value={basis}
            onChange={setBasis}
            options={[
              { value: "", label: t("customers.build.raise.pick", { defaultValue: "Choose…" }) },
              ...FEE_BASES.map((one) => ({
                value: one,
                label: t(`customers.build.fee.basis.${one.replace("per ", "")}`, {
                  defaultValue: one,
                }),
              })),
            ]}
          />
        </>
      )}
      {picked !== null && perCase && (
        <TextField
          id="build-fee-amount"
          label={t("customers.build.charges.col.amount", { defaultValue: "Amount" })}
          required
          numeric
          value={amount}
          onChange={setAmount}
        />
      )}
      <DatePickerField
        id="build-fee-date"
        label={t("customers.build.fee.date", { defaultValue: "Posting date" })}
        required
        value={date}
        onChange={setDate}
        prefill={todayInZone(props.timeZone)}
        dateFormat={props.dateFormat}
      />
      <SelectField
        id="build-fee-terms"
        label={t("customers.build.fee.terms", { defaultValue: "Payment terms" })}
        required
        value={terms}
        onChange={setTerms}
        options={[
          { value: "", label: t("customers.build.raise.pick", { defaultValue: "Choose…" }) },
          ...FEE_TERMS.map((days) => ({
            value: days,
            label: t("customers.build.fee.inDays", { days, defaultValue: `${days} days` }),
          })),
        ]}
      />
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-163-BRC10 item 2 · decision log 2026-10-02 (`56eb54ba9`)
// generated: 2026-10-02 by lane NC-B
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO — HUMAN-REVIEW-PENDING money path)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
