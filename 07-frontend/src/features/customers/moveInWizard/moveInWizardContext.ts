// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-004 (S19 Move-In wizard) · CR-171-BRC10 P2.15
// Rules:    BR-SHL-046 (one declared step list) · BR-SHL-048 (a parked draft
//           keeps every field of every step) · BR-SHL-019 (one commit)
// ───────────────────────────────────────────────────────
// **THE SEAM THE FOUR STEP FILES READ — `CR-171-BRC10` P2.15.**
//
// The four-step move-in (images 30–47) is built by four lanes at once
// (CR §8.1 round R2b: WIZ-UNIT, WIZ-CUST, WIZ-BILL, WIZ-REV), and
// `MoveInWizard.tsx` stays lane WIZ's alone. So each step lives in its own
// file (`StepUnit.tsx`, `StepCustomer.tsx`, `StepBilling.tsx`,
// `StepReview.tsx`) and reads EVERYTHING the wizard holds through this one
// object — the state, its setters and the reads the frame already made.
//
// ⚠ **STATE A STEP ADDS LIVES IN ITS OWN FILE, NOT IN THE WIZARD.** A step's
// state must outlive the step (the rail unmounts it), so it is held by the
// wizard — but through the step's own hook (`useStepUnitOwn` …), called once
// by the wizard. The hook says what its state contributes to the commit
// (`payload`), to a parked draft (`park`) and how it comes back (`hydrate`),
// so a lane adding co-owners or fees edits ITS step file and nothing else.
//
// ⚠ **A STEP'S `payload` IS MERGED OVER THE WIZARD'S OWN BODY LAST**, so a
// lane that sends a key the wizard already builds (e.g. `deposit`) replaces it
// — on purpose, because that is how a step re-draws an existing capability.
// It never removes one: omit a key to leave the wizard's value standing.

import type { ReactNode } from "react";

import type { ApiClient } from "@/api/client";
import type { AccountDetail, UnitRow } from "@/api/endpoints";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { FieldVisitValue } from "@/features/work/FieldVisitOrders";
import type { Translator } from "@/features/tenancy/settingsShared";

import type { DepositForm } from "../depositCapability";
import type { DiscountClaimForm } from "../moveInRequestBlocks";
import type { ReadsDraft } from "../moveReadsCapture";
import type { CustomerForm, PreferencesForm } from "../NewAccountWizard";
import type { StepBillingOwn } from "./StepBilling";
import type { StepCustomerOwn } from "./StepCustomer";
import type { StepReviewOwn } from "./StepReview";
import type { StepUnitOwn } from "./StepUnit";

/** The four step ids, in order — `moveShared.MOVE_IN_STEPS` is the list. */
export type MoveInStepId = "unit" | "customer" | "billing" | "review";

/** BR-CUS-022 + BR-CUS-056 — see `MoveInWizard.moveInDateProblem`. */
export type MoveInDateProblem = "required" | "on_or_before_move_day";

/**
 * A step's own state, held by the wizard through the step's hook.
 *
 * `park` is merged into the draft's `values` under the step's own key (see
 * `MoveInWizard`), and `hydrate` receives that same object back — distrust it
 * exactly as `hydrateForm` does, because a draft is a week-old JSON blob.
 */
export interface StepOwn<T> {
  value: T;
  set: (next: T) => void;
  /** Keys this step adds to the `POST …/move-in` body. `{}` adds none. */
  payload: Record<string, unknown>;
  /** What rides in a parked draft. `{}` parks nothing of this step's own. */
  park: Record<string, unknown>;
  hydrate: (parked: unknown) => void;
}

export interface MoveInWizardContext {
  t: Translator;
  client: ApiClient;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  /** `/move-ins/new` — the clerk chooses the unit; else it came from the URL. */
  standalone: boolean;

  // ── Unit (step 1) ──────────────────────────────────────────────────────
  /** The vacant-unit picker on the standalone road, `null` otherwise. */
  picker: ReactNode;
  unitId: string;
  /** The account whose unit is being taken; `null` for a first occupant. */
  outgoing: AccountDetail | null;
  /** The picked unit's own row (standalone road). */
  pickedUnit: UnitRow | null;
  unitLabel: string;
  unitFree: boolean;
  firstOccupant: boolean;
  /** The unit whose meters open — `""` while not known. */
  outgoingUnitId: string;
  /** `BR-CUS-1101` — the unit's services, and the ones this account takes. */
  serviceOffer: readonly string[];
  ticked: readonly string[];
  setChosenServices: (next: string[] | null) => void;
  offerLoading: boolean;
  offerFailed: boolean;
  openedAt: string;
  setOpenedAt: (next: string) => void;
  earliest: string | null;
  dateProblem: MoveInDateProblem | null;
  readsDraft: ReadsDraft;
  setReadsDraft: (next: ReadsDraft) => void;
  fieldVisit: FieldVisitValue;
  setFieldVisit: (next: FieldVisitValue) => void;

  // ── Customer (step 2) ──────────────────────────────────────────────────
  customer: CustomerForm;
  setCustomer: (next: CustomerForm) => void;
  /** `CR-122-BRC06` — the request this move-in came from, or `""`. */
  serviceRequestId: string;
  serviceRequestNo: string | null;
  identityFromRequest: { label: string; value: string } | null;
  /** Lane CF-1 — the request's SSN and licence as MASKS (their last four),
   *  shown as the Identity boxes' placeholders: the server carries the
   *  numbers themselves (`services._carry_request_identity`). */
  requestIdentifierMasks?: { ssn: string; licence: string };

  // ── Billing (step 3) ───────────────────────────────────────────────────
  preferences: PreferencesForm;
  setPreferences: (next: PreferencesForm) => void;
  deposit: DepositForm;
  setDeposit: (next: DepositForm) => void;
  discount: DiscountClaimForm;
  setDiscount: (next: DiscountClaimForm) => void;
  /** `BR-TEN-042` — the outgoing account's currency, `null` when none. */
  currency: string | null;

  // ── The frame ──────────────────────────────────────────────────────────
  /** Continue has been pressed on this step — only then is a refusal red. */
  tried: Readonly<Record<MoveInStepId, boolean>>;
  markTried: (step: MoveInStepId) => void;
  /** Open a step by its 1-based number (Review's ✎ Edit, image 45). */
  goToStep: (step: number) => void;
  /** CR-181-BRC10 — Complete's reopen refusal (*Pay the old balance first.*),
   *  routed to the Customer step; `null` when there is none. */
  reopenRefusal?: string | null;
  clearReopenRefusal?: () => void;
  /**
   * Each step's OWN state, held by the wizard through the step's hook
   * (`useStep<X>Own`) — read `ctx.own.<step>.value`, write `.set` (`DEF-CUS-9729`:
   * the split built the hooks and handed no step its own state back).
   */
  own: {
    unit: StepOwn<StepUnitOwn>;
    customer: StepOwn<StepCustomerOwn>;
    billing: StepOwn<StepBillingOwn>;
    review: StepOwn<StepReviewOwn>;
  };
}
