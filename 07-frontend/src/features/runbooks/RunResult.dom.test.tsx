// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1. `vitest.config.ts`
// keeps the default environment at `node` deliberately (`DEF-523`) — 200+
// suites are `renderToStaticMarkup` first-paint tests that neither need nor
// want a DOM — so an interactive suite opts in per file. Without it every case
// here dies on `ReferenceError: document is not defined`, which is exactly how
// this file first ran.
/* ══════════════════════════════════════════════════════════════════════════
 * `RBS-006` — the result renderer, drawn over the REAL frozen report.
 *
 * Story: US-RBS-016 · US-RBS-001 — CR-075 wave C task C2.
 * Rules: `BR-RBS-020` · `BR-RBS-021` · `NFR-3` · B14 rules 2, 4, 31, 32.
 *
 * ⚠ **THE FIXTURE IS A REAL RUN, NOT A HAND-WRITTEN PROP BAG.**
 * `blocks/__fixtures__/rbs001-report.json` is written by
 * `06-backend/tests/test_us_rbs_001_configuration_check.py` from an actual
 * execution of runbook 1 over the blockers fixture, and that test asserts the
 * committed bytes still match the engine. A hand-written payload here would
 * test this file against my own idea of the engine — which is precisely how
 * `DEF-RBS-4284` happened: the engine and the eleven block components each had
 * a shape, not one matched, and both suites were green because each side tested
 * against itself.
 *
 * ⚠ **WHAT WOULD MAKE THIS FILE PASS WRONGLY.** Asserting that the render
 * produced SOME markup: a renderer handed a report it cannot draw still returns
 * a `<div>`. So the central test below walks EVERY block in the fixture and
 * requires a value out of that block to be in the DOM — a dropped block fails
 * by name, and adding a block to the report without teaching the renderer fails
 * here rather than on a clerk's screen.
 * ══════════════════════════════════════════════════════════════════════════ */
import { render, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import report from "./blocks/__fixtures__/rbs001-report.json";
import type { BlockContext, ReportBlock } from "./blocks/types";
import { RunResult } from "./RunResult";
import type { RunResultView } from "./resultTypes";
import { tenantPathFrom } from "@/routing/tenantPath";

const CTX: BlockContext = {
  timeZone: "America/Chicago",
  dateFormat: "MM/DD/YYYY",
  // The shell's own helper bound to this file's tenant, never a hand-rolled
  // join (`DEF-RBS-4329`). `draw` already mounts under the real route pattern.
  toHref: (path: string) => tenantPathFrom("silver-creek", path),
};

function viewOf(overrides: Partial<RunResultView> = {}): RunResultView {
  return {
    header: {
      runbookName: "Configuration check",
      runbookTo: "/silver-creek/runbooks/configuration-check",
      title: "Run · Today 08:12",
      took: "12s",
      rerun: { enabled: true },
    },
    report: report as unknown as ReportBlock[],
    records: { page: 1, per: 50, chip: "all" },
    ...overrides,
  };
}

function draw(view: RunResultView, handlers: Partial<Record<string, () => void>> = {}) {
  const noop = () => undefined;
  return render(
    // ⚠ MOUNTED UNDER THE REAL PATH PATTERN. `DEF-CWP-3925`: a component mounted
    // bare inside a `MemoryRouter` with no `/:tenant/…` route gets `undefined`
    // from `useParams()` and builds every address as `//portal/…` — a
    // protocol-relative URL to another host that reads as a perfectly good
    // string to `toContain`. The one assertion that could catch it cannot even
    // be written against a bare mount.
    <MemoryRouter initialEntries={["/silver-creek/runbooks/configuration-check/runs/r1"]}>
      <Routes>
        <Route
          path="/:tenant/runbooks/:key/runs/:runId"
          element={
            <RunResult
              view={view}
              ctx={CTX}
              loading={false}
              onRecordsQuery={vi.fn()}
              onRerun={handlers.onRerun ?? noop}
              onDownload={noop}
              onDecide={noop}
              onAct={noop}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RBS-006 draws the frozen report", () => {
  it("draws EVERY block the report carries — nothing is silently dropped", () => {
    const { container } = draw(viewOf());
    const html = container.innerHTML;

    for (const block of report as unknown as ReportBlock[]) {
      switch (block.block) {
        case "verdict":
          // Lifted into the page head's sub-line, per the composition rule.
          expect(html, "the verdict reached neither the head nor the body")
            .toContain(block.payload.count);
          break;
        case "kpis":
          for (const tile of block.payload.tiles) {
            expect(html, `the ${tile.label} tile drew nothing`).toContain(tile.label);
          }
          break;
        case "chain":
          for (const cell of block.payload.cells) {
            expect(html, `chain cell ${cell.position} drew nothing`).toContain(cell.label);
          }
          break;
        case "breakdown":
          // ⚠ ABSENT FROM `RBS-006-R1`'s FRAME AND DRAWN ANYWAY. A sheet is a
          // region list, not the whole screen, and §8.1's whole reason is that
          // a service with nothing wrong is still LISTED — a screen that hid it
          // would show progress as a row disappearing, which reads like a bug.
          expect(html, "the per-service breakdown was dropped").toContain(
            block.payload.heading,
          );
          break;
        case "records":
          for (const column of block.payload.columns) {
            expect(html, `the ${column.label} column drew nothing`).toContain(column.label);
          }
          break;
        case "downloads":
          for (const file of block.payload.files) {
            expect(html, `the ${file.label} download drew nothing`).toContain(file.label);
          }
          break;
        default:
          // Every other block name is legal and simply not in runbook 1's
          // report. It is drawn by the same switch in `RunResult`, which `tsc`
          // keeps exhaustive.
          break;
      }
    }
  });

  it("the verdict's WORD reaches the clerk, not only its count — DEF-RBS-4313", () => {
    // ⚠ **THIS CASE EXISTS BECAUSE THE FIRST VERSION OF THIS SCREEN DROPPED IT.**
    // The composition took `verdict.count` alone. On runbook 1 that LOOKED
    // right, because its count — "3 things stop billing" — happens to carry the
    // meaning. It does not generalise: the month-end journal file's count reads
    // "1 to fix · 3 months open." while its WORD is "Ready to import" or "No
    // file", which are the two states that runbook exists to tell apart. So the
    // fixture here is deliberately NOT runbook 1 — a case written only against
    // the runbook that happens to survive the bug cannot see the bug.
    const withWord: ReportBlock[] = [
      {
        block: "verdict",
        payload: {
          word: "Ready to import",
          tone: "success",
          count: "1 to fix · 3 months open.",
          detail: "Debits $68,317.12 · Credits $68,317.12",
        },
      },
      ...(report as unknown as ReportBlock[]).filter((b) => b.block !== "verdict"),
    ];
    const { container } = draw(viewOf({ report: withWord }));
    const html = container.innerHTML;
    expect(html, "the verdict WORD never reached the screen").toContain("Ready to import");
    expect(html, "the count line was dropped").toContain("1 to fix · 3 months open.");
    expect(html, "the detail was dropped").toContain("Debits $68,317.12");
    // The tone is carried by a real pill, not by the word sitting in plain text.
    expect(container.querySelector(".pill")?.textContent).toBe("Ready to import");
  });

  it("the verdict becomes the page head's sub-line and is NOT printed twice", () => {
    const { container } = draw(viewOf());
    const sentence = "3 things stop billing";
    const hits = container.innerHTML.split(sentence).length - 1;
    // B14 rule 32 — one sentence per section. Drawing the leading verdict as a
    // band AND as the sub-line would print the same words twice on one screen.
    expect(hits, `"${sentence}" appears ${hits} times; the budget is one`).toBe(1);
  });

  it("the kicker names where the page exits to, as an ADDRESS", () => {
    // ⚠ SCOPED TO THIS RENDER, NEVER `screen`. `screen` queries the whole
    // document, and without auto-cleanup each `render` in this file leaves its
    // tree behind — so by the third case a global query finds three matches and
    // fails with "found multiple elements", which reads like a component bug
    // and is a test-harness one. `within(container)` asks about the render in
    // front of it.
    const { container } = draw(viewOf());
    const back = within(container).getByRole("link", { name: /Configuration check/i });
    // ⚠ ASSERTED AS A DESTINATION, not as a present string. `//host/…` reads as
    // a perfectly good href to a `toContain` assertion (`DEF-CWP-3925`).
    expect(back.getAttribute("href")).toBe("/silver-creek/runbooks/configuration-check");
  });

  it("no database id and no rule id reaches the screen — B14 rules 31 and 32", () => {
    const { container } = draw(viewOf());
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\b(?:BR|OQ|DEF|TC|US|EP|GT|RB)-[A-Z]*-?\d{2,5}\b/);
    expect(text).not.toMatch(/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-/);
    // `decided_by_rule` IS a rule id, it IS on every row, and no block draws it.
    // That is `ReportRow.meta` doing its job rather than an accident.
    expect(JSON.stringify(report)).toContain("decided_by_rule");
  });

  it("a re-run the user may not start is DISABLED with its reason RENDERED, not only hovered", () => {
    const reason = "A run is already going";
    const { container } = draw(
      viewOf({
        header: { ...viewOf().header, rerun: { enabled: false, reason } },
      }),
    );
    const button = within(container).getByRole("button", { name: /Run again/i });
    // `toBeDisabled` is jest-dom's and this repo does not load it — asserting
    // the attribute directly says the same thing and cannot silently become a
    // no-op if a matcher package goes missing.
    expect(button.hasAttribute("disabled")).toBe(true);
    // ⚠ `DEF-SHL-4043` — a `title` alone opens on hover, after a delay, and
    // NEVER on a touch screen. Twenty screens drew a grey button that said
    // nothing for four weeks while the docstring promised otherwise, and
    // `toContain(reason)` passed on every one of them.
    expect(container.querySelector("[data-rerun-reason]")?.textContent).toBe(reason);
  });

  it("a report with no verdict block draws no sub-line rather than a manufactured one", () => {
    const withoutVerdict = (report as unknown as ReportBlock[]).filter(
      (b) => b.block !== "verdict",
    );
    const { container } = draw(viewOf({ report: withoutVerdict }));
    // A stated absence is CLOSED by default (B14 rule 32). The screen still
    // draws, which is the point: the renderer must not require any one block.
    expect(container.innerHTML).not.toContain("3 things stop billing");
    expect(container.innerHTML).toContain("Run · Today 08:12");
  });
});
