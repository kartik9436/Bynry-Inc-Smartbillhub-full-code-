// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-020 (auto-archival: 2-yr hot → cold, 7-yr retention,
//           AUTOMATIC and never manual) · US-AUD-007 (the same job over the
//           audit trail)   Screens: S61
// Rules:    BR-MET-055 · BR-AUD-012 (never manual, audited) · BR-AUD-009
//           (System Admin + Executive) · CLAUDE.md law 1 (a field claiming a
//           guarantee is not the guarantee) · law 2 (built is not wired)
// ───────────────────────────────────────────────────────
/**
 * The screen that answers "has data retention ever run?" — the question the
 * surface-debt register said nobody could answer.
 *
 * Four of these six assert something the screen must SAY rather than something
 * it must show, and that is the shape of this story: the ledger existed, the
 * job ran, and every fact about it was invisible. The two hardest to get right
 * are the honest ones — that "never run" is a finding rather than a blank, and
 * that "archived" does not yet mean off-site.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { api } from "@/api/client";
import type { RetentionRunsResponse } from "@/api/endpoints";

import { RETENTION_ROUTE, RetentionRunsPage, retentionQueryKey, retentionTiles } from "./RetentionRunsPage";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** A deployment where the job has never fired — the honest default. */
function neverRun(): RetentionRunsResponse {
  return {
    status: {
      hot_window_months: 24,
      retention_years: 7,
      tables: [
        {
          table_name: "meter_reads",
          has_ever_run: false,
          last_run_date: null,
          last_run_status: null,
          last_run_note: null,
          runs: 0,
          partitions_archived: 0,
          partitions_purged: 0,
          never_run_reason: "no run of the retention job has ever been recorded for this table",
        },
        {
          table_name: "audit_log",
          has_ever_run: false,
          last_run_date: null,
          last_run_status: null,
          last_run_note: null,
          runs: 0,
          partitions_archived: 0,
          partitions_purged: 0,
          never_run_reason: "no run of the retention job has ever been recorded for this table",
        },
      ],
      off_site_shipping: false,
      off_site_reason: "shipper_absent",
      manual_trigger: false,
      schedule: "monthly, 1st, 02:00 UTC",
    },
    runs: [],
  };
}

/** US-MET-020 §4's own fixture: `meter_reads_2024_08`, 18,412 rows. */
function hasRun(): RetentionRunsResponse {
  const base = neverRun();
  base.status.tables[0] = {
    ...base.status.tables[0],
    has_ever_run: true,
    last_run_date: "2026-09-01",
    last_run_status: "success",
    runs: 1,
    partitions_archived: 1,
    never_run_reason: null,
  };
  base.runs = [
    {
      id: "run-1",
      table_name: "meter_reads",
      run_date: "2026-09-01",
      recorded_at: "2026-09-01T02:00:00Z",
      status: "success",
      note: null,
      hot_window_months: 24,
      retention_months: 84,
      archived: [
        {
          partition: "meter_reads_2024_08",
          row_count: 18412,
          includes_this_tenant: true,
          destination: null,
          shipped: false,
          shipped_reason: "shipper_absent",
        },
      ],
      purged: [],
      archived_count: 1,
      purged_count: 0,
    },
  ];
  return base;
}

function render(seed: RetentionRunsResponse): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(retentionQueryKey, seed);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}${RETENTION_ROUTE}`]}>
        <RetentionRunsPage client={api} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Data retention — has it ever run? (US-MET-020 / US-AUD-007)", () => {
  it("US-MET-020: a deployment that has never archived SAYS SO — it is not a blank screen", () => {
    const html = render(neverRun());
    expect(html).toContain(t("audit.retention.neverRan"));
    expect(html).toContain(t("audit.retention.noRuns"));
    // Both tables are named, so an operator sees which obligation is unmet.
    expect(html).toContain(t("audit.retention.table.meter_reads"));
    expect(html).toContain(t("audit.retention.table.audit_log"));
  });

  it("US-MET-020 TC-1/TC-2: a recorded run shows the partition it moved and how many rows", () => {
    const html = render(hasRun());
    expect(html).toContain("meter_reads_2024_08");
    expect(html).toContain("18412"); // §4's own figure, per partition
    expect(html).toContain(t("audit.retention.includedYou"));
    expect(html).toContain(t("audit.retention.historyTitle"));
  });

  it("CLAUDE.md law 1: the screen states that ARCHIVED does not yet mean OFF-SITE", () => {
    // Nothing in this repo registers a cold-store shipper, so every run records
    // shipped:false. Without this line an operator could tell an auditor the
    // data had left the building — which is a field claiming a transfer that
    // never happened, in the most expensive place to be wrong.
    expect(render(hasRun())).toContain(t("audit.retention.notOffSite"));
  });

  it("BR-MET-055 / BR-AUD-012: there is NO run-now control, and the absence is explained", () => {
    const html = render(hasRun());
    expect(html).toContain(
      t("audit.retention.neverManual", { schedule: "monthly, 1st, 02:00 UTC" }),
    );
    // The word a "Run now" button would carry appears nowhere on the screen.
    expect(html).not.toContain("Run now");
  });

  it("the tiles count PARTITIONS and never sum rows into an unanchored headline", () => {
    const tiles = retentionTiles(hasRun().status.tables, t);
    // `KpiTile` is a union (money | value); these are quantities, never money,
    // so a money tile here would be the bug the narrowing catches.
    const reads = tiles.find((tile) => tile.id === "meter_reads");
    expect(reads !== undefined && "value" in reads && reads.value).toBe(1); // one MONTH, not 18,412
    const trail = tiles.find((tile) => tile.id === "audit_log");
    // Never a 0: "has not run" and "ran and moved nothing" are different facts.
    expect(trail !== undefined && "value" in trail && trail.value).toBe("—");
  });

  it("the retention bound is printed from the SERVER, not hardcoded on the screen", () => {
    const html = render(hasRun());
    expect(html).toContain(t("audit.retention.law", { hot: 24, years: 7 }));
  });
});
