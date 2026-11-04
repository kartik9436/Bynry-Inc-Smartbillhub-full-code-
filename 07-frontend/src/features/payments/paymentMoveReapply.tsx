// ── Trace ──────────────────────────────────────────────
// Change:   CR-135 phase 1 · `P1.6` — "Screens for Move and Reapply".
//           Blueprint `05-prototype/06 Payments Page Blueprint.pdf`, §03
//           frames 2·3f (p47) and 2·3g (p48), built from the DRAWING per
//           B14 rule 42 and the PO's instruction of 2026-09-22.
// Rules:    B14 rule 11 (a consequence preview before a commit that writes
//           money) · rule 21 (Tailwind utilities, no stylesheet class) ·
//           rule 31 (no database id is ever a visible value) · rule 32 (one
//           sentence per section) · rule 33 (a fact ≤ 6 words) · rule 38
//           (how a form is BUILT is the UI rules') · rule 43 (a piece of UI
//           is a COMPONENT, importable — not 120 lines inside a page) ·
//           CLAUDE.md hard rule 4 (a correction is NEW ROWS, never an edit)
// Rules:    BR-PAY-865 (a moved payment keeps the ORIGINAL's dates) ·
//           BR-PAY-866 (the destination re-allocates under its OWN rules and
//           that is shown BEFORE anybody confirms) · BR-PAY-867 (refused
//           while the batch is reconciled) · BR-PAY-031 (reapply)
// Tests:    07-frontend/src/features/payments/moveAndReapply.dom.test.tsx
// Impacts:  features/payments/PaymentsPage.tsx (the two row actions that open
//           these) · features/payments/paymentsBulk.tsx (`P1.7` — the bulk
//           bar's dead Reapply comes off in the same change)
// ───────────────────────────────────────────────────────
//
// TWO FINISHED ENGINES THAT NO CLERK COULD REACH.
//
// `POST /payments/{id}/move`, `GET /payments/{id}/move-preview`,
// `POST /payments/{id}/reapply` and `GET /payments/{id}/reapply-plan` have all
// been SERVED since 2026-09-03, and `movePayment`, `getPaymentMovePreview`,
// `reapplyPayment` and `getReapplyPlan` have all been written in
// `api/endpoints.ts` since the same day. **Measured 2026-09-22: outside
// `endpoints.ts` itself, not one of the four was named anywhere in
// `07-frontend/src/`.** That is hard-won law 2 exactly — built is not wired —
// and it passed every check the repo has, because `tsc` is content with an
// exported symbol nobody imports and `G118`, which asks this very question,
// reads only `07-frontend/src/portal/`.
//
// ⚠ **THE DOOR IS THE ROW OVERFLOW, NOT THE BULK BAR, AND THE DRAWING IS
// EXPLICIT ABOUT IT.** Both frames give the same Doors line — *"The row
// overflow on 2·1, and 2·2. 2 doors — there are none today"* — and the
// selection toolbar on p33 says *"Reverse, danger tier, with Refund beside it.
// **Nothing else on the bar**"*, with Reapply and Send receipts *"off the bar
// entirely"*. A move and a reapply are acts on ONE payment: they name a
// destination account or a specific bill, and neither question has an answer
// for fifty ticked rows at once.
//
// ⚠ **THE CONSEQUENCE BOX IS THE RULE AND NOT A COURTESY.** BR-PAY-866 is in
// two binding halves — the destination re-allocates under its own rules, *"and
// that is correct and **must be shown before confirming**"*. So neither form
// composes its own arithmetic: the preview route does the sums and this file
// renders the sentences. The one thing computed here is which of the served
// figures to put in which sentence.

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ConsequenceBox } from "@/components/ConsequenceBox";
import { todayInZone } from "@/components/DateCell";
import { formatMoney } from "@/components/MoneyCell";
import {
  FormModal,
  SelectField,
  TextField,
  type FormSubmitOutcome,
  type Translator,
} from "@/components/FormModal";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { formErrorEnvelope, isApiError, type ApiClient } from "@/api/client";
import {
  getPaymentMovePreview,
  getReapplyPlan,
  movePayment,
  reapplyPayment,
  type PaymentMovePreview,
  type PaymentRow,
  type ReapplyPlan,
  type ReappliedPayment,
  type TransferredMoney,
} from "@/api/endpoints";
import {
  AccountPickerFields,
  Money,
  ProblemList,
  sumDecimalStrings,
  useAccountSearch,
  useOpenBills,
} from "./paymentsShared";

// ── Shared between the two frames ──────────────────────────────────────────

/**
 * The server's refusal, as a sentence the clerk can act on.
 *
 * BR-PAY-867's refusal arrives as a 422 and the drawing renders it as a
 * sentence, never a toast: *"a move is REFUSED while the deposit batch is
 * reconciled … that refusal is a 422 the screen renders as a sentence, not an
 * error toast"* (`api/endpoints.ts`). `FormModal` already owns the field-error
 * slot; this is what a caller hands back for the ones that are not a field.
 */
function submitFailure(error: unknown): FormSubmitOutcome {
  if (isApiError(error)) {
    return { ok: false, error: formErrorEnvelope(error) };
  }
  return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
}

/** `PMT-2609-000418 · $158.10` — the kicker both frames draw above the title.
 *
 *  The amount is formatted by the SAME function every money cell in the product
 *  uses, so the kicker and the row it was opened from cannot round differently
 *  (B4.4 half-up, two places on screen). */
function paymentKicker(payment: PaymentRow, t: Translator): string {
  return t("payments.moveReapply.kicker", {
    number: payment.payment_no ?? t("payments.row.noNumber"),
    amount: formatMoney(payment.amount, payment.currency),
  });
}

// ══════════════════════════════════════════════════════════════════════════
// 2·3f — MOVE THIS PAYMENT
// ══════════════════════════════════════════════════════════════════════════

/**
 * WHY a payment is being moved, as the drawing draws it: a select, defaulting
 * to the reason nearly every move has.
 *
 * ⚠ **`other` IS PART OF THE CONTROL AND NOT AN AFTERTHOUGHT.** The service
 * takes `reason` as REQUIRED FREE TEXT and no vocabulary has ever been ruled,
 * so a closed list of four would NARROW what a clerk may record — and hard
 * rule 4 makes the audit row the only durable record of why a customer's money
 * moved between two accounts. A select that cannot say what happened is a fold
 * that did not carry every act (`DEF-PAY-6199`'s shape). So the drawn select
 * ships, and its last option opens a box.
 */
const MOVE_REASONS = ["wrong_account", "their_other_account", "customer_asked", "other"] as const;
type MoveReasonId = (typeof MOVE_REASONS)[number];

/** The reason the drawing shows the select resting on. */
const MOVE_REASON_DEFAULT: MoveReasonId = "wrong_account";

function moveReasonSchema(t: Translator) {
  return z.object({
    account_id: z.string().min(1, t("payments.move.destinationRequired")),
    // Only the free-text box is validated here; the select cannot be empty.
    reason_text: z.string(),
  });
}

/**
 * What the clerk is sending as `reason` — the chosen sentence, or their own
 * words when they chose `other`.
 *
 * It is the TRANSLATED sentence rather than a code, deliberately: the audit row
 * is read by a person at this utility, in the language this utility works in,
 * and a code the service has never heard of would be less use there, not more.
 */
export function moveReasonText(
  reason: MoveReasonId,
  typed: string,
  t: Translator,
): string {
  return reason === "other" ? typed.trim() : t(`payments.move.reason.${reason}`);
}

/**
 * `reopens_on_source` carries an `invoice_id` and NO bill number, which B14
 * rule 31 forbids putting on screen. The drawing answers the same question one
 * level up and in the customer's terms — *"Ana Alvarez owes $158.10 again"* —
 * so what this needs off the preview is the TOTAL, not the list.
 */
export function reopensTotal(preview: PaymentMovePreview): string | null {
  return sumDecimalStrings(preview.reopens_on_source.map((entry) => entry.amount));
}

export function MovePaymentModal(props: {
  client: ApiClient;
  payment: PaymentRow;
  /** The tenant's own zone. `moved_on` is a business day, never a clock (G6). */
  timeZone: string;
  onClose: () => void;
  onMoved: (result: TransferredMoney) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { payment } = props;

  const [term, setTerm] = useState("");
  const [accountId, setAccountId] = useState("");
  const [reason, setReason] = useState<MoveReasonId>(MOVE_REASON_DEFAULT);
  const [reasonText, setReasonText] = useState("");
  const [approval, setApproval] = useState("");
  const [submitToken] = useState(() => crypto.randomUUID());

  const search = useAccountSearch(term, props.client, "move-destination");

  // ⚠ THE PREVIEW IS READ ONLY ONCE A DESTINATION EXISTS, because the route
  // takes one: `GET /payments/{id}/move-preview?to=`. Until then the box is
  // absent rather than empty — an empty consequence box is a promise that the
  // screen has looked and found nothing to say, which is not true yet.
  const preview = useQuery({
    queryKey: ["payments", "move-preview", payment.id, accountId],
    queryFn: () => getPaymentMovePreview(payment.id, accountId, props.client),
    enabled: accountId !== "",
    retry: false,
  });

  const plan = preview.data;
  const reopens = plan === undefined ? null : reopensTotal(plan);

  // The service, not this screen, decides whether an approval is wanted: only
  // it knows whether a bill re-opens or a closed month is touched.
  const approvalWanted = plan?.approval_required === true;

  useEffect(() => {
    // A new destination is a new question, so a note typed against the old
    // answer does not travel with it.
    setApproval("");
  }, [accountId]);

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    const why = moveReasonText(reason, reasonText, translate);
    if (why === "") {
      return { ok: false, error: { code: "", message_key: "payments.move.reasonRequired" } };
    }
    try {
      const result = await movePayment(
        payment.id,
        {
          to_account_id: accountId,
          reason: why,
          moved_on: todayInZone(props.timeZone),
          approval: approvalWanted ? approval : null,
          idempotency_key: submitToken,
        },
        props.client,
      );
      props.onMoved(result);
      return { ok: true };
    } catch (error) {
      return submitFailure(error);
    }
  }

  return (
    <FormModal
      title={t("payments.move.title")}
      kicker={paymentKicker(payment, translate)}
      schema={moveReasonSchema(translate)}
      values={{ account_id: accountId, reason_text: reasonText }}
      submitLabel={t("payments.move.submit")}
      // B14 rule 6: a move writes a reversal on one account and a new payment
      // on another, and moving it back is a SECOND move carrying its own date
      // — so it is not undone by repeating it. `MoveUnitModal` took the danger
      // tier for the same reason.
      submitVariant="danger"
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* ① WHERE IT IS NOW — the drawing's first note, "because the whole act
          is a comparison". Without it the clerk is asked to choose a
          destination with the source nowhere on screen. */}
      <Note data-where-it-is-now="">
        {t("payments.move.whereItIsNow", {
          account: payment.account_no ?? t("payments.row.noAccountNo"),
          customer: payment.customer_name ?? t("payments.row.noCustomer"),
        })}
      </Note>

      <AccountPickerFields
        searchLabel={t("payments.move.moveTo")}
        accountLabel={t("payments.move.destination")}
        term={term}
        onTermChange={setTerm}
        search={search}
        value={accountId}
        onChange={setAccountId}
        t={translate}
      />

      <SelectField
        id="reason"
        label={t("payments.move.why")}
        value={reason}
        onChange={(value) => setReason(value as MoveReasonId)}
        options={MOVE_REASONS.map((code) => ({
          value: code,
          label: t(`payments.move.reason.${code}`),
        }))}
      />
      {reason === "other" && (
        <TextField
          id="reason_text"
          label={t("payments.move.reasonOwnWords")}
          value={reasonText}
          onChange={setReasonText}
          required
        />
      )}

      {/* ② BOTH SIDES — "a move changes two accounts and the screen says
          both" (B14 rule 11). Every figure is the SERVER's. */}
      {preview.isPending && accountId !== "" && (
        <Note>{t("payments.move.previewLoading")}</Note>
      )}
      {preview.isError && <RefusalStrip>{t("payments.move.previewFailed")}</RefusalStrip>}
      {plan !== undefined && (
        <ConsequenceBox
          tone="check"
          tag={t("payments.moveReapply.check")}
          data-consequence="move"
          title={
            reopens === null
              ? t("payments.move.owesAgainUnknown", {
                  customer: payment.customer_name ?? t("payments.row.noCustomer"),
                })
              : t("payments.move.owesAgain", {
                  customer: payment.customer_name ?? t("payments.row.noCustomer"),
                  amount: formatMoney(reopens, payment.currency),
                })
          }
          body={t("payments.move.destinationMet")}
        />
      )}

      {/* The approval BR-PAY-011 asks for, and only when the SERVICE asked.
          This side never predicts it. */}
      {approvalWanted && (
        <TextField
          id="approval"
          label={t("payments.move.approval")}
          value={approval}
          onChange={setApproval}
          help={t("payments.move.approvalHelp")}
          required
        />
      )}

      {plan !== undefined && plan.problems.length > 0 && (
        <ProblemList problems={plan.problems} title={t("payments.move.problems")} />
      )}
    </FormModal>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 2·3g — REAPPLY THIS PAYMENT
// ══════════════════════════════════════════════════════════════════════════

/** The drawn choice above the bill table. `specific` is what the frame rests
 *  on; `credit` leaves the money on the account instead of on a bill. */
const REAPPLY_CHOICES = ["specific", "credit"] as const;
type ReapplyChoice = (typeof REAPPLY_CHOICES)[number];

function reapplySchema(t: Translator) {
  return z.object({
    targets: z.array(z.string()).min(1, t("payments.reapply.targets_required")),
    reason_text: z.string().min(1, t("payments.reapply.reason_required")),
  });
}

/**
 * What the reapply will DO, in the drawing's two sentences.
 *
 * ⚠ **BOTH FIGURES COME OFF THE PLAN AND THE PICKED BILLS, AND NEITHER IS A
 * BALANCE THIS SCREEN COMPUTED.** `meets` is what the payment currently holds
 * down (served, NET of every mirror row) and `open_balance` is what a bill asks
 * for (served). The one arithmetic here is the SMALLER of the two — how much of
 * this payment a bill can absorb — which is a fact about the form and not about
 * the account, exactly as `remainingToAllocate` is.
 */
export function reapplyOutcome(
  plan: ReapplyPlan | undefined,
  picked: readonly string[],
): { releasedTotal: string | null; releasedNames: string[] } {
  if (plan === undefined) {
    return { releasedTotal: null, releasedNames: [] };
  }
  // Every bill the payment meets today is released, because that is what this
  // screen sends: `release` omitted means "every bill it currently meets".
  const kept = new Set(picked);
  const released = plan.meets.filter((bill) => !kept.has(bill.invoice_id));
  return {
    releasedTotal: sumDecimalStrings(released.map((bill) => bill.amount)),
    // B14 rule 31 — a bill with no readable number is NAMED as one, never
    // printed as its id.
    releasedNames: released.map((bill) => bill.invoice_number ?? ""),
  };
}

export function ReapplyPaymentModal(props: {
  client: ApiClient;
  payment: PaymentRow;
  timeZone: string;
  onClose: () => void;
  onReapplied: (result: ReappliedPayment) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { payment } = props;

  const [choice, setChoice] = useState<ReapplyChoice>("specific");
  const [picked, setPicked] = useState<readonly string[]>([]);
  const [reasonText, setReasonText] = useState("");

  // WHAT IT MEETS NOW — "the before, because a reapply is a swap". It is read
  // unconditionally: the modal cannot draw its first line without it.
  const plan = useQuery({
    queryKey: ["payments", "reapply-plan", payment.id],
    queryFn: () => getReapplyPlan(payment.id, props.client),
    retry: false,
  });

  // WHERE IT COULD GO — the account's open position, which is the same read
  // the Record modal's bill picker makes, through the same hook.
  const bills = useOpenBills(payment.account_id, props.client, choice === "specific");

  const meetsNow = useMemo(() => {
    const first = plan.data?.meets[0];
    return first?.invoice_number ?? null;
  }, [plan.data]);

  const outcome = reapplyOutcome(plan.data, picked);

  function toggle(invoiceId: string) {
    setPicked((current) =>
      current.includes(invoiceId)
        ? current.filter((id) => id !== invoiceId)
        : [...current, invoiceId],
    );
  }

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const result = await reapplyPayment(
        payment.id,
        {
          // `amount` is the payment's own: a reapply moves ONE payment's money,
          // and the service refuses a target sum that is not it.
          targets: picked.map((invoiceId) => ({
            invoice_id: invoiceId,
            amount: payment.amount,
          })),
          // Omitted = every bill it currently meets, which is the ordinary case
          // and what this screen sends (see `ReapplyPaymentBody.release`).
          release: null,
          reason: reasonText.trim(),
          on_date: todayInZone(props.timeZone),
        },
        props.client,
      );
      props.onReapplied(result);
      return { ok: true };
    } catch (error) {
      return submitFailure(error);
    }
  }

  const openBills = bills.data?.bills ?? [];

  return (
    <FormModal
      title={t("payments.reapply.title")}
      kicker={paymentKicker(payment, translate)}
      schema={reapplySchema(translate)}
      values={{ targets: picked, reason_text: reasonText }}
      submitLabel={t("payments.reapply.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* ① WHAT IT MEETS NOW. */}
      {plan.isPending && <Note>{t("payments.reapply.planLoading")}</Note>}
      {plan.isError && <RefusalStrip>{t("payments.reapply.planFailed")}</RefusalStrip>}
      {plan.data !== undefined && (
        <Note data-meets-now="">
          {meetsNow === null
            ? t("payments.reapply.meetsNothing")
            : t("payments.reapply.meetsNow", { bill: meetsNow })}
        </Note>
      )}

      <SelectField
        id="apply_to"
        label={t("payments.reapply.applyTo")}
        value={choice}
        onChange={(value) => {
          setChoice(value as ReapplyChoice);
          setPicked([]);
        }}
        options={REAPPLY_CHOICES.map((code) => ({
          value: code,
          label: t(`payments.reapply.choice.${code}`),
        }))}
      />

      {choice === "specific" && (
        <>
          {bills.isPending && <Note>{t("payments.openBills.loading")}</Note>}
          {bills.isError && <RefusalStrip>{t("payments.openBills.failed")}</RefusalStrip>}
          {bills.data !== undefined && openBills.length === 0 && (
            <Note>{t("payments.reapply.noOpenBills")}</Note>
          )}
          {openBills.length > 0 && (
            <table className="w-full border-collapse text-base">
              <thead>
                <tr className="border-b border-divider text-left text-xs uppercase tracking-wide">
                  <th scope="col" className="w-8 py-2" />
                  <th scope="col" className="py-2 font-semibold">
                    {t("payments.reapply.col.bill")}
                  </th>
                  <th scope="col" className="py-2 font-semibold">
                    {t("payments.reapply.col.issued")}
                  </th>
                  <th scope="col" className="py-2 text-right font-semibold">
                    {t("payments.reapply.col.total")}
                  </th>
                  <th scope="col" className="py-2 text-right font-semibold">
                    {t("payments.reapply.col.owesNow")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {openBills.map((bill) => (
                  <tr key={bill.number} className="border-b border-divider">
                    <td className="py-2">
                      <input
                        type="checkbox"
                        // The ACCESSIBLE NAME is the bill NUMBER, never the id
                        // (B14 rule 31), which is also what a walkthrough and a
                        // screen reader both find this row by.
                        aria-label={bill.number}
                        checked={bill.invoice_id !== null && picked.includes(bill.invoice_id)}
                        disabled={bill.invoice_id === null}
                        onChange={() => bill.invoice_id !== null && toggle(bill.invoice_id)}
                      />
                    </td>
                    <td className="py-2">{bill.number}</td>
                    <td className="py-2">
                      {bill.issued_on ?? t("payments.openBills.noIssueDate")}
                    </td>
                    {/* A figure that could not be read is a STATED ABSENCE and
                        never a zero — `OpenBillPicker` answers the same two
                        cells the same way, with the same two keys. */}
                    <td className="py-2 text-right">
                      {bill.total === null ? (
                        t("payments.openBills.noFigure")
                      ) : (
                        <Money amount={bill.total} currency={bill.currency} />
                      )}
                    </td>
                    <td className="py-2 text-right">
                      {bill.open_balance === null ? (
                        t("payments.openBills.noFigure")
                      ) : (
                        <Money amount={bill.open_balance} currency={bill.currency} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {/* ② BOTH BILLS MOVE — "stated as two facts, six words each". */}
      {picked.length > 0 && outcome.releasedTotal !== null && (
        <ConsequenceBox
          tone="check"
          tag={t("payments.moveReapply.check")}
          data-consequence="reapply"
          title={t("payments.reapply.reopensAt", {
            bill: outcome.releasedNames[0] || t("payments.reapply.thatBill"),
            amount: formatMoney(outcome.releasedTotal, payment.currency),
          })}
          body={t("payments.reapply.othersMeet")}
        />
      )}

      {/* The service REFUSES a reapply with no reason, so the marker is the
          rule and not a house style. */}
      <TextField
        id="reason_text"
        label={t("payments.reapply.why")}
        value={reasonText}
        onChange={setReasonText}
        required
      />

      {plan.data !== undefined && plan.data.problems.length > 0 && (
        <ProblemList problems={plan.data.problems} title={t("payments.reapply.problems")} />
      )}
    </FormModal>
  );
}
