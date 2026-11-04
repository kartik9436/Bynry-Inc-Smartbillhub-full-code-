// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-007 (S36 Revenue & AR — the KPI strip, revenue by service,
//           the cash and adjustments panels) · US-LED-004 (the period tie-out
//           and drift comparison this screen names and does NOT compute)
//           Screens: S36
// Rules:    BR-REP-001 (every money figure declares its date basis) ·
//           BR-REP-009 (the collection ratio's numerator) · BR-REP-011 (DSO
//           needs twelve months) · BR-SHL-020 (plain-language failure) ·
//           BR-SHL-023 (one money path) · CLAUDE.md rule 2
// ───────────────────────────────────────────────────────
// **THE TWO NULLS ARE THE POINT OF THIS FILE.**
//
// `collection_pct` and `dso` come back null, and each has a flattering number
// sitting right next to it that a screen could print instead. Collected ÷ billed
// gives **80.62%** — but BR-REP-009's ruled numerator is *cash applied to bills
// in period*, and the books do not record which bill a payment met, so the ruled
// figure is **72.49%**. Eight points apart, and the one we can compute is the
// generous one. DSO is the same shape: the formula needs twelve months of
// billing and a tenant three months old has three.
//
// A finance officer reading 80.62% under a heading that means 72.49% is the most
// expensive defect this screen can ship, and it would pass every shape test. So
// the assertions below are that the numbers are ABSENT and the reason is a
// sentence — not that the panels render.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { LedgerUnavailable } from "@/api/endpoints";

import { FINANCE_TABS, gapSentence, isZeroAmount } from "./financeShared";
// CR-060 C25 / T10 — the panel that replaced the Refunds TAB. Imported here
// because the strip case below is only half a test without it: a tab removed
// and no door built is a screen that does not exist (hard-won law 2).
import { RefundsQueuePanel } from "@/features/payments/RefundsQueuePanel";
import {
  CashPanel,
  GAP_COLLECTION_PCT,
  GAP_DSO,
  GAP_WRITTEN_OFF_YTD,
  TieOutPanel,
  revenueArKpis,
} from "./RevenueArPage";

const t = i18n.getFixedT("en");

//: LE-1/LE-6 — the same July figures the backend suite and the ledger review
//: row assert. Nothing here is invented for the test.
const REPORT = {
  basis: "posting",
  currency: "USD",
  period: { start: "2026-07-01", end: "2026-07-31" },
  kpis: {
    billed: "553.690000",
    collected: "446.370000",
    collected_from_cash: "446.370000",
    collected_from_applied_deposits: "0.000000",
    collection_pct: null,
    still_owed: "152.320000",
    accounts_owing: 4,
    dso: null,
    written_off_ytd: "0.000000",
  },
  revenue_by_service: [],
  aging: null,
  //: LE-1's cash line renders as TWO figures and is never added up: 150.00 is
  //: realised, 292.87 is keyed but not yet confirmed by a bank (PO 2026-08-11,
  //: "until bank record and reconcilaition confirm it it is not realised").
  cash: { basis: "posting", realised: "150.000000", undeposited: "292.870000" },
  adjustments: {
    basis: "posting",
    credits_issued: "0.000000",
    debits_posted: "0.000000",
    late_fees_applied: null,
  },
  tie_out: { ar_control: "152.320000", computed_by: null },
  unavailable: [
    {
      code: GAP_COLLECTION_PCT,
      br_ref: "BR-REP-009",
      detail: "the books do not record which bill a payment met",
    },
    { code: GAP_DSO, br_ref: "BR-REP-011", detail: "twelve months of billing do not exist yet" },
  ],
} as never;

//: The same two gaps, typed, for the assertions that pass one to `gapSentence`.
const GAPS: LedgerUnavailable[] = [
  {
    code: GAP_COLLECTION_PCT,
    br_ref: "BR-REP-009",
    detail: "the books do not record which bill a payment met",
  },
  { code: GAP_DSO, br_ref: "BR-REP-011", detail: "twelve months of billing do not exist yet" },
];

describe("US-LED-007 · S36 Revenue & AR", () => {
  it("US-LED-007 TC-1: every money tile declares its basis and stays a string", () => {
    const tiles = revenueArKpis(REPORT, t, "en-US");
    // `KpiTile` is a UNION — money or value, never both — so this narrowing is
    // BR-REP-001 expressed in the type: an unlabeled money KPI cannot be built.
    const money = tiles.filter((tile) => "money" in tile);
    expect(money.length).toBeGreaterThan(0);
    for (const tile of money) {
      if (!("money" in tile)) continue;
      expect(tile.money.basis).toBe("posting"); // BR-REP-001
      expect(tile.money.currency).toBe("USD");
      expect(typeof tile.money.amount).toBe("string"); // CLAUDE.md rule 2
    }
  });

  it("US-LED-007 TC-2: the collection ratio renders its REASON, not the flattering 80.62%", () => {
    const tiles = revenueArKpis(REPORT, t, "en-US");
    const pct = tiles.find((tile) => tile.id === "collection_pct");
    expect(pct).toBeDefined();
    expect(pct && "money" in pct).toBe(false); // a ratio is not money

    // The tile's value is a rendered explanation rather than a figure — which
    // is a better answer than an empty cell: a blank invites somebody to fill
    // it in, a sentence says why it is blank.
    const html = renderToStaticMarkup(<>{pct && "value" in pct ? pct.value : null}</>);
    expect(html).not.toBe("");
    // 446.37 ÷ 553.69 = 80.62%. The ruled figure is 72.49%. NEITHER may appear:
    // one is wrong, and the other cannot be derived from these books at all.
    expect(html).not.toContain("80.6");
    expect(html).not.toContain("72.4");
    expect(html).not.toContain(GAP_COLLECTION_PCT); // the code must not leak
  });

  it("US-LED-007 TC-3: DSO renders its reason too, and no day count", () => {
    const tiles = revenueArKpis(REPORT, t, "en-US");
    const dso = tiles.find((tile) => tile.id === "dso");
    const html = renderToStaticMarkup(<>{dso && "value" in dso ? dso.value : null}</>);
    expect(html).not.toBe("");
    expect(html).not.toContain(GAP_DSO);
    // BR-REP-011's formula over three months of history would print a number.
    expect(html).not.toMatch(/\b\d+(\.\d+)?\s*(days?|d)\b/i);
  });

  it("US-LED-007 TC-4: each absent figure names a REASON, never the server's code", () => {
    for (const gap of GAPS) {
      const sentence = gapSentence(gap, t);
      expect(sentence).not.toBe("");
      expect(sentence).not.toBe(gap.code);
      expect(sentence).not.toContain("_"); // a code leaking through reads as snake_case
    }
  });

  it("US-LED-007 TC-5: realised cash and undeposited cash are shown apart and never summed", () => {
    const html = renderToStaticMarkup(<CashPanel report={REPORT} t={t} locale="en-US" />);
    expect(html).toContain("150.00");
    expect(html).toContain("292.87");
    // 150.00 + 292.87 = 442.87 — the figure that appears the moment somebody
    // decides a clerk "really" has that much cash. It must not be on the page.
    expect(html).not.toContain("442.87");
  });

  // ══════════════════════════════════════════════════════════════════════════
  // US-LED-004 — THE RELEASE BLOCKER. This panel used to say it could not be
  // computed; the assertion below used to be `expect(html).toContain
  // ("US-LED-004")`, i.e. it asserted the NAME OF THE STORY THAT WOULD BUILD
  // IT. It builds it now, so the assertions are about money.
  // ══════════════════════════════════════════════════════════════════════════
  const TIE_OUTS_GREEN = {
    basis: "posting",
    period: { start: "2026-07-01", end: "2026-07-31" },
    rows: [
      {
        subledger: "accounts_receivable" as const,
        state: "agreed" as const,
        gl: "152.320000",
        register: "152.320000",
        drift: "0.000000",
        currency: "USD",
        basis: "posting",
        blocks_release: false,
        causes: [],
      },
      {
        subledger: "deposit_liability" as const,
        state: "agreed" as const,
        gl: "0.000000",
        register: "0.000000",
        drift: "0.000000",
        currency: "USD",
        basis: "posting",
        blocks_release: false,
        causes: [],
      },
      {
        subledger: "tax_payable" as const,
        state: "agreed" as const,
        gl: "47.380000",
        register: "47.380000",
        drift: "0.000000",
        currency: "USD",
        basis: "posting",
        blocks_release: false,
        causes: [],
      },
    ],
    drifting: [],
    unverifiable: [],
    release_blocked: false,
    dismissible: false,
  };

  it("US-LED-004 TC-1: the three LE-1 tie-outs render as equalities, not as a promise", () => {
    const html = renderToStaticMarkup(<TieOutPanel report={TIE_OUTS_GREEN} t={t} locale="en-US" />);
    expect(html).toContain("152.32"); // AR: control AND register
    expect(html).toContain("47.38"); // tax payable
    expect(html).toContain("Receivables");
    expect(html).toContain("Customer deposits");
    expect(html).toContain("Tax payable");
    // ⚠ **DEF-2367 — THIS ASSERTED THE ENGLISH BY VALUE AND WENT STALE.** It
    // read `toContain("All three agree")` until 2026-09-02, when CR-060 T6c/T6d
    // reworded the heading to *Everything agrees* across eleven catalogues —
    // correctly, because the panel covers FOUR tie-outs now and "all three" had
    // become false. The suite went red on a copy change that was right.
    // **Nothing in this repo reads copy and a test together:** G15, G18 and G27
    // all PASS on it, because the key exists, resolves and is rendered. So the
    // assertion goes through the SAME translator the screen uses — it cannot
    // drift from a rewording, and it still fails if the panel says nothing.
    expect(html).toContain(t("finance.tieOut.allAgree"));
    expect(html).not.toContain("Release blocked");
    // The old copy is GONE — a panel that still named the unbuilt story would
    // be telling a finance officer the check has not run.
    expect(html).not.toContain("US-LED-004");
  });

  it("US-LED-004 TC-2: a drift shows BOTH figures, the delta and the subledger, and blocks", () => {
    const drifting = {
      ...TIE_OUTS_GREEN,
      rows: [
        TIE_OUTS_GREEN.rows[0],
        {
          ...TIE_OUTS_GREEN.rows[1],
          state: "drifting" as const,
          gl: "0.000000",
          register: "153.500000",
          drift: "-153.500000",
          blocks_release: true,
          causes: [
            {
              code: "deposit_register_is_never_written",
              br_ref: "BR-LED-007 · DEF-177",
              detail: "the customer register column is never written by any path in this product.",
              wanted_reads: [],
            },
          ],
        },
        TIE_OUTS_GREEN.rows[2],
      ],
      drifting: ["deposit_liability"],
      release_blocked: true,
    };
    const html = renderToStaticMarkup(<TieOutPanel report={drifting} t={t} locale="en-US" />);

    // BOTH figures with their currency, and the SIGNED delta — never a bare
    // "failed", and never one figure without the other to compare it to.
    expect(html).toContain("$153.50"); // the register side
    expect(html).toContain("-$153.50"); // the difference, signed
    expect(html).toContain("Customer deposits");
    expect(html).toContain("Does not agree");
    expect(html).toContain("Release blocked");
    // …and the server's own cause, rendered as the app's plain-language
    // sentence for that code — not the raw code, and not a generic apology.
    expect(html).toContain("register is not being maintained");
    expect(html).not.toContain("deposit_register_is_never_written");
    // US-LED-004 TC-5 — the panel says the drift clears when it is explained,
    // and offers no control that could dismiss it.
    //
    // ⚠ **THIS ASSERTED `"no way to dismiss this"` UNTIL 2026-09-25.** That
    // sentence was nineteen words of rationale on a note a clerk cannot
    // dismiss and therefore reads every time (`DEF-LED-6603`). The Finance
    // blueprint p036 draws the note and names its length in the same breath —
    // *"three words"* — and the drawn screen reads **"Clears when explained."**
    expect(html).toContain("Clears when explained.");
    expect(html).not.toContain("no way to dismiss this");
    // ⚠ **THE SECOND HALF WAS `not.toContain("<button")` AND THAT STOPPED
    // MEANING WHAT IT SAID ON 2026-09-24 (`P2.20`).** The tie-out is on the
    // shared table now, so the panel legitimately contains buttons — the
    // search box's, `+ Filter`, the column chooser, the pager. **None of them
    // dismisses anything**, which is the invariant TC-5 actually protects, and
    // an assertion that no button exists at all can no longer distinguish a
    // dismiss control from a pager arrow. It is asserted by what a dismiss
    // control would SAY instead, which is the thing a clerk would press.
    for (const dismissWord of ["Dismiss", "Ignore", "Acknowledge", "Clear flag"]) {
      expect(html, dismissWord).not.toContain(dismissWord);
    }
  });

  it("DEF-176: an OMITTED figure cannot take the Finance screen down", () => {
    // MoneyCell RAISES on a nullish amount (DEF-151's fix, and correct: a tile
    // reading "null USD" shipped to production). DEF-176 is what that costs
    // when one cell is unguarded — the raise escapes to the error boundary and
    // the WHOLE screen is replaced by "Unexpected Application Error!".
    //
    // The server always sends these keys. This asserts the panel survives the
    // day it does not, because "the server always sends it" is a claim about
    // another codebase and this is the screen that pays for it being wrong.
    const missing = {
      ...TIE_OUTS_GREEN,
      rows: [
        // Keys deliberately absent rather than null — `=== null` would wave
        // this through and `formatMoney` would throw.
        { ...TIE_OUTS_GREEN.rows[0], gl: undefined, register: undefined, drift: undefined },
        TIE_OUTS_GREEN.rows[1],
        TIE_OUTS_GREEN.rows[2],
      ],
    } as unknown as Parameters<typeof TieOutPanel>[0]["report"];

    const html = renderToStaticMarkup(<TieOutPanel report={missing} t={t} locale="en-US" />);
    // It renders, and the rest of the panel is still readable.
    expect(html).toContain("Subledger tie-out");
    expect(html).toContain("47.38");
    expect(html).toContain("Not available");
  });

  it("US-LED-004: a side nobody could read renders as an absence, never as $0.00", () => {
    const unverifiable = {
      ...TIE_OUTS_GREEN,
      rows: [
        {
          ...TIE_OUTS_GREEN.rows[0],
          state: "unverifiable" as const,
          gl: null,
          register: null,
          drift: null,
          currency: null,
          blocks_release: true,
          causes: [
            {
              code: "no_account_carries_the_accounts_receivable_designation",
              br_ref: "BR-LED-007",
              detail: "this tenant has designated no receivables account.",
              wanted_reads: [],
            },
          ],
        },
        TIE_OUTS_GREEN.rows[1],
        TIE_OUTS_GREEN.rows[2],
      ],
      unverifiable: ["accounts_receivable"],
      release_blocked: true,
    };
    const html = renderToStaticMarkup(
      <TieOutPanel report={unverifiable} t={t} locale="en-US" />,
    );
    // ⚠ **THE WORD IS *Not checked* SINCE 2026-09-24 (`P2.20`).** It was *Could
    // not be checked*, which reads as a failure; blueprint p036 draws this
    // cell as **Not checked** and p037's gap box says *"Customer deposits
    // reads **Not checked** for good"* — a standing fact, not an error.
    expect(html).toContain("Not checked");
    expect(html).toContain("Release blocked");
    // The plausible zero, in the one panel where it would be most believed.
    // Scoped to the UNVERIFIABLE row: the deposit row below it legitimately
    // holds $0.00 and must keep it — 0.00 = 0.00 is a real tie-out.
    //
    // ⚠ **SCOPED BY THE ROW'S SUBLEDGER NAME, NOT BY A `<tr class=…>`
    // (`P2.20`).** The verdict class used to sit on the `<tr>`; `DataTable`
    // owns its own rows now, so it travels on the STATE CELL. Slicing from the
    // row's own name is what survives that and is what a reader would do.
    const rowStart = html.lastIndexOf("<tr", html.indexOf("Receivables"));
    const arRow = html.slice(rowStart, html.indexOf("</tr>", rowStart));
    expect(arRow).not.toContain("cell-money");
    expect(arRow).not.toContain("0.00");
    expect(arRow).toContain("Not available");
  });

  it("a served zero is recognised in every decimal form the ledger emits", () => {
    // NUMERIC(18,6) reaches the screen as "0.000000", and a cell testing
    // `amount === "0"` would print every real zero as a figure.
    for (const zero of ["0", "0.00", "0.000000", "-0.000000", " 0 "]) {
      expect(isZeroAmount(zero)).toBe(true);
    }
    expect(isZeroAmount("0.010000")).toBe(false);
  });

  // ══════════════════════════════════════════════════════════════════════════
  // DEF-151 — THE STATE EVERY DEPLOYMENT STARTS IN, WHICH NO FIXTURE COVERED
  // ══════════════════════════════════════════════════════════════════════════
  // `REPORT` above is a tenant three months into trading, and every fixture in
  // this file's history has been. `written_off_ytd` is served **null** on every
  // deployment — the read model refuses an all-time total mislabelled
  // year-to-date — and because the fixture always supplied `"0.000000"`, the
  // tests passed over a screen that printed the literal text `null USD` to a
  // finance officer beside five tiles that handled absence correctly.
  //
  // So: a BRAND-NEW tenant, with every figure the wire may withhold withheld at
  // once. Nothing here is invented — it is the payload
  // `GET /finance/revenue-ar` actually returned on a tenant provisioned through
  // the real signup on 2026-08-16, captured while reproducing the defect.

  const NEW_TENANT = {
    basis: "posting",
    currency: "USD",
    period: { start: "2026-08-01", end: "2026-08-31" },
    kpis: {
      billed: "0.000000",
      collected: "0.000000",
      collected_from_cash: "0.000000",
      collected_from_applied_deposits: "0.000000",
      collection_pct: null,
      still_owed: "0.000000",
      accounts_owing: 0,
      dso: null,
      written_off_ytd: null, // ← the one no fixture ever set
    },
    revenue_by_service: [],
    aging: null,
    cash: { basis: "clearing", realised: "0.000000", undeposited: "0.000000" },
    adjustments: {
      basis: "posting",
      credits_issued: "0.000000",
      debits_posted: "0.000000",
      late_fees_applied: null,
    },
    tie_out: { ar_control: "0.000000", computed_by: null },
    unavailable: [
      { code: GAP_COLLECTION_PCT, br_ref: "BR-REP-009", detail: "…" },
      { code: GAP_DSO, br_ref: "BR-REP-011", detail: "…" },
      {
        code: GAP_WRITTEN_OFF_YTD,
        br_ref: "BR-TEN-022",
        detail: "the caller did not state ytd_start",
      },
    ],
  } as never;

  it("DEF-151: Written off YTD reads as an ABSENCE with its reason — never the word null", () => {
    const tiles = revenueArKpis(NEW_TENANT, t, "en-US");
    const writtenOff = tiles.find((tile) => tile.id === "written_off");
    expect(writtenOff).toBeDefined();
    // Not a money tile: money renders through MoneyCell, and MoneyCell cannot
    // render an absence because it has no reason to give.
    expect(writtenOff && "money" in writtenOff).toBe(false);

    const html = renderToStaticMarkup(
      <>{writtenOff && "value" in writtenOff ? writtenOff.value : null}</>,
    );
    // THE DEFECT, asserted as itself. This is the exact text the PO read on the
    // live deployment; the neighbouring heading is not what was wrong.
    expect(html).not.toContain("null USD");
    expect(html).not.toMatch(/\bnull\b/);
    // …and the treatment its five neighbours use: the label, then the reason.
    expect(html).toContain(t("finance.absent"));
    // React's server renderer escapes the apostrophe, so compare like for like.
    expect(html.replace(/&#x27;/g, "'")).toContain(t(`finance.gap.${GAP_WRITTEN_OFF_YTD}`));
    expect(html).not.toContain(GAP_WRITTEN_OFF_YTD); // the code must not leak
    // A zero is the OTHER wrong answer: "$0.00 written off" is a claim about
    // this utility's bad debt that nobody made.
    expect(html).not.toContain("0.00");
  });

  it("DEF-151: on a brand-new tenant NO tile in the strip renders a null or an unbacked zero", () => {
    const tiles = revenueArKpis(NEW_TENANT, t, "en-US");
    expect(tiles.length).toBe(6);
    for (const tile of tiles) {
      if ("money" in tile) {
        // Every money tile that still IS money carries a real decimal string.
        // This is the property `money()` used to have no way of enforcing.
        expect(typeof tile.money.amount, `${tile.id} amount`).toBe("string");
        expect(tile.money.amount, `${tile.id} amount`).toMatch(/^-?\d+(\.\d+)?$/);
        continue;
      }
      // Every absent tile renders a sentence, not an empty cell and not a code.
      const html = renderToStaticMarkup(<>{tile.value}</>);
      expect(html, `${tile.id}`).not.toBe("");
      expect(html, `${tile.id} renders a raw null`).not.toMatch(/\bnull\b/);
      expect(html, `${tile.id} names a reason`).toContain(t("finance.absent"));
    }
  });
});

// ── CR-060 C25 / T10 — the Finance tab strip ──────────────────────────────
//
// ⚠ **THIS STRIP REACHED EIGHT TABS AND NOTHING RAISED, WHICH IS WHY THIS
// DESCRIBE BLOCK EXISTS AT ALL.** `C25` restructured it to six; `CR-059` task
// 18 shipped a whole Refunds page as a seventh; the Costs tab had already made
// a sixth. **No test in this repository asserted the strip's contents in any
// form**, so each arrival was correct on its own and the total was nobody's.
// The PO settled the count on 2026-09-03, asked directly, verbatim: *"C25 says
// six tabs. - this is correct."*
//
// **THE ASSERTION IS BY NAME AND IN ORDER, NEVER BY LENGTH ALONE.** A
// `toHaveLength(6)` goes green on a seventh tab that replaced a sixth, and on
// six tabs in the wrong order — which matters here because `C25` states the
// order in terms: *"the five tabs after it run in the order the month is
// actually worked"*, with General Ledger leading because *"opening on the trial
// balance means the first thing anyone sees is whether the month balances"*.
describe("CR-060 C25 · the Finance strip is C25's SIX", () => {
  /** `C25`'s six, in `C25`'s order. Written out rather than derived, so a
   *  change to the array is a change to this list too — a test that computed
   *  its expectation from the thing it is testing would pass on anything. */
  const C25_SIX = ["gl", "revenue", "deposits", "taxes", "cost-of-service", "export"];

  it("the six are exactly C25's, in C25's order", () => {
    expect(FINANCE_TABS.map((tab) => tab.id)).toEqual(C25_SIX);
  });

  it("a SEVENTH tab goes red here rather than reaching a clerk silently", () => {
    // The count, stated on its own as well as through the list above. This is
    // the case an eighth tab would break, and it is the one that did not exist
    // when Refunds and Costs each arrived.
    expect(FINANCE_TABS).toHaveLength(6);
  });

  it("every tab's label is translated — a strip cannot render a raw key", () => {
    for (const tab of FINANCE_TABS) {
      expect(t(tab.labelKey), tab.id).not.toBe(tab.labelKey);
    }
  });

  it("Refunds is not a tab, and its DOOR is a panel on this screen", () => {
    // Both halves, because either alone passes on a broken product: the tab is
    // gone (the PO's ruling) AND `RevenueArPage` draws the queue (the
    // integrator's placement, on `C25`'s own stated principle — a refund gives
    // back money the account holds as credit, and the credit position lives in
    // Revenue & AR, exactly where write-offs folded for the same reason).
    expect(FINANCE_TABS.map((tab) => tab.id)).not.toContain("refunds");
    expect(RefundsQueuePanel).toBeTypeOf("function");
  });

  it("Write-offs is not a tab either — the same fold, one CR earlier", () => {
    expect(FINANCE_TABS.map((tab) => tab.id)).not.toContain("write-offs");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-007@e419f62 (same five sources as apps/ledger/api.py, which
//         serves this screen; co-packet US-LED-004)
// generated: 2026-08-12 by the orchestrating session — the W5 finance-screens
//         lane authored RevenueArPage.tsx and was cut off before its tests, so
//         G10 stood red naming exactly these stories.
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — a test file calls no endpoint) E=deferred(no-frontend-half — this IS the frontend half's test) F✔ G✔ H=deferred(PO 2026-08-09)
// gates: G10 was RED naming US-LED-004 and US-LED-007 before this file existed
//         — the gate's own output is the red-proof.
// exceptions: `RevenueArPage` itself is not mounted — it pulls a live query
//         client, a router and a permissions context, and what is worth pinning
//         here is which figures are refused, not that React renders.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
