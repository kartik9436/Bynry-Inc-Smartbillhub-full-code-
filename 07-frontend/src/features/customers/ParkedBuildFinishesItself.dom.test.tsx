// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-6135 (parking a draft build and finishing it made a SECOND
//          build) · DEF-CUS-6132 (a clerk could not get back into a draft at
//          all: the row led to the property page or nowhere)
// Rules:   BR-SHL-048 (d), CONFIRMED-AS-AMENDED 2026-09-21 — PO verbatim:
//          *"this is big problem - we cannot create two build - you can update
//          the existing build"* · BR-SHL-048 (a) — a park carries COPIED
//          VALUES and no foreign key, which is the FIX here rather than the
//          obstacle · BR-SHL-048 (b) — a resumed draft is re-validated at
//          execution, never trusted from the park · BR-MET-112 — nothing is
//          written until the last button, and a New Connect started from
//          SCRATCH is untouched by any of this
// Process: 12-governance/22-product-maintenance-process.md §4 — *"write the
//          test that would have caught it, beside the code, in its module's
//          own suite"*
// ───────────────────────────────────────────────────────
//
// WHAT THE WALK SAW, WHICH IS WHAT THESE CASES ARE ABOUT
// ------------------------------------------------------
// Approving `SR-26-0002` raised `CON-26-0129` as a draft. A clerk opened its
// wizard, typed, parked it, came back from the New connects tab and pressed
// through — and the server answered `200` with **`CON-26-0132`**, a second
// build on the same property naming no application, while `CON-26-0129` sat
// there still a draft and still the one the application pointed at. One piece
// of work, three rows on the tab, one of them with a BLANK number.
//
// WHY EVERY CHECK PASSED OVER IT (law 7, habit 2 — the false pass, written out)
// ----------------------------------------------------------------------------
// * **The park was asserted and the RESUME was not.** `wizardPark.dom.test.tsx`
//   proves the typing comes back, and it does. The build id was parked
//   correctly and dropped by `hydrateForm` one line later, inside a callback no
//   case could reach without driving eight steps of a browser. `draftFromPark`
//   exists so that line is callable.
// * **`state=requested` on the id you already had cannot tell the two apart.**
//   A second build leaves the first one DRAFT, so the only honest verdict is
//   the ID the commit is sent. Asserting a COUNT is worse than useless here:
//   the walk's own first version counted `GET /connections`, which includes
//   parked wizards as rows, and announced *"a SECOND build was created"* over a
//   run in which nothing committed at all.
// * **A door asserted by NAME rather than by ADDRESS.** `rowDoor` is asserted
//   against the string a clerk's browser would go to.
import "@testing-library/jest-dom/vitest";
import { describe, expect, it } from "vitest";

import { rowDoor } from "./NewConnectsTab";
import {
  commitPlanOf,
  draftFromPark,
  draftFromRaisedBuild,
  emptyDraft,
  parkSubjectRefOf,
} from "./newConnectDraft";
import type { ConnectionDetail } from "./newConnectEndpoints";

const BUILD_ID = "01a0c23c-f5ac-75a7-9796-4a1c1283dc26";
const BUILD_NO = "CON-26-0129";
const PREMISES_ID = "01a0c888-9999-7aaa-8bbb-ccccddddeeee";
const PARK_ID = "01a0c42b-2a49-7e2d-a502-8d355925adfe";

/** `CON-26-0129`, as `GET /connections/{id}` serves it — the draft `SR-26-0002`
 *  raised, against a property that was already on file. */
const RAISED = {
  id: BUILD_ID,
  connection_no: BUILD_NO,
  state: "draft",
  premises: {
    id: PREMISES_ID,
    premise_no: "P-00057",
    name: null,
    address: "500 Main St",
  },
  prefill: {
    request_id: "01a0e111-2222-7333-8444-000011112222",
    request_no: "SR-26-0002",
    applicant_kind: "person",
    applicant_name: "Whitfield, Dana",
    applicant_email: "dana@example.com",
    applicant_phone: "(512) 555-1720",
    matched_customer_id: null,
    address_as_given: "500 Main St",
    address_unit_as_given: null,
    plot_or_parcel: null,
    property_type: "single_family",
    what_is_being_built: "A house",
    units_on_property: 1,
  },
  unit_summary: null,
  applicant: "Whitfield, Dana",
  request_no: "SR-26-0002",
  mode: "our_crew",
  started_at: null,
  target_activation: null,
  waiting_on: null,
  units: 0,
  orders: { done: 0, total: 0 },
  services: [],
  work_orders: [],
  unit_rows: [],
  assets: [],
  sub_meter_links: null,
  quote_total: { amount: null, display: null, currency: null },
  quote_settled_at: null,
  charges: null,
  deposit: null,
  outstanding: [],
  history: [],
  owner_account_no: null,
  unavailable: [],
} as unknown as ConnectionDetail;

/**
 * What `POST /wizard-parks` stores when a clerk presses `Park it` on that
 * wizard, as `GET /wizard-parks/{id}` hands it back.
 *
 * ⚠ **`subject_ref` COMES FROM THE PRODUCT'S OWN FUNCTION AND IS NOT BUILT
 * HERE.** A fixture that composed it would be asserting itself — law 7's
 * *structurally incapable of failing* — over one of the two halves this defect
 * was made of. `values` is the wizard's literal `{ draft }`.
 */
function parkOf(draft: ReturnType<typeof emptyDraft>) {
  return { subject_ref: parkSubjectRefOf(draft), values: { draft } };
}

describe("DEF-CUS-6135 · a parked wizard finishes the build it was working on", () => {
  // ════════════════════════════════════════════════════════════════════════
  // 1 · THE PARK CARRIES THE BUILD — clause (a) USED, not bent
  // ════════════════════════════════════════════════════════════════════════
  it("parks the build's id AND its number as copied values", () => {
    const parked = parkOf(draftFromRaisedBuild(emptyDraft(), RAISED));
    expect(parked.subject_ref).toEqual({
      connection_id: BUILD_ID,
      connection_no: BUILD_NO,
    });
  });

  it("a New Connect started from SCRATCH still parks nothing — BR-MET-112 unchanged", () => {
    expect(parkOf(emptyDraft()).subject_ref).toEqual({});
  });

  // ════════════════════════════════════════════════════════════════════════
  // 2 · THE RESUME PUTS IT BACK — this is the line that was broken
  // ════════════════════════════════════════════════════════════════════════
  it("the resumed draft still knows which build it is finishing", () => {
    const typed = { ...draftFromRaisedBuild(emptyDraft(), RAISED) };
    typed.owner = { ...typed.owner, name: "Brazos Bend Warehousing" };
    const resumed = draftFromPark(parkOf(typed));

    // ⛔ THE VERDICT, AND IT NEEDS NO DENOMINATOR: the same id means the draft
    // is finished, a different one means a second build stands beside it.
    expect(commitPlanOf(resumed, null, [], PARK_ID).connection_id).toBe(BUILD_ID);
    expect(resumed.connectionNo).toBe(BUILD_NO);
    // Provenance survives too, or step 1's *where this came from* line goes
    // blank and the clerk is told the build has no application.
    expect(resumed.requestNo).toBe("SR-26-0002");
    // And the typing, which is what the park panel promised all along.
    expect(resumed.owner.name).toBe("Brazos Bend Warehousing");
  });

  it("a draft parked BEFORE this fix still resumes onto its build", () => {
    // ⚠ These rows exist on a beta tenant right now: the id was already inside
    // `values.draft` and `subject_ref` was `{}`. Without the fallback read,
    // every one of them would still mint a second build the first time
    // somebody picked it up.
    const typed = draftFromRaisedBuild(emptyDraft(), RAISED);
    const oldShape = { subject_ref: {}, values: { draft: typed } };
    expect(draftFromPark(oldShape).connectionId).toBe(BUILD_ID);
  });

  it("a wizard started from scratch and parked still creates exactly ONE build", () => {
    const resumed = draftFromPark(parkOf(emptyDraft()));
    // `null` is *start a new one*, and that path is the ordinary case.
    expect(commitPlanOf(resumed, null, [], PARK_ID).connection_id).toBeNull();
  });

  // ════════════════════════════════════════════════════════════════════════
  // 3 · AND THE DRAFT THAT HELD THE TYPING IS SPENT
  // ════════════════════════════════════════════════════════════════════════
  it("the commit names the parked draft, so one piece of work leaves ONE row", () => {
    const resumed = draftFromPark(parkOf(draftFromRaisedBuild(emptyDraft(), RAISED)));
    expect(commitPlanOf(resumed, null, [], PARK_ID).wizard_park_id).toBe(PARK_ID);
  });

  it("a wizard that was never parked sends no draft to discard", () => {
    expect(commitPlanOf(emptyDraft(), null, []).wizard_park_id).toBeNull();
  });
});

describe("DEF-CUS-6132 · a clerk can get back into a draft build", () => {
  // The three kinds of row this tab draws, asserted BY ADDRESS.
  it("a DRAFT build opens its own wizard", () => {
    expect(
      rowDoor({ id: BUILD_ID, state: "draft", home: { kind: "premises", id: PREMISES_ID } }),
    ).toBe(`/connections/new?build=${BUILD_ID}`);
  });

  it("a draft whose address never resolved opens it too — it had NO link at all", () => {
    expect(rowDoor({ id: BUILD_ID, state: "draft", home: null })).toBe(
      `/connections/new?build=${BUILD_ID}`,
    );
  });

  it("a COMMITTED build opens ITS OWN page, whichever host it lives on", () => {
    // ⚠ `DEF-CUS-9107` — **SINCE `ab052ac04` (2026-09-28, `CR-151-BRC09` §6a,
    // the flip)** a committed build has a page of its own,
    // `/{tenant}/connections/{id}`, and the list opens it rather than its host
    // (`buildHomePath` still answers where a build LIVES, for the approval
    // queue and the dispatcher). The two hosts now give the SAME door.
    expect(
      rowDoor({ id: BUILD_ID, state: "requested", home: { kind: "premises", id: PREMISES_ID } }),
    ).toBe(`/connections/${BUILD_ID}`);
    expect(
      rowDoor({ id: BUILD_ID, state: "activated", home: { kind: "account", id: PREMISES_ID } }),
    ).toBe(`/connections/${BUILD_ID}`);
  });

  it("a PARKED wizard has no build to open, and says so by returning nothing", () => {
    // Its door is the `Resume` control in the state cell (`resumePath`), and a
    // link onto nothing passes every test in this repo — which is the fault
    // this whole change removes rather than moves.
    expect(rowDoor({ id: null as unknown as string, state: "parked", home: null })).toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: BR-SHL-048 (d) · 02-decision-log.md 2026-09-21 ("ONE PIECE OF WORK IS
//         ONE BUILD") · DEF-CUS-6135 · DEF-CUS-6132
// generated: 2026-09-21 by lane PARK-1
// proof: every case was shown RED against the tree at b1a45be60 before the fix
//         landed — the resume cases answered a FRESH uuid instead of BUILD_ID,
//         and the door cases answered `/premises/…?tab=build` and `null`.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
