// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-018/019/020   Screens: S30 (Budget Bills tab) · BIL-01.budget
// Drawing:  `05-prototype/04 Billing, As Built.pdf` §05 entry 25, p121–p122,
//           read AS IMAGES (B14 rule 42). Its table is EIGHT columns:
//           ACCOUNT · STATUS · COMPUTED · OVERRIDE · THEY PAY · ACTUAL TO DATE ·
//           VARIANCE · RE-LEVEL, and its rule row says why three of them are
//           money: *"The ±30% bound is measured against the computed figure, so
//           hiding it is how an override gets typed blind."*
// Rules:    B14 rule 12 (the table toolbar) · rule 16 (a pagination footer on
//           every list table) · rule 31 (no database id is the visible value of
//           a field) · NFR-3 (universal server pagination) · BR-BIL-017 (three
//           level figures, never collapsed) · CLAUDE.md rule 2 (money displays
//           to 2 decimals)
// ───────────────────────────────────────────────────────
// ⚠ **WHAT THIS FILE CAN AND CANNOT SEE, SAID FIRST (hard-won law 7).**
// `renderToStaticMarkup` performs no layout and fires no effect. It cannot tell
// you the columns are aligned, that the pager pages, or that anything looks
// right. What it CAN tell you — and what nothing in this repository told anyone
// before — is **which columns the Budget Bills table declares, in which order,
// and what each cell renders when the server says null.**
//
// ⚠ **AND IT EXISTS BECAUSE THE SCREEN CANNOT BE DRIVEN WITH DATA IN THIS
// ENVIRONMENT.** Budget enrolment requires twelve months of ISSUED billing
// history; this database holds **zero invoices**, so no account anywhere can be
// enrolled and the live table has no row to render. The browser walk therefore
// proves the empty screen and this file proves the populated one. Saying which
// check covers what is the point of this paragraph.
//
// RED-FIRST PROOF, through this harness (`npx vitest run
// src/features/billing/budgetBillsTable.dom.test.tsx`) and not a hand-rolled
// entry point, in a `git worktree` pinned at `531f3506` — the tip before this
// change. **All six went red**, verbatim:
//
//   TC-B1 → column "Status" is missing or out of order: expected -1 to be
//           greater than 743
//   TC-B2 → expected '<div class="flex flex-col gap-4"><p c…' to contain
//           'Rows per page'
//   TC-B3 → expected … to contain '88.00'
//   TC-B4 → expected +0 to be 3
//   TC-B5 → expected … to contain 'No account number'
//   TC-B6 → expected … to contain 'billing.budget.kpi.enrolled'
//
// ⚠ **AND WHAT THAT RED DOES AND DOES NOT PROVE, because law 7's second habit
// is to ask what would make a check pass — or fail — wrongly.** The
// pre-change component built a different query key (`budgetListKey(status)`,
// with no page or filter in it), so the seeded response did not reach it and
// it rendered its empty list. **So these reds prove the old screen did not put
// these things in front of a clerk; they do not isolate WHICH of the two
// reasons each one had.** TC-B2 is the exception and is conclusive either way:
// the old list had no pager to render under any data at all.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";
import type { BudgetListResponse, BudgetStatusRow } from "@/api/billingOpsEndpoints";

import * as billingShared from "./billingShared";
import { BudgetBillsTab, budgetListKey } from "./BudgetBillsTab";

const t = (key: string): string => i18n.t(key);

/** ⚠ EVERY FIGURE HERE IS THIS FIXTURE'S OWN AND NONE IS THE DRAWING'S.
 *  B14 rule 37: a number inked into a wireframe is an illustration, and a test
 *  that asserts `$142.00` because p121 draws it has written a test about the
 *  illustrator's choice of example. These are shapes: one row with an override
 *  and one without, one off-budget row that keeps its computed level. */
const ROWS: BudgetStatusRow[] = [
  {
    account_id: "01a00000-0000-7000-8000-0000000000a1",
    account_no: "A-40001",
    customer_name: "Navarro, P.",
    status: "enrolled",
    level: "88.000000",
    level_override: "96.000000",
    level_override_reason: "agreed on the phone",
    effective_level: "96.000000",
    variance_balance: "-212.800000",
    currency: "USD",
    settle_up_month: 1,
    enrolled_on: "2026-01-04",
    last_leveled_at: "2026-01-04",
    actual_to_date: "1056.000000",
    actual_months: 9,
    relevel_due_on: "2026-07-04",
    relevel_is_due: true,
    relevel_drift_unavailable: "nothing stores a recomputed level",
  },
  {
    // The row with NOTHING to show in three of its cells. It is the case the
    // old table could not express at all, and the one a dash-versus-zero bug
    // hides in: a brand-new enrolment has no actual and no re-level date.
    account_id: "01a00000-0000-7000-8000-0000000000a2",
    account_no: null,
    customer_name: null,
    status: "off_budget",
    level: "260.000000",
    level_override: null,
    level_override_reason: null,
    effective_level: null,
    variance_balance: null,
    currency: "USD",
    settle_up_month: null,
    enrolled_on: "2026-09-01",
    last_leveled_at: null,
    actual_to_date: null,
    actual_months: 0,
    relevel_due_on: null,
    relevel_is_due: null,
    relevel_drift_unavailable: "nothing stores a recomputed level",
  },
];

const RESPONSE: BudgetListResponse = {
  results: ROWS,
  count: 2,
  parameters: { relevel_cadence_months: 6 },
  parameters_unavailable: null,
  statuses: ["enrolled", "off_budget"],
  summary: {
    enrolled: 2,
    accounts_total: 1284,
    accounts_total_unavailable: null,
    shortfall_accounts: 1,
    shortfall_amount: "-212.800000",
    shortfall_currency: "USD",
    shortfall_currencies: ["USD"],
    relevel_due: 1,
    relevel_cadence_months: 6,
    asks_waiting: null,
    asks_waiting_unavailable: "a level-pay ask carries no route, kind or account",
  },
  unavailable: [],
};

/** ⚠ MOUNTED UNDER THE REAL PATH PATTERN (hard-won law 2's fixture clause).
 *  A bare `MemoryRouter` with no `:tenant` leaves every address the page builds
 *  as `//…`, which reads as a perfectly good string to `toContain`. */
function render(response: BudgetListResponse = RESPONSE): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: Infinity } },
  });
  // The key the component builds for its FIRST request: status `enrolled`, no
  // re-level chip, no search, page 1 at the default size. Seeded rather than
  // fetched, so these cases assert over the TABLE and not over a skeleton.
  client.setQueryData(budgetListKey("enrolled|||1|50"), response);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/billing/budget"]}>
            <Routes>
              <Route path="/:tenant/billing/:tab" element={<BudgetBillsTab />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

describe("§05 screen 25 — the Budget Bills table is the table the drawing needs", () => {
  it("TC-B1 · declares the eight drawn columns, in the drawn order", () => {
    const html = render();
    const drawn = [
      t("billing.budget.col.account"),
      t("billing.budget.col.status"),
      t("billing.budget.col.computed"),
      t("billing.budget.col.override"),
      t("billing.budget.col.theyPay"),
      t("billing.budget.col.actualToDate"),
      t("billing.budget.col.variance"),
      t("billing.budget.col.relevel"),
    ];
    let cursor = -1;
    for (const label of drawn) {
      const at = html.indexOf(`>${label}<`, cursor + 1);
      expect(at, `column "${label}" is missing or out of order`).toBeGreaterThan(cursor);
      cursor = at;
    }
  });

  it("TC-B2 · carries a pagination footer (B14 rule 16 · NFR-3)", () => {
    const html = render();
    // The old list rendered every row the server held and had no footer at all,
    // which is correct at 218 accounts and 13x short of the top of the ICP.
    expect(html).toContain(t("table.pager.pageSize"));
  });

  it("TC-B3 · shows the COMPUTED figure beside the override, never instead of it", () => {
    const html = render();
    // BR-BIL-017: the ±30% bound is measured against the computed level, so a
    // clerk typing an override must be able to see the figure it is measured
    // against. 88.00 is computed, 96.00 is the override; both, in one row.
    expect(html).toContain("88.00");
    expect(html).toContain("96.00");
  });

  it("TC-B4 · renders an absent figure as a dash and NEVER as 0.00", () => {
    const html = render();
    // A zero monthly amount is a real, chooseable figure. Printing one where
    // the server said "I could not compute this" tells a clerk the customer
    // pays nothing — which is the defect this rule exists for.
    //
    // ⚠ THE ASSERTION IS PER CELL, NOT A STRING SEARCH. A first draft looked
    // for `"0.00<"` anywhere in the markup and went red on `$260.00`, which is
    // a real figure ending in those characters — a check that cannot tell a
    // pass from a fail is worse than no check (hard-won law 7).
    const offBudget = html.slice(html.indexOf(t("billing.budget.noAccountNo")));
    const cells = [...offBudget.matchAll(/<td[^>]*>(.*?)<\/td>/g)].map((m) => m[1]);
    // OVERRIDE, THEY PAY and VARIANCE are all null on this row: three dashes.
    expect(cells.filter((c) => c.includes('aria-hidden="true">—')).length).toBe(3);
    expect(cells.some((c) => c.includes("$0.00"))).toBe(false);
    // ACTUAL TO DATE says it in words rather than drawing a dash, because
    // "no bill yet" is a fact a clerk can act on.
    expect(html).toContain(t("billing.budget.noActual"));
  });

  it("TC-B5 · never prints a database id as a visible value (B14 rule 31)", () => {
    const html = render();
    const visible = html.replace(/<[^>]*>/g, " ");
    expect(visible).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
    // The row with no account number states the absence in words rather than
    // falling back to the id, which is the breach again one branch on.
    expect(html).toContain(t("billing.budget.noAccountNo"));
  });

  it("TC-B7 · the account number is a door to the account (DEF-BIL-5325)", () => {
    const html = render();
    // BY ADDRESS, not by "there is an <a> somewhere". `DEF-CWP-3925` is what a
    // door asserted any other way costs: eight controls over live screens, and
    // a fixture that could not tell a working link from a broken one.
    expect(html).toContain(`href="/brazosbend/accounts/${ROWS[0].account_id}"`);
    // And the row with NO account number is still a door — the words go in the
    // link, so an account a clerk cannot name is still one they can open.
    expect(html).toContain(`href="/brazosbend/accounts/${ROWS[1].account_id}"`);
    expect(html).toContain(t("billing.budget.noAccountNo"));
    // ⚠ WHAT WOULD MAKE THIS PASS WRONGLY: a `MemoryRouter` with no `:tenant`
    // builds `//accounts/…`, a protocol-relative URL to another host that reads
    // as a fine string to `toContain`. The tenant is pinned into the expected
    // value above for exactly that reason, and `render` mounts the real path.
    expect(html).not.toContain('href="//accounts/');
  });

  it("TC-B8 · a re-level month is written the way the drawing writes it (DEF-BIL-5324)", () => {
    // p121 draws `Jan 2027` in this cell; the screen printed `2027-01`, which
    // is the ISO value sliced rather than a month a clerk reads.
    // ⚠ THE DATE IS THIS CASE'S OWN, NOT THE DRAWING'S (B14 rule 37) — what is
    // asserted is the SHAPE, a named month and a four-digit year.
    const html = render({
      ...RESPONSE,
      count: 1,
      results: [{ ...ROWS[0], relevel_is_due: false, relevel_due_on: "2027-01-04" }],
    });
    expect(html).toContain("Jan 2027");
    // The old rendering, pinned at both ends so a longer string cannot sneak by.
    expect(html).not.toContain(">2027-01<");
    // `formatMonthYear` returns its input verbatim on a value it cannot read;
    // that fallback must not be what made the line above pass.
    expect(html).not.toContain("2027-01-04");
  });

  it("TC-B9 · no override form floats under the table, and the pencil is live (DEF-BIL-5262)", () => {
    const html = render();
    // The screen rendered — an absence assertion over a blank page passes for
    // the wrong reason, so this pins that the table is actually there first.
    expect(html).toContain(t("billing.budget.col.override"));
    // The two boxes that named no account are gone.
    expect(html).not.toContain('id="bil-budget-override"');
    expect(html).not.toContain('id="bil-budget-override-reason"');
    // And the row action is no longer disabled over them. This is the sentence
    // that greyed the pencil on EVERY row until a clerk had typed into a form
    // that belonged to no row — a dead control with a reason that was true
    // only because of where the form was (hard-won law 2's mirror).
    expect(html).not.toContain(t("billing.budget.overrideNeedsReason"));
  });

  it("TC-B10 · the drawn `Settle up the year` door — absent, or pointing at 25.2", () => {
    // p121 draws TWO controls in screen 25's page head: `+ Enrol an account`,
    // which opens entry 25.1, and `Settle up the year →`, which opens entry
    // 25.2. While 25.2 has no front end the door is ABSENT and not greyed —
    // PO 2026-08-27, `CR-043` finding 10: a control we have not built comes OFF
    // the screen. The day 25.2 lands, the door is owed.
    //
    // ⚠ **THIS CASE WAS WRITTEN THE OTHER WAY ROUND AND THE OTHER WAY ROUND WAS
    // WRONG.** It asserted that no settle-up route was declared, so that it
    // would fail when one appeared. Within the hour entry 25.2's lane declared
    // one and named it `BUDGET_FORECAST_ROUTE` — **no `SETTLE` in the
    // identifier** — and the filter sailed straight over it. That is law 7's
    // *structurally incapable of failing*, caught live, on the one case written
    // to prevent exactly this. A test whose whole job is to fire on an event
    // must not depend on what somebody names the event.
    //
    // So it is stated positively instead, and it holds in BOTH worlds without
    // knowing which one it is in.
    const routeNames = Object.keys(billingShared).filter((name) => name.endsWith("_ROUTE"));
    // The convention is asserted too: if this line ever fails, the filter above
    // has stopped being able to see what it is looking for.
    expect(routeNames).toContain("BUDGET_ENROL_ROUTE");
    const forecast = routeNames
      .filter((name) => /SETTLE|FORECAST|TRUE_?UP/i.test(name))
      .map((name) => (billingShared as Record<string, unknown>)[name])
      .filter((value): value is string => typeof value === "string");

    const html = render();
    // The door that IS built, by address — never by its words.
    expect(html).toContain(`href="/brazosbend${billingShared.BUDGET_ENROL_ROUTE}"`);
    if (forecast.length === 0) {
      // Entry 25.2 has no address yet: nothing on this screen may point at one.
      expect(html).not.toContain("settle-up");
      return;
    }
    // Entry 25.2 HAS an address, so screen 25's page head owes it the door
    // p121 draws beside `+ Enrol an account`.
    for (const route of forecast) {
      expect(html).toContain(`href="/brazosbend${route}"`);
    }
  });

  it("TC-B6 · the four KPI tiles are drawn, and the uncountable one says so", () => {
    const html = render();
    for (const key of [
      "billing.budget.kpi.enrolled",
      "billing.budget.kpi.shortfall",
      "billing.budget.kpi.relevel",
      "billing.budget.kpi.asks",
    ]) {
      expect(html).toContain(t(key));
    }
    // ⚠ THE TILE IS DRAWN RATHER THAN DROPPED. The queue is real — a customer
    // can ask for level pay from the portal — and a missing tile would tell a
    // clerk the product forgot about it. It renders the absence instead.
    expect(html).toContain(t("billing.budget.kpi.asksAbsent"));
  });
});
