// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-008 (S56 trial balance and its balanced footer) ·
//           US-LED-013 (the S56 journal list) · US-LED-014 (S41 dual-basis
//           remittance) · US-LED-015 (the S42 close checklist and WARN +
//           CONFIRM) · US-LED-016 (the S42/S43 export preview and its gates)
//           Screens: S41 · S42 · S43 · S56
// Rules:    BR-LED-002 (BOTH bases always; the collected basis is not
//           derivable) · BR-LED-006 · BR-LED-007 (drift is a red flag, never a
//           silent fix) · BR-LED-013 · BR-LED-017 (an export needs a CLOSED
//           period) · BR-LED-018 (WARN + CONFIRM) · BR-REP-001 · BR-SHL-011
//           (the URL grammar — and DEF-095's period bound, which is NOT a list
//           filter) · CLAUDE.md rule 2
// ───────────────────────────────────────────────────────
// **THE FOUR REFUSALS ARE THE POINT OF THIS FILE**, exactly as the two nulls
// are the point of `revenueAr.test.tsx`. Each has a tidier answer sitting right
// beside it that a screen could render instead:
//
//   · an EMPTY period could render a green "Balanced" over 0 = 0 (DEF-110's own
//     warning: the seed fixture holds one bill dated 30 June, so a July close
//     would close nothing and pass);
//   · an UNBALANCED period could render the difference away;
//   · an `unknown` checklist item could render as a tick or as a plain ✗;
//   · the COLLECTED tax column could render the BILLED figure, which would have
//     a utility remit tax on money nobody has paid.
//
// Every assertion below is that the screen refuses, and that the refusal is a
// sentence a finance officer can act on.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";
import { LOCALE_REGISTRY } from "@/i18n";

import type {
  ExportPreviewResponse,
  RemittanceResponse,
  TrialBalanceResponse,
} from "@/api/endpoints";

import { AuthorityTable, remittanceSchema } from "./RemittancePage";
import {
  ACCOUNTING_PROVIDER,
  CLOSE_EXPORT_VIEWS,
  headTitleKeyFor,
  savedExportTarget,
} from "./CloseExportPage";
// ⚠ `ExportCostSection` MOVED TO `financeShared` WITH `P4.12`, and
// `ExportSummaryTable` — the `PlainTable` it hung under — was DELETED rather
// than moved: 6·2 draws those five columns as a `DataTable` with a toolbar, a
// ▦ chooser and a ↓, and keeping the old component beside the new one would
// have been dead UI (hard-won law 2). Its two TABLE cases moved to
// `exportView.test.tsx`, where the table they describe now lives; the three
// cost cases below are unchanged apart from the component they mount.
import { ExportCostSection } from "./financeShared";
// ⚠ `checklistTone` MOVED TO `CloseView` WITH THE PANEL IT BELONGS TO (`P5.9`,
// 2026-09-24). No re-export was left behind on purpose — two import paths for
// one function is the drift the move exists to remove.
import { checklistTone } from "./CloseView";
import type { ConnectionRow, ProviderCard } from "@/api/integrationsEndpoints";
import {
  TrialBalanceTable,
  trialBalanceView,
} from "./GeneralLedgerPage";
import type { TableRequestState } from "@/components/tableTypes";

const t = i18n.getFixedT("en");
const translate = (key: string, params?: Record<string, unknown>) => t(key, params) as string;

// ── LE-1's July, as `apps/ledger/wire.trial_balance_dict` serves it ───────
const TRIAL_BALANCE: TrialBalanceResponse = {
  basis: "posting",
  currency: "USD",
  period: { start: "2026-07-01", end: "2026-07-31" },
  rows: [
    {
      account_id: "a1", code: "1200", name: "Accounts receivable", type: "asset",
      debit: "152.320000", credit: "0.000000",
      gross_debit: "553.690000", gross_credit: "401.370000",
      // CR-060 C4 — the June cutover carried 45.00 of migrated AR into July,
      // which is exactly the figure the opening column exists to show. The
      // backend asserts the same number against the same fixture in
      // `tests/test_cr060_c4_opening_closing.py`.
      opening: "45.000000", closing: "197.320000",
    },
    {
      account_id: "a2", code: "4100", name: "Electric revenue", type: "revenue",
      debit: "0.000000", credit: "506.310000",
      gross_debit: "0.000000", gross_credit: "506.310000",
      opening: "0.000000", closing: "-506.310000",
    },
  ],
  total_debit: "553.690000",
  total_credit: "553.690000",
  total_opening: "0.000000",
  total_closing: "0.000000",
  difference: "0.000000",
  balanced: true,
};

/** The toolkit's request state, at its defaults. Declared once so the cases
 *  below read as assertions about the TABLE rather than about paging. */
const TABLE_STATE: TableRequestState = {
  q: "",
  sort: "code",
  dir: "asc",
  page: 1,
  per: 50,
  filters: {},
};
const noop = () => undefined;

describe("US-LED-008 — the S56 trial balance", () => {
  it("renders the SERVER's balanced verdict and the SERVER's totals", () => {
    const html = renderToStaticMarkup(
      <TrialBalanceTable
        report={TRIAL_BALANCE}
        t={translate}
        state={TABLE_STATE}
        onStateChange={noop}
      />,
    );
    expect(html).toContain("Balanced");
    // The footer is the served figure, not a client-side sum of the column.
    expect(html).toContain("553.69");
    expect(html).toContain("152.32");
  });

  it("renders an UNBALANCED period unbalanced, with the difference (BR-LED-007)", () => {
    // US-LED-008 TC-5: the screen CANNOT render this as balanced. Drift can only
    // come from a posting-service bypass, and the one thing a finance screen
    // must never do is make broken books look tidy.
    const drifting: TrialBalanceResponse = {
      ...TRIAL_BALANCE,
      total_credit: "553.680000",
      difference: "0.010000",
      balanced: false,
    };
    const html = renderToStaticMarkup(
      <TrialBalanceTable
        report={drifting}
        t={translate}
        state={TABLE_STATE}
        onStateChange={noop}
      />,
    );
    expect(html).not.toContain("Balanced");
    expect(html).toContain("0.010000");
    expect(html).toContain("The books do not add up");
  });

  // ══════════════════════════════════════════════════════════════════════
  // CR-060 C4 — opening · movement · closing ON SCREEN
  // ══════════════════════════════════════════════════════════════════════
  // ⚠ These assert the RENDERED MARKUP, deliberately. No gate in this repo
  // reads rendered output, so a column that exists in the config and never
  // reaches the DOM — because it was filtered out of the visible set, or the
  // cell renderer returned nothing — passes `tsc`, eslint and every
  // config-shaped assertion. The markup is the only witness.
  it("draws BOTH position columns and the account's own opening figure (C4)", () => {
    const html = renderToStaticMarkup(
      <TrialBalanceTable
        report={TRIAL_BALANCE}
        t={translate}
        state={TABLE_STATE}
        onStateChange={noop}
      />,
    );
    // ⚠ **THE COLUMN HEADER, NOT THE WORD.** A bare `toContain("Opening")`
    // passed while the column header read SABOTAGE, because the FOOTER carries
    // the same label — a check that cannot distinguish the thing it is pointed
    // at is worse than no check (hard-won law 7, and this is the second time
    // this repo has recorded that exact shape). The header is a sort BUTTON, so
    // the assertion names the markup only a header can produce.
    expect(html).toContain('<button type="button" class="table-sort">Opening');
    expect(html).toContain('<button type="button" class="table-sort">Closing');
    // The 45.00 the June cutover carried in, and the 197.32 it closes at.
    expect(html).toContain("45.00");
    expect(html).toContain("197.32");
  });

  it("foots the WHOLE period even when the view is filtered (C4 · C14)", () => {
    // The table pages and filters; the footer never does. A reader who took a
    // page total for the month's would be reading a number that is not there.
    const filtered: TableRequestState = { ...TABLE_STATE, filters: { type: "revenue" } };
    const html = renderToStaticMarkup(
      <TrialBalanceTable
        report={TRIAL_BALANCE}
        t={translate}
        state={filtered}
        onStateChange={noop}
      />,
    );
    expect(html).toContain("553.69"); // the served footing, unfiltered
    expect(html).toContain("These totals cover every account in the period");
    expect(html).toContain("Balanced");
  });

  // ══════════════════════════════════════════════════════════════════════
  // CR-060 C14 — the shared toolkit, and the ONE piece of logic under it
  // ══════════════════════════════════════════════════════════════════════
  it("searches, filters and sorts without touching a money figure (C14)", () => {
    expect(trialBalanceView(TRIAL_BALANCE.rows, TABLE_STATE).total).toBe(2);
    // Search matches code OR name.
    expect(
      trialBalanceView(TRIAL_BALANCE.rows, { ...TABLE_STATE, q: "receivable" }).page.map(
        (row) => row.code,
      ),
    ).toEqual(["1200"]);
    expect(
      trialBalanceView(TRIAL_BALANCE.rows, { ...TABLE_STATE, q: "4100" }).page.map(
        (row) => row.code,
      ),
    ).toEqual(["4100"]);
    // The declared `f.type` filter, which is the only dimension the toolbar
    // offers (DEF-1700: a screen declares a dimension, it does not grow a row).
    expect(
      trialBalanceView(TRIAL_BALANCE.rows, { ...TABLE_STATE, filters: { type: "revenue" } }).page
        .map((row) => row.code),
    ).toEqual(["4100"]);
    // Sorting on a money column ORDERS the rows and produces no figure: the
    // revenue account's closing is negative, so it sorts below AR ascending.
    expect(
      trialBalanceView(TRIAL_BALANCE.rows, { ...TABLE_STATE, sort: "closing" }).page.map(
        (row) => row.code,
      ),
    ).toEqual(["4100", "1200"]);
    expect(
      trialBalanceView(TRIAL_BALANCE.rows, {
        ...TABLE_STATE,
        sort: "closing",
        dir: "desc",
      }).page.map((row) => row.code),
    ).toEqual(["1200", "4100"]);
  });

  it("renders an EMPTY period as empty, never as a balanced zero (DEF-110)", () => {
    const empty: TrialBalanceResponse = {
      ...TRIAL_BALANCE,
      rows: [],
      total_debit: "0.000000",
      total_credit: "0.000000",
    };
    const html = renderToStaticMarkup(
      <TrialBalanceTable report={empty} t={translate} state={TABLE_STATE} onStateChange={noop} />,
    );
    expect(html).toContain("This is an empty book, not a balanced one.");
  });
});

// ── US-LED-013 — the journal list ────────────────────────────────────────

// ⛔ `US-LED-013 — the S56 journal list` IS GONE (`DEF-LED-6723`, 2026-09-25).
//
// Its two cases mounted `JournalEntryTable`, a component with zero production
// callers since `P1.15` split the view strip — so they were green over code no
// clerk could reach, which is the shape that keeps a dead component looking
// alive. The component is deleted; **the two RULES they asserted moved to
// `journalView.test.tsx`**, against the table a clerk actually sees.

// ── US-LED-014 — the dual-basis remittance table ─────────────────────────
const REMITTANCE: RemittanceResponse = {
  basis: { billed: "posting", collected: "clearing" },
  currency: "USD",
  period: { start: "2026-07-01", end: "2026-07-31" },
  rows: [
    {
      account_id: "t1", code: "2200-01", name: "TX Comptroller — state sales tax",
      billed: "13.870000", collected: null, remitted: "4.500000",
      outstanding_billed: "9.370000", outstanding_collected: null,
      remitting_basis: null, bases: ["billed", "collected"],
      // OQ-1190 (PO 2026-08-31) — the same authority's debt as the BILLS
      // charged it, named the way rating names it. It AGREES with the books
      // here, which is the ordinary case and the one the screen must not turn
      // into an alarm.
      authority_name: "Texas Comptroller of Public Accounts",
      billed_from_bills: "13.870000", bill_line_count: 3, bill_count: 3,
      billed_delta: "0.000000", bills_agree: true, problems: [],
    },
  ],
  totals: {
    billed: "13.870000", collected: null, remitted: "4.500000",
    outstanding_billed: "9.370000", billed_from_bills: "13.870000",
  },
  tie_out: { tax_payable_gl: "13.870000" },
  unavailable: [],
};

describe("US-LED-014 — S41 dual-basis remittance", () => {
  it("NEVER prints the billed figure in the collected column", () => {
    // LE-3's State authority billed 13.87. The collected basis is not
    // derivable, and printing 13.87 in that column would have a utility remit
    // tax on money nobody has paid.
    //
    // COUNTED, not merely "contains": the reason sentence renders in the footer
    // too, so a screen that filled the cell with the billed figure would still
    // satisfy a `toContain` on the sentence.
    //
    // ⚠ **THE EXPECTED COUNT WENT 2 → 4 ON 2026-08-31 (`OQ-1190`)** and the
    // four places are named so the number stays falsifiable rather than
    // becoming whatever the screen happens to render. The PO's ruling added a
    // *Billed on bills* column, so 13.87 now belongs in: the row's **Billed**
    // cell · the row's **Billed on bills** cell · the footer's **Billed**
    // total · the footer's **Billed on bills** total. It belongs nowhere else,
    // and a FIFTH occurrence is the defect this assertion has always existed
    // for — the billed figure leaking into a COLLECTED cell, which would have a
    // utility remit tax on money nobody has paid. The agreement sentence
    // carries no figure, which is why it adds none.
    const html = renderToStaticMarkup(
      <AuthorityTable report={REMITTANCE} t={translate} onRecord={() => undefined} />,
    );
    expect(html.split("13.87").length - 1).toBe(4);
    expect(html).toContain("The books cannot say how much tax sits inside the payments received");
  });

  // ── DEF-LED-6722 — the footer's COLLECTED total ─────────────────────────
  it("foots the collected column instead of refusing under a column of real money", () => {
    // ⚠ The footer cell was `{absentCollected}`, unconditional, while the rows
    // above it drew figures — a refusal that outlived CR-060 C19 by three
    // weeks. `totals.collected` null is the only case it may cover.
    const collected: RemittanceResponse = {
      ...REMITTANCE,
      rows: [{ ...REMITTANCE.rows[0], collected: "9.000000" }],
      totals: { ...REMITTANCE.totals, collected: "9.000000" },
    };
    const html = renderToStaticMarkup(
      <AuthorityTable report={collected} t={translate} onRecord={() => undefined} />,
    );
    // TWICE: the row's own cell and the All authorities total.
    expect(html.split("9.00").length - 1).toBe(2);
    expect(html).not.toContain(
      "The books cannot say how much tax sits inside the payments received",
    );
  });

  it("still refuses the collected TOTAL when the read genuinely cannot say", () => {
    // NON-VACUOUS: the fixture's rows carry `collected: null`, so this is the
    // absence the refusal exists for and it must survive the fix above.
    const html = renderToStaticMarkup(
      <AuthorityTable report={REMITTANCE} t={translate} onRecord={() => undefined} />,
    );
    expect(html).toContain(
      "The books cannot say how much tax sits inside the payments received",
    );
  });

  it("says the filing basis is unset rather than choosing one", () => {
    // LE-3 files State on COLLECTED and County on BILLED in the SAME month, so
    // a default would be wrong for one of them in its first month.
    const html = renderToStaticMarkup(
      <AuthorityTable report={REMITTANCE} t={translate} onRecord={() => undefined} />,
    );
    expect(html).toContain("Nobody has chosen whether this authority is filed");
  });

  // ── OQ-1190 — the per-authority subtotal on the FINANCE screen ──────────
  // PO 2026-08-31: *"(a) Add a per-authority subtotal to the bill and the
  // finance screens"*. The books identify an authority by its 2200-nn account
  // and cannot name it (`GAP_TAX_AUTHORITY_NAME`); the BILLS can, because a tax
  // line carries `tax_id`. So the row now carries both, and whether they agree.
  it("names the authority AND keeps the account it has always been identified by", () => {
    const html = renderToStaticMarkup(
      <AuthorityTable report={REMITTANCE} t={translate} onRecord={() => undefined} />,
    );
    // The name RATING knows — what a clerk writes on a return.
    expect(html).toContain("Texas Comptroller of Public Accounts");
    // And the account, which is still the identity in the books (BR-BIL-069).
    expect(html).toContain("2200-01");
    expect(html).toContain("TX Comptroller — state sales tax");
  });

  // ── DEF-LED-6706 — THE AUTHORITY COLUMN ALWAYS HAS A NAME TO DRAW ───────
  it("falls back to the account's own name instead of printing Authority not named above it", () => {
    // ⚠ THE DEFECT THE PO SAW, EXACTLY: the cell rendered *"Authority not
    // named"* and then printed *"2200-01 · Tax payable — Local · Bexar
    // County"* on the line directly underneath it. `authority_name` is the
    // name RATING knows and is populated only from the bills IN THE WINDOW, so
    // any window with no bills in it — which is most of them — hit the absent
    // state. BR-BIL-069 (PO 2026-08-11) rules the 2200-nn account IS the
    // authority's identity in the books, so the row always holds a name.
    const unnamed: RemittanceResponse = {
      ...REMITTANCE,
      rows: [{ ...REMITTANCE.rows[0], authority_name: null }],
    };
    const html = renderToStaticMarkup(
      <AuthorityTable report={unnamed} t={translate} onRecord={() => undefined} />,
    );
    expect(html).not.toContain("Authority not named");
    expect(html).toContain("TX Comptroller — state sales tax");
    expect(html).toContain("2200-01");
  });

  it("states whether the bills and the books agree, and never reconciles them", () => {
    const agreeing = renderToStaticMarkup(
      <AuthorityTable report={REMITTANCE} t={translate} onRecord={() => undefined} />,
    );
    expect(agreeing).toContain("Bills and books agree.");

    // A DISAGREEMENT IS REPORTED WITH BOTH FIGURES AND NEITHER IS MOVED — the
    // posture `_charges_by_service` takes on the bill, for its reason: a screen
    // that balanced the books would destroy the evidence BR-BIL-032 exists to
    // surface. The books say 13.87; the bills say 14.87.
    const drifted: RemittanceResponse = {
      ...REMITTANCE,
      rows: [{ ...REMITTANCE.rows[0], billed_from_bills: "14.870000",
               billed_delta: "1.000000", bills_agree: false }],
      totals: { ...REMITTANCE.totals, billed_from_bills: "14.870000" },
    };
    const html = renderToStaticMarkup(
      <AuthorityTable report={drifted} t={translate} onRecord={() => undefined} />,
    );
    expect(html).not.toContain("Bills and books agree.");
    // BOTH figures, so the size of the disagreement is visible.
    expect(html).toContain("14.87");
    expect(html).toContain("13.87");
  });

  it("shows an ABSENT bill-side figure as absent and never as 0.00", () => {
    // On a screen a return is filed from, 0.00 reads as "this authority is owed
    // nothing". A missing figure must say it is missing.
    const unanswered: RemittanceResponse = {
      ...REMITTANCE,
      rows: [{ ...REMITTANCE.rows[0], authority_name: null, billed_from_bills: null,
               bill_line_count: null, billed_delta: null, bills_agree: null,
               problems: ["no_bill_side_tax_lines_resolve_to_this_account"] }],
      totals: { ...REMITTANCE.totals, billed_from_bills: null },
    };
    const html = renderToStaticMarkup(
      <AuthorityTable report={unanswered} t={translate} onRecord={() => undefined} />,
    );
    expect(html).toContain("No bill-side figure for this account.");
    // ⚠ DEF-LED-6706 — THIS LINE READ `toContain("Authority not named")` and
    // was asserting the defect. The case is about the BILL-SIDE FIGURE being
    // absent; the authority's name is a separate fact the books always hold
    // (BR-BIL-069), and pinning the placeholder here is how a screen printing
    // *Authority not named* above the authority's name kept a green suite.
    expect(html).not.toContain("Authority not named");
    expect(html).toContain("TX Comptroller — state sales tax");
    // NON-VACUOUS: the billed column still carries its real figure, so this is
    // not passing because the whole table went blank.
    expect(html).toContain("13.87");
    // And 13.87 is now in TWO places only — the books' cell and the books'
    // total — because the bill-side column and its total are both absent.
    expect(html.split("13.87").length - 1).toBe(2);
  });

  it("refuses a zero, a float-shaped blank and a missing confirmation reference", () => {
    const schema = remittanceSchema(translate);
    expect(schema.safeParse({
      amount: "0.00", basis: "billed", confirmation_ref: "X", entry_date: "2026-08-18",
    }).success).toBe(false);
    expect(schema.safeParse({
      amount: "13.87", basis: "billed", confirmation_ref: "", entry_date: "2026-08-18",
    }).success).toBe(false);
    expect(schema.safeParse({
      amount: "13.87", basis: "", confirmation_ref: "TXC-1", entry_date: "2026-08-18",
    }).success).toBe(false);
    expect(schema.safeParse({
      amount: "13.87", basis: "collected", confirmation_ref: "TXC-2026-08-9012",
      entry_date: "2026-08-18",
    }).success).toBe(true);
  });
});

// ── US-LED-015 — the close checklist ─────────────────────────────────────

describe("US-LED-015 — the S42 close checklist", () => {
  // ⚠ **THE THREE RENDER CASES MOVED TO `CloseView.dom.test.tsx` (`P5.9`).**
  // They mounted `CloseChecklistPanel`, which no longer exists: 6·1 is two
  // numbered steps with a door on every unfinished row, not a board headed
  // *Before you close*. The assertions were not dropped — every one of them is
  // in the new file against the new shape, which is the only place they can now
  // be true. What STAYS here is the pure function, because it is a mapping and
  // not a rendering, and this file is where the finance surface's mappings are
  // tested.

  it("maps unknown to neutral, not to the same tone as not-done", () => {
    expect(checklistTone("complete")).toBe("success");
    expect(checklistTone("unknown")).toBe("neutral");
  });
});

// ── US-LED-016 — the export preview and its gates ────────────────────────
const PREVIEW: ExportPreviewResponse = {
  period: { start: "2026-07-01", end: "2026-07-31" },
  target: "qbo",
  granularity: "summary",
  currency: "USD",
  entries: 2,
  rows: [
    {
      code: "1200", name: "Accounts receivable", type: "asset", account_id: "a1",
      target_ref: "QB-1200", debit: "152.320000", credit: "0.000000", currency: "USD",
      window: { start: "2026-07-01", end: "2026-07-31" },
    },
    {
      code: "6900", name: "Bad debt", type: "expense", account_id: "a3",
      target_ref: null, debit: "0.000000", credit: "0.000000", currency: "USD",
      window: { start: "2026-07-01", end: "2026-07-31" },
    },
  ],
  total_debits: "553.690000",
  total_credits: "553.690000",
  period_total_debits: "553.690000",
  period_total_credits: "553.690000",
  balanced: true,
  period_closed: false,
  missing_refs: ["6900 · Bad debt"],
  already_exported: null,
  sendable: false,
  cost_section: {
    source: "register", in_trial_balance: false, entries: 0, cost_total: "0.000000",
    currency: "USD", rows: [], missing_refs: [], unavailable: [],
    // CR-060 T6c / DEF-3380 — nothing settled on this fixture, which is the
    // ordinary case and the one US-LED-021 TC-7's figures were signed against.
    settled: {
      count: 0, total: "0.000000", currency: "USD", source: "journal",
      in_trial_balance: true, label: "IN THE BOOKS",
    },
  },
};

describe("US-LED-016 — the S42/S43 export", () => {
  it("keeps the supplier-cost total OUT of the balanced footer (US-LED-021 TC-7)", () => {
    const withCosts: ExportPreviewResponse = {
      ...PREVIEW,
      cost_section: {
        ...PREVIEW.cost_section,
        entries: 5,
        cost_total: "51902.500000",
        unavailable: [
          {
            code: "posting_shape_is_not_ruled",
            br_ref: "BR-LED-039 · OQ-200",
            detail: "register-derived",
          },
        ],
      },
    };
    const html = renderToStaticMarkup(
      <ExportCostSection section={withCosts.cost_section} t={translate} />,
    );
    expect(html).toContain("51,902.50");
    // ⚠ Through the translator (DEF-2367 / B14 rule 34), for the same reason
    //    as `AssetLifecycle.test.tsx`: CR-060 T12 swept "kept apart from the
    //    totals above" into the one ruled pair, and an assertion that copies
    //    the English is a copy of the catalogue that goes stale the moment the
    //    catalogue moves. What is being asserted is unchanged — the cost line
    //    is labelled, and the footer below it is still only the receivable.
    expect(html).toContain(
      translate("finance.export.costTotal", { count: withCosts.cost_section.entries }),
    );
    // ⚠ **THE RECEIVABLE FOOTING IS ASSERTED IN `exportView.test.tsx` NOW**,
    // because this component no longer draws it — and that is the POINT of the
    // split rather than a weakened case: the cost figure and the footer are two
    // pieces of markup and the rule is that one is not inside the other. A
    // component that cannot render the footer cannot accidentally sum into it.
    expect(html).not.toContain("553.69");
  });

  it("says on screen that already-paid purchases are not in the cost figure (CR-060 T6c)", () => {
    // The figure a clerk reconciled last month gets smaller the first time
    // somebody records a supplier invoice as paid, because that cost is now in
    // the balanced totals instead (DEF-3380). A number that shrinks with no
    // explanation on the screen is the shape hard-won law 1 is about.
    const withSettled: ExportPreviewResponse = {
      ...PREVIEW,
      cost_section: {
        ...PREVIEW.cost_section,
        entries: 4,
        cost_total: "50662.500000",
        settled: { ...PREVIEW.cost_section.settled, count: 1, total: "1240.000000" },
      },
    };
    const html = renderToStaticMarkup(
      <ExportCostSection section={withSettled.cost_section} t={translate} />,
    );
    expect(html).toContain("1 already-paid invoices are not in this figure");
    expect(html).toContain("would hand the same money over twice");
    // B14 rule 32 — a stated absence is a disclosure CLOSED by default, so the
    // sentence rides a `<details>` with no `open` attribute rather than sitting
    // on the work surface as another paragraph.
    expect(html).toContain("<details>");
    expect(html).not.toContain("<details open");
  });

  it("shows nothing about settled costs when nothing is settled", () => {
    // 0 is a derived answer here, not a default — and an empty disclosure would
    // be a stated absence of an absence, which is rule 32's own failure mode.
    const html = renderToStaticMarkup(
      <ExportCostSection
        section={{ ...PREVIEW.cost_section, entries: 5, cost_total: "51902.500000" }}
        t={translate}
      />,
    );
    expect(html).not.toContain("already-paid");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-LED-6499 · P2.4 — the property filter EXISTS, and the panel that denied
// it is gone
// ═══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS BLOCK REPLACES THE `CR-060` C24 / `DEF-2347` ONE, AND THE OLD BLOCK
// IS WHY THE DEFECT LASTED THREE WEEKS.** It asserted that a sentence was
// PRESENT in eleven catalogues and that its English read, exactly, *"Every
// journal line carries its property. No report filters on it yet."* Both
// assertions were true the day they were written and **neither could ever go
// red when the filter shipped** — which it did on 2026-09-03, in `CR-060` C24,
// the very change request the old block is named after.
//
// That is `DEF-2346`'s shape, recorded in the decision log about this same
// screen: *"its test asserted each sentence was PRESENT and never that it was
// TRUE, so no assertion in it could go red when the feature it called unbuilt
// shipped"*. The old block even quoted that lesson in its own comment — and
// then pinned a sentence instead of a behaviour, one panel further down.
//
// **So what is asserted now is the BEHAVIOUR, in both directions:**
//   1. the false sentence is buyable in NO catalogue — a lane restoring it in
//      the tenth language goes red like the first;
//   2. the filter REACHES THE SERVER — the request carries `f.premises`, which
//      is the one thing that makes the control more than decoration.
//
// (2) is the assertion the old block had no equivalent of, and it is the one
// that fails if someone deletes the control, forgets the cache key, or wires
// the chip to state nothing reads.
describe("DEF-LED-6499 · P2.4 — no Finance screen denies the property filter", () => {
  it("the retired sentence is in no catalogue, in any language", () => {
    // PROVED RED FIRST — the two keys were put back into all eleven catalogues
    // and this test was run. Verbatim:
    //   AssertionError: en still carries the retired property sentence:
    //   expected 'Every journal line carries its proper…' to be undefined
    for (const entry of LOCALE_REGISTRY) {
      const catalog = entry.catalog as Record<string, string>;
      expect(
        catalog["finance.gl.premisesFilterUnavailable"],
        `${entry.code} still carries the retired property sentence`,
      ).toBeUndefined();
      expect(
        catalog["finance.gl.premisesFilterTitle"],
        `${entry.code} still carries the retired property heading`,
      ).toBeUndefined();
    }
  });

  it("every catalogue words the property filter itself", () => {
    // The replacement is a CONTROL, so what every catalogue must now carry is
    // the control's own words rather than an apology for its absence. Parity is
    // G15's job; this asserts the seven keys are the ones a clerk reads here.
    for (const entry of LOCALE_REGISTRY) {
      const catalog = entry.catalog as Record<string, string>;
      for (const suffix of [
        "label",
        "placeholder",
        "tooShort",
        "searching",
        "failed",
        "noMatch",
        "unnamed",
      ]) {
        expect(
          catalog[`finance.gl.premisesFilter.${suffix}`],
          `${entry.code} has no finance.gl.premisesFilter.${suffix}`,
        ).toBeTruthy();
      }
    }
  });

  it("the other S56 absence is UNCHANGED, because it was re-verified and is true", () => {
    // C23. `GET /ledger/journal-entries/{id}` is mounted DELETE-only in
    // `apps/ledger/journal_api.py`, `reporting.journal_entry_list` has no
    // ledger-account filter, and `reporting.account_ledger` answers for a
    // CUSTOMER account rather than a chart row. Pinned so a future sweep does
    // not "fix" a sentence that is still correct — the mirror of DEF-2347, and
    // the reason both were checked rather than one assumed from the other.
    expect(i18n.getFixedT("en")("finance.gl.expandUnavailable")).toBe(
      "Opening one account line to the entries behind it needs a detail read the server does not serve yet.",
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════
// CR-069 wave J — the REMEMBERED DESTINATION on S43
// ══════════════════════════════════════════════════════════════════════════
//
// Before wave J the export picker had no memory: a clerk chose one of four
// formats every month and nothing recorded where the file was going. The saved
// `accounting_file` connection is that memory (`BR-INT-010` makes the
// accounting target a CONNECTION), and `savedExportTarget` is the one function
// that decides what S43 shows and sets from it.
//
// ⚠ WHAT IS PINNED HERE IS EVERY WAY IT ANSWERS **NOTHING**, not merely the
// happy path — because the failure that matters is not a wrong destination, it
// is a finance screen going dark because a Settings read did not answer.
describe("CR-069 wave J — S43 remembers where the month's journal goes", () => {
  const CONNECTION: ConnectionRow = {
    id: "01a0763a-0000-7000-8000-0000000000ac",
    label: "Month-end journal",
    describe: "Month-end journal · QuickBooks · downloaded here",
    settings: { label: "Month-end journal", destination: "download", file_format: "iif" },
    connected_by: "Alex Reed",
    environment: "production" as const,
    status: "working" as const,
    enabled: true,
    cadence: "manual" as const,
    next_run_at: null,
    last_test_at: "2026-09-06T09:00:00Z",
    last_test_ok: true,
    last_test_text: "Wrote an empty QuickBooks file.",
    connected_at: "2026-09-06T08:00:00Z",
    credential: null,
    expiry: {
      state: "unknown" as const,
      expires_at: null,
      days_left: null,
      window_days: 14,
      version: null,
    },
  };
  const card = (connection: ConnectionRow | null) =>
    [{ key: ACCOUNTING_PROVIDER, connection } as unknown as ProviderCard];

  it("names the saved destination and hands back the format the picker must show", () => {
    const saved = savedExportTarget(card(CONNECTION));
    expect(saved?.describe).toBe("Month-end journal · QuickBooks · downloaded here");
    expect(saved?.format).toBe("iif");
  });

  it("answers null for every shape that is NOT a remembered destination", () => {
    // Each of these renders S43 exactly as it was before wave J.
    expect(savedExportTarget(undefined)).toBeNull(); // the read did not answer
    expect(savedExportTarget([])).toBeNull(); // no accounting card
    expect(savedExportTarget(card(null))).toBeNull(); // card, no connection
    expect(savedExportTarget(card({ ...CONNECTION, status: "not_set_up" }))).toBeNull();
    expect(savedExportTarget(card({ ...CONNECTION, enabled: false }))).toBeNull();
    expect(savedExportTarget(card({ ...CONNECTION, describe: null, label: null }))).toBeNull();
  });

  it("STILL names it when the last test failed — a destination is not un-told", () => {
    // The judgment worth pinning: hiding the line on `not_working` would make
    // S43 say *nowhere* about a destination S8 is showing at that moment, which
    // is two screens disagreeing about one fact.
    const saved = savedExportTarget(card({ ...CONNECTION, status: "not_working" }));
    expect(saved?.describe).toBe("Month-end journal · QuickBooks · downloaded here");
  });

  it("refuses a saved format the ledger does not take, rather than passing it through", () => {
    // A manifest can grow a fifth format before the ledger's four move. An
    // unvalidated string would set the picker to a value no <option> carries,
    // which renders as an EMPTY select and reads as a bug in the screen.
    const saved = savedExportTarget(
      card({ ...CONNECTION, settings: { ...CONNECTION.settings, file_format: "xlsx" } }),
    );
    expect(saved?.describe).toBe("Month-end journal · QuickBooks · downloaded here");
    expect(saved?.format).toBeUndefined();
  });

  it("the sentence a clerk reads is the destination and nothing else", () => {
    // B14 rule 32 — one sentence, no rule id, no internal code.
    const line = i18n.getFixedT("en")("finance.export.savedTarget", {
      destination: "Month-end journal · QuickBooks · downloaded here",
    });
    expect(line).toBe("Going to Month-end journal · QuickBooks · downloaded here.");
    for (const forbidden of ["BR-", "OQ-", "DEF-", "CR-", "accounting_file", "iif"]) {
      expect(line).not.toContain(forbidden);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-016@7e1e359 (the same sources the four screens were authored from: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md · EP-LED-04 · EP-LED-05 · 09-ledger/02-business-rules.md · 08-qa/01-e2e/journeys/J19-month-end-close.md)
// generated: 2026-08-15 by story-coder (DEF-112 lane)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — a test file calls no endpoint) E=deferred(no-frontend-half — this IS the frontend half's test) F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED, three times, and each failure is quoted in the lane report: forcing the trial balance to render "Balanced" unconditionally → `AssertionError: expected '<div class="met-panel">…' not to contain 'Balanced'`; filling the collected tax column from the billed figure → `AssertionError: expected 3 to be 2`; restoring DEF-095's `f.` prefix → `AssertionError: expected '/api/brazosbend/finance/revenue-ar?f.…' not to contain 'f.from='` (that one lives in src/api/periodBounds.test.ts).
// exceptions: the four screens are not MOUNTED — each pulls a live query client, a router and a permissions context, and what is worth pinning here is which figures the screens refuse, not that React renders. Mounting is the J19 browser journey's job.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────


describe("DEF-LED-6657 · P4.12 — tab 6 is two screens, so the head names the one you are on", () => {
  /** ⚠ **THIS CASE EXISTS BECAUSE THE SCREEN SHIPPED WITH THE WRONG HEAD AND
   * NOTHING NOTICED.** The Close/Export strip switched views and the page head
   * went on reading *"Close September"* over the export filter, the preview
   * and the hand-over history. p069 draws this view's head as **Export**, and
   * B14 rule 44 makes the drawing what is on the screen.
   *
   * WHAT WOULD MAKE THIS CHECK PASS WRONGLY — asked first (law 7, habit 2):
   * asserting only that the two keys DIFFER would pass if both were wrong, and
   * asserting one view would pass while the other regressed. So both views are
   * named, both keys are spelled out, and every declared view is covered. */
  it("names a different, correct head key for each of the two views", () => {
    expect(headTitleKeyFor("close")).toBe("finance.close.headTitle");
    expect(headTitleKeyFor("export")).toBe("finance.export.headTitle");
  });

  it("covers every view the strip declares, so a third one cannot arrive headless", () => {
    const keys = CLOSE_EXPORT_VIEWS.map((view) => headTitleKeyFor(view));
    expect(new Set(keys).size).toBe(CLOSE_EXPORT_VIEWS.length);
  });

  it("every head key it returns is really in the catalogue", () => {
    /* The half that bites hardest: a key that resolves to nothing renders as
       the key itself, which reads on screen as a bug report. */
    for (const view of CLOSE_EXPORT_VIEWS) {
      const key = headTitleKeyFor(view);
      expect(i18n.exists(key), `${key} is not in en.json`).toBe(true);
    }
  });
});
