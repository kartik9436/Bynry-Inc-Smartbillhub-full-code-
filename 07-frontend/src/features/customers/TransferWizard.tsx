// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W7 — **`TRF-02`, THE TRANSFER WIZARD**, all five steps as
//           drawn 2026-08-25 (B18 §5.7.7 `TRF-02.1`…`TRF-02.5`). The list half
//           of this id shipped the same day (`TransfersTab.tsx`, US-CUS-027);
//           EP-CUS-08's Scope puts the wizard explicitly OUT, so this screen
//           arrives with its story written alongside it — US-CUS-029,
//           `04-docs/05-modules/03-customers/06-epics/EP-CUS-10-transfer-disconnect-wizards.md`
//           (hard-won law 8: every screen needs a story).
// Rules:    BR-CUS-085 (**the STAYS-WITH-YOU sentence this screen renders** —
//           *"nothing is refunded and re-collected"*. ⚠ It binds the
//           PROHIBITION ONLY, not the deposit POSITION moving; written into
//           the register 2026-08-25 by DEF-711, which is why the block at 1a
//           below no longer applies) · BR-CUS-023 (the deposit is a LOOKUP
//           and `deposit_on_file` is a
//           refused input, so *"no refund and re-collection"* holds BY
//           CONSTRUCTION on the incoming account) · BR-CUS-024 (deposit
//           carry-forward — mechanics PROPOSED, which is why the POSITION does
//           not move) · BR-CUS-017 (only a
//           VACANT or RESERVED unit may be moved into) · BR-CUS-030 (the
//           closure is conditional on the final bill settling, not on the date) ·
//           BR-CUS-057 (deposit interest — CONFIRMED as a rule, its engine
//           UNBUILT, which is why a deposit line may carry no figure at all) ·
//           BR-CUS-102 (*"Those are sample only from Prototype; you calcualte
//           correctly"* — r10's DATA loses authority, its layout/copy/rules do
//           not) · BR-SHL-018/019 (rail semantics, ONE transactional commit) ·
//           BR-SHL-025 (a control that cannot act is DISABLED WITH ITS REASON) ·
//           BR-SHL-046 (one declared step list) · BR-SHL-047 (every wizard
//           parks) · B14 rules 10, 11, 18, 21
// Questions: ⛔ OQ-365 (does a transfer's deposit and arrears move gross, or
//           does the close settle first? Four signed rules meet on a transfer
//           and all four were written about a customer who is LEAVING) — step 4
//           states both positions and elects, and moves nothing.
// Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.7.7
// Tests:    07-frontend/src/features/customers/TransferWizard.test.tsx
// Impacts:  ⛔ `apps/customers/api.py` mounts NO transfer write endpoint —
//           REPORTED with the exact functions (see transferDisconnectEndpoints).
//           ⚠ `TransfersTab.tsx`'s empty-state CTA was disabled *"the transfer
//           wizard is not built yet"*; one line now points it here.
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHAT THIS SCREEN IS FOR, IN ITS OWN DRAWN WORDS
// ══════════════════════════════════════════════════════════════════════════
// `TRF-02`'s H1 is *"Same customer, moving to another of your addresses."* and
// its sub is *"Five steps · one job, not two. The deposit moves with them."*
// Step 1's badge states the mechanism: **STAYS WITH YOU** — *"This customer is
// not leaving. Their deposit, their discounts and their history move with them
// — nothing is refunded and re-collected."* It is the sentence the whole wizard
// exists to make true, and it is `BR-CUS-085` — see the Trace block above.
//
// ══════════════════════════════════════════════════════════════════════════
// 1a · ✅ RESOLVED 2026-08-25 (DEF-711) — `BR-CUS-085` IS NOW A REGISTERED RULE
//        AND CARRIES THIS SENTENCE. THE HISTORY IS KEPT BECAUSE THE FIX WAS AN
//        ID ALLOCATION, NOT A CODE CHANGE, AND NOTHING ON SCREEN MOVED.
// ══════════════════════════════════════════════════════════════════════════
// ~~§5.7.7 writes *"That is `BR-CUS-085`'s reason stated to a clerk"*, and
// `04-docs/05-modules/03-customers/02-business-rules.md` runs **083 → 086**:
// there is no such row. Worse, **B18 proposes the SAME NUMBER elsewhere for a
// different statement** — its NEW-rules table reads *"a parked wizard never
// holds money — a deposit taken is a payment row"*. One id, two claims, neither
// registered.~~
//
// **PO ruling 2026-08-25: `BR-CUS-085` is the DEPOSIT rule — this sentence — and
// the parked-wizard statement took the new number `BR-CUS-108`.** The reasoning
// recorded with the ruling is why it went this way round: *085 was already cited
// in shipped code paths for the deposit meaning, so moving it would mean
// re-pointing live citations to settle a proposal that had none.* Both rules are
// in `02-business-rules.md`, CONFIRMED, dated 2026-08-25.
//
// **This file's behaviour is UNCHANGED by that ruling.** It still renders the
// SENTENCE, which is drawn copy and binds as drawn copy (PO 2026-08-16: r10 is
// the reference for layout, copy, flows, states and the rules written on the
// screens); the test asserts the COPY, not the id. What changed is that the
// Trace block may now cite `BR-CUS-085` and have it resolve.
//
// ⛔ **AND THE REGISTERED RULE BINDS THE PROHIBITION, NOT A MOVEMENT.** It says
// no refund is raised and no re-collection is asked for — which BR-CUS-023
// already guarantees BY CONSTRUCTION here, `deposit_on_file` being a REFUSED
// input field on the incoming account whatever a clerk elects. It does **not**
// say the deposit POSITION moves: that is BR-CUS-024 (mechanics PROPOSED) and
// ⛔ `OQ-365` (OPEN, non-blocking), so section 2 below stands word for word.
// ⚠ The badge's *"discounts and their history"* are drawn copy with no mechanism
// anywhere — nothing carries either across a transfer, and this file invents
// neither.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · ⛔ EVERY MONEY FIGURE THE DRAWING SHOWS IS ABSENT HERE, AND SAYING SO
//      IS THE FEATURE
// ══════════════════════════════════════════════════════════════════════════
// §5.7.7 draws `$150.00 principal + $3.50 interest = $153.50 moving`, and the
// arithmetic foots four ways across three steps. **None of it can be served.**
//
//   · The principal and the arrear ARE readable — `GET /accounts/{id}` is
//     mounted and carries `deposit_on_file`, `balance` (the LEDGER's figure
//     since DEF-127, not the cache) and `currency`. Those are rendered as the
//     server sent them.
//   · **The INTEREST is not, and therefore neither is the carried total.**
//     BR-CUS-057 is CONFIRMED and its accrual is published by nothing
//     (US-CUS-023 §7). `transfers.MoneyStatement.deposit_carried` returns
//     `None` rather than falling back to the principal, and ❄️ **WE-7 / GT-23**
//     is the frozen pair that says why: the tempting zero *"does not merely
//     lose precision, it serves the principal AS the carried amount and keeps
//     $3.50 of the customer's money"*. On the drawing's own account that is
//     $150.00 shown where $153.50 is held — correct-looking and wrong.
//   · So step 4 renders the principal and the arrear, and renders the CARRIED
//     TOTAL as an absence with that reason. It never adds the two numbers it
//     has.
//
// ⚠ **AND NO SERVER SERVES THE STATEMENT AT ALL YET** — `money_statement` is
// keyed by a transfer id and there is no transfer row before the commit. Both
// reasons are on the screen; neither is a placeholder for the other.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · WHAT IS DRAWN AND IS NOT BUILT, EACH WITH ITS REASON
// ══════════════════════════════════════════════════════════════════════════
//   * **Step 1's panels (b) relationships, (c) same customer, (d) premise.**
//     `GET /accounts/{id}` carries the CUSTOMER and its sibling accounts, so
//     panel (c) is real. Sub-meter links and sub-accounts (b) and the premise's
//     owner/occupancy (d) are published by no endpoint this screen may call;
//     both render their absence. ⚠ Panel (d)'s drawn *"free text, not an
//     account"* is DEF-650 drawn on the screen and agrees with BR-MET-113 —
//     recorded, not built here.
//   * **Steps 2 and 3's reads.** `transfers.py` writes no meter read — its own
//     docstring — and `TransferCommitPlan` carries none. The register tables are
//     drawn as what will be captured, with the capture disabled and its reason,
//     rather than as inputs that would be silently discarded.
//   * **`Split into two`** (the frame's third action). Splitting a transfer into
//     a move-out plus a move-in is the exact opposite of BR-CUS-086 (*"a
//     transfer is ONE JOB and appears in NEITHER Move-ins nor Move-outs"*), and
//     nothing in `transfers.py` can decompose a row. Drawn DISABLED with that
//     sentence.
//   * **The three carry-across warnings.** *"Senior rate must be re-checked —
//     eligibility depends on the premises, not the person"* and *"the new unit
//     carries its own plan … by coincidence, not by carry-over"* are RULES B18
//     records with no id and no code (`discounts.py` has no re-check on
//     transfer). Rendered as the warnings they are drawn as; REPORTED as owed.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccountDetail, uploadAccountDocument } from "@/api/endpoints";
import type { AccountContact, AccountDetail, AccountDocumentType } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";
import { emptyUsAddress, usZipIsValid } from "@/components/UsAddressFields";
import type { UsAddressValue } from "@/components/UsAddressFields";
import { formatDate } from "@/components/DateCell";
import { CheckboxField, DatePickerField } from "@/components/FormModal";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { PlainTable, RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";
import { WizardFrame } from "@/components/WizardFrame";
import type { LeaveDraft } from "@/components/LeaveGuard";
import type { WizardCommitOutcome, WizardExit, WizardNavState, WizardStep } from "@/components/WizardFrame";
import type { RegionalDateFormat } from "@/components/DateCell";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  ACCOUNT_SEARCH_IDLE,
  MIN_SEARCH_CHARS,
  accountFinderLabel,
  isAccountId,
  useAccountSearch,
} from "./accountFinder";
import type { AccountSearchState } from "./accountFinder";
import { useMutation as useSearchMutation } from "@tanstack/react-query";
import { searchCustomerId } from "./customerEndpoints";
import type { CustomerSearchQuery, CustomerSearchResult, CustomerSearchRow } from "./customerEndpoints";
import { CoOwnerCards, coOwnerFormatProblem, coOwnerProblem, coOwnersPayload } from "./CoOwnerCards";
import type { CoOwnerDraft } from "./CoOwnerCards";
import {
  CustomerIdentityPanel,
  CustomerWhoPanel,
  customerFormatProblem,
  emptyCustomerWhoExtras,
} from "./customerForm/CustomerWhoPanel";
import type { CustomerWhoExtras } from "./customerForm/CustomerWhoPanel";
import { MailingAddressBlock } from "./customerForm/MailingAddressBlock";
import { CustomerMatchPanel } from "./customerMatch/CustomerMatchPanel";
import { MoveInDocumentsTable, documentsPayload } from "./MoveInDocumentsTable";
import type { MoveInDocDraft } from "./MoveInDocumentsTable";
import { DiscountsSection, PreferencesSection, TaxSection } from "./moveInWizard/BillingExtras";
import { billingPayload, billingProblems, emptyStepBillingOwn } from "./moveInWizard/billingModel";
import type { StepBillingOwn } from "./moveInWizard/billingModel";
import { getMoveInPricing, moveInMoneyKeys } from "@/api/moveInMoneyEndpoints";
import { emptyPreferencesForm } from "./NewAccountWizard";
import type { PreferencesForm } from "./NewAccountWizard";
import type { DraftDocument } from "./newConnectDraft";
import { getUnitPricing, unitPricingQueryKey } from "./UnitPricingPanel";
import { flowProgress, parkStoreBlockedReason, stepFromParam } from "./moveShared";
import { Dash, accountCategoryName, accountHeadline, useAccountCategories } from "./customersShared";
// CR-035 — the park store, its resume handle and the list a park lands on.
import { parkedHomePath, hydrateForm, parkedString, useWizardPark } from "./wizardPark";
import {
  applicantCapturePayload,
  clearedForKind,
  emptyApplicantCapture,
} from "./applicantCapture";
import type { ApplicantCaptureValue } from "./applicantCapture";
import { AbsentValue } from "./newConnectShared";
import type { Translator } from "./newConnectShared";
import {
  commitTransfer,
  previewTransferAccount,
  previewTransferBuyer,
} from "./transferDisconnectEndpoints";
import type {
  BuyerPreview,
  TransferAccountPreview,
  TransferRefusal,
} from "./transferDisconnectEndpoints";
import {
  FieldVisitOrders,
  emptyFieldVisit,
  fieldVisitPayload,
  fieldVisitProblem,
  hydrateFieldVisit,
} from "@/features/work/FieldVisitOrders";
import type { FieldVisitValue, RaisedWorkOrderRef } from "@/features/work/FieldVisitOrders";
import type { TransferCommitPlan, TransferRecord } from "./transferDisconnectEndpoints";
import { StepIntro, TRANSFERS_TAB_PATH, TRANSFER_STEPS } from "./transferDisconnectShared";
// ⚠ **REUSED, NOT RE-DECLARED — `DEF-CUS-5075`.** The buyer's block is the same
// customer form `NewAccountWizard` and `MoveInWizard` already collect, and
// `accountIdentityShortfall` is `BR-CUS-1023`'s client half. A second identity
// form would be a second place a government identifier is typed
// (`BR-CUS-1020`), with its own eleven catalogue entries free to drift from
// these, and the PO's standing instruction of 2026-09-12 is explicit: *build
// from the actual code, and do not create duplicate code*.
import {
  CUSTOMER_KIND_COMPANY,
  CUSTOMER_KIND_PERSON,
  accountIdentityShortfall,
  emptyCustomerForm,
} from "./NewAccountWizard";
import type { CustomerForm } from "./NewAccountWizard";

/** A1 allocates no id for this screen. B18 §3 maps S89 as *"Transfers tab —
 *  list **+ 5-step wizard**"*, so the wizard is the second half of S89 rather
 *  than a new number; the r10 id is `TRF-02`. The ALLOCATION is the PO's (D1)
 *  and is not taken here — this is the DOM handle a gate and an e2e assertion
 *  need. */
export const TRANSFER_WIZARD_SCREEN = "S89";

const STEP_PARAM = "step";
const PARK_PARAM = "park";

// ══════════════════════════════════════════════════════════════════════════
// THE DRAFT — held in this component and written by ONE commit
// ══════════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════════
// ⚠ **A TRANSFER IS A SALE. REDESIGNED 2026-09-12 — `DEF-CUS-5075`.**
// ══════════════════════════════════════════════════════════════════════════
// PO ruling of 2026-09-01, verbatim: *"dont create new account - we reassing
// that account - bascailly I have sold my property - so account get transfer to
// new person or business; if I move to new location then it is new Service
// request"*.
//
// So the account, its number, its unit, its meters, its plan, its billing cycle
// and its whole ledger **stay exactly where they are**, and the CUSTOMER
// changes. The server was rewritten to that shape the same day
// (`transfers.reassign_account`, five staged writes in one transaction) and this
// screen was not, for eleven days:
//
//     what the screen sent          what the door reads
//     from_account_id          ✓    from_account_id
//     to_unit_id               ✗    customer{display_name · kind · identity}
//     out_date, in_date        ✗    sold_on
//     deposit_carry            ✗    field_visit
//     arrears_follow           ✗
//
// Five of six keys ignored, three of four never sent, and the commit answered
// `422 customers.transfer.buyer_required` at the second of five writes. **The
// screen was not merely out of date — it could not complete its job at all.**
//
// ⚠ **AND THE BLUEPRINT'S PROSE DESCRIBES THE OLD MODEL WHILE ITS OWN DRAWING
// DESCRIBES THE NEW ONE** (`DEF-CUS-5078`). p118's *"Onto the Transfers tab,
// with two dates rather than one"* is stale; the frame three inches below it
// states *"One date, because there is only one. This used to be a flow with an
// out date and an in date, because it closed one account and opened another."*
// **The frame is newer and the frame wins** (the ruling of 2026-09-10). Nothing
// below is built from that prose.
//
// ⚠ **WHAT IS DELIBERATELY GONE, so nobody puts it back:**
//   · `toUnitId` — **the unit does not change.** A customer moving to another
//     address is a NEW SERVICE REQUEST, which the ruling says in as many words.
//   · `outDate` / `inDate` — one day, not two. A sale closes nothing and opens
//     nothing, so there is no gap and nothing to order.
//   · `depositCarry` / `arrearsFollow` — `OQ-1252` was answered inside the hour
//     on 2026-09-01: *"money follow property - new owner boutght everything
//     property + debt also"*. A box for a clerk to clear would be a control
//     that can reverse a PO ruling, and `acknowledge_money` now reads no key.
//   · the final read — a sale closes no account, so there is no closing figure
//     to capture. The meter keeps running on one unbroken account.
export interface TransferDraft {
  /** Step 1. The account being SOLD — `TRF-02.1`'s search, which since DEF-732
   *  really is one: the box takes the NUMBER every list shows
   *  (`AC-2026-00025`), the customer's name or the service address through the
   *  published `GET /accounts?q=` (BR-CUS-053), and this field holds the id the
   *  clerk's CHOICE resolved to. A pasted account id still resolves directly. */
  fromAccountId: string;
  /**
   * Step 2. **Who is buying it.** The drawn block: a kind, a full name, and one
   * identifier belonging to that kind — a person by Social Security number,
   * driving licence or phone; a company by its Tax ID.
   *
   * ⚠ **`CustomerForm` IS REUSED FROM `NewAccountWizard`, NOT RE-DECLARED.** It
   * already carries exactly these fields, its eleven catalogues already hold
   * their labels, and `accountIdentityShortfall` already implements
   * `BR-CUS-1023` — the same rule the server's `_validated_buyer` mirrors. A
   * second identity form in this product would be a second place a government
   * identifier is typed, which is what `BR-CUS-1020` exists to refuse, and the
   * PO's standing instruction of 2026-09-12 refuses generally: *build from the
   * actual code, and do not create duplicate code*.
   */
  buyer: CustomerForm;
  /**
   * Step 2, the rest of it — **`BR-CUS-1081`, PO ruling 2026-09-20.** Verbatim:
   * *"step 2 dont allow to take kYC documents - DOB, all detaisl we need to
   * create account - Similar to Move in request"*.
   *
   * ⚠ **A SECOND OBJECT AND NOT A WIDER `CustomerForm`, DELIBERATELY.**
   * `CustomerForm` is `NewAccountWizard`'s and is shared by three wizards;
   * widening it would move every construction site in this product for two
   * fields only a capture form asks for. `buyer` above keeps the identity the
   * three of them share — and `BR-CUS-1023` therefore keeps ONE implementation,
   * `accountIdentityShortfall`, which is the thing that must not fork.
   *
   * ⚠ **THE OVERLAP IS MAPPED IN ONE PLACE AND NOWHERE ELSE**
   * (`buyerCaptureValue` / `patchBuyerCapture` below). Two objects holding a
   * phone number is how two screens come to disagree about it, so nothing else
   * in this file reads either half directly.
   */
  buyerCapture: ApplicantCaptureValue;
  /**
   * **The buyer's MAILING address — hard rule 8's first named exception and the
   * only lawful second address in the product** (`BR-CUS-1081` §3, PO
   * 2026-09-20: *"please add it at buyer"*). `customers.addresses`
   * `kind='mailing'`, written through `services.update_account_mailing_address`,
   * the door that already exists. No address column is added anywhere.
   *
   * ⊕ **2026-09-23 — `DEF-CUS-6388` (the word) and `DEF-CUS-6393` (T3).** The
   * block is *Mailing address* with a *Same as service address* tick, the one
   * word the PO ruled for every screen (*"we should use same vocablory in
   * everywhere"*). **Ticked is the default and it is a real answer:** no
   * mailing row, so the bill goes by post to the service address — and the
   * SELLER's mailing row is removed at the sale rather than kept (T3: *"otherwise
   * bills go by post to the service address"*).
   */
  mailingSameAsService: boolean;
  buyerMailing: BuyerMailingForm;
  /**
   * **T1 — the customer the clerk FOUND and LINKED** (`DEF-CUS-6386`). Set, it
   * IS the buyer: the commit names it by `customer_id` and no identifier is
   * re-typed. Null while nobody is linked — **which is the ORDINARY state of
   * this step and not a gap to be filled** (`DEF-CUS-6549`).
   *
   * ⛔ **`buyerCreating` IS GONE AND MUST NOT COME BACK.** It was T1's third
   * branch — a flag the *Create customer* button set, which the whole capture
   * then rendered behind — and it made the customer search a PRECONDITION for
   * typing a buyer at all. PO ruling 2026-09-24 (`DEF-CUS-6549`) puts the form
   * first and the search beside it, so there is no state in which the fields
   * are hidden and nothing left for a flag to say.
   */
  buyerCustomer: CustomerSearchRow | null;
  /**
   * **The buyer's documents — `DEF-CUS-6390`.** PO: *"you have to take buyer
   * documents - as we have taken document in move in or new connect or new
   * request"*. Held on the draft (a `File` cannot ride a JSON commit) and filed
   * against the account after the sale, through `POST /accounts/{id}/documents`
   * — New Connect's `fileOwnerDocuments` shape. ⚠ Never parked: a `File` does
   * not survive JSON, so `useWizardPark` is handed the draft without them.
   */
  buyerDocuments: DraftDocument[];
  /**
   * ⊕ **`DEF-CUS-10255` — THE BUYER STEP IS MOVE-IN'S CUSTOMER FORM** (PO
   * 2026-10-18, image `07-transfer.png`): *Contact by* and a company's facts
   * (`CustomerWhoExtras`), the co-buyer full cards, the documents table (staged
   * on the server exactly as a move-in's are), and Move-in's Tax, Discounts and
   * Preferences panels. **The seller's exemption and discounts are NOT copied:**
   * these open empty and hold the BUYER's.
   */
  buyerExtras: CustomerWhoExtras;
  coBuyersOn: boolean;
  coBuyers: CoOwnerDraft[];
  buyerDocRows: MoveInDocDraft[];
  buyerBilling: StepBillingOwn;
  buyerPrefs: PreferencesForm;
  /** Step 3. **The day the account changes hands — one date, not two.** */
  soldOn: string;
  /** Step 4. *"I have shown this to the buyer"*, drawn as a `Before you
   *  continue` checkbox. It records that a clerk PUT THE FIGURE IN FRONT of the
   *  buyer, not that the buyer agreed with it — the drawing says so itself. */
  shownToBuyer: boolean;
  /** Step 2's field visit — ⊕ **THE ONE SHARED TABLE since 2026-09-23
   *  (`DEF-CUS-6392`, item 12, PO: *"this is correct"*).** The rows a clerk
   *  added (job type · priority · due · assigned to · note) or *No visit
   *  needed*, riding the ONE plan because this door is one transaction and
   *  there is no transfer row for a second call to name. It was a list of
   *  ticked template ids (`RaiseFieldWork`) until then. ⚠ It raises WORK; it
   *  captures no reading. */
  fieldVisit: FieldVisitValue;
}

/** The buyer's mailing address, as the kit's ONE US address block holds it
 *  (`components/UsAddressFields.tsx`, `DEF-CUS-6388` — PO: *"take USA Address
 *  specific fields"*). `line1` is required when the block is sent at all. */
export type BuyerMailingForm = UsAddressValue;

/**
 * **THE ONE PLACE THE TWO HALVES OF THE BUYER MEET.**
 *
 * `buyer` holds what the three wizards share (`CustomerForm`) and
 * `buyerCapture` holds what only a capture form asks for. The fields that
 * appear in BOTH — the kind and the identifiers — are the SHARED object's, and
 * this function is what hands them to the capture block. Nothing else reads
 * across, which is why they cannot drift.
 */
export function buyerCaptureValue(draft: TransferDraft): ApplicantCaptureValue {
  return {
    ...draft.buyerCapture,
    applicant_kind: draft.buyer.customer_kind,
    ssn: draft.buyer.ssn,
    drivers_licence: draft.buyer.driving_licence,
    tax_id: draft.buyer.tax_id,
    applicant_phone: draft.buyer.phone,
    applicant_email: draft.buyer.email,
    // ⊕ `DEF-CUS-10255` — the Who panel's date of birth and the Preferences
    // panel's language are the shared form's now; the co-buyers are full
    // cards (`buyer_account.co_owners`), so no contact-only co-applicant rides.
    date_of_birth: draft.buyer.dob,
    add_co_applicant: false,
    co_applicant_name: "",
    co_applicant_email: "",
    co_applicant_phone: "",
  };
}

/**
 * ⊕ **`DEF-CUS-10255` — THE BUYER'S OWN PANELS, AS THE COMMIT CARRIES THEM.**
 * The move-in's own builders (`coOwnersPayload`, `documentsPayload`,
 * `billingPayload`) so a co-buyer card or a certificate means one thing on
 * both screens. `undefined` when nothing was entered (the old commit).
 */
export function buyerAccountPayload(draft: TransferDraft): Record<string, unknown> | undefined {
  const out: Record<string, unknown> = {};
  const kind = draft.buyer.customer_kind === CUSTOMER_KIND_COMPANY ? "officer" : "co_owner";
  if (draft.coBuyersOn && draft.coBuyers.length > 0) {
    out.co_owners = coOwnersPayload(kind, draft.coBuyers);
  }
  const docs = documentsPayload(draft.buyerDocRows);
  if (docs.length > 0) out.documents = docs;
  const billing = billingPayload({ ...draft.buyerBilling, planRows: null });
  for (const key of ["tax_exemption", "discount_claims", "autopay_instrument_id"]) {
    if (billing[key] !== undefined) out[key] = billing[key];
  }
  if (draft.buyerBilling.prefsOn) {
    out.paperless = draft.buyerPrefs.paperless;
    out.sms_reminders = draft.buyerPrefs.sms_reminders;
    out.autopay = draft.buyerPrefs.autopay;
  }
  return Object.keys(out).length === 0 ? undefined : out;
}

/** The inverse: a patch from the capture block, split back over the two
 *  halves. Written beside its twin so a field added to one is impossible to
 *  forget in the other. */
export function patchBuyerCapture(
  draft: TransferDraft,
  next: Partial<ApplicantCaptureValue>,
): Partial<TransferDraft> {
  const buyer: Partial<CustomerForm> = {};
  if (next.ssn !== undefined) buyer.ssn = next.ssn;
  if (next.drivers_licence !== undefined) buyer.driving_licence = next.drivers_licence;
  if (next.tax_id !== undefined) buyer.tax_id = next.tax_id;
  if (next.applicant_phone !== undefined) buyer.phone = next.applicant_phone;
  if (next.applicant_email !== undefined) buyer.email = next.applicant_email;
  if (next.applicant_kind !== undefined) buyer.customer_kind = next.applicant_kind;
  // `date_of_birth` lives on `CustomerForm.dob` too, and the CAPTURE spelling
  // is canonical (`BR-CUS-1081` §7) — so both are written and the payload
  // reads the capture one.
  if (next.date_of_birth !== undefined) buyer.dob = next.date_of_birth;
  return {
    buyer: { ...draft.buyer, ...buyer },
    buyerCapture: { ...draft.buyerCapture, ...next },
  };
}

export function emptyTransferDraft(): TransferDraft {
  return {
    fromAccountId: "",
    // ⚠ **`customer_kind` ARRIVES EMPTY AND NOT `person` (`BR-CUS-1022`).**
    // `emptyCustomerForm` already gets this right and its own comment says why:
    // a pre-selected kind would judge a business by a date of birth it has not
    // got and file its Tax ID nowhere. Reused rather than restated.
    buyer: emptyCustomerForm(),
    buyerCapture: emptyApplicantCapture(),
    // ⚠ DEFAULTED TRUE, and it is a real answer: no mailing row, the bill goes
    // by post to the service address (T3). Unticked asks for the address.
    mailingSameAsService: true,
    buyerMailing: emptyUsAddress(),
    buyerCustomer: null,
    buyerDocuments: [],
    buyerExtras: emptyCustomerWhoExtras(),
    coBuyersOn: false,
    coBuyers: [],
    buyerDocRows: [],
    // The drawing opens Preferences ticked and Tax / Discounts unticked; the
    // plan's fees and payment are not this step's (a sale charges nothing).
    buyerBilling: { ...emptyStepBillingOwn(), prefsOn: true },
    buyerPrefs: emptyPreferencesForm(),
    soldOn: "",
    // ⚠ NOT defaulted true. It records a clerk's act — that the figure was put
    // in front of the buyer — and a product that ticked it for them would be
    // recording something nobody did.
    shownToBuyer: false,
    fieldVisit: emptyFieldVisit(),
  };
}

/**
 * What step 5 posts. Assembled in ONE place so what the screen shows and what
 * the payload sends cannot drift — which is exactly what `DEF-CUS-5075` was:
 * the drift was invisible because nothing compared the two sides.
 *
 * **Three keys, and every one of them is read by `transfer_commit`:**
 * `from_account_id` → `start_transfer` · `customer` → `set_new_customer` AND
 * `reassign_account` (sent once, validated twice, deliberately — see that
 * view's own docstring) · `sold_on` → `set_sale_date`. `acknowledge_money`
 * reads nothing, because the debt follows the property and there is nothing
 * left to elect.
 *
 * ⚠ **ONLY THE IDENTIFIERS THAT BELONG TO THE STATED KIND ARE SENT.** A
 * company's Social Security number is filed where the company matcher never
 * looks (`BR-CUS-1022`), and the server strips it anyway — but sending it would
 * put a person's government identifier on a wire for no purpose at all, which
 * is the wrong side of `BR-CUS-1020` even when it is harmless.
 */
export function transferPlanOf(draft: TransferDraft): TransferCommitPlan {
  const buyer = draft.buyer;
  const kind = buyer.customer_kind.trim();
  const identity: Record<string, string> = {};
  if (kind === CUSTOMER_KIND_COMPANY) {
    if (buyer.tax_id.trim() !== "") identity.tax_id = buyer.tax_id.trim();
  } else if (kind === CUSTOMER_KIND_PERSON) {
    if (buyer.ssn.trim() !== "") identity.ssn = buyer.ssn.trim();
    if (buyer.driving_licence.trim() !== "") {
      identity.driving_licence = buyer.driving_licence.trim();
    }
    if (buyer.phone.trim() !== "") identity.phone = buyer.phone.trim();
  }
  // ✅ **`BR-CUS-1081` §1 — THE CAPTURE VOCABULARY, SENT FLAT BESIDE
  // `identity{}`.** The contract is explicit that both spellings work and that
  // the capture ones are canonical: *"Identifiers may arrive flat (the capture
  // spelling) or nested under identity{} (what the shipped wizard sends). Both
  // work; on a clash the nested block wins."* So `identity{}` STAYS — removing
  // it would change what a shipped payload means for no gain — and the fields
  // the ruling ADDED ride flat, where `BUYER_CAPTURE_FIELDS` reads them.
  //
  // ⛔ **AN EMPTY STRING IS NOT SENT, EXCEPT FOR THE CO-APPLICANT.** A blank
  // optional field means *nothing was typed*, and sending `""` for it would
  // read as *erase what is on file* — which for a buyer is the seller's email
  // and phone (`BR-CUS-1081` §2, "Absent means"). The three co-applicant keys
  // are the deliberate exception and `applicantCapturePayload` says why.
  const capture = applicantCapturePayload(buyerCaptureValue(draft));
  const captured: Record<string, string> = {};
  for (const [key, value] of Object.entries(capture)) {
    if (value !== "" || key.startsWith("co_applicant_")) captured[key] = value;
  }
  // ⊕ **T1 — A LINKED CUSTOMER IS THE BUYER (`DEF-CUS-6386`).** The found
  // customer is named by `customer_id` and speaks for itself: its own name and
  // kind, and NO identifier (the server holds it encrypted and this screen is
  // only ever served the last four). The contact fields the clerk typed still
  // ride flat, because they are what the account's contact row becomes (T3).
  const linked = draft.buyerCustomer;
  return {
    from_account_id: draft.fromAccountId.trim(),
    customer: {
      display_name: linked !== null ? linked.display_name : buyer.full_name.trim(),
      kind: linked !== null ? linked.kind : kind,
      identity: linked !== null ? {} : identity,
      ...captured,
      ...(linked !== null ? { customer_id: linked.id } : {}),
      ...(buyer.email.trim() !== "" ? { email: buyer.email.trim() } : {}),
      // ⊕ `DEF-CUS-10255` — the Preferences panel's language (capture field).
      ...(draft.buyerBilling.prefsOn && draft.buyerPrefs.preferred_language !== ""
        ? { preferred_language: draft.buyerPrefs.preferred_language }
        : {}),
      // **HARD RULE 8's ONE NAMED EXCEPTION** — where the BILL goes, which for
      // a landlord is another building. Omitted when *Same as service address*
      // is ticked: no mailing row, so the bill goes by post to the service
      // address and the seller's row is removed at the sale (T3).
      ...(!draft.mailingSameAsService && draft.buyerMailing.line1.trim() !== ""
        ? {
            mailing_address: {
              line1: draft.buyerMailing.line1.trim(),
              // `line2` rides only when typed: the write door takes it from
              // the day its `ADDRESS_FIELDS` does (REQ-FIX's `customers` push).
              ...(draft.buyerMailing.line2.trim() !== ""
                ? { line2: draft.buyerMailing.line2.trim() }
                : {}),
              city: draft.buyerMailing.city.trim(),
              state: draft.buyerMailing.state.trim(),
              postal_code: draft.buyerMailing.postal_code.trim(),
            },
          }
        : {}),
    },
    sold_on: draft.soldOn,
    ...(buyerAccountPayload(draft) !== undefined ? { buyer_account: buyerAccountPayload(draft) } : {}),
    // ⛔ OMITTED when there is nothing to say (no row, no *No visit needed*)
    // — `fieldVisitPayload` answers `undefined` then, and an empty election on
    // the wire means nothing (`DEF-CUS-6392`).
    ...(fieldVisitPayload(draft.fieldVisit) !== undefined
      ? { field_visit: fieldVisitPayload(draft.fieldVisit) }
      : {}),
  };
}

/**
 * ⚠ **THE RULE IS REUSED; THE SENTENCE IS THIS SCREEN'S OWN — AND THAT SPLIT
 * WAS FOUND BY WALKING IT.** `accountIdentityShortfall` is `BR-CUS-1023`'s
 * client half and is the same function `NewAccountWizard` and `MoveInWizard`
 * use, so the three screens cannot disagree about what counts as an identifier
 * and none of them can disagree with the server. That much is right and stays.
 *
 * **But its four catalogue sentences all name the wrong act.** They read
 * *"Give the customer a name before opening the account"*, *"Say whether this
 * is a person or a business before opening the account"* and *"an account
 * cannot be opened without it"* — written for a wizard that OPENS an account.
 * **A sale opens nothing.** A clerk selling a property was told, in a red
 * strip, that an account could not be opened, which is not a thing they were
 * trying to do.
 *
 * Caught by walking the redesigned step 2 in a browser and reading what it
 * said — not by `tsc`, not by the 19 cases in this file, and not by any gate:
 * reusing a rule and inheriting its copy is indistinguishable from reusing both
 * to every check that exists. So the KEY is remapped here, one place, and the
 * four sale sentences live at the call site as `defaultValue`s for the
 * translation lane.
 */
const BUYER_SHORTFALL_SENTENCE: Record<string, string> = {
  "customers.account.identity_name_required": "customers.transfer.buyer.nameRequired",
  "customers.account.identity_kind_required": "customers.transfer.buyer.kindRequired",
  "customers.account.identity_required_person": "customers.transfer.buyer.personRequired",
  "customers.account.identity_required_company": "customers.transfer.buyer.companyRequired",
};

/**
 * The catalogue key of the ONE thing missing from the buyer's block, or
 * `null`. The rule is `accountIdentityShortfall`'s; the wording is a sale's.
 *
 * ⚠ **THE SEARCH IS NOT A PRECONDITION, AND THIS FUNCTION MUST NOT MAKE IT ONE
 * AGAIN — `DEF-CUS-6549`, PO ruling 2026-09-24.** From `2.351.0` this opened
 * with `if (!draft.buyerCreating) return "customers.transfer.buyer.findFirst"`,
 * so a clerk who had not searched was REFUSED on a step that was drawing no
 * form either. The PO reported it twice. Their ruling, option (a) of the two
 * put to them: *"the clerk has the buyer in front of them, and a wrong phone
 * caught at the counter is cheaper than one caught by a returned bill. - thissi
 * correct - please correct this"*. **A buyer typed straight in is the primary
 * path**, so a blank draft falls through to `accountIdentityShortfall` and the
 * clerk is told which FIELD is missing — never told to go and search first.
 */
export function buyerShortfall(draft: TransferDraft): string | null {
  // A LINKED customer IS the buyer and needs nothing more: the commit names
  // them by `customer_id` and the server already holds their identifier.
  if (draft.buyerCustomer !== null) return null;
  const key = accountIdentityShortfall(draft.buyer);
  return key === null ? null : (BUYER_SHORTFALL_SENTENCE[key] ?? key);
}

/**
 * **What the preview door said, in one line a clerk can act on.**
 *
 * Four verdicts, four different acts, and B14 rule 33 holds each to six words
 * per sentence. The identifying DETAIL — `C-00902 · Vasquez, M.` — is a VALUE
 * and rides after the sentence exactly as the drawing prints it; the customer
 * NUMBER is a tenant series and not a database id, so rule 31 is satisfied
 * (`matched` carries a uuid and that uuid is never rendered).
 */
export function buyerMatchSentence(
  preview: BuyerPreview | null,
  t: Translator,
): ReactNode {
  const match = preview?.buyer_match ?? null;
  // ⛔ NOTHING, rather than "no match": a door we did not ask and a buyer
  // nobody has on file are different facts (hard rule 2).
  if (match === null || match === undefined) return null;
  const named = preview?.buyer_name ?? null;
  const candidate = (match.candidates ?? [])[0] ?? null;
  const detail =
    [candidate?.customer_no ?? null, candidate?.display_name ?? named]
      .filter((part): part is string => typeof part === "string" && part !== "")
      .join(" · ") || null;
  const said: Record<string, string> = {
    named: t("customers.transfer.step2.matchNamed", {
      defaultValue: "You picked this customer.",
    }),
    matched: t("customers.transfer.step2.matchFound", {
      defaultValue: "Matched an existing customer.",
    }),
    candidates: t("customers.transfer.step2.matchCandidates", {
      defaultValue: "Someone similar is on file.",
    }),
    none: t("customers.transfer.step2.matchNone", {
      defaultValue: "Nobody on file matches.",
    }),
  };
  const sentence = said[match.verdict];
  if (sentence === undefined) return null;
  return (
    <Note className="max-w-measure" data-buyer-match={match.verdict}>
      {sentence}
      {detail === null ? null : ` ${detail}`}
      {/* ⚠ **THE ACTIONABLE HALF — `BR-CUS-089` wants name + date of birth +
          one government identifier for a STRONG match, so a buyer with a
          candidate and no date of birth is ONE QUESTION away from reusing a
          customer instead of minting a second one. Six words. */}
      {match.verdict === "candidates" && (match.missing_for_strong ?? []).length > 0
        ? ` ${t("customers.transfer.step2.matchMissing", {
            defaultValue: "A date of birth would decide.",
          })}`
        : null}
    </Note>
  );
}

/** The four sale sentences, each at rule 33's six-word cap, and each a `t()`
 *  call with a LITERAL key so `i18n_extract_defaults.py` can recover it. */
function buyerShortfallText(key: string, t: Translator): string {
  const said: Record<string, string> = {
    "customers.transfer.buyer.nameRequired": t("customers.transfer.buyer.nameRequired", {
      defaultValue: "Name the buyer.",
    }),
    "customers.transfer.buyer.kindRequired": t("customers.transfer.buyer.kindRequired", {
      defaultValue: "Say whether the buyer is a person or a company.",
    }),
    "customers.transfer.buyer.personRequired": t("customers.transfer.buyer.personRequired", {
      defaultValue: "Add one identifier: a licence, a phone or an SSN.",
    }),
    "customers.transfer.buyer.companyRequired": t("customers.transfer.buyer.companyRequired", {
      defaultValue: "Add the company's Tax ID.",
    }),
    // ⛔ `customers.transfer.buyer.findFirst` — *"Search for the buyer first."*
    // — IS RETIRED, not reworded (`DEF-CUS-6549`, PO ruling 2026-09-24). It was
    // the sentence the gate spoke with, and there is no gate now.
  };
  return said[key] ?? t(key);
}

// ⛔ **`sameDayOf` AND `datesAreOrdered` ARE DELETED, AND THAT IS THE RULING
// RATHER THAN A TIDY-UP.** Both answered a question about TWO dates — is the
// arrival the same day as the departure, and is it at least not before it. A
// sale has ONE date, so neither question exists: there is no departure, no
// arrival, no gap and nothing to order. `transfers.set_sale_date` writes the
// one date into both stored columns so `same_day` is true by construction
// rather than by a clerk typing it twice. A lane that restores either function
// is restoring the second account `BR-CUS-1030` removed.

/**
 * **FILE THE BUYER'S DOCUMENTS AGAINST THE ACCOUNT THEY BOUGHT — `DEF-CUS-6390`.**
 *
 * PO, verbatim: *"you have to take buyer documents - as we have taken document
 * in move in or new connect or new request"*. The step takes them with the
 * SAME `DocumentCapture`; a `File` is not JSON and cannot ride the commit, so
 * they are filed AFTER it through `POST /accounts/{id}/documents` — New
 * Connect's `fileOwnerDocuments` shape, for its reasons: the upload is handed
 * in so a test can watch it happen (hard-won law 2), one refusal does not stop
 * the rest, and none of them undoes the sale. The clerk is told the count.
 */
export async function fileBuyerDocuments(
  held: readonly DraftDocument[],
  accountId: string | null,
  upload: (accountId: string, doc: DraftDocument) => Promise<unknown>,
): Promise<{ filed: number; unfiled: number } | null> {
  if (held.length === 0) return null;
  if (accountId === null || accountId === "") return { filed: 0, unfiled: held.length };
  let filed = 0;
  for (const doc of held) {
    try {
      await upload(accountId, doc);
      filed += 1;
    } catch {
      // Counted as unfiled below. The clerk is told the number.
    }
  }
  return { filed, unfiled: held.length - filed };
}

/** A refusal the server named, in its own words — the commit's sentence,
 *  served early (`DEF-CUS-6395`). */
function refusalText(refusal: TransferRefusal, t: Translator): string {
  return t(refusal.message_key, { ...refusal.params });
}

// ══════════════════════════════════════════════════════════════════════════
// THE COMPONENT
// ══════════════════════════════════════════════════════════════════════════

export interface TransferWizardProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function TransferWizard(props: TransferWizardProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const { dateFormat, timeZone: regionalTimeZone } = useRegional(props);

  const step = stepFromParam(searchParams.get(STEP_PARAM), TRANSFER_STEPS);
  const nav: WizardNavState = { step, reached: step };
  function setStep(next: WizardNavState): void {
    const query = new URLSearchParams(searchParams);
    query.set(STEP_PARAM, String(next.step));
    setSearchParams(query, { replace: true });
  }
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

  const [draft, setDraft] = useState<TransferDraft>(emptyTransferDraft);
  // DEF-732 — what the clerk TYPED, kept by the wizard rather than by step 1:
  // the step's content unmounts on the way to step 2, and a search term that
  // vanished on the way back would look like the wizard forgot the account.
  const [accountTerm, setAccountTerm] = useState("");
  const [result, setResult] = useState<TransferRecord | null>(null);
  function patch(next: Partial<TransferDraft>): void {
    setDraft((current) => ({ ...current, ...next }));
  }

  // `GET /accounts/{id}` IS mounted, and it is the only server figure either
  // half of this screen has. Everything step 1 and step 4 print about money
  // comes from here or is stated absent.
  const accountId = draft.fromAccountId.trim();
  // The PUBLISHED search (BR-CUS-053), reused rather than a new endpoint —
  // account #, customer #, customer name, service address and meter #, in the
  // tenant's own scope.
  const accountSearch: AccountSearchState = useAccountSearch(accountTerm, client);
  // B14 rule 32 — the category's NAME comes from the catalogue the server
  // publishes, so a code never reaches a clerk and a category a future ruling
  // adds reads correctly the day its migration seeds it (BR-CUS-094).
  const categories = useAccountCategories(client);
  const accountQuery = useQuery({
    queryKey: ["transfer-wizard-account", accountId],
    queryFn: () => getAccountDetail(accountId, client),
    enabled: accountId !== "",
  });
  const account: AccountDetail | null = accountQuery.data ?? null;

  // ── `DEF-CUS-6395` + `DEF-CUS-5182` · STEP 1's ANSWER, THE MOMENT THE ACCOUNT
  // IS PICKED ─────────────────────────────────────────────────────────────
  // The refusal the commit WOULD raise (already being sold, not an occupant),
  // the seller as the account names them, whether it is the premises' master
  // account, and the cycle, period, next bill and ledger start this screen
  // used to hard-code as *"Not available yet"*. Writes nothing.
  const accountPreviewQuery = useQuery({
    queryKey: ["transfer-account-preview", accountId],
    queryFn: () => previewTransferAccount(accountId, client),
    enabled: accountId !== "",
    retry: false,
  });
  const accountPreview: TransferAccountPreview | null = accountPreviewQuery.data ?? null;
  // The BASE CHARGE is rating's own Σ (`BR-RAT-027`), read through the unit
  // pricing door the move-in wizard already renders — one source, not two.
  const unitId = account?.unit_id ?? null;
  const pricingQuery = useQuery({
    queryKey: unitPricingQueryKey(unitId ?? ""),
    queryFn: () => getUnitPricing(unitId ?? "", client),
    enabled: unitId !== null && unitId !== "",
    retry: false,
  });
  const baseCharge = pricingQuery.data?.plan?.base_charges ?? null;
  const baseCurrency =
    pricingQuery.data?.services.find((row) => row.currency)?.currency ?? account?.currency ?? null;

  // ── T1 · the buyer, found or created (`DEF-CUS-6386`) ───────────────────
  // The TERM is what is in the box; the SUBMITTED term is what the clerk asked
  // with *Search customer* — held here because the step's content unmounts.
  // ⊕ `DEF-CUS-10255` — *Search customer ID* and its results table (CF-1's
  // `CustomerMatchPanel`) replace the free-text finder; the answer is held
  // here because the step's content unmounts.
  const [buyerSearchAnswer, setBuyerSearchAnswer] = useState<CustomerSearchResult | null>(null);
  const [buyerDismissed, setBuyerDismissed] = useState<string[]>([]);
  const buyerSearch = useSearchMutation({
    mutationFn: (query: CustomerSearchQuery) => searchCustomerId(query, client),
    onSuccess: (answer) => setBuyerSearchAnswer(answer),
    onError: () => setBuyerSearchAnswer(null),
  });

  // ── `DEF-CUS-6392` · the field visit's rows turn red only once Continue
  // has been pressed on step 2 — the move-in's own posture. The table reads
  // its job types and holders itself (`GET /work/raise-options`, `/work/crews`).
  const [buyerStepTried, setBuyerStepTried] = useState(false);

  // ── `BR-CUS-1081` §4 · IS THIS BUYER ALREADY ON FILE? ───────────────────
  //
  // **The drawn feedback line on p127** — *"Matched an existing customer.
  // C-00902 · Vasquez, M., on the phone number."* — and the step's own premise,
  // *"Matched first, created only on no match"*, stated back about the buyer
  // actually being typed. Before this the match happened server-side AT COMMIT
  // and the clerk was never told.
  //
  // ⚠ **KEYED ON WHAT THE COMMIT WOULD SEND, NOT ON THE FORM.** The key is the
  // serialised `customer` block, so the door is asked again exactly when the
  // answer could change and never for a keystroke in a field it does not read.
  // ⚠ **ASKED ONLY ONCE A KIND AND A NAME EXIST.** With neither, the answer is
  // `none` for every buyer alive — a true sentence that tells a clerk nothing
  // and would flash over an empty form.
  // ⚠ **ADVISORY, AND IT GATES NOTHING** (`BR-CUS-019` — *the duplicate check
  // is ADVISORY; staff decides*). `canLeaveStep` does not read it and a failed
  // preview leaves the step completable, which is why `retry` is off: a door
  // that cannot answer must not hold a clerk up.
  const buyerPreviewQuery = useQuery({
    queryKey: [
      "transfer-buyer-preview",
      accountId,
      JSON.stringify(transferPlanOf(draft).customer),
    ],
    queryFn: () => previewTransferBuyer(transferPlanOf(draft).customer, client, accountId),
    // ⊕ T1 — asked for a LINKED buyer too: that is when the commit's
    // buyer-is-the-seller refusal can bite (`DEF-CUS-6395`).
    enabled:
      draft.buyerCustomer !== null ||
      (draft.buyer.full_name.trim() !== "" && draft.buyer.customer_kind.trim() !== ""),
    retry: false,
  });
  // The refusals the COMMIT would raise, served on the step where their cause
  // is picked — step 1 for the account, step 2 for the buyer (`DEF-CUS-6395`).
  const accountRefusal: TransferRefusal | null = accountPreview?.refusal ?? null;
  const buyerRefusal: TransferRefusal | null = buyerPreviewQuery.data?.refusal ?? null;

  const commit = useMutation({
    mutationFn: () => commitTransfer(transferPlanOf(draft), client),
  });

  // ── `DEF-CUS-6390` · the buyer's documents, filed after the sale ─────────
  const [docOutcome, setDocOutcome] = useState<{ filed: number; unfiled: number } | null>(null);

  async function runCommit(): Promise<WizardCommitOutcome> {
    try {
      const answered = await commit.mutateAsync();
      setResult(answered);
      // ⊕ `DEF-CUS-10255` — the buyer's documents are staged on the server as
      // a move-in's are and filed INSIDE the commit (`buyer_account.documents`),
      // so nothing is uploaded after it any more; the old held list is empty.
      setDocOutcome(
        await fileBuyerDocuments(draft.buyerDocuments, answered.from_account_id, (id, doc) =>
          uploadAccountDocument(
            id,
            { file: doc.file, docType: doc.docType as AccountDocumentType, name: doc.name },
            client,
          ),
        ),
      );
      fireToast(
        t("customers.transfer.toast", {
          defaultValue: "The sale is recorded.",
        }),
      );
      return { ok: true };
    } catch (error) {
      // BR-SHL-020 — the server's own refusal in its own words, with every
      // answer still on screen (A18 §4).
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // CR-035 — PARK AND RESUME
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **THE SUBJECT IS THE ACCOUNT THEY ARE LEAVING, AND IT IS A COPIED
  // STRING** (BR-SHL-048 (a)): a parked draft carries no foreign key, so the
  // "Waiting on" list reads what was true when the clerk parked it. `subjectRef`
  // is the same id `accountQuery` will look up AGAIN on resume — carried so the
  // wizard can re-read the account, never so anything can join to a draft.
  const park = useWizardPark({
    steps: TRANSFER_STEPS,
    step,
    parkOpen,
    context: {
      flow: "transfer",
      subjectLabel: account === null ? accountTerm : accountHeadline(account, translate),
      subjectRef: { account_id: accountId === "" ? null : accountId },
      // ⚠ **THE DOCUMENTS ARE NOT PARKED** — a `File` does not survive JSON,
      // and a parked row of empty objects would upload nothing on resume.
      values: { account_term: accountTerm, draft: { ...draft, buyerDocuments: [] } },
    },
    t: translate,
    client,
    // BR-SHL-048 (b) — the elections come back as TYPING, not as decisions
    // already taken. Step 4's own warning still applies on the way through
    // (*"an election is not a movement"*), the balance is re-read from the
    // server, and `datesAreOrdered` runs again on today's calendar.
    onHydrate: (row) => {
      setAccountTerm(parkedString(row.values, "account_term"));
      const parked = hydrateForm(emptyTransferDraft(), row.values.draft);
      // `DEF-CUS-6392` — the field visit is a nested value, distrusted field by
      // field (BR-SHL-048 (b)); a draft parked before the table arrived held a
      // list of template ids and comes back empty.
      const rawVisit =
        row.values.draft !== null && typeof row.values.draft === "object"
          ? (row.values.draft as Record<string, unknown>).fieldVisit
          : undefined;
      setDraft({ ...parked, fieldVisit: hydrateFieldVisit(rawVisit) });
    },
    // CR-035 · AMENDMENT 1 (PO 2026-08-26) — a parked draft lands on the tab
    // for its OWN kind of work, not on a ninth queue. `parkedHomePath` is the
    // one place those five destinations are named.
    onParked: () => navigate(tenantPath(parkedHomePath("transfer"))),
  });
  // `DEF-SHL-10001` — the leave-page popup's *Save as draft* writes the
  // same `wizard_parks` row this wizard's Park writes, as a draft.
  const leaveDraft: LeaveDraft = {
    onSave: park.saveDraft,
    savedMessage: t("leaveGuard.saved", { place: t("customers.accounts.tab.transfers") }),
  };

  /** B19 §12.2 — TWO controls, and they stay two. `Save & exit` leaves quietly
   *  and writes nothing; `Park` records what is being waited on, a note and a
   *  reminder, and still writes nothing outside the draft store (BR-SHL-048). */
  const exit: WizardExit = {
    onSaveAndExit: () => navigate(tenantPath(TRANSFERS_TAB_PATH)),
    // ✅ BR-SHL-047 is now TRUE rather than merely ruled: the shared sentence
    // this reused is `null` since CR-035, so this control acts. One `return` in
    // `wizardParkPort()` turned all five wizards on, which is why the reason
    // was one function and never a boolean at five call sites.
    parkBlockedReason: parkStoreBlockedReason(translate),
    parkOpen,
    onParkOpenChange: setParkOpen,
    onPark: park.onPark,
    dateFormat,
    parkedAt: park.parkedAt,
  };

  if (result !== null) {
    return (
      <TransferDone
        record={result}
        documents={docOutcome}
        t={translate}
        onDone={() => navigate(tenantPath(TRANSFERS_TAB_PATH))}
        fieldVisit={draft.fieldVisit}
        dateFormat={dateFormat}
        timeZone={props.timeZone ?? regionalTimeZone}
        client={client}
      />
    );
  }

  const steps: WizardStep[] = [
    {
      id: TRANSFER_STEPS[0].id,
      label: t(TRANSFER_STEPS[0].labelKey, { defaultValue: TRANSFER_STEPS[0].en }),
      content: (
        <LeavingStep
          draft={draft}
          account={account}
          failed={accountQuery.isError}
          onPatch={patch}
          term={accountTerm}
          onTermChange={setAccountTerm}
          search={accountSearch}
          dateFormat={dateFormat}
          categoryName={
            account === null ? "" : accountCategoryName(account.account_type, categories.all)
          }
          preview={accountPreview}
          baseCharge={baseCharge}
          baseCurrency={baseCurrency}
          t={translate}
        />
      ),
      // ⊕ `DEF-CUS-6395` — the commit's own account refusal holds the step.
      validate: () => accountId !== "" && accountRefusal === null,
    },
    {
      id: TRANSFER_STEPS[1].id,
      label: t(TRANSFER_STEPS[1].labelKey, { defaultValue: TRANSFER_STEPS[1].en }),
      content: (
        <BuyerStep
          draft={draft}
          account={account}
          onPatch={patch}
          t={translate}
          dateFormat={dateFormat}
          preview={buyerPreviewQuery.data ?? null}
          client={client}
          fieldVisitShowErrors={buyerStepTried}
          timeZone={props.timeZone ?? regionalTimeZone}
          categoryName={
            account === null ? "" : accountCategoryName(account.account_type, categories.all)
          }
          search={{
            answer: buyerSearchAnswer,
            pending: buyerSearch.isPending,
            failed: buyerSearch.isError,
            dismissed: buyerDismissed,
            onDismiss: (id) => setBuyerDismissed((was) => [...was, id]),
            run: (query) => buyerSearch.mutate(query),
          }}
        />
      ),
      // ⚠ **THE STEP REFUSES ON THE BUYER, WHICH IS WHAT THE SERVER REFUSES
      // ON** — `BR-CUS-1023`'s own clause: name the missing thing at the door
      // where the clerk is typing. Before today this validated
      // `draft.outDate !== ""`, a field the door does not read, and the only
      // refusal a clerk could actually reach was a 422 at step 5 naming
      // `buyer_required` — a field no step offered.
      validate: () => {
        setBuyerStepTried(true);
        return (
          buyerShortfall(draft) === null &&
          buyerRefusal === null &&
          (draft.mailingSameAsService || usZipIsValid(draft.buyerMailing.postal_code)) &&
          // ⊕ `DEF-CUS-10255` — Move-in's rules on the buyer: the format
          // checks, a named co-buyer, and a complete Tax / Discounts panel.
          customerFormatProblem(draft.buyer) === null &&
          (!draft.coBuyersOn ||
            (coOwnerProblem(draft.coBuyers) === null && coOwnerFormatProblem(draft.coBuyers) === null)) &&
          billingProblems({ ...draft.buyerBilling, planRows: [] }).length === 0 &&
          fieldVisitProblem(draft.fieldVisit) === null
        );
      },
    },
    {
      id: TRANSFER_STEPS[2].id,
      label: t(TRANSFER_STEPS[2].labelKey, { defaultValue: TRANSFER_STEPS[2].en }),
      content: (
        <SaleDateStep
          draft={draft}
          account={account}
          onPatch={patch}
          t={translate}
          dateFormat={dateFormat}
          preview={accountPreview}
          baseCharge={baseCharge}
          baseCurrency={baseCurrency}
        />
      ),
      // One date, so there is nothing to order it against. `set_sale_date`
      // refuses an absent date by name and so does this.
      validate: () => draft.soldOn !== "",
    },
    {
      id: TRANSFER_STEPS[3].id,
      label: t(TRANSFER_STEPS[3].labelKey, { defaultValue: TRANSFER_STEPS[3].en }),
      content: (
        <TakeOnStep
          draft={draft}
          account={account}
          onPatch={patch}
          dateFormat={dateFormat}
          t={translate}
        />
      ),
      // ⚠ **`shownToBuyer` IS NOT A GATE, DELIBERATELY.** Whether the buyer
      // must be shown what they are taking on, and where, has never been ruled
      // — the drawing says so in as many words — so refusing the step on it
      // would be this screen inventing a rule about somebody's money.
      validate: () => true,
    },
    {
      id: TRANSFER_STEPS[4].id,
      label: t(TRANSFER_STEPS[4].labelKey, { defaultValue: TRANSFER_STEPS[4].en }),
      content: (
        <TransferReviewStep
          draft={draft}
          account={account}
          preview={accountPreview}
          t={translate}
          dateFormat={dateFormat}
          timeZone={props.timeZone ?? regionalTimeZone}
          client={client}
        />
      ),
      validate: () => true,
    },
  ];

  // BR-SHL-046 — ONE declared list answers the count, the rail and the step
  // line. `flowProgress` clamps, so `?step=99` names step 5 rather than
  // reading past the end of the array.
  const progress = flowProgress(TRANSFER_STEPS, step);
  const currentStep = TRANSFER_STEPS[progress.step - 1];

  return (
    <div data-screen={TRANSFER_WIZARD_SCREEN} data-r10="TRF-02">
      <PageHeader
        kicker={t("customers.transfer.kicker", { defaultValue: "Transfer" })}
        /* ══ THE TITLE, AND IT IS THE CURRENT STEP'S — `DEF-CUS-6542` ═══════
           ⚠ **EVERY WORD OF THE OLD TITLE AND SUBTITLE WAS THE REPLACED JOB**
           — *"Same customer, moving to another of your addresses"* and *"Five
           steps · one job, not two. The deposit moves with them."* A customer
           moving to another of your addresses is a NEW SERVICE REQUEST, and the
           deposit moves nowhere because the account it sits on does not move.
           `DEF-CUS-5075`.

           ⚠ **AND THE REPLACEMENT WAS STILL ONE CONSTANT FOR FIVE SCREENS**, so
           it was right on step 1 and wrong on the other four — a clerk on the
           buyer step was told to *"Find the account, and who is selling"* with
           `Step 2 of 5 · The buyer` printed directly underneath it. It survived
           because a screenshot of step 1 is what every walkthrough and every
           review had looked at.

           ⚠ **THE NAME COMES OFF THE SAME ARRAY AS THE COUNT, THE RAIL AND THE
           STEP LINE** — `BR-SHL-046`'s durable clause, *"driven by ONE declared
           step list"*. A sixth step declares its own title beside its own rail
           label and needs no edit here.

           ⚠ **THE FIVE STRINGS ARE NO LONGER THE DRAWN ONES — PO RULING
           2026-09-24, verbatim: *"4 · The five transfer headings - b  Shorten
           all five to the cap"*.** They were built as drawn for one day, at
           7 · 4 · 4 · 5 · 7 words against B14 rule 33's cap of three, under the
           *"b) Leave as drawn"* precedent the PO set that morning for the
           move-out. Put to them a second time for these five, they ruled the
           other way. The heads now read *Account & seller* · *The buyer* ·
           *The date* · *The money* · *Review & confirm*; three of the five are
           the blueprint's own section names for the same content (p131). **The
           move-out's four shortfall labels are untouched — both rulings are
           live.** See `transferDisconnectShared.tsx` for the whole chain. */
        title={
          currentStep.titleKey === undefined
            ? t(currentStep.labelKey, { defaultValue: currentStep.en })
            : t(currentStep.titleKey, { defaultValue: currentStep.titleEn })
        }
        /* ⛔ **NO ROLLUP — THE DRAWING HAS NONE, ON ANY OF THE FIVE STEPS
           (`DEF-CUS-6542`).** This head used to carry a `Note` reading *"5 steps
           · the account changes hands, nothing else moves."* on every step.
           **p127–p131 each draw exactly three lines above the rail — the
           `TRANSFER` kicker, the 32px title, and `Step N of 5 · <rail label>` —
           and nothing else**, so the sentence was ours rather than the
           agreement's (B14 rule 41).

           It also broke two rules it was standing next to. Its COUNT is what
           `customers.wizard.stepOfNamed` prints one line below, and B14 rule 32
           says a row never repeats what its own control offers; and *"nothing
           else moves"* is RATIONALE — why a sale is safe — which rule 33 puts at
           **zero words on screen**, removed rather than shortened.

           ⚠ **THE FACT IS NOT LOST AND THAT IS WHY THIS IS A DELETION RATHER
           THAN A MOVE.** *What this sale will not touch* is drawn as a panel of
           its own on step 1 (p127) and is rendered there, itemised — issued
           bills, payments taken, journal entries, the account number, the unit
           and meters, the service agreements. A clerk who needs the assurance
           reads the panel that gives it in full; the head no longer summarises
           it in nine words over four screens where it answers nothing a clerk
           standing there is asking. `customers.transfer.subSteps` is retired
           from the eleven catalogues in the same commit. */
        backTo={{
          to: tenantPath(TRANSFERS_TAB_PATH),
          label: t("customers.transfers.title", { defaultValue: "Transfers" }),
        }}
        /* ⛔ **`Split into two` IS REMOVED, NOT DISABLED — `DEF-CUS-5075`.** It
           was drawn on the frame of the job the PO replaced, where a transfer
           was a move-out plus a move-in and splitting it back was at least a
           coherent thing to want. **Under `BR-CUS-1030` there is nothing to
           split**: one account changes hands, no account closes and none opens.
           A greyed control for an incoherent act is hard-won law 2's mirror —
           a dead door that teaches a clerk the product might one day do
           something it never will — and the drawn step 1 at p113 carries only
           `Save & exit` in its header. */
      />
      {/* ══ THE LINE UNDER THE TITLE, AND IT NAMES THE STEP ══════════════════
          `DEF-CUS-5179`. The blueprint's page image (p113–p117) writes
          `Step 1 of 5 · Find the account` under the 32px title of every one of
          the five screens, and this line read `Step N of 5 · one account
          changes hands, all at once.` on all five — a number and a slogan,
          never which step a clerk is standing on. It matters most on the one
          journey nobody walks: a parked draft resumes at step 4, and step 4 of
          a slogan is not an answer.

          ⚠ **THE NAME COMES OFF THE SAME ARRAY AS THE COUNT AND THE RAIL** —
          `BR-SHL-046`'s durable clause, *"driven by ONE declared step list"* —
          so a sixth step needs no edit here and cannot make this line disagree
          with the bar above it.

          ⚠ **AND THE KEY IS THE SHARED ONE, DELIBERATELY (`DEF-CUS-5177`).**
          `customers.wizard.stepOfNamed` is already in all eleven catalogues,
          minted by the lane that fixed the same fault on the twelve move-in and
          move-out screens this morning. That row's whole finding is that two
          lanes minted two keys for one sentence and no check can see a
          duplicate, so this wizard adds none: the eighth wizard to be walked
          reads the same key the first two do.

          ⚠ **THE ATOMICITY SENTENCE IS NOT LOST, IT IS WHERE THE DRAWING PUTS
          IT.** *"All five writes land together, or none does"* is drawn on step
          5's own consequence list and is rendered there (`data-will="atomic"`),
          which is also rule 33: a step line is a FACT and the reason a commit
          is safe is RATIONALE, worth zero words in a head. */}
      <Note className="mb-3 max-w-measure" data-flow-footer="">
        {t("customers.wizard.stepOfNamed", {
          ...progress,
          name: t(currentStep.labelKey, { defaultValue: currentStep.en }),
          defaultValue: "Step {{step}} of {{of}} · {{name}}",
        })}
      </Note>
      <WizardFrame
        steps={steps}
        nav={nav}
        onNavChange={setStep}
        /* ⚠ **`Complete the sale ✓`, WHICH IS WHAT THE DRAWING SAYS AND WHAT
           THE ACT IS** — `DEF-CUS-5075`. And the failure title said *"Neither
           half happened"*, which described the two halves of the replaced job.
           There is one job: five staged writes in one transaction, all or
           none. B14's button grammar keeps the `✓` — this commits. */
        commitLabel={t("customers.transfer.commit", { defaultValue: "Complete the sale ✓" })}
        commitFailedTitle={t("customers.transfer.commitFailed", {
          defaultValue: "The sale was not recorded. Nothing changed hands.",
        })}
        onCommit={runCommit}
        onCommitted={() => undefined}
        exit={exit}
        saveDraft={leaveDraft}
      />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 1 · LEAVING (`TRF-02.1`)
// ══════════════════════════════════════════════════════════════════════════
/**
 * Step 1 — the account they are leaving, and the three things this screen
 * cannot check.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⛔ DEF-731 · WHAT THIS DOCSTRING IS FOR — IT IS WHAT THE SCREEN USED TO SAY
 * ══════════════════════════════════════════════════════════════════════════
 * Until 2026-08-26 the three absences below rendered as `RefusalStrip` — the
 * RED strip `BR-SHL-020` reserves for a server refusal — carrying sentences
 * written to an engineer:
 *
 *   (b) *"…is not published by any endpoint this screen can read"*
 *   (d) *"…are not served to this screen"*
 *   (x) *"…because no endpoint it can call answers them"*
 *
 * Two faults compounded, and the PO reported both: the VOICE (a clerk does not
 * have an endpoint) and the TONE (three red blocks are the first thing a
 * transfer shows, before anybody has done anything wrong). **An absence is not
 * an error**, so all three are neutral notes now, and so are the two on steps 2
 * and 3. The RED strips that remain in this file are real refusals — an account
 * that would not load, dates out of order, an arrear that could not be read.
 *
 * **The findings themselves are not lost. They are these, and they are why the
 * copy says what it says:**
 *
 *   · **(b) relationships.** Nothing serves this screen whether the account has
 *     a sub-meter measuring through it or sub-accounts beneath it. The drawing
 *     prints `Standalone`; printing that word would be a FINDING nobody
 *     computed, on the screen that authorises a closure — so the copy says the
 *     matter is unchecked and declines to reassure.
 *   · **(d) the premise.** Its owner/manager and its occupied-unit count are
 *     served to nothing this screen may call. The drawing's own note that an
 *     owner is free text and not an account is a separate product finding this
 *     repo already carries.
 *   · **(x) the blockers.** The drawn `CHECKED` / `FOLLOWS` banners assert an
 *     active payment plan, an unresolved dispute and an unbilled cycle are all
 *     clear. None of the three is readable from here, and a clearance nobody
 *     computed is the most expensive sentence a wizard can print.
 *
 * **Where a finding needs an owner it needs a defect row, not a paragraph on
 * the page** — that is DEF-731's own prevention column, and this lane REPORTED
 * the three above rather than minting ids for them (prime directive).
 */

// ══════════════════════════════════════════════════════════════════════════
// THE DRAWN FACT ROWS — `DEF-CUS-5180`
// ══════════════════════════════════════════════════════════════════════════
//
// The blueprint draws step 1 and step 3 as columns of `label … value` rows with
// a rule under each, the value hard against the right edge. `PlainTable` is the
// kit's shape for exactly that and every other fact panel in this module
// already uses it, so these add no component and no stylesheet class (B14 rule
// 21) — `Fact` is a row, not a table.

/** One drawn row. A `<th scope="row">` and not a `<div>`, because the label
 *  NAMES the value and a screen reader has to be told which. */
function Fact(props: { label: string; children: ReactNode }) {
  return (
    <tr>
      <th scope="row">{props.label}</th>
      <td>{props.children}</td>
    </tr>
  );
}

/**
 * ⚠ **THREE FIELDS THE SERVER SENDS AND THE SHARED TYPE DOES NOT YET DECLARE.**
 *
 * `apps/customers/selectors._unit_facts` widened its pick on 2026-09-13 to
 * carry the unit's floor, its floor area and the premises' reference — all
 * three already returned by `metering.unit_detail_dict` and simply not
 * selected. `api/endpoints.ts` is another lane's file today (law 11: a shared
 * file edited under a live sibling is the revert this repository has recorded
 * eight times), so the three are declared HERE, structurally, and read through
 * one narrowing.
 *
 * ⚠ **THIS IS A CLAIM ABOUT A PAYLOAD AND NOT A GUARANTEE OF ONE** (hard-won
 * law 1). Every field is OPTIONAL and every reader treats `undefined` as *"this
 * build is talking to a server that has not shipped it"* — the same posture
 * `premise_locality` and `paperless` take in the shared type. `DEF-CUS-5188`'s
 * neighbour is owed: fold these into `AccountDetail` when that file is free.
 */
interface UnitExtras {
  unit_floor?: string | null;
  unit_square_feet?: number | null;
  premise_no?: string | null;
}

function unitExtras(account: AccountDetail): UnitExtras {
  return account as AccountDetail & UnitExtras;
}

/** An election the account carries, in the two words the drawing uses. */
function onOff(on: boolean, t: Translator): string {
  return on
    ? t("customers.transfer.fact.on", { defaultValue: "On" })
    : t("customers.transfer.fact.off", { defaultValue: "Off" });
}

/** The contact the bill is addressed to. `is_primary` is the server's own flag;
 *  where nothing is flagged the first row is what every other account surface
 *  shows, and showing a different one here would make two screens disagree. */
function primaryContact(account: AccountDetail): AccountContact | null {
  // `?? []` — `DEF-CUS-5995`. Declared non-optional, served by a wire that can
  // omit it, and read mid-render, so an absence takes the STEP rather than the cell.
  const contacts = account.contacts ?? [];
  return contacts.find((row) => row.is_primary) ?? contacts[0] ?? null;
}

/**
 * ⚠ **`kind='mailing'` IS THE ONE LAWFUL SECOND ADDRESS AND `kind='service'` IS
 * RETIRED** (hard rule 8). A mailing row is *where the BILL goes*, which for a
 * landlord is another building; its absence is a real answer — the bill goes to
 * the service address the account walks to through its premises — and that is
 * what the drawing prints in the cell.
 */
function mailingLine(account: AccountDetail): string | null {
  // `?? []` — `DEF-CUS-5995`, the same read shape as `contacts` above.
  const row = (account.addresses ?? []).find((address) => address.kind === "mailing");
  if (row === undefined) {
    return null;
  }
  const parts = [row.line1, row.city, row.state, row.postal_code].filter(
    (part): part is string => part !== null && part !== "",
  );
  return parts.length === 0 ? null : parts.join(", ");
}

/**
 * The blueprint's second step-1 panel — *"What is changing hands with it"* —
 * and step 3's *"What changes hands on that day"*. **One component, because the
 * drawing shows the same facts twice on purpose**: step 1 answers *what am I
 * selling* and step 3 answers *what does the date apply to*, and a second copy
 * is how the two start disagreeing.
 *
 * `period` is the one difference the drawing actually draws: step 1 carries the
 * unit's FLOOR and FLOOR AREA, step 3 carries the CURRENT PERIOD and the NEXT
 * BILL instead. Nothing else moves between the two.
 */
function ChangingHandsPanel(props: {
  account: AccountDetail;
  t: Translator;
  /** True on step 3, where the drawing swaps the two unit rows for the two
   *  billing-period ones. */
  period: boolean;
  /** ⊕ `DEF-CUS-5182` — the cycle, period, next bill and ledger start, served
   *  by `POST /transfers/account-preview`. Null while it is being asked. */
  preview?: TransferAccountPreview | null;
  /** Rating's Σ of the plan's base charges (`BR-RAT-027`), from the unit
   *  pricing door. Null where the unit's plan states none. */
  baseCharge?: string | null;
  baseCurrency?: string | null;
  dateFormat?: RegionalDateFormat;
}) {
  // DEF-SHL-3964: the tenant's own format, never a hand-written fallback (DEF-SHL-9122).
  const regional = useRegional(props);
  const { account, t } = props;
  const extras = unitExtras(account);
  const preview = props.preview ?? null;
  const dateFormat = regional.dateFormat;
  // ⛔ **`unserved("DEF-CUS-5182")` IS GONE (2026-09-23).** Five rows were
  // HARD-CODED *"Not available yet"* and never asked anything. Each is now a
  // served figure or a six-word FACT saying what is absent — never rationale.
  const absent = (key: string, fallback: string) => (
    <AbsentValue reason={t(key, { defaultValue: fallback })} />
  );
  const day = (iso: string | null | undefined): string | null =>
    iso === null || iso === undefined || iso === "" ? null : formatDate(iso, "UTC", dateFormat);
  const cycle = preview?.billing_cycle ?? null;
  const cycleText =
    cycle === null
      ? null
      : [
          cycle.name ?? cycle.code,
          cycle.bill_day === null
            ? null
            : t("customers.transfer.fact.billDay", {
                defaultValue: "bills on day {{day}}",
                day: cycle.bill_day,
              }),
        ]
          .filter((part): part is string => part !== null && part !== "")
          .join(" · ");
  const periodText =
    preview?.current_period == null
      ? null
      : [day(preview.current_period.start), day(preview.current_period.end)]
          .filter((part): part is string => part !== null)
          .join(" – ");
  return (
    <Panel as="section">
      <h4 className="font-heading text-md m-0 mb-2">
        {props.period
          ? t("customers.transfer.step3.changesTitle", {
              defaultValue: "What changes hands on that day",
            })
          : t("customers.transfer.step1.panelChanging", {
              defaultValue: "What is changing hands with it",
            })}
      </h4>
      <PlainTable>
        <tbody>
          <Fact label={t("customers.transfer.fact.unit", { defaultValue: "Unit" })}>
            {/* B14 rule 31 — the unit's LABEL, never its id. An account with no
                unit is a master account (`BR-CUS-1010`) and genuinely has none. */}
            {account.unit_label ?? <Dash />}
          </Fact>
          <Fact label={t("customers.transfer.fact.unitType", { defaultValue: "Unit type" })}>
            {/* A CODE, rendered through the catalogue the units list already
                uses. It is never printed raw — B14 rule 32. */}
            {account.unit_type === null || account.unit_type === undefined ? (
              <Dash />
            ) : (
              t(`metering.units.type.${account.unit_type}`, { defaultValue: account.unit_type })
            )}
          </Fact>
          {!props.period && (
            <Fact label={t("customers.transfer.fact.floor", { defaultValue: "Floor" })}>
              {extras.unit_floor ?? <Dash />}
            </Fact>
          )}
          {!props.period && (
            <Fact label={t("customers.transfer.fact.floorArea", { defaultValue: "Floor area" })}>
              {/* ⚠ ALWAYS WITH ITS UNIT (CLAUDE.md hard rule 3). `square_feet`
                  is an integer and the unit is not in the number. */}
              {extras.unit_square_feet === null || extras.unit_square_feet === undefined ? (
                <Dash />
              ) : (
                t("customers.transfer.fact.squareFeet", {
                  defaultValue: "{{count}} sq ft",
                  count: extras.unit_square_feet,
                })
              )}
            </Fact>
          )}
          <Fact label={t("customers.transfer.fact.premises", { defaultValue: "Premises" })}>
            {/* The BUILDING's street line and the premises' own reference —
                `PR-0518`, a tenant numbering series and not a database key. */}
            {premisesLine(account) ?? <Dash />}
          </Fact>
          <Fact label={t("customers.transfer.fact.serviceAddress", { defaultValue: "Service address" })}>
            {/* ⚠ **COMPOSED HERE, FROM TWO HALVES THAT TRAVEL SEPARATELY** —
                `BR-MET-1161`. The street line and the locality are both read
                from the ONE home, the premises, so a map and an envelope cannot
                disagree; joining them on the screen is what stops a second
                stored copy appearing to hold the answer. */}
            {serviceAddressLine(account) ?? <Dash />}
          </Fact>
          <Fact label={t("customers.transfer.fact.services", { defaultValue: "Services" })}>
            {/* `?? []` for `DEF-CUS-5995`'s reason and no other: this cell has
                never been seen to throw, and it is the same read on the same
                payload four rows above one that did. */}
            {(account.services ?? []).length === 0 ? (
              <Dash />
            ) : (
              (account.services ?? [])
                .map((code) => t(`rating.service.${code}`, { defaultValue: code }))
                .join(" · ")
            )}
          </Fact>
          <Fact label={t("customers.transfer.fact.meters", { defaultValue: "Meters" })}>
            {/* ⚠ **GUARDED AT THE READ, AND THE EMPTY CASE IS A STATED ABSENCE**
                (`DEF-CUS-5991`). Two faults, one line. `meters` is typed
                non-optional and the wire does not always agree — a payload
                without the array read `undefined.length` and took the WHOLE
                step down mid-render, which vitest reports as an UNHANDLED
                ERROR at the end of a run rather than as a failing assertion.
                And a unit with NO METER AT ALL is lawful and ordinary — the
                move-out scenarios carry a whole row for it (`R4`) — so the
                empty list SAYS SO instead of drawing a bare dash, which claims
                this row has no answer about a row that has a good one.
                ⚠ THE KEY IS THE MOVE RECORD'S OWN, deliberately: it is
                answered in all eleven catalogues (B14 rule 35) and a second
                spelling of `No meter on this unit` is a twelfth way to say one
                thing. Five words, so B14 rule 33's six-word FACT cap holds. */}
            {meterLine(account) ?? (
              <AbsentValue
                reason={t("customers.moveRecord.readsAbsent.unit_has_no_meters", {
                  defaultValue: "No meter on this unit",
                })}
              />
            )}
          </Fact>
          <Fact label={t("customers.transfer.fact.plan", { defaultValue: "Plan" })}>
            {/* `DEF-2419` — the plan the UNIT stands on today, which is what the
                account is billed on (PO 2026-09-01, *"from unit you will derive
                the plan"*). `plan` is the different question — the snapshot
                taken when the account was set up — and has no table. */}
            {planLine(account) ?? <Dash />}
          </Fact>
          <Fact label={t("customers.transfer.fact.baseCharge", { defaultValue: "Base charge" })}>
            {/* Rating's own Σ, printed as served — this file adds nothing up
                (hard rule 2). */}
            {props.baseCharge != null && props.baseCurrency != null ? (
              <MoneyCell amount={props.baseCharge} currency={props.baseCurrency} />
            ) : preview === null ? (
              <Dash />
            ) : (
              absent("customers.transfer.fact.noBaseCharge", "No base charge recorded.")
            )}
          </Fact>
          <Fact label={t("customers.transfer.fact.billingCycle", { defaultValue: "Billing cycle" })}>
            {cycleText ??
              (preview === null ? <Dash /> : absent("customers.transfer.fact.noCycle", "No billing cycle set."))}
          </Fact>
          {props.period && (
            <Fact label={t("customers.transfer.fact.currentPeriod", { defaultValue: "Current period" })}>
              {periodText ??
                (preview === null ? <Dash /> : absent("customers.transfer.fact.noPeriod", "No period set."))}
            </Fact>
          )}
          {props.period && (
            <Fact label={t("customers.transfer.fact.nextBill", { defaultValue: "Next bill" })}>
              {day(preview?.next_bill_on) ??
                (preview === null ? <Dash /> : absent("customers.transfer.fact.noNextBill", "No bill date set."))}
            </Fact>
          )}
          {!props.period && (
            <Fact label={t("customers.transfer.fact.ledger", { defaultValue: "Ledger" })}>
              {/* A sale closes no account, so the ledger runs unbroken from
                  the day the account opened (`BR-CUS-1030`). */}
              {day(preview?.ledger_since) === null ? (
                <Dash />
              ) : (
                t("customers.transfer.fact.ledgerSince", {
                  defaultValue: "Unbroken since {{date}}",
                  date: day(preview?.ledger_since),
                })
              )}
            </Fact>
          )}
        </tbody>
      </PlainTable>
    </Panel>
  );
}

/** `310 Marigold Lane · PR-0518` — the street line and the premises' own
 *  reference, either half of which may be absent. */
function premisesLine(account: AccountDetail): string | null {
  const extras = unitExtras(account);
  const parts = [account.premise_address ?? null, extras.premise_no ?? null].filter(
    (part): part is string => part !== null && part !== "",
  );
  return parts.length === 0 ? null : parts.join(" · ");
}

/** `310 Marigold Lane, Silver Creek, TX 78611` — hard rule 8's one home,
 *  composed on the screen from the two halves the payload sends separately. */
function serviceAddressLine(account: AccountDetail): string | null {
  const locality = account.premise_locality ?? null;
  const parts = [
    account.premise_address ?? null,
    locality?.city ?? null,
    [locality?.state ?? null, locality?.postal_code ?? null]
      .filter((part): part is string => part !== null && part !== "")
      .join(" "),
  ].filter((part): part is string => part !== null && part !== "");
  return parts.length === 0 ? null : parts.join(", ");
}

/** `M-8841 · Main · M-8842` — the meters standing on the account's unit, or
 *  null when there are none to name.
 *
 *  ⚠ **`?? []` IS NOT DEFENSIVE TIDYING, IT IS `DEF-CUS-5991`.** `AccountDetail`
 *  declares `meters` non-optional, so `tsc` is satisfied by a read that the
 *  wire can still answer with nothing — and the caller renders mid-table, so
 *  the throw takes the whole step, not the cell. Null and empty are the SAME
 *  answer here on purpose: both mean *nothing to name*, and both are stated
 *  rather than dashed. */
function meterLine(account: AccountDetail): string | null {
  const meters = account.meters ?? [];
  if (meters.length === 0) {
    return null;
  }
  return meters
    .map((meter) => [meter.asset_no, meter.qualifier].filter((part) => part !== null).join(" "))
    .join(" · ");
}

/** `SCW-RES · Residential · v1`, and null on each of the three real absences
 *  `seams.unit_plan_in_force` answers with: no unit, no plan on the unit, or a
 *  plan no longer published. */
function planLine(account: AccountDetail): string | null {
  // ⚠ `?? null`, NOT `=== null` — `DEF-CUS-5995`, the SECOND crash in this one
  // table and the one the first one hid. `unit_plan` is declared
  // `AccountUnitPlan | null`, so a payload that simply omits the key is
  // `undefined`, sails past a `=== null` test and throws on `plan.code` four
  // rows below the meters cell. `tsc` cannot see it: the type says the field is
  // always there and the wire does not agree.
  const plan = account.unit_plan ?? null;
  if (plan === null) {
    return null;
  }
  const parts = [plan.code, plan.name, plan.version === null ? null : `v${plan.version}`].filter(
    (part): part is string => part !== null && part !== "",
  );
  return parts.length === 0 ? null : parts.join(" · ");
}

/** ⊕ `DEF-CUS-6383` — the account has nobody linked (a FACT, three words). */
function noCustomer(t: Translator): ReactNode {
  return (
    <span data-no-customer="">
      {t("customers.transfer.fact.noCustomer", { defaultValue: "No customer linked" })}
    </span>
  );
}

export function LeavingStep(props: {
  draft: TransferDraft;
  account: AccountDetail | null;
  failed: boolean;
  onPatch: (next: Partial<TransferDraft>) => void;
  /** DEF-732 — the term the clerk typed, and what the published search
   *  answered for it. **Optional ONLY because the static markup cases in this
   *  module render this step directly with no wizard around it**; the wizard
   *  passes all three, and G13 is what keeps that true (a `??` default with no
   *  caller anywhere is exactly the dead-UI shape it fails on). Absent, the box
   *  still renders and simply offers nothing — it never silently becomes an
   *  id-only field again. */
  term?: string;
  onTermChange?: (term: string) => void;
  search?: AccountSearchState;
  /** `Opened 03/08/2022` goes through the ONE formatter the rest of the
   *  product uses, so a tenant on `DD/MM/YYYY` reads this row the way they read
   *  every other date.
   *
   *  ⚠ **OPTIONAL FOR THE SAME REASON `term` AND `search` ARE, AND FOR NO
   *  OTHER.** Static-markup cases in this module and in
   *  `screenVoice.guard.test.tsx` render this step directly with no wizard
   *  around it; the wizard passes both, which is what G13 checks and what stops
   *  a defaulted prop becoming a prop nothing ever passes. */
  dateFormat?: RegionalDateFormat;
  /** The account category's own NAME, resolved by `accountCategoryName` against
   *  the catalogue the server publishes. Never a label typed on this screen.
   *  Optional for the reason above; empty renders an empty cell, never a
   *  guessed label. */
  categoryName?: string;
  /** ⊕ `DEF-CUS-6395` / `DEF-CUS-5182` — `POST /transfers/account-preview`. */
  preview?: TransferAccountPreview | null;
  baseCharge?: string | null;
  baseCurrency?: string | null;
  t: Translator;
}) {
  // DEF-SHL-3964: the tenant's own format, never a hand-written fallback (DEF-SHL-9122).
  const regional = useRegional(props);
  const account = props.account;
  const refusal = props.preview?.refusal ?? null;
  // ⊕ `DEF-CUS-6382` — ONE searchable control, the kit's (B14 rule 43). The
  // published search's four facts, as the kit's four booleans.
  const term = props.term ?? "";
  const search = props.search ?? ACCOUNT_SEARCH_IDLE;
  // ⚠ `DEF-CUS-9106` — A PASTED ID IS ITS OWN ANSWER (DEF-732's second rule).
  // This step moved onto the kit control directly on 2026-09-24 and lost the
  // path `AccountFinder` keeps: the kit fires `onChange("")` on every
  // keystroke, so a pasted uuid was set and wiped in one event and
  // `GET /accounts/{id}` was never asked. `handleTerm` owns every value change
  // that comes from typing — an id sets the account, anything else clears it
  // (the money rule: no stale id behind a changed box) — and `handlePick` lets
  // only a real pick through. The same two functions as `AccountFinder`'s.
  const pasted = isAccountId(term.trim());
  const idle = !pasted && term.trim().length < MIN_SEARCH_CHARS;
  function handleTerm(next: string): void {
    props.onTermChange?.(next);
    props.onPatch({ fromAccountId: isAccountId(next) ? next.trim() : "" });
  }
  function handlePick(next: string): void {
    if (next !== "") {
      props.onPatch({ fromAccountId: next });
    }
  }
  const accountOptions = search.matches.map((row) => ({
    value: row.id,
    label: accountFinderLabel(row, props.t),
  }));
  // The account already chosen stays nameable while the term is unchanged —
  // the kit shows the chosen option's label, never the id (B14 rule 31).
  if (
    props.draft.fromAccountId !== "" &&
    !accountOptions.some((option) => option.value === props.draft.fromAccountId) &&
    (account !== null || pasted)
  ) {
    accountOptions.unshift({
      value: props.draft.fromAccountId,
      // A pasted id reads as what was pasted until its account loads — never
      // as a uuid the clerk did not type (B14 rule 31 holds: it IS the term).
      label: account !== null ? accountHeadline(account, props.t) : term.trim(),
    });
  }
  return (
    <>
      <Panel as="section">
        <StepIntro
          title={props.t("customers.transfer.step1.title", {
            defaultValue: "The account being sold",
          })}
        >
          {/* ⚠ **THIS READ *"Find the account at the address they are moving
              out of. The customer on it is the customer who ARRIVES at the new
              address"*** — the replaced job, and the sentence that told a clerk
              the wrong thing about what they were doing (`DEF-CUS-5075`). The
              customer on it is the SELLER, and a different person is about to
              take their place. */}
          {props.t("customers.transfer.step1.help", {
            defaultValue: "Find the account whose property has been sold.",
          })}
        </StepIntro>
        {/* ⊕ **ONE CONTROL, NOT TWO — `DEF-CUS-6382`.** This was `AccountFinder`
            — a search box and a separate *Matching account* select, two
            controls for one choice. The kit's remote search select (the one
            Payments uses, B14 rule 43) draws the five states inside one
            panel: typed too little, searching, the search failed, no match,
            the matches. Typing clears a stale choice, which is its money rule. */}
        <RemoteSearchSelectField
          id="trf_account"
          label={props.t("customers.transfer.step1.account", {
            defaultValue: "Account being sold",
          })}
          placeholder={props.t("customers.transfer.step1.findHint", {
            defaultValue: "Number, name or address.",
          })}
          required
          term={term}
          onTermChange={handleTerm}
          status={{
            idle,
            searching: !idle && !pasted && !search.searched && !search.failed,
            searched: search.searched,
            failed: search.failed,
          }}
          options={accountOptions}
          value={props.draft.fromAccountId}
          onChange={handlePick}
          /* The four sentences Payments' combobox already says, in all eleven
             catalogues — the same control, so the same words. */
          words={{
            tooShort: props.t("payments.form.accountTooShort"),
            searching: props.t("payments.form.accountSearching"),
            failed: props.t("payments.form.accountSearchFailed"),
            noMatch: props.t("payments.form.accountNoMatch"),
          }}
        />
        {refusal !== null && (
          // ⊕ `DEF-CUS-6395` — the commit's own refusal, on the step where the
          // account was picked. The step holds until it clears.
          <RefusalStrip data-account-refusal={refusal.code}>
            {refusalText(refusal, props.t)}
          </RefusalStrip>
        )}
        {props.failed && (
          // ⚠ THIS SENTENCE NOW MEANS WHAT IT SAYS. It can only fire for an id
          // that IS one and that this tenant cannot read — never for "you typed
          // something that is not an id", which is DEF-732 exactly.
          <RefusalStrip data-account="unreadable">
            {props.t("customers.transfer.step1.accountFailed", {
              defaultValue:
                "That account could not be read, so nothing below is filled in. Nothing has been written.",
            })}
          </RefusalStrip>
        )}
      </Panel>

      {/* ⛔ **`Stays with you` AND *"Moving house is not a sale. Raise a service
          request."* ARE REMOVED, NOT SHORTENED — `DEF-CUS-6385`, PO 2026-09-23.**
          Both were RATIONALE (why the product works this way), which B14 rule
          33 puts at ZERO words on screen; the PO listed both by name. */}
      {/* ══ THE TWO DRAWN FACT PANELS — `DEF-CUS-5180` ═══════════════════════
          The blueprint's page image (p113) draws step 1 as TWO panels of facts
          side by side with the search: *"The account — and all of it changes
          hands"*, sixteen rows, and *"What is changing hands with it"*,
          twelve. What stood here was ONE panel of six.

          ⚠ **THE TEXT EXTRACT COULD NOT HAVE TOLD ANYONE THIS**, which is the
          PO's 2026-09-13 ruling in one screen: *"When you use images to create
          screens your accuracy is higher; hence dont create screens using only
          Text"*. A vector wireframe flattened to a text layer is a list of
          labels with the panel headings, the grouping and the two-column
          arrangement gone, so six rows and twenty-eight rows read the same.

          ⚠ **SIXTEEN OF THE MISSING ROWS WERE ALREADY IN THE PAYLOAD.** Nothing
          new is fetched: `GET /accounts/{id}` has carried the customer, the
          category, the status, `opened_at`, `autopay`, `paperless`,
          `preferred_language`, the contacts and the mailing address all along
          and this screen asked for none of them. Three more — the floor, the
          floor area and the premises reference — were in metering's
          `unit_detail_dict` and were dropped by `_unit_facts`'s pick on the way
          through; that pick is widened, read-only, in the same change.

          ⚠ **AND THREE DRAWN ROWS ARE SERVED BY NOTHING (`DEF-CUS-5182`).**
          Base charge, billing cycle and the ledger's length have no source for
          this screen — no cycle column on the account, no price on
          `unit_plan`, and nothing counts unbroken months. They are drawn as
          ROWS STATING THEIR ABSENCE rather than left out, because a row nobody
          has asked for and a row somebody forgot to wire look identical when
          both are missing. */}
      {account !== null && (
        <Panel as="section">
          <h4 className="font-heading text-md m-0 mb-2">
            {props.t("customers.transfer.step1.panelA", {
              defaultValue: "The account — and all of it changes hands",
            })}
          </h4>
          <PlainTable>
            <tbody>
              <Fact label={props.t("customers.transfer.fact.accountNumber", { defaultValue: "Account number" })}>
                {/* B14 rule 31 — the NUMBER a clerk reads off a list, never the
                    row's key. `account_no` is null only on a row imported
                    before the tenancy series existed. */}
                {account.account_no ?? <Dash />}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.customerNumber", { defaultValue: "Customer number" })}>
                {/* ⊕ `DEF-CUS-6383` — a dash read as *nothing recorded*; with
                    nobody linked the row now says so (a FACT, ≤ 6 words). */}
                {account.customer_no ??
                  (account.customer == null ? noCustomer(props.t) : <Dash />)}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.seller", { defaultValue: "Seller" })}>
                {/* The drawing calls this row SELLER and not CUSTOMER, and the
                    word is the whole ruling: on a sale the person on the
                    account is the one leaving it. `DEF-CUS-5075`. */}
                {account.customer?.display_name ?? account.name ?? <Dash />}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.customerKind", { defaultValue: "Customer kind" })}>
                {account.customer == null
                  ? noCustomer(props.t)
                  : props.t(`customers.customer.kind.${account.customer.kind}`, {
                      defaultValue: account.customer.kind,
                    })}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.category", { defaultValue: "Category" })}>
                {/* The category's NAME from the catalogue the server publishes
                    (B14 rule 32), and — ⊕ `DEF-CUS-6384` — the account's
                    SUB-CATEGORY beside it, the tenant's own reference data from
                    Settings (`account_subtype_name`). The comment that stood
                    here said `account_subtypes` held ZERO rows; the seed carries
                    13, and it was deleted (hard-won law 1). */}
                {[
                  props.categoryName === undefined || props.categoryName === ""
                    ? null
                    : props.categoryName,
                  account.account_subtype_name ?? null,
                ]
                  .filter((part): part is string => part !== null && part !== "")
                  .join(" · ") || <Dash />}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.status", { defaultValue: "Status" })}>
                {/* The TENANT's own label, which is renameable reference data —
                    never `status`, which is the lookup code (B14 rule 32). */}
                {account.status_name}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.opened", { defaultValue: "Opened" })}>
                {account.opened_at === null ? (
                  <Dash />
                ) : (
                  /* ⚠ **THE ZONE IS NOT READ AND MUST STILL BE PASSED**
                     (`BR-SHL-023`). `opened_at` is a CALENDAR DATE and
                     `formatDate` takes its date-only path for one, deliberately
                     — 03/08/2022 is 03/08/2022 in every tenant, and a `Date()`
                     round-trip through a zone is what turns it into the 2nd for
                     half the world. */
                  formatDate(account.opened_at, "UTC", regional.dateFormat)
                )}
              </Fact>
              <Fact label={props.t("customers.transfer.step1.balance", { defaultValue: "Current balance" })}>
                {/* ⛔ NEVER `$0.00` OVER A NULL. `balance` is the LEDGER's own
                    figure since DEF-127, and null means the books could not be
                    asked — which looks exactly like a settled account if a
                    zero is printed over it. */}
                {account.balance === null ? (
                  <AbsentValue
                    reason={props.t("customers.transfer.step4.balanceAbsent", {
                      defaultValue: "The balance could not be read.",
                    })}
                    tracks="DEF-127"
                  />
                ) : (
                  <MoneyCell
                    amount={account.balance}
                    currency={account.balance_currency ?? account.currency}
                  />
                )}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.depositOnFile", { defaultValue: "Deposit on file" })}>
                {account.deposit_on_file === null ? (
                  <AbsentValue
                    reason={props.t("customers.transfer.step1.depositAbsent", {
                      defaultValue: "No deposit position is recorded on this account.",
                    })}
                  />
                ) : (
                  <MoneyCell amount={account.deposit_on_file} currency={account.currency} />
                )}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.depositInterest", { defaultValue: "Deposit interest" })}>
                {/* ❄️ **WE-7 / GT-23 IS WHY THIS IS NEVER `$0.00`.** BR-CUS-057
                    is a CONFIRMED rule whose accrual is published by nothing, and
                    the frozen pair says the tempting zero *"does not merely lose
                    precision, it serves the principal AS the carried amount"*.
                    On the drawing's own account that is $150.00 shown where
                    $153.50 is held — correct-looking and wrong. */}
                {/* ⚠ **THE OLD SENTENCE ENDED *"what carries across is decided
                    at step 4"* AND THAT HAS BEEN FALSE SINCE `DEF-CUS-5075`.**
                    Step 4 decides nothing: its two elections were removed when
                    `OQ-1252` was answered — *"money follow property - new owner
                    boutght everything property + debt also"* — and that step's
                    own header says it now has none. So the row was sending a
                    clerk to a decision that does not exist, on the screen the
                    Product Owner was reading aloud on 2026-09-20. It was 34
                    words of rationale as well, which B14 rule 33 puts at zero
                    on screen. ⛔ The ❄️ `WE-7` / `GT-23` constraint is
                    UNTOUCHED: this row still never renders `$0.00`, because a
                    zero here serves the principal as the carried amount. */}
                {/* ⊕ `DEF-CUS-6385` — the drawing's own two words. *"Deposit
                    interest is not built yet"* was rationale (rule 33). */}
                <AbsentValue
                  reason={props.t("customers.transfer.fact.notRecorded", {
                    defaultValue: "Not recorded",
                  })}
                  tracks="BR-CUS-057"
                />
              </Fact>
              <Fact label={props.t("customers.transfer.fact.autopay", { defaultValue: "Autopay" })}>
                {/* ⚠ **THE DRAWN VALUE IS `On · bank transfer` AND THE
                    INSTRUMENT IS NOT SERVED.** `autopay` is a boolean on the
                    account; which mandate pays it belongs to payments and
                    reaches this payload through nothing. On or off is the
                    honest half, and naming a tender nobody read would be the
                    same class of invention as a zero over a null. */}
                {onOff(account.autopay, props.t)}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.paperless", { defaultValue: "Paperless billing" })}>
                {/* ⚠ **NEITHER ELECTION TURNS PRINT OFF** — BR-BIL-036 makes
                    print the floor, so this says what the account gets IN
                    ADDITION. `undefined` is a bundle deployed against a server
                    older than CR-052 W4, which is not the same as `false`. */}
                {account.paperless === undefined ? <Dash /> : onOff(account.paperless, props.t)}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.billEmail", { defaultValue: "Bill email" })}>
                {primaryContact(account)?.email ?? <Dash />}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.phone", { defaultValue: "Phone" })}>
                {primaryContact(account)?.phone ?? <Dash />}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.language", { defaultValue: "Preferred language" })}>
                {account.preferred_language ?? <Dash />}
              </Fact>
              <Fact label={props.t("customers.transfer.fact.mailing", { defaultValue: "Mailing address" })}>
                {/* ⚠ **AN ABSENT MAILING ROW IS A FACT, NOT A GAP** — hard rule
                    8's own shape. `customers.addresses` `kind='mailing'` is the
                    one lawful second address in this product, *where the BILL
                    goes*; an account without one is billed at the service
                    address it walks to through its premises, which is what the
                    drawing prints in that cell. `kind='service'` is RETIRED and
                    is not read here. */}
                {mailingLine(account) ?? props.t("customers.transfer.fact.mailingSame", {
                  defaultValue: "Same as service",
                })}
              </Fact>
            </tbody>
          </PlainTable>
        </Panel>
      )}

      {account !== null && (
        <ChangingHandsPanel
          account={account}
          t={props.t}
          period={false}
          preview={props.preview ?? null}
          baseCharge={props.baseCharge ?? null}
          baseCurrency={props.baseCurrency ?? null}
          dateFormat={props.dateFormat}
        />
      )}

      {/* Panel (c) — the drawn `The same customer elsewhere`. THIS ONE IS REAL:
          BR-CUS-054's entity is served, and `customer.accounts` is the
          tenant-scoped "all accounts for this customer" capability the rule
          names.

          ⚠ **THE SECOND ROW IS THE ONE THE PANEL EXISTS FOR.** The blueprint
          draws `Affected by this sale · No — that one is theirs still` beside
          the count, and it is the question a clerk on the phone is actually
          asking. A count on its own invites the opposite answer: a seller with
          three accounts reads as three accounts changing hands, and exactly one
          is. */}
      {account?.customer != null && (
        <Panel as="section">
          <h4 className="font-heading text-md m-0 mb-2">
            {props.t("customers.transfer.step1.panelC", {
              defaultValue: "The same customer elsewhere",
            })}
          </h4>
          <PlainTable>
            <tbody>
              <Fact
                label={props.t("customers.transfer.fact.otherAccounts", {
                  defaultValue: "Other accounts",
                })}
              >
                <span data-other-accounts={String(account.customer.accounts.length - 1)}>
                  {/* B14 rule 31 — the NUMBERS a clerk reads off a list, never
                      the ids beside them in the same payload. */}
                  {account.customer.accounts.length <= 1
                    ? props.t("customers.transfer.fact.noOtherAccounts", { defaultValue: "None" })
                    : `${account.customer.accounts.length - 1} · ${account.customer.accounts
                        .filter((row) => row.id !== account.id)
                        .map((row) => row.account_no)
                        .join(" · ")}`}
                </span>
              </Fact>
              <Fact
                label={props.t("customers.transfer.fact.affected", {
                  defaultValue: "Affected by this sale",
                })}
              >
                {props.t("customers.transfer.fact.notAffected", {
                  defaultValue: "No — that one is theirs still",
                })}
              </Fact>
            </tbody>
          </PlainTable>
        </Panel>
      )}

      {/* ══ THE DRAWN `What this sale will not touch` — six rows ═══════════════
          Absent until 2026-09-13 (`DEF-CUS-5180`). Every row is a STATEMENT OF
          LAW rather than a lookup, which is why it is drawn on the step where a
          clerk is deciding whether to go on: a sale reassigns an account and
          rewrites no record that was already made.

          ⚠ **AND THE FIRST ROW IS HARD RULE 4 ON SCREEN.** An issued bill, a
          payment taken and a journal line may never be updated or deleted; a
          transfer does not, and could not, re-address one. The drawing's own
          sentence is the plainest statement of it in the product — *"a bill is
          a record of what was sent, not a claim about who owes it today"* — so
          it is rendered rather than paraphrased. */}
      <Panel as="section">
        <h4 className="font-heading text-md m-0 mb-2">
          {props.t("customers.transfer.step1.panelNotTouch", {
            defaultValue: "What this sale will not touch",
          })}
        </h4>
        <PlainTable>
          <tbody>
            <Fact
              label={props.t("customers.transfer.notTouch.bills", { defaultValue: "Issued bills" })}
            >
              {props.t("customers.transfer.notTouch.billsValue", {
                defaultValue: "Stay in the seller's name, for ever",
              })}
            </Fact>
            <Fact
              label={props.t("customers.transfer.notTouch.payments", {
                defaultValue: "Payments taken",
              })}
            >
              {props.t("customers.transfer.notTouch.paymentsValue", {
                defaultValue: "Stay as taken",
              })}
            </Fact>
            <Fact
              label={props.t("customers.transfer.notTouch.journal", {
                defaultValue: "Journal entries",
              })}
            >
              {props.t("customers.transfer.notTouch.journalValue", {
                defaultValue: "Stay as posted",
              })}
            </Fact>
            <Fact
              label={props.t("customers.transfer.notTouch.accountNo", {
                defaultValue: "The account number",
              })}
            >
              {props.t("customers.transfer.notTouch.unchanged", { defaultValue: "Unchanged" })}
            </Fact>
            <Fact
              label={props.t("customers.transfer.notTouch.unitMeters", {
                defaultValue: "The unit and meters",
              })}
            >
              {props.t("customers.transfer.notTouch.unchanged", { defaultValue: "Unchanged" })}
            </Fact>
            <Fact
              label={props.t("customers.transfer.notTouch.agreements", {
                defaultValue: "Service agreements",
              })}
            >
              {props.t("customers.transfer.notTouch.unchanged", { defaultValue: "Unchanged" })}
            </Fact>
          </tbody>
        </PlainTable>
      </Panel>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 2 · THE BUYER (`TRF-02.2`) — *"Who is buying it"*
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS REPLACED `FinalReadsStep`, AND THE REPLACEMENT IS THE WHOLE RULING
// (`DEF-CUS-5075`).** That step asked for a MOVE-OUT DATE and drew a register
// table of final readings. Under `BR-CUS-1030` a sale **closes no account and
// opens none**: the meter keeps running on one unbroken account, so there is no
// final read to take and no closing figure to capture. The drawing says so in
// its own dashed block on p114 — *"A FINAL READ, TYPED HERE · There is none,
// and it is not missing. Nothing on a sale records a meter reading: the account
// is not closing, so there is no closing figure to capture."*
//
// What the step asks for instead is the one thing the server refused the whole
// wizard for: **who is buying it.** `set_new_customer` answers
// `422 customers.transfer.buyer_required` without it, at the second of five
// staged writes.
//
// ⚠ **THE CHANGEOVER-READ PANEL STAYS, AND IT IS NOT A CONTRADICTION.** The
// drawing keeps `Field visit — the changeover read` on this very step and says
// what it is for: *"This is where the reading is ARRANGED, and it is not typed
// here."* It raises WORK ORDERS on the same account — a sale creates no second
// account for a job to belong to — and the reading lands later through the
// ordinary reads door. Raising work is not capturing a read.

/** What the buyer search answers, held by the wizard (the step unmounts). */
export interface BuyerSearchState {
  answer: CustomerSearchResult | null;
  pending: boolean;
  failed: boolean;
  dismissed: readonly string[];
  onDismiss: (id: string) => void;
  run: (query: CustomerSearchQuery) => void;
}

/** *Search customer ID*'s question, from what the clerk typed — Move-in's
 *  shape: the kind, the name, and the identifiers of that kind. `null` until
 *  a kind and a name exist. */
export function buyerSearchQuery(buyer: CustomerForm): CustomerSearchQuery | null {
  const kind = buyer.customer_kind.trim();
  if (kind === "" || buyer.full_name.trim() === "") return null;
  const query: CustomerSearchQuery = { kind, name: buyer.full_name.trim() };
  const put = (key: Exclude<keyof CustomerSearchQuery, "kind">, value: string) => {
    if (value.trim() !== "") query[key] = value.trim();
  };
  if (kind === CUSTOMER_KIND_COMPANY) {
    put("tax_id", buyer.tax_id);
  } else {
    put("date_of_birth", buyer.dob);
    put("ssn", buyer.ssn);
    put("driving_licence", buyer.driving_licence);
    put("phone", buyer.phone);
  }
  return query;
}

/**
 * **STEP 2 — THE BUYER**, ⊕ rebuilt from image `07-transfer.png`
 * (`DEF-CUS-10255`, PO 2026-10-18): the seller as the account names them ·
 * *Who is buying* (CF-1's `CustomerWhoPanel`, NO category — it is the
 * seller's account's) · *Identity* with *Search customer ID* and its results
 * table (replacing `CustomerFinder`'s free-text box) · the co-buyer full cards
 * · the documents table · the mailing address block · Move-in's Tax, Discounts
 * and Preferences panels for the buyer — **the seller's exemption and
 * discounts are not copied** — and the field-visit table the step already had.
 *
 * ⚠ **THE FORM IS THE PRIMARY PATH AND THE SEARCH IS BESIDE IT**
 * (`DEF-CUS-6549`, PO 2026-09-24). Nothing is hidden behind the search: a
 * linked customer FILLS the boxes the clerk is looking at and they stay
 * editable; *Unlink* keeps the clerk's typing.
 */
export function BuyerStep(props: {
  draft: TransferDraft;
  account: AccountDetail | null;
  onPatch: (next: Partial<TransferDraft>) => void;
  t: Translator;
  dateFormat?: RegionalDateFormat;
  /** `BR-CUS-1081` §4 — advisory; the one commit refusal it carries is served
   *  here (`DEF-CUS-6395`). */
  preview?: BuyerPreview | null;
  client?: ApiClient;
  /** Red only once Continue has been pressed on this step. */
  fieldVisitShowErrors?: boolean;
  timeZone?: string;
  /** The seller's category by NAME (B14 rule 31), as step 1 shows it. */
  categoryName?: string;
  /** ⊕ `DEF-CUS-10255` — the search, held by the wizard. Optional only for
   *  static-markup cases; the wizard passes it (`G13`). */
  search?: BuyerSearchState;
}) {
  const regional = useRegional(props);
  const { timeZone: regionalZone } = useRegional({});
  const timeZone = props.timeZone ?? regionalZone;
  const draft = props.draft;
  const buyer = draft.buyer;
  const linked = draft.buyerCustomer;
  const shortfall = buyerShortfall(draft);
  const refusal = props.preview?.refusal ?? null;
  const show = props.fieldVisitShowErrors ?? false;
  const company = buyer.customer_kind === CUSTOMER_KIND_COMPANY;
  const query = buyerSearchQuery(buyer);
  const client = props.client ?? api;
  // Move-in's Tax and Discounts read the plan the ACCOUNT is on — the same
  // pricing door, keyed on the account's unit and category.
  const pricingQuery = {
    unitId: props.account?.unit_id ?? "",
    accountType: props.account?.account_type ?? "",
  };
  const pricing = useQuery({
    queryKey: moveInMoneyKeys.pricing(pricingQuery),
    queryFn: () => getMoveInPricing(pricingQuery, client),
    enabled: pricingQuery.unitId !== "" && pricingQuery.accountType !== "",
    retry: false,
  });

  function link(row: CustomerSearchRow): void {
    // The found customer IS the buyer; the boxes fill and stay editable
    // (`DEF-CUS-6549`). The identifiers are withdrawn: a linked buyer rides the
    // commit as `customer_id`, and an SSN typed against them would reach no
    // column at all (`DEF-CUS-6487`'s shape).
    props.onPatch({
      buyerCustomer: row,
      buyer: {
        ...buyer,
        full_name: row.display_name,
        customer_kind: row.kind,
        dob: buyer.dob === "" ? (row.date_of_birth ?? "") : buyer.dob,
        ssn: "",
        driving_licence: "",
        tax_id: "",
      },
    });
  }

  const searchButton =
    props.search === undefined ? undefined : (
      <Button
        data-search-customer-id=""
        disabled={query === null || props.search.pending}
        title={query === null ? props.t("customers.moveIn.customer.match.needKind") : undefined}
        onClick={() => {
          if (query !== null) props.search?.run(query);
        }}
      >
        {props.t("customers.moveIn.customer.search")}
      </Button>
    );
  const matchPanel =
    props.search === undefined ? null : (
      <CustomerMatchPanel
        result={props.search.answer}
        pending={props.search.pending}
        failed={props.search.failed}
        linkedId={linked?.id ?? null}
        linkedRow={linked}
        dismissed={[...props.search.dismissed]}
        onLink={link}
        onUnlink={() => props.onPatch({ buyerCustomer: null })}
        onNotThem={(row) => props.search?.onDismiss(row.id)}
        timeZone={timeZone}
        dateFormat={regional.dateFormat}
      />
    );
  const sellerCategory = props.categoryName ?? null;

  return (
    <div className="flex flex-col gap-6" data-transfer-buyer="">
      {/* The seller, as the account names them — the category the buyer takes
          on comes from here (image 07: *"Category comes from the seller"*). */}
      <Panel as="section" title={props.t("customers.transfer.buyer.seller")} data-transfer-seller="">
        <PlainTable>
          <tbody>
          <Fact label={props.t("customers.transfer.buyer.sellerAccount")}>
            {props.account === null
              ? noCustomer(props.t)
              : [props.account.account_no, primaryContact(props.account)?.full_name]
                  .filter((part) => part !== null && part !== undefined && part !== "")
                  .join(" · ")}
          </Fact>
          <Fact label={props.t("customers.transfer.buyer.sellerCategory")}>
            {sellerCategory === null || sellerCategory === "" ? <Dash /> : sellerCategory}
          </Fact>
          </tbody>
        </PlainTable>
      </Panel>

      <CustomerWhoPanel
        title={props.t("customers.transfer.buyer.whoTitle")}
        customer={buyer}
        onCustomer={(next) => {
          // ⚠ SWITCHING KIND BLANKS WHAT THE NEW KIND IS NOT ASKED FOR
          // (`BR-CUS-1022`), through the shared `clearedForKind`.
          if (next.customer_kind !== buyer.customer_kind) {
            props.onPatch(
              patchBuyerCapture(
                { ...draft, buyer: next },
                { applicant_kind: next.customer_kind, ...clearedForKind(next.customer_kind) },
              ),
            );
            return;
          }
          props.onPatch({ buyer: next });
        }}
        extras={draft.buyerExtras}
        onExtras={(patch) => props.onPatch({ buyerExtras: { ...draft.buyerExtras, ...patch } })}
        showCategory={false}
        companyTrailing={
          searchButton === undefined ? undefined : (
            <>
              <div className="flex justify-end">{searchButton}</div>
              {matchPanel}
            </>
          )
        }
        showErrors={show}
        t={props.t}
        dateFormat={regional.dateFormat}
        timeZone={timeZone}
      />

      {company ? null : (
        <CustomerIdentityPanel
          customer={buyer}
          onCustomer={(next) => props.onPatch({ buyer: next })}
          trailing={searchButton}
          t={props.t}
        >
          {matchPanel}
        </CustomerIdentityPanel>
      )}

      <CoOwnerCards
        kind={company ? "officer" : "co_owner"}
        label="co_buyer"
        enabled={draft.coBuyersOn}
        onEnabledChange={(next) => props.onPatch({ coBuyersOn: next })}
        rows={draft.coBuyers}
        onChange={(rows) => props.onPatch({ coBuyersOn: true, coBuyers: rows })}
        t={props.t}
        dateFormat={regional.dateFormat}
        timeZone={timeZone}
        showErrors={show}
        showPhotoId={false}
      />

      <MoveInDocumentsTable
        rows={draft.buyerDocRows}
        onChange={(rows) => props.onPatch({ buyerDocRows: rows })}
        serviceRequestId=""
        t={props.t}
        client={props.client}
      />

      <MailingAddressBlock
        value={{
          mailing_same: draft.mailingSameAsService,
          mailing_line1: draft.buyerMailing.line1,
          mailing_line2: draft.buyerMailing.line2,
          mailing_city: draft.buyerMailing.city,
          mailing_state: draft.buyerMailing.state,
          mailing_postal_code: draft.buyerMailing.postal_code,
        }}
        onChange={(patch) =>
          props.onPatch({
            ...(patch.mailing_same !== undefined ? { mailingSameAsService: patch.mailing_same } : {}),
            buyerMailing: {
              line1: patch.mailing_line1 ?? draft.buyerMailing.line1,
              line2: patch.mailing_line2 ?? draft.buyerMailing.line2,
              city: patch.mailing_city ?? draft.buyerMailing.city,
              state: patch.mailing_state ?? draft.buyerMailing.state,
              postal_code: patch.mailing_postal_code ?? draft.buyerMailing.postal_code,
            },
          })
        }
        serviceAddress={props.account === null ? "" : (serviceAddressLine(props.account) ?? "")}
        t={props.t}
      />

      {/* Move-in's own three panels, for the BUYER (PO 2026-10-18, *"corect"*).
          They open empty: the seller's exemption and discounts are not copied. */}
      <TaxSection
        own={draft.buyerBilling}
        set={(buyerBilling) => props.onPatch({ buyerBilling })}
        taxes={pricing.data?.plan?.taxes ?? []}
        problems={billingProblems({ ...draft.buyerBilling, planRows: [] })}
        tried={show}
        dateFormat={regional.dateFormat}
        client={client}
        t={props.t}
      />
      <DiscountsSection
        own={draft.buyerBilling}
        set={(buyerBilling) => props.onPatch({ buyerBilling })}
        offered={pricing.data?.plan?.claimable_discounts ?? []}
        preferences={draft.buyerPrefs}
        setPreferences={(buyerPrefs) => props.onPatch({ buyerPrefs })}
        problems={billingProblems({ ...draft.buyerBilling, planRows: [] })}
        tried={show}
        t={props.t}
      />
      <PreferencesSection
        own={draft.buyerBilling}
        set={(buyerBilling) => props.onPatch({ buyerBilling })}
        preferences={draft.buyerPrefs}
        setPreferences={(buyerPrefs) => props.onPatch({ buyerPrefs })}
        client={client}
        t={props.t}
      />

      {linked === null ? buyerMatchSentence(props.preview ?? null, props.t) : null}
      {shortfall !== null ? (
        <RefusalStrip data-buyer-shortfall="">{buyerShortfallText(shortfall, props.t)}</RefusalStrip>
      ) : null}
      {refusal !== null ? (
        // `DEF-CUS-6395` — the commit's buyer-is-the-seller refusal, here.
        <RefusalStrip data-buyer-refusal={refusal.code}>{refusalText(refusal, props.t)}</RefusalStrip>
      ) : null}

      {/* ── `DEF-CUS-6392` · does somebody have to attend? — THE ONE
          FIELD-VISIT TABLE every flow mounts (PO: *"this is correct"*). */}
      <Panel as="section" data-step-content="field-visit">
        <FieldVisitOrders
          flowKind="transfer"
          value={draft.fieldVisit}
          onChange={(fieldVisit) => props.onPatch({ fieldVisit })}
          showErrors={show}
          dateFormat={regional.dateFormat}
          timeZone={timeZone}
          t={props.t}
          client={props.client}
        />
      </Panel>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 3 · THE DATE OF SALE (`TRF-02.3`) — ONE DATE, BECAUSE THERE IS ONE
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS REPLACED `ArrivingStep`, WHICH ASKED WHICH UNIT THE CUSTOMER WAS
// MOVING TO (`DEF-CUS-5075`).** Under `BR-CUS-1030` **the unit does not change
// at all**: a customer moving to another of your addresses is a NEW SERVICE
// REQUEST, which the PO's ruling says in as many words. So there is no target
// unit to pick, no `BR-CUS-017` race to lose, no service-start date and no
// second date to order against the first.
//
// ⚠ **AND NOTHING IS PRORATED.** One unbroken account, one service agreement,
// one billing period: the bill for the period covering the sale is issued to
// whoever owns the account when it is issued. The drawing states it in a red
// box — *"Nothing is prorated at a sale"* — and states the consequence a clerk
// must say out loud: *"The buyer pays for days the seller used."* That follows
// from the debt going with the property, and it is the one thing on this wizard
// a buyer should be told on the phone.

export function SaleDateStep(props: {
  draft: TransferDraft;
  /** ⚠ **THE DRAWN `What changes hands on that day` PANEL NEEDS THE ACCOUNT,
   *  AND THIS STEP HAD NO WAY TO SEE ONE** (`DEF-CUS-5180`). Null while nothing
   *  is chosen and while the read is in flight, which on this step is only
   *  reachable by typing `?step=3` into the bar. */
  account: AccountDetail | null;
  onPatch: (next: Partial<TransferDraft>) => void;
  t: Translator;
  dateFormat: RegionalDateFormat;
  /** ⊕ `DEF-CUS-5182` — the same served facts as step 1 (`DEF-CUS-6382`'s
   *  neighbour, item 14): fixed once, rendered in both places. */
  preview?: TransferAccountPreview | null;
  baseCharge?: string | null;
  baseCurrency?: string | null;
}) {
  return (
    <>
      <Panel as="section">
        <StepIntro
          title={props.t("customers.transfer.step3.title", { defaultValue: "The date of sale" })}
        >
          {props.t("customers.transfer.step3.help", {
            defaultValue: "The day the account changes hands.",
          })}
        </StepIntro>
        <DatePickerField
          id="trf_sold_on"
          label={props.t("customers.transfer.step3.soldOn", { defaultValue: "Date of sale" })}
          dateFormat={props.dateFormat}
          // DEF-CUS-10265 — the product's picker in the tenant's format, never
          // a native date box (PO 2026-10-18, *"any date field … date picker"*).
          regional
          required
          value={props.draft.soldOn}
          onChange={(soldOn) => props.onPatch({ soldOn })}
        />
        {/* B14 rule 11's consequence, and it is the drawn red box. Two
            sentences of six words or fewer — rule 33's cap for a consequence
            stated before an irreversible act. */}
        <RefusalStrip data-no-proration="">
          {props.t("customers.transfer.step3.noProration", {
            defaultValue: "Nothing is prorated at a sale. One period, one bill.",
          })}
        </RefusalStrip>
      </Panel>

      {/* ══ THE DRAWN READ-ONLY PANEL — `DEF-CUS-5180` ══════════════════════
          The blueprint (p115) draws twelve rows under the date field headed
          *"What changes hands on that day"*, and the sentence beneath them is
          the reason it is drawn at all: *"Read-only, and that is the point.
          None of this is chosen on a sale."* The step had the date and nothing
          the date applies to.

          ⚠ **THE SAME COMPONENT AS STEP 1's SECOND PANEL, DELIBERATELY.** The
          drawing shows the same facts twice because the two steps ask different
          questions of them; a second copy of the rows is how the two answers
          start to differ. */}
      {props.account !== null && (
        <ChangingHandsPanel
          account={props.account}
          t={props.t}
          period
          preview={props.preview ?? null}
          baseCharge={props.baseCharge ?? null}
          baseCurrency={props.baseCurrency ?? null}
          dateFormat={props.dateFormat}
        />
      )}

      <Panel as="section">
        <h4 className="font-heading text-md m-0 mb-2">
          {props.t("customers.transfer.step3.doesTitle", { defaultValue: "What the date does" })}
        </h4>
        <Note className="max-w-measure" data-date-does="">
          {props.t("customers.transfer.step3.doesShort", {
            defaultValue: "The buyer owns the account then.",
          })}
        </Note>
        {/* ⚠ **THE SENTENCE A CLERK HAS TO SAY OUT LOUD.** The drawing puts it
            in the danger tier for a reason: it is the one fact on this wizard a
            buyer will dispute later if nobody told them. */}
        <RefusalStrip data-buyer-pays-sellers-days="">
          {props.t("customers.transfer.step3.buyerPays", {
            defaultValue: "The buyer pays for days the seller used.",
          })}
        </RefusalStrip>
      </Panel>

      {/* ⛔ *"What it does not do · Nothing closes and nothing starts."* is
          removed — RATIONALE, B14 rule 33, and named by the PO (`DEF-CUS-6385`). */}
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 4 · WHAT THE BUYER TAKES ON (`TRF-02.4`)
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS STEP USED TO HAVE TWO SWITCHES AND NOW HAS NONE (`DEF-CUS-5075`).**
// `depositCarry` and `arrearsFollow` were a clerk's elections because four
// signed rules disagreed and nobody had ruled. **`OQ-1252` was answered inside
// the hour on 2026-09-01** — PO, verbatim: *"money follow property - new owner
// boutght everything property + debt also"* — so a box for a clerk to clear
// would be a control that can reverse a PO ruling. `acknowledge_money` reads no
// key from the plan any more, and the drawing's own panel is headed *"Why there
// is nothing to decide here"*.
//
// ⚠ **AND NOTHING MOVES, WHICH IS WHY IT COSTS ONE LINE.** The account carries
// its own ledger and the account is not going anywhere, so the balance never
// moves because the thing it sits on never moves. What the buyer takes on is
// the balance and the deposit **as they stand** — figures recorded at the
// moment of sale so what was taken on is on the record.
//
// ⚠ **THE DEPOSIT-INTEREST ABSENCE IS UNCHANGED AND IS NOT A FINDING.**
// `BR-CUS-057` is signed and its engine is unbuilt, so the interest renders as
// *not recorded* and never as `$0.00` — a zero would be a claim. ❄️ `WE-7`
// freezes `$3.50` on a $150 deposit held 14 months and `GT-61` freezes `$22.25`
// on 89 months; both are FROZEN figures this product does not compute, and the
// consequence runs against the customer. Registered, deliberate, and not to be
// filed again.

export function TakeOnStep(props: {
  draft: TransferDraft;
  account: AccountDetail | null;
  onPatch: (next: Partial<TransferDraft>) => void;
  /** The drawn `As it stands on <date>` heading reads the SALE's date through
   *  the one formatter, so it cannot disagree with step 3's field. */
  dateFormat: RegionalDateFormat;
  t: Translator;
}) {
  const account = props.account;
  return (
    <>
      <Panel as="section">
        {/* ⛔ The help line (*"The debt goes with the property. Nothing moves
            and nothing is refunded."*) is removed: its first half is the red
            line below, its second is rationale (`DEF-CUS-6385`). */}
        <StepIntro
          title={props.t("customers.transfer.step4.title", {
            defaultValue: "What the buyer takes on",
          })}
        />
        {/* ⚠ **THE DRAWN CARD IS HEADED WITH THE DATE THE FIGURES ARE AS AT**
            (`DEF-CUS-5180`). The blueprint (p116) writes *"As it stands on
            05/09/2026"* over the three rows, and the date is the sale's own —
            not today's. It matters because the money is recorded AT THE MOMENT
            OF SALE and a buyer reading a figure wants to know which day it
            belongs to. Before the date is typed there is no such day, so the
            heading says that instead of guessing one. */}
        <p className="text-md m-0 mb-2" data-as-at="">
          {props.draft.soldOn === ""
            ? props.t("customers.transfer.step4.asAtUnset", {
                defaultValue: "As it stands today. Set the sale date first.",
              })
            : props.t("customers.transfer.step4.asAt", {
                defaultValue: "As it stands on {{date}}",
                date: formatDate(props.draft.soldOn, "UTC", props.dateFormat),
              })}
        </p>
        <PlainTable>
          <tbody>
            <tr>
              <th scope="row">
                {props.t("customers.transfer.step4.balance", {
                  defaultValue: "Account balance",
                })}
              </th>
              <td>
                {/* ⚠ **THE SERVER'S FIGURE, AND IT IS A RUNNING TOTAL RATHER
                    THAN A RE-DERIVED ONE.** The drawing says so itself: it is
                    what every other screen shows and what the buyer takes on,
                    *"but it is a cache, and this screen says so instead of
                    implying an audit"*. Nothing is summed in a browser. */}
                {account?.balance == null ? (
                  <AbsentValue
                    reason={props.t("customers.transfer.step4.balanceAbsent", {
                      defaultValue: "The balance could not be read.",
                    })}
                  />
                ) : (
                  <MoneyCell amount={account.balance} currency={account.currency} />
                )}
              </td>
            </tr>
            <tr>
              <th scope="row">
                {props.t("customers.transfer.step4.principal", {
                  defaultValue: "Deposit on file",
                })}
              </th>
              <td>
                {account?.deposit_on_file == null ? (
                  <AbsentValue
                    reason={props.t("customers.transfer.step4.principalAbsent", {
                      defaultValue: "No deposit position is recorded on this account.",
                    })}
                  />
                ) : (
                  <MoneyCell amount={account.deposit_on_file} currency={account.currency} />
                )}
              </td>
            </tr>
            <tr>
              <th scope="row">
                {props.t("customers.transfer.step4.interest", {
                  defaultValue: "Deposit interest earned",
                })}
              </th>
              <td>
                {/* ⛔ BR-CUS-057 IS CONFIRMED AND ITS ENGINE IS UNBUILT. Never
                    `$0.00` over it — that would be a claim, and the money runs
                    against the customer. */}
                <AbsentValue
                  reason={props.t("customers.transfer.fact.notRecorded", {
                    defaultValue: "Not recorded",
                  })}
                  tracks="BR-CUS-057"
                />
              </td>
            </tr>
            <tr data-taken-on="">
              <th scope="row">
                {props.t("customers.transfer.step4.takenOn", {
                  defaultValue: "Taken on by the buyer",
                })}
              </th>
              <td>
                {/* ⚠ **THIS IS THE BALANCE AND IT IS NOT A SUM** (`DEF-CUS-5180`).
                    The drawing rules a line above it and sets it in bold, which
                    reads as a total — and a total of the three rows above would
                    be the balance PLUS the deposit, which is not what the buyer
                    takes on and is not what any of the four signed rules says.
                    `BR-CUS-1030`: the debt goes with the property and the
                    deposit does not move, because the account it sits on does
                    not move. So this row restates the balance under the name
                    the clerk says out loud, and adds nothing.

                    ⛔ **AND IT MUST NOT FALL BACK TO ZERO.** Where the books
                    could not be asked, the row a clerk would read as *"they owe
                    nothing"* is the one figure this screen may never invent
                    (DEF-127, CLAUDE.md hard rule 2). */}
                {account?.balance == null ? (
                  <AbsentValue
                    reason={props.t("customers.transfer.step4.balanceAbsent", {
                      defaultValue: "The balance could not be read.",
                    })}
                  />
                ) : (
                  <MoneyCell amount={account.balance} currency={account.currency} />
                )}
              </td>
            </tr>
          </tbody>
        </PlainTable>
        {/* B14 rule 11, and the drawing's own red line. */}
        <RefusalStrip data-debt-follows-property="">
          {props.t("customers.transfer.step4.debtFollows", {
            defaultValue: "The debt goes with the property.",
          })}
        </RefusalStrip>
      </Panel>

      <Panel as="section">
        <h4 className="font-heading text-md m-0 mb-2">
          {props.t("customers.transfer.step4.feesTitle", {
            defaultValue: "Fees on this sale",
          })}
        </h4>
        {/* ⛔ **THERE IS NO CHANGE-OF-OWNERSHIP FEE, AND THE DRAWN REASON IS
            HALF WRONG — CORRECTED HERE RATHER THAN COPIED.** The drawing says
            *"no rule sets one, NO TABLE HOLDS ONE, and no door would take the
            money"*. Measured on `brazosbend` 2026-09-12: the seeded catalogue
            DOES hold `TRANSFER — Account transfer fee`. What it does not hold is
            an AMOUNT (`charge_code_amounts` has no row for it). So the absence
            is real and its stated cause was not, and a lane building the fee
            must look for the amount rather than for the code. */}
        <p className="text-md max-w-measure m-0 text-neutral-700" role="note" data-fee="none">
          {props.t("customers.transfer.step4.noFeeShort", {
            defaultValue: "No fee is charged.",
          })}
        </p>
      </Panel>

      <Panel as="section">
        <h4 className="font-heading text-md m-0 mb-2">
          {props.t("customers.transfer.step4.beforeTitle", {
            defaultValue: "Before you continue",
          })}
        </h4>
        {/* ⚠ **IT RECORDS THAT THE FIGURE WAS SHOWN, NOT THAT THE BUYER AGREED
            WITH IT** — the drawing's own words, and the distinction is the
            point: a clerk can confirm what they did and cannot confirm what
            somebody else thought. ⚠ It is NOT a gate. Whether the buyer must be
            shown what they are taking on, and where, has never been ruled — the
            drawing says so — so refusing the step on it would invent a rule. */}
        <CheckboxField
          id="trf_shown_to_buyer"
          label={props.t("customers.transfer.step4.shown", {
            defaultValue: "I have shown this to the buyer",
          })}
          checked={props.draft.shownToBuyer}
          onChange={(shownToBuyer) => props.onPatch({ shownToBuyer })}
        />
        {/* `CheckboxField` carries no `help` slot, so the sentence sits beside
            it rather than a second checkbox component being added to the kit. */}
        <Note className="max-w-measure">
          {props.t("customers.transfer.step4.shownHelp", {
            defaultValue: "Recorded with the sale.",
          })}
        </Note>
      </Panel>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 5 · REVIEW — ONE ACCOUNT, ONE NEW OWNER (`TRF-02.5`)
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **EVERY ROW OF THIS REVIEW DESCRIBED THE REPLACED JOB (`DEF-CUS-5075`).**
// It read `Closing` / `Opening` / `Deposit — Moves, nothing refunded` /
// `Arrear — Follows to the new account` / `Account state — Closed, once the
// final bill settles`, and it carried a `Both or neither` banner about *"one
// address closing and one opening"*. **Nothing closes at a sale and nothing
// opens**, no deposit moves because the account it sits on does not move, and
// the arrear is not an election. A clerk reading that review and pressing the
// commit would have been told, by the screen, that an account was about to
// close — and then refused by the server for a buyer nobody had been asked for.
//
// The drawn review is `The account being sold` · `The buyer` · `The date` ·
// `The money` · `What will happen when you confirm`, and the last of those is
// B14 rule 11's consequence preview before an irreversible act.

export function TransferReviewStep(props: {
  draft: TransferDraft;
  account: AccountDetail | null;
  /** ⊕ the step-1 preview: the seller, and whether the account is the
   *  premises' MASTER account (T2 decides the owner line on that). */
  preview?: TransferAccountPreview | null;
  t: Translator;
  dateFormat: RegionalDateFormat;
  timeZone?: string;
  /** `DEF-CUS-6392` — the field-visit table's `review` mode reads Work's names. */
  client?: ApiClient;
}) {
  // DEF-SHL-3964: the tenant's own format, never a hand-written fallback (DEF-SHL-9122).
  const regional = useRegional(props);
  const buyer = props.draft.buyer;
  const linked = props.draft.buyerCustomer;
  const preview = props.preview ?? null;
  const noDate = props.t("customers.transfer.step5.noDate", { defaultValue: "no date set" });
  const buyerName = linked !== null ? linked.display_name : buyer.full_name;
  const sellerName =
    preview?.seller?.name ?? preview?.seller_name ?? props.account?.name ?? null;
  const sellerEmail = props.account === null ? null : (primaryContact(props.account)?.email ?? null);
  const buyerEmail = buyer.email.trim() === "" ? null : buyer.email.trim();
  const buyerPhone = buyer.phone.trim() === "" ? null : buyer.phone.trim();
  const mailingGiven =
    !props.draft.mailingSameAsService && props.draft.buyerMailing.line1.trim() !== "";
  const mailingLineText = [
    props.draft.buyerMailing.line1,
    props.draft.buyerMailing.line2,
    props.draft.buyerMailing.city,
    [props.draft.buyerMailing.state, props.draft.buyerMailing.postal_code]
      .filter((part) => part.trim() !== "")
      .join(" "),
  ]
    .map((part) => part.trim())
    .filter((part) => part !== "")
    .join(", ");
  // ⊕ DEF-CUS-10264 — every row below reads what the COMMIT sends
  // (`buyerAccountPayload`), so Review cannot describe a sale the server will
  // not make. The co-buyers are the step's cards; the contact-only
  // co-applicant is the older shape and is read only when no card is.
  const extras = buyerAccountPayload(props.draft) ?? {};
  const coBuyerNames = props.draft.coBuyersOn
    ? props.draft.coBuyers.map((card) => card.full_name.trim()).filter((name) => name !== "")
    : [];
  const coApplicant =
    coBuyerNames.length > 0
      ? coBuyerNames.join(", ")
      : props.draft.buyerCapture.add_co_applicant
        ? props.draft.buyerCapture.co_applicant_name.trim()
        : "";
  const documents =
    props.draft.buyerDocuments.length +
    (Array.isArray(extras.documents) ? extras.documents.length : 0);
  const exemption = extras.tax_exemption as { certificate_ref?: string } | undefined;
  const claims = Array.isArray(extras.discount_claims) ? extras.discount_claims.length : 0;
  const preferenceWords = [
    extras.paperless === true ? props.t("customers.moveIn.review.paperless") : "",
    extras.sms_reminders === true ? props.t("customers.moveIn.review.textReminders") : "",
    extras.autopay === true ? props.t("customers.moveIn.review.autopay") : "",
  ].filter((word) => word !== "");
  const row = (label: string, value: ReactNode, attr?: string) => (
    <tr data-review={attr}>
      <th scope="row">{label}</th>
      <td>{value}</td>
    </tr>
  );
  const absent = (key: string, fallback: string) => (
    <AbsentValue reason={props.t(key, { defaultValue: fallback })} />
  );
  return (
    <>
      <Panel as="section">
        {/* ⛔ *"Nothing closes and nothing opens. The customer changes."* was
            the help line here — rationale (`DEF-CUS-6385`). */}
        <StepIntro
          title={props.t("customers.transfer.step5.title", {
            defaultValue: "One account, one new owner",
          })}
        />
        <PlainTable>
          <tbody>
            {row(
              props.t("customers.transfer.step5.accountSold", { defaultValue: "The account being sold" }),
              props.account?.account_no ??
                props.t("customers.transfer.step5.accountUnread", { defaultValue: "not read yet" }),
            )}
            {row(
              props.t("customers.transfer.fact.seller", { defaultValue: "Seller" }),
              sellerName ?? <Dash />,
              "seller",
            )}
            {row(
              props.t("customers.transfer.step5.buyer", { defaultValue: "The buyer" }),
              buyerName === ""
                ? props.t("customers.transfer.step5.buyerMissing", { defaultValue: "not named yet" })
                : buyerName,
              "buyer",
            )}
            {row(
              props.t("customers.transfer.fact.customerNumber", { defaultValue: "Customer number" }),
              linked !== null
                ? (linked.customer_no ?? <Dash />)
                : props.t("customers.transfer.step5.newNumber", {
                    defaultValue: "Issued at the sale",
                  }),
              "buyer-number",
            )}
            {row(
              props.t("customers.transfer.step5.identifier", { defaultValue: "Identifier given" }),
              /* ⚠ WHICH identifier, NEVER THE VALUE (`BR-CUS-1020`). A linked
                 buyer presents none: the customer on file is the evidence. */
              linked !== null
                ? props.t("customers.transfer.step5.onFile", { defaultValue: "Customer on file" })
                : buyer.customer_kind === CUSTOMER_KIND_COMPANY && buyer.tax_id.trim() !== ""
                  ? props.t("customers.newAccount.field.taxId", { defaultValue: "Tax ID" })
                  : buyer.ssn.trim() !== ""
                    ? props.t("customers.newAccount.field.ssn", { defaultValue: "Social Security number" })
                    : buyer.driving_licence.trim() !== ""
                      ? props.t("customers.newAccount.field.drivingLicence", {
                          defaultValue: "Driving licence",
                        })
                      : buyer.phone.trim() !== ""
                        ? props.t("customers.account.field.phone", { defaultValue: "Phone" })
                        : props.t("customers.transfer.step5.noIdentifier", { defaultValue: "none given" }),
            )}
            {row(
              props.t("customers.transfer.step5.saleDate", { defaultValue: "Date of sale" }),
              props.draft.soldOn === ""
                ? noDate
                : formatDate(props.draft.soldOn, regional.timeZone, regional.dateFormat),
            )}
            {row(
              props.t("customers.transfer.step4.balance", { defaultValue: "Account balance" }),
              props.account?.balance == null ? (
                absent("customers.transfer.step4.balanceAbsent", "The balance could not be read.")
              ) : (
                <MoneyCell amount={props.account.balance} currency={props.account.currency} />
              ),
            )}
            {row(
              props.t("customers.account.field.mailingAddress", { defaultValue: "Mailing address" }),
              mailingGiven
                ? mailingLineText
                : props.t("customers.transfer.step2.sameAsService", {
                    defaultValue: "Same as service address",
                  }),
              "mailing",
            )}
            {row(
              props.t("customers.transfer.step5.coApplicant", { defaultValue: "Co-applicant" }),
              coApplicant === ""
                ? props.t("customers.transfer.fact.noOtherAccounts", { defaultValue: "None" })
                : coApplicant,
              "co-applicant",
            )}
            {row(
              props.t("customers.newConnect.step1.documents", { defaultValue: "Documents" }),
              documents === 0
                ? props.t("customers.transfer.fact.noOtherAccounts", { defaultValue: "None" })
                : props.t("customers.transfer.step5.documentsCount", {
                    defaultValue: "{{count}} to file",
                    count: documents,
                  }),
              "documents",
            )}
            {row(
              props.t("customers.moveIn.review.tax"),
              exemption === undefined
                ? props.t("customers.moveIn.review.notExempt")
                : [props.t("customers.moveIn.review.exempt"), exemption.certificate_ref ?? ""]
                    .filter((part) => part !== "")
                    .join(" · "),
              "tax",
            )}
            {row(
              props.t("customers.moveIn.review.discounts"),
              claims === 0
                ? props.t("customers.moveIn.review.none")
                : props.t("customers.transfer.step5.discountsCount", { count: claims }),
              "discounts",
            )}
            {row(
              props.t("customers.moveIn.review.preferences"),
              preferenceWords.length === 0
                ? props.t("customers.moveIn.review.none")
                : preferenceWords.join(" · "),
              "preferences",
            )}
            {row(
              props.t("customers.transfer.step5.shownToBuyer", { defaultValue: "Shown to the buyer" }),
              props.draft.shownToBuyer
                ? props.t("customers.transfer.step5.shownYes", { defaultValue: "Yes" })
                : props.t("customers.transfer.step5.shownNo", { defaultValue: "Not recorded" }),
            )}
          </tbody>
        </PlainTable>
      </Panel>

      {/* B14 rule 11 — the consequence preview before an irreversible commit.
          Each line is one thing the commit does, at rule 33's six-word cap, and
          each is TRUE of this sale (`DEF-CUS-6393` T3 · `DEF-CUS-6394` T2 ·
          `DEF-CUS-6391` T4 · `DEF-CUS-6387`). ⛔ *"All five writes land
          together, or none does"* (rationale), *"Autopay and the bill email
          stay the seller's"* and *"The property's owner record still wants
          updating by hand"* (both no longer true) are removed. */}
      <Panel as="section" accent>
        <h4 className="font-heading text-md m-0 mb-1" data-consequence="one-transaction">
          {props.t("customers.transfer.step5.willHappen", { defaultValue: "What this will do" })}
        </h4>
        <ul className="ml-4 list-disc">
          <li className="text-md" data-will="customer">
            {props.t("customers.transfer.step5.willCustomer", {
              defaultValue: "The buyer becomes the customer.",
            })}
          </li>
          <li className="text-md" data-will="seller">
            {preview?.seller === null
              ? props.t("customers.transfer.step5.willSellerByName", {
                  defaultValue: "The seller is recorded by name.",
                })
              : props.t("customers.transfer.step5.willSellerEnded", {
                  defaultValue: "The seller's link is ended.",
                })}
          </li>
          <li className="text-md" data-will="money">
            {/* ⛔ `DEF-CUS-6430`. This line read *"The balance and deposit are
                recorded as they stand"* — and the day-of-sale figures are computed at commit and
                stored on no row (`transfer_reads.SALE_FIGURE_NOT_STORED`); the
                only copy is the audit row, which is pruned (hard rule 4 forbids
                calling it a record). What IS true is BR-CUS-085: they go with
                the account. */}
            {props.t("customers.transfer.step5.willMoneyFollows", {
              defaultValue: "Balance and deposit move with it.",
            })}
          </li>
          <li className="text-md" data-will="seller-reach">
            {props.t("customers.transfer.step5.willSellerReach", {
              defaultValue: "Seller's email, phone and autopay removed.",
            })}
          </li>
          <li className="text-md" data-will="bills">
            {mailingGiven
              ? props.t("customers.transfer.step5.willBillsMailing", {
                  defaultValue: "Bills go to the mailing address.",
                })
              : props.t("customers.transfer.step5.willBillsService", {
                  defaultValue: "Bills go to the service address.",
                })}
          </li>
          <li className="text-md" data-will="owner">
            {preview?.is_master === true
              ? props.t("customers.transfer.step5.willOwnerMoves", {
                  defaultValue: "The buyer becomes the property's owner.",
                })
              : props.t("customers.transfer.step5.willOwnerStays", {
                  defaultValue: "The property's owner stays the same.",
                })}
          </li>
          {coApplicant === "" ? null : (
            <li className="text-md" data-will="co-applicant">
              {props.t("customers.transfer.step5.willCoApplicant", {
                defaultValue: "{{name}} is stored as co-applicant.",
                name: coApplicant,
              })}
            </li>
          )}
          {documents === 0 ? null : (
            <li className="text-md" data-will="documents">
              {props.t("customers.transfer.step5.willDocuments", {
                defaultValue: "{{count}} documents are filed.",
                count: documents,
              })}
            </li>
          )}
        </ul>
      </Panel>

      {/* `DEF-CUS-6392` — the orders the commit will raise, as step 2 drew
          them, or *No visit needed*. Nothing is raised before the commit. */}
      {props.draft.fieldVisit.none || props.draft.fieldVisit.rows.length > 0 ? (
        <Panel as="section" data-review="field-visit">
          <FieldVisitOrders
            flowKind="transfer"
            mode="review"
            value={props.draft.fieldVisit}
            dateFormat={props.dateFormat}
            timeZone={regional.timeZone}
            t={props.t}
            client={props.client}
          />
        </Panel>
      ) : null}

      {/* ══ WHAT GOES OUT — `DEF-CUS-5949`, PO 2026-09-23 ═══════════════════════
          *"Show and SEND the messages the buyer and the seller get"*. The commit
          QUEUES these three (`transfers._queue_sale_messages`) in the utility's
          own language (`OQ-CUS-12619`). ⚠ **"Nobody is told about this sale"
          WAS FALSE AND IS GONE:** the sale has queued the buyer's and the
          seller's letters since 2026-09-20. ⚠ **QUEUED IS NOT SENT, AND THE
          COLUMN SAYS QUEUED** — delivery happens when the utility's email and
          text channels are connected, and no screen may claim a send that did
          not happen. The meter-visit text goes only when a visit is asked for.
          The drawing's per-row SEND ticks and TEMPLATE picker are not drawn:
          nothing on the server would read them (hard-won law 2). */}
      <Panel as="section">
        <h4 className="font-heading text-md m-0 mb-2">
          {props.t("customers.transfer.step5.outTitle", { defaultValue: "What goes out" })}
        </h4>
        <PlainTable data-messages="">
          <thead>
            <tr>
              <th scope="col">{props.t("customers.transfer.msg.col.says", { defaultValue: "What it says" })}</th>
              <th scope="col">{props.t("customers.transfer.msg.col.to", { defaultValue: "To" })}</th>
              <th scope="col">{props.t("customers.transfer.msg.col.channel", { defaultValue: "Channel" })}</th>
              <th scope="col">{props.t("customers.transfer.msg.col.address", { defaultValue: "Sent to" })}</th>
              <th scope="col">{props.t("customers.transfer.msg.col.when", { defaultValue: "When" })}</th>
            </tr>
          </thead>
          <tbody>
            <tr data-message="transfer_to_buyer">
              <td>{props.t("customers.transfer.msg.toBuyer", { defaultValue: "The account is now yours" })}</td>
              <td>{buyerName === "" ? <Dash /> : buyerName}</td>
              <td>{props.t("customers.transfer.msg.email", { defaultValue: "Email" })}</td>
              <td>{buyerEmail ?? absent("customers.transfer.msg.noEmail", "No email given")}</td>
              <td>{props.t("customers.transfer.msg.queued", { defaultValue: "Queued on confirm" })}</td>
            </tr>
            {props.draft.fieldVisit.none || props.draft.fieldVisit.rows.length === 0 ? null : (
              <tr data-message="transfer_field_visit_sms">
                <td>{props.t("customers.transfer.msg.visit", { defaultValue: "Someone will read the meter" })}</td>
                <td>{buyerName === "" ? <Dash /> : buyerName}</td>
                <td>{props.t("customers.transfer.msg.text", { defaultValue: "Text" })}</td>
                <td>{buyerPhone ?? absent("customers.transfer.msg.noPhone", "No phone given")}</td>
                <td>{props.t("customers.transfer.msg.queued", { defaultValue: "Queued on confirm" })}</td>
              </tr>
            )}
            <tr data-message="transfer_to_seller">
              <td>{props.t("customers.transfer.msg.toSeller", { defaultValue: "The account is no longer yours" })}</td>
              <td>{sellerName ?? <Dash />}</td>
              <td>{props.t("customers.transfer.msg.email", { defaultValue: "Email" })}</td>
              <td>{sellerEmail ?? absent("customers.transfer.msg.noEmailOnFile", "No email on file")}</td>
              <td>{props.t("customers.transfer.msg.queued", { defaultValue: "Queued on confirm" })}</td>
            </tr>
          </tbody>
        </PlainTable>
      </Panel>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE DONE PANEL
// ══════════════════════════════════════════════════════════════════════════

export function TransferDone(props: {
  record: TransferRecord;
  /** `DEF-CUS-6390` — how many of the buyer's documents were filed. */
  documents?: { filed: number; unfiled: number } | null;
  t: Translator;
  onDone: () => void;
  /** `DEF-CUS-6392` — the field-visit table as step 2 held it; with
   *  `record.work_orders` it renders `live` (real numbers, status from Work). */
  fieldVisit?: FieldVisitValue;
  dateFormat?: RegionalDateFormat;
  timeZone?: string;
  client?: ApiClient;
}) {
  // DEF-SHL-3964: the tenant's own format, never a hand-written fallback (DEF-SHL-9122).
  const regional = useRegional(props);
  const record = props.record;
  const messages = record.messages ?? [];
  const owner = record.premises_owner ?? null;
  const messageWord = (template: string | null): string =>
    template === "transfer_to_seller"
      ? props.t("customers.transfer.msg.toSeller", { defaultValue: "The account is no longer yours" })
      : template === "transfer_field_visit_sms"
        ? props.t("customers.transfer.msg.visit", { defaultValue: "Someone will read the meter" })
        : props.t("customers.transfer.msg.toBuyer", { defaultValue: "The account is now yours" });
  return (
    <div data-screen={TRANSFER_WIZARD_SCREEN} data-transfer-done="">
      <Panel as="section">
        <h2 className="font-heading text-h4 m-0 mb-2">
          {props.t("customers.transfer.done.title", { defaultValue: "The sale is recorded" })}
        </h2>
        <PlainTable>
          <tbody>
            <tr>
              <th scope="row">{props.t("customers.transfer.done.account", { defaultValue: "Account" })}</th>
              {/* The NUMBER, never the id — B14 rule 31. */}
              <td>{record.from_account_no ?? ""}</td>
            </tr>
            <tr>
              <th scope="row">{props.t("customers.transfer.done.newOwner", { defaultValue: "New owner" })}</th>
              <td data-done="buyer">
                {record.reassignment?.to_customer_name ??
                  props.t("customers.transfer.done.ownerUnread", { defaultValue: "recorded" })}
              </td>
            </tr>
            <tr>
              <th scope="row">{props.t("customers.transfer.fact.seller", { defaultValue: "Seller" })}</th>
              <td data-done="seller">{record.seller_name ?? <Dash />}</td>
            </tr>
            {owner === null ? null : (
              <tr>
                <th scope="row">
                  {props.t("customers.transfer.done.propertyOwner", { defaultValue: "Property owner" })}
                </th>
                <td data-done="owner" data-owner-state={owner.state}>
                  {owner.state === "moved"
                    ? props.t("customers.transfer.done.ownerMoved", { defaultValue: "Now the buyer" })
                    : owner.state === "not_moved"
                      ? props.t("customers.transfer.done.ownerNotMoved", {
                          defaultValue: "Not moved. Set it on Premises.",
                        })
                      : props.t("customers.transfer.done.ownerSame", { defaultValue: "Unchanged" })}
                </td>
              </tr>
            )}
            {props.documents == null ? null : (
              <tr>
                <th scope="row">{props.t("customers.newConnect.step1.documents", { defaultValue: "Documents" })}</th>
                <td data-done="documents">
                  {props.t("customers.transfer.done.documentsFiled", {
                    defaultValue: "{{filed}} filed, {{unfiled}} not filed",
                    filed: props.documents.filed,
                    unfiled: props.documents.unfiled,
                  })}
                </td>
              </tr>
            )}
          </tbody>
        </PlainTable>
        {messages.length === 0 ? null : (
          <>
            <h4 className="font-heading text-md m-0 mt-4 mb-2">
              {props.t("customers.transfer.step5.outTitle", { defaultValue: "What goes out" })}
            </h4>
            <PlainTable data-done-messages="">
              <tbody>
                {messages.map((message, index) => (
                  <tr key={`${message.template_code ?? "message"}-${index}`}>
                    <th scope="row">{messageWord(message.template_code)}</th>
                    <td>
                      {/* QUEUED is the truth this product can state; a row with
                          no address says where it could not go. */}
                      {message.code.endsWith("queued") && message.address !== null
                        ? props.t("customers.transfer.done.msgQueued", {
                            defaultValue: "Queued to {{address}}",
                            address: message.address,
                          })
                        : message.code.endsWith("queued")
                          ? props.t("customers.transfer.done.msgNoAddress", {
                              defaultValue: "Queued. No address to send to.",
                            })
                          : props.t("customers.transfer.done.msgNotQueued", {
                              defaultValue: "Could not be queued.",
                            })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </>
        )}
        {/* `DEF-CUS-6392` — the orders the sale raised: the real number links to
            each, and STATUS and ASSIGNED TO are read from Work, never copied. */}
        {(record.work_orders ?? []).length > 0 || props.fieldVisit?.none === true ? (
          <div className="mt-4" data-done="field-visit">
            <FieldVisitOrders
              flowKind="transfer"
              mode="live"
              value={props.fieldVisit ?? emptyFieldVisit()}
              raised={(record.work_orders ?? []) as RaisedWorkOrderRef[]}
              dateFormat={regional.dateFormat}
              timeZone={regional.timeZone}
              t={props.t}
              client={props.client}
            />
          </div>
        ) : null}
        <div className="mt-4">
          <Button variant="primary" onClick={props.onDone}>
            {props.t("customers.transfer.done.back", { defaultValue: "Back to transfers" })}
          </Button>
        </div>
      </Panel>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-029 (EP-CUS-10, written by this lane — hard-won law 8) ·
//         B18 §5.7.7 `TRF-02.1`…`TRF-02.5` · BR-CUS-017 · BR-CUS-030 ·
//         BR-CUS-023 · BR-CUS-024 · BR-CUS-054 · BR-CUS-057 · BR-CUS-086 ·
//         BR-CUS-102 ·
//         BR-SHL-018/019/020/025/046/047 · ❄️ WE-7 / GT-23 · OQ-365 ·
//         DEF-127 · DEF-650 · DEF-692 · apps/customers/transfers.py
// generated: 2026-08-25 by lane W7WIZ
// amended: 2026-08-26 by lane SCREENVOICE — **DEF-731 (widened)**. Step 1 met a
//         clerk with THREE RED PANELS saying *"is not published by any endpoint
//         this screen can read"*. Two faults: the VOICE, and the TONE — an
//         absence is not an error, and `RefusalStrip` is BR-SHL-020's server
//         refusal. All five absence strips (steps 1, 2, 3) are neutral notes in
//         a clerk's language; the three RED strips that remain are real refusals
//         (an account that would not load, dates out of order, an unreadable
//         arrear). The findings moved to `LeavingStep`'s docstring.
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions:
//   E1 ⛔ **`POST /transfers/commit` IS NOT MOUNTED** — every write in
//      `transfers.py` is reachable only from Python. The screen calls it and
//      renders A18 §4's failure with the server's own words. REPORTED.
//   E3 **NOT ONE MONEY FIGURE IS COMPUTED IN THIS CLIENT.** The principal and
//      the balance are the server's own strings through `MoneyCell`; the
//      interest and the carried total are ABSENT WITH THEIR REASONS, because
//      the principal alone IS ❄️ WE-7 / GT-23's frozen failure.
//   E3 steps 2 and 3 render NO reading figures and NO asset rows — the drawn
//      ones are a seeded fixture and `transfers.py` writes no meter read.
//   E3 step 1's CHECKED / FOLLOWS clearances are NOT claimed; the screen says
//      what it did not check.
//   E3 `Split into two` is DISABLED with BR-CUS-086 as its reason.
//   E3 the `?step=` place survives a reload and the ANSWERS do not — there is
//      no draft row to resume from, exactly as with the other four wizards.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
