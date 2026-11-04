// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-020 (S37 — the batch list, the KPI strip, the day-cut) ·
//           US-PAY-021 (S38 — the four match states) · US-PAY-022 (S40 — the
//           tie-out and the refusal to reconcile a residual) · US-PAY-023 (S39
//           — both sides, the trail and BR-PAY-004's lock) · US-PAY-015 /
//           US-PAY-018 / US-PAY-019 (the collections board: the tier already
//           sent, the plan pause, and the three-valued next step)
//           Screens: S37 · S38 · S39 · S40 · S34
// Rules:    BR-PAY-004 · BR-PAY-016 · BR-PAY-017 · BR-PAY-019 · BR-PAY-035 ·
//           BR-PAY-040 · BR-CUS-043 · BR-SHL-020 · BR-SHL-023 · BR-SHL-025
// ───────────────────────────────────────────────────────
// **THE ASSERTIONS THIS FILE EXISTS FOR ARE THE NULL ONES.**
//
// A batch the bank has not shown carries NO bank figure and NO difference. If
// either renders as `$0.00`, the screen draws a deposit that reconciles
// perfectly against money nobody has confirmed — which is DEF-127 (an account
// screen showing **$0.00** while the ledger held an issued, unpaid **$108.88**)
// pointed at a bank reconciliation, where it would be worse: a clerk would sign
// the day off.
//
// The collections board has the same shape one module along. `runs` is
// three-valued — steps today / a rule stopped it / **this deployment cannot
// say** — and a screen that collapsed the third into the second would tell a
// utility "we are not chasing them" when the truth is "we cannot work out
// whether we will".
//
// Every money figure here is PE-10's or the PO's card day, copied and never
// recomputed: **DEP-260808-CHK 471.39**, **DEP-260808-CSH 121.78**, and the
// card day's **5,120.40 / 4,972.90 / −147.50**.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  DepositBatchDetail,
  DepositBatchRow,
  DepositBatchesResponse,
  LadderBoardResponse,
} from "@/api/bankRecEndpoints";
import { ToastProvider } from "@/components/Toast";

import { CollectionsPage, collectionsQueryKey } from "./CollectionsPage";
import { DepositBatchPage, depositBatchQueryKey } from "./DepositBatchPage";
import { DepositsPage, depositBatchesQueryKey } from "./DepositsPage";
import { amountForInput, explainsTheDifference, scaledDecimal } from "./depositsShared";

const TENANT = "brazosbend";
const AS_OF = "2026-08-16";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

/** PE-10's cheque batch, freshly cut: the bank has not spoken. */
function inTransitBatch(over: Partial<DepositBatchRow> = {}): DepositBatchRow {
  return {
    id: "batch-chk",
    code: "DEP-260808-CHK",
    method_code: "check",
    method_name: "Check",
    deposited_on: "2026-08-08",
    recorded_total: "471.390000",
    // THE TWO NULLS. Not optional, not zero.
    bank_total: null,
    difference: null,
    currency: "USD",
    payment_count: 3,
    status: "in_transit",
    locked: false,
    ...over,
  };
}

function batchList(over: Partial<DepositBatchesResponse> = {}): DepositBatchesResponse {
  return {
    count: 1,
    next: null,
    previous: null,
    results: [inTransitBatch()],
    kpis: {
      deposited_total: "471.390000",
      batch_count: 1,
      matched_total: "0.000000",
      matched_count: 0,
      reconciled_total: "0.000000",
      reconciled_count: 0,
      unmatched_total: "0.000000",
      unmatched_count: 0,
      in_transit_total: "471.390000",
      in_transit_count: 1,
      currency: "USD",
    },
    // `P2.10` — nothing held back by default: the ordinary utility has no
    // counter open, and the line must then draw NOTHING (B14 rule 32 — a
    // stated absence is CLOSED by default). The case below overrides it.
    still_open: { batch_count: 0, recorded_total: "0.000000", currency: "USD" },
    unavailable: [
      {
        code: "grouped_bank_credits_not_matchable",
        br_ref: "BR-PAY-019 · OQ-161",
        detail: "one-to-one only",
      },
    ],
    // `P1.4` — the chips are the SERVER's now. A screen that typed them out is
    // `DEF-PAY-6556`, and a fixture that omits them would leave the toolbar
    // with no options and no way to tell that from a server that served none.
    statuses: [
      { value: "unmatched", label_key: "payments.deposits.filter.unmatched" },
      { value: "in_transit", label_key: "payments.deposits.filter.inTransit" },
      { value: "matched", label_key: "payments.deposits.filter.matched" },
      { value: "reconciled", label_key: "payments.deposits.filter.reconciled" },
    ],
    methods: [{ value: "check", label: "Check" }],
    cuttable_days: [],
    fee_account: { available: true, gl_account_id: "gl-6800", designation: "bank_fees" },
    statement_imports: [],
    ...over,
  };
}

function renderList(seed: DepositBatchesResponse): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(
    depositBatchesQueryKey({
      q: "",
      sort: "deposited_on",
      dir: "desc",
      page: 1,
      per: 50,
      status: "",
      method: "",
    }),
    seed,
  );
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/finance/deposits`]}>
          <Routes>
            <Route path="/:tenant/finance/deposits" element={<DepositsPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The PO's card day, matched to its NET credit and owed an explanation. */
function cardDayDetail(over: Partial<DepositBatchDetail> = {}): DepositBatchDetail {
  return {
    batch: {
      id: "batch-card",
      code: "DEP-260804-CARD",
      method_code: "card",
      method_name: "Card",
      deposited_on: "2026-08-04",
      recorded_total: "5120.400000",
      bank_total: "4972.900000",
      difference: "-147.500000",
      currency: "USD",
      payment_count: 28,
      status: "matched",
      locked: false,
    },
    live_total: "5120.400000",
    members: [
      {
        payment_id: "pay-1",
        payment_no: "PMT-2608-000001",
        confirmation: null,
        memo: null,
        account_id: "acc-1",
        account_no: "A-11025",
        amount: "5120.400000",
        reversed_amount: "0.000000",
        currency: "USD",
        status: "cleared",
        posted_at: "2026-08-04T10:00:00Z",
        cleared_at: "2026-08-04T10:00:00Z",
      },
    ],
    bank_line: {
      bank_line_id: "line-1",
      posted_on: "2026-08-06",
      reference: "CARD SETTLEMENT STRIPE",
      amount: "4972.900000",
      currency: "USD",
      line_no: 18,
      bank_account_name: "Chase Operating",
      bank_account_mask: "4021",
      statement_import_id: "imp-1",
      period_start: "2026-08-01",
      period_end: "2026-08-06",
    },
    trail: [
      { id: "e1", event: "created", occurred_at: "2026-08-04T17:00:00Z", actor_id: null, detail: {} },
      { id: "e2", event: "matched", occurred_at: "2026-08-06T06:40:00Z", actor_id: null, detail: {} },
      { id: "e3", event: "flagged", occurred_at: "2026-08-06T06:41:00Z", actor_id: null, detail: {} },
    ],
    resolutions: [],
    unavailable: [],
    ...over,
  };
}

function renderDetail(seed: DepositBatchDetail): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(depositBatchQueryKey(seed.batch.id), seed);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/finance/deposits/${seed.batch.id}`]}>
          <Routes>
            <Route path="/:tenant/finance/deposits/:batchId" element={<DepositBatchPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function board(over: Partial<LadderBoardResponse> = {}): LadderBoardResponse {
  return {
    as_of: AS_OF,
    rows: [
      {
        account_id: "acc-10802",
        // B14 rule 31 (DEF-2580): `account_no` is the value the board renders;
        // `account_id` is never a visible value. Present here so the fixture
        // matches the served row — a fixture missing it would let a screen test
        // pass over a shape the API does not produce.
        account_no: "AC-2026-10802",
        balance: "948.200000",
        currency: "USD",
        oldest_due_on: "2026-04-22",
        current_tier: "friendly",
        tier_sent_on: "2026-07-30",
        last_notice_on: "2026-07-30",
        plan_paused: false,
        plan_pause_reason: "no_plan",
        plan_id: null,
        medical_hold: false,
        runs: true,
        next_rung: "first_10_day",
        next_step_on: "2026-08-20",
        skip_reason: null,
        days_late: 116,
        detail_code: "decided",
      },
    ],
    rungs: ["friendly", "first_10_day", "second_5_day", "final_48_hour"],
    next_step_available: true,
    intervals: { reminder_days: 3, tier_days: [10, 5], final_hours: 48 },
    tiles: {
      accounts: 1,
      at_tier: { friendly: 1, first_10_day: 0, second_5_day: 0, final_48_hour: 0 },
      not_started: 0,
      paused: 0,
      due_today: 1,
    },
    problems: [],
    ...over,
  };
}

function renderBoard(seed: LadderBoardResponse): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(collectionsQueryKey(seed.as_of), seed);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/payments/collections`]}>
          <Routes>
            {/* DEF-216: `today` is PASSED, not left to the clock. Without it the
                page opened on the real date, asked for a query key this fixture
                had not primed, and rendered its loading skeleton — so these four
                tests passed on 2026-08-16 and failed every day after, reading as
                content mismatches rather than as a clock problem. */}
            <Route
              path="/:tenant/payments/collections"
              element={<CollectionsPage today={seed.as_of} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// US-PAY-020 — S37
// ══════════════════════════════════════════════════════════════════════════
describe("US-PAY-020 · S37 — the deposit batch list", () => {
  it("TC-1: PE-10's cheque batch renders its frozen 471.39 with the tenant's currency", () => {
    const html = renderList(batchList());
    expect(html).toContain("DEP-260808-CHK");
    expect(html).toContain('<span class="cell-money-amount">$471.39</span>');
    // The wire carries six decimals and the ONE formatter trims to two; nothing
    // on this screen re-rounds (BR-SHL-023).
    expect(html).not.toContain("471.390000");
  });

  it("TC-2 / DEF-127: a batch the bank has not shown reports PENDING, never $0.00", () => {
    const html = renderList(batchList());
    expect(html).toContain(escaped(t("payments.deposits.bankPending")));

    // THE ASSERTION THIS FILE EXISTS FOR, and it is scoped to the ROW on
    // purpose. The FIRST version of this test asserted `not.toContain("$0.00")`
    // over the whole page and went red — correctly. The zeros it found were the
    // KPI tiles' "Reconciled $0.00" and "Unmatched $0.00", and **those are real
    // zeros**: this tenant genuinely has nothing reconciled and nothing
    // unmatched, folded from the very rows below them.
    //
    // That is exactly the distinction this lane is about. A zero somebody
    // COUNTED is a fact and must render as one; a zero nobody filled is the
    // DEF-127 defect. Narrowing the assertion to the table body keeps the guard
    // pointed at the second and stops it forbidding the first.
    const body = html.slice(html.indexOf("<tbody>"), html.indexOf("</tbody>"));
    expect(body).toContain('<span class="cell-money-amount">$471.39</span>');
    expect(body).not.toContain("$0.00");
    // Both absent cells carry the SAME sentence, because both are the same
    // absence: the bank has not spoken about this batch at all.
    expect(body.split(escaped(t("payments.deposits.bankPending"))).length - 1).toBe(2);
  });

  it("TC-2: in-transit money is its OWN tile and is not folded into a matched total", () => {
    const html = renderList(batchList());
    expect(html).toContain(escaped(t("payments.deposits.kpi.inTransit")));
    expect(html).toContain(escaped(t("payments.deposits.kpi.unmatched")));
  });

  it("the deposit slip works, and its refusal sentence is gone (P4.6)", () => {
    // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-24, AND THAT IS THE
    // POINT OF INVERTING IT RATHER THAN DELETING IT.** It read *"the
    // deposit-slip export renders DISABLED with its reason (BR-SHL-025)"* and
    // it was correct for as long as no deposits export resource existed —
    // `apps/payments/exports.py` registers one now.
    //
    // CLAUDE.md hard-won law 2: *"when you write a hold, write the test that
    // fires when the hold expires"*. A hold's test that goes on asserting the
    // hold is the opposite — it makes the refusal PERMANENT, because removing
    // it turns the suite red and the next lane puts it back. So the assertion
    // is turned around and stays in the same place.
    const html = renderList(batchList());
    expect(html).not.toContain(escaped(t("payments.deposits.slipUnavailable")));
    // The control is present AND pressable. `toContain("disabled")` is a
    // whole-page check and would pass on any other disabled control, so the
    // download button is found by its own handle first.
    const control = html.slice(html.indexOf('data-download="button"'));
    expect(control).not.toBe("");
    expect(control.slice(0, 200)).not.toContain("disabled");
  });

  it("with nothing left to bank, the day-cut says so rather than offering a dead button", () => {
    const html = renderList(batchList({ cuttable_days: [] }));
    expect(html).toContain(escaped(t("payments.deposits.nothingToCut")));
  });

  it("every named gap the server sent is rendered, never dropped", () => {
    // ⚠ **THIS FIXTURE WAS THE ONLY THING KEEPING A FALSE SENTENCE ALIVE
    // (`DEF-PAY-6330`).** It invents `grouped_bank_credits_not_matchable`, and
    // the server STOPPED sending that code on 2026-09-01 when `CR-059` task 45
    // landed `match_set`. The sentence went on rendering in eleven languages —
    // *"Those deposits will stay unmatched"* — on the same page as the control
    // that matches them, and this assertion passed throughout, because a test
    // that feeds itself a retired code can never notice the code is retired.
    // The backend already carried a comment saying the sentence was false; the
    // comment reached no catalogue.
    //
    // So the fixture now uses a gap the server actually sends, and the case
    // keeps the guarantee it was written for — a named gap is RENDERED, never
    // swallowed — while gaining the one it lacked: a retired code renders
    // NOTHING rather than its own dotted key.
    // ⚠ **THIS FIXTURE USED `no_deposit_slip_export` UNTIL 2026-09-24 AND THAT
    // CODE IS NOW RETIRED (`P4.6`) — which is the SECOND time this one case has
    // been caught feeding itself a dead code, and the paragraph above is the
    // first.** `apps/payments/exports.py` registers the deposits resource, so
    // `BANKREC_UNAVAILABLE` no longer carries that entry and the server can
    // never send it again. The fixture moves to the gap the server DOES still
    // send. **The lesson is the one already written above and evidently worth
    // repeating: a test that feeds itself its own fixture cannot notice the
    // world moved.** What keeps this honest is the second half of the case —
    // a retired code must render NOTHING — and that half is what would fire if
    // somebody put a dead code back.
    // ⚠ **AND A THIRD TIME, 2026-10-30 (`DEF-PAY-10694`, LBX-05):**
    // `unmatched_bank_lines_are_counted_only` is retired with its eleven keys —
    // G3 was ruled that day and a returned line or a fee line now posts. The
    // fixture moves to `explained_lines_are_not_posted`, which the
    // reconciliation statement still sends for an ordinary explanation, and the
    // retired code joins the "renders nothing" half.
    const html = renderList(
      batchList({
        unavailable: [
          { code: "explained_lines_are_not_posted", br_ref: "BR-PAY-020", detail: "" },
        ],
      }),
    );
    expect(html).toContain(escaped(t("payments.problem.explained_lines_are_not_posted")));
    // A retired code renders nothing at all — not its own dotted key.
    for (const code of ["no_deposit_slip_export", "unmatched_bank_lines_are_counted_only"]) {
      const gone = renderList(
        batchList({ unavailable: [{ code, br_ref: "BR-PAY-020", detail: "" }] }),
      );
      expect(gone).not.toContain("payments.problem.");
      expect(gone).not.toContain("deposit slip");
      expect(gone).not.toContain(escaped("counted only"));
    }
    const retired = renderList(batchList({ unavailable: [{ code: "grouped_bank_credits_not_matchable", br_ref: "BR-PAY-020", detail: "" }] }));
    expect(retired).not.toContain("payments.problem.");
    expect(retired).not.toContain("stay unmatched");
  });

  // ── `CR-136-BRC07` `P2.10` — the money this list is NOT showing ──────────
  //
  // Since phase 0's re-key a deposit batch exists from the moment its till
  // OPENS, so S37 now serves only batches whose counter is sealed (the
  // blueprint's own word, p059: it *"becomes bankable"* at Close). That gives
  // this screen a deliberate blind spot, and hard-won law 7 is explicit that
  // a declared blind spot with no NUMBER attached is indistinguishable from an
  // empty one. These two cases are that number, in both directions.
  it("P2.10: money still at an open counter is stated, with its figure", () => {
    const html = renderList(
      batchList({
        still_open: { batch_count: 1, recorded_total: "612.500000", currency: "USD" },
      }),
    );
    // The FIGURE, through the one money formatter (BR-SHL-023) — never the
    // raw six-decimal wire value, which is what a template string would print.
    expect(html).toContain("$612.50");
    expect(html).not.toContain("612.500000");
    expect(html).toContain('data-testid="deposits-still-open"');
  });

  it("P2.10: a utility with every drawer closed is told nothing at all", () => {
    // B14 rule 32 — a stated absence is CLOSED by default. A line reading
    // "$0.00 at 0 open counters" on every Finance screen, every day of the
    // year, is the failure this guards.
    const html = renderList(batchList());
    expect(html).not.toContain('data-testid="deposits-still-open"');
  });
});

// ══════════════════════════════════════════════════════════════════════════
// US-PAY-023 / US-PAY-022 — S39 and the S40 modal
// ══════════════════════════════════════════════════════════════════════════
describe("US-PAY-023 · S39 — the batch detail", () => {
  it("TC-1: both sides render — 5,120.40 recorded against the bank's NET 4,972.90", () => {
    const html = renderDetail(cardDayDetail());
    expect(html).toContain('<span class="cell-money-amount">$5,120.40</span>');
    expect(html).toContain('<span class="cell-money-amount">$4,972.90</span>');
    expect(html).toContain("CARD SETTLEMENT STRIPE");
  });

  it("TC-1: the trail renders oldest FIRST — created, then matched, then flagged", () => {
    const html = renderDetail(cardDayDetail());
    const created = html.indexOf(escaped(t("payments.deposits.event.created")));
    const matched = html.indexOf(escaped(t("payments.deposits.event.matched")));
    const flagged = html.indexOf(escaped(t("payments.deposits.event.flagged")));
    expect(created).toBeGreaterThan(-1);
    expect(created).toBeLessThan(matched);
    expect(matched).toBeLessThan(flagged);
  });

  it("TC-3: a LOCKED batch offers Unreconcile and never Resolve (BR-PAY-004)", () => {
    const locked = cardDayDetail();
    locked.batch = { ...locked.batch, status: "reconciled", locked: true };
    const html = renderDetail(locked);
    expect(html).toContain(escaped(t("payments.deposits.unreconcile")));
    expect(html).not.toContain(escaped(t("payments.deposits.resolveDifference")));
  });

  it("an unmatched batch says the bank has not spoken instead of drawing empty fields", () => {
    const unmatched = cardDayDetail();
    unmatched.batch = {
      ...unmatched.batch,
      status: "in_transit",
      bank_total: null,
      difference: null,
    };
    unmatched.bank_line = null;
    const html = renderDetail(unmatched);
    expect(html).toContain(escaped(t("payments.deposits.bankPending")));
    expect(html).toContain(escaped(t("payments.deposits.noBankLineYet")));
  });

  it('US-PAY-022 / BR-PAY-035: "Force match anyway" does not exist on this screen', () => {
    const html = renderDetail(cardDayDetail());
    // The prototype draws the button (UtilityBilling.html:5597) and the rule
    // made it permanently SUPERSEDED. It is absent, not disabled: a disabled
    // control would say the feature exists somewhere.
    expect(html.toLowerCase()).not.toContain("force match");
  });

  it("US-PAY-022: no GL account NUMBER is written anywhere (DEF-067)", () => {
    const html = renderDetail(cardDayDetail());
    // The prototype offers "6200 · Merchant Fees" and "1020 · Undeposited
    // Funds"; neither code is in any signed chart. The account is named by
    // DESIGNATION and resolved server-side.
    expect(html).not.toContain("6200");
    expect(html).not.toContain("1020");
  });
});

describe("US-PAY-022 · S40 — the tie-out, computed exactly", () => {
  it("§7: −147.50 explains a −147.50 difference, on the NUMERIC(18,6) grid", () => {
    expect(explainsTheDifference("-147.500000", ["-147.50"])).toBe(true);
  });

  it("TC-6: −80.00 of −147.50 does NOT tie, so the screen says so before the round trip", () => {
    expect(explainsTheDifference("-147.500000", ["-80.00"])).toBe(false);
  });

  it("the comparison never goes through a float", () => {
    // The scaled BigInt is exact, which is why this file asserts the integer
    // and not a rounded string.
    // ⚠ This comment used to cite Number("5120.40") - Number("4972.90") as
    // 147.50000000000045; on this engine it is exactly 147.5 (DEF-PAY-6650).
    // A pair that IS inexact — 9758.11 - 8154.50 — is asserted, both halves,
    // in batchLineActions.dom.test.tsx.
    expect(scaledDecimal("147.50")).toBe(147500000n);
    expect(scaledDecimal("-147.500000")).toBe(-147500000n);
    expect(scaledDecimal("not a number")).toBeNull();
  });

  it("a difference nobody has (bank silent) can never be explained", () => {
    expect(explainsTheDifference(null, ["-147.50"])).toBe(false);
  });

  it("the pre-filled amount drops PADDING zeros and never a significant digit", () => {
    // The S40 form opened showing `-147.500000` on the running app. Trimming is
    // exact — it is not the display formatter and this value goes back to the
    // server's tie-out.
    expect(amountForInput("-147.500000")).toBe("-147.50");
    expect(amountForInput("-147.505000")).toBe("-147.505");
    expect(amountForInput("5.000000")).toBe("5.00");
    // And what it must never do: change a figure it cannot read.
    expect(amountForInput("not a number")).toBe("not a number");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// US-PAY-015 / US-PAY-018 / US-PAY-019 — the collections board
// ══════════════════════════════════════════════════════════════════════════
describe("US-PAY-015 / US-PAY-018 / US-PAY-019 — the collections board", () => {
  it("US-PAY-015 TC-4: the tier already sent, and the day it went", () => {
    const html = renderBoard(board());
    expect(html).toContain(escaped(t("payments.tier.friendly")));
    expect(html).toContain(escaped(t("payments.collections.tierSentOn", { date: "2026-07-30" })));
  });

  it("DEF-216: the board opens on the date it is GIVEN, never on the wall clock", () => {
    // The guard for the CAUSE, not the symptom. The four cases around it assert
    // CONTENT and would go red again for any reason at all; this one names the
    // cause, so a regression reports "the clock is back" rather than
    // "expected 'Friendly reminder'".
    //
    // A date deliberately far from any plausible today: if the page ever
    // reverts to `todayIso()` this cannot coincidentally pass.
    const seed = board();
    seed.as_of = "2019-03-04";
    const html = renderBoard(seed);
    expect(html).toContain("2019-03-04");
    expect(html, "a skeleton means the page asked for a key nobody primed").not.toContain(
      'aria-busy="true"',
    );
  });

  it("US-PAY-019: an account paused by a plan shows the pause, not a next step", () => {
    const paused = board();
    paused.rows = [
      {
        ...paused.rows[0],
        plan_paused: true,
        plan_pause_reason: "plan_active_and_current",
        plan_id: "plan-1",
        runs: false,
        next_rung: null,
        next_step_on: null,
        skip_reason: "payment_plan_pause",
        days_late: null,
        detail_code: "plan_pause",
      },
    ];
    const html = renderBoard(paused);
    expect(html).toContain(escaped(t("payments.collections.paused")));
    expect(html).toContain(escaped(t("payments.collections.noDueDate")));
  });

  it("THE HONEST ABSENCE: with no floor, the next step is 'cannot say' — never a rung", () => {
    const unknown = board({
      next_step_available: false,
      problems: [
        {
          code: "ladder_balance_floor_unset",
          br_ref: "BR-PAY-017 · OQ-137",
          detail: "no floor stored",
        },
      ],
    });
    unknown.rows = [
      {
        ...unknown.rows[0],
        runs: null,
        next_rung: null,
        next_step_on: null,
        skip_reason: null,
        days_late: null,
        detail_code: "thresholds_unset",
      },
    ];
    const html = renderBoard(unknown);
    expect(html).toContain(escaped(t("payments.collections.cannotSay")));
    expect(html).toContain(escaped(t("payments.collections.thresholdMissing")));
    // The tier already sent is a FACT and still renders — the board degrades,
    // it does not go blank.
    expect(html).toContain(escaped(t("payments.tier.friendly")));
    // And the balance is still a real, currency-bearing figure.
    expect(html).toContain('<span class="cell-money-amount">$948.20</span>');
  });

  it("the board says out loud that it sends nothing", () => {
    const html = renderBoard(board());
    expect(html).toContain(escaped(t("payments.collections.previewOnly")));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-020@5b2e814 (sources: 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md US-PAY-020/021/022/023 §3 · EP-PAY-04 US-PAY-015 · EP-PAY-05 US-PAY-018/019 · 08-payments/02-business-rules.md BR-PAY-004/016/017/019/035/040 · 05-prototype/UtilityBilling.html lines 3802-3830, 4021-4090, 5568-5600; co-packets US-PAY-021, US-PAY-022, US-PAY-023, US-PAY-015, US-PAY-018, US-PAY-019)
// generated: 2026-08-16 by story-coder (payments SURFACE lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — every case failed to resolve ./DepositsPage, ./DepositBatchPage and ./CollectionsPage before those modules existed; verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔
// exceptions: (1) the money figures are PE-10's and the PO's card day, COPIED and never recomputed — a test that recomputed its expectation would agree with a broken implementation · (2) `expect(html).not.toContain("$0.00")` is the DEF-127 guard and is deliberately blunt: on a row whose only real figure is $471.39, ANY zero on the screen is a column claiming a figure nobody confirmed · (3) the tie-out assertions read the BigInt directly (147500000n) rather than a formatted string, because the property under test is exactness and a string would hide it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
