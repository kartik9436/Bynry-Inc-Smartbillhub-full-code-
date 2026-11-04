// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W1 T1.10/T1.11 — S81, the Accounts page's Imports tab.
// Story:    US-CUS-019.  Screens: S81 · S17.
// Rules:    BR-MET-096 (ONE runner — this tab is `GET /imports` FILTERED, not a
//           second list) · BR-MET-090 (a run's figures are what it RECORDED) ·
//           BR-SHL-011 (`?tab=` URL grammar, unknown values fall back) ·
//           BR-SHL-025 (disabled WITH the reason) · BR-SHL-044 (exactly one
//           primary, and it relabels with the tab) · B14 rule 15 (icon row
//           actions with an accessible name)
// ───────────────────────────────────────────────────────
// The assertions that matter most here are the NEGATIVE ones, in AST-04's own
// spirit: a premises run must NOT appear on the accounts tab, the KPI tiles
// must NOT print a total when the list could not be read, and the `↑` import
// must NOT be on the Accounts tab's header any more (T1.11).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import type { ImportRunRow } from "@/api/endpoints";
import { getImportRuns } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { AccountsListPage, accountsTabFromParam } from "./AccountsListPage";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** B18 §5.9.6's three `[shot]` runs, as `run_list` serves them. */
function run(over: Partial<ImportRunRow> = {}): ImportRunRow {
  return {
    id: "run-2814",
    run_no: "RUN-2814",
    target: "accounts",
    file_name: "customer_accounts_migration.csv",
    rows_in: 1251,
    loaded: 1247,
    rejected: 4,
    status: "loaded",
    run_by: "alex.reed@brazosbend.test",
    started_at: "2026-07-28T12:05:00Z",
    finished_at: "2026-07-28T12:09:00Z",
    ...over,
  };
}

const SEEDED: ImportRunRow[] = [
  run({
    id: "run-2822",
    run_no: "RUN-2822",
    file_name: "autopay_enrolments.csv",
    rows_in: 312,
    loaded: 310,
    rejected: 2,
    started_at: "2026-08-01T14:18:00Z",
    finished_at: "2026-08-01T14:19:00Z",
  }),
  run(),
  run({
    id: "run-2801",
    run_no: "RUN-2801",
    file_name: "contact_updates.csv",
    rows_in: 88,
    loaded: 88,
    rejected: 0,
    started_at: "2026-07-20T10:44:00Z",
    finished_at: "2026-07-20T10:45:00Z",
  }),
  // A PREMISES run — served by the same endpoint and MUST NOT render here.
  run({
    id: "run-2790",
    run_no: "RUN-2790",
    target: "premises",
    file_name: "premises.csv",
    rows_in: 431,
    loaded: 425,
    rejected: 6,
    started_at: "2026-07-14T09:00:00Z",
  }),
];

/**
 * Renders the real page at a real URL, with the run list PREFETCHED under the
 * tab's own query key — the AST-04 test's shape. `renderToStaticMarkup` never
 * resolves a promise, so a query that is not already in the cache renders the
 * loading state and asserts nothing about the rows.
 */
async function renderTab(
  path: string,
  rows: ImportRunRow[] | "unreadable" = SEEDED,
): Promise<string> {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      const url = String(input);
      if (url.includes("/imports")) {
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
      return new Response(JSON.stringify({ results: [], count: 0, rollup: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  try {
    await queryClient.prefetchQuery({
      // ⚠ THE EMPTY FILTER OBJECT IS PART OF THE KEY (CR-045 wave D · D.14),
      // and the request now carries the tab's fixed `f.target=accounts` scope.
      queryKey: ["import-runs", "accounts", {}],
      queryFn: () => getImportRuns(client, { target: "accounts" }),
    });
  } catch {
    // An unreadable list is one of the cases under test — the query lands in
    // the cache as an error and the tab must render its retry frame.
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <AccountsListPage client={client} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-030 W1 T1.10 — S81, the Accounts page's Imports tab", () => {
  it("BR-SHL-011: the strip carries both tabs and `?tab=imports` is what the workflow returns to", async () => {
    // `components/workflow/kinds.ts` sets the accounts kind's `returnTo` to the
    // literal "/accounts?tab=imports". If this URL did not land on the tab, a
    // finished import would return the operator to the accounts list with no
    // sign the run ever happened.
    const html = await renderTab("/accounts?tab=imports");
    expect(html).toContain(t("customers.accounts.tab.accounts"));
    expect(html).toContain(t("customers.accounts.tab.imports"));
    expect(html).toContain(t("customers.imports.lede"));
    // The run table replaces the accounts body — the accounts empty state is
    // not underneath it.
    expect(html).not.toContain(t("customers.accounts.emptyTitle"));
  });

  it("BR-SHL-011: an unknown ?tab= falls back to Accounts rather than erroring", () => {
    expect(accountsTabFromParam("imports")).toBe("imports");
    expect(accountsTabFromParam("accounts")).toBe("accounts");
    expect(accountsTabFromParam(null)).toBe("accounts");
    // ⚠ AMENDED 2026-08-24 (CR-030 W2 T2.1). This line read
    // `expect(accountsTabFromParam("transfers")).toBe("accounts") // W7's, not
    // built` — true when the strip held two tabs, and false now that it holds
    // B18 §4's eight. `transfers` is a REAL tab id whose body is a stated
    // absence, so resolving it to `accounts` would send a user somewhere they
    // did not ask for. This is DEF-625's class one file over: a pin on the
    // absence of a feature, correct when written, blocking the commit that
    // implements the ruling. What the case still guards is the fallback itself,
    // and it is asserted on a string that really is not a tab.
    expect(accountsTabFromParam("transfers")).toBe("transfers");
    expect(accountsTabFromParam("nonsense")).toBe("accounts");
    expect(accountsTabFromParam("")).toBe("accounts");
  });

  it("BR-MET-096: the ONE run list is FILTERED to accounts — a premises run does not render", async () => {
    const html = await renderTab("/accounts?tab=imports");
    expect(html).toContain("RUN-2814");
    expect(html).toContain("RUN-2822");
    expect(html).toContain("RUN-2801");
    expect(html).toContain("customer_accounts_migration.csv");
    expect(html).not.toContain("RUN-2790");
    expect(html).not.toContain("premises.csv");
  });

  it("B18 §5.9.4 / BR-MET-090: the KPI tiles SUM what the runs recorded", async () => {
    const html = await renderTab("/accounts?tab=imports");
    expect(html).toContain(t("customers.imports.kpi.runs"));
    expect(html).toContain(t("customers.imports.kpi.rowsLoaded"));
    expect(html).toContain(t("customers.imports.kpi.rejected"));
    expect(html).toContain(t("customers.imports.kpi.lastRun"));
    // 3 accounts runs (the premises one is filtered out before the sum).
    expect(html).toContain(">3<");
    // 1,247 + 310 + 88 = 1,645 — B18 §5.9.4's own figure.
    expect(html).toContain("1,645");
    // 4 + 2 + 0 = 6.
    expect(html).toContain(">6<");
    // LAST RUN names the newest run's FILE, and `run_list` is newest-first.
    expect(html).toContain("autopay_enrolments.csv");
  });

  it("no fabricated KPI: a list AT the 200-row server cap dashes every tile", async () => {
    // `run_list` serves at most 200 rows and does not page, so at the cap the
    // sums are a FLOOR. Printing a floor as a total is the same defect as
    // inventing one — every tile shows the quiet dash, and the cap note says
    // why in words.
    const capped = Array.from({ length: 200 }, (_unused, index) =>
      run({ id: `run-${index}`, run_no: `RUN-${9000 + index}` }),
    );
    const html = await renderTab("/accounts?tab=imports", capped);
    expect((html.match(/data-kpi-absent="true"/g) ?? []).length).toBe(4);
    // The labels still render — the tile is drawn and its value stated absent,
    // never dropped, so the reader knows the figure exists and we could not
    // complete it.
    expect(html).toContain(t("customers.imports.kpi.runs"));
    expect(html).toContain(t("customers.imports.kpi.lastRun"));
    expect(html).toContain(t("metering.imports.cap", { cap: 200 }));
    // 200 × 1,247 = 249,400 must NOT appear anywhere as a total.
    expect(html).not.toContain("249,400");
  });

  it("no fabricated KPI: an unreadable run list never prints a zero", async () => {
    const html = await renderTab("/accounts?tab=imports", "unreadable");
    // "0 runs" would be a claim about a tenant whose history we could not read
    // at all, and "no imports yet" would be the same claim in words.
    expect(html).not.toContain(">0<");
    expect(html).not.toContain(t("customers.imports.empty.title"));
  });

  it("B14 rule 15 / B18 §5.9.4: `↺ Roll back` on a loaded run, `🔧 Fix rows` disabled with its reason", async () => {
    const html = await renderTab("/accounts?tab=imports", [
      run(),
      run({ id: "run-2830", run_no: "RUN-2830", status: "validated", loaded: 0 }),
    ]);
    // Icons with accessible names — never text links (G37's shape, asserted
    // here at the call site the gate cannot read).
    expect(html).toContain(`aria-label="${t("metering.imports.action.rollback")}"`);
    expect(html).toContain(`aria-label="${t("metering.imports.action.fixRows")}"`);
    // BR-SHL-025: the blocked one carries its reason as the tooltip.
    expect(html).toContain(t("metering.imports.fixRowsBlocked"));
  });

  it("the rollback callout states the law, not just the courtesy window", async () => {
    const html = await renderTab("/accounts?tab=imports");
    expect(html).toContain(t("customers.imports.rollbackCallout"));
    // hard rule 4 reaches the screen: an already-billed account is KEPT.
    expect(t("customers.imports.rollbackCallout")).toContain("30 days");
    expect(t("customers.imports.rollbackCallout")).toContain("billed");
  });

  it("A18: an empty accounts history says so, and its CTA is the ONE import entry", async () => {
    const html = await renderTab("/accounts?tab=imports", []);
    expect(html).toContain(t("customers.imports.empty.title"));
    expect(html).toContain(t("customers.imports.empty.helper"));
    expect(html).toContain(t("customers.accounts.action.import"));
  });
});

describe("CR-030 W1 T1.11 — the `↑` import leaves the Accounts header", () => {
  it("BR-SHL-044: the Accounts tab carries `+ New account` and NO import button", async () => {
    const html = await renderTab("/accounts");
    expect(html).toContain(t("customers.accounts.action.new"));
    // B18 §5.9.2 row 7 — the import moved to its own tab. It is on the STRIP
    // as a tab label, and not as a header button beside Move-in/Move-out.
    expect(html).not.toContain(t("customers.accounts.action.import"));
    expect(html).toContain(t("customers.accounts.action.moveIn"));
    expect(html).toContain(t("customers.accounts.action.moveOut"));
  });

  it("BR-SHL-044 (a): the ONE primary slot relabels to `↑ New import` on the Imports tab", async () => {
    const html = await renderTab("/accounts?tab=imports");
    expect(html).toContain(t("customers.accounts.action.import"));
    // Exactly one primary per page: the S18 entry is not also rendered, and
    // the account-scoped Move-in/Move-out secondaries are not on this tab.
    expect(html).not.toContain(t("customers.accounts.action.new"));
    // ⚠ ASKED OF THE BUTTON, NOT OF THE DOCUMENT (CR-030 W2 T2.1). This read
    // `not.toContain(t("customers.accounts.action.moveIn"))` — "Move-in" — and
    // B18 §4's strip now carries a TAB called "Move-ins", which contains that
    // substring. The assertion would have gone red on a page that is correct,
    // which is worse than not asserting: the thing it means is that the
    // account-scoped SECONDARY is not on this tab, so that is what it asks.
    expect(html).not.toMatch(/<button[^>]*>Move-in<\/button>/);
    expect(html).not.toMatch(/<button[^>]*>Move-out<\/button>/);
  });
});

describe("DEF-CUS-5009 · which run is offered which action, asserted by CASE", () => {
  /** Every row's actions, read off the RENDERED table by accessible name —
   *  never off the branch that chose them. That distinction is the defect:
   *  the old ternary was correct code answering the wrong question, and a test
   *  of the branch would have agreed with it. */
  async function actionsByRun(): Promise<Record<string, string[]>> {
    const html = await renderTab("/accounts?tab=imports");
    const out: Record<string, string[]> = {};
    for (const tr of html.split("<tr").slice(1)) {
      const runNo = tr.match(/RUN-\d+|IMP-[\d-]+/)?.[0];
      if (runNo === undefined) continue;
      out[runNo] = [...tr.matchAll(/aria-label="([^"]+)"/g)]
        .map((m) => m[1])
        .filter((name) =>
          name === t("metering.imports.action.rollback") ||
          name === t("metering.imports.action.fixRows"),
        );
    }
    return out;
  }

  it("a finished run WITH rejected rows is offered the fix — it used to be offered only Roll back", async () => {
    const byRun = await actionsByRun();
    // RUN-2814: 1,251 in / 1,247 loaded / 4 REJECTED / loaded.
    expect(byRun["RUN-2814"]).toContain(t("metering.imports.action.fixRows"));
    // …and roll back as well, because both are true of it: reverse all 1,251,
    // or repair the 4. They are not alternatives.
    expect(byRun["RUN-2814"]).toContain(t("metering.imports.action.rollback"));
    // RUN-2822: 312 / 310 / 2 REJECTED / loaded — the same pair.
    expect(byRun["RUN-2822"]).toContain(t("metering.imports.action.fixRows"));
  });

  it("a finished run with NOTHING rejected is not offered a fix for rows it has not got", async () => {
    const byRun = await actionsByRun();
    // RUN-2801: 88 / 88 / 0 rejected / loaded.
    expect(byRun["RUN-2801"]).toEqual([t("metering.imports.action.rollback")]);
  });

  it("a run still in flight with nothing rejected is offered neither, rather than a fix for nothing", async () => {
    const inFlight = [
      run({
        id: "imp-260912-02",
        run_no: "IMP-260912-02",
        file_name: "smoke-accounts.csv",
        rows_in: 3,
        loaded: 0,
        rejected: 0,
        status: "extracted",
        finished_at: null,
      }),
    ];
    const html = await renderTab("/accounts?tab=imports", inFlight);
    // This is the row that USED to carry `Fix the rejected rows`, disabled,
    // while the two runs with rejects carried nothing of the kind.
    expect(html).not.toContain(t("metering.imports.action.fixRows"));
    expect(html).not.toContain(t("metering.imports.action.rollback"));
  });

  /**
   * ⏳ **THE HOLD-EXPIRY CASE — CLAUDE.md hard-won law 2's mirror half.**
   *
   * *"When you write a hold, write the test that fires when the hold expires,
   * in the same commit."* Reopening a finished run is `ACC-S9`, a
   * specification with no ruling deferring it, and until it is built the fix
   * renders DISABLED carrying its reason (BR-SHL-025).
   *
   * **The day `ACC-S9` lands and the `reason` goes, this case goes RED and
   * names the row that owns it.** That is the whole point: a hold with no such
   * test is a promise nobody is keeping, and this one had already rotted onto
   * the wrong rows before anybody looked.
   */
  it("ACC-S9 · the fix is still HELD, and still says why — this case fires the day it is built", async () => {
    const html = await renderTab("/accounts?tab=imports");
    const fix = html
      .split("<button")
      .find((b) => b.includes(`aria-label="${t("metering.imports.action.fixRows")}"`));
    expect(fix, "the fix action is not rendered at all — DEF-CUS-5009").toBeDefined();
    // Disabled, and the reason is ON the control rather than in a grey box.
    expect(fix).toContain("disabled=");
    expect(fix).toContain(t("metering.imports.fixRowsBlocked"));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030/B18@2026-08-23 §5.9.4 (S81) · US-CUS-019 · W1 T1.10/T1.11
// generated: 2026-08-24 by the CR-030 W1 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest✔
// exceptions: E4 the cases are asserted over STATIC markup through the mocked client seam, the shape every other customers test uses — a click on the tab strip and the rollback dialog's own confirm need a browser and stay the Playwright journey's · E4 TC-IMP-8..10 (rollback refused when billed / outside the window) assert a SERVER verdict and are the backend suite's; ⚠ THIS CLAUSE READ "this file asserts only that the control is offered on a loaded run and blocked with its reason elsewhere" UNTIL 2026-09-12, AND IT DESCRIBED THE DEFECT — DEF-CUS-5009. "Blocked with its reason elsewhere" was true and was the bug: elsewhere meant every run that had not finished, and never the runs that actually had rejected rows. The file now asserts the pairing by CASE off the rendered table — rejected > 0 is offered the fix, rejected = 0 is not, a loaded run is offered roll back — and carries ACC-S9's hold-expiry case
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
