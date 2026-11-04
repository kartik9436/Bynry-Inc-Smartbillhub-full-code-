// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 2 · P2.8 + P2.16 — "retire three screens into
//          definitions rendered by 2·1". NOT DONE, and this is the clock on it.
//          Screens: S59 · S60 · RPT-03 (the customer statement).
// Rules:   CLAUDE.md hard-won law 2, THE MIRROR, and its prescription —
//          **WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES WHEN THE HOLD
//          EXPIRES, IN THE SAME COMMIT, and assert the destination BY ADDRESS
//          AND BY THE SCREEN ID IT OPENS.** ·
//          12-governance/22-product-maintenance-process.md (*"a live screen
//          redrawn end to end is MAINTENANCE"* — reproduce, LOCATE, blast
//          radius) · B14 rule 31 (no database id is a visible value).
// ───────────────────────────────────────────────────────
//
// **THREE SCREENS A CLERK USES TODAY, AND THE BRIEF ASKS FOR THEM TO BE
// DELETED.** They are not deleted, because neither definition that would
// replace them can be executed — measured, and pinned from the server side in
// `06-backend/tests/test_cr142_p2_retirement_contract.py`:
//
//     runner.run("account_ledger") → DatasetNotExecutable ('journal_lines' has no query)
//     runner.run("statement")      → DatasetCannotServe   (invoices declines it, correctly)
//
// This file is the OTHER end of that hold. It asserts what a lane must not
// break while the blocker stands, and it is written the way `phaseHolds.dom.
// test.tsx` is written, for the reason that file gives: on 2026-09-05 the
// customer portal had two working doors out of eight, and every check passed.
//
// ⚠ **BY ADDRESS *AND* BY THE SCREEN ID IT OPENS, BECAUSE EITHER ALONE PASSES
// ON THE BUG.** `DEF-REP-6812` is the worked case: `/settings/audit-log`
// matched a route perfectly well — `settings/:tab` — and opened Settings →
// Company. Here the hazard is sharper still: `/reports/:reportKey` is a
// CATCH-ALL sitting in the same family. Delete
// `{ path: ACCOUNT_LEDGER_ROUTE… }` from `App.tsx` and `/reports/account-ledger`
// does not 404 — it is swallowed by the viewer as a report named
// `account-ledger`, which the server refuses with VAL-005. **An address
// assertion alone would be green on that.**
//
// ⚠ **AND THE MOUNT IS THE REAL ROUTING TABLE** — `APP_ROUTES`, matched with
// `matchRoutes` — not a bare `MemoryRouter`. A component mounted with no
// `/:tenant/…` pattern gets `useParams().tenant === undefined` and builds
// `//reports/…`, a protocol-relative URL to another host that reads as a
// perfectly good string to `toContain`.
import { matchRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/App";
import { resolveScreen } from "@/routing/screenIds";

import { AccountLedgerReportPage } from "./AccountLedgerReportPage";
import { ByPremisesReportPage } from "./ByPremisesReportPage";
import { CustomerStatementPage } from "./CustomerStatementPage";
import { ReportViewerPage } from "./ReportViewerPage";

const TENANT = "brazosbend";

/**
 * The three live addresses, the component each still mounts, the screen id it
 * opens, and the definition key it will retire INTO when its blocker lifts.
 *
 * ⚠ **THE KEY COLUMN IS THE FINDING.** `P2.8` says *"three definitions added"*
 * and `P2.16` says *"two definitions gained"*; the table holds **two** and the
 * drawing agrees with the table (p069, read as an image per B14 rule 42:
 * *"They collapse into two definitions with a `Subject` parameter"*). There is
 * no `by_premises` key and no `customer_statement` key, so *"redirect to
 * `/reports/{key}`"* has no key to point at for two of these three.
 */
const HELD_PAGES = [
  {
    address: `/${TENANT}/reports/account-ledger`,
    page: AccountLedgerReportPage,
    a1: "S59",
    r10: "RPT-02",
    retiresInto: "account_ledger?subject=account",
    blocker: "journal_lines has no dataset query — DatasetNotExecutable",
    file: "AccountLedgerReportPage.tsx",
  },
  {
    address: `/${TENANT}/reports/by-premises`,
    page: ByPremisesReportPage,
    a1: "S60",
    r10: "RPT-02",
    retiresInto: "statement?subject=premises",
    blocker: "the invoices dataset declines `statement` by name — DatasetCannotServe",
    file: "ByPremisesReportPage.tsx",
  },
  {
    address: `/${TENANT}/reports/customer-statement`,
    page: CustomerStatementPage,
    a1: null,
    r10: "RPT-03",
    retiresInto: "statement?subject=customer",
    blocker: "the invoices dataset declines `statement` by name — DatasetCannotServe",
    file: "CustomerStatementPage.tsx",
  },
] as const;

/** What the ROUTER mounts at an address — the element, not a mirror table. */
function elementAt(address: string): unknown {
  const matches = matchRoutes(APP_ROUTES, address);
  expect(matches, `${address} matches no route at all`).not.toBeNull();
  const leaf = (matches ?? [])[(matches ?? []).length - 1];
  return (leaf?.route as { element?: { type?: unknown } })?.element?.type;
}

describe("HOLD · the three bespoke report pages stay until their definitions can answer", () => {
  for (const held of HELD_PAGES) {
    it(`${held.address} still opens ${held.file}`, () => {
      // BY ADDRESS. The failure message is the retirement contract, so the
      // lane that lands the blocker's fix is told exactly what to do next.
      expect(
        elementAt(held.address),
        `${held.address} no longer opens ${held.file}.\n` +
          `  If you RETIRED it: keep the address working — P2.8 says "KEEP THE ` +
          `ADDRESSES, they are bookmarked and linked from Finance" — and point ` +
          `it at the viewer for \`${held.retiresInto}\`.\n` +
          `  If you DELETED the route: /reports/:reportKey is a CATCH-ALL and ` +
          `has just swallowed this address as a report named ` +
          `"${held.address.split("/").pop()}", which the server refuses with ` +
          `VAL-005. A clerk sees an error, not a redirect.\n` +
          `  The blocker as measured on 2026-09-27: ${held.blocker}.`,
      ).toBe(held.page);

      // BY THE SCREEN ID IT OPENS. An element assertion alone passes if the
      // screen-id table drifts; an id assertion alone passes if the router
      // moves the address. Both have happened in this repo.
      const screen = resolveScreen(held.address);
      expect(
        screen.a1,
        `${held.address} now reports A1 id ${String(screen.a1)}, not ${String(held.a1)}`,
      ).toBe(held.a1);
      expect(
        screen.r10,
        `${held.address} now reports r10 id ${String(screen.r10)}, not ${held.r10}`,
      ).toBe(held.r10);
    });
  }

  it("none of the three is served by the viewer yet — the catch-all has not taken them", () => {
    // The mirror assertion, and it is the one with the clock in it. The day a
    // lane repoints these addresses at 2·1 this case goes red and names the
    // three page components that are then owed a deletion.
    for (const held of HELD_PAGES) {
      expect(
        elementAt(held.address),
        `${held.address} now opens the report viewer. If \`${held.retiresInto}\` ` +
          `can answer, DELETE ${held.file} and its Finance links in the same ` +
          `commit — a page nothing routes to is dead code that still ships.`,
      ).not.toBe(ReportViewerPage);
    }
  });

  it("Finance's two links still open a page of their own, not the catch-all", () => {
    // BLAST RADIUS, asserted rather than remembered. `RevenueArPage` navigates
    // to BY_PREMISES_ROUTE and CUSTOMER_STATEMENT_ROUTE; both must open a real
    // screen. This is the check that would have caught the property-Overview
    // redesign, which the maintenance process names as the case this has
    // already gone wrong on.
    //
    // ⚠ **`matchRoutes(...) !== null` IS NOT THE CHECK, AND THE FIRST DRAFT OF
    // THIS CASE USED IT.** `/reports/:reportKey` is a catch-all in the same
    // family, so deleting either route leaves `matchRoutes` matching happily —
    // the assertion was STRUCTURALLY INCAPABLE OF FAILING (hard-won law 7's
    // second shape), and it was proved so: with the by-premises route removed
    // from `APP_ROUTES` it still passed. What it must ask is WHICH element.
    const CATCH_ALL_FOR = {
      [`/${TENANT}/reports/by-premises`]: ByPremisesReportPage,
      [`/${TENANT}/reports/customer-statement`]: CustomerStatementPage,
    } as const;
    for (const [address, page] of Object.entries(CATCH_ALL_FOR)) {
      const element = elementAt(address);
      expect(
        element,
        `${address} now falls through to /reports/:reportKey. Finance → ` +
          `Revenue & AR navigates here from RevenueArPage.tsx, and a clerk ` +
          `following that link reaches VAL-005 rather than a report.`,
      ).not.toBe(ReportViewerPage);
      expect(element, `${address} no longer opens its own page`).toBe(page);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P2.8 · P2.16 · 05-prototype/09 Reports Build Brief.pdf p010-p013, p069-p073 read as IMAGES per B14 rule 42
// screens: S59 · S60 · RPT-03
// generated: 2026-09-27 by lane REP-P2-RETIRE
// gates: RED PROVED FIRST — each address case was run with its route element swapped for ReportViewerPage in APP_ROUTES and failed naming the page component and the blocker; the Finance case was run with the by-premises route removed and failed naming RevenueArPage.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
