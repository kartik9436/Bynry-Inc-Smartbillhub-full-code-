// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-003 (global search) — the destination map
// Rules:    BR-SHL-005 AS AMENDED 2026-09-03 (nine groups, per-group View all) ·
//           BR-SHL-011 (the list URL grammar — `q`)
// ───────────────────────────────────────────────────────
//
// **THIS IS WHAT MAKES A SECOND LIST OF PATHS ACCEPTABLE**, and it is the exact
// bargain `sidebarReachability.test.tsx` struck for `sidebarDestinations.ts`:
// the list may exist only because a test holds it to the feature modules' own
// route constants. Move a route and forget `searchDestinations.ts` and this
// suite fails naming the group. "A register that keeps claiming debt it has
// paid off is how a gate stops being a gate" (DEF-077).

import { describe, expect, it } from "vitest";

import { ASSETS_ROUTE } from "@/features/assets/assetsShared";
import { BILLING_ROUTE } from "@/features/billing/billingShared";
import { ACCOUNTS_ROUTE } from "@/features/customers/customersShared";
import { CUSTOMERS_ROUTE } from "@/features/customers/CustomersListPage";
import { SERVICE_REQUESTS_ROUTE } from "@/features/customers/serviceRequestShared";
import { PREMISES_ROUTE, UNITS_ROUTE } from "@/features/metering/meteringShared";
import { PAYMENTS_ROUTE } from "@/features/payments/paymentsShared";
import { PLANS_RATES_ROUTE } from "@/features/rating/ratingShared";
import {
  WORK_CREWS_ROUTE,
  WORK_ORDERS_ROUTE,
  WORK_ORDER_TEMPLATES_ROUTE,
  WORK_PARTS_ROUTE,
} from "@/features/work/WorkShell";

import { SEARCH_DESTINATIONS, resultPath, viewAllPath } from "./searchDestinations";

describe("US-SHL-003 — where each search group goes", () => {
  it("names all FIFTEEN groups and no more", () => {
    // BR-SHL-005 as amended. The 2026-09-03 ruling's headline says "eight" and
    // its own enumeration lists nine (DEF-3460); the enumeration is the
    // content, and the server's `GROUP_ORDER` is the arbiter. CR-073 took it
    // to fifteen on 2026-09-05. A group with no destination would render rows
    // that link nowhere.
    expect(Object.keys(SEARCH_DESTINATIONS)).toHaveLength(15);
  });

  it.each([
    ["premises", PREMISES_ROUTE],
    ["units", UNITS_ROUTE],
    ["assets", ASSETS_ROUTE],
    ["master_accounts", ACCOUNTS_ROUTE],
    ["accounts", ACCOUNTS_ROUTE],
    ["customers", CUSTOMERS_ROUTE],
    ["bills", BILLING_ROUTE],
    ["payments", PAYMENTS_ROUTE],
    ["requests", SERVICE_REQUESTS_ROUTE],
    // CR-073. ⚠ The Work constants carry NO `/:tenant` — `App.tsx` adds it —
    // and this pin is what stops these two lists drifting apart again
    // (DEF-WRK-4051 made two shipped screens unreachable for three commits).
    ["work_orders", WORK_ORDERS_ROUTE],
    ["work_order_templates", WORK_ORDER_TEMPLATES_ROUTE],
    ["parts", WORK_PARTS_ROUTE],
    ["workforce", WORK_CREWS_ROUTE],
    ["plans", `${PLANS_RATES_ROUTE}/plans`],
    ["charges", `${PLANS_RATES_ROUTE}/charge-codes`],
  ] as const)("%s's list is the feature module's own route constant", (entity, route) => {
    expect(SEARCH_DESTINATIONS[entity].list).toBe(route);
  });

  it("View all applies the query as BR-SHL-011's `q`, encoded", () => {
    expect(viewAllPath("accounts", "A-104")).toBe("/accounts?q=A-104");
    // A query is free text a person typed — it can hold anything.
    expect(viewAllPath("premises", "118 Cedar & Ridge")).toBe(
      "/premises?q=118%20Cedar%20%26%20Ridge",
    );
  });

  it("a bill opens /billing/bills/{id}, NOT /billing/{id}", () => {
    // `/billing/:tab` is the bills screen's tab route, so a uuid in that
    // position resolves as a tab name and the bill never opens.
    expect(resultPath("bills", "abc-123", "BL-2608")).toBe("/billing/bills/abc-123");
  });

  it("a group with no detail screen opens its list filtered to that row", () => {
    // Payments and customers have no `/{id}` route in this product. The row is
    // still not a dead click: it lands on the list showing that one record.
    // ⚠ The filter is the LABEL (the identifier), never the id — B14 rule 31.
    expect(resultPath("payments", "abc-123", "PMT-88213")).toBe("/payments?q=PMT-88213");
    expect(resultPath("customers", "abc-123", "C-5500")).toBe("/customers?q=C-5500");
    expect(resultPath("payments", "abc-123", "PMT-88213")).not.toContain("abc-123");
  });

  it("every other group opens the record itself", () => {
    expect(resultPath("accounts", "id-1", "A-10432")).toBe("/accounts/id-1");
    expect(resultPath("master_accounts", "id-2", "A-10999")).toBe("/accounts/id-2");
    expect(resultPath("premises", "id-3", "P-2001")).toBe("/premises/id-3");
    expect(resultPath("units", "id-4", "U-3001")).toBe("/premises/units/id-4");
    expect(resultPath("assets", "id-5", "MTR-4400")).toBe("/assets/id-5");
    expect(resultPath("requests", "id-6", "SR-26-0046")).toBe("/requests/id-6");
  });

  it("CR-073's six new groups open the right thing, or the right list", () => {
    // A job and a template open the record. `App.tsx` addresses both by uuid —
    // the frontend route param is spelled `:orderNo`, which is a NAME and not
    // a promise: `OrdersPage` builds the link from `row.id`.
    expect(resultPath("work_orders", "id-7", "WO-0011")).toBe("/work/orders/id-7");
    expect(resultPath("work_order_templates", "id-8", "Meter set")).toBe("/work/templates/id-8");
    expect(resultPath("plans", "id-9", "RES-W")).toBe("/plans-rates/plans/id-9");
    expect(resultPath("charges", "id-10", "LATE-FEE")).toBe("/plans-rates/charge-codes/id-10");

    // Parts and workforce have no detail address to open, so they land on the
    // list FILTERED TO THAT ROW — never a route that does not resolve.
    expect(resultPath("parts", "id-11", "MTR-W58")).toBe("/work/parts?q=MTR-W58");
    expect(resultPath("workforce", "id-12", "R. Patel")).toBe("/work/crews?q=R.%20Patel");
    // ⚠ B14 rule 31 — the filter is the LABEL, never the id.
    expect(resultPath("parts", "id-11", "MTR-W58")).not.toContain("id-11");
    expect(resultPath("workforce", "id-12", "R. Patel")).not.toContain("id-12");
  });

  it("DEF-WRK-4094 — every `?q=` destination is a screen that PARSES `?q=`", () => {
    // ⚠ **THE PIN THAT WOULD HAVE CAUGHT DEF-WRK-4094.** Four Work lists held
    // their table state locally and never read the query string, so every link
    // built here promised a filter and delivered a full list — `tsc` green,
    // route resolving, screen rendering. Nothing asked whether the DESTINATION
    // honours the grammar the SOURCE writes. This does.
    const parsesQuery = new Map<string, string>([
      ["/work/orders", "OrdersPage.tsx"],
      ["/work/templates", "TemplatesPage.tsx"],
      ["/work/parts", "PartsPage.tsx"],
      ["/work/crews", "CrewsPage.tsx"],
    ]);
    const modules = import.meta.glob("../features/work/*.tsx", {
      eager: true,
      query: "?raw",
      import: "default",
    }) as Record<string, string>;

    for (const [list, file] of parsesQuery) {
      expect(Object.values(SEARCH_DESTINATIONS).some((d) => d.list === list)).toBe(true);
      const source = Object.entries(modules).find(([path]) => path.endsWith(file))?.[1];
      expect(source, `${file} was not found — the pin is measuring nothing`).toBeTruthy();
      // ⚠ **THE CALL, NOT THE WORD.** The first draft asked whether the file
      // CONTAINED "seedQueryFromUrl" — and the sabotage passed it, because the
      // comment explaining the fix names the helper in prose. A guard whose
      // evidence cannot distinguish pass from fail is worse than none; this is
      // the second time that exact shape bit this change (see the backend's
      // tenant-filter case), which is why it is written down in both places.
      const reads = /\b(seedQueryFromUrl|parseTableParams)\s*\(/.test(source ?? "");
      expect(
        reads,
        `${file} is a "View all" destination but never reads ?q= from the URL (DEF-WRK-4094)`,
      ).toBe(true);
    }
  });
});
