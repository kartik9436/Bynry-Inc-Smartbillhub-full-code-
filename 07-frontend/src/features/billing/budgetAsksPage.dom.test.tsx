// ── Trace ──────────────────────────────────────────────
// Story:    §05 entry 25.3 `Asks` (Billing blueprint p126–p127, read as images)
// Rules:    B14 rule 31 (no database id is ever a field's visible value) ·
//           rule 32 (no rule id or internal code in clerk-facing copy) ·
//           rule 33 (the five caps; RATIONALE is zero words on screen) ·
//           rule 37 (a drawn figure is an ILLUSTRATION) · rule 41 (the product
//           matches the drawing) · hard-won law 2 and its fixture clause
//           (mount under the REAL path pattern) · BR-SHL-020 (a tile states an
//           absence, never a substituted 0)
// Tests:    this file
// Open:     OQ-BIL-12359
// ───────────────────────────────────────────────────────
//
// ⚠ **THE FIXTURE MOUNTS THE REAL PATH PATTERN.** A bare `MemoryRouter` with no
// `/:tenant/…` route leaves `useParams().tenant` undefined, so every address the
// page builds comes out `//billing/…` — a protocol-relative URL to another host,
// which reads as a perfectly good string to `toContain`. That fixture is how
// `DEF-CWP-3925` hid eight dead doors over live screens, so every door case here
// asserts the WHOLE address including the tenant segment.
//
// ⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY** (law 7, habit 2):
//   · `TC-A3` would pass on a screen printing `0` beside a correct sentence if
//     it only asserted the sentence. It asserts the dash AND that `>0<` is not
//     the value of any tile — which is the actual failure mode, because a zero
//     looks finished.
//   · `TC-A5` would pass on a page that rendered the table headers under the
//     absence sentence. It asserts the headers are ABSENT — furniture over rows
//     that cannot arrive is the dead control `DEF-CWP-3925` cost eight doors to.
//   · `TC-A6` would pass on a table missing one of the two level columns if it
//     only counted headers. It names BOTH by their catalogue text, because
//     collapsing them is the specific mistake p127 warns about in capitals.
//   · `TC-A7` asserts the door's FULL address. `toContain("/requests")` alone
//     passes on `//requests`, the protocol-relative bug above.
//   · `TC-A9` strips attribute values before hunting for a uuid, because
//     `account_id` legitimately travels inside an `href`. Without the strip it
//     would fail on a correct screen; without the assertion it would pass on one
//     printing a row id at a clerk.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";
import type { BudgetAsksResponse, BudgetListResponse } from "@/api/billingOpsEndpoints";

import { BudgetAsksPage, budgetAsksKey } from "./BudgetAsksPage";
import { BudgetBillsTab, budgetListKey } from "./BudgetBillsTab";
import { BUDGET_ASKS_ROUTE, BUDGET_ENROL_ROUTE, BUDGET_TAB_ROUTE } from "./billingShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const TENANT = "brazosbend";

/** Today's answer: the rows are withheld and the reason travels with them. */
const WITHHELD: BudgetAsksResponse = {
  count: null,
  results: [],
  page: 1,
  per: 50,
  rows_unavailable:
    "an ask to level payments is raised as an ordinary service request and carries no route, " +
    "no kind and no account of its own, so the requests waiting to be put on a level cannot " +
    "be told apart from every other request a customer has raised. The queue is withheld " +
    "rather than filled with rows nobody checked.",
  summary: {
    waiting: null,
    waiting_unavailable: "…",
    eligible_now: null,
    eligible_now_unavailable: "…",
    not_eligible: null,
    not_eligible_unavailable: "…",
    // ⚠ B14 rule 37 — `11` is an ILLUSTRATION of a SHAPE, not the drawing's
    // own figure asserted back at itself. What is asserted is that a SERVED
    // number reaches the tile and an UNSERVED one says so.
    enrolled_this_month: 11,
    enrolled_from_portal: null,
    enrolled_from_portal_unavailable: "…",
  },
  unavailable: [],
};

/** The day `customers` publishes its read — the hold expiring, on the screen. */
const SERVED: BudgetAsksResponse = {
  ...WITHHELD,
  count: 2,
  rows_unavailable: null,
  results: [
    {
      reference: "SR-26-0087",
      asked_on: "2026-11-07",
      account_id: "11111111-2222-3333-4444-555555555555",
      account_no: "ACC-10519-C",
      customer_name: "Nguyen, T.",
      level_shown: "112.0000",
      level_now: "119.0000",
      currency: "USD",
      eligible: true,
      not_eligible_because: null,
    },
    {
      reference: "SR-26-0091",
      asked_on: "2026-11-05",
      account_id: "66666666-7777-8888-9999-000000000000",
      account_no: "ACC-10655-A",
      customer_name: "Duarte, S.",
      level_shown: null,
      level_now: null,
      currency: null,
      eligible: false,
      not_eligible_because: "Seven months of bills only",
    },
  ],
};

function render(body: BudgetAsksResponse = WITHHELD): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: Infinity } },
  });
  client.setQueryData(budgetAsksKey(1, 50), body);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          {/* THE REAL PATH PATTERN — see this file's header. */}
          <MemoryRouter initialEntries={[`/${TENANT}${BUDGET_ASKS_ROUTE}`]}>
            <Routes>
              <Route path="/:tenant/billing/budget/asks" element={<BudgetAsksPage />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

describe("§05 entry 25.3 — a customer's ask reaching a clerk", () => {
  it("TC-A1 · draws the page head the drawing gives it", () => {
    const html = render();
    expect(html).toContain(t("billing.budgetAsks.title"));
    expect(html).toContain(t("billing.budgetAsks.caption"));
    // The Billing tab strip stays, with Budget Bills active — the drawing keeps
    // it and so does 25.1 one screen along.
    expect(html).toContain(t("billing.tab.budget"));
  });

  it("TC-A2 · the four drawn tiles are all there, in the drawn order", () => {
    const html = render();
    const order = [
      t("billing.budgetAsks.kpi.waiting"),
      t("billing.budgetAsks.kpi.eligible"),
      t("billing.budgetAsks.kpi.notEligible"),
      t("billing.budgetAsks.kpi.enrolled"),
    ].map((label) => html.indexOf(label));
    expect(order.every((at) => at >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it("TC-A3 · an unreadable tile shows a dash and its reason — never a zero", () => {
    // `0` on `Waiting` says *nobody asked*; a dash with a line under it says
    // *nobody could ask* (BR-SHL-020). On a screen about people waiting for a
    // telephone call those are not the same statement.
    const html = render();
    expect(html).toContain(t("billing.budgetAsks.kpi.notRecorded"));
    expect(html).toContain("—");
    // The one REAL figure is served and reaches the tile.
    expect(html).toContain(">11<");
    // …and no tile fabricated a zero in place of an absence.
    expect(html).not.toContain(">0<");
  });

  it("TC-A4 · the drawn provenance line is stated absent, never invented", () => {
    // p126 draws *"3 from the portal"* under the fourth tile. Nothing records
    // where an enrolment came from; rule 37 makes the drawn figure an
    // illustration, so the screen says the fact is not held.
    const html = render();
    expect(html).toContain(t("billing.budgetAsks.kpi.originNotHeld"));
    expect(html).not.toContain("3 from the portal");
  });

  it("TC-A5 · while the rows are withheld, no table furniture is drawn", () => {
    const html = render();
    expect(html).toContain(t("billing.budgetAsks.notHeld"));
    // No headers, no search box, no filter chips over rows that cannot arrive.
    expect(html).not.toContain(t("billing.budgetAsks.col.reference"));
    expect(html).not.toContain(t("billing.budgetAsks.col.levelShown"));
    expect(html).not.toContain("<table");
  });

  it("TC-A6 · when the server serves rows, BOTH level columns are drawn", () => {
    // ⚠ p127, in capitals: *"THE TWO LEVEL COLUMNS ARE NOT A DUPLICATE."* A
    // month passes, a bill lands, and the quoted figure stops being correct.
    const html = render(SERVED);
    expect(html).toContain(t("billing.budgetAsks.col.levelShown"));
    expect(html).toContain(t("billing.budgetAsks.col.levelNow"));
    expect(html).toContain(t("billing.budgetAsks.col.reference"));
    expect(html).toContain(t("billing.budgetAsks.col.eligible"));
    // Both figures render, and they differ — which is the whole argument for
    // the second column existing at all.
    expect(html).toContain("112.00");
    expect(html).toContain("119.00");
    // *"Not eligible is a row, not a rejection"* — the reason is ON the row.
    expect(html).toContain("Seven months of bills only");
  });

  it("TC-A7 · the door out points at the requests queue, with the tenant on it", () => {
    const html = render();
    expect(html).toContain(t("billing.budgetAsks.openRequests"));
    expect(html).toContain(`href="/${TENANT}/requests"`);
    // The protocol-relative bug this fixture exists to catch.
    expect(html).not.toContain('href="//requests"');
  });

  it("TC-A8 · a served row's Enrol door opens 25.1 with the account filled in", () => {
    // *"It reuses the enrol screen rather than repeating it"* (p127). Two
    // enrolment forms would drift within a release.
    const html = render(SERVED);
    expect(html).toContain(
      `href="/${TENANT}${BUDGET_ENROL_ROUTE}?account=11111111-2222-3333-4444-555555555555"`,
    );
    expect(html).toContain(t("billing.budgetAsks.enrol"));
    expect(html).toContain(t("billing.budgetAsks.tellThemWhy"));
  });

  it("TC-A9 · no database id is the visible value of a field (rule 31)", () => {
    // `account_id` legitimately travels inside an `href` for the door above, so
    // attribute VALUES are stripped before the hunt. What is asserted is that no
    // uuid reaches the TEXT a clerk reads.
    const text = render(SERVED).replace(/="[^"]*"/g, "");
    expect(text).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
    // What a clerk DOES read is the number on the paper bill and the number
    // they quote down the telephone.
    expect(text).toContain("ACC-10519-C");
    expect(text).toContain("SR-26-0087");
  });

  it("TC-A10 · no rule id and no internal code reaches the clerk (rule 32)", () => {
    for (const html of [render(), render(SERVED)]) {
      const text = html.replace(/<!--[\s\S]*?-->/g, "").replace(/="[^"]*"/g, "");
      expect(text).not.toMatch(/\b(?:OQ|DEF|BR|GT|US|EP|CR|NFR)-[A-Z]{0,3}-?\d{2,5}\b/);
    }
  });

  it("TC-A11 · the server's own sentence is NOT what the clerk reads", () => {
    // `DEF-BIL-5316` one screen along: the tab printed the server's engineer-
    // facing explanation verbatim, two rule ids and all. This screen states the
    // same absence in its own catalogue words and never renders `rows_unavailable`.
    const html = render();
    expect(html).not.toContain("ordinary service request");
    expect(html).toContain(t("billing.budgetAsks.notHeld"));
  });

  it("TC-A12 · RATIONALE is zero words on screen (rule 33)", () => {
    // Group 1 of the drawing — `WHY AN ASK AND NOT AN ENROLMENT`, four rows —
    // answers *why does the product work this way*. Rule 33 removes it rather
    // than shortening it. So does the warning band under the pager.
    const html = render();
    for (const drawn of [
      "WHY AN ASK AND NOT AN ENROLMENT",
      "rows of exactly six kinds",
      "What is at stake",
      "NOT A DUPLICATE",
      "A month can pass",
    ]) {
      expect(html).not.toContain(drawn);
    }
  });
});

describe("§05 entry 25.3 — the door, asserted by ADDRESS so it cannot rot", () => {
  it("TC-A13 · the route constant is the address App.tsx mounts", () => {
    // `DEF-CWP-3925`'s hold-expiry test asserted a screen was REGISTERED at one
    // address while the router mounted it at another, and every check passed
    // over both. This asserts the literal, and the App test below asserts the
    // mount, so the two cannot drift apart silently.
    expect(BUDGET_ASKS_ROUTE).toBe("/billing/budget/asks");
    expect(BUDGET_ASKS_ROUTE.startsWith(BUDGET_TAB_ROUTE)).toBe(true);
  });

  it("TC-A14 · the Budget Bills tab carries a door that points HERE", () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: Infinity } },
    });
    const list: BudgetListResponse = {
      results: [],
      count: 0,
      parameters: { override_bound_pct: "30", eligibility_months: 12 },
      parameters_unavailable: null,
      statuses: ["enrolled", "off_budget"],
      unavailable: [],
    };
    client.setQueryData(budgetListKey(""), list);
    const html = renderToStaticMarkup(
      <QueryClientProvider client={client}>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <ToastProvider>
            <MemoryRouter initialEntries={[`/${TENANT}${BUDGET_TAB_ROUTE}`]}>
              <Routes>
                <Route path="/:tenant/billing/budget" element={<BudgetBillsTab />} />
              </Routes>
            </MemoryRouter>
          </ToastProvider>
        </TenantRegionalProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain(`href="/${TENANT}${BUDGET_ASKS_ROUTE}"`);
    expect(html).toContain(t("billing.budgetAsks.door"));
    // The enrol door is still there — two doors, not one replacing the other.
    expect(html).toContain(`href="/${TENANT}${BUDGET_ENROL_ROUTE}"`);
  });
});
