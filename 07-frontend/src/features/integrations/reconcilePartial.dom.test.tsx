// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-INT-9849 (PO GIS review 2026-10-07, gap 3) — the parcel check's
//          Preview now reads the first few pages of the City's register so it
//          answers inside the web worker's 60 seconds; the result must SAY so.
// Rules:   B14 rule 33 (a fact is six words or fewer) · rule 35 (eleven
//          catalogues, each in its own words) · hard-won law 7 (a part of the
//          register must never read as the register)
// ───────────────────────────────────────────────────────
/**
 * The run result after a Preview that stopped after a few pages.
 *
 * ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a note drawn on EVERY preview would
 * pass the first case and lie on the second; so the second case asserts the
 * note is ABSENT on a complete walk, and the third that an unknown total says
 * nothing about a total rather than printing *of null*.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ReconcileReport } from "@/api/integrationsEndpoints";

import { ReconcileResult } from "./ConnectionDetailPage";

afterEach(cleanup);

function report(extra: Partial<ReconcileReport> & { counts?: Record<string, unknown> }): ReconcileReport {
  return {
    run_id: "r",
    trace_id: "t",
    mode: "preview",
    started_by: "person",
    started_by_name: "Dana Whitfield",
    stopped: false,
    headline: "",
    applied: {},
    ...extra,
    counts: {
      city_rows: 3000,
      city_pages: 3,
      city_pages_total: 70,
      premises_examined: 412,
      units_examined: 0,
      differences_found: 9,
      queued: 4,
      fields_set_to_never_touch: 7,
      ...(extra.counts ?? {}),
    },
  } as ReconcileReport;
}

function draw(r: ReconcileReport) {
  return render(
    <MemoryRouter>
      <ReconcileResult report={r} queuePath={null} />
    </MemoryRouter>,
  );
}

describe("the parcel check's Preview, stopped after a few pages (DEF-INT-9849)", () => {
  it("says it stopped after 3 of 70 pages", () => {
    draw(report({ complete: false }));
    const note = document.querySelector("[data-reconcile-partial]");
    expect(note).not.toBeNull();
    expect(note).toHaveTextContent("Stopped after 3 of 70 pages.");
  });

  it("says nothing of the kind when the whole register was read", () => {
    draw(report({ complete: true, counts: { city_pages: 3, city_pages_total: 3 } }));
    expect(document.querySelector("[data-reconcile-partial]")).toBeNull();
    expect(screen.queryByText(/Stopped after/)).toBeNull();
  });

  it("never invents a total the City would not give", () => {
    draw(report({ complete: false, counts: { city_pages_total: null } }));
    const note = document.querySelector("[data-reconcile-partial]");
    expect(note).toHaveTextContent("Stopped after 3 pages.");
    expect(note?.textContent).not.toMatch(/of|null/);
  });
});
