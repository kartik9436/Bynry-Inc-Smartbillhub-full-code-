// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-003 — the results popover. TC-1..TC-4 (a row per group and
//           where it goes), TC-6 (A18 §4 failed + Retry), TC-8 (A18 §2 no
//           results), and the amendment's TC-11 (B14 rule 31).
//           Screens: shell chrome, every authenticated screen
// Rules:    BR-SHL-005 AS AMENDED 2026-09-03 (nine groups, ≤5, per-group
//           "View all") · B14 rule 31 · B14 rule 32
// ───────────────────────────────────────────────────────
// Same conventions as AppShell's own suite: no DOM library in package.json, so
// markup asserts on react-dom/server static output, wrapped in a MemoryRouter
// because every row and every "View all" is a <Link>.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n"; // initializes the i18next singleton with the eleven catalogues

import type { SearchGroup } from "@/api/endpoints";

import { GlobalSearchResults } from "./GlobalSearchResults";

const ACCOUNT_ID = "01a064d5-bf86-72bb-97d9-cdd65f650afe";
const BILL_ID = "01a064d5-bf86-72bb-97d9-cdd65f650bbb";

function render(
  groups: readonly SearchGroup[],
  status: "idle" | "loading" | "error" | "ready" = "ready",
  query = "A-104",
): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <GlobalSearchResults
        query={query}
        groups={groups}
        status={status}
        onRetry={() => undefined}
        onNavigate={() => undefined}
        toHref={(path) => `/silvercreek${path}`}
        formatMoney={(amount, currency) => `${currency} ${Number(amount).toFixed(2)}`}
      />
    </MemoryRouter>,
  );
}

const ACCOUNTS: SearchGroup = {
  entity: "accounts",
  rows: [
    {
      id: ACCOUNT_ID,
      label: "A-10432",
      context: "Maria Delgado",
      amount: null,
      currency: null,
    },
  ],
};

const BILLS: SearchGroup = {
  entity: "bills",
  rows: [
    {
      id: BILL_ID,
      label: "BL-2608-018410",
      context: "A-10432",
      amount: "148.630000",
      currency: "USD",
    },
  ],
};

describe("US-SHL-003 — the results popover", () => {
  it("TC-1: a row shows its identifier and its one context line, and links to the record", () => {
    const html = render([ACCOUNTS]);
    expect(html).toContain("A-10432");
    expect(html).toContain("Maria Delgado");
    expect(html).toContain(`href="/silvercreek/accounts/${ACCOUNT_ID}"`);
  });

  // ══════════════════════════════════════════════════════════════════════
  // B14 RULE 31 — "no Databse ID on screen - that is a rule"
  // ══════════════════════════════════════════════════════════════════════
  it("TC-11: the record id is in the HREF and NOWHERE a reader can see it", () => {
    const html = render([ACCOUNTS, BILLS]);
    // It IS present — a popover that could not link anywhere would be useless.
    expect(html).toContain(`href="/silvercreek/accounts/${ACCOUNT_ID}"`);
    // …and it appears ONLY there. Strip every href and no uuid survives.
    const withoutHrefs = html.replace(/href="[^"]*"/g, "");
    expect(withoutHrefs).not.toContain(ACCOUNT_ID);
    expect(withoutHrefs).not.toContain(BILL_ID);
    expect(withoutHrefs).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/);
  });

  it("money renders to TWO places from the stored four-place decimal (hard rule 2)", () => {
    const html = render([BILLS]);
    expect(html).toContain("USD 148.63");
    // The wire value never reaches the screen unrounded.
    expect(html).not.toContain("148.630000");
  });

  it("BR-SHL-005: every group carries its own View all", () => {
    const html = render([ACCOUNTS, BILLS]);
    expect(html).toContain('href="/silvercreek/accounts?q=A-104"');
    expect(html).toContain('href="/silvercreek/billing?q=A-104"');
  });

  it("a bill links to /billing/bills/{id}, never /billing/{id}", () => {
    // `/billing/:tab` is the bills screen's TAB route, so a uuid in that
    // position resolves as a tab name and the bill never opens — a dead link
    // that tsc and every other assertion here would pass.
    const html = render([BILLS]);
    expect(html).toContain(`href="/silvercreek/billing/bills/${BILL_ID}"`);
  });

  it("a group the client has never heard of still renders its rows and does not crash", () => {
    // A TENTH group added server-side must not take the popover down with it.
    // This is the SignupWizard lesson — a front end that keeps its own copy of
    // a server list drops the eleventh item silently — and the answer here is
    // that the ROWS survive even when the client has no heading for the group.
    //
    // ⚠ THE CAST IS THE POINT. `SearchEntity` is a union, so `tsc` refuses an
    // unknown entity and the ONLY way to write this case is to lie to the type
    // — which is exactly what a server one deploy ahead does at runtime. An
    // earlier draft of this test passed "requests", a KNOWN entity, and its
    // name claimed something it did not check.
    const html = render([
      { entity: "quotes" as SearchGroup["entity"], rows: ACCOUNTS.rows },
    ]);
    expect(html).toContain("A-10432");
    expect(html).toContain("Maria Delgado");
    // The row still links somewhere rather than throwing on an unmapped route.
    expect(html).toContain("href=");
  });

  it("TC-8: no match states the query back, in one sentence, with no create action", () => {
    const html = render([], "ready", "zzzz");
    expect(html).toContain("zzzz");
    // A18 §2 offers no "create" beside a global search — the reader was looking
    // for something that exists, not asking to make one.
    expect(html.toLowerCase()).not.toContain("create");
    expect(html.toLowerCase()).not.toContain("add ");
  });

  it("TC-6: a failure says so and offers Retry — never a silent empty popover", () => {
    const html = render([], "error");
    expect(html).toContain("Search could not run.");
    expect(html).toContain("Retry");
    // Distinguishable from "nothing matched", which is the whole point: an
    // empty popover on a failure teaches a user their record does not exist.
    expect(html).not.toContain("No results");
  });

  it("in flight it says so rather than showing a stale or empty list", () => {
    expect(render([], "loading")).toContain("Searching…");
  });

  it("idle renders NOTHING — an empty box has no popover", () => {
    expect(render([], "idle")).toBe("");
  });
});
