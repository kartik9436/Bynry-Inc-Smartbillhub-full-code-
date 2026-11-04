// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W4 task 4.10 — **S85, the capture form (REQ-03.1…6) and its
//           confirmation (REQ-03.sent)**. Design: B19 §1–§7 and §11, from the
//           PO's screenshots of 2026-08-24. Screens: S85 (B18's proposal; A1
//           allocates no id and decision **D1** is unruled)
// Rules:    BR-CUS-093 (numbered AT CREATION — and the two copy lines it makes
//           FALSE are not reproduced anywhere in this file) · BR-CUS-094 (SEVEN
//           selectable categories in the ruling's order + `government` LEGACY,
//           unselectable on a new record) · BR-CUS-095 (the checklist ships
//           entirely unticked; attaching never blocks creation) · BR-CUS-090
//           (the counter accepts what is handed over) · BR-CUS-092 (the
//           identifier is refused BY NAME today — no control is drawn that
//           cannot save) · BR-CUS-070 (the address as given is kept verbatim) ·
//           BR-SHL-018/019 (the shared wizard frame) · BR-SHL-025 · B14 rule 21
// Tests:    07-frontend/src/features/customers/ServiceRequestCapturePage.test.tsx
//           (TC-REQ-1 · TC-REQ-2 · TC-REQ-3 · TC-REQ-4)
// AMENDED:  2026-08-25 by lane F-REQ — **CR-033.** PO on v2.46.0, looking at
//           `/requests/new` step 1: *"on this screen - apply as - we need
//           customer categories that we have from settings - ehre as drop
//           down"*, then, showing `/accounts/new` step 1 (ACC-03): *"why don
//           you make request staep 1 simialr to this one -"*.
//           Three consequences, all in step 1:
//             (a) the CUSTOMER CATEGORY control MOVES here from step 2 — the
//                 same fetched BR-CUS-094 catalogue, the same legacy handling,
//                 drawn as ACC-03's `SegmentedField`; the step's `validate`
//                 moves with it, so a request cannot leave step 1 uncategorised;
//             (b) the step takes ACC-03's SHAPE — a question as the heading, a
//                 hint, then Category, Full name, Email, Phone;
//             (c) **`Applying as` is REPLACED, not re-pointed** — see
//                 `capturePayload` for why nothing derives one from the other.
//           ⚠ **AND ONE THING CR-033 §3 GETS WRONG, RECORDED HERE BECAUSE THE
//           NEXT AGENT WILL READ IT AND BELIEVE IT.** CR-033 says the list's
//           `NOT YET CLASSIFIED` badge is there *"because the category was
//           never asked for"*. It is not. `service_request_reads.list_row`
//           serves `type` from `request.outcome` filtered to
//           `ServiceRequest.JOB_OUTCOMES` (`new_connection · move_in ·
//           move_out · transfer · disconnect`) and `type_absence` from
//           `not request.outcome`. That is the JOB the request becomes — a
//           clerk's decision at review — and `set_customer_category` does not
//           touch it. **So asking for the category here does NOT clear
//           `NOT YET CLASSIFIED`,** and nothing in this file pretends it does.
//           REPORTED for a ruling rather than papered over.
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// TWO SENTENCES B19 DRAWS THAT THIS FILE MAY NOT PRINT — BR-CUS-093
// ══════════════════════════════════════════════════════════════════════════
// The ruling of 2026-08-24 made both FALSE, and §13 of B19 stamps them:
//
//   * the footer *"Step N of 6 · nothing is created until you submit"* becomes
//     ***"Step N of 6 · saved as draft SR-26-0048"***, and it is rendered by
//     `CaptureDraftFooter` in `serviceRequestShared.tsx` so there is exactly one
//     place it can be got wrong;
//   * the header *"the request is created and numbered when the fee is
//     collected"* **comes out entirely**. There is no component here that
//     renders it — the way to never print a false sentence is to have nowhere
//     to print it from.
//
// ✅ **THE THING BR-CUS-093 ASKED FOR AND THE SERVER COULD NOT DO IS DONE —
// PO ratification 2026-09-20, `DEF-CUS-6006`.** This block reported the gap
// instead of papering over it, correctly, for four weeks; it is closed now and
// the chain is written out rather than left to be inferred.
//
// It read: `_clean_capture(partial=False)` REQUIRES `address_as_given` before a
// row may be created, and the address is step 3 of six — so a draft could not
// exist at the instant the form opens and there was no number to read down the
// phone until the clerk had typed an address. Worse than the missing number:
// `Save as draft` is a header action on EVERY step, so it was a permanently
// disabled control on steps 1 and 2 for every request type in the product.
//
// **What the PO ruled** (decision log, `## 2026-09-20 · SEVEN PO RATIFICATIONS
// FROM ONE SITTING`, §3): a draft is created from the applicant NAME ALONE, a
// staff-raised one from NOTHING, and **the address requirement MOVES to
// SUBMIT** — `_require_submit_minimum`. So BR-CUS-093's worked example is now
// literally true: *"a clerk opens the form on Tuesday, the request is
// `SR-26-0048` from that moment"*, once the name is typed.
//
// ⚠ **BR-CUS-070 IS UNTOUCHED AND THE TRAP IT COULD HAVE SPRUNG WAS PROVED
// ABSENT BEFORE THIS SHIPPED.** The address is still stored verbatim and still
// immutable after capture — implemented as *after the row leaves DRAFT*, so a
// blank does NOT count as captured and a draft opened with no address can still
// be given one on step 3. Proved in `test_cr031_service_request.py` and walked
// in a browser; a draft whose address field was locked empty forever would have
// been a worse bug than the one this fixes.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT IS DRAWN AND CANNOT BE BUILT — each disabled WITH its reason
// ══════════════════════════════════════════════════════════════════════════
//   * **`Social Security Number` (REQ-03.1).** BR-CUS-092 clause (b) makes the
//     app-layer encryptor the precondition and it does not exist; the capture
//     path refuses `ssn`, `id_number` and eleven other names BY NAME rather
//     than dropping them. Clause (d): *"stored encrypted"* stays OFF the
//     screen. **A control that cannot save is not drawn as an input** — it is a
//     disabled field carrying the server's own sentence. B19 §14.1 settles the
//     SHAPE it will eventually take (`ID type` + `ID number`, masked to last
//     four with a type prefix, `DL ••••4417`) — one column with a type, not an
//     `ssn` column and a `drivers_licence` column.
//   * **The file inputs (REQ-03.4).** `attach_document` stores a `storage_ref`
//     and **no route in this product accepts a file for a service request** —
//     `apps/tenancy/api.py`'s logo upload is the only multipart endpoint there
//     is. A file input that cannot upload is dead UI (hard-won law 2), so the
//     step records WHICH documents were brought (`doc_type` + `name`, no
//     `storage_ref`) and the file control is disabled with that reason. The
//     record is honest: the server then reads the row as *needed, no file*,
//     which is exactly what it is.
//   * **`See the customer's view` (the banner).** B19 §0 reads it as implying
//     the applicant-facing render is the SAME object with different chrome. No
//     rule says so and no route serves it; a link to a screen that does not
//     exist is worse than its absence, so it is not drawn.
import { useMutation, useQueries, useQuery } from "@tanstack/react-query";

import { getCharges } from "@/api/endpoints";
import { canBeRaisedOnItsOwn } from "./NewConnectChargesStep";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { todayInZone } from "@/components/DateCell";
// ⛔ `CheckboxField` and `FieldStack` left with the applicant panel and
// `UsAddressFields` left with the mailing panel — both are B14 rule 43
// extractions, and an import kept "in case" is what eslint is for.
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { emptyUsAddress, usZipIsValid } from "@/components/UsAddressFields";
import type { UsAddressValue } from "@/components/UsAddressFields";
// ══════════════════════════════════════════════════════════════════════════
// **B14 RULE 43 — THE DOCUMENT BLOCK IS A COMPONENT NOW, AND THIS PAGE IS
// WHERE IT WAS EXTRACTED FROM.**
// ══════════════════════════════════════════════════════════════════════════
// PO, 2026-09-20: *"document sotrage - we need to make it compoentn so thatw e
// cna use it in other palces also"* and *"make them coponents - dont write
// stand alone code , engineer it"*. Step 4 below WAS ~330 lines of table,
// chips, form and buttons written inline in this 4,300-line file, plus eight
// `useState` hooks — importable by nothing, so a second screen needing to take
// a document off a person had to copy it. **The markup MOVED; it was not
// re-typed.** Same five columns in p078's order, same four chips, same two
// buttons, same `file_present` questions, same catalogue keys.
import {
  DOCUMENT_ACCEPT,
  DocumentStateCell,
  filterDocumentRows,
} from "@/components/documents";
import type {
  DocumentFilter,
  DocumentRow,
} from "@/components/documents";
import { useAccountSubtypes } from "./customersShared";
// **B14 rule 43 — step 1 IS the shared customer form** (lane CF-1,
// 2026-10-18, drawing set `customer-forms-2026-10-18` image 03):
// `CaptureCustomerForm` maps this page's `CaptureForm` onto the shared Who,
// Identity, About-the-customer, Co-applicant, Documents, Mailing address and
// Preferences pieces. `CaptureApplicantPanel` is gone and the mailing block
// moved onto step 1 with it; `serviceAddressLines` stays where it was.
import { CaptureCustomerForm } from "./CaptureCustomerForm";
import { coOwnersPayload, coOwnerFormatProblem } from "./CoOwnerCards";
import { coApplicantDrafts } from "./customerForm/requestCarry";
import type { CoOwnerDraft } from "./CoOwnerCards";
import { customerFormatProblem } from "./customerForm/CustomerWhoPanel";
import type { MoveInDocDraft } from "./MoveInDocumentsTable";
import { serviceAddressLines } from "./CaptureMailingAddressPanel";
import { editRefusalKey, requestIsEditable } from "./serviceRequestEditDoor";
import { PageHeader } from "@/components/PageHeader";
import { RefusalStrip } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import { CityAddressCheck, useCityAddressCheck } from "@/features/metering/addPremise/CityAddressCheck";
import {
  RequestPaymentDetails,
  feeCollectionBody,
  paymentDetailsProblem,
  PAY_LATER,
  PAY_NOW,
} from "./RequestPaymentDetails";
import { StatusPill } from "@/components/StatusPill";
import { WizardFrame, clampStepToReached } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { LEAVE_DELIBERATELY } from "@/components/LeaveGuard";
import type { LeaveDraft } from "@/components/LeaveGuard";
import { getTenantServices } from "@/api/endpoints";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  APPLICANT_KINDS,
  CAPTURE_CHANNELS,
  DOC_TYPE_OTHER,
  // ⛔ `PROPERTY_TYPES` is no longer imported here — the six radios came off
  // step 3 on 2026-09-19 (PO: *"if premises is found then we already have all
  // details related with property"*). The constant stays exported from
  // `serviceRequestEndpoints`, the column stays on the model, and the step 6
  // review still renders whatever a request already carries.
  createServiceRequest,
  addServiceRequestFee,
  getServiceRequest,
  getServiceRequestCaptureDefaults,
  getServiceRequestCategories,
  patchServiceRequest,
  removeServiceRequestFee,
  resolveServiceRequestAddress,
  searchPremisesPicker,
  setServiceRequestCategory,
  setServiceRequestServices,
  submitServiceRequest,
  uploadServiceRequestDocument,
  collectServiceRequestFee,
  getRequestExtraMessages,
  saveRequestExtraMessages,
} from "./serviceRequestEndpoints";
import type {
  CapturePayload,
  PremisesPickerRow,
  PremisesPickerUnit,
  RequestCustomEntity,
  ServiceRequestDetail,
  ServiceRequestDocument,
  ServiceRequestFeeLine,
  RequestExtraMessage,
} from "./serviceRequestEndpoints";
import { REQUEST_CUSTOM_ENTITIES } from "./serviceRequestEndpoints";
import {
  RequestApplicantCustomFields,
  RequestCustomFieldsRecap,
  RequestPropertyCustomFields,
  changedRequestCustom,
  emptyRequestCustom,
  hydrateRequestCustom,
  missingOnStep,
  requestCustomPayload,
  requestRegistryQuery,
} from "./requestCustomFields";
import type { RequestCustomForm } from "./requestCustomFields";
import type { CustomFieldRegistryEntry } from "@/api/endpoints";
import { customFieldErrors } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import {
  // ⛔ `BlockedControl` was imported here by `d54a7f7d` and NEVER rendered in
  // this file. It is deleted from `serviceRequestShared` (`DEF-GOV-10106`):
  // the "other screens use it" this note used to claim was never true.
  CaptureDraftFooter,
  DateOrNotSupplied,
  FeeLinesTable,
  moneyText,
  billingAddressLine,
  Field,
  CatalogueSentence,
  FieldGrid,
  MoneyOrAbsence,
  SERVICE_REQUESTS_ROUTE,
  SERVICE_REQUEST_NEW_ROUTE,
  // ⛔ `ServiceCard` and `StatedFact` are no longer imported here, and both
  // removals are rulings rather than tidying: the eleven service CARDS became
  // one multiselect (PO 2026-09-15) and the two identity ABSENCES became
  // inputs (`BR-CUS-092` amended, same day). Nothing else rendered either, so
  // both are DELETED from `serviceRequestShared` (`DEF-GOV-10106`).
  chargeCodeOptions,
  TextOrNotSupplied,
  serviceRequestPath,
} from "./serviceRequestShared";
// ═══════════════════════════════════════════════════════════════════════════
// **REQ-03 TASKS 8, 9 AND 10 — B14 RULE 43.** The two table arrays and the
// Review's communication card are COMPONENTS, declared once in their own file
// and mounted four times here.
//
// ⛔ **`RequestedServicesTable` AND `ApplicationFeeAdder` ARE NO LONGER
// IMPORTED.** The first drew the connection date on EVERY service row
// (`DEF-CUS-7840`) and the second was the *Choose a fee…* box the redesign
// replaced with a row. Both stay exported from `serviceRequestShared` — the
// request detail and the confirmation still use them.
import {
  ApplicationFeesTableArray,
  CustomerMessagesCard,
  ReviewServicesTable,
  ServicesTableArray,
} from "./serviceRequestTableArrays";
import type { CustomerMessageRow, ServiceOnSite, ServiceTableRow } from "./serviceRequestTableArrays";

/**
 * **FOUR STEPS — PO APPROVAL 2026-09-29, from the drawings in
 * `05-prototype/new-request-four-steps-2026-09-29/`.**
 *
 * It was SIX — `customer · connection · addresses · documents · fees · check`
 * — and the redesign folds them without losing an input:
 *
 * | was | is |
 * |---|---|
 * | `customer` + the category pair + `documents` | **`applicant`** |
 * | `addresses` | **`property`** |
 * | the rest of `connection` + `fees` | **`service`** |
 * | `check` | **`review`** |
 *
 * ⚠ **A WIZARD'S STEP COUNT IS A FLOW, AND A FLOW IS THE DRAWING'S**
 * (`DEF-GOV-5248`). The bill run shipped six steps against a blueprint drawing
 * four, and four further lanes then built onto the wrong shape, because a
 * pointer handed flows to the prototype. This constant is the one place that
 * can go wrong the same way, so the mapping is written out here rather than
 * left to be inferred.
 *
 * ⚠ **IT IS SHARED, AND IT MOVED IN THIS COMMIT BY AGREEMENT.** Lane SCREEN-A
 * owns it for this redesign; a lane rebuilding step 3 or step 4 reads it and
 * does not rewrite it. `DEF-633` is what a stepper, a footer and a header
 * disagreeing about the count costs.
 */
export const CAPTURE_STEPS = ["applicant", "property", "service", "review"] as const;
export type CaptureStep = (typeof CAPTURE_STEPS)[number];

/**
 * **WHICH NUMBER A STEP IS, DERIVED — never a literal on a screen.**
 *
 * The Review draws `Edit step 1`, `Edit step 2` and `Edit step 3`, and those
 * three numbers are the ONLY place in this product where one screen states
 * another screen's position. A typed `3` is correct exactly until the flow
 * moves, and then it is a live control pointing at the wrong page with every
 * check still green (hard-won law 2's mirror). This reads the array.
 *
 * ⚠ **IT READS `CAPTURE_STEPS` AND DOES NOT TOUCH IT.** The constant is lane
 * SCREEN-A's for this redesign, by agreement written on the constant itself.
 *
 * A step id that is not in the array answers `1` rather than `0`, because a
 * wizard has no step zero and a link to one opens nothing.
 */
export function captureStepNumber(id: CaptureStep): number {
  const at = CAPTURE_STEPS.indexOf(id);
  return at < 0 ? 1 : at + 1;
}

/** A9 / B13 §1: the step number is URL state, so a half-done flow is linkable.
 *  The same constant the other four starting-service wizards declare, spelt the
 *  same way (`NewAccountWizard.STEP_PARAM`, `moveShared.STEP_PARAM`,
 *  `NewConnectWizard`'s own). */
export const STEP_PARAM = "step";

/**
 * ⚠ **THE STEP IS URL STATE, AND THIS WIZARD WAS THE ONE OF FIVE WHERE IT WAS
 * NOT (`DEF-CUS-5083`).** `EP-SHL-03-forms-wizards.md` is a rule and not a
 * habit: *"Wizard step | **all wizards** | A9 routing model (`?step=`) | none
 * (URL state) | int | system-derived | clamped to reached steps
 * (BR-SHL-018)"*. `MoveInWizard` and `MoveOutWizard` both cite it verbatim.
 * Measured before the fix: `/requests/new?step=2` painted **`Step 1 of 6`**,
 * because the step lived in component state and `useSearchParams` was read for
 * `?request=` only. **The blueprint draws six addresses for this wizard**
 * (`?step=1` … `?step=6`, pages 75–79) and a link to any of them landed the
 * clerk on step 1 with every `toContain` on the href passing.
 *
 * ⚠ **THE CLAMP IS TO THE STEP COUNT, WHICH IS WHAT THE FOUR SIBLINGS DO.**
 * `NewAccountWizard:477`, `MoveInWizard:411` and `NewConnectWizard:439` all
 * derive `{ step, reached: step }` from the URL and say why in the same words:
 * *"The forward fence is the step itself: a user can always go BACK to a step
 * they have been on, and forward only through Continue (BR-SHL-018)."* Copying
 * that judgment rather than inventing a fifth behaviour is the whole point of
 * the defect — a wizard that clamped to `reached` instead would still not
 * resolve the six drawn addresses, and this menu would have two step models
 * across five screens instead of one.
 *
 * It reuses `clampStepToReached`, the frame's own clamp, rather than a fourth
 * copy of `Math.min(Math.max(1, n), count)`: `reached` is handed the step count
 * because this wizard keeps no fence, which is the sibling behaviour stated
 * rather than re-derived.
 */
export function captureStepFromParam(raw: string | null): number {
  return clampStepToReached(
    Number(raw ?? "1"),
    { step: 1, reached: CAPTURE_STEPS.length },
    CAPTURE_STEPS.length,
  ).step;
}

/** The form's own state. Everything is a STRING (rule 2 for the money fields,
 *  and a calendar date is a raw `YYYY-MM-DD` string end to end). */
export interface CaptureForm {
  channel: string;
  /**
   * ✅ **`Applying as` IS BACK, AND IT IS `BR-CUS-1022` RATHER THAN NOSTALGIA
   * FOR THE CONTROL `CR-033` REMOVED (`DEF-CUS-5415`).**
   *
   * The rule, verbatim: *"THE KIND MUST BE STATED WHERE IDENTITY IS PRESENTED,
   * AND IS REFUSED BY NAME WHERE IT IS NOT — the test to apply depends on the
   * answer, and a guess of `person` would judge a business by a date of birth
   * it has not got and file its Tax ID nowhere."* The PO's ruling of
   * 2026-09-15 put IDENTITY on step 1, so step 1 became the place that
   * sentence names. `CR-033` took this control out on 2026-08-25 and
   * `BR-CUS-1022` was ruled six days later; nothing reconciled the two and
   * `applicant_kind` simply stopped being sent, leaving every request on the
   * column's `person` default.
   *
   * ⚠ **IT IS NOT THE CUSTOMER CATEGORY WEARING A NEW NAME.** `CR-033` §4 is
   * explicit that they are different facts — *"a residential account can be
   * held by a business (a landlord), and a sole trader is a person on a
   * commercial account"* — so neither derives the other, and the category has
   * gone to step 2 where the blueprint draws it.
   */
  applicant_kind: string;
  applicant_name: string;
  applicant_email: string;
  applicant_phone: string;
  /** ✅ **BR-CUS-092 — the field the screen has been promising since B19 §2.**
   *  Held as the raw string the applicant typed; it is sent ONCE, on capture,
   *  and never read back — the detail response carries `identifier.ssn_last4`
   *  and nothing more. */
  ssn: string;
  /**
   * ✅ **`BR-CUS-092` AMENDED 2026-09-15 — clause (a) finishing, not a rule
   * being reversed.** A PERSON's date of birth, a plain calendar date because
   * `BR-CUS-1020` settled that it *"must be COMPARABLE"* and is the middle
   * clause of `BR-CUS-089`'s strong match rather than an identifier.
   *
   * ⚠ **A COMPANY HAS NONE AND IS NEVER ASKED** (`BR-CUS-1022`).
   */
  date_of_birth: string;
  /** ✅ **`BR-CUS-092(a)`'s second identifier, a PERSON's only.** Clause (c)
   *  binds every READ of it to the last four (`maskIdentifier`); clause (d)
   *  keeps the *"stored encrypted"* sentence off the screen until the column
   *  is live. */
  drivers_licence: string;
  /** ✅ **A COMPANY's identifier and a company's only** (`BR-CUS-1022`):
   *  *"a company is never asked for a driving licence and a person is never
   *  asked for a Tax ID … asking for both and leaving one blank turns a rule
   *  into a habit and the blank field eventually gets filled with something."* */
  tax_id: string;
  /**
   * ✅ **WHAT IS ALREADY ON FILE, AS ITS LAST FOUR — NEVER A VALUE TO SEND
   * (`DEF-CUS-6427`, the Edit ruling of 2026-09-23, trap 1).**
   *
   * A request reopened for correction carries `identifier.ssn_last4` and
   * `identifier.drivers_licence_last4` and NOTHING MORE — `BR-CUS-092(c)`
   * keeps the full number off the wire. So the box above (`ssn`) opens EMPTY
   * and shows `••• ••• • 5236` as its placeholder, and this field is what the
   * placeholder is drawn from.
   *
   * ⚠ **THE MASK IS NOT A VALUE AND IS NEVER IN ONE.** A mask loaded into
   * `ssn` would be saved back over the real number the first time the clerk
   * pressed Save. `maskedFieldValue` reads the pair: a number TYPED is sent;
   * nothing typed over a number on file sends NOTHING (the key is absent, which
   * the server reads as *unchanged*); and only an on-file number the clerk
   * has deliberately cleared — switching the applicant to a business — sends
   * `""`.
   */
  ssn_on_file: string;
  /** The licence's last four on file — see `ssn_on_file`, same rule. */
  drivers_licence_on_file: string;
  /** Lane CF-1 — a business's Tax ID already on file, as its last four;
   *  shown as a mask, never re-sent unless retyped (`DEF-CUS-10223`). */
  tax_id_on_file: string;
  /** Lane CF-1 — Move-in's *Government ID* (last four, BR-CUS-045). */
  gov_id_last4: string;
  /** Lane CF-1 — Move-in's *Contact by*. */
  contact_by: string;
  /** Lane CF-1 — the full co-applicant cards (Move-in's co-owner card);
   *  `add_co_applicant` is the panel's tick. The three `co_applicant_*`
   *  fields below are read back from the server and mirrored from the first
   *  card there; the screen no longer types them. */
  co_applicants: CoOwnerDraft[];
  /** Lane CF-1 — the request's Preferences (no autopay — PO 2026-10-18). */
  prefs_on: boolean;
  paperless: boolean;
  sms_reminders: boolean;
  preferred_language: string;
  add_co_applicant: boolean;
  co_applicant_name: string;
  co_applicant_email: string;
  co_applicant_phone: string;
  account_type_code: string;
  account_subtype_id: string;
  requested_start: string;
  services: string[];
  /**
   * **THE DRAWN `SERVICE` / `REQUESTED START` TABLE, one date per picked
   * service** (accounts blueprint p076). The drawing argues it in its own
   * words: *"Each service carries its own start. A block that needs electric
   * on the 12th and sewer a fortnight later is one request and not two, so the
   * date sits per service rather than once on the form."*
   *
   * Keyed by service CODE, so removing a service from the multiselect takes
   * its date with it and re-adding it does not resurrect a stale one.
   */
  service_starts: Record<string, string>;
  address_as_given: string;
  address_unit_as_given: string;
  /** ⚠ **WHAT THE CLERK PICKED OUT OF THE PREMISES REGISTER, BESIDE WHAT THE
   *  APPLICANT SAID — never instead of it** (PO ruling 2026-09-15 + hard rule
   *  8). None of these is a column on `service_requests`: the premises' own
   *  address facts are read by walking to the premises, which is why the
   *  request stores an id and this form holds the walked values for display
   *  only. */
  picked_premises_id: string;
  picked_premise_no: string;
  picked_premises_city: string;
  picked_premises_state: string;
  picked_premises_postal: string;
  picked_unit_id: string;
  picked_unit_no: string;
  plot_or_parcel: string;
  what_is_being_built: string;
  /**
   * ⊕ **`How many units are on this property?` — `BR-CUS-1055`, PO ruling
   * 2026-09-15, verbatim: *"we need to build this"*.**
   *
   * A **CLAIM, not a count**: what the applicant says is there, which the
   * register may agree with or not. Before `customers/0049` there was no
   * column at all and the drawing's own note says where the number went
   * instead — *"the number lives only in whatever the clerk typed into the
   * notes, which no screen and no rule can read"*.
   *
   * Held as a STRING like every other field on this form; `_clean_unit_count`
   * turns it into an integer, refuses anything that is not a whole number and
   * refuses a negative, **accepts zero** and imposes no maximum (`NFR-5`).
   * `""` reaches the server as `None`, which is *not supplied*.
   */
  units_on_property: string;
  /** **THE PARTS THE APPLICANT GAVE — PO ruling 2026-09-22.** For MATCHING a
   *  premises; see the step-3 panel for the whole chain. */
  address_city_as_given: string;
  address_state_as_given: string;
  address_postal_code_as_given: string;
  billing_address_same: boolean;
  /**
   * ✅ **WHERE THE BILL GOES, AS A US ADDRESS — `DEF-CUS-6408`, PO report
   * 2026-09-23**, verbatim: *"if customer want put billing address then it
   * should full address line, unit, city, zip it shoould be match how address
   * taken in USA ;do'nt make it mandatory"*.
   *
   * ⛔ **`billing_address_as_given` — the one free-text box — IS NO LONGER A
   * FIELD OF THIS FORM.** It stays on the server and in its payload type, so
   * every request captured before today keeps the string it was given; this
   * wizard neither sends nor clears it. (This read *"the wizard never
   * hydrates from a draft"* until 2026-09-24; it does now — `DEF-CUS-5880` —
   * and it still never sends this key, because a request reopened for Edit
   * PATCHes only what the clerk changed and nothing here can change it.)
   *
   * **All five optional**, even once the box is unticked. `State` is a
   * two-letter code picked from a searchable list (B14 rule 8 — fifty-two
   * options). The PO named line, unit, city and ZIP and not the state; a US
   * address has one and a ZIP alone does not make an envelope, so it is asked
   * for too — and, like the rest, never required.
   */
  billing_address: UsAddressValue;
  property_type: string;
  documents: string[];
  fee_timing: string;
  fee_due_by: string;
  fee_method: string;
  /**
   * **THE COUNTER TENDER — PO ruling 2026-09-15.** Card: the LAST FOUR, the
   * brand and the terminal's authorisation code, and **never** the number, the
   * expiry or the security code. Cheque: the number, the bank and the date
   * written on it.
   *
   * ⚠ **THE CARD FIELDS ARE THE SHORT LIST ON PURPOSE.** Holding a full card
   * number puts this product inside the card industry's rules, and nothing
   * here ever charges that card again.
   */
  card_last4: string;
  card_brand: string;
  card_auth_code: string;
  cheque_no: string;
  cheque_bank: string;
  cheque_date: string;
  /** `DEF-CUS-10041` — the rest of the Pay-now detail (`RequestPaymentDetails`).
   *  None of it is a capture column: it travels to `POST .../fee-collection`
   *  at submit and nowhere else. */
  fee_receipt_no: string;
  cash_received: string;
  ach_holder: string;
  ach_last4: string;
  ach_reference: string;
  money_order_no: string;
  money_order_issuer: string;
  wire_reference: string;
  wire_bank: string;
  wire_date: string;
  what_they_said: string;
  /** `CR-161-BRC10` W6 — the utility's own fields placed Input on Staff New
   *  Request, one blob per record type (`requestCustomFields.tsx`). */
  custom: RequestCustomForm;
}

export function emptyCaptureForm(): CaptureForm {
  return {
    channel: CAPTURE_CHANNELS[0],
    // ⚠ **SEEDED `person`, AND THAT IS THE COLUMN DEFAULT MADE VISIBLE RATHER
    // THAN A GUESS.** `BR-CUS-1022` forbids GUESSING a kind where identity is
    // presented; it does not forbid a control opening on the commoner answer
    // in front of the clerk, which is the opposite of a guess — the clerk can
    // see it and change it, and the fields below change with it.
    applicant_kind: APPLICANT_KINDS[0],
    applicant_name: "",
    applicant_email: "",
    applicant_phone: "",
    ssn: "",
    date_of_birth: "",
    drivers_licence: "",
    tax_id: "",
    ssn_on_file: "",
    drivers_licence_on_file: "",
    tax_id_on_file: "",
    gov_id_last4: "",
    contact_by: "",
    co_applicants: [],
    prefs_on: false,
    paperless: false,
    sms_reminders: false,
    preferred_language: "",
    add_co_applicant: false,
    co_applicant_name: "",
    co_applicant_email: "",
    co_applicant_phone: "",
    account_type_code: "",
    account_subtype_id: "",
    requested_start: "",
    services: [],
    service_starts: {},
    address_as_given: "",
    address_unit_as_given: "",
    picked_premises_id: "",
    picked_premise_no: "",
    picked_premises_city: "",
    picked_premises_state: "",
    picked_premises_postal: "",
    picked_unit_id: "",
    picked_unit_no: "",
    plot_or_parcel: "",
    what_is_being_built: "",
    units_on_property: "",
    address_city_as_given: "",
    address_state_as_given: "",
    address_postal_code_as_given: "",
    billing_address_same: true,
    billing_address: emptyUsAddress(),
    property_type: "",
    documents: [],
    fee_timing: "",
    fee_due_by: "",
    fee_method: "",
    card_last4: "",
    card_brand: "",
    card_auth_code: "",
    cheque_no: "",
    cheque_bank: "",
    cheque_date: "",
    fee_receipt_no: "",
    cash_received: "",
    ach_holder: "",
    ach_last4: "",
    ach_reference: "",
    money_order_no: "",
    money_order_issuer: "",
    wire_reference: "",
    wire_bank: "",
    wire_date: "",
    what_they_said: "",
    custom: emptyRequestCustom(),
  };
}

/**
 * **THE SERVER'S OWN MINIMUM FOR CREATING A ROW**, mirrored here so the screen
 * can say WHY it cannot save yet instead of posting and being refused.
 *
 * ⚠ **THE ADDRESS CAME OUT OF THIS TEST ON 2026-09-20 — PO ratification,
 * `DEF-CUS-6006`.** It read *"`_clean_capture(partial=False)` requires
 * `address_as_given` always"*, which was true of the server and was a defect in
 * both halves: `address_as_given` is captured on **step 3** while `Save as
 * draft` is a header action on **every** step, so this function returned
 * `false` on steps 1 and 2 for every request type in the product and the
 * control was permanently disabled. `create_request`'s own docstring said the
 * opposite — *"a row has to exist before step 2"* — so intent and validation
 * contradicted each other and validation won.
 *
 * **What is required now** (decision log, 2026-09-20 §3): the applicant's
 * NAME ALONE, and **nothing at all** on a staff-raised channel — **BR-CUS-091**,
 * because collections raising a disconnect on `500 Main` is not somebody
 * applying for anything and demanding an applicant name would make the clerk
 * invent one.
 *
 * ⚠ **THE ADDRESS IS NOT GONE, IT MOVED TO SUBMIT**, and this file does not
 * carry a second copy of that test. Two things hold it: step 3's own `validate`
 * (`form.address_as_given.trim() !== ""`, untouched by this change) refuses to
 * advance without one, which is what satisfies the ruling's *"Save as draft,
 * step 3+ — unchanged"* row without making this gate step-aware; and
 * `_require_submit_minimum` on the server refuses the submit itself. *"There is
 * no service request about nowhere"* is still true — of a REQUEST, which was
 * never true of a DRAFT.
 */
/** The id `Save as draft` points its `aria-describedby` at. Declared once so
 *  the note and the button cannot drift apart (B14 rule 31 — it is a DOM hook,
 *  never a value a clerk reads). */
const DRAFT_BLOCKED_NOTE_ID = "capture-draft-blocked";

/**
 * ⊕ **LANE CF-1 (2026-10-18) — WHAT HOLDS STEP 1, AS ONE CATALOGUE KEY, OR
 * NULL: Move-in's required-field rules on the request** (decision log
 * 2026-10-18: *"phone required for a person, email optional, at least one ID
 * unless an existing customer is linked"*, accepted by the PO). A person's
 * phone IS one of the IDs that rule counts (`accountIdentityShortfall`), so a
 * person owes a name and a phone; a business owes a name and its Tax ID — the
 * move-in's own `moveInCustomerProblem`, minus the link a request never makes.
 * The phone and email are format-checked; a co-applicant card needs a name; a
 * typed mailing ZIP must be a ZIP. **A staff-raised request (BR-CUS-091) owes
 * no applicant fact at all** — only the shapes of what was typed.
 */
export function applicantStepProblem(form: CaptureForm): string | null {
  const staff = form.channel === "staff_collections";
  if (!staff && form.applicant_name.trim() === "") {
    return "customers.moveIn.customer.problem.fullName";
  }
  const format = customerFormatProblem({ email: form.applicant_email, phone: form.applicant_phone });
  if (format !== null) return format;
  if (!staff) {
    if (form.applicant_kind === "business") {
      if (form.tax_id.trim() === "" && form.tax_id_on_file === "") return "customers.form.taxIdRequired";
    } else if (form.applicant_phone.trim() === "") {
      return "customers.moveIn.customer.problem.phone";
    }
  }
  if (form.add_co_applicant) {
    const card = form.co_applicants.some((row) => row.full_name.trim() === "")
      ? "customers.moveIn.customer.problem.coOwnerName"
      : coOwnerFormatProblem(form.co_applicants);
    if (card !== null) return card;
  }
  if (!form.billing_address_same && !usZipIsValid(form.billing_address.postal_code)) {
    return "customers.account.mailingZipInvalid";
  }
  return null;
}

export function canCreateDraft(form: CaptureForm): boolean {
  if (form.channel === "staff_collections") {
    return true;
  }
  return form.applicant_name.trim() !== "";
}

/** What `POST /service-requests` and `PATCH …/{id}` accept. Anything outside
 *  `CAPTURE_FIELDS` is refused BY NAME, so this is built explicitly rather than
 *  by spreading the form. */
/**
 * ══════════════════════════════════════════════════════════════════════════
 * **THE IDENTITY SEAM — three field names the capture path does not accept
 * yet, held in ONE place so lane G fills one line and not six.**
 * ══════════════════════════════════════════════════════════════════════════
 *
 * The PO ruled on 2026-09-15 that the date of birth and the driving licence
 * are captured on step 1, and `BR-CUS-092`'s amendment of the same day records
 * that this FINISHES clause (a) rather than reversing anything. `BR-CUS-1022`
 * adds the Tax ID for a company. **The screen is built; the columns are lane
 * G's.**
 *
 * ⚠ **THIS CANNOT BE "SEND IT AND SEE".** `_clean_capture` refuses
 * `date_of_birth` and `dob` BY NAME with `BIZ_STATE` — deliberately, so a
 * dropped identifier is never silent — and an unknown key is refused the same
 * way. Sending one today does not lose a field, it **fails the whole PATCH**,
 * so every step of the wizard would stop saving. The flag is therefore a real
 * guard and not a stylistic hedge.
 *
 * **WHAT LANE G MUST PUBLISH, and this is the whole contract:**
 *   · `CAPTURE_FIELDS` gains `date_of_birth`, `drivers_licence`, `tax_id`
 *     (and `date_of_birth`/`dob` leave `IDENTIFIER_FIELDS`);
 *   · `service_requests.date_of_birth` is a plain `date`;
 *     `service_requests.drivers_licence` and `.tax_id` are
 *     `EncryptedTextField`s with a blind index beside each — **no `_last4`
 *     column of any kind** (`BR-CUS-092`);
 *   · the read path serves `applicant.drivers_licence_last4` and
 *     `applicant.tax_id_last4` as READ PROJECTIONS, and `applicant.dob`.
 *
 * **Then the only edit here is `true`**, and the case in the test file that
 * asserts these three names are absent from the payload goes RED and names
 * this constant — which is hard-won law 2's own instruction: *when you write a
 * hold, write the test that fires when the hold expires.*
 */
export const IDENTITY_CAPTURE_ACCEPTED = true;

// ⛔ **`TAX_ID_CAPTURE_ACCEPTED` IS GONE — LANE CF-1, 2026-10-18,
// `DEF-CUS-10223`.** It read `false` and held the business Tax ID the screen
// drew: the box took a number and the number went nowhere, on every business
// request. `service_requests.tax_id` exists since `customers/0087`
// (encrypted, refused on a person by name), so the hold expired and the flag
// with it — `identityPayload` sends a business's Tax ID unconditionally.

/**
 * **WHAT THIS KIND IS ASKED FOR, and nothing of the other kind's**
 * (`BR-CUS-1022`, verbatim: *"NEITHER KIND BORROWS THE OTHER'S CRITERIA AND
 * NEITHER IS ASKED FOR THE OTHER'S EVIDENCE"*).
 *
 * A person: date of birth + (SSN or driving licence). A company: its Tax ID,
 * and it **has no date of birth at all** — so the branch is not a convenience
 * and switching kind clears what the other kind answered, because *"asking for
 * both and leaving one blank turns a rule into a habit and the blank field
 * eventually gets filled with something."*
 */
export function identityFieldsFor(kind: string): readonly ("dob" | "ssn" | "licence" | "tax_id")[] {
  return kind === "business" ? ["tax_id"] : ["dob", "ssn", "licence"];
}

/** Everything the other kind answered, blanked. Called on every kind change so
 *  a company can never carry a date of birth and a person can never carry a
 *  Tax ID — the refusal is in the DATA and not only in the layout. */
export function clearOtherKind(form: CaptureForm, kind: string): Partial<CaptureForm> {
  const asked = new Set(identityFieldsFor(kind));
  return {
    applicant_kind: kind,
    ...(asked.has("dob") ? {} : { date_of_birth: "" }),
    // ⚠ **THE NUMBER ON FILE IS CLEARED WITH THE BOX (`DEF-CUS-6427`).** A
    // reopened request holds its SSN only as `ssn_on_file`; switching the
    // applicant to a company must take THAT away too, or the stored number
    // stays on a business the server then refuses by name (`BR-CUS-1022`).
    ...(asked.has("ssn") ? {} : { ssn: "", ssn_on_file: "" }),
    ...(asked.has("licence") ? {} : { drivers_licence: "", drivers_licence_on_file: "" }),
    ...(asked.has("tax_id") ? {} : { tax_id: "", tax_id_on_file: "" }),
  };
}

/**
 * `TX4417882` → `•••••1882`. The repo's own audit mask (`_mask_audit_blob`
 * writes `•••••6789`), so one shape means *last four* everywhere.
 *
 * ⚠ **CLAUSE (c) BINDS EVERY READ AND THIS IS THE ONE THE WIZARD OWNS.** The
 * full licence exists in front-end state only while the clerk is typing it, and
 * step 6 reads it back over a counter a customer may be standing at. Everywhere
 * ELSE the last four is a SERVER projection (`crypto.last_four`) and the full
 * value never reaches the browser.
 */
export function maskIdentifier(value: string): string {
  const cleaned = value.replace(/[^0-9A-Za-z]/g, "");
  if (cleaned === "") {
    return "";
  }
  return cleaned.length <= 4
    ? "•".repeat(cleaned.length)
    : `•••••${cleaned.slice(-4)}`;
}

export function capturePayload(form: CaptureForm): CapturePayload {
  return {
    channel: form.channel,
    // ✅ **SENT AGAIN — `BR-CUS-1022` / `DEF-CUS-5415`.** The comment below is
    // `CR-033`'s and is kept because its REASONING still stands: the kind and
    // the customer category are different facts and neither derives the other.
    // What changed is that `CR-033` removed the control and left the fact
    // unstated, and `BR-CUS-1022` — ruled six days later — refuses an
    // unstated kind wherever identity is presented. The PO's ruling of
    // 2026-09-15 put identity on this step, so the fact is now asked and sent.
    applicant_kind: form.applicant_kind as CapturePayload["applicant_kind"],
    // ⛔ **SUPERSEDED (PO ruling 2026-09-15 → `BR-CUS-1022` reaches this
    // screen; `DEF-CUS-5415`).** This read *"`applicant_kind` IS NOT SENT FROM
    // THIS FORM ANY MORE — CR-033"*, because step 1 had drawn it as `Applying
    // as · A person | A business` and the PO asked for the CUSTOMER CATEGORY
    // in that position instead (2026-08-25). The removal was correct for what
    // was known then and its reasoning is kept above: the two are **different
    // facts** and CR-033 §4 says so in as many words: *"a residential account
    // can be held by a business (a landlord), and a sole trader is a person on
    // a commercial account"*. The category still does NOT derive
    // `applicant_kind` and nothing here guesses one from the other.
    //
    // **What the ruling changed is that the fact is now ASKED.** `CR-033`
    // replaced the control and left the column on its `person` default;
    // `BR-CUS-1022`, six days later, refused an unstated kind wherever
    // identity is presented; and the ruling of 2026-09-15 put identity on this
    // step. So the value above is the clerk's answer, not a default arriving
    // invisibly from the model.
    applicant_name: form.applicant_name.trim(),
    applicant_email: form.applicant_email.trim(),
    applicant_phone: form.applicant_phone.trim(),
    // ✅ **BR-CUS-092(a)/(b) — DEF-632, PO 2026-08-27.** The one identifier
    // name `_clean_capture` accepts. `""` is sent as `""`, which the server
    // stores as NULL rather than encrypting an empty string — an empty column
    // keeps meaning "we do not hold one", and a clerk who typed the number into
    // the wrong applicant can clear it by emptying the box.
    //
    // ✅ **THE TRAP THIS COMMENT WARNED ABOUT IS CLOSED — `DEF-CUS-6427`,
    // 2026-09-24.** It read: *"The day rehydration is added, this field must be
    // omitted from the payload when it was not edited, rather than sent
    // blank."* Rehydration is added (`hydrateCaptureForm`), and so is the
    // omission: the read path serves only the last four, so a reopened request
    // opens with `ssn` EMPTY and `ssn_on_file` holding `5236`, and
    // `maskedFieldValue` then answers `undefined` — the key is absent and the
    // server leaves the stored number alone. A clerk who TYPES a number sends
    // it; a clerk who types nothing over a number on file sends nothing.
    ssn: maskedFieldValue(form.ssn, form.ssn_on_file),
    // ✅ **THE TWO IDENTIFIERS THE RULING OF 2026-09-15 ADDED, THROUGH THE ONE
    // SEAM.** See `IDENTITY_CAPTURE_ACCEPTED` for the whole contract and for
    // why this cannot simply be sent: `_clean_capture` refuses `date_of_birth`
    // BY NAME, and an unknown key fails the PATCH outright rather than
    // dropping a field — so an ungated send would stop the wizard saving at
    // every step. `identityFieldsFor` decides WHICH of them this kind is asked
    // for, so a company never sends a licence and a person never sends a Tax
    // ID (`BR-CUS-1022`).
    ...(IDENTITY_CAPTURE_ACCEPTED ? identityPayload(form) : {}),
    // ✅ **THE COUNTER TENDER NEVER RIDES THE CAPTURE PATCH** —
    // `_clean_capture` refuses an unknown key outright. It goes to
    // `POST .../fee-collection` at submit (`DEF-CUS-10041`, `feeCollectionBody`).
    // ⊕ Lane CF-1 (2026-10-18) — the shared customer form's other values. The
    // full co-applicant cards replace the three `co_applicant_*` boxes (the
    // server mirrors the first card into those columns for their readers).
    co_applicants: form.add_co_applicant ? coOwnersPayload("co_owner", form.co_applicants) : [],
    gov_id_last4: form.gov_id_last4.trim(),
    contact_by: form.contact_by,
    preferred_language: form.preferred_language.trim(),
    paperless: form.prefs_on && form.paperless,
    sms_reminders: form.prefs_on && form.sms_reminders,
    requested_start: form.requested_start === "" ? undefined : form.requested_start,
    address_as_given: form.address_as_given.trim(),
    address_unit_as_given: form.address_unit_as_given.trim(),
    // ✅ **THE FIVE PARTS, AND `""` FOR EACH WHEN THE BOX IS TICKED
    // (`DEF-CUS-6408`).** Ticking *Same as the service address* is a clerk
    // saying there is no separate address, so parts typed before the tick
    // must not survive it. ⊕ Lane CF-1 — sent as the MAILING address
    // (`mailingPayload`), the one name for where the bill goes.
    ...mailingPayload(form),
    // ✅ **THE PICK REACHES THE SERVER — lane E's contract.** Empty string
    // here means *the clerk cleared it*, which lane E spells `null` and which
    // UNDOES a pick; `undefined` would mean *this PATCH is not about the
    // address* and would leave a stale match standing. Two different acts, and
    // the difference is one `?? null`.
    picked_premises_id: form.picked_premises_id === "" ? null : form.picked_premises_id,
    picked_unit_id: form.picked_unit_id === "" ? null : form.picked_unit_id,
    plot_or_parcel: form.plot_or_parcel.trim(),
    what_is_being_built: form.what_is_being_built.trim(),
    // ⊕ **`BR-CUS-1055`.** Sent as the typed string, **including `""`** —
    // `_clean_unit_count` reads an empty string as `None`, so clearing the box
    // clears the column, which is the same act `ssn` already spells this way.
    // `undefined` would mean *this PATCH is not about the unit count* and would
    // leave a stale claim standing after the clerk wiped it.
    units_on_property: form.units_on_property.trim(),
    address_city_as_given: form.address_city_as_given.trim(),
    address_state_as_given: form.address_state_as_given.trim(),
    address_postal_code_as_given: form.address_postal_code_as_given.trim(),
    // ⛔ **NOTHING ON THIS WIZARD WRITES A PROPERTY TYPE ANY MORE** (PO,
    // 2026-09-19: *"if premises is found then we already have all details
    // related with property"*). The line stays because removing a CONTROL is
    // not dropping a COLUMN: `form.property_type` is now always `""` from this
    // screen, which is already spelt `undefined` below, and a caller that does
    // know the type can still set it.
    property_type:
      form.property_type === ""
        ? undefined
        : (form.property_type as CapturePayload["property_type"]),
    what_they_said: form.what_they_said.trim(),
    // ⚠ **`fee_timing` IS DERIVED FROM THE TENDER NOW — PO report 2026-09-22,
    // row 11, which took `Collect later` off the screen.** With one option
    // left there was no control to read, and writing `collect_now` on to every
    // request regardless would tell the customer portal *before we start*
    // about money nobody intends to take at the counter.
    //
    // So: a METHOD chosen is a clerk saying they are taking it now, and no
    // method is **not an answer rather than a guess** — which is exactly what
    // `apps/portal/paying.py::_fee_when` already does with a null
    // (`WHEN_NOT_RECORDED`, *"a screen saying before we start over a request
    // nobody set a timing on would be inventing a deadline"*).
    //
    // ⚠ **`collect_later` IS STILL A LAWFUL STORED VALUE** and the portal
    // still reads it; rows already carrying it are untouched (hard rule 4).
    // What was removed is the question, not the spelling.
    // ✅ **`DEF-CUS-10041` (PO 2026-10-11) — THE QUESTION IS BACK, ASKED
    // OUTRIGHT.** *"user can make the payment now or user can make the payment
    // later"* reverses the 2026-09-22 cut described above: `Pay now` /
    // `Pay later` is the clerk's own answer, and no answer is still sent as
    // nothing rather than a guess.
    fee_timing:
      form.fee_timing === "collect_now" || form.fee_timing === "collect_later"
        ? form.fee_timing
        : undefined,
    fee_due_by: form.fee_due_by === "" ? undefined : form.fee_due_by,
    // `DEF-CUS-10041` follow-up (walk, 2026-10-11) — Pay later carries NO
    // method: switching Wire → Pay later had kept `wire`, and the confirmation
    // then said "How it was paid: wire" for a fee nobody had paid.
    fee_method: form.fee_timing === "collect_now" ? form.fee_method.trim() : "",
    // ⊕ `CR-161-BRC10` W6 — the answered fields only, and no key at all when
    // nothing was typed, so a utility with no fields posts what it always did.
    ...(requestCustomPayload(form.custom) === undefined
      ? {}
      : { custom_data: requestCustomPayload(form.custom) }),
  };
}

/**
 * The billing address's five parts, as `CAPTURE_FIELDS` names them — or five
 * empty strings when *Same as the service address* is ticked.
 */
/**
 * Lane CF-1 — **WHERE THE BILL GOES, SENT UNDER ITS ONE NAME** (`mailing_*`,
 * the name every other screen uses). Nothing while *Same as service address*
 * is ticked, the five US parts when it is not. The server writes the older
 * `billing_*` columns alongside, so every reader that predates the rename
 * keeps the same answer.
 */
export function mailingPayload(form: CaptureForm): {
  mailing_same: boolean;
  mailing_line1: string;
  mailing_line2: string;
  mailing_city: string;
  mailing_state: string;
  mailing_postal_code: string;
} {
  const parts = billingPartsPayload(form);
  return {
    mailing_same: form.billing_address_same,
    mailing_line1: parts.billing_line1_as_given,
    mailing_line2: parts.billing_line2_as_given,
    mailing_city: parts.billing_city_as_given,
    mailing_state: parts.billing_state_as_given,
    mailing_postal_code: parts.billing_postal_code_as_given,
  };
}

export function billingPartsPayload(form: CaptureForm): {
  billing_line1_as_given: string;
  billing_line2_as_given: string;
  billing_city_as_given: string;
  billing_state_as_given: string;
  billing_postal_code_as_given: string;
} {
  const keep = (value: string): string => (form.billing_address_same ? "" : value.trim());
  const parts = form.billing_address;
  return {
    billing_line1_as_given: keep(parts.line1),
    billing_line2_as_given: keep(parts.line2),
    billing_city_as_given: keep(parts.city),
    billing_state_as_given: keep(parts.state),
    billing_postal_code_as_given: keep(parts.postal_code),
  };
}

/**
 * The three names the ruling of 2026-09-15 adds, built ONLY for the kind that
 * is asked for them. Typed loosely because `CapturePayload` cannot declare
 * them until lane G widens `CAPTURE_FIELDS` — which is the same fact
 * `IDENTITY_CAPTURE_ACCEPTED` records, in the type system rather than in a
 * boolean.
 */
export function identityPayload(form: CaptureForm): Record<string, string> {
  const asked = new Set(identityFieldsFor(form.applicant_kind));
  const out: Record<string, string> = {};
  if (asked.has("dob")) {
    out.date_of_birth = form.date_of_birth;
  }
  if (asked.has("licence")) {
    // Same rule as the SSN: absent when nothing was typed over one on file.
    const licence = maskedFieldValue(form.drivers_licence, form.drivers_licence_on_file);
    if (licence !== undefined) {
      out.drivers_licence = licence;
    }
  }
  if (asked.has("tax_id")) {
    // A number on file shows as its mask and is never re-sent unless retyped
    // (`maskedFieldValue`, `DEF-CUS-6427`'s rule for the SSN).
    const tax = maskedFieldValue(form.tax_id, form.tax_id_on_file);
    if (tax !== undefined) {
      out.tax_id = tax;
    }
  }
  return out;
}

/**
 * **ONE SERVICE'S START, AS THE CLERK SEES IT — the one place that decides it
 * (`DEF-CUS-6409`, PO reports 2026-09-23).**
 *
 * PO ruling 2026-09-22, option (b), verbatim: *"Keep both, make one fill the
 * other — the per-service dates default from the job date, and a clerk
 * overrides where a service differs"*. So a service's start is:
 *
 *   * the date the clerk typed in THAT service's box, where they typed one;
 *   * `null` where they deliberately EMPTIED that box (`""` is stored in
 *     `service_starts` — *not given* is still a thing a clerk can say);
 *   * otherwise the job's `Connection date` — the default the box shows.
 *
 * ⚠ **THIS WAS A DISPLAY-ONLY FALLBACK AND THAT WAS THE DEFECT.** Step 2's box
 * showed `form.service_starts[code] ?? form.requested_start`, while the payload
 * and the review both read `form.service_starts` alone. So a clerk saw
 * `15-Oct-26` in every service's box, the POST carried
 * `{code: "water", requested_start: null}`, the review printed `—`, the server
 * stored NULL, and the request detail printed `—` too — for SR-26-0016, Water,
 * Sewer, Trash and Fire all four. **The date was shown and never captured.**
 * Every surface now asks this function, so the box, the payload, the review and
 * — through what is stored — the detail cannot disagree again.
 *
 * ⚠ **THE FORM STILL HOLDS NO COPY OF THE DEFAULT.** `service_starts[code]`
 * stays ABSENT until a clerk types, so a clerk who corrects the job date on step
 * 2 sees every untouched service follow it, and the next save sends the new
 * date. The default is RESOLVED at the moment it is read, never frozen into
 * state — that half of the previous note was right and is kept.
 */
export function serviceStart(form: CaptureForm, code: string): string | null {
  const own = form.service_starts[code];
  if (own !== undefined) {
    return own === "" ? null : own;
  }
  return form.requested_start === "" ? null : form.requested_start;
}

/**
 * **THE DRAWN PER-SERVICE STARTS, in the shape lane F's route takes.** One
 * entry per PICKED service, in the order the clerk picked them, so a service
 * dropped from the multiselect cannot leave a date behind it. Each date is
 * `serviceStart`'s — the clerk's own, or the job date it defaults from.
 *
 * ⚠ **THIS IS THE PAYLOAD AND NOT THE CALL.** `setServiceRequestServices` is the
 * single call site; keeping the shape pure is what lets a test assert it
 * without a server. Step 6's review reads THIS, so what the clerk checks is
 * what was sent.
 */
export function serviceStartsPayload(
  form: CaptureForm,
): { code: string; requested_start: string | null }[] {
  return form.services.map((code) => ({ code, requested_start: serviceStart(form, code) }));
}

/**
 * **IS THIS SERVICE ALREADY ON THE PROPERTY? — the drawn `STATUS` column, and
 * the honest half of it.**
 *
 * ⚠ **ONLY THE NEGATIVE IS DERIVED, AND THE POSITIVE IS NOT GUESSED.** A
 * request whose address matched NO premises has nothing on site by
 * construction, so every service on it is `new` and that is a fact this screen
 * genuinely holds. Where a premises DID match, whether THAT service is already
 * connected lives in the metering register and no seam serves it to this
 * screen — so the answer is `null` and the cell draws this page's absence
 * glyph.
 *
 * **`null` is never drawn as `New`.** A screen that filled the gap with the
 * drawn value would be asserting something about somebody's property, and the
 * whole reason the PO wanted this column is that a clerk should not promise a
 * date against a service that is already there.
 *
 * ⚠ **IT IS PER REQUEST TODAY AND THE COLUMN IS PER ROW ON PURPOSE.** The row
 * shape carries its own `status`, so the day a per-service answer is served
 * the derivation moves and nothing else does.
 */
export function serviceOnSite(form: CaptureForm): ServiceOnSite {
  return form.picked_premise_no === "" && form.picked_unit_no === "" ? "new" : null;
}

/**
 * The Services table hands back its WHOLE list; this is what that means to the
 * form.
 *
 * ⚠ **A ROW WITH NO SERVICE IN IT YET IS NOT A SERVICE.** It is dropped from
 * `services`, because `set_services` REPLACES the set and an empty code is not
 * one the server has ever heard of. The row itself survives on screen through
 * `pendingServiceRow`; the caller sets that from the same list.
 */
export function serviceRowsToForm(
  form: CaptureForm,
  rows: readonly ServiceTableRow[],
): Partial<CaptureForm> {
  const answered = rows.filter((row) => row.code !== "");
  const starts: Record<string, string> = {};
  for (const row of answered) {
    // ⚠ **AN EMPTY BOX IS *NOT GIVEN*, NOT *CLEARED*, AND THE DIFFERENCE COST A
    // TEST ITS RED.** A row that has just been given its service has an empty
    // date for one render, before `serviceStart` fills it from the job's.
    // Writing that `""` into `service_starts` would store an explicit blank,
    // `serviceStart` would read it back as *not given*, and the POST would
    // carry `requested_start: null` for a service the screen was showing a
    // date against — `DEF-CUS-6409` coming straight back.
    if (row.requested_start === "") continue;
    // The job's own date is not an override of itself. Under the PO's
    // 2026-09-22 option (b) the fallback runs job → service, so a row left
    // agreeing with the job stays ABSENT and follows it when the clerk moves
    // it. Only a DIFFERENT date is a per-service fact.
    if (row.requested_start === form.requested_start) continue;
    starts[row.code] = row.requested_start;
  }
  return { services: answered.map((row) => row.code), service_starts: starts };
}

// ══════════════════════════════════════════════════════════════════════════
// **EDIT — A SAVED REQUEST, LOADED; AND ONLY WHAT CHANGED, SENT BACK**
// (`DEF-CUS-6427` + `DEF-CUS-5880`, the Edit ruling of 2026-09-23)
// ══════════════════════════════════════════════════════════════════════════
//
// The ruling set the ORDER and the order is the data-loss guard: load the
// saved request into the form first, keep a masked value out of every payload,
// and only then open a door onto it. These four functions are that order, and
// each is pure so a test can hold it without a server.

/**
 * A value served MASKED, as the payload should carry it.
 *
 *   · typed      → the typed value (the clerk is replacing it);
 *   · not typed, one ON FILE → `undefined`: the key is ABSENT, and an absent
 *     key is how `update_request` reads *unchanged* (it is `partial=True`);
 *   · neither    → `""`, which the server stores as NULL — exactly what a
 *     new capture always sent, so a request typed from scratch is unchanged.
 *
 * ⚠ **THERE IS NO BRANCH THAT RETURNS THE MASK, AND THERE MUST NEVER BE ONE.**
 */
export function maskedFieldValue(typed: string, onFile: string): string | undefined {
  const value = typed.trim();
  if (value !== "") {
    return value;
  }
  return onFile === "" ? "" : undefined;
}

/** `5236` → `••• ••• • 5236`, the request detail's own SSN glyphs. */
export function ssnOnFileMask(lastFour: string): string {
  return lastFour === "" ? "" : `\u2022\u2022\u2022 \u2022\u2022\u2022 \u2022 ${lastFour}`;
}

/** `9566` → `•••••9566`, `maskIdentifier`'s shape for a licence. */
export function licenceOnFileMask(lastFour: string): string {
  return lastFour === "" ? "" : `\u2022\u2022\u2022\u2022\u2022${lastFour}`;
}

/**
 * **THE SAVED REQUEST, AS THE FORM — `DEF-CUS-5880`.** Until this existed the
 * wizard opened on `?request=` with every box EMPTY: the request was fetched
 * into `draft` and never into `form`, and the next save PATCHed those empty
 * boxes over the stored email, phone and SSN.
 *
 * Every field comes from what the detail read ALREADY serves; nothing here is
 * invented and nothing is a second copy of a server rule.
 *
 * ⚠ **THE SSN AND LICENCE OPEN EMPTY.** Only their last four exist in the
 * browser (`BR-CUS-092(c)`), so they land in `ssn_on_file` /
 * `drivers_licence_on_file` for the placeholder and never in a value.
 *
 * ⚠ **A SERVICE'S DATE IS KEPT ONLY WHERE IT DIFFERS FROM THE JOB'S.** A start
 * equal to the job date is left to FOLLOW it — `serviceStart`'s default — so a
 * clerk correcting the job date sees the untouched services move with it, as
 * they did on the day of capture. A service stored with NO date on a job that
 * has one is kept as `""`, which is *not given* rather than *the job's*.
 *
 * ⚠ **THE MATCHED PREMISES IS LOADED AS THE PICK, FOR DISPLAY.** Step 3 reads
 * `picked_premises_id` to decide between the matched block and the typed
 * parts; the id is never SENT unless the clerk changes it
 * (`changedCapturePayload`), so a resolver's match is not turned into a pick
 * by opening the form.
 *
 * `tax_id` and the counter tender are not held on a request
 * (`TAX_ID_CAPTURE_ACCEPTED`, `TENDER_CAPTURE_ACCEPTED`), so they open empty —
 * the truth, not a gap.
 */
export function hydrateCaptureForm(detail: ServiceRequestDetail): CaptureForm {
  const empty = emptyCaptureForm();
  const text = (value: string | null | undefined): string => value ?? "";
  const applicant = detail.applicant;
  const place = detail.location_and_services;
  const identifier = applicant.identifier;
  const coApplicant = applicant.co_applicant;
  const jobDate = text(detail.header.requested_start);
  const serviceStarts: Record<string, string> = {};
  for (const row of place.services) {
    const own = text(row.requested_start);
    if (own !== jobDate) {
      serviceStarts[row.code] = own;
    }
  }
  const matched = text(place.resolved_premises_id) !== "";
  const locality = place.premise_locality;
  return {
    ...empty,
    channel: text(detail.header.channel) || empty.channel,
    applicant_kind: text(applicant.person_or_company) || empty.applicant_kind,
    applicant_name: text(applicant.name),
    applicant_email: text(applicant.email),
    applicant_phone: text(applicant.phone),
    ssn: "",
    ssn_on_file: identifier.ssn_present ? text(identifier.ssn_last4) || "\u2022\u2022\u2022\u2022" : "",
    date_of_birth: text(applicant.date_of_birth),
    drivers_licence: "",
    drivers_licence_on_file: identifier.drivers_licence_present
      ? text(identifier.drivers_licence_last4) || "\u2022\u2022\u2022\u2022"
      : "",
    add_co_applicant:
      (applicant.co_applicants ?? []).length > 0 ||
      [coApplicant.name, coApplicant.email, coApplicant.phone].some((value) => text(value) !== ""),
    // ⊕ Lane CF-1 — the full cards, each identifier read back as its LAST
    // FOUR only and therefore never put in a box (the server keeps the stored
    // number when a card is re-sent without one — `_keep_stored_secrets`). A
    // request from before the cards carries the three columns: one card.
    co_applicants: coApplicantDrafts(applicant),
    tax_id_on_file: identifier.tax_id_present ? text(identifier.tax_id_last4) || "••••" : "",
    gov_id_last4: text(applicant.gov_id_last4),
    contact_by: text(applicant.contact_by),
    prefs_on: applicant.preferences?.paperless === true || applicant.preferences?.sms_reminders === true,
    paperless: applicant.preferences?.paperless === true,
    sms_reminders: applicant.preferences?.sms_reminders === true,
    preferred_language: text(applicant.language),
    co_applicant_name: text(coApplicant.name),
    co_applicant_email: text(coApplicant.email),
    co_applicant_phone: text(coApplicant.phone),
    account_type_code: text(applicant.customer_category?.account_type?.code),
    account_subtype_id: text(applicant.customer_category?.account_subtype?.id),
    requested_start: jobDate,
    services: place.services.map((row) => row.code),
    service_starts: serviceStarts,
    address_as_given: text(place.address_as_given),
    address_unit_as_given: text(place.address_unit_as_given),
    picked_premises_id: matched ? text(place.resolved_premises_id) : "",
    picked_premise_no: matched ? text(place.resolved_premises_no) : "",
    picked_premises_city: matched ? text(locality?.city) : "",
    picked_premises_state: matched ? text(locality?.state) : "",
    picked_premises_postal: matched ? text(locality?.postal_code) : "",
    picked_unit_id: matched ? text(place.resolved_unit_id) : "",
    picked_unit_no: matched ? text(place.resolved_unit_no) : "",
    plot_or_parcel: text(place.plot_or_parcel),
    what_is_being_built: text(place.what_is_being_built),
    units_on_property: place.units_on_property === null ? "" : String(place.units_on_property),
    address_city_as_given: text(place.address_city_as_given),
    address_state_as_given: text(place.address_state_as_given),
    address_postal_code_as_given: text(place.address_postal_code_as_given),
    billing_address_same: place.billing_address_same,
    billing_address: {
      line1: text(place.billing_line1_as_given),
      line2: text(place.billing_line2_as_given),
      city: text(place.billing_city_as_given),
      state: text(place.billing_state_as_given),
      postal_code: text(place.billing_postal_code_as_given),
    },
    property_type: text(place.property_type),
    fee_timing: text(detail.fees.fee_timing),
    fee_due_by: text(detail.fees.fee_due_by),
    // `cheque` is the request's old spelling; the utility's list says `check`.
    fee_method: text(detail.fees.fee_method) === "cheque" ? "check" : text(detail.fees.fee_method),
    what_they_said: text(detail.decision.what_they_said),
    custom: hydrateRequestCustom(detail.custom_data),
  };
}

/** A pick travels as a PAIR. Lane E's contract reads *both null* as UNDO, so a
 *  lone `picked_unit_id: null` (the clerk cleared only the unit) would drop the
 *  premises as well if the unchanged premises id were left out. */
export const PICK_PAYLOAD_KEYS = ["picked_premises_id", "picked_unit_id"] as const;

/** The payload keys that say WHERE — a change to any of them re-runs the
 *  resolver, which writes evidence and has its own audit row. */
export const ADDRESS_PAYLOAD_KEYS = [
  "address_as_given",
  "address_unit_as_given",
  "address_city_as_given",
  "address_state_as_given",
  "address_postal_code_as_given",
  ...PICK_PAYLOAD_KEYS,
] as const;

/**
 * **ONLY WHAT CHANGED — `DEF-CUS-6427` trap (c), and the reason one edited
 * field can no longer blank twelve others.**
 *
 * `update_request` is `partial=True`: a key it is not sent is a column it does
 * not touch. So the safe PATCH is the difference between the form as it was
 * LAST SAVED (or loaded) and the form now — never the whole form, which is
 * what every step sent until today. A clerk who opens `SR-26-0048` and corrects
 * the phone sends `{"applicant_phone": "512-555-0199"}` and nothing else, and
 * the `service_request.updated` audit row then records exactly that one
 * before → after, which is what hard rule 7 is for.
 *
 * ⚠ **A KEY THAT WENT FROM A VALUE TO NOTHING IS SENT AS `null`**, because
 * `capturePayload` spells *empty* as `undefined` for a few dates and codes,
 * and `undefined` vanishes from JSON — so clearing the job date would
 * otherwise never reach the server.
 *
 * ⚠ **THE MASKED PAIR IS DECIDED HERE, NOT BY COMPARING PAYLOADS.** A number
 * TYPED and different from what was last saved is sent; an on-file number the
 * clerk CLEARED (only `clearOtherKind` does that) is sent as `""`; everything
 * else — including every save that simply did not touch the box — sends no
 * key at all.
 */
export function changedCapturePayload(saved: CaptureForm, next: CaptureForm): CapturePayload {
  const before = capturePayload(saved) as Record<string, unknown>;
  const after = capturePayload(next) as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
    // `custom_data` is decided below, per record type and per key — never as
    // a whole blob, which would re-send a stored answer to a field switched
    // off since and be refused by name (`CR-161-BRC10` W6).
    if (key === "ssn" || key === "drivers_licence" || key === "tax_id" || key === "custom_data") {
      continue;
    }
    if (JSON.stringify(before[key]) === JSON.stringify(after[key])) {
      continue;
    }
    out[key] = after[key] === undefined ? null : after[key];
  }
  if (PICK_PAYLOAD_KEYS.some((key) => key in out)) {
    for (const key of PICK_PAYLOAD_KEYS) {
      out[key] = after[key] ?? null;
    }
  }
  const customChanges = changedRequestCustom(saved.custom, next.custom);
  if (customChanges !== undefined) {
    out.custom_data = customChanges;
  }
  const masked = [
    ["ssn", "ssn_on_file"],
    ["drivers_licence", "drivers_licence_on_file"],
    ["tax_id", "tax_id_on_file"],
  ] as const;
  for (const [typedKey, onFileKey] of masked) {
    const typed = next[typedKey].trim();
    const typedBefore = saved[typedKey].trim();
    if (typed !== "") {
      if (typed !== typedBefore) {
        out[typedKey] = typed;
      }
    } else if (next[onFileKey] === "" && (saved[onFileKey] !== "" || typedBefore !== "")) {
      out[typedKey] = "";
    }
  }
  return out as CapturePayload;
}

/**
 * `123-45-6789` → `••• ••• • 6789`, the exact glyph string B19 §7 draws.
 *
 * ⚠ **THIS IS A CONVENIENCE FOR ONE SCREEN, NOT THE PRODUCT'S MASKING RULE.**
 * The masking that matters is a SERVER projection: `service_request_reads`
 * calls `crypto.last_four()` and the full number never reaches the browser at
 * all (BR-CUS-092(c)). This function exists only because the CAPTURE WIZARD is
 * the one place the full value legitimately sits in front-end state — the clerk
 * typed it thirty seconds ago — and step 6 should not read it back in full over
 * a counter a customer may be standing at.
 *
 * **It is never used on data that came from the server.** If you find yourself
 * calling it on a fetched payload, the payload is carrying something it should
 * not and the fix is on the server.
 */
export function maskSsn(value: string): string {
  const digits = value.replace(/[^0-9A-Za-z]/g, "");
  if (digits === "") {
    return "";
  }
  // Fewer than four characters: there is no fifth character to hide and padding
  // would invent one, so every character is hidden rather than none.
  const tail = digits.length <= 4 ? "" : digits.slice(-4);
  return tail === "" ? "\u2022".repeat(digits.length) : `\u2022\u2022\u2022 \u2022\u2022\u2022 \u2022 ${tail}`;
}

/** REQ-03.6's sub-line: *"2 fields left blank. None of them stop the request
 *  being created."* — a computed count that repeats step 4's posture. It counts
 *  the OPTIONAL fields nobody filled; the required ones are gated at their own
 *  step and are never part of this number. */
export function blankOptionalCount(form: CaptureForm): number {
  const optional = [
    form.address_unit_as_given,
    form.plot_or_parcel,
    form.what_is_being_built,
    form.what_they_said,
    form.applicant_email,
    form.applicant_phone,
  ];
  return optional.filter((value) => value.trim() === "").length;
}

/**
 * ══════════════════════════════════════════════════════════════════════════
 * **STEP 4's FOUR FILTER CHIPS — `All · Required · Missing · Rejected`**
 * (accounts blueprint p078, drawn above the attach controls).
 * ══════════════════════════════════════════════════════════════════════════
 *
 * ⚠ **`Required` IS THE TENANT'S CHECKLIST AND NEVER THIS SCREEN'S OPINION
 * (`BR-CUS-095`).** The checklist ships ENTIRELY UNTICKED, so on a fresh
 * tenant `Required` is legitimately empty and the chip says so instead of
 * naming two documents a jurisdiction may not ask for. The list comes off the
 * saved draft (`documents.checklist_required`), which is the SERVER's answer
 * for THIS request's job type.
 *
 * ⚠ **`Missing` MEANS *NO FILE HELD*, AND THIS PARAGRAPH SAID THE OPPOSITE
 * UNTIL 2026-09-19.** It read: *"`Missing` IS not ticked here, NOT no file
 * held. No route in this product accepts a file for a service request, so *no
 * file held* would be every row on every request forever — a filter that never
 * narrows anything is a control that does not work."* **Every clause of that
 * was true when it was written and the first one stopped being true this
 * morning**, when `apps/customers/service_request_documents.py` and
 * `core/document_shrink.py` landed a real store with a real multipart route.
 * A filter defined around an absence outlives the absence — hard-won law 1 —
 * so it is amended here BEFORE the table that uses it is built (step W), not
 * afterwards.
 *
 * ⚠ **AND `Missing` IS NOW ANSWERABLE, WHICH IS THE WHOLE POINT.** A row can
 * hold a file or not, so the chip really narrows: on the beta's `SR-26-0001`
 * it selects both rows, because both point at nothing.
 */
/**
 * What the browser's file picker filters on — `BR-SHL-031`'s allowlist.
 *
 * ⚠ **A CONVENIENCE, NEVER THE GUARD.** The server refuses anything outside
 * `service_request_documents.ALLOWED_CONTENT_TYPES` with a **415**, and a clerk
 * can defeat `accept` in any picker. This only saves them choosing a file that
 * was always going to be refused.
 *
 * ⚠ **IT IS THE KIT'S CONSTANT NOW, NOT A SECOND SPELLING — B14 rule 43.**
 * This line used to write the string out again, explaining that it was *"the
 * same string as `ACCOUNT_DOCUMENT_ACCEPT`, and deliberately not imported from
 * it"* because that one is typed against the ACCOUNT door and lives in
 * `api/endpoints.ts`. That objection was to borrowing another DOOR's constant
 * and it still stands; it was never an objection to a shared one.
 * `components/documents` is the shared one. The NAME survives because three
 * files and a test import it.
 */
export const SERVICE_REQUEST_DOCUMENT_ACCEPT = DOCUMENT_ACCEPT;

/** ⚠ **RE-EXPORTED FROM THE KIT, NOT DECLARED HERE — B14 rule 43.** The four
 *  chips are `components/documents`' now; these names survive because this
 *  page's own tests and two siblings import them by these spellings. */
export { DOCUMENT_FILTERS as DOC_FILTERS } from "@/components/documents";
export type { DocumentFilter as DocFilter } from "@/components/documents";

/**
 * Is this document REQUIRED on this request — and it is two facts, never one.
 *
 * p078's own prose says so: *"Two different facts decide whether a document is
 * required and both feed the same approval gate: the utility's own checklist
 * for this request type, and a clerk ticking `required on this request` because
 * of something about this applicant."* `BR-CUS-095` is the first
 * (`checklist_required`, and it ships ENTIRELY UNTICKED); `required_flag` on
 * the row is the second.
 *
 * ⚠ **`null` IS A THIRD ANSWER AND THE DRAWING DRAWS IT.** p078's `Anything
 * else` row shows `—` in REQUIRED, not `No`: the catch-all type is not
 * something a checklist can name, so *"is it required"* has no answer rather
 * than a negative one. The screen renders the em dash the drawing draws.
 */
export function docRequired(
  row: DocumentRow,
  detail: ServiceRequestDetail | null,
): boolean | null {
  if (row.doc_type === DOC_TYPE_OTHER) {
    return null;
  }
  const checklist = new Set(detail?.documents.checklist_required ?? []);
  return row.required === true || checklist.has(row.doc_type);
}

/**
 * The drawn table's rows, narrowed by the pressed chip.
 *
 * ⚠ **IT FILTERS ROWS, WHERE `filterDocTypes` FILTERED TYPES**, and that is the
 * drawing's change rather than a refactor: p078 draws a TABLE of what this
 * request holds, not a tick-list of what it could hold. A type with no row is
 * simply not on the request yet, and `Add another document` is how one arrives.
 */
export function filterDocRows(
  rows: readonly ServiceRequestDocument[],
  filter: DocumentFilter,
  detail: ServiceRequestDetail | null,
): ServiceRequestDocument[] {
  // ⚠ **THE NARROWING IS THE KIT'S; WHAT IS REQUIRED IS THIS REQUEST'S.** Rule
  // 43 clause 3 — share the field set, let each host own what only it knows.
  // Only this page can answer *is it on the tenant's checklist for this job
  // type*, so it hands that answer in and the kit does the filtering.
  return filterDocumentRows(rows, filter, (row) => docRequired(row, detail));
}

/** One row of step 3's drawn `LOOKED FOR` / `MATCHED` / `CONFIDENCE` table. */
export interface MatchRow {
  key: string;
  /** What to PRINT in `LOOKED FOR`. A plain string for the two address rows;
   *  the unit-count row needs a number interpolated, so it carries a catalogue
   *  key and its parameters instead and the render site resolves it — which
   *  is where B14 rule 33 lives (`DEF-CUS-5010`: a function that returns
   *  English decides wording somewhere nobody is looking). */
  lookedFor: string | { key: string; params: Record<string, string | number> };
  /** What to PRINT. `null` renders as the *Not supplied* absence — **never as
   *  an id**, which is `DEF-CUS-5386` coming straight back. */
  matched: string | { key: string; params: Record<string, string | number> } | null;
  /**
   * ⊕ **`agrees` AND `differs` ARE `BR-CUS-1055`'s, AND THEY ARE A FOURTH
   * AND FIFTH FACT RATHER THAN A RENAMING.** The three above are about an
   * ADDRESS — did we find the building, did we find the unit. These two are
   * about a CLAIM: the applicant says six flats, the register holds six rows,
   * and the drawing prints `Agrees` (p077). `differs` does not appear in the
   * drawing at all and is built anyway, because a confidence column that can
   * only ever say one word is a check that cannot fail (hard-won law 7).
   */
  confidence: "exact" | "onRecord" | "notFound" | "agrees" | "differs";
}

/**
 * **THE MATCH IS EVIDENCE, NEVER A DECISION** — the drawing says so beside the
 * table (p077) and `BR-CUS-070` is the rule under it: what the applicant said
 * is kept word for word and the match sits BESIDE it.
 *
 * ⚠ **IT READS THE SERVER'S ANSWER FIRST AND THE CLERK'S PICK ONLY AS A
 * FALLBACK, AND THE ORDER MATTERS.** `CR-094-BRC01` wave 1 lane B publishes
 * `resolved_premises_no`, `resolved_unit_no`, `resolved_premise_address` and
 * `resolved_match` on `location_and_services`; the server is what decides what
 * a picked row MEANS, and a screen that printed only what the clerk clicked
 * would go on saying *exact* after a PATCH the server refused.
 *
 * ⚠ **THE FALLBACK CHAIN IS LANE B'S OWN AND THE LAST LINK IS AN ABSENCE, NOT
 * AN ID.** *"Either NUMBER can be `null` while its id is not, because both
 * columns are nullable on a tenant that never turned its numbering series on.
 * Fall back to `resolved_premise_address`, and to a stated absence — **never to
 * the id**, which is the defect coming straight back."* (B14 rule 31,
 * `DEF-CUS-5386`.)
 *
 * ⚠ **THREE CONFIDENCES, AND THEY ARE THREE DIFFERENT FACTS.** `exact` is the
 * server's own `resolved_match` — the word the blueprint prints after each
 * number — or, before the first save, the clerk having picked the row out of
 * the register, where there is nothing to be uncertain about. `onRecord` is the
 * resolver having matched TEXT on its own, with no number to show for it.
 * `notFound` is `no_premise`. One word for all three would claim that a
 * resolver's guess and a clerk's choice are the same evidence.
 */
/** ⚠ **IT TAKES NO TRANSLATOR, AND THAT IS THE LAST FALLBACK BEING REMOVED
 *  RATHER THAN AN OVERSIGHT.** An earlier draft put the word *On record* into
 *  the MATCHED cell when there was no number to print — the same fact twice,
 *  beside the CONFIDENCE column that already says it. This function now
 *  returns FACTS and a confidence KEY; every word on the screen is looked up
 *  at the render site, which is where B14 rule 33 lives. */
export function matchRows(
  form: CaptureForm,
  detail: ServiceRequestDetail | null,
): MatchRow[] {
  /*
   * ⛔ **`registerUnits` IS GONE — PO report 2026-09-22, ROW 12's BLAST
   * RADIUS, ONE STEP FURTHER OUT THAN THE ROW ITSELF.**
   *
   * It carried how many units the register holds on the picked premises, for
   * the drawn third evidence row (`Units on the property · 6` → `6 units on
   * PR-0731` → `Agrees`, p077). That row is off the product, so the parameter
   * fed nothing — and an argument nothing reads is the same dead wiring as a
   * prop nothing passes, just pointing the other way.
   *
   * **It also retires a stated gap, which is the part worth recording.** The
   * read path has never served the register's own unit count
   * (`location_and_services.resolved_premise_unit_count` was the contract
   * wanted), so the number only ever existed on the picker row a clerk had
   * just chosen and a RESUMED draft had none. That gap was reported rather
   * than faked; with the row gone there is nothing left for it to be a gap
   * in. If the row ever comes back, so does the contract.
   */
  const place = detail?.location_and_services ?? null;
  const resolution = place?.resolution_kind ?? null;
  const serverFound = resolution !== null && resolution !== "no_premise";
  const rows: MatchRow[] = [];

  if (form.address_as_given.trim() !== "") {
    const number = place?.resolved_premises_no ?? null;
    const address = place?.resolved_premise_address ?? null;
    const picked = form.picked_premise_no === "" ? null : form.picked_premise_no;
    const matched = number ?? picked ?? address ?? null;
    rows.push({
      key: "premises",
      lookedFor: form.address_as_given.trim(),
      // ⚠ **THE LAST LINK IS AN ABSENCE AND NOT A WORD.** This read
      // `matched ?? (serverFound ? t(…confidence.onRecord) : null)`, which put
      // *On record* in the MATCHED column beside *On record* in the CONFIDENCE
      // column — the same fact twice, and a cell that looks like a value and
      // is not. Lane B's own instruction is *"fall back to
      // `resolved_premise_address`, and to a stated absence"*; the confidence
      // column is where *we matched something we cannot name* belongs.
      matched,
      confidence:
        place?.resolved_match !== null && place?.resolved_match !== undefined
          ? "exact"
          : picked !== null
            ? "exact"
            : serverFound
              ? "onRecord"
              : "notFound",
    });
  }

  if (form.address_unit_as_given.trim() !== "") {
    const number = place?.resolved_unit_no ?? null;
    const picked = form.picked_unit_no === "" ? null : form.picked_unit_no;
    const matched = number ?? picked;
    rows.push({
      key: "unit",
      lookedFor: form.address_unit_as_given.trim(),
      matched,
      confidence: matched === null ? "notFound" : "exact",
    });
  }

  // ⛔ **THE THIRD DRAWN ROW IS REMOVED — PO report 2026-09-22, row 12.**
  //
  // It compared the applicant's CLAIM about how many units are on the property
  // against what the register holds (`BR-CUS-1055`, p077). The PO removed the
  // question that produced the claim, from step 3 and from the request detail,
  // so the row has nothing to compare: on a new draft `units_on_property` is
  // always empty, and on a RESUMED draft it would print a number the clerk can
  // no longer see, edit or correct — which is worse than not printing it.
  //
  // ⚠ **THE OTHER TWO ROWS ARE UNTOUCHED** and so is every other thing this
  // table does. The address match and the unit match are the evidence a clerk
  // approves on; only the unit COUNT left.
  //
  // ⚠ **`registerUnits` IS NOW UNUSED AND IS KEPT AS A PARAMETER ON PURPOSE.**
  // Its own docstring records a real gap — the read path serves the applicant's
  // claim and nothing about the matched premises' own unit count, so a resumed
  // draft could never fill it — and that gap is still true and still worth the
  // next lane finding. Deleting the parameter would delete the finding with it
  // (hard-won law 1: a comment is a note, and this one has a caller).

  return rows;
}

/**
 * ══════════════════════════════════════════════════════════════════════════
 * **THE ONE CALL SITE FOR THE DRAWN PER-SERVICE STARTS — lane F's to fill.**
 * ══════════════════════════════════════════════════════════════════════════
 *
 * **WHAT IS TRUE TODAY, measured in `service_request_service.set_services`:**
 * every `ServiceRequestService` row is created with
 * `requested_start=request.requested_start` — the WHOLE JOB's date, copied
 * onto each service. The column the drawing needs therefore exists and holds
 * the same value on every row, and no route lets a caller set it per service.
 *
 * **`BR-CUS-1070` (lane F, 2026-09-15) HAS NOW PUBLISHED THE SHAPE, AND THIS
 * IS BUILT TO IT** — the ruling is in the decision log and the payload is
 * quoted there verbatim:
 *
 *     POST /service-requests/{id}/services
 *     { "services": [ { "code": "electric", "requested_start": "2026-12-05" },
 *                     { "code": "sewer",    "requested_start": null } ] }
 *
 * — the SAME replace-the-set route, widened to take objects as well as the bare
 * codes it takes now, *"so the guest portal, the sample seeder and every stored
 * caller keep working unchanged"*. `serviceStartsPayload(form)` builds exactly
 * that array, and `BR-CUS-1070` settles what a NULL means: *"an unset
 * per-service date stays NULL and means* not given*"* — it does **not** fall
 * back to the job's `Connection date`, and the job's date does not fall back to
 * the services'.
 *
 * ⚠ **THE RULING HAS LANDED AND THE ROUTE HAS NOT**, measured at
 * `2c8161fc`: `set_services` still creates every row with
 * `requested_start=request.requested_start`, so sending an object today is
 * refused as an unknown service code. The flag is therefore the ONE line that
 * moves when lane F's code lands — and `serviceStartsWriteIsLive` in the test
 * file goes RED on that day and names it, which is hard-won law 2's own
 * instruction: *when you write a hold, write the test that fires when the hold
 * expires.*
 *
 * ⚠ **WHAT IS NOT HELD IS THE CLERK'S TYPING.** The dates are live on screen,
 * held in `form.service_starts` and read back on step 6's review, exactly as
 * `p080` draws them. Nothing on this screen tells a clerk a date is kept that
 * is not.
 */
/**
 * ⛔ **THE HOLD IS OVER — `DEF-CUS-5416`, 2026-09-15.** This read `false` for
 * four hours while `POST /service-requests/{id}/services` was already live and
 * already accepting `{code, requested_start}` (`BR-CUS-1070`, lane F, landed
 * mid-build). The consequence was not a missing feature but a SILENT LOSS: a
 * clerk typed a start date per service on step 2, step 6 read it back to them
 * from form state, and the submit sent bare codes — so the dates were never
 * stored and nothing on screen said so.
 *
 * ⚠ **THAT IS HARD-WON LAW 2'S MIRROR, and the hold's own test is what makes
 * it survivable**: the assertion pinned this constant to `false`, so landing
 * the route turned it red and named itself instead of rotting quietly. Keep
 * the constant and keep the test — a hold with no expiry test is a promise
 * nobody is keeping.
 */
export const SERVICE_STARTS_WRITE_PATH_EXISTS = true;

/*
 * ⛔ **`TENDER_CAPTURE_ACCEPTED` AND `tenderPayload` ARE DELETED —
 * `DEF-CUS-10041`, PO 2026-10-11.** The hold read *"stays `false` while the
 * WIZARD has nowhere to post it; the day the fee step calls `fee-collection`
 * directly, it flips"*. That day is today: Pay now posts the tender through
 * `POST .../fee-collection` at submit (`RequestPaymentDetails.tsx`,
 * `feeCollectionBody`), so the step-3 card and check boxes stop being inputs
 * that were sent nowhere. The full card number still has no shape anywhere.
 */

/*
 * ⛔ **`serviceStartsSummary` IS DELETED — PO report 2026-09-22, rows 14/15.**
 *
 * It derived p080's `05/12/2026, all three` for step 6: one date said once,
 * with the agreement stated rather than three identical rows. Its single
 * caller was the review `Field` that is now `RequestedServicesTable`, which
 * shows the dates THEMSELVES — strictly more than the summary could, because
 * it can show one service starting on a different day from another.
 *
 * **Deleted rather than left exported**, because an exported helper nothing
 * calls is how a second spelling of a fact survives long enough for somebody
 * to reach for it. The FACT it derived is not lost: the server still serves
 * `location_and_services.requested_start_agreement`, which is the same three
 * answers (`agreed` · they differ · nobody gave one) derived once so the
 * wizard and the request's own screen cannot disagree — **and no screen reads
 * it today.** An earlier version of this note said `RequestedStart` still
 * rendered it; that component's last caller was the row this table replaced,
 * so it was dead UI within the hour and is deleted. The field stays served.
 */

/** `DEF-CUS-10041` — what is still owed on a draft as the server's string, or
 *  `""` when nothing is (no draft, no fee lines, paid, waived or `$0.00`). */
export function owingAmount(draft: ServiceRequestDetail | null): string {
  const amount = draft?.fees.outstanding.amount ?? "";
  return /^\d+(\.\d+)?$/.test(amount) && !/^0*(\.0*)?$/.test(amount) && draft?.fees.receipt_no == null
    ? amount
    : "";
}

/** Today as `YYYY-MM-DD`, the calendar-date string every date control in this
 *  product speaks. Used as the date of birth's upper bound. */
export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

type Translate = (key: string, params?: Record<string, unknown>) => string;

export interface ServiceRequestCapturePageProps extends RegionalProps {
  client?: ApiClient;
}

/**
 * ══════════════════════════════════════════════════════════════════════════
 * **REQ-03 — AND A BARE `/requests/new` IS ALWAYS A BLANK STEP 1
 * (`DEF-CUS-6410`, PO report 2026-09-23).**
 * ══════════════════════════════════════════════════════════════════════════
 *
 * PO, verbatim, over a screenshot of `SR-26-0016`'s confirmation: *"when user
 * click on cappture another button user should redirect on new request wizard
 * on step"* — step 1, blank.
 *
 * ⚠ **WHAT WAS WRONG WAS NOT THE BUTTON.** The confirmation is a STATE of this
 * page, drawn at `/requests/new?step=6&request=<id>`. `Capture another`
 * navigated to `/requests/new` — the SAME route — so React Router re-rendered
 * the component it already had instead of mounting a new one: the finished
 * request, its form, its fees and its `sent` flag all survived, and the clerk
 * stayed on the confirmation with the address bar saying they had left it.
 * Reproduced in Chromium on the tip before a line was read
 * (`10-scripts/po20260923_req_fix_walk.mjs`).
 *
 * **SO THE PAGE DECIDES, NOT THE BUTTON.** The wizard never writes a bare
 * address itself — every step move sets `?step=` and the first save sets
 * `?request=` — so an address with NEITHER, arrived at from one that had
 * either, can only be somebody coming in fresh: this button, the sidebar, a
 * link. That moment remounts the wizard under a new key, which discards every
 * piece of state it held (the draft id included, so the next request takes its
 * own number) without a hard reload. Any other door to `/requests/new` gets the
 * same guarantee for free.
 *
 * ⚠ **IT IS THE OPPOSITE OF A RESUME.** It only ever throws a request away.
 * The RESUME / EDIT door (`serviceRequestEditDoor.tsx`, `DEF-CUS-6427`) opens
 * this same page WITH `?request=`, so it is never bare and this never fires on
 * it. (This note used to point at `serviceRequestResumeHold.test.ts`, which
 * forbade any reopen path until the form loaded the saved request; it was
 * deleted on 2026-09-24 in the commit that wired the door, as it instructed.)
 */
export function ServiceRequestCapturePage(props: ServiceRequestCapturePageProps) {
  const [search] = useSearchParams();
  const visit = useFreshVisit(!search.has("request") && !search.has(STEP_PARAM));
  return <CaptureWizard key={visit} {...props} />;
}

/**
 * A counter that moves when the address BECOMES bare — never on the first
 * render, and never while it stays bare, so a clerk typing on a fresh step 1
 * is not wiped by a re-render. See `ServiceRequestCapturePage`.
 */
export function useFreshVisit(bare: boolean): number {
  const [visit, setVisit] = useState(0);
  const wasBare = useRef(bare);
  useEffect(() => {
    if (bare && !wasBare.current) {
      setVisit((previous) => previous + 1);
    }
    wasBare.current = bare;
  }, [bare]);
  return visit;
}

function CaptureWizard(props: ServiceRequestCapturePageProps) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  // ⚠ **`timeZone` AS WELL AS `dateFormat`, BECAUSE `uploaded_at` IS A
  // TIMESTAMP AND NOT A CALENDAR DATE.** The drawn `UPLOADED BY` cell prints
  // `S. Ortiz · 05/04/2026`; the date half of that comes out of an ISO instant,
  // so it has to be read in the tenant's zone or a document filed at 6pm in
  // Texas prints tomorrow's date. `formatDate` takes both (BR-SHL-023).
  const { dateFormat, timeZone } = useRegional(props);
  const [search, setSearch] = useSearchParams();

  const [form, setForm] = useState<CaptureForm>(emptyCaptureForm);
  // `DEF-CUS-5083` — the step is the URL's, not this component's. See
  // `captureStepFromParam`. `search`/`setSearch` are already in hand above for
  // `?request=`, so this adds no second source of truth for the query string.
  const step = captureStepFromParam(search.get(STEP_PARAM));
  const nav: WizardNavState = { step, reached: step };
  function setNav(next: WizardNavState): void {
    const params = new URLSearchParams(search);
    params.set(STEP_PARAM, String(next.step));
    setSearch(params, { replace: true });
  }
  const [draft, setDraft] = useState<ServiceRequestDetail | null>(null);
  const [sent, setSent] = useState<ServiceRequestDetail | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  /** `CR-161-BRC10` W6 — the server's `custom_data.<key>` refusals, marked on
   *  the control that drew the field (the kit's `FieldErrorsScope`). */
  const [customErrors, setCustomErrors] = useState<Record<string, string>>({});
  /** The three input registries a step's `Continue` asks — the SAME cached
   *  reads the controls make, so the check and the boxes cannot disagree. */
  const customRegistryResults = useQueries({
    queries: REQUEST_CUSTOM_ENTITIES.map((entity) => requestRegistryQuery(entity, client)),
  });
  const customersRegistry = customRegistryResults[0]?.data;
  const accountsRegistry = customRegistryResults[1]?.data;
  const premisesRegistry = customRegistryResults[2]?.data;
  const customRegistries: Partial<Record<RequestCustomEntity, CustomFieldRegistryEntry[]>> = {
    customers: customersRegistry ?? [],
    accounts: accountsRegistry ?? [],
    premises: premisesRegistry ?? [],
  };
  /** ⚠ **STEP 4's CHIP LIVES IN `DocumentCapture` NOW — B14 rule 43.** Which
   *  chip is pressed is nothing the server stores and nothing this page needs
   *  back, so it went with the block. Step 3's search box is VIEW state for the
   *  same reason and stays, because step 3 is the only thing that reads it. */
  const [premisesQuery, setPremisesQuery] = useState("");
  /** `DEF-CUS-9041` — what the clerk types into the street box on a SUBMITTED
   *  request. It is a SEARCH and nothing else: `address_as_given` is the
   *  applicant's and is never sent once the request has left draft
   *  (`BR-CUS-070`), so the box holds this instead of the form value. */
  const [amendSearch, setAmendSearch] = useState<string | null>(null);
  const navigate = useNavigate();

  // ⛔ **THE `Attaching one` FORM, ITS FOUR CONTROLS AND `addDocument` /
  // `openDocument` ARE GONE — LANE CF-1, 2026-10-18.** Step 1's documents are
  // the SHARED documents table now (`MoveInDocumentsTable`, drawing set
  // `customer-forms-2026-10-18` image 03): one row per required type, + Add
  // document, an upload per row. Each file is still written to the request the
  // moment it is uploaded (`stageRequestDocument`), so a document still
  // survives a draft — which was the reason the old form wrote on the press.

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 5 · THE APPLICATION FEE COMES OUT OF THE TENANT'S CHARGE CODES
  //
  // **PO report 2026-09-22, row 11.** The step showed `Quoted` and
  // `Outstanding` as read-only figures and offered no way to make either of
  // them anything but `$0.00` — `DEF-CUS-5904`, a door that has been exported
  // and called by nothing since the module was built.
  //
  // ⚠ **`status: "active"` IS NOT A TIDINESS FILTER.** A deactivated charge is
  // one the utility has STOPPED selling (`IS-1`, deactivate-first), and
  // offering one here would quote a price the tenant retired.
  // ══════════════════════════════════════════════════════════════════════════
  const feeChargesQuery = useQuery({
    queryKey: ["charges", "service-request-fee"],
    queryFn: () => getCharges({ per: 200, filters: { status: "active" } }, client),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const feeCodes = useMemo(
    () => chargeCodeOptions(feeChargesQuery.data?.results ?? [], canBeRaisedOnItsOwn),
    [feeChargesQuery.data],
  );
  const [feeBusy, setFeeBusy] = useState(false);
  const [feeError, setFeeError] = useState<string | null>(null);
  /**
   * **AN UNANSWERED ROW, IN EACH OF THE TWO TABLE ARRAYS — REQ-03 tasks 8
   * and 9.**
   *
   * The drawing puts `+ Service` and `+ Fee` UNDER their tables and the
   * chooser IN the row, which means a row has to exist before it has anything
   * in it. That half-row is the only piece of either table that is not already
   * either form state or a stored server row, so it is held here — as a
   * BOOLEAN and not as a half-built record, because a half-built fee line is a
   * thing no reader could tell from a real one.
   */
  const [pendingServiceRow, setPendingServiceRow] = useState(false);
  const [pendingFeeRow, setPendingFeeRow] = useState(false);

  /**
   * **`+ Add a fee ▾` — pick a fee and it becomes a row** (PO approval
   * 2026-09-23). The pick IS the add: there is no second button, because the
   * row that appears is the confirmation, and its ✕ is the undo.
   */
  async function addTheFee(code: string): Promise<void> {
    const id = draft?.header.id ?? "";
    const row = feeCodes.find((candidate) => candidate.code === code);
    if (id === "" || row === undefined) return;
    setFeeBusy(true);
    setFeeError(null);
    try {
      // ⚠ **`unit_amount` IS THE STORED FOUR-PLACE STRING AND NEVER THE
      // DISPLAY ONE.** The client's own docstring says why the server refuses a
      // JSON float — `25.10` arrives as `25.099999999999998` — and sending
      // `amount_display` would post a number rounded for a person to read as
      // the money a customer is charged. CLAUDE.md rule 2.
      const tab = await addServiceRequestFee(
        id,
        {
          charge_code: row.code,
          charge_code_id: row.id,
          unit_amount: row.amount ?? "0",
          quantity: "1",
          // ⊕ `Charged per · Request` — an application fee is raised once,
          // for this request, which is what a quantity of 1 already says. The
          // build's quote lines speak the same vocabulary (`per meter`, …).
          basis: "per request",
          description: row.name,
        },
        client,
      );
      setDraft((previous) => (previous === null ? previous : { ...previous, fees: tab }));
    } catch (error) {
      // ⛔ **LAYER 2 OF THE PO's 2026-09-21 RULING.** A picker filtered when
      // this panel mounted cannot know that a tenant edited the code on
      // Settings since — so the refusal lands HERE, in words, on the panel that
      // owns the field, rather than leaving as a 500.
      setFeeError(isApiError(error) ? t(error.messageKey, error.params) : t("api.error.unexpected"));
    } finally {
      setFeeBusy(false);
    }
  }
  /**
   * The fee table's ✕ — `DELETE …/fees/{id}`. **OQ-357 closed 2026-09-23 as
   * "both"**: a draft's line is removed, a submitted request's is waived. The
   * server refuses a waived line and a paid one by name and the refusal lands
   * on the panel that owns the table.
   */
  async function removeTheFee(line: ServiceRequestFeeLine): Promise<void> {
    const id = draft?.header.id ?? "";
    if (id === "") return;
    setFeeBusy(true);
    setFeeError(null);
    try {
      const tab = await removeServiceRequestFee(id, line.id, client);
      setDraft((previous) => (previous === null ? previous : { ...previous, fees: tab }));
    } catch (error) {
      setFeeError(isApiError(error) ? t(error.messageKey, error.params) : t("api.error.unexpected"));
    } finally {
      setFeeBusy(false);
    }
  }

  // ⛔ **`waiveTheFee` AND ITS DIALOG LEAVE THIS SCREEN WITH THE `Waive`
  // COLUMN — REQ-03 task 9, 2026-09-29.** `03-service-1440.png` draws SIX
  // columns and a waive is not one of them.
  //
  // ⚠ **NO CAPABILITY IS LOST, WHICH IS THE ONLY GROUND ON WHICH A CONTROL
  // MAY BE REMOVED HERE** (the redesign's own second defect: *"Removing that
  // capability is not what was asked for"*). Waiving lives on the REQUEST, in
  // `RequestFeeHandoverModal` off the detail's Fees panel, which is where
  // `BR-CUS-090` puts money so the person who takes it and the person who
  // reconciles it are two people. Proved before the removal: the detail page
  // passes `onWaive` and opens that modal with the tenant's own reasons.
  /** The category last POSTed for this draft — see `persist`. */
  const sentCategory = useRef<{ code: string; subtype: string }>({ code: "", subtype: "" });

  const existingId = search.get("request");

  /**
   * **THE FORM AS THE SERVER LAST HAD IT** — set when a saved request is
   * loaded, and again after every successful save. `changedCapturePayload`
   * measures against it, so a PATCH carries only what the clerk changed
   * (`DEF-CUS-6427`). `null` only before the first save of a NEW request, which
   * is a POST of the whole form and has nothing to blank.
   */
  const savedForm = useRef<CaptureForm | null>(null);
  /** The per-service payload last POSTed, so an unchanged set is not re-sent
   *  (every send is a write and an audit row). */
  const savedServices = useRef<string | null>(null);
  /** Which request the form was loaded FROM — hydration happens once per id,
   *  never again on a refetch, so it cannot overwrite a clerk mid-edit. */
  const hydratedFrom = useRef<string | null>(null);

  // A draft opened from the list or from a half-finished session. BR-CUS-093's
  // whole point: *"the applicant rings back Thursday quoting it, the clerk
  // finds it in `Draft` and finishes it."*
  //
  // ✅ **AND NOW IT IS LOADED INTO THE FORM — `DEF-CUS-5880`, 2026-09-24.** This
  // query set `draft` and nothing else, so the wizard opened with every box
  // EMPTY over a request the server held in full, and the next save PATCHed
  // those empty boxes over the stored email, phone and SSN. That is why the
  // door onto this address was held shut by a test for five days. The form is
  // now built from the fetched request (`hydrateCaptureForm`) BEFORE the wizard
  // renders a single input — see `loadingExisting` below — and `savedForm`
  // records it, so the first save sends only what the clerk changed.
  const existingQuery = useQuery({
    queryKey: ["service-request-draft", existingId],
    queryFn: async () => {
      const loaded = await getServiceRequest(existingId ?? "", client);
      if (hydratedFrom.current !== loaded.header.id) {
        const hydrated = hydrateCaptureForm(loaded);
        hydratedFrom.current = loaded.header.id;
        savedForm.current = hydrated;
        savedServices.current = JSON.stringify(serviceStartsPayload(hydrated));
        sentCategory.current = {
          code: hydrated.account_type_code,
          subtype: hydrated.account_subtype_id,
        };
        setForm(hydrated);
      }
      setDraft(loaded);
      return loaded;
    },
    enabled: existingId !== null && existingId !== "" && draft === null,
  });
  /** A request is being opened and is not in hand yet — nothing is drawn that
   *  a clerk could type into, because anything typed now would be overwritten
   *  by the load or, worse, saved over it. */
  const loadingExisting = existingId !== null && existingId !== "" && draft === null;
  /**
   * **THE REQUEST HAS LEFT DRAFT — a correction, not a capture.** Its buttons
   * change with it: `Save changes` instead of `Save as draft` and `Submit`
   * (a submitted request is not submitted twice), and the page returns to the
   * request once saved. Read from the LOADED state, never from the door that
   * opened the wizard, so a shared link cannot disagree with the record.
   */
  const amending = draft !== null && draft.header.state !== "draft";

  // ✅ BR-CUS-094 — the SEVEN, in the ruling's order, plus `government` as
  // LEGACY. Served as two lists precisely so a screen cannot flatten them.
  const categoriesQuery = useQuery({
    queryKey: ["service-request-categories"],
    queryFn: () => getServiceRequestCategories(client),
  });

  // *"Everything we supply is listed."* — the TENANT's enabled services, not a
  // hard-coded ten. A tenant that sells three gets three cards, never seven
  // empty ones.
  const servicesQuery = useQuery({
    queryKey: ["tenant-services"],
    queryFn: () => getTenantServices(client),
  });

  // ══════════════════════════════════════════════════════════════════════════
  // `Connection date` OPENS 15 WORKING DAYS OUT — PO ruling 2026-09-22
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **THE SERVER COMPUTES IT; THIS ONLY ASKS.** Working days means weekends
  // AND this tenant's public holidays out, and neither is in the browser. On
  // the demo tenant the calendar is the difference between 2026-10-13 and
  // **2026-10-14** (Columbus Day sits in the window), so a weekday count here
  // would be quietly wrong by a day and would disagree with every other
  // business-day figure the product prints.
  const captureDefaultsQuery = useQuery({
    queryKey: ["service-request-capture-defaults"],
    queryFn: () => getServiceRequestCaptureDefaults(client),
    // A default is worth one read per wizard, not one per step change.
    staleTime: 5 * 60 * 1000,
  });

  // ⚠ **IT SEEDS ONCE, ONLY A BLANK FIELD, AND ONLY ON A WIZARD THAT IS NOT
  // REOPENING A DRAFT.** Three guards, each for a different way this goes
  // wrong: seeding a field a clerk has filled would overwrite them mid-type;
  // seeding on a draft would write today's default over the date the applicant
  // actually asked for; and seeding more than once would fight the clerk every
  // time the query refetched. `seededDefaultDate` is what makes it once —
  // `form.requested_start === ""` alone would re-fire the moment a clerk
  // deliberately CLEARED the box, which is a real thing to want to do.
  const seededDefaultDate = useRef(false);
  useEffect(() => {
    const suggested = captureDefaultsQuery.data?.requested_start;
    if (
      suggested === undefined ||
      suggested === null ||
      seededDefaultDate.current ||
      existingId !== null ||
      form.requested_start !== ""
    ) {
      return;
    }
    seededDefaultDate.current = true;
    update({ requested_start: suggested });
    // `update` is recreated per render; the ref above is what bounds this, not
    // the dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [captureDefaultsQuery.data?.requested_start, existingId]);

  // ══════════════════════════════════════════════════════════════════════════
  // THE SUB-CATEGORY TREE (BR-CUS-067) — THE SHARED READ, NOT A SECOND COPY
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **THIS WAS ITS OWN `useQuery` UNDER ITS OWN KEY `["account-subtypes"]`,
  // BESIDE THE KIT'S `["lookups","account_subtypes"]` — two cache entries for
  // one question, and only one of them knew about the PARENT** (PO 2026-09-22,
  // item 2: *"sub-category offers ALL sub-categories"*). Measured in a browser
  // on the demo tenant before the fix: **13 sub-types offered under every one
  // of the 7 categories**, so a clerk could file `Residential → Heavy
  // industrial` and nothing anywhere would call it wrong — `set_customer_
  // category` resolves the id against the tenant and never asks which category
  // it hangs off.
  //
  // ⚠ **THE FILTER AND THE CLEAR ARE NOT WRITTEN HERE. `DEF-CUS-5674` BUILT
  // BOTH, ONE SCREEN OVER**, for `NewAccountWizard` — *"a floating sub-type is
  // a sub-type of nothing"*. `accountSubtypesUnder` is the list, and the
  // clear-on-change below runs through that SAME function, so the product has
  // exactly one spelling of *which sub-types hang off this category*.
  //
  // ⚠ **IT ALSO BRINGS THE 403 THE OLD QUERY COULD NOT SEE (`DEF-CUS-5673`).**
  // `GET /lookups/{list}` is gated on the Settings role and a Billing Clerk —
  // the role that actually captures requests — is refused. The old query
  // reported that as an empty list, which is indistinguishable from *this
  // category has no children*. `failed` tells them apart.
  const subtypes = useAccountSubtypes(client);

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 3 · THE PREMISES REGISTER, SEARCHED — PO ruling 2026-09-15
  // ══════════════════════════════════════════════════════════════════════════
  // PO verbatim: *"if we have unit or street address then we should take it
  // from premises/Unit - it means its a search and if not foudn them alow user
  // to add them"*.
  //
  // ⚠ **`GET /premises/picker` IS THE REGISTER'S OWN SEARCH, PUBLISHED BY LANE
  // E FOR THIS SCREEN**, and it is not the S14 list wearing a query: it hands
  // the paginator an UNEVALUATED queryset, so the read costs the page rather
  // than the register (`NFR-3` — `_page`'s `list(rows)` is invisible at 79
  // properties and is the shape of the existing breaches at the top of T5).
  //
  // ⚠ **THE UNITS RIDE ON THE PREMISES ROW.** One round trip, and a unit list
  // that cannot disagree with the building it is drawn under. An earlier draft
  // of this screen called `/units?f.premises_id=…` separately; lane E's payload
  // made that second call redundant, and two ways to ask one question is the
  // thing this repo punishes hardest.
  //
  // ⚠ **`enabled` IS THE COST CONTROL.** Two characters minimum (the server
  // IGNORES a shorter `q` rather than refusing it, `BR-SHL-011`), never on
  // mount, and never once a premises is picked.
  const premisesSearch = useQuery({
    queryKey: ["capture-premises-picker", premisesQuery],
    queryFn: () => searchPremisesPicker(premisesQuery, client),
    enabled: premisesQuery.trim().length >= 2 && form.picked_premises_id === "",
  });

  /**
   * ⛔ **THE PICKED ROW IS HELD, NOT RE-DERIVED FROM THE SEARCH — AND UNTIL
   * 2026-09-19 IT WAS RE-DERIVED AND WAS THEREFORE ALWAYS `null`
   * (`DEF-CUS-5873`).**
   *
   * `pickPremises` ends with `setPremisesQuery("")`, which is right — the
   * results list should close the moment a row is chosen. But the query KEY is
   * `["capture-premises-picker", premisesQuery]`, so emptying the query moves
   * the key to one that has never been fetched, `premisesSearch.data` becomes
   * `undefined`, and a `pickedRow` looked up inside those results is `null` on
   * the very next render — **for ever, not briefly.**
   *
   * ⚠ **WHAT THAT COST WAS THE UNIT PICKER THE RULING ASKED FOR.** PO,
   * 2026-09-15: *"if we have unit or street address then we should take it from
   * premises/Unit - it means its a search"*, and the branch below reads
   * `(pickedRow?.units ?? []).length > 0` to decide whether to draw the
   * register's own unit list. With `pickedRow` permanently `null` that branch
   * could never be true, so **a clerk who picked `P-00045` — six units on
   * record — was still handed a free-text box**, on every premises, every
   * time. Measured in Chromium on `brazosbend`: `unit control tag: INPUT`.
   *
   * ⚠ **NOTHING COULD HAVE CAUGHT IT.** `tsc` is happy — the optional chain
   * is exactly what you write for a row that may be absent. The suite is happy:
   * the test that exercises the picker hands the component its own mocked
   * search results and never presses the button that empties the query. And the
   * screen does not look broken, because the fallback it silently takes is a
   * perfectly good box. It is hard-won law 2's shape — built, and not wired.
   *
   * **The fix is to keep what `pickPremises` already has in its hand.** The row
   * is the clerk's choice and outlives the search that found it; the lookup
   * below stays as the path for a row picked before this state existed.
   */
  const [heldPremises, setHeldPremises] = useState<PremisesPickerRow | null>(null);
  const pickedRow: PremisesPickerRow | null =
    form.picked_premises_id === ""
      ? null
      : (heldPremises?.id === form.picked_premises_id ? heldPremises : null) ??
        (premisesSearch.data?.results ?? []).find(
          (row) => row.id === form.picked_premises_id,
        ) ??
        null;

  /**
   * The unit as the mailing block should PRINT it — the register's own
   * `unit_no` where a unit was picked out of the register, and otherwise what
   * the clerk typed. Never the id (B14 rule 31), and never both.
   */
  const pickedUnitLabel: string =
    form.picked_unit_id === ""
      ? form.address_unit_as_given
      : ((pickedRow?.units ?? []).find((unit) => unit.id === form.picked_unit_id)?.unit_no ??
        form.address_unit_as_given);

  /**
   * ⊕ **THE DRAWN EVIDENCE TABLE, BUILT ONCE PER RENDER.**
   *
   * ⚠ **IT WAS CALLED TWICE — ONCE FOR `.length > 0` AND ONCE FOR `.map`.**
   * That was harmless while the function read only `form` and `draft`; it
   * stops being harmless the moment a row's contents depend on a third input,
   * because the guard and the body can then disagree about what is in the
   * table.
   *
   * The third input is the register's own unit count for the picked premises,
   * which exists only on the picker row the clerk chose — see `matchRows` for
   * why the read path cannot supply it yet.
   */
  const evidenceRows = matchRows(form, draft);

  /**
   * **PICKING IS THE ACT THE RULING NAMES**, and it writes two different kinds
   * of thing — which is why it is one function rather than six `update()`
   * calls scattered through the JSX.
   *
   *   · `picked_premises_id` — a real field on the capture payload (lane E),
   *     so the clerk's choice REACHES THE SERVER and the resolver stops
   *     guessing at prose. `address_as_given` takes the register's own line
   *     because that is what the clerk chose; `BR-CUS-070` forbids the
   *     RESOLVER overwriting it, and a clerk deliberately picking a row is not
   *     the resolver.
   *   · `picked_premises_city` and its two neighbours — **NOT fields.** Hard
   *     rule 8 puts an address on `premises` and nowhere else, so they are
   *     held here for DISPLAY and are re-read by walking. Nothing sends them,
   *     and `G85` refuses a fourth home.
   */
  function pickPremises(row: PremisesPickerRow): void {
    update({
      // ⚠ **NOT ON A SUBMITTED REQUEST — `DEF-CUS-9041`.** `BR-CUS-070` keeps
      // what the applicant typed word for word once the request has left
      // draft, and the server refuses `address_as_given` there by name; the
      // pick is a SEPARATE fact and is all that travels. On a draft the
      // clerk is the one typing, so the register's line takes the box.
      ...(amending ? {} : { address_as_given: row.address_line ?? "", address_unit_as_given: "" }),
      picked_premises_id: row.id,
      picked_premise_no: row.premise_no ?? "",
      picked_premises_city: row.city ?? "",
      picked_premises_state: row.state ?? "",
      picked_premises_postal: row.postal_code ?? "",
      picked_unit_id: "",
      picked_unit_no: "",
    });
    // ⊕ The chosen row is KEPT (see `pickedRow`): the line below moves the
    // search's query key, and anything read out of those results is gone on the
    // next render.
    setHeldPremises(row);
    setPremisesQuery("");
    if (amending) setAmendSearch(row.address_line ?? "");
  }

  /** Back to typing. The clerk keeps what they typed — the box is
   *  `address_as_given` and always was — and loses only the register row.
   *
   *  ⚠ **BOTH IDS GO TO `null` AND NOT TO ABSENT.** Lane E's contract makes
   *  those two different acts: *neither sent* leaves a pick alone, and *both
   *  null* undoes it. `capturePayload` reads the empty strings here and sends
   *  `null`, so clearing the box really does clear the match. */
  function clearPickedPremises(): void {
    setHeldPremises(null);
    update({
      picked_premises_id: "",
      picked_premise_no: "",
      picked_premises_city: "",
      picked_premises_state: "",
      picked_premises_postal: "",
      picked_unit_id: "",
      picked_unit_no: "",
    });
  }

  /** The unit, where the building has one. ⚠ **`unit_no` IS NOT A DATABASE ID
   *  (B14 rule 31)** — it is the tenant's own visible series, which is exactly
   *  the value `DEF-CUS-5386` says a screen must show where it shows a uuid.
   *  The uuid travels as `picked_unit_id` and never renders. */
  function pickUnit(unit: PremisesPickerUnit | null): void {
    update({
      picked_unit_id: unit?.id ?? "",
      picked_unit_no: unit?.unit_no ?? "",
      // DEF-CUS-9041 — the applicant's own unit words stay as they gave them
      // on a submitted request; the picked unit is the fact that travels.
      ...(amending ? {} : { address_unit_as_given: unit?.unit_no ?? "" }),
    });
  }

  const save = useMutation({
    mutationFn: async (next: CaptureForm) => {
      if (draft === null) {
        const created = await createServiceRequest(capturePayload(next), client);
        savedForm.current = next;
        setDraft(created);
        // Keep the number in the URL from the instant it exists, so a refresh
        // or a shared link lands on the same draft rather than opening a
        // second one and burning a second number (BR-CUS-093 consequence (a):
        // gaps are normal, but we do not create them for free).
        //
        // ⚠ **IT MERGES INTO THE QUERY STRING; IT DOES NOT REPLACE IT
        // (`DEF-CUS-5099`).** This read `setSearch({ request: … })`, which sets
        // the WHOLE query string to one key. That was harmless while the step
        // lived in component state, and the moment `DEF-CUS-5083` made the step
        // URL state it became a reset: the first save of a draft happens on a
        // forward move, so a clerk pressing Continue on step 3 was dropped back
        // to **step 1** with the draft loaded. **Found by walking all six steps
        // rather than by loading each one** — every per-step check still passed,
        // because each step was correct at its own address.
        //
        // `setSearch` here must therefore preserve whatever else is in the bar,
        // which today is `step` and tomorrow is anything the screen adds.
        setSearch(
          (previous) => {
            const merged = new URLSearchParams(previous);
            merged.set("request", created.header.id);
            return merged;
          },
          { replace: true },
        );
        return created;
      }
      // ✅ **ONLY WHAT CHANGED SINCE THE LAST SAVE (`DEF-CUS-6427`).** This sent
      // `capturePayload(next)` — the WHOLE form — on every step, which was
      // harmless while the form only ever held what was typed in this sitting
      // and became the data-loss path the moment a saved request could be
      // reopened. Nothing changed → no PATCH at all, and no empty audit row.
      const payload =
        savedForm.current === null
          ? capturePayload(next)
          : changedCapturePayload(savedForm.current, next);
      if (Object.keys(payload).length === 0) {
        return draft;
      }
      const updated = await patchServiceRequest(draft.header.id, payload, client);
      savedForm.current = next;
      setDraft(updated);
      return updated;
    },
    onError: (error) => {
      setSaveError(
        isApiError(error) ? t(error.messageKey, error.params) : t("api.error.unexpected"),
      );
      // ⊕ `CR-161-BRC10` W6 — a refused answer is marked on its own control.
      setCustomErrors(isApiError(error) ? customFieldErrors(error.fieldErrors, translate) : {});
    },
    onSuccess: () => {
      setSaveError(null);
      setCustomErrors({});
    },
  });

  /**
   * Persist whatever the server will take, then run the side calls that have
   * their own routes (category · services · address resolution · documents).
   *
   * ⚠ **THE SIDE CALLS ARE REPLAYED FROM THE WHOLE FORM, NOT FIRED PER STEP,
   * AND A BROWSER WALKTHROUGH IS WHAT FOUND THAT (hard-won law 6).** The first
   * version keyed each call to the step the clerk was leaving — `category` and
   * `services` on step 2, `resolve-address` on step 3. But the draft ROW does
   * not exist on step 2: `_clean_capture(partial=False)` needs the address,
   * which is step 3, so leaving step 2 posts nothing at all and the category
   * and the ten service cards were **silently discarded**. Measured in
   * Chromium: `POST /service-requests` and `POST .../resolve-address` fired,
   * `POST .../category` and `POST .../services` never did, and the request
   * reached step 6 with no category and no services while every unit test,
   * `tsc` and every gate stayed green.
   *
   * So the rule is: once a row exists, send everything the form currently
   * holds. `set_services` REPLACES the set and `set_customer_category` sets one
   * column, so both are idempotent and a replay costs a round trip, not a
   * duplicate.
   */
  async function persist(next: CaptureForm, step: CaptureStep): Promise<boolean> {
    if (!canCreateDraft(next)) {
      // Nothing to post yet, and that is not an error — the applicant has not
      // been named. ⚠ **THIS COMMENT READ *"the clerk is on step 1 and the
      // server needs an address"* UNTIL 2026-09-20**, describing the symptom of
      // `DEF-CUS-6006` as though it were the design: on step 1 the address
      // could not be typed at all, so what it actually documented was a control
      // nobody could ever use. The server no longer needs one to open a draft.
      // The header says so, in four words, beside the button.
      return true;
    }
    const firstSave = draft === null;
    // Measured BEFORE the save moves `savedForm` on. See `ADDRESS_PAYLOAD_KEYS`.
    const baseline = savedForm.current;
    const addressChanged =
      baseline === null ||
      ADDRESS_PAYLOAD_KEYS.some((key) => key in changedCapturePayload(baseline, next));
    try {
      const row = await save.mutateAsync(next);
      const id = row.header.id;
      // ⚠ **THE CATEGORY IS SENT ONLY WHEN IT CHANGES, AND A BROWSER
      // WALKTHROUGH IS WHY.** `POST .../category` answers **200 the first time
      // and 500 on every call after it**: `set_customer_category` builds its
      // audit `before` blob from `request.account_type_id` /
      // `.account_subtype_id`, which are `UUID` objects once set, and the audit
      // row JSON-serialises `details` — `TypeError: Object of type UUID is not
      // JSON serializable`. Measured directly against the running stack: call
      // one 200, call two 500, call three (a DIFFERENT code) 500. The same
      // function's `after` block already writes `str(subtype.id)`, so the fix
      // is `str(...)` on the two `before` values — in a backend file this lane
      // may not edit. **REPORTED; a clerk who changes their mind about the
      // category still meets it.**
      //
      // Sending only on change is the right shape anyway — the other three
      // side calls were each measured idempotent (services ×3, resolve ×2,
      // PATCH ×2, all 200) and are replayed freely.
      const categoryChanged =
        next.account_type_code !== "" &&
        (sentCategory.current.code !== next.account_type_code ||
          sentCategory.current.subtype !== next.account_subtype_id);
      if (categoryChanged) {
        await setServiceRequestCategory(
          id,
          {
            account_type_code: next.account_type_code,
            ...(next.account_subtype_id === ""
              ? {}
              : { account_subtype_id: next.account_subtype_id }),
          },
          client,
        );
        sentCategory.current = {
          code: next.account_type_code,
          subtype: next.account_subtype_id,
        };
      }
      // ⚠ **THE DATES RIDE THE ONE CALL, AND THERE IS NOT A SECOND ONE**
      // (`DEF-CUS-5416`, 2026-09-15). `POST .../services` REPLACES the set, so
      // a second call would replace what the first had just written. Lane F's
      // route takes a bare code OR `{code, requested_start}` in one mixed list
      // (`BR-CUS-1070`), which is exactly what `serviceStartsPayload` builds.
      //
      // ⚠ **AND ONLY WHEN THE SET OR A DATE CHANGED (`DEF-CUS-6427`).** It was
      // replayed on every save — idempotent, but a write and an audit row each
      // time, and on a request reopened for correction a clerk changing the
      // phone would have re-posted every service.
      const services = serviceStartsPayload(next);
      const servicesKey = JSON.stringify(services);
      if (savedServices.current !== servicesKey) {
        await setServiceRequestServices(id, services, client);
        savedServices.current = servicesKey;
      }
      if (firstSave || (step === "property" && addressChanged)) {
        // The resolver writes EVIDENCE, never a decision (BR-CUS-070). It is
        // what fills REQ-03.3's CHECK callout and step 6's *"What the lookup
        // found"*, which is STORED on the request. Re-run when the address
        // changes; not on every step, because it is a write.
        await resolveServiceRequestAddress(id, client);
      }
      // ⛔ **THE DOCUMENT REPLAY LOOP IS GONE FROM HERE, AND IT IS A RULING
      // BEING OBEYED RATHER THAN A STEP BEING DROPPED.** It read the ticked
      // types out of `form.documents` and POSTed the ones it had not sent yet,
      // guarded by an `attached` ref against `attach_document`'s append. Step 4
      // now writes each document to the server AT THE MOMENT IT IS ADDED —
      // `Attach a file` with the bytes, `Add another document` without — so
      // there is nothing left for a save to replay, and the ref that stopped
      // four copies of `proof_of_identity` has nothing to guard.
      //
      // ⚠ **IT IS ALSO WHY A DOCUMENT NOW SURVIVES A DRAFT.** The old shape
      // could only post what was in component state, and component state does
      // not survive the clerk leaving the wizard — so a document ticked and not
      // followed by a save was simply lost. Writing on the press removes the
      // window entirely.
      return true;
    } catch (error) {
      setSaveError(
        isApiError(error) ? t(error.messageKey, error.params) : t("api.error.unexpected"),
      );
      return false;
    }
  }

  function update(patch: Partial<CaptureForm>): void {
    setForm((previous) => ({ ...previous, ...patch }));
  }

  // ⊕ Lane CF-1 — the shared documents table's rows the clerk added in this
  // sitting (each file is ON THE REQUEST the moment it is uploaded; on a
  // reopened request the table reads them back from the server).
  const [docDrafts, setDocDrafts] = useState<MoveInDocDraft[]>([]);
  // Lane CF-1 — Continue was pressed on step 1, so the shared form shows its
  // refusals (format, the required phone and ID) where they are.
  const [applicantTried, setApplicantTried] = useState(false);

  /**
   * Lane CF-1 — **the shared table's upload, filed on the REQUEST.** A
   * document belongs to a request, so the draft is created first when it does
   * not exist yet (the same posture `addDocument` takes, and for its reason);
   * the reply is the whole documents tab, kept as the draft's, and the new
   * row's id is the card the table holds.
   */
  async function stageRequestDocument(args: {
    file: File;
    docType: string;
  }): Promise<{ card_id: string; name: string }> {
    let id = draft?.header.id ?? null;
    if (id === null) {
      if (!canCreateDraft(form)) {
        throw new Error(t("customers.serviceRequest.capture.cannotSaveDraftYet"));
      }
      const created = await save.mutateAsync(form);
      id = created.header.id;
    }
    const tab = await uploadServiceRequestDocument(
      id,
      { file: args.file, docType: args.docType },
      client,
    );
    setDraft((previous) => (previous === null ? previous : { ...previous, documents: tab }));
    const mine = tab.documents.filter(
      (doc) => doc.doc_type === args.docType && (doc.name ?? "") === args.file.name,
    );
    const row = mine[mine.length - 1] ?? tab.documents[tab.documents.length - 1];
    return { card_id: row.id, name: row.name ?? args.file.name };
  }

  // `DEF-CUS-10041` — the fee still owed on the draft, `""` when none is.
  const owingNow = owingAmount(draft);

  // `DEF-CUS-10040` — Add a premise's *Check address*, on the typed address.
  const cityCheck = useCityAddressCheck(client, todayIso);

  async function runCityCheck(): Promise<void> {
    if (form.address_as_given.trim() === "") return;
    await cityCheck.run({
      address_line: form.address_as_given.trim(),
      city: form.address_city_as_given.trim(),
      state: form.address_state_as_given.trim(),
      postal_code: form.address_postal_code_as_given.trim(),
    });
  }

  /** *Use these details* — the City's answer replaces what was typed, parcel too. */
  function useCityDetails(): void {
    const check = cityCheck.check;
    if (check.kind !== "match") return;
    const match = check.match;
    update({
      address_as_given: match.address_line || form.address_as_given,
      address_city_as_given: match.city ?? "",
      address_state_as_given: match.state ?? "",
      address_postal_code_as_given: match.postal_code ?? "",
      plot_or_parcel: match.parcel || form.plot_or_parcel,
    });
    cityCheck.setCheck({ ...check, used: true });
  }

  /** `CR-161-BRC10` W6 — one record type's answers changed; its marked
   *  refusals clear as the clerk types. */
  function updateCustom(entity: RequestCustomEntity, values: CustomFieldValues): void {
    setForm((previous) => ({ ...previous, custom: { ...previous.custom, [entity]: values } }));
    setCustomErrors({});
  }

  const requestNo = draft?.header.request_no ?? null;
  // ⛔ **`driversLicenceReason` IS GONE WITH THE ABSENCE IT EXPLAINED — PO
  // ruling 2026-09-15.** It read the SERVER's own `unavailable` sentence for
  // the licence and printed it as a `StatedFact`, which was the honest shape
  // while no column existed. The licence is an INPUT now, so a sentence saying
  // we do not hold one would be printed over the box a clerk is typing it
  // into — which is hard-won law 2's MIRROR, a live capability behind a dead
  // refusal, and the shape that cost the customer portal six working doors.
  //
  // ✅ **AND THE SERVER HAS STOPPED SAYING IT TOO.** This note used to add
  // that `service_request_reads` still rode `UNAVAILABLE.driversLicence` and
  // that it was another lane's file. Lane G retired that entry in the same
  // commit as the column, so the fallback has nothing left to fall back to.
  // The three symbols it left standing — `UNAVAILABLE.driversLicence`, this
  // constant and the catalogue key `applicant.driversLicenceAbsent` — are
  // retired here, which is where lane G's own record says they belong.

  // ══════════════════════════════════════════════════════════════════════════
  // **WHAT THE CUSTOMER IS TOLD — the Review's card (REQ-03 task 10).**
  //
  // ⚠ **NO SECOND READ.** The server puts this card on the DETAIL payload the
  // review already holds, and says why in its own docstring: a call of its own
  // would make the card's rows and the fee figures they quote two reads that
  // can disagree. This lane's first draft added a `GET .../applicant-messages`
  // query and it is gone.
  //
  // ⚠ **EVERY WORD IS RESOLVED HERE AND NONE TRAVELS** (`BR-SHL-020` r2). The
  // server sends `message_key` + `params`, a channel CODE and a reason KEY;
  // the address is data and is printed as it is.
  //
  // ⚠ **A WITHHELD ROW SAYS WHY, IN ITS `WHEN` CELL** — the drawing's own
  // *"Not sent — none outstanding"*. An absent row and a withheld one look
  // identical, and telling them apart is what this card is for.
  // ══════════════════════════════════════════════════════════════════════════
  const told = draft?.told_on_submit;
  const messageRows: CustomerMessageRow[] = useMemo(
    () =>
      (told?.rows ?? []).map((row) => ({
        key: row.occasion,
        message: t(row.message_key, row.params),
        channel: t(`customers.serviceRequest.messages.channel.${row.channel}`, {
          defaultValue: "",
        }),
        to: row.to ?? "",
        when: row.will_send
          ? t(`customers.serviceRequest.messages.when.${row.when ?? ""}`, { defaultValue: "" })
          : t(row.not_sent_reason_key ?? "", { defaultValue: "" }),
        withheld: !row.will_send,
      })),
    [told, t],
  );
  /**
   * The card's STATED absence, or `null` where the server answered.
   *
   * ⚠ **TWO DIFFERENT ABSENCES AND NEITHER IS *nothing to say*.** No draft
   * saved yet, and a detail that carries no card at all. An empty table would
   * spell both the same way and neither honestly.
   */
  const messageAbsence: string | null =
    draft === null
      ? t("customers.serviceRequest.messages.needADraft")
      : told === undefined
        ? t("customers.serviceRequest.messages.serverCannotAnswer")
        : null;

  // ══════════════════════════════════════════════════════════════════════
  // `DEF-CUS-10042` — the messages a CLERK adds on step 4. Read once a draft
  // exists; held here while the clerk edits (`null` = untouched, so the
  // server's rows show); written at Submit or Save, never per keystroke,
  // because a half-typed row is refused by name and would read as an error.
  // ══════════════════════════════════════════════════════════════════════
  const extraQuery = useQuery({
    queryKey: ["customers", "service-request", "extra-messages", draft?.header.id ?? ""],
    queryFn: () => getRequestExtraMessages(draft?.header.id ?? "", client),
    enabled: draft !== null,
    retry: false,
  });
  const [extraRows, setExtraRows] = useState<RequestExtraMessage[] | null>(null);
  // A server that answers in another shape is read as "no rows, no templates",
  // never as a crash of the whole wizard.
  const extraServed = extraQuery.data;
  const extraShown: RequestExtraMessage[] =
    extraRows ?? (Array.isArray(extraServed?.rows) ? extraServed.rows : []);
  const extraTemplates = Array.isArray(extraServed?.templates?.results)
    ? extraServed.templates.results
    : [];

  /** Writes the added rows if the clerk changed them; the refusal as a sentence, or `null`. */
  async function saveExtras(): Promise<string | null> {
    if (extraRows === null || draft === null) return null;
    try {
      const saved = await saveRequestExtraMessages(draft.header.id, extraRows, client);
      setExtraRows(saved.rows);
      return null;
    } catch (error) {
      return isApiError(error) ? t(error.messageKey, error.params) : t("api.error.unexpected");
    }
  }

  const steps: WizardStep[] = useMemo(() => {
    const enabledServices = (servicesQuery.data ?? []).filter((row) => row.enabled);
    // The drawn rows: one per picked service, plus at most one unanswered row
    // a clerk has just made with `+ Service`.
    const serviceTableRows: ServiceTableRow[] = [
      ...form.services.map((code) => ({
        code,
        requested_start: serviceStart(form, code) ?? "",
        status: serviceOnSite(form),
      })),
      ...(pendingServiceRow
        ? [{ code: "", requested_start: "", status: null } as ServiceTableRow]
        : []),
    ];
    return [
      // ── 1 · APPLICANT · REQ-03.1 ────────────────────────────────────────
      // ══════════════════════════════════════════════════════════════════════
      // **SIX STEPS INTO FOUR — PO APPROVAL 2026-09-29.** Built from
      // `05-prototype/new-request-four-steps-2026-09-29/01-applicant-1440.png`
      // and `01b-applicant-coapplicant-open-1440.png`, read as IMAGES rather
      // than as text — B14 rule 42, PO: *"build all screens using images and
      // not text/content"*.
      //
      // **NOTHING IS LOST IN THE MERGE, WHICH IS THE WHOLE CLAIM OF THE
      // REDESIGN.** All 42 inputs keep a place: Applicant (13 + 5 documents) ·
      // Property (12) · Service (5 + 7) · Review (read-only).
      //
      // TWO PANELS AND NOTHING ELSE:
      //   * **The applicant** — the eleven controls and the co-applicant, in
      //     `CaptureApplicantPanel` (B14 rule 43: a piece of UI is a COMPONENT,
      //     and this was ~300 lines written into a 5,282-line page);
      //   * **Documents** — the whole of the old step 4, moved here.
      // ══════════════════════════════════════════════════════════════════════
      {
        id: "applicant",
        label: t("customers.serviceRequest.step.applicant"),
        // ✅ **THE CATEGORY GATE TRAVELS WITH THE CONTROL, FOR THE THIRD
        // TIME.** PO 2026-09-29, verbatim: *"move this to appliant sicne it is
        // applicant - arrtributes"*. `CR-033` put it on step 1, the ruling of
        // 2026-09-15 moved it to step 2, and this one moves it back — and the
        // `validate` went with it each time, because a step that refuses to
        // advance over a field nobody can see is `DEF-CUS-5082` exactly.
        validate: () => {
          // ⊕ Lane CF-1 — Move-in's required-field rules, everywhere (decision
          // log 2026-10-18: *"phone required for a person, email optional, at
          // least one ID unless an existing customer is linked"*). A request
          // links no customer (that happens on the move-in or new connect), so
          // a PERSON owes a phone and one ID, a BUSINESS its Tax ID. A
          // staff-raised request (BR-CUS-091) owes none of it.
          setApplicantTried(true);
          return applicantStepProblem(form) === null &&
            form.account_type_code !== "" &&
            // ⊕ `CR-161-BRC10` W6 — a customer or account field required on
            // Staff New Request holds the step it is typed on.
            missingOnStep(customRegistries, form.custom, ["customers", "accounts"]).length === 0;
        },
        content: (
          <div className="flex flex-col gap-6">
            {/* ⊕ **LANE CF-1 — THE SHARED CUSTOMER FORM (drawing set
                `customer-forms-2026-10-18`, image 03).** Who is applying ·
                Identity (no *Search customer ID* — PO: *"in new request we
                dont need Search customer ID"*) · About the customer · Co-
                applicants · Documents · Mailing address · Preferences (no
                Autopay). `CaptureCustomerForm` maps this page's form onto the
                shared pieces; nothing here re-implements one. */}
            <CaptureCustomerForm
              form={form}
              update={update}
              onApplicantKindChange={(kind) => update(clearOtherKind(form, kind))}
              subtypeRows={subtypes.rows}
              customCustomers={form.custom.customers}
              onCustomCustomers={(values) => updateCustom("customers", values)}
              documents={docDrafts}
              onDocuments={setDocDrafts}
              requestId={draft?.header.id ?? ""}
              requiredDocTypes={draft?.documents.checklist_required ?? []}
              stageDocument={stageRequestDocument}
              serviceAddress={serviceAddressLines({
                street: form.address_as_given,
                unit: pickedUnitLabel,
                city:
                  form.picked_premises_id === "" ? form.address_city_as_given : form.picked_premises_city,
                state:
                  form.picked_premises_id === "" ? form.address_state_as_given : form.picked_premises_state,
                postalCode:
                  form.picked_premises_id === ""
                    ? form.address_postal_code_as_given
                    : form.picked_premises_postal,
                unitWord: t("customers.serviceRequest.capture.unitWord"),
              }).join(", ")}
              ssnPlaceholder={ssnOnFileMask(form.ssn_on_file)}
              licencePlaceholder={licenceOnFileMask(form.drivers_licence_on_file)}
              showErrors={applicantTried}
              t={translate}
              dateFormat={dateFormat}
              timeZone={timeZone}
              client={client}
            />
            {applicantTried && applicantStepProblem(form) !== null ? (
              <RefusalStrip role="alert" data-applicant-problem="">
                {t(applicantStepProblem(form) ?? "")}
              </RefusalStrip>
            ) : null}
            {/* ⊕ `CR-161-BRC10` W6 — the ACCOUNT's own fields placed Input on
                Staff New Request (the customer's moved into *About the
                customer* above). Nothing without them. */}
            <RequestApplicantCustomFields
              form={form.custom}
              onChange={(entity, values) => updateCustom(entity, values)}
              errors={customErrors}
              client={client}
            />
          </div>
        ),
      },

      // ── 2 · PROPERTY · REQ-03.2 ─────────────────────────────────────────
      {
        id: "property",
        label: t("customers.serviceRequest.step.property"),
        // The street line is still the one thing `Continue` asks for. (The
        // mailing ZIP's shape moved to step 1 with the mailing block — lane
        // CF-1, `applicantStepProblem`.)
        validate: () =>
          form.address_as_given.trim() !== "" &&
          // ⊕ `CR-161-BRC10` W6 — a property field required on Staff New
          // Request holds the step it is typed on.
          missingOnStep(customRegistries, form.custom, ["premises"]).length === 0,
        content: (
          <div>
            <Panel as="section">
              {/* ══════════════════════════════════════════════════════════
                  **THE ADDRESS IS PICKED OUT OF THE PREMISES REGISTER, NOT
                  TYPED INTO FIVE BOXES — PO ruling 2026-09-15**, verbatim:
                  *"if we have unit or street address then we should take it
                  from premises/Unit - it means its a search and if not foudn
                  them alow user to add them"*.

                  ⚠ **AND THAT IS HARD RULE 8 APPLIED TO A SCREEN RATHER THAN
                  A NEW RULE.** An address lives on `premises` and NOWHERE
                  else, so `City`, `State` and `ZIP code` are read by WALKING
                  to the picked premises and are shown read-only. The ruling
                  says so in as many words, and it names what it stopped: a
                  lane dispatched the same hour *"was adding `city`, `state`
                  and `postal_code` COLUMNS TO `service_requests`"* — three
                  columns `G85` refuses as a fourth home for an address.

                  ⚠ **WHAT THE APPLICANT SAID IS STILL WHAT IS STORED.** The
                  box below IS `address_as_given` and `BR-CUS-070` keeps it
                  word for word; the register's own line only ever gets there
                  because a clerk CHOSE it. The resolver still never overwrites
                  it, and the match sits beside it in the table at the foot of
                  this step.

                  ⚠ **AND THE UNMATCHED CASE STAYS TYPED, DELIBERATELY.** The
                  drawing says so in red on p077: *"a new connection at a field
                  with no address yet is exactly the job this wizard exists
                  for."* So nothing here refuses an address the register does
                  not hold — `+ Premises` opens the register's own creator, and
                  a clerk who does not need it simply types.
                  ══════════════════════════════════════════════════════════ */}
              <h3>{t("customers.serviceRequest.capture.serviceAddress")}</h3>
              <FieldGrid columns={2}>
                {/* ⚠ **ON A SUBMITTED REQUEST THIS BOX IS A SEARCH, NOT A FIELD
                    — `DEF-CUS-9041`, which superseded *"READ-ONLY ONCE THE
                    REQUEST HAS LEFT DRAFT"*.** The server refuses
                    `address_as_given` after submission (`BR-CUS-070`,
                    `addressAsGivenImmutable`), and that half stands: nothing
                    typed here is SAVED on an amend. But this box is also the
                    ONLY thing that starts the register search, so read-only
                    meant no portal request — every one arrives submitted —
                    could ever have its property picked, and the Approve dialog
                    read *Property — Not in Premises* over a building on file.
                    So on an amend the typing drives the search alone
                    (`amendSearch`) and the pick is what travels. */}
                <TextField
                  id="address_as_given"
                  label={t("customers.serviceRequest.capture.streetOrPremise")}
                  required
                  value={amending ? (amendSearch ?? form.address_as_given) : form.address_as_given}
                  onChange={(value) => {
                    if (amending) {
                      setAmendSearch(value);
                      if (form.picked_premises_id !== "") {
                        clearPickedPremises();
                      }
                      setPremisesQuery(value);
                      return;
                    }
                    update({ address_as_given: value });
                    // Typing after a pick means the clerk is looking again, so
                    // the register row comes off rather than sitting stale
                    // beside a line it no longer describes.
                    if (form.picked_premises_id !== "") {
                      clearPickedPremises();
                    }
                    setPremisesQuery(value);
                  }}
                  help={t("customers.serviceRequest.capture.searchTheRegister")}
                />
                {/* ⚠ **THE UNIT IS A PICKER ONLY WHERE THERE IS SOMETHING TO
                    PICK.** The ruling says *"where there is one picks a
                    unit"*; a premises with no units, or none picked yet,
                    leaves the clerk the box the drawing draws. */}
                {form.picked_premises_id !== "" && (pickedRow?.units ?? []).length > 0 ? (
                  <SelectField
                    id="address_unit_as_given"
                    label={t("customers.serviceRequest.capture.unit")}
                    value={form.picked_unit_id}
                    placeholder={t("customers.serviceRequest.capture.chooseAUnit")}
                    onChange={(value) =>
                      pickUnit((pickedRow?.units ?? []).find((unit) => unit.id === value) ?? null)
                    }
                    options={(pickedRow?.units ?? []).map((unit) => ({
                      value: unit.id,
                      // B14 rule 31 — `unit_no` is the tenant's own series and
                      // the uuid is the VALUE, which is never rendered.
                      label:
                        unit.label === null || unit.label === ""
                          ? (unit.unit_no ?? "")
                          : `${unit.unit_no ?? ""} · ${unit.label}`,
                    }))}
                  />
                ) : (
                  <TextField
                    id="address_unit_as_given"
                    label={t("customers.serviceRequest.capture.unit")}
                    value={form.address_unit_as_given}
                    onChange={(value) => update({ address_unit_as_given: value })}
                    help={t("customers.serviceRequest.capture.unitHelp")}
                  />
                )}
              </FieldGrid>

              {/* THE REGISTER'S ANSWER. Twenty rows of a paginated list
                  (`NFR-3`), asked for only once two characters are typed and
                  never once a row is picked. */}
              {premisesSearch.isFetching && (
                <p className="text-sm text-neutral-700">{t("states.loading")}</p>
              )}
              {form.picked_premises_id === "" &&
                premisesQuery.trim().length >= 2 &&
                !premisesSearch.isFetching && (
                  <div className="flex flex-col items-start gap-1" data-premises-results="">
                    {(premisesSearch.data?.results ?? []).length === 0 ? (
                      <p className="text-sm text-neutral-700">
                        {/* ⚠ **TWO SENTENCES, WHICH IS WHAT THE DRAWING DRAWS
                            AND WHAT `BR-CUS-070` IS ABOUT.** Only the first
                            was built, so the screen said an address was not
                            found and never said it was KEPT — which is the one
                            thing a clerk taking a new connection at a
                            greenfield site needs to know. Three words and six,
                            inside rule 33's cap for a FACT. */}
                        <strong>{t("customers.serviceRequest.capture.noPremisesMatch")}</strong>{" "}
                        {t("customers.serviceRequest.capture.typedAddressIsKept")}
                      </p>
                    ) : (
                      (premisesSearch.data?.results ?? []).map((row) => (
                        <Button
                          key={row.id}
                          variant="ghost"
                          data-premises-option={row.premise_no ?? ""}
                          onClick={() => pickPremises(row)}
                        >
                          {`${row.premise_no ?? ""} · ${row.address_line ?? ""}`}
                        </Button>
                      ))
                    )}
                    {/* ⛔ **`+ Premises` IS REMOVED — `DEF-CUS-7850`, PO
                        2026-09-29: *"if not found not add premise button
                        should not show"*, then *"this si correct"*.

                        ⚠ **IT DREW IN BOTH STATES AND IT WAS A DOOR OUT OF A
                        WIZARD.** Pressing it navigated the clerk into the
                        premises register and lost the request they were
                        halfway through capturing. **A request records what the
                        applicant SAID** — `BR-CUS-070` keeps the typed address
                        word for word — and the register is matched separately,
                        which the *Found in Premises* panel below already does.
                        So there was never an act to offer here.

                        **REMOVING A CONTROL IS NOT DROPPING A CAPABILITY.** The
                        premises register still has its own creator at
                        `/premises/new`, reached from the register, where
                        creating a premises belongs (B2 §2 — this module may
                        not write one). */}
                  </div>
                )}

              {/* ════════════════════════════════════════════════════════
                  **CITY, STATE AND ZIP: THE PREMISES' OWN FACTS, WALKED AND
                  READ-ONLY — AND THIS IS THE ONE PLACE ON THIS STEP WHERE THE
                  DRAWING IS NOT BUILT.**

                  p077 draws all three as boxes a clerk types into, `State` as
                  a dropdown, each with an asterisk. **They are not built that
                  way and they may not be**, and the reason is signed twice
                  over:

                    * `CLAUDE.md` hard rule 8 / `BR-MET-1161` — *an address is
                      stored on `premises` and NOWHERE else*, and everything
                      else derives it by walking;
                    * **PO ruling 2026-09-15**, verbatim: *"if we have unit or
                      street address then we should take it from premises/Unit
                      - it means its a search and if not foudn them alow user
                      to add them"*.

                  ⚠ **THE DRAWING ITSELF STATES THIS ABSENCE, IN AMBER, BESIDE
                  THESE VERY BOXES**, and it argues the product's side rather
                  than the wireframe's: *"THE ADDRESS IS ONE FIELD TODAY, NOT
                  FIVE — … Five boxes are five columns, and the reason there
                  is one is that an applicant's address is not a premises
                  yet."* p075 says a dashed block IS a stated absence, and this
                  is one of the three p077's own caption counts.

                  ⚠ **THE THREE COLUMNS WERE WRITTEN ONCE AND TAKEN OUT AN HOUR
                  LATER, AND `service_request_service.CAPTURE_FIELDS` CARRIES
                  THE WARNING IN CAPITALS: *"Do not re-add them"*.**
                  `address_city_as_given`, `address_state_as_given` and
                  `address_postal_code_as_given` had a model field, a
                  migration, a widened allow list and a fifth `G85` home entry
                  on 2026-09-15 before the ruling landed. `BR-CUS-1055` records
                  the near-miss precisely so the next lane reading five drawn
                  boxes does not build them again, and **this lane was that
                  lane**: its brief asked for three editable fields and new
                  payload keys. Held, not built, and reported — which is B14
                  rule 41's own carve-out (*the only thing that reaches the PO
                  is a drawing that contradicts a signed rule*) and hard-won
                  law 13's short list.

                  What IS built is the drawn LAYOUT: two across, `City` beside
                  `State`, `ZIP code` on the row below, directly under the
                  street and unit boxes where p077 puts them.
                  ════════════════════════════════════════════════════════ */}
              {/* ══════════════════════════════════════════════════════════
                  **`City`, `State` and `ZIP code`: TYPED WHILE NO PREMISE IS
                  PICKED, THE PREMISE'S OWN AND READ-ONLY ONCE ONE IS
                  (`DEF-CUS-10039`, PO 2026-10-11).**

                  PO, on a screenshot of three locked empty boxes under *No
                  premises match*: *"City , state, zipcode user unable any
                  values - why?"*. That restores the PO ruling of 2026-09-22 —
                  *"correct address will be on presmies but first time you will
                  ahve to take the details to match it"* — which a later rebuild
                  to drawing `02-property-1440.png` had reversed on the
                  drawing's authority alone, without putting it back to the PO.
                  The drawing never outranked a ruling (B14 rule 41's own
                  carve-out). Hard rule 8 is untouched: these are the request's
                  record of what the applicant SAID (`BR-CUS-070`), never an
                  address home, and once a premise is picked the premise is
                  what every screen shows.

                  *Check address* (`DEF-CUS-10040`) is the same piece Add a
                  premise draws, offered only while nothing is picked; *Use
                  these details* writes the City's street, city, state, ZIP and
                  parcel into the typed fields.
                  ══════════════════════════════════════════════════════════ */}
              <div
                data-address-parts=""
                data-premises-picked={
                  form.picked_premises_id === "" ? undefined : form.picked_premise_no
                }
              >
                {form.picked_premises_id === "" ? (
                  <FieldGrid columns={3}>
                    <TextField
                      id="address_city_as_given"
                      label={t("customers.serviceRequest.capture.city")}
                      value={form.address_city_as_given}
                      onChange={(value) => {
                        update({ address_city_as_given: value });
                        cityCheck.setCheck({ kind: "none" });
                      }}
                    />
                    <TextField
                      id="address_state_as_given"
                      label={t("customers.serviceRequest.capture.addressState")}
                      value={form.address_state_as_given}
                      onChange={(value) => {
                        update({ address_state_as_given: value });
                        cityCheck.setCheck({ kind: "none" });
                      }}
                    />
                    <TextField
                      id="address_postal_code_as_given"
                      label={t("customers.serviceRequest.capture.postalCode")}
                      value={form.address_postal_code_as_given}
                      onChange={(value) => {
                        update({ address_postal_code_as_given: value });
                        cityCheck.setCheck({ kind: "none" });
                      }}
                    />
                  </FieldGrid>
                ) : (
                  <>
                    <FieldGrid columns={3}>
                      <TextField
                        id="address_city_as_given"
                        label={t("customers.serviceRequest.capture.city")}
                        value={form.picked_premises_city}
                        onChange={() => undefined}
                        readOnly
                      />
                      <TextField
                        id="address_state_as_given"
                        label={t("customers.serviceRequest.capture.addressState")}
                        value={form.picked_premises_state}
                        onChange={() => undefined}
                        readOnly
                      />
                      <TextField
                        id="address_postal_code_as_given"
                        label={t("customers.serviceRequest.capture.postalCode")}
                        value={form.picked_premises_postal}
                        onChange={() => undefined}
                        readOnly
                      />
                    </FieldGrid>
                    <p className="text-sm text-neutral-700" data-address-parts-note="">
                      {t("customers.serviceRequest.capture.fromTheMatchedPremise")}
                    </p>
                  </>
                )}
                {form.picked_premises_id === "" && (
                  <div className="mb-5" data-request-city-check="">
                    <CityAddressCheck
                      check={cityCheck.check}
                      onCheck={() => void runCityCheck()}
                      onUseDetails={useCityDetails}
                      onKeepMine={() => cityCheck.setCheck({ kind: "none" })}
                      t={t}
                    />
                  </div>
                )}
              </div>

              {/* ⚠ **`What is being built` MOVES INTO THIS PANEL AND STOPS
                  BEING CONDITIONAL.** It lived in an accent panel that drew
                  only once the SERVER had said it holds no such premises, so
                  on an unsaved request — which is every request at the moment a
                  clerk is typing — the one question about a greenfield site
                  was not on screen at all. `02-property-1440.png` draws it
                  directly under the three read-only boxes, unconditionally.

                  ⛔ **THE TWO SENTENCES THAT PANEL CARRIED ARE NOT REBUILT.**
                  *"We do not have this address on record yet. Tell us a bit
                  more:"* and the 24-word *"…so we cannot confirm which of the
                  requested services are available"* are both RATIONALE, which
                  B14 rule 33 puts at **zero words on screen**, and the
                  approved drawing draws neither. */}
              <FieldGrid columns={2}>
                <TextField
                  id="what_is_being_built"
                  label={t("customers.serviceRequest.capture.whatIsBeingBuilt")}
                  value={form.what_is_being_built}
                  onChange={(value) => update({ what_is_being_built: value })}
                  placeholder={t("customers.serviceRequest.capture.whatIsBeingBuiltHelp")}
                />
              </FieldGrid>
            </Panel>


            {/* ══════════════════════════════════════════════════════════════
                **`How many units are on this property?` IS REMOVED — PO report
                2026-09-22, row 12.**

                It was built on the PO's own instruction of 2026-09-15 and taken
                off a week later, from BOTH screens: this question and the
                `Units on site` row that displayed it on the request detail.

                ⚠ **THE COLUMN AND EVERY ROW THAT HOLDS ONE ARE UNTOUCHED.**
                `service_requests.units_on_property` still exists, is still
                served, and every request already carrying a number still
                carries it — `CAPTURE_FIELDS` still accepts it, so a caller
                that knows the fact can still send it. What the PO removed is
                the QUESTION and the row that showed the answer.

                ⚠ **AND THE WHOLE PANEL GOES WITH IT**, because this question
                was the only thing in it. A `The property` heading over nothing
                is the empty section B14 rule 32 is about.
                ══════════════════════════════════════════════════════════════ */}
            {/* ══════════════════════════════════════════════════════════════
                **THE BILLING BOX IS DRAWN AND DISABLED, NOT HIDDEN** (p077).

                It used to appear only once the tick came off, so a clerk read
                a lone checkbox and had to clear it to find out what clearing
                it did. The drawing keeps the box on screen the whole time,
                greyed, with the tick above it — so the shape of the answer is
                visible before the question is answered.

                ⚠ **`disabled`, NOT `readOnly`, AND THE KIT DRAWS THE
                DIFFERENCE** (`DEF-MET-4984`): `readOnly` is a value worth
                reading and copying, `disabled` is a box with nothing in it
                that will not take what you type. This is the second.

                ⚠ **BR-SHL-025 — A DISABLED CONTROL OWES THE READER ITS
                REASON**, and the help line is it. The drawing's sentence is
                *"Filled in only when the box above is cleared."* — nine words,
                where **B14 rule 33** caps a fact at six. Shortened to six with
                the same meaning, which is **rule 38**: how a form is built is
                the UI rules', what it says is the drawing's.

                ⚠ **AND THE DRAWN `—` INSIDE THE BOX IS NOT BUILT.** An em dash
                sitting in a disabled input is the wireframe's way of drawing
                *empty*; putting one in `value` would make the screen hold a
                character no clerk typed and the payload would have to strip it
                again. An empty disabled box says the same thing and cannot
                leak.
                ══════════════════════════════════════════════════════════════ */}
            {/* ⊕ **LANE CF-1 (2026-10-18) — THE MAILING ADDRESS MOVED TO STEP 1**
                with the rest of the shared customer form (drawing set
                `customer-forms-2026-10-18`, image 03 draws it under the
                documents). It is the shared `MailingAddressBlock` there, sent
                as `mailing_*`; ticked, it still prints this step's address. */}
            {/* ⛔ **`Property details` IS OFF THIS STEP, AND THE COLUMN STAYS.**

                The drawing draws neither the heading nor the six radios, and
                the PO said why: *"if premises is found then we already have
                all details related with property"*. A clerk who has just
                picked a building out of the premises register has already told
                us what sort of property it is; asking again, in six radios
                each carrying its own explanation, was 84 words of form over a
                fact the register holds.

                ⚠ **REMOVING A CONTROL IS NOT DROPPING A COLUMN**, and the
                drawing says exactly that one panel over, about the plot field:
                *"Removing a control is not dropping a column. The request
                still has somewhere to keep a plot or parcel reference, and
                nothing on this wizard writes it any more."* So `property_type`
                stays on `CaptureForm`, stays in `capturePayload` — where `""`
                already sends `undefined`, so a request captured here now
                carries none — stays in `CAPTURE_FIELDS`, stays on the model
                and stays on the step 6 review, where it reads as the absence
                it has become. **No migration. A caller that knows the type can
                still send it.** */}


            {/* ══════════════════════════════════════════════════════════════
                **`What the register matched` — the drawn `LOOKED FOR` /
                `MATCHED` / `CONFIDENCE` table** (p077, lower left).

                The drawing's own caption is the rule: *"The match is evidence,
                never a decision. What the resolver found sits beside what the
                applicant said."* `BR-CUS-070` is the signed half of it.

                ⚠ **THE `MATCHED` COLUMN CAN ONLY SHOW WHAT THE CLERK PICKED,
                AND THAT IS A GAP IN THE READ PATH RATHER THAN A CHOICE.** The
                request stores `resolved_premises_id` and `resolved_unit_id`
                and `service_request_reads` serves **no number beside either**
                — so where the SERVER resolved the address on its own, the only
                honest cell is *On record*, because B14 rule 31 forbids
                printing the uuid and `DEF-CUS-5386` is that exact live defect
                one screen over. The contract wanted is
                `location_and_services.resolved_premise_no` and
                `.resolved_unit_no`; it is stated in the lane report rather
                than faked here.
                ══════════════════════════════════════════════════════════════ */}
            {/* ⚠ **THE PANEL IS DRAWN WHETHER OR NOT ANYTHING MATCHED.** It
                appeared only once the resolver had something to show, so a
                clerk had no way of telling *nothing matched* from *we never
                looked*. The approved drawing puts it on screen in the
                not-found state with its own sentence, which is what an
                empty state is for. */}
            <Panel as="section">
              <h3>{t("customers.serviceRequest.capture.whatTheRegisterMatched")}</h3>
              {evidenceRows.length === 0 ? (
                <p className="text-sm text-neutral-700" data-match-empty="">
                  {t("customers.serviceRequest.capture.nothingMatchedYet")}
                </p>
              ) : (
                <table className="data-table" data-table="match-evidence">
                  <thead>
                    <tr>
                      <th>{t("customers.serviceRequest.capture.col.lookedFor")}</th>
                      <th>{t("customers.serviceRequest.capture.col.matched")}</th>
                      <th>{t("customers.serviceRequest.capture.col.confidence")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evidenceRows.map((row) => (
                      <tr key={row.key} data-match-row={row.key}>
                        <td>
                          {typeof row.lookedFor === "string"
                            ? row.lookedFor
                            : t(row.lookedFor.key, row.lookedFor.params)}
                        </td>
                        <td>
                          <TextOrNotSupplied
                            value={
                              row.matched === null || typeof row.matched === "string"
                                ? row.matched
                                : t(row.matched.key, row.matched.params)
                            }
                            t={translate}
                          />
                        </td>
                        <td data-confidence={row.confidence}>
                          {t(`customers.serviceRequest.capture.confidence.${row.confidence}`)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>
            {/* ⊕ `CR-161-BRC10` W6 — the property's own fields, placed Input
                on Staff New Request in Settings. Nothing without them. */}
            <RequestPropertyCustomFields
              form={form.custom}
              onChange={(entity, values) => updateCustom(entity, values)}
              errors={customErrors}
              client={client}
            />
          </div>
        ),
      },

      // ── 3 · SERVICE · REQ-03.3 ──────────────────────────────────────────
      // **The old `Connection` and `Fees` steps are ONE step now** — the
      // four-step redesign approved 2026-09-29. The panels below are
      // unchanged apart from the category pair, which moved to step 1.
      // Rebuilding them as the drawn table arrays is lane SCREEN-B's.
      {
        id: "service",
        label: t("customers.serviceRequest.step.service"),
        // ✅ **THE CATEGORY GATE ARRIVES WITH THE CONTROL — PO ruling
        // 2026-09-15, verbatim: *"this should be on step 2 as per image"*.**
        // The blueprint draws `Category *` at the top of this step (p076) and
        // argues the order in its own words: *"what they want comes first,
        // because it is what decides which questions the rest of the wizard
        // has to ask."* A request may not leave step 2 uncategorised, which is
        // the gate `CR-033` put on step 1 and this ruling moved back.
        //
        // Nothing ELSE on this step is required: the sub-category is optional,
        // the connection date is optional, and `BR-CUS-095` is explicit that
        // the service selection never blocks creation.
        // ⛔ **NO GATE HERE ANY MORE — IT LEFT WITH THE CATEGORY CONTROL, FOR
        // STEP 1** (PO 2026-09-29). `BR-CUS-095` is explicit that the service
        // selection never blocks creation and the connection date is
        // optional, so this step asks for nothing — EXCEPT Pay now's detail
        // (`DEF-CUS-10041`): a clerk who says the money is being taken now
        // gives what that method needs before moving on. Pay later asks nothing.
        validate: () => {
          const problem = paymentDetailsProblem(form, owingNow);
          return problem === null ? true : t(problem);
        },
        content: (
          <div>
{/* ⛔ **`Customer category *` AND `Sub-category` HAVE GONE TO STEP
                1** — PO 2026-09-29, verbatim: *"move this to appliant sicne it
                is applicant - arrtributes"*. They describe the APPLICANT, and
                the sub-category is what decides plan eligibility, so they sit
                beside the name. The whole panel goes with them: it held
                nothing else, and a heading over nothing is the empty section
                B14 rule 32 is about.

                **THE CATALOGUE SOURCE IS UNTOUCHED** — `GET /service-requests/
                categories`, the same rows Settings lists, never a hardcoded
                pair. Only the slot moved. */}
            {/* ═════════════════════════════════════════════════════════════
                **THE SERVICES, AS ONE TABLE ARRAY — REQ-03 task 8, PO
                2026-09-29:** *"can we merge this two and create table array
                for this"*. Built from `03-service-1440.png` as an IMAGE
                (B14 rule 42).

                ⛔ **THE CHIPS AND THE SEPARATE *Add a service…* BOX ARE
                GONE.** *Which services* and *When each one is wanted* were
                two controls describing one act. **Adding a row IS adding a
                service** now, and the date sits in the row beside it.

                ⚠ **THE CONNECTION DATE STAYS OUTSIDE THE TABLE, AND THAT IS
                SETTLED FROM THE CODE RATHER THAN FROM TASTE**
                (`DEF-CUS-7840`): `service_requests.requested_start` —
                commented *"Connection date"* — is ONE per request, and
                `ServiceRequestService.requested_start` is one per service.

                ⚠ **`BR-CUS-1070` AS THE PO NARROWED IT ON 2026-09-22 IS
                UNTOUCHED**: the job's date SEEDS an untouched service row for
                display (`serviceStart`), and `service_starts[code]` stays
                ABSENT until the clerk types in that row — so the request
                still records *no date was given* and never invents one.
                ═════════════════════════════════════════════════════════════ */}
            <Panel as="section">
              <h3>{t("customers.serviceRequest.capture.services")}</h3>
              {/* The drawn summary line. A FACT, four words, and its
                  denominator is DERIVED — never a literal. */}
              <p
                className="text-sm text-neutral-700"
                data-services-count={enabledServices.length}
                data-services-selected={form.services.length}
              >
                {t("customers.serviceRequest.capture.servicesSelected", {
                  selected: form.services.length,
                  total: enabledServices.length,
                })}
              </p>
              <ServicesTableArray
                rows={serviceTableRows}
                options={enabledServices.map((row) => ({
                  value: row.service,
                  // ⚠ **THE CATALOGUE'S NAME, NEVER AN ENUM CODE**
                  // (`DEF-BIL-5336` was exactly this fault).
                  label: row.name,
                }))}
                dateFormat={dateFormat}
                t={translate}
                onChange={(rows) => {
                  // The blank row lives on screen, not in the form — see
                  // `pendingServiceRow`. Answering it fills a service and the
                  // row stops being blank; its ✕ drops it.
                  setPendingServiceRow(rows.some((row) => row.code === ""));
                  update(serviceRowsToForm(form, rows));
                }}
              />
              {enabledServices.length === 0 && (
                <p className="text-sm text-neutral-700">
                  {t("customers.serviceRequest.capture.noServicesEnabled")}
                </p>
              )}
              {/* The whole job's date, drawn BENEATH the table and outside it. */}
              <FieldGrid columns={2}>
                <DatePickerField
                  id="requested_start"
                  label={t("customers.serviceRequest.capture.connectionDate")}
                  value={form.requested_start}
                  onChange={(value) => update({ requested_start: value })}
                  dateFormat={dateFormat}
                  help={t("customers.serviceRequest.capture.connectionDateHelp")}
                />
              </FieldGrid>
            </Panel>
            {/* ── the old step 5, `Fees` ── */}
            <Panel as="section">
              <h3>{t("customers.serviceRequest.fees.applicationFees")}</h3>
              {/* ══════════════════════════════════════════════════════════
                  **THE FEES ARE A TABLE — `DEF-CUS-6411`, PO approval
                  2026-09-23** (*"i like this please use this"*):
                  `Fee · Charged per · Qty · Unit price · Amount · Waive · ✕`,
                  `+ Add a fee ▾` as the last row, `Total` under `Amount`.

                  ⛔ **`Quoted` AND `Outstanding` ARE OFF THIS STEP, AND IT IS
                  ARITHMETIC RATHER THAN TASTE.** The table's `Total` IS
                  `fees.quoted` — the server's sum of the unwaived lines — so a
                  `Quoted` beside it was the same figure twice. `Outstanding` is
                  `quoted − settled − collected`, and on a request being
                  captured nothing has been settled or collected: money is
                  taken on the request's own Fees panel once it is open
                  (`BR-CUS-090`). So it equalled the Total too, on every request
                  this step can show. Both figures stay where they differ — the
                  review, the confirmation and the request detail.

                  ⚠ **THE AMOUNT IS STILL THE CATALOGUE'S AND IS NEVER TYPED**
                  (PO report 2026-09-22 row 11, `DEF-CUS-5904`), and since
                  `DEF-CUS-6416` the SERVER prices the line from the charge
                  code and refuses a figure that disagrees — a stale screen
                  learns the price moved rather than quoting the old one.
                  ══════════════════════════════════════════════════════════ */}
              {draft === null ? (
                <p className="text-sm text-neutral-700">
                  {t("customers.serviceRequest.capture.feesNeedADraft")}
                </p>
              ) : (
                <ApplicationFeesTableArray
                  fees={draft.fees}
                  t={translate}
                  collection="application-fees"
                  busy={feeBusy}
                  codes={feeCodes.map((row) => ({ value: row.code, label: row.name }))}
                  pendingRow={pendingFeeRow}
                  onAddRow={() => setPendingFeeRow(true)}
                  onDropPendingRow={() => setPendingFeeRow(false)}
                  removeBlocked={
                    // ⛔ **`OQ-357` — REMOVE WHILE DRAFT, WAIVE AFTER.** The
                    // server refuses the same thing in the same words
                    // (`feeRemoveNotDraft`).
                    //
                    // ⚠ **RESTORED 2026-09-29 (`DEF-CUS-7920`).**
                    // `a503a0f4b` moved this table to
                    // `ApplicationFeesTableArray` and did not carry this prop
                    // over. `removeBlocked` is OPTIONAL on the component, so
                    // `tsc` was green, every other case was green, and the
                    // ✕ went LIVE on a request that has left draft — a clerk
                    // correcting a submitted request could press it and
                    // collect a server refusal where the button used to be
                    // disabled with its reason. **Hard-won law 2: a component
                    // with an optional prop that nothing passes.**
                    amending ? t("customers.serviceRequest.feeRemoveNotDraft") : undefined
                  }
                  onPick={(_line, code) => {
                    setPendingFeeRow(false);
                    void addTheFee(code);
                  }}
                  onRemove={(line) => void removeTheFee(line)}
                />
              )}
              {/* ⚠ **THE CATALOGUE ANSWERED AND HOLDS NOTHING RAISEABLE — a
                  STATED absence** (B14 rule 32). It rode on the old
                  *Choose a fee…* box, and the box is gone; an empty `+ Fee`
                  with no words is a screen a clerk cannot tell from a broken
                  one, which is the whole reason the sentence existed. */}
              {draft !== null &&
                (feeChargesQuery.data?.results ?? []).length > 0 &&
                feeCodes.length === 0 && (
                  <p className="mt-2 text-sm text-neutral-700" data-fee-adder-empty="">
                    {t("customers.serviceRequest.fees.noneToOffer")}
                  </p>
                )}
              {feeError !== null && (
                <p className="mt-2 max-w-prose text-sm text-danger-700" data-fee-refused="">
                  {feeError}
                </p>
              )}
              <p className="mt-2 max-w-prose text-sm text-neutral-700">
                {t("customers.serviceRequest.capture.noInvoiceNoAccount")}
              </p>
            </Panel>

            {/* ══════════════════════════════════════════════════════════
                **PAYMENT DETAILS — `DEF-CUS-10041`, PO 2026-10-11.** *"instead
                of when it is being paid > payment detail"*, then Pay now /
                Pay later, then each method's own inputs (the table the PO
                accepted; decision log 2026-10-11). Drawn only while a fee is
                owed — a `$0.00` request has nothing to take (`DEF-CUS-9819`).
                The money itself is taken at SUBMIT, below in `onCommit`.

                ⛔ This replaces a panel titled *"When is it being paid?"* whose
                card and cheque boxes were sent nowhere (`TENDER_CAPTURE
                _ACCEPTED = false`) and whose Cash said *"Record the cash on
                the request."* while recording nothing.
                ══════════════════════════════════════════════════════════ */}
            {owingNow !== "" && (
              <Panel as="section">
                <RequestPaymentDetails
                  form={form}
                  update={update}
                  owing={owingNow}
                  owingText={draft === null ? "" : moneyText(draft.fees.outstanding)}
                  currency={draft?.fees.outstanding.currency ?? null}
                  client={client}
                  timeZone={timeZone}
                  dateFormat={dateFormat}
                  t={translate}
                />
              </Panel>
            )}
          </div>
        ),
      },

      // ── 4 · REVIEW · REQ-03.4 ───────────────────────────────────────────
      {
        id: "review",
        label: t("customers.serviceRequest.step.review"),
        content: (
          <div>
            <Panel as="section">
              {/* ⚠ **NO HEADING HERE — *Check and submit* IS THE PAGE TITLE.**
                  It was an `h3` printing the same three words four inches under
                  the 32px title this lane put above it, which is the same fault
                  step 1 had and was caught the same way: by looking at the
                  built page rather than at the suite. The blueprint (p79)
                  draws the title, the stepper, and then the review blocks —
                  nothing between them. */}
              {/* The computed sub-line, repeating step 4's posture: *"N fields
                  left blank. None of them stop the request being created."* */}
              <p className="max-w-prose text-sm text-neutral-700" data-blank-count={blankOptionalCount(form)}>
                {t("customers.serviceRequest.capture.blanksDoNotBlock", {
                  count: blankOptionalCount(form),
                })}
              </p>
              {/* ⊕ `CR-161-BRC10` W6 — every answer to the utility's own
                  fields, listed automatically; nothing at all without them. */}
              <RequestCustomFieldsRecap form={form.custom} client={client} />
            </Panel>

            {/* ══════════════════════════════════════════════════════════════
                THE REVIEW READS IN THE ORDER THE CLERK FILLED IT IN — the
                blueprint's own (accounts blueprint p79–80, step 6 drawn in two
                columns). Its left column is, in order:

                    The applicant            ✎ Step 1
                    What they are asking for ✎ Step 2
                    Addresses and property   ✎ Step 3

                **It read 1 → 3 → 2**, so a clerk checking their work jumped
                from the address back to the connection they had answered a step
                earlier. Nothing about the DATA changed here — three panels
                swapped order and three headings took the drawing's words:
                `Applicant` → *The applicant*, `Service address` → *Addresses
                and property*, `Connection` → *What they are asking for*.

                ⚠ **THE DRAWN TWO-COLUMN SPLIT IS NOW BUILT** — `CR-094-BRC01`
                lane D, p079–p080 read as images. This note used to say it was
                *"not built and not faked"*, on two grounds: *"the Fees block
                needs a saved draft the wizard may not have yet, and the
                On-submit block needs the message queue this product does not
                send from."* **The first was true and is handled rather than
                avoided** — the column renders the fees it has and says so
                where there is no draft yet. **The second confused two
                blocks:** `On submit` is the request NUMBER, the state move and
                what the request will be waiting on, all three of which the
                server serves today; it is *What goes out to the applicant*
                that needs the queue, and that block is still absent.

                ⛔ **AND IT STAYS ABSENT ON PURPOSE, WHICH IS A HOLD AND NOT AN
                OVERSIGHT.** The drawing's `SEND · WHAT IT SAYS · TO · CHANNEL
                · TEMPLATE · WHEN` table and its template picker belong to the
                messaging seam a sibling lane is building; a second messages
                table drawn here would be the thing that seam exists to
                prevent.
                ══════════════════════════════════════════════════════════════ */}
            {/* **TWO COLUMNS, AS DRAWN (p079–p080).** Left: what the clerk
                answered, in the order they answered it. Right: what the
                request HAS — its documents, its money and what pressing submit
                will do. `max-lg:grid-cols-1` because this scale is
                desktop-first (`G36`); the staff app is built at 1440 and must
                work at 1280, and nothing here is a phone screen. */}
            <div className="grid grid-cols-2 gap-6 max-lg:grid-cols-1">
              <div data-review-column="left">
              <Panel as="section">
                <h3>{t("customers.serviceRequest.capture.reviewApplicant")}</h3>
                <Button
                    variant="ghost"
                    data-review-edit="applicant"
                    onClick={() => setNav({ ...nav, step: captureStepNumber("applicant") })}
                  >
                    {t("customers.serviceRequest.capture.editStep", {
                      step: captureStepNumber("applicant"),
                    })}
                </Button>
                <FieldGrid columns={3}>
                  <Field label={t("customers.serviceRequest.capture.fullName")}>
                    <TextOrNotSupplied value={form.applicant_name} t={translate} />
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.email")}>
                    <TextOrNotSupplied value={form.applicant_email} t={translate} />
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.phone")}>
                    <TextOrNotSupplied value={form.applicant_phone} t={translate} />
                  </Field>
                </FieldGrid>
                {/* ✅ B19 §7 draws `Social Security Number → ••• ••• • 4471 ·
                    stored encrypted` HERE, at the point of submission, and it is
                    now TRUE and therefore printed — DEF-632, PO 2026-08-27.

                    ⚠ **MASKED FROM THE FORM STATE, WHICH IS THE ONE PLACE ON
                    THIS SCREEN THE FULL NUMBER LEGITIMATELY EXISTS.** The clerk
                    typed it into this wizard a moment ago; showing it back in
                    full at step 6 would put a government identifier on a screen a
                    customer may be standing in front of, for no gain — the clerk
                    can go back and edit if the last four are wrong. Everywhere
                    ELSE in the product the mask is a SERVER projection
                    (`identifier.ssn_last4`) and the full value never reaches the
                    browser at all. */}
                <Field label={t("customers.serviceRequest.capture.ssn")}>
                  {form.ssn.trim() === "" && form.ssn_on_file !== "" ? (
                    <span>{ssnOnFileMask(form.ssn_on_file)}</span>
                  ) : form.ssn.trim() === "" ? (
                    <TextOrNotSupplied value="" t={translate} />
                  ) : (
                    // ⛔ **`· stored encrypted` IS OFF THE SCREEN — `DEF-CUS-6414`,
                    // B14 rule 33.** It says WHY the product holds the number
                    // the way it does, which is RATIONALE: zero words on
                    // screen. The mask itself is the fact a clerk reads, and
                    // BR-CUS-092(c)'s promise is kept by the mask, not by a
                    // sentence about it.
                    <span>{maskSsn(form.ssn)}</span>
                  )}
                </Field>
                {/* ✅ **THE ROWS THE RULING OF 2026-09-15 MADE REAL.** p080
                    draws `Channel`, `Date of birth`, `Driver's licence` and
                    `SSN` in this block; the first was never rendered and the
                    other two were absences. `Applying as` is drawn by no
                    blueprint frame and is here because `BR-CUS-1022` makes it
                    the fact that decides which of the rest were even asked —
                    a review that showed the evidence and hid the test would be
                    the least useful place to leave it out.

                    ⚠ **THE LICENCE AND THE TAX ID ARE MASKED HERE AND THE
                    `"stored encrypted"` PHRASE IS NOT PRINTED BESIDE THEM**
                    — `BR-CUS-092` clause (c) for the first and clause (d) for
                    the second, and the difference is the whole point: the
                    masking is a promise we can keep today, the encryption is
                    one we cannot make until the column exists. */}
                <FieldGrid columns={3}>
                  <Field label={t("customers.serviceRequest.capture.reviewChannel")}>
                    <TextOrNotSupplied
                      value={t(`customers.serviceRequest.channel.${form.channel}`, {
                        defaultValue: form.channel,
                      })}
                      t={translate}
                    />
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.applyingAs")}>
                    <TextOrNotSupplied
                      value={t(`customers.serviceRequest.applicantKind.${form.applicant_kind}`, {
                        defaultValue: form.applicant_kind,
                      })}
                      t={translate}
                    />
                  </Field>
                  {form.applicant_kind === "business" ? (
                    <Field label={t("customers.serviceRequest.capture.taxId")}>
                      <TextOrNotSupplied
                        value={maskIdentifier(form.tax_id)}
                        t={translate}
                      />
                    </Field>
                  ) : (
                    <Field label={t("customers.serviceRequest.applicant.driversLicence")}>
                      <TextOrNotSupplied
                        value={
                          form.drivers_licence.trim() === ""
                            ? licenceOnFileMask(form.drivers_licence_on_file)
                            : maskIdentifier(form.drivers_licence)
                        }
                        t={translate}
                      />
                    </Field>
                  )}
                </FieldGrid>
                {/* ✅ **`CUSTOMER CATEGORY` AND `SUB-CATEGORY` READ BACK WITH THE
                    APPLICANT — REQ-03, PO 2026-09-29:** *"move this to appliant
                    sicne it is applicant - arrtributes"*. They are facts about
                    who is applying, not about what is being asked for, and
                    `04-review-1440.png` draws them as the last row of this
                    panel.

                    ⛔ **`Services requested` — the comma list — IS GONE WITH
                    THEM.** It said *Water, Sewer, Trash* one panel above a
                    table that names every service on its own row with its own
                    date and its own status. One fact, once. */}
                <FieldGrid columns={2}>
                  <Field label={t("customers.serviceRequest.capture.category")}>
                    {/* `DEF-CUS-6413` — the category's NAME from the same served
                        catalogue the picker offered, never its code. */}
                    <TextOrNotSupplied
                      value={
                        form.account_type_code === ""
                          ? null
                          : ([
                              ...(categoriesQuery.data?.selectable ?? []),
                              ...(categoriesQuery.data?.legacy ?? []),
                            ].find((row) => row.code === form.account_type_code)?.name ??
                            form.account_type_code)
                      }
                      t={translate}
                    />
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.subCategory")}>
                    <TextOrNotSupplied
                      value={
                        // B14 rule 31 — the NAME, resolved from the SAME rows
                        // the picker offered.
                        subtypes.rows.find((row) => row.id === form.account_subtype_id)?.name ?? ""
                      }
                      t={translate}
                    />
                  </Field>
                </FieldGrid>
                {form.applicant_kind !== "business" && (
                  <Field label={t("customers.serviceRequest.applicant.dateOfBirth")}>
                    {/* `DEF-CUS-6413` — the tenant's date format, like every
                        other date on this screen; it printed `2026-09-02`. */}
                    <DateOrNotSupplied
                      value={form.date_of_birth}
                      t={translate}
                      timeZone={timeZone}
                      dateFormat={dateFormat}
                    />
                  </Field>
                )}
              </Panel>

              <Panel as="section">
                <h3>{t("customers.serviceRequest.capture.reviewAskingFor")}</h3>
                <Button
                    variant="ghost"
                    data-review-edit="asking-for"
                    onClick={() => setNav({ ...nav, step: captureStepNumber("service") })}
                  >
                    {t("customers.serviceRequest.capture.editStep", {
                      step: captureStepNumber("service"),
                    })}
                </Button>
                {/* ══════════════════════════════════════════════════════════
                    **THE SAME TABLE THE REQUEST DETAIL DRAWS — PO report
                    2026-09-22, rows 14 and 15, and B14 rule 43.**

                    Two `Field`s stood here: a SUMMARY of the per-service dates
                    (*05/12/2026, all three*) and the job's `Connection date`
                    beside it. The summary could state the AGREEMENT and could
                    never show one service starting on a different day from
                    another — which is the thing a clerk is checking on the
                    review step.

                    ⚠ **EXACTLY THREE COLUMNS, AND THAT IS A RULING.** PO
                    2026-09-22, verbatim *"dont add these"*, refusing a size
                    column, a charge column and a per-service status. No
                    placeholder column, no hidden column, no commented-out one.

                    ⚠ **`BR-CUS-1070` IS OBEYED HERE AND NOT WEAKENED.** The
                    two dates are independent facts and neither falls back to
                    the other: the SERVICE column carries the per-service date
                    and prints a dash where there is none, and the CONNECTION
                    DATE column carries the whole job's date. p080 draws them
                    as adjacent rows of one request precisely because *"that
                    state is unreachable under any fallback."*
                    ══════════════════════════════════════════════════════════ */}
                {/* ⚠ **`serviceStartsPayload`, NOT `form.service_starts` —
                    `DEF-CUS-6409`.** This read the clerk's typed dates alone,
                    so every service whose box showed the job date printed `—`
                    here. It reads what is SENT now: the review is where a clerk
                    checks what will be stored, and it must not disagree with
                    the POST. The note above about `BR-CUS-1070` predates the
                    PO's ruling of 2026-09-22 (b), which narrowed it to ONE
                    direction — job → service. */}
                {/* ⚠⚠ **THE CONNECTION DATE IS PRINTED ONCE AND IS NOT A COLUMN
                    — `DEF-CUS-7840`, filed before it was fixed.** The review drew
                    `SERVICE · REQUESTED START · CONNECTION DATE` and repeated the
                    request-level date down every row, which made a per-request
                    fact look per-service and invited a clerk to believe the
                    rows could differ. Settled from the CODE and not from an
                    opinion: `service_requests.requested_start` — commented
                    *"Connection date"* — is ONE per request, and
                    `ServiceRequestService.requested_start` is one per service.

                    The freed column is `STATUS`, which the PO asked for so a
                    clerk sees what is already on the property before promising
                    a date — see `serviceOnSite` for the half of it this
                    product can honestly answer today. */}
                <ReviewServicesTable
                  rows={serviceStartsPayload(form).map((row) => ({
                    code: row.code,
                    requested_start: row.requested_start ?? "",
                    status: serviceOnSite(form),
                  }))}
                  t={translate}
                  timeZone={timeZone}
                  dateFormat={dateFormat}
                  collection="review-services"
                />
                <div className="mt-4">
                  <Field label={t("customers.serviceRequest.capture.connectionDate")}>
                    <span data-review-connection-date="">
                      <DateOrNotSupplied
                        value={form.requested_start}
                        t={translate}
                        timeZone={timeZone}
                        dateFormat={dateFormat}
                      />
                    </span>
                  </Field>
                </div>
              </Panel>

              <Panel as="section">
                <h3>{t("customers.serviceRequest.capture.reviewAddresses")}</h3>
                <Button
                    variant="ghost"
                    data-review-edit="addresses"
                    onClick={() => setNav({ ...nav, step: captureStepNumber("property") })}
                  >
                    {t("customers.serviceRequest.capture.editStep", {
                      step: captureStepNumber("property"),
                    })}
                </Button>
                <FieldGrid columns={2}>
                  <Field label={t("customers.serviceRequest.capture.address")}>
                    <TextOrNotSupplied value={form.address_as_given} t={translate} />
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.unit")}>
                    {/* *"Blanks are shown as blanks, never omitted."* */}
                    <TextOrNotSupplied value={form.address_unit_as_given} t={translate} />
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.plot")}>
                    <TextOrNotSupplied value={form.plot_or_parcel} t={translate} />
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.whatIsBeingBuilt")}>
                    <TextOrNotSupplied value={form.what_is_being_built} t={translate} />
                  </Field>
                  <Field label={t("customers.serviceRequest.location.lookupFound")}>
                    {/* STORED on the request (B19 §7) — the resolver's verdict is
                        a fact the review renders, not a re-computation.

                        ⚠ **`lookup_found` HOLDS A CATALOGUE KEY BY DESIGN
                        (`DEF-CUS-5010`), SO IT MUST BE RESOLVED AND NEVER
                        PRINTED** — `DEF-CUS-5905`. With `TextOrNotSupplied`
                        this step printed the literal string
                        `customers.serviceRequest.lookup.premiseNoUnit` to the
                        clerk, at the moment they are confirming the facts they
                        are about to submit. B14 rule 31 forbids an internal
                        code as the visible value of a field, so this is a rule
                        breach and not an untidiness.

                        ⚠ **THE THIRD SURFACE OF ONE DEFECT.** `DEF-CUS-5420`
                        fixed the two detail surfaces on 2026-09-15 and missed
                        this one, which is why the component is now the SAME one
                        the detail page uses rather than a second way of doing
                        it: `CatalogueSentence` resolves a key, falls back to the
                        text itself for a clerk's free wording, and prints a
                        readable sentence when the value is a machine token
                        nobody catalogued. */}
                    <CatalogueSentence
                      value={draft?.location_and_services.lookup_found ?? null}
                      t={translate}
                    />
                  </Field>
                  {/* ⚠ **`premise_no` AND `unit_no`, NEVER A UUID — B14 rule
                      31**, and `DEF-CUS-5386` is that live defect one screen
                      over. p080 draws `Matched premises → PR-0731 · exact` and
                      `Matched unit → U-001884 · exact`; our own series read
                      `P-00074` and `U-00101-A` and the drawn ones are
                      illustrations (rule 37). The `· exact` half is the
                      clerk's own pick — see `matchRows`. */}
                  <Field label={t("customers.serviceRequest.capture.matchedPremises")}>
                    <TextOrNotSupplied value={form.picked_premise_no} t={translate} />
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.matchedUnit")}>
                    <TextOrNotSupplied value={form.picked_unit_no} t={translate} />
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.city")}>
                    {/* `DEF-CUS-10039` follow-up — the TYPED value when no premise is picked. */}
                    <TextOrNotSupplied
                      value={form.picked_premises_id === "" ? form.address_city_as_given : form.picked_premises_city}
                      t={translate}
                    />
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.addressState")}>
                    {/* `DEF-CUS-10039` follow-up — the TYPED value when no premise is picked. */}
                    <TextOrNotSupplied
                      value={form.picked_premises_id === "" ? form.address_state_as_given : form.picked_premises_state}
                      t={translate}
                    />
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.postalCode")}>
                    {/* `DEF-CUS-10039` follow-up — the TYPED value when no premise is picked. */}
                    <TextOrNotSupplied
                      value={form.picked_premises_id === "" ? form.address_postal_code_as_given : form.picked_premises_postal}
                      t={translate}
                    />
                  </Field>
                  {/* `DEF-CUS-6408` — the five parts as ONE line, written the
                      way the request detail writes it (`billingAddressLine`). */}
                  <Field label={t("customers.serviceRequest.location.billingAddress")}>
                    <span data-review-billing="">
                      <TextOrNotSupplied
                        value={
                          form.billing_address_same
                            ? t("customers.serviceRequest.location.billingSame")
                            : billingAddressLine({ ...form.billing_address, legacy: null })
                        }
                        t={translate}
                      />
                    </span>
                  </Field>
                </FieldGrid>
              </Panel>
              </div>

              <div data-review-column="right">
                {/* ══════════════════════════════════════════════════════════
                    **`Documents` ✎ Step 4** — the drawn `DOCUMENT · FILE ·
                    STATE` table and, beneath it, the one sentence that matters
                    at this point: how many required documents are not cleared.

                    ⚠ **THE ROWS ARE THE SERVER'S AND THE COUNT IS THE
                    SERVER'S.** `documents.checklist_unmet` is what the TENANT
                    ticked for this request's job type (`BR-CUS-095`); a count
                    computed here would be this screen's opinion about a
                    jurisdiction's law. The `FILE` column reads *No file* on
                    every row today and that is TRUE — no route in this product
                    accepts a file for a request — rather than a gap in this
                    table.
                    ══════════════════════════════════════════════════════════ */}
                <Panel as="section">
                  <h3>{t("customers.serviceRequest.tab.documents")}</h3>
                  <Button
                      variant="ghost"
                      data-review-edit="documents"
                      onClick={() => setNav({ ...nav, step: captureStepNumber("applicant") })}
                    >
                      {t("customers.serviceRequest.capture.editStep", {
                        step: captureStepNumber("applicant"),
                      })}
                  </Button>
                  {(draft?.documents.documents ?? []).length === 0 ? (
                    <p className="text-sm text-neutral-700">
                      {t("customers.serviceRequest.documents.noneAttached")}
                    </p>
                  ) : (
                    <table className="data-table" data-table="review-documents">
                      <thead>
                        <tr>
                          <th>{t("customers.serviceRequest.documents.col.document")}</th>
                          <th>{t("customers.serviceRequest.capture.col.file")}</th>
                          <th>{t("customers.serviceRequest.capture.col.state")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(draft?.documents.documents ?? []).map((doc) => (
                          <tr key={doc.id} data-doc-row={doc.doc_type}>
                            <td>
                              {t(`customers.serviceRequest.docType.${doc.doc_type}`, {
                                defaultValue: doc.doc_type,
                              })}
                            </td>
                            <td>
                              {doc.attached
                                ? t("customers.serviceRequest.documents.attached")
                                : t("customers.serviceRequest.documents.notAttached")}
                            </td>
                            {/* ⚠ **THE KIT'S CELL, NOT A THIRD SPELLING — PO
                                report 2026-09-22 rows 2 and 3, B14 rule 43.**
                                This printed the RAW `verification_state`
                                through the catalogue **with no `file_present`
                                guard at all**, so on the beta's six seeded rows
                                (`DEF-CUS-5872`) it read `Verified` over a file
                                nobody can open — and it still said `Not yet
                                checked`, the word for a virus scan this product
                                does not run, after that had been removed from
                                the two tables either side of it. One verdict,
                                one place. */}
                            <td data-doc-state="">
                              <DocumentStateCell row={doc} t={translate} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {(draft?.documents.checklist_unmet ?? []).length > 0 && (
                    <p
                      className="text-sm text-neutral-700"
                      data-docs-unmet={(draft?.documents.checklist_unmet ?? []).length}
                    >
                      {t("customers.serviceRequest.capture.docsNotCleared", {
                        count: (draft?.documents.checklist_unmet ?? []).length,
                      })}
                    </p>
                  )}
                </Panel>

                {/* ══════════════════════════════════════════════════════════
                    **`Fees` ✎ Step 5** — the five drawn rows: Quoted · Fee
                    timing · Taken · Settled by an invoice · Outstanding.

                    ⚠ **EVERY FIGURE IS THE SERVER'S, THROUGH `MoneyCell`.**
                    Hard rule 2 — stored to four decimals, displayed at two —
                    and `MoneyOrAbsence` carries the server's own 2-dp
                    `display` beside it so a test can prove the two agree
                    without re-implementing the rounding a third time.
                    **Nothing on this screen adds, subtracts or rounds
                    anything.**

                    ⚠ **THE DRAWN `$130.00` AND `$105.00` ARE GONE WITH THE
                    RULING OF 2026-09-15, not with a style choice.** Step 5
                    takes the application fee and nothing else — *"all other
                    fes are taken duirng movein or new conenct request"* — so
                    two of the drawing's three quoted lines leave this screen
                    and the large outstanding leaves with them. An outstanding
                    can still arise from a PART-PAID application fee, which is
                    why the row stays.
                    ══════════════════════════════════════════════════════════ */}
                <Panel as="section">
                  <h3>{t("customers.serviceRequest.capture.stepShort.fees")}</h3>
                  <Button
                      variant="ghost"
                      data-review-edit="fees"
                      onClick={() => setNav({ ...nav, step: captureStepNumber("service") })}
                    >
                      {t("customers.serviceRequest.capture.editStep", {
                        step: captureStepNumber("service"),
                      })}
                  </Button>
                  {draft === null ? (
                    <p className="text-sm text-neutral-700">
                      {t("customers.serviceRequest.capture.feesNeedADraft")}
                    </p>
                  ) : (
                    <div data-review-fees="">
                      {/* ══════════════════════════════════════════════════
                          **THE SAME FEE LINES AS STEP 5, READ-ONLY —
                          `DEF-CUS-6411`, PO approval 2026-09-23.** The five
                          stacked rows (`Quoted · Fee timing · Taken · Settled
                          by an invoice · Outstanding`) became: the table with
                          its `Total`, then the timing, then what is still
                          owed. `Quoted` left because the Total IS it; `Taken`
                          and `Settled by an invoice` left because a request
                          being captured has had neither — money is taken on the
                          request once it is open (`BR-CUS-090`) — and
                          `Outstanding` already nets both.

                          ⛔ **AND *"70.00 is still owed. Documents gate this,
                          not money."* IS GONE (`DEF-CUS-6412`, `DEF-CUS-6414`).**
                          Its figure had no currency (it printed the server's
                          bare `display`), it repeated `Outstanding` one line
                          up, and its second sentence is RATIONALE, which B14
                          rule 33 puts at zero words on screen.
                          ══════════════════════════════════════════════════ */}
                      <FeeLinesTable
                        fees={draft.fees}
                        t={translate}
                        collection="review-fees"
                      />
                      <div className="mt-4">
                      <FieldGrid columns={2}>
                        <Field label={t("customers.serviceRequest.capture.feeTiming")}>
                          <TextOrNotSupplied
                            value={
                              draft.fees.fee_timing === null || draft.fees.fee_timing === ""
                                ? null
                                : // Step 3's own words (*Pay now* / *Pay later*), so
                                  // Review names the choice the clerk made there.
                                  draft.fees.fee_timing === PAY_NOW
                                  ? t("customers.serviceRequest.pay.now")
                                  : draft.fees.fee_timing === PAY_LATER
                                    ? t("customers.serviceRequest.pay.later")
                                    : String(draft.fees.fee_timing)
                            }
                            t={translate}
                          />
                        </Field>
                        <Field label={t("customers.serviceRequest.fees.outstanding")}>
                          <span data-review-outstanding="">
                            <MoneyOrAbsence money={draft.fees.outstanding} t={translate} />
                          </span>
                        </Field>
                      </FieldGrid>
                      </div>
                    </div>
                  )}
                </Panel>

                {/* ══════════════════════════════════════════════════════════
                    **`What the customer is told` — THE ONE GENUINELY NEW
                    CAPABILITY IN THIS REDESIGN.** PO, 2026-09-29: *"on review
                    you should display 1 card for communcaition to cusomer - in
                    table format step 4"*.

                    ⚠ **A MESSAGE THAT WILL NOT BE SENT GETS ITS OWN ROW SAYING
                    SO.** An absent row and a withheld one look identical, and
                    that difference is the whole reason the card is worth
                    drawing.

                    ⚠ **NOTHING ENGLISH CROSSES THE WIRE** (`BR-SHL-020` r2).
                    The server sends occasion, channel and moment as KEYS and
                    `messageRows` resolves every one through the catalogue; the
                    ADDRESS is data and travels as it is.

                    ⚠ **A STATED ABSENCE IS RENDERED AS AN ABSENCE AND NEVER
                    FILLED WITH PLAUSIBLE ROWS.** Where no draft exists yet, or
                    the notifications seam cannot answer for this request, the
                    card says so — telling a clerk somebody is about to be
                    written to when nobody is would be the worst thing this
                    card could do.
                    ══════════════════════════════════════════════════════════ */}
                <section>
                  {/* ⊕ `DEF-CUS-10042` — the kit's TableArray, with *Add a
                      message*; the automatic rows stay read-only. It draws
                      its OWN frame, so it is not wrapped in a Panel (the walk
                      of 2026-10-11 found a panel inside a panel). */}
                  <CustomerMessagesCard
                    rows={messageRows}
                    absence={messageAbsence}
                    t={translate}
                    extra={{
                      rows: extraShown,
                      templates: extraTemplates,
                      defaultAddress: form.applicant_email.trim(),
                      onChange: (rows) => setExtraRows(rows),
                    }}
                  />
                </section>

                {/* ══════════════════════════════════════════════════════════
                    **`On submit` ✎ Step 6** — the three drawn rows, and all
                    three are served today.

                    ⚠ **THE NUMBER EXISTS BEFORE THE SUBMIT, WHICH IS
                    `BR-CUS-093` AND IS THE DRAWING'S OWN POINT:** *"A draft
                    carries its own number, so a clerk can quote it to somebody
                    standing at the counter who has not finished answering."*
                    Where the server's minimum is not met yet there IS no
                    number, and the row says that rather than inventing one.
                    ══════════════════════════════════════════════════════════ */}
                {/* Nothing is submitted when a request is being CORRECTED, so
                    the panel about what submitting does is not drawn. */}
                {!amending && (
                <Panel as="section">
                  <h3>{t("customers.serviceRequest.capture.onSubmit")}</h3>
                  <Field label={t("customers.serviceRequest.capture.requestNumber")}>
                    {requestNo === null ? (
                      <span>{t("customers.serviceRequest.capture.notNumberedYet")}</span>
                    ) : (
                      <span data-request-no={requestNo}>
                        {`${requestNo} · ${t("customers.serviceRequest.capture.alreadyAllocated")}`}
                      </span>
                    )}
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.reviewState")}>
                    <span>{t("customers.serviceRequest.capture.draftToSubmitted")}</span>
                  </Field>
                  <Field label={t("customers.serviceRequest.capture.waitingOn")}>
                    <TextOrNotSupplied value={draft?.header.waiting_on ?? null} t={translate} />
                  </Field>
                </Panel>
                )}
              </div>
            </div>
          </div>
        ),
      },
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    form,
    draft,
    nav,
    categoriesQuery.data,
    servicesQuery.data,
    subtypes.rows,
    t,
    // ⊕ `CR-161-BRC10` W6 — the refusals and the three registries a step reads.
    customErrors,
    customersRegistry,
    accountsRegistry,
    premisesRegistry,
    // `DEF-CUS-10040` / `DEF-CUS-10042` — state drawn inside steps 2 and 4.
    cityCheck.check,
    extraShown,
    extraTemplates,
  ]);

  // ── REQ-03.sent — the confirmation ────────────────────────────────────────
  if (sent !== null) {
    return <CaptureConfirmation detail={sent} t={translate} />;
  }

  // ── A REQUEST BEING OPENED — nothing to type into until it is in hand ──────
  // (`DEF-CUS-6427`). An input drawn before the load lands is an input whose
  // contents the load then replaces, or whose empty value a Save sends.
  if (loadingExisting) {
    return (
      <div data-screen="REQ-03">
        <p
          role={existingQuery.isError ? "alert" : "status"}
          className="text-sm text-neutral-700"
        >
          {existingQuery.isError
            ? t("customers.serviceRequest.detail.loadFailed")
            : t("states.loading")}
        </p>
      </div>
    );
  }

  // ── A DECIDED REQUEST, REACHED BY A TYPED ADDRESS ──────────────────────────
  // No list row and no detail page draws a door onto one (`requestIsEditable`),
  // and the server refuses the PATCH anyway. This says so BEFORE the clerk
  // types anything, in the server's own words, and draws no form.
  if (draft !== null && !requestIsEditable(draft.header.state)) {
    return (
      <div data-screen="REQ-03">
        <PageHeader
          kicker={t("customers.serviceRequest.capture.kickerEdit", { number: requestNo ?? "" })}
          title={draft.header.applicant ?? requestNo ?? ""}
          backTo={{
            to: tenantPath(serviceRequestPath(draft.header.id)),
            label: requestNo ?? t("customers.serviceRequest.detail.back"),
          }}
        />
        <p role="alert" className="text-sm text-danger-700" data-edit-refused={draft.header.state}>
          {t(editRefusalKey(draft.header.state))}
        </p>
      </div>
    );
  }

  /** A correction is saved and the clerk goes back to the request they were
   *  correcting — the page that sent them here, now showing what they fixed. */
  async function saveChangesAndReturn(): Promise<void> {
    if (draft === null) return;
    if (await persist(form, currentStep)) {
      navigate(tenantPath(serviceRequestPath(draft.header.id)), { state: LEAVE_DELIBERATELY });
    }
  }

  const currentStep = CAPTURE_STEPS[nav.step - 1] ?? "applicant";

  // ⚠ **`DEF-SHL-10001` — THE LEAVE-PAGE POPUP'S *Save as draft* IS THE
  // REQUEST ITSELF.** A request in draft is this screen's store: the same
  // `persist` every forward move already calls. Two cases keep no draft and
  // say so instead: a request being CORRECTED after it left draft (saving it
  // would not be a draft), and a form with no applicant yet, which `persist`
  // answers `true` without writing anything — a save that would report a
  // draft that does not exist.
  const leaveDraft: LeaveDraft | null = amending
    ? null
    : {
        onSave: async () =>
          canCreateDraft(form) && (await persist(form, currentStep))
            ? { ok: true }
            : { ok: false },
        savedMessage: t("leaveGuard.saved", { place: t("customers.accounts.tab.requests") }),
      };

  return (
    // `REQ-03` — the screen id a door onto this wizard is asserted against
    // (hard-won law 2: assert the destination by ADDRESS and by the screen it
    // opens). A DOM hook, never a value a clerk reads (B14 rule 31).
    <div data-screen="REQ-03">
      {/* ══════════════════════════════════════════════════════════════════
          THE HEAD IS THE BLUEPRINT'S, READ OFF THE PAGE IMAGES — `CR-094-BRC01`
          lane F, accounts blueprint p75–80, all six frames drawn at 1280.

          Every frame draws the same three lines, and they change with the step:

              NEW REQUEST                     ← the kicker, identical on all six
              Who is this request for?        ← the TITLE, one per step
              Step 1 of 6 · Customer          ← the sub-line, one per step

          and the six titles, quoted in order: *Who is this request for?* ·
          *What are they asking for?* · *Addresses* · *Documents* · *Fees* ·
          *Check and submit*.

          TWO THINGS CHANGED HERE:

          1 · **The kicker was `NEW SERVICE REQUEST` and is drawn `NEW
              REQUEST`.** The screen already sits under a `Requests` crumb and
              inside the Requests register; the extra word was ours.
          2 · **The title was the constant *Capture a service request.* on all
              six steps**, with the step's own question demoted to an `h3`
              inside the body. The drawing puts the question in the page title,
              which is what a 32px line is for (B14 rule 40): it says what THIS
              screen is asking, and it changes as the clerk moves.

          ⚠ **THE SUB-LINE IS NOT THE ONE THAT WAS REFUSED, AND THE DIFFERENCE
          MATTERS.** This block previously carried a standing `NO SUB-LINE`
          note: B19 §1 drew *"Five steps · the request is created and numbered
          when the fee is collected."*, which was false twice — `DEF-633` on the
          count and `BR-CUS-093(c)` on when a request is numbered — so it was
          taken out rather than reworded into a third claim nobody ruled. **That
          refusal is untouched.** `Step N of 6 · <step>` makes NO claim about
          numbering and none about a five-step flow; it states which of six
          steps the clerk is standing on, which is true by construction and is
          what the blueprint draws on every one of the six frames. The false
          sentence still has nowhere in this file to be printed from.
          ══════════════════════════════════════════════════════════════════ */}
      <PageHeader
        kicker={
          amending
            ? t("customers.serviceRequest.capture.kickerEdit", { number: requestNo ?? "" })
            : t("customers.serviceRequest.capture.kicker")
        }
        title={t(`customers.serviceRequest.capture.stepTitle.${currentStep}`)}
        rollup={
          <span className="text-sm text-neutral-700">
            {t("customers.serviceRequest.capture.stepOfSix", {
              n: nav.step,
              total: CAPTURE_STEPS.length,
              name: t(`customers.serviceRequest.capture.stepShort.${currentStep}`),
            })}
          </span>
        }
        backTo={{
          to: tenantPath(SERVICE_REQUESTS_ROUTE),
          label: t("customers.serviceRequest.detail.back"),
        }}
        secondaryActions={
          /* ══════════════════════════════════════════════════════════════
              **THE REFUSAL IS VISIBLE TEXT, NOT A `title` — PO 2026-09-20,
              verbatim: *"we should show a message in short to user when this
              happens"*.**

              ⚠ **A `title` IS REACHABLE BY A MOUSE HOVER AND BY NOTHING
              ELSE.** Not by a touch, not by a keyboard, and not by a screen
              reader on a DISABLED control — which is the one control it was
              hung on. The sentence a clerk needed most was the sentence only
              a clerk with a mouse could get at, which is hard-won law 2's
              mirror: a live refusal nothing asks about.

              **B14 rule 33** caps an INSTRUCTION at six words per sentence
              and puts RATIONALE at **zero words on screen**. The key it
              replaced here was thirty-eight words of rationale — *why* a
              request needs these fields, *what* the number is for. What is
              drawn is the instruction: **"Enter the name first."**

              ⚠ **`aria-describedby` AND NOT `aria-labelledby`**: the button
              is still called *Save as draft*; the note says why it will not
              act. And the note carries the id rather than the button
              carrying the words, so the sentence exists on screen exactly
              once. */
          <>
            {!canCreateDraft(form) && (
              <span id={DRAFT_BLOCKED_NOTE_ID} className="text-sm text-neutral-700">
                {t("customers.serviceRequest.capture.nameFirst")}
              </span>
            )}
            {/* ✅ **ON A REQUEST THAT HAS LEFT DRAFT THIS IS `Save changes`**
                (`DEF-CUS-6427`) — it is not a draft, and a clerk correcting
                one phone number on step 1 should not have to walk to step 6
                to save it. It sends only what changed and returns to the
                request. */}
            <Button
              variant="secondary"
              disabled={!canCreateDraft(form) || save.isPending}
              aria-describedby={canCreateDraft(form) ? undefined : DRAFT_BLOCKED_NOTE_ID}
              onClick={() =>
                void (amending
                  ? saveChangesAndReturn()
                  : persist(form, currentStep).then((ok) => (ok ? saveExtras() : null)))
              }
            >
              {amending
                ? t("customers.serviceRequest.capture.saveChanges")
                : t("customers.serviceRequest.capture.saveAsDraft")}
            </Button>
          </>
        }
      />

      {/* ══════════════════════════════════════════════════════════════════
          **`CAPTURING FOR A CUSTOMER` — A PILL, AND NO LONGER A PANEL AROUND
          ONE PILL** (`DEF-CUS-6007`, 2026-09-20).

          The clerk's own name is still NOT drawn: no payload carries it — the
          server stamps `received_by` from the session and serves no display
          name — and a hard-coded *"Billing clerk: A. Reed"* is the prototype's
          fixture. That refusal is untouched.

          ⚠ **WHAT CAME OFF IS THE `Panel`, AND THIS FILE ALREADY ARGUED IT
          ONE SCREEN DOWN.** The co-applicant block's own note, written when its
          heading went: *"A `Panel` is this repo's INFORMATION GROUP, and a
          group of one checkbox is not a group."* A group of one status pill is
          not a group either — it was a bordered `p-4 mb-4` box drawn around
          four words, which is B14 rule 32's *"too much content"* in layout
          rather than in copy, and it put a 16px box between the 32px page head
          (rule 40) and the wizard.

          **The four words themselves are rule 33-clean and stay**: it is a
          FACT, capped at six words, carrying no rationale.

          ⚠ **`data-banner` MOVES TO A BARE WRAPPER RATHER THAN ONTO THE
          PILL.** `StatusPill` takes `tone`, `title` and `children` and spreads
          nothing, so an extra attribute on it is silently dropped — dead markup
          that every check passes over. Widening the shared component for one
          screen's handle is what B14 rule 36 calls hand-rolling from the other
          end. The `div` carries `mb-4`, which is the 16px BLOCK step of rule
          39's scale — the gap the `Panel` used to supply — and no border, no
          fill and no padding, because a group of one is not a group. The handle
          itself is part of the contract, the same way `Button`'s `data-variant`
          is: a rendered-output check is the only instrument that can see this
          at all (hard-won law 6).
          ══════════════════════════════════════════════════════════════════ */}
      <div className="mb-4" data-banner="capturing-for-a-customer">
        <StatusPill tone="neutral">
          {t("customers.serviceRequest.capture.capturingForACustomer")}
        </StatusPill>
      </div>

      {saveError !== null && (
        <p role="alert" className="text-sm text-danger-500">
          {saveError}
        </p>
      )}

      <WizardFrame
        steps={steps}
        nav={nav}
        saveDraft={leaveDraft}
        onNavChange={(next) => {
          // Persist on every forward move, so a browser crash on step 5 does
          // not lose steps 1–4 — and so the number exists as early as the
          // server allows (BR-CUS-093).
          if (next.step > nav.step) {
            void persist(form, currentStep);
          }
          setNav(next);
        }}
        commitLabel={
          amending
            ? t("customers.serviceRequest.capture.saveChangesCommit")
            : t("customers.serviceRequest.capture.submit")
        }
        commitFailedTitle={
          amending
            ? t("customers.serviceRequest.capture.saveChangesFailed")
            : t("customers.serviceRequest.capture.submitFailed")
        }
        onCommit={async (): Promise<WizardCommitOutcome> => {
          const saved = await persist(form, "review");
          // `DEF-CUS-10042` — the clerk's added messages, before anything
          // that could fire them (the submit fires the `On submit` rows).
          const extraRefused = saved ? await saveExtras() : null;
          if (extraRefused !== null) {
            return { ok: false, reason: extraRefused };
          }
          // ✅ **A CORRECTION IS SAVED, NEVER RE-SUBMITTED (`DEF-CUS-6427`).**
          // `submit` moves DRAFT → SUBMITTED and nothing else; on a request
          // already past it the save IS the whole commit.
          if (amending) {
            return saved
              ? { ok: true }
              : {
                  ok: false,
                  reason: saveError ?? t("customers.serviceRequest.capture.saveChangesFailed"),
                };
          }
          if (!saved || draft === null) {
            return {
              ok: false,
              reason: saveError ?? t("customers.serviceRequest.capture.cannotSaveDraftYet"),
            };
          }
          // ══════════════════════════════════════════════════════════════
          // **THE WRITE AND THE RE-READ ARE SEPARATE ACTS AND HAVE SEPARATE
          // FAILURES — `DEF-CUS-6178`, PO report 2026-09-22 PRIORITY 0.**
          //
          // These were ONE `try` until today: submit, re-read, show. So a
          // failure of the SECOND was reported with the words that belong to
          // the FIRST, and the clerk read **"We could not submit this request
          // / Something went wrong. Nothing was saved — try again."** over a
          // request the server holds as `submitted`. Reproduced in a browser
          // (`10-scripts/po20260922_submit_after_commit_reproduce.mjs`), those
          // two sentences exactly, with the state read back as `submitted`.
          //
          // ⚠ **THE RE-READ HAS FAR MORE WAYS TO FAIL THAN THE SUBMIT IT
          // FOLLOWS.** `GET /service-requests/{id}` builds the WHOLE detail
          // payload — every tab, every fee line, every document, every
          // timeline row — where the submit moves one state. So the call most
          // likely to break is the one that runs after the point of no return.
          //
          // ⚠ **AND A CLERK TOLD *nothing was saved* RE-ENTERS THE WHOLE
          // APPLICATION.** That is the expensive half: the second submit is a
          // no-op (hard rule 6, `idempotent_replay`), so the product does not
          // duplicate anything — the person does the work twice for nothing.
          // ══════════════════════════════════════════════════════════════
          // ══════════════════════════════════════════════════════════════
          // **PAY NOW TAKES THE MONEY HERE, BEFORE THE SUBMIT — `DEF-CUS-10041`.**
          // Before the submit so a refusal (no till open, the fee changed
          // under the clerk) leaves the request a DRAFT the clerk can fix and
          // press again, rather than a submitted request with a half-told
          // story. The amount is what the server says is owed NOW, re-read,
          // because the counter takes the whole fee (`OQ-CUS-12624`) and a
          // stale figure is refused. Idempotent on the receipt (rule 6), so a
          // second press after a failed submit does not take it twice.
          // ══════════════════════════════════════════════════════════════
          if (form.fee_timing === PAY_NOW) {
            try {
              const fresh = await getServiceRequest(draft.header.id, client);
              const owing = owingAmount(fresh);
              if (owing !== "") {
                await collectServiceRequestFee(
                  draft.header.id,
                  feeCollectionBody(form, owing, todayInZone(timeZone)),
                  client,
                );
              }
            } catch (error) {
              return {
                ok: false,
                reason: isApiError(error)
                  ? t(error.messageKey, error.params)
                  : t("api.error.unexpected"),
              };
            }
          }
          try {
            // TC-REQ-2 / hard rule 6 — a second submit is a no-op on the
            // server (`idempotent_replay: true`), so a double-click cannot
            // create a second request or send a second acknowledgement.
            await submitServiceRequest(draft.header.id, client);
          } catch (error) {
            // ⚠ **THIS IS THE ONLY BRANCH THAT MAY SAY *nothing was saved*.**
            // The write itself refused, so nothing moved and the sentence is
            // true.
            return {
              ok: false,
              reason: isApiError(error)
                ? t(error.messageKey, error.params)
                : t("api.error.unexpected"),
            };
          }
          // PAST HERE THE REQUEST IS SUBMITTED. Whatever happens next, the
          // screen says so.
          try {
            setSent(await getServiceRequest(draft.header.id, client));
          } catch {
            // ⚠ **THE DRAFT WE ALREADY HOLD, NOT A FABRICATED ONE.** It
            // carries the request NUMBER, which is the one thing the clerk
            // needs to find this again, and `CaptureConfirmation` shows it.
            // The acknowledgement block may be one beat behind; a stale block
            // on a real request is a different order of wrong from telling
            // somebody their application was lost.
            setSent(draft);
          }
          return { ok: true };
        }}
        onCommitted={() => {
          if (amending && draft !== null) {
            navigate(tenantPath(serviceRequestPath(draft.header.id)));
          }
        }}
      />

      {/* *"Saved as draft SR-26-0048"* is FALSE of a request that has left
          draft, so the footer is drawn only for one that has not; the kicker
          carries the number while correcting. */}
      {!amending && (
        <CaptureDraftFooter
          step={nav.step}
          steps={CAPTURE_STEPS.length}
          requestNo={requestNo}
          t={translate}
        />
      )}
    </div>
  );
}

/**
 * **REQ-03.sent** — the confirmation.
 *
 * ⚠ **THE ACKNOWLEDGEMENT PANEL IS NOT DRAWN AS SENT, BECAUSE NOTHING SENT
 * ONE.** B19 §11.2 draws an `Acknowledgement email` panel badged *Sent
 * automatically*. The server's own `unavailable` list says why it could not
 * even be QUEUED: notifications' `SOURCE_TYPES` is a constant vocabulary of
 * eight and `service_request` is not one of them, and cross-module writes are
 * forbidden. So the panel prints the SERVER's sentence — *"No acknowledgement
 * has been sent to the applicant and none is waiting to be sent. Tell them
 * yourself if they need confirming."* A badge saying `Sent automatically` over
 * an empty queue is the exact shape of hard-won law 1.
 *
 * ⚠ **AND THE `Nothing is charged` LINE IS NOT PRINTED WHERE A FEE WAS TAKEN —
 * BR-CUS-090 clause (3).** The drawn acknowledgement says *"Nothing is charged
 * and no service changes until we have confirmed what is needed"* directly
 * beneath a panel confirming cash was collected. Customer-facing and provably
 * false at the moment it is sent. Where money was taken the sentence states the
 * amount, the method and the receipt number instead.
 */
export function CaptureConfirmation(props: { detail: ServiceRequestDetail; t: Translate }) {
  const fees = props.detail.fees;
  /**
   * **THE ACKNOWLEDGEMENT PANEL READS THIS REQUEST'S OWN STATE — `DEF-CUS-6418`.**
   *
   * It printed the server's STATIC `acknowledgement_cannot_be_queued` sentence
   * — *"No acknowledgement has been sent to the applicant and none is waiting
   * to be sent"* — on every confirmation. That sentence stopped being true on
   * 2026-09-15 (`DEF-CUS-5389`): `submit` queues the acknowledgement into
   * `outbound_messages` whenever the applicant gave an email, and records WHY
   * when it cannot. So a clerk was told *nothing is waiting* over an email that
   * was waiting. The request carries the real answer in
   * `decision.acknowledgement` and that is what is drawn.
   *
   * B14 rule 33: a FACT at six words, an INSTRUCTION at six a sentence, and no
   * rationale. *"Queued"* and never *"sent"* (`BR-CUS-079`): no delivery adapter
   * exists, and a queued row is what somebody could later send.
   */
  const ack = props.detail.decision?.acknowledgement ?? null;
  const ackQueued = ack?.state === "queued";
  const ackReason = ack?.reason ?? "";

  return (
    <div data-screen="REQ-03.sent">
      <Panel as="section">
        <p className="text-xs uppercase tracking-wide text-neutral-700">
          {props.t("customers.serviceRequest.sent.kicker")}
        </p>
        {/* ⚠ **AN `<h1>`, AND THE BROWSER WALKTHROUGH IS WHY.** This was a `<p>`
            and the walkthrough failed the screen on its own first rule — *"a
            missing/empty main heading (<h1>) — a screen that renders nothing"*.
            It was not nothing: it was the request number, drawn large, with no
            heading in the document at all. Every other screen in this feature
            gets its `<h1>` from `PageHeader`; the confirmation has no page
            header, so it owns its own. Nothing else on the page competes for
            the role — the number IS what this screen is about.
            ⚠ **`text-h2`, NOT AN ARBITRARY SIZE.** B19 §11.2 draws the number
            "very large, in the accent"; the type scale has no exceptions and
            `text-[32px]` is what G34 exists to refuse. `text-h2` already
            carries the heading weight and leading, so no `font-*` rides with
            it — `text-h5`'s own note in tailwind.css warns about that pairing. */}
        <h1 className="text-h2 text-accent" data-request-no={props.detail.header.request_no ?? ""}>
          {props.detail.header.request_no ?? props.t("customers.serviceRequest.number.absent")}
        </h1>
        <p className="max-w-prose text-sm text-neutral-700">
          {props.t("customers.serviceRequest.sent.quoteThisNumber")}
        </p>
      </Panel>

      {/* ══════════════════════════════════════════════════════════════════
          **THE FEE LINES, AS THE SAME TABLE — `DEF-CUS-6411`.** `Form fee` was
          a one-fee summary: a request with two fees read as one. Now the
          lines and their `Total`, then what the counter took.

          ⚠ **EVERY FIGURE CARRIES ITS CURRENCY (`DEF-CUS-6412`).** The
          shortfall sentence printed `0.00 collected of 70.00 quoted · 70.00
          outstanding` — the server's bare 2-dp `display`, with no `$` — while
          `MoneyCell` beside it printed `$0.00`. It interpolates
          `formatMoney(amount, currency)` now, the path `ApplicationFeeLine`
          already takes, so the sentence and the cells cannot disagree.

          ⚠ **`HOW IT WAS PAID` PRINTS THE LABEL (`DEF-CUS-6413`).** It printed
          the stored code, `cash`, where every other screen reads `Cash`.
          ══════════════════════════════════════════════════════════════════ */}
      <Panel as="section">
        <h3>{props.t("customers.serviceRequest.sent.formFee")}</h3>
        <FeeLinesTable
          fees={fees}
          t={props.t}
          collection="sent-fees"
        />
        <div className="mt-4">
        <FieldGrid columns={3}>
          <Field label={props.t("customers.serviceRequest.fees.collected")}>
            <MoneyOrAbsence money={fees.collected} t={props.t} />
          </Field>
          <Field label={props.t("customers.serviceRequest.fees.method")}>
            <span data-sent-method={fees.fee_method ?? ""}>
              <TextOrNotSupplied
                value={
                  fees.fee_method === null || fees.fee_method === ""
                    ? null
                    : props.t(`customers.serviceRequest.feeMethod.${fees.fee_method}`, {
                        defaultValue: fees.fee_method,
                      })
                }
                t={props.t}
              />
            </span>
          </Field>
          <Field label={props.t("customers.serviceRequest.fees.receipt")}>
            <TextOrNotSupplied value={fees.receipt_no} t={props.t} />
          </Field>
        </FieldGrid>
        </div>
        {/* ⚠ BR-CUS-090 — the shortfall sentence, where there is one. */}
        {fees.shortfall_is_open_balance && (
          <p className="max-w-prose text-sm text-neutral-700" data-sent-shortfall="">
            {props.t("customers.serviceRequest.fees.collectedOfQuotedOutstanding", {
              collected: moneyText(fees.collected),
              quoted: moneyText(fees.quoted),
              outstanding: moneyText(fees.outstanding),
            })}
          </p>
        )}
      </Panel>

      {/* ══════════════════════════════════════════════════════════════════
          **`Acknowledgement email` — WHAT HAPPENED TO IT, AND NOTHING ELSE.**

          ⛔ **THE `Nothing is charged…` / `…was taken by cash…` PARAGRAPH IS
          GONE (`DEF-CUS-6414`, B14 rule 33).** Both sentences described what
          the EMAIL tells the applicant (`BR-CUS-090` clause 3, which is
          enforced in the notifications template, not here) — rationale on a
          clerk's screen, 15 and 26 words. The money it restated is in the
          panel above, in figures.
          ══════════════════════════════════════════════════════════════════ */}
      <Panel as="section">
        <h3>{props.t("customers.serviceRequest.sent.acknowledgement")}</h3>
        <p role="note" className="max-w-prose text-sm text-neutral-700" data-ack-state={ack?.state ?? ""}>
          {ackQueued
            ? props.t("customers.serviceRequest.sent.ackQueued")
            : ackReason === "applicant_supplied_no_email_or_phone" ||
                ackReason === "applicant_supplied_no_email_address"
              ? props.t("customers.serviceRequest.sent.ackNoEmail")
              : props.t("customers.serviceRequest.sent.ackNotQueued")}
        </p>
        {!ackQueued && (
          <p className="max-w-prose text-sm text-neutral-700">
            {props.t("customers.serviceRequest.sent.ackTellThem")}
          </p>
        )}
      </Panel>

      {/* B14 rule 33 — each line a FACT of at most six words (`DEF-CUS-6414`).
          They were 10, 16, 17 and 14 words. */}
      <Panel as="section">
        <h3>{props.t("customers.serviceRequest.sent.whatHappensNext")}</h3>
        <ul className="m-0 list-none p-0 text-sm text-text">
          <li className="py-1">{props.t("customers.serviceRequest.sent.next1")}</li>
          <li className="py-1">{props.t("customers.serviceRequest.sent.next2")}</li>
          <li className="py-1">{props.t("customers.serviceRequest.sent.next3")}</li>
          <li className="py-1">{props.t("customers.serviceRequest.sent.next4")}</li>
        </ul>
      </Panel>

      <div className="flex flex-wrap gap-2">
        <ConfirmationActions detail={props.detail} t={props.t} />
      </div>
    </div>
  );
}

function ConfirmationActions(props: { detail: ServiceRequestDetail; t: Translate }) {
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  return (
    <>
      {/* `Print receipt` is NOT drawn: no receipt document exists — payments
          owns the `RCT-` series and this module only RECORDS the number the
          counter wrote on the slip. A print button over nothing is dead UI. */}
      {/* `DEF-CUS-6410` — a bare `/requests/new`. The PAGE decides that a bare
          address is a fresh visit and starts step 1 blank (see
          `ServiceRequestCapturePage`); the button only goes there. */}
      <Button
        variant="secondary"
        onClick={() => navigate(tenantPath(SERVICE_REQUEST_NEW_ROUTE))}
      >
        {props.t("customers.serviceRequest.sent.captureAnother")}
      </Button>
      <Button
        variant="primary"
        onClick={() => navigate(tenantPath(serviceRequestPath(props.detail.header.id)))}
      >
        {props.t("customers.serviceRequest.sent.openTheRequest")}
      </Button>
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W4 task 4.10 · B19 §1–§7 · §11 · BR-CUS-090..095
// generated: 2026-08-24 by the CR-031 W4 FRONTEND lane (M3)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: tsc✔ eslint✔ vitest✔ · G13✔ G31✔ G37✔ G40✔
// exceptions: E3 **the draft cannot be created at form-open** as BR-CUS-093's
//   worked example describes — the create path requires `address_as_given`
//   (step 3) and `applicant_name`; the control is disabled with that reason and
//   the gap is REPORTED as needing a defect row and a backend change ·
//   E3 the footer primary reads the shared `Continue` rather than B19's
//   destination-naming `Connection →` / `Fees →`: `WizardFrame` owns that
//   label for all ten wizards and is not this lane's file. REPORTED ·
//   E3 **no file input** — no route accepts a file for a service request, so
//   the step records WHICH documents were brought and says so · E3 the
//   `2 needed · 1 optional` badge is not drawn: BR-CUS-095 ships the checklist
//   unticked, so the honest fresh-tenant number is zero · E3 `Billing clerk:
//   A. Reed` and `See the customer's view` are not drawn — no payload carries a
//   clerk display name and no route serves an applicant-facing render ·
//   E3 `Print receipt` is not drawn: payments owns the receipt series and this
//   module only records the number
// ── AMENDED 2026-08-25 · lane F-REQ · CR-033 ──────────────
// packet: CR-033 (12-governance/11-change-requests.md) · BR-CUS-094 ·
//   BR-CUS-092 · `_clean_capture`'s `IDENTIFIER_FIELDS`
// change: step 1 mirrors ACC-03 — heading, hint, CUSTOMER CATEGORY (moved from
//   step 2, still fetched from `GET /service-requests/categories`), channel,
//   Full name / Email / Phone, then Date of birth and Government ID as STATED
//   FACTS. `Applying as` is removed and `applicant_kind` is no longer sent.
// gates: tsc✔ eslint --max-warnings 0✔ vitest 20/20 in this file's suite✔
// proved RED first (hard-won law 7), three breaks:
//   (1) `applicant_kind: "person"` put back in `capturePayload` →
//       `expected [ 'channel', 'applicant_kind', …(18) ] to not include
//        'applicant_kind'`;
//   (2) the category dropped from step 1's `validate` → the gate case failed on
//       `Unable to find an accessible element with the role "radio" and name
//        "Agricultural"` — the wizard had advanced to step 2, which is the
//       failure the case exists to catch;
//   (3) the options hardcoded to `Residential · Commercial · Industrial` → four
//       cases red on the same message, proving the fixture's three invented
//       codes can only arrive over the wire.
// exceptions: E3 **DATE OF BIRTH AND GOVERNMENT ID ARE NOT INPUTS**, where
//   ACC-03 collects both: `_clean_capture` refuses `dob`, `date_of_birth` and
//   `gov_id_last4` BY NAME (`IDENTIFIER_FIELDS`) with `BIZ_STATE`. Drawing them
//   would be dead UI (hard-won law 2) over a promise BR-CUS-092(d) forbids ·
//   E3 **ACC-03's OWN CATEGORY LIST IS STALE AND IS NOT COPIED** — ⚠ SUPERSEDED
//   2026-08-26 (DEF-684 closed): it read *"`NewAccountWizard` renders
//   `ACCOUNT_CATEGORIES` — four codes including `government` — which BR-CUS-094
//   superseded on 2026-08-24 … REPORTED; that file is another lane's"*. The
//   report was acted on: the tuple is DELETED and ACC-03, S19, the S14 master
//   modal and S17's filter all read `GET /service-requests/categories` through
//   `customersShared.useAccountCategories`. Nothing is copied still — there is
//   nothing left to copy · E3 the control is a SEGMENTED control, not the PO's word
//   *"drop down"* — their second sentence asked for ACC-03's step 1, and
//   ACC-03's category control is `SegmentedField` · E3 **CR-033 §5 says
//   `A person / A business` should be KEPT below the category**; this lane was
//   directed to replace it and did. REPORTED, and reversing it is re-adding one
//   `SegmentedField` and one payload key · E3 asking the category here does NOT
//   clear the list's `NOT YET CLASSIFIED` — see the trace header
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
