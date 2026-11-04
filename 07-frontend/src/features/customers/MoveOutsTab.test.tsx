// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W5 — the Move-outs tab's FRONTEND cases. Written against B18
//           §5.6.1 / §5.6.2 / §5.6.4 / §5.6.6 / §5.6.7 (r11 step 2c).
// Rules:    BR-CUS-030 · BR-CUS-031 (billing publishes no final bill) ·
//           BR-CUS-057 (deposit interest — CONFIRMED, NOT BUILT) · BR-CUS-081 /
//           BR-CUS-082 (the two ruled landings) · BR-SHL-046 (SIX steps, not
//           four) · DEF-127 (never a fabricated zero) · DEF-332
// ───────────────────────────────────────────────────────
//
// ⚠ **THE TWO CASES THIS FILE EXISTS FOR ARE BOTH NEGATIVE.**
//
//   1. `no landing word is rendered on any row`. §5.6.2 draws `SHORT $175.20`
//      in the accent and §5.6.4 forces a FOUR-WAY DECISION off the back of that
//      word — pursue it, recover from another account, write it off, or move it
//      to the master. A `SHORT` this screen guessed would put a customer into
//      BR-CUS-082's restarted collections ladder on a figure nobody computed.
//   2. `the three undecidable tiles never render 0`. DEF-127 pointed at a KPI
//      strip: `REFUNDS TO PAY · 0` says nobody is owed their deposit back, and
//      it reads as good news to the one person paid to act on the bad kind.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { defaultRequestState } from "@/components/tableTypes";

import {
  MoveOutsTab,
  listMoveOuts,
  moveOutFilterGroups,
  moveOutsKpis,
  moveOutsQueryKey,
  moveOutsTableConfig,
} from "./MoveOutsTab";
import type { MoveOutList, MoveOutRow } from "./MoveOutsTab";
// p117's doors are asserted by ADDRESS and by the SCREEN they open — hard-won
// law 2's mirror. Both constants come from the page itself so a router change
// cannot leave this file asserting an address nothing is mounted at.
import { MOVE_RECORD_ROUTE, MOVE_RECORD_SCREEN, moveRecordPath } from "./MoveRecordPage";
import { resumePath } from "./parkedDrafts";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const CONFIG = moveOutsTableConfig(t, {
  // `DEF-CUS-5994` — the parked draft's state cell. A STUB, for the reason the
  // routed ones beside it are stubs: the real one needs the tenant's date
  // format and the translator, and a config case must not mount a page to get
  // them.
  draftState: () => <span />,
  moveOutDate: () => <span />,
  settlement: () => <span />,
  // p117's three routed cells. The config takes no router, which is why they
  // are passed in — see `moveOutsTableConfig`'s own note.
  reference: () => <span />,
  accountLink: () => <span />,
  openRecord: () => <span />,
});

/** The rendered TEXT — tags and attributes stripped. See `MoveInsTab.test.tsx`
 *  for why a naive `html.includes` cannot answer these questions: the refusal
 *  sentences QUOTE the words they forbid, and DEF-332 puts every tracking id in
 *  an attribute precisely so it is not in the copy. */
function visibleText(html: string): string {
  return html.replace(/<[^>]*>/g, " ");
}

/** `move_out_settlement.GAP_REASONS[GAP_FINAL_BILL]`, as the server sends it —
 *  and note it contains the phrase "final-bill", which is why the landing
 *  assertions below run over `visibleText` and not the raw markup. */
const FINAL_BILL_ABSENT = {
  code: "final_bill_not_stated",
  br_ref: "BR-CUS-031 · US-BIL-011",
  detail:
    "billing publishes no per-account final-bill total, so the left-hand column of B19 " +
    "§15.9.0 cannot be read from here and the caller must state it.",
};

const DEPOSIT_INTEREST_ABSENT = {
  code: "deposit_interest_not_accrued",
  br_ref: "BR-CUS-057 · US-CUS-023 §7 · GT-61",
  detail: "the accrual engine is customers' own and is NOT BUILT.",
};

const NO_STORE_BEFORE_CLOSE = {
  code: "move_out_before_close_has_no_store",
  br_ref: "BR-CUS-030",
  detail:
    "A move-out that has not committed yet is not recorded anywhere. `accounts` carries no " +
    "`scheduled_move_out_on`, no move-out state and no step.",
};

const READS_ABSENT = {
  code: "unit_reads_not_readable_from_customers",
  br_ref: "B1 · BR-MET-036",
  detail: "customers publishes no metering read seam.",
};

/** ⚠ **THE SERVER'S SENTENCE, VERBATIM — `RecordNumberCell` RENDERS `detail`
 *  TO A CLERK**, which is the established posture for this one absence family
 *  (`MOVE_JOB_PREDATES_THE_RECORD` is written the same way). A shortened stub
 *  here would make the case pass over copy nobody had read. */
const NO_PARKED_REFERENCE = {
  code: "parked_move_out_has_no_reference",
  br_ref: "BR-CUS-150 · BR-SHL-048",
  detail:
    "This move-out has not finished, so it has no number yet. A number is given when it " +
    "completes, and nothing that was typed is lost in the meantime.",
};

const NO_PARKED_SETTLEMENT = {
  code: "parked_move_out_has_no_settlement",
  br_ref: "BR-CUS-030 · BR-SHL-048",
  detail: "nothing is settled until the account closes.",
};

/** ⚠ **THE MOVE-OUT TAB'S OWN CODE SINCE 2026-09-19.** A closed move-out and a
 *  draft move-in have no step for two different reasons; one sentence stretched
 *  over both is what let the move-outs half go stale. */
const STEP_ABSENT = {
  code: "closed_move_out_has_no_step",
  br_ref: "BR-CUS-030 · BR-SHL-046",
  detail: "how many steps somebody walked to finish it was not written down.",
};

/** §5.6.7's `A-11340 · Northwind Mfg. · 77 Industrial Way` — the row that also
 *  appears on the Accounts tab and the Disconnects tab. One account, three
 *  tabs, consistent. */
function row(over: Partial<MoveOutRow> = {}): MoveOutRow {
  return {
    // CR-039 wave D 17–19 — every closed account has left a numbered record
    // since 2026-08-27, so the DEFAULT row carries one; the two absences are
    // set per-case by the tests that are about them.
    move_no: "MVO-26-0001",
    move_no_unavailable: null,
    // PO ruling 2026-09-19 — the list holds two kinds of row. The DEFAULT is a
    // move-out that happened; `parkedRow()` below is the other one.
    row_kind: "account",
    park_id: null,
    waiting_on: null,
    park_note: null,
    remind_on: null,
    parked_at: null,
    age_days: null,
    account_id: "acc-11340",
    account_no: "A-11340",
    account_absence: null,
    customer: "Northwind Mfg.",
    customer_no: "C-01340",
    customer_source: "customer_entity",
    customer_absence: null,
    unit_id: "u-9",
    unit: "77 Industrial Way",
    move_out_date: "2026-09-12",
    move_out_date_absence: null,
    step: { reached: null, of: 6, unavailable: STEP_ABSENT },
    // ⚠ **SERVED, 2026-08-26 (CR-038 W9 · DEF-786)** — and the row carries
    // B18 §5.6.2's amber THIRD state, which the settlement's own stored flag
    // (`accounts.final_read_state`) is now the one thing allowed to say.
    final_read: {
      state: "estimated",
      measured_against: "2026-09-12",
      meters_total: 1,
      meters_read: 1,
      missing: [],
      unavailable: null,
    },
    settlement: {
      currency: "USD",
      landing: null,
      landings: ["settled", "refund_due", "short", "refused_other_debt", "refused_excess"],
      complete: false,
      sentence: null,
      deposit_held: { stored: "150.0000", display: "150.00" },
      deposit_interest: null,
      // DEF-127's own figure — the account that owed $108.88 and was rendered
      // $0.00 on the one screen a clerk opens to find out.
      outstanding: { stored: "108.8800", display: "108.88" },
      outstanding_source: "ledger",
      unavailable: [FINAL_BILL_ABSENT, DEPOSIT_INTEREST_ABSENT],
    },
    state: "closed",
    leaving_this_week: false,
    ...over,
  };
}

/** PO ruling 2026-09-19, verbatim **`yes`** — a move-out that has NOT finished.
 *
 *  This is the Accounts blueprint p117's drawn second row, `MVO-26-0087 ·
 *  2 of 6 · In progress`, in the shape the server actually serves it: a real
 *  step, a real account, and a NAMED absence wherever a draft genuinely cannot
 *  answer — no reference, no settlement. */
function parkedRow(over: Partial<MoveOutRow> = {}): MoveOutRow {
  return row({
    row_kind: "parked_move_out",
    park_id: "park-0087",
    move_no: null,
    move_no_unavailable: NO_PARKED_REFERENCE,
    account_id: "acc-11602",
    account_no: "A-11602",
    account_absence: null,
    customer: "Ncube, T.",
    customer_no: "C-01602",
    unit: "1408 Elm · Unit E",
    move_out_date: "2026-05-09",
    move_out_date_absence: null,
    step: { reached: 2, of: 6, unavailable: null },
    final_read: {
      state: "due",
      measured_against: "2026-05-09",
      meters_total: 1,
      meters_read: 0,
      missing: ["M-4402"],
      unavailable: null,
    },
    settlement: {
      currency: "USD",
      landing: null,
      landings: ["settled", "refund_due", "short", "refused_other_debt", "refused_excess"],
      complete: false,
      sentence: null,
      deposit_held: { stored: null, display: null },
      deposit_interest: null,
      outstanding: { stored: null, display: null },
      outstanding_source: null,
      unavailable: [NO_PARKED_SETTLEMENT],
    },
    state: "in_progress",
    waiting_on: null,
    parked_at: "2026-09-14T09:00:00Z",
    age_days: 5,
    ...over,
  });
}

function payload(over: Partial<MoveOutList> = {}): MoveOutList {
  return {
    rows: [row()],
    kpis: {
      open: 5,
      open_means: "closed_and_not_yet_finally_billed",
      open_unavailable: NO_STORE_BEFORE_CLOSE,
      leaving_this_week: 1,
      // ⚠ DERIVED NOW (DEF-786): the seam answers, so the tile draws a FIGURE.
      final_reads_due: 3,
      final_reads_due_unavailable: null,
      final_reads_due_means: "closed_move_outs_with_a_meter_unread_since_close",
      final_reads_due_meterless: 1,
      shortfalls_to_decide: null,
      shortfalls_to_decide_unavailable: FINAL_BILL_ABSENT,
      refunds_to_pay: null,
      refunds_to_pay_unavailable: FINAL_BILL_ABSENT,
      period_basis: "tenant_today",
      as_of: "2026-08-25",
    },
    page: 1,
    per: 50,
    total: 5,
    pages: 1,
    columns: [
      // CR-039 wave D 17–19 — the ninth column, and it LEADS. §5.6.2's eight
      // follow it unchanged.
      "reference",
      "account",
      "customer",
      "unit",
      "move_out_date",
      "step",
      "final_read",
      "settlement",
      "state",
    ],
    states: [
      { code: "closed", label: "Closed", drawn: false, supported: true, unavailable: null },
      {
        code: "scheduled",
        label: "Scheduled",
        drawn: true,
        supported: false,
        unavailable: NO_STORE_BEFORE_CLOSE,
      },
      {
        code: "in_progress",
        label: "In progress",
        drawn: true,
        supported: false,
        unavailable: NO_STORE_BEFORE_CLOSE,
      },
      {
        code: "waiting",
        label: "Waiting",
        drawn: true,
        supported: false,
        unavailable: NO_STORE_BEFORE_CLOSE,
      },
    ],
    // CR-045 wave D · D.10 — the served `f.<name>` vocabulary and its buckets.
    // ⚠ **`filters` IS `closed` AND NOT `state`, WHICH IS THE FINDING.** Only
    // ONE of the four `states` above is `supported`, so a state filter would
    // offer a single option that changes nothing (B14 rule 9). `closed_at` is
    // the one stored, filterable fact this list holds.
    filters: ["closed"],
    closed_windows: [
      { code: "last7", days: 7 },
      { code: "last30", days: 30 },
      { code: "last90", days: 90 },
    ],
    search: {
      hint: "Customer, account #, unit, or address…",
      min_chars: 2,
      legs: ["customer", "account_no", "unit", "address"],
      unavailable: [
        {
          code: "move_out_has_no_request_link",
          br_ref: "BR-CUS-080",
          detail: "a move-out creates no child, so `link_child` has no reference to write.",
        },
      ],
    },
    exclusion: {
      callout:
        "A transfer appears only here. Its two halves are deliberately kept out of " +
        "Move-ins and Move-outs — the same job listed three times would be counted three times.",
      contract: ["transfer_half_account_ids"],
      half_account_ids: ["acc-9001"],
    },
    unavailable: [
      NO_STORE_BEFORE_CLOSE,
      {
        code: "move_out_window_has_no_closing_edge",
        br_ref: "BR-CUS-031 · US-BIL-011",
        detail: "nothing takes a row off this list, because there is no final bill to reach.",
      },
    ],
    as_of: "2026-08-25",
    ...over,
  };
}

/**
 * CR-045 wave G · `DEF-1702` — the tab rendered with `state.filters` set.
 *
 * ⚠ **THE URL IS THE ASSERTION AND THE ROW COUNT IS NOT.** `/move-outs` is
 * PAGED and `move_outs_queryset` applies `f.closed` BEFORE paging, so a case
 * that counted rendered rows would pass on a screen narrowing the page in hand.
 */
async function renderTab(
  body: MoveOutList,
  filters: Record<string, string> = {},
): Promise<{ html: string; urls: string[] }> {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      urls.push(String(input));
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = { ...defaultRequestState(CONFIG), filters };
  await queryClient.prefetchQuery({
    queryKey: moveOutsQueryKey(state),
    queryFn: () =>
      listMoveOuts(
        { q: state.q, page: state.page, per: state.per, filters: state.filters },
        client,
      ),
  });
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      {/* ⚠ **MOUNTED UNDER THE REAL `/:tenant/accounts` PATTERN, NOT BARE
          (2026-09-19).** `useTenantPath` reads the tenant off `useLocation()`
          rather than `useParams()`, so this fixture happened to resolve one
          before p117's three doors existed — and hard-won law 2's own record is
          a portal fixture that mounted bare, left `tenant` undefined and let
          every address render `//portal/…`, a protocol-relative URL to another
          host that `toContain` reads as a perfectly good string. The pattern is
          declared so the fixture can never drift into answering that way. */}
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=move-outs`]}>
        <Routes>
          <Route path="/:tenant/accounts" element={<MoveOutsTab client={client} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { html, urls };
}

/** The `href` of the ONE tag carrying `marker`, or `null`.
 *
 * ⚠ **READ THE MARKED TAG, NEVER THE PAGE (`bc4aea692`'s red proof).** The
 * sibling Move-ins lane wrote its three door cases as
 * `toContain('href="/brazosbend/moves/…"')` — an address SOMEWHERE on the
 * page — and a row carries TWO controls pointing at the same record, so
 * stripping `tenantPath` from one of them left the string supplied by the
 * other and all three passed green over a link rendering `/moves/MVI-26-0114`.
 * Each assertion below reads the href out of the tag it is about. */
/** The word inside the STATE cell of the first row — the tag this file owns,
 *  never the page.
 *
 *  ⚠ **`Closed` IS LEGITIMATELY ON THIS SCREEN TWICE OVER** — the `f.closed`
 *  filter is named `Closed` and the OPEN tile's caption reads *"closed, not yet
 *  finally billed"*. So a page-wide `not.toContain("Closed")` is red over a
 *  correct screen, and a page-wide `toContain("Completed")` is green over a
 *  state cell that still says the old word. Both are the `hrefOf` lesson one
 *  column over. */
function stateWordOf(html: string): string | null {
  return (
    /data-move-out-state="[^"]*"><span[^>]*>([^<]*)</.exec(html)?.[1]?.trim() ?? null
  );
}

/**
 * ⚠ **THE MARKER MOVED ONTO A WRAPPER ON 2026-09-25 (`DEF-CUS-6759`), SO THIS
 * READS THE FIRST `<a>` INSIDE IT RATHER THAN THE MARKED ELEMENT ITSELF.** The
 * row action is a `RowActionLink` now, and that component takes a fixed shape
 * and spreads nothing — a `data-*` handed to it typechecks, renders nowhere,
 * and is asserted on by a test that cannot find it. So the tab stamps the
 * marker on a `<span>` it owns, exactly as `ParkedDraftActions` already does,
 * and the address under test is the anchor the span contains.
 */
function hrefOf(html: string, marker: string): string | null {
  // The marker ON the anchor — the reference and the account cells.
  const own = new RegExp(`<a[^>]*\\b${marker}="[^"]*"[^>]*>`).exec(html)?.[0] ?? "";
  if (own !== "") {
    return /href="([^"]*)"/.exec(own)?.[1] ?? null;
  }
  // The marker on a WRAPPER — the ACTIONS cell, since `DEF-CUS-6759`. Slice
  // from the END of the marked opening tag, so the first `<a>` found is the
  // one INSIDE the span and never the span's own tag.
  const at = new RegExp(`\\b${marker}="[^"]*"[^>]*>`).exec(html);
  if (at === null) {
    return null;
  }
  const tag = /<a[^>]*>/.exec(html.slice(at.index + at[0].length))?.[0] ?? "";
  return /href="([^"]*)"/.exec(tag)?.[1] ?? null;
}

describe("the Move-outs tab (CR-030 W5)", () => {
  it("law 2 — the tab CALLS `GET /move-outs`; the endpoint is not merely mounted", async () => {
    const { urls } = await renderTab(payload());
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain("/move-outs");
    expect(urls[0]).toContain(TEST_TENANT);
  });

  it("§5.6.2 — the drawn columns render §5.6.7's Northwind row", async () => {
    const { html } = await renderTab(payload());
    expect(html).toContain("A-11340");
    expect(html).toContain("Northwind Mfg.");
    expect(html).toContain("77 Industrial Way");
  });

  it("⛔ NO LANDING WORD IS RENDERED ON ANY ROW — not `SHORT`, not `settles exactly`", async () => {
    const { html } = await renderTab(payload());
    const visible = visibleText(html);
    // §5.6.4 forces a FOUR-WAY DECISION off this word, and BR-CUS-082 restarts
    // a collections ladder from it. A guessed landing is a customer chased for
    // a figure nobody computed.
    expect(visible).not.toContain("SHORT");
    expect(visible).not.toContain("Short by");
    expect(visible).not.toContain("settles exactly");
    expect(visible).not.toContain("Settles exactly");
    expect(visible).not.toContain("refunded");
    // ⚠ **THE CELL IS ONE LINE AS OF 2026-09-19 (`DEF-CUS-5899`)** — p117 draws
    // a direction, and three stacked terms are the opposite of one. The two
    // TERMS are still carried, as data rather than as copy, so DEF-127's figure
    // stays findable and the whole settlement is one click away on the account.
    expect(visible).not.toContain("Deposit held");
    expect(visible).not.toContain("Outstanding");
    expect(html).toContain('data-deposit-held-display="150.00"');
    expect(html).toContain('data-outstanding-display="108.88"');
    // ⛔ What the ONE line says: the reason there is no verdict, and nothing
    // that could be mistaken for one.
    expect(html).toContain('data-move-absent="settlement"');
    // ⚠ **THE CELL IS AN EM DASH SINCE 2026-09-25 (`DEF-CUS-6760`).** It read
    // *"No settlement yet — the final bill is not readable"* on every row, and
    // the second half of that is RATIONALE, which B14 rule 33 puts at ZERO
    // words on screen. p119 draws this column's absence as a dash.
    expect(visible).not.toContain("No settlement yet");
    expect(visible).not.toContain("final bill is not readable");
    expect(visible).toContain("\u2014");
    // ⛔ AND THE REASON IS NOT LOST — it rides on the cell, where it always did.
    expect(html).toContain('data-tracks="');
    expect(html).toContain('data-settlement-landing=""');
    expect(html).not.toContain("data-settlement-net");
  });

  /**
   * ⚠ **p117's ONE LINE, BUILT AND UNREACHABLE — and the case exists so it is
   * not silently DEAD (hard-won law 2).** The drawing renders `Short by
   * $186.40`; `move_out_settlement_cell` hard-codes `landing: None`,
   * `complete: False` and serves no `net`, so no row on any real deployment
   * takes this branch today. The day the server answers, this is the shape the
   * cell draws — and `DEF-CUS-5899`'s other half is what has to land first.
   *
   * ⛔ **BOTH HALVES OR NEITHER.** The second half of this case is the one that
   * matters: a landing with no figure must NOT print a bare `Short by`.
   */
  it("p117 — a SERVED landing draws ONE line: the direction and its figure, and never half of one", async () => {
    const base = payload();
    const landed = {
      ...base,
      rows: [
        row({
          settlement: {
            ...row().settlement,
            landing: "short",
            complete: true,
            net: { stored: "186.4000", display: "186.40" },
          },
        }),
      ],
    };
    const { html } = await renderTab(landed);
    expect(html).toContain('data-settlement-landing="short"');
    expect(html).toContain('data-settlement-net="186.40"');
    const visible = visibleText(html);
    expect(visible).toContain("Short by");
    // Hard rule 2 — the server's 2-dp string, formatted and never re-rounded.
    expect(visible).toContain("$186.40");

    // ⛔ A LANDING WITH NO FIGURE PRINTS NOTHING BUT THE ABSENCE. Without this
    // the branch would render `Short by` with no amount, which is a direction
    // asserted over a number nobody computed — §2's whole objection.
    const halfLanded = {
      ...base,
      rows: [row({ settlement: { ...row().settlement, landing: "short", complete: true } })],
    };
    const { html: half } = await renderTab(halfLanded);
    expect(visibleText(half)).not.toContain("Short by");
    expect(half).toContain('data-move-absent="settlement"');
  });

  it("the OUTSTANDING figure is the ledger's, and its absence is never `$0.00`", async () => {
    const { html } = await renderTab(payload());
    expect(html).toContain('data-outstanding-display="108.88"');

    // ⛔ THE OTHER HALF OF DEF-127: the books could not be asked.
    const unreadable = payload();
    unreadable.rows = [
      row({
        settlement: {
          ...row().settlement,
          outstanding: { stored: null, display: null },
          outstanding_source: null,
          unavailable: [
            {
              code: "ledger_publishes_no_per_account_ar_position",
              br_ref: "BR-CUS-015 · BR-REP-002 · DEF-127",
              detail:
                "the ledger module publishes no per-account AR position, so what this " +
                "customer owes cannot be read from the books.",
            },
          ],
        },
      }),
    ];
    const { html: absent } = await renderTab(unreadable);
    // ⚠ **THE MARKER MOVED WITH THE COLLAPSE (2026-09-19, `DEF-CUS-5899`).**
    // `data-move-absent="outstanding"` was the stacked `Outstanding` line's own
    // absence note; there is one line now and it is the settlement's. The RULE
    // this case exists for is untouched: the books not being readable must
    // never come out as a figure.
    expect(absent).toContain('data-move-absent="settlement"');
    // `DEF-CUS-6760` — the sentence became a dash; the RULE this case exists
    // for is untouched, and it is the two assertions below.
    expect(visibleText(absent)).not.toContain("No settlement yet");
    // ⛔ On THIS cell a fabricated zero reads as "square, and owed nothing
    // back" (DEF-127). The assertion is scoped to the FABRICATION and not to
    // the substring: a bare `not.toContain("0.00")` went RED on the deposit's
    // own correct `$150.00` — the same over-broad-search mistake `visibleText`
    // exists for, in its third disguise.
    expect(absent).not.toContain("$0.00");
    // The attribute is ABSENT rather than empty when the books could not be
    // asked, so a reader cannot mistake "not worked out" for a served zero.
    expect(absent).not.toContain("data-outstanding-display");
    // The deposit IS a column the server read, so it is still carried.
    expect(absent).toContain('data-deposit-held-display="150.00"');
  });

  it("BR-SHL-046 — a row WITH a step draws SIX segments and never B18's superseded four", async () => {
    // ⚠ **THE COUNT IS STILL PROVED, ON THE ROW THAT HAS A STEP.** The bar is
    // drawn only where the server sent a `reached` (`DEF-CUS-6770`), so the
    // segments are asserted on a parked row — which is the only row this
    // product ever gives one to.
    const { html } = await renderTab(payload({ rows: [parkedRow()] }));
    expect(html).toContain('data-step-of="6"');
    expect(html).toContain('data-step-segment="6"');
    expect(html).not.toContain('data-step-segment="7"');
    // ⛔ THE SUPERSEDED COUNT, in either shape it could come back.
    expect(html).not.toContain('data-step-of="4"');
    expect(visibleText(html)).not.toContain("of 4");
  });

  /**
   * ⚠ **THE FURNITURE, AND THE CASE THAT KEEPS IT GONE — `DEF-CUS-6770`,
   * reported by the PO on `v2.351.98`.** Every closed row drew `step.of` EMPTY
   * segments above the words `Step not recorded`: one absence stated twice,
   * the top half as placeholder furniture. p119 draws no bar at all — the
   * column is `6 of 6` · `2 of 6` in plain text — so an empty bar was never in
   * the drawing in any form.
   */
  it("`DEF-CUS-6770` — a row with NO step draws no segments, only the words", async () => {
    const { html } = await renderTab(payload());
    expect(visibleText(html)).toContain("Step not recorded");
    // The wrapper still carries what the server said; only the BAR is gone.
    expect(html).toContain('data-step-of="6"');
    expect(html).toContain('data-step-reached=""');
    expect(html).not.toContain("data-step-segment");
  });

  /**
   * ⚠ **THIS CASE IS TURNED AROUND, NOT DELETED (2026-09-19, `DEF-CUS-5897`).**
   * It asserted that `SHORTFALLS TO DECIDE` and `REFUNDS TO PAY` rendered their
   * REASON rather than `0` — correct while they were drawn, and the PO dropped
   * both tiles on 2026-09-19 (*"Drop it"*, twice). So the assertion now says
   * the tiles are GONE, and the case still guards the same money rule: neither
   * figure is derivable, so neither may come back as a number.
   *
   * ⚠ Their KEYS are still on the payload above, deliberately — the server
   * still serves them and a reader that drops a served key starts lying about
   * the contract (`MoveOutKpis`).
   */
  it("p117 — the two undecidable tiles are GONE from the strip, and their keys are still served", async () => {
    const { html } = await renderTab(payload());
    for (const marker of ["shortfalls-to-decide", "refunds-to-pay"]) {
      expect(html).not.toContain(`data-move-absent="${marker}"`);
    }
    const visible = visibleText(html);
    expect(visible).not.toContain("Shortfalls to decide");
    expect(visible).not.toContain("Refunds to pay");
    // ⛔ AND NEITHER CAME BACK AS A FIGURE, which is the rule underneath the
    // tiles rather than the tiles themselves.
    expect(visible).not.toContain("the deposit does not cover it");
    expect(visible).not.toContain("money leaving the building");
    // The three p117 DOES draw are all here, each carrying a figure.
    // ⚠ `Open` became `Awaiting final bill` on 2026-09-25 — `DEF-CUS-6762`.
    expect(visible).toContain("Awaiting final bill");
    expect(visible).toContain("Leaving this week");
    expect(visible).toContain("Final reads due");
    // The payload still holds what the server still sends.
    expect(payload().kpis.shortfalls_to_decide).toBeNull();
    expect(payload().kpis.refunds_to_pay).toBeNull();
  });

  it("p117 — the strip is THREE tiles, in the drawn order", async () => {
    const tiles = moveOutsKpis(payload(), t);
    expect(tiles.map((tile) => tile.id)).toEqual(["open", "leaving-this-week", "final-reads-due"]);
  });

  it("§5.6.1 — `FINAL READS DUE` draws the DERIVED figure, and its RATIONALE sub-line is gone", async () => {
    const { html } = await renderTab(payload());
    expect(html).not.toContain('data-move-absent="final-reads-due"');
    // ⛔ **B14 rule 33 — RATIONALE IS ZERO WORDS ON SCREEN (`DEF-CUS-5898`).**
    // *"nothing settles without one"* says WHY the figure matters, which is the
    // kind of sentence rule 33 removes rather than shortens.
    expect(visibleText(html)).not.toContain("nothing settles without one");
    // The server's own definition rides along so a caption cannot redefine it.
    expect(html).toContain(
      'data-final-reads-due-means="closed_move_outs_with_a_meter_unread_since_close"',
    );
    expect(html).toContain('data-final-reads-due-meterless="1"');
  });

  it("⛔ a NULL `final_reads_due` still renders the reason, never `0`", async () => {
    const base = payload();
    const { html } = await renderTab({
      ...base,
      kpis: {
        ...base.kpis,
        final_reads_due: null,
        final_reads_due_unavailable: READS_ABSENT,
      },
    });
    expect(html).toContain('data-move-absent="final-reads-due"');
    expect(html).toContain("Not readable");
  });

  /**
   * ⚠⚠ **THE TILE IS LABELLED FOR WHAT IT COUNTS SINCE 2026-09-25
   * (`DEF-CUS-6762`), AND IT WAS LABELLED `Open` BEFORE.** The PO saw `OPEN 5`
   * standing over five rows each reading `Completed`, with nothing on the
   * screen telling them apart. **Both figures were right and no logic moved:**
   * this counts move-outs that have CLOSED and are not yet finally billed, and
   * the rows are right that the move-out completed. p119 heads the same tile
   * `OPEN` meaning *"not yet closed"* — the opposite sense — and this product
   * cannot count those at all, so the tile had the drawn WORD over an undrawn
   * MEANING with a caption underneath to stop it being read backwards.
   * **A label needing a caption to stop it being read backwards is the wrong
   * label**, so the label states the meaning and the caption comes off (B14
   * rule 32's one statement per section).
   */
  it("`DEF-CUS-6762` — the first tile says what it counts, and does not say `Open`", async () => {
    const { html } = await renderTab(payload());
    const visible = visibleText(html);
    expect(visible).toContain("Awaiting final bill");
    // ⛔ THE WORD THAT CONTRADICTED THE ROWS. `Completed` is on every row of
    // this fixture, so a tile reading `Open` above them is the report.
    expect(visible).toContain("Completed");
    expect(visible).not.toContain("closed, not yet finally billed");
    // ⚠ NOTHING LEFT THE WIRE — the server's own sentence for what was counted
    // is still carried as data, the `open_means` precedent this tab already
    // uses in three other places.
    expect(html).toContain('data-open-means="closed_and_not_yet_finally_billed"');
  });

  // ── CR-045 wave G · B14 RULE 12 · THE `+ Filter ▾` PANEL IS ON THE TOOLBAR
  //    ROW, AND THE SEGMENT STRIP THAT USED TO BE HERE IS GONE (`DEF-1702`) ──
  //
  // ⚠ **WHAT THESE TWO CASES REPLACED, AND WHY THIS TAB IS THE CLEAREST PROOF
  // THAT A SEGMENT IS NOT A FILTER.** One asserted the strip rendered inside
  // `.table-toolbar`; the other that three of the four state segments were
  // DISABLED naming the columns they would need. Both were true and **both were
  // GREEN on a screen with no filter control at all** — `onSelect={() =>
  // undefined}`.
  //
  // The strip could not simply be folded into the `+ Filter` panel, because its
  // dimension is unusable here: `MOVE_OUT_STATES` marks exactly ONE code
  // `supported`, so a State group would offer a single option that changes
  // nothing. The panel's dimension is a WINDOW on `closed_at` instead — a
  // different question over a different column, which is the whole distinction.
  it("B14 rule 12 — the `+ Filter` panel renders INSIDE the shared toolbar row", async () => {
    const { html } = await renderTab(payload());
    const toolbar = html.indexOf("table-toolbar");
    const panel = html.indexOf("+ Filter");
    const table = html.indexOf("<table");
    expect(toolbar).toBeGreaterThan(-1);
    expect(panel).toBeGreaterThan(-1);
    expect(table).toBeGreaterThan(-1);
    expect(toolbar).toBeLessThan(panel);
    expect(panel).toBeLessThan(table);
  });

  it("⛔ `DEF-1702` — the INERT segment strip is gone; nothing here renders a control that ignores clicks", async () => {
    const { html } = await renderTab(payload());
    // The markers `WorklistSegments` emitted, and nothing else did. NOT the
    // segment WORDS: `Closed` is this tab's own STATE cell on every row.
    expect(html).not.toContain("data-worklist-segments");
    expect(html).not.toContain("data-segment=");
  });

  it("⛔ the panel offers a CLOSED WINDOW and NOT a state — the schema decides this, not taste", async () => {
    const { html } = await renderTab(payload());
    const group = moveOutFilterGroups(payload().closed_windows, t)[0];
    // ⚠ **THE NAME IS THE FINDING.** `services.move_out` writes `closed_at`,
    // the terminal status and the agreement end dates in ONE commit, so this
    // product holds no move-out before it closes; three of the four drawn
    // states can never be filled and the fourth is every row on the list.
    expect(group.name).toBe("closed");
    expect(group.options.map((option) => option.value)).toEqual(["last7", "last30", "last90"]);
    // The label is built from the SERVED `days`, so a fourth window added on
    // the server arrives with the right words and no edit here.
    expect(group.options[0].label).toContain("7");
    // Before the first response the group is empty and is dropped (`DEF-782`).
    expect(moveOutFilterGroups(undefined, t)[0].options).toEqual([]);
    // ⚠ **THE THREE UNSERVABLE STATES ARE STILL SERVED AND ARE NO LONGER
    // STATED ON SCREEN (2026-09-19, `DEF-CUS-5898`).** This line read
    // `toContain("has not gone through yet is not kept anywhere")`. That
    // sentence is 45 words of RATIONALE and B14 rule 33 — ratified 2026-08-30,
    // four days after the DEF-731 lane wrote it — puts rationale at zero words
    // on screen. The CODE is still on the wire and is carried on the root, so
    // the fact is findable without being printed at a clerk.
    expect(visibleText(html)).not.toContain("has not gone through yet");
    expect(html).toContain("move_out_before_close_has_no_store");
  });

  it("CR-045 wave G — `f.closed` LEAVES THE BROWSER, which is the only thing that makes this a filter", async () => {
    const { urls } = await renderTab(payload(), { closed: "last30" });
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain("f.closed=last30");
    // BR-SHL-011's grammar, not a bare `?closed=` the route would drop.
    expect(urls[0]).not.toMatch(/[?&]closed=last30/);
  });

  it("an EMPTY filter value is an ABSENT dimension, never `f.closed=`", async () => {
    const { urls } = await renderTab(payload(), { closed: "" });
    expect(urls[0]).not.toContain("f.closed");
  });

  it("the query key carries the filters, or the filtered request reads the unfiltered cache", () => {
    const base = defaultRequestState(CONFIG);
    expect([...moveOutsQueryKey(base)]).not.toEqual([
      ...moveOutsQueryKey({ ...base, filters: { closed: "last7" } }),
    ]);
  });

  it("§5.6.2 — FINAL READ draws the SERVED state, `estimated` included", async () => {
    const { html } = await renderTab(payload());
    expect(html).toContain('data-reads-state="estimated"');
    expect(visibleText(html)).toContain("Estimated");
    expect(html).toContain('data-reads-count="1/1"');
    expect(html).not.toContain('data-move-absent="final-read"');
  });

  it("a close with NO recorded flag serves the derived state AND says the flag is missing", async () => {
    const base = payload();
    const { html } = await renderTab({
      ...base,
      rows: [
        {
          ...base.rows[0],
          final_read: {
            state: "taken",
            measured_against: "2026-09-12",
            meters_total: 1,
            meters_read: 1,
            missing: [],
            unavailable: {
              code: "final_read_state_not_recorded",
              br_ref: "BR-CUS-031 · CR-038 W9 task 4",
              detail: "this close predates the column, or the read seam could not answer.",
            },
          },
        },
      ],
    });
    const visible = visibleText(html);
    // ⚠ BOTH, never one: the derived state is real and how the settlement got
    // its reading is unrecorded. Rendering only one would be the half-truth.
    expect(visible).toContain("Taken");
    expect(html).toContain('data-move-absent="final-read-note"');
    // `DEF-CUS-7902` — beside a figure the absence is its SHORT fact on screen
    // and its sentence in the tooltip (`DEF-CUS-6177`, B14 rules 32/33). It
    // rendered a bare `—` here, because `final_read_state_not_recorded` had no
    // short form: the reassuring half showed and the missing flag read as
    // nothing at all.
    expect(visible).toContain("Source not recorded");
    expect(html).toContain("was not recorded for this move-out");
  });

  /**
   * ⚠ **INVERTED 2026-09-19 (`DEF-CUS-5898`), AND THE INVERSION IS THE GUARD.**
   * This case asserted both list-level absences were PRINTED under the table —
   * `data-move-absent="list"`, *"A closed account stays on this list"*, *"cannot
   * be seen from here"*. Together with the sort footnote that was ~78 words, all
   * of it RATIONALE, and the PO ruled it off: *"you ahve to follow our UI rules
   * - this is correct screen - too much text"*.
   *
   * It is kept rather than deleted so the prose cannot come back unnoticed, and
   * it asserts the OTHER half in the same breath: the codes are still served
   * and still carried, so this is a screen that stopped printing a fact, not a
   * product that stopped knowing it.
   */
  it("B14 rule 33 — NO rationale under the table, and both absence codes still carried", async () => {
    const { html } = await renderTab(payload());
    const visible = visibleText(html);
    expect(html).not.toContain('data-move-absent="list"');
    expect(visible).not.toContain("A closed account stays on this list");
    expect(visible).not.toContain("cannot be seen from here");
    // The deleted footnote — its key is gone from all eleven catalogues, so a
    // regression would render the raw key rather than the sentence.
    expect(visible).not.toContain("Opens newest first");
    expect(visible).not.toContain("customers.moveOuts.list.sortFootnote");
    // ✅ AND THE FACTS ARE STILL ON THE PAGE, as data.
    expect(html).toContain(
      'data-list-absences="move_out_before_close_has_no_store move_out_window_has_no_closing_edge"',
    );
  });

  it("the KPI helper is pure and renders p117's three tiles from an absent payload", () => {
    expect(moveOutsKpis(undefined, t)).toHaveLength(3);
    // DEF-664 — the query key carries this component's OWN state, never a URL.
    expect(moveOutsQueryKey(defaultRequestState(CONFIG))[0]).toBe("move-outs");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // PO ruling 2026-08-26 — "-Enable Move in /move out"
  // ══════════════════════════════════════════════════════════════════════════
  it("the empty state's `+ New move-out` is LIVE, and the account's-own-page reason is gone", async () => {
    // The EMPTY list is the only state this CTA renders in (DEF-729).
    const { html } = await renderTab(payload({ rows: [], total: 0 }));
    const tag = /<button[^>]*>\+ New move-out<\/button>/.exec(html)?.[0] ?? "";
    expect(tag).not.toBe("");
    expect(tag).not.toContain('disabled=""');
    // The reason — *"A move-out closes one named account, so it starts from that
    // account's own page"* — was true about the ENDPOINT and wrong about the
    // screen: naming the account is step 1 of the flow, not a prerequisite for
    // reaching it. `/move-outs/new` opens on the shared account finder.
    expect(visibleText(html)).not.toContain("starts from that account");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // p117 · PO 2026-09-19 — THE THREE DOORS (`DEF-CUS-5900`)
  //
  // ⚠ **THIS IS HARD-WON LAW 2'S MIRROR WRITTEN AS A TEST, WHICH IS WHAT THE
  // LAW ASKS FOR.** *"When you write a hold, write the test that fires when the
  // hold expires, in the same commit — assert the destination by ADDRESS and by
  // the screen id it opens."* This tab's own lifecycle trailer carried *"no row
  // action"* as an exception for three weeks; the record page landed this week
  // and nothing here would have noticed.
  //
  // ⚠ **EACH CASE READS THE HREF OUT OF THE TAG IT IS ABOUT** — see `hrefOf`.
  // A row carries TWO controls onto the same record, so a page-wide
  // `toContain` cannot tell a working link from a broken one.
  // ══════════════════════════════════════════════════════════════════════════
  it("p117 — the REFERENCE opens the move-out record, at the tenant-scoped address", async () => {
    const { html } = await renderTab(payload());
    expect(hrefOf(html, "data-move-out-record")).toBe(`/${TEST_TENANT}/moves/MVO-26-0001`);
    // ⛔ THE PROTOCOL-RELATIVE SHAPE, named so a regression is unmistakable.
    expect(hrefOf(html, "data-move-out-record")).not.toMatch(/^\/moves\//);
  });

  it("p117 — the ACCOUNT number opens the account", async () => {
    const { html } = await renderTab(payload());
    expect(hrefOf(html, "data-move-out-account")).toBe(`/${TEST_TENANT}/accounts/acc-11340`);
  });

  /**
   * ⚠⚠ **THE DOOR IS AN ICON SINCE 2026-09-25 — `DEF-CUS-6759`.** The PO,
   * on `v2.351.98`: *"few bugs on Move out - list screen action it should be
   * icons not buttons"*, which supersedes their own 2026-09-19 acceptance of
   * p117's drawn text button on this list. **The ADDRESS is what this case is
   * for and it did not move**; what changed is that the control is now a
   * `RowActionLink` with an accessible name instead of a word in a border.
   */
  it("p117 — every row carries its OPEN door, onto the SAME address as the reference", async () => {
    const { html } = await renderTab(payload());
    const open = hrefOf(html, "data-move-out-open");
    expect(open).toBe(`/${TEST_TENANT}/moves/MVO-26-0001`);
    // The contract between this lane and the record page: ONE address, so the
    // two controls on a row can never disagree about where they go.
    expect(open).toBe(hrefOf(html, "data-move-out-record"));
    // ⛔ **AN ICON WITH A NAME, NOT A WORD ON THE SCREEN.** B14 rule 15's own
    // note is that an icon with no accessible name passes every text-absence
    // check in the suite and is unusable without a mouse, so the name is what
    // is asserted — it is also the string a screen reader announces.
    expect(visibleText(html)).not.toContain("↗ Open");
    expect(html).toContain('aria-label="Open the move-out"');
    expect(html).toContain('data-size="row"');
  });

  /**
   * ⚠ **THE HOLD-EXPIRY HALF: the address is `MOVE_RECORD_ROUTE`'s, and the
   * screen it opens is `MOVE_RECORD_SCREEN`.** Asserting the string alone would
   * pass over a router mounting that page somewhere else — law 7's *looking at
   * the wrong thing*, which this repo has a recorded instance of on exactly
   * this shape (a hold-expiry test asserting a screen was REGISTERED at an
   * address while the router mounted it elsewhere).
   */
  it("p117 — the address the doors build IS the route the record page is mounted at", async () => {
    const { html } = await renderTab(payload());
    expect(moveRecordPath("MVO-26-0001")).toBe("/moves/MVO-26-0001");
    expect(MOVE_RECORD_ROUTE).toBe("/moves/:ref");
    expect(MOVE_RECORD_SCREEN).toBe("S19.moveRecord");
    expect(hrefOf(html, "data-move-out-open")).toBe(
      `/${TEST_TENANT}${moveRecordPath("MVO-26-0001")}`,
    );
  });

  /**
   * ⛔ **A LINK ROUND A NULL IS A CONTROL THAT OPENS NOTHING** — the shape that
   * cost the portal front page six dead doors out of eight. Where there is no
   * record the reference falls through to the server's own sentence and the row
   * gets NO action at all, rather than a greyed button restating it (rule 32).
   */
  it("p117 — a row with no reference gets no link and no `↗ Open`, only the server's reason", async () => {
    const base = payload();
    const { html } = await renderTab({
      ...base,
      rows: [
        row({
          move_no: null,
          move_no_unavailable: {
            code: "move_reference_predates_the_record",
            br_ref: "CR-039 wave D",
            detail: "this job closed before move records were written.",
          },
        }),
      ],
    });
    expect(html).not.toContain("data-move-out-record");
    expect(html).not.toContain("data-move-out-open");
    expect(visibleText(html)).not.toContain("↗ Open");
    // The ACCOUNT door is unaffected — it never depended on a move record.
    expect(hrefOf(html, "data-move-out-account")).toBe(`/${TEST_TENANT}/accounts/acc-11340`);
  });

  // ══════════════════════════════════════════════════════════════════════════
  // p117 · B14 RULE 12 — THE TOOLBAR
  // ══════════════════════════════════════════════════════════════════════════
  it("B14 rule 19 — the prompt names REFERENCE, which is the first column drawn", async () => {
    const { html } = await renderTab(payload());
    // ⚠ **AND THE SERVER DOES NOT MATCH IT YET — `DEF-CUS-5896`.**
    // `move_outs_queryset` has no `move_no` leg and `MOVE_OUT_SEARCH_HINT`
    // still reads the old four. The row names both halves; only this one is in
    // this commit, and the case is here so the prompt and the declaration can
    // never drift apart again.
    expect(html).toContain("Reference, customer, account #, unit, or address…");
    expect(CONFIG.searchFields).toContain("reference");
  });

  /**
   * ⚠ **THE ONE THING THE CHANGE LIST ASKED TO BE VERIFIED RATHER THAN
   * BUILT.** Rule 12's grammar is `[Search…] [All | filter chips ×] [+ Filter
   * ▾] … [▦ Columns]`, and the question was whether applying the one declared
   * filter actually renders a REMOVABLE chip. It does: `FilterBar` draws the
   * applied dimension as a chip whose ✕ is a LABELLED control — a bare `×`
   * glyph names nothing to a screen reader, which is the defect rule 12 was
   * written against in the first place.
   */
  /**
   * ⚠ **THIS IS ASSERTED ON `FilterBar` WITH THIS TAB'S OWN GROUPS, AND THE
   * REASON IS A FIXTURE LIMIT WORTH NAMING (law 7's *looking at the wrong
   * thing*).** `renderTab`'s `filters` argument reaches the PREFETCH only —
   * `MoveOutsTab` builds its own `TableRequestState` with `useState` and takes
   * no initial-filter prop — so a case that rendered the TAB with `{closed:
   * "last30"}` and looked for a chip would be asserting over a bar that was
   * handed an EMPTY state. It would fail for the wrong reason today, and the
   * day the tab grew such a prop it would pass without ever having tested the
   * chip. The sibling case above asserts the same filter over the URL, which is
   * the half a rendered chip cannot prove.
   *
   * What is verified here is exactly the question the change list asked:
   * **does the one dimension this tab declares produce a REMOVABLE chip?**
   */
  it("B14 rule 12 — applying `Closed` renders a REMOVABLE chip, with a labelled ✕", () => {
    const groups = offerableFilters(moveOutFilterGroups(payload().closed_windows, t));
    const bar = (filters: Record<string, string>) =>
      renderToStaticMarkup(
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=move-outs`]}>
          <FilterBar
            filters={groups}
            state={{ ...defaultRequestState(CONFIG), filters }}
            onStateChange={() => undefined}
          />
        </MemoryRouter>,
      );

    // `All` is the default, and with NOTHING applied there is no chip to remove.
    const none = bar({});
    expect(visibleText(none)).toContain("All");
    expect(none).not.toContain('aria-label="Remove the Closed filter"');

    // ✅ THE CHIP ARRIVES WITH THE FILTER, carrying the dimension's own label
    // and the chosen window's words.
    const applied = bar({ closed: "last30" });
    expect(applied).toContain('data-chip="resting"');
    expect(visibleText(applied)).toContain("Closed");
    expect(visibleText(applied)).toContain("Last 30 days");
    // …and its ✕ is a real control with an accessible NAME, not a bare glyph.
    // A clickable `×` names nothing to a screen reader, which is half of the
    // defect rule 12 was written against.
    expect(applied).toContain('aria-label="Remove the Closed filter"');
    expect(/<button[^>]*aria-label="Remove the Closed filter"[^>]*>×<\/button>/.test(applied)).toBe(
      true,
    );
  });

  /**
   * ⚠ **TWO OF p117's TOOLBAR CONTROLS ARE NOT THIS FILE'S TO FIX, AND THE
   * CASE RECORDS WHICH.** `▦ Columns` renders as a glyph alone where the
   * drawing writes the word — it is `components/ColumnChooser.tsx`, shared by
   * every `DataTable` in the product. `⇩ Export` is drawn and is NOT rendered
   * at all: `apps/customers/` registers no `move-outs` export resource, so
   * BR-SHL-010 keeps an undeclared capability unrendered (`DEF-1005`).
   *
   * Asserted rather than left in a comment, so the day either lands this case
   * goes red and names it — hard-won law 1: a comment claiming a gap is not the
   * record of one.
   */
  it("p117 — the ▦ has no word and there is no ⇩ Export, and both are other lanes'", async () => {
    const { html } = await renderTab(payload());
    // The glyph's control is present — `ColumnChooser`'s `<summary>` carries
    // its accessible name — and the drawn WORD beside it is not.
    expect(html).toContain('aria-label="Show or hide columns"');
    expect(visibleText(html)).not.toContain("Columns ▾");
    // BR-SHL-010 — no capability, no control. Never drawn disabled either.
    expect(visibleText(html)).not.toContain("Export");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // PO RULING 2026-09-19, verbatim **`yes`** — THE UNFINISHED MOVE-OUTS,
  // and `DEF-CUS-5901`'s one word.
  // ══════════════════════════════════════════════════════════════════════════
  it("`DEF-CUS-5901` — a finished move-out reads `Completed`, and never `Closed`", async () => {
    const { html } = await renderTab(payload());
    // ⚠ **READ THE STATE CELL, NOT THE PAGE.** The word `Closed` is legitimately
    // on this screen twice over — the `f.closed` filter is named `Closed` and
    // the OPEN tile's caption reads *"closed, not yet finally billed"* — so a
    // page-wide `not.toContain("Closed")` would be red over a correct screen,
    // and a page-wide `toContain("Completed")` would pass over a state cell
    // that still said the old word. `StatusPill` is what this is about.
    const pill = stateWordOf(html);
    expect(pill).toBe("Completed");
  });

  it("`DEF-CUS-5901` — the STORED value is untouched; only the word moved", async () => {
    // ⛔ **THE WHOLE SHAPE OF THIS FIX.** The row still arrives as `closed` and
    // the screen still keys on `closed`; if this ever needs a migration, the
    // fix was done wrong.
    const { html } = await renderTab(payload({ rows: [row({ state: "closed" })] }));
    const pill = stateWordOf(html);
    expect(pill).toBe("Completed");
    // …and the state cell carries no internal code (B14 rule 31).
    expect(pill).not.toBe("closed");
  });

  it("p117 — an unfinished move-out is a row, with its real step and `In progress`", async () => {
    const { html } = await renderTab(payload({ rows: [parkedRow()], total: 1 }));
    const visible = visibleText(html);
    // The drawn cell: `2 of 6`, off the draft's own step column.
    expect(visible).toContain("2 of 6");
    expect(html).toContain('data-step-progress="2/6"');
    // …and never the absence that used to ride on every step cell.
    expect(visible).not.toContain("Step not recorded");
    expect(visible).toContain("In progress");
    // The account, the customer and the unit are the same facts a finished row
    // prints — which is WHY this is a row and not a panel.
    expect(hrefOf(html, "data-move-out-account")).toBe(`/${TEST_TENANT}/accounts/acc-11602`);
    expect(visible).toContain("Ncube, T.");
  });

  it("p117 — an unfinished row's `↗ Open` resumes the wizard, not a record page", async () => {
    const { html } = await renderTab(payload({ rows: [parkedRow()], total: 1 }));
    // ⚠ THE OTHER DESTINATION. A draft has no record and no reference to
    // address one with; what a clerk wants is to carry on where they stopped.
    expect(hrefOf(html, "data-move-out-resume")).toBe(
      `/${TEST_TENANT}/move-outs/new?parked=park-0087`,
    );
    // …built through the ONE builder the parked panel's Resume uses, so the
    // two surfaces cannot drift apart on the handle.
    expect(resumePath({ id: "park-0087", flow: "move_out" })).toBe(
      "/move-outs/new?parked=park-0087",
    );
    // ⛔ THE PROTOCOL-RELATIVE SHAPE, named so a regression is unmistakable.
    expect(hrefOf(html, "data-move-out-resume")).not.toMatch(/^\/move-outs\//);
    // …and it is NOT the record door: there is no record.
    expect(html).not.toContain("data-move-out-open");
    expect(html).not.toContain("data-move-out-record");
  });

  it("p117 — an unfinished row states its two absences and invents nothing", async () => {
    const { html } = await renderTab(payload({ rows: [parkedRow()], total: 1 }));
    const visible = visibleText(html);
    // REFERENCE — only a move-IN draft is numbered while it is in hand. FIVE
    // words in the cell (B14 rule 33), the full sentence on the `title` — the
    // posture the SETTLEMENT column two cells over already takes. Measured in a
    // browser first: the whole sentence wrapped to TWELVE lines in this column.
    expect(visible).toContain("No number until it completes");
    expect(html).toContain("This move-out has not finished, so it has no number yet.");
    expect(html).toContain('data-move-absent="reference"');
    // ⛔ NO INTERNAL REFERENCE REACHES THE CLERK (B14 rules 31 and 32).
    expect(visible).not.toContain("`");
    expect(visible).not.toMatch(/BR-[A-Z]{3}-\d/);
    // SETTLEMENT — nothing is settled until the account closes, and there is
    // not even a gap to name. The CELL is five words; the long form is the
    // title, which is the posture this column already had.
    // ⚠ **THE CELL IS AN EM DASH SINCE 2026-09-25 (`DEF-CUS-6760`)**, on this
    // row as on the closed one: a column that states a figure does not explain
    // itself, and p119 draws the in-flight row's settlement as a dash too. The
    // sentence is still the cell's `title`, and the STATE column on this same
    // row already says the move-out has not finished.
    expect(visible).not.toContain("Not settled until it closes");
    expect(html).toContain("Nothing is settled until the account closes.");
    // ⛔ NEVER A ZERO ON EITHER MONEY TERM (DEF-127): on this column a `0.00`
    // reads as *this customer is square and owed nothing back*.
    expect(visible).not.toContain("$0.00");
    // ⛔ …and never the CLOSED row's reason, which is a different statement.
    expect(visible).not.toContain("the final bill is not readable");
  });

  it("p117 — an unfinished row with no date says so rather than printing a dash", async () => {
    const { html } = await renderTab(
      payload({
        rows: [
          parkedRow({
            move_out_date: null,
            move_out_date_absence: {
              code: "parked_move_out_date_not_chosen_yet",
              br_ref: "BR-SHL-048",
              detail: "the date is asked for later in the wizard.",
            },
            step: { reached: 1, of: 6, unavailable: null },
          }),
        ],
        total: 1,
      }),
    );
    expect(visibleText(html)).toContain("No move-out date yet.");
    expect(html).toContain('data-move-absent="move-out-date"');
  });

  it("the two kinds sit on one page and the CLOSED row keeps its step absence", async () => {
    // ⛔ **THE COEXISTENCE, ASSERTED ON ONE PAGE.** A step where one is stored,
    // an absence where none is — four code paths close an account and only one
    // is the wizard, so a full bar on the finished row would claim a clerk
    // walked six steps they never saw.
    const { html } = await renderTab(payload({ rows: [row(), parkedRow()], total: 2 }));
    const visible = visibleText(html);
    expect(visible).toContain("Step not recorded");
    expect(visible).toContain("2 of 6");
    expect(visible).toContain("Completed");
    expect(visible).toContain("In progress");
  });

  it("UI-RULES 17 — the empty state exists, and its helper is five words", async () => {
    const { html } = await renderTab(payload({ rows: [], total: 0 }));
    const visible = visibleText(html);
    expect(visible).toContain("No move-outs yet");
    expect(visible).toContain("Closed accounts are listed here.");
    // ⛔ The 16-word version, whose first sentence explained what a move-out IS
    // — RATIONALE, which B14 rule 33 removes rather than shortens.
    expect(visible).not.toContain("A move-out closes an account");
  });
});
