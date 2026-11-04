// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-038 W6 (2026-08-26) — BR-MET-125's report half
// Screens: S14 / PRM-02 Overview
// Rules:   BR-MET-125 (the master-vs-subs gap is STORED per premises per
//          period AND REPORTED — PO verbatim *"(a) store + report — keeps the
//          door open"*) · CLAUDE.md hard rule 3 (an explicit unit, always) ·
//          hard rule 2 (percentages DISPLAY 2) · B14 rule 21 (Tailwind
//          utilities; this section declares no stylesheet class)
// ───────────────────────────────────────────────────────
// ⚠ **THE POINT OF THESE CASES IS THE THREE EMPTY STATES, NOT THE HAPPY ROW.**
// A single "no data" line would be a lie about two of them: a premises with no
// master has nothing to reconcile ever; a premises with masters and no stored
// period has simply not been read; and a stored period that could not be
// computed is a gap NOBODY KNOWS, which must never render as a gap of zero.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { SubmeterReconciliationReport, SubmeterReconciliationRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { SubmeterReconciliationSection } from "./PremisesDetailPage";

const TEST_TENANT = "brazosbend";
const PREMISES_ID = "p-221";

/**
 * The BR-MET-125 worked figure, exactly as the PO signed it: master
 * **12,400 kWh** − Σ subs **11,940** = **460 kWh (3.71%)** against **3%**.
 * The percentage strings are the SERVER's — the screen never rounds.
 */
function overToleranceRow(over: Partial<SubmeterReconciliationRow> = {}) {
  return {
    id: "r-1",
    period_month: "2026-08-01",
    channel: "total",
    master_asset_id: "a-1",
    master_asset_no: "M-9000",
    service_code: "electric",
    unit: "kWh",
    master_consumption: "12400.000000",
    submeter_sum: "11940.000000",
    gap_quantity: "460.000000",
    gap_pct: "3.709677419354838709677419355",
    tolerance_pct: "3.000000",
    gap_pct_display: "3.71%",
    tolerance_pct_display: "3.00%",
    within_tolerance: false,
    status: "computed",
    reason: null,
    submeter_count: 2,
    submeters_resolved: 2,
    unresolved_submeters: [],
    computed_at: "2026-08-26T18:00:00Z",
    ...over,
  } as SubmeterReconciliationRow;
}

function report(over: Partial<SubmeterReconciliationReport> = {}): SubmeterReconciliationReport {
  return {
    premises_id: PREMISES_ID,
    periods: ["2026-08-01"],
    period_month: null,
    rows: [overToleranceRow()],
    has_masters: true,
    ...over,
  };
}

function servingClient(payload: SubmeterReconciliationReport, seen: string[] = []) {
  return createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL) => {
      seen.push(String(input));
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });
}

function draw(payload: SubmeterReconciliationReport, seen: string[] = []) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter>
          <SubmeterReconciliationSection
            premisesId={PREMISES_ID}
            client={servingClient(payload, seen)}
            t={(key: string, params?: Record<string, unknown>) =>
              // The section is rendered through the REAL i18n bundle by
              // `PremisesOverviewTab`; here the translator is the identity on
              // the key so a case asserts WHICH sentence was chosen rather than
              // one locale's wording (which a copy edit would break).
              (params?.defaultValue as string) ?? key
            }
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("BR-MET-125 — the premises sub-meter reconciliation section", () => {
  it("draws the stored gap with its unit and the server's 2dp percentage", async () => {
    const seen: string[] = [];
    draw(report(), seen);

    await waitFor(() =>
      expect(screen.getByText("metering.premises.submeterRecon.heading")).toBeInTheDocument(),
    );
    // It asks the real endpoint — a section wired to nothing is dead UI
    // (hard-won law 2).
    expect(
      seen.some((url) => url.includes(`/premises/${PREMISES_ID}/submeter-reconciliation`)),
    ).toBe(true);

    expect(screen.getByText("M-9000")).toBeInTheDocument();
    // CLAUDE.md hard rule 3 — every quantity renders WITH its unit. UnitCell
    // strips the storage zeros (DEF-646) and keeps the unit beside the number.
    const cells = screen.getAllByText("kWh");
    expect(cells.length).toBeGreaterThanOrEqual(3); // master · Σ subs · gap
    expect(screen.getByText("12,400")).toBeInTheDocument();
    expect(screen.getByText("11,940")).toBeInTheDocument();
    expect(screen.getByText("460")).toBeInTheDocument();
    // Hard rule 2 — the percentage displays at 2dp, and it is the SERVER's
    // string: the screen never re-rounds a figure it did not compute.
    expect(screen.getByText("(3.71%)")).toBeInTheDocument();
    expect(screen.getByText("3.00%")).toBeInTheDocument();
    expect(
      screen.getByText("metering.premises.submeterRecon.status.overTolerance"),
    ).toBeInTheDocument();
  });

  it("a gap inside the tolerance reads as reconciled, not as a warning", async () => {
    draw(
      report({
        rows: [
          overToleranceRow({
            within_tolerance: true,
            gap_pct_display: "1.20%",
            tolerance_pct_display: "3.00%",
          }),
        ],
      }),
    );
    await waitFor(() =>
      expect(
        screen.getByText("metering.premises.submeterRecon.status.withinTolerance"),
      ).toBeInTheDocument(),
    );
  });

  it("an uncomputable period names the unread sub-meters and draws NO zero gap", async () => {
    // ⚠ THE CASE THIS WHOLE COMPONENT EXISTS FOR. A short Σ must never render
    // as a bigger unaccounted loss, and an unknown gap must never render as 0.
    draw(
      report({
        rows: [
          overToleranceRow({
            status: "not_evaluated",
            reason: "submeter_sum_incomplete",
            master_consumption: null,
            submeter_sum: null,
            gap_quantity: null,
            gap_pct: null,
            gap_pct_display: null,
            tolerance_pct: null,
            tolerance_pct_display: null,
            within_tolerance: null,
            submeters_resolved: 1,
            unresolved_submeters: [{ asset_no: "S-9002", reason: "no_read_in_period" }],
          }),
        ],
      }),
    );
    await waitFor(() =>
      expect(
        screen.getByText("metering.premises.submeterRecon.status.notEvaluated"),
      ).toBeInTheDocument(),
    );
    // The sub that was not read is NAMED, so a person can go and walk it.
    expect(screen.getByText(/S-9002/)).toBeInTheDocument();
    // And no fabricated zero anywhere in the row.
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("a premises with no master says so — it does not draw an empty table", async () => {
    draw(report({ has_masters: false, rows: [], periods: [] }));
    await waitFor(() =>
      expect(screen.getByText("metering.premises.submeterRecon.noMasters")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("masters but no stored period is a DIFFERENT sentence from no masters", async () => {
    draw(report({ has_masters: true, rows: [], periods: [] }));
    await waitFor(() =>
      expect(screen.getByText("metering.premises.submeterRecon.noPeriods")).toBeInTheDocument(),
    );
    expect(screen.queryByText("metering.premises.submeterRecon.noMasters")).not.toBeInTheDocument();
  });
});
