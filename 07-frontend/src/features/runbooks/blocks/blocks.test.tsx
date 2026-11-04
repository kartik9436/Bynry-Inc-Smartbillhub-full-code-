/* ══════════════════════════════════════════════════════════════════════════
 * CR-075 wave C · C1b — the twelve blocks
 * ══════════════════════════════════════════════════════════════════════════
 * Assertions are what a READER sees, from the build sheets' own words. The two
 * that matter most are structural rather than visual, and both go red on a real
 * mistake a later lane is likely to make:
 *
 *   · the twelve NAMES must equal `contract.py`'s `BLOCK_TYPES` — two
 *     declarations of one thing that CAN disagree, kept from disagreeing by a
 *     test, because no tuple can be shared across Python and TypeScript;
 *   · `records` is a STATED ABSENCE with a number attached (11 of 12), so the
 *     gap is visible and shrinks by one the day C2 lands it. A stated absence
 *     with no test is a comment claiming a guarantee (hard-won law 1).
 * ══════════════════════════════════════════════════════════════════════════ */
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { BLOCKS_BUILT } from "./index";
import { BLOCK_TYPES } from "./types";
import type { BlockContext } from "./types";
import { VerdictBlock } from "./VerdictBlock";
import { ChainBlock } from "./ChainBlock";
import { RankedBlock } from "./RankedBlock";
import { SentenceBlock } from "./SentenceBlock";
import { FactsBlock } from "./FactsBlock";
import { ReconciledBlock } from "./ReconciledBlock";
import { BreakdownBlock } from "./BreakdownBlock";
import { ActionBlock } from "./ActionBlock";
import { RowDecisionsBlock } from "./RowDecisionsBlock";
import { KpisBlock } from "./KpisBlock";
import { RecordsBlock } from "./RecordsBlock";
import { tenantPathFrom } from "@/routing/tenantPath";

const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

const TENANT = "brazosbend";
/** The address `RBS-006` is actually served at — see `draw` below. */
const RUN_PATH = `/${TENANT}/runbooks/configuration_check/runs/run-1`;

const CTX: BlockContext = {
  timeZone: "America/Chicago",
  dateFormat: "MM/DD/YYYY",
  // The shell's own helper bound to a tenant, never a hand-rolled join
  // (`DEF-RBS-4329`).
  toHref: (path: string) => tenantPathFrom(TENANT, path),
};

function draw(node: React.ReactNode): string {
  // ⚠ **AT THE ADDRESS THE SCREEN IS SERVED AT — `DEF-RBS-4329`.** This file's
  // Link cases used to render at `/`, where a relative `to` resolves to the
  // right answer for the wrong reason. The defect register names this file as
  // one of the three checks that looked one step short.
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[RUN_PATH]}>
      <Routes>
        <Route path="/:tenant/runbooks/:key/runs/:runId" element={<>{node}</>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("the twelve names are the backend's twelve names", () => {
  it("matches contract.py's BLOCK_TYPES, name for name and in order", () => {
    // `06-backend/apps/runbooks/contract.py` mints them and refuses a
    // thirteenth at run close (BR-RBS-021). If these two lists drift, a report
    // the backend accepts draws nothing on screen — and nothing else would say.
    const here = nodeUrl.fileURLToPath(new URL("./blocks.test.tsx", import.meta.url));
    const root = here.slice(0, here.indexOf("/07-frontend/"));
    const contract = nodeFs.readFileSync(`${root}/06-backend/apps/runbooks/contract.py`, "utf8");
    const tuple = contract.split("BLOCK_TYPES = (")[1]?.split(")")[0] ?? "";
    const names = [...tuple.matchAll(/BLOCK_([A-Z_]+),/g)].map((m) => m[1].toLowerCase());
    expect(names, "contract.py's BLOCK_TYPES could not be read — this check now covers nothing")
      .toHaveLength(12);
    expect([...BLOCK_TYPES]).toEqual(names);
  });

  it("all TWELVE have a component — `records` landed with C2 and the absence is closed", () => {
    expect(BLOCKS_BUILT).toHaveLength(12);
    const missing = BLOCK_TYPES.filter((n) => !BLOCKS_BUILT.includes(n as never));
    expect(missing, "a block name with no component draws NOTHING on screen").toEqual([]);
  });
});

describe("what a reader sees, from the build sheets' own words", () => {
  it("Verdict draws RBS-006-R9's three lines", () => {
    const html = draw(
      <VerdictBlock
        payload={{
          word: "Not balanced",
          tone: "danger",
          count: "6 of 9 steps clear",
          detail: "Tax off by $14.25 · $312.00 unapplied",
        }}
      />,
    );
    expect(html).toContain("Not balanced");
    expect(html).toContain("6 of 9 steps clear");
    expect(html).toContain("Tax off by $14.25");
  });

  it("Chain draws RBS-006-R1's ten cells, red at the earliest failure, each naming its blocker", () => {
    const html = draw(
      <ChainBlock
        payload={{
          label: "Ten steps, three stopped billing.",
          cells: [
            { id: "1", position: 1, label: "Services", state: "ok" },
            { id: "3", position: 3, label: "Tax", state: "bad", note: "No tax region set" },
            { id: "4", position: 4, label: "Counts", state: "notReached", note: "Never reached" },
          ],
        }}
      />,
    );
    expect(html).toContain("No tax region set");
    expect(html).toContain("Never reached");
    expect(html).toContain('data-chain-state="bad"');
  });

  it("Ranked draws RBS-006-R4's causes with money formatted by the kit, never by the block", () => {
    const html = draw(
      <RankedBlock
        ctx={CTX}
        payload={{
          heading: "What caused it · largest first",
          rows: [
            {
              id: "a",
              label: "More water used",
              detail: "7,240 gal vs 5,250 gal",
              weight: 46.4,
              value: { kind: "money", amount: "46.4000", currency: "USD" },
            },
          ],
        }}
      />,
    );
    expect(html).toContain("More water used");
    expect(html).toContain("$46.40"); // 4 stored, 2 shown — hard rule 2
    expect(html).not.toContain("46.4000");
  });

  it("a percentage inside a block shows TWO decimals, whatever the payload stored", () => {
    const html = draw(
      <FactsBlock
        ctx={CTX}
        payload={{
          heading: "Usage",
          rows: [
            { id: "a", label: "Change", value: { kind: "percent", value: "38", basis: "points", signed: true } },
            { id: "b", label: "Tax rate", value: { kind: "percent", value: "0.062500", basis: "fraction" } },
          ],
        }}
      />,
    );
    expect(html).toContain("+38.00%");
    expect(html).toContain("6.25%");
    expect(html).not.toContain("6.250000");
  });

  it("a RATE shows up to FOUR decimals in the same table a money cell shows two — the kind decides", () => {
    // 09-component-inventory.md: "A screen that formats both with one helper is
    // wrong in one of the two directions on every row."
    //
    // ⚠ **THIS CASE ASSERTED `$8.2900` UNTIL 2026-10-13 (`DEF-WRK-10119`) AND
    // THE COMPONENT WAS RIGHT.** CLAUDE.md hard rule 2, PO 2026-10-02: *"Show
    // unit prices with up to 4 decimals and keep every total at 2."* A rate
    // shows the places it CARRIES, up to four, never fewer than two — so
    // `8.290000` is `$8.29` and the zeros-kept half of OQ-620(a) is superseded.
    // `formatRate` moved in 565e6a831 (2.451.0) and this case was not moved
    // with it. The point of the case survives, on a rate that carries four:
    // `8.9375` is `$8.9375` as a RATE and `$8.94` as MONEY, in one table.
    const html = draw(
      <FactsBlock
        ctx={CTX}
        payload={{
          rows: [
            { id: "a", label: "Rate", value: { kind: "rate", rate: "8.937500", currency: "USD" } },
            { id: "b", label: "Charge", value: { kind: "money", amount: "8.9375", currency: "USD" } },
            { id: "c", label: "Flat", value: { kind: "rate", rate: "8.290000", currency: "USD" } },
          ],
        }}
      />,
    );
    expect(html).toContain("$8.9375"); // the rate keeps the four places it carries
    expect(html).toContain("$8.94"); // the money rounds to two
    expect(html).toContain("$8.29"); // a rate drops the zeros after the second place
    expect(html).not.toContain("$8.2900");
  });

  it("Sentence draws the card and truncates nothing — the rule 33 divergence stays visible", () => {
    const long = "A ".repeat(88).trim();
    const html = draw(<SentenceBlock payload={{ tone: "success", label: "Read this aloud", text: long }} />);
    expect(html).toContain("Read this aloud");
    expect(html).toContain(long);
  });

  it("Reconciled and Breakdown are ONE table shape with different columns", () => {
    const columns = [
      { key: "line", label: "Line" },
      { key: "recorded", label: "Recorded", numeric: true },
      { key: "books", label: "In the books", numeric: true },
    ];
    const rows = [
      {
        id: "r1",
        cells: {
          line: { kind: "text" as const, text: "Receivables" },
          recorded: { kind: "money" as const, amount: "1204318.2200", currency: "USD" },
          books: { kind: "money" as const, amount: "1204318.2200", currency: "USD" },
        },
      },
    ];
    const recon = draw(
      <ReconciledBlock ctx={CTX} payload={{ heading: "Tie-out", columns, rows, tiesLabel: "Ties" }} />,
    );
    // B14 rule 34: ONE pair of words for held here and in the books.
    expect(recon).toContain("Recorded");
    expect(recon).toContain("In the books");
    expect(recon).toContain("$1,204,318.22");
    const breakdown = draw(<BreakdownBlock ctx={CTX} payload={{ heading: "By channel", columns, rows }} />);
    // One table type, B14 rule 20 — the same class on both.
    expect(breakdown).toContain('class="data-table"');
    expect(recon).toContain('class="data-table"');
  });

  it("a row id is never the visible value of a field — B14 rule 31", () => {
    const html = draw(
      <BreakdownBlock
        ctx={CTX}
        payload={{
          heading: "By class",
          columns: [{ key: "name", label: "Class" }],
          rows: [{ id: "8f14e45f-ceea-467a", cells: { name: { kind: "text", text: "Residential" } } }],
        }}
      />,
    );
    expect(html).toContain("Residential");
    expect(html).not.toContain("8f14e45f");
  });

  it("A DISABLED ACTION SAYS WHY, and the reason is readable without a mouse", () => {
    const html = draw(
      <ActionBlock
        onAct={() => {}}
        payload={{ label: "Close period ✓", tier: "danger", enabled: false, reason: "3 items open." }}
      />,
    );
    expect(html).toContain("3 items open.");
    expect(html).toContain("aria-describedby");
    // ⚠ THE ATTRIBUTE, NOT THE SUBSTRING. `toContain("disabled")` passes on
    // EVERY button in this product, enabled or not: `buttonKit`'s class list
    // carries `disabled:opacity-45` and `disabled:cursor-not-allowed`. The
    // first draft of this pair asserted the substring and the ENABLED case went
    // red for the right reason on the wrong evidence — hard-won law 7's second
    // habit, "ask what would make this check pass wrongly".
    expect(html).toContain('disabled=""');
  });

  it("an ENABLED action carries no orphan reason", () => {
    const html = draw(
      <ActionBlock onAct={() => {}} payload={{ label: "Close period ✓", tier: "danger", enabled: true }} />,
    );
    expect(html).not.toContain("data-action-reason");
    expect(html).not.toContain('disabled=""');
  });

  it("Row decisions draw NAMED VALUES as text buttons — the ruled divergence from rule 15", () => {
    const html = draw(
      <RowDecisionsBlock
        ctx={CTX}
        onDecide={() => {}}
        payload={{
          heading: "Parcels that disagree",
          columns: [{ key: "p", label: "Premises" }],
          rows: [{ id: "r1", cells: { p: { kind: "text", text: "14 Cedar St" } } }],
          choices: [
            { id: "theirs", label: "Accept theirs →" },
            { id: "ours", label: "Keep ours" },
          ],
        }}
      />,
    );
    // An icon cannot carry WHICH of two values is kept — Part 4 §3.
    expect(html).toContain("Accept theirs →");
    expect(html).toContain("Keep ours");
    expect(html).toContain('data-decision="theirs"');
  });

  it("a money KPI keeps its basis label — no unlabeled money number reaches a tile", () => {
    const html = draw(
      <KpisBlock
        ctx={CTX}
        payload={{
          tiles: [
            { id: "a", label: "Revenue at risk", value: { kind: "money", amount: "9840.0000", currency: "USD" } },
            { id: "b", label: "Blockers", value: { kind: "text", text: "3" } },
          ],
        }}
      />,
    );
    expect(html).toContain("$9,840.00"); // hard rule 2, and the sheet's `$9,840` is the divergence
    expect(html).toContain("Blockers");
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * CR-075 wave G · the `records` block's GRID display mode — `DEF-RBS-4354`
 * ══════════════════════════════════════════════════════════════════════════
 * `BR-RBS-021`: the coverage grid is a DISPLAY MODE of the twelfth-of-twelve
 * `records` block and not a thirteenth block. Runbook 24 is the first thing in
 * the product to emit one, and the mode had never been rendered with a real
 * route until it did.
 *
 * ⚠ **THE ASSERTION IS THE WHOLE HREF, NOT ITS ENDING.** `DEF-RBS-4329`'s own
 * register row names an href assertion that ends with the route as one of the
 * three checks that looked one step short: a wrongly PREFIXED href still
 * satisfies it. Both cases below compare the complete string.
 * ══════════════════════════════════════════════════════════════════════════ */
describe("the records block in grid mode", () => {
  const gridPayload = {
    display: "grid" as const,
    columns: [
      { key: "account", label: "Account" },
      { key: "reason", label: "Why" },
      { key: "open", label: "Test bill" },
    ],
    rows: [
      {
        id: "acc-1",
        cells: {
          account: { kind: "text" as const, text: "A-24000" },
          reason: { kind: "text" as const, text: "" },
          open: {
            kind: "link" as const,
            label: "Open the test bill",
            to: "runbooks/test_bill/runs/child-1",
          },
        },
      },
      {
        id: "acc-2",
        cells: {
          account: { kind: "text" as const, text: "A-24001" },
          reason: { kind: "text" as const, text: "Sewer: no June read." },
          open: {
            kind: "link" as const,
            label: "Open the test bill",
            to: "runbooks/test_bill/runs/child-2",
          },
        },
      },
    ],
    total: 2,
    grid: {
      labelKey: "account",
      stateByRowId: { "acc-1": "clean" as const, "acc-2": "refused" as const },
      linkKey: "open",
      reasonKey: "reason",
    },
    empty: { title: "Nothing was priced.", helper: "Add accounts with a plan." },
  };

  const state = {
    q: "",
    sort: "account",
    dir: "asc" as const,
    page: 1,
    per: 50 as const,
    filters: {},
  };

  function drawGrid() {
    return draw(
      <RecordsBlock
        ctx={CTX}
        payload={gridPayload}
        state={state}
        onStateChange={() => undefined}
        loading={false}
        chip={null}
        screenId="RBS-006.coverage_grid"
      />,
    );
  }

  it("draws one cell per record, coloured by its outcome, never by a severity", () => {
    const html = drawGrid();
    expect(html).toContain('data-records-display="grid"');
    expect((html.match(/data-record-cell=""/g) ?? []).length).toBe(2);
    expect(html).toContain('data-record-state="clean"');
    expect(html).toContain('data-record-state="refused"');
    // B14 rule 31 — the ACCOUNT NUMBER is drawn and the row id never is.
    expect(html).toContain("A-24000");
    expect(html).not.toContain("acc-1<");
  });

  it("opens each cell at the TENANT's address — DEF-RBS-4354", () => {
    const html = drawGrid();
    // ⚠ The whole href. Before the fix this read
    // `/brazosbend/runbooks/configuration_check/runs/run-1/runbooks/test_bill/runs/child-1`
    // — a perfectly good-looking string that opens onto nothing.
    expect(html).toContain('href="/brazosbend/runbooks/test_bill/runs/child-1"');
    expect(html).toContain('href="/brazosbend/runbooks/test_bill/runs/child-2"');
    expect(html).not.toContain(`${RUN_PATH}/runbooks/test_bill`);
  });

  it("carries the engine's own refusal sentence onto the red cell", () => {
    // `RecordGrid` puts the reason in the `title` AND under the label, so a
    // mouse-only reader is not the only one who can reach it.
    const html = drawGrid();
    expect(html).toContain("Sewer: no June read.");
    expect(html).toContain('title="Sewer: no June read."');
  });
});
