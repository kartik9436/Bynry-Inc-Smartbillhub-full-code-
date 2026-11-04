// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-007 (S36) · US-LED-009 (S59) · US-LED-010 (S60) ·
//           US-LED-008 (S56) · US-LED-014 (S41) · US-LED-015 (S42) ·
//           US-LED-016 (S42/S43) — every finance read that takes a window
//           Screens: S36 · S41 · S42 · S43 · S56 · S59 · S60
// Rules:    BR-SHL-011 (the LIST grammar `q/sort/dir/page/per/f.<name>` — and
//           the boundary of it) · BR-REP-001 (a report states its period) ·
//           BR-TEN-022 (the period is COMPUTED and served, never guessed)
// ───────────────────────────────────────────────────────
// DEF-095 — one spelling for a period bound, checked from the side that was
// never checked.
//
// `reportQuery` prefixed EVERY param with `f.` under BR-SHL-011's LIST grammar,
// `from` and `to` included. `apps/ledger/api._window` and
// `apps/reports/api._required_window` both read the BARE names. So three screens
// sent `f.from=2026-08-01&f.to=2026-08-31` and asked for a window the server
// never saw: the two endpoints that REQUIRE a window answered 422
// `ledger.report.period_required`, and the one that does not served the
// CUMULATIVE position under a period heading — a figure that looks like the
// month and is the whole book.
//
// **NOTHING CAUGHT IT BECAUSE THE TWO HALVES WERE NEVER COMPARED.** The frontend
// suite asserted the wrapper's OUTPUT shape against a hand-built response and
// never its REQUEST; the backend suite called its own views with the names it
// reads. Each half was internally consistent. The defect's own prevention column
// names the durable fix — *"a check that every query-param NAME a frontend
// wrapper sends for a given path appears in the backend view that serves it"* —
// and this is the frontend half of it: the URL each wrapper actually builds,
// asserted against the names the server reads.
//
// A period bound is not a list filter. `f.` stays on the genuine filters.
import { describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import {
  getAccountLedgerReport,
  getByPremisesReport,
  getCloseChecklist,
  getJournalEntries,
  getRemittanceByAuthority,
  getRevenueAr,
  getTrialBalance,
} from "@/api/endpoints";

const TEST_TENANT = "brazosbend";

/** A client that records the URL and answers an empty 200. */
function recorder() {
  const seen: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL) => {
      seen.push(String(input));
      return new Response(JSON.stringify({ rows: [], results: [], count: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  return { seen, client };
}

const WINDOW = { from: "2026-07-01", to: "2026-07-31" };

describe("DEF-095 — a period bound is not a list filter", () => {
  it("sends `from` and `to` BARE on every finance read that takes a window", async () => {
    const { seen, client } = recorder();
    await getRevenueAr(WINDOW, client);
    await getAccountLedgerReport({ ...WINDOW, account_id: "acc-1" }, client);
    await getByPremisesReport(WINDOW, client);
    await getTrialBalance(WINDOW, client);
    await getJournalEntries(WINDOW, client);
    await getRemittanceByAuthority(WINDOW, client);
    await getCloseChecklist(WINDOW, client);

    expect(seen).toHaveLength(7);
    for (const url of seen) {
      // The exact defect: `f.from=` / `f.to=` reached three endpoints that read
      // the bare names, and two of them answered 422.
      expect(url).not.toContain("f.from=");
      expect(url).not.toContain("f.to=");
      expect(url).toContain("from=2026-07-01");
      expect(url).toContain("to=2026-07-31");
    }
  });

  it("keeps `f.` on the params that ARE list filters", async () => {
    const { seen, client } = recorder();
    // The journal list's own capability row: these really are BR-SHL-011
    // filters and the server reads them prefixed.
    //
    // ⚠ **S59's ACCOUNT IS NOT ONE, AND THIS CASE SAID IT WAS UNTIL
    // 2026-10-02.** It asserted `f.account_id=acc-1` — the request that made
    // S59 refuse every run with `VAL-001 reports.account_ledger.account_required`,
    // because `apps/reports/api._account_ledger` reads a BARE `account`
    // (`DEF-REP-6648`, fixed `7cf3853d3`, 2026-09-24, by `SERVER_PARAM_NAMES`).
    // This case was red from that commit on, defending the defect. It now
    // asserts the server's own word, bare, and that no `f.` copy goes with it.
    await getAccountLedgerReport({ ...WINDOW, account_id: "acc-1" }, client);
    await getJournalEntries({ ...WINDOW, status: "posted", type: "accrual" }, client);
    expect(seen[0]).toContain("account=acc-1");
    expect(seen[0]).not.toContain("f.account_id");
    expect(seen[1]).toContain("f.status=posted");
    expect(seen[1]).toContain("f.type=accrual");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-016@7e1e359 (12-governance/10-defect-log.csv DEF-095 + the six finance reads it names: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md · EP-LED-05 · 09-ledger/02-business-rules.md)
// generated: 2026-08-15 by story-coder (DEF-112 lane — DEF-095's durable half, from the side that was never checked)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — this asserts the REQUEST a wrapper builds, and calls no server) E=deferred(no-frontend-half — this IS a frontend test) F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — with `reportQuery`'s `f.` prefix restored on every param, this file failed with `AssertionError: expected '/api/brazosbend/finance/revenue-ar?f.…' not to contain 'f.from='`, which is DEF-095 exactly.
// exceptions: this asserts the frontend half of the comparison DEF-095's prevention column asks for. The BACKEND half — that the server reads the bare names and refuses the prefixed ones — is `test_us_led_016_tc1b__a_period_bound_is_read_bare_and_never_under_an_f_prefix` in 06-backend/tests/test_us_led_016_finance_api.py. Neither half alone would have caught the defect; that is the whole lesson.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
