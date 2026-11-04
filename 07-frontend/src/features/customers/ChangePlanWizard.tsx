// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-016 (S23 steps 1–2 — pick a plan, set the effective date,
//           and read the proration preview) ·
//           US-CUS-017 (S23 step 3 — confirm, sync the unit, notify)
// Change:   CR-013 part 5 — **PLN-04, "change an account's plan"**. Row 16 of
//           the 16-surface inventory (`06-rating/09-screen-inventory.md` §18).
//           ⚠ THE INVENTORY CALLS ROW 16 **NEW** AND IT IS NOT — this screen
//           has been built since 2026-08-11, with exactly the CR's three steps
//           (*"pick new plan · effective date & proration · confirm & notify"*).
//           Row 16 is the one row of sixteen whose file lives in ANOTHER
//           module's folder, which is how the enumeration missed it. **DEF-420.**
//           Building it "new" would have shipped a second door onto one write.
//           What the CR actually added, and what this lane built, is two things:
//             · **ineligible plans LISTED WITH THE FAILING RULE, not filtered
//               out** — *"an absent option teaches the operator the product
//               cannot do it."* The server used to `continue` past them
//               (`apps/customers/services.py`); it now emits the row with an
//               `ineligible_reason` CODE and the screen draws it disabled with
//               the reason. **Listed is not offered** — whether the mismatch
//               case should become acknowledgeable the way `drops_services`
//               already is, is the PO's: **OQ-302**.
//             · **the deposit differential is READ.** See below — it was on the
//               wire and nothing consumed it (hard-won law 2).
//           Screens: S23 (A1) / **PLN-04** (r10 draws no badge; CR-013 numbers
//           it) — entered from the S21 "Change plan" action
// Rules:    BR-CUS-041 (published + service-compatible plans only; effective
//           immediate / next-cycle / custom; a service-dropping change needs an
//           explicit acknowledgment) · BR-CUS-042 vs BR-CUS-062 (the deposit
//           differential — two CONFIRMED rules disagree, OQ-179, so no deposit
//           figure is drawn) · BR-CUS-011 (who/when/from→to/reason/source) ·
//           BR-CUS-013 (the assignment SNAPSHOTS the plan version) ·
//           BR-CUS-029 SUPERSEDED (there is no account-side plan record — the
//           account DERIVES its plan from the unit) · BR-RAT-030 (drafts are
//           not assignable) · BR-RAT-043 (eligibility is advisory-with-audit —
//           the wizard SHOWS the note and LOGS the checkbox; it never gates) ·
//           BR-RAT-004 / B4.3 (proration is the rating engine's, and this
//           screen computes no money at all) · BR-SHL-020 (plain language) ·
//           BR-SHL-025 (a control that cannot be honoured is disabled WITH its
//           reason) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S23 — the three-step Change Plan page.
//
// THE ONE RULE THIS FILE IS WRITTEN AROUND: **it computes no money.** Not the
// base delta, not the proration, not the net impact. Every figure it draws is a
// NUMERIC(18,6) string the server produced, and the preview says which function
// produced the prorated ones (`proration.computed_by`). B4.3 is finance-signed
// and frozen; a subtraction typed here would be a second implementation of
// signed money law, on a screen a customer is read from.
//
// WHAT THIS SCREEN CANNOT SHOW, AND SAYS SO INSTEAD OF DRAWING A ZERO
// ───────────────────────────────────────────────────────────────────
//   · **The deposit differential.** US-CUS-016 §7 works it as −$50.00 and its
//     net impact as −$68.50. BR-CUS-042 says compute it; BR-CUS-062 (the later
//     PO ruling, corroborated by 11b §2.6 and by the rating module's own
//     proration docstring) says there is no deposit recompute in v1. Two
//     CONFIRMED rules, one customer-facing figure — OQ-179. The line renders as
//     not-computed WITH the reason, and the net impact says it excluded it.
//     ⚠ **AMENDED 2026-08-21 (CR-013 part 5): THE SLOT NOW READS THE FIGURE.**
//     `deposit_differential` has been on the wire since this file was written
//     and NOTHING CONSUMED IT — the component rendered only the not-computed
//     note, so the day OQ-179 is ruled and the server begins stating the
//     amount, this screen would still have said "not computed" and no test
//     would have gone red. That is hard-won law 2 exactly. The figure is
//     rendered when the server states one and the reason when it does not;
//     **OQ-179 is NOT resolved here and no amount is computed, defaulted or
//     zeroed** — a `0.00` would read as "no deposit is owed" rather than
//     "nobody has ruled what is owed".
//   · **The usage half of a mid-cycle split.** B4.3 prorates usage too, and
//     pricing usage for a period that has not happened needs a forecast no rule
//     defines (OQ-180).
//   · **The prorated base lines, today.** Metering publishes no read of a
//     unit's cycle window, so a mid-cycle split cannot be LOCATED on a
//     calendar. Assuming a 30-day month would invent money from a calendar
//     nobody configured.
//   · **"Next cycle start" as an effective-date option.** Same missing read:
//     nobody can name the day. The option renders DISABLED with that reason
//     rather than sending a request that will be refused.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  confirmPlanChange,
  getAccountDetail,
  getPlanChangeOptions,
  previewPlanChange,
} from "@/api/endpoints";
import type {
  PlanChangeOption,
  PlanChangePreview,
  PlanChangeResult,
  PreviewUnavailable,
} from "@/api/endpoints";
import { CheckboxField, DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { CustomFieldsInput, customDataChanges } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import { initialWizardNav, WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { MoneyCell } from "@/components/MoneyCell";
import { formatDate } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { PlainTable, RefusalStrip } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import {
  CELL_FULL,
  Dash,
  GuardedButton,
  isDenied,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
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

import "./customers.css";

// ── Pure pieces (provable without a browser or a network) ──────────────────

export const CHANGE_PLAN_STEPS = ["plan", "effective", "confirm"] as const;
export type ChangePlanStep = (typeof CHANGE_PLAN_STEPS)[number];

/**
 * ⛔ **`DEF-CUS-5071` — THE RAIL'S WORDS, AND WHY THIS MAP EXISTS AT ALL.**
 *
 * `CHANGE_PLAN_STEPS` had **two readers in the whole repository**: its own
 * type alias on the line above, and `AccountActions.test.tsx`, which asserted
 * the array equals `["plan","effective","confirm"]` — the array equalling
 * itself. **Nothing rendered it**, so this and the payment plan were the only
 * two of eleven customers wizards with no step rail: zero rail nodes on step 1
 * AND on step 2 after a plan was picked, measured in Chromium on `brazosbend`
 * 2026-09-12, and the words `Plan`/`Effective`/`Confirm` appeared nowhere.
 * The blueprint drew the rail and stamped its own frame **`NO STEPPER IS
 * RENDERED`**, unable to tell whether the rail arrived after the first choice
 * or the drawing was wrong; walking to step 2 settled it.
 *
 * **B14 rule 3 is RATIFIED and unenforced:** *"Any flow with 2+ stages uses
 * the numbered step rail (clickable when complete) + a wizard-actions
 * footer."* Nine siblings in this folder get that from `components/WizardFrame`
 * and these two did not, so this is a WIRING job and not a second rail — a
 * hand-rolled one here would be the tenth place the rail, the Back/Continue
 * row, the single-flight commit and A18's working and failed states each got
 * an opinion.
 *
 * The rail is BUILT FROM THIS CONST by `.map()`, which is the half that
 * matters for the next change: a fourth step added to the array appears on the
 * rail, and a step whose label key is missing is a typecheck error rather than
 * a silent gap. Keys are LITERAL strings so G18 can see them.
 */
export const CHANGE_PLAN_STEP_LABEL_KEYS: Record<ChangePlanStep, string> = {
  plan: "customers.planChange.step.plan",
  effective: "customers.planChange.step.effective",
  confirm: "customers.planChange.step.confirm",
};

/**
 * ⚠ **THE PAGE TITLE IS THE STEP'S OWN QUESTION — `DEF-CUS-5171`, B14 rule 41.**
 *
 * `13-change-plan-wizard.md` draws three heads and they are three different
 * sentences: **`Pick a plan`** · **`When does it take effect?`** ·
 * **`Confirm the change`**, each under the kicker `CHANGE PLAN` and over a
 * sub-line `Step 1 of 3 · Plan`. The product drew `Change plan` on all three
 * with the account number as its kicker — the drawing's two halves, swapped,
 * and the step's name nowhere.
 *
 * It is a title rather than a heading because that is where the drawing puts
 * it, and B14 rule 2 allows exactly one page head per screen: a second
 * `<h1>`-sized question inside the body would be two heads on one surface.
 * The rail already names the step; this says what the step ASKS.
 */
export const CHANGE_PLAN_TITLE_KEYS: Record<ChangePlanStep, string> = {
  plan: "customers.planChange.title.plan",
  effective: "customers.planChange.title.effective",
  confirm: "customers.planChange.title.confirm",
};

export const planChangeOptionsKey = (accountId: string) =>
  ["accounts", "plan-change-options", accountId] as const;

/**
 * US-CUS-016 TC-6: a plan covering fewer services than the unit takes DROPS
 * one, and Continue is blocked until the clerk acknowledges it explicitly.
 *
 * Returns the acknowledgment requirement rather than a boolean "ok", because
 * the screen has to render WHICH services would be lost — "no silent service
 * loss" is the rule, and a bare veto teaches nothing.
 */
export function requiresServiceDropAck(plan: PlanChangeOption | null): boolean {
  return plan !== null && plan.drops_services.length > 0;
}

/**
 * CR-013 part 5 (PLN-04): *"ineligible plans listed with the failing rule, not
 * filtered out"*.
 *
 * ⚠ LISTED IS NOT OFFERED. The row is drawn with its reason and is
 * UNSELECTABLE — BR-SHL-025's shape, and the same posture step 2 of PLN-03
 * takes for a service with no schedule. Until 2026-08-21 the server simply
 * skipped these rows, so a clerk looking for a plan they had just published saw
 * nothing at all and had nothing to read (OQ-302).
 */
export function planIsSelectable(plan: PlanChangeOption): boolean {
  return plan.ineligible_reason === null;
}

/**
 * The sentence under an ineligible row. One translated string per catalogue,
 * keyed by the SERVER's code — never a server-assembled phrase, and never a
 * generic "not eligible" that tells the clerk nothing they can act on.
 *
 * An unknown code renders the code itself rather than a blank: a reason nobody
 * has translated yet is still a reason, and a silent empty line would read as
 * "refused for no stated cause".
 */
export function ineligibleReasonText(plan: PlanChangeOption, t: Translator): string {
  if (plan.ineligible_reason === "covers_unavailable_services") {
    return t("customers.planChange.ineligible.coversUnavailableServices", {
      services: plan.missing_services.join(", "),
    });
  }
  if (plan.ineligible_reason === "no_services") {
    return t("customers.planChange.ineligible.noServices");
  }
  return plan.ineligible_reason ?? "";
}

/**
 * BR-CUS-041's three effective-date options. `next_cycle` is DISABLED and the
 * reason travels with it: the cycle window is a metering read nobody publishes,
 * so nobody can name the day, and the server refuses the option for the same
 * reason. Shown-and-disabled rather than hidden (BR-SHL-025) — a clerk told to
 * "make it effective next cycle" must see that the product knows the option
 * exists.
 */
export interface EffectiveOption {
  value: string;
  labelKey: string;
  /** True = SHOWN and unselectable, with the reason under the field. */
  disabled?: boolean;
}

export const EFFECTIVE_OPTIONS: readonly EffectiveOption[] = [
  { value: "immediately", labelKey: "customers.planChange.effective.immediately", disabled: true },
  { value: "next_cycle", labelKey: "customers.planChange.effective.nextCycle", disabled: true },
  { value: "custom", labelKey: "customers.planChange.effective.custom" },
];

/**
 * ⚠ **THE SERVER'S OWN SENTENCE NO LONGER REACHES A CLERK — `DEF-CUS-5170`.**
 *
 * `UnavailableNote` printed `unavailable.detail` — an ENGINEERING sentence —
 * and then `br_refs`/`oq_ref` after it, so **`BR-CUS-042 · BR-CUS-062 ·
 * OQ-179`** and **`BR-RAT-004 · OQ-180`** were on the screen of anybody
 * changing a plan, measured in Chromium on `brazosbend` 2026-09-13. `B14` rule
 * 31 is exact about this — *"not a rule number … not a path, not a function
 * name"* — and rule 33 adds the half that decides the shape of the fix:
 * **RATIONALE is ZERO WORDS on screen.**
 *
 * So the reason moves HERE, keyed by the server's CODE, and the screen says
 * what the drawing says. `13-change-plan-wizard.md` gives the deposit line one
 * sentence — *"The deposit is not worked out again in this version. The amount
 * set at move-in stands."* — and that is the whole of it.
 *
 * ⚠ **AN UNKNOWN CODE STILL SAYS SOMETHING.** A silent empty line would read
 * as *refused for no stated cause*, so an unmapped code renders the neutral
 * not-calculated sentence and the CODE itself rides nowhere near the screen.
 */
export const UNAVAILABLE_REASON_KEYS: Record<string, string> = {
  deposit_differential_unavailable: "customers.planChange.unavailable.deposit",
  usage_unavailable: "customers.planChange.unavailable.usage",
  proration_unavailable: "customers.planChange.unavailable.proration",
};

/** The block's own heading. `13-change-plan-wizard.md` heads the deposit
 *  absence `DEPOSIT DIFFERENTIAL` and puts the sentence under it — the LINE
 *  names itself and the sentence says what happened to it. Two blocks both
 *  headed `Not calculated` say neither. */
export const UNAVAILABLE_LABEL_KEYS: Record<string, string> = {
  deposit_differential_unavailable: "customers.planChange.depositDifferential",
  usage_unavailable: "customers.planChange.usageLine",
  proration_unavailable: "customers.planChange.proratedLine",
};

/**
 * A server-stated absence, **in this screen's words** — `DEF-CUS-5170`.
 *
 * ⚠ **IT USED TO PRINT THE SERVER'S PARAGRAPH AND ITS IDS.** `unavailable.detail`
 * is engineering prose and `br_refs`/`oq_ref` are repository references, and all
 * three reached a clerk: `BR-CUS-042 · BR-CUS-062 · OQ-179` under the deposit
 * line and `BR-RAT-004 · OQ-180` under the usage one. B14 rule 31 keeps a rule
 * number off a screen and rule 33 keeps RATIONALE off one entirely, and the
 * drawing agrees with both — it gives the deposit absence ONE sentence.
 *
 * The provenance is not deleted, it MOVES: the codes are mapped in
 * `UNAVAILABLE_REASON_KEYS` above and the server's reasoning stays on the
 * server, which is where a reader who needs it can still find it.
 */
export function UnavailableNote(props: {
  unavailable: PreviewUnavailable;
  /** Which absence this is. Optional because the payload already carries it —
   *  see below; a caller passes it only where the two could differ. */
  slot?: string;
  t: Translator;
}) {
  const { unavailable, t } = props;
  // ⚠ **THE SLOT COMES OFF THE PAYLOAD WHEN A CALLER DOES NOT NAME ONE.**
  // `unavailable.code` IS the slot on every `*_unavailable` payload this
  // product serves, so requiring the caller to repeat it is two sources for
  // one fact — and the first draft of this component destructured
  // `unavailable` and then read nothing off it, which eslint caught and which
  // is hard-won law 2 in miniature: a prop nothing consumes.
  const slot = props.slot ?? unavailable.code;
  const key = UNAVAILABLE_REASON_KEYS[slot];
  return (
    <p className="cus-unavailable" role="note" data-unavailable={slot}>
      <span className="cus-unavailable-label">
        {t(UNAVAILABLE_LABEL_KEYS[slot] ?? "customers.planChange.notComputed")}
      </span>
      <span className="cus-unavailable-detail">
        {key === undefined ? t("customers.planChange.notComputedHelp") : t(key)}
      </span>
    </p>
  );
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface ChangePlanWizardProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

/**
 * `DEF-CUS-9170` — the answers every OPEN service agreement already shares, so
 * Change plan's service fields open on what is true for all of them. A key the
 * agreements disagree on (or one holds and another does not) opens blank; the
 * clerk sees no value rather than one agreement's value presented as all's.
 * Only keys the clerk then CHANGES travel, and the server merges them into each
 * agreement's own stored answers.
 */
export function sharedAgreementAnswers(
  agreements: readonly { ended_on: string | null; custom_data?: Record<string, unknown> }[],
): CustomFieldValues {
  const open = agreements.filter((row) => row.ended_on === null);
  if (open.length === 0) return {};
  const first = open[0].custom_data ?? {};
  const out: CustomFieldValues = {};
  for (const key of Object.keys(first)) {
    const value = JSON.stringify(first[key]);
    if (open.every((row) => JSON.stringify((row.custom_data ?? {})[key]) === value)) {
      out[key] = first[key];
    }
  }
  return out;
}

export function ChangePlanWizard(props: ChangePlanWizardProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const fireToast = useToast();
  const { dateFormat } = useRegional(props);
  const accountId = params.accountId ?? "";

  // `DEF-CUS-5071` — the frame owns navigation now, so there is ONE number for
  // the step: its nav state. The old `useState<ChangePlanStep>` is gone rather
  // than kept beside it, because two sources for one number is how a rail comes
  // to say four while the footer says six (`DEF-648`).
  const [nav, setNav] = useState<WizardNavState>(initialWizardNav);
  const [planId, setPlanId] = useState("");
  const [dropAck, setDropAck] = useState(false);
  const [effectiveOn, setEffectiveOn] = useState("");
  const [reason, setReason] = useState("");
  const [notify, setNotify] = useState(true);
  const [proofLogged, setProofLogged] = useState(false);
  const [preview, setPreview] = useState<PlanChangePreview | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [result, setResult] = useState<PlanChangeResult | null>(null);
  // `DEF-CUS-9170` — the utility's own SERVICE-AGREEMENT fields placed Input
  // on Change plan (slot `S23`). `null` until the clerk touches one, so the
  // controls open on the answers the account's open agreements already share.
  const [serviceCustom, setServiceCustom] = useState<CustomFieldValues | null>(null);

  const cell = useAccessCell(ACCOUNTS_PERMISSION, client);
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("customers.accounts.rbac.readOnly");

  const detailQuery = useQuery({
    queryKey: ["accounts", "detail", accountId],
    queryFn: () => getAccountDetail(accountId, client),
    enabled: accountId !== "",
  });
  const serviceSeed = sharedAgreementAnswers(detailQuery.data?.service_agreements ?? []);
  const serviceValues = serviceCustom ?? serviceSeed;
  const serviceChanged = customDataChanges(serviceSeed, serviceValues);
  const optionsQuery = useQuery({
    queryKey: planChangeOptionsKey(accountId),
    queryFn: () => getPlanChangeOptions(accountId, client),
    // `DEF-CUS-5178` — an account with no unit derives no plan, so this read
    // can only 404. Not asking is better than asking and explaining: a request
    // the caller knows will fail is a 404 in the server's log for a condition
    // that is not an error.
    enabled: accountId !== "" && detailQuery.data?.unit_id != null,
    retry: false,
  });

  const previewMutation = useMutation({
    mutationFn: () =>
      previewPlanChange(accountId, { rate_plan_id: planId, effective_on: effectiveOn }, client),
    onSuccess: (data) => {
      setPreview(data);
      setRefusal(null);
    },
    onError: (error: unknown) => {
      setPreview(null);
      setRefusal(apiErrorText(error, translate));
    },
  });

  const confirmMutation = useMutation({
    mutationFn: () =>
      confirmPlanChange(
        accountId,
        {
          rate_plan_id: planId,
          effective_on: effectiveOn,
          reason: reason === "" ? null : reason,
          notify,
          eligibility_proof_logged: proofLogged,
          ...(Object.keys(serviceChanged).length > 0
            ? { service_custom_data: serviceChanged }
            : {}),
        },
        client,
      ),
    onSuccess: (data) => {
      setResult(data);
      setRefusal(null);
      // US-CUS-017's exit toast. "customer notified" is said ONLY when a queue
      // row exists — `notification` is null when the election was off AND when
      // the queue refused, and the second case is in `problems` too.
      fireToast(
        data.notification !== null
          ? t("customers.planChange.toast.changedAndNotified", {
              date: data.assignment.assigned_from,
            })
          : t("customers.planChange.toast.changed", { date: data.assignment.assigned_from }),
      );
    },
    // `DEF-CUS-5071` — the FRAME reports a failed commit now, through A18 §4's
    // `FailedWithRetry` with every entered value still on screen. Setting
    // `refusal` as well would print the same sentence twice, in two places, on
    // one press. The preview mutation above still uses the strip, because a
    // preview is not the commit and has no frame card of its own.
    onError: () => undefined,
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("customers.accounts.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  // ⚠ **THE ACCOUNT'S OWN READ IS AWAITED; THE OPTIONS READ IS NOT, YET.**
  // `DEF-CUS-5178` — a wizard that cannot run on this account must say so at
  // first paint rather than spinning through a request whose answer it already
  // knows. The options guard is below, after the refusal.
  if (detailQuery.isPending) {
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
  const detail = detailQuery.data;
  // ⛔ **`DEF-CUS-5178` — AN ACCOUNT THAT HOLDS NO UNIT HAS NO PLAN TO CHANGE,
  //     AND THE SCREEN KNOWS THAT BEFORE IT ASKS.**
  //
  // A master account carries sub-accounts and no unit of its own
  // (`unit_id: null`), and `BR-CUS-029` is SUPERSEDED in the direction that
  // makes this decisive: **the account DERIVES its plan from the unit.** No
  // unit, no plan, nothing to move to — so `GET …/plan-changes/options`
  // answers `404`, correctly.
  //
  // ⚠ **THE SCREEN USED TO READ THAT 404 AS A FAILURE.** It fell to
  // `FailedWithRetry` and told a clerk *"We could not find that. It may have
  // been removed, or the address may be wrong."* over a correct address, on an
  // account that will never have a plan, with a `Retry` that can only fail
  // again. Measured at 1280 and 1440 on `AC-2026-00052`: a 253px card where
  // every sibling dialog is 648–836.
  //
  // ⚠ **SO THE FACT IS READ, NOT THE STATUS CODE.** `detail.unit_id` is
  // already in hand and is the thing that decides it; inferring a business
  // refusal from an HTTP status is how a screen comes to say *the address may
  // be wrong* about a correct address. The transport failure keeps its own
  // branch below, unchanged — a server that genuinely fell over must still be
  // retryable.
  //
  // ⚠ **THE DOOR IS A SEPARATE HALF AND IS NOT THIS FILE'S.** The rail gates
  // `Change plan` on `status_behavior_class`, and a master account is active
  // and billable — so the control is LIVE and lands here. That is
  // `AccountDetailPage.tsx`'s gate to widen; this screen refuses properly
  // whichever door opened it, including the address typed by hand and the
  // Overview's Plan group (`R5`).
  if (detail.unit_id === null) {
    return (
      <div className="cus-page">
        <PageHeader
          backTo={{
            to: tenantPath(accountDetailPath(accountId)),
            label: accountHeadline(detail, translate),
          }}
          kicker={t("customers.planChange.kicker")}
          title={t(CHANGE_PLAN_TITLE_KEYS.plan)}
        />
        <RefusalStrip role="alert" data-refusal="no-unit">
          {t("customers.planChange.noUnit")}
        </RefusalStrip>
        <Panel as="section">
          <p className="met-panel-hint">{t("customers.planChange.noUnitHelp")}</p>
          <GuardedButton
            label={t("customers.planChange.backToAccount")}
            reason={null}
            variant="primary"
            onClick={() => navigate(tenantPath(accountDetailPath(accountId)))}
          />
        </Panel>
      </div>
    );
  }
  if (optionsQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (optionsQuery.data === undefined) {
    // The picker is the whole of step 1: without it there is no wizard, and an
    // empty list would claim this account has no plan to move to.
    return (
      <FailedWithRetry
        title={t("customers.planChange.title")}
        reason={apiErrorText(optionsQuery.error, translate)}
        onRetry={() => void optionsQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(accountDetailPath(accountId)))}
      />
    );
  }

  const options = optionsQuery.data;
  const selected = options.plans.find((row) => row.id === planId) ?? null;
  const dropBlocked = requiresServiceDropAck(selected) && !dropAck;

  const step1Reason =
    writeBlockedReason ??
    (selected === null
      ? t("customers.planChange.pickAPlan")
      : // The disabled radio already prevents this, so this branch is the
        // BELT to that brace: a plan the server refuses must not reach step 2
        // by any route, and Continue says which rule refuses it.
        !planIsSelectable(selected)
        ? ineligibleReasonText(selected, translate)
        : dropBlocked
          ? t("customers.planChange.acknowledgeDrop")
          : null);
  const step2Reason =
    writeBlockedReason ??
    (effectiveOn === ""
      ? t("customers.planChange.pickADate")
      : preview === null
        ? t("customers.planChange.previewFirst")
        : null);

  /**
   * `DEF-CUS-5071` — the three DECLARED steps, in the declared order, each
   * with the rail label its id names and the refusal its own Continue owes.
   * Built by `.map()` over `CHANGE_PLAN_STEPS` so the rail cannot fall out
   * of step with the list, and so a fourth step appears on it.
   *
   * ⚠ **A STEP'S `validate` RETURNS THE SENTENCE, NOT A BOOLEAN.** The old
   * hand-rolled footer used `GuardedButton`, which renders Continue
   * DISABLED with its reason in a tooltip; the frame renders Continue
   * live and prints the refusal at the button that refused it (`DEF-178`,
   * and `DEF-936` for the per-step sentence). **That is a divergence from
   * the drawing, which inks a greyed Continue, and B14 rule 38 settles it:
   * where a drawing and our UI rules disagree about how a form is BUILT,
   * the UI rules win.** The nine siblings all behave this way and the
   * alternative was a tenth footer with its own opinion.
   */
  const stepContent: Record<ChangePlanStep, ReactNode> = {
    plan: (
      <>
        <Panel as="section">
          {/* The drawing labels the picker `New plan` (`13-change-plan-wizard.md`);
              the product headed it `1 · Pick the new plan`, which repeats the
              step number the rail and the sub-line both already carry. */}
          <h3>{t("customers.planChange.newPlan")}</h3>
          {/* ⚠ **A DRAWN SENTENCE THAT WAS NOT BUILT.** It is also what replaces
              the roll-up's `Services at this unit` row: the same fact, said in
              the form a clerk can act on. */}
          <p className="met-panel-hint">{t("customers.planChange.onlyCovering")}</p>
          {options.plans.length === 0 ? (
            <p className="met-panel-hint">{t("customers.planChange.noCompatiblePlans")}</p>
          ) : (
            <ul className="cus-plan-list">
              {options.plans.map((plan) => (
                <li key={plan.id} className="cus-plan-row">
                  <label className="radio" htmlFor={`plan-${plan.id}`}>
                    <input
                      id={`plan-${plan.id}`}
                      type="radio"
                      name="rate_plan_id"
                      value={plan.id}
                      checked={planId === plan.id}
                      // CR-013 part 5: listed WITH the failing rule, and
                      // unselectable. `disabled` rather than hidden is the
                      // whole point of the row existing (BR-SHL-025).
                      disabled={!planIsSelectable(plan)}
                      onChange={() => {
                        setPlanId(plan.id);
                        setDropAck(false);
                        setPreview(null);
                      }}
                    />
                    <span className="dot" aria-hidden="true" />
                    <span>{plan.name}</span>
                  </label>
                  {/* The failing rule, in the clerk's language. Drawn from the
                      server's CODE so the sentence is one translated string. */}
                  {!planIsSelectable(plan) && (
                    <StatusPill tone="neutral">
                      {ineligibleReasonText(plan, translate)}
                    </StatusPill>
                  )}
                  <span className="cus-plan-meta">
                    {plan.base_charges !== null ? (
                      <MoneyCell amount={plan.base_charges} currency={detail.currency} />
                    ) : (
                      <Dash />
                    )}
                    <span className="met-qualifier"> {t("customers.planChange.perMonthBase")}</span>
                  </span>
                  {plan.is_current && (
                    <StatusPill tone="neutral">{t("customers.planChange.currentPill")}</StatusPill>
                  )}
                  {/* US-CUS-016 TC-1's per-row notes, assembled from CODES so
                      each sentence is one translated string. */}
                  {plan.drops_services.length > 0 && (
                    <StatusPill tone="danger">
                      {t("customers.planChange.dropsServices", {
                        services: plan.drops_services.join(", "),
                      })}
                    </StatusPill>
                  )}
                  {plan.requires_eligibility.length > 0 && (
                    <StatusPill tone="warning">
                      {t("customers.planChange.requiresEligibility")}
                    </StatusPill>
                  )}
                </li>
              ))}
            </ul>
          )}
          {requiresServiceDropAck(selected) && (
            <CheckboxField
              id="drop_ack"
              label={t("customers.planChange.dropAck", {
                services: (selected?.drops_services ?? []).join(", "),
              })}
              checked={dropAck}
              onChange={setDropAck}
            />
          )}
        </Panel>
      </>
    ),
    effective: (
      <>
        <Panel as="section">
          {/* No section heading: `13-change-plan-wizard.md` heads step 2 with
              the page title (`When does it take effect?`) and goes straight to
              the `Effective` field. `2 · Effective date and what it costs` was
              a second heading saying the same thing one size smaller. */}
          <SelectField
            id="effective_option"
            label={t("customers.planChange.effectiveOption")}
            value="custom"
            onChange={() => undefined}
            options={EFFECTIVE_OPTIONS.map((option) => ({
              value: option.value,
              label: t(option.labelKey),
              disabled: option.disabled === true,
            }))}
            // BR-SHL-025: "Next cycle start" is shown and unselectable, with
            // the reason under the field. The DATE is what the server needs,
            // and nobody can name next cycle's first day.
            help={t("customers.planChange.effectiveHelp")}
          />
          <DatePickerField
            id="effective_on"
            label={t("customers.planChange.effectiveOn")}
            value={effectiveOn}
            onChange={(value) => {
              setEffectiveOn(value);
              setPreview(null);
            }}
            dateFormat={dateFormat}
            required
            help={t("customers.planChange.effectiveOnHelp")}
          />
          <GuardedButton
            label={t("customers.planChange.showPreview")}
            reason={
              writeBlockedReason ??
              (effectiveOn === "" ? t("customers.planChange.pickADate") : null)
            }
            working={previewMutation.isPending}
            onClick={() => previewMutation.mutate()}
          />

          {preview !== null && <PreviewPanel preview={preview} t={translate} />}

        </Panel>
      </>
    ),
    confirm: (
      <>
        <Panel as="section">
          {/* As step 2: the page title is `Confirm the change` and the drawing
              puts the from/to facts directly under it. */}
          <dl className="met-facts">
            <div>
              <dt>{t("customers.planChange.from")}</dt>
              <dd>{options.current_plan.name}</dd>
            </div>
            <div>
              <dt>{t("customers.planChange.to")}</dt>
              <dd>{selected?.name ?? <Dash />}</dd>
            </div>
            <div>
              <dt>{t("customers.planChange.effectiveOn")}</dt>
              {/* ⚠ **THROUGH `formatDate`, NOT PRINTED AS ISO.** `BR-SHL-023`
                  keeps ONE formatting path in this product, and this line
                  printed `2026-10-01` to a tenant who had asked for
                  `MM/DD/YYYY` — the same fault `DisconnectWizard`'s floor line
                  was fixed for on 2026-09-12. */}
              <dd>{effectiveOn === "" ? <Dash /> : formatDate(effectiveOn, "UTC", dateFormat)}</dd>
            </div>
          </dl>
          {preview !== null && <PreviewPanel preview={preview} t={translate} />}
          <TextField
            id="reason"
            label={t("customers.planChange.reason")}
            value={reason}
            onChange={setReason}
            help={t("customers.planChange.reasonHelp")}
          />
          <CheckboxField
            id="notify"
            label={t("customers.planChange.notify")}
            checked={notify}
            onChange={setNotify}
          />
          <CheckboxField
            id="eligibility_proof"
            label={t("customers.planChange.logEligibilityProof")}
            checked={proofLogged}
            onChange={setProofLogged}
          />
          {/* BR-RAT-043: advisory-with-audit. The checkbox is EVIDENCE on the
              trail, never a gate — its absence does not block v1 (TC-3). */}
          <p className="pay-form-note">{t("customers.planChange.eligibilityAdvisory")}</p>
          {/* `DEF-CUS-9170` — renders NOTHING when the utility placed no
              service-agreement field Input on Change plan. Never priced. */}
          <CustomFieldsInput
            entity="service_agreements"
            screen="S23"
            values={serviceValues}
            onChange={setServiceCustom}
            client={client}
          />
        </Panel>
      </>
    ),
  };
  const stepRefusal: Record<ChangePlanStep, string | null> = {
    plan: step1Reason,
    effective: step2Reason,
    confirm: writeBlockedReason,
  };
  const steps: WizardStep[] = CHANGE_PLAN_STEPS.map((id) => ({
    id,
    label: t(CHANGE_PLAN_STEP_LABEL_KEYS[id]),
    content: stepContent[id],
    validate: () => stepRefusal[id] ?? true,
  }));

  /** ONE transactional call (BR-SHL-019). The frame single-flights the
   *  press, renders A18 §3 while it is out and A18 §4 with every entered
   *  value still on screen if it fails. */
  async function runConfirm(): Promise<WizardCommitOutcome> {
    try {
      await confirmMutation.mutateAsync();
      return { ok: true };
    } catch (error: unknown) {
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }


  return (
    <div className="cus-page">
      {/* ⚠ **THE DRAWN HEAD — `DEF-CUS-5171`, B14 rule 41.** `CHANGE PLAN` is
          the kicker and the STEP'S QUESTION is the title; the product had the
          two the other way round with one fixed title on all three steps. The
          roll-up is the drawing's step-1 rail, which is exactly two rows:
          `Current plan` and `Current base`.

          ⚠ **`Services at this unit` IS GONE AND THAT IS THE RULE BEING
          FOLLOWED, NOT AN OVERSIGHT.** Rule 41: *"which facts appear is the
          drawing's"*. The fact it carried is not lost — the drawing states it
          as a sentence under the picker instead (*"Only plans that cover this
          account's services are offered."*), which is the same information in
          the form a clerk can act on. */}
      <PageHeader
        backTo={{
          to: tenantPath(accountDetailPath(accountId)),
          label: accountHeadline(detail, translate),
        }}
        kicker={t("customers.planChange.kicker")}
        title={t(CHANGE_PLAN_TITLE_KEYS[CHANGE_PLAN_STEPS[nav.step - 1] ?? "plan"])}
        rollup={
          <span className="cus-rollup">
            <span className="cus-rollup-item">
              <span className="cus-rollup-label">{t("customers.planChange.currentPlan")}</span>
              <span className="cus-rollup-value">{options.current_plan.name}</span>
            </span>
            <span className="cus-rollup-item">
              <span className="cus-rollup-label">{t("customers.planChange.currentBaseShort")}</span>
              {/* Every money figure on this screen is the SERVER's string
                  through `MoneyCell` — nothing here divides, adds or rounds. */}
              <span className="cus-rollup-value">
                {options.current_plan.base_charges != null ? (
                  <>
                    <MoneyCell
                      amount={options.current_plan.base_charges}
                      currency={detail.currency}
                    />
                    <span className="met-qualifier"> {t("customers.planChange.perMonth")}</span>
                  </>
                ) : (
                  <Dash />
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


      {/* ── The three steps, on the SHARED frame (`DEF-CUS-5071`) ────────
          B14 rule 3: a flow with 2+ stages uses the numbered rail and a
          wizard-actions footer. `WizardFrame` owns both, plus the ✓ commit
          and its working and failed states. This screen declares steps. */}
      {result !== null ? (
        // A RECEIPT IS NOT A STEP. Once the change is made the rail has
        // nothing left to navigate and a Continue would be a lie, so the
        // frame is replaced by what happened — including what did NOT
        // happen, from the server's own codes (the deposit differential is
        // in `problems` on every change, OQ-179).
        <Panel as="section">
            <div className="pay-result" role="status">
              <h4>{t("customers.planChange.done")}</h4>
              <dl className="met-facts">
                <div>
                  <dt>{t("customers.planChange.effectiveOn")}</dt>
                  <dd>{result.assignment.assigned_from}</dd>
                </div>
                <div>
                  <dt>{t("customers.planChange.historyRow")}</dt>
                  <dd>{result.assignment.source}</dd>
                </div>
              </dl>
              {/* What did NOT happen, from the server's own codes. The deposit
                  differential is here on every change (OQ-179), and a clerk who
                  expected a $50 refund to be raised has to be told it was not. */}
              {result.problems.map((problem) => (
                <UnavailableNote key={problem.code} unavailable={problem} slot={problem.code} t={translate} />
              ))}
              <GuardedButton
                label={t("customers.planChange.backToAccount")}
                reason={null}
                variant="primary"
                onClick={() => navigate(tenantPath(accountDetailPath(accountId)))}
              />
            </div>
        </Panel>
      ) : (
        <>
          {/* BR-SHL-046 — the count comes from the DECLARED list, so the
              sentence cannot say three while the rail draws four. */}
          <p className="met-panel-hint">
            {t("customers.planChange.stepOf", {
              step: nav.step,
              of: CHANGE_PLAN_STEPS.length,
              // `DEF-CUS-5171` — the drawing's sub-line is `Step 1 of 3 · Plan`
              // and the product printed `Step 1 of 3`. The name comes from the
              // declared step list, so it cannot say Plan while the rail says
              // Effective.
              name: t(
                CHANGE_PLAN_STEP_LABEL_KEYS[CHANGE_PLAN_STEPS[nav.step - 1] ?? "plan"],
              ),
            })}
          </p>
          <WizardFrame
            steps={steps}
            nav={nav}
            onNavChange={setNav}
            commitLabel={t("customers.planChange.confirm")}
            commitFailedTitle={t("customers.planChange.commitFailed")}
            onCommit={runConfirm}
            onCommitted={() => undefined}
          />
        </>
      )}

    </div>
  );
}

export default ChangePlanWizard;

// ── The preview panel ──────────────────────────────────────────────────────

/**
 * Every figure here is the SERVER's string, rendered. Nothing is added,
 * subtracted, formatted into a total or defaulted to zero.
 */
export function PreviewPanel(props: { preview: PlanChangePreview; t: Translator }) {
  const { preview, t } = props;
  return (
    <div className="cus-preview">
      <h4>{t("customers.planChange.previewTitle")}</h4>
      <PlainTable>
        <thead>
          <tr>
            <th>{t("customers.planChange.line")}</th>
            <th>{t("customers.planChange.amount")}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{t("customers.planChange.currentBase")}</td>
            <td>
              <MoneyCell amount={preview.base.current_total} currency={preview.currency} />
            </td>
          </tr>
          <tr>
            <td>{t("customers.planChange.newBase")}</td>
            <td>
              <MoneyCell amount={preview.base.new_total} currency={preview.currency} />
            </td>
          </tr>
          <tr>
            <td>{t("customers.planChange.baseDelta")}</td>
            <td>
              <MoneyCell amount={preview.base.delta} currency={preview.currency} />
            </td>
          </tr>
        </tbody>
      </PlainTable>

      {/* The mid-cycle split — the engine's figures, or the reason there are
          none. `computed_by` is rendered because "the rating engine did this"
          is a claim, and a claim a reader can check is worth more than one they
          have to take on trust (hard-won law 1). */}
      {preview.proration !== null ? (
        <PlainTable>
          <thead>
            <tr>
              <th>{t("customers.planChange.proratedLine")}</th>
              <th>{t("customers.planChange.serviceDays")}</th>
              <th>{t("customers.planChange.amount")}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{preview.proration.current_plan_line.plan}</td>
              <td>{preview.proration.current_plan_line.service_days}</td>
              <td>
                <MoneyCell
                  amount={preview.proration.current_plan_line.amount}
                  currency={preview.currency}
                />
              </td>
            </tr>
            <tr>
              <td>{preview.proration.new_plan_line.plan}</td>
              <td>{preview.proration.new_plan_line.service_days}</td>
              <td>
                <MoneyCell
                  amount={preview.proration.new_plan_line.amount}
                  currency={preview.currency}
                />
              </td>
            </tr>
          </tbody>
        </PlainTable>
      ) : (
        preview.proration_unavailable !== null && (
          <UnavailableNote unavailable={preview.proration_unavailable} slot="proration_unavailable" t={t} />
        )
      )}
      {/* ⚠ **`apps.rating.engine.prorate_base_charge` WAS ON THIS SCREEN —
          `DEF-CUS-5170`.** `computed_by` is a Python module path and a function
          name, and B14 rule 31 names both. The drawing says the same thing in
          four words — *"Computed by the server."* — which is the claim a clerk
          can act on; WHICH function it was is a fact for a log and for this
          comment. The field is still READ (it is what makes the claim true) and
          it rides on `title` as evidence, which rule 31 permits. */}
      {preview.proration !== null && (
        <p className="met-panel-hint" title={preview.proration.computed_by}>
          {t("customers.planChange.computedBy")}
        </p>
      )}

      {/* US-CUS-016 §7's deposit line — CR-013 part 5 makes it half of what
          PLN-04 exists to preview: *"deposit differential, refund or additional
          request"*.

          ⚠ THE SLOT READS THE FIGURE NOW, AND THAT IS THE FIX. `deposit_-
          differential` has been on the wire since this screen was written and
          NOTHING READ IT — the component rendered the not-computed note and
          nothing else, so the day OQ-179 is ruled and the server begins stating
          the figure, the screen would still have said "not computed" and no
          test would have failed. That is hard-won law 2 exactly: a served field
          nothing consumes is a feature that does not exist.

          ⚠ AND NO FIGURE IS INVENTED WHILE IT IS NULL. BR-CUS-042 says compute
          the differential; BR-CUS-062 says there is no deposit recompute in v1.
          Both are CONFIRMED and they disagree — OQ-179 — so this lane does NOT
          choose (prime directive). It renders whichever of the two the SERVER
          states: the amount when there is one, the server's reason when there
          is not, and never a zero, which would read as "no deposit is owed". */}
      {preview.deposit_differential !== null ? (
        // B14 rule 21: NO new stylesheet class. This borrows the net-impact
        // row's declared shape (label · money · qualifier), which is the same
        // shape this line has, rather than minting a class for one paragraph.
        <p className="cus-net-impact">
          <span className="cus-net-impact-label">
            {t("customers.planChange.depositDifferential")}
          </span>
          <MoneyCell amount={preview.deposit_differential} currency={preview.currency} />
          <span className="met-qualifier"> {t("customers.planChange.depositDifferentialHelp")}</span>
        </p>
      ) : (
        preview.deposit_differential_unavailable !== null && (
          <UnavailableNote
            unavailable={preview.deposit_differential_unavailable}
            slot="deposit_differential_unavailable"
            t={t}
          />
        )
      )}
      {preview.usage_unavailable !== null && (
        <UnavailableNote unavailable={preview.usage_unavailable} slot="usage_unavailable" t={t} />
      )}

      <p className="cus-net-impact">
        <span className="cus-net-impact-label">{t("customers.planChange.netImpact")}</span>
        <MoneyCell amount={preview.net_impact.amount} currency={preview.currency} />
        {/* A net that quietly summed a shorter list would be the most dangerous
            number on this screen: it would look like the whole answer. */}
        {/* ⚠ **THE EXCLUDED LINES WERE PRINTED AS THEIR SERVER CODES —
            `DEF-CUS-5170`.** It read *"This total leaves out:
            deposit_differential, usage."* An enum value is an internal
            reference (B14 rule 31), and a clerk asked what the total leaves
            out should be told in words. The codes still choose the words; they
            no longer ARE them. The sentence stays because a net that quietly
            summed a shorter list would be the most dangerous figure here. */}
        <span className="met-qualifier">
          {" "}
          {t("customers.planChange.netExcludes", {
            lines: preview.net_impact.excludes
              .map((code) => t(`customers.planChange.excluded.${code}`, { defaultValue: "" }))
              .filter((word) => word !== "")
              .join(", "),
          })}
        </span>
      </p>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-016@f7c1a20 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/03-customers/06-epics/EP-CUS-04-account-actions.md · 04-docs/05-modules/03-customers/06-epics/EP-CUS-05-change-plan.md · 04-docs/05-modules/03-customers/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.6; co-packet US-CUS-017, same four sources)
// generated: 2026-08-11 by story-coder (W8 customers ACTION lane — S23, the wizard the "Change plan" rail action had been naming in an arrives-with panel)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — screen module) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report — tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔ (G13 unwired-props, G15 i18n-parity across 11 catalogues, G18 call sites, G19 hostnames)
// exceptions: (1) this screen computes NO money — every figure is a server string, and `proration.computed_by` is rendered so "the rating engine produced this" is checkable rather than claimed · (2) the deposit-differential line is NOT drawn: BR-CUS-042 and BR-CUS-062 are both CONFIRMED and disagree (OQ-179), so the slot renders the server's not-computed note and the net impact names the exclusion · (3) "Next cycle start" renders DISABLED — the cycle window is a metering read nobody publishes, so nobody can name the day; "Immediately" is likewise not offered as an OPTION because the server resolves it to the tenant's today and the wizard would then show a date the clerk never saw. Both resolve to the same one control the server actually needs: an explicit date · (4) the eligibility checkbox is EVIDENCE, never a gate (BR-RAT-043) · (5) there is no account-side plan record and none is drawn (BR-CUS-029 SUPERSEDED — the account derives its plan from the unit)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
