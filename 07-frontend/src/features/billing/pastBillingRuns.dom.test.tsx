// ── Trace ──────────────────────────────────────────────
// Change:  CR-101-BRC03 §07 — blueprint screen 27 `Past billing runs`, p145–p146
//          of `05-prototype/04 Billing, As Built.pdf`, read AS IMAGES at scale 2
//          and the table band again at scale 4 (B14 rule 42).
// Defects: DEF-BIL-5351 (the grey panel over a working read) · DEF-BIL-5352
//          (the run status never advances) · DEF-BIL-5371 (the read is not
//          paginated and serves no total)
// Rules:   B14 rule 15 (row actions are icons) · rule 16 (the pagination
//          footer) · rule 31 (no database id is a visible value) · rule 32 (one
//          stated absence, closed by default) · rule 37 (a drawn figure is an
//          illustration) · NFR-3
// ───────────────────────────────────────────────────────
// ⚠ **WHAT THIS FILE CAN AND CANNOT SEE, SAID FIRST (hard-won law 7).**
// `renderToStaticMarkup` performs no layout and fires no effect. It cannot tell
// you the columns line up, that the pager pages, or that the screen looks like
// p146. What it CAN tell you is **which columns this table declares, in which
// order, what each cell renders when the server says null, and that nothing
// internal reaches a clerk.** The layout half is the browser walk —
// `10-scripts/cr101_past_runs_walkthrough.mjs` — and saying which check covers
// what is the point of this paragraph.
//
// ══════════════════════════════════════════════════════════════════════════
// THE HANDSHAKE FIRED, AND THIS IS WHAT IT LOOKED LIKE
// ══════════════════════════════════════════════════════════════════════════
// Five things p146 draws were unserved when this screen was first built, and
// each was held by a **compile-time tripwire**: a type whose value is `false`
// while a field is absent and `true` once it lands, assigned to `false`. A hold
// with no test that fires when it expires is a promise nobody is keeping
// (hard-won law 2), and a runtime assertion could not have done this job — it
// would pass happily over a server that had started serving the field, which is
// the exact case they existed to catch.
//
// The sibling lane landed the server on 2026-09-15 and `tsc` went red, verbatim:
//
//     pastBillingRuns.dom.test.tsx(241,11): error TS2322:
//       Type 'false' is not assignable to type 'true'.
//
// So the tripwires are REPLACED BY ASSERTIONS ON WHAT ARRIVED — the VALUE
// column, the four tiles, the status vocabulary, the three filter chips and the
// server's own total — rather than deleted, and rather than loosened until they
// passed again.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { TenantRegionalProvider } from "@/components/TenantRegional";
import { internalReferencesInMarkup } from "@/testSupport/internalReferences";

import { PastBillingRunsPanel, tileRow } from "./PastBillingRunsPanel";
import type { PastRunRow } from "./PastBillingRunsPanel";
import type { BillRunTiles } from "@/api/endpoints";

const t = (key: string): string => i18n.t(key);

const CYCLE_A = "01a0a444-5529-7d5b-b51b-a0f0546811c6";
const CYCLE_B = "01a0a44f-d7e1-7961-a315-468867798cf6";

/**
 * ⚠ **EVERY FIGURE HERE IS THIS FIXTURE'S OWN AND NONE IS THE DRAWING'S**
 * (B14 rule 37). p146 draws 34 runs, 11,842 bills and `BR-2609-0051`; a test
 * asserting those would be a test about the illustrator's choice of example.
 * What IS taken from the drawing is the SHAPE of the rows its notes argue for:
 *
 *   · two runs over ONE period, on different cycles — p146 note 2, *"a utility
 *     bills in cycles, not months"*;
 *   · a run that issued NOTHING and is still a row — note 3, *"a run that
 *     vanished would leave a clerk unable to explain a gap in the numbering"*;
 *   · a run with no number and no actor, which is what the LIVE demo tenant
 *     actually holds on one of its three rows.
 */
const ROWS: PastRunRow[] = [
  {
    id: "01a0a445-0000-7000-8000-00000000aa01",
    run_no: "RUN-0002",
    cycle_id: CYCLE_A,
    period_start: "2026-08-01",
    period_end: "2026-08-31",
    issued_at: "2026-09-02T09:00:00+00:00",
    accounts: 39,
    bills_issued: 39,
    held: 0,
    status: "issued",
    bill_type: "cycle",
    created_at: "2026-08-01T08:00:00+00:00",
    ran_by_name: "Dana Whitfield",
    cycle_code: "CY-001",
    value: "346386.550000",
    value_currency: "USD",
  },
  {
    id: "01a0a445-0000-7000-8000-00000000aa02",
    run_no: "RUN-0003",
    cycle_id: CYCLE_B,
    period_start: "2026-08-01",
    period_end: "2026-08-31",
    issued_at: "2026-09-02T09:00:00+00:00",
    accounts: 12,
    bills_issued: 12,
    held: 2,
    // p146 note 4 — *Corrected* is a status the correction workflow sets, and
    // it is the only screen where a clerk can see that a whole run was redone.
    status: "corrected",
    bill_type: "cycle",
    created_at: "2026-08-01T09:00:00+00:00",
    ran_by_name: "M. Okonkwo",
    cycle_code: "CY-003",
    value: "104406.200000",
    value_currency: "USD",
  },
  {
    // The abandoned shape: issued nothing, and still a row at zero.
    id: "01a0a445-0000-7000-8000-00000000aa03",
    run_no: null,
    cycle_id: null,
    period_start: "2026-07-01",
    period_end: "2026-07-31",
    issued_at: null,
    accounts: 0,
    bills_issued: 0,
    held: 0,
    // p146 note 3 — *Abandoned is drawn, and at zero*: a run that issued
    // nothing still occupies its number, so a clerk can explain a gap in the
    // numbering to an auditor.
    status: "abandoned",
    bill_type: "cycle",
    created_at: "2026-07-01T08:00:00+00:00",
    ran_by_name: null,
    cycle_code: null,
    value: null,
    value_currency: null,
  },
];

const CYCLES = [
  { id: CYCLE_A, code: "CY-001" },
  { id: CYCLE_B, code: "CY-003" },
];

/** ⚠ THIS FIXTURE'S OWN FIGURES, NOT p146's (B14 rule 37). The drawing's
 *  34 / 11,842 / 6 / 58 min are the illustrator's examples; what is taken from
 *  it is the SHAPE — four tiles, each a count with a line beneath it. */
const TILES: BillRunTiles = {
  year: 2026,
  runs: { count: 3, cycles: 2 },
  bills_issued: { count: 51, value: "450792.750000", currency: "USD" },
  exceptions: { runs: 1, all_resolved: false },
  // `DEF-BIL-5376`: nothing records how long a run took, and the shared type
  // says so with the literal `null`. The tile states the absence.
  longest_run: null,
};

/** ⚠ MOUNTED UNDER THE REAL PATH PATTERN (hard-won law 2's fixture clause).
 *  A bare `MemoryRouter` with no `:tenant` leaves every address the panel
 *  builds as `//billing/run?…` — a protocol-relative URL to another host, which
 *  reads as a perfectly good string to `toContain`. */
function render(rows: readonly PastRunRow[] = ROWS): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: Infinity } },
  });
  // The keys the panel builds for its FIRST request: no cycle chosen, page 1 at
  // the default size. Seeded rather than fetched, so these cases assert over the
  // TABLE and not over a loading skeleton.
  client.setQueryData(
    ["billing", "runs", "history", "", "", "", "", 1, 50],
    { rows, total: rows.length, tiles: rows.length === 0 ? null : TILES },
  );
  client.setQueryData(["cycles", "all", "runs-history"], CYCLES);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <MemoryRouter initialEntries={["/brazosbend/billing/history"]}>
          <Routes>
            <Route path="/:tenant/billing/:tab" element={<PastBillingRunsPanel />} />
          </Routes>
        </MemoryRouter>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

describe("§07 screen 27 — Past billing runs is the workspace the drawing needs", () => {
  it("TC-I1 · declares the drawn columns, in the drawn order", () => {
    const html = render();
    // p146's header row, left to right — all SEVEN now, VALUE between BILLS
    // and RUN BY exactly where the drawing puts it.
    const drawn = [
      t("billing.runs.col.run"),
      t("billing.runs.col.cycle"),
      t("billing.runs.col.period"),
      t("billing.runs.col.bills"),
      t("billing.runs.col.value"),
      t("billing.runs.col.runBy"),
      t("billing.runs.col.status"),
    ];
    let cursor = -1;
    for (const label of drawn) {
      const at = html.indexOf(`>${label}<`, cursor);
      expect(at, `column "${label}" is missing or out of order`).toBeGreaterThan(cursor);
      cursor = at;
    }
  });

  it("TC-I2 · every row opens the run it names — the ROW, the number and the icon", () => {
    const html = render();
    // p146: *"Every row opens the run it names … A table you cannot drill into
    // is a report, and this is a workspace."*
    //
    // ⚠ **THIS CASE WAS WRONG WHEN IT WAS FIRST WRITTEN, AND THE RED-FIRST PROOF
    // IS WHAT FOUND IT (hard-won law 7's *looking at the wrong thing*).** It
    // asserted `toContain("/brazosbend/billing/run?run=<id>")` and called that
    // "the row opens the run" — but the identity link and the icon each carry
    // that same address, so pointing `rowHref` at a DIFFERENT run left every
    // assertion green. The row target is asserted BY ITS OWN ATTRIBUTE below.
    for (const row of ROWS) {
      expect(
        html,
        `the ROW does not target ${row.run_no ?? row.id}`,
      ).toContain(`data-row-href="/brazosbend/billing/run?run=${row.id}"`);
    }
    // The number itself is the link, which is how `All bills` builds a bill
    // number — not merely an icon at the far end of the row.
    expect(html).toMatch(
      new RegExp(`href="/brazosbend/billing/run\\?run=${ROWS[0].id}"[^>]*>RUN-0002`),
    );
    // And B14 rule 15's icon, with its accessible name — the drawn `Open`
    // built as the rule requires rather than as the text link p146 inks.
    expect(html).toMatch(
      new RegExp(`aria-label="${t("billing.runs.action.open")}"`),
    );
  });

  it("TC-I3 · two runs in one period are two rows, and the period is its own column", () => {
    const html = render();
    // p146 note 2 — `08-A` and `08-B` both cover August, and collapsing the
    // period into the cycle name hides the thing a clerk checks continuity
    // against. Both cycle codes render — from the SERVER's `cycle_code` now,
    // never from a uuid resolved in the browser — and August renders twice.
    expect(html).toContain("CY-001");
    expect(html).toContain("CY-003");
    expect(html.split("08/01/2026").length - 1).toBe(2);
  });

  it("TC-I4 · an abandoned run is a row, at zero, with its absences stated", () => {
    const html = render();
    // p146 note 3. The third fixture row issued nothing and carries no number,
    // no cycle and no actor — none of which removes it from the table.
    expect(html).toContain(t("billing.runs.cell.noNumber"));
    expect(html).toContain(t("billing.runs.cell.noCycle"));
    expect(html).toContain(t("billing.runs.cell.noRunBy"));
    expect(html).toContain(">0<");
  });

  it("TC-I5 · the cycle is a CODE and no database id reaches the screen (B14 rule 31)", () => {
    const html = render();
    // The ids are in `href`s, which is a URL and not the visible value of a
    // field. What rule 31 forbids is a uuid rendered AS the cell — so the check
    // is that no id appears in text, which is what `>…<` tests.
    expect(html).not.toContain(`>${CYCLE_A}<`);
    expect(html).not.toContain(`>${CYCLE_B}<`);
    expect(html).toContain(">CY-001<");
  });

  it("TC-I6 · nothing internal reaches a clerk (DEF-BIL-5339's instrument)", () => {
    // Reads RENDERED text and the two attributes a browser shows — `title` and
    // `aria-label` — never `data-*`, because the 2026-08-19 ruling put the
    // reference there on purpose. The gap disclosure's `data-rule-ref` names
    // three defect ids and is invisible to this by design.
    expect(internalReferencesInMarkup(render())).toEqual([]);
  });

  it("TC-I7 · the drawn VALUE column renders through MoneyCell, at two decimals", () => {
    // ⚠ **THIS WAS A TRIPWIRE AND IS NOW AN ASSERTION.** It held
    // `HasKey<PastRunRow,"value"> = false` while no endpoint served a run's
    // value; the day the row type declared it, `tsc` refused the line. What it
    // asserts now is the thing the tripwire was protecting: CLAUDE.md hard rule
    // 2 — money is STORED to four decimals and DISPLAYED at two, always beside
    // its CHAR(3), through the one MoneyCell.
    const html = render();
    expect(html).toContain("346,386.55");
    expect(html).not.toContain("346386.550000");
    expect(html).toContain("$");
    // A run that issued nothing has NO value to state — never a zero, which
    // would read as *it billed nothing* rather than *it never billed*.
    expect(html).toContain(t("billing.runs.cell.noValue"));
  });

  it("TC-I8 · the footer's total is the SERVER's, never a count of the rows on screen", () => {
    // `NFR-3`. The seeded page carries its own total; nothing in the panel adds
    // up `rows.length`. At a 40,000-account utility a client-side total is a
    // page size wearing a total's clothes.
    const html = render();
    expect(html).toContain("Rows per page");
    // The panel reads `runsQuery.data.total`. Seeding a total that does NOT
    // match the row count is what proves it is read rather than derived.
    expect(renderWithTotal(ROWS, 87)).toContain("87");
  });

  it("TC-I9 · the status is the column's own word, including the two only this screen shows", () => {
    // ⚠ **ALSO A TRIPWIRE THAT FIRED.** It held `string extends
    // PastRunRow["status"]` while the column was an open string nothing
    // advanced; `runs.record_run_outcome` advances it now, so the pill says
    // what the run IS. `Corrected` and `Abandoned` are the two words p146 draws
    // that no composed sentence could ever have produced.
    //
    // ⚠ **SCOPED TO THE PILL, AND THE RED-FIRST PROOF IS WHY.** As first written
    // this searched the WHOLE page for each word and stayed GREEN when the pill
    // was mutated back to a composed *Issued / Not issued* sentence — because
    // the Status FILTER lists all five words in its panel, so every assertion
    // found its string somewhere else on the page. Law 7's *looking at the wrong
    // thing*, in a case written to replace a tripwire that caught exactly that
    // class of miss.
    const html = render();
    for (const status of ["issued", "corrected", "abandoned"]) {
      const word = t(`billing.runs.status.${status}`);
      expect(html, `no status PILL reads "${word}"`).toMatch(
        new RegExp(`<span class="pill[^"]*">${word}</span>`),
      );
    }
  });

  it("TC-I13 · the four drawn tiles are the server's aggregate, in the drawn order", () => {
    const html = render();
    let cursor = -1;
    for (const label of [
      t("billing.runs.tile.runs"),
      t("billing.runs.tile.bills"),
      t("billing.runs.tile.exceptions"),
      t("billing.runs.tile.longest"),
    ]) {
      const at = html.indexOf(label, cursor);
      expect(at, `tile "${label}" is missing or out of order`).toBeGreaterThan(cursor);
      cursor = at;
    }
    // The money under BILLS ISSUED is a money figure and obeys hard rule 2.
    expect(html).toContain("450,792.75");
  });

  it("TC-I14 · no tile is computed from the rows on screen", () => {
    // The fixture's tiles deliberately DISAGREE with its rows: three rows, and
    // a tile saying 3 runs over 2 cycles and 51 bills. A panel that counted
    // what it could see would print the row figures instead — which is the
    // `NFR-3` breach this case exists to make impossible to introduce quietly.
    const tiles = tileRow(TILES, ((key: string, vars?: Record<string, unknown>) =>
      `${key}:${JSON.stringify(vars ?? {})}`) as never);
    expect(tiles.map((tile) => tile.id)).toEqual(["runs", "bills", "exceptions", "longest"]);
    expect(tiles[0]).toMatchObject({ value: String(TILES.runs.count) });
    expect(tiles[1]).toMatchObject({ value: String(TILES.bills_issued.count) });
    expect(tiles[2]).toMatchObject({ value: String(TILES.exceptions.runs) });
  });

  it("DEF-BIL-9007 · counts are grouped: 40,017 bills, never 40017", () => {
    const tiles = tileRow(
      { ...TILES, bills_issued: { count: 40017, value: "7371905.32", currency: "USD" } },
      ((key: string) => key) as never,
    );
    expect(tiles[1]).toMatchObject({ value: "40,017" });
  });

  it("TC-I15 · a tile with nothing behind it states the absence rather than printing a zero", () => {
    const tiles = tileRow(
      { ...TILES, bills_issued: { count: 0, value: null, currency: null } },
      ((key: string) => key) as never,
    );
    // `KpiTile` is a union — a money tile has no `value` — so the narrowing is
    // asserted rather than assumed: a tile that became a money tile would fail
    // here rather than silently reading `undefined`.
    expect(tiles[3]).toHaveProperty("value", "billing.runs.tile.noLongest");
    expect(tiles[3].detail).toBeUndefined();
    expect(tiles[1].detail).toBe("billing.runs.tile.noValue");
  });

  it("TC-I10 · the grey panel's key is retired, and nothing renders it", () => {
    // `DEF-BIL-5351`. The tab said *"It arrives with the billing run work."*
    // over a read that had answered for weeks. A key with no consumer is the
    // half a grep can check; the other half is that this screen renders instead,
    // which every case above asserts.
    expect(i18n.exists("billing.arrives.history")).toBe(false);
  });

  it("TC-I11 · the empty state is the drawn empty state, not a blank table", () => {
    const html = render([]);
    expect(html).toContain(t("billing.runs.empty"));
    expect(html).toContain(t("billing.runs.emptyHelper"));
  });

  it("TC-I12 · the three drawn filter chips are declared, and the search box has its prompt", () => {
    // ⚠ **THIS CASE REPLACES ONE THAT TESTED A CLIENT-SIDE CYCLE LOOKUP, WHICH
    // IS DELETED.** The read serves `cycle_code`, so the browser resolves
    // nothing; and it accepts `q`, `f.cycle_id`, `f.status` and `f.year`, so all
    // three chips p146 draws are real. A declared filter with no control is dead
    // configuration (`G45`), and a declared search with no prompt fails B14
    // rule 19 — both are asserted through what the panel RENDERS.
    //
    // ⚠ **SCOPED TO THE FILTER PANEL'S OWN `<legend>`, AND AGAIN THE RED-FIRST
    // PROOF IS WHY.** Searching the whole page for "Status" stayed GREEN with
    // the chip's label blanked, because the COLUMN header carries the same word.
    // The legend is the element `FilterBar` gives each declared dimension, and
    // it is what a screen reader announces with the option.
    const html = render();
    for (const label of [
      t("billing.runs.filter.cycle"),
      t("billing.runs.filter.status"),
      t("billing.runs.filter.year"),
    ]) {
      expect(html, `no filter legend reads "${label}"`).toMatch(
        new RegExp(`<legend[^>]*>${label}</legend>`),
      );
    }
    expect(html).toContain(t("billing.runs.search"));
  });

});

/** A second render seeding a total that deliberately disagrees with the row
 *  count, so TC-I8 can tell a total that is READ from one that is DERIVED. */
function renderWithTotal(rows: readonly PastRunRow[], total: number): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: Infinity } },
  });
  client.setQueryData(["billing", "runs", "history", "", "", "", "", 1, 50], {
    rows,
    total,
    tiles: TILES,
  });
  client.setQueryData(["cycles", "all", "runs-history"], CYCLES);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <MemoryRouter initialEntries={["/brazosbend/billing/history"]}>
          <Routes>
            <Route path="/:tenant/billing/:tab" element={<PastBillingRunsPanel />} />
          </Routes>
        </MemoryRouter>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}
