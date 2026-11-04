// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  DEF-CUS-7618 (2026-09-28) — `WorkOrdersTab` grew a THIRD host,
//          `build`, so the build detail page could compose it instead of
//          hand-rolling a second work-orders table (`CR-151-BRC09` §2 rule
//          (2), B14 rule 43).
// Rules:   CLAUDE.md hard-won law 2's mirror (a cell that refuses when it need
//          not) · law 7 habit 2 (*what would make this check pass wrongly?*) ·
//          B14 rule 20 (one table type) · rule 31
// Tests:   this file IS the test. `buildViews.test.tsx` and
//          `buildViewsWorkOrders.dom.test.tsx` own the other two hosts and are
//          unchanged by that widening; this file pins them anyway, because a
//          widening that quietly moved them is the only way it could be wrong.
// ───────────────────────────────────────────────────────
//
// WHAT WOULD MAKE THIS PASS WRONGLY (law 7, habit 2)
// --------------------------------------------------
// * **Asserting only the BUILD host.** Every build-only difference in
//   `WorkOrdersTab` is a branch on one flag, and a branch written the wrong
//   way round moves the property and the account instead. So the first
//   describe below is about the two hosts this change was NOT allowed to
//   touch, and it names the four things the widening could have moved:
//   the column heads, the holder cell's hook, the raise button and the
//   closing note.
// * **Reading the crew cell for a NAME and stopping there.** A cell that
//   printed the holder in both columns would pass that. Each case below reads
//   BOTH cells of the SAME row, one for the name and one for the stated
//   absence, so a cell that filled both goes red.
// * **Mounting the component bare.** `DEF-CWP-3925`: with no matching route
//   `useParams()` is undefined and every address the component builds comes
//   out `//…`, which reads as a good string. Every mount below is under the
//   real path pattern for its host.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { WorkOrdersTab, scopedOrdersQueryKey } from "./buildViews";
import type { ScopedWorkOrderList, ScopedWorkOrderRow } from "./workEndpoints";

const TENANT = "brazosbend";
const PREMISES = "prm-2209";
const ACCOUNT = "acc-3310";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function order(over: Partial<ScopedWorkOrderRow> = {}): ScopedWorkOrderRow {
  return {
    id: "wo-a",
    order_no: "WO-9001",
    type: "Meter set",
    premise: { id: PREMISES, premise_no: "P-02209", address: "44 Cedar Court" },
    service: "water",
    state: "planned",
    outcome: null,
    mode: "our_crew",
    is_gate: false,
    connection: null,
    account: null,
    raised_at: "2026-09-12T10:31:00Z",
    stands_on: "build",
    scope: "per_unit",
    unit_label: "1",
    external_ref: null,
    completed_at: null,
    accepted_at: null,
    accepted_by: null,
    field_data: null,
    technician: null,
    window_start: null,
    window_end: null,
    due_at: null,
    ...over,
  };
}

const HELD_BY_CREW = order({
  id: "wo-a",
  order_no: "WO-9001",
  technician: { kind: "crew", name: "Meter crew", slug: "meter-crew" },
});
const HELD_BY_PERSON = order({
  id: "wo-b",
  order_no: "WO-9002",
  type: "Fire marshal inspection",
  service: "fire",
  technician: { kind: "person", name: "Ray Alvarez", slug: "ray-alvarez" },
});
const ANOTHER_BUILDS = order({
  id: "wo-z",
  order_no: "WO-9404",
  type: "Meter exchange",
  stands_on: "asset",
});

function payload(rows: ScopedWorkOrderRow[]): ScopedWorkOrderList {
  return { count: rows.length, next: null, previous: null, results: rows };
}

/** The host that the widening MUST NOT have moved, mounted as it is today. */
function mountPremises(rows: ScopedWorkOrderRow[]): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(scopedOrdersQueryKey("premises", PREMISES), payload(rows));
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TENANT}/premises/${PREMISES}?tab=work-orders`]}>
        <Routes>
          <Route
            path="/:tenant/premises/:premisesId"
            element={
              <WorkOrdersTab
                host="premises"
                hostId={PREMISES}
                t={t}
                timeZone="America/Chicago"
                dateFormat="MM/DD/YYYY"
                openOrderId={null}
                onOpenOrder={() => undefined}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mountAccount(rows: ScopedWorkOrderRow[]): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(scopedOrdersQueryKey("account", ACCOUNT), payload(rows));
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TENANT}/accounts/${ACCOUNT}?tab=work-orders`]}>
        <Routes>
          <Route
            path="/:tenant/accounts/:accountId"
            element={
              <WorkOrdersTab
                host="account"
                hostId={ACCOUNT}
                t={t}
                timeZone="America/Chicago"
                dateFormat="MM/DD/YYYY"
                openOrderId={null}
                onOpenOrder={() => undefined}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * The BUILD host, mounted at the build's own address and reading the PREMISES
 * cache — which is the whole of what the third host is: one shared read,
 * narrowed by the ids the build's own read names.
 */
function mountBuild(rows: ScopedWorkOrderRow[], only: string[]): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(scopedOrdersQueryKey("premises", PREMISES), payload(rows));
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TENANT}/connections/bld-1?tab=work`]}>
        <Routes>
          <Route
            path="/:tenant/connections/:connectionId"
            element={
              <WorkOrdersTab
                host="build"
                hostId={PREMISES}
                onlyOrderIds={only}
                t={t}
                timeZone="America/Chicago"
                dateFormat="MM/DD/YYYY"
                openOrderId={null}
                onOpenOrder={() => undefined}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function heads(): string[] {
  return Array.from(document.querySelectorAll("table thead th")).map((th) =>
    (th.textContent ?? "").replace(/[▲▼]/g, "").trim(),
  );
}

describe("the two hosts the third one was not allowed to move", () => {
  // ⚠ Every one of these is a thing the build branch could have leaked into.
  it("the PROPERTY draws its own seven heads, its one holder cell, its button and its note", () => {
    mountPremises([HELD_BY_CREW]);
    // `P8`'s set, unchanged: no SERVICE column and no TECHNICIAN column.
    expect(heads()).toEqual([
      "Work",
      "What",
      "Where",
      "Crew",
      "Booked",
      "Status",
      "Actions",
    ]);
    // ONE holder cell, under its own hook — the build's two cells must not
    // appear here.
    expect(document.querySelectorAll("[data-order-who]")).toHaveLength(1);
    expect(document.querySelector("[data-order-crew]")).toBeNull();
    expect(document.querySelector("[data-order-technician]")).toBeNull();
    // The crew NAME, plain, with no stated absence beside it.
    const who = document.querySelector("[data-order-who]") as HTMLElement;
    expect(who.textContent).toContain("Meter crew");
    expect(who.querySelector("[data-absent]")).toBeNull();
    // Its own `⚡ Raise work here` button above the table, and its closing note.
    expect(document.body.textContent).toContain("Raise work here");
    expect(document.body.textContent).toContain(t("work.orders.atPlace.notes"));
  });

  it("the ACCOUNT draws its own heads, its fixed-sort line, and neither of the build's cells", () => {
    mountAccount([HELD_BY_CREW]);
    expect(heads()).toEqual([
      "Order #",
      "Type",
      "Priority",
      "Technician",
      "Due",
      "Status",
      "Raised by",
      "Actions",
    ]);
    expect(document.querySelectorAll("[data-order-who]")).toHaveLength(1);
    expect(document.querySelector("[data-order-crew]")).toBeNull();
    // `ACC-T08`'s footer sentence, and the census hook the render check reads.
    expect(document.querySelector("[data-order-sort]")).not.toBeNull();
    expect(document.querySelector("[data-account-overview]")).not.toBeNull();
  });
});

describe("the BUILD host — `03-work.png`, composed rather than copied", () => {
  it("draws the drawn eight, in the drawn order, with the row action last", () => {
    mountBuild([HELD_BY_CREW, HELD_BY_PERSON], ["wo-a", "wo-b"]);
    expect(heads()).toEqual([
      "Order",
      "What",
      "Service",
      "Unit",
      "Crew",
      "Technician",
      "Target",
      "State",
      "Actions",
    ]);
  });

  it("splits the ONE served holder across the two cells, each way round", () => {
    mountBuild([HELD_BY_CREW, HELD_BY_PERSON], ["wo-a", "wo-b"]);
    const crewOf = (no: string) =>
      document.querySelector(`[data-order-crew="${no}"]`) as HTMLElement;
    const techOf = (no: string) =>
      document.querySelector(`[data-order-technician="${no}"]`) as HTMLElement;

    // A CREW holds WO-9001.
    expect(crewOf("WO-9001").textContent).toContain("Meter crew");
    expect(techOf("WO-9001").querySelector("[data-absent]")).not.toBeNull();
    expect(techOf("WO-9001").textContent).not.toContain("Meter crew");

    // A PERSON holds WO-9002 — the mirror image, and the cell that names the
    // person must not also name it as a crew.
    expect(techOf("WO-9002").textContent).toContain("Ray Alvarez");
    expect(crewOf("WO-9002").querySelector("[data-absent]")).not.toBeNull();
    expect(crewOf("WO-9002").textContent).not.toContain("Ray Alvarez");
  });

  it("says NOBODY in both cells when nobody holds the job, and invents neither", () => {
    mountBuild([order({ id: "wo-c", order_no: "WO-9003" })], ["wo-c"]);
    const crew = document.querySelector('[data-order-crew="WO-9003"]') as HTMLElement;
    const tech = document.querySelector('[data-order-technician="WO-9003"]') as HTMLElement;
    expect(crew.querySelector("[data-absent]")).not.toBeNull();
    expect(tech.querySelector("[data-absent]")).not.toBeNull();
  });

  it("keeps only the ids the build's own read names, though the route answers the address", () => {
    mountBuild([HELD_BY_CREW, HELD_BY_PERSON, ANOTHER_BUILDS], ["wo-a", "wo-b"]);
    const drawn = Array.from(document.querySelectorAll("[data-order-row]")).map((el) =>
      el.getAttribute("data-order-row"),
    );
    expect([...drawn].sort()).toEqual(["WO-9001", "WO-9002"]);
    expect(drawn).not.toContain("WO-9404");
  });

  it("arrives unfiltered, so a finished job is on screen without pressing anything", () => {
    // The property arrives on the `OPEN` chip; the build must not, or three of
    // `03-work.png`'s four rows would be hidden under a strip that counts them.
    mountBuild(
      [order({ id: "wo-d", order_no: "WO-9004", state: "completed", completed_at: "2026-10-02T09:00:00Z" })],
      ["wo-d"],
    );
    expect(document.querySelector('[data-order-row="WO-9004"]')).not.toBeNull();
  });

  it("draws neither the property's raise button nor its closing note", () => {
    mountBuild([HELD_BY_CREW], ["wo-a"]);
    // The page header already carries `Raise order`; two doors to one act on
    // one screen is what the PO took off this page's header on 2026-09-28.
    expect(document.body.textContent).not.toContain("Raise work here");
    // *"Every job here, finished ones included, newest first"* is false of a
    // build's tab in two of its three clauses (hard-won law 1).
    expect(document.body.textContent).not.toContain(t("work.orders.atPlace.notes"));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7618 · CR-151-BRC09 §2 rule (2) · `03-work.png` (B14 rule 42)
// generated: 2026-09-28 by the DEF-CUS-7618 lane
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: proved RED before it was trusted green, TWICE, each on a different
//   half of the file, and each break was reverted and the file proved
//   byte-identical to its pre-break copy afterwards:
//     * declaring `technicianColumn` on EVERY host instead of only on `build`
//       → 2 failed, 6 passed — the PROPERTY's head list and the ACCOUNT's, the
//       two this widening was not allowed to move;
//     * collapsing the crew cell's `onBuild` branch so the build host falls
//       through to the single-holder cell → 2 failed, 6 passed — the two cases
//       that read BOTH cells of one row.
//   The narrowing is proved red in `BuildDetailTabs.dom.test.tsx` instead,
//   where it belongs: dropping `onlyOrderIds` in `BuildWorkTab` put another
//   build's `WO-26-0411` on the tab and that file's case named it.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
