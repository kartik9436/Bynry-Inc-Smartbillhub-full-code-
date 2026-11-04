// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W7 task 7.4 — S89's FRONTEND cases. Written against B18
//           §5.7.1/§5.7.2/§5.7.3/§5.7.5/§5.7.6, which declared them before this
//           code existed (r11 step 2c).
// Rules:    TC-TRF-2 (`→ —`, not a blank) · BR-CUS-057 (deposit interest —
//           CONFIRMED, NOT BUILT) · ❄️ WE-7 / GT-23 ($150.00 principal + $3.50
//           interest = $153.50) · DEF-127 (never a fabricated zero) ·
//           BR-CUS-099 (the `request #` leg is ruled away)
// ───────────────────────────────────────────────────────
//
// ⚠ **REBUILT 2026-09-20 TO p131 (`DEF-CUS-5092`).** `BR-CUS-1030` made a
// transfer a REASSIGNMENT on 2026-09-01 and this tab went on drawing the job it
// deleted for nineteen days. Several cases below asserted the OLD job and were
// therefore PINNING FALSEHOODS — a green suite over a screen that taught a
// clerk the flow backwards. Each is INVERTED rather than deleted, with what it
// used to say written beside it, because a case that quietly disappears takes
// the reason with it.
//
// ⚠ **THE MONEY CASES ARE STILL THE POINT OF THIS FILE, AND TWO OF THEM ASSERT
// WHAT MUST NOT APPEAR.** `$0.00` and `150.00` are both WRONG for a figure that
// cannot be read: the first says the customer owes nothing, the second serves a
// principal AS a carried amount. A test that only checked the happy sentence
// would pass over both.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes, matchRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";

import { createApiClient } from "@/api/client";
import { defaultRequestState } from "@/components/tableTypes";

import {
  TakenOnCell,
  TransfersTab,
  transferLineToneClass,
  transferStateTone,
  transfersKpis,
  transfersQueryKey,
  transfersTableConfig,
} from "./TransfersTab";
import { TRANSFER_RECORD_SCREEN, transferRecordPath } from "./TransferRecordPage";
import { listTransfers } from "./worklistEndpoints";
import type { TransferList, TransferMoneyCell, TransferRow } from "./worklistEndpoints";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/**
 * The path builder the REAL component is handed, spelled here exactly as
 * `TransfersTab` spells it at its own call site.
 *
 * ⚠ **IT IS DELIBERATELY NOT A STUB THAT RETURNS ITS ARGUMENT.** A fixture
 * that fakes the tenant segment is the fixture flaw that hid eight broken
 * doors on the customer portal: with no tenant, every address a page builds
 * comes out `//transfers/…` — a protocol-relative URL to another host, which
 * reads as a perfectly good string to `toContain`. Every assertion below
 * therefore names the WHOLE address, `/brazosbend/transfers/TRF-…`, so a
 * dropped tenant fails rather than passing on a substring.
 */
const tenantPath = (segment: string): string =>
  `/${TEST_TENANT}/${segment.replace(/^\//, "")}`;

const CONFIG = transfersTableConfig(
  t,
  {
    saleDate: () => <span />,
    state: () => <span />,
  },
  tenantPath,
);

/** `transfers.DEPOSIT_INTEREST_NOT_READABLE`, as the server sends it. */
const INTEREST_NOT_READABLE = {
  code: "deposit_interest_not_readable",
  br_ref: "BR-CUS-057",
  detail:
    "BR-CUS-057's deposit-interest accrual is CONFIRMED and NOT BUILT. " +
    "No deposit figure is served for this transfer while the term cannot be read.",
};

/** CR-039 wave D task 15 — `transfers.TRANSFER_NUMBER_UNAVAILABLE`, the
 *  server's own words. Copied here rather than paraphrased so a re-wording on
 *  the Python side that this screen quietly stopped matching would show up as a
 *  diff in two files instead of none. */
const TRANSFER_NUMBER_ABSENT = {
  code: "numbering_series_missing",
  series: "transfer",
  open_question: "OQ-426",
  detail:
    "This transfer has no reference number yet. A number series for transfers has not " +
    "been set up, so nothing has been issued — the job is complete and only its " +
    "reference is missing.",
};

const MONEY_RULE_ABSENT = {
  code: "transfer_money_rule_does_not_exist",
  br_ref: "BR-CUS-025 · BR-CUS-081",
  detail: "No signed rule covers a transfer's money, so nothing moves.",
};

function money(over: Partial<TransferMoneyCell> = {}): TransferMoneyCell {
  return {
    currency: "USD",
    lines: [
      {
        kind: "deposit_carried",
        tone: "ink",
        text: "deposit carried $154.20",
        amount: { stored: "154.2000", display: "154.20" },
        unavailable: null,
      },
      {
        kind: "arrear_follows",
        tone: "amber",
        text: "arrear follows $542.10",
        amount: { stored: "542.1000", display: "542.10" },
        unavailable: null,
      },
    ],
    sentences: ["deposit carried $154.20", "arrear follows $542.10"],
    gaps: ["transfer_money_rule_does_not_exist"],
    unavailable: [MONEY_RULE_ABSENT],
    ...over,
  };
}

/** §5.7.6's `A-11455 → A-12055 · Park, Jenna` — the row that carries both
 *  sentences and is the same $542.10 the Accounts tab shows at `60+ past`. */
function row(over: Partial<TransferRow> = {}): TransferRow {
  return {
    id: "trf-0001",
    // CR-039 wave D task 15. The DEFAULT is the absence, because that is what
    // every tenant sees while OQ-426 is open — a fixture whose default were a
    // number would let the absence path go untested by accident.
    transfer_no: null,
    transfer_no_unavailable: TRANSFER_NUMBER_ABSENT,
    state: "in_progress",
    step: 3,
    step_of: 5,
    step_label: "Dates — out, in, and whether they are the same day",
    step_cell: "3 of 5",
    customer_id: "cus-1",
    customer: "Park, Jenna",
    customer_no: "C-00455",
    buyer: null,
    buyer_no: null,
    from_account_id: "acc-1",
    from_account_no: "A-11455",
    to_account_id: "acc-2",
    to_account_no: "A-12055",
    from_cell: ["A-11455", "→ A-12055"],
    to_unit_id: "u-2",
    from_to: {
      from: "901 Hillside Ave",
      to: "26 Meadowbank Rise",
      to_absence: null,
    },
    out_date: "2026-08-28",
    in_date: "2026-09-03",
    same_day: false,
    deposit_carry_elected: true,
    arrears_follow_elected: true,
    committed_at: null,
    cancelled_at: null,
    money: money(),
    moving_this_week: true,
    ...over,
  };
}

function payload(over: Partial<TransferList> = {}): TransferList {
  return {
    rows: [row()],
    kpis: {
      open: 2,
      moving_this_week: 1,
      deposits_carrying: 1,
      arrears_following: 1,
      completed_this_month: 3,
      period_basis: "tenant_month_to_date",
      as_of: "2026-08-25",
    },
    page: 1,
    per: 50,
    total: 5,
    pages: 1,
    columns: [
      "from_account",
      "customer",
      "from_to",
      "out_date",
      "in_date",
      "step",
      "money",
      "state",
    ],
    steps: [{ step: 1, label: "Find the account and confirm the customer" }],
    search: {
      // BR-CUS-099 — the box no longer offers `request #`.
      hint: "Customer, account #, or either address…",
      min_chars: 2,
      legs: ["customer", "account_no", "either_address"],
      unavailable: [],
    },
    exclusion: {
      callout:
        "A transfer appears only here. Its two halves are deliberately kept out of " +
        "Move-ins and Move-outs — the same job listed three times would be counted " +
        "three times.",
      contract: ["transfer_half_account_ids"],
      half_account_ids: ["acc-1", "acc-2"],
    },
    as_of: "2026-08-25",
    ...over,
  };
}

interface Render {
  html: string;
  urls: string[];
}

async function renderTab(body: TransferList | "unreadable"): Promise<Render> {
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
  const state = defaultRequestState(CONFIG);
  try {
    await queryClient.prefetchQuery({
      queryKey: transfersQueryKey(state),
      queryFn: () => listTransfers({ q: state.q, page: state.page, per: state.per }, client),
    });
  } catch {
    // An unreadable payload is one of the cases under test.
  }
  // ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT BARE IN A `MemoryRouter`
  // (`DEF-CUS-6532`).** This fixture WAS bare. It happened to resolve the
  // tenant correctly — `useTenantPath` reads `useLocation().pathname` rather
  // than `useParams()`, so this repo does not have the portal's exact bug —
  // and that is luck rather than design: the day a screen here reaches for
  // `useParams().tenant`, a bare fixture would render every address as
  // `//transfers/…`, a protocol-relative URL to another host, and `toContain`
  // would read it as a perfectly good string. Mounting at `/:tenant/accounts`
  // makes the fixture true under both ways of resolving it.
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=transfers`]}>
        <Routes>
          <Route path="/:tenant/accounts" element={<TransfersTab client={client} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { html, urls };
}

describe("S89 · the Transfers tab (CR-030 W7 task 7.4)", () => {
  it("law 2 — the tab CALLS `GET /transfers`; the endpoint is not merely mounted", async () => {
    const { urls } = await renderTab(payload());
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain("/transfers");
    expect(urls[0]).toContain(TEST_TENANT);
  });

  it("CR-039 W-D 15 — with no series, the REFERENCE cell states why, and never shows a dash or a made-up id", async () => {
    const { html } = await renderTab(payload());
    // The server's sentence, on the screen, where a clerk looking for a
    // reference will look for it.
    expect(html).toContain("A number series for transfers has not been set up");
    expect(html).toContain('data-record-number="transfer"');
    expect(html).toContain('data-record-number-absent=""');
    // The tracking id is a `data-` attribute and NEVER part of the sentence
    // (DEF-332 — our internal ids mean nothing to a billing clerk).
    expect(html).toContain('data-tracks="OQ-426"');
    expect(html).not.toContain("OQ-426 —");
    // ⛔ AND NO INVENTED PREFIX ANYWHERE. B18 §5.7 draws no transfer number, so
    // the screen must not be the place one appears (OQ-426).
    expect(html).not.toMatch(/TRF-\d/);
  });

  it("CR-039 W-D 15 — the moment a series exists the cell prints the number and drops the reason", async () => {
    const { html } = await renderTab(
      payload({
        rows: [row({ transfer_no: "ZZPROBE-26-0001", transfer_no_unavailable: null })],
      }),
    );
    expect(html).toContain("ZZPROBE-26-0001");
    // The absence is GONE, not sitting beside a real number.
    expect(html).not.toContain("A number series for transfers has not been set up");
    expect(html).not.toContain('data-record-number-absent=""');
  });

  /**
   * ⚠ **THIS CASE WAS NAMED *"the eight drawn columns"* AND ASSERTED THE OLD
   * JOB.** It required `26 Meadowbank Rise` — the DESTINATION address — on a
   * flow where nothing moves and `to_unit_id` is set by no live path. What it
   * now checks is p131's set: the reference, the ADDRESS of the property being
   * sold, ONE account number, and the step.
   */
  it("p131 — the drawn columns render the Park row, and the destination address is gone", async () => {
    const { html } = await renderTab(payload());
    expect(html).toContain("A-11455");
    expect(html).toContain('data-address-cell=""');
    expect(html).toContain("901 Hillside Ave");
    expect(html).toContain("3 of 5");
    // ⛔ THE SECOND ADDRESS AND THE SECOND ACCOUNT, both of which the ruling
    // deleted. `→ A-12055` was the FROM ACCOUNT cell's second line.
    expect(html).not.toContain("26 Meadowbank Rise");
    expect(html).not.toContain("→ A-12055");
  });

  /**
   * ⚠ **THIS SAID *the drawn EIGHT* UNTIL 2026-09-24 AND NOW SAYS NINE
   * (`DEF-CUS-6532`).** The ninth is the `↗ Open` door, which p133 draws on
   * every row and which this tab did not build — so the census was counting a
   * set the drawing did not have, and a census that agrees with the code
   * rather than the drawing is worth nothing. The eight that were here are
   * unchanged and in the same order; `actions` is appended after `STATE`,
   * which is where the drawing puts it.
   */
  it("p131 — the columns are the drawn nine, in the drawn order, and `in_date` and `from_to` are gone", () => {
    expect(CONFIG.columns.map((column) => column.key)).toEqual([
      "reference",
      "address",
      "from_account",
      "customer",
      "out_date",
      "step",
      "money",
      "state",
      "actions",
    ]);
    // The labels a clerk actually reads, character for character off p131.
    const labels = CONFIG.columns.map((column) => column.label);
    expect(labels).toEqual([
      "Reference",
      "Address",
      "Account",
      "Sold to",
      "Sale date",
      "Step",
      "Taken on",
      "State",
      "Actions",
    ]);
    // ⛔ The three words the deleted job left behind.
    expect(labels).not.toContain("From account");
    expect(labels).not.toContain("In date");
    expect(labels).not.toContain("From → to");
  });

  /**
   * ⚠ **`SOLD TO` IS THE ONE COLUMN THAT COULD HAVE SHIPPED A NEW FALSEHOOD.**
   * `transfer.customer` is the SELLER until `reassign_account` overwrites it at
   * commit, so a `Sold to` that simply printed `row.customer` would name the
   * seller on every open row — the exact defect class this rebuild removes.
   */
  it("`Sold to` names the buyer only once the sale has committed, and states the absence before that", async () => {
    const open = await renderTab(payload({ rows: [row({ committed_at: null })] }));
    expect(open.html).toContain('data-sold-to-absent=""');
    expect(open.html).toContain("Recorded when the sale completes");
    // ⛔ THE SELLER'S NAME MUST NOT APPEAR UNDER A `Sold to` HEADING.
    expect(open.html).not.toContain('data-sold-to=""');

    // ⛔ `DEF-CUS-6462` — the server's REAL shape: `customer` is the SELLER
    // for good (migration 0060) and the buyer rides `buyer`. This case used to
    // hand the done row the buyer's name in `customer`, a payload the server
    // stopped sending on 2026-09-20, and so it passed while the product drew
    // the seller under `Sold to`.
    const done = await renderTab(
      payload({
        rows: [
          row({
            committed_at: "2026-09-05T14:06:00Z",
            state: "done",
            customer: "Park, Jenna",
            customer_no: "C-00455",
            buyer: "Ferraro, L.",
            buyer_no: "C-00877",
          }),
        ],
      }),
    );
    expect(done.html).toContain('data-sold-to=""');
    const soldTo = done.html.slice(done.html.indexOf('data-sold-to=""'));
    const cell = soldTo.slice(0, soldTo.indexOf("</td>"));
    expect(cell).toContain("Ferraro, L.");
    expect(cell).toContain("C-00877");
    expect(cell).not.toContain("Park, Jenna");
    expect(cell).not.toContain("C-00455");
    expect(done.html).not.toContain("Recorded when the sale completes");
  });

  /**
   * ⚠ **TC-TRF-2 IS RETIRED WITH THE JOB IT BELONGED TO, NOT FAILED.** It read
   * *"a transfer at step 1 → `→ —` in the FROM ACCOUNT cell, not a blank"* and
   * it was right about a TWO-LINE cell whose second line was the second
   * account. `BR-CUS-1030` deleted the second account: `reassign_account` sets
   * `to_account_id` to the SAME account, so on a completed sale that cell read
   * `A-11455` over `→ A-11455`. What replaces it is the assertion that the
   * arrow is GONE — because the server still SENDS `from_cell`, so a future
   * edit could quietly put it back.
   */
  it("the ACCOUNT cell is one line — `from_cell`'s arrow is still served and no longer drawn", async () => {
    const { html } = await renderTab(
      payload({
        // ⚠ **THE FIXTURE MOVES `from_account_no`, NOT ONLY `from_cell`** — the
        // column reads the plain field now, and a fixture that only moved the
        // old two-line array would assert over a stale value and pass for the
        // wrong reason.
        rows: [row({ from_account_no: "A-11109", from_cell: ["A-11109", "→ —"] })],
      }),
    );
    expect(html).toContain('data-account-cell=""');
    expect(html).toContain("A-11109");
    // ⛔ NEITHER FORM OF THE SECOND LINE.
    expect(html).not.toContain("→ —");
    expect(html).not.toContain('data-from-cell=""');
  });

  /**
   * ⚠ **THIS CASE REQUIRED BOTH STACKED SENTENCES AND p131 DRAWS ONE FIGURE.**
   * It asserted `deposit carried $154.20` above `arrear follows $542.10` — and
   * both describe positions that DO NOT MOVE, which is the point of a sale. The
   * deposit is the one thing a transfer deliberately leaves alone.
   */
  it("p131 — `Taken on` is ONE figure, the arrear, and the deposit sentence is gone", async () => {
    const { html } = await renderTab(payload());
    expect(html).toContain('data-taken-on="542.10"');
    expect(html).toContain("$542.10");
    // ⛔ THE DEPOSIT SENTENCE. Still SERVED on `money.lines` — this asserts it
    // is not DRAWN, which is a different statement (`DEF-CUS-3653`).
    expect(html).not.toContain("deposit carried");
    expect(html).not.toContain("154.20");
    // Tone is DATA, decided once in the design and carried on the line.
    expect(transferLineToneClass("amber")).toBe("text-warning-700");
    expect(html).toContain("text-warning-700");
  });

  it("the deposit line is still SERVED behind the column that stopped drawing it", async () => {
    const { html } = await renderTab(payload());
    // The fixture sends both lines; the screen renders one. If a lane ever
    // "tidies" the payload, this case still passes and the BACKEND suite is
    // what fails — which is why the assertion is on the fixture's own shape.
    expect(money().lines.map((line) => line.kind)).toEqual([
      "deposit_carried",
      "arrear_follows",
    ]);
    expect(html).toContain("$542.10");
  });

  it("⛔ an arrear whose figure cannot be read renders the REASON — never `$0.00`, never the principal", () => {
    const html = renderToStaticMarkup(
      <TakenOnCell
        money={money({
          lines: [
            {
              kind: "arrear_follows",
              tone: "amber",
              text: null,
              amount: { stored: null, display: null },
              unavailable: INTEREST_NOT_READABLE,
            },
          ],
          // `sentences` is SHORTER than `lines` here, which is exactly why the
          // screen renders `lines` and not `sentences`.
          sentences: [],
        })}
      />,
    );
    expect(html).toContain("CONFIRMED and NOT BUILT");
    expect(html).toContain('data-taken-on-absent=""');
    // The id is an ATTRIBUTE and never in the sentence (DEF-332).
    expect(html).toContain('data-tracks="BR-CUS-057"');
    // ⛔ THE TWO WRONG ANSWERS. `$0.00` says the buyer takes on nothing;
    // `150.00` serves a principal AS the figure (❄️ WE-7 / GT-23).
    expect(html).not.toContain("0.00");
    expect(html).not.toContain("150.00");
  });

  it("a row with NO arrear renders `—`, which means none and is a different claim", () => {
    const html = renderToStaticMarkup(
      <TakenOnCell money={money({ lines: [], sentences: [] })} />,
    );
    expect(html).toContain('data-taken-on-none=""');
    expect(html).toContain("—");
    // The reason nothing moves is still reachable on the cell it is about.
    expect(html).toContain("No signed rule covers");
  });

  /**
   * ⚠ **THIS CASE ASSERTED A SENTENCE THAT IS NOW FALSE, AND ASSERTED IT
   * VERBATIM.** It required *"the same job listed three times would be counted
   * three times"* on the screen. **There are no halves** — nothing closes and
   * nothing opens — and even corrected it would be an INTERNAL COUNTING
   * DECISION between three tabs, which B14 rule 33 puts at zero words on
   * screen. p131 draws the red note as four words.
   */
  it("p131 — the red note is `One account, not two.` and the counting contract is off the screen", async () => {
    const { html } = await renderTab(payload());
    expect(html).toContain('data-one-account-callout=""');
    expect(html).toContain("One account, not two.");
    // ⛔ THE COUNTING CONTRACT, which is still SERVED and still governs what
    // Move-ins and Move-outs subtract — it is a rule between MODULES and a
    // clerk is not a party to it.
    expect(html).not.toContain("the same job listed three times");
    expect(html).not.toContain('data-one-job-callout=""');
    // …and the payload still carries it, so nobody reads this as "stop serving it".
    expect(html).toContain('data-callout-served=""');
  });

  /**
   * ⚠ **THIS CASE PINNED THREE FALSE TILES.** It asserted five values
   * `[2, 1, 1, 1, 3]` and that the third tile's detail read *"not refunded and
   * re-collected"* — a deposit ELECTION `OQ-1252` removed on 2026-09-01.
   */
  it("p131 — three tiles, and the two elections nobody makes any more are gone", () => {
    const tiles = transfersKpis(payload(), t);
    expect(tiles.map((tile) => tile.id)).toEqual([
      "open",
      "selling-this-week",
      "owed-on-accounts-being-sold",
    ]);
    expect(tiles[0].label).toBe("Open");
    expect(tiles[1].label).toBe("Selling this week");
    expect(tiles[2].label).toBe("Owed on accounts being sold");
    // The two counts that survive, off the same served fields as before.
    expect("value" in tiles[0] ? tiles[0].value : null).toBe(2);
    expect("value" in tiles[1] ? tiles[1].value : null).toBe(1);
    // ⛔ THE SIX WORDS THAT WERE FALSE.
    const labels = tiles.map((tile) => tile.label);
    expect(labels).not.toContain("Moving this week");
    expect(labels).not.toContain("Deposits carrying");
    expect(labels).not.toContain("Arrears following");
    expect(labels).not.toContain("Completed this month");
    expect(tiles[0].detail).toBe("a sale part-way through");
    expect(tiles[0].detail).not.toBe("same customer, new address");
  });

  /**
   * ⚠ **A ZERO ON A MONEY TILE IS A CLAIM.** `kpi_strip` serves five COUNTS and
   * no money, so `Owed on accounts being sold` has nothing to show. `$0.00`
   * would be DEF-127's *"looks exactly like a settled account"* at strip scale,
   * and `0` would be worse — it reads as a real count.
   */
  it("the money tile STATES its absence and never invents a zero", async () => {
    const { html } = await renderTab(payload());
    expect(html).toContain('data-kpi-absent="owed"');
    expect(html).toContain("Not available");
    expect(html).not.toContain("$0.00");
    const tiles = transfersKpis(payload(), t);
    // It is a `value` tile and not a `money` one: `KpiMoney` REQUIRES an
    // `amount`, and there is no amount to give it — the type would be lied to.
    expect("money" in tiles[2]).toBe(false);
  });

  /**
   * ⚠ **THIS CASE GUARDED THE `FROM → TO` COLUMN, WHICH IS GONE.** It asserted
   * *"The new address has not been chosen yet"* — a stage of a job in which the
   * customer moves to a new unit. Under `BR-CUS-1030` **no live path sets
   * `to_unit_id` at all**, so that note rendered on every open row forever and
   * the column it sat in described a destination that does not exist.
   */
  it("the destination-address column is gone, and the note that sat in it goes with it", async () => {
    const { html } = await renderTab(
      payload({
        rows: [
          row({
            from_to: {
              from: "12 Harbour View",
              to: null,
              to_absence: { reason: "target_unit_not_chosen_yet" },
            },
          }),
        ],
      }),
    );
    // The property being sold is still drawn — from the SAME served field.
    expect(html).toContain("12 Harbour View");
    // ⛔ The destination half and its note.
    expect(html).not.toContain('data-to-absent=""');
    expect(html).not.toContain("has not been chosen yet");
  });

  /**
   * ⚠ **THIS CASE WAS THE INVERSE UNTIL 2026-08-25 (lane W7WIZ), AND THE
   * INVERSION IS THE POINT.** It asserted the CTA was disabled carrying *"the
   * transfer wizard is not built yet"* — true and correct while `TRF-02` had no
   * route (BR-SHL-025 / hard-won law 2). The wizard is mounted now, so that
   * assertion had become a test PINNING A FALSEHOOD: it would have stayed green
   * over a dead button forever. What is asserted instead is the two halves law
   * 2 actually cares about — the button is LIVE, and the reason sentence is
   * GONE, so nobody can leave the disabled copy behind next to a working route.
   */
  it("law 2 — the empty state's CTA is live and no longer claims the wizard is unbuilt", async () => {
    const { html } = await renderTab(payload({ rows: [], total: 0, pages: 0 }));
    expect(html).toContain("No transfers yet");
    expect(html).toContain("+ New transfer");
    expect(html).not.toContain("not built yet");
  });

  /**
   * ⚠ **AN EMPTY STATE IS WHERE A CLERK LEARNS A FLOW, AND THIS ONE TAUGHT IT
   * BACKWARDS.** It read *"A transfer moves the same customer to a new address
   * as one job, rather than a move-out followed by a move-in"* — which is the
   * exact case the wizard's own red warning says **is not a transfer**.
   */
  it("the empty state describes a SALE, and no longer the job the ruling deleted", async () => {
    const { html } = await renderTab(payload({ rows: [], total: 0, pages: 0 }));
    expect(html).toContain("A transfer sells a property.");
    expect(html).toContain("The account stays; the owner changes.");
    // ⛔ THE SENTENCE THAT WAS FALSE, in both of its halves.
    expect(html).not.toContain("moves the same customer to a new address");
    expect(html).not.toContain("a move-out followed by a move-in");
  });

  /**
   * ⚠ **THE TOOLBAR ON AN EMPTY LIST — CHECKED, AND IT IS TWO DIFFERENT
   * EMPTIES.** A toolbar that vanished with the rows would strand a clerk who
   * had filtered down to nothing: the list would report "none" and offer no
   * way back. **`DataTable` guards exactly that**, and the guard is
   * `hasQueryState` (`DataTable.tsx:408`):
   *
   *   · **nothing created yet** — no search, no chips — the whole table region
   *     including the toolbar is replaced by `EmptyList` (`BR-SHL-012` / A18
   *     §1). There is nothing to clear, and an empty header over no rows is
   *     banned by the same rule;
   *   · **filtered or searched down to nothing** — the toolbar and the chips
   *     STAY and `ZeroResults` replaces the rows, carrying `onClearFilters`
   *     (A18 §2).
   *
   * So the absence below is the FIRST case and is deliberate. The second
   * branch is `DataTable`'s own to prove — this tab holds its table state in a
   * `useState` that no caller can seed (DEF-664), so a static render cannot
   * reach it from here, and asserting it with a fixture that cannot distinguish
   * the branches would be worse than not asserting it.
   */
  it("rule 12 — the toolbar is the chip set on a populated list, and its absence on a virgin one is DataTable's guard", async () => {
    const populated = await renderTab(payload());
    // `[Search…] [+ Filter ▾] … [▦ Columns]` — the search prompt is the
    // server's own `SEARCH_HINT`, so the box offers what the data can answer.
    expect(populated.html).toContain("Customer, account #, or either address");
    expect(CONFIG.searchPlaceholder).toBe("customers.transfers.list.searchPlaceholder");
    expect((CONFIG.filters ?? []).map((group) => group.name)).toEqual(["state"]);

    // ⛔ p131 draws `Open · Selling this week · Completed · All` as a fixed
    // SEGMENT strip. B14 rule 12 replaced that with removable chips over
    // `+ Filter ▾`, and rule 38's reasoning applies: a strip here would differ
    // from eight sibling tabs on one screen's authority. Stamped, not silent.
    expect(populated.html).not.toContain(">Completed<");
    expect(populated.html).not.toContain(">Selling this week</button>");

    // Nothing created yet: `EmptyList` replaces the whole region, CTA included.
    const virgin = await renderTab(payload({ rows: [], total: 0, pages: 0 }));
    expect(virgin.html).toContain("state-empty");
    expect(virgin.html).toContain("+ New transfer");
    expect(virgin.html).not.toContain("Customer, account #, or either address");
  });

  /**
   * ⚠ **THIS ASSERTION HAS NOW BEEN RIGHT THREE TIMES AND SAID THREE DIFFERENT
   * THINGS**, which is the whole value of keeping it rather than deleting it.
   * It began as *"no column is sortable"* (correct while the server took no
   * `sort`), became `["reference", "out_date", "in_date", "state"]` under
   * `BR-CUS-1046`, and now drops the two dates.
   *
   * **`SORTS["out_date"]` ORDERS BY `from_account__closed_at`.** That was right
   * while a transfer CLOSED the outgoing account; `BR-CUS-1030` removed the
   * closure on 2026-09-01, so the term is NULL on every live row and the sort
   * falls through to `id`. **A date header that reorders rows by nothing is a
   * control telling a clerk something untrue** — the same reasoning that made
   * this case say "no column is sortable" in the first place. `DEF-CUS-5975`
   * carries it, and the column gains `sortable` back in the commit that points
   * the server's term at `transfers.out_date`.
   */
  it("only the sorts the server can actually perform are offered, and the default did not move", () => {
    const sortable = CONFIG.columns
      .filter((column) => column.sortable === true)
      .map((column) => column.key);
    expect(sortable).toEqual(["reference", "state"]);
    // ⛔ THE BROKEN PAIR. `in_date` orders by `to_account__opened_at`, which
    // since the ruling is the account's ORIGINAL opening date — not the sale.
    expect(sortable).not.toContain("out_date");
    expect(sortable).not.toContain("in_date");
    // ⚠ **THIS TAB'S DEFAULT IS THE ONE THAT DID NOT CHANGE.** It already
    // opened `-created_at, -id`, which is why `BR-CUS-1046` asked nothing of it.
    expect(CONFIG.defaultSort).toEqual({ sort: "created", dir: "desc" });
  });

  it("the STATE tone is the screen's and B18 draws none", () => {
    expect(transferStateTone("done")).toBe("success");
    expect(transferStateTone("in_progress")).toBe("warning");
    expect(transferStateTone("scheduled")).toBe("neutral");
  });

  it("a failed read never renders the empty state — that would assert 'you have none'", async () => {
    const { html } = await renderTab("unreadable");
    // Same measured limitation as `ServiceRequestsListPage.test.tsx`:
    // `renderToStaticMarkup` runs no effects and an ERRORED cache entry reports
    // `pending` on first paint, so the positive assertion belongs to the
    // browser walkthrough. The negative one is what matters here.
    expect(html).not.toContain("No transfers yet");
  });

  /**
   * ⚠ **G27 IS RED ON THIS FILE BY CONSTRUCTION, AND THIS IS THE ASSERTION THAT
   * SAYS WHAT THAT RED DOES AND DOES NOT MEAN.**
   *
   * G27 exists because the PO photographed a deployed panel whose heading read
   * `notifications.rights.title` — a screen rendering its own source code. It
   * finds every LITERAL `t("some.key")` whose key no catalogue defines, and it
   * reports 25 of them here, because a lane may not write the shared
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

  // ══════════════════════════════════════════════════════════════════════
  // THE DOOR — OPEN IN EVERY STATE, BY PO RULING
  // ══════════════════════════════════════════════════════════════════════
  // PO, 2026-09-24, looking at a `Done` row on a live tenant: *"also this done
  // request - we are unabel to open - view should be available - all the
  // time"*. Read as the general rule it is: **a record is viewable in every
  // state, and what a clerk cannot DO with it is disabled on the record page,
  // never by removing the door.**
  //
  // ⚠ **THIS BLOCK REPLACES A HOLD-EXPIRY TEST THAT EXISTED, FIRED ONCE, AND
  // THEN COULD NOT FIRE AGAIN (`DEF-CUS-6532`) — WHICH IS THE PART WORTH
  // KEEPING.** Hard-won law 2's mirror says *"when you write a hold, write the
  // test that fires when the hold expires — assert the destination by ADDRESS
  // and by the screen id it opens."* This file DID. Hold 1 was *"no transfer
  // record page exists at any address"*; a sibling mounted
  // `TRANSFER_RECORD_ROUTE` hours later and the case went red by name.
  //
  // **Then it was RE-POINTED at hold 2 — *"`GET /transfers/{ref}` is not
  // mounted"* — and every assertion it kept was a FRONTEND fact.** No vitest
  // case can observe a Django urlpattern. `transfer_record_api.py` landed
  // 2026-09-20 in `86a28f23d`, and the case went on passing GREEN for four
  // days over a live screen with no door to it. Law 7's *incapable of failing*
  // wearing law 2's mirror as a costume.
  //
  // **So the lesson is narrower and sharper than "write an expiry test":
  // a hold re-pointed ACROSS A TIER BOUNDARY has no expiry test, only
  // something that looks like one.** Assert the new condition where it lives,
  // or release the hold and file the remainder as its own row.
  //
  // What replaces it presses the door instead of watching for it: the ADDRESS,
  // the SCREEN ID it opens, and one case per state the list can draw.

  /**
   * The address is the whole address and the screen id is the record's own.
   *
   * ⚠ **`toContain` ON A PARTIAL PATH IS WHAT THIS ASSERTION MUST NOT BE.**
   * `/transfers/TRF-26-0021` is a substring of `//transfers/TRF-26-0021`, the
   * protocol-relative URL a fixture with no tenant produces — which is how
   * eight broken doors passed on the customer portal. Every expectation here
   * names `/brazosbend/…` from its first character.
   */
  it("the `↗ Open` door is built from the record lane's own path, and lands on its screen", async () => {
    const { html } = await renderTab(
      payload({ rows: [row({ transfer_no: "TRF-26-0021", transfer_no_unavailable: null })] }),
    );
    const href = `/${TEST_TENANT}${transferRecordPath("TRF-26-0021")}`;
    expect(href).toBe("/brazosbend/transfers/TRF-26-0021");
    expect(html).toContain(`href="${href}"`);

    // …and that address opens the RECORD, not the wizard and not a 404.
    const matched = matchRoutes(APP_ROUTES, href) ?? [];
    const paths = matched.map((one) => one.route.path ?? "");
    expect(paths.some((path) => path.includes("transfers/:"))).toBe(true);
    expect(paths).not.toContain("transfers/new");
    // The screen id, so a lane re-pointing the route at some other component
    // fails here rather than shipping a door onto the wrong page.
    expect(TRANSFER_RECORD_SCREEN).toBe("S89.transferRecord");
  });

  /**
   * **ONE CASE PER STATE, AND THE POINT IS THAT THEY ARE ALL THE SAME CASE.**
   * `done` is the state the PO reported; the others are every state
   * `transfer_reads.TRANSFER_FILTER_STATES` can put on this list. If a future
   * lane gates the door on progress, this goes red naming the state it broke.
   */
  it.each(["in_progress", "scheduled", "parked", "done"])(
    "a `%s` transfer opens exactly like every other one — the door is never state-gated",
    async (state) => {
      const { html } = await renderTab(
        payload({
          rows: [
            row({
              state,
              transfer_no: "TRF-26-0021",
              transfer_no_unavailable: null,
              committed_at: state === "done" ? "2026-09-05T14:06:00Z" : null,
            }),
          ],
        }),
      );
      expect(html).toContain(`href="/${TEST_TENANT}/transfers/TRF-26-0021"`);
      // …and it is the KIT's row action rather than a hand-rolled link (B14
      // rule 43 — a piece of UI is a COMPONENT). `data-variant`/`data-size`
      // are `Button`'s own stated contract, so a hand-rolled `<Link>` wearing
      // the same classes still fails this.
      expect(html).toContain('data-variant="ghost"');
      expect(html).toContain('data-size="row"');
      // The accessible name rule 15 requires of an UNLABELLED icon.
      expect(html).toContain(`aria-label="${t("customers.transfers.action.open")}"`);
    },
  );

  /**
   * ⛔ **THE ONE ROW THAT CANNOT OPEN, AND IT IS NOT A STATE GATE.**
   * The record is addressed by its REFERENCE. A tenant provisioned before the
   * `transfer` numbering series was seeded has rows with none, and those
   * cannot be addressed at all — BR-SHL-025, disabled WITH ITS REASON rather
   * than removed, because a control somebody deleted is a rule the clerk has
   * to guess.
   *
   * ⚠ **AND NO UUID IS SUBSTITUTED (B14 rule 31).** The reader accepts one as
   * a way IN for exactly this tenant; that is never a way to WRITE one into a
   * link. `row()`'s default carries `transfer_no: null` with the id
   * `trf-0001`, so a lane reaching for `row.id` fails here.
   */
  it("a row with no reference is disabled with its reason — and never linked by database id", async () => {
    const { html } = await renderTab(payload({ rows: [row()] }));
    expect(html).not.toContain("/transfers/trf-0001");
    expect(html).not.toContain(`/${TEST_TENANT}/transfers/null`);
    expect(html).toContain(`title="${t("customers.transfers.action.openBlocked")}"`);
    expect(html).toContain("disabled");
  });

  /**
   * p131 draws a `SOLD BY` column. `reassign_account` OVERWRITES
   * `transfer.customer_id` with the buyer at commit, so the seller survives
   * only in the commit response's `reassignment` block and in `audit_log`,
   * **which is pruned on a retention schedule**. A `Sold by` column would
   * therefore be empty on exactly the rows a clerk needs it — the completed
   * ones — or would be read off a log that gets deleted.
   *
   * **THE DAY THE SERVER SENDS A `sold_by`, THIS GOES RED AND NAMES THE
   * COLUMN.** It asserts on the TYPE, so a lane widening `TransferRow` cannot
   * land the field and forget the column (`DEF-CUS-5976`).
   */
  it("`Sold by` stays absent until the server sends a seller of its own", async () => {
    const shape = row();
    expect("sold_by" in shape).toBe(false);
    expect("seller" in shape).toBe(false);
    const labels = CONFIG.columns.map((column) => column.label);
    expect(labels).not.toContain("Sold by");
    // ⛔ AND IT IS NOT FAKED FROM `customer` — which since 2026-09-20 IS the
    // seller, so the column is `DEF-CUS-5976`'s to serve, by ruling.
    const { html } = await renderTab(
      payload({ rows: [row({ committed_at: "2026-09-05T14:06:00Z", state: "done" })] }),
    );
    expect(html).not.toContain('data-sold-by');
  });

  it.todo(
    "TC-TRF-1 (the exclusion contract): a transfer appears in NEITHER Move-ins nor Move-outs and their counts stay 3 and 5 — neither list exists in this application yet, and the contract is asserted server-side against `transfer_half_account_ids` in 06-backend/tests/test_w7_worklists.py",
  );
  it.todo(
    "TC-TRF-3..6 (deposit carry, same-day reads, a live target account, the two-way link at commit) are WRITE cases with no surface on this tab — the transfer wizard is not built, and they live in the backend suite",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W7 task 7.4 (S89) · B18 §5.7 · BR-CUS-057 · BR-CUS-099 ·
//         ❄️ WE-7 / GT-23 · DEF-127
// generated: 2026-08-25 by lane F-TABS
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E4 TC-TRF-1's cross-tab count cannot be asserted from this screen
//         — the Move-ins and Move-outs lists do not exist yet · E4 TC-TRF-3..6
//         are write cases with no surface on this tab
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
