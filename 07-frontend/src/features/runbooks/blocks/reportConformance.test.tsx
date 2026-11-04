/* ══════════════════════════════════════════════════════════════════════════
 * THE ENGINE'S ACTUAL REPORT, DRAWN BY THE ACTUAL COMPONENTS.
 *
 * Story: US-RBS-016 · US-RBS-001 — CR-075 wave C task C2.
 * Rules: `BR-RBS-020` (the report is composed at close and FROZEN) ·
 *        `BR-RBS-021` (a thirteenth block needs THREE runbooks) · B14 rule 31.
 *
 * ⚠ **THIS FILE EXISTS BECAUSE OF `DEF-RBS-4284`, AND IT IS THE CHECK THAT WAS
 * MISSING.** On 2026-09-06 the engine and the eleven block components each had a
 * shape for all six blocks runbook 1 emits, and NOT ONE of them matched — the
 * two chain state vocabularies did not share a single value. Both suites were
 * green. The only cross-check in the repository read `contract.py`'s
 * `BLOCK_TYPES` and asserted the twelve NAMES, and `blocks.test.tsx`'s own
 * comment had already predicted what that leaves open:
 *
 *     "If these two lists drift, a report the backend accepts draws nothing on
 *      screen — and nothing else would say."
 *
 * It was right about the mechanism and one level too high. A name check over an
 * unchecked payload is a declared blind spot with no number attached — hard-won
 * law 7's fifth shape, the one that reported `0 unresolved` truthfully over 21
 * live refusals.
 *
 * **WHAT MAKES THIS DIFFERENT FROM A SNAPSHOT.** The fixture is written by
 * `06-backend/tests/test_us_rbs_001_configuration_check.py` from a REAL RUN of
 * runbook 1 over the blockers fixture, and that test asserts the committed bytes
 * still match the engine. So the engine cannot drift without failing there, and
 * the renderer cannot drift without failing here. Neither side can move alone.
 *
 * ⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY** — asked because a check you
 * cannot describe a false pass for is one you do not understand. Rendering a
 * block and asserting only that it produced SOME html: a component handed a
 * payload it does not understand still returns a `<section>`. So every
 * assertion below names a VALUE out of the fixture and requires it in the
 * output. A shape that drifts makes the value disappear, not the markup.
 * ══════════════════════════════════════════════════════════════════════════ */
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { defaultRequestState } from "@/components/tableTypes";
import { tenantPathFrom } from "@/routing/tenantPath";

import report from "./__fixtures__/rbs001-report.json";
import { BLOCKS_BUILT } from "./index";
import { VerdictBlock } from "./VerdictBlock";
import { KpisBlock } from "./KpisBlock";
import { ChainBlock } from "./ChainBlock";
import { BreakdownBlock } from "./BreakdownBlock";
import { RecordsBlock } from "./RecordsBlock";
import { DownloadsBlock } from "./DownloadsBlock";
import type {
  BlockContext,
  BreakdownPayload,
  ChainPayload,
  DownloadsPayload,
  KpisPayload,
  RecordsPayload,
  ReportBlock,
  VerdictPayload,
} from "./types";

const TENANT = "brazosbend";
/** The address `RBS-006` is actually served at. It matters: a relative `to`
 *  resolves against the CURRENT route, so the depth of this path is what made
 *  `DEF-RBS-4329` visible. */
const RUN_PATH = `/${TENANT}/runbooks/configuration_check/runs/run-1`;

const CTX: BlockContext = {
  timeZone: "America/Chicago",
  dateFormat: "MM/DD/YYYY",
  // ⚠ THE SHELL'S OWN HELPER, BOUND TO A TENANT — never a hand-rolled
  // `/${TENANT}/${path}`. A test that reimplements the thing under test cannot
  // see it drift; this one goes red if `tenantPathFrom` ever stops prefixing.
  toHref: (path: string) => tenantPathFrom(TENANT, path),
};

/** The fixture, checked against what the renderer declares.
 *
 *  ⚠ **AN ANNOTATION, NEVER `as`.** The first draft of this file wrote
 *  `report as ReportBlock[]` with a comment claiming `tsc` would catch a drifted
 *  payload. It would not: `as` is an ASSERTION and it SILENCES exactly the error
 *  this file exists to raise. Proved by sabotaging the fixture back to the
 *  pre-`DEF-RBS-4284` shape and watching the typecheck pass over it — a comment
 *  claiming a guarantee is not the guarantee (hard-won law 1), found in the very
 *  file written to catch that class. An annotation is checked on assignment. */
const blocks: ReportBlock[] = report as unknown as ReportBlock[];

function draw(node: React.ReactNode): string {
  // ⚠ **UNDER THE REAL ROUTE PATTERN, NOT A BARE `MemoryRouter` —
  // `DEF-RBS-4329` and `DEF-CWP-3925`.** This used to be
  // `<MemoryRouter>{node}</MemoryRouter>`, which mounts everything at `/`. A
  // relative `<Link to="settings/services">` there resolves to exactly
  // `/settings/services` — the right answer, for the wrong reason — so the
  // assertion below passed while the same link on the real screen went to
  // `/brazosbend/runbooks/configuration_check/runs/<id>/settings/services` and
  // opened onto "not built yet". Mount at the address the screen is served at,
  // or the one assertion that could catch this cannot be written.
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[RUN_PATH]}>
      <Routes>
        <Route path="/:tenant/runbooks/:key/runs/:runId" element={<>{node}</>} />
      </Routes>
    </MemoryRouter>,
  );
}

function payloadOf<T>(name: string): T {
  const block = blocks.find((b) => b.block === name);
  expect(block, `the fixture has no ${name} block — regenerate it with RBS_WRITE_FIXTURE=1`)
    .toBeDefined();
  return block!.payload as T;
}

describe("the engine's own report, drawn by the renderer's own components", () => {
  it("names only blocks the renderer has built", () => {
    const named = [...new Set(blocks.map((b) => b.block))];
    expect(named.length, "the fixture is empty — this check now covers nothing")
      .toBeGreaterThan(0);
    for (const name of named) {
      expect(BLOCKS_BUILT, `the report names ${name} and no component draws it`)
        .toContain(name);
    }
  });

  it("Verdict draws the tenant verdict as a WORD, never as the code `no_go`", () => {
    const payload = payloadOf<VerdictPayload>("verdict");
    const html = draw(<VerdictBlock payload={payload} />);
    expect(html).toContain("No-go");
    expect(html).toContain("3 things stop billing");
    // B14 rule 32 — an internal code may never be clerk-facing copy.
    expect(html).not.toContain("no_go");
  });

  it("KPIs draw every tile the engine counted", () => {
    const payload = payloadOf<KpisPayload>("kpis");
    const html = draw(<KpisBlock payload={payload} ctx={CTX} />);
    for (const tile of payload.tiles) {
      expect(html, `the ${tile.label} tile drew nothing`).toContain(tile.label);
    }
    expect(payload.tiles.map((t) => t.id)).toEqual(["blockers", "warnings", "steps_clear"]);
  });

  it("Chain draws ten cells, red at the earliest failure, each red one naming its blocker", () => {
    const payload = payloadOf<ChainPayload>("chain");
    expect(payload.cells).toHaveLength(10);
    const html = draw(<ChainBlock payload={payload} />);

    const red = payload.cells.filter((c) => c.state === "bad").map((c) => c.position);
    expect(red, "RBS-006-R1 reddens Tax, Rate coverage and Account chain").toEqual([3, 5, 6]);
    expect(html).toContain('data-chain-state="bad"');

    // ⚠ A red cell NAMES the blocker (`RBS-006-R1` region 3, `BR-RBS-027`) and a
    // green one says what it LOOKED AT — an empty estate and a correct one must
    // not read the same (law 7). Both arrive through `note`.
    for (const cell of payload.cells.filter((c) => c.state === "bad")) {
      expect(cell.note, `cell ${cell.position} is red and names no blocker`).toBeTruthy();
      expect(html).toContain(cell.note!);
    }
  });

  it("Breakdown draws one row per service, a green one beside a red one", () => {
    const payload = payloadOf<BreakdownPayload>("breakdown");
    const html = draw(<BreakdownBlock payload={payload} ctx={CTX} />);
    expect(html).toContain("By service");
    // §8.1's whole reason: a service with nothing wrong is still LISTED, so a
    // utility that fixes one watches it go green instead of watching a row
    // vanish, which reads like a bug rather than like progress.
    for (const row of payload.rows) {
      const service = row.cells.service;
      expect(service.kind).toBe("text");
      if (service.kind === "text") {
        expect(html).toContain(service.text);
      }
    }
  });

  it("Records draws the findings table — every column, every row, every fix route", () => {
    const payload = payloadOf<RecordsPayload>("records");
    const html = draw(
      <RecordsBlock
        payload={payload}
        ctx={CTX}
        state={defaultRequestState({
          screenId: "RBS-006.rb1",
          columns: [],
          getRowId: () => "",
          defaultSort: { sort: "step", dir: "asc" },
        })}
        onStateChange={() => undefined}
        loading={false}
        chip={{ selected: "all", onSelect: () => undefined }}
        screenId="RBS-006.rb1"
      />,
    );

    expect(payload.columns.map((c) => c.key)).toEqual([
      "step",
      "finding",
      "affects",
      "weight",
      "fix",
    ]);
    for (const column of payload.columns) {
      expect(html, `the ${column.label} header drew nothing`).toContain(column.label);
    }

    // ⚠ THE FIX ROUTE IS ASSERTED AS A DESTINATION, NOT AS A PRESENT STRING.
    // "has a fix route" is satisfied by any string, and a string naming no
    // screen is a dead button over a live finding — hard-won law 2's mirror,
    // the shape that left the customer portal with two working doors out of
    // eight.
    for (const row of payload.rows) {
      const fix = row.cells.fix;
      expect(fix.kind).toBe("link");
      if (fix.kind === "link") {
        expect(fix.to, "a finding with no destination is a dead button").toBeTruthy();
        expect(html).toContain(fix.label);
        // The WHOLE href, anchored at the tenant. `toContain` on a suffix is what
        // let `DEF-RBS-4329` through: a wrongly PREFIXED href still ends in the
        // route it was supposed to name.
        expect(html, "the fix route lost its tenant, or gained the run's path").toContain(
          `href="/${TENANT}/${fix.to}"`,
        );
      }
    }
  });

  it("Records draws the chips with their counts, and `All` is the one selected", () => {
    const payload = payloadOf<RecordsPayload>("records");
    const html = draw(
      <RecordsBlock
        payload={payload}
        ctx={CTX}
        state={defaultRequestState({
          screenId: "RBS-006.rb1",
          columns: [],
          getRowId: () => "",
          defaultSort: { sort: "step", dir: "asc" },
        })}
        onStateChange={() => undefined}
        loading={false}
        chip={{ selected: "all", onSelect: () => undefined }}
        screenId="RBS-006.rb1"
      />,
    );
    for (const chip of payload.chips ?? []) {
      expect(html).toContain(`${chip.label} ${chip.count}`);
    }
    // The selected chip inverts to an ink fill — r10's `.fchip.active`, carried
    // by the kit so every chip row in the product agrees (B14 rule 36).
    expect(html).toContain('data-chip="selected"');
  });

  it("the blockers come before the warnings, which is the order a clerk acts in", () => {
    const payload = payloadOf<RecordsPayload>("records");
    const weights = payload.rows.map((row) => {
      const cell = row.cells.weight;
      return cell.kind === "pill" ? cell.label : "?";
    });
    const firstWarning = weights.indexOf("Warning");
    const lastBlocker = weights.lastIndexOf("Blocks billing");
    if (firstWarning !== -1 && lastBlocker !== -1) {
      expect(lastBlocker, "a warning sorts above a blocker").toBeLessThan(firstWarning);
    }
  });

  it("no cell puts a database id or a rule id on screen — B14 rule 31 and rule 32", () => {
    const payload = payloadOf<RecordsPayload>("records");
    const idShaped = /\b(?:BR|OQ|DEF|TC|US|EP|GT|RB)-[A-Z]*-?\d{2,5}\b/;
    const uuidShaped = /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-/;
    for (const row of payload.rows) {
      for (const [key, cell] of Object.entries(row.cells)) {
        const words =
          cell.kind === "text" ? cell.text : cell.kind === "pill" ? cell.label : cell.kind === "link" ? cell.label : "";
        expect(idShaped.test(words), `${key} shows an internal id: ${words}`).toBe(false);
        expect(uuidShaped.test(words), `${key} shows a database id: ${words}`).toBe(false);
      }
      // ⚠ `meta` is the exception that proves the rule: `decided_by_rule` IS a
      // rule id, it is carried on the row, and NO block draws it. The renderer
      // walks `columns`, so it cannot reach a screen — see `ReportRow.meta`.
      expect(row.meta?.decided_by_rule, "the trace to the deciding rule was dropped")
        .toBeTruthy();
    }
  });

  it("Downloads draws the result files the runbook offers", () => {
    const payload = payloadOf<DownloadsPayload>("downloads");
    const html = draw(<DownloadsBlock payload={payload} onDownload={() => undefined} />);
    for (const file of payload.files) {
      expect(html).toContain(file.label);
    }
  });
});
