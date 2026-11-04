// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-018 (S24 — amount & term → editable schedule → agreement
//           and activation) · US-PAY-017 (the payments-owned rows this draws)
//           Screens: S24 (entered from the S21 "Payment plan" action)
// Rules:    BR-CUS-043 (schedule = (total − down) ÷ n, remainder on the FINAL
//           instalment; step-2 edits must re-sum EXACTLY; ONE live plan per
//           account; dunning + disconnect pause while active and current) ·
//           BR-CUS-044 (agreement → the plan activates on the CUSTOMER's
//           e-signature ALONE; ⚠ its `defaulted` state and {missed_count}
//           default clause are SUPERSEDED — PO 2026-08-11) · BR-CUS-037
//           (customers writes no financial table — the rows are payments') ·
//           BR-BIL-073 (A PLAN DOES NOT SUSPEND THE CURRENT BILL — PO
//           2026-08-11, OQ-138) · BR-SHL-020 (plain-language refusal) ·
//           BR-SHL-025 (a control that cannot be honoured renders DISABLED with
//           its reason) · BR-SHL-044 (one page header) · BR-TEN-043 (a business
//           date is typed, never read off a clock) · CLAUDE.md rule 2 (money
//           renders with its currency; every instalment with its date)
// ───────────────────────────────────────────────────────
// S24 — the three-step payment-plan page.
//
// ❄️ THE FROZEN FIGURE THIS SCREEN EXISTS TO SHOW (GT-47, B5, finance-signed):
// **$267.30 less a $50.00 down payment over six instalments is 5 × $36.22 and a
// FINAL $36.20.** The last row is 36.20 and not 36.22 — the remainder lands on
// the final instalment and nowhere else (BR-CUS-043 / A7) — and that is what
// makes the schedule re-sum to $217.30 exactly. **This file computes none of
// it.** Every amount drawn here is a NUMERIC(18,6) string the server produced;
// there is no division, no rounding and no subtraction in this component, and
// step 2's edits are sent BACK to the server to be re-summed. A cent invented
// on a screen is a cent on an agreement a customer signs.
//
// THE FOUR THINGS THIS SCREEN REFUSES TO SAY
// ──────────────────────────────────────────
//  1. **It never opens with $0.00 in the amount box.** The balance is the
//     LEDGER's figure (DEF-127). When the books cannot be asked, the server
//     answers `balance: null` with a reason, this screen prints the reason, and
//     the wizard does not open — because a clerk who sees $0.00 where "we could
//     not tell" belongs will spread a debt nobody could read.
//  2. **It never offers to VOID a plan.** PO 2026-08-11, verbatim: *"nodrop we
//     chase for payments until write off"*. There are four plan states and none
//     of them is `void`; whether STAFF may cancel one is OQ-239, minted and
//     unanswered, so no control exists for it. A missed instalment is CHASED —
//     it is shown on the plan, and it changes nothing about the plan.
//  3. **It never implies the current bill is paused.** The step-3 summary says
//     the current month's bill is still due, on its face (PO 2026-08-11) —
//     believing otherwise IS the defect that ruling closed (DEF-061).
//  4. **It never says an agreement was SIGNED, or SENT anywhere.** Sending
//     QUEUES the agreement; no dispatcher and no provider adapter exists in
//     this release. And no e-signature provider is connected (the DocuSign seam
//     is B7 / integrations, which holds three docstrings and no models), so
//     activation is a clerk RECORDING a signature they hold, with the date the
//     customer signed — never the product asserting one arrived.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  activatePaymentPlan,
  getAccountDetail,
  getPaymentPlans,
  previewPaymentPlan,
  sendPaymentPlanAgreement,
} from "@/api/endpoints";
import type { PaymentPlanContext, PaymentPlanRow, PaymentPlanSchedule } from "@/api/endpoints";
import { CheckboxField, DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import {
  CELL_FULL,
  GuardedButton,
  isDenied,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import { initialWizardNav, WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  ACCOUNTS_PERMISSION,
  ACCOUNTS_ROUTE,
  DASHBOARD_ROUTE,
  accountDetailPath,
  accountHeadline,
} from "./customersShared";

import {
  PlanInstalments,
  PaymentPlanScheduleTable,
  blockedSentence,
  paymentPlansKey,
} from "./PaymentPlanSchedule";
import "./customers.css";

// ── Pure pieces (provable without a browser or a network) ──────────────────

export const PAYMENT_PLAN_STEPS = ["terms", "schedule", "agreement"] as const;
export type PaymentPlanStep = (typeof PAYMENT_PLAN_STEPS)[number];

/**
 * ⛔ **`DEF-CUS-5071` — THE RAIL'S WORDS.** This const had the same two readers
 * `CHANGE_PLAN_STEPS` had — its own type alias and a test asserting the array
 * equals itself — and no renderer, so `S24` was the second of the only two
 * customers wizards out of eleven with no step rail (zero rail nodes measured
 * on `brazosbend`, 2026-09-12; `Terms`/`Schedule`/`Agreement` appeared nowhere
 * on the page). B14 rule 3 asks for the numbered rail on any flow with 2+
 * stages; nine siblings get it from `components/WizardFrame` and this is now
 * the tenth. The rail is built by `.map()` over the const above, so the two
 * cannot drift.
 */
export const PAYMENT_PLAN_STEP_LABEL_KEYS: Record<PaymentPlanStep, string> = {
  terms: "customers.paymentPlan.step.terms",
  schedule: "customers.paymentPlan.step.schedule",
  agreement: "customers.paymentPlan.step.agreement",
};

/**
 * ⚠ **THE PAGE TITLE IS THE STEP'S OWN — `DEF-CUS-5171`, B14 rule 41.**
 *
 * `14-payment-plan-wizard.md` heads the three steps **`Terms`** ·
 * **`The schedule`** · **`The agreement`**, under the kicker `PAYMENT PLAN`
 * and over a sub-line `Step 1 of 3 · Terms`. The product drew `Payment plan`
 * on all three, kickered with the account number — the drawing's two halves
 * swapped — and printed the step number twice inside the body instead
 * (`Step 1 · Amount and term`).
 */
export const PAYMENT_PLAN_TITLE_KEYS: Record<PaymentPlanStep, string> = {
  terms: "customers.paymentPlan.title.terms",
  schedule: "customers.paymentPlan.title.schedule",
  agreement: "customers.paymentPlan.title.agreement",
};

export { blockedSentence, paymentPlansKey };

/** S24 step 3's channel elections. At least one is required (US-CUS-018 §5). */
export const AGREEMENT_CHANNEL_LABELS: Record<string, string> = {
  email: "customers.paymentPlan.channel.email",
  sms: "customers.paymentPlan.channel.sms",
  print: "customers.paymentPlan.channel.print",
};

/**
 * Why the wizard cannot open — the SERVER's reason, or none.
 *
 * Exported and pure so the rule is testable without a browser. The order is the
 * order a clerk needs: an unreadable balance and an unreadable plan list are
 * different facts from "this account already has a plan", and each has to reach
 * the screen as itself (DEF-127's whole lesson).
 */
export function blockedReason(context: PaymentPlanContext): string | null {
  return context.can_propose ? null : (context.cannot_propose_reason ?? "");
}

/**
 * Whether the SEND control may fire, and WHY NOT when it may not.
 *
 * BR-SHL-025: a forbidden control renders disabled carrying its reason rather
 * than firing and being refused. The server refuses each of these too and stays
 * the enforcement — this is the explanation, not the guard.
 */
export function sendBlockedReason(
  schedule: PaymentPlanSchedule | null,
  channels: string[],
  writeBlocked: string | null,
): string | null {
  if (writeBlocked !== null) return writeBlocked;
  if (schedule === null) return "customers.paymentPlan.previewFirst";
  if (channels.length === 0) return "customers.paymentPlan.pickAChannel";
  return null;
}

/**
 * The one live plan, or null (BR-CUS-043: exactly one).
 *
 * `null` when the list itself could not be read — the caller renders THAT with
 * its own reason, because "no plan" and "we could not look" must not draw the
 * same empty panel.
 */
export function livePlanOf(context: PaymentPlanContext): PaymentPlanRow | null {
  return context.live_plan;
}

/** A live or historical plan, with what it does and does NOT do. */
function PlanPanel(props: {
  plan: PaymentPlanRow;
  t: Translator;
  onActivate?: () => void;
  activateReason?: string | null;
  signedOn: string;
  onSignedOn: (value: string) => void;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
}) {
  const { plan, t } = props;
  return (
    <Panel as="section" data-testid="plan-panel">
      <h3>{t("customers.paymentPlan.livePlanTitle")}</h3>
      <p className="met-panel-hint">
        <MoneyCell amount={plan.total_amount} currency={plan.currency} />
        <span className="met-qualifier">
          {t("customers.paymentPlan.spreadOver", { count: plan.installment_count })}
        </span>
      </p>
      {/* PO 2026-08-11 (OQ-138), on the plan itself and not only in the wizard:
          the pause covers the ARREARS this plan spreads; the current month's
          bill is due every month and is chased like anybody else's. */}
      <p className="met-panel-hint" role="note">
        {t("customers.paymentPlan.currentBillStillDue")}
      </p>
      {/* ⛔ CR-059 CS-23 · task 6 — the plan's own progress, its counts, its
          missed line and its instalments. Since PO 2026-10-11 they are ONE
          shared component, because the Debtors detail draws the same table
          (B14 rule 43) — see `PaymentPlanSchedule.tsx`. */}
      <PlanInstalments plan={plan} dateFormat={props.dateFormat} />
      {plan.status === "agreement_sent" && props.onActivate !== undefined && (
        <div className="cus-wizard-actions">
          <DatePickerField
            id="signed_on"
            label={t("customers.paymentPlan.signedOn")}
            value={props.signedOn}
            onChange={props.onSignedOn}
            dateFormat={props.dateFormat}
            help={t("customers.paymentPlan.signedOnHelp")}
            required
          />
          <GuardedButton
            label={t("customers.paymentPlan.recordSignature")}
            reason={props.activateReason ?? null}
            variant="primary"
            onClick={props.onActivate}
          />
        </div>
      )}
    </Panel>
  );
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface PaymentPlanWizardProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function PaymentPlanWizard(props: PaymentPlanWizardProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const { dateFormat } = useRegional(props);
  const accountId = params.accountId ?? "";

  // `DEF-CUS-5071` — ONE number for the step, and it is the frame's nav state.
  const [nav, setNav] = useState<WizardNavState>(initialWizardNav);
  const [balanceToSpread, setBalanceToSpread] = useState("");
  const [downPayment, setDownPayment] = useState("");
  const [installments, setInstallments] = useState("4");
  const [cadence, setCadence] = useState("monthly");
  const [firstDue, setFirstDue] = useState("");
  const [autopay, setAutopay] = useState(true);
  const [suspendLateFees, setSuspendLateFees] = useState(false);
  const [suspendDisconnect, setSuspendDisconnect] = useState(true);
  const [edits, setEdits] = useState<Record<number, string>>({});
  const [channels, setChannels] = useState<string[]>(["email"]);
  const [schedule, setSchedule] = useState<PaymentPlanSchedule | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [signedOn, setSignedOn] = useState("");

  const cell = useAccessCell(ACCOUNTS_PERMISSION, client);
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("customers.accounts.rbac.readOnly");

  const detailQuery = useQuery({
    queryKey: ["accounts", "detail", accountId],
    queryFn: () => getAccountDetail(accountId, client),
    enabled: accountId !== "",
  });
  const planQuery = useQuery({
    queryKey: paymentPlansKey(accountId),
    queryFn: () => getPaymentPlans(accountId, client),
    enabled: accountId !== "",
    retry: false,
  });

  const previewMutation = useMutation({
    mutationFn: () =>
      previewPaymentPlan(
        accountId,
        {
          balance_to_spread: balanceToSpread,
          down_payment: downPayment === "" ? undefined : downPayment,
          installments: Number.parseInt(installments, 10),
          cadence,
          first_due_date: firstDue,
          autopay_enabled: autopay,
          suspend_late_fees: suspendLateFees,
          suspend_disconnect: suspendDisconnect,
          edits: Object.entries(edits).map(([seq, amount]) => ({
            seq: Number.parseInt(seq, 10),
            amount,
          })),
        },
        client,
      ),
    onSuccess: (data) => {
      setSchedule(data);
      setRefusal(null);
      // `DEF-CUS-5071` — the mutation no longer advances the step. Step 1's
      // `validate` awaits this call and the FRAME advances on its answer,
      // which is what `WizardFrame` documents for a step that does the work
      // its own Continue implies: one press, single-flighted, with A18 §3's
      // working state while it is out.
    },
    onError: (error: unknown) => {
      setSchedule(null);
      setRefusal(apiErrorText(error, translate));
    },
  });

  const sendMutation = useMutation({
    mutationFn: () =>
      sendPaymentPlanAgreement(
        accountId,
        {
          balance_to_spread: balanceToSpread,
          down_payment: downPayment === "" ? undefined : downPayment,
          installments: Number.parseInt(installments, 10),
          cadence,
          first_due_date: firstDue,
          autopay_enabled: autopay,
          suspend_late_fees: suspendLateFees,
          suspend_disconnect: suspendDisconnect,
          edits: Object.entries(edits).map(([seq, amount]) => ({
            seq: Number.parseInt(seq, 10),
            amount,
          })),
          channels,
          on_date: planQuery.data?.as_of ?? "",
        },
        client,
      ),
    onSuccess: async (data) => {
      setRefusal(null);
      // US-CUS-018 §1's exit toast — and it says QUEUED, never "sent": nothing
      // in this release hands a document to a provider (PO 2026-08-16, *"I
      // already confirm it before it Queue them"*).
      fireToast(t("customers.paymentPlan.toast.queued", { count: data.plan.installment_count }));
      await queryClient.invalidateQueries({ queryKey: paymentPlansKey(accountId) });
      // Back to step 1 with a clean slate — the queued plan is the account's
      // now and shows in `PlanPanel` above. The nav is the frame's, so it is
      // reset rather than a `setStep`.
      setNav(initialWizardNav());
      setSchedule(null);
    },
    onError: (error: unknown) => setRefusal(apiErrorText(error, translate)),
  });

  const activateMutation = useMutation({
    mutationFn: (planId: string) =>
      activatePaymentPlan(
        planId,
        { current_status: "agreement_sent", signed_on: signedOn },
        client,
      ),
    onSuccess: async () => {
      setRefusal(null);
      fireToast(t("customers.paymentPlan.toast.activated", { date: signedOn }));
      await queryClient.invalidateQueries({ queryKey: paymentPlansKey(accountId) });
    },
    onError: (error: unknown) => setRefusal(apiErrorText(error, translate)),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("customers.accounts.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (detailQuery.isPending || planQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (detailQuery.data === undefined) {
    if (isPermissionDenied(detailQuery.error)) {
      return (
        <PermissionDenied
          helper={t("customers.accounts.denied")}
          onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
        />
      );
    }
    return (
      <FailedWithRetry
        title={t("customers.account.detail.failedTitle")}
        reason={apiErrorText(detailQuery.error, translate)}
        onRetry={() => void detailQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(ACCOUNTS_ROUTE))}
      />
    );
  }
  if (planQuery.data === undefined) {
    return (
      <FailedWithRetry
        title={t("customers.paymentPlan.title")}
        reason={apiErrorText(planQuery.error, translate)}
        onRetry={() => void planQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(accountDetailPath(accountId)))}
      />
    );
  }

  const detail = detailQuery.data;
  const context = planQuery.data;
  const live = livePlanOf(context);
  const blocked = blockedReason(context);
  const sendReason = sendBlockedReason(schedule, channels, writeBlockedReason);

  /**
   * `DEF-CUS-5071` — the three DECLARED steps on the shared frame.
   *
   * ⚠ **STEP 1's `validate` DOES THE WORK ITS CONTINUE IMPLIES**, which is the
   * case `WizardFrame` documents in as many words: *"a step may therefore do
   * the work its own Continue implies and answer when it is done… the frame
   * single-flights the press and renders the A18 §3 working state while it is
   * out, so a second press is not a second run."* Pressing Continue previews
   * the schedule and the frame advances on the answer — which is what the old
   * hand-rolled footer did through `previewMutation.onSuccess` calling
   * `setStep`, with no single-flight and no working state.
   *
   * ⚠ **IT IS NOT A COMMIT AND MUST NOT BECOME ONE (`BR-SHL-019`).** The
   * preview writes nothing; the ONE transactional call is still the ✓ at
   * step 3, `POST` of the agreement.
   */
  const stepContent: Record<PaymentPlanStep, ReactNode> = {
    terms: (
      <>
        <Panel as="section">
          {/* No section heading: the page title is the step's name
              (`Terms`) and `14-payment-plan-wizard.md` goes straight to
              `Balance to spread`. `Step 1 · Amount and term` was a second
              heading printing the number the rail and sub-line both carry. */}
          <TextField
            id="balance_to_spread"
            label={t("customers.paymentPlan.balanceToSpread")}
            value={balanceToSpread}
            numeric
            required
            onChange={setBalanceToSpread}
            help={t("customers.paymentPlan.balanceToSpreadHelp")}
          />
          <TextField
            id="down_payment"
            label={t("customers.paymentPlan.downPayment")}
            value={downPayment}
            numeric
            onChange={setDownPayment}
            help={t("customers.paymentPlan.downPaymentHelp")}
          />
          <TextField
            id="installments"
            label={t("customers.paymentPlan.installments")}
            value={installments}
            numeric
            required
            onChange={setInstallments}
          />
          <SelectField
            id="cadence"
            label={t("customers.paymentPlan.cadenceLabel")}
            value={cadence}
            onChange={setCadence}
            options={context.cadences.map((value) => ({
              value,
              label: t(`customers.paymentPlan.cadence.${value}`),
            }))}
          />
          <DatePickerField
            id="first_due_date"
            label={t("customers.paymentPlan.firstDue")}
            value={firstDue}
            onChange={setFirstDue}
            dateFormat={dateFormat}
            required
            help={t("customers.paymentPlan.firstDueHelp")}
          />
          <CheckboxField
            id="autopay_enabled"
            label={t("customers.paymentPlan.autopay")}
            checked={autopay}
            onChange={setAutopay}
          />
          <CheckboxField
            id="suspend_late_fees"
            label={t("customers.paymentPlan.suspendLateFees")}
            checked={suspendLateFees}
            onChange={setSuspendLateFees}
          />
          <CheckboxField
            id="suspend_disconnect"
            label={t("customers.paymentPlan.suspendDisconnect")}
            checked={suspendDisconnect}
            onChange={setSuspendDisconnect}
          />
        </Panel>
      </>
    ),
    schedule: (
      <>
      {/* A schedule is what steps 2 and 3 are ABOUT, and the rail cannot
          reach them without step 1 producing one — but an unreachable
          branch that renders nothing is still a blank panel if it is ever
          reached, so it says what is missing instead (BR-SHL-020). */}
      {schedule === null ? (
        <Panel as="section">
          <p className="met-panel-hint">{t("customers.paymentPlan.previewFirst")}</p>
        </Panel>
      ) : (
        <>
          <Panel as="section">
            <p className="met-panel-hint">
              {t("customers.paymentPlan.scheduleHint")}{" "}
              <MoneyCell amount={schedule.spread} currency={schedule.currency} />
            </p>
            <PaymentPlanScheduleTable
              rows={schedule.installments}
              currency={schedule.currency}
              dateFormat={dateFormat}
              edits={edits}
              onEdit={(seq, amount) => setEdits({ ...edits, [seq]: amount })}
            />
            {/* ⚠ **TWO DRAWN LINES THAT WERE NOT BUILT — `DEF-CUS-5171`.**
                `14-payment-plan-wizard.md` puts *"The remainder lands on the
                FINAL row, never spread across the others"* under the table and
                a `Progress 0 of 5 paid` line beneath that.

                The remainder sentence is `BR-CUS-043` and `B4.4` said to a
                clerk, and it is the reason the last row of the frozen `GT-47`
                schedule is `$36.20` where the five above it are `$36.22`. The
                `Final instalment` pill already marks WHICH row; this says WHY,
                which is the half a clerk asked to check a schedule needs.

                ⚠ **THE PROGRESS COUNT IS COMPUTED, NEVER THE DRAWN `0 of 5`
                (B14 rule 37).** On a proposal nothing is paid, so the count
                genuinely is zero of however many instalments the SERVER
                returned — and it is read off `installments.length` rather than
                off the number typed in step 1, because the server is what
                decides how many rows a schedule has. */}
            <p className="met-panel-hint" data-schedule="remainder">
              {t("customers.paymentPlan.remainderOnFinal")}
            </p>
            <p className="met-panel-hint" data-schedule="progress">
              {t("customers.paymentPlan.progressOf", {
                paid: schedule.installments.filter((row) => row.paid_posted_on).length,
                count: schedule.installments.length,
              })}
            </p>
          </Panel>
        </>
      )}
      </>
    ),
    agreement: (
      <>
      {/* A schedule is what steps 2 and 3 are ABOUT, and the rail cannot
          reach them without step 1 producing one — but an unreachable
          branch that renders nothing is still a blank panel if it is ever
          reached, so it says what is missing instead (BR-SHL-020). */}
      {schedule === null ? (
        <Panel as="section">
          <p className="met-panel-hint">{t("customers.paymentPlan.previewFirst")}</p>
        </Panel>
      ) : (
        <>
          <Panel as="section">
            <ul className="kv-list">
              <li>
                <span className="kv-k">{t("customers.paymentPlan.totalSpread")}</span>
                <span className="kv-v">
                  <MoneyCell amount={schedule.spread} currency={schedule.currency} />
                </span>
              </li>
              <li>
                <span className="kv-k">{t("customers.paymentPlan.downPayment")}</span>
                <span className="kv-v">
                  <MoneyCell amount={schedule.down_payment} currency={schedule.currency} />
                </span>
              </li>
              <li>
                <span className="kv-k">{t("customers.paymentPlan.installments")}</span>
                <span className="kv-v">{schedule.installment_count}</span>
              </li>
            </ul>
            {/* PO 2026-08-11, ON THE SUMMARY'S FACE — US-CUS-018 §1 requires this
                sentence here rather than leaving a clerk to infer it. */}
            <p className="met-panel-hint" role="note" data-testid="current-bill-note">
              {t("customers.paymentPlan.currentBillStillDue")}
            </p>
            {/* The pause, stated for what it covers and no more. */}
            <p className="met-panel-hint" role="note">
              {t("customers.paymentPlan.pauseScope")}
            </p>
            <fieldset className="field">
              <legend>{t("customers.paymentPlan.channels")}</legend>
              {context.agreement_channels.map((channel) => (
                <CheckboxField
                  key={channel}
                  id={`channel-${channel}`}
                  label={t(AGREEMENT_CHANNEL_LABELS[channel] ?? channel)}
                  checked={channels.includes(channel)}
                  onChange={(on) =>
                    setChannels(
                      on ? [...channels, channel] : channels.filter((one) => one !== channel),
                    )
                  }
                />
              ))}
            </fieldset>
            {/* Hard-won law 2, said out loud: the agreement is QUEUED, and no
                e-sign provider exists. (`DEF-NOT-10537`, 2026-10-22: it also
                said nothing leaves — false once email sends.) */}
            <p className="met-panel-hint" role="note" data-testid="queue-only-note">
              {t("customers.paymentPlan.queueOnly")}
            </p>
          </Panel>
        </>
      )}
      </>
    ),
  };

  /** `Recalculate` is neither Back, nor Continue, nor the commit — so it rides
   *  the frame's own `secondaryActions` slot rather than a second button row
   *  beside it (`DEF-712`'s reasoning: one row, one alignment, one tier). */
  const recalculate =
    PAYMENT_PLAN_STEPS[nav.step - 1] === "schedule" ? (
      <GuardedButton
        label={t("customers.paymentPlan.recalculate")}
        reason={writeBlockedReason}
        working={previewMutation.isPending}
        onClick={() => previewMutation.mutate()}
      />
    ) : undefined;

  const steps: WizardStep[] = PAYMENT_PLAN_STEPS.map((id) => ({
    id,
    label: t(PAYMENT_PLAN_STEP_LABEL_KEYS[id]),
    content: stepContent[id],
    validate:
      id === "terms"
        ? async () => {
            if (writeBlockedReason !== null) {
              return writeBlockedReason;
            }
            if (balanceToSpread === "" || firstDue === "") {
              return t("customers.paymentPlan.termsFirst");
            }
            try {
              await previewMutation.mutateAsync();
              return true;
            } catch (error: unknown) {
              // The strip above already carries the server's sentence; the
              // frame says the step did not pass rather than repeating it.
              return apiErrorText(error, translate);
            }
          }
        : () => writeBlockedReason ?? true,
  }));

  /** ONE transactional call (BR-SHL-019). */
  async function runSend(): Promise<WizardCommitOutcome> {
    if (sendReason !== null) {
      return { ok: false, reason: t(sendReason) };
    }
    try {
      await sendMutation.mutateAsync();
      return { ok: true };
    } catch (error: unknown) {
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }


  return (
    <div className="cus-page">
      <PageHeader
        backTo={{
          to: tenantPath(accountDetailPath(accountId)),
          label: accountHeadline(detail, translate),
        }}
        kicker={t("customers.paymentPlan.kicker")}
        title={t(PAYMENT_PLAN_TITLE_KEYS[PAYMENT_PLAN_STEPS[nav.step - 1] ?? "terms"])}
        rollup={
          <span className="cus-rollup">
            <span className="cus-rollup-item">
              <span className="cus-rollup-label">{t("customers.paymentPlan.balance")}</span>
              <span className="cus-rollup-value">
                {/* ⚠ NEVER a zero. When the ledger could not be asked, the
                    REASON renders here — a $0.00 in this slot reads exactly
                    like a settled account (DEF-127). */}
                {context.balance !== null ? (
                  <MoneyCell
                    amount={context.balance}
                    currency={context.currency ?? detail.currency}
                  />
                ) : (
                  <span className="cus-unavailable-detail" data-testid="balance-unavailable">
                    {t("customers.paymentPlan.balanceUnavailable", {
                      reason: context.balance_unavailable ?? "",
                    })}
                  </span>
                )}
              </span>
            </span>
          </span>
        }
      />

      {refusal !== null && (
        <RefusalStrip role="alert">
          {refusal}
        </RefusalStrip>
      )}

      {/* ⛔ **BR-SHL-025 AT FIRST PAINT, NOT ON PRESS — `DEF-CUS-5071`.**
          The hand-rolled footer used `GuardedButton`, which renders the
          control DISABLED with its reason in a tooltip, so a read-only role
          learnt it could not act before touching anything. `WizardFrame`
          reports a refusal at the button that refused it, AFTER a press
          (`DEF-178`) — right for a step that is merely unfinished and wrong
          for a role that may never finish it.

          So the RBAC refusal is a page-level strip, which is exactly what the
          nine siblings on this frame already do (`MoveOutWizard.tsx:816`).
          Reused rather than re-invented, and it is why the read-only case in
          this screen's suite still passes. */}
      {writeBlockedReason !== null && (
        <RefusalStrip role="alert">{writeBlockedReason}</RefusalStrip>
      )}


      {/* The plans this account HAS. `null` is not an empty list: it means
          payments publishes no read here, and it renders as that. */}
      {context.plans === null ? (
        <RefusalStrip role="note" data-testid="plans-unavailable">
          {t("customers.paymentPlan.plansUnavailable", {
            reason: context.plans_unavailable ?? "",
          })}
        </RefusalStrip>
      ) : (
        live !== null && (
          <PlanPanel
            plan={live}
            t={translate}
            signedOn={signedOn}
            onSignedOn={setSignedOn}
            dateFormat={dateFormat}
            activateReason={
              writeBlockedReason ??
              (signedOn === "" ? t("customers.paymentPlan.signatureDateFirst") : null)
            }
            onActivate={() => activateMutation.mutate(live.id)}
          />
        )
      )}

      {blocked !== null && (
        <RefusalStrip role="note" data-testid="cannot-propose">
          {blockedSentence(context, translate)}
        </RefusalStrip>
      )}

      {/* ── The three steps, on the SHARED frame (`DEF-CUS-5071`) ────────
          B14 rule 3: a flow with 2+ stages uses the numbered rail and a
          wizard-actions footer. `WizardFrame` owns both, the ✓ commit, its
          single flight and A18 §3/§4. Nothing renders when the account may
          not have a plan proposed — `blocked` says why, above. */}
      {blocked === null && (
        <>
          {/* BR-SHL-046 — the count comes from the DECLARED list. */}
          <p className="met-panel-hint">
            {t("customers.paymentPlan.stepOf", {
              step: nav.step,
              of: PAYMENT_PLAN_STEPS.length,
              // `DEF-CUS-5171` — the drawn sub-line is `Step 1 of 3 · Terms`.
              name: t(
                PAYMENT_PLAN_STEP_LABEL_KEYS[PAYMENT_PLAN_STEPS[nav.step - 1] ?? "terms"],
              ),
            })}
          </p>
          <WizardFrame
            steps={steps}
            nav={nav}
            onNavChange={setNav}
            secondaryActions={recalculate}
            commitLabel={t("customers.paymentPlan.sendAgreement")}
            commitFailedTitle={t("customers.paymentPlan.commitFailed")}
            onCommit={runSend}
            onCommitted={() => undefined}
          />
        </>
      )}

    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-018@bbed56d (05-golden-tests.md + EP-CUS-06-payment-plan.md + 03-customers/02-business-rules.md + J13-payment-plan-life.md)
// generated: 2026-08-16 by story-coder (surface-debt tails lane — S24, the wizard whose engine shipped on 2026-08-11 with nothing to click)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report for the verbatim RED transcripts — the balance
//         tile was first rendered with a `?? "0.00"` fallback and the test
//         FAILED on `assert '0.00' is None`, and the GT-47 schedule was first
//         computed with the remainder spread evenly (6 × 36.22 = 217.32) and
//         the endpoint refused with BR-CUS-043's own sentence
// exceptions: (1) NO VOID CONTROL and no `defaulted` state anywhere on this
//         screen — PO 2026-08-11, *"nodrop we chase for payments until write
//         off"*. Whether staff may CANCEL a plan is OQ-239, minted by this lane
//         and unanswered, so nothing is drawn for it.
//         (2) THE AGREEMENT DOCUMENT IS NOT RENDERED HERE. Its body is the S67
//         contract template (BR-NOT-004 ①) and its e-sign envelope is
//         integrations' (B7); this screen records the channel ELECTION and says
//         on its face that the agreement is QUEUED and that no e-signature
//         provider is connected.
//         (3) THE DOWN PAYMENT IS NOT TAKEN HERE. It is a `payments` row with
//         purpose `plan_down` (BR-PAY-012) through the ordinary intake path
//         (US-CUS-012's Record payment), which is the only writer of that
//         table. The field captures the AMOUNT the schedule is built on.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
