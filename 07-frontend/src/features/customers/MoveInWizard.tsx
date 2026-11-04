// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-004 (S19 Move-In wizard, five steps) · US-CUS-007 (the
//           deposit fields inside S19 step 4 — every one of which the server
//           refuses)
//           Screens: S19 (entered from the S20 close-out chain, and from the
//           closed account's own detail page)
// Rules:    BR-CUS-010 / BR-CUS-014 (unit and account never diverge; the plan
//           lives once on the unit and the account derives it) · BR-CUS-017 (at
//           most ONE active account per unit) · BR-CUS-019 (the customer search
//           is advisory — and unbuildable) · BR-CUS-020 (only vacant units) ·
//           BR-CUS-021 (initial reads commit through the metering service) ·
//           BR-CUS-022 (the first bill starts at the service start date) ·
//           BR-CUS-023 / BR-CUS-024 (the deposit is a plan LOOKUP; carry-forward
//           rides the customer entity) · BR-CUS-028 (the preference set) ·
//           BR-CUS-029 (the account plan snapshot has NO table) · BR-CUS-045
//           (contact PII — the last four of a government id only) · BR-CUS-054
//           (the first-class customer entity has no table) · BR-CUS-055 (the
//           seeded statuses and their behaviour classes) · BR-CUS-056 (the
//           incoming account starts the day AFTER the outgoing one's move day) ·
//           BR-CUS-059 (autopay is CAPTURE-ONLY in v1) · BR-MET-040 (a plan is
//           REQUIRED at activation) · BR-MET-044 (the unit KEEPS its last plan
//           as the next tenant's prefill) · BR-SHL-018 (wizard rail semantics) ·
//           BR-SHL-019 (ONE transactional commit) · BR-SHL-025 (a forbidden
//           control is disabled WITH its reason) · BR-SHL-033 (dates use the
//           date control) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S19 — the guided Move-in page. `POST /accounts/{id}/move-in` landed on
// 2026-08-11 with no screen calling it; this is that screen.
//
// `{id}` IS THE OUTGOING ACCOUNT. 11b §S19 defines exactly one move-in row and
// it is account-scoped: the next occupant takes the unit the named account is
// leaving. `unit_id` is a REFUSED field (BR-CUS-017) and a unit in the BODY
// would be a second, disagreeing source of truth for which room the tenant is
// entering — that is unchanged, and no payload here carries one.
//
// ⚠ **AMENDED 2026-08-26 (PO ruling, lane MOVEENTRY) — "SO THIS PAGE HAS NO
// UNIT PICKER AT ALL" IS NO LONGER TRUE, AND THE RULE UNDER IT IS.** The PO
// overruled the disabled Accounts-header entry in their own words: *"a move-in
// creates the next occupant of a particular account's unit and no account is
// chosen in that header … -Enable Move in /move out"*. So `/move-ins/new`
// mounts this same wizard with nothing in the path and step 1 asks for the UNIT
// — because that is what a clerk has — and DERIVES the outgoing account from it
// through `moveShared.lastClosedAccountForUnit`, which mirrors the server's own
// `selectors.last_closed_account_for_unit`. The unit is a QUESTION on the
// screen; it is still never a field in the body, and `{id}` is still the
// outgoing account.
//
// ⚠ **AND A VACANT UNIT WITH NO FINISHED TENANCY IS A FIRST OCCUPANT — IT MOVES
// IN HERE (`DEF-CUS-6353`, decided 2026-09-23).** Until that day step 1 refused
// it and pointed at S18, because the only move-in door was account-scoped. The
// PO's move-in approval ruling sends an approved request for such a unit here,
// so `POST /units/{unit_id}/move-in` now takes it under the SAME guards
// (`services._move_in` is one body behind both doors). The clerk picks the start
// date — there is no move-out to follow — and keys the first reading.
//
// `services.MOVE_IN_FIELDS` is the create set minus `unit_id`. Everything else
// the five prototype steps draw is refused BY NAME, and none of it is collected:
//
//   · **The returning-customer search** (step 2's results table and its "Use"
//     buttons). `customer` / `customer_id` are refused (BR-CUS-054).
//     ⚠ **CORRECTED 2026-08-25 (CR-030 W5 R1 lane) — THE REASON WRITTEN HERE
//     WAS FALSE, and hard-won law 1 is exactly this shape pointed at a note:
//     a comment claiming a fact is not the fact.** It read *"the first-class
//     `customers` entity and its `customer_accounts` link have no tables"*.
//     **Both tables exist and have since 2026-08-11** — `apps/customers/
//     models.Customer` (`db_table = "customers"`) and `models.CustomerAccount`
//     (`db_table = "customer_accounts"`, N:M, unique on the PAIR), built by the
//     US-CUS-019 import lane on B2 r9 #1's column list. `AccountDetail.customer`
//     is served from them today.
//     **The refusal still stands and this lane does not touch it** — the true
//     reason is the one `services.REFUSED_FIELDS` already carries, corrected on
//     the same day the tables landed: *"linking a customer at create is
//     US-CUS-003 step 1, not built"*. So the advisory duplicate check and the
//     "Use existing customer" button of S18 step 1 (US-CUS-003 TC-5) were never
//     built, and `POST /accounts` has no linking path to call. A move-in
//     therefore still writes a fresh contact row — for a reason about a missing
//     STEP, not a missing TABLE.
//     ⚠ **THREE OTHER PLACES STILL CARRY THE OLD, FALSE REASON AND ARE NOT
//     THIS LANE'S FILES — REPORTED, not edited:** `services.MOVE_IN_UNAVAILABLE`
//     (`customer_not_linked`: *"the first-class `customers` entity has no
//     table"*; `deposit_carry_forward_unavailable`: *"with no customer entity
//     there is no 'same customer' to carry from"*) and the catalogue strings
//     `customers.moveIn.customer.noSearch` (*"the shared customer record it
//     would look through does not exist"*) and `customers.moveIn.carryWhy`
//     (*"That link has no table"*). Those four sentences reach a user's screen.
//   · **"Bill from"** (step 3's Move-in date / Next cycle start select).
//     `bill_from` is refused (BR-CUS-022 — the option set is PROPOSED and has
//     no column). The proration rule itself is CONFIRMED; what is missing is
//     anywhere to record which of the two options was chosen.
//   · **The initial reads** (step 3's prior-final / initial / source table).
//     `initial_reads` is refused (BR-CUS-021): reads commit through metering's
//     own append-only service. The unit's meters are LISTED so the unread
//     registers are visible, and no prior-final figure is invented for them.
//   · **The plan** (step 4's select, with the unit default pre-selected).
//     `plan` / `rate_plan_id` / `plan_version` are refused (BR-CUS-029). Under
//     the PO's 2026-08-11 ruling the plan lives ONCE on the unit and the account
//     derives it, so there is nothing for a plan control here to write —
//     BR-MET-044 keeps the unit's last plan as the next tenant's prefill with
//     no action from this page.
//   · **The deposit** (step 4's three radios, including "Carry $150 forward").
//     `deposit_on_file`, `deposit_election` and `carry_deposit_from` are all
//     refused (BR-CUS-023 / BR-CUS-024): the amount is a lookup from the plan
//     deposit schedule, and carry-forward rides the customer linkage that does
//     not exist. With no customer entity there is no "same customer" to carry
//     from — the server warns exactly that.
//   · **Paperless** (step 4's checkbox). A PROPOSED-SCHEMA column that was not
//     built (BR-CUS-028). Autopay IS accepted, and IS capture-only (BR-CUS-059).
//
// BR-CUS-056 is the one rule this page can enforce ahead of the server: the
// outgoing account pays the move day, so the earliest start is the day AFTER
// its `closed_at`. That date is computed, pre-filled and explained; a start on
// or before the move day is refused server-side and named here first.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { ApiError, api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getAccountDetail,
  getAccounts,
  getUnit,
  moveInAccount,
  moveInToUnit,
} from "@/api/endpoints";
import type { UnitRow } from "@/api/endpoints";
import type { AccountDetail, AccountMoveInResult } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { todayInZone } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";
import {
  emptyFieldVisit,
  fieldVisitPayload,
  hydrateFieldVisit,
} from "@/features/work/FieldVisitOrders";
import type { FieldVisitValue } from "@/features/work/FieldVisitOrders";
import { WizardFrame } from "@/components/WizardFrame";
import { LEAVE_DELIBERATELY } from "@/components/LeaveGuard";
import type { LeaveDraft } from "@/components/LeaveGuard";
import type {
  WizardCommitOutcome,
  WizardExit,
  WizardNavState,
  WizardStep,
} from "@/components/WizardFrame";
import {
  CELL_FULL,
  isDenied,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { accountDetailQueryKey } from "./AccountDetailPage";
import {
  MOVE_INS_TAB_PATH,
  MOVE_IN_STEPS,
  MOVE_IN_STEP_SHAPE_FOUR,
  MOVE_IN_STEP_SHAPE_KEY,
  MOVE_IN_WIZARD_ROUTE,
  MOVE_OUT_WIZARD_ROUTE,
  MoveInUnitPick,
  PickFirstNote,
  lastClosedAccountForUnit,
  moveInStoredStep,
  parkStoreBlockedReason,
  stepFromParam,
} from "./moveShared";
// CR-035 — the park store, its resume handle and the list a park lands on.
import { PARKED_PARAM, parkedHomePath, hydrateForm, parkedString, useWizardPark } from "./wizardPark";
import { MoveInUnitSearch, unitTitle } from "./moveInWizard/MoveInUnitSearch";
import {
  CARRY_PARAM,
  CARRY_READS,
  FROM_MOVE_IN_VALUE,
  searchMoveInUnitRow,
  startMoveInHandover,
  useCarriedClosingReads,
  useMoveInUnitSearch,
} from "./moveInWizard/moveInUnitSearch";
import type { MoveInUnitRow } from "./moveInWizard/moveInUnitSearch";
import { datedReadsDraft, hydrateReadsDraft, readsPayloadPart } from "./moveReadsCapture";
import type { ReadsDraft } from "./moveReadsCapture";
import { emptyDiscountClaim } from "./moveInRequestBlocks";
import type { DiscountClaimForm } from "./moveInRequestBlocks";
import { getServiceRequest } from "./serviceRequestEndpoints";
import { requestBillingAddress } from "./serviceRequestShared";
import {
  type DepositForm,
  depositPayload,
  emptyDepositForm,
} from "./depositCapability";
import type { CustomerForm, PreferencesForm } from "./NewAccountWizard";
import {
  CUSTOMER_KIND_COMPANY,
  CUSTOMER_KIND_PERSON,
  customerBlockFor,
  emptyCustomerForm,
  emptyPreferencesForm,
  hydrateCustomerForm,
  mailingAddressFor,
} from "./NewAccountWizard";
import {
  ACCOUNTS_PERMISSION,
  ACCOUNTS_ROUTE,
  ACTIVE_STATUS_CODE,
  accountCloseOutPath,
  DASHBOARD_ROUTE,
  accountDetailPath,
  accountHeadline,
  earliestMoveInDate,
  isClosedAccount,
} from "./customersShared";

import type {
  MoveInDateProblem,
  MoveInStepId,
  MoveInWizardContext,
} from "./moveInWizard/moveInWizardContext";
import { StepBilling, stepBillingVerdict, useStepBillingOwn } from "./moveInWizard/StepBilling";
import {
  StepCustomer,
  requestIdentityLine,
  stepCustomerVerdict,
  useStepCustomerOwn,
} from "./moveInWizard/StepCustomer";
import type { StepCustomerOwn } from "./moveInWizard/StepCustomer";
import { coApplicantDrafts, requestCustomerCustom, requestMailing } from "./customerForm/requestCarry";
import { StepReview, useStepReviewOwn } from "./moveInWizard/StepReview";
import { StepUnit, stepUnitVerdict, useStepUnitOwn } from "./moveInWizard/StepUnit";
import { useMoveInEdit } from "./moveInWizard/useMoveInEdit";
import { moveRecordPath } from "./MoveRecordPage";
import { MoveInCompleted } from "./moveInWizard/MoveInCompleted";

import "./customers.css";

// `DEF-CUS-9052`'s helper moved with the customer step (P2.15); re-exported so
// no importer has to learn the new address.
export { requestIdentityLine };

// ── Pure pieces (provable without a browser or a network) ──────────────────

/**
 * US-CUS-004 §1: the five ruled steps, in the prototype's own order.
 *
 * **DERIVED, NOT DECLARED HERE — BR-SHL-046** (PO 2026-08-24): *"the list's
 * progress bar and the wizard's step bar must be driven by ONE declared step
 * list"*. Move-in was never in dispute; DEF-648 was about the move-out's four
 * against six. The mechanism is the durable half of that ruling, so move-in
 * reads the same single source and the Move-ins tab can read it too.
 */
export const MOVE_IN_STEP_IDS = MOVE_IN_STEPS.map((step) => step.id);
export const MOVE_IN_STEP_COUNT = MOVE_IN_STEPS.length;
/** A9 / B13 §1: the step number is URL state, so a half-done flow is linkable. */
export const STEP_PARAM = "step";

/** `?request=<id>` — the approved service request this move-in fulfils
 *  (`CR-122-BRC06`). URL state exactly like `?step=` and `?parked=`, so the
 *  link from the request's own page survives a reload and a resumed draft
 *  lands on the same move-in. */
export const REQUEST_PARAM = "request";
/** A9: `?park=1` is URL state for the same reason `?step=` is. */
export const PARK_PARAM = "park";

/** BR-SHL-011's spirit: an out-of-range `?step=` clamps, it never errors. */
export function moveInStepFromParam(raw: string | null): number {
  return stepFromParam(raw, MOVE_IN_STEPS);
}

/**
 * BR-CUS-022 + BR-CUS-056, in the order a user meets them. `on_or_before_move_day`
 * mirrors the server's own refusal so the user is told before a round trip
 * rather than after one; the server stays authoritative either way, and its
 * message names the outgoing account and the earliest legal start.
 */
export type { MoveInDateProblem };

export function moveInDateProblem(
  openedAt: string,
  earliest: string | null,
): MoveInDateProblem | null {
  if (openedAt === "") {
    return "required";
  }
  if (earliest !== null && openedAt < earliest) {
    return "on_or_before_move_day";
  }
  return null;
}

/**
 * The `POST /accounts/{id}/move-in` body — EXACTLY `services.MOVE_IN_FIELDS`
 * and nothing else. `unit_id` is absent BY CONSTRUCTION, not filtered out: the
 * unit comes from the outgoing account in the URL, and sending one would be
 * refused whole.
 *
 * `status` is always the occupying one: US-CUS-004 §1's exit is "unit derives
 * Occupied", and the server refuses a move-in whose status does not occupy
 * (the DRAFT road stays open, and it is S18).
 *
 * `contact` and `addresses` are omitted entirely when empty — an empty contact
 * object would create a nameless contact row, and an address of empty strings
 * would claim a mailing address that differs from the service one (B2 §2: no
 * mailing row IS "same as service").
 */
export function moveInPayload(args: {
  customer: CustomerForm;
  preferences: PreferencesForm;
  openedAt: string;
  /**
   * ⚠ **BR-CUS-021's OPENING READS — ADDED 2026-08-26 (CR-038 W9 task 3).**
   * `initial_reads` was a REFUSED field until the metering half existed; it is
   * now `MOVE_IN_FIELDS` and routes through `seams.commit_event_reads` with the
   * event `move_in` and the acting user stamped on every row (BR-MET-128).
   *
   * ⛔ OMITTED ENTIRELY when the clerk keyed nothing — `readsPayloadPart`
   * returns `{}`, never `{initial_reads: []}`. A move-in with no readings is
   * lawful and the server refuses an empty list on purpose.
   */
  reads?: ReadsDraft;
  /**
   * `CR-122-BRC06` — **the approved request this move-in fulfils**, or `""`.
   * `BR-CUS-080`'s child half: `moves.record_move` writes it onto the move
   * record, so the chain from the application to the account it produced
   * survives the session. ⛔ OMITTED when the clerk started from an account,
   * which is the ordinary case.
   */
  serviceRequestId?: string;
  /**
   * `CR-122-BRC06` — **the DRAFT this was keyed into.** The server adopts the
   * draft's `MVI-` reference for the finished record instead of allocating a
   * second one, and deletes the draft in the same transaction. ⛔ OMITTED when
   * there is no draft, and the server then numbers the record exactly as it
   * did before this existed.
   */
  wizardParkId?: string | null;
  /**
   * `CR-122-BRC06` — **the discount CLAIM, recorded and never acted on.**
   *
   * ⛔ It creates no discount, no enrolment and no reduction:
   * `proof_before_first_reduction` defaults true and `eligibility_rule` has no
   * evaluator behind it, so enrolment stays a staff act through
   * `discount_services.enrol_account`. ⛔ And it never gates service (B18
   * §5.3.4). It lands on `accounts.eligibility_claimed` / `eligibility_note`,
   * the same pair `service_requests` already carries.
   *
   * ⛔ OMITTED when nothing was ticked, exactly as `initial_reads` is: an
   * account nobody asked reads `false`, which is the true answer.
   */
  discount?: DiscountClaimForm;
  /**
   * ⚠ **THE TURN-ON — CR-070 wave P, `US-WRK-039`, `BR-WRK-055`.** The template
   * ids a clerk ticked on step 3. The raise happens AFTER the account, the plan
   * and the opening reads are committed, so a job that cannot be created cannot
   * leave a household without supply and without a record of why.
   *
   * ⛔ OMITTED when nothing was ticked, for `initial_reads`' reason: no visit
   * needed is the ordinary answer, and an empty election on the wire means
   * nothing.
   */
  fieldVisit?: FieldVisitValue;
  /**
   * ⚠ **THE DEPOSIT — `CR-094-BRC01` wave H, step 5.** PO: *"if there are
   * deposits, then there should be a proper flow to accept those deposit also …
   * but it should be in the same flow"*.
   *
   * ⛔ OMITTED ENTIRELY when the account owes none — `depositPayload` returns
   * `undefined`, never `{decision: "not_required"}`. A block saying *"not
   * required, 0.00"* would put a zero deposit on the confirmation where there
   * should be no deposit row at all, which is the distinction the server's own
   * `deposit.py` and `rating.deposit_rule_for` both refuse to collapse.
   */
  deposit?: DepositForm;
  /**
   * ⚠ **WHICH OF THE UNIT'S SERVICES THIS ACCOUNT TAKES —
   * `BR-CUS-1101`, PO ruling 2026-09-25.** Service CODES, ticked on step 2.
   *
   * ⛔ **OMITTED when the clerk left every one ticked**, and that is not a
   * saving — it is the honest shape. The server reads an absent `services`
   * as *every point on the unit*, which is exactly what *"I changed nothing"*
   * means, and sending the full list would record a choice nobody made.
   */
  services?: readonly string[];
  /**
   * `CR-171-BRC10` P2.15 — what each step's OWN state adds to the body
   * (`StepOwn.payload`), in step order. Merged LAST, so a step that re-draws
   * an existing capability under its existing key replaces the wizard's value.
   */
  stepPayloads?: readonly Record<string, unknown>[];
}): Record<string, unknown> {
  const { customer, preferences } = args;
  const payload: Record<string, unknown> = {
    account_type: customer.account_type,
    status: ACTIVE_STATUS_CODE,
    autopay: preferences.autopay, // BR-CUS-059 — captured, never drafted on
    tax_exempt: preferences.tax_exempt,
    // `BR-CUS-028` + `BR-BIL-036` — the two elections that ADD a channel on top
    // of the printed bill. Writable since `customers 0034`; see the fields'
    // own note on `PreferencesForm`. Sent unconditionally because `false` is a
    // real answer here: "not paperless" is a preference, not an absent value.
    paperless: preferences.paperless,
    sms_reminders: preferences.sms_reminders,
  };
  // Omitted when unanswered, never sent as `""` — the New account wizard's own
  // note on this key, and the same `CREATE_FIELDS` door.
  if (customer.account_subtype !== "") {
    payload.account_subtype = customer.account_subtype;
  }
  if (args.openedAt !== "") {
    // BR-CUS-022 / BR-CUS-056: the account's start AND every service
    // agreement's `started_on`, and the day after the outgoing account's last.
    payload.opened_at = args.openedAt;
  }
  if (preferences.preferred_language.trim() !== "") {
    payload.preferred_language = preferences.preferred_language.trim();
  }
  if (preferences.tax_exempt_ref.trim() !== "") {
    payload.tax_exempt_ref = preferences.tax_exempt_ref.trim();
  }
  // `DEF-CUS-6363` — the rows added on step 3, or *No visit needed*. OMITTED
  // when the clerk did neither, for `initial_reads`' reason.
  const visit = args.fieldVisit === undefined ? undefined : fieldVisitPayload(args.fieldVisit);
  if (visit !== undefined) {
    payload.field_visit = visit;
  }
  const deposit = args.deposit === undefined ? undefined : depositPayload(args.deposit);
  if (deposit !== undefined) {
    payload.deposit = deposit;
  }
  if (preferences.tax_exempt_expires !== "") {
    payload.tax_exempt_expires = preferences.tax_exempt_expires;
  }
  if (customer.full_name.trim() !== "") {
    payload.contact = {
      full_name: customer.full_name.trim(),
      email: customer.email.trim() === "" ? null : customer.email.trim(),
      phone: customer.phone.trim() === "" ? null : customer.phone.trim(),
      dob: customer.dob === "" ? null : customer.dob,
      // BR-CUS-045: the server keeps the LAST FOUR of whatever arrives; the
      // field asks for four digits so a full id is never typed in the first
      // place.
      gov_id_last4:
        customer.gov_id_last4.trim() === "" ? null : customer.gov_id_last4.trim().slice(-4),
      is_primary: true,
    };
  }
  // ── `CR-058` task 8 — **THE `customer` BLOCK THIS SCREEN NEVER SENT** ────
  // `POST /accounts/{id}/move-in` has accepted the whole customer block since
  // `CR-056` W3 — name, kind, SSN, licence, phone, Tax ID and the returning-
  // customer matcher — and this payload sent **a contact only**. So every
  // move-in at the counter produced an account with a blank customer column,
  // which is hard-won law 2 (built is not wired) on the second of two screens.
  // PO 2026-09-01 on this door: *"You either create new Customer ID or you link
  // existing customer ID here"*.
  //
  // ⚠ **IMPORTED FROM S18, NEVER COPIED.** Both wizards write the same customer
  // and `CR-058` task 3's whole point is that no door repeats the logic.
  const block = customerBlockFor(customer);
  if (block !== null) {
    payload.customer = block;
  }
  // `DEF-CUS-6359` — ONE builder for both doors: nothing when *Same as service
  // address* is ticked, the five US parts when it is not.
  const mailing = mailingAddressFor(customer);
  if (mailing !== null) {
    payload.addresses = [mailing];
  }
  // CR-122-BRC06 — the claim, and the note only where there is one. The CODES
  // are what the clerk ticked; they travel in the note because `accounts` has
  // one text column for this and inventing a second table for three checkboxes
  // would be a store nobody ruled on. The note is what a person reads when they
  // follow the claim up, so it names the discounts in words.
  const claimedCodes = args.discount?.codes ?? [];
  if (claimedCodes.length > 0) {
    payload.eligibility_claimed = true;
    const typed = (args.discount?.note ?? "").trim();
    payload.eligibility_note = typed === ""
      ? claimedCodes.join(", ")
      : `${claimedCodes.join(", ")} — ${typed}`;
  }
  // CR-122-BRC06 — both are OMITTED rather than sent empty: `_reject_unknown`
  // would take either, but a `""` reaching `_adopt_move_in_draft` or
  // `record_move` is a value that has to be tested for at the far end, and a
  // key that is simply absent is not.
  // `BR-CUS-1101` — the ticks, and ONLY when they are a real subset. The
  // caller hands in both lists so this one decision lives in one place.
  if (args.services !== undefined) {
    payload.services = [...args.services];
  }
  if ((args.serviceRequestId ?? "") !== "") {
    payload.service_request_id = args.serviceRequestId;
  }
  if ((args.wizardParkId ?? "") !== "") {
    payload.wizard_park_id = args.wizardParkId;
  }
  return Object.assign(
    // DEF-CUS-10165 — every opening read carries the date its box showed.
    { ...payload, ...readsPayloadPart("initial_reads", datedReadsDraft(args.reads ?? {}, args.openedAt)) },
    ...(args.stepPayloads ?? []),
  );
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface MoveInWizardProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

/**
 * ⚠ **THE WIZARD IS KEYED, SO *+ START ANOTHER MOVE-IN* STARTS FROM NOTHING
 * (`CR-171-BRC10` P2.16, image 48).** The completed screen replaces the wizard
 * at the SAME address, so a link back to `/move-ins/new` would leave every
 * piece of state — the answer included — exactly where it was. Bumping the key
 * remounts the body: a fresh form, a fresh draft, nothing carried over.
 */
export function MoveInWizard(props: MoveInWizardProps) {
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const [round, setRound] = useState(0);
  return (
    <MoveInWizardBody
      key={round}
      {...props}
      onStartAnother={() => {
        navigate(tenantPath(MOVE_IN_WIZARD_ROUTE));
        setRound((current) => current + 1);
      }}
    />
  );
}

function MoveInWizardBody(props: MoveInWizardProps & { onStartAnother: () => void }) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { timeZone, dateFormat } = useRegional(props);


  // ══════════════════════════════════════════════════════════════════════════
  // TWO WAYS IN, ONE WIZARD — PO ruling 2026-08-26 ("-Enable Move in /move out")
  // ══════════════════════════════════════════════════════════════════════════
  // `/accounts/:accountId/move-in` — the OUTGOING account arrived in the URL
  // from the close-out chain or from the closed account's own page. Unchanged.
  //
  // `/move-ins/new` — nothing arrived, and the PO's own sentence says what step
  // 1 must therefore ask: *"a move-in creates the next occupant of a particular
  // account's unit"*. So the clerk chooses the UNIT — the thing in front of them
  // — and the outgoing account is DERIVED from it by the server's own rule
  // (`moveShared.lastClosedAccountForUnit`, which mirrors
  // `apps/customers/selectors.last_closed_account_for_unit`).
  //
  // ⚠ **A UNIT WITH NO FINISHED TENANCY IS A FIRST OCCUPANT (`DEF-CUS-6353`).**
  // `POST /accounts/{id}/move-in` takes the outgoing account in its PATH, so a
  // unit nobody has lived in commits through `POST /units/{unit_id}/move-in`
  // instead — the same server body and guards, with the unit in the path.
  const routeAccountId = params.accountId ?? "";
  const standalone = routeAccountId === "";
  const [unitId, setUnitId] = useState("");
  // ══════════════════════════════════════════════════════════════════════════
  // CR-122-BRC06 · THE REQUEST THIS MOVE-IN CAME FROM
  // ══════════════════════════════════════════════════════════════════════════
  // PO ruling 2026-09-19, verbatim: *"here if ove is coming from service
  // request these details will be filled in"*.
  //
  // ⚠ **THE COLUMN WAS NEVER MISSING — THE WIRE WAS (hard-won law 2).**
  // `service_request_id` joined `MOVE_IN_FIELDS` on 2026-09-15 under
  // `CR-094-BRC01` and the server has accepted it ever since; this file had
  // ZERO references to a service request in 1,932 lines. Nothing set the link
  // on the way in and nothing read the request on the way out, so step 2 asked
  // a clerk to re-key a name, an email, a phone and a date of birth that an
  // approved request was already holding.
  //
  // It is URL state (`?request=<id>`) for the reason `?step=` and `?parked=`
  // are: the approved request's own page links here, and a reload, a bookmark
  // or a resumed draft has to land on the same move-in.
  const [serviceRequestId, setServiceRequestId] = useState(
    () => searchParams.get(REQUEST_PARAM) ?? "",
  );
  // The forward fence is the step itself: a user can always go BACK to a step
  // they have been on, and forward only through Continue (BR-SHL-018).
  const step = moveInStepFromParam(searchParams.get(STEP_PARAM));
  const nav: WizardNavState = { step, reached: step };
  function setStep(next: WizardNavState): void {
    const query = new URLSearchParams(searchParams);
    query.set(STEP_PARAM, String(next.step));
    setSearchParams(query, { replace: true });
  }
  const [customer, setCustomer] = useState<CustomerForm>(emptyCustomerForm);
  const [preferences, setPreferences] = useState<PreferencesForm>(emptyPreferencesForm);
  const [openedAt, setOpenedAt] = useState("");
  const [result, setResult] = useState<AccountMoveInResult | null>(null);
  /** `CR-171-BRC10` P2.17 — the resumed draft's `MVI-` reference (`""` when it
   *  has none), or `null` on a new move-in. Drives *Edit move-in · …*. */
  const [editReference, setEditReference] = useState<string | null>(null);
  /** CR-181-BRC10 — a reopen refusal, drawn on the Customer step; cleared on
   *  the next change there. */
  const [reopenRefusal, setReopenRefusal] = useState<string | null>(null);
  // A9: `?park=1`, exactly like `?step=` — a reload mid-park keeps the form.
  const parkOpen = searchParams.get(PARK_PARAM) === "1";
  function setParkOpen(open: boolean): void {
    const query = new URLSearchParams(searchParams);
    if (open) {
      query.set(PARK_PARAM, "1");
    } else {
      query.delete(PARK_PARAM);
    }
    setSearchParams(query, { replace: true });
  }

  const cell = useAccessCell(ACCOUNTS_PERMISSION, client);
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("customers.accounts.rbac.readOnly");

  // ══════════════════════════════════════════════════════════════════════════
  // DEF-CUS-10190 · THE PICKER SEARCHES EVERY UNIT (PO ruling 2026-10-17)
  // ══════════════════════════════════════════════════════════════════════════
  // *"user wants search all units irrespective of ther tatus and perform the
  // move-in process"*. This REPLACES `GET /units?f.occupancy=vacant&per=500`
  // (BR-CUS-020's vacant-only read, and an `NFR-3` breach at T5): the server
  // pages the search, sorts vacant first, and says per row what a move-in may
  // do — `move_in`, `move_out_first`, `close_out_first`, or nothing (blocked,
  // with its reason). An occupied unit's move-in raises the OLD occupant's
  // move-out first (*"the move-in won't close their account by itself"*).
  const [unitTerm, setUnitTerm] = useState("");
  const [unitPage, setUnitPage] = useState(1);
  const [chosenRow, setChosenRow] = useState<MoveInUnitRow | null>(null);
  const [settling, setSettling] = useState(false);
  const [settleRefusal, setSettleRefusal] = useState<string | null>(null);
  const unitSearch = useMoveInUnitSearch(unitTerm, unitPage, client, standalone && chosenRow === null);
  // A resumed draft names a unit but not its row: the row is RE-READ (BR-SHL-048
  // (b) — what was true when it was parked may not be true now).
  const chosenRowQuery = useQuery({
    queryKey: ["move-in-unit-row", unitId],
    queryFn: () => searchMoveInUnitRow(unitId, client),
    enabled: standalone && unitId !== "" && (chosenRow === null || chosenRow.id !== unitId),
    retry: false,
  });
  useEffect(() => {
    const row = chosenRowQuery.data ?? null;
    if (row !== null && row.id === unitId) setChosenRow(row);
  }, [chosenRowQuery.data, unitId]);

  // The PUBLISHED account list, filtered by the unit (`unit_id` is in
  // `ACCOUNT_FILTERS` and has been served since W2). NO new endpoint — the same
  // finding `accountFinder.tsx` records for the account search.
  const unitAccountsQuery = useQuery({
    queryKey: ["move-in-unit-accounts", unitId],
    queryFn: () => getAccounts({ filters: { unit_id: unitId }, per: 200 }, client),
    enabled: standalone && unitId !== "",
    retry: false,
  });
  const predecessor =
    unitAccountsQuery.data === undefined
      ? null
      : lastClosedAccountForUnit(unitAccountsQuery.data.results);
  /** `DEF-CUS-6353` — the unit's accounts have been READ and none of them is a
   *  finished tenancy: nobody has lived here, so nobody is being followed. */
  const firstOccupant =
    standalone && unitId !== "" && unitAccountsQuery.isSuccess && predecessor === null;
  /** The picked unit's own row, for the facts step 1 shows when there is no
   *  outgoing account to read them off. */
  //  `DEF-CUS-10190` — the vacant-only list that answered this is gone; no
  //  step reads it (`ctx.pickedUnit` has no reader), so it stays null.
  const pickedUnit: UnitRow | null = null;

  /** The account whose unit is being taken — from the URL, or derived from the
   *  unit the clerk chose. `""` means "not resolved", never "none". */
  const fromAccountId = standalone ? (predecessor?.id ?? "") : routeAccountId;

  const outgoingQuery = useQuery({
    queryKey: accountDetailQueryKey(fromAccountId),
    queryFn: () => getAccountDetail(fromAccountId, client),
    enabled: fromAccountId !== "",
  });

  // ── CR-038 W9 task 3 · BR-CUS-021's opening reads ─────────────────────────
  // The registers the clerk keyed, and the inventory they were keyed against.
  // The query lives HERE rather than inside the step, so the capture table and
  // `UnitAssetsPanel` read ONE answer — two `useQuery` calls on the same key
  // would be one cache entry and two renders, and the capture would draw rows
  // the panel had not listed yet.
  // ⚠ NOT the `unitId` above — that one is the standalone road's PICKED unit,
  // which is empty on the account-scoped road. This is the unit the OUTGOING
  // account actually holds, which is the only unit whose meters are being
  // taken over, on both roads.
  // `DEF-CUS-6353` — a first occupant has no outgoing account, so the unit is
  // the one the clerk picked.
  const outgoingUnitId = outgoingQuery.data?.unit_id ?? (firstOccupant ? unitId : "");
  // ⚠ **EMPTY, NOT SEEDED — PO 2026-09-23 (`DEF-CUS-6362`).** This called
  // `useReadsDraft`, which fills every box with the register's last reading:
  // `OQ-394`'s ruling, asked about a MOVE-OUT's closing figure. On a move-in a
  // prefilled box nobody touched records a reading nobody took, so the PO
  // approved an empty box with the last reading in its own column beside it.
  // Only what the clerk types is in this draft. The move-out keeps its prefill.
  const [readsDraft, setReadsDraft] = useState<ReadsDraft>({});
  // `DEF-CUS-10190` — back from the old occupant's move-out (`?carry=reads`):
  // the opening reads are the closing reads just taken, with their dates.
  useCarriedClosingReads({
    enabled: standalone && searchParams.get(CARRY_PARAM) === CARRY_READS,
    unitId: outgoingUnitId,
    client,
    draft: readsDraft,
    setDraft: setReadsDraft,
  });

  // ── `BR-CUS-1101` · step 2 — WHICH OF THE UNIT'S SERVICES THIS
  // ACCOUNT TAKES (PO ruling 2026-09-25) ────────────────────
  //
  // ⚠ **THE OFFER IS THE UNIT'S POINTS AND NOT THE OUTGOING ACCOUNT'S
  // SERVICES**, and after this rule those are two different lists. Step 1's
  // fact row reads `outgoing.services`, which is one chip per agreement the
  // LEAVING tenant held — so once a tenant can take three of six, a next
  // occupant offered that list could never take back the three their
  // predecessor dropped. `metered_services` is metering's own de-duplication
  // of this unit's service points, which is the same walk the server makes in
  // `_unit_service_offer`.
  //
  // ⚠ **`outgoingUnitId` AND NOT `unitId`** — the same distinction the
  // reads capture above makes: `unitId` is the standalone road's picked unit
  // and is empty on the account-scoped road.
  const unitOfferQuery = useQuery({
    queryKey: ["unit", "move-in-service-offer", outgoingUnitId],
    queryFn: () => getUnit(outgoingUnitId, client),
    enabled: outgoingUnitId !== "",
    retry: false,
  });
  const serviceOffer: readonly string[] = unitOfferQuery.data?.metered_services ?? [];
  /** `null` = **the clerk has not touched the ticks**, which is a different
   *  fact from *every one ticked* and is what rides in a parked draft.
   *
   *  ⚠ **THE PRE-TICK IS A FALLBACK, NOT AN EFFECT, AND THAT IS
   *  DELIBERATE.** An effect that copied the offer into state would not run
   *  under `renderToStaticMarkup`, so every server-rendered assertion would see
   *  an all-UNTICKED step over a unit that offers six services — a test
   *  looking at the wrong thing (hard-won law 7). Falling back to the offer
   *  renders the same ticks on both paths and needs no effect at all. */
  const [chosenServices, setChosenServices] = useState<string[] | null>(null);
  const ticked: readonly string[] = chosenServices ?? serviceOffer;
  /** ⛔ **OMITTED WHEN NOTHING WAS DROPPED.** An absent `services` means
   *  *every point on the unit* to the server, which is exactly what a clerk who
   *  changed nothing meant — sending the full list would record a choice
   *  nobody made. */
  const servicesForPayload =
    serviceOffer.length > 0 && ticked.length < serviceOffer.length ? ticked : undefined;

  // ── CR-070 wave P · the turn-on (US-WRK-039, BR-WRK-055) ──────────────────
  //
  // Asked about the OUTGOING account, because that is what this wizard has in
  // its hand on step 3: the new account does not exist until the commit, and
  // the services are the same — it is the same unit.
  // ⚠ **`DEF-CUS-6363` — THE FIELD VISIT IS ROWS A CLERK ADDS, NOT A TICK LIST
  // OF PUBLISHED TEMPLATES.** `RaiseFieldWork` offered only the utility's
  // published templates (none at a utility that has written none) and spoke of
  // a move-out. `FieldVisitOrders` is the ONE component every flow mounts; it
  // reads its own options, and the orders are still RAISED at the save.
  const [fieldVisit, setFieldVisit] = useState<FieldVisitValue>(emptyFieldVisit);
  /** Continue has been pressed on a step — only then are its refusals red
   *  (`DEF-CUS-6360`, `DEF-CUS-6363`). One record for the four steps. */
  const [tried, setTried] = useState<Record<MoveInStepId, boolean>>({
    unit: false,
    customer: false,
    billing: false,
    review: false,
  });
  // `CR-171-BRC10` P2.15 — each step's OWN state, held here so it outlives
  // the rail but declared in the step's file (see `moveInWizardContext.ts`).
  const unitOwn = useStepUnitOwn();
  const customerOwn = useStepCustomerOwn(customer);
  const billingOwn = useStepBillingOwn();
  const reviewOwn = useStepReviewOwn();
  // `CR-094-BRC01` wave H — step 5's own state, parked and hydrated with the
  // rest (`BR-SHL-048` (a)): a clerk who walks away mid-deposit comes back to
  // the figure they had typed, and to nothing else.
  const [deposit, setDeposit] = useState<DepositForm>(emptyDepositForm);
  // `CR-122-BRC06` — step 4's discount CLAIM, parked and hydrated with the
  // rest. ⛔ It gates nothing: B18 §5.3.4, *"never blocks service — only the
  // discount"*, so it appears in no `validate` and in no refusal.
  const [discount, setDiscount] = useState<DiscountClaimForm>(emptyDiscountClaim);

  // ══════════════════════════════════════════════════════════════════════════
  // CR-122-BRC06 · READ THE REQUEST, AND FILL STEP 2 FROM IT — ONCE
  // ══════════════════════════════════════════════════════════════════════════
  // PO ruling 2026-09-19: *"here if ove is coming from service request these
  // details will be filled in"*.
  const requestQuery = useQuery({
    queryKey: ["service-request", serviceRequestId],
    queryFn: () => getServiceRequest(serviceRequestId, client),
    enabled: serviceRequestId !== "",
    // The request is read ONCE and then belongs to the form, exactly as a
    // parked draft is: refetching behind a clerk who is typing would overwrite
    // their corrections with the application they are correcting.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  // ⚠ **THE PREFILL RUNS ONCE PER REQUEST AND NEVER AGAIN, AND THE GUARD IS A
  // REF.** A clerk correcting a misspelled name must not have it typed back
  // over them on the next render — which is what state, or no guard at all,
  // would do. This is the same shape `useWizardPark`'s `hydrated` ref takes,
  // for the same reason.
  const prefilled = useRef<string | null>(null);
  useEffect(() => {
    const request = requestQuery.data;
    if (request === undefined || prefilled.current === serviceRequestId) {
      return;
    }
    prefilled.current = serviceRequestId;
    const applicant = request.applicant;
    setCustomer((current) => ({
      ...current,
      // ⛔ **ONLY WHERE THE CLERK HAS TYPED NOTHING.** A resumed draft hydrates
      // BEFORE this runs, and a draft is what the clerk actually left behind —
      // so anything already in the box wins over the application it came from.
      full_name: current.full_name === "" ? (applicant.name ?? "") : current.full_name,
      email: current.email === "" ? (applicant.email ?? "") : current.email,
      phone: current.phone === "" ? (applicant.phone ?? "") : current.phone,
      dob: current.dob === "" ? (applicant.date_of_birth ?? "") : current.dob,
      // `DEF-CUS-9035` — the class the clerk picked ON THE REQUEST (capture
      // step 2). The form opens on `residential`, so the request's class
      // replaces that opening value only; a legacy class is never offered on
      // a new record (`BR-CUS-094`) and is left for the clerk to choose. The
      // request's LINKED customer is carried by the server, which adds it to
      // the customer block when this wizard names none.
      account_type:
        current.account_type === "residential" &&
        applicant.customer_category?.account_type &&
        applicant.customer_category.account_type.legacy !== true
          ? applicant.customer_category.account_type.code
          : current.account_type,
      // `DEF-CUS-6359` — the request's billing address becomes the mailing
      // address, unticking *Same as service address*; where the applicant said
      // "same as service" (or gave none) the box stays ticked. Again ONLY where
      // the clerk has typed nothing, so a resumed draft wins.
      // ⊕ Lane CF-1 — the government ID's last four, which is all the request
      // keeps and therefore safe to put in the box.
      gov_id_last4:
        current.gov_id_last4 === "" ? (applicant.gov_id_last4 ?? "") : current.gov_id_last4,
      ...(() => {
        // ⊕ Lane CF-1 — the one name for where the bill goes (`mailing_address`),
        // falling back to the older parts a cached detail carries.
        const billing = requestMailing(request) ?? requestBillingAddress(request.location_and_services);
        if (billing === null || current.mailing_line1 !== "" || !current.mailing_same) {
          return {};
        }
        return {
          mailing_same: false,
          mailing_line1: billing.line1,
          mailing_line2: billing.line2,
          mailing_city: billing.city,
          mailing_state: billing.state,
          mailing_postal_code: billing.postal_code,
        };
      })(),
    }));
    setPreferences((current) => ({
      ...current,
      preferred_language:
        current.preferred_language === ""
          ? (applicant.language ?? "")
          : current.preferred_language,
      // ⊕ Lane CF-1 — the request's Preferences (no autopay on a request).
      // An election is only ever turned ON from the request, never off.
      paperless: current.paperless || applicant.preferences?.paperless === true,
      sms_reminders: current.sms_reminders || applicant.preferences?.sms_reminders === true,
    }));
    // ⊕ **LANE CF-1 (2026-10-18) — EVERY OTHER VALUE THE REQUEST HOLDS.** PO:
    // *"ALSO DATA COLECTED IS NOT LOST"*; image 01's note *"From an approved
    // request: every field arrives filled in"*. Contact by, the co-applicant
    // cards (their SSN and licence are carried by the server — the screen is
    // only ever shown a last four) and the utility's own customer fields —
    // each ONLY where the clerk, or a resumed draft, has put nothing.
    (customerOwn.set as unknown as Dispatch<SetStateAction<StepCustomerOwn>>)((current) => {
      const cards = coApplicantDrafts(applicant);
      const custom = requestCustomerCustom(request);
      return {
        ...current,
        contact_by: current.contact_by === "" ? (applicant.contact_by ?? "") : current.contact_by,
        co_owners_on: current.co_owners.length === 0 && cards.length > 0 ? true : current.co_owners_on,
        co_owners: current.co_owners.length === 0 ? cards : current.co_owners,
        custom: Object.keys(current.custom).length === 0 ? custom : current.custom,
      };
    });
    // ⊕ **`DEF-CUS-9044` — THE THREE FACTS THE REQUEST HOLDS AND THIS WIZARD
    // ASKED AGAIN.** The unit the clerk picked on the request, whether the
    // applicant is a person or a business, and the day they asked to start.
    // Each was re-asked from blank — step 1 a list of every vacant unit — so a
    // clerk could open the account on a different unit or date from the one
    // they approved. Same posture as every field above: ONLY where the clerk
    // (or a resumed draft) has put nothing.
    const requestUnit = request.location_and_services.resolved_unit_id ?? "";
    if (requestUnit !== "") {
      setUnitId((current) => (current === "" ? requestUnit : current));
    }
    const requestKind =
      applicant.person_or_company === "business" || applicant.person_or_company === "company"
        ? CUSTOMER_KIND_COMPANY
        : applicant.person_or_company === "person"
          ? CUSTOMER_KIND_PERSON
          : "";
    if (requestKind !== "") {
      setCustomer((current) =>
        current.customer_kind === "" ? { ...current, customer_kind: requestKind } : current,
      );
    }
    const requestStart = request.header.requested_start ?? "";
    if (requestStart !== "") {
      setOpenedAt((current) => (current === "" ? requestStart : current));
    }
    // ⛔ **THE TWO ENCRYPTED IDENTIFIERS ARE NOT COPIED, DELIBERATELY.** The
    // request stores an SSN and a driving licence encrypted and serves only
    // the LAST FOUR of each (BR-CUS-045). Writing `••••4417` into the box the
    // clerk is about to submit would send that literal string to the server as
    // an identifier. A clerk re-keys those two, and that is the correct cost.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestQuery.data, serviceRequestId]);

  // ⊕ **`DEF-CUS-9052` — WHO THE REQUEST ALREADY SAYS THIS IS.** A customer the
  // clerk linked on the request, or (for a business) the Tax ID it typed on its
  // portal application. The server carries either into the account
  // (`_carry_request_decisions`), so the customer step shows it and does not
  // demand an identifier the clerk would only retype. A clerk who types one
  // anyway is still sent, and wins.
  const identityFromRequest = requestIdentityLine(requestQuery.data, customer.customer_kind, translate);

  // ⚠ **A REF, BECAUSE THE MUTATION IS DECLARED ABOVE THE PARK HOOK AND THE
  // HOOK ORDER IS NOT NEGOTIABLE (`CR-122-BRC06`).** `useWizardPark` must sit
  // below every early return's guard and above none of them; reading
  // `park.parkedId` here directly would be a use-before-declare. The ref is
  // synced by the effect just under the hook, and the mutation reads it at
  // CLICK time — long after any render has settled.
  const parkIdRef = useRef<string | null>(null);

  const moveIn = useMutation({
    mutationFn: () => {
      const body = moveInPayload({
        customer,
        preferences,
        openedAt,
        reads: readsDraft,
        fieldVisit,
        deposit,
        serviceRequestId,
        wizardParkId: parkIdRef.current,
        discount,
        services: servicesForPayload,
        stepPayloads: [unitOwn.payload, customerOwn.payload, billingOwn.payload, reviewOwn.payload],
      });
      // `DEF-CUS-6353` — with no account to follow, the unit's own door.
      return fromAccountId === ""
        ? moveInToUnit(unitId, body, client)
        : moveInAccount(fromAccountId, body, client);
    },
  });

  // ══════════════════════════════════════════════════════════════════════════
  // CR-035 — PARK AND RESUME, AND IT IS DECLARED ABOVE EVERY EARLY RETURN
  // ══════════════════════════════════════════════════════════════════════════
  // Four whole-page returns follow this line (denied · loading · failed · done).
  // A hook after any of them is a hook that runs on some renders and not others,
  // which React refuses at runtime rather than at compile time — so the binding
  // is built here, where every road passes through, and both roads pass the SAME
  // `exit` object down. One park path, not two.
  //
  // ⚠ **THE SUBJECT IS THE UNIT, IN THE WORDS THE PICKER SHOWED**, and it is
  // COPIED (BR-SHL-048 (a)): a parked draft carries no foreign key, so this
  // string is what the "Waiting on" list reads a week later even if the premise
  // has been renamed since. `subjectRef` is the unit id, carried so the wizard
  // can look the unit up AGAIN on resume — never so anything can join to it.
  const unitLabel =
    (chosenRow !== null && chosenRow.id === unitId ? unitTitle(chosenRow) : null) ??
    outgoingQuery.data?.unit_label ??
    "";
  // CR-171-BRC10 P2.34 (lane MVI-WIZ-REV) — put a draft's or an edit's
  // values into the form. ONE function for both, so an Edit opens exactly as
  // a resumed draft does (the PO's *"use same form Add form to edit"*).
  function applyValues(values: Record<string, unknown>): void {
    setUnitId(parkedString(values, "unit_id"));
    setOpenedAt(parkedString(values, "opened_at"));
    setCustomer(hydrateCustomerForm(values.customer));
    setPreferences(hydrateForm(emptyPreferencesForm(), values.preferences));
    setDeposit(hydrateForm(emptyDepositForm(), values.deposit));
    // CR-122-BRC06 — the opening reads and the request this came from. Both
    // are distrusted exactly as the four above are: `hydrateReadsDraft`
    // keeps only rows whose shape it recognises, and the request id is
    // re-read from the server on resume rather than believed.
    setReadsDraft(hydrateReadsDraft(values.reads));
    setServiceRequestId(parkedString(values, "service_request_id"));
    setDiscount(hydrateForm(emptyDiscountClaim(), values.discount));
    setFieldVisit(hydrateFieldVisit(values.field_visit));
    // `BR-CUS-1101` — distrusted like every other parked value: only an array
    // of strings is taken, and anything else lands back on `null`, which
    // re-pre-ticks from the unit's offer when it loads.
    setChosenServices(
      Array.isArray(values.services)
        ? values.services.filter((code): code is string => typeof code === "string")
        : null,
    );
    // P2.15 — each step distrusts its own slice (`StepOwn.hydrate`).
    const own =
      typeof values.step_own === "object" && values.step_own !== null
        ? (values.step_own as Record<string, unknown>)
        : {};
    unitOwn.hydrate(own.unit);
    customerOwn.hydrate(own.customer);
    billingOwn.hydrate(own.billing);
    reviewOwn.hydrate(own.review);
  }
  // P2.34 — `?request=<id>&edit=1` (the details view's Edit) opens THIS form
  // on the request (`GET|PUT …/move-in-form`); `useMoveInEdit` says how.
  const edit = useMoveInEdit({ client, requestId: serviceRequestId, apply: applyValues });
  const parkValues: Record<string, unknown> = {
    unit_id: unitId,
    opened_at: openedAt,
    customer,
    preferences,
    deposit,
    // CR-122-BRC06 — the reads and the request link ride in the draft too,
    // because "every field of every step" is the requirement and a clerk
    // who keyed four opening readings has done the slowest part of the job.
    reads: readsDraft,
    service_request_id: serviceRequestId,
    discount,
    // `BR-CUS-1101` — the ticks ride in the draft too. `null` is *not
    // touched*, which is a different fact from *all of them ticked* and
    // hydrates back as the pre-tick rather than as a recorded choice.
    services: chosenServices,
    // `DEF-CUS-6363` — the work-order rows ride in the draft; nothing is
    // RAISED until the move-in is saved.
    field_visit: fieldVisit,
    // ⚠ **`CR-171-BRC10` P1.03 — WHICH SHAPE WROTE THIS DRAFT.** The
    // seven→four step map is not idempotent, so the list's STEP cell and
    // the resume below must know a four-step draft from a seven-step one
    // (`moveShared.moveInDraftIsFourStep`; `move_reads` reads the same key).
    [MOVE_IN_STEP_SHAPE_KEY]: MOVE_IN_STEP_SHAPE_FOUR,
    // P2.15 — each step's own state, under the step's id.
    step_own: {
      unit: unitOwn.park,
      customer: customerOwn.park,
      billing: billingOwn.park,
      review: reviewOwn.park,
    },
  };
  const park = useWizardPark({
    steps: MOVE_IN_STEPS,
    step,
    parkOpen,
    context: {
      flow: "move_in",
      subjectLabel: unitLabel,
      // BR-SHL-048 (a) — COPIED ids in a plain object, never a foreign key. The
      // outgoing account rides along because the endpoint is account-scoped
      // (`POST /accounts/{id}/move-in`) and a resume has to find it again; both
      // are looked up afresh, neither is joined to.
      subjectRef: {
        unit_id: unitId === "" ? (outgoingQuery.data?.unit_id ?? null) : unitId,
        account_id: fromAccountId === "" ? null : fromAccountId,
        // `DEF-CUS-9735` — a move-in from a request names it, and an approved
        // one carries the job's `MVI-` number, so the draft is found again
        // and spends no second number.
        ...edit.subjectRef,
      },
      values: parkValues,
    },
    // P1.03 — a seven-step draft resumes on the CR's map, every value kept.
    storedStep: moveInStoredStep,
    t: translate,
    client,
    // ⚠ **CR-122-BRC06 — THE DRAFT, AND IT IS THE SAME ROW `Park` WRITES.**
    // PO ruling 2026-09-19. Until today `Save & exit` "left quietly and wrote
    // NOTHING", so the head carried two buttons side by side, one of which
    // silently threw away everything typed — and nothing on either told a
    // clerk which was which. This writes the draft on open and keeps it
    // current, so BOTH buttons now keep the work and the only difference left
    // is the one B19 §12.2 names: `Park` also records what is being waited on.
    // ⚠ P2.34 — NOT while an Edit is being read, and never on an undecided
    // request: its draft is the request's own (`PUT …/move-in-form`), and an
    // autosave here would mint a second move-in for it (`DEF-CUS-9731`).
    autosave: edit.mode === "none" || edit.mode === "move_in",
    // BR-SHL-048 (b) — the typing comes back and NOTHING ELSE does. No cached
    // predecessor, no remembered "the unit was free": `unitAccountsQuery` and
    // `outgoingQuery` re-fire from the hydrated id, and `unitFree` is recomputed
    // from today's answer. A unit taken while this sat parked refuses the commit
    // exactly as it would for a clerk who had just typed it.
    onHydrate: (row) => {
      // P2.34 — an Edit of an approved request resumes the request's own
      // park; the form already holds the edit's values (the request's facts
      // laid over that park), so the park's stripped copy must not go over them.
      if (edit.applied) return;
      setEditReference(row.reference ?? "");
      applyValues(row.values);
    },
    // CR-035 · AMENDMENT 1 (PO 2026-08-26) — a parked draft lands on the tab
    // for its OWN kind of work, not on a ninth queue. `parkedHomePath` is the
    // one place those five destinations are named.
    onParked: () => navigate(tenantPath(parkedHomePath("move_in"))),
  });
  // CR-122-BRC06 — see `parkIdRef`. `park.parkedId` is `?parked=`, which the
  // autosave sets the moment it writes the draft, so this is the draft's id
  // from the clerk's first keystroke onward.
  useEffect(() => {
    parkIdRef.current = park.parkedId;
  }, [park.parkedId]);

  /**
   * CR-030 W5 task 5.1 · BR-SHL-047 · CR-035 — `Save & exit` and `Park`, from
   * the frame, and **they stay two controls** (B19 §12.2).
   *
   * `Save & exit` leaves quietly and writes NOTHING: the step is in the address
   * bar and that is all it relies on. `Park` writes a draft that records what is
   * being waited on, a note and a reminder — and still writes nothing outside
   * the draft store (BR-SHL-048). Collapsing them would lose the answer to
   * *"what are you waiting for?"*, which is the entire point of the second one.
   *
   * ⚠ **DECLARED ONCE FOR BOTH ROADS.** The unchosen-unit road used to build its
   * own inline `exit` with a stub `onPark`; two park paths is how one of them
   * quietly stops working.
   */
  // ⚠ **IT NO LONGER THROWS THE TYPING AWAY, AND IT DID NOT NEED A SAVE STEP
  // TO STOP (`CR-122-BRC06`).** The autosave above has already written every
  // keystroke to the draft, so leaving is just leaving. `CR-171-BRC10` P2.17:
  // the button is the page head's *Save draft & exit* (image 30), and on
  // `/move-ins/new` it lands on the Move-ins list whatever unit was picked —
  // the list is where the draft is (CR §5.3: the back link is *← Move-ins*).
  const leave = () =>
    navigate(tenantPath(standalone ? MOVE_INS_TAB_PATH : accountDetailPath(fromAccountId)), {
      state: LEAVE_DELIBERATELY,
    });
  // P2.34 — on an undecided request, *Save draft & exit* and the last step's
  // commit both write back to the REQUEST and return to its details view.
  async function saveRequestEdit(): Promise<WizardCommitOutcome> {
    try {
      await edit.save(step, parkValues);
      navigate(tenantPath(edit.requestNo ? moveRecordPath(edit.requestNo) : MOVE_INS_TAB_PATH), {
        state: LEAVE_DELIBERATELY,
      });
      return { ok: true };
    } catch (error) {
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }
  // ══════════════════════════════════════════════════════════════════════
  // **`DEF-CUS-10002` — AN UNDECIDED REQUEST'S EDIT NOW KEEPS ITSELF CURRENT,
  // IN ITS OWN STORE.** PO, confirming the cause (2026-10-07): *"The move-in
  // was opened from a service request, where automatic save is off, so the
  // work really was lost."* The park autosave above stays OFF here, because a
  // park row would mint a second move-in for the request (`DEF-CUS-9731`);
  // what runs instead is `PUT …/move-in-form` — the request's own draft, the
  // one *Save draft & exit* already writes — a moment after each change.
  //
  // ⚠ **THE BASELINE IS NOT FROZEN ON THE FIRST RENDER.** Applying the
  // request's values ripples through derived fields for a render or two; a
  // baseline frozen at once would read that ripple as the clerk's change and
  // write the request back untouched. It used to be frozen by an 800 ms timer
  // instead, which lost a change typed inside the window (`DEF-CUS-10014`);
  // it now follows the form until the clerk first acts — see below. `pending`
  // (the form still being read) writes nothing, as before.
  // ══════════════════════════════════════════════════════════════════════
  const [requestAutosaveFailed, setRequestAutosaveFailed] = useState(false);
  const requestSnapshot = JSON.stringify({ step, values: parkValues });
  const latestRequestSnapshot = useRef(requestSnapshot);
  latestRequestSnapshot.current = requestSnapshot;
  const requestBaseline = useRef<string | null>(null);
  // ── `DEF-CUS-10014` — THE BASELINE IS THE LOADED FORM, NOT A CLOCK ───────
  // ⚠ **IT WAS TAKEN BY AN 800 MS TIMER, AND A CHANGE TYPED INSIDE THOSE
  // 800 MS BECAME THE BASELINE.** Measured on 2.560.3: the form loaded, the
  // date was typed half a second later, the timer then read the typed date as
  // *what the request already says*, no `PUT` was ever sent, and *Leave
  // without saving* lost it (leave-guard walk A8, three runs of three).
  //
  // Now the baseline FOLLOWS the form — the request's values as applied, and
  // any ripple through derived fields after them — until the clerk first acts
  // on the page (a key, a pointer, an input), and stops there. So the first
  // change a PERSON makes is always a difference, however soon after load,
  // and a ripple nobody made is never one. No timer decides either.
  const requestTouched = useRef(false);
  const requestMode = edit.mode === "request";
  useEffect(() => {
    requestTouched.current = false;
    requestBaseline.current = requestMode ? latestRequestSnapshot.current : null;
    if (!requestMode) return;
    // Not filtered on `isTrusted`: the form's own controls dispatch nothing,
    // and a test's events are untrusted by construction.
    const touched = () => {
      requestTouched.current = true;
    };
    const kinds = ["keydown", "pointerdown", "input", "change"] as const;
    for (const kind of kinds) document.addEventListener(kind, touched, true);
    return () => {
      for (const kind of kinds) document.removeEventListener(kind, touched, true);
    };
  }, [requestMode]);
  useEffect(() => {
    if (!requestMode || requestBaseline.current === null) return;
    if (!requestTouched.current) {
      // Nobody has acted yet: whatever the form holds is still the request.
      requestBaseline.current = requestSnapshot;
      return;
    }
    if (requestBaseline.current === requestSnapshot) return;
    const sent = requestSnapshot;
    const write = window.setTimeout(() => {
      edit.save(step, parkValues).then(
        () => {
          requestBaseline.current = sent;
          setRequestAutosaveFailed(false);
        },
        () => setRequestAutosaveFailed(true),
      );
    }, 600);
    return () => window.clearTimeout(write);
    // The write follows the VALUES; `edit.save` and `parkValues` are rebuilt
    // every render and listing them would write on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestMode, requestSnapshot]);

  // `DEF-SHL-10001` — the leave-page popup's *Save as draft*: the request's
  // own form on an undecided request, the park row everywhere else, and none
  // while the edit is still being read (writing then would guess the store).
  const leaveDraft: LeaveDraft | null =
    edit.mode === "pending"
      ? null
      : {
          onSave:
            edit.mode === "request"
              ? () =>
                  edit.save(step, parkValues).then(
                    () => ({ ok: true as const }),
                    () => ({ ok: false as const }),
                  )
              : park.saveDraft,
          savedMessage: t("leaveGuard.saved", { place: t("customers.accounts.tab.moveIns") }),
        };
  const autosaveNote =
    park.autosaveFailed || requestAutosaveFailed ? t("wizard.autosaveFailed") : null;

  const saveDraftExit = () => {
    if (edit.mode !== "request") {
      leave();
      return;
    }
    void saveRequestEdit().then((outcome) => {
      if (!outcome.ok) fireToast(outcome.reason);
    });
  };
  const exit: WizardExit = {
    // P2.17 — drawn in the page head instead of beside Park (see `MoveInShell`).
    onSaveAndExit: null,
    // P2.34 — an undecided request keeps ONE draft, its own, written by Save
    // (`PUT …/move-in-form`); a Park here would mint a second move-in.
    parkBlockedReason:
      edit.mode === "request" ? t("customers.moveIn.edit.parkRequest") : parkStoreBlockedReason(translate),
    parkOpen,
    onParkOpenChange: setParkOpen,
    onPark: park.onPark,
    dateFormat,
    // ⛔ CR §2 S9 (PO 2026-10-05, *"this is okay"*): the park-age sentence
    // *"Waiting 0 days — nothing is held or changed until you finish this"*
    // leaves this wizard. The frame draws it only from `parkedAt`.
    parkedAt: null,
  };
  // P2.17 / image 47 — a resumed draft is an EDIT of that move-in. Read once,
  // on resume (`onHydrate`); the wizard's own autosave never hydrates.
  const editing = edit.isEdit && (edit.mode === "request" || edit.mode === "move_in");
  const reference = editing ? (edit.reference ?? "") : editReference;
  const title =
    reference === null
      ? t("customers.moveIn.title")
      : reference === ""
        ? t("customers.moveIn.titleEditNoRef")
        : t("customers.moveIn.titleEdit", { reference });

  async function commit(): Promise<WizardCommitOutcome> {
    if (edit.mode === "request") {
      return saveRequestEdit();
    }
    try {
      const answered = await moveIn.mutateAsync();
      setResult(answered);
      fireToast(t("customers.moveIn.toast", { account: answered.account_no ?? "" }));
      return { ok: true };
    } catch (error) {
      // BR-SHL-020: the server's own message_key through the catalog — this is
      // where BR-CUS-017's "that unit already has an account", BR-CUS-056's
      // "the outgoing account owns that day" and BR-MET-040's "plan required at
      // activation" reach the user, with everything typed still on screen.
      const reason = apiErrorText(error, translate);
      // CR-181-BRC10 — a reopen refusal (*Pay the old balance first.*, too
      // old, another unit …) is the Customer step's to fix, so it lands THERE
      // with the footer kept (`refusedOnStep`, the DEF-MET-6110 posture).
      if (error instanceof ApiError && error.messageKey.startsWith("customers.moveIn.reopen.")) {
        const customerStep = MOVE_IN_STEPS.findIndex((one) => one.id === "customer") + 1;
        setReopenRefusal(reason);
        setStep({ step: customerStep, reached: customerStep });
        return { ok: false, reason, refusedOnStep: customerStep };
      }
      return { ok: false, reason };
    }
  }

  // P2.34 — an undecided request is not approved by this form, so its last
  // step SAVES the request rather than completing a move-in.
  const commitLabel =
    edit.mode === "request" ? t("customers.moveIn.saveChanges") : t("customers.moveIn.commit");

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("customers.accounts.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  // ⚠ **THE WHOLE-PAGE STATES BELONG TO THE ACCOUNT-SCOPED ROAD ONLY.** With an
  // account in the URL there is nothing else this page could be doing. On
  // `/move-ins/new` the same two facts are about one FIELD in a flow the clerk
  // is standing in, and replacing the wizard with a failure card would throw
  // away the unit picker that is the way out of the failure — so they render
  // inside step 1 instead.
  if (!standalone) {
    if (outgoingQuery.isPending) {
      return <LoadingSkeleton variant="card" />; // A18 §3
    }
    if (outgoingQuery.data === undefined) {
      if (isPermissionDenied(outgoingQuery.error)) {
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
          reason={apiErrorText(outgoingQuery.error, translate)}
          onRetry={() => void outgoingQuery.refetch()}
          onDownloadReport={() => undefined}
          onCancel={() => navigate(tenantPath(ACCOUNTS_ROUTE))}
        />
      );
    }
  }

  // Null ONLY on the standalone road before a unit resolves to a predecessor —
  // the guard above returns before this line whenever an account came from the
  // URL.
  const outgoing: AccountDetail | null = outgoingQuery.data ?? null;
  // `BR-TEN-042` — one tenant, one currency, and the outgoing account carries
  // it. READ off the row rather than guessed: `UnitPricingPanel.money`'s own
  // note is that inventing `USD` puts a currency on a screen the tenant never
  // chose (hard rule 2 · `DEF-1121`). `null` while the account is still
  // loading, or on a VACANT unit with no outgoing account at all — and then
  // the deposit step reads the TENANT's code through `useTenantCurrency()`
  // (`DEF-CUS-5114`, 2026-10-04), the same code under `BR-TEN-042`.
  const currency: string | null = outgoing?.currency ?? null;

  // The commit answered. The wizard is REPLACED rather than navigated away
  // from: the five warnings say what a move-in did NOT do, and a toast on the
  // way to the new account's page shows none of them.
  if (result !== null) {
    return (
      <MoveInCompleted
        result={result}
        t={translate}
        timeZone={timeZone}
        dateFormat={dateFormat}
        onStartAnother={props.onStartAnother}
      />
    );
  }

  // BR-CUS-056: the day after the outgoing account's move day, and the earliest
  // start the server will accept.
  const earliest = earliestMoveInDate(outgoing?.closed_at ?? null);
  // BR-CUS-017: while the outgoing account still holds the unit, the commit is
  // refused — said before it runs (the S18 step-3 precedent). A first occupant's
  // unit came from the VACANT list, and the server checks it again at save.
  // `DEF-CUS-10190` — on the standalone road the SERVER's row decides first:
  // only a `move_in` path is free. An occupied unit's older closed tenancy
  // would otherwise read as a predecessor and wave the move-in through to a
  // BR-CUS-017 refusal at the very last button.
  const pathFree = !standalone || (chosenRow !== null && chosenRow.id === unitId && chosenRow.path === "move_in");
  const unitFree = pathFree && (firstOccupant || (outgoing !== null && isClosedAccount(outgoing)));
  const dateProblem = moveInDateProblem(openedAt, earliest);

  /**
   * `DEF-CUS-10190` — *Start move-out* (or *Close out*, for a cut account).
   *
   * The move-in is kept as its own draft and the OLD occupant's move-out is
   * raised as a draft by the server, prefilled with the day before this
   * move-in (`POST /move-ins/handover`); the clerk lands in the move-out
   * wizard on it. Nothing is closed here — PO: *"the move-in won't close
   * their account by itself"*. A cut account goes to its close-out page,
   * which settles it at the cut (BR-CUS-430); no draft is written for that.
   */
  async function settleFirst(row: MoveInUnitRow): Promise<void> {
    setSettling(true);
    setSettleRefusal(null);
    try {
      let moveInParkId = parkIdRef.current;
      if (moveInParkId === null) {
        await park.saveDraft();
        moveInParkId = new URLSearchParams(window.location.search).get(PARKED_PARAM);
      }
      const answer = await startMoveInHandover(
        { unit_id: row.id, opened_at: openedAt === "" ? todayInZone(timeZone) : openedAt, move_in_park_id: moveInParkId },
        client,
      );
      const back = moveInParkId === null ? "" : `&${FROM_MOVE_IN_VALUE}=${encodeURIComponent(moveInParkId)}`;
      if (answer.path === "close_out_first") {
        navigate(tenantPath(`${accountCloseOutPath(answer.account_id)}?${back.slice(1)}`), {
          state: LEAVE_DELIBERATELY,
        });
        return;
      }
      navigate(
        tenantPath(`${MOVE_OUT_WIZARD_ROUTE}?${PARKED_PARAM}=${encodeURIComponent(answer.move_out_park_id ?? "")}`),
        { state: LEAVE_DELIBERATELY },
      );
    } catch (error) {
      setSettleRefusal(apiErrorText(error, translate));
    } finally {
      setSettling(false);
    }
  }

  /** The standalone road's step 1, or null on the account-scoped one. */
  const picker = !standalone ? null : (
    <MoveInUnitPick
      unitId={unitId}
      onUnitChange={setUnitId}
      options={[]}
      unitsLoading={false}
      unitsFailed={false}
      unitSearch={
        <MoveInUnitSearch
          term={unitTerm}
          onTermChange={(term) => {
            setUnitTerm(term);
            setUnitPage(1);
          }}
          page={unitPage}
          onPage={setUnitPage}
          search={unitSearch}
          chosen={chosenRow !== null && chosenRow.id === unitId ? chosenRow : null}
          onChoose={(row) => {
            setChosenRow(row);
            setSettleRefusal(null);
            setUnitId(row.id);
          }}
          onChange={() => {
            setChosenRow(null);
            setSettleRefusal(null);
            setUnitId("");
          }}
          onSettleFirst={(row) => void settleFirst(row)}
          settleBlockedReason={
            chosenRow?.path === "move_out_first" && openedAt === ""
              ? t("customers.moveIn.unitSearch.dateFirst")
              : null
          }
          settling={settling}
          settleRefusal={settleRefusal}
          t={translate}
        />
      }
      predecessor={predecessor}
      resolved={unitAccountsQuery.isSuccess}
      accountsFailedReason={
        unitAccountsQuery.isError
          ? apiErrorText(unitAccountsQuery.error, translate)
          : outgoingQuery.isError
            ? apiErrorText(outgoingQuery.error, translate)
            : null
      }
      t={translate}
    />
  );

  // ⚠ **THE RAIL KEEPS ALL SIX WHILE THE UNIT IS UNCHOSEN — BR-SHL-046.** The
  // step number is an INDEX (a Move-ins row reopens this wizard AT one), so a
  // step that vanished would misaddress every step after it. Each later step
  // says what it is waiting for and refuses to validate.
  if (outgoing === null && !firstOccupant) {
    const pending: WizardStep[] = MOVE_IN_STEPS.map((defn, index) => ({
      id: defn.id,
      label: t(defn.labelKey, { defaultValue: defn.en }),
      content:
        index === 0 && picker !== null ? (
          picker
        ) : (
          <PickFirstNote>
            {t("customers.moveIn.find.pickFirst", {
              defaultValue: "Choose the unit above first — the rest of the move-in is about it.",
            })}
          </PickFirstNote>
        ),
      validate: () => false,
    }));
    return (
      <MoveInShell
        backTo={{
          to: tenantPath(MOVE_INS_TAB_PATH),
          label: t("customers.accounts.tab.moveIns"),
        }}
        title={title}
        onSaveDraftExit={saveDraftExit}
        saveDraft={leaveDraft}
        autosaveNote={autosaveNote}
        commitLabel={commitLabel}
        writeBlockedReason={writeBlockedReason}
        nav={nav}
        onNavChange={setStep}
        steps={pending}
        onCommit={() =>
          Promise.resolve({
            ok: false,
            reason: t("customers.moveIn.find.pickFirst", {
              defaultValue: "Choose the unit above first — the rest of the move-in is about it.",
            }),
          })
        }
        exit={exit}
        t={translate}
      />
    );
  }

  // ══════════════════════════════════════════════════════════════════════════
  // CR-171-BRC10 P2.15 · FOUR STEPS, ONE FILE EACH
  // ══════════════════════════════════════════════════════════════════════════
  // Everything a step reads, in one object. The step files own what is drawn
  // and when Continue holds; this file owns the state, the park and the commit.
  const ctx: MoveInWizardContext = {
    t: translate,
    client,
    dateFormat,
    timeZone,
    standalone,
    picker,
    unitId,
    outgoing,
    pickedUnit,
    unitLabel,
    unitFree,
    firstOccupant,
    outgoingUnitId,
    serviceOffer,
    ticked,
    setChosenServices,
    offerLoading: unitOfferQuery.isPending && outgoingUnitId !== "",
    offerFailed: unitOfferQuery.isError,
    openedAt,
    setOpenedAt,
    earliest,
    dateProblem,
    readsDraft,
    setReadsDraft,
    fieldVisit,
    setFieldVisit,
    customer,
    setCustomer,
    serviceRequestId,
    serviceRequestNo: requestQuery.data?.header.request_no ?? null,
    identityFromRequest,
    requestIdentifierMasks: (() => {
      const identifier = requestQuery.data?.applicant.identifier;
      if (identifier === undefined) return undefined;
      return {
        ssn: identifier.ssn_present ? `•••-••-${identifier.ssn_last4 ?? ""}` : "",
        licence: identifier.drivers_licence_present ? `•••• ${identifier.drivers_licence_last4 ?? ""}` : "",
      };
    })(),
    preferences,
    setPreferences,
    deposit,
    setDeposit,
    discount,
    setDiscount,
    currency,
    tried,
    markTried: (id) => setTried((current) => (current[id] ? current : { ...current, [id]: true })),
    goToStep: (target) => setStep({ step: target, reached: target }),
    reopenRefusal,
    clearReopenRefusal: () => setReopenRefusal(null),
    own: { unit: unitOwn, customer: customerOwn, billing: billingOwn, review: reviewOwn },
  };
  // ⚠ **THE ORDER IS `MOVE_IN_STEPS`' AND THE ID IS READ FROM IT**, so the
  // rail, the list's STEP column and these bodies cannot disagree (BR-SHL-046).
  const bodies: Record<MoveInStepId, Pick<WizardStep, "content" | "validate">> = {
    unit: { content: <StepUnit ctx={ctx} />, validate: () => stepUnitVerdict(ctx) },
    customer: { content: <StepCustomer ctx={ctx} />, validate: () => stepCustomerVerdict(ctx) },
    billing: { content: <StepBilling ctx={ctx} />, validate: () => stepBillingVerdict(ctx) },
    review: { content: <StepReview ctx={ctx} /> },
  };
  const steps: WizardStep[] = MOVE_IN_STEPS.map((defn) => ({
    id: defn.id,
    label: t(defn.labelKey, { defaultValue: defn.en }),
    ...bodies[defn.id as MoveInStepId],
  }));

  return (
    <MoveInShell
      // ⚠ P2.17 — `/move-ins/new` goes back to the Move-ins list (image 30),
      // never to the PREVIOUS occupant's account it derived (CR §5.3 read
      // *"← Rosa Pemberton"*); only the account-scoped road returns there.
      backTo={
        !standalone && outgoing !== null
          ? { to: tenantPath(accountDetailPath(fromAccountId)), label: accountHeadline(outgoing, translate) }
          : { to: tenantPath(MOVE_INS_TAB_PATH), label: t("customers.accounts.tab.moveIns") }
      }
      writeBlockedReason={writeBlockedReason}
      title={title}
      onSaveDraftExit={saveDraftExit}
      saveDraft={leaveDraft}
      autosaveNote={autosaveNote}
      commitLabel={commitLabel}
      nav={nav}
      onNavChange={setStep}
      steps={steps}
      onCommit={
        writeBlockedReason === null
          ? commit
          : () => Promise.resolve({ ok: false, reason: writeBlockedReason })
      }
      exit={exit}
      t={translate}
    />
  );
}

export default MoveInWizard;

/**
 * THE PAGE AROUND THE RAIL — header, role refusal, frame — declared ONCE and
 * rendered by BOTH roads, so the unchosen-unit state cannot drift into a
 * second, differently-shaped page.
 *
 * ⚠ **REDRAWN FROM IMAGES 30 AND 47 (`CR-171-BRC10` P2.17, 2026-10-05).** The
 * head is the back link, the title — *New move-in*, or *Edit move-in · MVI-…*
 * on a resumed draft — and **Save draft & exit** at the right; then the
 * four-step rail (a done step shows a tick, image 45); then the step; then
 * **Park** at the left and Back · Continue at the right. Three things the
 * seven-step page drew are GONE because the drawing has none of them and
 * B14 rule 33 puts each at zero words: the kicker and the *Step n of 7 · …*
 * line (the rail already says both), the audit sentence (*"A move-in is
 * recorded in the audit log by the server…"*, ruled out by the PO, CR §2 S9)
 * and the park age (*"Waiting 0 days — nothing is held or changed until you
 * finish this"*, S9 — `parkedAt` is not handed to the frame). The rail count
 * still comes from `MOVE_IN_STEPS` (BR-SHL-046).
 *
 * ⚠ **SAVE DRAFT & EXIT IS THE PAGE'S, NOT THE FRAME'S.** The frame draws its
 * `Save & exit` beside Park at the bottom; the drawing puts it top right, so
 * the frame is given `onSaveAndExit: null` and the header carries the button
 * (`NewPlanForm`'s precedent). It writes nothing of its own — the autosave has
 * already kept the draft (`CR-122-BRC06`).
 */
function MoveInShell(props: {
  backTo: { to: string; label: string };
  title: string;
  onSaveDraftExit: () => void;
  /** `DEF-SHL-10001` — the leave-page popup's draft, or null. */
  saveDraft: LeaveDraft | null;
  /** `DEF-CUS-10002` — one short line when the last autosave failed. */
  autosaveNote: string | null;
  commitLabel: string;
  writeBlockedReason: string | null;
  nav: WizardNavState;
  onNavChange: (next: WizardNavState) => void;
  steps: WizardStep[];
  onCommit: () => Promise<WizardCommitOutcome>;
  exit: WizardExit;
  t: Translator;
}) {
  const { t } = props;
  return (
    <div className="flex flex-col gap-5" data-screen="move-in-wizard">
      <PageHeader
        backTo={props.backTo}
        title={props.title}
        secondaryActions={
          <Button onClick={props.onSaveDraftExit} data-move-in-save-draft="">
            {t("customers.moveIn.saveDraftExit")}
          </Button>
        }
      />

      {props.writeBlockedReason !== null && (
        <RefusalStrip role="alert">{props.writeBlockedReason}</RefusalStrip>
      )}

      {props.autosaveNote !== null && (
        <p className="m-0 text-sm text-danger-700" role="status" data-move-in-autosave="failed">
          {props.autosaveNote}
        </p>
      )}

      <WizardFrame
        steps={props.steps}
        nav={props.nav}
        onNavChange={props.onNavChange}
        doneMark="tick"
        commitLabel={props.commitLabel}
        commitFailedTitle={t("customers.moveIn.commitFailed")}
        onCommit={props.onCommit}
        onCommitted={() => undefined}
        exit={props.exit}
        saveDraft={props.saveDraft}
      />
    </div>
  );
}

// ── Steps ──────────────────────────────────────────────────────────────────
// One file per step since `CR-171-BRC10` P2.15: `moveInWizard/StepUnit.tsx`,
// `StepCustomer.tsx`, `StepBilling.tsx`, `StepReview.tsx`. Each reads this
// wizard through `MoveInWizardContext` (built in `MoveInWizard` above).

// ── The answer ─────────────────────────────────────────────────────────────
// `CR-171-BRC10` P2.16 — `moveInWizard/MoveInCompleted.tsx` (image 48). The
// old result panel (*Move-in complete.*, *What was written*, *What the server
// could not do*, *Open the new account*) is gone with its catalogue keys.

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-004@bbed56d (story+rules snapshot — EP-CUS-02 move-in story; co-packets US-CUS-005@bbed56d · US-CUS-007@bbed56d · customers 02-business-rules@f125a9c)
// generated: 2026-08-11 by story-coder (W2 customers FRONTEND lane 3 — S19, the screen `POST /accounts/{id}/move-in` shipped without) · AMENDED 2026-08-25 by the CR-030 W5 R1 lane (tasks 5.2/5.3/5.6 — step 3 mounts `UnitAssetsPanel` over `GET /units/{id}/assets`, step 4 mounts `UnitPricingPanel` over `GET /units/{id}/pricing`, step 5 gains the "what we'll send" panel; and E3's claim that `customers`/`customer_accounts` have no tables is CORRECTED — both were built 2026-08-11 and the refusal's true reason is US-CUS-003 step 1 never being built. This file adds NO className of its own, so it stays under G31 at ratchet 0 — every Tailwind utility this lane wrote lives in the two new components, exactly as the N2 move-out lane put its impact screen in `moveShared.tsx`)
// amended: 2026-08-26 by lane MOVEENTRY — **PO ruling** (same one as
//         `MoveOutWizard.tsx`). `/move-ins/new` mounts this wizard with nothing
//         in the path and step 1 asks for the UNIT — the PO's own sentence,
//         *"a move-in creates the next occupant of a particular account's
//         unit"* — deriving the outgoing account from it through
//         `moveShared.lastClosedAccountForUnit`, which mirrors
//         `apps/customers/selectors.last_closed_account_for_unit`. NO endpoint
//         is added: the two reads are `GET /units?f.occupancy=vacant` and
//         `GET /accounts?f.unit_id=`, both published. A vacant unit with NO
//         finished tenancy has no move-in road at all — `apps/customers/api.py`
//         says so — and step 1 states that and links to S18 rather than
//         inventing one. ⚠ NEW key `customers.moveIn.unit.hintPicked`, for the
//         same catalogue-beats-default reason; and `customers.moveIn.unit
//         .noPicker` is no longer drawn on the standalone road, where it would
//         be false. This file still adds NO className of its own (G31).
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [CR-030 W5 R1, 2026-08-25] tsc✔ · eslint --max-warnings 0 on the four lane files✔ · vitest MoveInWizard.test.tsx 35 passed / 4 todo (39)✔ — 21 passed / 4 todo was the pre-lane count, so this lane adds 14 and drops none; full suite 2408 passed / 1 skipped / 187 todo across 139 files, 2 FAILED and NEITHER IS THIS LANE'S (`ServiceRequestDocumentSettingsPage.test.tsx`, W4's file, asserts `toContain` on copy holding `"` which `renderToStaticMarkup` escapes to `&quot;` — pre-existing, REPORTED). run_gates 24 PASS / 18 FAIL / 0 SKIP, and TWO of the FAILs are this lane's, both expected and both needing a file this lane does not own: G27 i18n-keys names 29 new keys no catalogue defines yet (handed over as `newkeys-R1.json`; every call site carries a `defaultValue` so nothing renders a raw key meanwhile, which is why G18 does NOT name them), and G31 declared-classes rises 0→15 because the two NEW components are written in Tailwind utilities per B14 rule 21 and `src/styles/route-b-migrated.txt` — not this lane's file — has no line for them yet. ⚠ All 32 utilities were compiled through the REAL Tailwind compiler against `src/styles/tailwind.css` (the stricter question `routeBUtilities.test.ts` will ask once the ledger lists them): 32/32 generate a rule, `normal-case` included, which was the only token not already attested in a migrated file. The other 16 FAILs (G1/G2/G3/G7/G8/G10/G11/G12/G15/G18/G25/G26/G28/G32/G33/G41) are pre-existing and untouched. G13 unwired-props✔ (188 components) · G38 stated-absences✔ (93 notes, 21 tracked, 72 untracked — EXACTLY the baseline: all three new notes cite a real id) · G40 unmounted-components✔ (1, at baseline) · G35 version-lockstep✔ 2.45.1. ORIGINAL 2026-08-11 RUN: tsc✔ · eslint --max-warnings 0✔ · vitest 702 passed / 168 todo across 51 files✔ (670 passed / 160 todo across 49 files was the pre-lane baseline — this lane adds 32 passing + 8 todo and dropped nothing) · vite build✔ · run_gates 12 PASS · 2 FAIL · 1 SKIP — and the two FAILs ARE NOT THIS LANE'S, stated rather than rounded up (hard-won law 1): G7 names six 06-backend files (db/rls_ledger_w5.sql, db/rls_notifications_w3.sql, ledger 0002_rls_w5_and_immutability.py, notifications 0002_rls_w3_outbound_queue.py …) with no human-review-ledger row, and G10 names US-BIL-023/024 · US-NOT-002/015 · US-PAY-014 with no backend TC test. All eleven belong to the W3/W5 billing·notifications·ledger lanes landing in 06-backend during this session; this lane touched no backend file. The FRONTEND half of G10 is clean (0 of the frontend-cited stories miss a test, US-CUS-004/005 included), and G13 unwired-props, G14 prototype-conformance and G15 i18n-parity (5 locales × 2466 keys, identical sets) all PASS. The pre-lane baseline for this session was 14 PASS · 0 FAIL · 1 SKIP
// exceptions: E3 [2026-08-25, CR-030 W5 · R1 · task 5.6] the step-5 "what we'll send" panel lists TWO rows and no more, because two is all this repo declares for a move-in: `notifications/catalogs.email_welcome` (whose own `used_by` reads "Not in use yet — a move-in does not send this") and BR-NOT-004 ② ("Service agreement (signed at move-in/new connection)"). BR-NOT-004 ③ the deposit agreement is EXCLUDED because this move-in records no deposit at all (BR-CUS-023), and ④ the autopay authorisation because nothing ties that NACHA document to a move-in — listing either would be a guess. NO ROW CARRIES A SEND STATUS (BR-NOT-013 / B18 §13 row 3 / W7 task 7.10), and the panel says plainly that no provider is connected on any channel
// exceptions: E3 [2026-08-25, R1] AN OPEN QUESTION IS OWED AND THIS LANE DID NOT MINT IT: *"which notices does completing a move-in produce, and on which channels?"* has no OQ row and `12-governance/` is not this lane's to write. The absence note therefore tracks DEF-266 (nothing a person can click delivers a message in this product) — the row whose closure must send somebody back to re-read this sentence. When the send-list question is minted, the note takes that id instead. REPORTED
// exceptions: E4 [2026-08-25, R1 · task 5.2] step 3's meter list is REPLACED by `UnitAssetsPanel`, not joined by it. `AccountDetail.meters` is the OUTGOING account's refs — an asset_no and a qualifier — so it could show neither the sub-meters, nor the behind-the-meter devices, nor where any register stood. Two lists of "the meters at this unit" on one step would be two answers to one question, and the shorter one omits equipment. The endpoint is `AnyTenantRole`, so no role loses information it had
// exceptions: E4 [2026-08-24, CR-030 W5 · N2] `Save & exit` and `Park` arrive from the SHARED frame (BR-SHL-047, task 5.1); `Park` renders DISABLED carrying its reason, and the reason is the missing STORE — `waiting_on`/`park_note`/`parked_at` are columns on `service_requests` alone and a move-in in progress is not a row · E4 the five steps derive from `moveShared.MOVE_IN_STEPS` so the Move-ins tab and this rail read ONE list (BR-SHL-046's durable half)
// exceptions: E3 there is NO unit picker: 11b §S19 defines one account-scoped move-in row, so the unit comes from the OUTGOING account in the URL and `unit_id` is a REFUSED field — the prototype's searchable vacant-unit table would be a second, disagreeing source of truth for which room the tenant enters · E3 no returning-customer search and no "Use" button (BR-CUS-054/019): `customer`/`customer_id` are refused and this move-in writes a fresh contact row; the server warns `customer_not_linked` and the step says the same before the commit. ⚠ CORRECTED 2026-08-25 (CR-030 W5 R1) — this line read "`customers` and `customer_accounts` have no tables" and that was FALSE: both were built 2026-08-11 by the US-CUS-019 lane (`apps/customers/models.Customer` db_table="customers", `models.CustomerAccount` db_table="customer_accounts"). The refusal is UNCHANGED and is not this lane's to change; its true reason is the one `services.REFUSED_FIELDS` has carried since the same day — "linking a customer at create is US-CUS-003 step 1, not built", i.e. S18 step 1's advisory duplicate check and "Use existing customer" were never built, so no linking path exists to call. FOUR user-visible sentences elsewhere still carry the old false reason and are REPORTED, not edited (services.MOVE_IN_UNAVAILABLE `customer_not_linked` + `deposit_carry_forward_unavailable`; en.json `customers.moveIn.customer.noSearch` + `customers.moveIn.carryWhy`) · E3 no "Bill from" selector (BR-CUS-022 — the proration RULE is confirmed, the option set is PROPOSED and has no column, so `bill_from` is refused) · E3 no initial-read control and no prior-final figure (BR-CUS-021 — `initial_reads` is refused; reads commit through metering's append-only service). The unit's meters are LISTED so the unread registers are visible · E3 no plan select (BR-CUS-029 + PO 2026-08-11: the plan lives ONCE on the unit and the account derives it, so there is nothing here to write); BR-MET-044's "the unit keeps its last plan" is stated as the fact it is, not mimed as a pre-selected option · E3 no deposit radios (BR-CUS-023/024): the amount is a lookup from the unbuilt plan deposit schedule and carry-forward rides the `customer_accounts` linkage, which does not exist — so "Carry $150 forward from A-11208" cannot be offered and the server warns `deposit_carry_forward_unavailable` · E3 no paperless toggle (BR-CUS-028 — PROPOSED-SCHEMA column, never built); autopay IS collected and IS capture-only (BR-CUS-059) · E4 BR-CUS-056 is enforced ahead of the server: the earliest legal start is computed from the outgoing account's `closed_at`, pre-filled through the shared date control's proposal mechanism, and an earlier date is named inline — the server refuses it too, and its refusal is what actually holds · E4 the review step shows the account number as allocated AT SAVE (BR-TEN-035) instead of the prototype's pre-printed "A-12049" · E4 the commit's ANSWER replaces the wizard rather than routing to the new account, so all five server warnings are read before the user leaves · E4 the prototype's page-head "Cancel" button is the shared header's BACK LINK (US-SHL-020/BR-SHL-044): one way out, drawn by the component, pointing at the account this flow acts on rather than at a generic list · E4 `CustomerForm`/`PreferencesForm` and their empty constructors are imported from S18 rather than re-declared: the two wizards write the SAME contact and preference columns, and a second copy would drift
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
