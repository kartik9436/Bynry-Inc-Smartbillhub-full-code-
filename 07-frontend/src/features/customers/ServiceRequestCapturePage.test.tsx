// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// ⚠ **THIS FILE OPTED INTO jsdom ON 2026-08-25 (CR-033).** Everything below
// was written against the default `node` environment and `renderToStaticMarkup`
// and still runs exactly as it did — that renderer needs no DOM and does not
// care that one is present. The pragma is here because CR-033's claims are
// about a WIZARD STEP, and `WizardFrame` renders one step at a time behind its
// own nav state: the file's own exception note already said the six steps
// *"are exercised in the browser walkthrough rather than here …
// `renderToStaticMarkup` cannot click"*. Step 1 is the one step a static render
// CAN reach, and the CR-033 block below still needs to click Continue to prove
// the category GATE. `vite.config.ts` documents the pragma as the per-file
// opt-in.
//
// Change:   CR-030 W4 task 4.15 — the `TC-REQ-*` cases with a FRONTEND surface,
//           for **S85 · REQ-03.1–6 and REQ-03.sent**.
// Rules:    BR-CUS-093 (the two copy lines it made FALSE) · BR-CUS-090 clause
//           (3) (the acknowledgement may not say *"Nothing is charged"* over a
//           collected fee) · BR-CUS-091 (a staff-raised request needs no
//           applicant name) · BR-CUS-092 (no identifier control is drawn)
// ───────────────────────────────────────────────────────
//
// The assertions that matter most here are the NEGATIVE ones, and each is a
// sentence a ruling DELETED:
//   * *"nothing is created until you submit"* must appear nowhere;
//   * *"the request is created and numbered when the fee is collected"* must
//     appear nowhere;
//   * *"Nothing is charged"* must NOT appear on a confirmation showing cash
//     collected;
//   * no `Social Security Number` input may exist.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// Registers `toBeInTheDocument` and friends on vitest's `expect`, scoped to
// this file — the repo has no global setup file, deliberately.
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import { emptyCoOwner } from "./CoOwnerCards";
import { feeCollectionBody } from "./RequestPaymentDetails";
import {
  CaptureConfirmation,
  CAPTURE_STEPS,
  captureStepNumber,
  ServiceRequestCapturePage,
  blankOptionalCount,
  canCreateDraft,
  capturePayload,
  clearOtherKind,
  filterDocRows,
  docRequired,
  IDENTITY_CAPTURE_ACCEPTED,
  identityPayload,
  matchRows,
  SERVICE_STARTS_WRITE_PATH_EXISTS,
  serviceStartsPayload,
  emptyCaptureForm,
  maskSsn,
} from "./ServiceRequestCapturePage";
import { CaptureDraftFooter } from "./serviceRequestShared";
import { internalReferencesIn } from "@/testSupport/internalReferences";
import type {
  Money,
  ServiceRequestDetail,
  ServiceRequestDocument,
} from "./serviceRequestEndpoints";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function money(amount: string, display: string, currency: string | null = "USD"): Money {
  return { amount, display, currency };
}

/** Only the parts of the detail `REQ-03.sent` reads. */
function sent(over: { collected?: string; receipt?: string | null } = {}): ServiceRequestDetail {
  const collected = over.collected ?? "25.0000";
  const receipt = over.receipt === undefined ? "RCP-26-4471" : over.receipt;
  return {
    header: {
      id: "sr-0056",
      request_no: "SR-26-0056",
      number_absence: null,
      state: "submitted",
      // §8 — the register tab an APPROVED request's work landed on. `null`
      // here because neither fixture is approved, which is also the value the
      // server serves for every unapproved request.
      queue: null,
      classification: "not_yet_classified",
      applicant: "Okonkwo, David",
      address_as_given: "14 Willow Bend",
      address_unit_as_given: null,
      // Nothing matched, so there is no premises to walk to for a town.
      premise_locality: null,
      lookup_found: null,
      received_at: "2026-08-24T09:00:00Z",
      received_by: "user-1",
      channel: "physical_form",
      waiting_on: null,
      waiting_since: null,
      requested_start: "2026-09-15",
    },
    actions: { available: [], can_approve: false, approve_blocked_by: [], can_park: true },
    applicant: {
      name: "Okonkwo, David",
      phone: null,
      email: null,
      language: null,
      person_or_company: "person",
      co_applicant: { name: null, email: null, phone: null },
      // DEF-632 — the identifier is a VALUE now, and this fixture is an
      // applicant who gave none: `ssn_present: false` must never draw the
      // "stored encrypted" claim over a blank column (BR-CUS-092(d)).
      identifier: {
        ssn_last4: null,
        ssn_present: false,
        stored_encrypted: false,
        drivers_licence_last4: null,
        drivers_licence_present: false,
        drivers_licence_stored_encrypted: false,
      },
      date_of_birth: null,
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
      // `14 Willow Bend` is B19 §7's address that resolves to NOTHING, so every
      // named field is null — never a blank string, which would read on screen
      // as *we looked and found nothing there*.
      resolved_premises_no: null,
      resolved_unit_no: null,
      resolved_premise_address: null,
      premise_locality: null,
      resolved_match: null,
      resolution_kind: "no_premise",
      lookup_found: null,
      plot_or_parcel: null,
      what_is_being_built: null,
      property_type: null,
      no_premise_flag: true,
      services: [],
      // BR-CUS-1070 — a request that has not reached step 2 yet. `count` 0 is a
      // real answer and nothing may divide by it.
      requested_start_agreement: { count: 0, agreed: null, unset: 0 },
      evidence: { premise_exists: false, unit_is_served: false, unit_is_vacant: false },
    },
    documents: {
      documents: [],
      verified: 0,
      attached: 0,
      blocks_creation: false,
      blocks_approval: false,
      outstanding: false,
      checklist_request_type: null,
      checklist_required: [],
      checklist_unmet: [],
    },
    fees: {
      lines: [],
      outstanding_lines: 0,
      quoted: money("130.0000", "130.00"),
      settled: money("0.0000", "0.00"),
      collected: money(collected, collected === "0.0000" ? "0.00" : "25.00"),
      outstanding: money("105.0000", "105.00"),
      shortfall_is_open_balance: collected !== "0.0000",
      receipt_no: receipt,
      collected_at: receipt === null ? null : "2026-08-24T09:05:00Z",
      quoted_at_collection: money("130.0000", "130.00"),
      fee_timing: "collect_now",
      fee_due_by: null,
      fee_method: "cash",
      posts_to_ledger: false,
      connection_quote: { raised: false, reason: "raised_after_review" },
    },
    decision: {
      what_they_said: null,
      what_the_lookup_found: null,
      options: [],
      // `CR-094-BRC01` wave 1 — the two dialogs read back, and one approval
      // preview per outcome. This screen draws none of them; the three keys are
      // here because the payload carries them and a fixture that lies about the
      // payload is a fixture that cannot catch anything.
      refusal: { reason_code: null, reason: null, message: null },
      more_info: { needed: [], message: null },
      what_approving_will_do: {},
      preselected: null,
      undrawn_verdict_absence: { tracks: "OQ-356" },
      conditions: {
        clear: 0,
        total: 4,
        blocking: [],
        conditions: [],
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
      acknowledgement: { state: null, reason: null, ref: null, sent: false, fee_statement: null },
    },
    history: [],
    unavailable: [
      {
        code: "acknowledgement_cannot_be_queued",
        br_ref: "BR-CUS-079",
        detail:
          "No acknowledgement has been sent to the applicant and none is waiting to be " +
          "sent. Tell them yourself if they need confirming.",
      },
    ],
  };
}

/**
 * A saved draft carrying THREE document rows, one of each kind p078 draws.
 *
 * ⚠ **THE THIRD ROW IS `DEF-CUS-5872` IN A FIXTURE, DELIBERATELY.** It says
 * `attached: true` and `verification_state: "verified"` while `file_present`
 * is `false` and `size_bytes` is `null` — which is the exact shape of all six
 * rows on the beta, whose `storage_ref` points at a file nobody ever stored. A
 * fixture in which `attached` and `file_present` always agree cannot tell a
 * working column from a broken one, which is the flaw hard-won law 7 names.
 */
function docRow(
  over: Partial<ServiceRequestDocument> & { doc_type: string },
): ServiceRequestDocument {
  return {
    id: `doc-${over.doc_type}`,
    what_it_proves: null,
    document_number: null,
    name: null,
    uploaded_at: null,
    uploaded_by: null,
    uploaded_by_name: null,
    size_bytes: null,
    original_size_bytes: null,
    attached: false,
    file_present: false,
    required: false,
    verification_state: "not_checked",
    verified_at: null,
    reject_reason: null,
    ...over,
  };
}

function withDocs(): ServiceRequestDetail {
  const base = sent();
  return {
    ...base,
    documents: {
      ...base.documents,
      documents: [
        docRow({
          doc_type: "proof_of_identity",
          name: "driving-licence.pdf",
          size_bytes: 1_240_000,
          uploaded_at: "2026-04-05T14:00:00Z",
          uploaded_by: "user-1",
          uploaded_by_name: "S. Ortiz",
          attached: true,
          file_present: true,
          verification_state: "verified",
          verified_at: "2026-04-06T09:00:00Z",
        }),
        docRow({ doc_type: "tenancy_agreement_or_deed" }),
        // The broken one: a ref that resolves to nothing, still reading
        // `verified`. See the note above.
        docRow({
          doc_type: "site_plan_or_unit_schedule",
          name: "block-plan.pdf",
          attached: true,
          file_present: false,
          verification_state: "rejected",
          reject_reason: "unreadable",
        }),
      ],
      attached: 2,
      verified: 1,
    },
  };
}

describe("REQ-03 · the frame (BR-CUS-093's two deleted sentences)", () => {
  it("the stepper is FOUR — the redesign of 2026-09-29, and DEF-633 still holds", () => {
    // `DEF-633` was a stepper, a footer and a header disagreeing about the
    // count. The count moved 6 → 4 with the PO's approval; what the defect is
    // about — that one number answers everywhere — is unchanged.
    expect(CAPTURE_STEPS).toHaveLength(4);
  });

  /**
   * **THE REVIEW'S EDIT LINKS COME OUT OF THE ARRAY, NEVER TYPED.** The
   * drawing reads `Edit step 1 · 2 · 3`; a literal would be right today and a
   * live control pointing at the wrong page the next time the flow moves —
   * which is `DEF-633`'s own shape one screen along.
   *
   * RED first: with the links back on literals this passed and the case below
   * it (the rendered `data-review-edit` handles) did not — which is why BOTH
   * exist.
   */
  it("REQ-03 · the drawn Edit-step numbers are derived from CAPTURE_STEPS", () => {
    expect(captureStepNumber("applicant")).toBe(1);
    expect(captureStepNumber("property")).toBe(2);
    expect(captureStepNumber("service")).toBe(3);
    expect(captureStepNumber("review")).toBe(4);
  });

  it("BR-CUS-093(b) · the footer names the DRAFT NUMBER, and never the old sentence", () => {
    const html = renderToStaticMarkup(
      <CaptureDraftFooter step={2} steps={4} requestNo="SR-26-0048" t={t} />,
    );
    expect(html).toContain(
      t("customers.serviceRequest.capture.draftFooter", {
        step: 2,
        steps: 4,
        number: "SR-26-0048",
      }),
    );
    // ⛔ The sentence the ruling made FALSE.
    expect(html.toLowerCase()).not.toContain("nothing is created until you submit");
  });

  it("before the server's minimum is met the footer says NOT SAVED, never a number", () => {
    const html = renderToStaticMarkup(
      <CaptureDraftFooter step={1} steps={6} requestNo={null} t={t} />,
    );
    expect(html).toContain(
      t("customers.serviceRequest.capture.draftFooterUnnumbered", { step: 1, steps: 6 }),
    );
    expect(html).not.toContain("SR-26-");
  });
});

describe("REQ-03 · what the server will accept before a row exists", () => {
  /**
   * ⚠ **THESE TWO CASES ARE REWRITTEN, NOT DELETED — PO ratification
   * 2026-09-20 (`DEF-CUS-6006`).** Each asserted *"and still an address"*, and
   * that clause is what the ruling moved to SUBMIT. The QUESTION each was
   * asking is untouched and is what they still ask: does an applicant-raised
   * request need a NAME (yes), and does `BR-CUS-091` lift it on a staff-raised
   * channel (yes). Deleting them would have taken the name guard with the
   * address guard, and the name did not move.
   */
  it("an applicant-raised request needs a NAME — the address moved to submit", () => {
    const form = emptyCaptureForm();
    expect(canCreateDraft(form)).toBe(false);
    expect(canCreateDraft({ ...form, applicant_name: "Osei, Grace" })).toBe(true);
    // An address with no name is still not enough: only the address moved.
    expect(canCreateDraft({ ...form, address_as_given: "14 Willow Bend" })).toBe(false);
    expect(
      canCreateDraft({
        ...form,
        applicant_name: "Osei, Grace",
        address_as_given: "14 Willow Bend",
      }),
    ).toBe(true);
  });

  it("BR-CUS-091 · a STAFF-RAISED request needs nothing at all", () => {
    // *"Collections raising a disconnect on 500 Main is not somebody applying
    // for anything, and demanding an applicant name would make the clerk invent
    // one."* ⚠ *"There is no service request about nowhere"* is still true —
    // of a REQUEST. It was never true of a DRAFT, and `_require_submit_minimum`
    // is where it is now enforced.
    const staff = { ...emptyCaptureForm(), channel: "staff_collections" };
    expect(canCreateDraft(staff)).toBe(true);
    expect(canCreateDraft({ ...staff, address_as_given: "500 Main" })).toBe(true);
  });

  it("the payload carries ONLY fields `_clean_capture` accepts — twelve names still banned", () => {
    const payload = capturePayload({
      ...emptyCaptureForm(),
      applicant_name: "Osei, Grace",
      address_as_given: "14 Willow Bend",
    });
    const keys = Object.keys(payload);
    // ⚠ **`ssn` LEFT THIS LIST ON 2026-08-27 AND NOTHING ELSE DID — DEF-632.**
    // It used to head the banned names, correctly, while the column did not
    // exist. The PO ruled on the Social Security number and not on identifiers
    // in general, so the list is one name shorter and no shorter than that.
    // `ssn` is asserted PRESENT in the DEF-632 block at the foot of this file.
    for (const banned of [
      "social_security_number",
      "gov_id",
      "gov_id_number",
      "id_number",
      "national_id",
      "ein",
      "tin",
      // ⊕ `gov_id_last4` left 2026-10-18 (lane CF-1) — Move-in's Government ID, kept as four (BR-CUS-045).
      "ssn_last4",
      // ⚠ **`drivers_licence_last4` REPLACED `date_of_birth`/`dob` HERE ON
      // 2026-09-15** — lane G opened those two on the PO's ruling and closed
      // the same door behind them: there is no `_last4` COLUMN for a licence
      // any more than for an SSN, so a caller-supplied last four would put
      // four digits of a government identifier in the clear beside the
      // ciphertext and make `BR-CUS-092(c)` false while every test passed.
      "drivers_licence_last4",
      "acting_for",
    ]) {
      expect(keys).not.toContain(banned);
    }
  });

  it("a co-applicant that was never added contributes nothing", () => {
    // ⊕ Lane CF-1 — the full cards replace the three boxes: an unticked
    // panel sends an EMPTY list, so a card typed then unticked is dropped.
    const payload = capturePayload({
      ...emptyCaptureForm(),
      applicant_name: "Osei, Grace",
      address_as_given: "14 Willow Bend",
      add_co_applicant: false,
      co_applicants: [{ ...emptyCoOwner(), full_name: "typed then unticked" }],
    });
    expect(payload.co_applicants).toEqual([]);
    expect(payload).not.toHaveProperty("co_applicant_name");
  });
});

describe("REQ-03.6 · the computed blank count", () => {
  it("counts the OPTIONAL blanks only — the required ones are gated at their step", () => {
    const form = emptyCaptureForm();
    expect(blankOptionalCount(form)).toBe(6);
    expect(
      blankOptionalCount({ ...form, applicant_email: "a@b.test", applicant_phone: "555" }),
    ).toBe(4);
  });
});

describe("REQ-03.sent · the confirmation (BR-CUS-090 clause 3 · BR-CUS-079)", () => {
  function render(detail: ServiceRequestDetail): string {
    return renderToStaticMarkup(
      <MemoryRouter initialEntries={["/brazosbend/requests/new"]}>
        <CaptureConfirmation detail={detail} t={t} />
      </MemoryRouter>,
    );
  }

  it("the number is the headline — an actual <h1> — and it is quotable", () => {
    const html = render(sent());
    // ⚠ **THE BROWSER WALKTHROUGH FOUND THIS AND NOTHING ELSE DID.** The number
    // was a `<p>`, so the confirmation had no main heading at all and failed
    // the walkthrough's own first rule. Every other screen in this feature gets
    // its `<h1>` from `PageHeader`; this one has no page header and owns its.
    expect(html).toMatch(/<h1[^>]*data-request-no="SR-26-0056"/);
    expect(html).toContain(t("customers.serviceRequest.sent.quoteThisNumber"));
  });

  /**
   * ⛔ **BR-CUS-090(3)'s TWO SENTENCES ARE OFF THE CONFIRMATION — `DEF-CUS-6414`,
   * 2026-09-23.** These two cases asserted *"Nothing is charged…"* where no
   * money was taken and *"…was taken by cash. The receipt number is…"* where
   * it was. Both described what the acknowledgement EMAIL says, which is
   * notifications' template to get right (and it does — the class that states
   * the money is pinned when a receipt exists); on a clerk's screen they were
   * 15 and 26 words of rationale beside a panel stating the money in figures.
   * B14 rule 33 puts rationale at zero words, so both directions now assert
   * ABSENCE — and the money itself is asserted, with its currency.
   */
  it("BR-CUS-090(3) · neither money sentence is printed where cash was taken — the figures are", () => {
    const html = render(sent());
    expect(html).not.toContain("Nothing is charged");
    expect(html).not.toMatch(/was taken by/);
    // The taken amount, with its currency (`DEF-CUS-6412`), and the tender's
    // LABEL rather than its code (`DEF-CUS-6413`).
    expect(html).toContain("$25.00");
    expect(html).toMatch(/data-sent-method="cash">Cash</);
  });

  it("…and none is printed where nothing was taken either", () => {
    const html = render(sent({ collected: "0.0000", receipt: null }));
    expect(html).not.toContain("Nothing is charged");
  });

  /**
   * ⚠ **THE ACKNOWLEDGEMENT PANEL READS THE REQUEST'S OWN STATE — `DEF-CUS-6418`.**
   * This case asserted the server's STATIC sentence, *"No acknowledgement has
   * been sent to the applicant…"*, which had been false since 2026-09-15:
   * `submit` queues the email whenever the applicant gave one.
   */
  it("BR-CUS-079 · never 'sent automatically' — and 'queued' only where the request says so", () => {
    const unqueued = render(sent());
    expect(unqueued.toLowerCase()).not.toContain("sent automatically");
    expect(unqueued).toContain(t("customers.serviceRequest.sent.ackNotQueued"));
    expect(unqueued).toContain(t("customers.serviceRequest.sent.ackTellThem"));
    expect(unqueued).not.toContain("none is waiting");

    const base = sent();
    const queued = render({
      ...base,
      decision: {
        ...base.decision,
        acknowledgement: { state: "queued", reason: null, ref: "OM-1", sent: false, fee_statement: null },
      },
    });
    expect(queued).toContain(t("customers.serviceRequest.sent.ackQueued"));
    expect(queued).not.toContain(t("customers.serviceRequest.sent.ackTellThem"));

    const noEmail = render({
      ...base,
      decision: {
        ...base.decision,
        acknowledgement: {
          state: "not_sent",
          reason: "applicant_supplied_no_email_address",
          ref: null,
          sent: false,
          fee_statement: null,
        },
      },
    });
    expect(noEmail).toContain(t("customers.serviceRequest.sent.ackNoEmail"));
  });

  it("`Print receipt` is NOT drawn — payments owns the receipt series", () => {
    const html = render(sent());
    expect(html).toContain(t("customers.serviceRequest.sent.openTheRequest"));
    expect(html).toContain(t("customers.serviceRequest.sent.captureAnother"));
    expect(html.toLowerCase()).not.toContain("print receipt");
  });

  it("the four WHAT HAPPENS NEXT lines are all four", () => {
    const html = render(sent());
    for (const n of [1, 2, 3, 4]) {
      expect(html).toContain(t(`customers.serviceRequest.sent.next${n}`));
    }
  });
});


// ══════════════════════════════════════════════════════════════════════════
// CR-033 · STEP 1 IS THE CUSTOMER CATEGORY, AND IT LOOKS LIKE ACC-03
// ══════════════════════════════════════════════════════════════════════════
//
// PO, 2026-08-25, on `/requests/new` step 1 and then on `/accounts/new` step 1:
//   *"on this screen - apply as - we need customer categories that we have from
//    settings - ehre as drop down"*
//   *"why don you make request staep 1 simialr to this one -"*
//
// Four claims, and each is a case:
//   1. the category is ASKED FOR ON STEP 1 and the step will not advance
//      without one — the whole reason for the change;
//   2. the options are the SERVED catalogue, not a hardcoded list — a test that
//      asserted the seven literal names would pass over a hardcoded seven;
//   3. `government` is offered DISABLED, not hidden and not selectable
//      (BR-CUS-094);
//   4. `Applying as` is GONE from the form and from the payload, and nothing
//      derives it from the category (CR-033 §4: two different facts).
describe("CR-033 · the customer category on capture step 1", () => {
  afterEach(cleanup);

  /** ⚠ **DELIBERATELY NOT THE REAL SEVEN.** BR-CUS-094's list is
   *  `Residential · Commercial · Industrial · Agricultural · Institutional ·
   *  Municipal · Builder or developer`, and a fixture that repeated it could
   *  not tell a fetched list from a hardcoded one — which is the single thing
   *  the PO asked for (*"that we have from settings"*). Three invented codes
   *  can only reach the screen through `GET /service-requests/categories`. */
  const SERVED = {
    selectable: [
      { code: "residential", name: "Residential" },
      { code: "agricultural", name: "Agricultural" },
      { code: "builder_or_developer", name: "Builder or developer" },
    ],
    legacy: [
      {
        code: "government",
        name: "Government",
        br_ref: "BR-CUS-094",
        why: "legacy",
      },
    ],
  };

  function mount(search = ""): void {
    const client = createApiClient({
      tenant: "brazosbend",
      /**
       * ⚠ **THE CREATE REPLY IS MOCKED BECAUSE STEP 1 NOW MAKES THE CALL —
       * `DEF-CUS-6006`, 2026-09-20.** Until the draft minimum moved, the forward
       * move off step 1 posted NOTHING (`canCreateDraft` was false with no
       * address), so this mock never needed an answer for it and returned `[]`
       * to everything it did not recognise. With a name now enough to open a
       * draft, `persist` fires on Continue, `setDraft([])` lands an array where
       * a detail belongs, and `draft?.documents.documents` throws — the page
       * blanks and the category options are never found. **The fixture was the
       * gap, not the product**, and a mock that answers every unknown URL with
       * `[]` is a mock that cannot tell a call it models from one it does not.
       */
      fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const writing = (init?.method ?? "GET") !== "GET";
        const body = url.includes("/service-requests/categories")
          ? SERVED
          : url.includes("/lookups/")
            ? { count: 0, next: null, previous: null, results: [] }
            : writing && url.includes("/service-requests")
              ? sent()
              : [];
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[`/brazosbend/requests/new${search}`]}>
          <ServiceRequestCapturePage client={client} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  /** ⚠ **AN OPTION, NOT A RADIO — PO, of the built step 2: *"please note on
   *  step 2 it is drop down for Category and sub category"*.** These cases
   *  were written against `SegmentedField`'s radio group and the CONTROL TYPE
   *  changed under them; the questions they ask did not, so the accessor moved
   *  and the assertions stayed. */
  // ⊕ Lane CF-1 (2026-10-18) — step 1 is the SHARED customer form: the
  // category is its *Category* select (`account_type`), the kind its
  // Person / Company pair, the phone a required field for a person.
  const categoryPicker = (): HTMLSelectElement =>
    document.getElementById("account_type") as HTMLSelectElement;
  const category = async (name: string): Promise<void> => {
    await userEvent.selectOptions(
      categoryPicker(),
      screen.getByRole("option", { name }) as HTMLOptionElement,
    );
  };
  const typePhone = async (): Promise<void> => {
    await userEvent.type(document.getElementById("phone") as HTMLInputElement, "(512) 555-0100");
  };

  /**
   * ⚠ **THESE SIX CASES WERE WRITTEN ABOUT STEP 1 AND THE CATEGORY IS NOW ON
   * STEP 2 — PO ruling 2026-09-15, verbatim: *"this should be on step 2 as per
   * image"*.** They are REWRITTEN rather than deleted, and each keeps the
   * question it was actually asking, because `CR-033` is NARROWED and not
   * reversed: its subject was WHICH control sits in the category's slot and
   * WHERE the list comes from — *"customer categories that we have from
   * settings"* — and both of those still hold. Only the POSITION moved.
   *
   * The harness opens at `?step=1`: the control has now moved BACK, by the
   * PO ruling of 2026-09-29 (*"move this to appliant sicne it is applicant -
   * arrtributes"*), and the gate moved with it for the third time.
   */
  it("draws the SERVED categories — three here, so nothing hardcoded can pass", async () => {
    mount("?step=1");
    expect(await screen.findByRole("option", { name: "Agricultural" })).toBeInTheDocument();
    // Exactly what the server sent, and nothing else — plus the leading
    // placeholder, which is the fourth option and is not a category.
    // ⊕ Lane CF-1 — the shared Who panel's *Category* (`account_type`).
    const picker = categoryPicker();
    expect(picker.tagName).toBe("SELECT");
    expect(picker.querySelectorAll("option")).toHaveLength(4);
    expect(screen.queryByRole("option", { name: "Commercial" })).toBeNull();
  });

  /**
   * ⚠ **AMENDED 2026-09-22, AND IT HAD BEEN RED SINCE `74511fa68` LANDED AT
   * 10:56 THAT MORNING (hard-won law 7 habit 1 — read the failures you did not
   * cause, and DATE them).** PO report item 3: `Government` comes off the NEW
   * REQUEST picker, with its 25-word explanation (rule 33 — rationale is zero
   * words on screen).
   *
   * **WHAT THE OLD CASE GOT RIGHT AND WHAT IS KEPT:** the VALUE is untouched.
   * It is still lawful on every record that holds it and is still refused BY
   * NAME at the write, so a clerk cannot reach it through a stale form or an
   * API call. That is the half `BR-CUS-094` is actually about, and it is the
   * half asserted below. What is NOT asserted any more is a control on this
   * screen, because there is not one.
   */
  it("BR-CUS-094 · `government` is not offered on the new-request picker at all", async () => {
    mount("?step=1");
    await screen.findByRole("option", { name: "Agricultural" });
    // Not an option, and — since 2026-09-22 — not a disabled control either.
    expect(screen.queryByRole("option", { name: "Government" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Government" })).toBeNull();
    // And its explanation went with it.
    expect(
      screen.queryByText(t("customers.serviceRequest.capture.legacyCategory")),
    ).toBeNull();
  });

  /**
   * ⚠ **THE GATE MOVED WITH THE CONTROL, AND THAT IS THE WHOLE CASE.** It used
   * to prove step 1 would not advance without a category. Leaving it there
   * would have been a step refusing to advance over a field nobody can see on
   * it — which is the shape this case exists to catch, one step along.
   *
   * RED at `2c8161fc`: step 1's `validate` still carried
   * `&& form.account_type_code !== ""`, so this case could not reach step 2 at
   * all and failed on not finding the category it had just been asked for.
   */
  it("STEP 1 will not advance without a category — the gate moved with the control", async () => {
    mount("?step=1");
    await screen.findByRole("option", { name: "Agricultural" });

    // ⚠ **THE DROPDOWN OPENS UNANSWERED, AND THE GATE DEPENDS ON THAT.** A
    // closed select with no leading empty option would open showing the FIRST
    // category, which reads as an answer nobody gave — and this case would
    // then pass straight through to step 2 and prove nothing.
    expect(categoryPicker()).toHaveValue("");

    await userEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
    expect(screen.getByRole("option", { name: "Agricultural" })).toBeInTheDocument();
    // Still on step 1 — the shared customer form is on screen (its mailing
    // block also says *Service address*, so that word cannot tell the steps apart).
    expect(document.querySelector("[data-request-customer-form]")).not.toBeNull();

    // ⚠ **THE STEP NOW GATES ON THE NAME, THE CATEGORY AND — lane CF-1,
    // Move-in's rules — A PERSON'S PHONE.** Answering only the category still
    // would not advance, which is the other half of the same rule.
    await category("Agricultural");
    await userEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
    // Still on step 1 — the shared customer form is on screen (its mailing
    // block also says *Service address*, so that word cannot tell the steps apart).
    expect(document.querySelector("[data-request-customer-form]")).not.toBeNull();
    await userEvent.type(
      screen.getByLabelText(t("customers.serviceRequest.capture.fullName"), { exact: false }),
      "Osei, Grace",
    );
    await typePhone();
    await userEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
    // Step 2 · the property, and the category is not repeated there.
    await waitFor(() => expect(document.querySelector("[data-request-customer-form]")).toBeNull());
    expect(screen.getAllByText(t("customers.serviceRequest.capture.serviceAddress")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("option", { name: "Agricultural" })).toBeNull();
  });

  /**
   * ⚠ **THIS CASE READ *"STEP 1 no longer refuses over a category it does not
   * draw"* AND THE RULING OF 2026-09-29 REVERSED IT.** It was right on
   * 2026-09-15 — a step must not refuse over a field nobody can see on it —
   * and the fix now runs the other way: the field is BACK, so the refusal is
   * back with it. The question is unchanged; only which direction satisfies it
   * has moved.
   */
  it("a name ALONE is not enough now — the category is on this step again", async () => {
    mount("?step=1");
    await screen.findByRole("option", { name: "Agricultural" });
    await userEvent.type(
      screen.getByLabelText(t("customers.serviceRequest.capture.fullName"), { exact: false }),
      "Osei, Grace",
    );
    await typePhone();
    await userEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
    // Still on step 1 — the shared customer form is on screen (its mailing
    // block also says *Service address*, so that word cannot tell the steps apart).
    expect(document.querySelector("[data-request-customer-form]")).not.toBeNull();
    await category("Agricultural");
    await userEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await waitFor(() => expect(document.querySelector("[data-request-customer-form]")).toBeNull());
    expect(screen.getAllByText(t("customers.serviceRequest.capture.serviceAddress")).length).toBeGreaterThan(0);
  });

  it("step 1 asks the question, the kind, and the contact fields", async () => {
    mount("?step=1");
    await screen.findByLabelText(t("customers.serviceRequest.capture.fullName"), {
      exact: false,
    });
    // ⊕ Lane CF-1 — the shared Who panel, titled as image 03 draws it.
    expect(
      screen.getByRole("heading", { name: t("customers.form.whoApplying") }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(t("customers.serviceRequest.capture.fullName"), { exact: false }),
    ).toBeInTheDocument();
    expect(document.getElementById("email")).not.toBeNull();
    expect(document.getElementById("phone")).not.toBeNull();
    // NO *Search customer ID* on the request (PO 2026-10-18).
    expect(document.querySelector("[data-search-customer-id]")).toBeNull();
    // The channel select stays — BR-CUS-091 hangs off it.
    expect(
      screen.getByLabelText(t("customers.serviceRequest.capture.channel")),
    ).toBeInTheDocument();
  });

  /**
   * ⚠ **THIS CASE IS REVERSED BY A RULING AND THE REVERSAL IS THE POINT.** It
   * asserted that the date of birth and the government id were STATED and not
   * collected, which was true while `_clean_capture` refused both by name. PO
   * ruling 2026-09-15: *"ensure user is able to inputs both these on step 1 -
   * Date of birth and driver's licence on step 1"*. `BR-CUS-092`'s amendment
   * of the same day records that this FINISHES clause (a) rather than
   * reversing it — the rule has required both since 2026-08-24.
   *
   * So the case asserts the opposite fact and keeps the one thing that did NOT
   * change: the old absence sentences must be gone, because printing *"we do
   * not hold a driving licence"* over the box a clerk is typing one into is
   * worse than either state on its own.
   */
  it("BR-CUS-092 · the date of birth and the licence are INPUTS on step 1 now", async () => {
    mount("?step=1");
    await screen.findByLabelText(t("customers.serviceRequest.capture.fullName"), {
      exact: false,
    });
    expect(
      screen.getByLabelText(t("customers.serviceRequest.applicant.dateOfBirth"), {
        exact: false,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(t("customers.serviceRequest.applicant.driversLicence"), {
        exact: false,
      }),
    ).toBeInTheDocument();
    // The sentence that said we could not hold a date of birth is off the
    // screen. ⚠ **AND THE LICENCE'S IS ASSERTED THE OTHER WAY, BECAUSE ITS KEY
    // IS RETIRED** — `applicant.driversLicenceAbsent` left all eleven
    // catalogues in this commit, so `t()` would answer with the KEY ITSELF and
    // `queryByText` on that can never find anything. **A check that cannot
    // fail is worse than no check** (law 7), so what is asserted is the
    // durable fact: the key is gone, and the input is there.
    expect(
      screen.queryByText(t("customers.serviceRequest.applicant.dateOfBirthAbsent")),
    ).toBeNull();
    expect(
      i18n.exists("customers.serviceRequest.applicant.driversLicenceAbsent"),
    ).toBe(false);
  });

  /**
   * ⚠ **AND THE MIRROR OF IT: `Applying as` IS BACK, AND THE CASE THAT PROVED
   * IT GONE IS NOW THE CASE THAT PROVES IT PRESENT (`DEF-CUS-5415`).**
   *
   * `CR-033` removed it on 2026-08-25 and `BR-CUS-1022` was ruled six days
   * later: *"THE KIND MUST BE STATED WHERE IDENTITY IS PRESENTED, AND IS
   * REFUSED BY NAME WHERE IT IS NOT — … a guess of `person` would judge a
   * business by a date of birth it has not got and file its Tax ID nowhere."*
   * Nothing reconciled the two for three weeks and nothing could: no check in
   * this repo reads a rule against a screen.
   *
   * ⚠ **`CR-033` §4's OWN REASONING IS UNTOUCHED AND IS ASSERTED HERE**: the
   * kind is not derived from the category and the category is not derived from
   * the kind.
   */
  it("BR-CUS-1022 · the kind is asked, is sent, and is not derived from the category", async () => {
    mount("?step=1");
    await screen.findByLabelText(t("customers.serviceRequest.capture.fullName"), {
      exact: false,
    });
    // ⊕ **LANE CF-1 (2026-10-18) — Person / Company ON TOP, AS EVERY CREATE
    // SCREEN DRAWS IT** (customer-forms drawing set, images 01, 03, 06). It
    // was a dropdown since 2026-09-19; the FACT and its rule are unchanged,
    // the CONTROL is the shared form's. Both answers are asserted.
    expect(screen.getByRole("radio", { name: t("customers.customer.kind.person") })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: t("customers.customer.kind.company") })).toBeInTheDocument();

    const payload = capturePayload({
      ...emptyCaptureForm(),
      applicant_name: "Osei, Grace",
      address_as_given: "14 Willow Bend",
      account_type_code: "residential",
    });
    expect(Object.keys(payload)).toContain("applicant_kind");
    expect(payload.applicant_kind).toBe("person");
    // A RESIDENTIAL category on a BUSINESS applicant — CR-033 §4's own worked
    // case, a landlord's company. Neither fact moves the other.
    expect(
      capturePayload({
        ...emptyCaptureForm(),
        applicant_kind: "business",
        account_type_code: "residential",
      }).applicant_kind,
    ).toBe("business");
  });

  /**
   * **`BR-CUS-1022`'s SHARPEST CLAUSE, ON SCREEN:** *"a company is never asked
   * for a driving licence and a person is never asked for a Tax ID, refused BY
   * NAME rather than dropped, because asking for both and leaving one blank
   * turns a rule into a habit and the blank field eventually gets filled with
   * something."*
   */
  it("BR-CUS-1022 · a business is never asked for a licence or a date of birth", async () => {
    mount("?step=1");
    await screen.findByLabelText(t("customers.serviceRequest.capture.fullName"), {
      exact: false,
    });
    await userEvent.click(screen.getByRole("radio", { name: t("customers.customer.kind.company") }));
    // ⊕ **AMENDED 2026-10-18 (lane CF-1) — THE SHARED FORM ASKS A COMPANY NO
    // PERSON'S EVIDENCE AT ALL.** The Identity panel is a person's; a company
    // has its Tax ID in Who (Move-in's company form). The RULE is unchanged:
    // *a company is never ASKED for a driving licence* — the boxes are gone.
    expect(document.getElementById("driving_licence")).toBeNull();
    expect(document.getElementById("dob")).toBeNull();
    expect(document.getElementById("ssn")).toBeNull();
    // …and it IS asked for the one identifier that is its own.
    expect(document.getElementById("tax_id")).not.toBeNull();
  });

  /**
   * **AND THE BLANKING IS IN THE DATA, NOT ONLY IN THE LAYOUT.** `BR-CUS-1022`
   * says the other kind's evidence is *"refused BY NAME rather than dropped"*,
   * so a person's date of birth typed and then switched to a business must not
   * survive in state where `identityPayload` could still build it.
   */
  it("BR-CUS-1022 · switching kind clears what the other kind answered", () => {
    const person = {
      ...emptyCaptureForm(),
      date_of_birth: "1988-04-11",
      ssn: "123456789",
      drivers_licence: "TX4417882",
    };
    const asBusiness = { ...person, ...clearOtherKind(person, "business") };
    expect(asBusiness.date_of_birth).toBe("");
    expect(asBusiness.ssn).toBe("");
    expect(asBusiness.drivers_licence).toBe("");
    const backToPerson = {
      ...asBusiness,
      tax_id: "99-0001234",
      ...clearOtherKind(asBusiness, "person"),
    };
    expect(backToPerson.tax_id).toBe("");
  });
});

describe("DEF-632 · the Social Security number is captured, and only four digits come back", () => {
  afterEach(cleanup);

  /** The same fetch stub CR-033 uses — step 1 will not render without a served
   *  category catalogue, so the DOM case needs one. */
  function mountStepOne(search = ""): void {
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async (input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.includes("/service-requests/categories")
          ? { selectable: [{ code: "residential", name: "Residential" }], legacy: [] }
          : url.includes("/lookups/")
            ? { count: 0, next: null, previous: null, results: [] }
            : [];
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[`/brazosbend/requests/new${search}`]}>
          <ServiceRequestCapturePage client={client} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  /**
   * ⚠ **`DEF-CUS-5083` — THE STEP IS URL STATE, AND THIS WIZARD WAS THE ONE OF
   * FIVE WHERE IT WAS NOT.** `EP-SHL-03-forms-wizards.md` is a rule, not a
   * habit: *"Wizard step | **all wizards** | A9 routing model (`?step=`) | none
   * (URL state)"*. Measured in Chromium before the fix: `/requests/new?step=2`
   * painted **`Step 1 of 6`**, and so did `?step=3` … `?step=6`, because the
   * step lived in component state while `useSearchParams` was read for
   * `?request=` only. **The blueprint draws six addresses for this wizard**
   * (pages 75–79) and a link to any of them landed the clerk on step 1 — with
   * every `toContain` on the href passing, because the href was correct and the
   * screen was not.
   *
   * ⚠ **IT ASSERTS THE CAPTION AND NOT A CLASS NAME**, because the caption is
   * what a clerk reads and the only thing that can tell step 2 from step 1.
   */
  it.each([
    ["?step=1", 1],
    ["?step=2", 2],
    ["?step=3", 3],
    ["?step=4", 4],
  ])("DEF-CUS-5083 — %s opens on that step", async (search, step) => {
    mountStepOne(search);
    expect(await screen.findByText(new RegExp(`Step ${step} of 4`))).toBeInTheDocument();
  });

  it.each([
    ["?step=5", 4],
    ["?step=0", 1],
    ["?step=banana", 1],
  ])("DEF-CUS-5083 — %s clamps rather than errors", async (search, step) => {
    // BR-SHL-011's spirit: an out-of-range `?step=` clamps, it never errors.
    mountStepOne(search);
    expect(await screen.findByText(new RegExp(`Step ${step} of 4`))).toBeInTheDocument();
  });

  /**
   * ⚠ **`DEF-CUS-5082` — A GATED FIELD WITH NO MARK MAKES THE FRAME LIE.**
   * `validate()` refuses `Continue` while the category is unchosen, and the
   * group carried no asterisk, no `required` and no `aria-required` — so the
   * refusal read *"This step isn't finished. Fill in what's marked above, then
   * press Continue again."* over a screen whose only mark was on a field the
   * clerk had already filled. Measured before the fix: `[aria-invalid=true]`
   * count **0**, error-class count **0**.
   *
   * That is the exact case `WizardFrame` warns about in its own comment — *"the
   * generic one is the FALLBACK — true whenever the unmet condition is a marked
   * field, and **a lie whenever it is not**"* — and B14 rule 10.
   *
   * ⚠ **BOTH DIRECTIONS ARE ASSERTED.** The mark must be on the category and
   * must NOT be on `channel`: `emptyCaptureForm` seeds `CAPTURE_CHANNELS[0]`, so
   * that control can never be empty and nothing gates on it. An asterisk on a
   * field that cannot be unanswered teaches a clerk the mark means nothing,
   * which is this defect running the other way — and a one-directional
   * assertion is what `DEF-CUS-4298` recorded: *"the test asserted the sentence
   * was PRESENT, which is not the same question as whether it is TRUE."*
   */
  it("DEF-CUS-5082 — the gated group carries its mark, and channel does not", async () => {
    // ⚠ **THE GATED GROUP IS THE CATEGORY AND IT IS BACK ON STEP 1** (PO
    // ruling 2026-09-29, reversing 2026-09-15). The defect this case was written for is unchanged — a step
    // that refuses over an unmarked field reads as *"Fill in what's marked"*
    // over a screen with nothing marked — so the case follows the control
    // rather than staying where the control used to be.
    mountStepOne("?step=1");
    // ⚠ **THE CONTROL IS A SELECT NOW AND THE DEFECT IS UNCHANGED.** It is the
    // MARK this case is about, not the widget: a step that refuses over an
    // unmarked field reads as *"Fill in what's marked"* over a screen with
    // nothing marked, whether the field is a radio group or a dropdown.
    // ⊕ Lane CF-1 — the shared Who panel's *Category* (`account_type`).
    await screen.findByRole("option", { name: "Residential" });
    const group = document.getElementById("account_type") as HTMLElement;
    expect(group).toHaveAttribute("aria-required", "true");
    // ⚠ `SelectField` binds its label with `htmlFor`, where `SegmentedField`
    // used an `id` and `aria-labelledby`. The MARK is what this asserts, and
    // it has to be looked up the way the new control publishes it.
    const label = document.querySelector('label[for="account_type"]');
    expect(label).not.toBeNull();
    expect(label?.querySelector(".field-required")).not.toBeNull();

    // …and `channel`, on the same step, still carries no mark: it is seeded with
    // `CAPTURE_CHANNELS[0]`, can never be empty, and nothing gates on it.
    cleanup();
    mountStepOne("?step=1");
    const channel = await screen.findByLabelText(
      t("customers.serviceRequest.capture.channel"),
      { exact: false },
    );
    expect(channel).not.toHaveAttribute("aria-required");
    const channelField = channel.closest(".field");
    expect(channelField?.querySelector(".field-required")).toBeNull();
  });

  it("RENDERS the field on step 1 and accepts typing — built is not wired", async () => {
    // ⚠ **HARD-WON LAW 2.** Every other case in this block is a pure function.
    // A `capturePayload` that carries `ssn` correctly proves nothing at all if
    // no control on the screen ever sets it — that is dead UI, it renders
    // nothing, and every one of those assertions still passes. So this one
    // mounts the real page and types into the real input.
    mountStepOne();
    const field = await screen.findByLabelText(
      t("customers.serviceRequest.capture.ssn"),
      { exact: false },
    );
    expect(field).toBeInTheDocument();
    await userEvent.type(field, "123-45-6789");
    expect(field).toHaveValue("123-45-6789");
    // ⛔ **AND THE PROMISE IS NO LONGER PRINTED BESIDE IT — B14 rule 33, PO
    // ruling 2026-09-19.** This asserted the opposite until that date, and the
    // change is about WORDS ON A SCREEN rather than about storage: the sentence
    // is RATIONALE (*why* the product works this way), which rule 33 puts at
    // **zero words on screen**, and p076 carries it in the blueprint's right
    // margin rather than on the form.
    //
    // ⚠ **THE PROMISE ITSELF IS UNTOUCHED AND MUST STAY THAT WAY** (hard-won
    // law 1). `ServiceRequest.ssn` is still an `EncryptedTextField` and
    // `tests/test_br_cus_092_ssn_capture.py` still reads the raw column back
    // through a second cursor; `BR-CUS-092` clause (d) LIFTED its hold on the
    // sentence, which is permission to print it and never an obligation to.
    // The key stays in all eleven catalogues so putting it back is one line.
    expect(
      screen.queryByText(t("customers.serviceRequest.capture.ssnHint")),
    ).toBeNull();
    // Nothing else on the step says it either — *"no help line under any of the
    // seven"* is the rule, and a second field quietly keeping the sentence
    // would satisfy the query above and break the rule.
    expect(document.body.textContent).not.toMatch(/[Ss]tored encrypted/);
  });

  /**
   * ⛔ **THIS CASE ASSERTED AN ABSENCE THAT A RULING REMOVED — PO 2026-09-15.**
   * It read *"states the DRIVING LICENCE absence on the same step"*, and was
   * right: `BR-CUS-092(a)` names two identifiers, the 2026-08-27 ruling
   * reached one, and an unbuilt half must never become a silent one. The
   * amendment of 2026-09-15 landed the other half, so the sentence has nothing
   * left to state.
   *
   * **It is rewritten to the same DISCIPLINE against the new fact:** the
   * licence is an input, it accepts typing, and — the half that still
   * binds — **clause (d) keeps the `"stored encrypted"` promise OFF it** while
   * the column does not exist. A control claiming encryption over a field that
   * goes nowhere is hard-won law 1 with a government identifier attached.
   */
  it("BR-CUS-092 · the licence is an input, and it makes no encryption promise yet", async () => {
    mountStepOne();
    const field = await screen.findByLabelText(
      t("customers.serviceRequest.applicant.driversLicence"),
      { exact: false },
    );
    await userEvent.type(field, "TX4417882");
    expect(field).toHaveValue("TX4417882");
    // The absence sentence is gone — asserted against the CATALOGUE, because
    // its key is retired and `t()` would answer with the key itself.
    expect(
      i18n.exists("customers.serviceRequest.applicant.driversLicenceAbsent"),
    ).toBe(false);
    // ⛔ **THE PROMISE IS OFF THE SCREEN — B14 rule 33, PO ruling 2026-09-19.**
    // See the SSN case above for the whole reasoning; it is the same sentence
    // and the same rule. **The column is still encrypted and still proved.**
    expect(
      screen.queryByText(t("customers.serviceRequest.capture.licenceStoredEncrypted")),
    ).toBeNull();
    // …and the drawn label is the drawing's word, not ours (B14 rule 41).
    expect(i18n.t("customers.serviceRequest.applicant.driversLicence")).toBe(
      "Driver's license",
    );
  });

  /**
   * **THE HOLD-EXPIRY CASES — hard-won law 2, verbatim: *when you write a
   * hold, write the test that fires when the hold expires.***
   *
   * Two write paths are held behind a flag in the page, because sending a name
   * `_clean_capture` does not know fails the WHOLE patch rather than dropping
   * a field. The day a sibling lane lands either column set, its flag flips
   * and these two cases go RED and name the constant to move.
   *
   * ⚠ **THEY ARE NOT ASSERTIONS THAT THE HOLD IS RIGHT.** They are assertions
   * that the SCREEN and the PAYLOAD agree about it — a clerk typing into a
   * field whose value the payload silently drops is exactly the dead UI `G13`
   * exists for, and the mitigation is that everything typed here is read back
   * on step 6.
   */
  /**
   * ⚠ **THE HOLD EXPIRED, AND THIS IS THE CASE THAT FIRED — hard-won law 2
   * working exactly as it says.** It asserted `IDENTITY_CAPTURE_ACCEPTED ===
   * false` and that three names were absent from the payload. Lane G landed
   * `date_of_birth` and `drivers_licence` in `CAPTURE_FIELDS` on the PO's
   * ruling of 2026-09-15, the flag flipped, and the case went RED naming the
   * constant to move — which is the whole reason a hold gets a test in the
   * same commit as the hold.
   *
   * ⚠ **AND IT SPLIT, BECAUSE LANE G OPENED TWO OF THREE.** `tax_id` is still
   * refused: `service_requests` has no such column and `customers.tax_id` one
   * table over is a different row's identifier. So the assertion is now TWO
   * assertions, and the second is a live hold with its own flag.
   */
  it("BR-CUS-092 · the date of birth and the licence now REACH the server", () => {
    const payload = capturePayload({
      ...emptyCaptureForm(),
      applicant_name: "Osei, Grace",
      address_as_given: "14 Willow Bend",
      date_of_birth: "1988-04-11",
      drivers_licence: "TX4417882",
    });
    expect(IDENTITY_CAPTURE_ACCEPTED).toBe(true);
    expect(payload.date_of_birth).toBe("1988-04-11");
    expect(payload.drivers_licence).toBe("TX4417882");
  });

  // ⊕ **THE HOLD EXPIRED — LANE CF-1, 2026-10-18, `DEF-CUS-10223`.** This case
  // read *"the Tax ID is still HELD"* and asserted `TAX_ID_CAPTURE_ACCEPTED`
  // was `false`: it went RED the day `service_requests.tax_id` landed
  // (`customers/0087`), exactly as a hold-expiry test should, and the flag is
  // deleted. A business's Tax ID now REACHES the server.
  it("BR-CUS-1022 · a business's Tax ID now REACHES the server (DEF-CUS-10223)", () => {
    const payload = capturePayload({
      ...emptyCaptureForm(),
      applicant_kind: "business",
      applicant_name: "Balcones Holdings LLC",
      address_as_given: "14 Willow Bend",
      tax_id: "99-0001234",
    });
    expect(payload.tax_id).toBe("99-0001234");
    // …and a BUSINESS still sends none of a person's evidence.
    for (const personsOwn of ["date_of_birth", "drivers_licence"]) {
      expect(Object.keys(payload)).not.toContain(personsOwn);
    }
    expect(payload.ssn).toBe("");
    // A PERSON never sends a Tax ID (refused by name on the server).
    expect(
      Object.keys(identityPayload({ ...emptyCaptureForm(), applicant_kind: "person", tax_id: "x" })),
    ).not.toContain("tax_id");
    // A number on file is shown as a mask and never re-sent unless retyped.
    expect(
      identityPayload({ ...emptyCaptureForm(), applicant_kind: "business", tax_id_on_file: "1234" }),
    ).toEqual({});
  });

  // ⚠ `DEF-CUS-10041` (PO 2026-10-11): this case asserted the tender was
  // HELD and named itself as the case that goes red the day the wizard posts
  // to `fee-collection`. That day came; the tender still never rides the
  // capture PATCH, and its shape is now `feeCollectionBody`'s.
  it("the counter tender never rides the capture PATCH, and goes to fee-collection in lane H's shape", () => {
    const payload = capturePayload({
      ...emptyCaptureForm(),
      fee_timing: "collect_now",
      fee_method: "card",
      card_last4: "4417",
      card_brand: "visa",
      card_auth_code: "081422",
      fee_receipt_no: "RCP-1",
    });
    for (const held of ["card", "check", "cheque", "card_last4", "cheque_no", "fee_receipt_no"]) {
      expect(Object.keys(payload)).not.toContain(held);
    }
    expect(payload.fee_timing).toBe("collect_now");
    const body = feeCollectionBody(
      {
        ...emptyCaptureForm(),
        fee_method: "card",
        card_last4: "4417",
        card_brand: "visa",
        card_auth_code: "A19422",
        fee_receipt_no: "RCP-1",
      },
      "45.0000",
      "2026-10-11",
    );
    expect(body).toMatchObject({
      amount: "45.0000",
      method: "card",
      receipt_no: "RCP-1",
      card: { last4: "4417", brand: "visa", auth_code: "A19422" },
    });
    const card = (body as { card: Record<string, unknown> }).card;
    for (const banned of ["number", "pan", "expiry", "cvv", "cvc"]) {
      expect(Object.keys(card)).not.toContain(banned);
    }
    expect(
      feeCollectionBody(
        {
          ...emptyCaptureForm(),
          fee_method: "cheque",
          cheque_no: "10241",
          cheque_bank: "First National",
          cheque_date: "2026-05-12",
          fee_receipt_no: "RCP-2",
        },
        "45.0000",
        "2026-10-11",
      ),
    ).toMatchObject({ method: "check", check: { number: "10241", bank: "First National", date: "2026-05-12" } });
  });

  it("sends `ssn` — the ONE identifier name the server now accepts", () => {
    // BR-CUS-092(a)/(b), PO 2026-08-27. Before this ruling `_clean_capture`
    // refused fourteen identifier names outright, so a control here would have
    // collected a government identifier into a request that threw it away.
    const payload = capturePayload({
      ...emptyCaptureForm(),
      applicant_name: "Okonkwo, David",
      address_as_given: "14 Willow Bend",
      ssn: " 123-45-6789 ",
    });
    expect(payload.ssn).toBe("123-45-6789");
  });

  it("sends an EMPTY string when nothing was typed, never a fabricated value", () => {
    // The server passes `""` straight through rather than encrypting it, so an
    // absent identifier stays absent and every `if not request.ssn` in the
    // product keeps meaning what it meant.
    const payload = capturePayload({
      ...emptyCaptureForm(),
      applicant_name: "Okonkwo, David",
      address_as_given: "14 Willow Bend",
    });
    expect(payload.ssn).toBe("");
  });

  it("carries NO other identifier field — the widening is exactly one name", () => {
    // `gov_id`, `drivers_licence_last4` and nine others still answer BIZ_STATE
    // by name — `date_of_birth` and `drivers_licence` left that list on
    // 2026-09-15 and are now ordinary `CAPTURE_FIELDS` members.
    // A payload key that the server refuses is a request that cannot be saved.
    const payload = capturePayload({
      ...emptyCaptureForm(),
      applicant_name: "Okonkwo, David",
      address_as_given: "14 Willow Bend",
      ssn: "123-45-6789",
    });
    for (const refused of [
      "social_security_number",
      "gov_id",
      "gov_id_number",
      "id_number",
      "national_id",
      "ein",
      "tin",
      // ⊕ `gov_id_last4` left 2026-10-18 (lane CF-1) — BR-CUS-045 keeps four.
      "ssn_last4",
      // ⚠ **`drivers_licence_last4` REPLACED `date_of_birth`/`dob` HERE ON
      // 2026-09-15** — lane G opened those two on the PO's ruling and closed
      // the same door behind them: there is no `_last4` COLUMN for a licence
      // any more than for an SSN, so a caller-supplied last four would put
      // four digits of a government identifier in the clear beside the
      // ciphertext and make `BR-CUS-092(c)` false while every test passed.
      "drivers_licence_last4",
      "acting_for",
    ]) {
      expect(Object.keys(payload)).not.toContain(refused);
    }
  });

  it("masks to B19 §7's own glyph string — `••• ••• • 6789`", () => {
    // The capture wizard is the ONE place the full value legitimately sits in
    // front-end state, because the clerk typed it a moment ago. Step 6 reads it
    // back masked so a government identifier is not on a screen a customer may
    // be standing in front of.
    expect(maskSsn("123-45-6789")).toBe("\u2022\u2022\u2022 \u2022\u2022\u2022 \u2022 6789");
    expect(maskSsn("123456789")).toBe("\u2022\u2022\u2022 \u2022\u2022\u2022 \u2022 6789");
    expect(maskSsn("")).toBe("");
  });

  it("never leaves more than the last four in the masked string", () => {
    // The assertion that matters: no spelling of the number survives masking.
    const masked = maskSsn("123-45-6789");
    for (const spelling of ["123", "12345", "456789", "123456789", "123-45-6789"]) {
      expect(masked).not.toContain(spelling);
    }
    expect(masked).toContain("6789");
  });

  it("hides EVERY character of a value too short to have a last four", () => {
    // There is no fifth character to hide and padding would invent one.
    expect(maskSsn("12")).toBe("\u2022\u2022");
    expect(maskSsn("6789")).toBe("\u2022\u2022\u2022\u2022");
  });

  it("prints the promise B19 §2 draws, now that it is true", () => {
    // ⚠ This assertion is the screen's half of hard-won law 1. The sentence was
    // deliberately KEPT OFF this screen while the column did not exist
    // (BR-CUS-092(d)); it is printed now because
    // `06-backend/tests/test_br_cus_092_ssn_capture.py` reads the column back
    // raw and proves it. If that proof goes, this text goes with it.
    expect(i18n.t("customers.serviceRequest.capture.ssnHint")).toBe(
      "Stored encrypted and shown to staff as the last four digits only.",
    );
    expect(i18n.t("customers.serviceRequest.capture.ssn")).toBe("Social Security Number");
  });
});

/**
 * ══════════════════════════════════════════════════════════════════════════
 * THE HEAD IS THE DRAWING'S — `CR-094-BRC01` lane F
 * ══════════════════════════════════════════════════════════════════════════
 *
 * Read off the accounts blueprint's PAGE IMAGES (p75–80, all six frames drawn
 * at 1280), not off the markdown extraction — the extractor keeps the labels
 * and loses the layout, and the PO ruled on 2026-09-13 that a screen is built
 * from the image.
 *
 * Every frame draws three lines and two of them change with the step:
 *
 *     NEW REQUEST                    ← the kicker, identical on all six
 *     Who is this request for?       ← the title, one per step
 *     Step 1 of 6 · Customer         ← the sub-line, one per step
 *
 * ⚠ **EACH CASE BELOW WAS PROVED RED AT THE LANE'S STARTING TIP** (`e3bcdd233`,
 * in a `git worktree`, under this same vitest) before the code moved. What each
 * one found there is quoted on the case.
 */
describe("the capture head matches the blueprint drawing", () => {
  // Each case renders the page; without this the mounts accumulate and a
  // "there is exactly one of these" assertion counts every previous render too.
  afterEach(cleanup);

  function mountAt(search: string): void {
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async (input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.includes("/service-requests/categories")
          ? { selectable: [], legacy: [] }
          : url.includes("/lookups/")
            ? { count: 0, next: null, previous: null, results: [] }
            : [];
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[`/brazosbend/requests/new${search}`]}>
          <ServiceRequestCapturePage client={client} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  // RED at the tip: the kicker read `NEW SERVICE REQUEST`.
  it("the kicker is the drawn NEW REQUEST, not NEW SERVICE REQUEST", () => {
    mountAt("?step=1");
    expect(i18n.t("customers.serviceRequest.capture.kicker")).toBe("NEW REQUEST");
    expect(screen.getByText("NEW REQUEST")).toBeInTheDocument();
    expect(screen.queryByText("NEW SERVICE REQUEST")).toBeNull();
  });

  /**
   * RED at the tip: every step drew the same `<h1>` — *Capture a service
   * request.* — and the step's own question was an `h3` in the body.
   *
   * ⚠ **THE `<h1>` IS ASSERTED BY ROLE, NOT BY TEXT SEARCH**, because on the
   * tip the words *Who is this request for?* WERE on the screen — in the body,
   * four inches below the title. A `getByText` would have passed over the
   * defect. What is drawn is the question **as the page title**.
   */
  it.each([
    [1, "Who is this request for?"],
    [2, "Where is the service going?"],
    [3, "What are they asking for?"],
    [4, "Check and submit"],
  ])("step %i draws its own question as the page title", (step, drawn) => {
    mountAt(`?step=${step}`);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(drawn);
  });

  /**
   * TWO assertions, because the fault has two directions and only the first
   * was red at the tip. Saying so is the point — a case that can only fail one
   * way, described as if it guards both, is hard-won law 7's *"ask what would
   * make this check pass wrongly"*.
   *
   *   · **The drawn line was ABSENT.** At the tip the head carried no step
   *     line at all, so `Step 1 of 6 · Customer` matched nothing. That half is
   *     RED at `e3bcdd233`, measured.
   *   · **And it must not be said TWICE.** The draft footer opened
   *     `Step 1 of 6 · not saved yet …`, so adding the drawn line put the
   *     prefix on one screen twice. The footer keeps its BR-CUS-093 draft
   *     statement and loses only that prefix.
   *     ⚠ This half CANNOT be proved red by the tip — at the tip there is one
   *     of them and the count is correct. It was proved red by putting the
   *     prefix back into `en.json` and re-running: *expected 2 to be 1*. That
   *     is the only way this half ever fails, and it is the way it will fail
   *     if somebody restores the prefix.
   */
  it.each([
    [1, "Applicant"],
    [2, "Property"],
    [3, "Service"],
    [4, "Review"],
  ])("step %i states where it is, in the drawn words, exactly once", (step, name) => {
    mountAt(`?step=${step}`);
    expect(
      screen.getAllByText(new RegExp(`Step ${step} of 4 \u00b7 ${name}`)),
    ).toHaveLength(1);
    // …and the bare prefix is not repeated anywhere else on the screen.
    expect(screen.getAllByText(new RegExp(`Step ${step} of 4`))).toHaveLength(1);
  });

  // RED at the tip: `Step N of N` and the step's name were not in the head, so
  // the head could not name the step a clerk was standing on.
  it("the sub-line names the step, in the drawn short form", () => {
    mountAt("?step=2");
    expect(screen.getByText(/Step 2 of 4 · Property/)).toBeInTheDocument();
  });

  /**
   * RED at the tip: the question was printed twice — once by the title this
   * lane added and once by the body `h3` that was already there. The hint
   * paragraph under it was two sentences of RATIONALE (B14 rule 33 puts that at
   * zero words on screen) and the blueprint draws none.
   */
  it("step 1's body starts at the fields — no second question, no rationale", () => {
    mountAt("?step=1");
    expect(screen.getAllByText("Who is this request for?")).toHaveLength(1);
    expect(
      screen.queryByText(/The category is what decides which plans are eligible/),
    ).toBeNull();
  });

  /**
   * The same fault, one step along, and it was found the same way — by looking
   * at the built page, not at the suite. Step 6 kept an `h3` reading *Check and
   * submit* under a 32px title reading *Check and submit*. RED the moment the
   * per-step title landed; invisible to every check in this repo before that,
   * because one of the two was in the body and no gate reads rendered output.
   */
  it("step 6's body starts at the review — the title is not repeated", () => {
    mountAt("?step=4");
    expect(screen.getAllByText("Check and submit")).toHaveLength(1);
  });
});

/**
 * The blueprint's step 6 (p79–80) reads its review in the order the clerk
 * filled it in — **The applicant** ✎ Step 1 · **What they are asking for**
 * ✎ Step 2 · **Addresses and property** ✎ Step 3.
 *
 * ⚠ **RED AT THE TIP, and it is an ORDER defect, which is the kind a presence
 * assertion cannot see.** All three panels were on the screen; they read
 * 1 → 3 → 2, so a clerk checking their work jumped from the address back to a
 * step they had answered earlier. The panels also carried our words rather than
 * the drawing's: `Applicant`, `Service address`, `Connection`.
 */
describe("the step 6 review reads in the drawn order", () => {
  afterEach(cleanup);

  const DRAWN = [
    "The applicant",
    "What they are asking for",
    "Addresses and property",
  ] as const;

  it("names the three sections the way the drawing does", () => {
    expect(i18n.t("customers.serviceRequest.capture.reviewApplicant")).toBe(DRAWN[0]);
    expect(i18n.t("customers.serviceRequest.capture.reviewAskingFor")).toBe(DRAWN[1]);
    expect(i18n.t("customers.serviceRequest.capture.reviewAddresses")).toBe(DRAWN[2]);
  });

  it("and puts them on the page in that sequence", async () => {
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async () =>
        new Response(JSON.stringify({ selectable: [], legacy: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={["/brazosbend/requests/new?step=4"]}>
          <ServiceRequestCapturePage client={client} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const heads = (await screen.findAllByRole("heading", { level: 3 }))
      .map((h) => h.textContent ?? "")
      .filter((text) => (DRAWN as readonly string[]).includes(text));
    expect(heads).toEqual([...DRAWN]);
  });
});


/**
 * ══════════════════════════════════════════════════════════════════════════
 * **`CR-094-BRC01` LANE D — the six steps rebuilt from the page images**
 * (accounts blueprint `p076`–`p081`, read as images at scale 2, B14 rule 42).
 * ══════════════════════════════════════════════════════════════════════════
 */
describe("CR-094-BRC01 lane D · the capture wizard against its drawing", () => {
  afterEach(cleanup);

  /** Eleven services, as the demo tenant runs them — which is why the enabled
   *  filter looks like it does nothing there and why the denominator case
   *  below serves a DIFFERENT set. */
  const ELEVEN = [
    "electric",
    "water",
    "gas",
    "sewer",
    "trash",
    "storm_water",
    "solar",
    "broadband",
    "thermal",
    "battery",
    "fire",
  ].map((code) => ({
    service: code,
    name: `Served name for ${code}`,
    enabled: true,
  }));

  function mountWith(
    search: string,
    over: {
      services?: { service: string; name: string; enabled: boolean }[];
      premises?: unknown[];
      detail?: ServiceRequestDetail;
      /** The tenant's charge catalogue, for step 5's fee picker. */
      charges?: unknown[];
      /** Every POST this mount saw, in order — so a case can assert what
       *  reached the server rather than only what the screen drew. A control
       *  that renders and sends nothing is hard-won law 2's dead UI. */
      posted?: { url: string; body: unknown }[];
    } = {},
  ): void {
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if ((init?.method ?? "GET").toUpperCase() === "POST" && over.posted !== undefined) {
          over.posted.push({
            url,
            body: typeof init?.body === "string" ? JSON.parse(init.body) : init?.body,
          });
        }
        let body: unknown = [];
        if (url.includes("/charges")) {
          const rows = over.charges ?? [];
          body = { count: rows.length, next: null, previous: null, results: rows };
        } else if (url.includes("/service-requests/categories")) {
          body = { selectable: [{ code: "residential", name: "Residential" }], legacy: [] };
        } else if (over.detail !== undefined && /\/documents$/.test(url.split("?")[0])) {
          // ⊕ Lane CF-1 — the shared documents table reads the request's
          // documents tab on its own route.
          body = over.detail.documents;
        } else if (over.detail !== undefined && /\/fees(\/|$)/.test(url.split("?")[0])) {
          // A fee write answers with the whole fees TAB, as the real route
          // does — an empty list here made the table read `lines` of nothing.
          body = over.detail.fees;
        } else if (
          // The saved draft — `?request=` puts the wizard on a request the
          // server already holds, which is the only way step 4 has rows.
          over.detail !== undefined &&
          /\/service-requests\/[^/?]+$/.test(url.split("?")[0])
        ) {
          body = over.detail;
        } else if (url.includes("/settings/services")) {
          body = over.services ?? ELEVEN;
        } else if (url.includes("/premises/picker")) {
          body = {
            count: (over.premises ?? []).length,
            next: null,
            previous: null,
            results: over.premises ?? [],
          };
        } else if (url.includes("/lookups/")) {
          body = { count: 0, next: null, previous: null, results: [] };
        }
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[`/brazosbend/requests/new${search}`]}>
          <ServiceRequestCapturePage client={client} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  // ── STEP 2 · the services control ──────────────────────────────────────

  /**
   * RED at `2c8161fc`: the step rendered eleven `ServiceCard`s in a
   * `grid-cols-3`, which is the shape the drawing rejects by name — *"A
   * multiselect, not eleven rows."*
   */
  /**
   * **THE CHIPS ARE GONE AND THE SERVICES ARE A TABLE ARRAY — REQ-03 task 8,
   * PO 2026-09-29:** *"can we merge this two and create table array for
   * this"*. `03-service-1440.png`, read as an image (B14 rule 42).
   *
   * ⚠ **PROVED RED FIRST** against the chips still in place: there was no
   * `data-editable-table='request-services'`, no `+ Service`, and `STATUS` was
   * not a column.
   */
  it("step 3 offers ONE table array, not a chip multiselect", async () => {
    mountWith("?step=3", { services: ELEVEN });
    await screen.findByText(
      t("customers.serviceRequest.capture.servicesSelected", { selected: 0, total: 11 }),
    );
    // The chips and the separate *Add a service…* box are gone.
    expect(document.querySelectorAll('[data-chip-add="capture-services"]')).toHaveLength(0);
    // ⚠ **THE HEADERS ARRIVE WITH THE FIRST ROW**, because the kit draws its
    // empty state instead of a header over nothing.
    fireEvent.click(document.querySelector("[data-add-service]") as HTMLElement);
    const table = document.querySelector(
      "[data-editable-table='request-services']",
    ) as HTMLElement;
    expect(table).not.toBeNull();
    expect(
      Array.from(table.querySelectorAll("thead th"))
        .map((th) => (th.textContent ?? "").trim())
        .filter(Boolean),
    ).toEqual([
      t("customers.serviceRequest.services.col.service"),
      t("customers.serviceRequest.services.col.requestedStart"),
      t("customers.serviceRequest.services.col.status"),
    ]);
    // The job's date is OUTSIDE the table, which is `DEF-CUS-7840`'s fix.
    expect(table.querySelector("#requested_start")).toBeNull();
    expect(document.getElementById("requested_start")).not.toBeNull();
  });

  /**
   * ⚠ **THE CASE THE RULING ASKS FOR BY NAME: the denominator MOVES when the
   * enabled set moves.** *"a tenant running four services reads `2 of 4
   * selected`, and hard-coding eleven would put a platform fact on a tenant's
   * screen and would break the day a twelfth service is seeded."*
   */
  it("the count's denominator is the tenant's enabled set, never eleven", async () => {
    const four = ELEVEN.slice(0, 5).map((row, i) => ({ ...row, enabled: i < 4 }));
    mountWith("?step=3", { services: four });
    const line = await screen.findByText(
      t("customers.serviceRequest.capture.servicesSelected", { selected: 0, total: 4 }),
    );
    expect(line).toHaveAttribute("data-services-count", "4");
    expect(screen.queryByText(four[4].name)).toBeNull();

    cleanup();
    mountWith("?step=3", { services: ELEVEN });
    expect(
      await screen.findByText(
        t("customers.serviceRequest.capture.servicesSelected", { selected: 0, total: 11 }),
      ),
    ).toHaveAttribute("data-services-count", "11");
  });

  /**
   * **THE NAME COMES FROM THE CATALOGUE AND NEVER FROM AN ENUM**
   * (`DEF-BIL-5336` was exactly this fault). The fixture's names are
   * deliberately not the product's.
   */
  it("service names are the served catalogue's, not a front-end enum", async () => {
    mountWith("?step=3", { services: ELEVEN });
    await screen.findByText(
      t("customers.serviceRequest.capture.servicesSelected", { selected: 0, total: 11 }),
    );
    fireEvent.click(document.querySelector("[data-add-service]") as HTMLElement);
    expect(screen.getByRole("option", { name: "Served name for fire" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Fire" })).toBeNull();
  });

  /**
   * **ADDING A ROW IS ADDING A SERVICE, AND THE ROW STATES ITS STATUS.** The
   * drawn `STATUS` reads *New* where the address matched no premises — the
   * half of that fact this product can honestly answer (`serviceOnSite`).
   */
  it("+ Service makes a row, its chooser fills it, and the row states its status", async () => {
    mountWith("?step=3", { services: ELEVEN });
    await screen.findByText(
      t("customers.serviceRequest.capture.servicesSelected", { selected: 0, total: 11 }),
    );
    fireEvent.click(document.querySelector("[data-add-service]") as HTMLElement);
    fireEvent.change(
      document.querySelector(
        "[data-editable-table='request-services'] tbody select",
      ) as HTMLSelectElement,
      { target: { value: "electric" } },
    );
    await screen.findByText(
      t("customers.serviceRequest.capture.servicesSelected", { selected: 1, total: 11 }),
    );
    const status = document.querySelector("[data-service-status]") as HTMLElement;
    expect(status).toHaveAttribute("data-service-status", "new");
    expect(status.textContent).toBe(t("customers.serviceRequest.services.status.new"));
  });

  /**
   * **THE HOLD HAS EXPIRED, AND THIS CASE IS WHY THAT WAS NOTICED** (hard-won
   * law 2's mirror, `DEF-CUS-5416`). It pinned the flag to `false` while lane
   * F's route was already live, so flipping it turned this red and named the
   * constant — which is the whole reason a hold is written with a test beside
   * it. The flag now reads `true` and the dates ride the one call that
   * replaces the set.
   *
   * ⚠ **THE SHAPE ASSERTION BELOW OUTLIVES THE HOLD AND IS THE POINT NOW**:
   * the route and this screen may not disagree about the key name. The ruling
   * says `code`, not `service`.
   */
  it("the per-service write path is LIVE, and its payload matches BR-CUS-1070", () => {
    expect(SERVICE_STARTS_WRITE_PATH_EXISTS).toBe(true);
    expect(
      serviceStartsPayload({
        ...emptyCaptureForm(),
        services: ["electric", "sewer"],
        service_starts: { electric: "2026-12-05" },
      }),
    ).toEqual([
      { code: "electric", requested_start: "2026-12-05" },
      // `BR-CUS-1070`: an unset per-service date stays NULL and means *not
      // given* — it does NOT fall back to the job's connection date.
      { code: "sewer", requested_start: null },
    ]);
  });

  // ── STEP 3 · the premises register, searched ───────────────────────────

  /** Lane E's published picker row, shape for shape — the units ride ON the
   *  premises, so picking a building and then a unit is ONE round trip. */
  const BALCONES = {
    id: "prm-1",
    premise_no: "P-00074",
    address_line: "212 Balcones Drive",
    city: "Austin",
    state: "TX",
    postal_code: "78704",
    units: [
      { id: "unt-1", unit_no: "U-00101-A", label: "Unit 3", is_common_area: false },
    ],
  };

  /**
   * RED at `2c8161fc`: step 3 was five typed boxes and asked nothing of the
   * register. PO ruling 2026-09-15: *"if we have unit or street address then
   * we should take it from premises/Unit - it means its a search"*.
   */
  it("step 3 searches the register and shows the premises' own facts", async () => {
    mountWith("?step=2", { premises: [BALCONES] });
    const box = await screen.findByLabelText(
      t("customers.serviceRequest.capture.streetOrPremise"),
      { exact: false },
    );
    await userEvent.type(box, "212 Bal");
    const option = await screen.findByRole("button", { name: /212 Balcones Drive/ });
    await userEvent.click(option);

    // City, state and ZIP are the PREMISES' — read by walking, never typed,
    // and never a column on the request (hard rule 8).
    // ⚠ **THEY ARE READ-ONLY BOXES SINCE 2026-09-29, NOT FREE TEXT.** The
    // approved drawing draws three greyed inputs, so the value is now an
    // input's `value` and a `getByText` would find nothing. The question is
    // unchanged: is what is shown the REGISTER's answer, and can a clerk type
    // over it?
    await waitFor(() =>
      expect(document.getElementById("address_city_as_given")).toHaveValue("Austin"),
    );
    expect(document.getElementById("address_state_as_given")).toHaveValue("TX");
    expect(document.getElementById("address_postal_code_as_given")).toHaveValue("78704");
    expect(document.getElementById("address_city_as_given")).toHaveAttribute("readonly");
  });

  /* ⛔ **`+ Premises` IS REMOVED AND THE CASE THAT ASSERTED IT IS GONE WITH
     IT — `DEF-CUS-7850`, PO 2026-09-29.** The question it asked is now asked
     the other way round, in both states, in
     `ServiceRequestCaptureFourStep.dom.test.tsx`: the button must be ABSENT
     whether or not a premises matched, and what the applicant typed must
     still be in the box (`BR-CUS-070`). Deleting an assertion without
     re-asking it somewhere is how a removed control comes back. */

  /** ⛔ The drawing takes the plot off this step and keeps the column. */
  it("step 3 no longer asks for a plot or parcel", async () => {
    mountWith("?step=2", { premises: [BALCONES] });
    await screen.findByLabelText(t("customers.serviceRequest.capture.streetOrPremise"), {
      exact: false,
    });
    expect(
      screen.queryByLabelText(t("customers.serviceRequest.capture.plot"), { exact: false }),
    ).toBeNull();
    // The COLUMN stays in the payload — a caller that knows it can still send
    // one. Removing a control is not dropping a column.
    expect(Object.keys(capturePayload(emptyCaptureForm()))).toContain("plot_or_parcel");
  });

  /**
   * ⚠ **THE PICK IS A FIELD ON THE PAYLOAD, NOT A THING THE SCREEN REMEMBERS**
   * — lane E's contract, `CR-094-BRC01`. A pick held only in component state
   * is dead UI with extra steps: the resolver would go on guessing from prose
   * and nothing about the clerk's choice would survive a refresh.
   *
   * ⚠ **AND `null` IS NOT `undefined` HERE.** Lane E makes them two different
   * acts: *neither sent* leaves a pick alone, so a PATCH about the fee does not
   * clear it; *both null* UNDOES the pick. One `?? null` is the whole
   * difference, and this case is what holds it.
   */
  it("the picked premises and unit reach the server, and clearing them undoes the pick", () => {
    const picked = capturePayload({
      ...emptyCaptureForm(),
      address_as_given: "212 Balcones Drive",
      picked_premises_id: "prm-1",
      picked_unit_id: "unt-1",
    });
    expect(picked.picked_premises_id).toBe("prm-1");
    expect(picked.picked_unit_id).toBe("unt-1");
    // …and the ids are NOT what a screen would print (B14 rule 31) — the
    // match table's own case below asserts the other half.
    const cleared = capturePayload({
      ...emptyCaptureForm(),
      address_as_given: "Lot 14, Willow Bend",
    });
    expect(cleared.picked_premises_id).toBeNull();
    expect(cleared.picked_unit_id).toBeNull();
  });

  /**
   * **THE MATCH TABLE READS THE SERVER FIRST.** Lane B publishes
   * `resolved_premises_no`, `resolved_unit_no`, `resolved_premise_address` and
   * `resolved_match`; the server decides what a picked row MEANS, so a screen
   * printing only what the clerk clicked would go on saying *exact* after a
   * PATCH the server refused.
   *
   * ⚠ **AND THE FALLBACK'S LAST LINK IS AN ABSENCE, NOT AN ID.** Lane B, in
   * capitals: *"Fall back to `resolved_premise_address`, and to a stated
   * absence — never to the id, which is the defect coming straight back."*
   */
  it("the match table prefers the SERVER's number, falls back to its address, never to an id", () => {
    const form = {
      ...emptyCaptureForm(),
      address_as_given: "212 Balcones Drive",
      picked_premises_id: "prm-1",
      picked_premise_no: "P-00074",
    };
    const served = (over: Record<string, unknown>): ServiceRequestDetail => {
      const base = sent();
      return {
        ...base,
        location_and_services: { ...base.location_and_services, ...over },
      };
    };

    // The server's own number wins over the clerk's copy of it.
    expect(
      matchRows(
form,
        served({
          resolution_kind: "served_vacant",
          resolved_premises_no: "P-00052",
          resolved_match: "exact_reference",
        }),
      )[0],
    ).toMatchObject({ matched: "P-00052", confidence: "exact" });

    // A tenant with no numbering series: the number is null and its ID is not.
    // The address is printed; the id never is.
    const noSeries = matchRows(
form,
      served({
        resolution_kind: "served_vacant",
        resolved_premises_id: "01a0a444-5b1c-736b-917f-0d84a6882e02",
        resolved_premises_no: null,
        resolved_premise_address: "500 Main St",
        resolved_match: "exact_reference",
      }),
    )[0];
    expect(noSeries.matched).toBe("P-00074");
    expect(noSeries.matched).not.toContain("01a0a444");

    // …and with nothing picked either, the ADDRESS is the last printable link.
    const addressOnly = matchRows(
{ ...form, picked_premises_id: "", picked_premise_no: "" },
      served({
        resolution_kind: "served_vacant",
        resolved_premises_id: "01a0a444-5b1c-736b-917f-0d84a6882e02",
        resolved_premises_no: null,
        resolved_premise_address: "500 Main St",
        resolved_match: "exact_reference",
      }),
    )[0];
    expect(addressOnly.matched).toBe("500 Main St");
    expect(addressOnly.matched).not.toContain("01a0a444");

    // ⚠ **AND THE CASE THAT ACTUALLY BITES THE ID FALLBACK, ADDED BECAUSE THE
    // THREE ABOVE DO NOT** (hard-won law 7: *ask what would make this check
    // pass wrongly*). Sabotaging the chain to end at `resolved_premises_id`
    // left every assertion above GREEN, because each of them still had a
    // number, a pick or an address to stop at. The id is only reachable when
    // all three are gone — a tenant with no numbering series, a resolver that
    // matched by text, and nothing picked — so that is the row this asserts.
    const idOnly = matchRows(
{ ...form, picked_premises_id: "", picked_premise_no: "" },
      served({
        resolution_kind: "served_vacant",
        resolved_premises_id: "01a0a444-5b1c-736b-917f-0d84a6882e02",
        resolved_premises_no: null,
        resolved_premise_address: null,
        resolved_match: "exact_reference",
      }),
    )[0];
    // ⚠ **`String(… ?? "")` AND NOT A BARE `not.toContain`.** On the healthy
    // code this cell is `null`, and `expect(null).not.toContain(…)` THROWS
    // rather than passing — a check that cannot run is not a check. Coercing
    // keeps the assertion meaningful in both directions: it bites the id
    // fallback and it holds over the absence.
    expect(String(idOnly.matched ?? "")).not.toContain("01a0a444");
    // It is a stated absence instead — `TextOrNotSupplied` renders `null` as
    // *Not supplied*, which is what B14 rule 31 leaves when there is no
    // printable number.
    expect(idOnly.matched).toBeNull();
  });

  /** B14 rule 31 · `premise_no` and `unit_no`, never a uuid — and
   *  `matchRows` is the pure half of it. */
  it("the match table names the premises by its number, never by its id", () => {
    const picked = {
      ...emptyCaptureForm(),
      address_as_given: "212 Balcones Drive",
      picked_premises_id: "prm-1",
      picked_premise_no: "P-00074",
      address_unit_as_given: "U-00101-A",
      picked_unit_no: "U-00101-A",
    };
    const rows = matchRows(picked, null);
    expect(rows.map((row) => row.confidence)).toEqual(["exact", "exact"]);
    expect(rows[0].matched).toBe("P-00074");
    // ⚠ `matched` may now be a catalogue key + params (the unit-count row), so
    // the uuid hunt reads the WHOLE row rather than assuming a string — an
    // `includes` that silently skipped the object shape would be a rule-31
    // check that cannot fail on half the table (hard-won law 7).
    expect(JSON.stringify(rows)).not.toContain("prm-1");

    // Nothing picked and the SERVER found nothing: `notFound`, not a blank.
    expect(
      matchRows({ ...emptyCaptureForm(), address_as_given: "Lot 14" }, null)[0].confidence,
    ).toBe("notFound");
  });

  /**
   * ⊕ **THE THIRD DRAWN ROW — `BR-CUS-1055`, PO ruling 2026-09-15 (*"we need
   * to build this"*), drawn on p077 as `Units on the property · 6` against
   * `6 units on PR-0731`, confidence `Agrees`.**
   *
   * The count is a **CLAIM, not a count**: what the applicant says against what
   * the register holds, and the two are allowed to disagree. So `differs` is
   * built even though the drawing never shows it — **a confidence column that
   * can only ever say one word is a check that cannot fail** (hard-won law 7),
   * and the word is the only thing on the screen that tells a clerk the
   * applicant may be wrong about their own building.
   */
  /**
   * ⚠⚠ **REVERSED 2026-09-22 — PO report row 12, *"Remove Units on site"*.**
   *
   * This case proved `BR-CUS-1055`'s third match row four ways: six claimed
   * against six on record AGREES, four against six DIFFERS, no register count
   * is NOT agreement, and an empty box is not a claim of zero. Every one of
   * those was right, and the question that produced the claim is gone — from
   * step 3 and from the request detail — so the row has nothing left to
   * compare.
   *
   * **The case is INVERTED rather than deleted**, for the reason
   * `DEF-CUS-3653` records: an absence is invisible to every check this repo
   * has, so the thing most likely to happen next is that somebody restores the
   * row without a ruling and nothing notices. This goes red if they do.
   *
   * **The two rows that carry the evidence a clerk approves on — the address
   * match and the unit match — are untouched and are asserted here too**, so
   * this case still fails if the removal took a neighbour with it.
   */
  it("BR-CUS-1055's unit-count row is GONE, and the two match rows beside it are not", () => {
    const base = {
      ...emptyCaptureForm(),
      address_as_given: "301 Mill Pond Ln",
      address_unit_as_given: "Unit 2",
      picked_premises_id: "prm-45",
      picked_premise_no: "P-00045",
    };

    // PO 2026-09-22 row 12 — no units row, whatever the claim and whatever the
    // register holds. All four of the old case's inputs are still exercised.
    // ⚠ **THE THIRD ARGUMENT WENT WITH THE ROW.** `matchRows` took a register
    // unit count to weigh the claim against; nothing reads it now, so the
    // pairs above became claims alone. An argument nothing reads is dead
    // wiring pointing the other way, and leaving it here would keep asserting
    // a comparison the product no longer makes.
    for (const claimed of ["6", "4", "", "0"] as const) {
      expect(
        matchRows({ ...base, units_on_property: claimed }, null).some(
          (row) => row.key === "units",
        ),
      ).toBe(false);
    }

    // …and the removal took nothing with it.
    const rows = matchRows({ ...base, units_on_property: "6" }, null);
    expect(rows.map((row) => row.key)).toEqual(["premises", "unit"]);
    expect(rows.find((row) => row.key === "premises")?.lookedFor).toBe("301 Mill Pond Ln");
    expect(rows.find((row) => row.key === "unit")?.lookedFor).toBe("Unit 2");
  });

  /**
   * ⊕ **WHAT STEP 3 NOW SENDS, AND WHAT IT HAS STOPPED SENDING.**
   *
   * The unit count is a real payload key (`CAPTURE_FIELDS` has accepted it
   * since `customers/0049`). The property type is NOT dropped — the CONTROL
   * came off the step on 2026-09-19 and the COLUMN stays, which the drawing
   * says in as many words about the plot field one panel over.
   */
  it("BR-CUS-1055 · the unit count is sent, and the property type no longer is", () => {
    const sent = capturePayload({
      ...emptyCaptureForm(),
      applicant_name: "Osei, Grace",
      address_as_given: "301 Mill Pond Ln",
      units_on_property: " 6 ",
    });
    expect(sent.units_on_property).toBe("6");
    // Clearing the box CLEARS the column: `""` is sent, which the server reads
    // as `None`. `undefined` would mean *this PATCH is not about the count* and
    // would leave a stale claim standing after the clerk wiped it.
    expect(
      capturePayload({ ...emptyCaptureForm(), units_on_property: "" }).units_on_property,
    ).toBe("");
    // ⛔ Nothing on this wizard writes a property type any more — but the key
    // is still buildable, so a caller that knows one can still send it.
    expect(capturePayload(emptyCaptureForm()).property_type).toBeUndefined();
    expect(
      capturePayload({ ...emptyCaptureForm(), property_type: "vacant_land" }).property_type,
    ).toBe("vacant_land");
  });

  /**
   * ⚠⚠ **PO RULING 2026-09-22 — STEP 3 TAKES THE ADDRESS IN PARTS, AND THIS
   * REVERSES A REFUSAL THIS SCREEN CARRIED FOR A WEEK.**
   *
   * Verbatim: *"correct address will be on presmies but first time you will
   * ahve to take the details to match it"*. On 2026-09-15 the PO had ruled
   * that capture is a SEARCH and the locality is walked to; three columns of
   * these exact names were added and removed the same hour, `BR-CUS-1055`
   * recorded the near-miss, and `CAPTURE_FIELDS` carried *"Do not re-add
   * them"* until today.
   *
   * **The rule was quoted correctly and applied to the wrong act.**
   * `BR-MET-1161` governs where an address is STORED as the truth; it says
   * nothing about what a clerk may TYPE, and a request that cannot take a city
   * and a ZIP cannot find the premises it is about.
   *
   * ⚠ **WHAT THIS CASE GUARDS IS THE POSTURE, NOT JUST THE PLUMBING.** Every
   * key is `_as_given`, because these are a STATEMENT and not an address of
   * record; the payload must never grow a bare `city`, `state` or
   * `postal_code`, which is what `G85` refuses on this table by name.
   */
  it("PO 2026-09-22 · step 3 sends the address PARTS, every one of them `_as_given`", () => {
    const sent = capturePayload({
      ...emptyCaptureForm(),
      applicant_name: "Osei, Grace",
      address_as_given: "301 Mill Pond Ln",
      address_city_as_given: "  Austin ",
      address_state_as_given: " TX ",
      address_postal_code_as_given: " 78704 ",
    });
    expect(sent.address_city_as_given).toBe("Austin");
    expect(sent.address_state_as_given).toBe("TX");
    expect(sent.address_postal_code_as_given).toBe("78704");

    // ⛔ **AND NOT A FOURTH HOME.** A bare `city` / `state` / `postal_code` on
    // this payload is the column `G85` refuses on this table, and it is what
    // the 2026-09-15 near-miss actually was.
    const keys = Object.keys(sent);
    for (const bare of ["city", "state", "postal_code", "zip", "postcode"]) {
      expect(keys).not.toContain(bare);
    }

    // Clearing a box CLEARS the column, the same way the unit count does:
    // `""` reads as `None` on the server, where `undefined` would leave a
    // stale claim standing after the clerk wiped it.
    const cleared = capturePayload({ ...emptyCaptureForm(), address_city_as_given: "" });
    expect(cleared.address_city_as_given).toBe("");
  });

  // ── STEP 4 · the drawn table and its four chips ─────────────

  /**
   * ⚠ **THIS TEST USED TO COUNT CHECKBOXES AND IT WAS TESTING THE WRONG
   * SCREEN.** Step 4 drew nine tick-boxes over `form.documents` — component
   * state that a draft save never read back — and the chips narrowed that
   * tick-list. p078 draws a TABLE of what the request HOLDS, so the chips now
   * narrow ROWS and the only checkbox on the step is `Required on this
   * request` in the attach form. Counting checkboxes would now pass on an
   * empty table, which is hard-won law 7's *incapable of failing*.
   */
  /**
   * ⚠ **AMENDED 2026-09-22, AND RED SINCE `74511fa68` (hard-won law 7 habit
   * 1).** PO report item 10: `All · Required · Missing · Rejected` come off
   * CAPTURE. They are the REVIEWER's filters — nothing on a capture screen can
   * be `Missing` or `Rejected`, because the clerk is standing there with the
   * file — and a clerk cannot return to this screen either
   * (`serviceRequestCapturePath` has zero production callers). They stay on the
   * request detail's Documents tab, which is the screen that reviews.
   *
   * **THE FILTERING ITSELF IS NOT DELETED AND IS STILL PROVED**, by the pure
   * case immediately below and by `DocumentFilterChips`' own tests: the
   * question *does `missing` ask about BYTES rather than about the column being
   * set* (`DEF-CUS-5872`) is the one that cost a defect, and it is still asked.
   */
  it("step 1's documents table draws NO reviewer chips, and every file on the request is listed", async () => {
    // ⊕ **AMENDED 2026-10-18 (lane CF-1).** Step 1's documents are the SHARED
    // documents table (drawing set `customer-forms-2026-10-18`, image 03): it
    // lists every document the request holds a FILE for, locked, beside the
    // utility's required rows. The reviewer chips stay off, as before.
    mountWith("?request=sr-0056&step=1", { detail: withDocs() });
    const table = () =>
      document.querySelector("[data-request-customer-form]")?.textContent ?? "";
    await waitFor(() => expect(table()).toContain("driving-licence.pdf"), { timeout: 4000 });
    // A row with no file is not a document on the table (`file_present`).
    expect(table()).not.toContain("block-plan.pdf");
    for (const name of ["all", "required", "missing", "rejected"] as const) {
      expect(
        screen.queryByRole("button", {
          name: t(`customers.serviceRequest.capture.filter.${name}`),
        }),
      ).toBeNull();
    }
    expect(document.querySelectorAll("[data-doc-filter]")).toHaveLength(0);
  });

  /** The pure half, so the four questions are readable without a DOM. */
  it("each chip asks a different question of the same rows", () => {
    const rows = withDocs().documents.documents;
    expect(filterDocRows(rows, "all", null)).toEqual(rows);
    // `missing` is about BYTES, not about the column being set.
    expect(filterDocRows(rows, "missing", null).map((r) => r.doc_type)).toEqual([
      "tenancy_agreement_or_deed",
      "site_plan_or_unit_schedule",
    ]);
    expect(filterDocRows(rows, "rejected", null).map((r) => r.doc_type)).toEqual([
      "site_plan_or_unit_schedule",
    ]);
    // Nothing is required until a checklist says so or a clerk ticks the box.
    expect(filterDocRows(rows, "required", null)).toEqual([]);
  });

  /**
   * ⚠ **`REQUIRED` HAS THREE ANSWERS AND THE DRAWING DRAWS ALL THREE.**
   * p078 prints `Yes`, `No` and — on the `Anything else` row — an em dash:
   * the catch-all type is not something a checklist can name, so *is it
   * required* has no answer rather than a negative one.
   */
  it("REQUIRED is Yes, No or no answer at all", () => {
    const [identity, tenancy, plan] = withDocs().documents.documents;
    expect(docRequired(identity, null)).toBe(false);
    expect(docRequired({ ...identity, required: true }, null)).toBe(true);
    // The tenant's own checklist is the second of the two facts.
    expect(
      docRequired(tenancy, {
        ...sent(),
        documents: { ...sent().documents, checklist_required: ["tenancy_agreement_or_deed"] },
      }),
    ).toBe(true);
    expect(docRequired({ ...plan, doc_type: "other" }, null)).toBeNull();
  });

  // ── STEP 6 · the right-hand column ─────────────────────────────────────

  /**
   * RED at `2c8161fc`: step 6 drew ONE column. The drawing (p079–p080) puts
   * Documents, Fees and On submit in a right-hand column beside the three
   * review blocks.
   */
  it("step 6 draws two columns, and the right one is the three drawn blocks", async () => {
    mountWith("?step=4");
    await screen.findByText(t("customers.serviceRequest.capture.reviewApplicant"));
    const right = document.querySelector('[data-review-column="right"]');
    expect(right).not.toBeNull();
    expect(right?.textContent).toContain(t("customers.serviceRequest.tab.documents"));
    expect(right?.textContent).toContain(t("customers.serviceRequest.capture.stepShort.fees"));
    expect(right?.textContent).toContain(t("customers.serviceRequest.capture.onSubmit"));

    // ⛔ **THE ONE DRAWN BLOCK STILL ABSENT, ASSERTED AS ABSENT.** *What goes
    // out to the applicant* and its template picker belong to the messaging
    // seam a sibling lane owns; a second messages table here is the thing that
    // seam exists to prevent.
    expect(right?.textContent).not.toContain("What goes out to the applicant");
  });

  /** `On submit`'s three rows, and the honest state before a draft exists. */
  it("On submit states the number, the move and what it waits on", async () => {
    mountWith("?step=4");
    expect(
      await screen.findByText(t("customers.serviceRequest.capture.notNumberedYet")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(t("customers.serviceRequest.capture.draftToSubmitted")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(t("customers.serviceRequest.capture.waitingOn")),
    ).toBeInTheDocument();
  });

  /**
   * ⛔ **THE SENTENCE THE COUNTER-FEE RULING SUPERSEDED MUST NOT BE PRINTED.**
   * PO 2026-09-15: the fee posts. *"This takes money and posts nothing"* was
   * half true and is now half false, so the screen says only the half that
   * survives — no invoice and no account.
   */
  it("step 5 no longer says the fee posts nothing", async () => {
    mountWith("?step=3");
    expect(
      await screen.findByText(t("customers.serviceRequest.capture.noInvoiceNoAccount")),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(t("customers.serviceRequest.fees.notALedgerPosting")),
    ).toBeNull();
  });

  /** The tender the PO asked for, and only for the method chosen. */
  /**
   * ══════════════════════════════════════════════════════════════════════════
   * **PO REPORT 2026-09-22, ROW 11 — THE APPLICATION FEE AMOUNT COMES FROM A
   * DROPDOWN READING THE CHARGE CODES.**
   * ══════════════════════════════════════════════════════════════════════════
   *
   * Step 5 showed `Quoted` and `Outstanding` as read-only figures and offered
   * no way to make either of them anything but `$0.00`. The door has existed
   * the whole time — `POST /service-requests/{id}/fees`, with
   * `addServiceRequestFee` exported beside it — and **was called by nothing**
   * (`DEF-CUS-5904`). That is hard-won law 2 exactly: the endpoint works, the
   * client works, `tsc` passes, and no clerk can raise an application fee.
   *
   * ⚠ **THE FIRST ASSERTION IS THE ONE THAT MATTERS, AND IT IS THE POST.**
   * A picker that renders, lists codes and sends nothing would satisfy every
   * visual check here and still be the defect this closes. So the case reads
   * what reached the server.
   *
   * ⚠ **AND IT ASSERTS THE *STORED* AMOUNT, NOT THE DISPLAYED ONE (rule 2).**
   * `amount` is four places and is the money a customer is charged;
   * `amount_display` is two places, rounded for a person to read. Posting the
   * display string is a silent money bug that no screen would ever show.
   */
  it("PO 2026-09-22 · step 5 raises the fee from a charge code, at the stored amount", async () => {
    const posted: { url: string; body: unknown }[] = [];
    // The fee picker needs a SAVED request to hang a line on, and the wizard
    // only loads one when the URL names it — the same reason step 4's document
    // case mounts this way.
    mountWith("?request=sr-0056&step=3", {
      detail: sent(),
      posted,
      charges: [
        {
          id: "chg-1",
          code: "CC-REQFEE",
          name: "Application processing fee",
          charge_type: "one_time",
          service: null,
          amount_rule: "flat",
          amount: "25.0000",
          percent: null,
          min_amount: null,
          max_amount: null,
          amount_display: "25.00",
          percent_display: null,
          min_amount_display: null,
          max_amount_display: null,
          gl_account_id: "gl-1",
        },
        // ⛔ **NOT OFFERED — the PO's own 2026-09-21 ruling.** `TAP` states no
        // amount, so it cannot be priced; a clerk picked exactly this code on
        // another screen and the last press answered *"Something went wrong on
        // our side."* after thirty-three acts (`DEF-MET-6110`).
        {
          id: "chg-2",
          code: "TAP",
          name: "New service tap fee",
          charge_type: "one_time",
          service: null,
          amount_rule: null,
          amount: null,
          percent: null,
          min_amount: null,
          max_amount: null,
          amount_display: null,
          percent_display: null,
          min_amount_display: null,
          max_amount_display: null,
          gl_account_id: "gl-2",
        },
        // ⛔ **NOT OFFERED — wrong KIND of charge.** A recurring base charge is
        // something that happens to an account over time; an application fee is
        // taken once, at a counter, against a request with no account yet.
        {
          id: "chg-3",
          code: "BASE-W",
          name: "Water base service",
          charge_type: "recurring",
          service: "water",
          amount_rule: "flat",
          amount: "8.0000",
          percent: null,
          min_amount: null,
          max_amount: null,
          amount_display: "8.00",
          percent_display: null,
          min_amount_display: null,
          max_amount_display: null,
          gl_account_id: "gl-3",
        },
      ],
    });

    // ⚠ **`+ Fee` MAKES A ROW AND ITS CHOOSER RAISES THE FEE — REQ-03 task 9,
    // 2026-09-29.** This case used a searchable `+ Add a fee ▾` box; the
    // drawing now puts the chooser IN the row and the button under the table.
    // **WHAT IT OFFERS IS UNCHANGED AND IS STILL THE POINT**: only the one
    // priceable, one-time code, so `TAP` (no amount) and `BASE-W` (recurring)
    // stay out.
    fireEvent.click(
      await waitFor(() => {
        const node = document.querySelector("[data-add-fee]");
        if (node === null) throw new Error("no + Fee yet");
        return node as HTMLElement;
      }),
    );
    const chooser = await waitFor(() => {
      const node = document.querySelector(
        "[data-editable-table='application-fees'] tbody select",
      ) as HTMLSelectElement | null;
      if (node === null) throw new Error("no chooser in the new row");
      return node;
    });
    const offered = Array.from(chooser.options)
      .map((option) => option.value)
      .filter(Boolean);
    expect(offered).toEqual(["CC-REQFEE"]);

    fireEvent.change(chooser, { target: { value: "CC-REQFEE" } });
    await waitFor(() => {
      expect(posted.some((row) => row.url.includes("/fees"))).toBe(true);
    });
    // ⚠ NOT named `sent` — `sent()` is this suite's detail fixture and is
    // called at the top of this very case; a `const sent` here would shadow it
    // and throw before the mount ever happened.
    const feePost = posted.find((row) => row.url.includes("/fees"))?.body as Record<
      string,
      unknown
    >;
    expect(feePost.charge_code).toBe("CC-REQFEE");
    expect(feePost.charge_code_id).toBe("chg-1");
    expect(feePost.unit_amount).toBe("25.0000");
    expect(feePost.quantity).toBe("1");
    // `Charged per · Request` — an application fee is raised once per request.
    expect(feePost.basis).toBe("per request");
  });

  // ⚠ `DEF-CUS-10041` (PO 2026-10-11): this case asserted the Pay now / Pay
  // later radios were ABSENT and drove a *"How is it being paid?"* select. The
  // PO asked for the choice back; the panel's own cases live in
  // `RequestPaymentDetails.dom.test.tsx`. What stays here is the screen half:
  // with no fee owed there is nothing to pay, so no payment panel is drawn.
  it("with no fee owed, step 3 draws no payment panel", async () => {
    mountWith("?step=3");
    await screen.findByRole("heading", { level: 1 });
    expect(document.querySelector("[data-payment-details]")).toBeNull();
    expect(screen.queryByText(t("customers.serviceRequest.pay.heading"))).toBeNull();
  });

  /**
   * ⚠ **B14 rules 31 and 32 — NOTHING INTERNAL REACHES A CLERK.**
   * `internalReferencesIn` reads RENDERED text for the id grammar and for
   * dotted Python identifiers, and it is how `DEF-BIL-5339` and
   * `DEF-BIL-5344` were caught. Every step is walked, because a leak on one
   * step is invisible to a check that only opens another.
   */
  it.each([1, 2, 3, 4, 5, 6])("step %i shows no rule id, defect id or code path", async (step) => {
    mountWith(`?step=${step}`, { premises: [BALCONES] });
    await screen.findByRole("heading", { level: 1 });
    expect(internalReferencesIn(document.body)).toEqual([]);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// THE DRAFT MINIMUM AND THE FORM GRID — PO ratifications 2026-09-20
// ═══════════════════════════════════════════════════════════════════════════
//
// `DEF-CUS-6006` (the draft gate) and `DEF-CUS-6007` (the grid and its
// rhythm). Decision log, `## 2026-09-20 · SEVEN PO RATIFICATIONS FROM ONE
// SITTING`, subsection 3, and the PO on the same screen: *"on this screen can
// you keep Applying as* and Channel - in one line/row - also you are not
// applying the spacing rules"*.
//
// ⚠ **THESE MOUNT UNDER THE REAL `/:tenant/requests/new` ROUTE PATTERN AND THE
// REST OF THIS FILE DOES NOT.** A bare `MemoryRouter` with no matching `Route`
// leaves `useParams().tenant` undefined, so every address the page builds comes
// out `//portal/…` — a protocol-relative URL to another host that reads as a
// perfectly good string to `toContain`. That is hard-won law 2's own fixture
// clause, and it is why `mountRouted` exists beside the four mounts above it
// rather than replacing them in a lane that is not about them.
describe("REQ-03 · the draft minimum and the form grid (2026-09-20)", () => {
  afterEach(cleanup);

  function mountRouted(search = ""): void {
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async (input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.includes("/service-requests/categories")
          ? { selectable: [], legacy: [] }
          : url.includes("/lookups/")
            ? { count: 0, next: null, previous: null, results: [] }
            : [];
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[`/brazosbend/requests/new${search}`]}>
          <Routes>
            <Route
              path="/:tenant/requests/new"
              element={<ServiceRequestCapturePage client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  const saveAsDraft = (): HTMLButtonElement =>
    screen.getByRole("button", {
      name: t("customers.serviceRequest.capture.saveAsDraft"),
    }) as HTMLButtonElement;

  // ── PART 1 · THE DRAFT MINIMUM ──────────────────────────────────────────
  it("a draft needs the applicant NAME ALONE — no address", () => {
    const form = emptyCaptureForm();
    expect(canCreateDraft(form)).toBe(false);
    expect(canCreateDraft({ ...form, applicant_name: "Osei, Grace" })).toBe(true);
  });

  it("a STAFF-RAISED draft needs NOTHING — BR-CUS-091", () => {
    expect(canCreateDraft({ ...emptyCaptureForm(), channel: "staff_collections" })).toBe(true);
  });

  it("an address with no name is still not enough", () => {
    // The name did not move. Only the address did.
    expect(canCreateDraft({ ...emptyCaptureForm(), address_as_given: "14 Willow Bend" })).toBe(
      false,
    );
  });

  it("Save as draft is LIVE on step 1 once the name is typed", async () => {
    mountRouted("?step=1");
    await screen.findByRole("heading", { level: 1 });
    expect(saveAsDraft()).toBeDisabled();
    await userEvent.type(
      screen.getByLabelText(t("customers.serviceRequest.capture.fullName"), { exact: false }),
      "Osei, Grace",
    );
    expect(saveAsDraft()).toBeEnabled();
  });

  /**
   * ⚠ **THE MESSAGE IS VISIBLE TEXT, NOT A `title` ATTRIBUTE.** PO, verbatim:
   * *"we should show a message in short to user when this happens"*. A `title`
   * is reachable by a mouse hover and by nothing else — not by a touch, not by
   * a keyboard, not by a screen reader on a DISABLED control, which is exactly
   * the control it was hung on. B14 rule 33 caps an INSTRUCTION at six words
   * per sentence and puts RATIONALE at ZERO words on screen.
   */
  it("the short message is rendered text, and the long rationale is gone", async () => {
    mountRouted("?step=1");
    await screen.findByRole("heading", { level: 1 });
    const short = t("customers.serviceRequest.capture.nameFirst");
    expect(short.split(/\s+/)).toHaveLength(4);
    const note = screen.getByText(short);
    expect(note).toBeInTheDocument();
    // The button POINTS at it rather than carrying the sentence itself.
    expect(saveAsDraft().getAttribute("title")).toBeNull();
    expect(saveAsDraft().getAttribute("aria-describedby")).toBe(note.id);
    // RATIONALE — why it cannot save yet, what a number is for — is off screen.
    expect(document.body.textContent).not.toContain("read down the phone");
  });

  it("the message goes once the name is typed", async () => {
    mountRouted("?step=1");
    await screen.findByRole("heading", { level: 1 });
    // ⚠ **ASSERTED PRESENT FIRST, OR THIS CASE PASSES ON AN ABSENT CATALOGUE
    // KEY.** Proved red at `934ada177`, it read *"expected null to be null"* —
    // true, and true of a screen that never renders the sentence at all. That
    // is hard-won law 7 habit (2): ask what would make this check pass wrongly.
    expect(screen.getByText(t("customers.serviceRequest.capture.nameFirst"))).toBeInTheDocument();
    await userEvent.type(
      screen.getByLabelText(t("customers.serviceRequest.capture.fullName"), { exact: false }),
      "Osei, Grace",
    );
    expect(screen.queryByText(t("customers.serviceRequest.capture.nameFirst"))).toBeNull();
  });

  // ── PART 2 · THE FORM GRID ──────────────────────────────────────────────
  /**
   * B14 rule 38 — where a drawing and our UI rules disagree about how a FORM IS
   * BUILT, the UI rules win. p076 pairs `Channel` with `Full name *`; the PO
   * ruled the row directly, and side-by-side fields are CONSTRUCTION.
   */
  it("the channel stays on step 1, inside the shared Who panel (lane CF-1)", async () => {
    // ⊕ **AMENDED 2026-10-18 (lane CF-1).** This case read *"Applying as and
    // Channel share one row"*; step 1 is the SHARED customer form now (drawing
    // set `customer-forms-2026-10-18`, image 03) and the kind is its Person /
    // Company pair on top. Image 03 does not draw the channel; it is KEPT,
    // because BR-CUS-091 hangs off it, under the Who panel's fields.
    mountRouted("?step=1");
    await screen.findByRole("heading", { level: 1 });
    const who = document.querySelector('[data-customer-panel="who"]') as HTMLElement;
    expect(who).not.toBeNull();
    expect(who.contains(document.getElementById("channel"))).toBe(true);
  });

  /**
   * B14 rule 39 as amended 2026-09-12 — *"a) 20 everywhere — the anatomy
   * wins"*. ⊕ Lane CF-1: the shared Who panel carries 20px INSIDE each grid
   * (`gap-y-5`) and BETWEEN its blocks (`gap-5`), so the rhythm is the kit's.
   */
  it("step 1 stacks its blocks on the ruled 20px rhythm", async () => {
    mountRouted("?step=1");
    await screen.findByRole("heading", { level: 1 });
    const grid = (document.getElementById("email") as HTMLElement).closest("div.grid") as HTMLElement;
    expect(grid.className).toContain("gap-y-5");
    expect(grid.className).not.toContain("gap-y-4");
    const stack = grid.parentElement as HTMLElement;
    expect(stack.className).toContain("gap-5");
  });

  /**
   * B14 rule 32 and the file's own precedent, written when the co-applicant
   * heading came off: *"A `Panel` is this repo's INFORMATION GROUP, and a group
   * of one checkbox is not a group."* A group of one status pill is not a group
   * either — it was a bordered 16px box with a single four-word pill in it.
   */
  it("the CAPTURING FOR A CUSTOMER pill is not wrapped in a panel of its own", async () => {
    mountRouted("?step=1");
    await screen.findByRole("heading", { level: 1 });
    const pill = screen.getByText(t("customers.serviceRequest.capture.capturingForACustomer"));
    expect(pill).toBeInTheDocument();
    expect(pill.closest("[data-panel]")).toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W4 task 4.15 · B19 §1–§7 · §11
// generated: 2026-08-24 by the CR-031 W4 FRONTEND lane (M3)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: vitest✔
// exceptions: E3 the six wizard STEPS are exercised in the browser walkthrough
//   rather than here: `WizardFrame` renders one step at a time behind its own
//   nav state, and `renderToStaticMarkup` cannot click. What is unit-tested is
//   every PURE rule the steps depend on — the create minimum, the payload
//   shape, the blank count and the footer copy · E3 TC-REQ-1 and TC-REQ-2
//   (numbering and submit idempotency) are SERVER guarantees; the frontend half
//   asserted here is that the number reaches the footer and the confirmation
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
