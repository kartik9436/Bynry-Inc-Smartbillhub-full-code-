// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave H — the ONE deposit capability, drawn once.
//           PO ruling 2026-09-12, verbatim: *"(a) It is one concept — money
//           held against an account — and building it four times would give
//           four behaviours."*, and *"if there are deposits, then there should
//           be a proper flow to accept those deposit also … you figure it out
//           where … but it should be in the same flow"*.
// Story:    US-CUS-007 (the deposit on a starting-service flow) · US-PAY-002
//           (payment purpose `deposit`)
//           Screens: S18 step 4 (New account · Deposit) · S19 step 5
//           (Move-in · Deposit) — blueprint pages 63-64 and 70-71
// Drawing:  `05-prototype/02 Accounts Menu Blueprint.pdf`, pinned at
//           `033981d4f`, sha256 `c8d596bb505f5020ce4b9474…`, read as IMAGES at
//           scale 2 (`DEF-GOV-5006` — every digit extracts as `&` from the
//           text layer, so no figure here came from it). Page 71's caption is
//           the instruction this file follows: *"Deposit · …?step=5 · copied
//           from the new-account wizard, with the one question a move-in
//           adds"*.
// Rules:    B14 rule 21 (Tailwind utilities, no stylesheet class — this file is
//           ON `styles/route-b-migrated.txt`, which is why every utility token
//           in the deposit step lives HERE and the two wizards add none) ·
//           rule 33 (on-screen text is capped by what it is FOR, and RATIONALE
//           is zero words on screen) · rule 37 (a figure in a wireframe is an
//           ILLUSTRATION) · rule 38 (where a drawing and our UI rules disagree
//           about how a form is BUILT, the UI rules win) · rule 39 (label →
//           input → helper; 20px between fields — inherited from the kit's own
//           `[data-panel] > .field + .field`, never re-stated here) ·
//           BR-CUS-025 (a deposit is a LIABILITY) · BR-CUS-037 (this screen is
//           an ENTRY POINT; payments records the money) · BR-SHL-025 (a control
//           that cannot act carries its reason)
// Amended:  2026-09-23 — the amount is the PLAN's figure for the category, read
//           only (DEF-CUS-6369); *Why this amount* deleted; *No* only where the
//           plan asks none (OQ-CUS-12620 (a), DEF-CUS-6371); a waive carries a
//           reason and is kept on the account (DEF-CUS-6370)
//           2026-10-21 — the drawn *Clearing date* and its CLEARING advisory
//           (*"The account reads $0.00 until cleared."*) are DELETED
//           (DEF-CUS-10324, CR-186-BRC10): every payment, a deposit included,
//           is `posted` at entry and the register moves then; only bank
//           reconciliation clears it, and no screen sets a clearing date. A
//           ruling beats a drawing, so the drawing's twelve controls are eleven
// Tests:   07-frontend/src/features/customers/depositCapability.test.tsx
// Impacts:  MoveInWizard.tsx (step 5) · NewAccountWizard.tsx (step 4's body) ·
//           06-backend/apps/customers/deposit.py (the `deposit` block this
//           builds is that module's whole vocabulary)
// ───────────────────────────────────────────────────────
/**
 * **ONE deposit step.** Two wizards mount it; there is no second copy.
 *
 * ════════════════════════════════════════════════════════════════════════
 * WHY IT IS A SHARED FILE AND NOT A STEP IN EACH WIZARD
 * ════════════════════════════════════════════════════════════════════════
 * The PO ruled the shape before the behaviour, and the reason is the
 * behaviour: *"building it four times would give four behaviours."* The
 * blueprint says the same thing from the drawing's side — page 71's caption
 * calls the move-in's deposit step *"copied from the new-account wizard, with
 * the one question a move-in adds"*. So the step is ONE component, the extra
 * question is ONE prop (`carryForward`), and the payload is built by ONE
 * function that the backend's `apps/customers/deposit.py` validates as its
 * whole vocabulary.
 *
 * ════════════════════════════════════════════════════════════════════════
 * WHAT WAS THERE BEFORE, AND WHY THE OLD REFUSALS ARE DELETED NOT REWORDED
 * ════════════════════════════════════════════════════════════════════════
 * Both wizards drew a deposit and both refused it, each naming a table that
 * did not exist. **The engine has existed since 2026-08-27**: a
 * `purpose="deposit"` payment posts `DR undeposited / CR deposit liability
 * 2300`, moves the `BR-CUS-670` register and queues the customer's receipt.
 * Nothing ever sent it. That is hard-won law 2's mirror at feature scale — a
 * finished engine behind no door — and hard-won law 1 says a refusal whose
 * reason has expired is deleted rather than reworded.
 *
 * ════════════════════════════════════════════════════════════════════════
 * THE AMOUNT IS THE PLAN'S, FOR THE CATEGORY — AND IT CANNOT BE TYPED
 * ════════════════════════════════════════════════════════════════════════
 * ⛔ **RULED 2026-09-23, AND IT SUPERSEDES THE DRAWING (`DEF-CUS-6369`).** PO,
 * verbatim: *"you need to take deposit amount as per plan ; plan will have
 * deposite chanrge code as per customer categoris ;so that value should be
 * atken as by default no override is required"*. The drawing's *Amount* box
 * read *"Typed by hand today."* and this file built exactly that; it is now a
 * READ-ONLY money fact filled from `GET /accounts/deposit-standard` — the
 * unit's plan × the category chosen on the Customer step, through the SAME
 * walk the server takes on the commit (`deposit.standard_for_unit`). Change the
 * category and the figure follows, because the read is keyed by it.
 *
 * ⚠ **THE PLAN DECIDES WHICH ANSWERS ARE OFFERED — `OQ-CUS-12620`, ruled (a).**
 * *"When the plan asks a deposit: take it or waive it (supervisor). "No" only
 * when the plan asks none."* So the select offers *Take* or *Waive* when the
 * plan asks a figure, and there is NO select when it asks none — the step says
 * *No deposit on this plan.* and nothing can be typed. `depositProblem` holds
 * the step on the same rule, and the server refuses it by name either way.
 *
 * ⚠ **THE WORD `(supervisor)` IN THE QUOTATION ABOVE IS SUPERSEDED — a Billing
 * Clerk or a System Admin waives (`OQ-CUS-12623`, 2026-09-24, `BR-CUS-1050`
 * amended).** PO, verbatim: *"p3 - clark and sysem admin can do it"*. The
 * quotation stays as the PO said it; this stamp is here because the next
 * reader of that line would otherwise build the old set. The screen has never
 * gated the option by role and does not start now — the server is the
 * enforcement (`BR-SHL-025`) and refuses a role outside the set BY NAME.
 *
 * ⚠ **"WHY THIS AMOUNT" AND THE CREDIT-TIER NOTE ARE DELETED, NOT REWORDED.**
 * Both existed to justify a typed judgement — four reasons for a figure, and a
 * note that *nothing works a credit grade out* to size it. A fixed figure has
 * no judgement behind it, so both went with the box (B14 rule 33: rationale
 * is removed, never shortened). The server stays tolerant of a `reason` a
 * draft parked before 2026-09-23 may still carry.
 *
 * ⚠ **A WAIVE NOW CARRIES A REASON, AND THE ACCOUNT KEEPS IT (`DEF-CUS-6370`).**
 *
 * ════════════════════════════════════════════════════════════════════════
 * WHERE THIS LEAVES THE DRAWING, STATED RATHER THAN QUIETLY DONE
 * ════════════════════════════════════════════════════════════════════════
 * ⚠ **THE HEADINGS AND FOUR HELPERS ARE SHORTER THAN DRAWN, under B14 rule
 * 33.** The drawing's section heads are questions — *"Does this account need
 * a deposit?"* — and rule 33 caps a heading at THREE WORDS with no sentence;
 * its *Due* helper is one twelve-word sentence where the rule allows six per
 * sentence and says *two sentences of six beat one of twelve*. Rule 38's last
 * clause leaves WHAT a form contains to the drawing, and nothing here drops a
 * field, an option or a fact — every one of the drawing's twelve controls is
 * present, in its order. What changes is length, which is exactly what rule 33
 * governs and what the PO said four times in twenty minutes. **Recorded in
 * `04-docs/05-modules/03-customers/08-screen-layouts.md`, not done quietly.**
 *
 * ⚠ **AND THE RATIONALE SENTENCES ARE NOT ON SCREEN AT ALL** — rule 33's fifth
 * cap is ZERO WORDS. The drawing's dashed boxes each carry a fact and then a
 * paragraph explaining why the product works that way; the fact is rendered
 * and the explanation lives here and in the register.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getDepositStandard, type DepositSizeChoice, type DepositStandard } from "@/api/endpoints";
import {
  CheckboxField,
  DatePickerField,
  SelectField,
  TextField,
  type Translator,
} from "@/components/FormModal";
import { MoneyCell, formatMoneyInput } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { useTenantCurrency } from "@/components/TenantRegional";
import type { RegionalDateFormat } from "@/components/DateCell";
import { sortBySize } from "@/features/rating/sizeOrder";

import { Advisory } from "./moveShared";
import { FieldGrid } from "./serviceRequestShared";

// ══════════════════════════════════════════════════════════════════════════
// PART 1 · THE VOCABULARY — declared ONCE, on both sides of the wire
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **DERIVED, NEVER HAND-TYPED TWICE.** Hard-won law 12: the service list is
// typed by hand in two places, so an eleventh service never appears on screen
// and fails SILENTLY. The decision list is `apps/customers/deposit.py`'s
// `DECISIONS` verbatim, and the option lists below are built by
// `.map` off them — so a fourth decision cannot be served and not drawn.
// (`deposit.REASONS` is no longer drawn at all — see the header.)

/** `deposit.DECISIONS` — the three answers, in the blueprint's own order. */
export const DEPOSIT_DECISIONS = ["required", "not_required", "waived"] as const;
export type DepositDecision = (typeof DEPOSIT_DECISIONS)[number];

/**
 * What the plan asks of this unit × category, as far as this step knows.
 *
 *   `""`     not read yet — the step holds (`depositProblem` names `amount`)
 *   `"asks"` the plan asks `amount`: *Take* or *Waive*
 *   `"none"` the plan asks nothing: *No deposit on this plan.*, the only answer
 */
export type DepositPlan = "" | "asks" | "none";

/**
 * `BR-PAY-026`'s tender vocabulary as the blueprint draws it — *"ACH · Card ·
 * Cash · Check · Lockbox · Money order · Wire"*.
 *
 * ⚠ **A DEFAULT LIST, NOT THE TENANT'S.** Payment methods are a tenant lookup
 * (`BR-PAY-026`) and the authority is the server, which refuses a code it does
 * not hold. Drawn from this list because no endpoint serves the tenant's
 * methods to a wizard step yet, and the seven the drawing names are the seven
 * every tenant is seeded with. **Filed as `DEF-CUS-5115` rather than inferred**,
 * because a tenant who retires *Lockbox* would still be offered it — hard-won
 * law 12's shape, one list over. The honest mitigation is that the SERVER
 * decides: `record_payment` refuses an unknown code by name, so the worst case
 * is a refusal a clerk can read rather than a payment booked against a method
 * the tenant does not have.
 */
export const DEPOSIT_METHODS = [
  "ach",
  "card",
  "cash",
  "check",
  "lockbox",
  "money_order",
  "wire",
] as const;

export interface DepositForm {
  decision: DepositDecision;
  /**
   * The PLAN's figure, exactly as the server stated it (a 4-decimal STRING,
   * never a number — money is never a float client-side). Filled by the step
   * from the read; never typed. Sent back on the commit so a plan edited in
   * between is refused by name rather than silently re-priced.
   */
  amount: string;
  /** What the plan asks — see `DepositPlan`. */
  plan: DepositPlan;
  /** `<unit>|<category>` the figure above was read for. A different pair means
   *  the figure is stale and the step holds until the new one arrives. */
  plan_for: string;
  /**
   * `DEF-CUS-9521` — the plan prices the deposit by meter size and no meter
   * is fitted, so the clerk picks a size (PO 2026-10-04: *"(c) Let the clerk
   * pick the size on the Deposit step."*). `size_pick` says the picker is
   * shown; `size_class` is the pick (`""` until chosen) and `size_label` its
   * NAME for the review. All three stay empty where a meter size is recorded.
   */
  size_pick: boolean;
  size_class: string;
  size_label: string;
  /** Required on a waive; kept on the account (`DEF-CUS-6370`). */
  waive_reason: string;
  due_on: string;
  take_now: boolean;
  method_code: string;
  confirmation: string;
  amount_taken: string;
  posted_at: string;
}

/**
 * Nothing is answered until the plan has been read — the decision starts at
 * `not_required` and `plan` at `""`, so the step HOLDS rather than letting a
 * clerk through on an answer nobody chose. The read then sets both.
 */
export function emptyDepositForm(): DepositForm {
  return {
    decision: "not_required",
    amount: "",
    plan: "",
    plan_for: "",
    size_pick: false,
    size_class: "",
    size_label: "",
    waive_reason: "",
    due_on: "",
    take_now: false,
    method_code: "",
    confirmation: "",
    amount_taken: "",
    posted_at: "",
  };
}

/** The collection half — cleared whenever it stops applying, never hidden. */
const NOTHING_COLLECTED: Pick<
  DepositForm,
  "take_now" | "method_code" | "confirmation" | "amount_taken" | "posted_at"
> = {
  take_now: false,
  method_code: "",
  confirmation: "",
  amount_taken: "",
  posted_at: "",
};

/** The key a figure is read for — the unit and the category, nothing else. */
/** `OQ-RAT-12786` — the server's refusal when the plan's deposit is priced by
 *  meter size and this unit's size is not priced (`customers/deposit.py`). */
export const SIZE_NOT_PRICED_KEY = "customers.deposit.sizeNotPriced";

export function planKey(unitId: string, category: string): string {
  return `${unitId}|${category}`;
}

/** `DEF-CUS-9524` — *Amount taken* is an AMOUNT the clerk reads and may
 *  retype, so its default is the figure as an amount DISPLAYS: 2 places
 *  (CLAUDE.md hard rule 2). The server states the plan's figure to four
 *  (`600.0000`); the money is the same either way. */
function takenDefault(figure: string): string {
  return formatMoneyInput(figure);
}

/** An *Amount taken* still following the figure — empty, or the figure in
 *  either spelling (the stored 4 places or the shown 2) — moves with it; one
 *  the clerk typed is theirs and is left alone. */
function takenFollowsFigure(form: DepositForm): boolean {
  if (!form.take_now) return false;
  const typed = form.amount_taken.trim();
  return typed === "" || typed === form.amount || typed === formatMoneyInput(form.amount);
}

/**
 * Fold what the plan asks into the form. Pure, so it is provable without a
 * browser; returns the SAME object when nothing changes, so the step's effect
 * cannot loop.
 *
 * * **asks** — the figure becomes the plan's; a `not_required` answer becomes
 *   *Take* (the only other answer is a waive — a Billing Clerk's or a System
 *   Admin's since 2026-09-24, `OQ-CUS-12623` — which is never pre-selected); an *Amount taken* that was still the old figure follows it.
 * * **none** — *No deposit* is the only answer, so the decision and every
 *   field behind it are cleared.
 */
export function applyPlanStandard(
  form: DepositForm,
  standard: DepositStandard,
  key: string,
): DepositForm {
  if (standard.asks && standard.pick_size && standard.sizes) {
    // `DEF-CUS-9521` — no meter fitted: the figure is the PICKED size's, and
    // there is none until the clerk picks (the step holds on `size_class`).
    const chosen = standard.sizes.find((size) => size.size_class === form.size_class);
    const figure = chosen?.amount ?? "";
    const takenFollows = takenFollowsFigure(form);
    const next: DepositForm = {
      ...form,
      decision: form.decision === "not_required" ? "required" : form.decision,
      amount: figure,
      plan: "asks",
      plan_for: key,
      size_pick: true,
      size_class: chosen ? chosen.size_class : "",
      size_label: chosen ? chosen.label : "",
      amount_taken: takenFollows ? takenDefault(figure) : form.amount_taken,
    };
    return sameForm(form, next) ? form : next;
  }
  if (!standard.asks || standard.amount === null) {
    const next: DepositForm = {
      ...form,
      ...NOTHING_COLLECTED,
      decision: "not_required",
      amount: "",
      plan: "none",
      plan_for: key,
      size_pick: false,
      size_class: "",
      size_label: "",
      waive_reason: "",
      due_on: "",
    };
    return sameForm(form, next) ? form : next;
  }
  const figure = standard.amount;
  const takenFollows = takenFollowsFigure(form);
  const next: DepositForm = {
    ...form,
    decision: form.decision === "not_required" ? "required" : form.decision,
    amount: figure,
    plan: "asks",
    plan_for: key,
    size_pick: false,
    size_class: "",
    size_label: "",
    amount_taken: takenFollows ? takenDefault(figure) : form.amount_taken,
  };
  return sameForm(form, next) ? form : next;
}

/** `DEF-CUS-9521` — the sizes in the order a clerk reads them: by the size
 *  the NAME states, smallest first (`sizeOrder`), never by code. */
export function sizesInOrder(sizes: readonly DepositSizeChoice[]): DepositSizeChoice[] {
  return sortBySize(sizes, (size) => size.label);
}

function sameForm(a: DepositForm, b: DepositForm): boolean {
  return (Object.keys(a) as (keyof DepositForm)[]).every((k) => a[k] === b[k]);
}

// ══════════════════════════════════════════════════════════════════════════
// PART 2 · THE PAYLOAD AND THE GATE — provable without a browser
// ══════════════════════════════════════════════════════════════════════════

/**
 * The `deposit` block for `POST /accounts` and `POST /accounts/{id}/move-in`,
 * or `undefined` when this account owes none.
 *
 * ⚠ **`undefined` RATHER THAN A BLOCK SAYING `not_required`.** The server
 * answers nothing at all for an account with no deposit, and a block that said
 * *"not required, 0.00"* would put a zero on the confirmation where there
 * should be no deposit row — the distinction `rating.deposit_rule_for` warns
 * about one layer down and `apps/customers/deposit.py` repeats.
 *
 * ⚠ **ONLY THE KEYS THAT MEAN SOMETHING FOR THIS DECISION ARE SENT.** A waived
 * deposit carries no method and no dates; sending the boxes a clerk typed into
 * and then hid would record a payment nobody made.
 */
export function depositPayload(form: DepositForm): Record<string, unknown> | undefined {
  if (form.decision === "not_required") return undefined;
  // The figure the step SHOWED, so the server can refuse it if the plan moved.
  const block: Record<string, unknown> = { decision: form.decision };
  if (form.amount.trim() !== "") block.amount = form.amount.trim();
  // `DEF-CUS-9521` — the picked size, only where no meter is fitted.
  if (form.size_pick && form.size_class !== "") block.size_class = form.size_class;
  if (form.decision === "waived") {
    if (form.waive_reason.trim() !== "") block.waive_reason = form.waive_reason.trim();
    return block;
  }
  if (form.due_on !== "") block.due_on = form.due_on;
  if (!form.take_now) return block;
  block.take_now = true;
  if (form.method_code !== "") block.method_code = form.method_code;
  if (form.confirmation.trim() !== "") block.confirmation = form.confirmation.trim();
  if (form.amount_taken.trim() !== "") block.amount_taken = form.amount_taken.trim();
  if (form.posted_at !== "") block.posted_at = form.posted_at;
  // No `cleared_at`, ever (DEF-CUS-10324): the server refuses it by name.
  return block;
}

/**
 * The field the step is NOT ready on, or `null`.
 *
 * ⚠ **IT RETURNS THE FIELD AND NOT A BOOLEAN, because `DEF-CUS-5082` is the
 * defect of a form that refuses on one field and marks another.** The caller
 * marks THAT field.
 *
 * The rules are the server's, restated so the clerk meets them before the
 * commit rather than after it. The server's refusal is what actually holds —
 * including `OQ-CUS-12620` (a): on a plan that asks a figure, *No* is not an
 * answer; on one that asks none, it is the only one.
 */
export function depositProblem(form: DepositForm): keyof DepositForm | null {
  if (form.plan === "") return "amount";
  if (form.plan === "none") return form.decision === "not_required" ? null : "decision";
  if (form.decision === "not_required") return "decision";
  if (form.size_pick && form.size_class === "") return "size_class";
  if (form.amount.trim() === "" || Number(form.amount) <= 0) return "amount";
  if (form.decision === "waived") return form.waive_reason.trim() === "" ? "waive_reason" : null;
  if (!form.take_now) return null;
  if (form.method_code === "") return "method_code";
  if (form.posted_at === "") return "posted_at";
  return null;
}

/** What the customer hands over today — the drawing's own footer total. */
export function takenToday(form: DepositForm): string {
  if (form.decision !== "required" || !form.take_now) return "0.00";
  const raw = form.amount_taken.trim() === "" ? form.amount : form.amount_taken;
  return formatMoneyInput(raw) || "0.00";
}

// ══════════════════════════════════════════════════════════════════════════
// PART 3 · THE STEP
// ══════════════════════════════════════════════════════════════════════════

export interface DepositStepProps {
  values: DepositForm;
  onChange: (next: DepositForm) => void;
  t: Translator;
  dateFormat: RegionalDateFormat;
  /**
   * The tenant's `CHAR(3)`, or `null` when this screen has not been served one.
   *
   * ⚠ **`null` RENDERS A SENTENCE, NEVER `USD`** — the precedent is
   * `UnitPricingPanel.money` in this same wizard family: *"inventing `USD` for
   * a row that did not state one would put a currency on a screen the tenant
   * never chose"* (hard rule 2, `DEF-151` / `DEF-1121`). The move-in reads it
   * off the outgoing account, which carries it under `BR-TEN-042`'s currency
   * lock; the new-account wizard (and a move-in into a VACANT unit) has no
   * account to read yet and passes `null`.
   *
   * ⚠ **`null` NOW FALLS BACK TO THE TENANT'S CODE (`DEF-CUS-5114`,
   * 2026-10-04)** — `useTenantCurrency()`, which the shell publishes from
   * `GET /shell/display`. Only when NOTHING is published does the footer state
   * the absence; it still never says `USD` on its own.
   */
  currency: string | null;
  /**
   * The ONE question a move-in adds (blueprint page 71's caption). A returning
   * tenant may have held an account with this utility before, and their own
   * deposit could follow them.
   *
   * ⚠ **A STATED ABSENCE AND NOT A CONTROL.** Carry-forward rides the
   * customer↔accounts linkage, and the server warns
   * `deposit_carry_forward_unavailable` on every move-in because no prior
   * position can be read. A control that saved nowhere would be a decision the
   * customer believes was recorded (`BR-CUS-024`, `OQ-510`).
   */
  carryForward?: boolean;
  /**
   * The UNIT the account will stand on, and the CATEGORY code picked on the
   * Customer step — the two facts the plan's figure is keyed by
   * (`plan_deposit_rules`, rate plan × category). `""` for either means *not
   * chosen yet*: nothing is read and the step holds.
   */
  unitId: string;
  category: string;
  /** Test seam — screens never build their own transport. */
  client?: ApiClient;
}

export function DepositStep(props: DepositStepProps) {
  const { t, values, onChange } = props;
  const set = (patch: Partial<DepositForm>) => onChange({ ...values, ...patch });
  const client = props.client ?? api;
  const key = planKey(props.unitId, props.category);
  const ready = props.unitId !== "" && props.category !== "";

  // ── the plan's figure, read by the SAME walk the commit takes ────────────
  const standard = useQuery({
    queryKey: ["deposit-standard", props.unitId, props.category],
    queryFn: () => getDepositStandard(props.unitId, props.category, client),
    enabled: ready,
    retry: false,
    staleTime: 30 * 1000,
  });
  // Folded INTO the form, so the wizard's `validate` and its review step read
  // one object. A figure read for another unit or category is STALE the moment
  // the key moves, and the step holds until the new one arrives — otherwise a
  // clerk who changed Residential to Commercial could commit $150.00 where the
  // plan asks $400.00 (the server would refuse it by name; this stops it first).
  useEffect(() => {
    if (standard.data === undefined) {
      if (values.plan !== "" && values.plan_for !== key) {
        onChange({ ...values, plan: "", plan_for: key });
      }
      return;
    }
    const next = applyPlanStandard(values, standard.data, key);
    if (next !== values) onChange(next);
  }, [key, standard.data, values, onChange]);

  // `OQ-CUS-12620` (a): on a plan that asks a figure, the answers are TAKE or
  // WAIVE — derived from `DEPOSIT_DECISIONS`, never retyped, with *No* left out.
  const decisionOptions = useMemo(
    () =>
      DEPOSIT_DECISIONS.filter((value) => value !== "not_required").map((value) => ({
        value,
        label: t(`customers.deposit.decision.${value}`),
      })),
    [t],
  );
  const methodOptions = useMemo(
    () =>
      DEPOSIT_METHODS.map((value) => ({
        value,
        label: t(`customers.deposit.method.${value}`),
      })),
    [t],
  );

  // `DEF-CUS-9521` — the plan's priced sizes, by NAME, smallest first.
  const sizes = useMemo(() => sizesInOrder(standard.data?.sizes ?? []), [standard.data]);
  const sizeOptions = useMemo(
    () => sizes.map((size) => ({ value: size.size_class, label: size.label })),
    [sizes],
  );

  const fresh = values.plan !== "" && values.plan_for === key;
  const owed = fresh && values.plan === "asks" && values.decision === "required";
  return (
    <Panel>
      <h3>{t("customers.deposit.title")}</h3>

      {!fresh ? (
        // ⚠ A FACT, NOT A CONTROL: nothing can be answered until the plan is
        // read, and `depositProblem` holds the step on the same condition.
        <p className="m-0 text-sm text-neutral-700" data-deposit-plan="pending">
          {!ready
            ? t("customers.deposit.planNeedsChoices")
            : standard.isError
              ? // `OQ-RAT-12786` — a deposit priced by meter size that this
                // unit's size does not price is a NAMED refusal from the
                // server (`customers.deposit.sizeNotPriced`), never "asks none";
                // it says so rather than the generic unreadable sentence.
                t(
                  isApiError(standard.error) && standard.error.messageKey === SIZE_NOT_PRICED_KEY
                    ? SIZE_NOT_PRICED_KEY
                    : "customers.deposit.planUnreadable",
                )
              : t("customers.deposit.planReading")}
        </p>
      ) : values.plan === "none" ? (
        // `OQ-CUS-12620` (a): the plan asks nothing, so *No* is the only answer
        // and there is nothing to type or pick.
        <p className="m-0 text-sm" data-deposit-plan="none">
          {t("customers.deposit.noPlanDeposit")}
        </p>
      ) : (
        <FieldGrid>
          <SelectField
            id="deposit_decision"
            label={t("customers.deposit.field.decision")}
            value={values.decision}
            required
            options={decisionOptions}
            onChange={(value) =>
              // Switching AWAY from `required` clears the collection half rather
              // than hiding it: a clerk who ticks "take it today", changes their
              // mind and commits must not send a payment instruction behind a
              // control they can no longer see.
              set(
                value === "required"
                  ? { decision: "required", waive_reason: "" }
                  : { decision: value as DepositDecision, due_on: "", ...NOTHING_COLLECTED },
              )
            }
          />
          {values.size_pick ? (
            <SelectField
              id="deposit_size_class"
              label={t("customers.deposit.field.size")}
              value={values.size_class}
              required
              options={sizeOptions}
              placeholder={t("customers.deposit.size.placeholder")}
              help={t("customers.deposit.help.sizePick")}
              onChange={(value) => {
                const chosen = sizes.find((size) => size.size_class === value);
                const figure = chosen?.amount ?? "";
                const takenFollows = takenFollowsFigure(values);
                set({
                  size_class: chosen ? chosen.size_class : "",
                  size_label: chosen ? chosen.label : "",
                  amount: figure,
                  amount_taken: takenFollows ? takenDefault(figure) : values.amount_taken,
                });
              }}
            />
          ) : null}
          {/* THE PLAN'S FIGURE, read-only — a value the clerk may READ and
              copy but not set (`TextField.readOnly`, BR-SHL-025's shape). */}
          <TextField
            id="deposit_amount"
            label={t("customers.deposit.field.amount")}
            value={formatMoneyInput(values.amount)}
            required
            numeric
            readOnly
            onChange={() => undefined}
            help={t("customers.deposit.help.planFigure")}
          />
        </FieldGrid>
      )}

      {fresh && values.plan === "asks" && values.decision === "waived" ? (
        <FieldGrid>
          <TextField
            id="deposit_waive_reason"
            label={t("customers.deposit.field.waiveReason")}
            value={values.waive_reason}
            required
            onChange={(value) => set({ waive_reason: value })}
          />
        </FieldGrid>
      ) : null}

      {owed ? (
        <FieldGrid>
          <DatePickerField
            id="deposit_due_on"
            label={t("customers.deposit.field.dueOn")}
            value={values.due_on}
            dateFormat={props.dateFormat}
            onChange={(value) => set({ due_on: value })}
            help={t("customers.deposit.help.dueOn")}
          />
        </FieldGrid>
      ) : null}

      {props.carryForward === true ? (
        <>
          <h3>{t("customers.deposit.carry.title")}</h3>
          <Advisory tag={t("customers.deposit.tag.carry")} tracks="BR-CUS-024">
            {t("customers.deposit.carryAbsent")}
          </Advisory>
        </>
      ) : null}

      {owed ? (
        <>
          <h3>{t("customers.deposit.paid.title")}</h3>
          <CheckboxField
            id="deposit_take_now"
            label={t("customers.deposit.field.takeNow")}
            checked={values.take_now}
            onChange={(checked) =>
              set(
                checked
                  ? {
                      take_now: true,
                      // *"Defaults to the deposit."* — the drawing's own helper.
                      // Proposed here AND resolved on the server, so a clerk who
                      // never touches the box and one who retypes the figure send
                      // the same instruction.
                      amount_taken:
                        values.amount_taken.trim() === ""
                          ? takenDefault(values.amount)
                          : values.amount_taken,
                    }
                  : { ...NOTHING_COLLECTED },
              )
            }
          />
          {values.take_now ? (
            <>
              <FieldGrid>
                <SelectField
                  id="deposit_method_code"
                  label={t("customers.deposit.field.method")}
                  value={values.method_code}
                  required
                  options={methodOptions}
                  placeholder={t("customers.deposit.method.placeholder")}
                  onChange={(value) => set({ method_code: value })}
                />
                <TextField
                  id="deposit_amount_taken"
                  label={t("customers.deposit.field.amountTaken")}
                  value={values.amount_taken}
                  numeric
                  onChange={(value) => set({ amount_taken: value })}
                  help={t("customers.deposit.help.amountTaken")}
                />
              </FieldGrid>
              <FieldGrid>
                <TextField
                  id="deposit_confirmation"
                  label={t("customers.deposit.field.confirmation")}
                  value={values.confirmation}
                  onChange={(value) => set({ confirmation: value })}
                  help={t("customers.deposit.help.confirmation")}
                />
                <DatePickerField
                  id="deposit_posted_at"
                  label={t("customers.deposit.field.postedAt")}
                  value={values.posted_at}
                  required
                  dateFormat={props.dateFormat}
                  onChange={(value) => set({ posted_at: value })}
                  help={t("customers.deposit.help.postedAt")}
                />
              </FieldGrid>
              <DepositTodayTotals form={values} currency={props.currency} t={t} />
            </>
          ) : null}
        </>
      ) : null}
    </Panel>
  );
}

/**
 * *"What the customer pays today"* — the drawing's own footer, page 71.
 *
 * The two rows under the deposit are ABSENCES with owners and not zeroes: the
 * first bill follows the cycle billing owns, and a connection fee is a charge
 * code the category may not carry. A `$0.00` in either would state that the
 * product had worked a figure out.
 */
export function DepositTodayTotals(props: {
  form: DepositForm;
  currency: string | null;
  t: Translator;
}) {
  // `DEF-CUS-5114` — no account in scope (New account, a vacant move-in)
  // reads the TENANT's code: `BR-TEN-042`, one tenant, one currency.
  const tenantCurrency = useTenantCurrency();
  const { t } = props;
  const currency = props.currency || tenantCurrency;
  const total = takenToday(props.form);
  const money =
    currency === null || currency === "" ? (
      <span className="text-neutral-700">{t("customers.deposit.totals.currencyAbsent")}</span>
    ) : (
      <MoneyCell amount={total} currency={currency} />
    );
  return (
    <dl
      className="mt-4 border-t border-divider pt-2 text-sm"
      data-deposit-totals=""
      aria-label={t("customers.deposit.totals.title")}
    >
      <TotalRow label={t("customers.deposit.totals.deposit")}>{money}</TotalRow>
      <TotalRow label={t("customers.deposit.totals.firstBill")}>
        <span className="text-neutral-700">{t("customers.deposit.totals.firstBillAbsent")}</span>
      </TotalRow>
      <TotalRow label={t("customers.deposit.totals.connectionFee")}>
        <span className="text-neutral-700">
          {t("customers.deposit.totals.connectionFeeAbsent")}
        </span>
      </TotalRow>
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 border-t border-neutral-900 pt-2 font-semibold">
        <dt>{t("customers.deposit.totals.takenToday")}</dt>
        <dd className="m-0 tabular-nums">{money}</dd>
      </div>
    </dl>
  );
}

function TotalRow(props: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-6 border-b border-divider py-2">
      <dt className="text-neutral-700">{props.label}</dt>
      <dd className="m-0 tabular-nums">{props.children}</dd>
    </div>
  );
}

/**
 * The review step's deposit block — blueprint page 72's *Deposit · Step 5*.
 *
 * Rendered by the REVIEW step of whichever wizard mounted the step, off the
 * same form object, so the two can never disagree about what is about to be
 * committed. Nothing here is served by the server; it is the clerk's own
 * entries read back.
 */
export function DepositReviewRows(props: {
  form: DepositForm;
  currency: string | null;
  t: Translator;
  /** `Fact`-shaped renderer the host wizard already uses for its own rows. */
  row: (label: string, value: React.ReactNode) => React.ReactNode;
}) {
  const { t, form, row } = props;
  // `DEF-CUS-5114` — the same fallback as the step's footer, so the review
  // and the step cannot disagree about the currency either.
  const tenantCurrency = useTenantCurrency();
  const currency = props.currency || tenantCurrency;
  if (form.decision === "not_required") {
    // `OQ-CUS-12620` (a): *No* is only ever the answer on a plan that asks
    // none, so the review says THAT rather than a bare "No".
    return <>{row(t("customers.deposit.field.decision"), t("customers.deposit.noPlanDeposit"))}</>;
  }
  const money = (raw: string) => {
    const text = formatMoneyInput(raw);
    if (text === "") return <Dash />;
    if (currency === null || currency === "") {
      return (
        <span className="text-neutral-700">{t("customers.deposit.totals.currencyAbsent")}</span>
      );
    }
    return <MoneyCell amount={text} currency={currency} />;
  };
  return (
    <>
      {row(t("customers.deposit.field.decision"), t(`customers.deposit.decision.${form.decision}`))}
      {form.size_pick ? row(t("customers.deposit.field.size"), form.size_label || <Dash />) : null}
      {row(t("customers.deposit.field.amount"), money(form.amount))}
      {form.decision === "waived"
        ? row(t("customers.deposit.field.waiveReason"), form.waive_reason.trim() || <Dash />)
        : null}
      {form.decision !== "required" || !form.take_now
        ? null
        : [
            row(
              t("customers.deposit.field.method"),
              t(`customers.deposit.method.${form.method_code}`),
            ),
            row(t("customers.deposit.field.amountTaken"), money(form.amount_taken || form.amount)),
            row(t("customers.deposit.field.postedAt"), form.posted_at || <Dash />),
          ]}
    </>
  );
}

function Dash() {
  return <span aria-hidden="true">—</span>;
}
