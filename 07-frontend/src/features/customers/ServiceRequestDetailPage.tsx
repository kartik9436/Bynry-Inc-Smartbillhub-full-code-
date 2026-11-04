// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W4 task 4.12 — **S84, the request detail (REQ-02)**, and
//           with it THREE of task 4.13's four unnumbered screens: the
//           **identity match** (Decision tab), the **quote builder** (Fees
//           tab) and **review-and-approve** (Decision tab). Design: B19 §12.2
//           and §12.3, from the PO's screenshots of 2026-08-24.
//           Screens: S84 (B18's proposal; A1 allocates none — **D1** unruled)
// Rules:    BR-CUS-090 (quoted · collected · outstanding — a shortfall is an
//           OPEN BALANCE, never a refusal at the desk and never a silent
//           waiver) · BR-CUS-091 (a customer MAY request a disconnect; the
//           decision panel's old refusal is WITHDRAWN and the control enabled —
//           and a disconnect is still NOT a move-out) · BR-CUS-092 (the
//           identifier is `ID type` + `ID number`, last-four on every read, and
//           it is NOT STORABLE YET — clause (d) keeps *"stored encrypted"* off
//           the screen) · BR-CUS-095 (the tenant checklist; two gates) ·
//           BR-CUS-089 (only a STRONG match may move money) · BR-CUS-070 (the
//           address as given is never overwritten) · BR-SHL-025 · BR-SHL-045
//           (the icon rail) · B14 rules 15 · 20 · 21
// Questions: OQ-355 (the fifth approval condition) · OQ-356 (undrawn verdicts)
//           · OQ-357 (the ⊘ glyph: remove or waive) — ALL OPEN, all rendered
//           as stated refusals carrying their id, none resolved here
// Tests:    07-frontend/src/features/customers/ServiceRequestDetailPage.test.tsx
//           (TC-REQ-6 · TC-REQ-7 · TC-REQ-9 · TC-REQ-10)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE THREE OPEN QUESTIONS ARE RENDERED, NOT RESOLVED.** Each is a
// sentence the SERVER writes into `unavailable`, shown on the control it is
// about (BR-SHL-025) with the row that will close it in `data-tracks`:
//
//   * **OQ-355** — the design prints *"4 of 5 conditions clear"* and only FOUR
//     can be named. The panel prints the server's `total`, which is 4, and says
//     the design shows a fifth nobody can itemise. Printing 5 would claim to
//     have checked something we cannot name.
//   * **OQ-356** — a verdict the drawing never showed is `possible`, offered
//     WITHOUT a recommendation. It is never inverted into a sentence.
//   * **OQ-357** — the `⊘` glyph on a fee row is remove-or-waive and is not
//     determinable from a picture. **Waive is drawn, built and served; remove
//     is not offered at all**, and the reason sits on the row.
//
// ⚠ **AND THE ONE THING THAT LOOKS LIKE A FIELD AND IS NOT.** B19 §12.3 draws
// `ID → •••• ••••• 4471`, `Date of birth → Mar 1988` and `Acting for → Self` on
// the Applicant tab, and the Customer match panel says *"Matched on: ID number
// and date of birth"*. **This schema carries none of the three.** BR-CUS-092
// ruled the identifier CAPTURABLE and made the app-layer encryptor its
// precondition; clause (d) is explicit that a false security promise over a
// government identifier is worse than an absent one. So the rows render as
// STATED ABSENCES with the server's own sentence, and the automatic matcher is
// a disabled control with its reason — a `strong` tier moves a customer's
// deposit (BR-CUS-089), so a tier derived from evidence we do not hold would be
// a money bug wearing a badge.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, isApiError, UNEXPECTED_ERROR_KEY } from "@/api/client";
import { getCharges } from "@/api/endpoints";
import type { ChargeRow } from "@/api/endpoints";
import {
  DocumentStateCell,
  documentFileType,
  documentVerdict,
  formatDocumentSize,
  openDocumentContent,
} from "@/components/documents";
import type { ApiClient } from "@/api/client";
import { Button, ButtonLink } from "@/components/Button";
import { Disclosure, DisclosureList } from "@/components/Disclosure";
import { DatePickerField, FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { canBeRaisedOnItsOwn } from "./NewConnectChargesStep";
import { PageHeader } from "@/components/PageHeader";
import { RequestEditButton } from "./serviceRequestEditDoor";
import { moveRecordPath } from "./MoveRecordPage";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { RefusalStrip } from "@/components/Surfaces";
import { refusalText } from "@/api/refusalText";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { CommitIcon, DownloadIcon, TrashIcon, WaiveIcon } from "@/components/icons";
import { DateCell, formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";
// `DEF-CUS-6109` — the wizard the approve modal's own drawn table sends the
// clerk to next. The ROUTE CONSTANT, never a hand-built string: a hardcoded
// `/connections/new` here is the small finding the Accounts blueprint already
// records against this very file's sibling (*"a route that will not move when
// the constant does"*).
import { NEW_CONNECT_ROUTE } from "./newConnectShared";

// ⚠ **`ACCOUNTS_ROUTE` COMES FROM `customersShared`, NOT FROM
// `AccountsListPage`.** The list page does not export it, and importing it
// from there yielded `undefined` at run time — the back control built
// `/brazosbend/undefined?tab=move-ins` with `tsc` clean and the LABEL correct,
// so only an assertion on the WHOLE address caught it. `toContain` would have
// passed: that is `DEF-CWP-3925`'s shape, one module over.
import { ACCOUNTS_ROUTE, useAccountCategories, useAccountSubtypes } from "./customersShared";
import {
  ACCOUNTS_TAB_IDS,
  ACCOUNTS_TAB_LABEL_KEYS,
  ACCOUNTS_TAB_PARAM,
} from "./AccountsListPage";
import type { AccountsTab } from "./AccountsListPage";

import { ServiceRequestInterruption } from "./ServiceRequestInterruption";

// `DEF-CUS-6350` — the Approve window is its own kit-built component now, and
// `ApproveModal` is no longer mounted here.
import { ApproveChecksModal } from "./ApproveChecksModal";
import { RequestCategoryToSet } from "./RequestCategoryToSet";
import { TemporaryStopApproveModal } from "./TemporaryStopApproveModal";
import { approveTemporaryStop } from "./temporaryStopEndpoints";
import { RequestCustomFieldsDetail } from "./requestCustomFields";
import { RequestCustomerLink } from "./RequestCustomerLink";
import { ServiceRequestJobLink } from "./ServiceRequestJobLink";
// ⚠ **`moveRecordPath` IS NO LONGER IMPORTED HERE (`DEF-CUS-7900`).** The
// approve landing for a move-in stopped being a record address on 2026-09-29;
// the *where it went* line on an already-approved request still builds one and
// it does so inside `ServiceRequestJobLink`, which owns that import. Two
// consumers of one helper, and this file stopped being one of them.
//
// `MOVE_IN_WIZARD_ROUTE` is `moveShared`'s (`/move-ins/new`, the address
// `App.tsx` mounts standalone) and `REQUEST_PARAM` is the wizard's own — the
// ONE spelling of `?request=`, read by `MoveInWizard` and written here, so the
// two cannot drift the way a hand-typed query string would.
import { MOVE_IN_WIZARD_ROUTE } from "./moveShared";
import { REQUEST_PARAM } from "./MoveInWizard";
import {
  AskForMoreModal,
  DecisionButton,
  DecisionOutcomeNote,
  RefuseModal,
} from "./serviceRequestDecisions";
export { APPROVE_SCHEMA, ASK_SCHEMA, REFUSE_SCHEMA } from "./serviceRequestDecisions";
// `DEF-CUS-6376` — `Record what was handed over` is a COMPONENT in its own file
// (B14 rule 43); its two schemas moved with it and are re-exported here.
import { RequestFeeHandoverModal } from "./RequestFeeHandoverModal";
export { COLLECT_SCHEMA, WAIVE_SCHEMA } from "./RequestFeeHandoverModal";

import {
  addServiceRequestNote,
  approveServiceRequest,
  // ⚠ `decideServiceRequestOutcome` is deliberately NOT imported here any more.
  // The Approve dialog sends the outcome WITH the approval in one post
  // (`DEF-CUS-5427`); the endpoint itself stays, because `POST .../decision` is
  // still the Decision tab's own door.
  addServiceRequestFee,
  getServiceRequest,
  linkServiceRequestCustomer,
  setServiceRequestCategory,
  patchServiceRequest,
  parkServiceRequest,
  refuseServiceRequest,
  rejectServiceRequestDocument,
  submitServiceRequest,
  transitionServiceRequest,
  verifyServiceRequestDocument,
} from "./serviceRequestEndpoints";
import type {
  ApplicantMessage,
  ServiceRequestDetail,
  ServiceRequestJob,
} from "./serviceRequestEndpoints";
import {
  ApplicationFeeAdder,
  ApplicationFeeLine,
  billingAddressLine,
  chargeCodeOptions,
  composeAddressLine,
  streetWithUnit,
  FeeLinesTable,
  moneyText,
  CatalogueSentence,
  Dash,
  DateOrNotSupplied,
  DrawnRow,
  DrawnSection,
  MoneyOrAbsence,
  RequestHeadChip,
  RequestNumber,
  RequestStatePill,
  EventWhat,
  RequestedServicesTable,
  SERVICE_REQUESTS_ROUTE,
  TextOrDash,
  TextOrNotSupplied,
  WhatItProves,
  maskLastFour,
} from "./serviceRequestShared";

/**
 * **THE THREE TABS THE BLUEPRINT DRAWS** — `Applicant · Documents · History`,
 * read off p082 as an image (B14 rule 42). `?tab=` keeps each deep-linkable
 * (BR-SHL-011).
 *
 * ⚠ **THE CODE HAD SIX AND THE DRAWING DRAWS THREE, AND WHETHER IT IS SIX OR
 * THREE IS OPEN WITH THE PRODUCT OWNER.** So the tab STRIP is the drawing's and
 * **not one live door was deleted to get there** — an open question may not be
 * resolved by choosing a value, least of all the destructive one. `Location &
 * services`, `Fees` and `Decision` did not lose their contents; each moved onto
 * the block the drawing puts it in:
 *
 *   * Location → `THE ADDRESS THEY GAVE` and `WHAT THEY ASKED FOR`, plus the
 *     interruption section, all on the Applicant tab;
 *   * Fees → the drawn `FEES` panel, keeping `Record what was handed over` and
 *     the per-line waive inside the disclosure;
 *   * Decision → **the three head modals**, which is the PO's own ruling:
 *     *"`Decide what this is` … becomes the Approve modal"*.
 *
 * If the answer comes back *six*, the strip grows again and nothing has to be
 * rebuilt. If it comes back *three*, it already is three.
 */
export const REQUEST_TABS = ["applicant", "documents", "history"] as const;
export type RequestTab = (typeof REQUEST_TABS)[number];

export function requestTabFromParam(raw: string | null): RequestTab {
  return (REQUEST_TABS as readonly string[]).includes(raw ?? "")
    ? (raw as RequestTab)
    : "applicant";
}

export function serviceRequestDetailKey(requestId: string): readonly unknown[] {
  return ["service-request", requestId];
}

type Translate = (key: string, params?: Record<string, unknown>) => string;

// ══════════════════════════════════════════════════════════════════════════
// THE THREE FORM SCHEMAS — each MIRRORS a server rule rather than inventing one
// ══════════════════════════════════════════════════════════════════════════

/** `Park this — what are you waiting for?` — `waiting_on` is required, the note
 *  and the reminder are not. The server refuses a blank with
 *  `customers.serviceRequest.waitingOnRequired`; this asks first. */
export const PARK_SCHEMA = z.object({
  waiting_on: z.string().trim().min(1),
  note: z.string().optional(),
  remind_on: z.string().optional(),
});

/** ⚠ **`REFUSE_SCHEMA` MOVED TO `serviceRequestDecisions.tsx` AND CHANGED
 *  SHAPE (`CR-094-BRC01` wave 2).** TC-REQ-9 — *a refusal with no reason is
 *  refused* — still holds and is still asserted at the control rather than at
 *  the server; what moved is WHICH field carries it. The blueprint's `Reason *`
 *  is the coded one of five (p084), and the free-text sentence is `What to tell
 *  them`, which goes to the applicant. It is re-exported above so every caller
 *  and every test keeps one import path.
 */

/** CR-070 wave P — the *Route* modal has no typed fields; see its own comment. */
export const ROUTE_SCHEMA = z.object({});

/** ⚠ **`COLLECT_SCHEMA` AND `WAIVE_SCHEMA` MOVED TO `RequestFeeHandoverModal.tsx`
 *  WITH THE MODAL THEY VALIDATE (`DEF-CUS-6376`, B14 rule 43)** — unchanged,
 *  and re-exported above so every caller and every test keeps one import path. */

// ══════════════════════════════════════════════════════════════════════════
// THE APPLICANT TAB, REBUILT TO ITS DRAWING — accounts blueprint p082–p083
// ══════════════════════════════════════════════════════════════════════════
//
// Read AS IMAGES at scale 2 (B14 rule 42; the PO asked for this four times on
// 2026-09-15 — *"I want you to use images only to create screens - do not use
// text or content ot create product screens"*). The drawing lays the tab out in
// TWO COLUMNS and gives each block a heading:
//
//     WHAT THEY ASKED FOR          DOCUMENTS · 4
//     WHO IS ASKING                FEES
//     THE ADDRESS THEY GAVE        HISTORY
//
// ⚠ **THE DRAWN NUMBERS ARE ILLUSTRATIONS (B14 rule 37).** `PR-0731`,
// `U-001884`, `$130.00`, `$105.00`, `6 units` are examples of a SHAPE. Ours
// read `P-00052` and `SCW-U-207`, and every figure comes from the payload.
//
// ⚠ **`Matched premises` AND `Matched unit` CLOSE `DEF-CUS-5386`.** The tab used
// to print `RESOLVED TO 01a0a444-5ad2-7e88-be8a-bdb8aa86c05e` at a clerk —
// a raw premises UUID as the visible value of a field, which B14 rule 31
// forbids in the PO's own words (*"no Databse ID on screen - that is a rule"*).
// It names the record now and the id rides on `title=`, which is `DEF-2716`'s
// proved fix. **The fallback ladder is part of the fix and is not decoration:**
// `premises.premise_no` and `units.unit_no` are both NULLABLE, so a tenant that
// never turned its numbering series on has an id and no number. Fall back to
// the premises' own address, then to a stated absence — **never to the id**,
// which is the defect coming straight back.
//
// ⚠ **THE ADDRESS LINE IS COMPOSED HERE AND NOT ON THE SERVER**, because the
// blueprint punctuates the same line two ways on two frames — `Austin TX 78704`
// on p083, `Austin, TX 78704` on p082 — so the punctuation is an illustration
// and choosing between two drawings is not a server's job (wave 1 lane B's §2
// rule 4). `premise_locality` is the PREMISES' town, never the applicant's.

/** `212 Balcones Drive · Unit 3 · Austin, TX 78704` — MOVED to
 *  `serviceRequestShared` on 2026-09-23 so the capture review writes a billing
 *  address the way this page does (`DEF-CUS-6408`); re-exported for the tests
 *  and callers that import it from here. */
export { composeAddressLine };

/**
 * A matched record, NAMED. `title` carries the internal id for support, which
 * is `DEF-2716`'s proved fix and B14 rule 31's own sentence — the id is never
 * the VISIBLE VALUE.
 */
export function MatchedRecord(props: {
  number: string | null;
  fallback: string | null;
  internalId: string | null;
  match: string | null;
  t: Translate;
}) {
  const word =
    props.match === null || props.match === ""
      ? ""
      : ` · ${props.t(`customers.serviceRequest.resolvedMatch.${props.match}`)}`;
  if (props.number !== null && props.number !== "") {
    return (
      <span title={props.internalId ?? undefined} data-matched="number">
        {props.number}
        {word}
      </span>
    );
  }
  if (props.fallback !== null && props.fallback !== "") {
    return (
      <span title={props.internalId ?? undefined} data-matched="address">
        {props.fallback}
        {word}
      </span>
    );
  }
  return (
    <span className="text-neutral-700" data-matched="none">
      {props.t("customers.serviceRequest.address.notMatched")}
    </span>
  );
}

/**
 * `Asked for` — the drawing's first left-column section (p082).
 *
 * ⚠ **REBUILT AS THE DRAWN DEFINITION LIST ON 2026-09-19.** It was a `Panel` of
 * two-across `Field`s — a grey card with labels above values. The PO put it
 * beside the drawing and ruled: *"we have to match drawing here - Drawing:
 * label left, value right, a hairline between rows, no box."*
 */
export function AskedForBlock(props: {
  detail: ServiceRequestDetail;
  t: Translate;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const loc = props.detail.location_and_services;
  const header = props.detail.header;
  /* ⛔ **THE `Electric · Water` RUN-ON LINE IS GONE — PO report 2026-09-22,
     rows 14/15.** It joined the service names into one sentence for a flat
     row; the three services now sit in `RequestedServicesTable` with their own
     requested start and connection date beside them. The derivation stayed
     behind for a few hours, assigned and read by nothing, which is dead code
     of exactly the kind a lane later "wires back up". */
  return (
    <DrawnSection title={props.t("customers.serviceRequest.asked.title")} name="what-they-asked-for">
      <DrawnRow label={props.t("customers.serviceRequest.asked.type")} testId="type">
        {props.t(`customers.serviceRequest.type.${header.classification}`, {
          defaultValue: props.t("customers.serviceRequest.type.notYetClassified"),
        })}
      </DrawnRow>
      <DrawnRow label={props.t("customers.serviceRequest.asked.subCategory")} testId="sub-category">
        {loc.property_type === null ? (
          <Dash />
        ) : (
          props.t(`customers.serviceRequest.propertyType.${loc.property_type}`)
        )}
      </DrawnRow>
      {/* ══════════════════════════════════════════════════════════════════
          **THREE ROWS BECOME ONE TABLE — PO report 2026-09-22, rows 14, 15
          and 12.**

          What was here, and what each could not say:

            · `Services requested · Water · Sewer · Trash` — a list of words
              with no dates on it;
            · `Requested start · 22-Sep-26, all 3` — one date and a claim that
              they agree, which can state the AGREEMENT and can never show one
              service starting on a different day from another;
            · `Units on site · 6` — **REMOVED** (row 12). It was the
              APPLICANT'S CLAIM about how many units are on the property, asked
              on New request step 3 and printed here, and the PO took both.

          ⚠ **EXACTLY THREE COLUMNS, AND THAT IS A RULING.** PO 2026-09-22,
          verbatim *"dont add these"*, refusing a proposed size/meter-size
          column, a charge column and a per-service status. The decision-log
          entry is titled *THE NEW REQUEST REVIEW TABLE IS THREE COLUMNS* and
          its consequence clause is explicit: no placeholder column, no hidden
          column, **and no commented-out one** — *"a column that exists and is
          empty is the thing this ruling is against, and a commented-out column
          is a promise nobody is keeping"*.

          ⚠ **ONE COMPONENT, MOUNTED TWICE (B14 rule 43).** The same table is
          step 6's review block on `REQ-03`. `RequestedServicesTable` is the
          component; neither screen writes the markup.

          ⚠ **`requested_start_agreement` IS STILL SERVED AND IS NOW READ BY
          NO SCREEN, WHICH IS SAID OUT LOUD RATHER THAN LEFT TO BE FOUND.**
          This comment claimed the capture review still rendered it through
          `RequestedStart`; **that was false within the hour**, because the
          capture review moved to this same table — and the component then sat
          exported and mounted by nobody until `G13` named it. It is deleted;
          see the block above `RequestedServicesTable`'s neighbours for what it
          knew and where that knowledge lives. The FIELD stays on the payload:
          it is a fact the server derives once so two screens cannot decide it
          differently, and dropping a served field is a contract change this
          report did not ask for.
          ══════════════════════════════════════════════════════════════════ */}
      <div className="py-2.5" data-drawn-row="services">
        <RequestedServicesTable
          services={loc.services}
          connectionDate={header.requested_start}
          t={props.t}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          testId="asked-for"
        />
      </div>
      {/* Three facts the product captures that this frame predates. They are
          KEPT AND HIDDEN WHEN EMPTY (decision log, 2026-09-19 open list), so a
          request carrying none of them reads exactly as the drawing draws it
          and one that carries a plot number does not lose it off a screen. */}
      <DrawnRow
        label={props.t("customers.serviceRequest.decision.whatTheySaid")}
        testId="what-they-said"
        hideWhenEmpty
        empty={!props.detail.decision.what_they_said}
      >
        <TextOrDash value={props.detail.decision.what_they_said} />
      </DrawnRow>
      <DrawnRow
        label={props.t("customers.serviceRequest.location.whatIsBeingBuilt")}
        testId="being-built"
        hideWhenEmpty
        empty={!loc.what_is_being_built}
      >
        <TextOrDash value={loc.what_is_being_built} />
      </DrawnRow>
      <DrawnRow
        label={props.t("customers.serviceRequest.location.plot")}
        testId="plot"
        hideWhenEmpty
        empty={!loc.plot_or_parcel}
      >
        <TextOrDash value={loc.plot_or_parcel} />
      </DrawnRow>
    </DrawnSection>
  );
}

/*
 * ⛔ **`RequestedStart` IS DELETED — PO report 2026-09-22, rows 14 and 15,
 * and `G13` is what found it.**
 *
 * It rendered `requested_start_agreement` as one sentence — *"22-Sep-26, all
 * three"* or *"Different days per service."* — for the flat `Requested start`
 * row that the PO replaced with `RequestedServicesTable`. When that row went,
 * its last production caller went with it, and the component sat exported,
 * tested and mounted by NOBODY. That is hard-won law 2, and this lane created
 * it: the commit that removed the row left a comment claiming the capture
 * review still used it, and the capture review had moved to the table too.
 * **A comment claiming a caller is not a caller** (law 1). `G13` said so —
 * *"renders behind `props.agreement` but no caller passes it"* — and this is
 * that finding acted on rather than baselined.
 *
 * ⚠ **WHAT IT KNEW, AND WHERE THAT KNOWLEDGE LIVES NOW — `DEF-CUS-5902`.**
 * The component branched on `agreed === null && count > 1` and did not read
 * `unset`, so a request where the clerk typed ONE date and no service carried
 * one of its own printed *"Different days per service."* over a request where
 * nothing varied. A clerk would have told an applicant something false. **The
 * distinction is the SERVER's and is untouched:**
 * `_requested_start_agreement` in `service_request_reads` says it in its own
 * docstring — `unset == count` is *nobody gave a date*, `unset == 0` with a
 * null `agreed` is *they disagree* — and `requested_start_agreement` is still
 * served on every request.
 *
 * ⚠ **AND THE TABLE THAT REPLACED IT CANNOT MAKE THAT MISTAKE**, which is why
 * the component is not worth keeping for the sake of the lesson: it prints the
 * per-service dates THEMSELVES, one row each, so there is no sentence to get
 * wrong. `BR-CUS-1070`'s rule that neither date falls back to the other is
 * written into `RequestedServicesTable`'s own docstring, which is where the
 * next lane will meet it.
 *
 * ⚠ **NO SCREEN READS `requested_start_agreement` TODAY.** The field stays on
 * the payload — it is a derived FACT the server owns and a later screen may
 * want, and removing a served field is a contract change this report did not
 * ask for. Said out loud rather than left for somebody to discover.
 */

/**
 * `Their address` — the drawing's third left-column section (p083).
 *
 * ⚠ **THE PROSE UNDER IT IS GONE.** The drawing prints *"What they typed is
 * kept beside what we matched, never replaced by it. The resolver is evidence;
 * if the two ever disagree, the clerk can see both."* — twenty-six words
 * explaining WHY the screen is built this way. That is RATIONALE, and B14 rule
 * 33 gives rationale **zero words on screen**; it belongs in a docstring, so it
 * is in this one. The two rows still sit one above the other, which is the part
 * of that sentence a clerk can actually use.
 */
/** `PO Box 4417, Apt 2, Ottumwa, IA 52501` — one line, the envelope's order. */
function mailingAddressLine(
  address: NonNullable<ServiceRequestDetail["applicant"]["application_mailing_address"]> | null | undefined,
): string | null {
  if (!address) return null;
  const stateZip = [address.state, address.postal_code].filter(Boolean).join(" ");
  return [address.line1, address.line2, [address.city, stateZip].filter(Boolean).join(", ")]
    .filter((part) => part !== null && part !== undefined && part !== "")
    .join(", ");
}

export function AddressBlock(props: { detail: ServiceRequestDetail; t: Translate }) {
  const loc = props.detail.location_and_services;
  // ⚠ **THE STREET AND THE UNIT, BOTH — `DEF-CUS-9042`.** This read
  // `address_unit_as_given ?? address_as_given`, and `??` PREFERS the unit, so
  // an applicant who typed `400 Heron Court` and `Unit 2` was shown as having
  // said `Unit 2`. The head was fixed for the identical expression on
  // 2026-09-22 (PO report row 13); this was the second copy of it.
  // A unit line a clerk composed WITH the street in it (`3450 Oak Ridge Dr ·
  // Unit 1`, the seeded shape) is printed as it is rather than twice.
  const street = (loc.address_as_given ?? "").trim();
  const unitWords = (loc.address_unit_as_given ?? "").trim();
  const asGiven = composeAddressLine(
    unitWords === ""
      ? street || null
      : street === "" || unitWords.startsWith(street)
        ? unitWords
        : `${street}, ${unitWords}`,
    // ⊕ `DEF-CWP-9817` — the town, state and ZIP the applicant GAVE
    // (`BR-CUS-1091`), which the portal now sends as well as the counter. This
    // passed `null` and so printed the street alone, dropping two of the three
    // parts the applicant typed. Still what they SAID, never the premises.
    {
      city: loc.address_city_as_given ?? null,
      state: loc.address_state_as_given ?? null,
      postal_code: loc.address_postal_code_as_given ?? null,
    },
  );
  const serviceAddress = composeAddressLine(
    loc.resolved_premise_address ?? loc.address_as_given,
    loc.premise_locality,
  );
  const billingLine = billingAddressLine({
    line1: loc.billing_line1_as_given,
    line2: loc.billing_line2_as_given,
    city: loc.billing_city_as_given,
    state: loc.billing_state_as_given,
    postal_code: loc.billing_postal_code_as_given,
    legacy: loc.billing_address_as_given,
  });
  return (
    <DrawnSection title={props.t("customers.serviceRequest.address.title")} name="the-address-they-gave">
      {/* BR-CUS-070 / TC-REQ-6 — byte-identical to submission, never
          overwritten by the resolver. */}
      <DrawnRow label={props.t("customers.serviceRequest.location.asGiven")} testId="as-given">
        <TextOrDash value={asGiven} />
      </DrawnRow>
      <DrawnRow label={props.t("customers.serviceRequest.address.serviceAddress")} testId="service-address">
        <TextOrDash value={serviceAddress} />
      </DrawnRow>
      <DrawnRow label={props.t("customers.serviceRequest.address.matchedPremises")} testId="matched-premises">
        <MatchedRecord
          number={loc.resolved_premises_no}
          fallback={loc.resolved_premise_address}
          internalId={loc.resolved_premises_id}
          match={loc.resolved_match}
          t={props.t}
        />
      </DrawnRow>
      <DrawnRow label={props.t("customers.serviceRequest.address.matchedUnit")} testId="matched-unit">
        <MatchedRecord
          number={loc.resolved_unit_no}
          fallback={null}
          internalId={loc.resolved_unit_id}
          match={loc.resolved_match}
          t={props.t}
        />
      </DrawnRow>
      {/* ✅ **WHERE THE BILL GOES, FROM ITS PARTS — `DEF-CUS-6408`.** A request
          captured since 2026-09-23 carries line 1, the unit, city, state and
          ZIP; an older one carries the one free-text box, shown exactly as
          typed and never parsed. `billingAddressLine` writes both the way the
          capture review does. */}
      <DrawnRow
        label={props.t("customers.serviceRequest.location.billingAddress")}
        testId="billing-address"
        hideWhenEmpty
        empty={!loc.billing_address_same && billingLine === null}
      >
        {loc.billing_address_same ? (
          props.t("customers.serviceRequest.location.billingSame")
        ) : (
          <TextOrDash value={billingLine} />
        )}
      </DrawnRow>
      <DrawnRow label={props.t("customers.serviceRequest.address.whatWeFound")} testId="what-we-found">
        {/* ⛔ `DEF-CUS-5010` — the column holds a catalogue KEY by design, so
            it is resolved and never printed raw. */}
        <CatalogueSentence value={loc.lookup_found} t={props.t} />
      </DrawnRow>
    </DrawnSection>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// WHO IS ASKING — one drawn section, and three cards fewer than yesterday
//
// ⚠⚠ **REBUILT 2026-09-19 ON THE PO's RULING** (*"we have to match drawing here
// - Drawing: label left, value right, a hairline between rows, no box"*). What
// left this block, each on the approved removal list rather than by taste:
//
//   * **the `Acting for` row** — a stated absence over a field with no column,
//     no vocabulary and no ruling behind it;
//   * **the Co-applicant CARD** — folded in as three rows, hidden when empty,
//     with its `Optional · contact only` badge gone (that is RATIONALE, and
//     B14 rule 33 gives rationale zero words on screen);
//   * **the Customer match CARD and its three sentences** — the matcher-absent
//     note, the may-move-money sentence and the tier/basis pair become ONE row;
//   * **`Record that I searched`** — MOVED, never deleted. See below.
//
// ⚠⚠⚠ **THE BUTTON THAT WOULD HAVE BROKEN EVERY APPROVAL IN THE PRODUCT.**
// `Record that I searched` is the only control anywhere that sets `search_done`,
// and `arrears_condition(search_done=False, …)` returns `CONDITION_BLOCKED` with
// `blocking=True`. Deleting it with the card it sat in would have refused the
// Approve press on **every request in the product**, silently, with `tsc` and
// every suite green — no test asserts that a request can be approved at all.
// It lives in the Approve dialog now, which is where p084 already puts
// conditions: the clerk clears it in the moment they are deciding.
// ⚠ 2026-10-11 (PO, option B): it is now *No match* inside *Search customer*
// (`RequestCustomerLink`), offered after a search answers; the Arrears row
// points there. Same write (`customer_id: null`), one place.
// `serviceRequestDecisions.tsx` carries the other half, and
// `ServiceRequestDetailPage.dom.test.tsx` has a case that goes RED if either
// end of it is removed without a replacement.
// ══════════════════════════════════════════════════════════════════════════

export function WhoIsAskingBlock(props: {
  detail: ServiceRequestDetail;
  t: Translate;
  // The date of birth is a CALENDAR date, so `DateCell` formats it from the
  // string itself and never through a zone — running a birthday through an
  // offset is how one moves by a day. The tenant's regional format still
  // decides how it reads (BR-SHL-023, one formatting path).
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { applicant } = props.detail;
  const match = applicant.customer_match;
  const matched = match.customer_id !== null || match.confirmed_at !== null;
  const co = applicant.co_applicant;

  return (
    <DrawnSection title={props.t("customers.serviceRequest.applicant.whoIsAsking")} name="who-is-asking">
      {/* ⚠ **HIDDEN WHEN NULL RATHER THAN SHOWN AS AN ABSENCE (CR-033).** The
          capture form STOPPED ASKING person-or-business — the PO replaced that
          control with the customer category. The column and the payload field
          stay. But a dash here would say *they did not tell us* about a request
          that was never asked, and hard-won law 1 forbids the screen from
          making a claim the data does not support. The old copy said so in
          eleven words; the row simply not being there says it in none. */}
      <DrawnRow
        label={props.t("customers.serviceRequest.asked.applyingAs")}
        testId="applying-as"
        hideWhenEmpty
        empty={applicant.person_or_company === null}
      >
        {applicant.person_or_company === null
          ? null
          : props.t(`customers.serviceRequest.applicantKind.${applicant.person_or_company}`)}
      </DrawnRow>
      {/* ⚠ **THE SECOND AXIS — RESTORED, `DEF-CUS-5903`.** The clerk is REQUIRED
          to pick this on capture step 2, the server has stored it since W4 and
          serves it here, and **no tab rendered it**: a value a clerk types,
          the product keeps, and nobody can read back — so it cannot be
          checked, corrected, or quoted when the applicant asks.

          ⚠ **THIS IS THE SECOND TIME.** The read was added on 2026-08-25
          exactly because the column was a live write with no read, and the
          2026-09-19 Applicant-tab rebuild dropped the row again. Found by a
          clerk walk in a browser; no check here could see it, because a row
          that is simply absent fails nothing.

          It sits beside `Applying as` because B19 §14.3 settles that these are
          the two axes of ONE question — the legal person, and what the account
          is priced as. Hidden when the clerk has not reached step 2, which is
          not an absence worth stating: they are simply not there yet. The NAME
          is printed and never the id (B14 rule 31).

          ⚠ It reuses the CAPTURE form's key rather than minting a new one:
          the clerk should read the same two words where they typed it and
          where they read it back, and all eleven catalogues already carry it
          in their own language (B14 rule 35). */}
      <DrawnRow
        label={props.t("customers.serviceRequest.capture.category")}
        testId="customer-category"
        hideWhenEmpty
        empty={
          props.detail.applicant.customer_category?.account_type == null
        }
      >
        <TextOrDash
          value={
            props.detail.applicant.customer_category?.account_subtype?.name
              ? `${props.detail.applicant.customer_category.account_type?.name} · ${props.detail.applicant.customer_category.account_subtype.name}`
              : (props.detail.applicant.customer_category?.account_type?.name ?? null)
          }
        />
      </DrawnRow>
      <DrawnRow label={props.t("customers.serviceRequest.applicant.name")} testId="applicant-name">
        <TextOrDash value={applicant.name} />
      </DrawnRow>
      <DrawnRow label={props.t("customers.serviceRequest.applicant.email")} testId="applicant-email">
        <TextOrDash value={applicant.email} />
      </DrawnRow>
      <DrawnRow label={props.t("customers.serviceRequest.applicant.phone")} testId="applicant-phone">
        <TextOrDash value={applicant.phone} />
      </DrawnRow>
      {/* ⊕ **`DEF-CWP-9163` — WHERE THE APPLICANT ASKED FOR THE BILL TO GO.**
          Typed on the portal's *Mailing address, if different* and read from
          the application, where it is stored once. Hidden when there is none:
          the bill then goes to the service address. Opening the account from
          this request carries it as the account's mailing address. */}
      <DrawnRow
        label={props.t("customers.account.field.mailingAddress")}
        testId="application-mailing-address"
        hideWhenEmpty
        empty={!applicant.application_mailing_address}
      >
        {mailingAddressLine(applicant.application_mailing_address)}
      </DrawnRow>
      <DrawnRow label={props.t("customers.serviceRequest.asked.channel")} testId="channel">
        {props.detail.header.channel === null || props.detail.header.channel === "" ? (
          <Dash />
        ) : (
          props.t(`customers.serviceRequest.channel.${props.detail.header.channel}`, {
            defaultValue: props.detail.header.channel,
          })
        )}
      </DrawnRow>
      <DrawnRow
        label={props.t("customers.serviceRequest.applicant.language")}
        testId="language"
        hideWhenEmpty
        empty={!applicant.language}
      >
        <TextOrDash value={applicant.language} />
      </DrawnRow>

      {/* ✅ **THE IDENTIFIERS — BR-CUS-092(c)/(d) and (a).**
          ⚠ **THE SCREEN MASKS NOTHING — IT RENDERS WHAT IT WAS GIVEN.**
          `ssn_last4` is four characters produced by `crypto.last_four()` on the
          server. The full number is not on this page, not in the JSON behind
          it, and not in any log or HAR taken from this session. A screen that
          masked a full value it had been handed would be one `JSON.stringify`
          away from disclosing it. Both rows hide when the request carries no
          such identifier, so an absence is not six lines of nothing. */}
      {/* ⊕ `DEF-CUS-10054` (PO 2026-10-11) — both identifier rows ALWAYS
          drawn, masked to the last four when on file and a dash when not; they
          were hidden when empty, so a clerk could not tell "none given" from
          "not shown here". */}
      <DrawnRow
        label={props.t("customers.serviceRequest.capture.ssn")}
        testId="ssn"
        empty={!applicant.identifier.ssn_present}
      >
        {/* ⛔ **`· stored encrypted` IS OFF THE SCREEN — `DEF-CUS-6414`.** This
            note used to keep it as *"a fact about this row … two words, well
            inside rule 33's six"*. The count was right and the KIND was not:
            it tells a clerk WHY the product shows four digits, which is
            RATIONALE, and B14 rule 33 puts rationale at ZERO words on screen.
            The mask is the fact. `stored_encrypted` is still served and still
            true — BR-CUS-092(d) — and nothing here claims otherwise. */}
        {applicant.identifier.ssn_present && applicant.identifier.ssn_last4 ? (
          `••• ••• • ${applicant.identifier.ssn_last4}`
        ) : (
          <TextOrDash value={null} />
        )}
      </DrawnRow>
      <DrawnRow
        label={props.t("customers.serviceRequest.applicant.driversLicence")}
        testId="drivers-licence"
        empty={!applicant.identifier.drivers_licence_present}
      >
        {applicant.identifier.drivers_licence_present && applicant.identifier.drivers_licence_last4 ? (
          `•••• ${applicant.identifier.drivers_licence_last4}`
        ) : (
          <TextOrDash value={null} />
        )}
      </DrawnRow>
      {/* ⊕ **`DEF-CWP-9045` — THE TAX ID A BUSINESS TYPED ONLINE.** Ruled
          `OQ-CWP-1560` (b): stored once on the application and READ from
          there. The server projects the last four; the number is not in the
          payload. Hidden when there is none, like the two rows above. */}
      <DrawnRow
        label={props.t("customers.newAccount.field.taxId")}
        testId="tax-id"
        hideWhenEmpty
        empty={applicant.identifier.tax_id_present !== true}
      >
        {`•••• ${applicant.identifier.tax_id_last4 ?? ""}`}
      </DrawnRow>
      {/* Served in full and not masked: `BR-CUS-1020` — `BR-CUS-092` names two
          identifiers and a date of birth is not one of them. */}
      <DrawnRow
        label={props.t("customers.serviceRequest.applicant.dateOfBirth")}
        testId="date-of-birth"
        hideWhenEmpty
        empty={!applicant.date_of_birth}
      >
        {applicant.date_of_birth === null || applicant.date_of_birth === "" ? null : (
          <DateCell
            value={applicant.date_of_birth}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        )}
      </DrawnRow>

      {/* ── THE CO-APPLICANT, FOLDED IN (PO ruling 2026-09-19) ─────────────
          A whole card, a heading and a badge for three optional contact
          details. They are three rows, and a request without a co-applicant
          now draws nothing at all instead of three dashes under a heading. */}
      <DrawnRow
        label={props.t("customers.serviceRequest.applicant.coApplicant")}
        testId="co-applicant"
        hideWhenEmpty
        empty={!co.name}
      >
        <TextOrDash value={co.name} />
      </DrawnRow>
      <DrawnRow
        label={props.t("customers.serviceRequest.applicant.coApplicantPhone")}
        testId="co-applicant-phone"
        hideWhenEmpty
        empty={!co.phone}
      >
        <TextOrDash value={co.phone} />
      </DrawnRow>
      <DrawnRow
        label={props.t("customers.serviceRequest.applicant.coApplicantEmail")}
        testId="co-applicant-email"
        hideWhenEmpty
        empty={!co.email}
      >
        <TextOrDash value={co.email} />
      </DrawnRow>

      {/* ── THE CUSTOMER MATCH, IN ONE ROW ─────────────────────────────────
          ⚠ **`may_move_money` IS THE SERVER'S BOOLEAN AND IS NOT DERIVED HERE**
          (`BR-CUS-089`, *"Only a strong match may move money"*). A screen
          re-deriving it from the tier string would be a second copy of a rule,
          free to drift the day a fourth tier arrives — which is the defect
          `DEF-CUS-5874` records one module over, on this same day. */}
      <DrawnRow
        label={props.t("customers.serviceRequest.match.title")}
        testId="customer-match"
      >
        {matched ? (
          <span data-may-move-money={String(match.may_move_money)}>
            {/* ⊕ **`DEF-CUS-9043` — WHO, FIRST.** This row printed tier and
                basis only, so after *Record that I searched* it was EMPTY and
                after a link it named nobody. The number is the tenant's own
                series and the name is the customer's; the id never renders. */}
            {[
              match.customer_id !== null
                ? [match.customer_no, match.display_name].filter((part) => part).join(" · ")
                : props.t("customers.serviceRequest.match.noneOnFile"),
              match.tier,
              match.basis,
            ]
              .filter((part) => part)
              .join(" · ")}
            {match.may_move_money
              ? ` · ${props.t("customers.serviceRequest.match.balanceMayCarry")}`
              : ""}
          </span>
        ) : (
          <span data-may-move-money="false">
            {props.t("customers.serviceRequest.match.notSearched")}
          </span>
        )}
      </DrawnRow>
    </DrawnSection>
  );
}

// ⚠⚠ **`DocumentsSummary` AND `HistorySummary` WERE DELETED HERE ON
// 2026-09-19, NOT UNMOUNTED.** They drew the drawing's own right rail — the
// documents table (p082) and the history table (p083) — and the PO ruled both
// off this tab: *"we should have these detials in document tab"* and *"all
// histroy details on appplicant tab should move to history"*. Both tabs already
// draw the full table, so these were the SECOND copy of each.
//
// **Deleted rather than left in the file**, because a component nothing mounts
// is dead UI (hard-won law 2) and an unused one sitting here is the thing a
// later lane "fixes" by putting the call back — which would restore a divergence
// the PO ruled on. The rail now holds `FeesBlock` alone.

/** The drawing's two-column Applicant tab, assembled. */
export function ApplicantTab(props: {
  detail: ServiceRequestDetail;
  t: Translate;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  working: boolean;
  onWaive: (feeId: string) => void;
  onCollect: () => void;
  feeCodes: readonly ChargeRow[];
  pickedFeeCode: string;
  onPickFeeCode: (code: string) => void;
  onAddFee: () => void;
  feeAddRefusal: string | null;
  feeCatalogueAnswered: boolean;
  /** CR-068 wave B — the request id the Interruption section reads. Optional so
   *  every existing test of this tab keeps working and simply draws no
   *  section, which is also what a request about no interruption draws. */
  requestId?: string;
  client?: ApiClient;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-2" data-tab-body="applicant">
      <div className="flex min-w-0 flex-col gap-8">
        <AskedForBlock
          detail={props.detail}
          t={props.t}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
        <WhoIsAskingBlock
          detail={props.detail}
          t={props.t}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
        <AddressBlock detail={props.detail} t={props.t} />
        {/* ⊕ `CR-161-BRC10` W6, gap 2 — the request's OWN COPY of every
            answer typed on Staff New Request, read-only, so the reviewer sees
            what was asked for before approving. Nothing without fields. */}
        <RequestCustomFieldsDetail
          data={props.detail.custom_data}
          formatDate={(iso) => formatDate(iso, props.timeZone, props.dateFormat)}
          client={props.client}
        />
        {/* CR-068 wave B — ABSENT unless this request is about an interruption
            (US-CWP-008 TC-1). It sits with the address because an interruption
            is a PLACE: the stretch of street, and the premises on it. */}
        {props.requestId === undefined ? null : (
          <ServiceRequestInterruption requestId={props.requestId} client={props.client} />
        )}
      </div>
      {/* ⚠⚠ **THE RIGHT RAIL IS FEES AND NOTHING ELSE, AND THAT IS A
          DELIBERATE DIVERGENCE FROM THE DRAWING.** p082–p083 put the documents
          table AND the history table in this rail. The PO ruled both out of
          this tab on 2026-09-19 — *"we should have these detials in document
          tab"* and *"all histroy details on appplicant tab should move to
          history"* — and a PO instruction supersedes a drawing; the drawing
          does not supersede the PO. Recorded here so the next lane meets the
          divergence rather than "correcting" it back.

          `DocumentsSummary` and `HistorySummary` are DELETED rather than left
          unrendered: a component nothing mounts is dead UI, and one left in the
          file is one the next lane restores by putting the call back. */}
      <div className="flex min-w-0 flex-col gap-6">
        <FeesBlock
          detail={props.detail}
          t={props.t}
          working={props.working}
          onWaive={props.onWaive}
          onCollect={props.onCollect}
          feeCodes={props.feeCodes}
          pickedFeeCode={props.pickedFeeCode}
          onPickFeeCode={props.onPickFeeCode}
          onAddFee={props.onAddFee}
          feeAddRefusal={props.feeAddRefusal}
          feeCatalogueAnswered={props.feeCatalogueAnswered}
        />
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// DOCUMENTS — TWO GATES
// ══════════════════════════════════════════════════════════════════════════

/* ══════════════════════════════════════════════════════════════════════════
   **`DocumentStateChip` LIVES IN `serviceRequestShared.tsx` NOW — PO report
   2026-09-22 row 2, B14 rule 43.**

   The chip was declared HERE and exported from a 2,482-line page, which is the
   shape rule 43 was ratified against: *a piece of UI is built as a COMPONENT;
   standalone code inside a page is not reuse.* The capture wizard's step 6
   review table could not import it, so it had written its OWN spelling of the
   same fact — the raw `verification_state` through the catalogue, with no
   `file_present` guard at all — and the two screens disagreed about a
   document's verdict on the beta's six broken rows (`DEF-CUS-5872`).

   **What moved with it:** `Not yet checked` is gone (row 2 — the scan state
   leaves the product's vocabulary) and `Nothing attached` stays, because the
   ABSENCE of a file is not a reviewer's verdict. A file with no verdict yet
   renders as an EMPTY cell rather than a claim.
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * The Documents tab — **the blueprint's own table** (p082), plus the two
 * actions that are live doors and are not in the drawing.
 *
 * ⚠ **FOUR PROSE BLOCKS BECAME ONE SENTENCE (PO ruling 2026-09-19).** The tab
 * opened with a count, two gate sentences and a checklist sentence — four
 * paragraphs before a clerk reached a document. B14 rule 32 gives a section ONE
 * sentence and rule 33 gives rationale **zero words**; three of the four were
 * rationale (*why a missing document does not stop the request*, *where the
 * checklist is configured*, *what happens at review*). The count survives
 * because it is the only one a clerk acts on, and `data-outstanding` still
 * rides on it so nothing that watched that signal lost it.
 *
 * ⚠ **THE TWO ROW ACTIONS STAY, AGAINST THE DRAWING.** p082 draws this table
 * read-only. Verify and Reject are the only doors in the product to checking a
 * document, and deleting a live door because a drawing predates it is hard-won
 * law 2's mirror — the same reasoning that keeps `Record what was handed over`
 * in the Fees block. Recorded as a divergence, not an oversight.
 */
export function DocumentsTab(props: {
  detail: ServiceRequestDetail;
  t: Translate;
  onVerify: (documentId: string) => void;
  onReject: (documentId: string) => void;
  /** Open the stored file. The HOST owns the route and the refusal sentence. */
  onOpen: (documentId: string) => void;
  /** `CR-158-BRC10` — save the file rather than open it. Optional so a host
   *  that only reviews can leave it out; the page passes it. */
  onDownload?: (documentId: string) => void;
  /** The tenant's own zone and date format, for the uploaded-on date. With
   *  either absent the date is simply not drawn. */
  timeZone?: string;
  dateFormat?: RegionalDateFormat;
  /** Which row is mid-open, so its control can say so rather than sit inert. */
  openingId: string | null;
  /** A refusal already resolved to a sentence — this tab never guesses a key. */
  openError: string | null;
  working: boolean;
}) {
  const { i18n } = useTranslation();
  const docs = props.detail.documents;
  // ══════════════════════════════════════════════════════════════════════════
  // **THE HEADER COUNTS WHAT THE TABLE LISTS — PO report 2026-09-22, row 4.**
  //
  // The PO saw **"0 of 0 verified"** printed above a table with ONE row in it.
  // Both numbers were true and they were counting different populations: the
  // server's `verified`/`attached` are computed over `with_file` — rows that
  // have a `storage_ref` — while the TABLE lists every row, including the
  // requirements nobody has brought a file for yet. A request whose only row is
  // an unmet requirement therefore reads `0 of 0` over `1`.
  //
  // **Counting the table's own rows is what makes the two agree**, and it is
  // the honest denominator for the sentence as written: a requirement with no
  // file cannot be verified, so it belongs in *how many are still to do*.
  //
  // ⚠ **`docs.verified` AND `docs.attached` ARE NOT CHANGED ON THE SERVER**, and
  // deliberately: they are a payload contract with callers this lane has not
  // walked, and moving them is a wider change than the one the PO reported.
  // What changes is which question THIS sentence asks. `data-outstanding` is
  // untouched — it is the server's own gate and nothing that watched it loses
  // its signal.
  // ══════════════════════════════════════════════════════════════════════════
  const verifiedOnScreen = docs.documents.filter(
    (doc) => documentVerdict(doc) === "verified",
  ).length;
  return (
    <Panel as="section">
      <h3>{props.t("customers.serviceRequest.tab.documents")}</h3>
      <p className="text-sm text-neutral-700" data-outstanding={String(docs.outstanding)}>
        {props.t("customers.serviceRequest.documents.verifiedOf", {
          verified: verifiedOnScreen,
          attached: docs.documents.length,
        })}
      </p>

      {docs.documents.length === 0 ? (
        <p className="text-sm text-neutral-700">
          {props.t("customers.serviceRequest.documents.noneAttached")}
        </p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>{props.t("customers.serviceRequest.documents.col.document")}</th>
              <th>{props.t("customers.serviceRequest.documents.col.file")}</th>
              <th>{props.t("customers.serviceRequest.documents.col.state")}</th>
              {/* ⚠ **`DEF-CUS-5907` — THE CLERK TYPES THIS AND NOTHING GAVE IT
                  BACK.** The capture form asks what each document proves and
                  the server has served `what_it_proves` all along; no tab
                  rendered it, so a clerk could not check it, correct it, or
                  answer a question about it. Same shape as `DEF-CUS-5903`.

                  ⚠ **THE CATALOGUE KEY ALREADY EXISTED IN ALL ELEVEN
                  LANGUAGES** — `documents.col.whatItProves`, minted for the
                  capture form. A column header naming a column that does not
                  exist is hard-won law 1 in the catalogue rather than in a
                  comment; using it here closes that too, and the clerk reads
                  the same three words in both places.

                  It sits AFTER the drawn three so `Document · File · State`
                  stay adjacent and in the blueprint's order (p086). */}
              <th>{props.t("customers.serviceRequest.documents.col.whatItProves")}</th>
              {/* ⚠ **A SEPARATE COLUMN, AND THE NUMBER IN IT IS MASKED — PO
                  ruling 2026-09-22, verbatim *"Yes, last four only"*, plus the
                  lane judgment recorded the same day (option (a)).** The form
                  asked *what does this document prove* and gave the clerk
                  nowhere to put a NUMBER, so on `SR-26-0011` a driving licence
                  number — `865554556` — was typed into the words box and
                  printed in full on a list screen. `BR-CUS-092(c)` has said
                  *last four only on every read path* since 2026-08-24 and this
                  cell was outside it. Now: `What it proves` = Identity,
                  `Document number` = `•••• 4556`. */}
              <th>{props.t("customers.serviceRequest.documents.col.documentNumber")}</th>
              <th>{props.t("customers.serviceRequest.col.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {docs.documents.map((doc) => (
              <tr key={doc.id} data-file-present={String(doc.file_present)}>
                <td>
                  {props.t(`customers.serviceRequest.docType.${doc.doc_type}`, {
                    defaultValue: doc.doc_type,
                  })}
                </td>
                {/* ⚠ **THE FILE NAME IS PRINTED ONLY WHERE THERE IS A FILE.**
                    `name` is set on all six of the beta's broken rows, so
                    printing it from `name` alone would offer `driving-licence.pdf`
                    over nothing at all — the drawing's own `Tenancy agreement →
                    —` row is what an absence looks like. */}
                {/* ══════════════════════════════════════════════════════════
                    **THE FILE NAME IS THE DOOR — PO 2026-09-22**: *"user is
                    aksing he should able to view the document submitted"*.

                    ⚠ **THE ENDPOINT HAS BEEN LIVE THE WHOLE TIME AND THIS
                    SCREEN COULD NOT REACH IT** — hard-won law 2's MIRROR, a
                    live endpoint behind no control at all. `GET
                    /service-requests/{id}/documents/{docId}/download` is
                    routed, and `openStoredDocument`'s own docstring already
                    named this tab as one of three surfaces missing it, in
                    these words: *"the request detail's Documents tab (which
                    can VERIFY and REJECT a file nobody can read)"*. A clerk
                    was being asked to certify a document they had no way to
                    open, while the CAPTURE form — where the file was still in
                    their hand — could open it. That is backwards: reviewing is
                    the moment you need to look at it.

                    ⚠ **REUSE, NOT A SECOND OPENER (B14 rule 43).** The same
                    wrapper the capture step calls, with this screen's own
                    route handed in — the helper deliberately knows no route,
                    so one opener serves every host.

                    ⚠ **THE URL IS A BEARER TOKEN** (up to four hours, PO
                    ruling 2026-08-30), so it is opened and never stored,
                    logged or put in a query cache. `openStoredDocument` also
                    refuses a scheme the browser cannot follow BY NAME, so this
                    control is never silently dead on a developer's machine.

                    ⚠ **IT IS A `<button>` AND NOT A CLICKABLE CELL.** A
                    clickable `<td>` is invisible to a keyboard, and the file
                    name is the thing a person aims at.

                    ⚠ **`—` STAYS EXACTLY WHERE IT WAS.** `name` is set on all
                    six of the beta's broken rows, so drawing a control from
                    `name` alone would offer `driving-licence.pdf` over nothing
                    at all (`DEF-CUS-5872`). No file, nothing to open, and no
                    control offered over nothing.
                    ══════════════════════════════════════════════════════════ */}
                <td>
                  {doc.file_present && (doc.name ?? null) !== null ? (
                    <button
                      type="button"
                      className="text-accent-700 underline underline-offset-2 disabled:text-neutral-700 disabled:no-underline"
                      data-doc-open={doc.doc_type}
                      disabled={props.openingId === doc.id}
                      onClick={() => props.onOpen(doc.id)}
                    >
                      {doc.name}
                    </button>
                  ) : (
                    <Dash />
                  )}
                  {/* `CR-158-BRC10` — what the file IS, how big, and when it
                      came in: `PDF · 3 KB · 10/01/2026`. The type is the
                      store's reading of the bytes, never the file's name. */}
                  {doc.file_present && (
                    <span className="block text-sm text-neutral-700 tabular-nums" data-doc-meta="">
                      {[
                        documentFileType(doc.content_type ?? null),
                        typeof doc.size_bytes === "number"
                          ? formatDocumentSize(doc.size_bytes, i18n.language)
                          : null,
                      ]
                        .filter((part): part is string => part !== null)
                        .join(" · ")}
                      {(doc.uploaded_at ?? null) !== null &&
                        props.timeZone !== undefined &&
                        props.dateFormat !== undefined && (
                        <>
                          {" · "}
                          <DateCell
                            value={doc.uploaded_at as string}
                            timeZone={props.timeZone}
                            dateFormat={props.dateFormat}
                          />
                        </>
                      )}
                    </span>
                  )}
                </td>
                {/* ══════════════════════════════════════════════════════
                    **ROWS 2 AND 3 OF THE PO'S LIST, AND BOTH ARRIVE AS ONE
                    COMPONENT (B14 rule 43).**

                    ROW 2 — *"Document states become Verified or Rejected
                    only"*. This cell drew a THIRD, neutral `Not yet checked`
                    pill: the word for a virus scan this product does not run.
                    It is gone, and a file nobody has judged yet renders as an
                    EMPTY cell rather than a claim. `Nothing attached` STAYS —
                    it is the absence of a FILE and not a reviewer's verdict,
                    and this tab draws the file name as a control so its FILE
                    cell is a bare dash; the absence has to be said once
                    somewhere, which is what `nameTheAbsence` is.

                    ROW 3 — a rejected document shows its reason, short.
                    `reject_reason` has been stored since the column was
                    written, is REQUIRED by `reject_document`, and no screen on
                    the reviewer's side had ever rendered it.

                    ⚠ **THE COMPONENT IS THE POINT.** The same ruling was built
                    in `components/documents/DocumentTable.tsx` for the capture
                    screen on 2026-09-22 and this tab was not touched, so the
                    clerk who ATTACHES a document and the clerk who REVIEWS it
                    saw different words about one row. `DocumentStateCell` is
                    that logic extracted; both tables ask it.
                    ══════════════════════════════════════════════════════ */}
                <td>
                  <DocumentStateCell row={doc} t={props.t} nameTheAbsence />
                </td>
                {/* A document nobody wrote a purpose for is a dash, never a
                    guess at what it might prove.
                    ⚠ **AND A CELL HOLDING AN IDENTIFIER IS MASKED** — see the
                    column header above. `WhatItProves` decides, once, for both
                    screens. */}
                <td>
                  <WhatItProves value={doc.what_it_proves ?? null} />
                </td>
                <td data-document-number={doc.doc_type}>
                  <TextOrDash value={maskLastFour(doc.document_number)} />
                </td>
                <td>
                  <RowActions>
                    {/* `CR-158-BRC10` — save the file. Offered over a FILE
                        only; a row recording an expectation has nothing to
                        save, and the reason says so. */}
                    {props.onDownload !== undefined && (
                      <RowAction
                        label={props.t("customers.serviceRequest.documents.download")}
                        icon={<DownloadIcon />}
                        reason={
                          doc.file_present
                            ? null
                            : props.t("customers.serviceRequest.documentHasNoFile", {
                                doc_type: doc.doc_type,
                              })
                        }
                        working={false}
                        onClick={() => props.onDownload?.(doc.id)}
                      />
                    )}
                    {/* ⚠ **A DOCUMENT WITH NO FILE CANNOT BE VERIFIED**, and
                        the control says so rather than disappearing: that
                        would be a clerk certifying nothing. The server refuses
                        it too (`documentHasNoFile`) — defence in depth.
                        ⚠ It asks `file_present` now, not `attached`: on the six
                        rows of `DEF-CUS-5872` those two disagree, and the one
                        that decides whether a file can be READ is this one. */}
                    <RowAction
                      label={props.t("customers.serviceRequest.documents.verify")}
                      icon={<CommitIcon />}
                      reason={
                        doc.file_present
                          ? null
                          : props.t("customers.serviceRequest.documents.cannotVerifyNoFile")
                      }
                      working={props.working}
                      onClick={() => props.onVerify(doc.id)}
                    />
                    <RowAction
                      label={props.t("customers.serviceRequest.documents.reject")}
                      icon={<TrashIcon />}
                      danger
                      reason={
                        doc.file_present
                          ? null
                          : props.t("customers.serviceRequest.documents.cannotRejectNoFile")
                      }
                      working={props.working}
                      onClick={() => props.onReject(doc.id)}
                    />
                  </RowActions>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {/* ⚠ **A REFUSED OPEN IS SAID OUT LOUD.** The link is minted by the
          server and can fail — a row whose `storage_ref` resolves to nothing
          answers `documentHasNoFile`, and the dev store mints a `file://` URL
          no browser will follow. Either way a control that appears to do
          nothing is the shape this product keeps removing. */}
      {props.openError !== null && (
        <p className="field-error" role="alert" data-doc-open-error="">
          {props.openError}
        </p>
      )}
    </Panel>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// FEES — the drawn `Quoted and taken` box, and BR-CUS-090
// ══════════════════════════════════════════════════════════════════════════

/**
 * ✅ **BR-CUS-090 IS THE WHOLE OF THIS PANEL, AND ITS WORKED CASE IS THE
 * ACCEPTANCE TEST:** quoted **$130.00**, taken **$25.00**, receipt
 * `RCP-26-4471` → *$105.00 outstanding*. Those figures are also what the
 * blueprint draws on p083 — and they are ILLUSTRATIONS there (B14 rule 37).
 * Every amount on screen comes from the payload, through `MoneyCell` with its
 * own `CHAR(3)`, at two decimals (CLAUDE.md hard rule 2).
 *
 * PO verbatim: *"we acept it and in finance we will reconcile ; here
 * segregation of responsibilitys, accept it and mark it as cash"*.
 *
 * ⚠ **THREE THINGS THIS PANEL MAY NEVER DO, each of which the ruling names:**
 *   1. **Refuse a shortfall at the desk.** `fee_collected < fee_quoted` is a
 *      lawful, storable state. The form does not validate the amount against
 *      the quote and the server does not either.
 *   2. **Call a shortfall a waiver.** A waiver is BR-CUS-073's explicit act
 *      with a reason, on a LINE. The two are drawn apart here on purpose.
 *   3. **Adjust the quote to match the cash.** The two roles are separate —
 *      the person who takes the money records it, finance agrees it against the
 *      cash count — so nothing here rewrites `quoted`.
 *
 * ⚠ **THE `Connection quote` IS `Not raised` AND THERE IS NO BUILDER FOR IT.**
 * The server answers `{raised: false, reason: "raised_after_review"}` with no
 * endpoint behind it. A builder drawn over no endpoint is dead UI (hard-won
 * law 2), so the quote half states its own absence.
 *
 * ⚠ **THIS WAS A WHOLE TAB AND IS NOW A BLOCK, AND NOT ONE DOOR WAS LOST.**
 * The blueprint puts `FEES` in the Applicant tab's right column (p083), so the
 * FIGURES are drawn there; `Record what was handed over` and the per-line waive
 * came with them, inside the disclosure, because deleting a counter's
 * money-taking control to match a picture would be the mirror of dead UI.
 */
export function FeesBlock(props: {
  detail: ServiceRequestDetail;
  t: Translate;
  onWaive: (feeId: string) => void;
  onCollect: () => void;
  working: boolean;
  /**
   * ⚠ **THE PICKER'S FOUR PROPS ARE REQUIRED, NOT OPTIONAL, AND THAT IS G13.**
   * An optional prop nothing passes is dead UI — a component that renders
   * nothing while every test passes and the feature does not exist. Four
   * defects in one day taught that, `G13` enforces it, and the cheap way to
   * stay on the right side of it is to make the prop impossible to forget.
   */
  feeCodes: readonly ChargeRow[];
  pickedFeeCode: string;
  onPickFeeCode: (code: string) => void;
  onAddFee: () => void;
  feeAddRefusal: string | null;
  feeCatalogueAnswered: boolean;
}) {
  const fees = props.detail.fees;
  /** No currency means no fee line was ever raised — the server serves the
   *  `CHAR(3)` beside every figure and has none to serve. The four figures
   *  above already refuse to print money on that state; this is the same
   *  question asked once, for the header that did not. */
  const noFeeRaised = fees.quoted.currency === null || fees.quoted.currency === "";
  /** 🔒 DEF-CUS-9819 (PO 2026-10-06) — a request with fee lines that owes
   *  $0.00 (a $0.00 application fee, or everything waived or paid) has
   *  nothing to collect, so the collect button is not drawn. A request with
   *  NO line keeps the button, exactly as before. A comparison of the
   *  server's own figure, never arithmetic (hard rule 2). */
  const nothingToCollect = fees.lines.length > 0 && owesNothing(fees.outstanding.amount);

  return (
    <Panel as="section" data-panel-name="fees">
      <h3>{props.t("customers.serviceRequest.fees.quotedAndTaken")}</h3>

      {/* ══════════════════════════════════════════════════════════════════
          **ONE LINE, ONE STATE — PO report 2026-09-22, row 10.**

          PO, verbatim: *"i dont know whether this informtion is correct - we
          are either taking application fees or we are waiveing it off so
          message should be in line with that"*.

          **What was here:** a four-row grid — `Quoted` · `Settled by an
          invoice` · `Collected` · `Outstanding` — each row printing
          `MoneyOrAbsence`, so on a request with no fee the SAME sentence
          appeared three times in one panel, and under it a *"Not yet: No
          blocking arrears."* line about something else entirely.

          **Why the grid is wrong and not merely noisy:** quoted / collected /
          outstanding is a FINANCE BREAKDOWN, and it exists to describe a
          PART-PAYMENT. An application fee is not that. It is raised or it is
          not; it is taken or it is waived. Four figures invite a clerk to
          reconcile three of them against each other on a value that only ever
          has one state.

          ⚠ **WHAT SURVIVES, BECAUSE IT IS A SIGNED RULE AND NOT DECORATION
          (`BR-CUS-090`):** a shortfall is an open balance and is NOT a waiver.
          That sentence is still drawn, immediately below, from the server's
          own `shortfall_is_open_balance` — and it is drawn only when there IS
          one, rather than being asserted over every request.

          ⚠ **AND THE DERIVATION IS STILL ONE PRESS AWAY.** The disclosure
          under this line still lists every fee row with its amount, its waiver
          and its own actions. Nothing a clerk could act on left the screen;
          what left is three restatements of one fact.
          ══════════════════════════════════════════════════════════════════ */}
      <ApplicationFeeLine fees={fees} t={props.t} />

      {/* ⚠ **A SHORTFALL IS AN OPEN BALANCE — NEVER A REFUSAL AND NEVER A
          WAIVER**, printed from the server's own boolean so the screen cannot
          draw it as either. Outside the disclosure, because it is the ruling
          and a clerk who never opens the panel must still read it. */}
      {/* ⚠ **ONLY WHERE SOMETHING WAS HANDED OVER (2026-09-23, measured against
          B14 rule 33 for `DEF-CUS-6414`).** *"Less was handed over. Not a
          waiver."* is two FACTS inside rule 33's cap — and the first one is
          FALSE on a request where nothing was handed over at all: the server's
          `shortfall_is_open_balance` is simply *outstanding > 0*, which a
          request with $0 collected also is. Walked on SR-26-0011: $0.00
          collected, and the panel said less had been handed over. A
          part-payment is what the sentence is about, so a part-payment is when
          it shows. */}
      {fees.shortfall_is_open_balance && !/^-?0+(\.0+)?$/.test(fees.collected.amount.trim()) && (
        <p className="mt-2 max-w-prose text-sm text-neutral-700" data-shortfall="open-balance">
          {props.t("customers.serviceRequest.fees.shortfallIsOpenBalance")}
        </p>
      )}

      {/* `Disclosure` collapses the DERIVATION and never the result — its own
          load-bearing rule — so the four figures stand above and the LINES,
          with their waive, live inside. B14 rule 32: a stated absence and a
          derivation are `<details>` CLOSED by default.

          ⚠ **AND IT IS NOT DRAWN AT ALL WHEN THERE IS NO FEE — 2026-09-21.**
          PO, the same day they made the fee optional: *"some utilities will
          not take applciation fees also"*. Measured on a `$0` request in a
          browser, this panel read:

              Quoted and taken · No fee has been raised on this request yet.
              Application fees · 0.00 collected of 0.00 quoted
                               · No fee has been raised on this request yet.

          **The same sentence twice in one panel** — which is the defect the
          four-figure grid above already fixed once and this header kept — and
          a `0.00 collected of 0.00 quoted` summary printing money with **no
          currency behind it**, which is exactly what the branch above exists
          to refuse. A derivation of nothing derives nothing.

          ⚠ **ONLY THE HEADER'S THREE FIGURES GO, AND THE PANEL STAYS OPEN.**
          The first draft of this fix hid the whole disclosure and took the
          CONNECTION QUOTE's own stated absence with it — a different fact from
          the application fee, and one a `$0` utility still has. A fix wider
          than its defect deletes a surface nobody asked about.

          ⛔ **AND THE REST OF THAT REQUIREMENT IS FILED, NOT QUIETLY DONE.**
          The panel itself and `Record what was handed over` still appear on a
          `$0` request, and they stay: hiding a live money-taking control
          changes what a clerk can DO, and there is no per-tenant
          application-fee setting to decide it from — a request with no fee
          line is not the same fact as a utility that charges none.
          `DEF-CUS-6102`. */}
      <DisclosureList>
        <Disclosure
          variant="row"
          title={props.t("customers.serviceRequest.fees.applicationFees")}
          summary={
            noFeeRaised
              ? undefined
              : props.t("customers.serviceRequest.fees.collectedOfQuoted", {
                  // `DEF-CUS-6412` — through `formatMoney` with the CHAR(3),
                  // never the bare `display` (`0.00 collected of 70.00`).
                  collected: moneyText(fees.collected),
                  quoted: moneyText(fees.quoted),
                })
          }
          value={noFeeRaised ? undefined : <MoneyOrAbsence money={fees.outstanding} t={props.t} />}
          status={
            fees.shortfall_is_open_balance
              ? props.t("customers.serviceRequest.fees.openBalance")
              : undefined
          }
        >
          {/* ══════════════════════════════════════════════════════════
              **A CLERK CAN RAISE AN APPLICATION FEE HERE — PO report
              2026-09-22, row 11, and `DEF-CUS-5904` with it.**

              `addServiceRequestFee` has been exported and called by NOTHING
              since this module was built: the endpoint works, the client
              works, `tsc` passes, and until today there was no door in the
              product. That is hard-won law 2, and it is why this picker is
              on BOTH screens rather than only on the wizard the PO was
              looking at — a request whose fee was never raised at capture
              could never be given one afterwards.

              **ONE COMPONENT, MOUNTED TWICE (B14 rule 43).** The capture
              wizard's fee step mounts the same `ApplicationFeeAdder`. The
              amount is the tenant's charge code and is never typed here. */}
          <ApplicationFeeAdder
            codes={props.feeCodes}
                        picked={props.pickedFeeCode}
            onPick={props.onPickFeeCode}
            onAdd={props.onAddFee}
            t={props.t}
            working={props.working}
            refusal={props.feeAddRefusal}
            nothingToOffer={props.feeCatalogueAnswered && props.feeCodes.length === 0}
          />

          {/* ══════════════════════════════════════════════════════════════
              **THE SAME FEE TABLE AS CAPTURE STEP 5, READ-ONLY, PLUS `Paid` —
              `DEF-CUS-6411`, PO approval 2026-09-23.** `Fee · Charged per · Qty
              · Unit price · Amount · Paid`, `Total` under `Amount`. A waived
              line reads as waived, with its reason.

              ⚠ **THE PER-LINE WAIVE STAYS, AS A ROW ACTION.** Once a request is
              submitted it is the ONLY door onto a waiver (OQ-357 closed
              2026-09-23 as "both": remove while a draft, waive after), and the
              head's `Waived` option only exists where exactly one line can be
              waived. A read-only table that dropped it would take a capability
              away from every request with two fees.

              ⛔ **THE DISABLED REMOVE ICON IS GONE**, with its sentence *"A fee
              line cannot be deleted. Waive it instead…"*. It was true of every
              line until OQ-357 closed; it is now false of a draft's lines and
              beside the point for a submitted request's, whose door is the
              waive. The server's matching `fee_line_cannot_be_removed` absence
              is retired in the same commit (`DEF-CUS-6418`).
              ══════════════════════════════════════════════════════════════ */}
          <FeeLinesTable
            fees={fees}
            t={props.t}
            collection="detail-fees"
            paidColumn
            rowAction={(line) => (
              <RowActions>
                <RowAction
                  label={props.t("customers.serviceRequest.fees.waive")}
                  /* One glyph per verb: the move-in's deposit waive draws the
                     same one (DEF-CUS-9778) — never the tick, which reads as
                     "paid" beside an amount. */
                  icon={<WaiveIcon />}
                  reason={
                    line.waived || line.settled_at !== null
                      ? props.t("customers.serviceRequest.fees.alreadySettledOrWaived")
                      : null
                  }
                  working={props.working}
                  /* ⚠ **THE ROW'S `id`, NEVER ITS `line_no` — `DEF-CUS-6096`.**
                     The endpoint addresses the row by uuid; `"1"` was a 500
                     four times in one walk over a screen that changed in no
                     way. */
                  onClick={() => props.onWaive(line.id)}
                />
              </RowActions>
            )}
          />

          {/* B18 §4.6, served in the payload so a caller cannot assume
              otherwise: NOTHING in this module posts to the ledger or issues an
              invoice. */}
          <p className="mt-2 max-w-prose text-sm text-neutral-700" data-posts-to-ledger={String(fees.posts_to_ledger)}>
            {props.t("customers.serviceRequest.fees.notALedgerPosting")}
          </p>

          <h4 className="mt-4 mb-1 text-md font-semibold">
            {props.t("customers.serviceRequest.fees.connectionQuote")}
          </h4>
          <StatusPill tone="neutral">
            {props.t("customers.serviceRequest.fees.quoteNotRaised")}
          </StatusPill>
          <p className="mt-2 max-w-prose text-sm text-neutral-700">
            {props.t("customers.serviceRequest.fees.quoteRaisedAfterReview")}
          </p>
        </Disclosure>
      </DisclosureList>

      <div className="mt-3">
        {nothingToCollect ? (
          <p className="m-0 text-md text-neutral-700" data-fee-collect="nothing">
            {props.t("customers.serviceRequest.fees.nothingToCollect")}
          </p>
        ) : (
          <Button variant="secondary" disabled={props.working} onClick={props.onCollect}>
            {props.t("customers.serviceRequest.fees.collect")}
          </Button>
        )}
      </div>
    </Panel>
  );
}

/** Zero or below, read off the server's 4-dp string: `0.0000`, `0`, `-5.0000`. */
function owesNothing(amount: string): boolean {
  const text = amount.trim();
  return text.startsWith("-") || /^0+(\.0+)?$/.test(text);
}

// ══════════════════════════════════════════════════════════════════════════
// HISTORY — append-only
// ══════════════════════════════════════════════════════════════════════════

export function HistoryTab(props: {
  detail: ServiceRequestDetail;
  t: Translate;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onAddNote: (note: string) => void;
  working: boolean;
}) {
  const [note, setNote] = useState("");
  return (
    <Panel as="section">
      <h3>{props.t("customers.serviceRequest.tab.history")}</h3>
      {/* Badged `Internal · never shown to the customer`. There is no
          customer-visible path and there must not be one — the portal is out of
          v1 scope, so a visibility flag would be a permission with nothing to
          permit. */}
      <StatusPill tone="neutral">
        {props.t("customers.serviceRequest.history.internalOnly")}
      </StatusPill>
      <div className="mt-2 flex flex-wrap items-end gap-2">
        <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
          {props.t("customers.serviceRequest.history.addNote")}
          <input
            className="border border-field-border bg-surface px-2 py-1 text-sm"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
        <Button
          variant="secondary"
          disabled={note.trim() === "" || props.working}
          title={
            note.trim() === ""
              ? props.t("customers.serviceRequest.history.noteRequired")
              : undefined
          }
          onClick={() => {
            props.onAddNote(note.trim());
            setNote("");
          }}
        >
          {props.t("customers.serviceRequest.history.save")}
        </Button>
      </div>

      {/* ⚠⚠ **THE DRAWN TABLE — `WHEN · WHAT · WHO` (p083), BUILT 2026-09-19.**
          This was an unlabelled `<ul>`: a date, a kind word and a note stacked
          in one cell, with no `WHO` at all. The blueprint draws three columns
          and prints `S. Ortiz` and `A. Whitfield` in the third.

          ⚠ **THE `WHO` COLUMN NEEDED A SERVER CHANGE AND NOT A SCREEN ONE.**
          `history[].actor` is a user id, and B14 rule 31 forbids a database id
          being the visible value of a field — the PO's own words, *"no Databse
          ID on screen - that is a rule"*. So the column stood EMPTY under a
          note reading *"Who acted is not named yet"*, which was a stated
          absence over a fact the server was holding and not resolving.
          `history_tab` serves `actor_name` now and the note is deleted. */}
      <table className="data-table mt-3">
        <thead>
          <tr>
            <th>{props.t("customers.serviceRequest.history.col.when")}</th>
            <th>{props.t("customers.serviceRequest.history.col.what")}</th>
            <th>{props.t("customers.serviceRequest.history.col.who")}</th>
          </tr>
        </thead>
        <tbody>
          {props.detail.history.map((event) => (
            <tr key={event.id}>
              <td className="whitespace-nowrap text-neutral-700">
                <DateOrNotSupplied
                  value={event.at}
                  t={props.t}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                  withTime
                />
              </td>
              {/* ⚠ **THE ACT, NOT ITS CATEGORY — PO report 2026-09-22 row 7,
                  `DEF-CUS-6181`.** This printed `event.kind`, which is one of
                  three words (`state` · `note` · `system`) and is the DEFAULT
                  for every side effect a clerk causes — so ten different acts
                  all read `System`, beside that same clerk's name in the WHO
                  column. The act's real name has been in `note_type` since the
                  field existed and no screen had read it. */}
              <td>
                <EventWhat kind={event.kind} noteType={event.note_type} t={props.t} />
                {event.to_state !== null && (
                  <span className="ml-1 text-neutral-700">
                    {props.t(`customers.serviceRequest.state.${event.to_state}`)}
                  </span>
                )}
                {/* ⛔ **`DEF-CUS-5420` / `DEF-CUS-5422`** — a note is a clerk's
                    free text on one row and a STORED CATALOGUE KEY or a
                    snake_case reason code on another. `CatalogueSentence`
                    resolves both and falls back to the text itself. */}
                {event.note !== null && event.note !== "" && (
                  <span className="block text-neutral-700">
                    <CatalogueSentence value={event.note} t={props.t} />
                  </span>
                )}
              </td>
              {/* ⚠ **THE NAME, NEVER THE ID.** A row written by a background
                  job or planted by the seed has no user, and the drawing prints
                  a dash in exactly that position.

                  ⚠ **AND `System` BELONGS HERE, WHICH IS THE OTHER HALF OF ROW
                  7.** A row cannot be both *System* and a person: until today
                  the word sat in the WHAT column, where it described the KIND
                  of the row rather than who caused it, while WHO carried the
                  clerk's own name. The word now appears in exactly one place
                  and means exactly one thing — **nobody was signed in** — and a
                  row a person caused says that person. */}
              <td className="whitespace-nowrap" data-actor-named={String(event.actor_name !== null)}>
                {event.actor_kind === "customer" ? (
                  // `DEF-CUS-9091` — the applicant acted through the portal.
                  <span data-actor="customer">
                    {event.actor_name === null
                      ? props.t("customers.serviceRequest.event.customerUnnamed")
                      : props.t("customers.serviceRequest.event.customerWho", {
                          name: event.actor_name,
                        })}
                  </span>
                ) : event.actor_name === null ? (
                  <span className="text-neutral-700" data-actor="system">
                    {props.t("customers.serviceRequest.event.system")}
                  </span>
                ) : (
                  <TextOrDash value={event.actor_name} />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// WHERE THE `←` GOES — PO report 2026-09-20 §8
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **`The register` NAMED FOUR DIFFERENT PLACES.** The PO pressed this
// control on an approved MOVE-IN request and landed on the requests list:
// *"when i lick on register - it shoudl take me to movein list page - instead
// it takes me to request list page"*. Four catalogue keys rendered the
// identical string and went to four destinations.
//
// **B14 rule 1 decides it: a page header's `←` NAMES WHERE IT EXITS TO.** A
// control that names its destination cannot send a clerk to the wrong tab —
// which is why the fix is a LABEL change as much as a route change, and why
// `backToRegister` is relabelled in all eleven catalogues rather than left
// saying `The register` over a link that now goes somewhere else.

/**
 * WHERE THIS REQUEST'S BACK CONTROL EXITS TO, AND WHAT IT IS CALLED.
 *
 * ⚠ **THE OUTCOME→QUEUE MAP IS `request_jobs.JOB_SHAPES` AND IS NOT COPIED
 * HERE.** The server answers *which queue* on the header as `queue`; this turns
 * the queue's name into the tab's slug and refuses anything `ACCOUNTS_TAB_IDS`
 * does not know. The decision log is explicit about why: *"that map is the
 * single source; a second one is how two screens come to disagree."*
 *
 * ⚠ **THE TWO VOCABULARIES ARE REAL AND THE DIFFERENCE IS ONE CHARACTER.** The
 * backend's queue is `move_ins` — it names a JOB QUEUE — and the tab is
 * `move-ins`. The slugs here are `AccountsListPage`'s, the same ones
 * `PARKED_HOME_PATHS` navigates to, and the test asserts the two agree rather
 * than trusting that they do.
 *
 * ⚠ **THE LABELS ARE THE TABS' OWN WORDS** (`ACCOUNTS_TAB_LABEL_KEYS`), not a
 * second set written for this screen. B14 rule 34's discipline: one pair of
 * words for one thing, everywhere. The Move-ins tab is called *Move-ins* on
 * whatever screen names it.
 */
export function requestBackDestination(header: { state: string; queue?: string | null }): {
  to: string;
  labelKey: string;
} {
  const queue = header.state === "approved" ? (header.queue ?? null) : null;
  if (queue !== null && queue !== "") {
    const slug = queue.replace(/_/gu, "-");
    if ((ACCOUNTS_TAB_IDS as readonly string[]).includes(slug)) {
      return {
        to: `${ACCOUNTS_ROUTE}?${ACCOUNTS_TAB_PARAM}=${slug}`,
        labelKey: ACCOUNTS_TAB_LABEL_KEYS[slug as AccountsTab],
      };
    }
  }
  // Everything else goes back to the requests list — where the request was
  // raised, and the only place an unapproved one is findable. The key is
  // `backToRegister`, relabelled to say so.
  return { to: SERVICE_REQUESTS_ROUTE, labelKey: "customers.serviceRequest.detail.backToRegister" };
}

// ══════════════════════════════════════════════════════════════════════════
// WHY A CONTROL IS DEAD — PO ratification 2026-09-20 §1, the second fault
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **EVERY DISABLED CONTROL ON THIS SCREEN GAVE ONE REASON, AND IT WAS
// FALSE FOUR TIMES OUT OF FIVE.** The string was
// `customers.serviceRequest.park.terminalNoPark` — *"This request is closed,
// so there is nothing to wait for."* — printed over a DRAFT, which is not
// closed and has nobody waiting for it. It also ran to eleven words where
// B14 rule 33 caps a FACT at six.
//
// `BR-SHL-025` is the rule being served: a control this state cannot honour is
// DISABLED WITH ITS REASON, never hidden. **A reason that is not true is worse
// than no reason** — it is a sentence a clerk acts on, and this one told them
// to stop looking at a request they could have submitted.
//
// ⚠ **THE SENTENCES ARE FACTS, NOT RATIONALE (B14 rule 33).** Each says what
// the request IS, in at most six words, and none explains why the product
// works this way — that belongs here in the code and in the register, at zero
// words on screen. None carries a rule id, a question id or a state VALUE
// (rules 31 and 32): `more_info` reads *"Waiting on the applicant."*, never
// `more_info`.

/** The five columns of the PO's table, in its own order. */
export const REQUEST_CONTROLS = [
  "submit",
  "approve",
  "request_info",
  "refuse",
  "park",
] as const;
export type RequestControl = (typeof REQUEST_CONTROLS)[number];

/**
 * WHAT A CLERK READS ON A DEAD CONTROL, GIVEN THE REQUEST'S STATE.
 *
 * ⚠ **IT ANSWERS FOR THE STATE AND NOT FOR THE CONTROL'S OWN GATE**, which is
 * the whole correction: whether a control is dead is the SERVER's answer
 * (`actions.available`, `actions.can_park`), and this says why. Calling it for
 * a control the state allows is a caller error, and it returns the state's
 * sentence rather than inventing a cheerful one — a live button never shows a
 * reason, because the screen only asks when it has already greyed something.
 *
 * ⚠ **THE LAST BRANCH IS NOT A CATCH-ALL, IT IS THE FOUR LEGACY STATES.**
 * `in_fulfilment`, `on_hold`, `completed`, `withdrawn` and `closed` can no
 * longer be REACHED — the 2026-09-19 ruling took the nine moves that led there
 * out of `TRANSITIONS` — but rows already sitting in them keep them and still
 * open on this screen. *"This request is closed."* is true of every one of
 * them, and it is the one place the old sentence's MEANING survives.
 */
export function requestControlReasonKey(control: RequestControl, state: string): string {
  const base = "customers.serviceRequest.actionReason";
  switch (state) {
    case "draft":
      // Four of the five are unlawful from a draft for exactly one reason, and
      // `submit` is the fifth — it is live here, so it never asks.
      return `${base}.notSubmitted`;
    case "submitted":
      return `${base}.alreadySubmitted`;
    case "under_review":
      // Only `submit` and `park` are dead here. Park's answer is the more
      // useful one: the request has been picked up, which is what parking a
      // submitted request DID.
      return control === "park" ? `${base}.alreadyUnderReview` : `${base}.alreadySubmitted`;
    case "more_info":
      // Parking a request that is waiting on the APPLICANT would take it off
      // the queue their answer belongs to — `park`'s own note in
      // `service_request_service.py` says so. The clerk is told the fact, not
      // the mechanism.
      return control === "park" ? `${base}.waitingOnApplicant` : `${base}.alreadySubmitted`;
    case "approved":
      // ⚠ **`approved` IS NOT A TERMINAL STATE** — `TERMINAL_STATES` is
      // `(completed, refused, withdrawn, closed)` — so *"this request is
      // closed"* was false here too, in the other direction.
      return `${base}.alreadyApproved`;
    case "refused":
      return `${base}.alreadyRefused`;
    default:
      return `${base}.closed`;
  }
}

// ══════════════════════════════════════════════════════════════════════════
// THE PAGE
// ══════════════════════════════════════════════════════════════════════════

export interface ServiceRequestDetailPageProps extends RegionalProps {
  client?: ApiClient;
}

export function ServiceRequestDetailPage(props: ServiceRequestDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const routeParams = useParams();
  const tenantPath = useTenantPath();
  // `DEF-CUS-6109` — approving into a new connection opens the build's wizard.
  const navigate = useNavigate();
  const client = props.client ?? api;
  const { timeZone, dateFormat } = useRegional(props);
  const [search, setSearch] = useSearchParams();
  // ⚠ **THE ID COMES FROM THE ROUTE AND FROM NOWHERE ELSE.** A `requestId`
  // prop was written here as a test seam and G13 refused it, correctly: an
  // optional prop nothing supplies is dead UI by another name (hard-won law 2),
  // and the tabs are unit-tested as components anyway.
  const requestId = routeParams.requestId ?? "";
  const tab = requestTabFromParam(search.get("tab"));

  const [park, setPark] = useState(false);
  const [waitingOn, setWaitingOn] = useState("");
  const [parkNote, setParkNote] = useState("");
  const [remindOn, setRemindOn] = useState("");
  // ── CR-094-BRC01 wave 2 · the head's three decisions, each a MODAL ────────
  //
  // PO ruling 2026-09-15, and the drawing it comes from (p082–p086, read as
  // images): `Refuse` · `Ask for more` · `Approve`, three dialogs, plus `Park`,
  // which the PO kept after being told it is the only thing setting the
  // register's WAITING ON column today. `Save & exit` and `Decide what this is`
  // are REMOVED by the same ruling — the second one BECAME the Approve modal.
  const [approve, setApprove] = useState(false);
  // ⊕ `DEF-CUS-10251` — whether the Approve window OPENED on a portal request
  // still needing its category; the *Set before approving* panel stays for the
  // window's life so the sub-category can follow the category once saved.
  const [categoryNeededAtOpen, setCategoryNeededAtOpen] = useState(false);
  const approveCategories = useAccountCategories(client);
  const approveSubtypes = useAccountSubtypes(client);
  const [refuse, setRefuse] = useState(false);
  const [ask, setAsk] = useState(false);
  const [collect, setCollect] = useState(false);
  // What the last decision actually did — see `DecisionOutcomeNote`. A button
  // that does the thing and says nothing is half a control.
  const [outcomeNote, setOutcomeNote] = useState<{
    job?: ServiceRequestJob;
    message?: ApplicantMessage | null;
  } | null>(null);
  // What the last ROW ACTION refused with, rendered below the head. `null` is
  // *nothing has failed*, which is not the same as *nothing has been pressed*.
  const [actionError, setActionError] = useState<unknown>(null);
  /** CR-183-BRC10 B2 — a field visit that could not be raised (catalogue key). */
  const [fieldVisitWarning, setFieldVisitWarning] = useState<string | null>(null);
  /** `taken` (the default) or `waived` — PO ruling 2026-09-22. */
  const [collectKind, setCollectKind] = useState<"taken" | "waived">("taken");

  // ══════════════════════════════════════════════════════════════════════════
  // THE APPLICATION FEE'S CHARGE CODES — PO report 2026-09-22, row 11
  //
  // ⚠ **THE QUERY KEY IS THE CAPTURE WIZARD'S**, so a clerk who walks from
  // the wizard to this screen does not pay for the catalogue twice and the two
  // screens cannot show different lists of the same thing.
  //
  // ⚠ **`status: "active"` IS NOT A TIDINESS FILTER.** A deactivated charge is
  // one the utility has STOPPED selling (`IS-1`, deactivate-first).
  // ══════════════════════════════════════════════════════════════════════════
  const feeChargesQuery = useQuery({
    queryKey: ["charges", "service-request-fee"],
    queryFn: () => getCharges({ per: 200, filters: { status: "active" } }, client),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const feeCodes = chargeCodeOptions(feeChargesQuery.data?.results ?? [], canBeRaisedOnItsOwn);
  const [pickedFeeCode, setPickedFeeCode] = useState("");
  const [feeAddRefusal, setFeeAddRefusal] = useState<string | null>(null);
  /**
   * **WHICH LINE THE PER-ROW `Waive` WAS PRESSED ON, or `null` for the head's
   * own door.**
   *
   * ⚠ **THE TWO CONTROLS NOW OPEN ONE MODAL, WHICH IS WHAT KILLED THE
   * HARDCODED REASON.** The per-line waive inside the fee disclosure used to
   * POST immediately, sending
   * `customers.serviceRequest.fees.defaultWaiveReason` — ONE English sentence,
   * identical on every waiver this product has ever recorded, which makes the
   * stored reason worth nothing to whoever reads it back. Routing it through
   * the modal means every waive now carries one of the TENANT's own reasons
   * and the clerk cannot avoid choosing.
   */
  const [waiveTarget, setWaiveTarget] = useState<string | null>(null);

  const detailQuery = useQuery({
    queryKey: serviceRequestDetailKey(requestId),
    queryFn: () => getServiceRequest(requestId, client),
    enabled: requestId !== "",
  });

  /**
   * ⚠⚠ **A ROW ACTION THAT FAILS NOW SAYS SO — `DEF-CUS-6096`, 2026-09-21.**
   *
   * This hook carried `onSuccess` and **no `onError`**, so every refusal from
   * every control that goes through it — `Waive`, `Verify`, `Reject`,
   * `Add note`, `Record that I searched` — was thrown away between the server
   * and the screen. On 2026-09-20 a clerk pressed `Waive` four times against a
   * server throwing a 500 four times, and **the screen changed in no way and
   * said nothing at all.** A failure a screen does not render is
   * indistinguishable from a mis-click, which is why the underlying fault
   * survived a whole walk.
   *
   * ⚠ **THE MODALS WERE NEVER AFFECTED AND THAT IS WHY NOBODY NOTICED.**
   * `post()` below hands the envelope back to `FormModal`, which renders it
   * through the catalogue. Every DIALOG in this screen told the truth; only the
   * controls that post directly were silent. Two paths out of one screen, one
   * of them with no error branch at all — G13 asks whether a prop is passed and
   * cannot ask this.
   *
   * The sentence is the SERVER's, rendered from its `message_key` and params
   * (`BR-SHL-020` / the 2026-08-19 ruling); nothing here writes copy.
   */
  // ══════════════════════════════════════════════════════════════════════════
  // OPENING A STORED DOCUMENT — PO 2026-09-22
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **IT IS DELIBERATELY NOT `mutate`.** That mutation refetches the whole
  // detail on success and writes `actionError`, which is right for Verify and
  // Reject — they CHANGE the request. Opening a file changes nothing, so a
  // refetch would be a wasted read and a shared error slot would put *"the file
  // could not be opened"* where a clerk reads the outcome of a verification.
  //
  // ⚠ **NOTHING ABOUT THE LINK IS KEPT.** `openStoredDocument` mints a bearer
  // URL good for up to four hours (PO 2026-08-30); it is opened and never
  // stored, logged or put in a query cache. Only the row id being opened and a
  // refusal sentence live here.
  const [docOpeningId, setDocOpeningId] = useState<string | null>(null);
  const [docOpenError, setDocOpenError] = useState<string | null>(null);

  async function openRequestDocument(documentId: string): Promise<void> {
    setDocOpenError(null);
    setDocOpeningId(documentId);
    try {
      // ⚠ **THE CONTENT ROUTE — `CR-158-BRC10`.** The file comes through
      // our own route with `Content-Disposition`, `nosniff` and a no-script
      // policy, and opens on every storage backend.
      openDocumentContent(
        `/service-requests/${requestId}/documents/${documentId}/content`,
        "view",
      );
    } catch (error) {
      setDocOpenError(
        isApiError(error)
          ? translate(error.messageKey, error.params)
          : translate("customers.serviceRequest.documentHasNoFile", { doc_type: "" }),
      );
    } finally {
      setDocOpeningId(null);
    }
  }

  const mutate = useMutation({
    mutationFn: async (action: () => Promise<unknown>) => action(),
    onSuccess: () => {
      setActionError(null);
      void detailQuery.refetch();
    },
    onError: (error: unknown) => setActionError(error),
  });

  /**
   * A `FormModal` submit: post, refresh, and hand the SERVER's envelope back so
   * the modal renders the refusal through the catalogue (B12 §3 / BR-SHL-020).
   * Nothing here writes a sentence — the server's `message_key` and its params
   * are what the clerk reads, which is the 2026-08-19 ruling (G32/G33).
   */
  async function post(action: () => Promise<unknown>): Promise<FormSubmitOutcome> {
    try {
      await action();
      await detailQuery.refetch();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return {
          ok: false,
          error: {
            code: error.code ?? "UNEXPECTED",
            message_key: error.messageKey,
            params: error.params,
            field_errors: error.fieldErrors.map((row) => ({
              field: row.field ?? "",
              message_key: row.message_key,
              params: row.params,
            })),
            ...(error.brRef === null ? {} : { br_ref: error.brRef }),
            ...(error.traceId === null ? {} : { trace_id: error.traceId }),
          },
        };
      }
      return {
        ok: false,
        error: { code: "UNEXPECTED", message_key: UNEXPECTED_ERROR_KEY },
      };
    }
  }

  if (detailQuery.isLoading) {
    return <LoadingSkeleton variant="card" />;
  }
  const detail = detailQuery.data;
  if (detail === undefined) {
    return (
      <p role="alert" className="text-sm text-danger-500">
        {t("customers.serviceRequest.detail.loadFailed")}
      </p>
    );
  }

  const working = mutate.isPending;
  const available = detail.actions.available;
  /**
   * **THE ONE FEE ROW A WAIVE FROM THE HEAD COULD MEAN — `DEF-CUS-6096`.**
   *
   * `POST …/fees/{id}/waive` acts on ONE row and is addressed by that row's
   * UUID, never by `line_no`. Where a request carries exactly one unwaived,
   * unsettled line — which is every application fee this product raises today
   * — the head's `Waived` option is unambiguous and this is the row. Where it
   * carries several, this is `null`, **the choice is not offered at all**, and
   * the per-line waive inside the fee disclosure stays the door: a modal with
   * no line named could only guess which one the clerk meant, and guessing
   * which fee to write off is not a guess this product may make.
   */
  const waivableLines = detail.fees.lines.filter(
    (line) => !line.waived && line.settled_at === null,
  );
  /**
   * The row a waive would land on: the one the clerk POINTED AT if they used
   * the per-line control, else the only lawful candidate if there is exactly
   * one. `null` means the `Waived` option is not offered from the head at all
   * — guessing which fee to write off is not a guess this product may make.
   */
  const waivableLineId =
    waiveTarget ?? (waivableLines.length === 1 ? (waivableLines[0]?.id ?? null) : null);
  /**
   * BR-SHL-025 — a control this state cannot honour is DISABLED WITH ITS
   * REASON, never hidden. The reason is the STATE's and is true of it; see
   * `requestControlReasonKey` for what each one says and why the one constant
   * that stood here before was false on four states out of six.
   *
   * ⚠ **`working` DOES NOT PRODUCE A REASON.** A button greyed for the second
   * a post is in flight has nothing to tell anybody, and a sentence appearing
   * and vanishing under the cursor would be noise. Reasons answer the STATE.
   */
  const reasonWhenDead = (control: RequestControl, live: boolean): string | undefined =>
    live ? undefined : t(requestControlReasonKey(control, detail.header.state));

  /** §8 — the `←`'s destination and its name, from the request's own outcome. */
  const backTo = requestBackDestination(detail.header);

  // ══════════════════════════════════════════════════════════════════════
  // THE ACTION BAR IS DRIVEN BY STATE — PO ratification 2026-09-20 §1
  // ══════════════════════════════════════════════════════════════════════
  //
  // The PO's table, quoted from the decision log entry they ratified in the
  // words *"this is correct - fix it"*:
  //
  //     | State            | Submit | Approve | Ask for more | Refuse | Park |
  //     | Draft            | ✅ only lawful action | ✗ | ✗ | ✗ | ✗ |
  //     | Submitted        | ✗ | ✅ | ✅ | ✅ | ✅ (→ Under review) |
  //     | Under review     | ✗ | ✅ | ✅ | ✅ | ✗ |
  //     | More info needed | ✗ | ✅ | ✅ | ✅ | ✗ |
  //     | Approved         | ✗ | ✗ | ✗ | ✗ | ✗ |
  //     | Refused          | ✗ | ✗ | ✗ | ✗ | ✗ |
  //
  // ⚠ **THE FIRST FOUR COLUMNS ARE ALREADY THE SERVER'S ANSWER AND ARE NOT
  // RESTATED HERE.** `service_request.TRANSITIONS` yields exactly this for
  // `submit` / `approve` / `refuse` / `request_info`, and it arrives as
  // `actions.available`. A second copy of the table in this file is how two
  // screens come to disagree — so the only thing this file decides is the
  // TIER and the REASON.
  //
  // ⚠ **THE PO'S OWN WORDS FOR WHAT WAS WRONG:** *"this is draft version of
  // request - it does not allow me to submit"*. A draft offered Refuse, Ask
  // for more, Park and Approve — all four unlawful from `draft` — and had no
  // Submit control anywhere on the page.
  // The state words are `SERVICE_REQUEST_STATES`', mirrored from
  // `apps/customers/models.ServiceRequest` — never a second vocabulary.
  const isDraft = detail.header.state === "draft";

  /**
   * ⚠ **THE PRIMARY MOVES WITH THE STATE, AND BOTH BUTTONS ARE ALWAYS DRAWN.**
   * B14 rule 4 allows a screen exactly one primary, and BR-SHL-025 forbids
   * hiding a control a state cannot honour. Those two together decide it: on a
   * DRAFT the one lawful action is `Submit`, so `Submit` takes the primary
   * slot and `Approve` stands in the secondary row, disabled with its reason;
   * everywhere else `Approve` is the primary and `Submit` is the disabled
   * secondary. Five controls, always five, one primary.
   *
   * **Submit is not a dialog.** The three decisions each open one because each
   * needs something written down — a reason, a checklist, an outcome. Submit
   * needs nothing and asks nothing: it is the clerk saying *this is ready*, and
   * a confirmation over it would be a rule-11 consequence preview for an act
   * with no consequence to preview.
   */
  const submitButton = (
    <DecisionButton
      label={t("customers.serviceRequest.action.submit")}
      variant={isDraft ? "primary" : "secondary"}
      testId="submit"
      disabled={!available.includes("submit") || working}
      reason={reasonWhenDead("submit", available.includes("submit"))}
      onClick={() => mutate.mutate(() => submitServiceRequest(requestId, client))}
    />
  );

  /**
   * ⚠ **THE DRAWING GREYS THIS BUTTON AND WE GREY THE MODAL'S COMMIT INSTEAD,
   * WHICH IS THE SAME REFUSAL SAID WHERE IT CAN BE READ.** p082 greys
   * `Approve` because two documents are unchecked, and p084 greys `Approve and
   * raise the build` for the same reason — one block drawn twice. A greyed head
   * button carries its reason only in a `title`, which is a mouse: unreachable
   * by keyboard, invisible on touch, and unread by a clerk who is on the phone.
   * `FormModal`'s `commitBlocked` puts it in words beside the button and
   * announces it (BR-SHL-025). So the head opens the dialog whenever the STATE
   * allows approving, and the dialog is where the document gate speaks.
   * Recorded as a divergence in the conformance file.
   *
   * ⚠ **IT IS A NAMED ELEMENT RATHER THAN AN INLINE SLOT SINCE 2026-09-20**,
   * because the primary slot is the STATE's, not this control's — see
   * `submitButton` above.
   */
  const approveButton = (
    <DecisionButton
      label={t("customers.serviceRequest.action.approve")}
      variant={isDraft ? "secondary" : "primary"}
      testId="approve"
      disabled={!available.includes("approve") || working}
      reason={reasonWhenDead("approve", available.includes("approve"))}
      onClick={() => {
        setCategoryNeededAtOpen(detail.applicant.category_to_be_set === true);
        setApprove(true);
      }}
    />
  );

  return (
    <div>
      {/* ══════════════════════════════════════════════════════════════════
          THE HEAD IS THE BLUEPRINT'S, READ OFF THE PAGE IMAGE — p082/p083 at
          scale 2 (B14 rule 42). The drawing, quoted:

              ← The register
              REQUEST SR-26-0001 · NEW CONNECTION
              Miller, Sarah                    [Refuse] [Ask for more] [Approve]
              Submitted   Waiting on documents   Counter   Received 05/04/2026
              ⌂ 212 Balcones Drive · Unit 3 · Austin, TX 78704

          ⚠ **THE FOUR BUTTONS, AND WHY PARK IS THE FOURTH.** The drawing draws
          three. The PO added Park on 2026-09-15 *after being told what removing
          it would cost* — it is the only thing in the product that sets the
          register's WAITING ON column — so it stays, and it is a CHANGE rather
          than defect work, recorded as such.

          ⚠ **`Save & exit` AND `Decide what this is` ARE GONE**, by the same
          ruling. The second became the Approve modal, which is why the head has
          no primary that merely navigates: a button whose whole job was to move
          the clerk to another tab is not a decision.

          ⚠ **THE ADDRESS LINE IS COMPOSED HERE.** Two facts make it and they
          arrive as two — what the applicant typed, and the matched premises'
          own locality — because the blueprint punctuates the same line two ways
          on two frames, so the punctuation is an illustration (rule 37).
          ══════════════════════════════════════════════════════════════════ */}
      <PageHeader
        kicker={
          detail.header.request_no === null
            ? t("customers.serviceRequest.detail.kicker")
            : t("customers.serviceRequest.detail.kickerWithType", {
                number: detail.header.request_no,
                type: t(`customers.serviceRequest.type.${detail.header.classification}`, {
                  defaultValue: t("customers.serviceRequest.type.notYetClassified"),
                }),
              })
        }
        title={
          detail.header.applicant ??
          detail.header.request_no ??
          t("customers.serviceRequest.detail.untitled")
        }
        backTo={{
          to: tenantPath(backTo.to),
          label: t(backTo.labelKey),
          testId: "request-back",
        }}
        /* ⚠ **FOUR CHIPS, IN THE DRAWING'S ORDER — p082/p083 read as images
           (B14 rule 42).** State · waiting on · channel · received. Until
           today only the STATE was a chip: the waiting-on was **missing from
           this screen entirely** while being the one column the register
           leads on, and the channel and the date were grey text a clerk's eye
           slid past. `PageHeader` renders `status` as its chip row, which is
           where the drawing puts all four.

           ⚠ **WAITING ON IS NOT A STATE AND THE CHIPS SAY SO BY SITTING SIDE
           BY SIDE.** p082's own annotation: *"SR-26-0046 is Approved AND
           waiting on a scheduled date"*. Two chips, two facts. */
        status={
          <>
            <RequestStatePill state={detail.header.state} t={translate} />
            {detail.header.waiting_on !== null && detail.header.waiting_on !== "" && (
              <RequestHeadChip tone="waiting" testId="waiting-on" waitingOn={detail.header.waiting_on}>
                {t("customers.serviceRequest.detail.waitingOnPrefix", {
                  what: t(`customers.serviceRequest.waitingOn.${detail.header.waiting_on}`, {
                    defaultValue: detail.header.waiting_on,
                  }),
                })}
              </RequestHeadChip>
            )}
            {detail.header.channel !== null && detail.header.channel !== "" && (
              <RequestHeadChip tone="channel" testId="channel" channel={detail.header.channel}>
                {t(`customers.serviceRequest.channel.${detail.header.channel}`, {
                  defaultValue: detail.header.channel,
                })}
              </RequestHeadChip>
            )}
            {detail.header.received_at !== null && detail.header.received_at !== "" && (
              <RequestHeadChip tone="neutral" testId="received">
                {t("customers.serviceRequest.detail.received")}{" "}
                <DateCell
                  value={detail.header.received_at}
                  timeZone={timeZone}
                  dateFormat={dateFormat}
                />
              </RequestHeadChip>
            )}
          </>
        }
        rollup={
          <span className="flex flex-col gap-1">
            <span className="flex flex-wrap items-baseline gap-3">
              {/* The number keeps its stated absence. A draft with no number
                  yet says so; it does not silently print nothing. */}
              {detail.header.request_no === null && (
                <RequestNumber
                  requestNo={detail.header.request_no}
                  absence={detail.header.number_absence}
                  t={translate}
                />
              )}
            </span>
            {/* ══════════════════════════════════════════════════════════
                **THE HEAD SHOWS THE WHOLE ADDRESS — PO report 2026-09-22,
                row 13.**

                The PO read **`SCW-U-301 · Silver Creek, TX 78611`** under the
                applicant's name and asked where the street was. It was never
                there: this line composed `address_unit_as_given ??
                address_as_given`, and `??` PREFERS the unit — so on every
                request where a clerk typed a unit label, the street line was
                the thing that fell away. The town and the ZIP came from the
                matched premises and looked complete, which is why nobody saw
                it go.

                ⚠ **`resolved_premise_address` IS WHAT A MATCHED REQUEST
                SHOWS, AND THAT IS A RULING RATHER THAN A PREFERENCE.** PO,
                2026-09-22: *"correct address will be on presmies but first
                time you will ahve to take the details to match it"*, and the
                decision-log entry of that day says it in as many words —
                **once `premises_id` is set, the premises' address is what
                every screen shows**. The entry is titled *A REQUEST TAKES THE
                ADDRESS IN PARTS SO IT CAN FIND THE PREMISES*.

                ⚠ **AND WHAT THE APPLICANT SAID IS NOT LOST.** `Their address`
                on the Applicant tab still prints `address_as_given` byte for
                byte beside the match (`BR-CUS-070`, TC-REQ-6). The head shows
                the address of RECORD; the tab shows the STATEMENT and the
                match side by side, which is the whole point of keeping both.

                ⚠ **UNMATCHED IS A REAL STATE AND FALLS BACK TO THE
                STATEMENT.** A new connection at a field with nothing on record
                is the job this wizard exists for; there the applicant's own
                line is the only address there is, and the unit label rides
                with it rather than replacing it.
                ══════════════════════════════════════════════════════════ */}
            <span className="text-sm text-neutral-700" data-head-address="">
              <TextOrNotSupplied
                value={composeAddressLine(
                  // DEF-CUS-10705 — the matched apartment rides after the
                  // street of record (p082 `· Unit 3 ·`); a house draws none.
                  streetWithUnit(
                    detail.location_and_services.resolved_premise_address,
                    detail.location_and_services.resolved_unit_id
                      ? detail.location_and_services.resolved_unit_label
                      : null,
                    detail.location_and_services.resolved_premises_units,
                    translate,
                  ) ??
                    ([detail.header.address_as_given, detail.header.address_unit_as_given]
                      .map((part) => (part ?? "").trim())
                      .filter((part) => part !== "")
                      .join(", ") ||
                      null),
                  detail.header.premise_locality,
                )}
                t={translate}
              />
            </span>
          </span>
        }
        leadingAction={
          <DecisionButton
            label={t("customers.serviceRequest.action.refuse")}
            variant="danger"
            testId="refuse"
            disabled={!available.includes("refuse") || working}
            reason={reasonWhenDead("refuse", available.includes("refuse"))}
            onClick={() => setRefuse(true)}
          />
        }
        secondaryActions={
          <>
            {/* CR-171-BRC10 P2.38 — a MOVE-IN request also lives on the Move-ins
                details view (`/moves/SR-…`, images 03–08), where it is approved,
                asked and declined in its own words. One request, two doors (S3);
                `MoveInDetail.dom.test.tsx` holds the address. */}
            {detail.header.classification === "move_in" && detail.header.request_no ? (
              <ButtonLink
                variant="ghost"
                to={tenantPath(moveRecordPath(detail.header.request_no))}
                data-testid="request-open-in-move-ins"
              >
                {t("customers.moveDetail.openInMoveIns")}
              </ButtonLink>
            ) : null}
            {/* `Edit` (or `Resume` on a draft) — `DEF-CUS-6427`, PO 2026-09-23:
                *"there is no edit available on … detail view"*. Absent, not
                greyed, once the request is decided: see
                `serviceRequestEditDoor.tsx`. */}
            <RequestEditButton requestId={requestId} state={detail.header.state} t={translate} />
            {/* ⚠ **SUBMIT STANDS HERE WHENEVER IT IS NOT THE PRIMARY.** The
                drawing's bar is `Refuse · Ask for more · Approve` and Submit is
                not in it, because p082 draws a SUBMITTED request and a
                submitted request cannot be submitted. It is first in the
                secondary row because it is first in the request's life — and it
                is drawn at all, rather than hidden on the five states that
                cannot honour it, because BR-SHL-025 says a control a state
                cannot honour is disabled with its reason. */}
            {!isDraft && submitButton}
            <DecisionButton
              label={t("customers.serviceRequest.action.request_info")}
              variant="secondary"
              /* ⚠ **`request_info`, NOT `ask` — THE SERVER'S OWN ACTION NAME.**
                 Everything that decides this control reads
                 `actions.available`, whose words come from
                 `service_request.TRANSITIONS`. The attribute read `ask` and
                 nothing else on the screen did, so a check written against the
                 action list looked for `request_info`, found nothing, and
                 reported a MISSING CONTROL over a control that was on screen. */
              testId="request_info"
              disabled={!available.includes("request_info") || working}
              reason={reasonWhenDead("request_info", available.includes("request_info"))}
              onClick={() => setAsk(true)}
            />
            {/* Kept on the PO's explicit ruling. It records WHAT is being
                waited for, a note and a reminder, and it is what surfaces on
                the register's WAITING ON column. */}
            <DecisionButton
              label={t("customers.serviceRequest.action.park")}
              variant="secondary"
              testId="park"
              disabled={!detail.actions.can_park || working}
              reason={reasonWhenDead("park", detail.actions.can_park)}
              onClick={() => setPark(true)}
            />
            {/* The twin of the line above: on a DRAFT the primary slot is
                Submit's, so Approve stands here, disabled, in the position the
                eye already expects it. */}
            {isDraft && approveButton}
          </>
        }
        primaryAction={isDraft ? submitButton : approveButton}
        tabsLabel={t("customers.serviceRequest.detail.tabsLabel")}
        activeTabId={tab}
        onTabSelect={(next) => setSearch({ tab: next.id }, { replace: true })}
        tabs={REQUEST_TABS.map((id) => ({
          id,
          label: t(`customers.serviceRequest.tab.${id}`),
        }))}
      />

      {outcomeNote !== null && (
        <DecisionOutcomeNote job={outcomeNote.job} message={outcomeNote.message} t={translate} />
      )}
      {/* `DEF-CUS-6350` — *Approved → Move-in MVI-26-0115*, read back from the
          server on every load and linking to the job by its number. */}
      <ServiceRequestJobLink
        job={detail.header.job}
        t={translate}
        requestId={detail.header.id}
        premisesId={detail.location_and_services.resolved_premises_id}
        premisesUnits={detail.location_and_services.resolved_premises_units}
        masterAllowed={detail.location_and_services.resolved_premises_master_allowed}
      />

      {/* ⚠ **THE REFUSAL A ROW ACTION USED TO SWALLOW — `DEF-CUS-6096`.**
          `role="alert"` on purpose: the control that raised it is a small icon
          inside a collapsed disclosure, so a clerk's eyes are not here and a
          `status` would be announced too quietly to reach them. */}
      {actionError !== null && (
        <RefusalStrip role="alert" className="mt-4" data-action-error="">
          {refusalText(translate, actionError)}
        </RefusalStrip>
      )}
      {/* CR-183-BRC10 B2 — the field visit could not be booked; the hold
          stands (BR-WRK-055) and the clerk is told, in Work's own words. */}
      {fieldVisitWarning !== null && (
        <RefusalStrip role="status" className="mt-4" data-field-visit-warning="">
          {translate(fieldVisitWarning)}
        </RefusalStrip>
      )}

      {tab === "applicant" && (
        <ApplicantTab
          detail={detail}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          working={working}
          requestId={requestId}
          client={client}
          onCollect={() => {
            setWaiveTarget(null);
            setCollectKind("taken");
            setCollect(true);
          }}
          /* ⚠ **THE PER-LINE WAIVE OPENS THE MODAL AND NO LONGER POSTS BLIND.**
             It used to fire `waiveServiceRequestFee` on the spot with
             `fees.defaultWaiveReason` — one hardcoded English sentence on every
             waiver in the product's history. It now names its line and hands
             the clerk the tenant's own reasons (PO ruling 2026-09-22). The
             address is still the row's UUID and never `line_no`
             (`DEF-CUS-6096`); what changed is where the REASON comes from. */
          onWaive={(feeId) => {
            setWaiveTarget(feeId);
            setCollectKind("waived");
            setCollect(true);
          }}
          feeCodes={feeCodes}
          pickedFeeCode={pickedFeeCode}
          onPickFeeCode={(code) => {
            setPickedFeeCode(code);
            setFeeAddRefusal(null);
          }}
          /* ⚠ **THE REFUSAL LANDS ON THE PANEL THAT OWNS THE FIELD**, which is
             layer 2 of the PO's 2026-09-21 ruling: a picker filtered when the
             screen mounted cannot know that a tenant edited the code on
             Settings since, so *"the commit must still catch the rule error
             and answer with words"*. `mutate` would put it in the page-level
             strip above the tabs; this keeps it beside the dropdown. */
          onAddFee={() => {
            const row = feeCodes.find((candidate) => candidate.code === pickedFeeCode);
            if (row === undefined) return;
            setFeeAddRefusal(null);
            void (async () => {
              try {
                // `unit_amount` is the STORED four-place string, never
                // `amount_display` — that one is rounded for a person to read
                // and this one is what a customer is charged (rule 2).
                await addServiceRequestFee(
                  requestId,
                  {
                    charge_code: row.code,
                    charge_code_id: row.id,
                    unit_amount: row.amount ?? "0",
                    quantity: "1",
                    description: row.name,
                  },
                  client,
                );
                setPickedFeeCode("");
                await detailQuery.refetch();
              } catch (error) {
                setFeeAddRefusal(refusalText(translate, error));
              }
            })();
          }}
          feeAddRefusal={feeAddRefusal}
          feeCatalogueAnswered={(feeChargesQuery.data?.results ?? []).length > 0}
        />
      )}
      {tab === "documents" && (
        <DocumentsTab
          detail={detail}
          t={translate}
          working={working}
          onVerify={(documentId) =>
            mutate.mutate(() => verifyServiceRequestDocument(requestId, documentId, client))
          }
          onReject={(documentId) =>
            mutate.mutate(() =>
              rejectServiceRequestDocument(
                requestId,
                documentId,
                t("customers.serviceRequest.documents.defaultRejectReason"),
                client,
              ),
            )
          }
          // ⚠ **THE HOST OWNS THE ROUTE AND THE REFUSAL, THE KIT OWNS THE
          // OPEN.** Same split the capture step already uses, so one opener
          // serves both screens and neither names the other's endpoint.
          onOpen={(documentId) => {
            void openRequestDocument(documentId);
          }}
          onDownload={(documentId) => {
            openDocumentContent(
              `/service-requests/${requestId}/documents/${documentId}/content`,
              "download",
            );
          }}
          timeZone={timeZone}
          dateFormat={dateFormat}
          openingId={docOpeningId}
          openError={docOpenError}
        />
      )}
      {tab === "history" && (
        <HistoryTab
          detail={detail}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          working={working}
          onAddNote={(note) =>
            mutate.mutate(() => addServiceRequestNote(requestId, { note }, client))
          }
        />
      )}

      {/* ── APPROVE — p083/p084, rebuilt as the kit window the PO approved
          on 2026-09-23 (`DEF-CUS-6350`). The window is its own component
          (B14 rule 43); this block only mounts it and says where the clerk
          lands. ─────────────────────────────────────────────────────── */}
      {/* ── CR-183-BRC10 T3 — a TEMPORARY STOP (or its *Restart now*) has its
          own window: account, dates, base charge only, *Field visit needed*.
          New connection and Move-in are not offered for it (the PO's report
          on SR-26-0017), and the server refuses both by name. ─────────── */}
      {approve && detail.temporary_stop != null && (
        <TemporaryStopApproveModal
          detail={detail}
          stop={detail.temporary_stop}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          onClose={() => setApprove(false)}
          onSubmit={(choice) =>
            post(async () => {
              const answer = await approveTemporaryStop(
                requestId,
                {
                  ...(choice.stopFrom !== undefined ? { stop_from: choice.stopFrom } : {}),
                  ...(choice.restartOn !== undefined ? { restart_on: choice.restartOn } : {}),
                  field_visit_needed: choice.fieldVisitNeeded,
                },
                client,
              );
              setOutcomeNote({ message: null });
              setFieldVisitWarning(answer.temporary_stop_result.warnings[0]?.message_key ?? null);
            }).then((result) => {
              // The window closes on success, as the job Approve does.
              if (result.ok) setApprove(false);
              return result;
            })
          }
        />
      )}
      {approve && detail.temporary_stop == null && (
        <ApproveChecksModal
          detail={detail}
          t={translate}
          working={working}
          /* ⊕ `DEF-CUS-10251` — *Category to be set* on a portal request: the
             pick is saved through the request's own category door at once. */
          categoryPicker={
            <RequestCategoryToSet
              detail={detail}
              t={translate}
              needed={categoryNeededAtOpen}
              categories={approveCategories.selectable}
              subtypeRows={approveSubtypes.rows}
              working={working}
              onSet={(code, subtypeId) =>
                mutate.mutate(() =>
                  setServiceRequestCategory(
                    requestId,
                    {
                      account_type_code: code,
                      ...(subtypeId === "" ? {} : { account_subtype_id: subtypeId }),
                    },
                    client,
                  ),
                )
              }
            />
          }
          /* *Same property* — the capture pick, through the capture door. The
             server then refuses a new connection there BY NAME. */
          onSameProperty={(premisesId) =>
            mutate.mutate(() =>
              patchServiceRequest(requestId, { picked_premises_id: premisesId }, client),
            )
          }
          /* ⊕ `DEF-CUS-9043` — LINK a customer on file. The same door as
             *Record that I searched*, with the customer named and the tier
             the decision log of 2026-10-02 records (`strong`). */
          customerLink={
            <RequestCustomerLink
              t={translate}
              client={client}
              requestId={requestId}
              timeZone={timeZone}
              dateFormat={dateFormat}
              working={working}
              /* ⚠⚠ **LOAD-BEARING: *No match* is the only control that
                 records a search with no prior customer, and without it a
                 first-time applicant can never be approved**
                 (`ARREARS_NOT_SEARCHED`). PO 2026-10-11, option B — it was the
                 Arrears row's *Record that I searched*. */
              onNoMatch={() =>
                // `customer_id: null` = *searched, and there is no prior customer*.
                mutate.mutate(() =>
                  linkServiceRequestCustomer(requestId, { customer_id: null }, client),
                )
              }
              onLink={(customerId) =>
                mutate.mutate(() =>
                  linkServiceRequestCustomer(
                    requestId,
                    { customer_id: customerId, tier: "strong" },
                    client,
                  ),
                )
              }
            />
          }
          onClose={() => setApprove(false)}
          onSubmit={(outcome, choice) =>
            post(async () => {
              // ONE post — the outcome travels WITH the approval and the server
              // writes both or neither (`DEF-CUS-5427`).
              const answer = await approveServiceRequest(requestId, undefined, client, outcome, {
                addressIsNew: choice.addressIsNew,
                // ⊕ `CR-161-BRC10` W6 — R5's pick travels with the approval.
                customFieldPicks: choice.customFieldPicks,
              });
              setOutcomeNote({ job: answer.job, message: null });
              // ══════════════════════════════════════════════════════════
              // WHERE THE CLERK LANDS — PO 2026-09-23 (`OQ-CUS-12616`):
              // *"My recommendation: yes - we agreed"*. Both kinds land on the
              // job just created; a job that could NOT be raised keeps the
              // clerk here, reading why (`DecisionOutcomeNote`).
              // ══════════════════════════════════════════════════════════
              const raised = answer.job?.raised;
              if (raised === undefined) return;
              // A NEW CONNECTION opens the build's own wizard, exactly as it did
              // (`DEF-CUS-6109`, blueprint p089's *"Next · The build's own
              // wizard asks for units, services, plans and charges"*).
              if (raised.kind === "connection" && raised.id !== "") {
                navigate(
                  tenantPath(`${NEW_CONNECT_ROUTE}?build=${encodeURIComponent(raised.id)}`),
                );
                return;
              }
              // ══════════════════════════════════════════════════════════
              // A MOVE-IN OPENS THE MOVE-IN WIZARD, CARRYING THIS REQUEST
              // (`DEF-CUS-7900`, PO 2026-09-29) — IT USED TO OPEN THE RECORD
              // ══════════════════════════════════════════════════════════
              // PO, verbatim: *"when user select the move-in user should
              // redirect on move-in list page or move-in request form; on list
              // view draft request should be open in move in -wizard form"*.
              // **One rule across three links: an UNFINISHED move-in opens the
              // WIZARD, a FINISHED one opens the RECORD.** A job raised half a
              // second ago is as unfinished as a move-in gets — it has no
              // account, no move-in date and no opening reading — so the record
              // was a page about something that has not happened, which is the
              // same complaint the Move-ins list drew (`MoveInsTab`'s reference
              // cell, fixed in this commit).
              //
              // ⚠ **THIS NARROWS `OQ-CUS-12616` (PO 2026-09-23, *"My
              // recommendation: yes - we agreed"*) AND DOES NOT REVERSE IT.**
              // That ruling says the clerk lands ON THE JOB JUST CREATED rather
              // than staying on the request, and this still does — it lands on
              // the job's WORK rather than on its filing card. The new
              // connection's half is untouched and still opens its build's
              // wizard, which is the symmetry the two kinds never had: same
              // dialog, same act, and until today two different kinds of
              // destination.
              //
              // ⚠⚠ **AND THE BACKEND HAS BEEN WAITING FOR THIS EXACT DOOR.**
              // `apps/customers/move_in_jobs.py` §3: *"A clerk who opens the
              // account by another door passes no request, so nothing closes
              // the job and it stays here beside the draft account it
              // produced … closing it needs the move-in wizard opened FROM the
              // job."* It served `PENDING_JOB_CLOSES_ON_THE_RECORDED_MOVE` on
              // every Move-ins response rather than leave a clerk to notice.
              // `?request=` IS that door: `MoveInWizard` reads it
              // (`REQUEST_PARAM`, `CR-122-BRC06`), prefills step 2 from the
              // application and posts `service_request_id`, which is what
              // `moves.record_move` closes the job on. **The wizard read that
              // parameter and NOTHING IN THE PRODUCT PASSED IT** — hard-won law
              // 2, built and not wired, with the one screen that should have
              // opened the door pointing at a record instead.
              //
              // ⚠ **NO `move_no` FALLBACK ANY MORE, AND ITS ABSENCE IS THE
              // POINT.** The old branch needed one because a RECORD can only be
              // addressed by a number and a tenant that keeps no `move_in`
              // series has none; it sent that clerk to the Move-ins tab to hunt
              // for the row. The wizard is addressed by the REQUEST, which this
              // page always has (`:requestId` is in its own route), so the
              // no-series tenant now lands on exactly the same screen as
              // everybody else. The condition that required a fallback is gone
              // rather than unhandled — decision log, 2026-09-29.
              if (raised.kind === "move_in") {
                navigate(
                  tenantPath(
                    `${MOVE_IN_WIZARD_ROUTE}?${REQUEST_PARAM}=${encodeURIComponent(requestId)}`,
                  ),
                );
              }
            }).then((result) => {
              if (result.ok) {
                setApprove(false);
              }
              return result;
            })
          }
        />
      )}

      {/* ── REFUSE — p084/p085 ──────────────────────────────────────────── */}
      {refuse && (
        <RefuseModal
          detail={detail}
          t={translate}
          onClose={() => setRefuse(false)}
          onSubmit={(input) =>
            post(async () => {
              const answer = await refuseServiceRequest(requestId, input, client);
              setOutcomeNote({ message: answer.applicant_message ?? null });
            }).then((result) => {
              if (result.ok) {
                setRefuse(false);
              }
              return result;
            })
          }
        />
      )}

      {/* ── ASK FOR MORE — p085/p086 ────────────────────────────────────── */}
      {ask && (
        <AskForMoreModal
          detail={detail}
          t={translate}
          onClose={() => setAsk(false)}
          onSubmit={(input) =>
            post(async () => {
              const answer = await transitionServiceRequest(
                requestId,
                "request_info",
                input.reason,
                client,
                undefined,
                {
                  info_needed: input.info_needed,
                  message_to_applicant: input.message_to_applicant,
                },
              );
              setOutcomeNote({ message: answer.applicant_message ?? null });
            }).then((result) => {
              if (result.ok) {
                setAsk(false);
              }
              return result;
            })
          }
        />
      )}

      {/* ── PARK ─────────────────────────────────────────────────────────── */}
      {park && (
        <FormModal
          title={t("customers.serviceRequest.park.title")}
          schema={PARK_SCHEMA}
          values={{ waiting_on: waitingOn, note: parkNote, remind_on: remindOn }}
          submitLabel={t("customers.serviceRequest.park.submit")}
          onClose={() => setPark(false)}
          onSubmit={() =>
            post(() =>
              parkServiceRequest(
                requestId,
                {
                  waiting_on: waitingOn.trim(),
                  note: parkNote.trim() === "" ? undefined : parkNote.trim(),
                  remind_on: remindOn === "" ? undefined : remindOn,
                },
                client,
              ),
            ).then((outcome) => {
              if (outcome.ok) {
                setPark(false);
              }
              return outcome;
            })
          }
        >
          <TextField
            id="waiting_on"
            label={t("customers.serviceRequest.park.waitingOn")}
            required
            value={waitingOn}
            onChange={setWaitingOn}
          />
          <TextField
            id="note"
            label={t("customers.serviceRequest.park.note")}
            help={t("customers.serviceRequest.park.noteHelp")}
            value={parkNote}
            onChange={setParkNote}
          />
          <DatePickerField
            id="remind_on"
            label={t("customers.serviceRequest.park.remindOn")}
            value={remindOn}
            onChange={setRemindOn}
            dateFormat={dateFormat}
          />
          <p className="max-w-prose text-sm text-neutral-700">
            {t("customers.serviceRequest.park.everythingStays")}
          </p>
        </FormModal>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          **`Record what was handed over` — TAKEN or WAIVED (PO ruling
          2026-09-22, `BR-CUS-090`).**

          PO, verbatim, with this modal open on `SR-26-0011`: *"on modal you
          ahve to give Waive off button"*, then *"button or options"*.

          ⚠ **OPTIONS AT THE HEAD, NOT A THIRD FOOTER BUTTON — and the reason
          is the FIELDS rather than taste.** `Taken` asks for an amount, a
          tender and a receipt and all three are REQUIRED; a waive has none of
          them. A footer button would leave three required money fields on
          screen that a waive must never fill, and a modal titled *what was
          handed over* cannot be submitted by somebody stating that nothing
          was. The title moves with the choice. Recorded in the decision log of
          2026-09-22 because the PO offered the choice and a judgment call is
          ours to make and write down.

          ⚠ **IT IS REUSE, NOT A SECOND WAIVER (B14 rule 43).**
          `waive_fee_line(actor, fee_id, *, reason)` and
          `POST …/fees/{id}/waive` have existed since the fee lines did, and
          there is a per-line waive TODAY buried inside the fee disclosure
          behind `Expand` — which is why the PO could not find it. What is new
          is the DOOR and the REASON.

          ⚠ **THE REASON IS THE TENANT'S OWN, NOT A HARDCODED SENTENCE.** Every
          waive this screen has ever performed sent
          `customers.serviceRequest.fees.defaultWaiveReason` — one English
          sentence, the same on every waiver, which makes the stored reason
          worth nothing to the person reading it back. The picker reads
          `/payments/reason-codes`, which is the clerk-facing door onto the
          tenant's own live reasons (`BR-TEN-036`); **it is NOT
          `/lookups/reason_codes`**, which is gated on the Settings role that
          `A4` gives a Billing Clerk no cell in.

          ⚠ **AN EMPTY LIST IS A REAL ANSWER** — a tenant may have deactivated
          every reason — and the picker stays empty rather than offering the
          seeds back, which is the posture `paymentsShared.reasonOptions`
          already takes. The commit is refused by the schema until a reason is
          chosen, so a waive cannot land unexplained.

          ⚠ **THE WAIVE IS ADDRESSED BY THE FEE ROW'S UUID — `DEF-CUS-6096`.**
          Sending `line_no` was a 500 this screen swallowed on every press
          until 2026-09-21. `line_no` is what a CLERK reads; `id` is what an
          ENDPOINT is addressed with, and they are not interchangeable.

          ⚠ **ONE LINE OR NOTHING.** The waive endpoint acts on ONE fee row.
          Where a request carries exactly one unwaived, unsettled line — which
          is every application fee this product raises today — that row is the
          subject. Where it carries several, the head offers `Taken` alone and
          the per-line waive inside the disclosure is the door, because a modal
          with no line named could only guess which one the clerk meant.
          ══════════════════════════════════════════════════════════════════ */}
      {collect && (
        <RequestFeeHandoverModal
          requestId={requestId}
          client={client}
          fees={detail.fees}
          waivableLineId={waivableLineId}
          initialKind={collectKind}
          timeZone={timeZone}
          dateFormat={dateFormat}
          onClose={() => {
            setCollect(false);
            setWaiveTarget(null);
          }}
          onDone={() => detailQuery.refetch()}
        />
      )}

      {/* ⚠ **THE BOTTOM ACTION ROW IS DELETED — PO ruling 2026-09-19.**
          It rendered a `<Button>` for every move in the server's
          `actions.available`, which is where `Withdraw` and `Close by hand`
          came from. The PO opened `SR-26-0010` beside the drawing and asked
          why they were there; **neither word appears once in the blueprint's
          242 pages.** The head's four buttons are the whole action set —
          *"we only have 3 refuse, ask for more and approve"* plus Park, which
          the PO added knowingly on 2026-09-15 because nothing else writes the
          register's WAITING ON column.

          ⚠ **THIS ROW IS WHY THE LAST REBUILD DID NOT FIX THE PAGE.** On
          2026-09-15 a lane rebuilt the HEAD to the drawing and changed exactly
          one line of this block — widening a filter so `request_info` would
          not appear twice. `withdraw` and `manual_close` were never in its
          scope, so they survived a rebuild of the screen they sit on. A
          control that no longer matches the drawing is invisible to every
          check this repository has (hard-won law 6), and it outlives any lane
          whose scope stopped above it. */}

      {/* ⚠ **THE ROUTE MODAL IS DELETED WITH THE ROW THAT OPENED IT — PO
          ruling 2026-09-19.** Nothing else ever set `routing`, so leaving it
          would have been a modal no press can reach: dead UI, which is what
          G13 and hard-won law 2 are both about.

          **Field work is not the request's act any more.** The PO, verbatim:
          *"once requets is approved then in move in or new connect we take
          all those decision to in fulfill etc"* — the approval raises a JOB,
          and the job is where somebody is sent. `route` leaves the request's
          state table with the other eight, and `in_fulfilment` stops being a
          state a request can reach. */}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W4 task 4.12 (+ three of 4.13's four) · B19 §12.2/§12.3
// generated: 2026-08-24 by the CR-031 W4 FRONTEND lane (M3)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: tsc✔ eslint✔ vitest✔ · G13✔ G31✔ G37✔ G40✔
// exceptions: E3 **the seven-glyph icon rail B19 §12.2 draws is NOT built** —
//   BR-SHL-045 names the seven for the ACCOUNT detail (send statement, print
//   bill, issue credit, change plan, disconnect notice, payment plan, add note)
//   and none of the seven has a service-request endpoint behind it; a rail of
//   seven disabled glyphs would be seven reasons nobody asked for. REPORTED as
//   needing its own ruling · E3 the **quote builder** (task 4.13) is NOT built:
//   the server answers `connection_quote: {raised: false}` with no endpoint
//   behind it, so what exists is the application-fee half and the quote half
//   states its own absence · E3 **OQ-355 · OQ-356 · OQ-357 are rendered as
//   stated refusals carrying their id and are NOT resolved** · E3 the
//   `Manual close` reason and the document reject reason use catalogue
//   defaults rather than a prompt — both are ROUTES that exist and both want a
//   modal; only `refuse` and `park` got one this lane, and the rest are named
//   in the report
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
