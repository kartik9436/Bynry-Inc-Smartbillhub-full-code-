// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  `CR-094-BRC01` lane F — **S84, the service-request detail's HEAD**,
//          built to the accounts blueprint's PAGE IMAGES rather than to the
//          markdown extraction of them (PO ruling 2026-09-13: *"When you use
//          images to create screens your accuracy is higher; hence dont create
//          screens using only Text"*).
//
//          ⚠ **THE DRAWING IS ON p82–83, NOT p141.** The extractor's index puts
//          screens 16 (the list) and 17 (the detail) on one span starting at
//          p141 and says in its own words that it could not separate them; the
//          markdown for screen 17 is a pointer with no drawing in it at all.
//          The images settle it — which is the whole reason the ruling above
//          exists.
// Rules:   B14 rule 40 (the page title is 32px, and this screen's is the
//          applicant) · B14 rule 41 (the product UI matches the blueprint) ·
//          B14 rule 32 · BR-CUS-093 (a draft carries its number from the
//          moment it is started — so the number's stated absence survives)
// Tests:   this file. The TAB BODIES are unit-tested as components in
//          `ServiceRequestDetailPage.test.tsx`, which runs under node and
//          cannot mount a routed page; the HEAD needs a router and a query
//          client, so it needs jsdom and therefore its own file.
// ───────────────────────────────────────────────────────
//
// WHAT THE DRAWING SAYS, QUOTED OFF THE IMAGE (p82, the request opened):
//
//     ← The register
//     REQUEST SR-26-0001 · NEW CONNECTION
//     Miller, Sarah
//     Submitted   Waiting on documents   Counter   Received 05/04/2026
//     ⌂ 212 Balcones Drive · Unit 3 · Austin, TX 78704
//
// ⚠ **EVERY CASE HERE WAS PROVED RED AT THIS LANE'S STARTING TIP**
// (`e3bcdd233`, in a `git worktree`, under this same vitest, through
// `npx vitest run` — the harness that runs it, not a hand-called module). What
// each one found there is quoted on the case.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { internalReferencesIn } from "@/testSupport/internalReferences";

import { ServiceRequestDetailPage } from "./ServiceRequestDetailPage";

const REQUEST_ID = "01a09540-7900-7dfa-abf4-b30b3c0fb6b8";

/**
 * One served request. The FIGURES here are this fixture's own and are NOT taken
 * from the drawing — B14 rule 37: *"a figure drawn in a wireframe is an
 * ILLUSTRATION, never a fact to build to"*, so seeding `SR-26-0001` /
 * `Miller, Sarah` / `05/04/2026` out of the picture would be asserting the
 * picture. What IS asserted is the drawn SHAPE: which fact stands where.
 */
const DETAIL = {
  header: {
    id: REQUEST_ID,
    request_no: "SR-26-0071",
    number_absence: null,
    state: "submitted",
    classification: "new_connection",
    applicant: "Okonkwo, Adaeze",
    address_as_given: "88 Pine Vista · Unit 2",
    lookup_found: null,
    received_at: "2026-08-14T09:22:00Z",
    received_by: null,
    channel: "walk_in",
    waiting_on: "documents",
    waiting_since: "2026-08-14T09:22:00Z",
    requested_start: null,
  },
  actions: {
    // ⚠ **WHAT THE STATE ALLOWS, WHICH IS WHAT THE HEAD'S FOUR BUTTONS READ.**
    // `available: []` here would leave every one of them disabled and the
    // assertions below would pass over a screen with four dead controls —
    // hard-won law 2's mirror, in a fixture.
    available: ["approve", "refuse", "request_info", "withdraw"],
    can_approve: false,
    approve_blocked_by: ["documents_verified"],
    can_park: true,
  },
  applicant: {
    name: "Okonkwo, Adaeze",
    phone: null,
    email: null,
    language: null,
    person_or_company: null,
    co_applicant: { name: null, email: null, phone: null },
    // An applicant who gave neither identifier and no date of birth: nothing
    // here may draw the "stored encrypted" claim over a blank (BR-CUS-092(d)).
    identifier: {
      ssn_present: false,
      ssn_last4: null,
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
    address_as_given: "88 Pine Vista",
    address_unit_as_given: "88 Pine Vista · Unit 2",
    units_on_property: 4,
    billing_address_same: true,
    billing_address_as_given: null,
    resolved_premises_id: "01a0a444-5ad2-7e88-be8a-bdb8aa86c05e",
    resolved_unit_id: null,
    resolved_premises_no: "P-00074",
    resolved_unit_no: null,
    resolved_premise_address: "88 Pine Vista",
    premise_locality: { city: "Silver Creek", state: "TX", postal_code: "78611" },
    resolved_match: "exact_reference",
    resolution_kind: "served_vacant",
    plot_or_parcel: null,
    what_is_being_built: null,
    property_type: null,
    no_premise_flag: false,
    lookup_found: null,
    services: [],
    evidence: { premise_exists: true, unit_is_served: false, unit_is_vacant: true },
  },
  documents: {
    documents: [],
    verified: 0,
    attached: 0,
    blocks_creation: false,
    // PO ruling 2026-09-16 — documents are OUTSTANDING, never blocking.
    blocks_approval: false,
    outstanding: true,
    checklist_request_type: null,
    checklist_required: [],
    checklist_unmet: [],
  },
  fees: {
    lines: [],
    outstanding_lines: 0,
    quoted: { amount: "0.0000", display: "0.00", currency: null },
    settled: { amount: "0.0000", display: "0.00", currency: null },
    collected: { amount: "0.0000", display: "0.00", currency: null },
    outstanding: { amount: "0.0000", display: "0.00", currency: null },
    shortfall_is_open_balance: false,
    receipt_no: null,
    collected_at: null,
    quoted_at_collection: null,
    fee_timing: null,
    fee_due_by: null,
    fee_method: null,
    posts_to_ledger: false,
    connection_quote: { raised: false, reason: "raised_after_review" },
  },
  decision: {
    what_they_said: null,
    what_the_lookup_found: null,
    options: [],
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
    refusal: { reason_code: null, reason: null, message: null },
    more_info: { needed: [], message: null },
    what_approving_will_do: {},
    acknowledgement: { state: null, reason: null, ref: null, sent: false, fee_statement: null },
  },
  history: [],
  unavailable: [],
};

function mount(detail: unknown = DETAIL): void {
  const client = createApiClient({
    tenant: "brazosbend",
    // ⚠ **THE MOCK ANSWERS BY ADDRESS, NOT WITH ONE BODY FOR EVERYTHING.** The
    // Applicant tab now mounts `ServiceRequestInterruption`, which asks its own
    // endpoint; a mock returning the request detail to every URL handed that
    // component a shape it cannot read and the page threw. A fixture that
    // cannot tell two endpoints apart is a fixture that proves neither
    // (hard-won law 2's `MemoryRouter` note, one layer down).
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(input);
      // The real endpoint 404s on a request that is not about an interruption,
      // and the component then renders NOTHING — its own docstring says so.
      // This fixture says the same thing the same way.
      if (url.includes("/interruption")) {
        return new Response(JSON.stringify({ detail: "not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(detail), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      {/* ⚠ **MOUNTED UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with
          no `/:tenant/...` route leaves `useParams()` empty, so `requestId` is
          `""` and every address the page builds comes out `//requests/…` — a
          protocol-relative URL to another host, which reads as a perfectly good
          string to `toContain`. That is how `DEF-CWP-3925` hid. */}
      <MemoryRouter initialEntries={[`/brazosbend/requests/${REQUEST_ID}`]}>
        <Routes>
          <Route
            path="/:tenant/requests/:requestId"
            element={<ServiceRequestDetailPage client={client} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the request detail's head matches the blueprint drawing", () => {
  afterEach(cleanup);

  /**
   * RED at the tip: the `<h1>` was **`SR-26-0005`** — the record's own reference
   * standing where the drawing puts a person's name, with the applicant demoted
   * into the roll-up beside it.
   *
   * ⚠ **ASSERTED BY ROLE, NOT BY TEXT.** At the tip the applicant's name WAS on
   * the screen, one line lower; `getByText` would have passed straight over the
   * defect. What is drawn is the name **as the page title**.
   */
  it("the page title is the applicant, not the request number", async () => {
    mount();
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      "Okonkwo, Adaeze",
    );
    expect(screen.getByRole("heading", { level: 1 })).not.toHaveTextContent("SR-26-0071");
  });

  /**
   * RED at the tip: the kicker read the bare word **`REQUEST`**. The drawing
   * reads `REQUEST SR-26-0001 · NEW CONNECTION` — the number a clerk quotes
   * down the phone, and the job this request becomes, before anyone scrolls.
   */
  it("the kicker carries the number and the type", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    const kicker = document.querySelector("[data-kicker]");
    expect(kicker?.textContent).toContain("SR-26-0071");
    expect(kicker?.textContent).toContain(
      i18n.t("customers.serviceRequest.type.new_connection", {
        defaultValue: i18n.t("customers.serviceRequest.type.notYetClassified"),
      }),
    );
  });

  /**
   * ⚠ **THIS CASE ASSERTED `← The register` UNTIL 2026-09-20 AND THE PO
   * REPORTED IT AS A DEFECT.** It was built to the drawing, correctly, and the
   * drawing's word turned out to name FOUR different places — decision log
   * 2026-09-20 §8. The PO pressed this control on an approved move-in request:
   * *"when i lick on register - it shoudl take me to movein list page -
   * instead it takes me to request list page"*.
   *
   * **B14 rule 1 decides it: a page header's `←` NAMES WHERE IT EXITS TO**, and
   * rule 38's principle settles the conflict with the drawing — where a
   * drawing and a signed rule disagree, the rule wins and the deviation is
   * recorded rather than silently taken either way. So the drawing stands as
   * drawn and the PRODUCT changes, which is the same posture the PO took on
   * the move-out record the same day: *"we will not make changes to drawing"*.
   *
   * This fixture is a SUBMITTED request, so the destination is the requests
   * list and the word is the one the Requests tab already uses. The full
   * per-outcome table is `ServiceRequestActionBar.dom.test.tsx`.
   */
  it("the back crumb names the requests list, not `the register`", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    const back = screen.getByTestId("request-back");
    expect(back.textContent).toContain(i18n.t("customers.accounts.tab.requests"));
    expect(screen.queryByText(/The register/)).toBeNull();
    expect(back.getAttribute("href")).toBe(`/brazosbend/requests`);
  });

  /**
   * RED at the tip: the roll-up repeated the request number and the applicant
   * name — both of which now stand in the kicker and the title — and printed
   * NEITHER the channel nor the received date, which the drawing puts on that
   * line.
   *
   * ⚠ **THE WORDS COME FROM THE LIST'S OWN KEYS.** `ServiceRequestsListPage`
   * renders `customers.serviceRequest.channel.<code>` and
   * `customers.serviceRequest.waitingOn.<code>`, each with the raw value as its
   * `defaultValue`. A second spelling of *Walk-in* two clicks from the first is
   * how a status word starts reading one way on a list and another on a record,
   * so this asserts the RESOLVED catalogue string rather than a literal.
   */
  it("the head draws FOUR chips — state, waiting on, channel, received (p082)", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    // ⚠ **THE CHANNEL IS DRAWN TWICE AND THAT IS THE DRAWING, NOT A BUG.** p082
    // puts it in the head's chip row (`Counter`) and p083 puts it inside
    // `WHO IS ASKING` as `Channel`. So this asserts the HEAD's one by its own
    // attribute rather than by a page-wide text query, which finds two.
    expect(
      screen.getAllByText(
        i18n.t("customers.serviceRequest.channel.walk_in", { defaultValue: "walk_in" }),
      ).length,
    ).toBeGreaterThan(0);
    expect(document.querySelector('[data-channel="walk_in"]')).not.toBeNull();
    expect(screen.getByText(/Received/)).toBeInTheDocument();
    expect(document.querySelector('[data-waiting-on="documents"]')).not.toBeNull();

    // ⚠ **THE WAITING-ON CHIP WAS MISSING FROM THIS SCREEN ENTIRELY UNTIL
    // 2026-09-19**, while being the column the register leads on — p082 draws
    // `Submitted` and `Waiting on documents` side by side precisely to show
    // they are two different facts. This is the assertion that keeps it here.
    const waiting = document.querySelector('[data-head-chip="waiting-on"]');
    expect(waiting, "the waiting-on chip is not drawn").not.toBeNull();

    // All four carry a BACKGROUND, which is what makes them chips rather than
    // the grey text three of them used to be.
    for (const name of ["waiting-on", "channel", "received"]) {
      const chip = document.querySelector(`[data-head-chip="${name}"]`);
      expect(chip, `${name} is not a chip`).not.toBeNull();
      expect(
        chip?.className.includes("bg-"),
        `the ${name} chip carries no background utility — it is plain text again`,
      ).toBe(true);
    }
  });

  /**
   * The mirror of the case above, and the one that stops a tidy-up going too
   * far: the number is no longer in the roll-up because it moved to the kicker,
   * and it must still be somewhere a clerk can read it out.
   */
  it("the number a clerk quotes is still on the screen, exactly once", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getAllByText(/SR-26-0071/)).toHaveLength(1);
  });

  /**
   * ⚠ **THE HOLD THIS FILE WROTE ON 2026-09-13 HAS EXPIRED, AND THIS IS THE
   * TEST THAT FIRES.** Its own lifecycle note read: *"the drawn TWO-COLUMN body
   * (Documents · Fees · History beside the applicant's facts) is NOT asserted
   * here because it is NOT BUILT … Reported in the lane report for a PO ruling
   * rather than decided by a test."* The PO ruled on 2026-09-15 and it is
   * built. A hold with no test that fires when it expires is a promise nobody
   * is keeping (hard-won law 2's mirror).
   */
  it("the body is THREE drawn sections and a Fees-only rail", async () => {
    // ⚠ **THIS CASE NAMED SIX PANELS UNTIL 2026-09-19 AND NOW NAMES FOUR, ON A
    // PO RULING RATHER THAN A REGRESSION.** The blueprint puts `DOCUMENTS · N`
    // and `HISTORY` in this tab's right rail (p082–p083). The PO ruled both
    // off it — *"we should have these detials in document tab"* and *"all
    // histroy details on appplicant tab should move to history"* — and a PO
    // instruction supersedes a drawing.
    mount();
    await screen.findByRole("heading", { level: 1 });
    for (const panel of ["what-they-asked-for", "who-is-asking", "the-address-they-gave", "fees"]) {
      expect(document.querySelector(`[data-panel-name="${panel}"]`)).not.toBeNull();
    }
    // The two the ruling removed, asserted ABSENT so a lane "correcting" the
    // rail back to the drawing goes red here and reads why.
    for (const gone of ["documents-summary", "history-summary"]) {
      expect(document.querySelector(`[data-panel-name="${gone}"]`)).toBeNull();
    }
    expect(document.querySelector('[data-tab-body="applicant"]')).not.toBeNull();
    // ⚠ **AND THE LEFT COLUMN IS THE DRAWN DEFINITION LIST, NOT A STACK OF
    // CARDS** — PO, verbatim: *"label left, value right, a hairline between
    // rows, no box"*. Asserted on the row element, because "no box" is a claim
    // about structure that a screenshot proves and a class name does not.
    expect(document.querySelectorAll("[data-drawn-row]").length).toBeGreaterThan(5);
  });

  /**
   * RED at this lane's starting tip (`ce2fc2f6`): the head drew `Save & exit`,
   * `Park` and a primary reading `Decide what this is →`, and there was no
   * `Refuse`, no `Ask for more` and no `Approve` on it at all — the decisions
   * lived two clicks away on a Decision tab. PO ruling 2026-09-15: the head
   * carries the three decisions as MODALS, `Park` stays, and the other two
   * controls are removed.
   */
  // ⚠ **FIVE SINCE 2026-09-20, AND THE FIFTH IS `Submit`** — PO ratification
  // of that day, decision log section 1. The four below are still the drawing's
  // and still in its order; `Submit` is the DRAFT's only lawful action and
  // stands disabled here, over a submitted request, per BR-SHL-025. The action
  // bar's full state table is `ServiceRequestActionBar.dom.test.tsx`.
  it("the head carries FIVE buttons — Submit, Refuse, Ask for more, Park, Approve", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    for (const action of ["submit", "refuse", "request_info", "park", "approve"]) {
      expect(document.querySelector(`[data-decision-action="${action}"]`)).not.toBeNull();
    }
    // B14 rule 6 — refusing an application is a destructive commit.
    expect(
      document.querySelector('[data-decision-action="refuse"]')?.getAttribute("data-variant"),
    ).toBe("danger");
    // …and the two the ruling REMOVED are gone.
    expect(
      screen.queryByText(i18n.t("customers.serviceRequest.action.saveAndExit")),
    ).toBeNull();
    expect(
      screen.queryByText(i18n.t("customers.serviceRequest.action.decideWhatThisIs")),
    ).toBeNull();
  });

  /**
   * The mirror of the case above: a head button that opens nothing is dead UI,
   * and a head button that opens a dialog nobody wired is worse. Pressing
   * `Refuse` must actually put the drawn dialog on the screen.
   */
  it("pressing Refuse opens the drawn dialog, with its five reasons", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    const button = document.querySelector('[data-decision-action="refuse"]');
    expect(button).not.toBeNull();
    fireEvent.click(button as Element);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByText(i18n.t("customers.serviceRequest.refuseReason.not_our_service_area")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(i18n.t("customers.serviceRequest.refuse.tellThemHelp")),
    ).toBeInTheDocument();
  });

  it("pressing Approve opens the drawn dialog, with nothing preselected", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    fireEvent.click(document.querySelector('[data-decision-action="approve"]') as Element);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    // ⚠ **TWO SINCE 2026-09-22** — PO, *"Option (b) — remove all three
    // permanently"*. `BR-CUS-091` is amended to SUPERSEDED-IN-PART and the
    // decision log of that date names where a move-out, a transfer and a
    // disconnect each start now.
    // ⚠ **THE KIT'S SEGMENTED CONTROL SINCE 2026-09-23 (`DEF-CUS-6350`)** —
    // a `radiogroup` of `radio` buttons, B14 rules 36/38. Nothing checked.
    const radios = document.querySelectorAll('[data-outcome-picker] [role="radio"]');
    expect(radios).toHaveLength(2);
    for (const radio of radios) {
      expect(radio).toHaveAttribute("aria-checked", "false");
    }
  });

  it("pressing Ask for more opens the drawn dialog, with its four ticks", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    fireEvent.click(document.querySelector('[data-decision-action="request_info"]') as Element);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(document.querySelectorAll('[data-section="what-is-needed"] input[type="checkbox"]'))
      .toHaveLength(4);
  });

  /**
   * ⚠ **THE TAB STRIP IS THE DRAWING'S THREE.** Whether it is three or six is
   * open with the PO, so nothing was deleted to get here — every door the other
   * three carried moved onto the block the drawing puts its content in. This
   * asserts the STRIP, which is the half the drawing settles.
   */
  it("the tab strip is Applicant · Documents · History", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    const tabs = [...document.querySelectorAll(".page-header-tabs button, .page-header-tabs a")];
    expect(tabs.map((tab) => tab.textContent?.trim())).toEqual([
      i18n.t("customers.serviceRequest.tab.applicant"),
      i18n.t("customers.serviceRequest.tab.documents"),
      i18n.t("customers.serviceRequest.tab.history"),
    ]);
  });

  /**
   * ⚠ **THE HALF THE UNIT TEST CANNOT SEE.** `Disclosure` UNMOUNTS its body
   * when closed, so `renderToStaticMarkup` proves nothing about what is inside
   * it — a check that cannot see its own subject. `OQ-357`'s refusal (*a fee
   * line cannot be deleted; waive it instead*) and the connection quote's own
   * absence both live there, and this is where they are checked: by opening it.
   */
  it("opening the fee derivation shows the waive, the refusal and the quote's absence", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    const toggle = screen.getByRole("button", {
      name: new RegExp(i18n.t("customers.serviceRequest.fees.applicationFees")),
    });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByText(i18n.t("customers.serviceRequest.fees.quoteNotRaised")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(i18n.t("customers.serviceRequest.fees.quoteRaisedAfterReview")),
    ).toBeInTheDocument();
    expect(document.querySelector('[data-posts-to-ledger="false"]')).not.toBeNull();
  });

  /**
   * `DEF-CUS-5386` at the page level, read off the RENDERED DOM rather than off
   * a component's markup — which is the only way this class of defect is ever
   * found (hard-won law 6).
   */
  it("no database id is the visible value of any field on the page", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    // The number and the match word share one element (`P-00074 · exact`), so
    // the matcher is a pattern rather than an exact string.
    expect(screen.getByText(/P-00074/)).toBeInTheDocument();
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("01a0a444-5ad2-7e88-be8a-bdb8aa86c05e");
    expect(internalReferencesIn(document.body)).toEqual([]);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-5427` — WHAT THE CLERK IS TOLD BEFORE THEY PRESS, AND WHAT ONE
// PRESS ACTUALLY SENDS
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **EVERY CASE HERE WAS PROVED RED AT `fa61e2a8` — THIS LANE'S STARTING TIP —
// THROUGH `npx vitest run`, THE HARNESS THAT RUNS THEM.** What each one found
// there is quoted on the case.
//
// ⚠ **AND THE FIXTURE CARRIES NO STORED OUTCOME, WHICH IS THE WHOLE POINT.**
// `DEF-CUS-5425` and `DEF-CUS-5427` are the two halves of one blind spot: every
// case that existed mounted this dialog on a request that had ALREADY been
// decided, so `approve_blocked_by` arrived without `outcome` on it and the two
// states that actually break — *nothing picked yet* and *just picked* — could
// not appear. `commit.outcome` is `null` below and `approve_blocked_by` is
// `["outcome"]`, which is what the server really answers for a request a clerk
// has just opened.
describe("DEF-CUS-5427 · the Approve dialog warns BEFORE the press, per outcome", () => {
  // ⚠ ITS OWN `cleanup`. The one above is scoped to the other describe, and
  // without this the second case renders a second page into the same document
  // and every `findByRole` fails on *"Found multiple elements"* — a red that
  // looks like the defect and is the harness (hard-won law 7, *looking at the
  // wrong thing*). Both of these cases failed that way before it was added.
  afterEach(cleanup);

  /** `service_request.conditions_summary`, as the server serves it per option. */
  function conditions(
    blocking: string[],
    outstanding: { key: string; message_key: string; params: Record<string, unknown> }[] = [],
  ) {
    return {
      clear: 4 - blocking.length - outstanding.length,
      total: 4,
      blocking,
      outstanding: outstanding.map((row) => row.key),
      conditions: [
        // The server always sends the blocked arrears row WITH its key; a
        // fixture row with `null` there is a shape the server never produces.
        ...blocking.map((key) => ({
          key,
          state: "blocked",
          blocking: true,
          message_key: "customers.serviceRequest.condition.arrearsNotSearched",
          params: {},
        })),
        ...outstanding.map((row) => ({
          key: row.key,
          state: "blocked",
          blocking: false,
          message_key: row.message_key,
          params: row.params,
        })),
      ],
    };
  }

  function option(outcome: string, conds: ReturnType<typeof conditions>) {
    return {
      outcome,
      known: true,
      creates: {
        kind: outcome,
        table: null,
        module: "customers",
        queue: `${outcome}s`,
        state_it_lands_in: null,
        raises_a_row: true,
        absence: null,
        blockers: [],
      },
      carries: null,
      rows: [{ then: "now", what: "request_becomes_approved_and_recorded_against_you" }],
      not_now: ["no_account_opens"],
      conditions: conds,
    };
  }

  /** The state the clerk walk actually found: nothing decided, every condition
   *  clear *for the stored outcome*, and `move_in` about to refuse. */
  const PENDING = {
    ...DETAIL,
    actions: { ...DETAIL.actions, can_approve: false, approve_blocked_by: ["outcome"] },
    decision: {
      ...DETAIL.decision,
      what_approving_will_do: {
        // ⚠ **THE ARREARS BLOCKER MOVED HERE ON 2026-09-22, AND THE FIXTURE IS
        //     WHAT HAD TO MOVE RATHER THAN THE CASE.** It sat on `transfer`,
        //     which the Approve modal no longer offers (PO: *"Option (b) —
        //     remove all three permanently"*), so the case below picked a radio
        //     that is not on the screen and failed on a missing element instead
        //     of on the behaviour it watches. The blocker is per-OUTCOME on the
        //     server and any outcome can carry it; `new_connection` is one the
        //     modal still draws, and an applicant in arrears asking for a new
        //     connection is a real case rather than a contrived one.
        new_connection: option("new_connection", conditions(["no_blocking_arrears"])),
        move_in: option(
          "move_in",
          conditions([], [
            {
              key: "documents_verified",
              message_key: "customers.serviceRequest.condition.requiredDocumentMissing",
              params: { count: 2, doc_types: "proof_of_identity,signed_service_agreement" },
            },
          ]),
        ),
        move_out: option("move_out", conditions([])),
        transfer: option("transfer", conditions(["no_blocking_arrears"])),
        disconnect: option("disconnect", conditions([])),
      },
    },
  };

  const posts: { url: string; body: unknown }[] = [];

  function mountPending(): void {
    posts.length = 0;
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if ((init?.method ?? "GET") !== "GET") {
          posts.push({ url, body: JSON.parse(String(init?.body ?? "{}")) });
          return new Response(JSON.stringify({ ...PENDING, job: { not_raised: { code: "x" } } }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.includes("/interruption")) {
          return new Response(JSON.stringify({ detail: "not found" }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify(PENDING), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[`/brazosbend/requests/${REQUEST_ID}`]}>
          <Routes>
            <Route
              path="/:tenant/requests/:requestId"
              element={<ServiceRequestDetailPage client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  async function openApprove(): Promise<void> {
    mountPending();
    await screen.findByRole("heading", { level: 1 });
    fireEvent.click(document.querySelector('[data-decision-action="approve"]') as Element);
    await screen.findByRole("dialog");
  }

  function pick(outcome: string): void {
    fireEvent.click(document.querySelector(`[data-segment="${outcome}"]`) as Element);
  }

  // The fixture's options carry no per-kind `window`, so the button reads the
  // kit window's own default word.
  function submit(): HTMLButtonElement {
    // Inside the DIALOG: the page head carries its own `Approve`, which opens it.
    return within(screen.getByRole("dialog")).getByRole("button", {
      name: i18n.t("customers.serviceRequest.approveChecks.submit.none"),
    }) as HTMLButtonElement;
  }

  it("with nothing picked the commit is refused, in words", async () => {
    await openApprove();
    expect(submit()).toBeDisabled();
    expect(document.querySelector("[data-commit-blocked]")?.textContent).toContain(
      i18n.t("customers.serviceRequest.approveChecks.pickFirst"),
    );
  });

  it("picking an outcome whose documents are outstanding LEAVES THE COMMIT LIVE and says what is still needed", async () => {
    // ⚠ RED AT `fa61e2a8` on the SECOND half: the commit went live, correctly
    // under the 2026-09-16 ruling, and the dialog said NOTHING about the two
    // documents — `[data-documents-outstanding]` did not exist. *"Not mandatory
    // is not the same as not mentioned."*
    // ⚠ **SINCE 2026-09-23 IT IS A ROW, AMBER — `!` noted, not blocking** —
    // in the kit's `CheckList`, and the build's *"The build will ask for
    // them"* is gone from a move-in (`DEF-CUS-6352`).
    await openApprove();
    pick("move_in");
    expect(submit()).not.toBeDisabled();
    const notice = document.querySelector('[data-check="documents_verified"]');
    expect(notice).not.toBeNull();
    expect(notice).toHaveAttribute("data-check-state", "noted");
    expect(notice?.textContent).toContain(
      i18n.t("customers.serviceRequest.checkFact.requiredDocumentMissing", { count: 2 }),
    );
    expect(document.body.textContent).not.toContain(
      i18n.t("customers.serviceRequest.approve.documentsAsked"),
    );
    // Rule 32 — the doc-type codes travel in the payload and never to the screen.
    expect(document.body.textContent).not.toContain("proof_of_identity");
    expect(internalReferencesIn(document.body)).toEqual([]);
  });

  it("picking an outcome that a REAL blocker stands against refuses the commit before the press", async () => {
    // ⚠ RED AT `fa61e2a8`: `approve_blocked_by` is the REQUEST's list and does
    // not move with the radio, so this came back enabled — which is exactly how
    // the walk's press saved an outcome and was then refused.
    // ⚠ **THE OUTCOME PICKED HERE CHANGED ON 2026-09-22.** It picked
    // `transfer`, which the modal no longer offers, so the pick found no
    // control at all and the case failed on a missing element rather than on
    // the behaviour it exists to watch. The blocker moved to `new_connection`
    // in the fixture above — what this case is about is that the commit
    // refuses BEFORE the press, not which radio was pressed.
    await openApprove();
    pick("new_connection");
    expect(submit()).toBeDisabled();
    expect(document.querySelector("[data-commit-blocked]")?.textContent).toContain(
      i18n.t("customers.serviceRequest.check.no_blocking_arrears"),
    );
    // …and the row that holds it is ✗, named — the PO's *"we are not showing
    // all this issues to user when they are processing"*.
    expect(document.querySelector('[data-check="no_blocking_arrears"]')).toHaveAttribute(
      "data-check-state",
      "bad",
    );
  });

  it("one press sends ONE post, carrying the outcome, and no separate decision post", async () => {
    // ⚠ RED AT `fa61e2a8`: TWO posts — `/decision` then `/approve` — which is
    // the defect itself. When the second failed the first had already written
    // `service_requests.outcome`.
    await openApprove();
    pick("move_in");
    fireEvent.click(submit());
    // Wait on the POST itself rather than on the page re-rendering: what this
    // case is about is what left the browser.
    await waitFor(() => expect(posts.length).toBeGreaterThan(0));
    expect(posts.filter((one) => one.url.includes("/decision"))).toHaveLength(0);
    const approves = posts.filter((one) => one.url.includes("/approve"));
    expect(approves).toHaveLength(1);
    expect(approves[0]?.body).toMatchObject({ outcome: "move_in" });
  });
});


/**
 * ⚠⚠⚠ **THE GUARD FOR THE BUTTON THAT WOULD HAVE BROKEN EVERY APPROVAL IN THE
 * PRODUCT, AND THERE WAS NO SUCH GUARD UNTIL NOW.**
 *
 * `Record that I searched` is the **only** control anywhere that sets
 * `search_done`, and `arrears_condition(search_done=False, …)` returns
 * `CONDITION_BLOCKED` with `blocking=True`. It used to sit in the Applicant
 * tab's Customer match card. The 2026-09-19 rebuild deletes that card — the
 * drawing has no such block — and deleting the button with it would have
 * **refused the Approve press on every request in the product, silently, with
 * `tsc` and every suite green**, because no test asserts that a request can be
 * approved at all.
 *
 * ⚠ **A DOCSTRING SAYING THIS CASE EXISTED WAS WRITTEN BEFORE THE CASE WAS.**
 * `serviceRequestDecisions.tsx` carried *"`ServiceRequestDetailPage.dom.test.tsx`
 * has a case that goes RED if it stops"* over a file with no such case in it —
 * hard-won law 1, exactly: *a comment claiming a guarantee is not the
 * guarantee*. This is the guarantee.
 *
 * **It asserts the WHOLE CHAIN and not the button**, because each link alone
 * can be true while the door is shut:
 *
 *   1. the condition is offered — the dialog finds the blocking arrears row BY
 *      ITS `message_key`, so renaming the key without moving this goes red;
 *   2. the control is drawn beside it;
 *   3. pressing it **POSTs to `customer-link`**, which is the write that sets
 *      `search_done`. A button that renders and calls nothing is dead UI, and
 *      that is what a check asserting only step 2 would pass over.
 */
describe("the arrears search — the one door that lets any request be approved", () => {
  afterEach(cleanup);

  /** A request whose ONLY blocker is *nobody has searched for this customer*.
   *  That is the live shape: a genuine first-time applicant. */
  const UNSEARCHED = {
    ...DETAIL,
    actions: { ...DETAIL.actions, can_approve: false, approve_blocked_by: ["no_blocking_arrears"] },
    decision: {
      ...DETAIL.decision,
      what_approving_will_do: {
        new_connection: {
          outcome: "new_connection",
          known: true,
          creates: {
            kind: "new_connection",
            table: null,
            module: "customers",
            queue: "new_connections",
            state_it_lands_in: null,
            raises_a_row: true,
            absence: null,
            blockers: [],
          },
          carries: null,
          rows: [{ then: "now", what: "request_becomes_approved_and_recorded_against_you" }],
          not_now: ["no_account_opens"],
          conditions: {
            clear: 3,
            total: 4,
            blocking: ["no_blocking_arrears"],
            outstanding: [],
            conditions: [
              {
                key: "no_blocking_arrears",
                state: "blocked",
                blocking: true,
                // ⚠ **THE SERVER'S OWN KEY, WHICH IS WHAT THE DIALOG MATCHES
                // ON.** Matching on the tier or on `customer_id === null` would
                // be a second copy of the rule — `DEF-CUS-5874`'s shape.
                message_key: "customers.serviceRequest.condition.arrearsNotSearched",
                params: {},
              },
            ],
          },
        },
      },
    },
  };

  const posts: { url: string; body: unknown }[] = [];

  function mountUnsearched(): void {
    posts.length = 0;
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if ((init?.method ?? "GET") !== "GET") {
          posts.push({ url, body: JSON.parse(String(init?.body ?? "{}")) });
          return new Response(JSON.stringify(UNSEARCHED), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.includes("/interruption")) {
          return new Response(JSON.stringify({ detail: "not found" }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.includes("/customer-search")) {
          return new Response(JSON.stringify({ result: "new", count: 0, customers: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify(UNSEARCHED), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[`/brazosbend/requests/${REQUEST_ID}`]}>
          <Routes>
            <Route
              path="/:tenant/requests/:requestId"
              element={<ServiceRequestDetailPage client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("the Approve dialog offers the search, and No match after it WRITES", async () => {
    mountUnsearched();
    await screen.findByRole("heading", { level: 1 });
    fireEvent.click(document.querySelector('[data-decision-action="approve"]') as Element);
    await screen.findByRole("dialog");
    fireEvent.click(document.querySelector('[data-segment="new_connection"]') as Element);

    // ⚠ **THE DOOR IS ASSERTED FIRST, AND WITH A SENTENCE A READER CAN ACT
    // ON.** Both ways of breaking this chain — the page not passing the
    // handler, and the dialog not drawing the section — take the SERVER's
    // condition sentence down with them, so a case that looked for the
    // sentence first reported *"Unable to find an element with the text: Nobody
    // has checked yet whether…"* for both. True, and it names neither cause.
    // A check whose output cannot tell a reader which link broke is the shape
    // hard-won law 7 warns about, found by breaking this guard both ways.
    // PO 2026-10-11, option B: the Arrears row POINTS at *Search customer*,
    // and *No match* appears there once a search answers.
    await waitFor(
      () => {
        expect(
          document.querySelector("[data-customer-search]"),
          "the customer search is not in the Approve dialog — with it gone NO request in the product can be approved (see ARREARS_NOT_SEARCHED)",
        ).not.toBeNull();
      },
      { timeout: 3000 },
    );
    expect(document.querySelector("[data-approve-arrears-search]")).not.toBeNull();
    expect(document.querySelector('[data-action="record-search"]')).toBeNull();
    fireEvent.click(document.querySelector("[data-customer-search]") as Element);
    const button = await waitFor(() => {
      const node = document.querySelector('[data-action="record-search"]');
      if (node === null) throw new Error("No match is not offered after the search answered");
      return node;
    });

    // …and the SERVER's own sentence is what explains it, never a second copy
    // of the rule written on this screen.
    // ⚠ Since 2026-09-23 the row says it in six words or fewer (B14 rule 33);
    // the full sentence is the refusal's, and the row is keyed by the SAME
    // server `message_key`.
    expect(
      within(screen.getByRole("dialog")).getByText(
        i18n.t("customers.serviceRequest.checkFact.arrearsNotSearched"),
      ),
    ).toBeInTheDocument();

    // 3 · and it WRITES. `customer_id: null` is a real answer — *searched, and
    //     there is no prior customer* — which is what clears the condition for
    //     a genuine first-time applicant.
    fireEvent.click(button as Element);
    await waitFor(() => expect(posts.length).toBeGreaterThan(0));
    expect(posts[0].url).toContain("/customer-link");
    expect(posts[0].body).toEqual({ customer_id: null });
  });

  it("the deleted Customer match card is NOT where the search lives any more", async () => {
    // The other half of the move: the Applicant tab must not carry it, or two
    // controls write one fact and the next lane deletes the wrong one.
    mountUnsearched();
    await screen.findByRole("heading", { level: 1 });
    expect(document.querySelector('[data-panel-name="customer-match"]')).toBeNull();
    expect(
      screen.queryByText(i18n.t("customers.serviceRequest.match.noMatch")),
    ).toBeNull();
  });
});

/**
 * ⛔ **`DEF-CUS-6096` — THE WAIVE THAT WAS A SILENT 500, BOTH HALVES.**
 *
 * PO ruling 2026-09-21: *"waiving is options and can you fix the issue here"*.
 *
 * Two independent faults were stacked, which is why it survived a whole walk:
 * the screen sent the LINE NUMBER where the endpoint wanted the row's ID, and
 * the mutation that carried it had **no error branch at all**, so the server's
 * four refusals reached nobody.
 *
 * ⚠ **THIS IS A DOM CASE AND IT HAS TO BE.** The fee lines live inside a
 * `Disclosure`, which UNMOUNTS its body when closed, so a markup assertion
 * cannot see the waive at all — a check that cannot see its own subject.
 */
describe("DEF-CUS-6096 · the waive addresses the row, and its failure is audible", () => {
  // ⚠ Without this, the second case in this block renders a SECOND page into
  // the same document and every query matches twice — which reads as a
  // product fault and is a harness one. Every other block in this file carries
  // the same line for the same reason.
  afterEach(cleanup);

  const FEE_ID = "0199a1d2-7c4e-7a10-9f31-2b6c5d4e8a01";

  const WITH_FEE = {
    ...DETAIL,
    fees: {
      ...DETAIL.fees,
      lines: [
        {
          // ⚠ Deliberately a shape no LINE NUMBER could ever be, so this
          // fixture cannot make an unaddressable waive look addressable.
          id: FEE_ID,
          line_no: 1,
          charge_code: "CC-REQFEE",
          description: "Application fee",
          basis: "per request",
          quantity: "1",
          unit_amount: { amount: "20.0000", display: "20.00", currency: "USD" },
          amount: { amount: "20.0000", display: "20.00", currency: "USD" },
          waived: false,
          waive_reason: null,
          settled_at: null,
          invoice_ref: null,
        },
      ],
      outstanding_lines: 1,
      quoted: { amount: "20.0000", display: "20.00", currency: "USD" },
      settled: { amount: "0.0000", display: "0.00", currency: "USD" },
      collected: { amount: "0.0000", display: "0.00", currency: "USD" },
      outstanding: { amount: "20.0000", display: "20.00", currency: "USD" },
      shortfall_is_open_balance: true,
    },
  };

  const posts: string[] = [];
  /** What each non-GET actually SENT — the url alone cannot show the reason. */
  const bodies: unknown[] = [];

  /** `refuse` decides what the POST answers with; GET always serves the fee. */
  function mountWithFee(refuse: { status: number; body: unknown } | null): void {
    posts.length = 0;
    bodies.length = 0;
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if ((init?.method ?? "GET") !== "GET") {
          posts.push(url);
          bodies.push(typeof init?.body === "string" ? JSON.parse(init.body) : null);
          if (refuse !== null) {
            return new Response(JSON.stringify(refuse.body), {
              status: refuse.status,
              headers: { "Content-Type": "application/json" },
            });
          }
          return new Response(JSON.stringify(WITH_FEE.fees), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.includes("/interruption")) {
          return new Response(JSON.stringify({ detail: "not found" }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          });
        }
        // ⚠ **THE TENANT'S OWN REASONS — PO ruling 2026-09-22.** The waive now
        // goes through the handover modal and asks for one of these; a fixture
        // that served the request payload here too would hand the picker a
        // shape with no `reasons` on it, the list would come back empty, and
        // every case below would fail for a reason that is the FIXTURE's.
        if (url.includes("/payments/reason-codes")) {
          return new Response(
            JSON.stringify({ reasons: [{ code: "HARDSHIP", name: "Hardship" }], count: 1 }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(JSON.stringify(WITH_FEE), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[`/brazosbend/requests/${REQUEST_ID}`]}>
          <Routes>
            <Route
              path="/:tenant/requests/:requestId"
              element={<ServiceRequestDetailPage client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  /**
   * ⚠ **THE WAIVE IS TWO ACTS SINCE 2026-09-22 AND THE HELPER SAYS SO.**
   *
   * The per-line control used to POST on the spot with one hardcoded English
   * reason. PO ruling of that date: the handover modal offers `Taken` or
   * `Waived`, and a waive carries one of the TENANT's own reasons. So pressing
   * `Waive` now OPENS the modal with that line named, a reason is chosen, and
   * the commit is what posts. **Everything these cases were written to guard
   * is unchanged** — the address is the row's UUID and a refusal is read out
   * loud — and the helper walks the new path to the same POST.
   */
  async function pressWaive(): Promise<void> {
    await screen.findByRole("heading", { level: 1 });
    // ⚠ Located by `aria-expanded` INSIDE the fees panel rather than by its
    // words: the disclosure's title is a phrase the head's own copy repeats,
    // and a name-based query matched three buttons. A query that matches the
    // wrong control is law 7's *looking at the wrong thing*.
    const toggle = document.querySelector(
      '[data-panel-name="fees"] button[aria-expanded="false"]',
    ) as HTMLButtonElement;
    fireEvent.click(toggle);
    const waive = screen.getByRole("button", { name: i18n.t("customers.serviceRequest.fees.waive") });
    // DEF-CUS-9778: one glyph per verb — the waive draws the waive icon, as
    // the move-in's deposit row does, never the commit tick.
    expect(waive.querySelector('svg[data-icon="waive"]')).not.toBeNull();
    fireEvent.click(waive);
    // The modal opens ON `Waived`, with the line the clerk pointed at.
    await screen.findByRole("dialog");
    expect(document.querySelector('[data-handover-kind="waived"]')).not.toBeNull();
    const reason = document.querySelector("#reason") as HTMLSelectElement;
    await waitFor(() => expect(reason.querySelectorAll("option").length).toBeGreaterThan(1));
    fireEvent.change(reason, { target: { value: "HARDSHIP" } });
    fireEvent.click(
      screen.getByRole("button", {
        name: i18n.t("customers.serviceRequest.collect.submit.waived"),
      }),
    );
  }

  it("the waive posts the row's ID and never its line number", async () => {
    mountWithFee(null);
    await pressWaive();
    await waitFor(() => expect(posts.length).toBe(1));
    // ⚠ **`toContain` WOULD PASS ON THE BUG**: `"1"` is a substring of the
    // uuid, and it is a substring of the REQUEST id too. `DEF-CWP-3925`'s
    // shape. So the whole address is asserted.
    expect(posts[0]).toBe(`/api/brazosbend/service-requests/${REQUEST_ID}/fees/${FEE_ID}/waive`);
    expect(posts[0]).not.toContain("/fees/1/waive");
  });

  /**
   * ⚠ **EVERY WAIVE THIS PRODUCT EVER RECORDED CARRIED THE SAME SENTENCE.**
   * The per-line control posted `customers.serviceRequest.fees.defaultWaiveReason`
   * — *"Waived at the counter."* — on every press, so the stored reason was
   * worth nothing to whoever read it back. PO ruling 2026-09-22: the modal
   * asks, and the answers are the tenant's own live reasons from
   * `/payments/reason-codes` (`BR-TEN-036`).
   */
  it("the waive carries the TENANT's reason and never the hardcoded sentence", async () => {
    mountWithFee(null);
    await pressWaive();
    await waitFor(() => expect(bodies.length).toBe(1));
    expect(bodies[0]).toMatchObject({ reason: "HARDSHIP" });
    expect(JSON.stringify(bodies[0])).not.toContain(
      i18n.t("customers.serviceRequest.fees.defaultWaiveReason"),
    );
  });

  it("a refused waive is rendered to the clerk instead of vanishing", async () => {
    // The server's own refusal, in its own words — the screen writes none
    // (`BR-SHL-020` / the 2026-08-19 ruling).
    mountWithFee({
      status: 409,
      body: {
        code: "BIZ-STATE",
        message_key: "customers.serviceRequest.feeAlreadySettled",
        params: {},
      },
    });
    await pressWaive();
    // ⚠ **THE REFUSAL MOVED INTO THE DIALOG ON 2026-09-22, AND THAT IS THE
    // POINT RATHER THAN A SIDE EFFECT.** The waive used to post from the row,
    // so its refusal landed on the PAGE's action strip. It now posts from the
    // handover modal's commit, and `BR-SHL-025` puts a refusal beside the
    // thing it is about: a clerk who pressed a button in a dialog reads the
    // answer in that dialog, not behind it. **What this case guards is
    // unchanged** — the server's own sentence reaches a human — and it is
    // asserted where a human would now find it.
    const dialog = await screen.findByRole("dialog");
    const strip = within(dialog).getByRole("alert");
    expect(strip.textContent).toContain(
      i18n.t("customers.serviceRequest.feeAlreadySettled"),
    );
    // …and the dialog STAYS OPEN over a refused waive, so the reason the clerk
    // chose is not thrown away with it.
    expect(document.querySelector('[data-handover-kind="waived"]')).not.toBeNull();
  });

  it("even a refusal with no catalogue sentence says SOMETHING", async () => {
    // ⚠ **THE 500 ITSELF.** A crash carries no `message_key`, so there is no
    // sentence to render — and *"nothing to say"* must not collapse back into
    // *"say nothing"*, which is the defect. The client's own fallback copy is
    // what a clerk reads, and it is asserted here so the silence cannot return
    // through the one path that has no key of its own.
    mountWithFee({ status: 500, body: { detail: "boom" } });
    await pressWaive();
    const dialog = await screen.findByRole("dialog");
    const strip = within(dialog).getByRole("alert");
    expect((strip.textContent ?? "").trim().length).toBeGreaterThan(0);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// PO RULING 2026-09-22 · `Record what was handed over` OFFERS A WAIVE
// ══════════════════════════════════════════════════════════════════════════

describe("PO 2026-09-22 · the handover modal is Taken or Waived", () => {
  afterEach(cleanup);

  /**
   * PO, verbatim, with this modal open on `SR-26-0011`: *"on modal you ahve to
   * give Waive off button"*, then *"button or options"*. Two options at the
   * HEAD, because a waive has no amount, no tender and no receipt — a footer
   * button would leave three REQUIRED money fields on screen that a waive must
   * never fill, and a modal titled *what was handed over* cannot be submitted
   * by somebody stating that nothing was.
   *
   * ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7): a modal that drew the two
   * radios and went on asking for the money fields anyway would satisfy *there
   * is a waive option*. So the money fields are asserted ABSENT under
   * `Waived`, the reason picker PRESENT, and the reverse under `Taken`.
   */
  /**
   * The modal only offers `Waived` over a request with exactly ONE unwaived,
   * unsettled fee line, so the fixture has one. It is declared here rather
   * than borrowed from the waive block above, because that block's mount also
   * controls what the POST answers and these cases never post.
   */
  const FEE_ID = "0199a1d2-7c4e-7a10-9f31-2b6c5d4e8a02";
  const HANDOVER = {
    ...DETAIL,
    fees: {
      ...DETAIL.fees,
      lines: [
        {
          id: FEE_ID,
          line_no: 1,
          charge_code: "CC-REQFEE",
          description: "Application fee",
          basis: "per request",
          quantity: "1",
          unit_amount: { amount: "40.0000", display: "40.00", currency: "USD" },
          amount: { amount: "40.0000", display: "40.00", currency: "USD" },
          waived: false,
          waive_reason: null,
          settled_at: null,
          invoice_ref: null,
        },
      ],
      outstanding_lines: 1,
      quoted: { amount: "40.0000", display: "40.00", currency: "USD" },
      settled: { amount: "0.0000", display: "0.00", currency: "USD" },
      collected: { amount: "0.0000", display: "0.00", currency: "USD" },
      outstanding: { amount: "40.0000", display: "40.00", currency: "USD" },
      shortfall_is_open_balance: true,
    },
  };

  function openHandover(): void {
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/interruption")) {
          return new Response(JSON.stringify({ detail: "not found" }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url.includes("/payments/reason-codes")) {
          return new Response(
            JSON.stringify({ reasons: [{ code: "HARDSHIP", name: "Hardship" }], count: 1 }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(JSON.stringify(HANDOVER), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[`/brazosbend/requests/${REQUEST_ID}`]}>
          <Routes>
            <Route
              path="/:tenant/requests/:requestId"
              element={<ServiceRequestDetailPage client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("opens on Taken, with the three money fields and no reason", async () => {
    openHandover();
    await screen.findByRole("heading", { level: 1 });
    fireEvent.click(
      screen.getByRole("button", { name: i18n.t("customers.serviceRequest.fees.collect") }),
    );
    await screen.findByRole("dialog");
    expect(document.querySelector('[data-handover-kind="taken"]')).not.toBeNull();
    expect(document.querySelector("#amount")).not.toBeNull();
    expect(document.querySelector("#method")).not.toBeNull();
    expect(document.querySelector("#receipt_no")).not.toBeNull();
    expect(document.querySelector("#reason")).toBeNull();
  });

  it("picking Waived asks for a REASON and shows none of the money fields", async () => {
    openHandover();
    await screen.findByRole("heading", { level: 1 });
    fireEvent.click(
      screen.getByRole("button", { name: i18n.t("customers.serviceRequest.fees.collect") }),
    );
    await screen.findByRole("dialog");
    fireEvent.click(
      document.querySelector('[data-handover-option="waived"] input') as HTMLInputElement,
    );
    expect(document.querySelector('[data-handover-kind="waived"]')).not.toBeNull();
    expect(document.querySelector("#reason")).not.toBeNull();
    // The three a waive must never fill.
    expect(document.querySelector("#amount")).toBeNull();
    expect(document.querySelector("#method")).toBeNull();
    expect(document.querySelector("#receipt_no")).toBeNull();
    // …and the title moved with the choice.
    const dialog = screen.getByRole("dialog");
    expect(dialog.textContent).toContain(
      i18n.t("customers.serviceRequest.collect.title.waived"),
    );
  });

  it("the paragraph that told the clerk they may NOT write it off is gone", async () => {
    openHandover();
    await screen.findByRole("heading", { level: 1 });
    fireEvent.click(
      screen.getByRole("button", { name: i18n.t("customers.serviceRequest.fees.collect") }),
    );
    await screen.findByRole("dialog");
    // ⛔ The old sentence's two worst clauses, verbatim. *you do not write it
    // off here* is a policy the PO has reversed; *finance reconciles it* is
    // RATIONALE, which B14 rule 33 puts at ZERO words on screen.
    expect(document.body.textContent).not.toContain("you do not write it off here");
    expect(document.body.textContent).not.toContain("finance reconciles it");
    // ⚠ **`BR-CUS-090` IS NOT WEAKENED** — a shortfall is still an open
    // balance and still not a waiver, in two sentences of five and six words.
    expect(document.body.textContent).toContain(
      i18n.t("customers.serviceRequest.collect.shortfallIsFine"),
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-094-BRC01 lane F · accounts blueprint p82–83 (images, scale 2) ·
//   14-ui-conventions.md rules 21, 31, 32, 33, 36, 37, 40, 41
// generated: 2026-09-13 by the CR-094-BRC01 lane F build
// checklist: A✔ B✔ C✔ D=n/a(no endpoint changed) E✔ F✔ G✔ H=n/a
// gates: tsc · vitest this file · the page is on src/styles/route-b-migrated.txt
// exceptions: E3 ⚠ **THE 2026-09-13 HOLD IS RETIRED.** It read *"the drawn
//   TWO-COLUMN body … is NOT asserted here because it is NOT BUILT"*; the PO
//   ruled on 2026-09-15 and `CR-094-BRC01` wave 2 built it, so the hold-expiry
//   case *"the body is the drawing's SIX blocks in TWO columns"* is what fires
//   in its place · E3 whether the strip carries THREE tabs or SIX is open with
//   the PO; the strip is the drawing's three and no live door was deleted to
//   get there — see `REQUEST_TABS`
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

/**
 * `DEF-CWP-9163` — the portal applicant's *Mailing address, if different*
 * reaches the clerk. Watched FAIL on `2.455.0` (no such row) before the fix.
 */
describe("the request detail shows where a portal applicant asked for the bill to go", () => {
  afterEach(cleanup);

  it("draws the mailing address on one line, in the envelope's order", async () => {
    mount({
      ...DETAIL,
      applicant: {
        ...DETAIL.applicant,
        application_mailing_address: {
          line1: "PO Box 4417",
          line2: null,
          city: "Ottumwa",
          state: "IA",
          postal_code: "52501",
        },
      },
    });
    await screen.findByRole("heading", { level: 1 });
    const row = await waitFor(() => {
      const found = document.querySelector('[data-drawn-row="application-mailing-address"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(row).toHaveTextContent("Mailing address");
    expect(row).toHaveTextContent("PO Box 4417, Ottumwa, IA 52501");
  });

  it("draws no row when the bill goes to the service address", async () => {
    mount();
    await screen.findByRole("heading", { level: 1 });
    expect(document.querySelector('[data-drawn-row="application-mailing-address"]')).toBeNull();
  });
});

/**
 * `DEF-CUS-10705` — a request matched to ONE apartment of a building keeps the
 * apartment in the head. Walked on `SR-26-0011` (1408 Elm St Apt B), which read
 * `1408 Elm St · Austin, TX 78702`; the drawing puts the unit after the street
 * (p082 `212 Balcones Drive · Unit 3 · Austin, TX 78704`). Watched FAIL before
 * the fix on the first two cases.
 */
describe("DEF-CUS-10705 · the request head names the apartment a request is matched to", () => {
  afterEach(cleanup);

  const matched = (label: string | null, units: number) => ({
    ...DETAIL,
    header: {
      ...DETAIL.header,
      premise_locality: { city: "Austin", state: "TX", postal_code: "78702" },
    },
    location_and_services: {
      ...DETAIL.location_and_services,
      address_as_given: "1408 Elm St",
      address_unit_as_given: "Apt B",
      resolved_premise_address: "1408 Elm St",
      resolved_unit_id: "01a0a444-5ad2-7e88-be8a-bdb8aa86c0ff",
      resolved_unit_no: "U-00042",
      resolved_unit_label: label,
      resolved_premises_units: units,
    },
  });

  async function head(): Promise<HTMLElement> {
    await screen.findByRole("heading", { level: 1 });
    const found = document.querySelector("[data-head-address]");
    expect(found).not.toBeNull();
    return found as HTMLElement;
  }

  it("a unit at a three-unit building is drawn after the street", async () => {
    mount(matched("B", 3));
    expect(await head()).toHaveTextContent("1408 Elm St · Unit B · Austin, TX 78702");
  });

  it("a label that already names itself is drawn as stored", async () => {
    mount(matched("Apt 2B", 3));
    expect(await head()).toHaveTextContent("1408 Elm St · Apt 2B · Austin, TX 78702");
  });

  it("a house — one unit — draws no unit", async () => {
    mount(matched("Main", 1));
    expect(await head()).toHaveTextContent(/^1408 Elm St · Austin, TX 78702$/);
  });
});
