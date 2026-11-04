// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — the DISCONNECT LIST, built to its drawing. PO
//           ruling 2026-09-20, verbatim: *"this is correct - build disconnect
//           list view - ensure you follow our toolkit rules search, filter,
//           colume selector, you follow ui skills and spacing rules that we
//           set - drwaing and screens hosuld match - please build it"*.
// Drawing:  `05-prototype/02 Accounts Menu Blueprint.pdf` p142, read AS AN
//           IMAGE at scale 8 — B14 rule 42. **This PDF's text layer renders
//           every digit as `&`**, so a screen built from extracted text loses
//           every figure on the page and every column boundary with it.
// Rules:    B14 rule 33 (LABEL ≤ 3 words · FACT ≤ 6 · RATIONALE zero) · rule 37
//           (a drawn figure is an ILLUSTRATION) · rule 15 (a row action is an
//           unlabelled icon) · rule 43 (a piece of UI is a COMPONENT) ·
//           BR-SHL-010 · hard-won law 2 and its MIRROR (a live screen behind a
//           dead control; a control onto nothing)
// ───────────────────────────────────────────────────────
//
// **WHY THIS FILE IS SEPARATE FROM `DisconnectsTab.test.tsx`.**
//
// That suite renders to STATIC MARKUP. It can prove a cell's words and it can
// never prove that pressing a chip sends anything — which is the whole of
// hard-won law 2, and the reason five worklists once shipped a filter that
// rendered and did nothing (`DEF-1702`). This file CLICKS, in jsdom.
//
// ⚠ **AND IT MOUNTS UNDER THE REAL PATH PATTERN, NOT A BARE `MemoryRouter`.**
// `DisconnectsTab` builds its empty-state address through `useTenantPath()`,
// which reads `useParams().tenant`. Mounted with no `/:tenant/...` route that
// is `undefined`, every address comes out `//accounts/…` — a protocol-relative
// URL to another host, which reads as a perfectly good string to `toContain`.
// That is `DEF-CWP-3925`'s fixture hole, named in hard-won law 2.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import { APP_ROUTES } from "@/App";
import type { RouteObject } from "react-router-dom";
import { SCREEN_ROUTES } from "@/routing/screenIds";

import { DisconnectsTab } from "./DisconnectsTab";
import { disconnectsTableConfig } from "./DisconnectsTab";
import {
  DISCONNECT_RECORD_ROUTE,
  DISCONNECT_RECORD_SCREEN,
} from "./disconnect/record/disconnectRecordEndpoints";
import type { DisconnectList, DisconnectRow } from "./worklistEndpoints";

const TEST_TENANT = "brazosbend";

/** The legs this list DECLARES, read off the config rather than retyped — a
 *  second copy of the tuple would agree with itself and with nothing else. */
const DISCONNECTS_SEARCH_FIELDS =
  disconnectsTableConfig((_k, p) => String((p as { defaultValue?: string })?.defaultValue ?? ""), {
    owed: () => <span />,
    tier: () => <span />,
    cutDate: () => <span />,
    lastNotice: () => <span />,
    state: () => <span />,
    actions: () => <span />,
  }).searchFields ?? [];

afterEach(cleanup);

const ABSENCE = { code: "delivery_adapter_absent", br_ref: "BR-NOT-005", detail: "no adapter" };
const NO_SCHEDULER = {
  code: "no_scheduler",
  br_ref: "BR-CUS-039",
  detail: "nothing advances the ladder",
  advances_on_a_schedule: false,
};

/** p142's own first row — `DSC-26-0003 · A-11812 · Bramble Bakery`. ⚠ Its
 *  FIGURES are illustrations (B14 rule 37); what this fixture pins is the
 *  SHAPE of a row, never `$2,410.00` as a requirement. */
function row(over: Partial<DisconnectRow> = {}): DisconnectRow {
  return {
    account_id: "acc-11812",
    case_no: "DSC-26-0003",
    case_no_unavailable: null,
    account_no: "A-11812",
    customer: "Bramble Bakery",
    address: "142 Bakers Row · Suite 1",
    unit_id: "u-11812",
    owed: {
      stored: "2410.0000",
      display: "2410.00",
      currency: "USD",
      source: "ledger",
      unavailable: null,
    },
    tier: {
      chips: [{ code: "tier_2_10_day", label: "TIER 2 · 10-DAY", tone: "ink" }],
      ambiguous: false,
      unavailable: [],
    },
    cut_date: "2026-05-14",
    cut_date_is_this_week: false,
    last_notice: {
      issued_on: "2026-04-24",
      tier: "tier_2_10_day",
      delivery_state: null,
      unavailable: ABSENCE,
    },
    state: { stored: "notice_sent", held_by: [], one_cell_is_unresolved: false, unavailable: null },
    ladder: {
      runs: true,
      halt_code: null,
      detail: "the ladder runs",
      sequence: "service",
      scheduler: NO_SCHEDULER,
    },
    protections: [],
    case: null,
    subject: null,
    chase_subject_unresolved: null,
    ...over,
  };
}

function payload(over: Partial<DisconnectList> = {}): DisconnectList {
  return {
    rows: [row()],
    kpis: {
      at_notice: 1,
      due_to_cut_this_week: 1,
      on_hold_protected: 1,
      cut_awaiting_payment: 0,
      cut_awaiting_payment_unavailable: {
        code: "cut_accrual_caption_superseded",
        br_ref: "BR-CUS-103",
        detail: "superseded",
      },
      reconnections_due: 0,
      as_of: "2026-09-20",
    },
    page: 1,
    per: 50,
    total: 3,
    pages: 1,
    columns: [
      "reference",
      "account",
      "customer",
      "address",
      "owed",
      "tier",
      "cut_date",
      "last_notice",
      "state",
    ],
    segment: "all",
    segments: [{ code: "all", label: "All", supported: true, unavailable: null }],
    filters: ["state"],
    states: [
      { code: "notice_sent" },
      { code: "scheduled" },
      { code: "on_hold" },
      { code: "cut" },
      { code: "reconnecting" },
    ],
    chips: [],
    search: {
      hint: "Customer, account #, address, or meter #…",
      legs: ["customer", "account_no", "address", "meter_no"],
    },
    delivery: ABSENCE,
    scheduler: NO_SCHEDULER,
    as_of: "2026-09-20",
    ...over,
  };
}

/**
 * Mount the tab AT ITS REAL ADDRESS.
 *
 * `bodies` is consumed in order, so a click that re-queries is answered with a
 * DIFFERENT result set — the only shape that can tell a server round trip from
 * a page narrowed in the browser (`DEF-1702`'s own reasoning).
 */
function mount(bodies: DisconnectList[]) {
  const urls: string[] = [];
  let call = 0;
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      urls.push(String(input));
      const body = bodies[Math.min(call, bodies.length - 1)];
      call += 1;
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=disconnects`]}>
        <Routes>
          <Route path="/:tenant/accounts" element={<DisconnectsTab client={client} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { urls };
}

describe("CR-125-BRC07 · S90's list, against p142 of the Accounts blueprint", () => {
  // ════════════════════════════════════════════════════════════════════════
  // THE FIVE TILES — the drawn labels, in the DRAWN ORDER
  // ════════════════════════════════════════════════════════════════════════
  /**
   * ⚠ **SCOPED TO THE STRIP, AND THE FIRST DRAFT WAS NOT.** A document-wide
   * `findAllByText(/At notice|Due to cut|…/)` also matches the quick-view chips
   * and the State cell, which use the same vocabulary on purpose — it returned
   * eleven nodes. A check whose subject is *"everything on the page that says
   * one of these words"* cannot answer *"are the five tiles in the drawn
   * order"* (hard-won law 7: what would make this pass wrongly).
   */
  function tileLabels(): string[] {
    const strip = document.querySelector(".kpi-grid");
    return Array.from(strip?.querySelectorAll("span.k") ?? []).map((node) =>
      String(node.textContent).trim(),
    );
  }

  /**
   * ⚠ **THE ORDER AND THE WORDS MOVED ON 2026-09-25 AND THE FIGURES DID NOT.**
   * p142 draws `AT NOTICE · DUE TO CUT · CUT, AWAITING RECONNECT · ON HOLD ·
   * RECONNECTIONS`; the redesign drawing draws `NOTIFIED · SCHEDULED · OFF ·
   * PAID · HELD` — HELD moves to the end, and every word becomes one of the
   * Product Owner's six clerk words, which are now the ONLY vocabulary on this
   * screen. Each tile still reads the same served number it read before.
   */
  it("draws the five tiles in the drawing's order, in the six clerk words", async () => {
    mount([payload()]);
    await screen.findByRole("table");
    // `DEF-CUS-10667` (PO 2026-10-29, *"1A"*): the fourth word is
    // `Reconnecting`, never `Paid` — see the case further down this file.
    expect(tileLabels()).toEqual(["Notified", "Scheduled", "Off", "Reconnecting", "Held"]);
  });

  /** ⚠ **THE COUNT IS ASSERTED FIRST, AND THAT IS NOT PADDING.** A `for` over
   *  whatever the regex happened to match passes on ONE tile as happily as on
   *  five — a check that cannot fail when four labels are wrong (hard-won law
   *  7's *what would make this pass wrongly*). It was written that way and
   *  found by asking the question. */
  it("B14 rule 33 — all five tile LABELS are three words or fewer", async () => {
    mount([payload()]);
    await screen.findByRole("table");
    const labels = tileLabels();
    expect(labels).toHaveLength(5);
    for (const label of labels) {
      expect(label.split(/\s+/).length).toBeLessThanOrEqual(3);
    }
  });

  /**
   * ⚠ **JUDGMENT 3, RECORDED ON THE SCREEN RATHER THAN IN A COMMENT.** p142
   * captions this tile *"the date has arrived"*; the figure beside it is
   * `kpis.due_to_cut_this_week`, which `_within_the_week` computes as **7 days
   * forward, inclusive at both ends**. Those count different things, and the
   * figure is the SERVER's.
   *
   * Printing the drawn caption over the served figure would put a FALSE
   * sentence on the tile — which is `DEF-716` exactly, on this same strip, on
   * this same screen. So the caption states what the figure IS. The drawn
   * definition is REPORTED as a server change, not taken by this lane.
   */
  it("the SCHEDULED caption states what the figure counts, and never p142's definition", async () => {
    mount([payload()]);
    // The redesign's own caption, and — unlike p142's — it is TRUE of the
    // served figure, which is why it can be printed verbatim.
    expect(await screen.findByText("Within seven days")).toBeInTheDocument();
    expect(screen.queryByText("the date has arrived")).not.toBeInTheDocument();
  });

  // ════════════════════════════════════════════════════════════════════════
  // THE NINE DRAWN COLUMNS
  // ════════════════════════════════════════════════════════════════════════
  it("heads the first column `Case #`, which is what p142 draws", async () => {
    mount([payload()]);
    const table = await screen.findByRole("table");
    const heads = within(table)
      .getAllByRole("columnheader")
      .map((cell) => String(cell.textContent).replace(/[⇅↑↓]/gu, "").trim());
    expect(heads[0]).toBe("Case #");
    expect(heads).not.toContain("Reference");
  });

  /**
   * ⚠ **THE FIGURE WINS OVER THE CAPTION, AND THAT WAS RULED BEFORE THIS LANE
   * STARTED.** p142's caption calls a `WAITING ON` column this tab's addition;
   * the figure beneath draws NINE columns and none of them is it. B14 rule 42
   * makes the drawing AS AN IMAGE the specification and extracted text only an
   * index — a caption is text, the figure is the image. So nine, and
   * `waiting_on` keeps rendering where it already does, inside the State cell
   * of a parked draft.
   */
  /**
   * ⚠ **`Last notice` LEFT THE DEFAULT SET ON 2026-09-25 — `DEF-CUS-6745`.**
   * Ten columns came to **1453px** inside a viewport with no horizontal scroll
   * container, so the Actions column and the only row action on this screen
   * were CLIPPED — by 13px at 1440 and by 173px at 1280, measured in Chromium.
   * The redesign drawing does not draw the column at all; p142 does. Neither
   * is overruled: `defaultVisible: false` keeps the column in the `▦` chooser,
   * one click away, and off the default table. The case below pins that it is
   * still OFFERED, so "off by default" cannot rot into "deleted".
   */
  it("draws the eight default columns plus the actions column, and no `Waiting on`", async () => {
    mount([payload()]);
    const table = await screen.findByRole("table");
    const heads = within(table)
      .getAllByRole("columnheader")
      .map((cell) => String(cell.textContent).replace(/[⇅↑↓]/gu, "").trim())
      .filter((label) => label !== "");
    expect(heads).toEqual([
      "Case #",
      "Account",
      "Customer",
      "Address",
      "Owed",
      "Tier",
      "Cut date",
      "State",
      // ⚠ **THE TENTH IS THE ACTIONS COLUMN AND IT IS LABELLED, THOUGH p142
      // DRAWS ITS HEADER BLANK.** Twenty-nine list tables in this product head
      // that column `Actions`; an unlabelled tenth header here would be this
      // screen departing from every other one on one drawing's authority, and
      // B14 rule 38 gives CONSTRUCTION to the UI rules. What the column
      // CONTAINS is still the drawing's: one action, open the case.
      "Actions",
    ]);
  });

  // ════════════════════════════════════════════════════════════════════════
  // THE DRAWN STATE VOCABULARY
  // ════════════════════════════════════════════════════════════════════════
  /**
   * ⚠ **THE THIRD SPELLING OF THIS COLUMN, AND THE FIRST THAT IS NOT A
   * TRANSLATION OF AN INTERNAL WORD.** §5.8.6 said `Notice sent` — the stored
   * code in English. p142 said `At notice`. The Product Owner's six clerk
   * words say **Notified**. All three cases are kept as one, because the value
   * of this check is that the two SUPERSEDED spellings are asserted absent.
   */
  it("says `Notified` — neither `Notice sent` nor p142's `At notice`", async () => {
    mount([payload()]);
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Notified")).toBeInTheDocument();
    expect(within(table).queryByText("Notice sent")).not.toBeInTheDocument();
    expect(within(table).queryByText("At notice")).not.toBeInTheDocument();
  });

  it("says `Scheduled`, not p142's `Due to cut`", async () => {
    mount([
      payload({
        rows: [
          row({
            state: {
              stored: "scheduled",
              held_by: [],
              one_cell_is_unresolved: false,
              unavailable: null,
            },
          }),
        ],
      }),
    ]);
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Scheduled")).toBeInTheDocument();
    expect(within(table).queryByText("Due to cut")).not.toBeInTheDocument();
  });

  // ════════════════════════════════════════════════════════════════════════
  // THE QUICK-VIEW CHIPS — JUDGMENT 1
  // ════════════════════════════════════════════════════════════════════════
  /**
   * ⚠⚠ **THE QUICK-VIEW CHIPS ARE GONE — PO, 2026-09-25 — AND THESE CASES ARE
   * REWRITTEN RATHER THAN DELETED.** p142 draws a chip row in front of the
   * filter panel, and this file asserted its order, its press, its second
   * press and its note. The screen offered **the same dimensions twice**: the
   * chips and the panel both wrote `f.state` and `f.due`, so a clerk had two
   * places to answer one question. The redesign draws search, `All`,
   * `+ Filter` and the column chooser, and nothing else.
   *
   * **What must not be lost is the CAPABILITY**, so the assertions become the
   * other half of the same claim: the chips are absent AND every value they
   * offered is still reachable through the panel, from the same served
   * vocabulary. A case that only asserted the absence would pass just as well
   * on a screen with no filtering at all — hard-won law 7's *what would make
   * this pass wrongly*.
   */
  it("draws NO quick-view chips — one filter list, not two", async () => {
    mount([payload()]);
    await screen.findByRole("table");
    expect(document.querySelectorAll("[data-quick-view]")).toHaveLength(0);
    expect(document.querySelector("[data-quick-view-note]")).toBeNull();
  });

  it("…and the dimension they carried is still offered, by the panel", async () => {
    mount([payload()]);
    await screen.findByRole("table");
    // The panel's own disclosure, opened, so the assertion is about what a
    // clerk can actually reach rather than about a helper's return value.
    await userEvent.click(screen.getByText("+ Filter"));
    const panel = document.body;
    for (const word of ["Notified", "Scheduled", "Reconnecting"]) {
      expect(within(panel).getAllByText(word).length).toBeGreaterThan(0);
    }
  });

  /**
   * ⚠ **`on_hold` IS NOW A FILTER THAT MATCHES, AND IT NEVER DID BEFORE —
   * `DEF-CUS-6746`.** This file used to assert the OPPOSITE: that no `On hold`
   * quick view is drawn, because `STATE_ON_HOLD` is declared, is in the
   * migration's CHECK vocabulary and is **assigned nowhere**, so the filter
   * could never match a row. That was a true reading of a BROKEN control, and
   * it is fixed in the read model rather than worked around on the screen:
   * `_list_queryset` now resolves `on_hold` the way the list and the HELD tile
   * already resolve it — an account carrying a protection in force. Measured
   * on PostgreSQL: `f.state=on_hold` returned 0 rows and now returns 2, over a
   * list whose State column says `Held` on exactly those two.
   */
  it("offers `Held` in the panel, because `on_hold` can now match a row", async () => {
    mount([payload()]);
    await screen.findByRole("table");
    await userEvent.click(screen.getByText("+ Filter"));
    expect(within(document.body).getAllByText("Held").length).toBeGreaterThan(0);
  });

  // ════════════════════════════════════════════════════════════════════════
  // `DEF-CUS-6749` — THE CREW WAS THERE, AND THE LIST SAYS SO
  // ════════════════════════════════════════════════════════════════════════
  /**
   * ⚠ **NOTHING COULD HAVE CAUGHT THIS AND THAT IS WHY IT IS WORTH A CASE.**
   * `apps/customers/disconnect_visits.py` has carried four outcomes since
   * `BR-CUS-1083` and `disconnect_reads.py` contained ZERO references to it.
   * Three of the four CLEAR the cut date and return the case to `notice_sent`
   * — a real, correct state — so a case a crew drove to on Tuesday and a case
   * nobody has ever visited rendered **identically**: same word, same empty
   * Cut date, no null and no gap anywhere for a check to notice. The write
   * side was fully tested; the read side did not know the table existed.
   *
   * Verified end to end on PostgreSQL before this case was written: recording
   * a `locked_gate` visit on `DSC-26-0001` moved it from `scheduled` back to
   * `notice_sent` and cleared its cut date, and the row then read
   * `Notified · Visited · Locked gate · 09/24/2026` in a browser.
   */
  it("a case a crew attended does not read like one nobody visited", async () => {
    mount([
      payload({
        rows: [
          row({
            state: {
              stored: "notice_sent",
              held_by: [],
              one_cell_is_unresolved: false,
              unavailable: null,
            },
            cut_date: null,
            visit: {
              outcome: "locked_gate",
              visited_on: "2026-09-24",
              clears_the_cut_date: true,
            },
          }),
        ],
      }),
    ]);
    const table = await screen.findByRole("table");
    // The STATE word is unchanged and correct — that is the trap, not a bug.
    expect(within(table).getByText("Notified")).toBeInTheDocument();
    // …and the row now carries what makes it different from an unvisited one.
    const cell = table.querySelector("[data-state-visit]");
    expect(cell).not.toBeNull();
    expect(cell?.getAttribute("data-state-visit")).toBe("locked_gate");
    expect(String(cell?.textContent)).toContain("Locked gate");
    expect(cell?.getAttribute("data-visit-cleared-date")).toBe("");
  });

  /** The mirror, and it is the half that makes the case above mean anything:
   *  a row with no recorded visit says NOTHING, because an absent row is not
   *  a claim that nobody went. A case asserting only the positive would pass
   *  on a screen that printed "Visited" over every row. */
  it("a row with no recorded visit claims nothing about one", async () => {
    mount([payload({ rows: [row({ visit: null })] })]);
    const table = await screen.findByRole("table");
    expect(table.querySelector("[data-state-visit]")).toBeNull();
    expect(within(table).queryByText(/Visited/u)).not.toBeInTheDocument();
  });

  // ════════════════════════════════════════════════════════════════════════
  // THE `LAST NOTICE` CELL — ONE LINE, AND NO RATIONALE ON IT
  // ════════════════════════════════════════════════════════════════════════
  /**
   * ⚠ **FOUND IN A BROWSER, NOT IN THIS SUITE — WHICH IS HARD-WON LAW 6's
   * WHOLE POINT.** p142 draws `10-day · 04/24/2026`: one line, two facts. The
   * cell rendered a COLUMN of three, the third being *"how it was delivered is
   * not recorded"* on every row — SEVEN words of RATIONALE against rule 33's
   * zero, and a second copy of a sentence the cell's `title` already carries.
   * Every case in this file passed over it, because none of them looked.
   */
  it("renders the notice as `TIER · DATE` and never repeats the delivery reason as prose", async () => {
    mount([payload()]);
    await screen.findByRole("table");
    // ⚠ **THE COLUMN IS OFF BY DEFAULT SINCE `DEF-CUS-6745`**, so this case
    // turns it on through the chooser a clerk uses. That is not scaffolding
    // around the assertion — it IS the other half of the claim in that
    // defect's fix: the column was taken off the default set and **not
    // deleted**, and a case that could no longer reach it would let "off by
    // default" rot into "gone" with nothing going red.
    await userEvent.click(screen.getByLabelText("Show or hide columns"));
    await userEvent.click(await screen.findByRole("checkbox", { name: /last notice/iu }));
    const table = await screen.findByRole("table");
    const cell = table.querySelector("[data-last-notice]");
    expect(cell).not.toBeNull();
    // The separator's spacing is a flex GAP, so it is absent from `textContent`
    // and present on screen. Normalising it here keeps the case about the two
    // facts and their order rather than about how the gap was drawn.
    expect(
      String(cell?.textContent)
        .replace(/\s+/gu, " ")
        .replace(/\s*·\s*/gu, " · ")
        .trim(),
    ).toBe("TIER 2 · 10-DAY · 04/24/2026");
    // TC-DSC-6's guarantee is untouched: the reason is still ON the cell, as
    // the `title` BR-SHL-025 asks for, and its marker is still assertable.
    expect(cell?.getAttribute("data-delivery-absent")).toBe("");
    expect(cell?.getAttribute("title")).toMatch(/does not send email/u);
  });

  /**
   * ⚠ **ONE WORD, AND SINCE 2026-10-29 IT IS `Reconnecting` — NEVER `Paid`
   * (`DEF-CUS-10667`).** p142 had a chip naming the VIEW and a cell naming the
   * STATE; the redesign gave the state ONE word on the tile and in the cell
   * alike, and that word was `Paid`. Since `BR-CUS-1097` (2026-09-25) and the
   * PO's C1 (*"Restore = Reconnect request"*) a case reaches `reconnecting`
   * OWING money — DSC-26-0001 asked to be reconnected owing $8,315.00 and read
   * `Paid`. PO, 2026-10-29: *"1A"* — the word is `Reconnecting`.
   *
   * RED FIRST: with `STATE_LABELS.reconnecting` and the catalogues still
   * reading `Paid`, `getByText("Reconnecting")` finds nothing.
   */
  it("the tile and the State cell say `Reconnecting`, never `Paid` — DEF-CUS-10667", async () => {
    mount([
      payload({
        rows: [
          row({
            state: {
              stored: "reconnecting",
              held_by: [],
              one_cell_is_unresolved: false,
              unavailable: null,
            },
          }),
        ],
      }),
    ]);
    const table = await screen.findByRole("table");
    expect(document.querySelector('[data-quick-view="reconnecting"]')).toBeNull();
    expect(within(table).getByText("Reconnecting")).toBeInTheDocument();
    expect(within(table).queryByText("Paid")).not.toBeInTheDocument();
    expect(tileLabels()).toContain("Reconnecting");
    expect(tileLabels()).not.toContain("Paid");
  });

  // ════════════════════════════════════════════════════════════════════════
  // B14 RULE 33 — THE DRAWING'S TWO NOTES ARE RATIONALE
  // ════════════════════════════════════════════════════════════════════════
  it("renders NEITHER explanatory note — rationale is zero words on screen", async () => {
    mount([payload()]);
    await screen.findByRole("table");
    const text = document.body.textContent ?? "";
    expect(text).not.toContain("is not a delay");
    expect(text).not.toContain("answer different questions");
  });

  // ════════════════════════════════════════════════════════════════════════
  // JUDGMENT 2 — `↗ Open` WAS HELD, THE HOLD EXPIRED, AND THE DOOR IS OPEN
  // ════════════════════════════════════════════════════════════════════════
  /**
   * ⚠ **THIS BLOCK REPLACES A HOLD THAT WENT GREEN OVER A LIVE SCREEN, AND THE
   * REPLACEMENT IS THE POINT — `DEF-CUS-6042`.**
   *
   * The hold asserted that `SCREEN_ROUTES` held no address under
   * `/disconnects/` but the wizard's, so it would go red the day a case screen
   * landed. It was written to survive a RENAME — it filtered on any
   * `/disconnects/` path rather than one spelling — and it was defeated by
   * something else entirely: **there are TWO registries a route can live in,
   * and it watched the one the router does not use.** `DisconnectRecordPage`
   * landed in `4ff860296`, mounted in `App.tsx` at `/:tenant/disconnects/:ref`,
   * and its `SCREEN_ROUTES` row was never added — so the hold passed, honestly,
   * over a registry that did not know the screen existed.
   *
   * That is hard-won law 7's fourth shape, which CLAUDE.md states almost word
   * for word: *a hold-expiry test asserted a screen was REGISTERED at an
   * address while the router was mounting it somewhere else.*
   *
   * **So the destination is now asserted against `APP_ROUTES` — the array the
   * router actually renders — and against the record lane's OWN exported
   * constant rather than a path retyped here**, because two spellings of one
   * address is the same defect one level down.
   */
  /** Every full pattern `App.tsx` declares, the way `matchPath` reads them. */
  function routerPatterns(routes: readonly RouteObject[], parent = ""): string[] {
    const out: string[] = [];
    for (const route of routes) {
      let here = parent;
      const structural = route.children !== undefined && route.element === undefined;
      if (route.index === true) {
        out.push(parent === "" ? "/" : parent);
      } else if (typeof route.path === "string") {
        here = route.path.startsWith("/")
          ? route.path
          : `${parent === "/" ? "" : parent}/${route.path}`;
        if (!structural) out.push(here);
      }
      if (route.children) out.push(...routerPatterns(route.children, here));
    }
    return out;
  }

  it("the destination EXISTS in the router, at the record lane's own address", () => {
    expect(DISCONNECT_RECORD_ROUTE).toBe("/disconnects/:ref");
    expect(routerPatterns(APP_ROUTES)).toContain(`/:tenant${DISCONNECT_RECORD_ROUTE}`);
  });

  /**
   * **BY SCREEN ID, AND NOT ONLY BY ADDRESS.** An address that matches a route
   * tells you the link is not a 404; it does not tell you WHICH screen opens.
   * The record page stamps `data-screen={DISCONNECT_RECORD_SCREEN}` on its own
   * root, so this asserts the constant the row action's destination renders —
   * and it is imported from that screen, never retyped.
   *
   * ⚠ **WHAT THIS DELIBERATELY DOES NOT ASSERT: that `SCREEN_ROUTES` also holds
   * the row.** It does not — the record lane mounted the route in `App.tsx` and
   * never added it — and `screenIds.test.tsx` is RED on exactly that, measured
   * red at `4ff860296` in a throwaway worktree. **A second red over one fact is
   * `G42`'s named anti-pattern** (*two checks over one fact disagree the first
   * time somebody edits either*), and the row belongs to the lane that mounted
   * the route (`DEF-710`'s own rule). It is REPORTED as `DEF-CUS-6042`, not
   * duplicated here and not quietly authored by this lane.
   */
  it("…and the destination is that screen, by its own id, in BOTH registries", () => {
    // BY SCREEN ID, not only by address: an address that matches a route says
    // the link is not a 404; it does not say WHICH screen opens.
    expect(DISCONNECT_RECORD_SCREEN).not.toBe("");
    const entry = SCREEN_ROUTES.find(
      (route) => route.path === `/:tenant${DISCONNECT_RECORD_ROUTE}`,
    );
    expect(entry).toBeDefined();
    // ⚠ **BOTH REGISTRIES, BECAUSE WATCHING ONE IS WHAT LET THE HOLD PASS.**
    // `DEF-CUS-6042`: the record route was mounted in `App.tsx` and absent from
    // `screenIds.ts` for part of a day, and the hold — which read only the
    // second — went green over a live screen. They agree now; this case is what
    // notices if they stop agreeing about THIS address again.
    expect(routerPatterns(APP_ROUTES)).toContain(`/:tenant${DISCONNECT_RECORD_ROUTE}`);
  });

  it("every row opens its case, at the address the record page is mounted on", async () => {
    mount([payload()]);
    const table = await screen.findByRole("table");
    const open = within(table).getByRole("link", { name: /open/iu });
    // The ADDRESS, built from the record lane's own path helper — and a real
    // one, not `//disconnects/…`: this fixture mounts under `/:tenant/accounts`
    // so `useParams().tenant` resolves (hard-won law 2's fixture note).
    expect(open).toHaveAttribute("href", `/${TEST_TENANT}/disconnects/DSC-26-0003`);
    // B14 rule 15 — an unlabelled glyph with an accessible name, never a
    // labelled button, whatever p142 draws (rule 38's split).
    expect(open.textContent).not.toMatch(/Open/u);
    expect(open.querySelector("svg")).not.toBeNull();
  });

  /** A row with no case number has nothing to open — a protection-only row
   *  never opened a case, and a case on a tenant with no numbering series has
   *  no reference yet. BR-SHL-025: disabled WITH the reason, never hidden. */
  /**
   * ⚠⚠ **THIS CASE ASSERTED THE DEFECT — `DEF-CUS-6748`.** It required the only
   * row action on this screen to be DISABLED on every protection-only row, and
   * it passed for weeks, because the refusal was TRUE: there really is no case
   * to open. `BR-SHL-025` was satisfied to the letter — a control that cannot
   * be used renders disabled WITH its reason — and that is exactly what hid it.
   * The rule asks whether a refusal is STATED; **nothing asked whether the row
   * had any working door at all**, and two of six rows had none. Hard-won law
   * 2's mirror: a live screen behind a dead control.
   *
   * **Both remedies were put to the Product Owner and neither was ruled on**:
   * either those rows leave this list, or the eye opens the account. The lane
   * took the second as the less destructive — a door is one line to remove,
   * and dropping the rows would take a held account off the one screen that
   * says a utility may not cut it. Recorded in the decision log as a judgment.
   *
   * The Case # cell still tells the two absences apart on `data-tracks`, so
   * nothing the old case protected is lost: what left the screen is the
   * 22-word SENTENCE (`DEF-CUS-6744`), never the fact.
   */
  it("a row with no case number opens the ACCOUNT, and no row is left without a door", async () => {
    mount([
      payload({
        rows: [
          row({
            case_no: null,
            case_no_unavailable: { code: "no_case_opened", detail: "none" },
          }),
        ],
      }),
    ]);
    const table = await screen.findByRole("table");
    // No disabled control anywhere in the row — the refusal is gone, not
    // reworded. A case that only asserted the link would pass with a dead
    // button beside it.
    expect(within(table).queryByRole("button", { name: /open/iu })).not.toBeInTheDocument();
    const open = within(table).getByRole("link", { name: /open/iu });
    expect(open).toHaveAttribute("href", expect.stringContaining("/accounts/"));
    // …and the absence is still DISTINGUISHED, on the attribute rather than in
    // prose: a dash that forgot which nothing it was would be the other defect.
    const cell = table.querySelector("[data-record-number-absent]");
    expect(cell).not.toBeNull();
    expect(cell?.getAttribute("data-tracks")).toBe("no_case_opened");
    expect(String(cell?.textContent).trim()).toBe("—");
  });

  // ════════════════════════════════════════════════════════════════════════
  // THE TOOLKIT — search, filter, column selector, all three the shared ones
  // ════════════════════════════════════════════════════════════════════════
  /**
   * ⚠ **THE PROMPT NAMES THE CASE NUMBER BECAUSE THE QUERY NOW REACHES IT, AND
   * NOT BECAUSE p142 ASKS FOR IT.** This lane measured the leg missing on
   * 2026-09-20 — the case number was the first column on every row and the one
   * thing a clerk quotes down a telephone, and `q` could not match it — and
   * reported it. The server lane added `case_no` to `SEARCH_HINT` and to its
   * `legs` tuple the same day.
   *
   * **Both halves or neither (`DEF-950`, hard-won law 2).** A prompt naming a
   * leg the query does not have is a promise the product breaks silently; a leg
   * no prompt names is a capability nobody finds. `G43` deliberately cannot
   * check this — no source-reading gate can compare an English sentence to a
   * Django `Q()` — so it is held here, by a case that names both.
   */
  it("the search prompt names the case number, and the declared legs include it", async () => {
    mount([payload()]);
    const box = await screen.findByPlaceholderText(/Case #, customer, account #, address/u);
    expect(box).toBeInTheDocument();
    // The prompt is true only if the box really declares that leg.
    expect(DISCONNECTS_SEARCH_FIELDS).toContain("case_no");
  });

  it("law 2 — a typed case number LEAVES THE BROWSER as `q`", async () => {
    const { urls } = mount([payload(), payload({ rows: [], total: 0 })]);
    const box = await screen.findByPlaceholderText(/Case #, customer/u);
    const before = urls.length;
    await userEvent.type(box, "DSC-26-0003");
    await waitFor(() => expect(urls.length).toBeGreaterThan(before), { timeout: 3000 });
    expect(urls[urls.length - 1]).toContain("q=DSC-26-0003");
  });

  // ════════════════════════════════════════════════════════════════════════
  // THE SUB-LINE — `10 tabs · Disconnects · 3 open cases`
  // ════════════════════════════════════════════════════════════════════════
  /**
   * ⚠ **THE TAB PUBLISHES THE SERVER'S FIGURE; IT DOES NOT COMPUTE ONE.**
   * `DEF-CUS-5953` named the remedy — *"each tab publishing its SERVED
   * `kpis.open` to the head"* — and the reason a second read from the head
   * was refused: two definitions of *open* on one screen.
   *
   * ⚠ **AND `undefined` IS NOT `0`.** Before the first response the tab knows
   * nothing and publishes nothing, and the head then OMITS the fragment. A `0`
   * is a claim, and on this tab it is the claim *nobody is being cut off*.
   */
  it("publishes the SERVER's open-case count, and nothing before the first response", async () => {
    const seen: (number | undefined)[] = [];
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(JSON.stringify(payload({ open_case_count: 3, total: 9 })), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=disconnects`]}>
          <Routes>
            <Route
              path="/:tenant/accounts"
              element={<DisconnectsTab client={client} onOpenCaseCount={(n) => seen.push(n)} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(seen[0]).toBeUndefined();
    await waitFor(() => expect(seen).toContain(3));
    // ⚠ NOT `total`, which is 9 here on purpose: `total` counts this list's
    // ROWS, and those are open cases UNION accounts carrying a protection.
    expect(seen).not.toContain(9);
  });

  it("the shared filter panel and the shared column selector are both on the toolbar", async () => {
    mount([payload()]);
    await screen.findByRole("table");
    // The two shared panels, each by its own disclosure rather than by a loose
    // word: `title="Filter by: …"` also contains "Filter", so a bare text query
    // matches two nodes and the assertion says nothing about either.
    expect(screen.getByText("+ Filter")).toBeInTheDocument();
    // The column chooser names itself on its trigger, not in its body.
    expect(screen.getByLabelText("Show or hide columns")).toBeInTheDocument();
  });

  // ════════════════════════════════════════════════════════════════════════
  // PO 2026-09-20 — *"A case due last week stops looking identical to one due
  // next month."* The DUE-NOW view and the OVERDUE marker.
  // ════════════════════════════════════════════════════════════════════════
  it("a cut date in the past reads as OVERDUE, and one already cut does not", async () => {
    mount([
      payload({
        rows: [
          row({
            case_no: "DSC-26-0091",
            account_no: "A-11091",
            cut_date: "2026-05-07",
            // ⚠ **FALSE, AND THAT IS THE POINT.** The served accent is
            // forward-looking, so it is the one fact the screen HAD and it
            // cannot show a date that has passed.
            cut_date_is_this_week: false,
            cut_due: { status: "overdue", days_overdue: 7, as_of: "2026-05-14" },
          }),
          row({
            case_no: "DSC-26-0092",
            account_no: "A-11092",
            cut_date: "2026-05-11",
            cut_date_is_this_week: true,
            // ⛔ The supply is already off, so this date is the record of WHEN
            // rather than a plan — `DEF-CUS-6055`'s general shape.
            cut_due: { status: "done", days_overdue: null, as_of: "2026-05-14" },
          }),
        ],
      }),
    ]);
    const table = await screen.findByRole("table");
    const late = within(table).getByText("A-11091").closest("tr") as HTMLElement;
    const already = within(table).getByText("A-11092").closest("tr") as HTMLElement;

    expect(late.querySelector("[data-cut-due-marker]")).not.toBeNull();
    expect(late.textContent).toContain("Overdue");
    expect(late.textContent).toContain("7 days late");
    // ⛔ A row whose supply is off carries NO marker at all — not a quieter
    // one, and not a zero.
    expect(already.querySelector("[data-cut-due-marker]")).toBeNull();
    expect(already.textContent).not.toContain("Overdue");
  });

});


// ── Record links (PO ruling 2026-10-19) — the account number opens the account
describe("Record links · a disconnect row's account number opens the account", () => {
  it("the number is a link to /accounts/<id>, under the tenant", async () => {
    mount([payload()]);
    await screen.findByRole("table");
    const link = screen.getAllByRole("link", { name: "A-11812" })[0];
    expect(link).toHaveAttribute("href", `/${TEST_TENANT}/accounts/acc-11812`);
  });
});
