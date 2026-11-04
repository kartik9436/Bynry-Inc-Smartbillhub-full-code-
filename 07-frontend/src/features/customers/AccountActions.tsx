// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-012 (S22 Record payment — the account-side entry point) ·
//           US-CUS-013 (S22 Adjust & Issue credit — DISABLED with their
//           reasons; the billing write paths do not exist) ·
//           US-CUS-014 (S22 Send statement & Print bill — DISABLED with their
//           reasons; no statement renderer, no document route) ·
//           US-CUS-015 (S22 Add note — LIVE; Disconnect notice DISABLED) ·
//           US-CUS-011 (the S21 Notes tab this modal writes into) ·
//           US-PAY-002 (the payment PURPOSE this form could not send until
//           2026-08-15 — bill · deposit · plan-down · prepay)
//           Screens: S21 · S22
// Rules:    BR-CUS-035 (notes: title or body, pinned first, customer_visible
//           captured and INERT in v1) · BR-CUS-037 (an S22 money modal is an
//           ENTRY POINT — it validates, calls the OWNING module's service and
//           audits; customers writes no financial table and no second payment
//           path exists) · BR-CUS-038 (adjustment approval, server-enforced) ·
//           BR-CUS-039 (disconnect tiers) · BR-CUS-040 (statement ≠ bill;
//           a reprint never recomputes) · BR-CUS-059 (autopay is capture-only:
//           enrolment NEVER blocks or auto-substitutes manual recording) ·
//           BR-PAY-001 (the four staff allocation choices; two need a bill
//           picker nothing serves — OQ-154) · BR-PAY-012 (every payment carries
//           a purpose, and each of the four puts the money somewhere else) ·
//           BR-PAY-021 (both dates) ·
//           BR-PAY-028 (one submit token per opened form) · BR-PAY-033 (the
//           posting date is pre-filled and overridable) · BR-SHL-020 (plain
//           language) · BR-SHL-023 (ONE money path) · BR-SHL-025 (a control
//           this deployment cannot honour renders disabled WITH its reason)
// ───────────────────────────────────────────────────────
// The S22 modal family, as this deployment can honour it.
//
// SEVEN MODALS ARE SPECIFIED (EP-CUS-04 §Scope). TWO ARE LIVE. The other five
// are rendered as disabled controls carrying a reason.
//
// ⚠ CORRECTED 2026-09-02 (CR-059 task 8). This paragraph used to read, verbatim:
//
//     "…carrying the server's own reason, and the reasons are DATA
//      (`ACTION_UNAVAILABLE` in `apps/customers/services.py`), not sentences
//      typed here — so the day a billing lane publishes `issue_credit_note`,
//      the reason stops being true in exactly one place."
//
// **THE SERVER'S `ACTION_UNAVAILABLE` NEVER REACHES THIS SCREEN.** No endpoint
// serves it; its only use in the backend is the text of a `NotImplementedError`.
// What this file renders is `reasonKey` below — a translation key resolved out
// of `src/i18n/locales/**`. So the reason does NOT live "in exactly one place":
// it lives in TWO, and on 2026-09-02 they disagreed, because the backend copy
// was corrected and the catalogue string still said the accounting question
// "has not been decided" — a question the PO answered on 2026-08-12. Hard-won
// law 1: a comment claiming a guarantee is not the guarantee, and this one had
// been claiming a wiring that was never built.
//
// The catalogue string is another lane's file this week, so the replacement
// English is REPORTED with this change rather than typed here:
//   customers.account.action.issueCreditBlocked
//     → "Credits are raised on a bill. Open the bill to credit it."
//
// WHY RECORD PAYMENT IS COMPOSED HERE RATHER THAN IMPORTED WHOLE
// ──────────────────────────────────────────────────────────────
// `features/payments` already ships a Record modal (S33) and this screen does
// NOT build a second payment path: it calls the same `recordPayment` wrapper,
// the same `POST /accounts/{id}/payments`, the same BR-PAY-001 allocation
// vocabulary, the same client-side schema and the same result panel — all
// imported from that module. The ONE difference is the account: S33's modal
// opens with a server-side account SEARCH, because a clerk at the payments
// ledger has not chosen one yet. On S21 the account is the page, and offering a
// picker there is a defect waiting to happen — a clerk one mis-click from
// posting a stranger's $247.30.
//
// The clean fix is an optional `account` prop on the payments modal, and
// `07-frontend/src/features/payments/` is another lane's territory in this
// brief, so it is REPORTED rather than edited. What is composed here is the
// FORM, never the money path.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  PAYMENT_PURPOSES,
  createAccountNote,
  getPayments,
  recordPayment,
} from "@/api/endpoints";
import type {
  AccountNote,
  AllocationOrder,
  PaymentMethodOption,
  PaymentPurpose,
  RecordedPayment,
} from "@/api/endpoints";
import type { RegionalDateFormat } from "@/components/DateCell";
import {
  CheckboxField,
  DatePickerField,
  FormModal,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { MoneyCell, formatMoneyInput, isAmountAbsent } from "@/components/MoneyCell";
import { Dash } from "@/features/metering/meteringShared";
import {
  ALLOCATION_CHOICES,
  OpenBillPicker,
  PlanInstallmentStrip,
  choiceNeedsTargets,
  methodOptions,
  reasonOptions,
  targetsBody,
  useAccountPlan,
  useOpenBills,
  useReasonCodes,
} from "@/features/payments/paymentsShared";
import type { BillTargets } from "@/features/payments/paymentsShared";
import { RecordPaymentPanel, recordPaymentSchema } from "@/features/payments/PaymentsPage";
import {
  PossibleDuplicateNotice,
  possibleDuplicateOf,
  useDuplicateWarning,
} from "@/features/payments/PossibleDuplicate";
import type { Translator } from "@/features/tenancy/settingsShared";


import "./customers.css";

// ── The TWO actions this deployment cannot honour (BR-SHL-025) ─────────────

/**
 * The S22 actions with no service behind them, and the i18n key carrying the
 * reason each is disabled.
 *
 * These are keys, not sentences: G19 forbids a hostname in a string and G18
 * requires every key to resolve, and a reason assembled from a server payload
 * would be an untranslated sentence rendered to a Spanish-speaking clerk.
 *
 * Each names WHY, not "coming soon" — a control that says "coming soon"
 * teaches nothing.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ **THIS LIST HELD FIVE UNTIL 2026-09-07 AND THREE OF THEM WERE FALSE**
 * ══════════════════════════════════════════════════════════════════════════
 * `DEF-CUS-4631`. The PO read the account screen and asked why icons were dead
 * (*"in account - view we have all those icons - can you activate them now"*,
 * then *"activate all of them"*). Three of the five were refusing on work that
 * had since been finished, one of them for over three weeks:
 *
 *   · **`issueCredit`** — *"Which account a goodwill credit should be charged
 *     to has not been decided."* `OQ-105` and `OQ-168` both read **CLOSED**,
 *     PO 2026-08-12: *"a separate write-off account"*. `apps.billing.
 *     corrections.credit_only_gl_accounts` has resolved DR write-off / CR
 *     customer credit balance by DESIGNATION ever since, and
 *     `execute_credit_only` posts the pair. `corrections.py`'s own docstring
 *     had already recorded on 2026-09-02 that this very string was one of two
 *     places still quoting the expired reason — and it stayed quoted.
 *   · **`printBill`** — *"Which copy a reprint should show … has not been
 *     decided either."* `OQ-103` and `OQ-169` both read **CLOSED**, PO
 *     2026-08-12: a later reprint renders THE CORRECTED instance and reissues
 *     accumulate. `GET /invoices/{id}/document` is mounted.
 *   · **`disconnectNotice`** — three clauses, all three false. The notice
 *     history HAS a table (`payments.collections_models.NoticeHistory`), the
 *     medical hold HAS a read (`customers.disconnects.medical_hold_for`), and
 *     `OQ-133`, `OQ-136` and `OQ-137` all read **CLOSED**, PO 2026-08-12.
 *
 * They are gone from this list because they are no longer unavailable. The rail
 * now DERIVES those three from facts about the account in front of you — see
 * `accountRailReadiness.ts` — so there is no sentence left to go stale.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ **AND `adjust` LEFT ON 2026-09-13 — THE FOURTH FALSE ONE (`DEF-CUS-5126`)**
 * ══════════════════════════════════════════════════════════════════════════
 * Its sentence was *"Adjustments are billing rows, and billing is not built.
 * There is no endpoint to post one to."* **Every clause of it was false, and it
 * survived the 2026-09-07 sweep above for a reason worth naming: that sweep
 * re-checked each reason against its OPEN QUESTION, and this one names an
 * ENDPOINT instead.** Nobody grepped for one — and a grep would have had to be
 * aimed at the right module, because `billing.Adjustment` really is a table
 * with no writer (`OQ-BIL-12348`) while the CAPABILITY lives in payments:
 * `POST /payments` has taken `type: "adjustment"` with a reason since `CR-059`
 * CS-35 on 2026-09-02, posting DR the reason's own GL account / CR receivables
 * and customer credit, gated on the tenant's approval threshold, and kept out
 * of the deposit batch. So a search for a BILLING adjustment endpoint returns
 * nothing and CONFIRMS the false refusal.
 *
 * `AdjustModal` below is the door. It is the only entry removed from this list
 * that took new code rather than a corrected sentence.
 *
 * ⚠ **`sendStatement` STAYS, AND IT IS THE ONE THAT WAS ALWAYS TRUE.** Nothing
 * in this product renders a statement, and no per-account read can discover
 * that, so it cannot be derived. It carries instead the thing the other three
 * never had and that CLAUDE.md law 2 asks for in the same breath as the hold:
 * a test that FAILS THE DAY THE HOLD LAPSES
 * (`accountRailHoldExpiry.test.ts`).
 *
 * ⚠ **THE SERVER'S TWIN IS `services.ACTION_UNAVAILABLE` AND IT HAD ROTTED
 * INDEPENDENTLY**, in a different way for each entry — its `print_bill` reason
 * said the document route *"is not mounted"* while `config/urls.py` mounted it.
 * Two copies of one fact, corrected on different days by different people, is
 * hard-won law 5; both halves are corrected in this commit.
 */
export const UNAVAILABLE_ACTIONS = [
  {
    id: "sendStatement",
    labelKey: "customers.account.action.sendStatement",
    reasonKey: "customers.account.action.sendStatementBlocked",
  },
] as const;

// ── S22 · Record payment (US-CUS-012) ──────────────────────────────────────

export const accountPaymentMethodsKey = (accountId: string) =>
  ["accounts", "payment-methods", accountId] as const;

/**
 * The tenant's LIVE payment methods (BR-PAY-026), taken off `GET /payments`.
 *
 * `GET /lookups/payment_methods` 404s on this deployment — payments registers
 * no lookup handler, which its own API file reports — so the method vocabulary
 * rides on the payments list response. Asking for one row keeps the trip cheap;
 * the `methods` member does not depend on the page.
 *
 * An empty list renders an empty picker, never the six seeds: empty means the
 * tenant deactivated every method, and offering the seeds back would offer
 * codes the server refuses.
 */
function usePaymentMethods(accountId: string, client: ApiClient) {
  return useQuery({
    queryKey: accountPaymentMethodsKey(accountId),
    queryFn: () => getPayments({ per: 1, filters: { account_id: accountId } }, client),
    retry: false,
  });
}

/**
 * `Adjust` — an amount taken off what this account owes, with a reason.
 *
 * ╔════════════════════════════════════════════════════════════════════════╗
 * ║  THE ENGINE WAS NEVER MISSING. THIS IS A DOOR ONTO IT.                 ║
 * ╚════════════════════════════════════════════════════════════════════════╝
 * `DEF-CUS-5126`. `POST /accounts/{id}/payments` with `type: "adjustment"` has
 * been complete since `CR-059` CS-35 (2026-09-02): it refuses without a reason,
 * refuses above the tenant's `credit_adjustment_approval_threshold_amount`
 * unless the recorder holds System Admin, posts **DR the reason's own GL
 * account / CR receivables for what met bills / CR customer credit for what
 * carried**, writes `audit_log`, and is never swept into a deposit batch. Not
 * one line of that is repeated here — this component chooses nothing about
 * money and nothing about the books.
 *
 * **WHAT IS REUSED RATHER THAN REBUILT:** `FormModal`, `recordPaymentSchema`,
 * `ALLOCATION_CHOICES` + `OpenBillPicker` + `targetsBody` (BR-PAY-001's four
 * staff choices, the same ones `RecordPaymentModal` draws), `useReasonCodes`
 * and `recordPayment` itself. The only thing this file adds is the form.
 *
 * ────────────────────────────────────────────────────────────────────────
 * THREE DIVERGENCES FROM r10's *Post adjustment*, EACH STATED RATHER THAN
 * SILENTLY DROPPED (skill §2.5 / §16 — file it, do not follow it)
 * ────────────────────────────────────────────────────────────────────────
 *   1. **NO GL-ACCOUNT PICKER.** r10 draws a `GL account` select offering
 *      *4100 · Electric Revenue* and two others. The account is DERIVED from
 *      the reason — `CR-008` ruling 9 put `default_gl_account_id` on
 *      `reason_codes` and `CR-066` table 2 (PO 2026-09-02, *"these are all
 *      good - please apply these"*) named which reason goes where. Letting a
 *      clerk pick would be choosing a GL account on a money path, which hard
 *      rule 5 gives to the ledger. B14 rule 37 also applies: the three codes
 *      drawn are an ILLUSTRATION, never a fact to build to.
 *   2. **NO DIRECTION CONTROL.** r10 draws *Credit (reduces balance)* against
 *      *Debit (increases balance)*. **There is no debit path in this product
 *      and building one is not an implementer's call** — increasing what a
 *      customer owes with no document they ever received is exactly what a
 *      one-time bill is for (`BR-BIL-020`: lines come only from rules and
 *      charge codes, *"free-typed amounts never exist on any bill"*). That is
 *      `OQ-BIL-12353`, OPEN. A one-option control is not a control, so the
 *      effect is stated as a FACT instead and the absence sits in the closed
 *      disclosure — B14 rule 32's shape.
 *   3. **NO *Requires supervisor approval* CHECKBOX.** The threshold is
 *      SERVER-enforced and a box a clerk ticks is not an authorisation
 *      (BR-SHL-025). A screen that states an authorisation it does not enforce
 *      is hard-won law 1. The server's own refusal sentence reaches the clerk
 *      through `FormModal` when the amount is over the line.
 *
 * ⚠ **THE MEMO IS NOT THE REASON, AND BOTH ARE SENT.** The reason is a CODE
 * that chooses a ledger account; the memo is what a person typed. `payments`
 * stores the memo on the row and keeps the reason only in `audit_log`, which is
 * pruned (`OQ-1340`) — see `OQ-BIL-12354`. Nothing here may describe either as
 * a permanent record of why.
 */
export function AdjustModal(props: {
  accountId: string;
  accountLabel: string;
  currency: string;
  today: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  onClose: () => void;
  onRecorded: (recorded: RecordedPayment) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;

  const [amount, setAmount] = useState("");
  // A CODE, never a label (B14 rule 31). The server validates it against the
  // same rows this picker was filled from, so the screen cannot offer one the
  // recorder then refuses.
  const [reasonCode, setReasonCode] = useState("");
  const [memo, setMemo] = useState("");
  const [postedAt, setPostedAt] = useState("");
  // BR-PAY-001's four staff choices, unchanged. An adjustment meets open bills
  // exactly as a payment does — CS-35's own sentence, *"the allocation engine
  // needs no change"* — so there is nothing here to decide.
  const [applyTo, setApplyTo] = useState<string>("oldest_first");
  const [targets, setTargets] = useState<BillTargets>({});
  // BR-PAY-028: ONE token per opened form, minted once. Re-minting per submit
  // would dedupe nothing and the server refuses a body without it.
  const [submitToken] = useState(() => crypto.randomUUID());

  const needsTargets = choiceNeedsTargets(applyTo);
  const openBills = useOpenBills(props.accountId, client, needsTargets);
  // Always enabled here: unlike S33's form, every row this modal writes is an
  // adjustment, so a reason is always required.
  const reasonsQuery = useReasonCodes(client, true);
  const reasons = reasonsQuery.data?.reasons ?? [];

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const recorded = await recordPayment(
        props.accountId,
        {
          amount,
          posted_at: postedAt === "" ? props.today : postedAt,
          // An adjustment is granted the moment it is made: there is no bank
          // and nothing to wait for. A `processing` row would meet no bill and
          // count toward no credit position, which is the whole point of it.
          cleared_at: postedAt === "" ? props.today : postedAt,
          // No tender and no reference: nothing arrived. The server leaves
          // `method` nullable for exactly these rows, and a tenderless row
          // cannot be swept into a deposit batch.
          method: null,
          confirmation: null,
          memo: memo === "" ? null : memo,
          type: "adjustment",
          reason: reasonCode || undefined,
          apply_to: applyTo as AllocationOrder,
          targets: needsTargets ? targetsBody(targets) : undefined,
          purpose: "bill",
          idempotency_key: submitToken,
        },
        client,
      );
      props.onRecorded(recorded);
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
      title={t("customers.account.adjust.title")}
      kicker={props.accountLabel}
      // The SAME schema both Record modals use, minus the account this one
      // already has. A second copy could drift from the server's own VAL codes.
      //
      // ⚠ **PLUS THE ONE RULE THAT IS TRUE HERE AND NOT THERE (`DEF-CUS-5167`).**
      // `recordPaymentSchema` is written for a PAYMENT, and a payment carries
      // no reason — `payments.services._reason_code` refuses one by name on a
      // receipt. Every row this form writes is an `adjustment`, and there the
      // same function refuses the row WITHOUT one, because the reason is what
      // chooses the GL account (`CR-008` ruling 9). So the shared schema is
      // correct and incomplete for this one form, and the gap reached a clerk
      // as a server refusal after a form they had already filled in.
      schema={recordPaymentSchema(translate)
        .omit({ account_id: true })
        .extend({ reason: z.string().min(1, t("customers.account.adjust.reasonRequired")) })}
      values={{
        amount,
        posted_at: postedAt === "" ? props.today : postedAt,
        reason: reasonCode,
      }}
      submitLabel={t("customers.account.adjust.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* r10's field order: amount, reason, then where it lands. */}
      <TextField
        id="amount"
        label={t("payments.form.amount")}
        value={amount}
        onChange={(next) => setAmount(formatMoneyInput(next))}
        required
        // B14 rule 33 — a FACT, six words or fewer. It replaces r10's
        // two-option Direction control, which this product has no debit half
        // for (OQ-BIL-12353).
        help={t("customers.account.adjust.effect")}
      />
      <SelectField
        id="reason"
        label={t("payments.form.reason")}
        value={reasonCode}
        onChange={setReasonCode}
        // The tenant's own live list. It is also what chooses the ledger
        // account, which is why it is a picker and not a free-typed note.
        options={reasonOptions(reasons)}
        placeholder={t("payments.form.reasonPlaceholder")}
        // `DEF-CUS-5167` — the server refuses an adjustment without one, so the
        // star was missing from the one field that cannot be left blank.
        required
      />
      <DatePickerField
        id="posted_at"
        label={t("payments.form.postedAt")}
        value={postedAt}
        onChange={setPostedAt}
        prefill={props.today}
        dateFormat={props.dateFormat}
        required
      />
      <SelectField
        id="apply_to"
        label={t("payments.form.applyTo")}
        value={applyTo}
        onChange={(next) => {
          setApplyTo(next);
          // Clearing on every change, exactly as S33's form does: a clerk who
          // picks a bill and then switches to "carry as credit" must not post
          // a target the instruction no longer means.
          setTargets({});
        }}
        options={ALLOCATION_CHOICES.map((choice) => ({
          value: choice.value,
          label: t(choice.labelKey),
        }))}
      />
      {needsTargets && (
        <OpenBillPicker
          t={translate}
          position={openBills.data}
          pending={openBills.isPending}
          failed={openBills.isError}
          mode={applyTo === "split" ? "split" : "specific"}
          targets={targets}
          onTargets={setTargets}
          amount={amount}
        />
      )}
      <TextField
        id="memo"
        label={t("payments.form.memo")}
        value={memo}
        onChange={setMemo}
      />
      {/* B14 rule 32: a stated absence is a disclosure, CLOSED by default. It
          carries the one thing a clerk could otherwise only learn by failing —
          that this form cannot charge somebody MORE — and names what does. */}
      <details>
        <summary>{t("customers.account.adjust.more")}</summary>
        <p>{t("customers.account.adjust.moreBody")}</p>
      </details>
    </FormModal>
  );
}

export function RecordPaymentModal(props: {
  accountId: string;
  accountLabel: string;
  currency: string;
  /** The account's cached balance, as the amount field's default. US-CUS-012
   *  TC-2: pre-filled and EDITABLE, and an autopay-enrolled account behaves
   *  identically (BR-CUS-059 — enrolment never blocks manual recording). */
  balance: string | null;
  today: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  onClose: () => void;
  onRecorded: (recorded: RecordedPayment) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const methodsQuery = usePaymentMethods(props.accountId, client);
  const methods: readonly PaymentMethodOption[] = methodsQuery.data?.methods ?? [];

  // ⚠ **THROUGH THE SHARED FORMATTER, AND THE PRE-FILL IS THE HALF THAT BIT
  // (`DEF-CUS-4999` / `DEF-CUS-5008` — one bug, found twice, 2026-09-12).**
  // This read `props.balance ?? ""`, so the box opened holding the raw served
  // column — `2410.000000` on `A-11812`, `247.300000` on `A-10432` — and a
  // clerk accepting the default SENT six decimals to
  // `POST /accounts/{id}/payments` on the common path. Hard rule 2 (PO re-sign
  // 2026-08-22): *"MOney 4 decimal, percentage 6 decimal , display both 2
  // decimal"*.
  //
  // **THE COLUMN IS NOT THE BUG AND MUST NOT BE "FIXED".** `accounts.balance`
  // is `NUMERIC(18,6)` and hard rule 2 says in terms that *"existing 18,6
  // columns stay lawful containers — the rule governs what is WRITTEN and what
  // new columns declare"*. DRF serving `"2410.000000"` is correct on the wire
  // too. **Only the display half was broken, and only in this file's two
  // lines** — the same figure read `$2,410.00` in the list and in the header,
  // two inches away, through `MoneyCell`.
  const [amount, setAmount] = useState(() => formatMoneyInput(props.balance));
  const [postedAt, setPostedAt] = useState("");
  const [method, setMethod] = useState("");
  // ⛔ `DEF-PAY-10750` (2026-10-30) — no *Clearing date* box. `CR-186-BRC10`
  // (PO 2026-10-21): every payment is `posted` at entry and `cleared` only when
  // its deposit batch is reconciled with the bank, and `record_payment` does
  // not store a `cleared_at` it is sent. `DEF-PAY-10737` took the same box off
  // Record payment (S35); this is its twin on the account screen.
  const [confirmation, setConfirmation] = useState("");
  const [memo, setMemo] = useState("");
  const [applyTo, setApplyTo] = useState("oldest_first");
  // CR-059 CS-4 · task 12 — the bills this payment is aimed at, keyed by the
  // bill's NUMBER. Same state and same component as S33's modal (one control,
  // two screens), because two copies of a money control drift.
  const [targets, setTargets] = useState<BillTargets>({});
  // BR-PAY-012: every payment carries a purpose. This form sent `bill` and
  // nothing else until 2026-08-15, because the service refused the other three
  // by name for linkages that did not exist; `apps/payments/purposes.py` built
  // all three and the form kept sending one value, so a clerk taking a $150.00
  // move-in deposit at the counter had no way to say that is what it was.
  const [purpose, setPurpose] = useState<PaymentPurpose>("bill");
  // BR-PAY-028: ONE token per OPENED form. Re-minting per submit would dedupe
  // nothing while looking as though it had; the server refuses a body without
  // one, which is why this is minted here and not there.
  const [submitToken] = useState(() => crypto.randomUUID());
  // DEF-PAY-9263 — "Looks like a duplicate" (card/ACH), and *Record anyway*.
  const duplicate = useDuplicateWarning();

  // CR-059 CS-4. Read only under a choice that names bills — this screen
  // already knows the account, so there is no "pick an account first" wait.
  const needsTargets = choiceNeedsTargets(applyTo);
  const openBills = useOpenBills(props.accountId, client, needsTargets);
  // CR-059 CS-23 · task 6 — the same strip S33's modal draws, from the same
  // hook and the same component. `null` is the ruled default.
  const [installmentSeq, setInstallmentSeq] = useState<number | null>(null);
  const plan = useAccountPlan(props.accountId, client);

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    // DEF-PAY-9263 — read once: true only when *Record anyway* was pressed.
    const confirmDuplicate = duplicate.takeConfirm();
    duplicate.clear();
    try {
      const recorded = await recordPayment(
        props.accountId,
        {
          ...(confirmDuplicate ? { confirm_duplicate: true } : {}),
          amount,
          posted_at: postedAt === "" ? props.today : postedAt,
          // `DEF-PAY-10750` — never a date: the reconciliation writes the
          // clearing date (CR-186-BRC10). Null keeps the wire explicit.
          cleared_at: null,
          method: method === "" ? null : method,
          confirmation: confirmation === "" ? null : confirmation,
          memo: memo === "" ? null : memo,
          // ⚠ THIS COLLAPSED EVERY CHOICE BUT `carry_credit` INTO
          // `oldest_first` UNTIL 2026-09-02, because two of the four could not
          // be reached. All four are live now (CR-059 CS-4), so the clerk's own
          // instruction travels, and the bills they aimed at travel with it.
          apply_to: applyTo as AllocationOrder,
          targets: needsTargets ? targetsBody(targets) : undefined,
          installment_seq: installmentSeq ?? undefined,
          // BR-PAY-012, sent on every submit including `bill`: this is the
          // field that decides where the money lands, and leaving it implicit
          // would leave the clerk's own choice to a server default.
          purpose,
          idempotency_key: submitToken,
        },
        client,
      );
      props.onRecorded(recorded);
      return { ok: true };
    } catch (error) {
      // DEF-PAY-9263 — nothing was saved; the panel names the earlier one.
      const earlier = possibleDuplicateOf(error);
      if (earlier !== null) {
        duplicate.warn(earlier);
        return { ok: true };
      }
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("payments.form.title")}
      kicker={props.accountLabel}
      // The SAME schema S33's modal uses, minus the account (this one has it).
      // A second copy could drift from the server's own VAL codes.
      schema={recordPaymentSchema(translate).omit({ account_id: true })}
      values={{ amount, posted_at: postedAt === "" ? props.today : postedAt }}
      submitLabel={t("payments.form.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* A2 §S22's first row: Current balance, READ-ONLY. Rendered as the fact
          it is — the CACHED column — because no writer maintains it yet and a
          clerk taking $247.30 against a stale figure needs to know which.

          ⚠ **THIS LINE WAS `${props.balance} ${props.currency}` AND IT IS WHY
          THE DEFECT READ AS DELIBERATE (`DEF-CUS-4999` / `DEF-CUS-5008`).**
          That template is BYTE-IDENTICAL to `formatMoney`'s own fallback for
          an amount it cannot parse (`MoneyCell.tsx`: *"A malformed amount
          renders verbatim with its code"*), so the modal permanently rendered
          the formatter's ERROR path in place of its normal one — and a
          reviewer comparing it against the codebase saw a shape the codebase
          genuinely contains elsewhere. `MoneyCell` is the one path
          (BR-SHL-023) and it reads `$2,410.00`.

          The null branch stays `Dash` rather than `MoneyCell`: DEF-151 made
          that component REFUSE an absent amount, and a caller must ask *"did
          a figure arrive?"* — `isAmountAbsent`, never `=== null` (DEF-176,
          where `undefined` from an omitted key took the money branch and
          killed a whole route). */}
      <p className="kv">
        <span className="kv-k">{t("customers.accounts.col.balance")}</span>
        <span className="kv-v">
          {isAmountAbsent(props.balance) ? (
            <Dash />
          ) : (
            <MoneyCell amount={props.balance} currency={props.currency} />
          )}
        </span>
        <span className="met-qualifier"> {t("customers.account.balanceCached")}</span>
      </p>
      <TextField
        id="amount"
        label={t("payments.form.amount")}
        value={amount}
        onChange={setAmount}
        numeric
        required
        // CLAUDE.md rule 2: the raw string goes to the server, which parses it.
        // Defaulted to the balance (A2: "Amount defaults to balance") and fully
        // editable — TC-2's whole point.
        help={t("customers.account.payment.amountHelp")}
      />
      {/* ══════════════════════════════════════════════════════════════════
          `What this money is for` SITS HERE BECAUSE BOTH DRAWINGS PUT IT HERE
          ══════════════════════════════════════════════════════════════════
          `DEF-CUS-5164`. This control was the LAST field on the form from the
          day it was added (2026-08-15) until 2026-09-13 — past `Apply to`, past
          the memo box, at the foot of the dialog. The accounts blueprint draws
          it SECOND, immediately under `Amount`, in BOTH of its drawings of this
          form: the as-built frame `ACC-A06` (*"one step, eight fields, and it
          commits"*) and R4's redrawn `ACC-Q06`, where it is the second row of
          THE MONEY. B14 rule 41, ratified 2026-09-13: *"layout, grouping,
          ORDER, labels, which facts appear — is the drawing's and is built."*

          ⚠ **AND IT LEAVES THIS FORM ORDERED DIFFERENTLY FROM ITS SIBLING,
          WHICH IS SAID OUT LOUD RATHER THAN DISCOVERED LATER.** `S35`'s Record
          modal (`features/payments/PaymentsPage.tsx`) was reordered on
          2026-09-03 after the PO walked it — *"too much text on the form and Im
          not sure whether inputs are arranged in logical order"* (`DEF-3507`) —
          and its answer was to put `purpose` next to `apply_to` at the END, on
          the reasoning that purpose is the coarse question and apply-to the
          fine one. That fix named `S22` in its own trace header and never
          reached this file. The two orders now agree on everything EXCEPT where
          purpose sits, and that is `DEF-CUS-5164`'s open half: the drawing wins
          here under rule 41, and whether the two forms should be reconciled is
          a question for a person, not for this lane. */}
      <SelectField
        id="purpose"
        label={t("payments.form.purpose")}
        value={purpose}
        onChange={(next) => setPurpose(next as PaymentPurpose)}
        // BR-PAY-012's four purposes, each putting the money somewhere
        // different: `bill` meets the open bills, `deposit` is HELD for the
        // customer and meets no bill and becomes no credit ($150.00 against
        // the deposit position), `plan_down` reduces the arrears its plan
        // spreads ($50.00 off PE-13's 267.30) AND links to the plan, and
        // `prepay` on an account with no open bills carries as credit
        // ($200.00). Each refusal — a deposit on a plan that requires none, a
        // down payment with no live plan — comes back as the SERVER's sentence
        // with its rule id.
        options={PAYMENT_PURPOSES.map((code) => ({
          value: code,
          label: t(`payments.purpose.${code}`),
        }))}
        required
        help={t("payments.form.purposeHelp")}
      />
      <DatePickerField
        id="posted_at"
        label={t("payments.form.postedAt")}
        value={postedAt}
        onChange={setPostedAt}
        prefill={props.today}
        dateFormat={props.dateFormat}
        required
        help={t("payments.form.postedAtHelp")}
      />
      <SelectField
        id="method"
        label={t("payments.form.method")}
        value={method}
        onChange={setMethod}
        options={methodOptions(methods)}
        placeholder={t("payments.form.methodPlaceholder")}
        // BR-CUS-059: the method records how THIS payment arrived. It never
        // implies or schedules a draft, and the note under the field says so —
        // an autopay-enrolled account is recorded here exactly like any other.
        help={t("customers.account.payment.methodHelp")}
      />
      <TextField
        id="confirmation"
        label={t("payments.form.confirmation")}
        value={confirmation}
        onChange={setConfirmation}
        // `DEF-CUS-5165` — the drawn helper, absent from this field since the
        // modal was built. Both drawings of this form carry it verbatim
        // (`ACC-A06`, `ACC-Q06`): it says whose number this is, which is what
        // stops a clerk typing our own payment id into it.
        help={t("customers.account.payment.confirmationHelp")}
      />
      <SelectField
        id="apply_to"
        label={t("payments.form.applyTo")}
        value={applyTo}
        onChange={(next) => {
          setApplyTo(next);
          setTargets({});
        }}
        // ⚠ ALL FOUR ARE LIVE SINCE 2026-09-02 (CR-059 CS-4). The two that were
        // disabled carried the SAME sentence S33 carried — one key rendered
        // twice — and it is deleted with them, from all eleven catalogues.
        options={ALLOCATION_CHOICES.map((choice) => ({
          value: choice.value,
          label: t(choice.labelKey),
        }))}
      />
      {needsTargets && (
        <OpenBillPicker
          position={openBills.data}
          pending={openBills.isPending}
          failed={openBills.isError}
          mode={applyTo === "split" ? "split" : "specific"}
          amount={amount}
          targets={targets}
          onTargets={setTargets}
          t={translate}
        />
      )}
      <PlanInstallmentStrip
        plan={plan.data?.live_plan ?? null}
        pending={plan.isPending}
        unavailable={plan.isError ? "" : (plan.data?.plans_unavailable ?? null)}
        chosenSeq={installmentSeq}
        onChoose={setInstallmentSeq}
        t={translate}
      />
      {/* LAST, as both drawings draw it — `ACC-A06` ends `Apply to · Memo` and
          `ACC-Q06` ends `WHERE IT GOES … Memo`. The helper is the drawn one
          (`DEF-CUS-5165`); it was absent from this field since the modal was
          built, and a memo box with nothing under it reads as a scratch pad
          rather than as something kept. */}
      <TextField
        id="memo"
        label={t("payments.form.memo")}
        value={memo}
        onChange={setMemo}
        help={t("customers.account.payment.memoHelp")}
      />
      {duplicate.earlier !== null && (
        <PossibleDuplicateNotice
          earlier={duplicate.earlier}
          onGoBack={duplicate.clear}
          onRecordAnyway={duplicate.confirmNext}
          submits
        />
      )}
    </FormModal>
  );
}

// ── S22 · Add note (US-CUS-015 TC-4 · BR-CUS-035) ──────────────────────────

export const accountNotesKey = (accountId: string) => ["accounts", "notes", accountId] as const;

/** No client-side rule holds for this form — see the modal's own comment. */
const NO_CLIENT_RULES = z.object({});

export function AddNoteModal(props: {
  accountId: string;
  accountLabel: string;
  client?: ApiClient;
  onClose: () => void;
  onSaved: (note: AccountNote) => void;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [pinned, setPinned] = useState(false);
  const [customerVisible, setCustomerVisible] = useState(false);

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const note = await createAccountNote(
        props.accountId,
        { title, body, pinned, customer_visible: customerVisible },
        client,
      );
      props.onSaved(note);
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
      title={t("customers.account.note.title")}
      kicker={props.accountLabel}
      // AN EMPTY SCHEMA, deliberately. US-CUS-011 TC-7's rule is "title OR
      // body", which is a relation between two fields rather than a per-field
      // constraint, and the SERVER already refuses it naming both fields (B8:
      // the server is authoritative). A zod `superRefine` here would be a
      // second statement of the same rule, free to disagree with it.
      schema={NO_CLIENT_RULES}
      values={{}}
      submitLabel={t("customers.account.note.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* ⚠ **THE HELPER SITS UNDER `Title`, WHICH IS WHERE `ACC-A15` DRAWS IT
          (`DEF-CUS-5166`).** It rendered under `Note` from the day this modal
          was built. The sentence states a rule about the PAIR — one or the
          other will do — and a clerk needs it before they type in the first
          box, not after they have passed it. The string itself did not change;
          only which input it is attached to. */}
      <TextField
        id="title"
        label={t("customers.account.note.field.title")}
        value={title}
        onChange={setTitle}
        help={t("customers.account.note.titleOrBodyHelp")}
      />
      <TextField
        id="body"
        label={t("customers.account.note.field.body")}
        value={body}
        onChange={setBody}
        multiline
      />
      <CheckboxField
        id="pinned"
        label={t("customers.account.note.field.pinned")}
        checked={pinned}
        onChange={setPinned}
      />
      <CheckboxField
        id="customer_visible"
        label={t("customers.account.note.field.customerVisible")}
        checked={customerVisible}
        onChange={setCustomerVisible}
      />
      {/* BR-CUS-035: the flag is CAPTURED and INERT in v1. Said out loud,
          because a clerk who ticks it and believes the customer can read the
          note has been misled by a control that does nothing.

          ⚠ **THE SENTENCE CHANGED ON 2026-09-12 AND THE FLAG DID NOT
          (`DEF-CUS-4998`).** It used to say the flag does nothing *"because
          there is no customer portal in this version"* — and the portal
          shipped, with accounts that sign in. What is STILL true is narrower
          and is what it now says: nothing shows an account note to a customer,
          because no portal screen reads `account_notes` (checked: zero
          references to `AccountNote` anywhere under `apps/portal/`). So the
          reason moved and the refusal stayed.

          ⚠ **AND OUR OWN TEST HAD BEEN REQUIRING THE FALSE SENTENCE** —
          `AccountActions.test.tsx` asserted `toContain("no customer portal")`.
          It now asserts the absence of that claim AND the presence of the true
          one; the negative is the half that cannot rot into a tautology. */}
      <p className="pay-form-note">{t("customers.account.note.customerVisibleInert")}</p>
    </FormModal>
  );
}

// ── S21 · the Notes tab ────────────────────────────────────────────────────
// ⚠ **`NotesTab` LEFT THIS FILE ON 2026-09-13 AND IS NOW
// `AccountNotesTab.tsx`.** `ACC-T11` draws a pinned CARD over a `WHEN ▼ · WHO ·
// KIND · NOTE` table with the shared toolbar and pager (B14 rule 41 — the
// product matches the blueprint), and every one of those is new UI, which
// B14 rule 21 writes in Tailwind utilities. THIS file is styled from
// `customers.css` and is not on `styles/route-b-migrated.txt`, so it cannot
// hold a utility without turning `g31_declared_classes.py` red — the same
// reason the note CARDS moved to `accountDetailTabs.tsx` in August. Nothing
// about a note's rules changed; only where the markup lives.

// ⚠ `isoToday` WAS RE-EXPORTED HERE AND IS DELETED WITH IT (`P0.7`,
// 2026-09-22). It returned the UTC day; the kit's `todayInZone(timeZone)`
// returns the TENANT's, which is what `BR-PAY-033`'s pre-filled posting date
// has to mean. `AccountDetailPage` — this file's only consumer of it —
// already resolves `timeZone` from `useRegional` and now passes that.
export { RecordPaymentPanel };

// ── AMENDED 2026-09-13 by the CR-094-BRC01 lane C build lane ───────────────
// B14 rule 41 — the four panels this screen opens are built to their drawn
// specification, row for row. `ACC-A06` / `ACC-Q06` put `What this money is for`
// SECOND and it was LAST (`DEF-CUS-5164`); both drawings carry a helper under
// `Reference or cheque number` and under `Memo` and neither was on the screen
// (`DEF-CUS-5165`); `ACC-A15` draws the title-or-body sentence under `Title` and
// it rendered under `Note` (`DEF-CUS-5166`). `Adjust`'s `Reason` is required by
// `payments.services._reason_code` and was optional on the form
// (`DEF-CUS-5167`). Nine imports the Notes tab took with it on 2026-09-13 are
// removed (`DEF-CUS-5173`) — they made `eslint --max-warnings 0` red on this
// file and read as nine live dependencies to the next reader.
// conformance: 04-docs/05-modules/03-customers/conformance/CR-094-laneC-header-and-rail-dialogs.md
// gates: RED PROVED FIRST — 7 of 9 new cases failed in a worktree pinned at ffe3a8152, quoted in the conformance file §7 · tsc --noEmit (local 5.5.4, proved able to fail) · eslint --max-warnings 0 · vitest src/features/customers src/features/payments = 13 failed / 1246 passed, the SAME 13 that fail at the clean tip with 1237 · account-dialog-fit.mjs 0 finding(s) over 14 frames · acc02-tab-conformance.mjs TAB=overview 0 divergence(s) · G31 PASS
// exceptions: E3 the four long helper sentences on Record payment are NOT re-worded — three are `payments.form.*` keys shared with S35, where DEF-3507 deliberately moved that copy into a closed `<details>`; re-wording them here would re-word another screen on this one's authority. REPORTED · E3 the dialog sub-line drops the account number the drawing shows (`BRAMBLE BAKERY · A-11812`); `accountHeadline` and the call sites are AccountDetailPage.tsx's, another lane's file. FILED as DEF-CUS-5168, not edited · E3 `purpose` now sits SECOND here and second-to-LAST on S35's twin modal; rule 41 settles it for this screen and the disagreement is DEF-CUS-5164's open half rather than this lane's to reconcile
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-012@f7c1a20 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/03-customers/06-epics/EP-CUS-04-account-actions.md · 04-docs/05-modules/03-customers/06-epics/EP-CUS-05-change-plan.md · 04-docs/05-modules/03-customers/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.6; co-packets US-CUS-013 · US-CUS-014 · US-CUS-015, same four sources)
// generated: 2026-08-11 by story-coder (W4 customers ACTION lane — the S22 modals S21 had been naming in an arrives-with panel)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — screen module) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report — tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔ (G13 unwired-props, G15 i18n-parity across 11 catalogues, G18 call sites, G19 hostnames)
// exceptions: (1) the Record modal is COMPOSED from `features/payments` (the same `recordPayment` wrapper, the same endpoint, the same BR-PAY-001 vocabulary, the same schema and the same result panel) rather than imported whole, because S33's modal opens with an account SEARCH and S21 already knows the account — a picker here is one mis-click from a stranger's payment. The clean fix is an optional `account` prop on the payments modal and that file is another lane's territory: REPORTED, not edited · (2) `specific` and `split` render DISABLED (OQ-154) exactly as they do on S33 — one rule, one reason, two screens · (3) the Add-note modal carries NO client-side schema: "title OR body" is a relation between two fields the server already refuses naming both, and a second statement of it could disagree · (4) FIVE of the seven S22 modals render as disabled controls with their reasons — adjust and issue-credit (no billing write path; OQ-105's reduced form open), send-statement (no statement renderer), print-bill (`GET /invoices/{id}/document` unmounted; OQ-103's sub-question open) and disconnect-notice (`notice_history` has no table; OQ-133/136/137 open). None is a "coming soon": four of the five wait on a decision, not on code
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
// AMENDED 2026-08-24 by the CR-030 W3 lane (B18 §5.2.2 · task 3.10 — the Notes
// tab renders CARDS, not rows):
// exceptions: E2 the note list markup moves to `accountDetailTabs.tsx` and is rendered from here as `<AccountNoteCards>`: r10 draws each note as a PANEL whose head is the title with `date · author` right-aligned, this file shipped a bottom-bordered list that reads as a table (B18 §5.2.2 calls it "a real conformance drift"), and B14 rule 21 puts new UI in Tailwind utilities — which this file, styled from `customers.css`, cannot hold without failing G31. Nothing about a note changed: same rows, same pin control, same BR-SHL-025 reason on it, same OQ-225 sentence beneath
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest (AccountDetailPage.test.tsx TC-ACD-6 — the card, its `date · author` head and its body, and NO `<tr>`/`<td>` in the tab; proved RED by deleting the card marker)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
