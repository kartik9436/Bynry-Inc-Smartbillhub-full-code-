// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-135` `P1.5` — *"Mount the existing imports list, with
//           `target=payments`"*. §03 frame 4·1 *Batches* (p061–p062) and its
//           §05 register row, **"Reuse — the existing imports list,
//           target=payments"**. Outcome: *"A fourth caller, not a fourth
//           implementation."*
// Screens:  S35 · PAY-F
// Rules:    BR-MET-096 (ONE `GET /imports`, filtered) · B14 rule 4 (the
//           drawing's *Doors: The Imports tab. 1 door.*) · rule 43 · hard
//           rule 4 (a posted payment cannot be unwritten — so no rollback)
// Tests:    this file
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY MOUNT IS UNDER THE REAL `/:tenant/payments/:tab` PATTERN.**
// CLAUDE.md hard-won law 2 records what a bare `MemoryRouter` costs: with no
// `/:tenant/…` route, `useParams().tenant` is undefined and every address the
// page builds comes out `//payments/…` — a protocol-relative URL to another
// host that reads as a perfectly good string to `toContain`. That fixture is
// how the customer portal's eight dead doors hid.
//
// ⚠ **THE DOOR IS ASSERTED BY ADDRESS, NOT BY LABEL.** `DEF-CWP-3925`: a
// control with a click handler carries nothing a test can read, so the one
// assertion that catches a door breaking cannot be written at all.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import type { ImportRunRow } from "@/api/endpoints";
import { getImportRuns } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { PaymentsPage } from "./PaymentsPage";
import { PAYMENTS_TABS_AWAITING_A_SCREEN } from "./paymentsShared";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** What the request actually asked for, captured off the fetch rather than
 *  asserted off the component's props — `BR-SHL-011` ignores an undeclared
 *  `f.<name>` SILENTLY, so "did we send the scope" is a question only the URL
 *  can answer. */
const asked: string[] = [];

function run(over: Partial<ImportRunRow> = {}): ImportRunRow {
  return {
    id: "run-9101",
    run_no: "IMP-260921-LBX",
    target: "payments",
    file_name: "friday_lockbox.csv",
    rows_in: 412,
    loaded: 0,
    rejected: 0,
    status: "validated",
    run_by: "dana.whitfield@brazosbend.test",
    started_at: "2026-09-21T11:04:00Z",
    finished_at: null,
    ...over,
  };
}

const SEEDED: ImportRunRow[] = [
  run(),
  run({
    id: "run-9098",
    run_no: "IMP-260920-SCN",
    file_name: "ruiz_grocery_sack.csv",
    rows_in: 1431,
    loaded: 1417,
    rejected: 14,
    status: "loaded",
    started_at: "2026-09-20T23:22:00Z",
    finished_at: "2026-09-20T23:26:00Z",
  }),
  // A PREMISES run — served by the SAME endpoint and it must not render here.
  run({
    id: "run-9002",
    run_no: "RUN-9002",
    target: "premises",
    file_name: "premises.csv",
    rows_in: 431,
    loaded: 425,
    rejected: 6,
    status: "loaded",
  }),
];

async function renderImports(
  rows: ImportRunRow[] | "unreadable" = SEEDED,
  writeBlocked = false,
): Promise<string> {
  asked.length = 0;
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async (input) => {
      const url = String(input);
      if (url.includes("/imports")) {
        asked.push(url);
        if (rows === "unreadable") {
          return new Response(JSON.stringify({ detail: "boom" }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify({ rows }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/access") || url.includes("/permissions")) {
        return new Response(
          JSON.stringify({ cell: writeBlocked ? "read" : "full" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ rows: [], methods: [], totals: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  try {
    await queryClient.prefetchQuery({
      // The tab's own key — `["import-runs", <scope>, <filters>]`. The empty
      // filter object is part of it (CR-045 wave D), and the request carries
      // the fixed `f.target=payments` scope.
      queryKey: ["import-runs", "payments", {}],
      queryFn: () => getImportRuns(client, { target: "payments" }),
    });
  } catch {
    // An unreadable list is one of the cases under test.
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/payments/imports`]}>
          <Routes>
            <Route
              path="/:tenant/payments/:tab"
              element={
                <PaymentsPage client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("P1.5 — the Imports tab mounts the ONE run list, scoped to payments", () => {
  it("the hold is GONE from the register and from the screen", async () => {
    // The mirror of `sevenTabs.dom.test.tsx`'s hold-expiry case, asserted from
    // this side: the register no longer names this tab, and the panel that
    // stood here is not in the markup.
    expect(PAYMENTS_TABS_AWAITING_A_SCREEN["imports"]).toBeUndefined();
    const html = await renderImports();
    expect(html).not.toContain("Imports are not built yet");
    expect(html).not.toContain('data-tracks="P1.5"');
  });

  it("renders the payments runs and NOT a premises run from the same endpoint", async () => {
    const html = await renderImports();
    expect(html).toContain("IMP-260921-LBX");
    expect(html).toContain("IMP-260920-SCN");
    expect(html).toContain("friday_lockbox.csv");
    // BR-MET-096: one endpoint, one filtered view. A premises run on the
    // payments tab is the defect this whole shape exists to prevent.
    expect(html).not.toContain("RUN-9002");
    expect(html).not.toContain("premises.csv");
  });

  it("asks the SERVER for the scope rather than filtering 200 rows in the browser", () => {
    // `DEF-CUS-5061`'s argument, kept: a tenant importing premises heavily
    // could otherwise push every payments run off the newest page, and the tab
    // would read "you have never imported payments" while its runs sat in a
    // table the server declined to send.
    expect(asked.length).toBeGreaterThan(0);
    expect(asked.some((url) => url.includes("f.target=payments"))).toBe(true);
  });

  it("the ONE door is an ADDRESS, and it is the tenant's own", async () => {
    const html = await renderImports();
    // ⚠ `//payments/imports/new` — what a fixture with no `/:tenant/…` route
    // produces — would satisfy a naive `toContain` and point at another host.
    expect(html).toContain(`href="/${TENANT}/payments/imports/new"`);
    expect(html).toContain(t("payments.imports.action.import"));
    // 4·1's note ①: *"one door, not two"*. A second `Scan` button stood beside
    // it until 2026-09-22 and came OFF — a sack of cheques is a source card on
    // Extract, not a second pipeline.
    expect((html.match(/href="\/brazosbend\/payments\/imports\/new"/g) ?? []).length).toBe(1);
  });

  it("the head is the drawing's — `Imports` under its own kicker", async () => {
    const html = await renderImports();
    expect(html).toContain(t("payments.imports.kicker"));
    // And the other six tabs are untouched: the strip still comes with it.
    expect(html).toContain(t("payments.tab.summary"));
    expect(html).toContain(t("payments.tab.outstandings"));
  });

  it("offers NO rollback on a loaded payments run — the server refuses it by name", async () => {
    // ⛔ **THE ASSERTION THIS FILE EXISTS FOR.** `IMP-260920-SCN` is `loaded`,
    // which is the one state every other Imports tab draws `↺ Roll back` on.
    // `import_runs.rollback` refuses the payments target BY NAME and
    // `_load_payments_rows` creates no rollback point, so the control would be
    // a live danger-tier button over a door the server keeps shut — hard-won
    // law 2's mirror, and what cost the customer portal six front doors.
    const html = await renderImports();
    expect(html).not.toContain(`aria-label="${t("metering.imports.action.rollback")}"`);
    // The fix IS offered, on the run that rejected fourteen rows — the two
    // actions answer two different questions (`DEF-CUS-5009`).
    expect(html).toContain(`aria-label="${t("metering.imports.action.fixRows")}"`);
  });

  it("an empty history says so, and its action is the same one door", async () => {
    const html = await renderImports([]);
    expect(html).toContain(t("payments.imports.empty.title"));
    expect(html).toContain(t("payments.imports.empty.helper"));
    expect(html).toContain(t("payments.imports.action.import"));
  });

  it("no fabricated figures: an unreadable list draws the retry frame, not a zero", async () => {
    const html = await renderImports("unreadable");
    expect(html).not.toContain(t("payments.imports.empty.title"));
    // 4·1 draws four tiles this list cannot serve; none of them is drawn, so
    // there is no tile to print a wrong zero into either.
    expect(html).not.toContain("Applied today");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p14 `P1.5` · §03 frame 4·1 (p061–p062) rendered at 2.0 · §05 register row S35 · PAY-F
// generated: 2026-09-22 by LANE P1-C
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/features/payments/paymentsImportsTab.dom.test.tsx · tsc --noEmit
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
