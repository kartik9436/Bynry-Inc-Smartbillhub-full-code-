// ── Trace ──────────────────────────────────────────────
// Change:   The MOVE RECORD screen (blueprint p074), approved by the PO
//           2026-09-19; its action bar ruled the same day — TWO doors and no
//           action.
// Rules:    B14 rule 31 (no database id is ever a field's visible value) ·
//           rule 33 (rationale is ZERO words on screen) · hard-won law 2 and
//           its mirror · DEF-127 (an absence and an empty cell are
//           indistinguishable once drawn)
// ───────────────────────────────────────────────────────
/**
 * What this file holds the SCREEN to — the four things a browser walk cannot
 * re-check on every commit, and that no other check in the repo can see.
 *
 * **1 · AN ABSENCE RENDERED AS A BLANK.** The server distinguishes *"this has
 * not happened yet"* from *"the seam cannot answer"* from *"this unit holds no
 * meter"*. A screen that drew a dash for all three would throw that away at the
 * last step, and `tsc` cannot see it because every one of them is a valid
 * `MoveFact`. Asserted on the WORDS a person reads.
 *
 * **2 · THE PAGE GROWING AN ACTION.** The blueprint's ruling — *"This record
 * has no actions"* — is the kind of thing a later lane "improves". Asserted as
 * a count of controls, not as a subset, because a subset assertion passes while
 * a third button is added.
 *
 * **3 · A LINKING CONTROL APPEARING WHERE THERE IS NO CUSTOMER.** The PO's
 * ruling names the linking case and the coordinator's brief is explicit that
 * the flow is NOT this lane's. So the no-customer branch must say so and offer
 * nothing — the easiest thing in the world to add later by accident.
 *
 * **4 · RATIONALE LEAKING ONTO THE SCREEN.** The server's `detail` sentences
 * explain WHY a fact is missing; B14 rule 33 puts rationale at zero words on
 * screen. They ride in `title` — machine-reachable, not read aloud — so this
 * file borrows `MoveInsTab.test.tsx`'s `visibleText` helper, which exists
 * because the naive `html.includes(...)` was wrong twice in exactly this way.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { MoveRecordPage, moveRecordPath } from "./MoveRecordPage";
import type { MoveAbsence, MoveRecordDetail } from "./MoveRecordPage";
// ⚠ **THE ROUTE CONSTANTS, IMPORTED RATHER THAN RETYPED.** The resume
// assertions below check the built address against the SAME constants
// `App.tsx` mounts the two wizards at, so a test cannot go on passing while
// the page and the router disagree about where a wizard lives — the shape that
// let a hold-expiry test assert one address while the router used another.
import { MOVE_IN_WIZARD_ROUTE, MOVE_OUT_WIZARD_ROUTE } from "./moveShared";
// ⚠ **THE TAB SLUGS COME FROM `PARKED_HOME_PATHS`, THE MAP THAT ALREADY OWNS
// "which list does this flow live on".** Retyping `"?tab=move-outs"` here would
// be the second map the decision log warns about — *"that map is the single
// source; a second one is how two screens come to disagree"* (2026-09-20 §8).
// These are `AccountsListPage`'s own HYPHENATED ids, already held against
// `ACCOUNTS_TAB_IDS` by `parkedDrafts.dom.test.tsx`.
import { PARKED_HOME_PATHS } from "./wizardPark";

/** `/accounts?tab=move-ins` and `/accounts?tab=move-outs`, from the one map. */
const MOVE_INS_TAB = PARKED_HOME_PATHS.move_in.split("=")[1];
const MOVE_OUTS_TAB = PARKED_HOME_PATHS.move_out.split("=")[1];

/**
 * The rendered TEXT — every tag and attribute stripped, leaving only what a
 * person actually reads.
 *
 * ⚠ **THE SAME HELPER `MoveInsTab.test.tsx` CARRIES, AND FOR ITS REASON.** The
 * absence sentences ride in `title=`, so a raw `html.includes(...)` finds the
 * rationale inside the very attribute that keeps it off the screen — and the
 * assertion that rule 33 is obeyed would pass or fail for the wrong reason. A
 * test that cannot tell a string being SHOWN from a string being carried as
 * machine data is not testing the thing it names.
 */
function visibleText(html: string): string {
  return html.replace(/<[^>]*>/g, " ");
}

const ABSENT = (code: string, detail: string): MoveAbsence => ({
  code,
  br_ref: "BR-CUS-150",
  detail,
});

const NO_ACCOUNT = ABSENT(
  "move_has_not_opened_an_account_yet",
  "This move-in has not completed, so no account has been opened.",
);

function completed(over: Partial<MoveRecordDetail> = {}): MoveRecordDetail {
  return {
    state: "completed",
    kind: "move_in",
    move_no: "MVI-26-0114",
    title: "Miller, Sarah",
    address_line: "1408 Elm Street · Unit A",
    effective_on: "2026-05-02",
    what_happened: {
      account_opened: { value: "A-12051", unavailable: null },
      from_account: { value: "A-10432 · Okafor, D.", unavailable: null },
      unit: { value: "1408 Elm Street · Unit A", unavailable: null },
      moved_in_on: { value: "2026-05-02", unavailable: null },
      earliest_legal_start: { value: "2026-01-29", unavailable: null },
      // A MOVE-IN, so the server always sends the *not asked* absence here —
      // a move-in ends no tenancy. The screen draws the row on a move-out
      // only, which the case below asserts.
      close_reason: {
        value: null,
        unavailable: ABSENT("close_reason_was_not_asked", "closed before the screen asked."),
      },
      committed_by: {
        value: { name: "S. Ortiz", at: "2026-05-02T10:04:00Z" },
        unavailable: null,
      },
    },
    opening_reads: {
      rows: [
        {
          register: "M-4021 · Electric · total",
          reading: "41680",
          read_at: "2026-05-02",
          how: "read",
        },
        {
          register: "M-4021 · Electric · demand",
          reading: null,
          read_at: "2026-05-02",
          how: "not_estimated",
        },
      ],
      unavailable: null,
    },
    money_taken: {
      required: { value: "150.0000", unavailable: null },
      taken: { value: "150.0000", unavailable: null },
      still_to_collect: { value: "0.0000", unavailable: null },
      tender: {
        value: null,
        unavailable: ABSENT(
          "deposit_tender_not_readable_from_customers",
          "The tender lives on the payment row and payments publishes no read for it.",
        ),
      },
    },
    still_owed: {
      demand_register: {
        value: { count: 1, registers: ["M-4021 · Electric · demand"] },
        unavailable: null,
      },
      visit: {
        value: null,
        unavailable: ABSENT("visit_not_readable_from_customers", "work publishes no read."),
      },
      carry_forward: {
        value: null,
        unavailable: ABSENT(
          "carry_forward_mechanics_are_proposed",
          "no column records an election and no linkage exists to walk.",
        ),
      },
    },
    doors: {
      account: { value: { account_id: "acc-uuid-1", account_no: "A-12051" }, unavailable: null },
      customer: { value: { customer_id: "cus-uuid-1", name: "Miller, Sarah" }, unavailable: null },
    },
    chips: { unread_registers: 1, reads_committed: 2 },
    ...over,
  };
}

function inFlight(over: Partial<MoveRecordDetail> = {}): MoveRecordDetail {
  const base = completed();
  return {
    ...base,
    state: "in_flight",
    move_no: "MVI-26-0113",
    title: "MVI-26-0113",
    step: 3,
    // The parked draft's own id — the handle `resumePath()` needs. The server
    // serves this for an `in_flight` record and for no other (PO ruling
    // 2026-09-19).
    park_id: "park-uuid-77",
    what_happened: {
      account_opened: { value: null, unavailable: NO_ACCOUNT },
      from_account: { value: null, unavailable: NO_ACCOUNT },
      unit: { value: "1408 Elm · Unit C", unavailable: null },
      moved_in_on: {
        value: null,
        unavailable: ABSENT("move_in_date_not_chosen_yet", "asked for on step 3."),
      },
      earliest_legal_start: { value: null, unavailable: NO_ACCOUNT },
      // The reason is written by the COMMIT, so an in-flight draft carries the
      // same absence `committed_by` beside it does.
      close_reason: {
        value: null,
        unavailable: ABSENT("move_not_committed_yet", "written at the commit."),
      },
      committed_by: {
        value: null,
        unavailable: ABSENT("move_not_committed_yet", "written at the commit."),
      },
    },
    opening_reads: { rows: [], unavailable: NO_ACCOUNT },
    doors: {
      account: { value: null, unavailable: NO_ACCOUNT },
      customer: { value: null, unavailable: NO_ACCOUNT },
    },
    chips: { unread_registers: 0, reads_committed: 0 },
    ...over,
  };
}

/**
 * Render the page at its REAL address pattern.
 *
 * ⚠ **MOUNTED UNDER `/:tenant/moves/:ref`, NOT BARE** — hard-won law 2's
 * fixture clause, which cost the customer portal a whole front page of broken
 * links. A component mounted inside a `MemoryRouter` with no matching route
 * gets `undefined` for every param, so every address it builds comes out
 * `//moves/…` — a protocol-relative URL to another host that reads as a
 * perfectly good string to `toContain`. Mounting under the real pattern is the
 * only way the link assertions below mean anything.
 */
function render(detail: MoveRecordDetail): string {
  const client = {
    get: async () => ({ status: 200, data: detail }),
  } as never;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // ⚠ **THE CACHE IS SEEDED, BECAUSE `renderToStaticMarkup` IS SYNCHRONOUS.**
  // A `useQuery` cannot resolve inside one pass, so the first version of this
  // helper rendered the LOADING SKELETON and seven assertions failed against
  // `<div class="skeleton …">`. That is law 7's *incapable of passing* shape,
  // and it is worth the note: had the assertions been written loosely enough to
  // pass over a skeleton, this file would have tested nothing at all and looked
  // green doing it. Seeding the exact key the page reads is what makes the
  // rendered markup the thing under test.
  const ref = detail.move_no ?? "";
  qc.setQueryData(["move-record", ref], detail);
  return renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/brazosbend${moveRecordPath(detail.move_no ?? "")}`]}>
        <Routes>
          <Route
            path="/:tenant/moves/:ref"
            element={<MoveRecordPage client={client} timeZone="UTC" dateFormat="MM/DD/YYYY" />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * Render the NOT-FOUND state, at the real address pattern, for a reference the
 * server does not hold.
 *
 * ⚠ **`null` RATHER THAN A THROWN ERROR, AND IT MATTERS.**
 * `renderToStaticMarkup` is synchronous, so a rejecting `queryFn` renders the
 * LOADING skeleton and the case would assert nothing — law 7's *incapable of
 * passing* shape, wearing a green tick. Seeding `null` puts the query in
 * `success` with no data, which is exactly the `!query.data` arm the page
 * branches on.
 */
function renderNotFound(ref: string): string {
  const client = { get: async () => ({ status: 404, data: null }) } as never;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(["move-record", ref], null);
  return renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/brazosbend${moveRecordPath(ref)}`]}>
        <Routes>
          <Route
            path="/:tenant/moves/:ref"
            element={<MoveRecordPage client={client} timeZone="UTC" dateFormat="MM/DD/YYYY" />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the move record", () => {
  it("names its address for a reference and never for a uuid", () => {
    // B14 rule 31 — the URL a clerk copies is the NUMBER.
    expect(moveRecordPath("MVI-26-0114")).toBe("/moves/MVI-26-0114");
    expect(moveRecordPath("MVI-26-0114")).not.toContain("uuid");
  });

  it("puts the move under /moves and never under /accounts", () => {
    // The placement IS the design (p073: a move is a record OF an act), and it
    // is also the only placement that works for an in-flight move, which has
    // no account to hang off.
    expect(moveRecordPath("MVI-26-0113").startsWith("/moves/")).toBe(true);
    expect(moveRecordPath("MVI-26-0113")).not.toContain("/accounts/");
  });
});

describe("the no-customer branch", () => {
  it("states the absence and offers NO linking control", () => {
    // The PO: *"Open the customer - if requried otherwise we will ahev to link
    // to exisitng one"*. Linking is its own piece of work and is NOT this
    // lane's — measured on the sample estate, this is the ORDINARY case for a
    // move-in, so the branch a clerk meets first must say so and stop there.
    const detail = completed({
      doors: {
        account: {
          value: { account_id: "acc-uuid-1", account_no: "A-12051" },
          unavailable: null,
        },
        customer: {
          value: null,
          unavailable: ABSENT(
            "move_has_no_linked_customer",
            "No customer record is linked to the account this move opened.",
          ),
        },
      },
    });
    const html = render(detail);
    const text = visibleText(html);

    expect(html).toContain("move-record-no-customer");
    expect(text).toContain("No customer linked");
    // the door that DOES exist is still there
    expect(html).toContain("move-record-open-account");
    // and nothing offers to make the link
    expect(text.toLowerCase()).not.toContain("link a customer");
    expect(text.toLowerCase()).not.toContain("link to");
    expect(html).not.toContain("move-record-link-customer");
  });
});

describe("rule 33 — rationale is zero words on screen", () => {
  it("keeps every absence SENTENCE off the page and in the title", () => {
    const detail = completed();
    const html = render(detail);
    const text = visibleText(html);

    // the reason exists, reachable, as machine-readable data
    expect(html).toContain("payments publishes no read for it");
    // …and is NOT read aloud on the screen
    expect(text).not.toContain("payments publishes no read for it");
    expect(text).not.toContain("no column records an election");
  });

  it("never prints a rule id in clerk-facing copy", () => {
    // B14 rule 32 — no rule id or internal code in what a clerk reads.
    const text = visibleText(render(completed()));
    expect(text).not.toMatch(/BR-CUS-\d/);
    expect(text).not.toContain("move_has_no_linked_customer");
  });
});

describe("an in-flight move", () => {
  it("renders, and says WHY each missing fact is missing", () => {
    // Half of what p073 draws is a move still in progress, and every row has an
    // `↗ Open`. This is the case a page reading only `move_records` would 404
    // on — correctly, and uselessly.
    const text = visibleText(render(inFlight()));

    expect(text).toContain("In progress");
    expect(text).toContain("Not opened yet"); // the account
    expect(text).toContain("Not committed yet"); // committed by
    expect(text).toContain("Not chosen yet"); // the date
  });

  it("offers no door it cannot open", () => {
    // Hard-won law 2's mirror: a live screen behind a dead control. An
    // in-flight move has no account, so the account door must be ABSENT rather
    // than present-and-broken.
    const html = render(inFlight());
    expect(html).not.toContain("move-record-open-account");
    expect(html).not.toContain("move-record-open-customer");
  });
});

describe("the completed record", () => {
  it("draws the six facts, the reads and the money", () => {
    const text = visibleText(render(completed()));

    expect(text).toContain("Account opened");
    expect(text).toContain("A-12051");
    expect(text).toContain("From account");
    expect(text).toContain("Earliest legal start");
    expect(text).toContain("Committed by");
    expect(text).toContain("S. Ortiz");
    // the reads table, with the drawing's two `How` words and no third
    expect(text).toContain("Read date");
    expect(text).toContain("Not estimated");
    // the money box
    expect(text).toContain("Still to collect");
  });

  it("titles the page with the customer's NAME, never the address", () => {
    // B14 rule 40 · p074. A title repeating the address line reads as a
    // rendering bug, and the server has a matching assertion.
    const detail = completed();
    const text = visibleText(render(detail));
    expect(text).toContain("Miller, Sarah");
    expect(detail.title).not.toBe(detail.address_line);
  });

  it("carries exactly TWO doors and no action", () => {
    // The blueprint: *"This record has no actions, and that is the answer
    // rather than a gap."* Counted, not sampled — a subset assertion passes
    // while somebody adds a third control.
    const html = render(completed());
    const testIds = [...html.matchAll(/data-testid="(move-record-[^"]+)"/g)].map((m) => m[1]);
    expect(new Set(testIds)).toEqual(
      new Set(["move-record-open-account", "move-record-open-customer"]),
    );
    // and the two PO removed by name never appear
    const text = visibleText(html).toLowerCase();
    expect(text).not.toContain("raise a visit");
    expect(text).not.toContain("record the reading");
  });

  it("builds its doors under the tenant, not against another host", () => {
    // The fixture clause of hard-won law 2: mounted at the real pattern, a
    // tenant-less address would come out `//accounts/…`.
    const html = render(completed());
    expect(html).toContain('href="/brazosbend/accounts/acc-uuid-1"');
    expect(html).not.toContain('href="//accounts');
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: blueprint p074 + the PO's approval and action-bar ruling of
//         2026-09-19
// generated: 2026-09-19, the move-record lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ══════════════════════════════════════════════════════════════════════════
// THE MOVE-OUT BRANCH — blueprint p117–p118 of the 281-page edition
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **ONE ADDRESS, TWO FLOWS — AND THE PAGE SERVED ONLY ONE OF THEM UNTIL
// 2026-09-19 (`DEF-CUS-5889`).** `App.tsx` claimed in a comment that *"a
// move-OUT record answers here too … so one address serves both flows"*.
// Measured with a real request: `GET /moves/MVO-26-0001` answers **200** with
// `kind: "move_out"`, so the ADDRESS did serve both — and the PAGE had no
// move-out branch at all, so it rendered *"Account opened"* and *"Moved in on"*
// about somebody who had LEFT. Hard-won law 1: the comment was not the
// guarantee. These cases are that guarantee.
//
// ⚠ **THEY MOUNT UNDER THE REAL `/:tenant/moves/:ref` PATTERN**, like every
// case above — a bare `MemoryRouter` leaves `useParams().tenant` undefined and
// every address the page builds comes out protocol-relative, which reads as a
// good string to `toContain` (law 2's fixture trap).
function movedOut(over: Partial<MoveRecordDetail> = {}): MoveRecordDetail {
  return completed({
    kind: "move_out",
    move_no: "MVO-26-0088",
    title: "Okafor, D.",
    effective_on: "2026-01-28",
    ...over,
  });
}

describe("DEF-CUS-9650 — an opening read prints through the shared quantity formatter", () => {
  it("reads 16082 kWh and 841 kgal, never the stored six places", () => {
    const html = visibleText(
      render(
        completed({
          opening_reads: {
            rows: [
              { register: "M-1 · Electric · total", reading: "16082.000000", unit: "kWh", read_at: "2026-05-02", how: "read" },
              { register: "M-2 · Water · total", reading: "841.000000", unit: "kgal", read_at: "2026-05-02", how: "read" },
              { register: "M-3 · Water · total", reading: "26.243700", unit: "kgal", read_at: "2026-05-02", how: "read" },
            ],
            unavailable: null,
          },
        }),
      ),
    );
    expect(html).not.toContain("16082.000000");
    expect(html).not.toContain("841.000000");
    expect(html).toContain("16,082");
    expect(html).toContain("kWh");
    expect(html).toContain("841");
    expect(html).toContain("26.24");
    expect(html).not.toContain("26.2437");
  });
});

describe("the move-out branch (p117–p118)", () => {
  it("relabels the facts a departure changes, and drops the two it does not have", () => {
    const html = render(movedOut());
    const text = visibleText(html);
    // p118: `Account closed`, `Moved out on`. The SAME served field, relabelled
    // — printing "Account opened" over a departure is the defect itself.
    expect(text).toContain("Account closed");
    expect(text).toContain("Moved out on");
    expect(text).not.toContain("Account opened");
    expect(text).not.toContain("Moved in on");
    // ⛔ `From account` and `Earliest legal start` are MOVE-IN facts and p118
    // draws neither. The server sends both carrying honest move-in absences, so
    // rendering them states two absences about questions nobody asked.
    expect(text).not.toContain("From account");
    expect(text).not.toContain("Earliest legal start");
  });

  it("keeps the move-IN page exactly as it was — the regression this branch could cause", () => {
    // The whole risk of a `kind` branch is the flow you were not looking at.
    const text = visibleText(render(completed()));
    expect(text).toContain("Account opened");
    expect(text).toContain("Moved in on");
    expect(text).toContain("From account");
    expect(text).not.toContain("Account closed");
    expect(text).not.toContain("Moved out on");
    // And the move-in money section is still the DEPOSIT box, not a settlement.
    expect(text).not.toContain("Closing balance");
  });

  it("says `Moved out` in the chip and `Final reads` over the table", () => {
    const text = visibleText(render(movedOut()));
    expect(text).toContain("Moved out");
    expect(text).toContain("Final reads");
    expect(text).not.toContain("Opening reads");
  });

  it("states `Unit now` as an absence rather than deriving it from occupancy", () => {
    // p118 draws `Unit now · Vacant · standby off` and NOTHING serves it — not
    // the move record, not close-impact. A unit standing empty and a unit whose
    // standby was switched off are two facts; deriving either from the other
    // states a measurement nobody took.
    const html = render(movedOut());
    const text = visibleText(html);
    expect(text).toContain("Unit now");
    // The LABEL a clerk reads is the short one...
    expect(text).toContain("Not recorded");
    // ...and the ENGINEERING REASON rides in `title=`, never on the screen —
    // rule 33 puts rationale at zero words, and `visibleText` is what tells a
    // string being SHOWN from one carried as machine data.
    expect(html).toContain("deriving either from occupancy");
    expect(text).not.toContain("deriving either from occupancy");
  });
});

describe("`Tie the shortfall back` — the action p118 draws and this wave does not wire", () => {
  it("renders NO shortfall-tying control while the dialog is unbuilt, and says what would change that", () => {
    // ⚠ **THIS ASSERTS AN ABSENCE ON PURPOSE, AND THE ABSENCE IS THE SAFE
    // CHOICE RATHER THAN THE LAZY ONE.** p118 draws `Tie the shortfall back`
    // beside `Open the account`. Rendering it now would be a live-looking
    // control that opens nothing — hard-won law 2's MIRROR, which cost the
    // customer portal six dead doors out of eight on one page, every one of
    // them passing 42 test files and 391 cases.
    //
    // ⚠ **THE WRITE PATH EXISTS — SAYING OTHERWISE WOULD ROT INTO A WRONG
    // ABSENCE NOTE.** `POST /accounts/{id}/settle-shortfall` is mounted in
    // `apps/customers/api.py` beside `close-impact`, `refund` and
    // `hold-excess`. What is missing is the CONSENT DIALOG, and it is deferred
    // because it moves money between accounts: financial immutability,
    // balanced pairs through the ledger posting service only, hard rule 7's
    // audit_log write, and a 🔒 human-review row. Its own wave, its own proof.
    //
    // ⚠ **WHAT THIS TEST IS AND IS NOT.** It is the hold written down where a
    // lane will meet it. It is NOT as strong as a holds-registry row with an
    // expiry — the staff app has no equivalent of the portal's `holds.ts`, so
    // nothing fires automatically the day the dialog lands. **The lane that
    // builds the dialog DELETES this case and asserts the button by address
    // and by the screen id it opens.** That deletion is the point: a test you
    // must consciously remove is a hold somebody has to look at.
    const html = render(movedOut());
    expect(html).not.toContain("settle-shortfall");
    expect(html).not.toContain("move-record-tie-shortfall");
    // And the page still offers the door it DOES have, so the absence above is
    // an unbuilt action rather than a broken screen.
    expect(html).toContain("move-record-open-account");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE DOOR THAT FINISHES AN UNFINISHED MOVE — PO ruling 2026-09-19
// ══════════════════════════════════════════════════════════════════════════
//
// *"We will need this action on details page - 4 · Close or complete it"*, the
// fourth of the four capabilities named that hour. Before it, an `In progress`
// row opened onto a record with no way forward and the clerk had to go back to
// the parked-drafts panel.
//
// ⚠ **EVERY ADDRESS BELOW IS ASSERTED TWICE — AS A LITERAL AND AGAINST THE
// ROUTE CONSTANT `App.tsx` ACTUALLY MOUNTS.** Hard-won law 2's mirror: a
// hold-expiry test once asserted a screen was registered at an address while
// the router mounted it somewhere else, and both opened onto *"not built
// yet"* with every check passing. The literal catches a silent re-spelling;
// the constant catches the page and the router drifting apart.
describe("the resume door on an in-flight move", () => {
  it("carries the clerk into the move-IN wizard at the parked draft", () => {
    const html = render(inFlight());

    expect(html).toContain("move-record-resume");
    // by ADDRESS — the exact string a browser would follow
    expect(html).toContain('href="/brazosbend/move-ins/new?parked=park-uuid-77"');
    // …and by the ROUTE THE ROUTER MOUNTS, so this cannot pass while the
    // wizard lives somewhere else
    expect(MOVE_IN_WIZARD_ROUTE).toBe("/move-ins/new");
    expect(html).toContain(`href="/brazosbend${MOVE_IN_WIZARD_ROUTE}?parked=`);
  });

  it("sends a move-OUT draft to the move-out wizard and never to the move-in one", () => {
    // One address serves both flows, so the flow is the thing most easily got
    // wrong here — and getting it wrong would open a wizard that hydrates a
    // draft of the other kind.
    const html = render(inFlight({ kind: "move_out", move_no: "MVO-26-0087" }));

    expect(html).toContain('href="/brazosbend/move-outs/new?parked=park-uuid-77"');
    expect(html).toContain(`href="/brazosbend${MOVE_OUT_WIZARD_ROUTE}?parked=`);
    expect(html).not.toContain("/move-ins/new");
  });

  it("offers NOTHING when the server sent no park id", () => {
    // ⚠ **THE FAILURE THIS FORBIDS IS A DOOR BUILT FROM THE REFERENCE.** The
    // record is addressed by `MVI-26-0113` and the wizard is resumed by id, so
    // a page that fell back to the reference would produce a real-looking URL
    // that resolves to no draft — hard-won law 2's mirror in its most
    // convincing costume. No handle, no door.
    const html = render(inFlight({ park_id: null }));

    expect(html).not.toContain("move-record-resume");
    expect(html).not.toContain("?parked=");
    expect(html).not.toContain("MVI-26-0113?parked");
  });

  it("leaves a COMPLETED record exactly as the blueprint ruled it", () => {
    // p077 and p118 draw a finished record whose only controls are doors. The
    // ruling adds an action for `in_flight` and for nothing else, so a
    // completed record must not grow one — counted, not sampled.
    const html = render(completed());
    const testIds = [...html.matchAll(/data-testid="(move-record-[^"]+)"/g)].map((m) => m[1]);

    expect(testIds).not.toContain("move-record-resume");
    expect(new Set(testIds)).toEqual(
      new Set(["move-record-open-account", "move-record-open-customer"]),
    );
  });

  it("does not displace the account door, because that door is never there to displace", () => {
    // The server answers `NO_ACCOUNT_UNTIL_IT_COMPLETES` for every unfinished
    // move — an account is what completing one PRODUCES. So the slot this
    // action takes was empty, and the two can never contend for it.
    const html = render(inFlight());

    expect(html).toContain("move-record-resume");
    expect(html).not.toContain("move-record-open-account");
  });

  it("says the SAME word the parked-drafts panel says", () => {
    // ⚠ **THE DRIFT GUARD, AND IT IS THE REASON THE KEY IS SHARED RATHER THAN
    // COPIED.** Two surfaces open the same draft at the same step; one act
    // wears one word (B14 rule 34's principle, and `DEF-CUS-5901` is what two
    // words for one state already cost). Sharing the catalogue key makes drift
    // impossible — this asserts that the sharing is still real, so anyone
    // re-wording the panel is told they are re-wording this too.
    const text = visibleText(render(inFlight()));
    const panelWord = i18n.t("customers.waitingOn.action.resume", { defaultValue: "Resume" });

    expect(panelWord).toBe("Resume");
    expect(text).toContain(panelWord);
    // rule 33 — a LABEL is three words or fewer, and one beats two
    expect(panelWord.trim().split(/\s+/)).toHaveLength(1);
  });

  it("builds the address under the tenant, never against another host", () => {
    // Law 2's fixture clause: mounted bare, `useParams().tenant` is undefined
    // and every address comes out `//move-ins/new…` — a protocol-relative URL
    // to somebody else's server that reads as a good string to `toContain`.
    const html = render(inFlight());

    expect(html).not.toContain('href="//move-ins');
    expect(html).toMatch(/href="\/brazosbend\/move-ins\/new\?parked=/);
  });
});

describe("`Tie the shortfall back` — the hold, and what makes it expire", () => {
  it("draws no shortfall control EVEN WHERE p118 draws one", () => {
    // ⚠ **THIS IS THE HOLD, AND IT IS EXERCISED UNDER THE DRAWN CONDITION
    // RATHER THAN THE ORDINARY ONE.** The sibling case above asserts the
    // control is absent on a default record — true today, but true only
    // because the settlement never lands `short` while no final bill is
    // stated. It would therefore go on passing after somebody wires the
    // button, because the fixture never reaches the branch that draws it.
    // This one seeds the settlement p118 actually draws — landed SHORT, with a
    // figure — so it is looking at the branch the button will live in.
    //
    // ⚠ **WHAT MAKES IT EXPIRE:** the day the consent dialog is built, this
    // case goes RED and names itself. **The lane that builds it DELETES this
    // case** and replaces it with the positive assertion — the control by
    // ADDRESS and by the screen id it opens, exactly as the resume door above
    // is asserted. A hold with no such test is a promise nobody is keeping.
    //
    // ⚠ **THE WRITE PATH EXISTS AND IS LIVE** — `POST /accounts/{id}/settle-shortfall`
    // is mounted beside `close-impact`. Saying otherwise here would rot into a
    // false note the next lane quotes. What is missing is the CONSENT DIALOG,
    // and it is deferred because it moves money between accounts: financial
    // immutability, balanced pairs through the ledger posting service only,
    // hard rule 7's `audit_log` write and a 🔒 human-review row.
    const html = render(movedOut());

    expect(html).not.toContain("move-record-tie-shortfall");
    expect(html).not.toContain("settle-shortfall");
    // and the page still offers the door it DOES have, so this is an unbuilt
    // action rather than a broken screen
    expect(html).toContain("move-record-open-account");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `← Move-ins` / `← Move-outs` — THE BACK CONTROL NAMES WHERE IT EXITS TO
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **`DEF-CUS-5996` — REPORTED FROM THE LIVE PRODUCT.** PO, verbatim: *"Same
// problem with MOve out also - it takes you to move in list page"*. This page
// serves BOTH flows and hardcoded `tab=move-ins` in two places, while already
// holding `record.kind` — decision log 2026-09-20 §8, *"The destination simply
// ignored a fact it already held."* **B14 rule 1 decides it: a page header's
// `←` NAMES WHERE IT EXITS TO**, and a control that names its destination
// cannot send a clerk to the wrong tab.
//
// ⚠ **ASSERTED BY ADDRESS, AND THE TWO FLOWS SEPARATELY.** A case that only
// checked the move-OUT would go on passing if somebody flipped the hardcode the
// other way; a case that only checked *"the href contains accounts"* would pass
// on both bugs. Each flow pins its OWN slug and denies its sibling's.
//
// ⚠ **THE SLUGS ARE `AccountsListPage`'s OWN, HYPHENATED** — `ACCOUNTS_TAB_IDS`
// reads `move-ins` / `move-outs`, and they are imported rather than retyped so
// this file cannot go on passing while the page and the tab strip disagree.
// They are NOT the backend's `QUEUE_MOVE_INS = "move_ins"`, which is
// underscored and names a job queue, not a tab.
describe("the back control names the list it exits to (DEF-CUS-5996)", () => {
  it("sends a move-OUT record to the Move-outs tab, by address", () => {
    const html = render(movedOut());

    expect(html).toContain(`href="/brazosbend/accounts?tab=${MOVE_OUTS_TAB}"`);
    expect(html).not.toContain(`href="/brazosbend/accounts?tab=${MOVE_INS_TAB}"`);
    // law 2's fixture trap: a protocol-relative address reads as a good string
    expect(html).not.toContain('href="//accounts');
  });

  it("sends a move-IN record to the Move-ins tab, by address", () => {
    const html = render(completed());

    expect(html).toContain(`href="/brazosbend/accounts?tab=${MOVE_INS_TAB}"`);
    expect(html).not.toContain(`href="/brazosbend/accounts?tab=${MOVE_OUTS_TAB}"`);
    expect(html).not.toContain('href="//accounts');
  });

  // ⚠ **THE NOT-FOUND STATE HAS NO `record`, SO IT HAS NO `kind`** — and it is
  // reached precisely when the server could not answer. It reads the REFERENCE
  // out of the URL instead: `MVO-` is the move-out series and `MVI-` the
  // move-in one (`moves.py:137`), and the lookup is `move_no__iexact`, so the
  // prefix is the one fact the 404 still holds. Anything else keeps today's
  // Move-ins destination — stated, not guessed at silently.
  it("sends a 404 on an MVO- reference to the Move-outs tab", () => {
    const html = renderNotFound("MVO-26-0088");

    expect(html).toContain(`href="/brazosbend/accounts?tab=${MOVE_OUTS_TAB}"`);
    expect(html).not.toContain(`href="/brazosbend/accounts?tab=${MOVE_INS_TAB}"`);
  });

  it("sends a 404 on an MVI- reference to the Move-ins tab", () => {
    const html = renderNotFound("MVI-26-0114");

    expect(html).toContain(`href="/brazosbend/accounts?tab=${MOVE_INS_TAB}"`);
    expect(html).not.toContain(`href="/brazosbend/accounts?tab=${MOVE_OUTS_TAB}"`);
  });

  it("falls back to Move-ins on a reference carrying neither prefix", () => {
    // Not a guess: it is the destination this page has always had, kept as the
    // default so an unrecognisable reference changes nothing.
    const html = renderNotFound("WHAT-26-0001");

    expect(html).toContain(`href="/brazosbend/accounts?tab=${MOVE_INS_TAB}"`);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// CR-168-BRC10 lane FLOW-FIX — the visit a move raised, and the money at 2 dp
// ══════════════════════════════════════════════════════════════════════════
//
// `DEF-CUS-9628`: a move-in read *Visit: Not raised* over a job raised, done and
// accepted, and a move-out showed no visit at all. `DEF-CUS-9632`: the deposit
// printed `0.0000`. Both measured on PostgreSQL by lane FLOW-MEASURE (§F).
const VISIT = {
  value: {
    raised: 1,
    done: 1,
    accepted: 1,
    orders: [
      { order_no: "WO-0047", service: "electric", state: "completed", done: true, accepted: true, assignee: "R. Patel" },
    ],
  },
  unavailable: null,
};

describe("DEF-CUS-9628 — the move record shows the visit it raised", () => {
  it("counts the move-in's visit and links its order by number", () => {
    const detail = completed();
    const html = render({ ...detail, still_owed: { ...detail.still_owed, visit: VISIT } } as never);
    const text = visibleText(html);
    expect(text).toContain("1 raised · 1 done · 1 accepted");
    expect(text).not.toContain("Not raised");
    expect(html).toContain('href="/brazosbend/work/orders/WO-0047"');
  });

  it("shows the visit on a MOVE-OUT too, which had no visit line at all", () => {
    const detail = movedOut();
    const html = render({ ...detail, still_owed: { ...detail.still_owed, visit: VISIT } } as never);
    expect(visibleText(html)).toContain("1 raised · 1 done · 1 accepted");
    expect(html).toContain('href="/brazosbend/work/orders/WO-0047"');
  });
});

describe("CR-185-BRC10 — the move-out record shows the tie-back to the owner", () => {
  it("pending until the final bill is sent, then Posted; absent when none", () => {
    const detail = movedOut();
    const pending = visibleText(
      render({
        ...detail,
        balance_to_owner: { status: "pending", pending: true, posted: false, amount: { display: "917.10" } },
      } as never),
    );
    expect(pending).toContain("$917.10 · Moves to the owner when the final bill is sent");
    const posted = visibleText(
      render({
        ...detail,
        balance_to_owner: { status: "posted", pending: false, posted: true, amount: { display: "917.10" } },
      } as never),
    );
    expect(posted).toContain("$917.10 · Posted");
    expect(render({ ...detail, balance_to_owner: null } as never)).not.toContain(
      "move-record-balance-to-owner",
    );
  });
});

describe("DEF-CUS-9632 — the deposit displays at 2 decimals (hard rule 2)", () => {
  it("never prints a four-decimal money string", () => {
    const detail = completed();
    const text = visibleText(
      render({
        ...detail,
        money_taken: {
          ...detail.money_taken,
          taken: { value: "0.0000", unavailable: null },
          currency: "USD",
        },
      }),
    );
    expect(text).not.toMatch(/\d\.\d{4}/);
    expect(text).toContain("$0.00");
    expect(text).toContain("$150.00");
  });
});
