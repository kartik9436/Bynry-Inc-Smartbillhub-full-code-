// ── Trace ──────────────────────────────────────────────
// Ruling:  decision log 2026-10-19 "Record links (navigation design)" — wherever
//          a record is shown as text and a detail page exists, the text is a
//          link to it. Customer ID stays PLAIN TEXT (no customer page yet).
// Lane:    RL-A (record links, job A). Job B owns `recordLinksJobB`.
//
// THE SAFETY NET FOR EVERY SCREEN/RECORD PAIR LANE RL-A LINKED.
//
// Two layers, and each says what it can and cannot see:
//
//  1. RENDERED — every pair is asserted by HREF in a per-screen suite mounted
//     under its real `/:tenant/…` path (hard-won law 2's fixture clause). The
//     table below names that suite and the exact href string it asserts, and
//     this file FAILS if the suite no longer carries that assertion — so a
//     revert to text cannot pass by deleting the case that would have caught it.
//     The rate schedule's Plans tab had no suite to extend and is rendered here.
//
//  2. SOURCE — the screen file still composes the link for that record (the
//     helper call inside a `to=`). This is a weaker check on its own (it reads
//     code, not output) and exists only so the table cannot drift from the
//     code; layer 1 is the guarantee.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import "@/i18n";
import { createApiClient } from "@/api/client";
import type { SchedulePlanRow } from "@/api/rateScheduleReads";
import { RecordLink } from "@/components/RecordLink";
import { RatePlansTab } from "@/features/rating/rateScheduleViewTabs";

// Node's own modules through the string-split import `buttonKit.test.ts` uses: a
// bare `import … from "node:fs"` passes vitest and fails `tsc`, which carries no
// @types/node for `src/`.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(u: URL): string;
};
const SRC = nodeUrl.fileURLToPath(new URL("../", import.meta.url));
const read = (path: string): string => nodeFs.readFileSync(`${SRC}${path}`, "utf8");

interface Pair {
  screen: string;
  record: string;
  /** The screen's source file, relative to `src/`. */
  file: string;
  /** What the file must still compose — the helper call that addresses it. */
  composes: string;
  /** The per-screen suite (relative to `src/`) that renders it … */
  suite: string;
  /** … and the href string that suite asserts. */
  href: string;
}

const PAIRS: Pair[] = [
  // Account page — Overview (S21)
  { screen: "Account · Overview", record: "unit", file: "features/customers/AccountDetailPage.tsx", composes: "unitDetailPath(detail.unit_id)", suite: "features/customers/AccountDetailPage.test.tsx", href: "/premises/units/u-10432a" },
  { screen: "Account · Overview", record: "premises", file: "features/customers/AccountDetailPage.tsx", composes: "premisesDetailPath(detail.service_premises_id)", suite: "features/customers/AccountDetailPage.test.tsx", href: "/premises/prm-1408" },
  { screen: "Account · Overview", record: "meter (asset)", file: "features/customers/AccountDetailPage.tsx", composes: "assetDetailPath(meter.id)", suite: "features/customers/AccountDetailPage.test.tsx", href: "/assets/ast-4021" },
  { screen: "Account · Overview", record: "linked account", file: "features/customers/AccountDetailPage.tsx", composes: "accountDetailPath(linked.id)", suite: "features/customers/AccountDetailPage.test.tsx", href: "/accounts/acc-10433" },
  // Accounts list (S17) and Customers list
  { screen: "Accounts list", record: "unit", file: "features/customers/AccountsListPage.tsx", composes: "unitDetailPath(row.unit_id)", suite: "features/customers/AccountsPage.test.tsx", href: "/premises/units/u-10432a" },
  { screen: "Accounts list", record: "premises (master)", file: "features/customers/AccountsListPage.tsx", composes: "premisesDetailPath(row.premises_id)", suite: "features/customers/AccountsPage.test.tsx", href: "/premises/prm-1408" },
  { screen: "Customers list · expanded", record: "account", file: "features/customers/CustomersListPage.tsx", composes: "accountDetailPath(entry.id)", suite: "features/customers/CustomersListPage.test.tsx", href: "/acme/accounts/acct-1" },
  // Job queue (Accounts → Complaints / Services)
  { screen: "Job queue", record: "work order", file: "features/customers/JobQueueTab.tsx", composes: "workOrderDetailPath(\"\", row.id)", suite: "features/customers/JobIntake.test.tsx", href: "/work/orders/wo-0412" },
  { screen: "Job queue", record: "account", file: "features/customers/JobQueueTab.tsx", composes: "accountDetailPath(row.account.id)", suite: "features/customers/JobIntake.test.tsx", href: "/accounts/acc-1" },
  // Work
  { screen: "Work order · Overview", record: "meter (asset)", file: "features/work/orderPage/OrderOverview.tsx", composes: "assetDetailPath(asset.id)", suite: "features/work/orderPage/orderPage.dom.test.tsx", href: "/assets/a-1" },
  { screen: "Work order · Overview", record: "premises", file: "features/work/orderPage/OrderOverview.tsx", composes: "premisesDetailPath(premisesId)", suite: "features/work/orderPage/orderPage.dom.test.tsx", href: "/premises/p-1" },
  { screen: "Work order · Overview", record: "unit", file: "features/work/orderPage/OrderOverview.tsx", composes: "unitDetailPath(unit.id)", suite: "features/work/orderPage/orderPage.dom.test.tsx", href: "/premises/units/u-1" },
  { screen: "Work order · Overview", record: "account", file: "features/work/orderPage/OrderOverview.tsx", composes: "accountDetailPath(accountId)", suite: "features/work/orderPage/orderPage.dom.test.tsx", href: "/accounts/a-1" },
  { screen: "Work orders list", record: "account", file: "features/work/OrdersPage.tsx", composes: "accountDetailPath(row.account.id)", suite: "features/work/OrdersPage.test.tsx", href: "/accounts/a-10891" },
  { screen: "Work orders tab (account/premises/build)", record: "work order", file: "features/work/buildViews.tsx", composes: "workOrderDetailPath(\"\", row.id)", suite: "features/work/buildViewsWorkOrders.dom.test.tsx", href: "/work/orders/wo-4822" },
  { screen: "Send someone out · outcome", record: "work order", file: "features/metering/SendSomeoneOutModal.tsx", composes: "encodeURIComponent(order.order_no)", suite: "features/metering/SendSomeoneOutModal.test.tsx", href: "/brazosbend/work/orders/WO-26-0117" },
  // Assets
  { screen: "Asset registry", record: "parent asset", file: "features/assets/AssetRegistryPage.tsx", composes: "assetDetailPath(row.parent_asset_id)", suite: "features/assets/AssetRegistry.test.tsx", href: "/assets/a-master-12" },
  { screen: "Asset registry (BTM)", record: "unit", file: "features/assets/AssetRegistryPage.tsx", composes: "unitDetailPath(row.assigned_unit_id)", suite: "features/assets/AssetRegistry.test.tsx", href: "/premises/units/u-1200" },
  // Meter reads
  { screen: "Meter reads list", record: "cycle", file: "features/metering/ReadsListPage.tsx", composes: "readCycleDetailPath(row.cycle_id)", suite: "features/metering/ReadsPage.test.tsx", href: "/reads/cycles/c-08a" },
  { screen: "Meter reads list", record: "route", file: "features/metering/ReadsListPage.tsx", composes: "routeReadsPath(row.route_id)", suite: "features/metering/ReadsPage.test.tsx", href: "/reads/routes/rt-1" },
  { screen: "Meter reads list", record: "premises", file: "features/metering/ReadsListPage.tsx", composes: "premisesDetailPath(row.premises_id)", suite: "features/metering/ReadsPage.test.tsx", href: "/premises/p-1408" },
  { screen: "Meter reads list", record: "unit", file: "features/metering/ReadsListPage.tsx", composes: "unitDetailPath(row.unit_id)", suite: "features/metering/ReadsPage.test.tsx", href: "/premises/units/u-1408a" },
  // Unit page and rate schedule → plan
  { screen: "Unit page", record: "plan", file: "features/metering/UnitDetailPage.tsx", composes: "planDetailRoute(props.planId)", suite: "features/metering/UnitPlanIdNeverShows.dom.test.tsx", href: "/plans-rates/plans/" },
  { screen: "Rate schedule · Plans", record: "plan", file: "features/rating/rateScheduleViewTabs.tsx", composes: "planDetailRoute(row.plan_id)", suite: "test/recordLinksJobA.test.tsx", href: "/acme/plans-rates/plans/pln-res" },
  // Settings → Routes & cycles
  { screen: "Route · Units", record: "unit", file: "features/tenancy/RouteDetailPage.tsx", composes: "unitDetailPath(member.unit_id)", suite: "features/tenancy/RoutesCyclesDetail.test.tsx", href: "/acme/premises/units/u4" },
  { screen: "Route · Assets", record: "meter (asset)", file: "features/tenancy/RouteDetailPage.tsx", composes: "assetDetailPath(meter.id)", suite: "features/tenancy/RoutesCyclesDetail.test.tsx", href: "/acme/assets/m1" },
  { screen: "Route · Accounts", record: "account", file: "features/tenancy/RouteDetailPage.tsx", composes: "accountDetailPath(row.account_id)", suite: "features/tenancy/RoutesCyclesDetail.test.tsx", href: "/acme/accounts/a1" },
  { screen: "Cycle · Coverage", record: "unit", file: "features/tenancy/CycleDetailPage.tsx", composes: "unitDetailPath(row.unit_id)", suite: "features/tenancy/RoutesCyclesDetail.test.tsx", href: "/acme/premises/units/u9" },
];

describe("record links, lane RL-A — every pair is still a link", () => {
  it.each(PAIRS.map((pair) => [`${pair.screen} → ${pair.record}`, pair] as const))(
    "%s",
    (_label, pair) => {
      const source = read(pair.file);
      expect(source, `${pair.file} no longer composes ${pair.composes}`).toContain(pair.composes);
      const suite = read(pair.suite);
      expect(suite.toLowerCase(), `${pair.suite} lost its record-links case`).toContain("record links");
      expect(suite, `${pair.suite} no longer asserts ${pair.href}`).toContain(pair.href);
    },
  );

  it("Customer ID stays plain text — no customer page exists, so nothing links it", () => {
    const source = read("features/customers/AccountDetailPage.tsx");
    const start = source.indexOf('t("customers.account.field.customerId")');
    const fact = source.slice(start, source.indexOf("</Fact>", start));
    expect(fact).toContain("detail.customer_no");
    expect(fact).not.toContain("InlineLinkTo");
    expect(fact).not.toContain("RecordLink");
  });
});

describe("RecordLink — the one fallback", () => {
  it("links when the id is served and draws the same words unlinked when it is not", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <RecordLink to="/acme/assets/a-1">M-1</RecordLink>
        <RecordLink to={null}>M-2</RecordLink>
      </MemoryRouter>,
    );
    expect(html).toContain('href="/acme/assets/a-1"');
    expect(html).toContain(">M-1</a>");
    expect(html).toContain("M-2");
    expect(html).not.toContain(">M-2</a>");
  });
});

describe("record links — the rate schedule's Plans tab", () => {
  it("each plan using the schedule opens the plan", () => {
    const row: SchedulePlanRow = {
      plan_id: "pln-res",
      plan_name: "Residential Standard",
      plan_code: "RES",
      customer_classes: [],
      class_differs: false,
      status: "published",
      units: 12,
    };
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["rate-schedules", "plans", "rs-1", 1, 50], {
      count: 1,
      next: null,
      previous: null,
      results: [row],
    });
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/acme/plans-rates/rate-schedules/rs-1?tab=plans"]}>
          <Routes>
            <Route
              path="/:tenant/plans-rates/rate-schedules/:tariffId"
              element={
                <RatePlansTab
                  detail={{ id: "rs-1" } as never}
                  client={createApiClient({ tenant: "acme" })}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(html).toContain('href="/acme/plans-rates/plans/pln-res"');
    expect(html).toContain(">Residential Standard</a>");
  });
});
