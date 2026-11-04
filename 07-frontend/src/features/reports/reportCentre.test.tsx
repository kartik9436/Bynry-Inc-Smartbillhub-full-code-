// ── Trace ──────────────────────────────────────────────
// Story:    US-REP-001 (S44 library) · US-REP-002 (S46 viewer) · US-REP-003
//           (IS-11 download) · US-REP-005 (AR ageing) · US-REP-006 (billing
//           register) · US-REP-007 (payments by method)   Screens: S44 · S46
// Rules:    BR-REP-001 (every money render names its basis — an unlabeled one
//           is a FAIL by contract) · BR-REP-002 (the screen computes nothing) ·
//           BR-REP-006 (live vocabularies) · BR-REP-014 (a deposit is never
//           inside a collection figure) · BR-REP-024 (a figure that cannot be
//           computed prints its REASON — never 0, never "null") · BR-SHL-025
//           (a control this deployment cannot honour is stated, not hidden) ·
//           CLAUDE.md rule 3 (a quantity with its unit)
// ───────────────────────────────────────────────────────
// THE NEGATIVE ASSERTIONS ARE WHY THIS FILE EXISTS.
//
// The easy S44 is twenty-three identical tiles that all open a viewer. Thirteen
// of them would render an empty table, and an empty table is a CLAIM: "no account
// is 90+ days overdue" is a different sentence from "this product cannot tell
// you who is". So the first case below asserts that an unavailable card is not
// a link, and that it carries a reason a person can read.
//
// The easy S46 KPI tile is one that prints 0.00 when the server sent null. On
// 2026-08-16 a tile in this product rendered the literal text `null USD`. The
// KPI cases assert the sentence, and assert that neither "0" nor "null" is
// anywhere in the rendered markup.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ReportCard, ReportKpi } from "@/api/reportsEndpoints";

import {
  MONEY_COLUMNS,
  REPORT_FILTERS,
  ReportCell,
  ReportTotalsRow,
} from "./ReportViewerPage";
// ⚠ **THE TILE AND THE TOTALS ROW MOVED IN `P2.5`/`P2.13` AND THE CASES DID
// NOT CHANGE.** `KpiTile` is now `ReportKpiTile` in its own component file and
// the bespoke `ReportTable` is gone — 2·1 renders on the shared `DataTable`, so
// what is left of that table here is its FOOTER, which is the only part of it
// that carried a rule. Every assertion below is the one it was before.
import { ReportKpiTile } from "./ReportKpiBand";
import { ROUTE_TARGETS, ReportCardTile, reasonSentence, targetFor } from "./ReportLibraryPage";
import { keyForSegment, viewerRouteFor } from "./reportsShared";

const t = i18n.getFixedT("en");
const tenantPath = (path: string) => `/brazosbend${path}`;

// ⚠ **THE CARD GREW FIELDS WITH `P1.1` AND THE ASSERTIONS BELOW DID NOT MOVE.**
// A card now carries the NAME the server resolved out of `report_definitions`
// (it used to carry none at all, and the screen named it through
// `t("reports.card.<key>.name")`), the group's and sub-group's own names, and
// `basis_label` — the drawing's own words, because *As at*, *Read date* and
// *Effective date* are three different facts that all map to one basis code.
function card(overrides: Partial<ReportCard>): ReportCard {
  return {
    key: "ar_aging",
    name: "AR Ageing",
    name_overridden: false,
    group: "receivables",
    group_name: "Receivables",
    sub_group: "receivables_arrears",
    kind: "viewer",
    origin: "built_in",
    badge: "AR",
    available: true,
    basis: "posting",
    basis_label: "Posting date",
    reason_code: null,
    reason_detail: null,
    routes_to_screen: null,
    service_codes: [],
    pinned: false,
    ...overrides,
  };
}

function render(node: React.ReactElement): string {
  return renderToStaticMarkup(<MemoryRouter>{node}</MemoryRouter>);
}

// ═══════════════════════════════════════════════════════════════════════════
// US-REP-001 — the library
// ═══════════════════════════════════════════════════════════════════════════
describe("US-REP-001 · S44 report library", () => {
  it("US-REP-001 TC-3: an available report card links to its viewer", () => {
    const html = render(
      <ReportCardTile card={card({})} t={t} tenantPath={tenantPath} />,
    );
    expect(html).toContain('href="/brazosbend/reports/ar-aging"');
    // BR-REP-001 — the basis is on the CARD, before anyone opens the report.
    expect(html).toContain("Posting date");
  });

  it("US-REP-001 TC-2: a route card goes to the screen that OWNS it, never to a second implementation", () => {
    const html = render(
      <ReportCardTile
        card={card({ key: "trial_balance", kind: "route", routes_to_screen: "S56" })}
        t={t}
        tenantPath={tenantPath}
      />,
    );
    expect(html).toContain('href="/brazosbend/finance/gl"');
    // BR-REP-003/005: reports NEVER re-implements a ledger-owned surface, so
    // every route target is a path that already belongs to another module.
    expect(Object.values(ROUTE_TARGETS)).not.toContain("/reports/trial-balance");
  });

  it("US-REP-001 TC-4: an UNAVAILABLE card opens nothing and says why", () => {
    const unavailable = card({
      key: "read_completeness",
      group: "operations",
      kind: "absent",
      available: false,
      basis: null,
      reason_code: "owning_module_publishes_no_report_read",
      reason_detail: "Metering publishes a paginated read LIST and no completeness read-model.",
    });
    const html = render(<ReportCardTile card={unavailable} t={t} tenantPath={tenantPath} />);

    // THE ASSERTION THIS FILE EXISTS FOR: no link. A tile that opens a viewer
    // onto an empty table tells a utility nobody is missing a read.
    expect(html).not.toContain("<a ");
    expect(html).not.toContain("href=");
    expect(targetFor(unavailable)).toBeNull();
    // …and the reason is a SENTENCE, in the user's language, not a code.
    expect(html).toContain("does not publish them as a report yet");
    expect(html).not.toContain("owning_module_publishes_no_report_read");
  });

  it("US-REP-001: a reason code with no catalogue entry still produces a sentence", () => {
    const sentence = reasonSentence(
      card({ available: false, reason_code: "a_code_nobody_has_translated" }),
      t,
    );
    // Never the raw code, and never blank — a card with an empty reason reads
    // as a card that is merely broken.
    expect(sentence).toBe("This report cannot be produced yet.");
  });

  it("US-REP-001: the URL segment and the API key are two vocabularies (DEF-131)", () => {
    expect(viewerRouteFor("ar_aging")).toBe("/reports/ar-aging");
    expect(keyForSegment("ar-aging")).toBe("ar_aging");
    // ⚠ **THE THIRD ASSERTION CHANGED ON 2026-09-27 AND WHAT IT GUARDS DID
    // NOT** (`P0.7`, lane REP-P2-TAIL). It read
    // `expect(keyForSegment("ar-ageing")).toBe("ar-ageing")`, which asserted
    // the MECHANISM of the deleted `VIEWER_SEGMENTS` map — an unknown segment
    // fell through its `?? segment` fallback untouched. The map held four rows
    // while the catalogue serves 46 definitions, so 42 keys were already
    // taking that fallback and working by accident; it is now
    // `segment.replace(/-/g, "_")` for every key alike.
    //
    // **THE GUARANTEE IS UNCHANGED AND IS WHAT IS ASSERTED BELOW: A TYPO MUST
    // NEVER BECOME A DIFFERENT REPORT.** `ar-ageing` is a misspelling of
    // `ar-aging`; it must not resolve to `ar_aging`, and it must reach the
    // server, which refuses it with VAL-005 and enumerates what it serves.
    // Both halves are asserted, because asserting only the first would pass
    // for a function that returned the empty string.
    expect(keyForSegment("ar-ageing")).not.toBe("ar_aging");
    expect(keyForSegment("ar-ageing")).toBe("ar_ageing");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// US-REP-002 — the viewer
// ═══════════════════════════════════════════════════════════════════════════
function kpi(overrides: Partial<ReportKpi>): ReportKpi {
  return { key: "total_ar", value: "184320.000000", kind: "money", detail: null, reason_code: null, ...overrides };
}

describe("US-REP-002 · S46 viewer", () => {
  it("US-REP-002 TC-4: a money KPI carries its basis", () => {
    const html = renderToStaticMarkup(
      <ReportKpiTile kpi={kpi({})} currency="USD" basis="posting" t={t} locale="en-US" />,
    );
    expect(html).toContain("Posting date");
  });

  it("US-REP-002 TC-4b: the SAME tile on a cash report names the CLEARING basis", () => {
    const html = renderToStaticMarkup(
      <ReportKpiTile
        kpi={kpi({ key: "total_received", value: "593.170000" })}
        currency="USD"
        basis="clearing"
        t={t}
        locale="en-US"
      />,
    );
    // The two reports disagree about the basis and BOTH are right — which is
    // the entire reason BR-REP-001 exists.
    expect(html).toContain("Clearing date");
    expect(html).not.toContain("Posting date");
  });

  it("BR-REP-024: a KPI the server could not compute prints its REASON, never 0 and never 'null'", () => {
    const html = renderToStaticMarkup(
      <ReportKpiTile
        kpi={kpi({
          key: "exceptions",
          value: null,
          kind: "count",
          reason_code: "exception_count_is_per_run_not_per_window",
        })}
        currency="USD"
        basis="posting"
        t={t}
        locale="en-US"
      />,
    );
    expect(html).toContain("Counted per bill run, not per date range");
    // The 2026-08-16 defect, asserted as an absence.
    expect(html).not.toContain("null");
    expect(html).not.toContain(">0<");
  });

  it("BR-REP-024: an unknown reason code still produces a sentence rather than a blank tile", () => {
    const html = renderToStaticMarkup(
      <ReportKpiTile
        kpi={kpi({ value: null, reason_code: "something_new" })}
        currency="USD"
        basis="posting"
        t={t}
      />,
    );
    expect(html).toContain("Cannot be worked out");
  });

  it("CLAUDE.md rule 3: a usage cell renders every quantity WITH its unit and never adds them", () => {
    const html = renderToStaticMarkup(
      <ReportCell
        reportKey="billing_register"
        column="usage"
        value={[
          { quantity: "684", unit: "kWh" },
          { quantity: "26.24", unit: "kgal" },
        ]}
        currency="USD"
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
      />,
    );
    expect(html).toContain("684 kWh");
    expect(html).toContain("26.24 kgal");
    // 684 + 26.24 = 710.24 — the number a screen produces when it forgets that
    // kWh and kgal are not the same thing.
    expect(html).not.toContain("710");
  });

  it("DEF-081: an amount whose currency could not be derived is shown WITHOUT a guessed symbol", () => {
    const html = renderToStaticMarkup(
      <ReportCell
        reportKey="billing_register"
        column="amount"
        value="247.870000"
        currency={null}
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
      />,
    );
    // ⚠ **NO SYMBOL, AND STILL TWO DECIMALS** (`DEF-REP-6902`). This case
    // asserted `247.870000` until 2026-09-27 — `DEF-081`'s half, correctly, and
    // storage width with it. Hard rule 2 counts the DIGITS a person reads and
    // does not ask whether a currency code is available, and the tax
    // remittance printed `531.140000` in its cell, its footer and its tile for
    // exactly this reason. The symbol assertion below is the part `DEF-081`
    // owns and it is unchanged.
    expect(html).toContain("247.87");
    expect(html).not.toContain("247.870000");
    expect(html).not.toContain("$");
  });

  // ── `DEF-REP-6902` / `DEF-REP-6903` · THE COLUMN SAYS WHAT KIND IT IS ─────
  //
  // ⚠ **PROVED RED FIRST, AND THE RED IS ON A SCREENSHOT AS WELL AS HERE.**
  // Walked at 1440 on 2026-09-27 before a line of this was written: **133
  // figures with more than two decimal places in the body of six reports and
  // ten in their footers**, `15816.000000` in the trend pack's footer directly
  // under a tile reading `$15,816.00` for the same figure. Each case below
  // fails on the shipped code by naming a report `MONEY_COLUMNS` does not
  // contain — which is forty-one of the forty-six.
  const KINDS = {
    money: { type: "money", unit: null, unit_from: null, money_basis: "posting", scale: 4 },
    percent: { type: "percent", unit: null, unit_from: null, money_basis: null, scale: 6 },
    quantity: { type: "quantity", unit: null, unit_from: "unit", money_basis: null, scale: null },
    count: { type: "count", unit: null, unit_from: null, money_basis: null, scale: null },
  } as const;

  it("DEF-REP-6902: a money column the dataset declares reads two decimals on a report no map names", () => {
    // `account_census` is deliberately NOT in `MONEY_COLUMNS` — that is the
    // whole defect. Its BALANCE column printed `247.300000` at a clerk.
    expect(MONEY_COLUMNS.account_census).toBeUndefined();
    const html = renderToStaticMarkup(
      <ReportCell
        reportKey="account_census"
        column="balance"
        value="247.300000"
        currency="USD"
        meta={KINDS.money}
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
      />,
    );
    expect(html).toContain("247.30");
    expect(html).not.toContain("247.300000");
  });

  it("DEF-REP-6902: a percentage reads two decimals and never six", () => {
    const html = renderToStaticMarkup(
      <ReportCell
        reportKey="service_order_activity"
        column="on_time_pct"
        value="100.000000"
        currency="USD"
        meta={KINDS.percent}
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
      />,
    );
    expect(html).toContain("100.00%");
    expect(html).not.toContain("100.000000");
  });

  it("DEF-REP-6903: a quantity reads as a meter reads it, trailing zeros dropped", () => {
    const shown = (value: string) =>
      renderToStaticMarkup(
        <ReportCell
          reportKey="usage_and_ranking"
          column="reading"
          value={value}
          currency={null}
          meta={KINDS.quantity}
          t={t}
          timeZone="America/Chicago"
          dateFormat="MM/DD/YYYY"
        />,
      );
    // The walk of 2026-10-12 (`CR-179-BRC10`): grouped as a person reads it,
    // `46,754` — and still trimmed, never `46,754.0`.
    expect(shown("46754.000000")).toContain("46,754");
    expect(shown("46754.000000")).not.toContain("46,754.0");
    // ⚠ **IT TRIMS AND IT DOES NOT ROUND.** A demand of 41.2 reads `41.2`, not
    // `41.20` and certainly not `41`. A quantity that carries real digits keeps
    // every one of them.
    expect(shown("41.200000")).toContain("41.2");
    expect(shown("41.200000")).not.toContain("41.20");
    expect(shown("0.125000")).toContain("0.125");
  });

  it("DEF-REP-6902: the FOOTER total is the same kind of thing as its column", () => {
    const html = renderToStaticMarkup(
      <ReportTotalsRow
        reportKey="trend_pack"
        columns={["narrative", "debit", "on_time_pct", "lines"]}
        totals={{ debit: "15816.000000", on_time_pct: "100.000000", lines: 36 }}
        columnMeta={{ debit: KINDS.money, on_time_pct: KINDS.percent, lines: KINDS.count }}
        currency="USD"
        t={t}
      />,
    );
    // The figure the PO photographed, and the tile above it reads $15,816.00.
    expect(html).toContain("15,816.00");
    expect(html).not.toContain("15816.000000");
    expect(html).toContain("100.00%");
    // A COUNT under a grouped report wore a currency symbol before this.
    expect(html).toContain("36");
  });

  it("DEF-REP-6902: a column no dataset declares renders exactly as it did before", () => {
    // The half that keeps the forty-six that were already right from moving:
    // no `meta` means no new branch, which is why this fix could not regress a
    // report it was not about.
    const html = renderToStaticMarkup(
      <ReportCell
        reportKey="ar_aging"
        column="total"
        value="247.870000"
        currency="USD"
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
      />,
    );
    expect(MONEY_COLUMNS.ar_aging).toContain("total");
    expect(html).toContain("247.87");
  });

  it("BR-REP-002: the footer is the SERVER's total — the screen sums nothing", () => {
    const html = renderToStaticMarkup(
      <table>
        <tfoot>
          <ReportTotalsRow
            reportKey="billing_register"
            columns={["invoice_no", "amount"]}
            // 553.69 is the SERVER's figure for a three-bill month; only two
            // rows exist on this page, so a screen that summed its own rows
            // would print 264.29 and this assertion would catch it. Paging is
            // what makes that a live hazard rather than a theoretical one.
            totals={{ amount: "553.690000" }}
            currency="USD"
            t={t}
            locale="en-US"
          />
        </tfoot>
      </table>,
    );
    expect(html).toContain("553.69");
    expect(html).not.toContain("264.29");
  });

  it("P2.13: a tile with no number reads 'Not counted yet' and shows no internal code", () => {
    // The two faults the brief walked on 2026-09-23, asserted together: a
    // FALSE multi-currency sentence, and `currency_not_derivable` printed on
    // screen under the tile.
    const html = renderToStaticMarkup(
      <ReportKpiTile
        kpi={kpi({ value: null, reason_code: "nothing_owed_at_this_date" })}
        currency={null}
        basis="posting"
        t={t}
        locale="en-US"
      />,
    );
    expect(html).toContain("Not counted yet");
    expect(html).toContain("Nothing owed at this date");
    expect(html).not.toContain("More than one currency");
    expect(html).not.toContain("currency_not_derivable");
  });

  it("P2.13: a share renders its unit — `42%`, never a bare `42.0`", () => {
    const html = renderToStaticMarkup(
      <ReportKpiTile
        kpi={kpi({ key: "d31_60", value: "63.250000", detail: "42.0", detail_kind: "share" })}
        currency="USD"
        basis="posting"
        t={t}
        locale="en-US"
      />,
    );
    expect(html).toContain("42.0%");
  });

  it("US-REP-002: a report is offered only the filters IT accepts", () => {
    // The ageing takes an as-of date and a class; it does not take a window,
    // and a control the server ignores makes a report LOOK filtered.
    expect(REPORT_FILTERS.ar_aging).toContain("asOf");
    expect(REPORT_FILTERS.ar_aging).not.toContain("bill_type");
    expect(REPORT_FILTERS.payments_by_method).toContain("purpose");
    expect(REPORT_FILTERS.revenue_by_service_rate).toEqual(["window"]);
  });

  it("BR-SHL-023: every money column is declared, so a count never wears a currency symbol", () => {
    expect(MONEY_COLUMNS.ar_aging).toContain("total");
    expect(MONEY_COLUMNS.ar_aging).not.toContain("days_late");
    expect(MONEY_COLUMNS.payments_by_method).not.toContain("count");
    expect(MONEY_COLUMNS.revenue_by_service_rate).not.toContain("accounts");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-REP-001@c6c35b2 (co-packets US-REP-002/003/005/006/007; 04-docs/05-modules/12-reports/06-epics/EP-REP-01-report-center.md · EP-REP-02-canned-reports.md · 12-reports/02-business-rules.md BR-REP-001/002/006/014/024)
// screens: S44 · S46
// generated: 2026-08-16 by story-coder (reports lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — this file could not resolve ./ReportLibraryPage or ./ReportViewerPage before those screens existed. tsc✔ eslint✔ vitest✔
// exceptions: (1) the screens are exercised through their exported pieces (ReportCardTile, KpiTile, ReportCell, ReportTable) rather than by mounting the full page with a mocked query client — the same shape reports.test.tsx already uses for S59/S60, and it lets each assertion name the ONE thing it is about
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
