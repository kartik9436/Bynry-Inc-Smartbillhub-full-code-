// ── Trace ──────────────────────────────────────────────
// Change:   `CR-137-BRC07` `P3.11` — screen **2·3c Add a correction** of
//           `05-prototype/06 Payments Page Blueprint.pdf`, **p042–p043 read AS
//           IMAGES at scale 2.0** (B14 rule 42).
// Screens:  2·3c Add a correction (`PAY-P`) — NEW. *"Half of this exists and it
//           is the half nobody can find."*
// Rules:    B14 rule 4 (`+ Noun` opens a creator — it CREATES a row) · rule 10
//           (required fields carry the asterisk) · rule 11 (a consequence
//           preview) · rule 33 (a CONSEQUENCE ≤ 6 words per sentence, at most
//           two; **RATIONALE is ZERO WORDS**) · rule 43 (a component) ·
//           CLAUDE.md hard rule 4 (satisfied, not circumvented) · hard rules
//           5 and 7
// ───────────────────────────────────────────────────────
// *"The amount is wrong and I cannot edit it. Now what?"*
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THIS IS THE OTHER HALF OF **Edit**, AND HARD RULE 4 IS WHAT SPLITS THEM
// ══════════════════════════════════════════════════════════════════════════
// p036, verbatim: *"**Edit** writes in place, and only ever to `confirmation`,
// `memo` and `method_id` — the entire narrowing granted on 2026-09-02. **+
// Correction** cannot touch the payment at all: an amount that is wrong is
// fixed by a **new row**. **Two controls, because they are two rules**, and a
// clerk shown one control for both will reach for the wrong one."*
//
// So the two sit side by side in 2·2's header and the button grammar says which
// is which: `Edit` writes, `+ Correction` creates (B14 rule 4).
//
// ⚠ **NO NEW ENDPOINT, AND THAT IS WHY THIS IS THE CHEAPEST OF THE THREE.**
// p043: *"Add → the existing record path with `type=adjustment`. **No new
// endpoint is needed**."* An adjustment is already a real thing — a payment
// whose `type` is `adjustment`, written down the same path as any other — so
// the engine, the ledger posting and the audit row are all there. **What was
// missing is a way IN from the payment being corrected**: today a clerk must go
// to the record form, find the account again, and know to change a field called
// Kind.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THIS SCREEN SAYS NOTHING ABOUT HOW LONG ANYTHING SURVIVES. THAT IS THE BUILD
// ══════════════════════════════════════════════════════════════════════════
// The PO ruled on 2026-09-23 that a correction's audit row is pruned like any
// other — *"keep the same rule s; when audit log is delete - it is deleted thats
// okay"* — so **no screen may describe this path as a permanent record of the
// old value, ever.**
//
// **AND THE HONEST BUILD IS SILENCE, NOT A DISCLAIMER.** B14 rule 33 puts
// **RATIONALE at ZERO WORDS ON SCREEN**, and rule 33's own amendment says
// rationale is **REMOVED rather than SHORTENED** — cutting a *why* to six words
// keeps the breach and makes it terser. A retention policy is rationale in its
// purest form. **So a screen that explains retention in order to be honest
// breaks rule 33 while trying to obey the ruling.**
//
// `P3.18` deleted exactly such a disclosure from the Edit path hours before
// this file was written (`CorrectionRetentionNote`, a `<details>` in eleven
// catalogues). **Do not reintroduce it here.** What honesty requires is an
// absence: never claim permanence, and do not explain why.
import { useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPaymentReasonCodes, recordPayment } from "@/api/endpoints";
import type { RecordedPayment } from "@/api/endpoints";
import type { PaymentDetail } from "@/api/paymentDetailEndpoints";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { todayInZone } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { DatePickerField } from "@/components/FormModal";
import { formatMoney } from "@/components/MoneyCell";

import { appliedBills } from "./paymentsShared";

/** A signed decimal STRING — never a float, at any point (hard rule 2). The
 *  minus sign is the whole meaning of this form (p042 ②), so it is explicitly
 *  allowed and `0` is explicitly not: a correction of nothing is not a
 *  correction, it is a form somebody opened and did not fill. */
const SIGNED_AMOUNT = /^-?\d+(\.\d{1,4})?$/;

export function addCorrectionSchema(t: (key: string) => string) {
  return z.object({
    reason_code: z.string().min(1, { message: t("payments.correction.reasonRequired") }),
    amount: z
      .string()
      .regex(SIGNED_AMOUNT, { message: t("payments.correction.amountFormat") })
      .refine((value) => Number(value) !== 0, {
        message: t("payments.correction.amountNonZero"),
      }),
    posted_at: z.string().min(1, { message: t("payments.correction.postedRequired") }),
    why: z.string().trim().min(1, { message: t("payments.correction.whyRequired") }),
  });
}

export interface AddCorrectionModalProps {
  client: ApiClient;
  detail: PaymentDetail;
  timeZone: string;
  locale: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onAdded: (result: RecordedPayment) => void;
}

export function AddCorrectionModal(props: AddCorrectionModalProps) {
  const { t } = useTranslation();
  const { detail } = props;
  const [reasonCode, setReasonCode] = useState("");
  const [amount, setAmount] = useState("");
  const [postedAt, setPostedAt] = useState(() => todayInZone(props.timeZone));
  const [why, setWhy] = useState("");
  // BR-PAY-028: ONE token per opened form, minted once. Re-minting it per
  // submit would dedupe nothing while looking as though it did (hard rule 6).
  const [submitToken] = useState(() => crypto.randomUUID());

  // The tenant's OWN list (BR-TEN-036), never a constant here — it is also what
  // chooses the GL account the adjustment debits, which is why the drawing's
  // *What is wrong* is a picker and not a free-typed note.
  const reasons = useQuery({
    queryKey: ["payments", "reason-codes"],
    queryFn: () => getPaymentReasonCodes(props.client),
    retry: false,
  });

  const bills = appliedBills(detail);
  const singleBill = bills.length === 1 ? bills[0] : null;
  const signed = SIGNED_AMOUNT.test(amount) && Number(amount) !== 0;
  const takesMoneyBack = signed && Number(amount) < 0;

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const result = await recordPayment(
        detail.account_id,
        {
          amount,
          posted_at: postedAt,
          // ⚠ **`adjustment` IS THE WHOLE POINT OF THIS DOOR.** It is what makes
          // the new row a correction rather than a second payment, and it is
          // what the server requires a `reason_code` for.
          type: "adjustment",
          // ⚠ **THE FIELD IS `reason`, NOT `reason_code`** — the body's own
          // docstring records `DEF-PAY-5128`, where this was never sent at all
          // and the type select offered two options that could only ever fail.
          reason: reasonCode,
          // The drawing's *Why* — *"the only record of the reason"* — and the
          // memo is where a payment row keeps a clerk's own words.
          memo: why.trim(),
          purpose: detail.purpose,
          // p042 draws *Apply to · The same bill*. When the payment met exactly
          // one bill that is a real destination and it is named; otherwise the
          // allocator's own default is left to it rather than guessed at here.
          ...(singleBill !== null && singleBill.invoiceNumber !== null
            ? {
                apply_to: "specific" as const,
                targets: [{ invoice_number: singleBill.invoiceNumber }],
              }
            : {}),
          currency: detail.currency,
          idempotency_key: submitToken,
        },
        props.client,
      );
      props.onAdded(result);
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
      kicker={t("payments.correction.kicker", {
        number: detail.payment_no ?? t("payments.row.noNumber"),
      })}
      title={t("payments.correction.title")}
      schema={addCorrectionSchema((key) => t(key))}
      values={{ reason_code: reasonCode, amount, posted_at: postedAt, why }}
      submitLabel={t("payments.correction.submit")}
      /* ⚠ **NOT DANGER TIER, AND THE ABSENCE IS A DECISION.** B14 rule 6's
         subject is the DESTRUCTIVE commit, and the amendment that ratified the
         optional tier is explicit that *"reddening a confirm that is not rule
         6's subject spends the tier's meaning everywhere the tier is true"*.
         A correction CREATES a row and destroys nothing — hard rule 4 is
         satisfied here, not circumvented — so this commits like any other
         creation. `Cancel` next door is danger; the contrast is the signal. */
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* ① **SAID BEFORE ANYTHING ELSE** — p042's own note calls it *"the single
          most misunderstood rule in the module"*. Two sentences at rule 33's
          six-word consequence cap. It is a FACT about what the form does, which
          is something a clerk acts on; it is not an explanation of hard rule 4,
          which would be rationale and belongs in this docstring. */}
      <ConsequenceBox
        tone="check"
        tag={t("payments.correction.notChangedTag")}
        data-consequence="correction-not-changed"
        title={t("payments.correction.notChangedTitle", {
          number: detail.payment_no ?? t("payments.row.noNumber"),
        })}
        body={t("payments.correction.notChangedBody")}
      />

      {/* Account — READ-ONLY, taken from the payment. It is drawn as a field
          rather than as a fact because it is what the new row will be written
          against, and a clerk correcting the wrong account is the one mistake
          this form must make impossible. B14 rule 31: the NUMBER, not the id. */}
      <TextField
        id="correction-account"
        label={t("payments.col.account")}
        value={
          detail.account_no === null
            ? t("payments.row.noAccountNo")
            : `${detail.account_no} · ${detail.customer_name ?? t("payments.row.noCustomer")}`
        }
        onChange={() => undefined}
        readOnly
        help={t("payments.correction.accountHelp")}
      />

      {/* *What is wrong* — the tenant's own reason list. */}
      <SelectField
        id="correction-reason"
        label={t("payments.correction.reason")}
        value={reasonCode}
        onChange={setReasonCode}
        required
        placeholder={t("payments.correction.reasonPlaceholder")}
        options={(reasons.data?.reasons ?? []).map((one) => ({
          value: one.code,
          label: one.name,
        }))}
      />

      {/* ② **SIGNED — *"a correction can go either way, and the sign is the
          whole meaning"*** (p042 ②). The helper is the drawing's own four
          words and it stays at four. */}
      <TextField
        id="correction-amount"
        label={t("payments.correction.amount")}
        value={amount}
        onChange={setAmount}
        required
        help={t("payments.correction.amountHelp")}
      />

      {/* B14 rule 7 — the date INPUT, and `dateFormat` is REQUIRED on it: the
          native picker follows the BROWSER locale, so the tenant's own format
          renders under the field through the one formatting path
          (`BR-SHL-023`). A screen that omitted it would show a clerk in Madrid
          a US date and call it theirs. */}
      <DatePickerField
        id="correction-posted"
        label={t("payments.form.postedAt")}
        value={postedAt}
        onChange={setPostedAt}
        dateFormat={props.dateFormat}
        required
      />

      {/* *Why* — required. ⚠ **THE DRAWN HELPER IS *"This is the only record of
          the reason."* — EIGHT WORDS AGAINST A FACT'S CAP OF SIX (B14 rule
          33).** Rule 38 gives the UI rules the HOW of a form and leaves the
          drawing what it CONTAINS, so the meaning is kept and the sentence is
          cut to the cap. ⚠ **AND IT MUST NEVER GROW INTO A RETENTION
          SENTENCE** — see this file's header. */}
      <TextField
        id="correction-why"
        label={t("payments.correction.why")}
        value={why}
        onChange={setWhy}
        required
        multiline
        help={t("payments.correction.whyHelp")}
      />

      {/* ③ **WHAT THIS WILL DO, IN THE CUSTOMER'S TERMS — B14 rule 11.**
          Drawn as *"Ana Alvarez will owe $8.10 more."* — the customer's
          balance, not the ledger's. It appears only once there is a FIGURE to
          state, because a consequence box with no number in it is furniture. */}
      {signed && (
        <ConsequenceBox
          tone="check"
          tag={t("payments.consequence.tag")}
          data-consequence="correction"
          title={t(
            takesMoneyBack
              ? "payments.correction.consequence.owesMore"
              : "payments.correction.consequence.owesLess",
            {
              customer: detail.customer_name ?? t("payments.row.noCustomer"),
              amount: formatMoney(
                // The SENTENCE is about magnitude — *owes $8.10 more* — and the
                // sign is already carried by which sentence is chosen. Printing
                // `−$8.10` inside *owes … more* would say it twice and read as
                // a double negative.
                amount.startsWith("-") ? amount.slice(1) : amount,
                detail.currency,
                props.locale,
              ),
            },
          )}
          body={
            singleBill !== null && singleBill.invoiceNumber !== null
              ? t("payments.correction.consequence.oneBill", {
                  bill: singleBill.invoiceNumber,
                })
              : t("payments.correction.consequence.noBill")
          }
        />
      )}
    </FormModal>
  );
}
