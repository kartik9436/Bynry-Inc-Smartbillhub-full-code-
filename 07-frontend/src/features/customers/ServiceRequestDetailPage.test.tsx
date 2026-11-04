// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W4 task 4.15 — the `TC-REQ-*` cases with a FRONTEND surface,
//           for **S84 · REQ-02**. The cases are B18 §5.3.9's, declared before
//           this code existed (r11 step 2c).
// Rules:    BR-CUS-090 (the worked case: quoted $130.00, taken $25.00, receipt
//           RCP-26-4471 → $105.00 outstanding) · BR-CUS-091 · BR-CUS-092 ·
//           BR-CUS-095 · BR-CUS-089 · BR-CUS-070
// Questions: OQ-355 · OQ-356 · OQ-357 — asserted PRESENT AS REFUSALS, never
//           resolved
// ───────────────────────────────────────────────────────
//
// The assertions that matter most here are the NEGATIVE ones:
//   * the words "stored encrypted" must appear NOWHERE (BR-CUS-092(d));
//   * the Disconnect option must NOT be disabled and must NOT carry the
//     withdrawn reason (BR-CUS-091);
//   * a fee shortfall must NOT be drawn as a waiver or as a refusal;
//   * a fee line must NOT offer a working `remove` (OQ-357);
//   * the conditions panel must NOT print 5 (OQ-355).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { internalReferencesInMarkup } from "@/testSupport/internalReferences";

import "@/i18n";
import i18n from "@/i18n";

import {
  AddressBlock,
  ApplicantTab,
  AskedForBlock,
  DocumentsTab,
  HistoryTab,
  FeesBlock,
  WhoIsAskingBlock,
  COLLECT_SCHEMA,
  PARK_SCHEMA,
  REFUSE_SCHEMA,
  composeAddressLine,
  requestTabFromParam,
} from "./ServiceRequestDetailPage";
import { ApproveChecksModal } from "./ApproveChecksModal";
import {
  APPROVE_SCHEMA,
  AskForMoreModal,
  RefuseModal,
  askInternalReason,
  refusalInternalReason,
} from "./serviceRequestDecisions";
import type { Money, ServiceRequestDetail } from "./serviceRequestEndpoints";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function money(amount: string, display: string, currency: string | null = "USD"): Money {
  return { amount, display, currency };
}

/** `request_jobs.approval_preview(request, outcome)`, as wave 1 lane A published
 *  it. The BLOCKERS list is what the modal reads before the clerk commits. */
function preview(
  outcome: string,
  rows: { then: string; what: string; queue?: string; absence?: unknown }[],
  blockers: { code: string; br_ref?: string }[] = [],
): ServiceRequestDetail["decision"]["what_approving_will_do"][string] {
  return {
    outcome,
    known: true,
    creates: {
      kind: outcome,
      table: null,
      module: "customers",
      queue: `${outcome}s`,
      state_it_lands_in: null,
      raises_a_row: rows.some((row) => row.what === "job_is_raised_naming_this_request"),
      absence: null,
      blockers,
    },
    carries: null,
    rows,
    not_now: ["no_account_opens", "no_meter_is_fitted", "nothing_is_energised"],
  } as never;
}

/** The server's own six `unavailable` entries, abbreviated to the codes the
 *  screens address by name. The `detail` strings are the SERVER's sentences. */
const UNAVAILABLE = [
  {
    code: "applicant_identifier_needs_an_encryptor",
    br_ref: "BR-CUS-092 · OQ-016 (CLOSED)",
    detail:
      "The applicant's Social Security number and driving licence are not recorded " +
      "anywhere yet, not even the last four digits, because the secure storage they " +
      "need is still being built. Do not promise a customer that we hold them.",
  },
  {
    code: "no_customer_matcher",
    br_ref: "DEF-632 · DEF-638 · BR-CUS-089",
    detail:
      "Nothing matches an applicant to an existing customer automatically. Search for " +
      "them and link them yourself, so the person whose deposit or arrears may follow " +
      "them is one somebody has actually identified.",
  },
  {
    code: "fee_line_cannot_be_removed",
    br_ref: "OQ-357",
    detail:
      "A fee line cannot be deleted. Waive it instead, with a reason — the line stays " +
      "visible and the waiver is recorded against your name.",
  },
  {
    code: "fifth_approval_condition_unnamed",
    br_ref: "OQ-355",
    detail:
      "Four approval conditions are checked and listed. The design shows a fifth and " +
      "does not say what it is, so it is not counted here rather than being claimed as " +
      "checked.",
  },
];

/** REQ-02's `SR-26-0039`, as `reads.detail` serves it. */
function detail(over: Partial<ServiceRequestDetail> = {}): ServiceRequestDetail {
  return {
    header: {
      id: "sr-0039",
      request_no: "SR-26-0039",
      number_absence: null,
      state: "under_review",
      // §8 — the register tab an APPROVED request's work landed on. `null`
      // here because neither fixture is approved, which is also the value the
      // server serves for every unapproved request.
      queue: null,
      classification: "not_yet_classified",
      applicant: "Osei, Grace",
      address_as_given: "3450 Oak Ridge Dr",
      address_unit_as_given: null,
      // The blueprint draws the head's address line in full (p082). The town
      // is the matched PREMISES' fact, walked to — never a column on the
      // request (PO ruling 2026-09-15, CLAUDE.md hard rule 8).
      premise_locality: null,
      lookup_found: "Served, and the unit is vacant",
      received_at: "2026-08-08T09:00:00Z",
      received_by: "user-1",
      channel: "walk_in",
      waiting_on: "documents",
      waiting_since: "2026-08-21T09:00:00Z",
      requested_start: "2026-09-15",
    },
    actions: {
      available: ["approve", "refuse", "request_info", "withdraw", "manual_close"],
      can_approve: false,
      // ⛔ **`DEF-CUS-5064` — THE SERVER'S OWN VOCABULARY.** `CONDITION_KEYS`
      // (`service_request.py:397`) is `no_blocking_arrears · eligibility_-
      // evidence · documents_verified · fee_settled`, and those four are the
      // only ones with catalogue entries. This fixture said `documents`, so
      // the panel rendered `customers.serviceRequest.condition.documents` —
      // and the assertion below built its EXPECTED string from the same
      // unresolvable key, so both halves were broken and the test was green.
      // Read from `GET /api/brazosbend/service-requests/{id}` on `brazosbend`.
      approve_blocked_by: ["documents_verified"],
      can_park: true,
    },
    applicant: {
      name: "Osei, Grace",
      phone: "555-0142",
      email: "grace@example.test",
      language: "en",
      person_or_company: "person",
      co_applicant: { name: null, email: null, phone: null },
      // DEF-632 — B19 §7's own worked value: `••• ••• • 4471 · stored
      // encrypted`. FOUR CHARACTERS reach the browser; the payload has no
      // field that could carry more (BR-CUS-092(c)).
      // ⚠ **BR-CUS-092(a) FINISHED 2026-09-15** — the licence is a VALUE too,
      // and `TX ••••882` is the blueprint's own worked example (accounts
      // blueprint p076, step 1). FOUR CHARACTERS reach the browser for each
      // identifier; the payload has no field that could carry more.
      identifier: {
        ssn_last4: "4471",
        ssn_present: true,
        stored_encrypted: true,
        drivers_licence_last4: "4882",
        drivers_licence_present: true,
        drivers_licence_stored_encrypted: true,
      },
      // Served in FULL: a date of birth is not one of BR-CUS-092's two
      // identifiers (BR-CUS-1020) and nothing signed masks it.
      date_of_birth: "1988-03-14",
      acting_for_absence: { tracks: "DEF-638" },
      customer_match: {
        customer_id: null,
        tier: null,
        basis: null,
        confirmed_at: null,
        may_move_money: false,
      },
    },
    location_and_services: {
      address_as_given: "14 Willow Bend",
      address_unit_as_given: null,
      // PO ruling 2026-09-22 — what the applicant said, for MATCHING a
      // premises. Null here: this fixture's request is already matched.
      address_city_as_given: null,
      address_state_as_given: null,
      address_postal_code_as_given: null,
      units_on_property: null,
      billing_address_same: true,
      billing_address_as_given: null,
      billing_line1_as_given: null,
      billing_line2_as_given: null,
      billing_city_as_given: null,
      billing_state_as_given: null,
      billing_postal_code_as_given: null,
      resolved_premises_id: null,
      resolved_unit_id: null,
      // ⚠ **THIS FIXTURE RESOLVES TO NOTHING, SO IT CANNOT CATCH THE DEFECT ON
      // THIS TAB.** `DEF-CUS-5386` is a raw premises UUID printed as the value
      // of `RESOLVED TO`, and a fixture whose `resolved_premises_id` is null
      // never renders that branch at all. A wave-2 case that fixes the screen
      // needs a RESOLVED fixture — ids set AND numbers set — or the assertion
      // it is built on cannot fail.
      resolved_premises_no: null,
      resolved_unit_no: null,
      resolved_premise_address: null,
      premise_locality: null,
      resolved_match: null,
      resolution_kind: "no_premise",
      lookup_found: "We don't have this address on record yet",
      plot_or_parcel: null,
      what_is_being_built: null,
      property_type: "standalone_owner_occupied",
      no_premise_flag: true,
      services: [
        { code: "electric", requested_start: "2026-09-15", available: null },
        { code: "water", requested_start: "2026-09-15", available: null },
      ],
      // BR-CUS-1070 — both services want the same day, so the server says so
      // once and the screen does not work it out for itself.
      requested_start_agreement: { count: 2, agreed: "2026-09-15", unset: 0 },
      evidence: { premise_exists: false, unit_is_served: false, unit_is_vacant: false },
    },
    documents: {
      documents: [
        {
          id: "doc-1",
          doc_type: "proof_of_identity",
          what_it_proves: "A driving licence, passport or state ID",
          document_number: null,
          name: "photo-id.pdf",
          uploaded_at: null,
          uploaded_by: null,
          // Nobody attached it, so there is nobody to name and no file to size.
          // `file_present` is the honest half of `attached` (DEF-CUS-5872).
          uploaded_by_name: null,
          size_bytes: null,
          original_size_bytes: null,
          file_present: false,
          attached: false,
          required: true,
          verification_state: "not_checked",
          verified_at: null,
          reject_reason: null,
        },
      ],
      verified: 0,
      attached: 0,
      // ⚠ PO ruling 2026-09-16 — documents no longer BLOCK; they are
      // OUTSTANDING and the clerk is told. The fixture carries both so the
      // screen is proved to read the field that still means something.
      blocks_creation: false,
      blocks_approval: false,
      outstanding: true,
      checklist_request_type: "move_in",
      checklist_required: ["proof_of_identity"],
      checklist_unmet: ["proof_of_identity"],
    },
    // ✅ **BR-CUS-090's WORKED CASE, verbatim from the ruling.**
    fees: {
      lines: [
        {
          // ⚠ **THE ROW'S OWN ID — `DEF-CUS-6096`.** Not the line number, and
          // deliberately a shape no line number could ever be, so a fixture
          // cannot make the waive look addressable when it is not.
          id: "0199a1d2-7c4e-7a10-9f31-2b6c5d4e8a01",
          line_no: 1,
          charge_code: "CC-REQFEE",
          description: "Application processing fee",
          basis: "per request",
          quantity: "1",
          unit_amount: money("25.0000", "25.00"),
          amount: money("25.0000", "25.00"),
          waived: false,
          waive_reason: null,
          settled_at: null,
          invoice_ref: null,
        },
      ],
      outstanding_lines: 1,
      quoted: money("130.0000", "130.00"),
      settled: money("0.0000", "0.00"),
      collected: money("25.0000", "25.00"),
      outstanding: money("105.0000", "105.00"),
      shortfall_is_open_balance: true,
      receipt_no: "RCP-26-4471",
      collected_at: "2026-08-08T09:05:00Z",
      quoted_at_collection: money("130.0000", "130.00"),
      fee_timing: "collect_now",
      fee_due_by: null,
      fee_method: "cash",
      posts_to_ledger: false,
      connection_quote: { raised: false, reason: "raised_after_review" },
    },
    decision: {
      what_they_said: "I'm moving into somewhere",
      what_the_lookup_found: "Served, and the unit is vacant",
      options: [
        {
          outcome: "new_connection",
          verdict: "not_possible",
          message_key: "customers.serviceRequest.verdict.newConnection.premiseExists",
        },
        { outcome: "move_in", verdict: "fits_the_evidence", message_key: null },
        { outcome: "move_out", verdict: "possible", message_key: null },
        { outcome: "transfer", verdict: "possible", message_key: null },
        // ✅ BR-CUS-091 — `disconnect` decides like any other option now. It
        // carries NO badge and no special absence.
        { outcome: "disconnect", verdict: "possible", message_key: null },
      ],
      preselected: null,
      undrawn_verdict_absence: { tracks: "OQ-356" },
      conditions: {
        clear: 3,
        total: 4,
        blocking: ["documents_verified"],
        conditions: [
          // `DEF-CUS-5064` — the keys the served payload actually carries.
          {
            key: "no_blocking_arrears",
            state: "clear",
            blocking: true,
            message_key: null,
            params: {},
          },
          {
            key: "eligibility_evidence",
            state: "noted",
            blocking: false,
            message_key: null,
            params: {},
          },
          {
            key: "documents_verified",
            state: "blocked",
            blocking: true,
            message_key: null,
            params: {},
          },
          // PO ruling 2026-09-21 — the fee is OUTSTANDING, never blocking.
          // The STATE stays `blocked`: `Condition.clear` reads it, and calling
          // this clear would print "4 of 4 conditions clear" over an open
          // balance. Only the gate moved.
          { key: "fee_settled", state: "blocked", blocking: false, message_key: null, params: {} },
        ],
        count_differs_from_design: { designed_total: 5, served_total: 4, tracks: "OQ-355" },
      },
      commit: {
        outcome: null,
        decided_by: null,
        decided_at: null,
        decided_against_evidence: false,
        outcome_kind: null,
        outcome_ref: null,
      },
      disconnect_is_not_a_move_out: {
        rule: "BR-CUS-091",
        move_out: "closes_the_account_and_settles_the_deposit",
        disconnect: "leaves_the_account_open_and_accruing",
      },
      // `CR-094-BRC01` wave 1 lane C — the two dialogs, read back.
      refusal: { reason_code: null, reason: null, message: null },
      more_info: { needed: [], message: null },
      // `CR-094-BRC01` wave 1 lane A — one preview PER OUTCOME, so the Approve
      // modal redraws as a radio moves with no round trip. `then` and `what`
      // are catalogue KEYS: a fixture holding sentences would prove nothing
      // about the thing this wave exists to stop.
      what_approving_will_do: {
        new_connection: preview("new_connection", [
          { then: "now", what: "request_becomes_approved_and_recorded_against_you" },
          { then: "now", what: "job_is_raised_naming_this_request", queue: "new_connects" },
          { then: "now", what: "the_outstanding_travels_with_it" },
          { then: "next", what: "the_jobs_own_wizard_asks_for_the_rest" },
          { then: "not_now", what: "no_account_no_meter_nothing_energised" },
        ]),
        move_in: preview("move_in", [
          { then: "now", what: "request_becomes_approved_and_recorded_against_you" },
          {
            then: "now",
            what: "no_job_row_is_raised",
            queue: "move_ins",
            absence: { code: "move_wizard_is_the_record", br_ref: "BR-CUS-152" },
          },
          { then: "now", what: "the_outstanding_travels_with_it" },
          { then: "next", what: "the_jobs_own_wizard_asks_for_the_rest" },
          { then: "not_now", what: "no_account_no_meter_nothing_energised" },
        ]),
        move_out: preview("move_out", []),
        transfer: preview("transfer", []),
        disconnect: preview("disconnect", []),
      },
      acknowledgement: {
        state: null,
        reason: "acknowledgement_cannot_be_queued",
        ref: null,
        sent: false,
        fee_statement: null,
      },
    },
    history: [
      {
        id: "ev-1",
        at: "2026-08-08T09:00:00Z",
        actor: "user-1",
        actor_name: "S. Ortiz",
        kind: "state",
        from_state: null,
        to_state: "draft",
        note: null,
        note_type: null,
        internal: true,
      },
      {
        id: "ev-2",
        at: "2026-08-10T09:00:00Z",
        actor: "user-1",
        // A row with no user — a seeded or process-written one. The screen
        // decides what the absence looks like; the drawing prints a dash.
        actor_name: null,
        kind: "state",
        from_state: "under_review",
        to_state: "refused",
        note: "No proof of address supplied.",
        note_type: null,
        internal: true,
      },
    ],
    unavailable: UNAVAILABLE,
    ...over,
  };
}

const noop = (): void => undefined;

describe("REQ-02 · Applicant (BR-CUS-092 · BR-CUS-089)", () => {
  it("BR-CUS-092(c)/(d) · the last four and the claim — DEF-632, PO 2026-08-27", () => {
    // ✅ **THIS ASSERTION IS THE EXACT REVERSE OF WHAT IT SAID YESTERDAY, AND
    // THAT IS THE DEFECT CLOSING.** It read *"the words 'stored encrypted'
    // appear NOWHERE"* and `expect(html).not.toMatch(/4471/)`, because the
    // column did not exist and the promise was false (clause (d), hard-won
    // law 1). Both halves are now built and proved server-side, so the screen
    // prints what B19 §7 always drew.
    //
    // ⛔ **AND ITS SECOND HALF REVERSED AGAIN ON 2026-09-23 (`DEF-CUS-6414`).**
    // The last four stays; *"stored encrypted"* goes. It is TRUE — that was
    // never the question — but it tells a clerk WHY the product shows four
    // digits, which is RATIONALE, and B14 rule 33 puts rationale at zero words
    // on screen. The mask is the fact.
    const html = renderToStaticMarkup(<WhoIsAskingBlock detail={detail()} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />);
    expect(html).toContain("4471");
    expect(html.toLowerCase()).not.toContain("stored encrypted");
  });

  it("DEF-CUS-9043 · the Customer match row NAMES the linked customer by number, and 'none on file' is said", () => {
    const linked = detail();
    linked.applicant.customer_match = {
      customer_id: "01a0fa41-17c2-71ca-9495-88d150c1090a",
      customer_no: "C-00053",
      display_name: "Marcus Bell",
      tier: "strong",
      basis: null,
      confirmed_at: "2026-10-02T09:00:00Z",
      may_move_money: true,
    };
    const html = renderToStaticMarkup(
      <WhoIsAskingBlock detail={linked} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />,
    );
    expect(html).toContain("C-00053 · Marcus Bell");
    expect(html).not.toMatch(/>[^<]*01a0fa41-17c2/);
    const none = detail();
    none.applicant.customer_match = {
      customer_id: null,
      customer_no: null,
      display_name: null,
      tier: null,
      basis: null,
      confirmed_at: "2026-10-02T09:00:00Z",
      may_move_money: false,
    };
    const blankRow = renderToStaticMarkup(
      <WhoIsAskingBlock detail={none} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />,
    );
    expect(blankRow).toContain(t("customers.serviceRequest.match.noneOnFile"));
  });

  it("DEF-CWP-9045 · a business's Tax ID typed online is shown as its LAST FOUR", () => {
    const business = detail();
    business.applicant.identifier = {
      ...business.applicant.identifier,
      tax_id_last4: "7731",
      tax_id_present: true,
    };
    const html = renderToStaticMarkup(
      <WhoIsAskingBlock detail={business} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />,
    );
    expect(html).toContain("•••• 7731");
    expect(html).toContain(t("customers.newAccount.field.taxId"));
  });

  it("renders ONLY what the server gave it — four characters, never a mask of a full value", () => {
    // ⚠ The guarantee is not "the screen masks it", it is "the screen was never
    // handed it". `ServiceRequestApplicant` has no field that could carry the
    // full number, so this asserts the rendered output against every spelling
    // of B19 §7's own worked identifier `••• ••• • 4471`.
    const html = renderToStaticMarkup(<WhoIsAskingBlock detail={detail()} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />);
    for (const spelling of ["452-88-4471", "452884471", "45288", "452-88", "88-4471"]) {
      expect(html).not.toContain(spelling);
    }
  });

  it("never claims 'stored encrypted' over a blank column", () => {
    // BR-CUS-092(d) in the negative — the claim is a fact about THIS ROW.
    // A screen drawing it from a constant would print it over an applicant who
    // gave no identifier at all, which is the false promise DEF-632 was.
    const blank = detail();
    blank.applicant.identifier = {
      ssn_last4: null,
      ssn_present: false,
      stored_encrypted: false,
      drivers_licence_last4: null,
      drivers_licence_present: false,
      drivers_licence_stored_encrypted: false,
    };
    blank.applicant.date_of_birth = null;
    const html = renderToStaticMarkup(<WhoIsAskingBlock detail={blank} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />);
    // The literal words, now the key is retired (`DEF-CUS-6414`) — asserting
    // the absence of a retired KEY would pass over anything at all.
    expect(html.toLowerCase()).not.toContain("stored encrypted");
    expect(html).not.toContain("4471");
  });

  it("BR-CUS-092(a) FINISHED · the DRIVING LICENCE is a VALUE, and it is four characters", () => {
    // ⚠ **THIS TEST USED TO ASSERT THE OPPOSITE, AND THAT IS THE POINT.** It
    // read *"the DRIVING LICENCE is still a stated absence — the widening is
    // half the rule"* and was correct until the PO's ruling of 2026-09-15:
    // *"ensure user is able to inputs both these on step 1 - Date of birth and
    // driver's licence on step 1"*. It is the hold-expiry test firing, which is
    // what a hold with a test is FOR (hard-won law 2's mirror).
    const html = renderToStaticMarkup(
      <WhoIsAskingBlock
        detail={detail()}
        t={t}
        timeZone="UTC"
        dateFormat="MM/DD/YYYY"
      />,
    );
    // ⚠ **THE CATALOGUE STRING IS ESCAPED BEFORE IT IS LOOKED FOR, AND THIS
    // ASSERTION WAS RED WITHOUT IT (`CR-094-BRC01` lane D).** The label became
    // the drawing's own word, `Driver's licence`, on 2026-09-15 — B14 rule 41,
    // and the blueprint draws it with an apostrophe. `renderToStaticMarkup`
    // escapes one to `&#x27;`, so comparing the RAW catalogue value against
    // MARKUP fails over a label that is on the screen.
    //
    // ⚠ **IT IS NOT A QUIRK OF THIS ONE STRING: 574 of the eleven catalogues'
    // English values carry an apostrophe**, so every `toContain(t(…))` in this
    // file is one copy change away from the same false red. `escapeHtml` is
    // the repo's own helper shape (`sidebarReachability.test.tsx`) and
    // `WorkflowRunner.test.tsx` already records the same trap running the
    // other way. Filed rather than papered over.
    expect(html).toContain(escapeHtml(t("customers.serviceRequest.applicant.driversLicence")));
    // The last four — and, since 2026-09-23, no *"stored encrypted"* beside it
    // (`DEF-CUS-6414`, B14 rule 33: rationale is zero words on screen).
    expect(html).toContain("4882");
    expect(html.toLowerCase()).not.toContain("stored encrypted");
    // And NOT the sentence that said the field did not exist.
    expect(html).not.toContain(t("customers.serviceRequest.applicant.driversLicenceAbsent"));
    expect(html).not.toContain('data-tracks="BR-CUS-092"');
  });

  it("BR-CUS-089's middle clause · the DATE OF BIRTH is a value, served in full", () => {
    // `BR-CUS-1020`, verbatim: *"it must be COMPARABLE, `contacts.dob` is a
    // plain date too, and `BR-CUS-092` names two identifiers of which it is not
    // one."* So it is not masked and it is not under `identifier`.
    const html = renderToStaticMarkup(<WhoIsAskingBlock detail={detail()} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />);
    expect(html).toContain(t("customers.serviceRequest.applicant.dateOfBirth"));
    // Rendered through the ONE formatting path (BR-SHL-023), in the tenant's
    // regional format — never as the raw ISO string the server sent.
    expect(html).toContain("03/14/1988");
    expect(html).not.toContain(t("customers.serviceRequest.applicant.dateOfBirthAbsent"));
  });

  it("'acting for' is GONE from this screen — PO removal list row, 2026-09-19", () => {
    // ⚠ **THIS ASSERTION IS THE EXACT REVERSE OF WHAT IT SAID YESTERDAY, AND
    // THAT IS THE RULING LANDING.** It read *"'acting for' is STILL a stated
    // absence, not omitted"* and asserted the label and its `data-tracks`.
    //
    // The PO put this column beside its drawing on 2026-09-19 and approved an
    // eighteen-row removal list whole (*"this is correct"*). `Acting for` is on
    // it: a stated absence, printed on every request, over a field with **no
    // column, no vocabulary and no ruling** behind it. B14 rule 32 gives a
    // screen a description budget and rule 33 gives rationale zero words; a
    // permanent sentence about something the product does not capture is both.
    const html = renderToStaticMarkup(<WhoIsAskingBlock detail={detail()} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />);
    expect(html).not.toContain(t("customers.serviceRequest.applicant.actingFor"));
    expect(html).not.toContain('data-tracks="DEF-638"');
  });

  it("DEF-638 12.c · the identifier has ONE label, and it is the capture form's", () => {
    // ⛔ **THE DEFECT, VERBATIM:** *"THE IDENTIFIER IS LABELLED `ID` ON THE
    // DETAIL AND `Social Security Number` ON THE CAPTURE FORM … two labels for
    // one field is a decision nobody has made."*
    //
    // It is made now, by the authority order and not by a PO question: B19 §7
    // draws this row as `Social Security Number → ••• ••• • 4471 · stored
    // encrypted`, and the generic `ID` was DEF-632-era caution that BR-CUS-092
    // retired when the value became storable.
    //
    // ⚠ **THE ASSERTION IS THE PAIR, NOT THE STRING.** Pinning the English
    // would pass the day somebody changed one catalogue and not the other —
    // which is the defect wearing a different spelling. This asserts that the
    // detail renders THE CAPTURE FORM'S OWN KEY, so the two screens cannot
    // drift again without the key itself changing in one place.
    const html = renderToStaticMarkup(<WhoIsAskingBlock detail={detail()} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />);
    expect(html).toContain(t("customers.serviceRequest.capture.ssn"));
    // And the retired label is gone from this screen. `ID` is a substring of
    // ordinary markup, so the comparison is against the catalogue value only
    // when the two genuinely differ — which, in English, they do.
    const retired = t("customers.serviceRequest.applicant.identifier");
    if (retired !== t("customers.serviceRequest.capture.ssn")) {
      expect(html).not.toContain(`>${retired}<`);
    }
  });

  it("BR-CUS-089 · money may not move on anything but a STRONG match", () => {
    // ⚠ **THE THIRTEEN-WORD SENTENCE WENT AND THE FACT STAYED.** The Customer
    // match CARD drew three sentences — the matcher-absent note, the tier/basis
    // pair and *"A strong match, so a deposit or a balance may be carried
    // across."* The PO ruled the card into ONE row (2026-09-19). The rule is
    // still the SERVER's boolean and is still not re-derived from the tier
    // string here, which is what this case has always been for; what changed is
    // that a clerk reads four words instead of thirteen (B14 rule 33).
    const weak = renderToStaticMarkup(<WhoIsAskingBlock detail={detail()} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />);
    expect(weak).toContain('data-may-move-money="false"');
    expect(weak).not.toContain(t("customers.serviceRequest.match.mayMoveMoney"));
    expect(weak).not.toContain(escapeHtml(t("customers.serviceRequest.match.balanceMayCarry")));
  });

  it("the customer match is ONE row and the card's three sentences are gone", () => {
    const html = renderToStaticMarkup(<WhoIsAskingBlock detail={detail()} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />);
    expect(html).toContain('data-drawn-row="customer-match"');
    // Exactly one match row, never the card's heading plus a tier and a basis
    // field under it.
    expect(html.split('data-drawn-row="customer-match"').length - 1).toBe(1);
    // And the button that used to sit in that card is NOT here — it moved into
    // the Approve dialog, where `arrears_condition` is actually cleared.
    expect(html).not.toContain(t("customers.serviceRequest.match.noMatch"));
  });
});

/** `SR-26-0001` on `brazosbend`, as lane B measured it out of PostgreSQL on
 *  2026-09-15 — **RESOLVED**, ids AND numbers set.
 *
 *  ⚠ **THE FIXTURE ABOVE RESOLVES TO NOTHING, SO IT COULD NOT CATCH
 *  `DEF-CUS-5386` AT ALL** — the raw-id branch never rendered, and lane B's
 *  record says so in as many words: *"a wave-2 case that fixes the screen needs
 *  a RESOLVED fixture … or the assertion it is built on cannot fail."* This is
 *  that fixture, and the cases below were proved RED on the old screen with it. */
const RESOLVED_PREMISES_ID = "01a0a444-5ad2-7e88-be8a-bdb8aa86c05e";
const RESOLVED_UNIT_ID = "01a0a444-5ada-7109-974b-d4c7143b9547";

function resolved(over: Record<string, unknown> = {}): ServiceRequestDetail {
  const one = detail();
  one.location_and_services = {
    ...one.location_and_services,
    address_as_given: "3450 Oak Ridge Dr",
    address_unit_as_given: "3450 Oak Ridge Dr · Unit 1",
    units_on_property: 6,
    billing_address_same: false,
    billing_address_as_given: "PO Box 41, Austin TX 78767",
    billing_line1_as_given: null,
    billing_line2_as_given: null,
    billing_city_as_given: null,
    billing_state_as_given: null,
    billing_postal_code_as_given: null,
    resolved_premises_id: RESOLVED_PREMISES_ID,
    resolved_unit_id: RESOLVED_UNIT_ID,
    resolved_premises_no: "P-00052",
    resolved_unit_no: "SCW-U-207",
    resolved_premise_address: "3450 Oak Ridge Dr",
    premise_locality: { city: "Silver Creek", state: "TX", postal_code: "78611" },
    resolved_match: "exact_reference",
    resolution_kind: "served_vacant",
    lookup_found: "customers.serviceRequest.lookup.servedAndVacant",
    ...over,
  } as never;
  return one;
}

describe("REQ-02 · THE ADDRESS THEY GAVE — BR-CUS-070 · DEF-CUS-5386", () => {
  it("DEF-CUS-5386 · the match is NAMED, and the database id is not the visible value", () => {
    // ⛔ **THE DEFECT, VERBATIM:** *"the field RESOLVED TO reads
    // 01a0a444-5ad2-7e88-be8a-bdb8aa86c05e"*. B14 rule 31, ratified by the PO
    // on 2026-08-31: *"no Databse ID on screen - that is a rule"*.
    //
    // ⚠ **THE OBVIOUS ASSERTION IS VACUOUS AND THE REGISTER SAYS SO:** with the
    // id on `title=` it is still in the markup, so `not.toContain(id)` fails on
    // the CORRECT fix. **Assert the POSITION.** The id may appear only inside a
    // `title` attribute and nowhere a clerk reads as a value.
    const html = renderToStaticMarkup(<AddressBlock detail={resolved()} t={t} />);
    expect(html).toContain("P-00052");
    expect(html).toContain("SCW-U-207");
    for (const id of [RESOLVED_PREMISES_ID, RESOLVED_UNIT_ID]) {
      const positions = [...html.matchAll(new RegExp(id, "g"))].map((hit) => hit.index ?? -1);
      expect(positions.length).toBeGreaterThan(0);
      for (const at of positions) {
        expect(html.slice(Math.max(0, at - 7), at)).toBe('title="');
      }
    }
  });

  it("a number that is NULL falls back to the address, never to the id", () => {
    // `premises.premise_no` and `units.unit_no` are both NULLABLE — a tenant
    // that never turned its numbering series on has an id and no number. The
    // fallback is part of the fix: falling back to the id is the defect coming
    // straight back.
    const html = renderToStaticMarkup(
      <AddressBlock detail={resolved({ resolved_premises_no: null, resolved_unit_no: null })} t={t} />,
    );
    expect(html).toContain("3450 Oak Ridge Dr");
    expect(html).toContain(t("customers.serviceRequest.address.notMatched"));
    expect(html).not.toMatch(new RegExp(`>[^<]*${RESOLVED_PREMISES_ID}`));
  });

  it("no internal reference of any kind reaches the clerk on this block", () => {
    // The shared rendered-output helper, which reads text nodes and the two
    // attributes a browser SHOWS (`title`, `aria-label`) for the id grammar and
    // for dotted Python identifiers. A screen nobody has asked this of is a
    // screen nobody has checked.
    expect(internalReferencesInMarkup(renderToStaticMarkup(<AddressBlock detail={resolved()} t={t} />))).toEqual([]);
  });

  it("TC-REQ-6 · what they typed sits BESIDE what we matched, never replaced by it", () => {
    const html = renderToStaticMarkup(<AddressBlock detail={resolved()} t={t} />);
    expect(html).toContain(t("customers.serviceRequest.location.asGiven"));
    expect(html).toContain("3450 Oak Ridge Dr · Unit 1");
    expect(html).toContain(t("customers.serviceRequest.address.matchedPremises"));
  });

  it("DEF-CUS-9042 · a street AND a unit are both what they said — the unit never replaces the street", () => {
    // A portal applicant types `400 Heron Court` and, separately, `Unit 2`.
    // The row read `Unit 2` alone: `unit ?? street` PREFERS the unit.
    const html = renderToStaticMarkup(
      <AddressBlock
        detail={resolved({
          address_as_given: "400 Heron Court, Katy, TX 77494",
          address_unit_as_given: "Unit 2",
        })}
        t={t}
      />,
    );
    expect(html).toContain("400 Heron Court, Katy, TX 77494, Unit 2");
  });

  it("DEF-CWP-9817 · the town and ZIP the applicant gave are part of what they said", () => {
    // The portal now asks Street · Town · ZIP (blueprint p31) and sends the
    // parts to the request's `_as_given` columns. This row passed `null` for
    // the locality and printed the street alone, dropping two of three parts.
    const html = renderToStaticMarkup(
      <AddressBlock
        detail={resolved({
          address_as_given: "1841 Quarry Hill Ct",
          address_unit_as_given: "Apt 12",
          address_city_as_given: "Silver Creek",
          address_state_as_given: null,
          address_postal_code_as_given: "78611",
        })}
        t={t}
      />,
    );
    expect(html).toContain("1841 Quarry Hill Ct, Apt 12 · Silver Creek, 78611");
  });

  it("the PO asked for BOTH addresses by name, and both are drawn", () => {
    // PO, 2026-09-15: *"we have to show service address and also allow to take
    // billing address"*. The server has carried the billing address since W4
    // and no screen drew it until this wave.
    const html = renderToStaticMarkup(<AddressBlock detail={resolved()} t={t} />);
    expect(html).toContain(t("customers.serviceRequest.address.serviceAddress"));
    expect(html).toContain("Silver Creek, TX 78611");
    expect(html).toContain(t("customers.serviceRequest.location.billingAddress"));
    expect(html).toContain("PO Box 41, Austin TX 78767");
  });

  it("the address line is composed on the SCREEN, and an empty part drops out", () => {
    // The blueprint punctuates the same line two ways on two frames, so the
    // punctuation is an illustration (B14 rule 37) and the server never
    // composes it. An empty result is `null` so a caller states an absence
    // rather than drawing a stray comma.
    expect(composeAddressLine("3450 Oak Ridge Dr", { city: "Silver Creek", state: "TX", postal_code: "78611" }))
      .toBe("3450 Oak Ridge Dr · Silver Creek, TX 78611");
    expect(composeAddressLine("3450 Oak Ridge Dr", null)).toBe("3450 Oak Ridge Dr");
    expect(composeAddressLine("3450 Oak Ridge Dr", { city: null, state: "TX", postal_code: null }))
      .toBe("3450 Oak Ridge Dr · TX");
    expect(composeAddressLine(null, null)).toBeNull();
  });

  it("TC-REQ-4 · an address matching nothing says so, and states no premises", () => {
    const html = renderToStaticMarkup(<AddressBlock detail={detail()} t={t} />);
    expect(html).toContain(t("customers.serviceRequest.address.notMatched"));
  });
});

describe("REQ-02 · WHAT THEY ASKED FOR — the drawn block", () => {
  function asked(over: Record<string, unknown> = {}): string {
    return renderToStaticMarkup(
      <AskedForBlock detail={resolved(over)} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />,
    );
  }

  /**
   * ⚠ **REVERSED BY THE PO ON 2026-09-22, ROW 12 — *"Remove Units on site"*.**
   * It was built on their own instruction of 2026-09-15 (*"we need to build
   * this"*) and taken off both screens a week later. The case is INVERTED
   * rather than deleted, because an absence is invisible to every check this
   * repo has (`DEF-CUS-3653`) and a row that quietly comes back is exactly
   * what this file is for.
   *
   * **The VALUE is untouched.** `units_on_property` is still captured
   * nowhere, still served, and still on every row that holds one; what the PO
   * removed is the QUESTION and the row that displayed it.
   */
  it("the unit count is NOT drawn — PO 2026-09-22 row 12", () => {
    const html = asked();
    expect(html).not.toContain("data-units-on-property");
    expect(html).not.toContain(t("customers.serviceRequest.asked.unitsOnProperty"));
  });

  it("an absence is an EM DASH on this page, and is NEVER drawn as `0`", () => {
    // Zero is a real answer — vacant land — and the two must not look alike
    // (wave 1 lane B's rule 5). That half is unchanged.
    //
    // ⚠ **WHAT CHANGED IS THE GLYPH, ON THE PO's APPROVED REMOVAL LIST (row 14,
    // 2026-09-19).** The words *Not supplied* leave this page and become `—`.
    // **The absence is still STATED** — the row is there and its value is a
    // dash, which is what B14 rule 32 asks for; six repetitions of a two-word
    // sentence down one column is what the PO has twice called too much
    // content, and the drawing prints a dash in exactly this position.
    // Scoped to this page: `NotSupplied` is untouched everywhere else.
    // ⚠ **THE SUBJECT MOVED ON 2026-09-22.** This case used to prove the glyph
    // on `Units on site`, and that row is gone (row 12). The RULE is unchanged
    // and is asserted on a row that is still drawn: the sub-category, which is
    // `null` on a request nobody has classified.
    const html = asked({ units_on_property: null, property_type: null });
    expect(html).toContain('data-absence="dash"');
    expect(html).not.toContain(t("customers.serviceRequest.notSupplied"));
    expect(html).not.toContain('data-units-on-property="0"');
  });

  it("the services asked for are NAMED from the catalogue, never as their codes", () => {
    const html = asked();
    expect(html).toContain(t("rating.service.electric"));
    expect(html).toContain(t("rating.service.water"));
  });
});

describe("REQ-02 · Documents — ONE GATE AND ONE NOTICE (BR-CUS-095, TC-REQ-7)", () => {
  // ⚠ **THIS CASE WAS NAMED `an unverified required document BLOCKS APPROVAL
  // and says so` AND WAS REWRITTEN RATHER THAN RE-POINTED (PO ruling
  // 2026-09-16, *"lets not make it mandetory"*).** Its name stated the rule
  // that was reversed, so flipping one assertion inside it would have left a
  // case asserting the opposite of what it claims to guard — the same shape the
  // applicant-message cases were corrected for on 2026-09-15. What is guarded
  // now is that the clerk is still TOLD: the screen must not go silent about an
  // unverified document just because it stopped refusing over one.
  it("TC-REQ-7 · an unverified required document is still REPORTED, in ONE sentence", () => {
    // ⚠ **THE SIGNAL SURVIVED AND THE FOUR PARAGRAPHS DID NOT (PO ruling
    // 2026-09-19).** This tab opened with a count, two gate sentences and a
    // checklist sentence — four paragraphs before a clerk reached a document.
    // B14 rule 32 gives a section ONE sentence; rule 33 gives rationale zero
    // words, and three of the four were rationale.
    //
    // `data-outstanding` moved onto the surviving count rather than being
    // dropped with the paragraph that carried it, so nothing watching that
    // signal lost it — which is the whole reason this case still passes.
    const html = renderToStaticMarkup(
      <DocumentsTab
        detail={detail()}
        t={t}
        onVerify={noop}
        onReject={noop}
        onOpen={noop}
        openingId={null}
        openError={null}
        working={false}
      />,
    );
    expect(html).toContain('data-outstanding="true"');
    // Composed from the FIXTURE's own counts, never from two numbers typed
    // here — a hardcoded pair passes wrongly the day the fixture changes.
    // ⚠ **THE DENOMINATOR CHANGED ON 2026-09-22, PO REPORT ROW 4.** The PO
    // saw *"0 of 0 verified"* over a table with ONE row in it. Both numbers
    // were true and they counted different populations: the server's
    // `verified`/`attached` count rows WITH A FILE, while the TABLE lists every
    // row including the requirements nobody has brought a file for. The header
    // now counts the table's own rows, which is what makes them agree.
    //
    // ⚠ **COMPOSED FROM THE FIXTURE, NEVER FROM A PAIR TYPED HERE** — a
    // hardcoded `0 of 1` passes wrongly the day the fixture grows a row. What
    // is hardcoded is WHICH QUESTION is asked, which is the thing that moved.
    const docs = detail().documents;
    expect(html).toContain(
      t("customers.serviceRequest.documents.verifiedOf", {
        verified: docs.documents.filter(
          (d) => d.file_present && d.verification_state === "verified",
        ).length,
        attached: docs.documents.length,
      }),
    );
  });

  it("the three rationale paragraphs are GONE from the Documents tab", () => {
    // ⚠ **THIS CASE IS THE REVERSE OF *attaching NEVER blocks creation, and
    // that sentence is on the screen too*.** The RULE is unchanged and is still
    // proved server-side (`blocks_creation` is a literal False); what left is
    // the paragraph explaining it to a clerk on every visit. B14 rule 33:
    // rationale is zero words on screen.
    const html = renderToStaticMarkup(
      <DocumentsTab
        detail={detail()}
        t={t}
        onVerify={noop}
        onReject={noop}
        onOpen={noop}
        openingId={null}
        openError={null}
        working={false}
      />,
    );
    expect(html).not.toContain(t("customers.serviceRequest.documents.gateCreation"));
    expect(html).not.toContain(t("customers.serviceRequest.documents.gateApprovalBlocked"));
    expect(html).not.toContain(t("customers.serviceRequest.documents.checklistEmpty"));
  });

  it("a document with no file cannot be VERIFIED, and the control says why", () => {
    const html = renderToStaticMarkup(
      <DocumentsTab
        detail={detail()}
        t={t}
        onVerify={noop}
        onReject={noop}
        onOpen={noop}
        openingId={null}
        openError={null}
        working={false}
      />,
    );
    // BR-SHL-025 — disabled WITH the reason, never hidden.
    expect(html).toContain(t("customers.serviceRequest.documents.cannotVerifyNoFile"));
    expect(html).toContain("disabled");
  });

  it("BR-CUS-095 · an EMPTY checklist draws no notice at all", () => {
    // ⚠ **THE RULE IS UNCHANGED; THE SENTENCE ABOUT IT IS GONE.** BR-CUS-095:
    // *"We ship with nothing ticked, and a utility that configures nothing
    // blocks nothing."* The old screen printed a paragraph saying where the
    // checklist is configured — which is RATIONALE (B14 rule 33) and was on
    // every request forever. **Nothing configured now draws nothing**, which is
    // the truest rendering of *blocks nothing* there is.
    const empty = detail();
    empty.documents.checklist_required = [];
    empty.documents.checklist_unmet = [];
    const html = renderToStaticMarkup(
      <DocumentsTab
        detail={empty}
        t={t}
        onVerify={noop}
        onReject={noop}
        onOpen={noop}
        openingId={null}
        openError={null}
        working={false}
      />,
    );
    expect(html).not.toContain("data-checklist-count");
    expect(html).not.toContain(t("customers.serviceRequest.documents.checklistEmpty"));
    // …and the table itself is still there, so this cannot pass vacuously.
    expect(html).toContain(t("customers.serviceRequest.documents.col.document"));
  });
});

/**
 * ⚠ **THE FEE PICKER'S SIX PROPS ARE REQUIRED, AND THAT IS ON PURPOSE (G13).**
 * PO report 2026-09-22 row 11 put a charge-code dropdown on this panel and on
 * the capture wizard's fee step, one component mounted twice (B14 rule 43).
 * Making the props OPTIONAL so these cases kept compiling untouched is exactly
 * the dead-UI shape hard-won law 2 is about: the panel would render, every case
 * would pass, and the feature would not exist.
 *
 * **EMPTY IS A REAL STATE AND IS WHAT THESE CASES EXERCISE** — a tenant whose
 * catalogue has not answered yet. `feeCatalogueAnswered: false` means *we have
 * not heard*, which draws no picker and no stated absence; the absence is for a
 * catalogue that answered with nothing raisable.
 */
const noFeePicker = {
  feeCodes: [] as const,
  pickedFeeCode: "",
  onPickFeeCode: noop,
  onAddFee: noop,
  feeAddRefusal: null,
  feeCatalogueAnswered: false,
};

describe("DEF-CUS-9819 · a request owing $0.00 has nothing to collect (PO 2026-10-06)", () => {
  function zeroFee(): ServiceRequestDetail {
    const base = detail();
    const line = { ...base.fees.lines[0], charge_code: "APP-FEE", description: "Application fee" };
    return {
      ...base,
      fees: {
        ...base.fees,
        lines: [{ ...line, unit_amount: money("0.0000", "0.00"), amount: money("0.0000", "0.00") }],
        quoted: money("0.0000", "0.00"),
        collected: money("0.0000", "0.00"),
        outstanding: money("0.0000", "0.00"),
        receipt_no: null,
        shortfall_is_open_balance: false,
      },
    };
  }

  it("a $0.00 application fee reads Nothing to collect and draws no collect button", () => {
    const html = renderToStaticMarkup(
      <FeesBlock detail={zeroFee()} t={t} onWaive={noop} onCollect={noop} working={false} {...noFeePicker} />,
    );
    expect(html).toContain('data-fee-collect="nothing"');
    expect(html).toContain(t("customers.serviceRequest.fees.nothingToCollect"));
    expect(html).not.toContain(t("customers.serviceRequest.fees.collect"));
    // Not "Not taken" — a $0.00 fee owes nothing.
    expect(html).toContain('data-fee-line="zero"');
    expect(html).toContain(t("customers.serviceRequest.fees.line.zero", { amount: "$0.00" }));
    // The per-line waive lives inside the closed disclosure and is untouched
    // (its gate is `waived || settled_at`, never the amount); the browser walk
    // opens it on a $0.00 line.
  });

  it("a $10.00 fee still owed keeps Record what was handed over", () => {
    const base = zeroFee();
    const owed = money("10.0000", "10.00");
    const html = renderToStaticMarkup(
      <FeesBlock
        detail={{
          ...base,
          fees: {
            ...base.fees,
            lines: [{ ...base.fees.lines[0], unit_amount: owed, amount: owed }],
            quoted: owed,
            outstanding: owed,
          },
        }}
        t={t}
        onWaive={noop}
        onCollect={noop}
        working={false}
        {...noFeePicker}
      />,
    );
    expect(html).toContain(t("customers.serviceRequest.fees.collect"));
    expect(html).not.toContain('data-fee-collect="nothing"');
  });

  it("a request with no fee line keeps the collect button exactly as before", () => {
    const base = zeroFee();
    const none = money("0.0000", "0.00", null);
    const html = renderToStaticMarkup(
      <FeesBlock
        detail={{ ...base, fees: { ...base.fees, lines: [], quoted: none, outstanding: none } }}
        t={t}
        onWaive={noop}
        onCollect={noop}
        working={false}
        {...noFeePicker}
      />,
    );
    expect(html).toContain(t("customers.serviceRequest.fees.collect"));
  });
});

describe("REQ-02 · Fees — BR-CUS-090 and OQ-357", () => {
  it("BR-CUS-090 · the worked case renders as $25.00 collected of $130.00 quoted · $105.00 outstanding", () => {
    const html = renderToStaticMarkup(
      <FeesBlock
        detail={detail()}
        t={t}
        onWaive={noop}
        onCollect={noop}
        working={false}
        {...noFeePicker}
      />,
    );
    // ⚠ **THE HEADLINE FIGURES ARE READABLE WITH THE PANEL CLOSED**, which is
    // `Disclosure`'s own load-bearing rule: collapsing hides the DERIVATION,
    // never the result. So `outstanding` is on the header — with the SERVER's
    // 2-dp `display` carried beside it so the two cannot drift (CLAUDE.md
    // rule 2: rounding for a human happens once, server-side) — and the
    // quoted/collected pair is in the summary line.
    expect(html).toContain('data-display="105.00"');
    // ⚠ **WITH ITS CURRENCY (`DEF-CUS-6412`).** This asserted
    // `25.00 collected of 130.00 quoted` — the bare `display`, no `$` — and
    // the PO's screenshot showed exactly that beside `$105.00`.
    expect(html).toContain(
      t("customers.serviceRequest.fees.collectedOfQuoted", {
        collected: "$25.00",
        quoted: "$130.00",
      }),
    );
    // ⚠ **ONE LINE SINCE 2026-09-22, PO REPORT ROW 10** — *"we are either
    // taking application fees or we are waiveing it off so message should be
    // in line with that"*. The four-figure grid is gone; what is asserted is
    // that the one true state is stated, with its money at 2 dp AND its
    // currency (a figure with no symbol was this lane's own first draft and
    // this suite is what caught it), and that the DERIVATION is still one
    // press away rather than deleted.
    expect(html).toContain('data-fee-line="taken"');
    expect(html).toContain("$25.00");
    expect(html).toContain("RCP-26-4471");
    // The disclosure still carries the outstanding figure a clerk acts on.
    expect(html).toContain('data-display="105.00"');
  });

  it("…and 'Less was handed over' is NOT said where nothing was handed over", () => {
    // Walked on SR-26-0011 (2026-09-23): $0.00 collected, and the panel read
    // *"Less was handed over. Not a waiver."* — a false fact. `shortfall_is_
    // open_balance` is *outstanding > 0*, which is true of every request whose
    // fee has not been taken at all; the sentence is about a PART-payment.
    const base = detail();
    const html = renderToStaticMarkup(
      <FeesBlock
        detail={{
          ...base,
          fees: {
            ...base.fees,
            collected: { amount: "0.0000", display: "0.00", currency: "USD" },
            receipt_no: null,
            shortfall_is_open_balance: true,
          },
        }}
        t={t}
        onWaive={noop}
        onCollect={noop}
        working={false}
        {...noFeePicker}
      />,
    );
    expect(html).not.toContain('data-shortfall="open-balance"');
  });

  it("a shortfall is an OPEN BALANCE — never drawn as a waiver and never as a refusal", () => {
    const html = renderToStaticMarkup(
      <FeesBlock
        detail={detail()}
        t={t}
        onWaive={noop}
        onCollect={noop}
        working={false}
        {...noFeePicker}
      />,
    );
    // ⚠ It is OUTSIDE the disclosure, so a clerk who never opens the panel
    // still reads it.
    expect(html).toContain('data-shortfall="open-balance"');
    expect(html).toContain(t("customers.serviceRequest.fees.shortfallIsOpenBalance"));
    // The one line on this request is NOT waived, and nothing may say it was.
    expect(html).not.toContain(
      t("customers.serviceRequest.fees.waivedWithReason", { reason: "" }),
    );
  });

  it("the LINES, the waive and the quote's absence sit in a CLOSED disclosure", () => {
    // ⚠ **`Disclosure` UNMOUNTS ITS BODY WHEN CLOSED — it does not merely hide
    // it** (its own comment says why: six panels of rate tables would otherwise
    // render and be paid for). So a `renderToStaticMarkup` assertion on the
    // fee lines, on `OQ-357`'s remove reason or on the connection quote passes
    // only when they are OUTSIDE the panel, and asserting them here would be a
    // check that cannot see its own subject.
    //
    // The blueprint draws FOUR FIGURES in this block (p083) and nothing else,
    // and B14 rule 32 makes a derivation a `<details>` closed by default — so
    // the lines belong inside. What is asserted here is the door; what is
    // behind it is asserted by the DOM case in `…dom.test.tsx`, which opens it.
    const html = renderToStaticMarkup(
      <FeesBlock
        detail={detail()}
        t={t}
        onWaive={noop}
        onCollect={noop}
        working={false}
        {...noFeePicker}
      />,
    );
    expect(html).toContain(t("customers.serviceRequest.fees.applicationFees"));
    expect(html).toContain('aria-expanded="false"');
    // The counter's own door is OUTSIDE the panel and always reachable: a
    // clerk taking cash may not have to open a derivation first.
    expect(html).toContain(t("customers.serviceRequest.fees.collect"));
  });

  it("a request with no fee line shows no currency rather than a fabricated one", () => {
    const none = detail();
    none.fees.quoted = money("0.0000", "0.00", null);
    none.fees.outstanding = money("0.0000", "0.00", null);
    none.fees.collected = money("0.0000", "0.00", null);
    none.fees.settled = money("0.0000", "0.00", null);
    none.fees.lines = [];
    const html = renderToStaticMarkup(
      <FeesBlock
        detail={none}
        t={t}
        onWaive={noop}
        onCollect={noop}
        working={false}
        {...noFeePicker}
      />,
    );
    // ⚠ **THE SENTENCE CHANGED ON 2026-09-22 (row 10) AND ITS JOB DID NOT.**
    // A request with no fee line says so ONCE, and it now says the thing a
    // clerk can act on — *No application fee.* — rather than describing the
    // absence of a database row.
    expect(html).toContain(t("customers.serviceRequest.fees.line.none"));
    expect(html).toContain('data-fee-line="none"');
    // Never a "$" with no currency behind it.
    expect(html).not.toContain("USD");
    // ⚠ **AND IT SAYS IT ONCE — 2026-09-21, `DEF-CUS-6102`.** Measured on a
    // `$0` request in a browser, the panel printed that sentence TWICE: once
    // in its body and once as the disclosure header's `value`, beside a
    // `0.00 collected of 0.00 quoted` summary drawing money with no currency
    // behind it. B14 rule 32 gives a section ONE sentence, and a derivation of
    // nothing derives nothing, so the disclosure is not drawn at all.
    // ⚠ **THE SENTENCE IT COUNTS MOVED ON 2026-09-22 AND THE COUNT DID NOT.**
    // `noCurrencyYet` is not printed by this panel any more — the one line is
    // `fees.line.none` — so counting the old string would assert ZERO for ever
    // and could never fail, which is law 7's *incapable of failing*. It counts
    // the sentence the panel actually prints.
    const said = html.split(t("customers.serviceRequest.fees.line.none")).length - 1;
    expect(said).toBe(1);
    // …and the summary that printed money with no currency behind it is gone.
    expect(html).not.toContain(
      t("customers.serviceRequest.fees.collectedOfQuoted", { collected: "0.00", quoted: "0.00" }),
    );
    // ⚠ **THE DISCLOSURE ITSELF STAYS**, and this assertion is why: hiding it
    // took the CONNECTION QUOTE's own stated absence with it, which is a
    // different fact from the application fee and one a `$0` utility still
    // has. A fix wider than its defect deletes a surface nobody asked about.
    expect(html).toContain(t("customers.serviceRequest.fees.applicationFees"));
    // …and the counter's own door is UNTOUCHED. Hiding a live money-taking
    // control would change what a clerk can do, which is the PO's to rule.
    expect(html).toContain(t("customers.serviceRequest.fees.collect"));
  });
});

describe("REQ-02 · THE APPROVE WINDOW — the kit window the PO approved 2026-09-23", () => {
  // ⚠ **REWRITTEN 2026-09-23 (`DEF-CUS-6350`, `DEF-CUS-6352`).** The dialog
  // these cases watched drew a `THEN`/`WHAT` table whose rows were worded for a
  // BUILD on every kind, so a move-in read *"A build opens for this address"*.
  // `ApproveChecksModal` replaces it; the behaviours that still matter are
  // asserted here on static markup and the rest in
  // `ApproveChecksModal.dom.test.tsx`, which needs a DOM.
  const promise = (): Promise<{ ok: true }> => Promise.resolve({ ok: true } as const);

  /** Both kinds open — "nothing preselected" is only true there since PO
   *  2026-10-11 (option A): a refused New connection pre-picks Move-in. */
  function bothOpen(): ServiceRequestDetail {
    const one = detail();
    (one.decision as unknown as { options: unknown[] }).options = [
      { outcome: "new_connection", verdict: "possible", message_key: null },
      { outcome: "move_in", verdict: "possible", message_key: null },
    ];
    return one;
  }

  function approve(one: ServiceRequestDetail = detail()): string {
    return renderToStaticMarkup(
      <ApproveChecksModal detail={one} t={t} onClose={noop} onSubmit={() => promise()} />,
    );
  }

  it("the TWO kinds are offered and NOTHING is preselected (when both are open)", () => {
    const html = approve(bothOpen());
    for (const outcome of ["new_connection", "move_in"]) {
      expect(html).toContain(`data-segment="${outcome}"`);
      expect(html).toContain(t(`customers.serviceRequest.approveChecks.kindOption.${outcome}`));
    }
    for (const gone of ["move_out", "transfer", "disconnect"]) {
      expect(html).not.toContain(`data-segment="${gone}"`);
    }
    expect(html).not.toContain('aria-checked="true"');
    // With nothing picked there are no checks to show, and the commit says so.
    expect(html).not.toContain("data-check-list");
    expect(html).toContain(t("customers.serviceRequest.approveChecks.pickFirst"));
  });

  it("PO 2026-10-11 — New connection refused: Move-in is picked for the clerk", () => {
    const html = approve();
    expect(html).toMatch(/aria-checked="true"[^>]*data-segment="move_in"|data-segment="move_in"[^>]*aria-checked="true"/);
  });

  it("the schema is what makes 'nothing preselected' safe — no outcome, no commit", () => {
    expect(APPROVE_SCHEMA.safeParse({ outcome: "" }).success).toBe(false);
    expect(APPROVE_SCHEMA.safeParse({ outcome: "   " }).success).toBe(false);
    expect(APPROVE_SCHEMA.safeParse({ outcome: "new_connection" }).success).toBe(true);
  });

  it("a blocked approval refuses the COMMIT in words, never a hidden button", () => {
    const html = approve(bothOpen());
    expect(html).toContain("data-commit-blocked");
    expect(html).toContain(t("customers.serviceRequest.approveChecks.submit.none"));
  });

  it("no internal reference of any kind reaches the clerk", () => {
    expect(internalReferencesInMarkup(approve())).toEqual([]);
  });
});

describe("REQ-02 · THE REFUSE DIALOG — p084/p085, DEF-CUS-5389", () => {
  function refuse(): string {
    return renderToStaticMarkup(
      <RefuseModal
        detail={detail()}
        t={t}
        onClose={noop}
        onSubmit={() => Promise.resolve({ ok: true } as const)}
      />,
    );
  }

  it("the five drawn reasons are a VOCABULARY, not a free-text box", () => {
    // ⛔ **THE DEFECT, VERBATIM:** *"Refuse opens a modal with ONE control, a
    // textarea … no reason vocabulary, no applicant message and no consequence
    // table — although the server already accepts a reason_code that nothing on
    // screen sets."* Five values group; five hundred typed sentences do not.
    const html = refuse();
    for (const code of [
      "not_our_service_area",
      "documents_not_provided",
      "applicant_withdrew",
      "duplicate_of_another_request",
      "other",
    ]) {
      expect(html).toContain(t(`customers.serviceRequest.refuseReason.${code}`));
      expect(html).toContain(`value="${code}"`);
    }
  });

  it("the CODE is never printed — the clerk reads the label and the server gets the code", () => {
    // B14 rule 31. The option's `value` is the code and its text is the word.
    const html = refuse();
    expect(html).not.toContain(">not_our_service_area<");
    expect(html).not.toContain(">duplicate_of_another_request<");
  });

  it("`What to tell them` is a SECOND field, and it says where it goes", () => {
    // The drawing separates them on purpose: the code is for counting and the
    // sentence is for the applicant.
    const html = refuse();
    expect(html).toContain(t("customers.serviceRequest.refuse.tellThem"));
    expect(html).toContain(t("customers.serviceRequest.refuse.tellThemHelp"));
  });

  it("TC-REQ-9 · a refusal with no reason does not validate", () => {
    expect(REFUSE_SCHEMA.safeParse({ reason_code: "" }).success).toBe(false);
    expect(REFUSE_SCHEMA.safeParse({ reason_code: "   " }).success).toBe(false);
    expect(REFUSE_SCHEMA.safeParse({ reason_code: "duplicate_of_another_request" }).success).toBe(
      true,
    );
  });

  it("the internal register line is the clerk's words — and NEVER the code", () => {
    // The server requires a free-text `reason` the drawing does not draw. A
    // code in a free-text human column is a code on a screen one read later
    // (`DEF-CUS-5010`'s shape), so the label is stored when nothing was typed.
    expect(refusalInternalReason("duplicate_of_another_request", "  ", t)).toBe(
      t("customers.serviceRequest.refuseReason.duplicate_of_another_request"),
    );
    expect(refusalInternalReason("other", "They withdrew at the counter.", t)).toBe(
      "They withdrew at the counter.",
    );
    expect(refusalInternalReason("other", "", t)).not.toBe("other");
  });

  it("the consequence table and the money panel are both drawn", () => {
    const html = refuse();
    expect(html).toContain(t("customers.serviceRequest.refuse.willDo"));
    expect(html).toContain(t("customers.serviceRequest.willDo.refuse.can_be_reopened"));
    expect(html).toContain(t("customers.serviceRequest.refuse.theMoney"));
    expect(html).toContain('data-display="105.00"');
  });

  it("the drawn HEDGE about refunding is NOT on screen — the PO withdrew it", () => {
    // p085 says the request closes *"holding $25.00 that may have to be given
    // back"*. The PO ruled the same day that an application fee is
    // non-refundable, so drawing that hedge would print a promise the product
    // had just stopped keeping (hard-won law 1).
    const html = refuse().toLowerCase();
    expect(html).not.toContain("given back");
    expect(html).not.toContain("refund");
  });

  it("B14 rule 6 · refusing is a destructive commit and wears the danger tier", () => {
    expect(refuse()).toContain('data-variant="danger"');
  });

  it("no internal reference of any kind reaches the clerk", () => {
    expect(internalReferencesInMarkup(refuse())).toEqual([]);
  });
});

describe("REQ-02 · THE ASK-FOR-MORE DIALOG — p085/p086, DEF-CUS-5389", () => {
  function ask(): string {
    return renderToStaticMarkup(
      <AskForMoreModal
        detail={detail()}
        t={t}
        onClose={noop}
        onSubmit={() => Promise.resolve({ ok: true } as const)}
      />,
    );
  }

  it("it is a DIALOG with a tick-list, not a button that sends one canned sentence", () => {
    // ⛔ **THE DEFECT, VERBATIM:** *"Ask for more is not a dialog at all: it is
    // a plain button in the lifecycle row that fires transitionServiceRequest
    // with a CANNED string … so every request asking for more says exactly the
    // same thing and the applicant is told nothing."*
    const html = ask();
    expect(html).toContain(t("customers.serviceRequest.ask.whatIsNeeded"));
    for (const code of [
      "readable_site_plan",
      "proof_of_identity",
      "connection_date",
      "something_else",
    ]) {
      expect(html).toContain(t(`customers.serviceRequest.infoNeeded.${code}`));
      expect(html).toContain(`id="info-needed-${code}"`);
    }
    expect(html).toContain(t("customers.serviceRequest.ask.message"));
    expect(html).toContain(t("customers.serviceRequest.ask.messageHelp"));
  });

  it("B14 rule 37 · the first tick drops the drawing's illustration clause", () => {
    // Drawn *"A readable site plan — the one attached was rejected"*. The half
    // after the dash is true of the one request in the picture and false of a
    // request with nothing attached, so the LABEL is the first half.
    const label = t("customers.serviceRequest.infoNeeded.readable_site_plan");
    expect(label).toBe("A readable site plan");
    expect(ask()).not.toContain("the one attached was rejected");
  });

  it("the clerk's own words go to the applicant; the ticks are the clerk's checklist", () => {
    expect(askInternalReason(["proof_of_identity"], "Bring photo id.", t)).toBe("Bring photo id.");
    expect(askInternalReason(["proof_of_identity", "connection_date"], "", t)).toBe(
      `${t("customers.serviceRequest.infoNeeded.proof_of_identity")} · ${t(
        "customers.serviceRequest.infoNeeded.connection_date",
      )}`,
    );
    // Nothing ticked and nothing typed still satisfies the server's required
    // reason — the drawing puts an asterisk on neither control.
    expect(askInternalReason([], "", t)).toBe(t("customers.serviceRequest.reason.request_info"));
  });

  it("the consequence table says the request stays OPEN", () => {
    const html = ask();
    expect(html).toContain(t("customers.serviceRequest.ask.willDo"));
    expect(html).toContain(t("customers.serviceRequest.willDo.ask.becomes_more_info"));
    expect(html).toContain(t("customers.serviceRequest.willDo.ask.leaves_your_queue"));
  });

  it("the footer reads the drawn words", () => {
    expect(ask()).toContain(t("customers.serviceRequest.ask.submit"));
  });

  it("no internal reference of any kind reaches the clerk", () => {
    expect(internalReferencesInMarkup(ask())).toEqual([]);
  });
});

describe("REQ-02 · the three form schemas mirror server rules", () => {
  it("BR-CUS-090 · the collection form does NOT compare the amount against the quote", () => {
    // Quoted $130.00, taken $25.00 — lawful, and the form says so by accepting.
    expect(
      COLLECT_SCHEMA.safeParse({ amount: "25.00", method: "cash", receipt_no: "RCP-26-4471" })
        .success,
    ).toBe(true);
    // A receipt number is still required: ONE receipt, recorded not allocated.
    expect(
      COLLECT_SCHEMA.safeParse({ amount: "25.00", method: "cash", receipt_no: "" }).success,
    ).toBe(false);
  });

  it("rule 2 · the amount is a decimal STRING to at most four places, never a float", () => {
    expect(COLLECT_SCHEMA.safeParse({ amount: "25.1", method: "cash", receipt_no: "R" }).success).toBe(
      true,
    );
    expect(
      COLLECT_SCHEMA.safeParse({ amount: "25.00001", method: "cash", receipt_no: "R" }).success,
    ).toBe(false);
    expect(
      COLLECT_SCHEMA.safeParse({ amount: "twenty five", method: "cash", receipt_no: "R" }).success,
    ).toBe(false);
  });

  it("Park needs to know WHAT is being waited for; the note and the reminder are optional", () => {
    expect(PARK_SCHEMA.safeParse({ waiting_on: "", note: "", remind_on: "" }).success).toBe(false);
    expect(PARK_SCHEMA.safeParse({ waiting_on: "documents" }).success).toBe(true);
  });
});

describe("REQ-02 · the tab in the URL", () => {
  it("restores a named tab and falls back rather than blanking on an unknown one", () => {
    expect(requestTabFromParam("documents")).toBe("documents");
    expect(requestTabFromParam("history")).toBe("history");
    // ⚠ **`fees`, `location` AND `decision` ARE NO LONGER TABS**, so a bookmark
    // to one falls back rather than blanking. The drawing draws three
    // (p082) and every door those three carried moved onto the block the
    // drawing puts its content in — see `REQUEST_TABS`.
    expect(requestTabFromParam("fees")).toBe("applicant");
    expect(requestTabFromParam("location")).toBe("applicant");
    expect(requestTabFromParam("decision")).toBe("applicant");
    expect(requestTabFromParam("nonsense")).toBe("applicant");
    expect(requestTabFromParam(null)).toBe("applicant");
  });
});

describe("DEF-CUS-5010 · a clerk never reads a dotted key as a reason", () => {
  /** What the DATABASE holds. `service_requests.lookup_found` stores a
   *  CATALOGUE KEY by design (`service_request_service.py`), and every one of
   *  `brazosbend`'s requests carries one of these. */
  const STORED_LOOKUP_KEY = "customers.serviceRequest.lookup.servedAndVacant";

  it("the address block resolves the stored lookup key into a sentence", () => {
    const html = renderToStaticMarkup(
      <AddressBlock detail={resolved({ lookup_found: STORED_LOOKUP_KEY })} t={t} />,
    );
    expect(html).toContain(t(STORED_LOOKUP_KEY));
    expect(html).not.toContain(STORED_LOOKUP_KEY);
  });

  it("a legacy row holding real English still reads as English", () => {
    // Any request written before the column carried a key. `CatalogueSentence`
    // falls back to the value, so a sentence is never swallowed by a failed
    // lookup.
    const html = renderToStaticMarkup(
      <AddressBlock
        detail={resolved({ lookup_found: "We don't have this address on record yet" })}
        t={t}
      />,
    );
    expect(html).toContain("We don&#x27;t have this address on record yet");
  });

  /** ⚠ **THE CLERK'S-EYE ASSERTION, AND THE ONE THAT WOULD HAVE CAUGHT THIS.**
   *  Not "is this key declared" — *does any internal code reach the screen*
   *  (B14 rule 32). It reads the whole rendered tab, which is what no existing
   *  check asked. */
  it("no `customers.serviceRequest.` key appears anywhere in the rendered tab", () => {
    const html = renderToStaticMarkup(
      // ⊕ `CR-161-BRC10` W6 — the tab now reads the custom-field registry
      // (the request's own copy, gap 2), so it renders inside a QueryClient.
      <QueryClientProvider client={new QueryClient()}>
        <ApplicantTab
          detail={resolved({ lookup_found: STORED_LOOKUP_KEY })}
          t={t}
          timeZone="UTC"
          dateFormat="MM/DD/YYYY"
          working={false}
          onWaive={noop}
          onCollect={noop}
          {...noFeePicker}
        />
      </QueryClientProvider>,
    );
    expect(html).not.toContain("customers.serviceRequest.");
    expect(internalReferencesInMarkup(html)).toEqual([]);
  });

  it("the right rail is FEES ONLY — a deliberate divergence from the drawing", () => {
    // ⚠⚠ **THIS CASE IS THE EXACT REVERSE OF WHAT IT SAID YESTERDAY** ("the two
    // summary tables the drawing puts in the right column are BOTH DRAWN"), and
    // that reversal is a PO ruling rather than a regression.
    //
    // p082/p083 put `DOCUMENTS · N`, `FEES` and `HISTORY` in this rail. On
    // 2026-09-19 the PO ruled the first and third off this tab — *"we should
    // have these detials in document tab"* and *"all histroy details on
    // appplicant tab should move to history"*. **A PO instruction supersedes a
    // drawing; the drawing does not supersede the PO.** Asserted so that a lane
    // reading the blueprint and "correcting" the rail back goes RED.
    const tab = renderToStaticMarkup(
      <QueryClientProvider client={new QueryClient()}>
        <ApplicantTab
          detail={detail()}
          t={t}
          timeZone="UTC"
          dateFormat="MM/DD/YYYY"
          working={false}
          onWaive={noop}
          onCollect={noop}
          {...noFeePicker}
        />
      </QueryClientProvider>,
    );
    expect(tab).toContain('data-panel-name="fees"');
    expect(tab).not.toContain(t("customers.serviceRequest.documents.col.file"));
    // ⚠ **ASSERTED ON THE DRAWN MARKUP, NOT ON THE WORD.** A first draft used
    // `t("…history.col.who")`, which is the single word *Who* in English — and
    // *Who is asking* is a section heading two blocks up, so the assertion was
    // red over a screen that was correct. A check that fails wrongly is worse
    // than no check (hard-won law 7).
    expect(tab).not.toContain("data-actor-named");
    expect(tab).not.toContain('data-panel-name="documents-summary"');
    // ⚠ **AND THE FEES BLOCK KEEPS ITS DOOR.** `Record what was handed over` is
    // the only way in the product to take an application fee at the counter
    // after the request exists. The drawing draws this block read-only and the
    // control STAYS — removing a live door because a drawing predates it is
    // hard-won law 2's mirror (PO removal list, row 18).
    expect(tab).toContain(t("customers.serviceRequest.fees.collect"));
  });

  it("the History tab is the drawn WHEN · WHAT · WHO table, and WHO is a NAME", () => {
    const history = (d = detail()) => renderToStaticMarkup(<HistoryTab detail={d} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" working={false} onAddNote={noop} />);
    const html = history();
    expect(html).toContain(t("customers.serviceRequest.history.col.when"));
    expect(html).toContain(t("customers.serviceRequest.history.col.what"));
    expect(html).toContain(t("customers.serviceRequest.history.col.who"));
    // The name the server now resolves — p083 prints `S. Ortiz` in this column.
    expect(html).toContain("S. Ortiz");
    // ⚠ **AND THE TWO NOTES THAT STOOD IN FOR IT ARE GONE.** The tab carried
    // *"Who acted is not named yet"* over an empty column and *"Nothing on this
    // timeline is ever edited or removed…"* under the list. The first was a
    // stated absence over a fact the server was holding all along; the second
    // is RATIONALE, which B14 rule 33 gives zero words on screen.
    expect(html).not.toContain(t("customers.serviceRequest.history.actorNotNamed"));
    expect(html).not.toContain(t("customers.serviceRequest.history.appendOnly"));
  });

  it("the WHO column never prints the actor id — B14 rule 31", () => {
    // ⚠ **THE FIRST DRAFT OF THIS CASE COULD NOT FAIL.** Putting `event.actor`
    // back into the cell left every case green, because the fixture's actor
    // reads `user-1` and nothing looked at it. That is hard-won law 7's *check
    // that cannot fail*, found the way law 7 says to find one: by asking what
    // would make it pass wrongly. The fixture carries a real UUID here.
    const history = (d = detail()) => renderToStaticMarkup(<HistoryTab detail={d} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" working={false} onAddNote={noop} />);
    const withUuid = detail();
    withUuid.history = withUuid.history.map((row) => ({
      ...row,
      actor: "01a0a444-5ad2-7e88-be8a-bdb8aa86c05e",
    }));
    const drawn = history(withUuid);
    expect(drawn).not.toContain("01a0a444-5ad2-7e88-be8a-bdb8aa86c05e");
    expect(drawn).not.toContain("user-1");
    expect(internalReferencesInMarkup(drawn)).toEqual([]);
    // A row with no user is a dash, never a name invented by the server.
    expect(drawn).toContain('data-actor-named="false"');
  });

  /**
   * ⚠ **`DEF-CUS-6181` — PO report 2026-09-22, row 7: *"A row cannot be both
   * System and a person."***
   *
   * The PO read an Audit tab where **every** row's WHO said `Vijay Bikkad`,
   * including the rows whose WHAT said `System`, and where two entries were
   * `System / SR-26-0011` and `System / This address is not on record.` —
   * neither of which says what happened.
   *
   * **Two faults, and only one of them is a word.** The WHAT column rendered
   * `kind`, which is a category of three and is the DEFAULT for every side
   * effect a clerk causes, so ten different acts all read `System`; and the
   * word sat in the column that answers *what happened* while the column that
   * answers *who* carried the clerk's name. The act's real name has been in
   * `note_type` since the field existed and no screen read it.
   *
   * ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7): a version that simply
   * stopped printing `System` anywhere would satisfy *the two columns do not
   * both say it*. So the act is asserted BY NAME, and `System` is asserted to
   * be PRESENT on the one row that genuinely has no actor.
   */
  it("DEF-CUS-6181 · WHAT names the act and WHO says System only where nobody acted", () => {
    const history = (d = detail()) => renderToStaticMarkup(<HistoryTab detail={d} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" working={false} onAddNote={noop} />);
    const audited = detail();
    audited.history = [
      // A clerk numbered it. `kind` is `system` because that is the DEFAULT for
      // a side effect, and the act is in `note_type`.
      {
        ...audited.history[0],
        kind: "system",
        actor_name: "V. Bikkad",
        note: "SR-26-0011",
        note_type: "number_allocated",
        to_state: null,
      },
      // A clerk took a fee. The tail after the colon is a VALUE, not a
      // vocabulary — the family before it is what names the act.
      {
        ...audited.history[1],
        id: "ev-fee",
        kind: "system",
        actor_name: "V. Bikkad",
        note: null,
        note_type: "fee_collected:cash",
        to_state: null,
      },
      // Nobody was signed in. THIS is the row the word belongs to.
      {
        ...audited.history[1],
        id: "ev-job",
        kind: "system",
        actor_name: null,
        note: null,
        note_type: null,
        to_state: null,
      },
    ];
    const drawn = history(audited);

    // The acts are NAMED.
    expect(drawn).toContain(t("customers.serviceRequest.eventType.number_allocated"));
    expect(drawn).toContain(t("customers.serviceRequest.eventType.fee_collected"));
    expect(drawn).toContain('data-event-type="number_allocated"');
    expect(drawn).toContain('data-event-type="fee_collected"');
    // The tail is not printed at a clerk (B14 rule 32 — no internal code).
    expect(drawn).not.toContain("fee_collected:cash");
    expect(internalReferencesInMarkup(drawn)).toEqual([]);

    // `System` appears ONCE, and it is in the WHO column of the row with no
    // actor — never beside a named person.
    expect((drawn.match(new RegExp(t("customers.serviceRequest.event.system"), "g")) ?? []).length)
      .toBe(1);
    expect(drawn).toContain('data-actor="system"');
    expect(drawn).toContain('data-actor-named="false"');
  });

  it("DEF-CUS-9091 · a row the CUSTOMER wrote names the customer, never System", () => {
    const history = (d = detail()) => renderToStaticMarkup(<HistoryTab detail={d} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" working={false} onAddNote={noop} />);
    const replied = detail();
    replied.history = [
      // The applicant sent a file from Track (DEF-CWP-9049): no staff actor,
      // and the server says the customer acted and who they are.
      {
        ...replied.history[0],
        id: "ev-reply",
        kind: "note",
        actor_name: "Ama Boateng",
        actor_kind: "customer",
        note: "w14-second-id.png",
        note_type: "customer_replied:document",
        to_state: null,
      },
      // A customer row with no applicant name on the request.
      {
        ...replied.history[1],
        id: "ev-note",
        kind: "note",
        actor_name: null,
        actor_kind: "customer",
        note: "I can send it on Monday.",
        note_type: "customer_note",
        to_state: null,
      },
    ];
    const drawn = history(replied);
    expect(drawn).toContain(t("customers.serviceRequest.event.customerWho", { name: "Ama Boateng" }));
    expect(drawn).toContain(t("customers.serviceRequest.event.customerUnnamed"));
    expect(drawn).toContain('data-actor="customer"');
    expect(drawn).not.toContain('data-actor="system"');
  });

  it("DEF-CUS-5420 / DEF-CUS-5422 · a stored key and a reason code both resolve", () => {
    const history = (d = detail()) => renderToStaticMarkup(<HistoryTab detail={d} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" working={false} onAddNote={noop} />);
    // ⛔ **`DEF-CUS-5420`, FOUND BY THE BROWSER WALK AND BY NOTHING ELSE.** A
    // timeline note is a clerk's free text on one row and a STORED CATALOGUE
    // KEY on another — the address lookup writes
    // `customers.serviceRequest.lookup.servedAndOccupied` into `note` — and the
    // History tab printed it verbatim. Measured on the running product at 1440
    // and 1280 on `SR-26-0005`.
    const keyed = detail();
    keyed.history = [
      { ...keyed.history[0], note: "customers.serviceRequest.lookup.servedAndOccupied" },
      { ...keyed.history[1], note: "No proof of address supplied." },
    ];
    const resolvedNotes = history(keyed);
    expect(resolvedNotes).not.toContain("customers.serviceRequest.lookup.servedAndOccupied");
    expect(resolvedNotes).toContain(t("customers.serviceRequest.lookup.servedAndOccupied"));
    // …and a clerk's own sentence still reads as itself.
    expect(resolvedNotes).toContain("No proof of address supplied.");

    // ⛔ **`DEF-CUS-5422` — THE SAME DEFECT ONE SHAPE ALONG.** The fix above
    // resolves a DOTTED catalogue key. The acknowledgement path stores
    // SNAKE_CASE reason codes in the same column, and those fell straight
    // through the `defaultValue` fallback.
    //
    // ⚠ **THE ASSERTION IS THE GENERAL SHAPE, NOT THE FOUR CODES WE KNOW.**
    const coded = detail();
    coded.history = [
      { ...coded.history[0], note: "applicant_supplied_no_email_or_phone" },
      { ...coded.history[1], note: "Landlord's agent must be present." },
    ];
    const codedNotes = history(coded);
    expect(codedNotes).not.toContain("applicant_supplied_no_email_or_phone");
    expect(codedNotes).toContain(t("customers.serviceRequest.event.systemNoteUnreadable"));
    // A clerk's sentence with an apostrophe still reads as itself — and it is
    // compared ESCAPED, because React escapes five characters into markup
    // (`DEF-CUS-5414`, this file's own trap).
    expect(codedNotes).toContain(escapeHtml("Landlord's agent must be present."));
  });

  it("the Documents tab is the drawn three columns, and a broken file cannot read Verified", () => {
    // ⛔ **`DEF-CUS-5872` ON THE SCREEN.** Six seeded rows on the beta point at
    // a file that does not exist and FOUR of them read `verified`. The chip
    // asks `file_present`, so the row says `Nothing attached` and the file cell
    // is a dash — whatever the state column claims.
    const broken = detail();
    broken.documents.documents = [
      {
        ...broken.documents.documents[0],
        name: "driving-licence.pdf",
        attached: true,
        verification_state: "verified",
        file_present: false,
      },
    ];
    const html = renderToStaticMarkup(
      <DocumentsTab
        detail={broken}
        t={t}
        onVerify={noop}
        onReject={noop}
        onOpen={noop}
        openingId={null}
        openError={null}
        working={false}
      />,
    );
    expect(html).toContain(t("customers.serviceRequest.documents.col.document"));
    expect(html).toContain(t("customers.serviceRequest.documents.col.file"));
    expect(html).toContain(t("customers.serviceRequest.documents.col.state"));
    expect(html).toContain(t("customers.serviceRequest.documents.state.nothingAttached"));
    expect(html).not.toContain("driving-licence.pdf");
    expect(html).not.toContain(t("customers.serviceRequest.documents.state.verified"));
    expect(html).toContain('data-file-present="false"');
    // ⚠ **AND THE THREE RATIONALE PARAGRAPHS ARE GONE** (B14 rules 32 and 33).
    expect(html).not.toContain(t("customers.serviceRequest.documents.gateCreation"));
    expect(html).not.toContain(t("customers.serviceRequest.documents.checklistEmpty"));
  });
});

/** React escapes five characters when it renders to a string. A catalogue
 *  value compared against MARKUP has to be escaped the same way, or the
 *  comparison is a check that fails wrongly. Same shape as
 *  `routing/sidebarReachability.test.tsx`'s. */
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W4 task 4.15 · B18 §5.3.9 · B19 §12.2/§12.3
// generated: 2026-08-24 by the CR-031 W4 FRONTEND lane (M3)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: vitest✔
// exceptions: E3 the tabs are asserted as COMPONENTS rather than through the
//   page, because `renderToStaticMarkup` never resolves the detail query and
//   the page would draw its skeleton — the same limitation `AccountUsageTab
//   .test` records. The page-level wiring is proved by the browser walkthrough
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────


/*
 * ⛔ **`DEF-CUS-5902`'s FOUR CASES ARE RETIRED WITH THEIR SUBJECT — PO report
 * 2026-09-22, rows 14 and 15.**
 *
 * They proved that `RequestedStart` read `unset` and did not invent a
 * disagreement: three services where NOBODY gave a date printed the request's
 * own date and not *"Different days per service."*, and a request where some
 * gave one and some did not still said so. That was a real regression, found
 * in a browser by a clerk walk and by no check here, and these cases were
 * written from the server's own sentence so the two worlds could not be
 * collapsed again.
 *
 * **The component is deleted** — the PO replaced the flat `Requested start`
 * row with `RequestedServicesTable`, which takes its last caller with it, and
 * `G13` named it as dead UI. A case whose subject does not exist cannot go
 * red, so retiring it beats leaving four green assertions about nothing.
 *
 * ⚠ **THE RULE IS NOT RETIRED AND IS NOT UNGUARDED.** The distinction lives
 * where it was always decided — `_requested_start_agreement` in
 * `service_request_reads`, whose docstring states both worlds and which is
 * tested server-side — and `requested_start_agreement` is still served on
 * every request. What is gone is one screen's rendering of it.
 *
 * ⚠ **AND THE TABLE CANNOT MAKE THE SAME MISTAKE.** It prints the per-service
 * dates themselves, one row each, so there is no summary SENTENCE to get
 * wrong; `BR-CUS-1070`'s rule that neither date falls back to the other is in
 * `RequestedServicesTable`'s own docstring, and the capture suite's
 * three-column case is what holds it.
 */



describe("DEF-CUS-5903 · the customer category is given back to the clerk", () => {
  /**
   * ⚠ **A LIVE WRITE THAT HAS NOW LOST ITS READ TWICE.** The clerk is REQUIRED
   * to pick a customer category on capture step 2 and the server has stored it
   * since W4. The read was added on 2026-08-25 precisely because the column was
   * *"a live WRITE with no READ"* — and the 2026-09-19 Applicant-tab rebuild
   * dropped the row again, so the server went on serving it and no tab gave it
   * back. A clerk could not check it, correct it, or answer a question about it.
   *
   * ⚠ **NO CHECK IN THIS REPOSITORY COULD HAVE CAUGHT THAT**, which is why
   * these cases exist rather than a note: a row that is simply ABSENT fails
   * nothing — not `tsc`, not a snapshot nobody took, not a gate. It was found
   * by a clerk walk in a browser (hard-won law 6).
   */
  const withCategory = (
    category: ServiceRequestDetail["applicant"]["customer_category"],
  ) => {
    const d = detail();
    return renderToStaticMarkup(
      <WhoIsAskingBlock
        detail={{ ...d, applicant: { ...d.applicant, customer_category: category } }}
        t={t}
        timeZone="UTC"
        dateFormat="MM/DD/YYYY"
      />,
    );
  };

  it("prints the category's NAME, and never its database id", () => {
    const html = withCategory({
      account_type: { id: "01a0ba93-a7c3-7027-8b47-da96b2c5a7c0", code: "residential", name: "Residential" },
      account_subtype: null,
      not_yet_categorised: false,
    });
    expect(html).toContain("Residential");
    // B14 rule 31 — the id is served and must never be the visible value
    expect(html).not.toContain("01a0ba93-a7c3-7027-8b47-da96b2c5a7c0");
    // and not the machine code either
    expect(html).not.toContain("residential");
  });

  it("names the sub-category beside it when there is one", () => {
    const html = withCategory({
      account_type: { id: "x", code: "commercial", name: "Commercial" },
      account_subtype: { id: "y", code: "restaurant", name: "Restaurant" },
      not_yet_categorised: false,
    });
    expect(html).toContain("Commercial");
    expect(html).toContain("Restaurant");
  });

  it("a request that has not reached step 2 draws no row at all", () => {
    // Not a stated absence: the clerk is not there yet, and the server says so
    // with `not_yet_categorised` rather than an `_absence`/`tracks` pair.
    const html = withCategory({
      account_type: null,
      account_subtype: null,
      not_yet_categorised: true,
    });
    expect(html).not.toContain('data-drawn-row="customer-category"');
  });

  it("a payload older than the field does not crash the block", () => {
    expect(() => withCategory(undefined)).not.toThrow();
  });
});


describe("DEF-CUS-5907 · what a document proves is given back to the clerk", () => {
  /**
   * ⚠ **THE THIRD VALUE THIS WALK FOUND IN THE SAME POSITION** — a clerk types
   * it on the capture form, the product stores it, the server serves it, and
   * no screen gives it back. `what_it_proves` has been on the `documents_tab`
   * payload all along and the table drew `Document · File · State · Actions`.
   *
   * ⚠ **AND THE COLUMN HEADER ALREADY EXISTED IN ALL ELEVEN CATALOGUES**,
   * minted for the capture form. A translated header for a column nobody
   * built is hard-won law 1 living in the catalogue, and it is now true.
   */
  it("the drawn column is there and carries the clerk's own words", () => {
    const html = renderToStaticMarkup(
      <DocumentsTab
        detail={detail()}
        t={t}
        onVerify={noop}
        onReject={noop}
        onOpen={noop}
        openingId={null}
        openError={null}
        working={false}
      />,
    );
    expect(html).toContain(t("customers.serviceRequest.documents.col.whatItProves"));
    expect(html).toContain("A driving licence, passport or state ID");
  });

  it("a document nobody wrote a purpose for is a dash, never a guess", () => {
    const d = detail();
    const docs = d.documents;
    const blanked = {
      ...d,
      documents: {
        ...docs,
        documents: docs.documents.map((row) => ({ ...row, what_it_proves: null })),
      },
    };
    const html = renderToStaticMarkup(
      <DocumentsTab
        detail={blanked}
        t={t}
        onVerify={noop}
        onReject={noop}
        onOpen={noop}
        openingId={null}
        openError={null}
        working={false}
      />,
    );
    expect(html).toContain(t("customers.serviceRequest.documents.col.whatItProves"));
    expect(html).not.toContain("A driver's license, passport or state ID");
  });
});
