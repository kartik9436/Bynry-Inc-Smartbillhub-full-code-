// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W7 task 7.11 — S90's FRONTEND cases. Written against B18
//           §5.8.1/§5.8.2/§5.8.5/§5.8.6, which declared them before this code
//           existed (r11 step 2c).
// Rules:    TC-DSC-6 (no notice is recorded — or rendered — as `emailed`) ·
//           TC-DSC-8 (`A-11507` owes $0.00 at tier `—` and is still on the tab)
//           · DEF-127 (an unreadable figure is never a zero) · OQ-374 (OPEN —
//           the segments and the chip) · OQ-366 (OPEN — no row names a party)
// ───────────────────────────────────────────────────────
//
// ⚠ **TWO CASES BELOW ASSERT THAT SOMETHING IS ABSENT FROM THE WHOLE RENDER,
// AND THAT IS THE ONLY HONEST FORM EACH CAN TAKE.**
//
//   · **TC-DSC-6** — the four delivery words must not appear ANYWHERE on the
//     tab. B18 draws the column and its own warning says the capability does
//     not exist. A test that asserted "the cell shows `—` when
//     `delivery_state` is null" would pass on a screen that printed `emailed`
//     the day a field went non-null.
//   · **OQ-366** — no row may name a chased party. J08 step 2b, verbatim: *"a
//     green assertion naming either party is a FAILURE."* So the case asserts
//     the SHAPE (`subject` stays null, the customer cell is the account's own
//     contact) rather than a party.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { defaultRequestState } from "@/components/tableTypes";

import {
  DisconnectsTab,
  LastNoticeCell,
  OwedCell,
  TierCell,
  chipToneClass,
  disconnectFilterGroups,
  disconnectsKpis,
  disconnectsQueryKey,
  disconnectsTableConfig,
} from "./DisconnectsTab";
import { listDisconnects } from "./worklistEndpoints";
import type { DisconnectList, DisconnectRow } from "./worklistEndpoints";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const CONFIG = disconnectsTableConfig(t, {
  // `CR-125-BRC07` — `actions` is REQUIRED rather than optional, and that is the
  // point: an optional cell nothing passes is hard-won law 2's dead UI, and this
  // column is the door onto the disconnect case record.
  actions: () => <span />,
  owed: () => <span />,
  tier: () => <span />,
  cutDate: () => <span />,
  lastNotice: () => <span />,
  state: () => <span />,
});

/** `disconnect_reads.SEGMENT_PRECEDENCE_UNRULED`, shortened to its sentence. */
const PRECEDENCE_UNRULED = {
  code: "segment_precedence_unruled",
  tracks: "OQ-374",
  br_ref: "B18 §5.8.2 · §5.8.3 · §5.8.6",
  detail:
    "B18 §5.8.2 draws six segments and they are NOT mutually exclusive. " +
    "`segment=all` is served and every other value is refused.",
};

/** `disconnects.DELIVERY_UNAVAILABLE`, shortened to its sentence. */
/** CR-039 wave D task 16 — `disconnects.CASE_NUMBER_UNAVAILABLE`, the server's
 *  own words, copied rather than paraphrased. */
const CASE_NUMBER_ABSENT = {
  code: "numbering_series_missing",
  series: "disconnect_case",
  open_question: "OQ-427",
  detail:
    "This case has no reference number yet. A number series for disconnections has not " +
    "been set up, so nothing has been issued — the case is on the ladder as normal and " +
    "only its reference is missing.",
};

/** `disconnect_reads.NO_CASE_TO_NUMBER` — the OTHER reason a reference cell is
 *  empty on this tab, and the whole reason it is a separate code: §5.8.6's HELD
 *  rows are here for a protection and never entered the ladder. */
const NO_CASE_OPENED = {
  code: "no_case_opened",
  detail:
    "This account is on the list because a protection is in force. No disconnection " +
    "case has been opened, so there is nothing to reference.",
};

const DELIVERY_UNAVAILABLE = {
  code: "delivery_adapter_absent",
  br_ref: "BR-NOT-005",
  detail:
    "There is no email, SMS or print adapter in this release, so `delivery_state` is " +
    "written NULL: a fabricated delivery state is what a utility shows a regulator " +
    "when a customer says they were never told.",
};

const NO_SCHEDULER = {
  code: "no_scheduler",
  tracks: "DEF-320",
  advances_on_a_schedule: false,
  detail: "no runner, job, queue or timer in this product reads a date and acts on it.",
};

// ⚠ RENAMED 2026-08-25 — DEF-716, in the SAME commit as the server's copy.
// This was `CUT_ACCRUAL_UNVERIFIED` / `cut_base_accrual_unverified`, and its
// detail read: *"Whether a CUT account keeps accruing its base charge is
// billing's behaviour and no rule in this packet states it."* That was true
// when written; **BR-CUS-103 (PO 2026-08-25, closing OQ-380, answer "no")
// settled it in the OPPOSITE direction — base charges STOP at the cut** — so a
// name implying doubt is now as wrong as the caption it guarded. The old
// spelling is kept here rather than deleted, the `disconnects.CUT_WILL`
// posture: a reader holding r10 or an old payload must be able to find it and
// be told it no longer binds.
//
// This is a FIXTURE of the server's constant
// (`apps/customers/disconnect_reads.CUT_ACCRUAL_CAPTION_SUPERSEDED`), so the
// two strings move together or this suite goes red — which is the check that
// kept the halves in step.
const CUT_ACCRUAL_CAPTION_SUPERSEDED = {
  code: "cut_accrual_caption_superseded",
  br_ref: "BR-CUS-103 (PO 2026-08-25, OQ-380) · B18 §5.8.1 · DEF-707 · DEF-716",
  // ⚠ THE DETAIL IS RENDERED COPY — it rides the tile's `title`. So it
  // DESCRIBES the superseded caption instead of quoting it: quoting it put the
  // false sentence back on the screen, and the guard four hundred lines below
  // (`expect(html).not.toContain("still accruing base charges")`) caught it.
  // The verbatim old wording lives in the comment above, which nobody renders.
  detail:
    "SUPERSEDED (BR-CUS-103 → base charges STOP at the cut). B18 drew this tile a caption " +
    "saying a cut account keeps accruing its base charge; the Product Owner ruled that it " +
    "does not, so that caption is not shown. This figure is a count of the cases whose " +
    "service is off, and nothing more — in particular it says nothing about what those " +
    "customers owe, because the reconnection fee does not yet reach the ledger (DEF-708).",
};

const LEDGER_UNREADABLE = {
  code: "ledger_publishes_no_per_account_ar_position",
  br_ref: "BR-CUS-015 · BR-REP-002 · DEF-127",
  detail: "what this customer owes cannot be read from the books.",
};

const SEGMENTS = [
  { code: "all", label: "All", supported: true, unavailable: null },
  { code: "at_notice", label: "At notice", supported: false, unavailable: PRECEDENCE_UNRULED },
  { code: "due_to_cut", label: "Due to cut", supported: false, unavailable: PRECEDENCE_UNRULED },
  { code: "on_hold", label: "On hold", supported: false, unavailable: PRECEDENCE_UNRULED },
  { code: "cut", label: "Cut", supported: false, unavailable: PRECEDENCE_UNRULED },
  {
    code: "reconnecting",
    label: "Reconnecting",
    supported: false,
    unavailable: PRECEDENCE_UNRULED,
  },
];

/** §5.8.6's `A-11812 · Bramble Bakery` — TIER 2, $2,410.00, notice sent. It is
 *  also OQ-374's own worked example. */
function row(over: Partial<DisconnectRow> = {}): DisconnectRow {
  return {
    account_id: "acc-11812",
    // CR-039 wave D task 16. The DEFAULT is the OQ-427 absence — what every
    // tenant sees today. A fixture defaulting to a number would leave the
    // absence path untested by accident, which is how a dash nobody looked at
    // ships (DEF-127's shape).
    case_no: null,
    case_no_unavailable: CASE_NUMBER_ABSENT,
    account_no: "A-11812",
    customer: "Bramble Bakery",
    address: "12 Foundry Row",
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
    cut_date: null,
    cut_date_is_this_week: false,
    last_notice: {
      issued_on: "2026-08-14",
      tier: "tier_2_10_day",
      // ⛔ NULL, ALWAYS. The writer writes it NULL and the reader reads it NULL.
      delivery_state: null,
      unavailable: DELIVERY_UNAVAILABLE,
    },
    state: {
      stored: "notice_sent",
      held_by: [],
      one_cell_is_unresolved: false,
      unavailable: null,
    },
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
      at_notice: 4,
      due_to_cut_this_week: 2,
      on_hold_protected: 3,
      cut_awaiting_payment: 1,
      cut_awaiting_payment_unavailable: CUT_ACCRUAL_CAPTION_SUPERSEDED,
      reconnections_due: 1,
      as_of: "2026-08-25",
    },
    page: 1,
    per: 50,
    total: 9,
    pages: 1,
    columns: [
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
    segments: SEGMENTS,
    // CR-045 wave D · D.8 — `disconnect_reads` serves BOTH on every response,
    // and they are different lists on purpose. `segments` is B18's six drawn
    // tabs (five unservable — OQ-374); `states` is `DISCONNECT_FILTER_STATES`,
    // the STORED case states `f.state` accepts. The panel reads the second.
    filters: ["state"],
    states: [
      { code: "notice_sent" },
      { code: "scheduled" },
      { code: "on_hold" },
      { code: "cut" },
      { code: "reconnecting" },
    ],
    chips: [
      { code: "tier_1_reminder", label: "TIER 1 · REMINDER", tone: "ink" },
      { code: "tier_2_10_day", label: "TIER 2 · 10-DAY", tone: "ink" },
      { code: "tier_3_48_hour", label: "TIER 3 · 48-HOUR", tone: "accent" },
      { code: "held_medical", label: "HELD · MEDICAL", tone: "grey" },
      { code: "held_payment_plan", label: "HELD · PAYMENT PLAN", tone: "grey" },
      { code: "held_weather_moratorium", label: "HELD · WEATHER MORATORIUM", tone: "grey" },
    ],
    search: {
      hint: "Customer, account #, address, or meter #…",
      legs: ["customer", "account_no", "address", "meter_no"],
    },
    delivery: DELIVERY_UNAVAILABLE,
    scheduler: NO_SCHEDULER,
    as_of: "2026-08-25",
    ...over,
  };
}

interface Render {
  html: string;
  urls: string[];
}

/**
 * ⚠ **THE SEGMENT STRIP LEFT THIS SCREEN AND THE HELPER THAT READ ONE SEGMENT
 * TAG WENT WITH IT (`DEF-CUS-3935`).** What it existed for is written down here
 * because the reasoning outlives the code, and it nearly shipped wrong twice:
 * a document-wide count of `disabled=""` could never see the rule it checked —
 * the column chooser alone renders four disabled Move-up / Move-down buttons,
 * so *"at least five disabled"* stayed TRUE with every segment switched ON. It
 * was proved by breaking it.
 *
 * **The assertion that replaced it is the stronger one, not a weaker one:**
 * `expect(html).not.toContain("data-segment=")` names the whole family rather
 * than one tag, so a segment that came back would fail it. `NewConnectsTab.
 * test.tsx` records the same finding from the other side.
 */

/**
 * CR-045 wave G · `DEF-1702` — the tab rendered with `state.filters` ALREADY
 * SET, which is the only way to see what the screen ASKS FOR.
 *
 * ⚠ **THE ASSERTION THAT MATTERS IS THE URL, NOT THE ROWS, AND THAT IS NOT A
 * WEAKER TEST — IT IS THE STRONGER ONE.** These lists are PAGED: the server
 * answers one window plus a `total`. A test that set a filter and counted the
 * rendered rows would pass just as happily on a screen that narrowed the page
 * in hand, which is the exact bug this dimension exists to avoid — a subset of
 * a subset, with an authoritative-looking total beside it. So the case asserts
 * that `f.state` LEAVES THE BROWSER, and a second case feeds back a payload
 * whose `total` moved to prove the screen reports the SERVER's count and not
 * `rows.length`.
 */
async function renderTab(
  body: DisconnectList | "unreadable",
  filters: Record<string, string> = {},
): Promise<Render> {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      urls.push(String(input));
      return body === "unreadable"
        ? new Response(JSON.stringify({ detail: "boom" }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          })
        : new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = { ...defaultRequestState(CONFIG), filters };
  try {
    await queryClient.prefetchQuery({
      queryKey: disconnectsQueryKey(state),
      queryFn: () =>
        listDisconnects(
          { q: state.q, page: state.page, per: state.per, filters: state.filters },
          client,
        ),
    });
  } catch {
    // An unreadable payload is one of the cases under test.
  }
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=disconnects`]}>
        <DisconnectsTab client={client} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { html, urls };
}

describe("S90 · the Disconnects tab (CR-030 W7 task 7.11)", () => {
  it("law 2 — the tab CALLS `GET /disconnects`; the endpoint is not merely mounted", async () => {
    const { urls } = await renderTab(payload());
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain("/disconnects");
    expect(urls[0]).toContain(TEST_TENANT);
  });

  it("CR-039 W-D 16 — with no series, the REFERENCE cell states why, and never shows a dash or a made-up id", async () => {
    const { html } = await renderTab(payload());
    expect(html).toContain("A number series for disconnections has not been set up");
    expect(html).toContain('data-record-number="disconnect"');
    expect(html).toContain('data-record-number-absent=""');
    expect(html).toContain('data-tracks="OQ-427"');
    // ⛔ No invented prefix. r10 draws a disconnection as `WO-4833` and B18
    // draws nothing; the screen must not settle OQ-427 by rendering either.
    expect(html).not.toMatch(/DSC-\d/);
    expect(html).not.toMatch(/WO-\d/);
  });

  it("⛔ CR-039 W-D 16 — a PROTECTION row says NOTHING WAS OPENED, not that numbering is missing", async () => {
    // §5.8.6's HELD rows: on this tab because a protection is in force, and
    // `case_payload` is null for them. Once rendered, one empty reference looks
    // exactly like the other and they say opposite things — one sends a clerk
    // to fix a settings problem that does not exist.
    const { html } = await renderTab(
      payload({
        rows: [row({ case_no: null, case_no_unavailable: NO_CASE_OPENED, case: null })],
      }),
    );
    expect(html).toContain("No disconnection case has been opened");
    expect(html).not.toContain("A number series for disconnections has not been set up");
    expect(html).toContain('data-tracks="no_case_opened"');
  });

  it("CR-039 W-D 16 — the moment a series exists the cell prints the number and drops the reason", async () => {
    const { html } = await renderTab(
      payload({ rows: [row({ case_no: "ZZPROBE-26-0001", case_no_unavailable: null })] }),
    );
    expect(html).toContain("ZZPROBE-26-0001");
    expect(html).not.toContain("A number series for disconnections has not been set up");
    expect(html).not.toContain('data-record-number-absent=""');
  });

  it("§5.8.2 — the eight drawn columns render §5.8.6's Bramble Bakery row", async () => {
    const { html } = await renderTab(payload());
    expect(html).toContain("A-11812");
    expect(html).toContain("Bramble Bakery");
    expect(html).toContain("TIER 2 · 10-DAY");
    // Hard rule 2 — the server's own 2-dp `display`, through the ONE money path.
    expect(html).toContain("$2,410.00");
  });

  // ── CR-045 wave G · B14 RULE 12 · THE `+ Filter ▾` PANEL IS ON THE TOOLBAR
  //    ROW, AND THE SEGMENT STRIP THAT USED TO BE HERE IS GONE (`DEF-1702`) ──
  //
  // ⚠ **WHAT THESE TWO CASES REPLACED, AND WHY THE REPLACEMENT IS STRICTER.**
  // They asserted that `WorklistSegments` rendered inside `.table-toolbar` and
  // that six segments were drawn with five DISABLED carrying their reason. Both
  // were true and both were GREEN on a screen with **no filter control at all**
  // — the strip's `onSelect` was `() => undefined`, so every one of its
  // enabled-ness assertions held over a control that could not narrow anything.
  // That is exactly how this screen was scored as *having* a filter twice while
  // having none (`DEF-1702`'s undercount). The order check is kept, pointed at
  // the control that now does the job; the disabled-segment check is replaced by
  // its own negation, so putting the dead strip back goes RED.
  it("B14 rule 12 — the `+ Filter` panel renders INSIDE the shared toolbar row", async () => {
    const { html } = await renderTab(payload());
    const toolbar = html.indexOf("table-toolbar");
    // `+ Filter ▾` is `FilterBar`'s own summary word — the control B14 rule 12
    // names, and the marker `def1702ServerFilters.test.tsx` already uses for
    // the four screens wave D wired.
    const panel = html.indexOf("+ Filter");
    const table = html.indexOf("<table");
    expect(toolbar).toBeGreaterThan(-1);
    expect(panel).toBeGreaterThan(-1);
    expect(table).toBeGreaterThan(-1);
    expect(toolbar).toBeLessThan(panel);
    expect(panel).toBeLessThan(table);
  });

  it("⛔ `DEF-1702` — the INERT segment strip is gone; nothing on this tab renders a control that ignores clicks", async () => {
    const { html } = await renderTab(payload());
    // The strip's own markers. `WorklistSegments` emitted both, and both are
    // asserted so that re-adding the component under a new name still fails.
    expect(html).not.toContain("data-worklist-segments");
    expect(html).not.toContain("data-segment=");
    // ⚠ **THE FIRST DRAFT OF THIS CASE ASSERTED THE SEGMENT WORDS AND WAS
    // WRONG, WHICH IS WORTH LEAVING WRITTEN DOWN.** It read
    // `expect(html).not.toContain("Due to cut")` — and `Due to cut this week`
    // is a KPI TILE on this very screen, so the case failed on chrome that has
    // nothing to do with the strip. Words that appear in more than one place
    // cannot carry a negative assertion; the two `data-` markers above are
    // emitted by `WorklistSegments` and by nothing else.
  });

  it("⛔ OQ-374 is UNTOUCHED — the payload still serves six segments and the route is still never asked for one", async () => {
    const { urls } = await renderTab(payload());
    // The screen no longer DRAWS them; it also never asks for one. A request
    // carrying `segment=` would meet `customers.disconnects.segment.unavailable`
    // and empty the tab — the "call the route to find out" the payload exists
    // to prevent, and the thing OQ-374 blocks.
    expect(urls).toHaveLength(1);
    expect(urls[0]).not.toContain("segment=");
  });

  it("⛔ TC-DSC-6 — no delivery claim appears anywhere on the tab", async () => {
    const { html } = await renderTab(payload());
    // ⚠ **THE COLUMN IS OFF BY DEFAULT SINCE `DEF-CUS-6745`**, so the CELL is
    // not in the default table. The guarantee TC-DSC-6 states is about the
    // whole tab and is if anything stronger for it: **no delivery claim
    // anywhere**, with the column hidden or shown. The `TIER · DATE` shape of
    // the cell itself is asserted in `DisconnectsListDrawing.dom.test.tsx`,
    // which turns the column on through the chooser to reach it.
    expect(html).not.toContain('data-last-notice=""');
    // ⛔ THE FOUR WORDS B18 DRAWS AND THIS PRODUCT CANNOT SUPPORT. There is no
    // map from a delivery state to a label anywhere in the tab's source, which
    // is what makes this assertion checkable rather than promised.
    for (const claim of ["emailed", "posted", "certified sent", "certified signed"]) {
      expect(html.toLowerCase()).not.toContain(claim);
    }
    // …and the reason a clerk expecting a channel is owed.
    // The marker rides on the CELL, which the hidden column does not render;
    // it is asserted where the cell is, in the drawing suite. What this case
    // owns is the tab-wide guarantee above.
  });

  it("⛔ DEF-127 — an unreadable OWED renders the reason, and never `$0.00`", () => {
    const html = renderToStaticMarkup(
      <OwedCell
        owed={{
          stored: null,
          display: null,
          currency: null,
          source: null,
          unavailable: [LEDGER_UNREADABLE],
        }}
      />,
    );
    expect(html).toContain("cannot be read from the books");
    expect(html).toContain('data-owed-absent=""');
    // On THIS tab a fabricated zero looks like an account nobody should chase.
    expect(html).not.toContain("0.00");
    expect(html).not.toContain("$");
  });

  it("TC-DSC-8 — a REAL `$0.00` renders as money, so the two absences cannot be confused", () => {
    // `A-11507` owes $0.00, is `Reconnecting` at tier `—`, and is on the tab
    // because a visit is due. That zero is a FIGURE; the case above is not.
    const html = renderToStaticMarkup(
      <OwedCell
        owed={{
          stored: "0.0000",
          display: "0.00",
          currency: "USD",
          source: "ledger",
          unavailable: null,
        }}
      />,
    );
    expect(html).toContain("$0.00");
    expect(html).not.toContain('data-owed-absent=""');
  });

  it("⛔ OQ-374 (the chip) — two applicable chips are BOTH rendered and flagged, never ranked", () => {
    const html = renderToStaticMarkup(
      <TierCell
        t={t}
        tier={{
          chips: [
            { code: "tier_2_10_day", label: "TIER 2 · 10-DAY", tone: "ink" },
            { code: "held_medical", label: "HELD · MEDICAL", tone: "grey" },
          ],
          ambiguous: true,
          unavailable: [
            {
              code: "more_than_one_chip_applies",
              tracks: "OQ-374",
              br_ref: "B18 §5.8.2 · §5.8.3",
              detail: "Which chip wins is stated by no rule, so every applicable chip is served.",
            },
          ],
        }}
      />,
    );
    // ⚠⚠ **THE PROTECTION CHIP LEFT THIS CELL ON 2026-09-25 AND NOTHING IS
    // HIDDEN — WHICH IS THE WHOLE TEST.** The old assertion was right on its
    // own terms: *dropping one would hide a protection from a screen that
    // authorises a cut*, and that was TRUE while the State column printed a
    // run-on of two state words and nothing else. It is false now. A held row
    // carries the `Held` badge AND names the protection under it
    // (`DisconnectStateBadge`), so the fact is said ONCE, in the column whose
    // question it answers — both drawings draw `—` in Tier on a held row.
    expect(html).toContain("TIER 2 · 10-DAY");
    expect(html).not.toContain("HELD · MEDICAL");
    // …and the AMBIGUITY note goes with it: a row that was "ambiguous" only
    // because a tier chip and a protection chip both applied is not ambiguous
    // HERE any more, and printing *two apply* over one visible chip would be a
    // note about something a clerk cannot see.
    expect(html).not.toContain('data-chips-ambiguous=""');
    // ⛔ **`OQ-374` IS UNTOUCHED AND THE SERVER STILL SERVES EVERY CHIP.** This
    // is a rendering choice on one screen, not a narrowing of the read: the
    // payload still carries the protection chips with `ambiguous` intact, and
    // the cell is handed all of them.
  });

  it("the TIER `—` says WHICH absence it is, and the two causes are distinguishable", () => {
    const noTier = renderToStaticMarkup(
      <TierCell
        t={t}
        tier={{
          chips: [],
          ambiguous: false,
          unavailable: [
            {
              code: "no_tier_reached",
              br_ref: "BR-CUS-039",
              detail: "no notice has been issued on this account, so it sits on no rung.",
            },
          ],
        }}
      />,
    );
    const unmapped = renderToStaticMarkup(
      <TierCell
        t={t}
        tier={{
          chips: [],
          ambiguous: false,
          unavailable: [
            {
              code: "unmapped_rung",
              br_ref: "BR-PAY-017 · B18 §5.8.2",
              detail: "this account sits on payments' `second_5_day` rung, which B18 draws no chip for.",
            },
          ],
        }}
      />,
    );
    expect(noTier).toContain('data-tier-absent="no_tier_reached"');
    expect(unmapped).toContain('data-tier-absent="unmapped_rung"');
    expect(noTier).not.toEqual(unmapped);
  });

  it("§5.8.2 — CUT DATE takes the accent when the SERVER says it is this week", async () => {
    const { html } = await renderTab(
      payload({
        rows: [row({ cut_date: "2026-08-26", cut_date_is_this_week: true })],
      }),
    );
    expect(html).toContain('data-cut-this-week="true"');
    expect(html).toContain("text-accent-700");
  });

  it("⛔ OQ-366 — no row names a chased party", async () => {
    const { html } = await renderTab(payload());
    // J08 step 2b: *"a green assertion naming either party is a FAILURE."* So
    // this asserts the SHAPE: the server serves `subject: null` on every row
    // and the screen renders no party field at all.
    expect(payload().rows.every((r) => r.subject === null)).toBe(true);
    expect(html).not.toContain("data-chase-subject");
    // The CUSTOMER column is a fact about the row — the account the debt was
    // measured on — and never a claim about who is being pursued.
    expect(html).toContain("Bramble Bakery");
  });

  it("§5.8.1 — the five drawn figures reach the strip, and the CUT tile does not print its caption as fact", async () => {
    const tiles = disconnectsKpis(payload(), t);
    // ⚠ **THE ORDER IS p142's FROM `CR-125-BRC07`, AND IT MOVED TWO TILES.**
    // The drawing reads `AT NOTICE · DUE TO CUT · CUT, AWAITING RECONNECT ·
    // ON HOLD · RECONNECTIONS`; this strip had `on-hold` third and
    // `cut-awaiting` fourth. The FIGURES are unchanged and still §5.8.6's —
    // `4 · 2 · 1 · 3 · 1` is the same five numbers against the same five tiles,
    // read in the drawn sequence.
    // ⚠ **THE ORDER MOVED AGAIN ON 2026-09-25 AND THE FIGURES DID NOT.** p142
    // reads `AT NOTICE · DUE TO CUT · CUT, AWAITING RECONNECT · ON HOLD ·
    // RECONNECTIONS`; the redesign drawing reads `NOTIFIED · SCHEDULED · OFF ·
    // PAID · HELD`, which moves HELD to the end. Same five served numbers,
    // read in the newly drawn sequence — `4 · 2 · 1 · 1 · 3`.
    expect(tiles.map((tile) => tile.id)).toEqual([
      "at-notice",
      "due-to-cut",
      "cut-awaiting",
      "reconnections",
      "on-hold",
    ]);
    expect(tiles.map((tile) => ("value" in tile ? tile.value : null))).toEqual([4, 2, 1, 1, 3]);
    const { html } = await renderTab(payload());
    // ⛔ B18 §5.8.1 writes *"still accruing base charges"* and calls it a money
    // statement. **SUPERSEDED (BR-CUS-103, PO 2026-08-25 → base charges STOP at
    // the cut.)** This assertion used to be justified by *"no rule states it"*,
    // which was true when it was written; a rule states it now, and it states
    // the OPPOSITE (DEF-716) — so the caption must not be printed because it is
    // FALSE, not because it is unverified. Same assertion, better reason.
    expect(html).not.toContain("still accruing base charges");
    // The drawing's caption for the OFF tile, and it is true at every value.
    expect(html).toContain("Service disconnected");
  });

  it("the filter panel offers NOTHING before the first response, and the SERVER's states after it", () => {
    // Before a response the screen does not yet know which states this tenant's
    // list can hold. An empty group is DROPPED by `offerableFilters` rather than
    // drawn as a legend over nothing (`DEF-782`).
    expect(disconnectFilterGroups(undefined, t)[0].options).toEqual([]);
    // After it, the options are `payload.states` — the SERVER's
    // `DISCONNECT_FILTER_STATES`, which is `CASE_STATES` minus the codes that
    // take a row off this list. Nothing is typed on this side (BR-SHL-010).
    const served = disconnectFilterGroups(
      [{ code: "cut" }, { code: "notice_sent" }],
      t,
    )[0];
    expect(served.name).toBe("state");
    expect(served.options.map((option) => option.value)).toEqual(["cut", "notice_sent"]);
    // ⚠ **NOT the six drawn SEGMENTS.** `on_hold` is computed from the account's
    // protections and is not a stored state; offering it here would be answering
    // OQ-374 by rendering.
    expect(served.options.map((option) => option.value)).not.toContain("on_hold");
    // ⚠ **THE THREE THE SERVER OFFERS AND THIS MAP USED TO MISS**
    // (`DEF-CUS-6053`). A clerk read `closed_out`, `in_progress_draft` and
    // `parked` in this panel. The map is asserted COMPLETE against the
    // server's own vocabulary in `disconnectStateLabels.test.ts`; this case
    // pins the three words a person actually reads here.
    const eight = disconnectFilterGroups(
      [
        { code: "closed_out" },
        { code: "in_progress_draft", label: "Draft" },
        { code: "parked", label: "Parked" },
      ],
      t,
    )[0];
    // ⚠ **`Closed out` BECAME `Closed` WITH THE SIX CLERK WORDS.** It is the
    // SEVENTH state and the six do not cover it; folding it onto one of them
    // would say something false, so it keeps a word of its own. REPORTED.
    expect(eight.options.map((option) => option.label)).toEqual(["Closed", "Draft", "Parked"]);
    // ⛔ **THIS ASSERTED THE OPPOSITE UNTIL `DEF-CUS-6053`** — *"a code the
    // label map has never seen renders as ITSELF — ugly and visible"*, which
    // encoded the defect as the contract. A code on screen is not
    // ugly-and-visible; it looks deliberate, it is never blank, and no gate in
    // this repo reads clerk-facing copy. It now states an absence and writes a
    // `console.error` naming the code.
    const said: string[] = [];
    const real = console.error;
    console.error = (...args: unknown[]) => void said.push(String(args[0]));
    try {
      const unknown = disconnectFilterGroups([{ code: "zz_new_state" }], t)[0];
      expect(unknown.options[0].label).toBe("Not named yet");
      expect(unknown.options[0].label).not.toBe("zz_new_state");
      // The VALUE is still the code — it is what `f.state=` posts, and B14
      // rule 31 is about what a person READS, never about what a form sends.
      expect(unknown.options[0].value).toBe("zz_new_state");
    } finally {
      console.error = real;
    }
    expect(said).toHaveLength(1);
    expect(said[0]).toContain("zz_new_state");
  });

  it("CR-045 wave G — `f.state` LEAVES THE BROWSER, which is the only thing that makes this a filter", async () => {
    // ⚠ **THE URL IS THE ASSERTION AND THE ROW COUNT IS NOT.** This list is
    // PAGED: `/disconnects` answers one window plus a `total`. A case that set
    // a filter and counted rendered rows would pass on a screen that narrowed
    // the page in hand — a subset of a subset with an authoritative total
    // beside it, which is worse than no control (`DEF-1702`).
    const { urls } = await renderTab(payload(), { state: "cut" });
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain("f.state=cut");
    // BR-SHL-011's grammar, not a bare `?state=`.
    expect(urls[0]).not.toMatch(/[?&]state=cut/);
  });

  it("an EMPTY filter value is an ABSENT dimension, never `f.state=`", async () => {
    // `FilterBar.setFilter` deletes the key on a chip ✕, but a caller may still
    // hand through `""` — an empty `f.state` is a value the server would try to
    // match, and it would answer nothing.
    const { urls } = await renderTab(payload(), { state: "" });
    expect(urls[0]).not.toContain("f.state");
  });

  it("the query key carries the filters, or the filtered request is answered from the unfiltered cache", () => {
    const base = defaultRequestState(CONFIG);
    expect([...disconnectsQueryKey(base)]).not.toEqual([
      ...disconnectsQueryKey({ ...base, filters: { state: "cut" } }),
    ]);
  });

  it("the chip tones are the server's decision, applied and not re-derived", () => {
    expect(chipToneClass("accent")).toContain("accent");
    expect(chipToneClass("grey")).toContain("neutral");
    // An unrecognised tone must never make a chip disappear.
    expect(chipToneClass("nonsense")).toBe(chipToneClass("ink"));
  });

  it("a notice-less row draws `—` and still carries the delivery reason", () => {
    const html = renderToStaticMarkup(
      <LastNoticeCell
        t={t}
        timeZone="UTC"
        dateFormat="MM/DD/YYYY"
        notice={{
          issued_on: null,
          tier: null,
          delivery_state: null,
          unavailable: DELIVERY_UNAVAILABLE,
        }}
      />,
    );
    expect(html).toContain('data-notice-none=""');
    // ⛔ DEF-742 — was `"no email, SMS or print adapter"`, the server's own
    // `detail`. The dash now carries the reader's sentence about the same fact.
    expect(html).toContain("How a notice reached the customer is not recorded");
    expect(html).not.toContain("BR-NOT-005");
  });

  /**
   * ⚠ **INVERTED 2026-08-25 (lane W7WIZ) FOR THE REASON THE TRANSFERS TAB'S
   * TWIN CARRIES.** This asserted the CTA was disabled with *"the disconnect
   * flow is not built yet"*, which was right while `DSC-02` had no route and
   * became a test pinning a falsehood the moment it did. ⚠ And the old case's
   * parenthetical — *"a danger commit onto nothing is worse"* — was correct
   * about the danger and wrong about what this button does: the flow it opens
   * SCHEDULES a cut and never performs one, so the destructive act is
   * `commit_cut` on the date and not this click.
   */
  it("law 2 — the empty state's CTA is live and no longer claims the flow is unbuilt", async () => {
    const { html } = await renderTab(payload({ rows: [], total: 0, pages: 0 }));
    expect(html).toContain("Nobody is on the ladder");
    expect(html).toContain("Start a disconnect");
    expect(html).not.toContain("not built yet");
  });

  // ── `BR-CUS-1046` (PO 2026-09-10, EXTENDED 2026-09-12) ────────────────────
  // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-12, AND IT WAS RIGHT AT
  // THE TIME.** It was named *"no column is sortable"* and it held the line
  // correctly for as long as the server took no `sort`: a sort control over a
  // fixed order is a live button that does nothing (hard-won law 2).
  //
  // `OQ-CUS-1790` measured that on six of this screen's eight lists and the PO
  // ruled option (c), verbatim: ***"All eight open newest-first and the six
  // gain a sort control. Largest job: six server-side sorts."*** So the
  // assertion is INVERTED rather than deleted, and the pair it now checks is
  // the pair that can rot apart: a `sortable` column with no server sort behind
  // it is the old defect, and a server sort no column offers is the mirror.
  it("gains ONE sort control, and the order is still deliberately not urgency", () => {
    const sortable = CONFIG.columns.filter((column) => column.sortable === true);
    // ⚠ **ONE, AND THE SHORTNESS IS THE POINT.** `disconnect_reads.SORTS` holds
    // `created` and `account_no` and nothing else: `cut_date` and `tier` are
    // per-CASE, this list is a UNION of open cases and protected accounts, and
    // §3's segment precedence is still unruled. Offering a tier sort would be
    // this screen inventing the ranking the read model refuses to take.
    expect(sortable.map((column) => column.key)).toEqual(["account_no"]);
    expect(CONFIG.defaultSort).toEqual({ sort: "created", dir: "desc" });
  });

  it("a failed read never renders the empty state — that would assert 'nobody is on the ladder'", async () => {
    const { html } = await renderTab("unreadable");
    expect(html).not.toContain("Nobody is on the ladder");
  });

  /**
   * ⚠ **G27 IS RED ON THIS FILE BY CONSTRUCTION, AND THIS IS THE ASSERTION THAT
   * SAYS WHAT THAT RED DOES AND DOES NOT MEAN.**
   *
   * G27 exists because the PO photographed a deployed panel whose heading read
   * `notifications.rights.title` — a screen rendering its own source code. It
   * finds every LITERAL `t("some.key")` whose key no catalogue defines, and it
   * reports 27 of them here, because a lane may not write the shared
   * catalogues and this tab's keys are handed over rather than merged.
   *
   * **What G27 cannot see is `defaultValue`.** Every call site in this tab
   * supplies one, so nothing renders a dotted key at a person — which is the
   * harm G27's own message claims. This case is the proof, and it is the thing
   * that must go red if a future edit drops a `defaultValue`: a key with no
   * fallback and no catalogue entry renders itself.
   *
   * **A DEFECT IS OWED ON THE GATE, not on this file:** G27's message says
   * *"Each renders its own key name to a user"*, and for a call site carrying a
   * `defaultValue` that sentence is false. Its own header already records the
   * correct rule for dynamic keys — *"most such call sites already pass a
   * `defaultValue`, which is the correct pattern"* — and the same reasoning
   * applies to a literal one.
   */
  it("no raw translation key reaches the screen — every call site carries a defaultValue", async () => {
    const { html } = await renderTab(payload());
    // The families this tab names. A miss renders as the dotted key itself.
    expect(html).not.toMatch(/customers\.(newConnects|transfers|disconnects)\.[a-zA-Z0-9_.]+/);
  });

  it.todo(
    "TC-DSC-9 (isolation): tenant B's `GET /disconnects` returns none of tenant A's — RLS FORCE is the guarantee and it is asserted server-side, never through a mocked client seam",
  );
  it.todo(
    "TC-DSC-1..5 and TC-DSC-7 are LADDER cases (a payment stops it, a plan freezes it, a break resumes it, the two refusals, the danger-tier commit) with no surface on this tab — the five-step flow is not built",
  );
  it.todo(
    "the segment strip FILTERS once OQ-374 closes — while `all` is the only value served there is no filter to assert, and a test that asserted one would pin a rule nobody has made",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W7 task 7.11 (S90) · B18 §5.8 · OQ-374 · OQ-366 · DEF-127 ·
//         TC-DSC-6 · TC-DSC-8
// generated: 2026-08-25 by lane F-TABS
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E4 TC-DSC-9 is a server/RLS claim a mocked seam cannot prove ·
//         E4 TC-DSC-1..5 and TC-DSC-7 are ladder/write cases with no surface on
//         this tab · E4 the segment FILTER cannot be asserted while OQ-374 is
//         open
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
