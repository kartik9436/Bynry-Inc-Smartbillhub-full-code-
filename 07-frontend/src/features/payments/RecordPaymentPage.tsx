// ── Trace ──────────────────────────────────────────────
// Defect:   `DEF-PAY-6317` — *Record a payment* was a MODAL where §03 frame
//           2·3a draws a PAGE, and `/:tenant/payments/record/new` was not a
//           route at all. PO, on the deployed build 2026-09-23, with the
//           blueprint open beside the product: ***"record payment is form -
//           not modal"***.
// Change:   `CR-136-BRC07` row `P2.9`'s deferred half. Blueprint
//           `05-prototype/06 Payments Page Blueprint.pdf` **p037–p039**, read
//           as IMAGES at scale 2.0 (B14 rule 42), plus p030 for the list this
//           page is a sibling of and p098 for the screen id.
// Screens:  `S35` — `/:tenant/payments/record/new`
// Rules:    B14 rule 2 (ONE page header) · rule 38 (a FORM is built to our UI
//           rules; the drawing decides what it CONTAINS) · rule 39 (two fields
//           to a row, 20px) · rule 41 (the product matches the drawing) ·
//           rule 43 (a piece of UI is a COMPONENT) · rule 33 (the copy caps) ·
//           rule 21 (Tailwind utilities, no stylesheet class) ·
//           BR-PAY-012 · BR-PAY-021 · BR-PAY-026 · BR-PAY-028 · BR-PAY-033
// Tests:    src/features/payments/recordPaymentPage.dom.test.tsx
//           src/features/payments/recordFormOrder.dom.test.tsx
//           src/features/payments/accountSearch.dom.test.tsx
//           src/features/payments/consequenceOnMoneyForms.dom.test.tsx
//           src/features/payments/cashTotal.dom.test.tsx
// ───────────────────────────────────────────────────────
// *"They are at the window with a cheque."* — p037's own question.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS ONE IS A PAGE AND THE OTHER SEVEN STAY MODALS — p038's TASK box
// ══════════════════════════════════════════════════════════════════════════
// Verbatim: *"It is **nine fields, an open-bill picker and an allocation
// table** — the largest write surface in the module, and the one a counter
// clerk uses dozens of times a shift. A modal cannot be linked, bookmarked or
// returned to after a refresh, and it has no page-head, so B14 rule 2's
// kicker, title and right-aligned actions have nowhere to go."*
//
// And the line that decides the other seven: *"**The split is by size, not by
// taste:** the one long form is a page; Edit, Correction, Cancel, Reverse,
// Move, Reapply and Resend are short and confirmatory, so they stay modals
// over the list you came from. **It needs a route** — there is none today,
// because the form has only ever been a modal."*
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ EVERYTHING IN THIS FILE BELOW THE FRAME CAME FROM `RecordPaymentModal`
// UNCHANGED, AND THAT IS THE DRAWING'S OWN INSTRUCTION
// ══════════════════════════════════════════════════════════════════════════
// p038's annotation, verbatim: *"unchanged from §02 screen 03 everything else
// · nine fields, their order, labels, helpers and the open-bill picker ·
// UNCHANGED from §02 screen 03"*, under a frame header that reads *"NINE
// FIELDS IN THE ORDER THE JSX EMITS THEM"*. **So the drawing is describing
// this code rather than asking it to move**, and the state, the submit body
// and every field below are `RecordPaymentModal`'s to the character — with
// every docstring they carried, because those hold the rulings (`DEF-3507`,
// `DEF-PAY-5128`, `CR-059` CS-4/CS-23/CS-35, the PO's 2026-09-13 field order).
//
// ⚠ **THE MODAL IS GONE, NOT KEPT BESIDE THIS.** p036 states the discipline
// for the same move one frame up — *"leaving both would give the product two
// answers to one question, which is how a figure starts to drift"* — and
// hard-won law 2's mirror is a live component nothing mounts.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ ONE DRAWN DIFFERENCE, DELIBERATELY NOT FOLLOWED, AND IT IS FILED
// ══════════════════════════════════════════════════════════════════════════
// p037 pairs **Method | Reference** on one row and **Kind | Apply to** on the
// next. The JSX emits `type` (Kind) BEFORE `method`, so in a two-column grid
// the pairs come out **Kind | Method** and **Reference | Apply to**.
//
// **The order is NOT changed to match**, for three reasons that agree:
//   1. the drawing says twice that the order is the JSX's and is UNCHANGED;
//   2. `recordFormOrder.dom.test.tsx` pins it, and it pins a PO RULING of
//      2026-09-13 — *the blueprint order, on BOTH screens* — which moved
//      `purpose` under the amount on this form and on `S22`;
//   3. B14 rule 37: a wireframe is an illustration of shape, not a fact to
//      build to, and here it contradicts its own stated rule.
// Recorded rather than silently followed either way.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ ② IS A SEARCHABLE SELECT AND NOT A SEGMENTED CONTROL — p039's GAP box
// ══════════════════════════════════════════════════════════════════════════
// The frame's ② asks for *"Cheque · Cash · Tap and pay as shortcuts, with More
// ▾"* drawn as the kit's `SegmentedField`. **p039 reverses it, dated 2026-09-22
// — *"② was a segmented control until 2026-09-22, and that was a rule 8 breach
// wearing a nicer coat"***: a list of five or more options is searchable, a
// tenant is seeded SIX methods and may add more, and a segmented control can
// neither type-filter nor stop growing sideways. So `method` stays the served
// `SelectField` it already was, and p037's own wireframe draws it that way.
import { useState } from "react";
import type { ReactNode } from "react";

import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { getPayments, recordPayment } from "@/api/endpoints";
import { PAYMENT_PURPOSES, PAYMENT_TYPES } from "@/api/endpoints";
import type {
  AllocationOrder,
  PaymentMethodOption,
  PaymentPurpose,
  PaymentType,
  RecordedPayment,
} from "@/api/endpoints";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { CustomFieldsInput } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import type { RegionalDateFormat } from "@/components/DateCell";
import { todayInZone } from "@/components/DateCell";
import { DatePickerField, FormPage, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { formatMoney } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";
import type { Translator } from "@/features/tenancy/settingsShared";

import { recordPaymentSchema } from "./PaymentsPage";
import { RecordCounterBanner } from "./CounterDoors";
import { PayForRecorded, PayForSeveralForm, PayForSwitch, payForFromState } from "./PayForSeveral";
import type { PayForMode, RecordedTender } from "./PayForSeveral";
import { PossibleDuplicateNotice, possibleDuplicateOf, useDuplicateWarning } from "./PossibleDuplicate";
import {
  ALLOCATION_CHOICES,
  AccountPickerFields,
  MoreAboutPayments,
  OpenBillPicker,
  PAYMENTS_RECORD_ROUTE,
  PlanInstallmentStrip,
  choiceNeedsTargets,
  methodOptions,
  paymentsDisplayCurrency,
  paymentTypeLabel,
  reasonOptions,
  targetsBody,
  useAccountPlan,
  useAccountSearch,
  useOpenBills,
  useReasonCodes,
} from "./paymentsShared";
import type { BillTargets } from "./paymentsShared";

/**
 * **2·3a's form, as a COMPONENT (B14 rule 43).**
 *
 * ⚠ **IT IS A COMPONENT AND NOT 300 LINES INSIDE `RecordPaymentPage` BELOW,
 * BECAUSE A SECOND HOST ALREADY EXISTS IN THE DRAWING.** p053's *My counter*
 * names *"the same form as 2·3a, with the batch already known"*, and p062 and
 * p084 each describe a third and fourth caller (*"2·3a with the barcode
 * filling the account"*, *"2·3a with the account known"*). Rule 43's test is
 * ADDRESSABILITY: a sibling screen that would have to COPY this block is the
 * failure, and it is the failure the PO ruled on — *"make them coponents -
 * dont write stand alone code , engineer it"*.
 *
 * Its props are `RecordPaymentModal`'s exactly, with `onClose` renamed
 * `onCancel` — a page goes BACK somewhere; it does not close.
 */
export function RecordPaymentForm(props: {
  client: ApiClient;
  methods: readonly PaymentMethodOption[];
  today: string;
  dateFormat: RegionalDateFormat;
  /** The tenant's `CHAR(3)`, read off the list response by the page that mounts
   *  this (BR-TEN-042's one-currency lock).
   *
   *  ⚠ **`null` IS A REAL STATE AND IT IS NOT A DEFAULT TO USD.** A brand-new
   *  tenant with issued bills and no payments has no code to read, and printing
   *  a dollar sign on a Canadian utility's money is the defect this screen
   *  already records one component over. When it is null the rule-11 box draws
   *  its sentence without the figure rather than inventing one. */
  currency: string | null;
  /** Where `Cancel` goes. The page hands it the list it came from. */
  onCancel: () => void;
  onRecorded: (recorded: RecordedPayment) => void;
  /** `DEF-PAY-10706` — the *Pay for* switch, drawn under the counter banner
   *  as the approved mock-up draws it. The page passes it; the form only
   *  places it. */
  modeSwitch?: ReactNode;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [accountQuery, setAccountQuery] = useState("");
  const [accountId, setAccountId] = useState("");
  const [amount, setAmount] = useState("");
  const [postedAt, setPostedAt] = useState("");
  const [method, setMethod] = useState("");
  // ⛔ `DEF-PAY-10737` (L2-07, PO 2026-10-30) — the *Clearing date* box is
  // GONE. `CR-186-BRC10` (PO 2026-10-21) made every payment `posted` at entry
  // and `cleared` only when its deposit batch is reconciled with the bank;
  // `services.record_payment` accepts `cleared_at` and DOES NOT STORE IT. The
  // box still asked, so an ACH typed with a clearing date two days ahead read
  // as answered and the field did nothing. (`DEF-PAY-10157`'s cash proposal
  // lived here; `clearingDate.ts` is deleted since `DEF-PAY-10750` took the
  // same box off the account screen's form.)
  const [confirmation, setConfirmation] = useState("");
  const [memo, setMemo] = useState("");
  const [applyTo, setApplyTo] = useState("oldest_first");
  // CR-059 CS-4 · task 12. The bills this payment is AIMED at, keyed by the
  // bill's own number (B14 rule 31 — never its id, which is also not what the
  // API takes). Cleared whenever the choice changes, so a clerk who picks a
  // bill and then switches to "carry as credit" cannot post a target the
  // instruction no longer means.
  const [targets, setTargets] = useState<BillTargets>({});
  // BR-PAY-012: every payment carries a purpose and the default is `bill`.
  // Until 2026-08-15 this form sent `bill` and NOTHING ELSE, because the
  // service refused the other three by name for linkages that did not exist.
  // `apps/payments/purposes.py` built all three, and the form kept sending one
  // value — a clerk taking a $150.00 deposit had no way to say so. Fixed here.
  const [purpose, setPurpose] = useState<PaymentPurpose>("bill");
  // CR-059 CS-35 (task 23). `payment` is the default, so a clerk who never
  // touches this control sends exactly what this form has always sent.
  const [paymentType, setPaymentType] = useState<PaymentType>("payment");
  // DEF-PAY-5128. The server REFUSES a credit or an adjustment carrying no
  // reason, by name, and REFUSES one on a payment — so this is state the type
  // decides, and it is CLEARED when the type goes back to `payment` rather than
  // hidden. A hidden field that keeps posting is how a receipt acquires a
  // giveaway reason that a report then counts.
  const [reasonCode, setReasonCode] = useState("");
  // Named rather than inlined at three call sites: it decides whether the two
  // cash fields are drawn AND whether they are sent, and those must never
  // disagree — a field that is hidden and still posted is the defect this
  // control exists to prevent.
  const isCash = paymentType === "payment";
  // BR-PAY-028: ONE token per opened form, minted once. Re-minting it per
  // submit would dedupe nothing; the server refuses a body without it.
  const [submitToken] = useState(() => crypto.randomUUID());
  // CR-161-BRC10 W5 — the utility's own answers for this payment.
  const [customData, setCustomData] = useState<CustomFieldValues>({});
  // DEF-PAY-9263 — "Looks like a duplicate" (card/ACH), and *Record anyway*.
  const duplicate = useDuplicateWarning();

  // IS-3: the account search is SERVER-side, from two characters, so an empty
  // box does not pull the tenant's whole account list into a select.
  //
  // ⚠ **DEF-3506 — THE GATE AND THE REQUEST NOW READ ONE STRING.** This was
  // `enabled: accountQuery.trim().length >= 2` beside `q: accountQuery`, and a
  // number pasted out of a spreadsheet took its whitespace to the server, where
  // it matched nothing and said nothing. `useAccountSearch` owns both halves —
  // and the three states the screen used to draw as an empty dropdown.
  const accountSearch = useAccountSearch(accountQuery, props.client, "account-picker");

  // CR-059 CS-4. Read only when the choice aims at named bills, and only once
  // an account has been chosen — the position is per account and there is none
  // to read before that.
  const needsTargets = choiceNeedsTargets(applyTo);
  const openBills = useOpenBills(accountId, props.client, needsTargets);
  // CR-059 CS-23 · task 6 — which instalment this payment meets. `null` is the
  // ruled default (the earliest unmet one) and is what every submit sends
  // unless the clerk chose otherwise.
  const [installmentSeq, setInstallmentSeq] = useState<number | null>(null);
  const plan = useAccountPlan(accountId, props.client);
  // DEF-PAY-5128 — read only when a reason is actually needed.
  const reasonsQuery = useReasonCodes(props.client ?? api, !isCash);
  const reasons = reasonsQuery.data?.reasons ?? [];

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    // DEF-PAY-9263 — read once: true only when *Record anyway* was pressed.
    const confirmDuplicate = duplicate.takeConfirm();
    duplicate.clear();
    try {
      const recorded = await recordPayment(
        accountId,
        {
          ...(confirmDuplicate ? { confirm_duplicate: true } : {}),
          amount,
          posted_at: postedAt === "" ? props.today : postedAt,
          // `DEF-PAY-10737` — never a date: the reconciliation writes the
          // clearing date (CR-186-BRC10). Null keeps the wire explicit.
          cleared_at: null,
          // ⚠ GATED ON `isCash`, THE SAME FLAG THAT DRAWS THEM. A credit has no
          // instrument and no bank line, so these go as null even if a value
          // was typed before the type was switched — the state is cleared too,
          // and both together are what stop a hidden field from posting.
          method: isCash && method !== "" ? method : null,
          confirmation: isCash && confirmation !== "" ? confirmation : null,
          memo: memo === "" ? null : memo,
          // CR-059 CS-35 (task 22 accepts it; task 23 is this control). Sent
          // always rather than only when it differs, because the server's own
          // default is `payment` and an explicit type is what makes the request
          // log say which of the three a clerk meant.
          type: paymentType,
          // DEF-PAY-5128. Sent on exactly the condition the field is drawn on —
          // `undefined` on a payment, where the server refuses a reason, and the
          // clerk's choice on a credit or an adjustment, where it requires one.
          // The two must never disagree: a field that is hidden and still posted
          // is the defect this control exists to prevent.
          reason: isCash ? undefined : reasonCode || undefined,
          // ⚠ THIS LINE READ `applyTo === "carry_credit" ? "carry_credit" :
          // "oldest_first"` UNTIL 2026-09-02 — it COLLAPSED the two choices the
          // form could not drive into oldest-first, silently, so a clerk who
          // somehow reached them got the default. All four are drivable now
          // (CR-059 CS-4), so the clerk's own instruction is what is sent.
          apply_to: applyTo as AllocationOrder,
          // `targets[]` only where the instruction names bills. Sending an
          // empty array under `oldest_first` would be a field the allocator has
          // to ignore, and a field a reader has to wonder about.
          targets: needsTargets ? targetsBody(targets) : undefined,
          // CR-059 CS-23. Sent only when the clerk overrode the default: an
          // explicit `null` and an absent field mean the same thing to the
          // server, and sending the default back would make a chosen row and
          // an unchosen one indistinguishable in the request log.
          installment_seq: installmentSeq ?? undefined,
          // BR-PAY-012. Sent on every submit, including `bill` — the server
          // defaults it, and a body that omits the field would leave the
          // clerk's own choice implicit in the one place it decides where the
          // money lands.
          purpose,
          idempotency_key: submitToken,
          // CR-161-BRC10 W5 — always sent from THIS screen, `{}` when empty.
          custom_data: customData,
        },
        props.client,
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
    <FormPage
      schema={recordPaymentSchema(translate)}
      values={{
        account_id: accountId,
        amount,
        posted_at: postedAt === "" ? props.today : postedAt,
      }}
      submitLabel={t("payments.form.submit")}
      onSubmit={handleSubmit}
      onCancel={props.onCancel}
    >
      {/* ══════════════════════════════════════════════════════════════════
          THE ORDER A CLERK WORKS IN — PO ruling 2026-09-03
          ══════════════════════════════════════════════════════════════════
          Verbatim, walking the deployed build: *"too much text on the form and
          Im not sure whether inputs are arranged in logical order"*. The order
          they asked for is the order a counter transaction happens in:

              WHO PAID → HOW MUCH → WHEN → HOW (tender and reference)
                       → WHAT IT IS FOR

          What was here instead: account, amount, both dates, KIND, method,
          reference, "Apply to" and its bill picker, the instalment strip, the
          memo, and the purpose LAST — so the two questions that decide where
          the money lands ("what is this for" and "which bills") sat on either
          side of a free-text box, and the tender sat between the dates and the
          allocation. Nothing is removed by this reorder; four blocks moved.

          ══════════════════════════════════════════════════════════════════
          AND THE COPY BUDGET — B14 rule 32
          ══════════════════════════════════════════════════════════════════
          One sentence per section, and a row never repeats what its own
          control offers. `purposeHelp` restated all four options the select
          beside it already lists; `typeHelp` restated the credit option;
          `methodHelp`, `postedAtHelp` and `clearedAtHelp` each carried a
          second, explanatory sentence. Every one of those sentences is still
          in the DOM — they are in `MoreAboutPayments` at the foot of this
          form, CLOSED. Deleting them would take a fact out of the product;
          leading with them is what the PO objected to. */}

      {/* ── `P2.9` · WHICH BATCH THIS GOES INTO ──────────────────────────
          §03 frame 2·3a note ①: *"Which batch this goes into · a clerk must
          never wonder · NEW"*, drawn ABOVE the first field as
          **"Goes into your counter batch CTR-260921-DW, open since 08:55."**

          ⚠ It states the position and REFUSES NOTHING — `BR-SHL-025` puts the
          check at the endpoint (`P2.23`), and `CR-136-BRC07` §3.4 narrows it
          to the three tenders that pass through hands. See `CounterDoors`. */}
      <RecordCounterBanner
        client={props.client}
        dateFormat={props.dateFormat}
        methodCode={method === "" ? null : method}
      />
      {props.modeSwitch}

      {/* ── WHO PAID ─────────────────────────────────────────────────────── */}
      <AccountPickerFields
        searchLabel={t("payments.form.accountSearch")}
        accountLabel={t("payments.form.account")}
        term={accountQuery}
        onTermChange={setAccountQuery}
        search={accountSearch}
        value={accountId}
        onChange={setAccountId}
        t={translate}
      />

      {/* ── THE PAIRED RUN — B14 RULE 39, AND IT IS **OUR** CALL RATHER THAN
          THE DRAWING'S (rule 38) ────────────────────────────────────────────
          p037 draws these in two columns and so does this, but the reason is
          rule 39's *"TWO FIELDS TO A ROW, 20px between fields in both
          directions"* and not the picture: rule 38 puts side-by-side fields,
          help under an input and the footer's button order in the FORM
          CONSTRUCTION bucket, where B14 and the kit decide and a drawing does
          not. `gap-5` IS that 20px. `AssetEditPage` is the worked precedent.

          ⚠ **WHAT THE FORM CONTAINS IS STILL THE DRAWING'S** — which nine
          fields, their order, their labels, the banner above them and the
          open-bill picker below are all p037–p038's, quoted in this file's
          header.

          The full-width blocks sit OUTSIDE this grid rather than carrying a
          `col-span-2`: the account picker, the memo, the bill picker and its
          allocation table, the instalment strip, the rule-11 box and the
          disclosure are each drawn spanning the page. */}
      <div className="grid grid-cols-2 gap-5 max-md:grid-cols-1" data-record-form-grid="">
        {/* ── HOW MUCH ─────────────────────────────────────────────────────── */}
        <TextField
          id="amount"
          label={t("payments.form.amount")}
          value={amount}
          onChange={setAmount}
          numeric
          required
          // CLAUDE.md rule 2: the raw string goes to the server, which parses it.
          // The second half of this help line — "Nothing here rounds it" — is
          // that rule explained to a clerk, and it is in the disclosure below.
          help={t("payments.form.amountBrief")}
        />
        {/* ── WHAT IT IS FOR ───────────────────────────────────────────────── */}
        {/* ⚠ **SECOND, UNDER THE AMOUNT — PO RULING 2026-09-13, AND IT MOVED
          THIS SCREEN TO MATCH THE ACCOUNT'S.** `purpose` sat ninth here, next
          to `apply_to` at the foot. `DEF-3507` put it there on 2026-09-03,
          after the PO walked this form — *"Im not sure whether inputs are
          arranged in logical order"* — reasoning that purpose is the coarse
          question and apply_to the fine one, so the two should be adjacent.

          ⚠ **THAT FIX NAMED `S22` IN ITS OWN TRACE HEADER AND NEVER REACHED
          `S22`.** The account screen's twin of this form kept the rejected
          shape for TEN DAYS, because this screen had a field-order test and
          that one had none — hard-won law 2's shape exactly: the fix landed,
          the other half of it did not, and every check passed over the gap.
          `CR-094-BRC01` lane C then built `S22` to the BLUEPRINT under B14
          rule 41, which draws this form twice with `purpose` directly under
          the amount. The collision between the PO's own September ruling and
          rule 41 was put to them and ruled: **the blueprint order, on BOTH
          screens.** So the coarse/fine adjacency is deliberately given up — a
          clerk answers *what is this money for* while the amount is still
          under their hand — and `apply_to` moves up beside the bills it
          names. The eight fields the two forms share are now in identical
          relative order, and `recordFormOrder.dom.test.tsx` keeps them there.

      {/* BR-PAY-012's four purposes, and each one puts the money somewhere
          DIFFERENT — which is why this is a field and not a note:
            bill       meets open bills oldest-first; the remainder carries as
                       account credit.
            deposit    meets NO bill and becomes NO credit ($150.00 held
                       against the deposit position — it is a liability the
                       utility owes back, and the server refuses it outright on
                       an account whose plan requires no deposit).
            plan_down  meets the ARREARS the plan spreads AND links to the plan
                       ($50.00 off PE-13's 267.30); refused when the account has
                       no live plan.
            prepay     $200.00 on an account with no open bills carries as
                       credit and auto-applies to the next bill (BR-PAY-010).
          Each refusal comes back as the SERVER's own sentence with its BR-ID
          (BR-SHL-020), so nothing here predicts which accounts qualify.

          ⚠ ITS HELP LINE IS IN THE DISCLOSURE, NOT HERE. It named all four
          options in order — the exact shape B14 rule 32 forbids: "a row never
          repeats what its own control offers". */}
        <SelectField
          id="purpose"
          label={t("payments.form.purpose")}
          value={purpose}
          onChange={(next) => setPurpose(next as PaymentPurpose)}
          options={PAYMENT_PURPOSES.map((code) => ({
            value: code,
            label: t(`payments.purpose.${code}`),
          }))}
          required
        />

        {/* ── WHEN ─────────────────────────────────────────────────────────── */}
        {/* BR-PAY-021 / BR-PAY-033 — the posting date, PRE-FILLED with today
          and always overridable. ⛔ The second field (the clearing date) is
          gone since `DEF-PAY-10737`: CR-186-BRC10 (PO 2026-10-21) gives the
          clearing date to the bank reconciliation alone, and the server never
          stored what this box sent. */}
        <DatePickerField
          id="posted_at"
          label={t("payments.form.postedAt")}
          value={postedAt}
          onChange={setPostedAt}
          prefill={props.today}
          dateFormat={props.dateFormat}
          required
          help={t("payments.form.postedAtBrief")}
        />

        {/* ── HOW: the tender and its reference ────────────────────────────── */}
        {/* CR-059 CS-35 (task 23). Three types, and this form sent `payment` and
          nothing else from the first migration until 2026-09-02 — so the only
          way to put a goodwill credit on an account was to record a FAKE
          PAYMENT, which then swept into the day's deposit batch and made the
          takings un-tieable. Task 22 taught `record_payment` the type; this is
          the control that lets a clerk say which one they mean. */}
        <SelectField
          id="type"
          label={t("payments.form.type")}
          value={paymentType}
          onChange={(next) => {
            setPaymentType(next as PaymentType);
            // Switching to a credit CLEARS the two cash fields rather than
            // hiding a value that would still be sent. A hidden input that keeps
            // posting is how a credit acquires a cheque number nobody typed.
            if (next !== "payment") {
              setMethod("");
              setConfirmation("");
            } else {
              // DEF-PAY-5128, the mirror of the two lines above: a payment
              // carries no reason and the server refuses one outright.
              setReasonCode("");
            }
          }}
          options={PAYMENT_TYPES.map((code) => ({
            value: code,
            label: paymentTypeLabel(code, translate),
          }))}
        />
        {/* ⚠ **DEF-PAY-5128 — THE FIELD THAT MADE THE TWO OPTIONS ABOVE
          SUBMITTABLE.** CS-35 built the select and never published the reasons,
          so *Credit* and *Adjustment* were incapable of passing from the day
          they shipped. `reason` is REQUIRED on both and REFUSED on a payment,
          which is why this is drawn and sent on exactly the same condition. */}
        {!isCash && (
          <SelectField
            id="reason"
            label={t("payments.form.reason")}
            value={reasonCode}
            onChange={setReasonCode}
            // The tenant's OWN live list, never a hardcoded five — the same rows
            // the recorder validates against, so this cannot offer one it refuses.
            options={reasonOptions(reasons)}
            placeholder={t("payments.form.reasonPlaceholder")}
          />
        )}

        {/* CS-35, verbatim: the type selector "hides the tender and reference
          fields for the latter two, because there is no cheque and no bank
          line". A credit is not money that arrived, so it has no instrument to
          name and nothing will ever match it on a bank statement. */}
        {isCash && (
          <>
            <SelectField
              id="method"
              label={t("payments.form.method")}
              value={method}
              onChange={setMethod}
              // BR-PAY-026: the tenant's own live list, the SAME one the S33 filter
              // uses. Never a hardcoded six. Where that list is edited is in the
              // disclosure below — it is a fact about Settings, not about this box.
              options={methodOptions(props.methods)}
              placeholder={t("payments.form.methodPlaceholder")}
            />
            <TextField
              id="confirmation"
              label={t("payments.form.confirmation")}
              value={confirmation}
              onChange={setConfirmation}
            />
          </>
        )}

        <SelectField
          id="apply_to"
          label={t("payments.form.applyTo")}
          value={applyTo}
          onChange={(next) => {
            setApplyTo(next);
            // A choice that no longer names bills carries no aim. Keeping the old
            // targets would post a bill under an instruction that does not mean
            // one, which the allocator would then have to guess about.
            setTargets({});
          }}
          // ⚠ ALL FOUR ARE LIVE SINCE 2026-09-02 (CR-059 CS-4, task 12). Two of
          // them carried `disabled` and a `help` line reading *"no endpoint
          // serves that position"*; the endpoint exists, so BOTH the flags and
          // the sentence are gone rather than left beside a working control —
          // CS-4's Proof asks for exactly that.
          options={ALLOCATION_CHOICES.map((choice) => ({
            value: choice.value,
            label: t(choice.labelKey),
          }))}
        />
      </div>
      <TextField id="memo" label={t("payments.form.memo")} value={memo} onChange={setMemo} />
      {/* CR-161-BRC10 W5 — the utility's OWN payment fields, typed once here
          and never editable afterwards (hard rule 4's trigger). Renders
          NOTHING when the utility has defined none. A refusal arrives keyed
          `custom_data.<key>` and FormPage keeps every typed value. */}
      <CustomFieldsInput
        entity="payments"
        screen="S35"
        values={customData}
        onChange={setCustomData}
        client={props.client}
      />
      {/* The picker and its running remainder — drawn only under a choice that
          aims at bills, because the other two never name one. */}
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
      {/* CR-059 CS-23 · task 6 — which instalment this payment will meet, and
          the option to change it. Drawn only once an account is chosen; an
          account with no plan draws nothing at all. */}
      {accountId !== "" && (
        <PlanInstallmentStrip
          plan={plan.data?.live_plan ?? null}
          pending={plan.isPending}
          unavailable={plan.isError ? "" : (plan.data?.plans_unavailable ?? null)}
          chosenSeq={installmentSeq}
          onChoose={setInstallmentSeq}
          t={translate}
        />
      )}

      {/* ⚠ **`P0.12` — B14 RULE 11'S BOX, ON THE FIRST OF THE THREE MONEY FORMS
          THE BLUEPRINT FILES AGAINST.** The rule opens on the word *money*:
          *"any form writing money, service state or legal notices shows a 'what
          this will do' box before its commit button."* `ConsequenceBox` is that
          box and it was rendered at 52 non-test call sites across seventeen
          areas — INCLUDING `portal/payments/PayNow.tsx`, the screen where a
          CUSTOMER pays — and **zero times on the staff form that writes the
          same money to the ledger**.

          ⚠ **DRAWN ONLY ONCE THERE IS SOMETHING TRUE TO SAY.** A box over an
          empty form would state a consequence of nothing, which is B14 rule
          32's noise and worse than no box: it trains a clerk to read past the
          one place the product tells them what is about to happen.

          The body is the ALLOCATION CHOICE in the clerk's own terms, never a
          restatement of the control above it. `carry_credit` is the one answer
          that does not meet a bill at all, and it is the one a clerk is most
          likely to pick by accident. */}
      {accountId !== "" && amount.trim() !== "" && props.currency !== null && (
        <ConsequenceBox
          tone="check"
          tag={t("payments.consequence.tag")}
          data-consequence="record"
          title={t("payments.form.consequence.title", {
            amount: formatMoney(amount, props.currency),
          })}
          body={
            // ⛔ `DEF-PAY-10737` — the *"meets no bill until cleared"* branch
            // is gone with the box: since CR-186-BRC10 every payment is applied
            // to open bills at entry, whatever the tender.
            applyTo === "carry_credit"
                ? t("payments.form.consequence.credit")
                : needsTargets
                  ? t("payments.form.consequence.chosen")
                  : t("payments.form.consequence.oldest")
          }
        />
      )}
      {duplicate.earlier !== null && (
        <PossibleDuplicateNotice
          earlier={duplicate.earlier}
          onGoBack={duplicate.clear}
          onRecordAnyway={duplicate.confirmNext}
          submits
        />
      )}
      {/* Every sentence this form used to lead with, kept and closed. */}
      <MoreAboutPayments summary={t("payments.form.moreAbout")}>
        <p className="pay-form-note">{t("payments.form.purposeHelp")}</p>
        <p className="pay-form-note">{t("payments.form.postedAtHelp")}</p>
        {/* `DEF-PAY-10737` — the clearing-date note went with its box; it
            said a blank date "meets no bill", which CR-186 made false. */}
        <p className="pay-form-note">{t("payments.form.typeHelp")}</p>
        <p className="pay-form-note">{t("payments.form.methodHelp")}</p>
        <p className="pay-form-note">{t("payments.form.amountHelp")}</p>
      </MoreAboutPayments>
    </FormPage>
  );
}

/**
 * **The routed screen — `/:tenant/payments/record/new`.**
 *
 * It owns the page head, the regional pair and where the form goes when it is
 * done; the form itself is the component above.
 *
 * ⚠ **THE HEAD IS B14 RULE 2's AND NOT THE DRAWING'S TO RESTATE.** p037 draws
 * `PAYMENTS › RECORD A PAYMENT` over **Record a payment** — the kicker and
 * title this already renders — and `backTo` names where it EXITS to, which is
 * rule 1: *"← Payments"* is an exit, never a step-back.
 */
export interface RecordPaymentPageProps extends RegionalProps {
  client?: ApiClient;
  /** Tests state the day they are testing; the app reads the tenant's zone.
   *  BR-PAY-033 — the posting date is PROPOSED, never taken from the clock. */
  today?: string;
}

export function RecordPaymentPage(props: RecordPaymentPageProps = {}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const fireToast = useToast();
  // ⚠ **RESOLVES ITS OWN REGIONAL PAIR, LIKE `MyCounterPage` AND
  // `CounterDoors` — `useRegional`'s own docstring says why.** Under
  // `vite build` there is NO fallback: a screen rendered outside
  // `<TenantRegionalProvider>` with no explicit prop fails loudly rather than
  // drawing a plausible wrong date (hard-won law 3). A test that wants to
  // state which tenant it is testing passes the pair explicitly.
  const { timeZone, dateFormat } = useRegional(props);
  const client = props.client ?? api;

  // ⚠ **THE TENDER LIST AND THE CURRENCY COME OFF THE SAME RESPONSE THAT
  // RENDERS THE LIST, WHICH IS THE WHOLE POINT (BR-PAY-026, BR-TEN-042).**
  // `PaymentsPage` reads both off its own `GET /payments`; this page has no
  // list under it, so it asks the same endpoint for ONE row. p038 says why it
  // may not be a literal array: *"value and options both served from GET
  // /payments methods[] — never a literal array"*, because a hardcoded three
  // hides the other three and can offer a tender the ledger has retired.
  //
  // `per: 1` because nothing here draws a row — only `methods[]` and the
  // `CHAR(3)`. It shares no query key with the list's, so it neither serves
  // nor poisons the list's cache.
  const lookups = useQuery({
    queryKey: ["payments", "record-new-lookups"],
    queryFn: () => getPayments({ per: 1 }, client),
    retry: false,
  });
  const methods = lookups.data?.methods ?? [];
  // Null is a REAL state and not a default to USD — see `RecordPaymentForm`'s
  // `currency` prop. A tenant with no payments yet has no code to read.
  const currency = paymentsDisplayCurrency(lookups.data);

  // ⚠ **THE LIST IS WHERE `Cancel` AND A FINISHED PAYMENT BOTH GO**, because
  // that is where every door onto this page is (p030's page head, its empty
  // state, 1·1's Summary tile and p053's till). A page that exits somewhere
  // the clerk did not come from is the `DEF-CWP-3925` shape pointed forwards.
  const backToList = () => navigate(tenantPath(PAYMENTS_RECORD_ROUTE));

  // ⚠ `DEF-PAY-10706` (PO Q4 = A, the approved mock-up) — *Pay for: One
  // account · Several accounts*. A master's *Pay units* door arrives with the
  // master in router STATE (never the URL — B14 rule 31) and opens on
  // Several accounts with it chosen.
  const location = useLocation();
  const doorPayer = payForFromState(location.state);
  const [mode, setMode] = useState<PayForMode>(doorPayer !== null ? "several" : "one");
  const [tender, setTender] = useState<{ result: RecordedTender; labels: string[] } | null>(null);
  const modeSwitch = <PayForSwitch value={mode} onChange={setMode} />;

  return (
    <div>
      <PageHeader
        kicker={t("payments.form.kicker")}
        title={t("payments.form.title")}
        backTo={{ to: tenantPath(PAYMENTS_RECORD_ROUTE), label: t("payments.form.back") }}
      />
      {mode === "several" ? (
        tender !== null ? (
          <PayForRecorded tender={tender.result} labels={tender.labels} onDone={backToList} />
        ) : (
          <PayForSeveralForm
            client={client}
            methods={methods}
            today={props.today ?? todayInZone(timeZone)}
            timeZone={timeZone}
            dateFormat={dateFormat}
            modeSwitch={modeSwitch}
            initialPayer={doorPayer}
            onCancel={backToList}
            onRecorded={(result, labels) => {
              fireToast(t("payments.payFor.recorded", {
                count: result.part_count,
                amount: formatMoney(result.amount, result.currency),
              }));
              void queryClient.invalidateQueries({ queryKey: ["payments"] });
              setTender({ result, labels });
            }}
          />
        )
      ) : (
      <RecordPaymentForm
        modeSwitch={modeSwitch}
        client={client}
        // ⚠ **THE TENANT'S OWN LIST AND ITS OWN CODE, NOT A HARDCODED SIX.**
        // BR-PAY-026 — the same rows the recorder validates against, so this
        // form cannot offer a tender the ledger has retired. `PaymentsPage`
        // reads both off the list response; this page has no list under it, so
        // it asks the SAME endpoint for one row — the `lookups` query above.
        methods={methods}
        today={props.today ?? todayInZone(timeZone)}
        dateFormat={dateFormat}
        currency={currency}
        onCancel={backToList}
        onRecorded={(result) => {
          fireToast(
            result.created
              ? t("payments.toast.recorded", { number: result.payment_no ?? result.id })
              : t("payments.toast.replay"),
          );
          void queryClient.invalidateQueries({ queryKey: ["payments"] });
          // ⚠ **THE RESULT TRAVELS BACK IN ROUTER STATE, NOT JUST AS A TOAST.**
          // `RecordPaymentPanel` on the list is what a clerk reads afterwards
          // — the number, what it met, what carried as credit, whether it
          // reached the books — and a toast carries none of that. The modal
          // used to set it directly; a page cannot, so it hands it over. The
          // list consumes it once and clears the history entry.
          navigate(tenantPath(PAYMENTS_RECORD_ROUTE), {
            state: { recordedPayment: result },
          });
        }}
      />
      )}
    </div>
  );
}

export default RecordPaymentPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: `DEF-PAY-6317` · `CR-136-BRC07` row `P2.9`'s deferred half · blueprint p030, p037–p039 and p098 as images at 2.0
// generated: 2026-09-23 by LANE RECORD-PAGE
// checklist: A✔ B=n/a(no endpoint moves — `POST /accounts/{id}/payments` is unchanged) C✔ D=n/a E✔(routed in App.tsx above `:tab`; four doors repointed in the same commit) F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest recordPaymentPage.dom · recordFormOrder.dom · accountSearch.dom · consequenceOnMoneyForms.dom · cashTotal.dom · screenIds · G31 · routeBUtilities.test.ts
// exceptions: E3 p037 pairs `Method | Reference` and `Kind | Apply to` while the JSX emits `type` before `method`, so the drawn PAIRING differs — the ORDER is deliberately not changed (the drawing says twice that it is the JSX's and UNCHANGED, and a PO ruling of 2026-09-13 pins it) · E3 the two-column grid is spelled with the same utilities `AssetEditPage` uses rather than through `serviceRequestShared`'s `FieldGrid`, which is a THIRD spelling of one rule-39 grid living in a feature module rather than the kit — noted, not fixed in passing
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
