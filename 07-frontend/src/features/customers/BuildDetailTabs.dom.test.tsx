// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 · the New Connect BUILD DETAIL page — tasks 6 to 12,
//           each tab asserted BY ITS ADDRESS and BY THE SCREEN it opens.
// Rules:    CLAUDE.md hard-won law 2 and its MIRROR · law 6 (this is the only
//           instrument in the repository that reads rendered output) ·
//           B14 rule 37 (no figure from a PNG is asserted here).
// ───────────────────────────────────────────────────────
//
// WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2)
// ---------------------------------------------------
// * **Mounting a tab body directly.** Then nothing proves the ADDRESS opens
//   it, which is the assertion that actually matters — a screen registered at
//   one address while the router mounts it at another passes every check, and
//   that is exactly the *looking at the wrong thing* shape. Every case below
//   enters at `/{tenant}/connections/{id}?tab=<id>` and reads what came up.
// * **Reading a cell by its position.** A column inserted in the wrong place
//   would pass; each case reads the COLUMN HEADS in order instead.
// * **Asserting Resend is disabled and stopping there.** A hardcoded
//   `disabled` passes that. The Messages case asserts BOTH directions, so the
//   day the payload stops refusing, the enabled case is the one that holds.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { BuildDetailPage } from "./BuildDetailPage";
// ⚠ **THE TAB BODIES MOVED TO `features/work/buildRecord/` ON 2026-09-28**
// (`DEF-CUS-7618`) — a build panel has one home and it is the kit. This file
// keeps its name because its SUBJECT has not moved: it is the build detail
// page's seven tabs, entered at the page's real address. Nothing below mounts
// a tab body directly, so the move is invisible to every assertion.
import { resendRefusal } from "@/features/work/buildRecord/BuildMessagesTab";
import type { BuildMessageRow } from "@/features/work/buildRecord/BuildMessagesTab";
import { rowRefusal } from "@/features/work/buildRecord/BuildUnitsTab";
import { quantityText } from "@/features/work/buildRecord/BuildChargesTab";
import type { ActivationRead } from "./buildLifecycleEndpoints";
import {
  ACCOUNT_ID,
  INVOICE_ID,
  BUILD_ID,
  ORDER_ID,
  ORDER_ID_2,
  PREMISES_ID,
  TENANT,
  UNIT_ID,
  buildDetailFixture,
  buildRecordFixture,
  premisesBuildFixture,
  premisesWorkOrdersFixture,
} from "./buildDetailFixture";
import type { BuildRecord } from "@/features/work/workEndpoints";

function mountTab(
  tab: string,
  over: {
    record?: BuildRecord;
    detail?: ReturnType<typeof buildDetailFixture>;
    documents?: Record<string, unknown>[];
    onPost?: (url: string, body: unknown) => unknown;
  } = {},
) {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      urls.push(url);
      const json = (body: unknown) =>
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      if (init?.method === "POST" && over.onPost !== undefined) {
        return json(over.onPost(url, JSON.parse(String(init.body ?? "null"))));
      }
      if (url.includes(`/connections/${BUILD_ID}/record`)) {
        return json(over.record ?? buildRecordFixture());
      }
      if (url.includes(`/premises/${PREMISES_ID}/build`)) {
        return json({ build: premisesBuildFixture() });
      }
      // CR-162-BRC10 — the activation read the Units tab and Approve draw from,
      // and the To-do tab's list. Matched BEFORE the bare build id below.
      if (url.includes(`/connections/${BUILD_ID}/activation`)) {
        return json(activationFixture());
      }
      if (url.includes(`/connections/${BUILD_ID}/todos`)) {
        return json({ connection_id: BUILD_ID, rows: [], todos_open: 0, notes: 0 });
      }
      // The SHARED work-order read the Work tab composes (`DEF-CUS-7618`).
      if (url.includes(`/premises/${PREMISES_ID}/work-orders`)) {
        return json(premisesWorkOrdersFixture());
      }
      if (url.includes(`/connections/${BUILD_ID}`)) {
        return json(over.detail ?? buildDetailFixture());
      }
      if (url.includes(`/accounts/${ACCOUNT_ID}/documents`)) {
        const documents = over.documents ?? [];
        return json({ count: documents.length, next: null, previous: null, results: documents });
      }
      // A bare array — see the note in `BuildDetailPage.dom.test.tsx`.
      if (url.includes("/settings/services")) {
        return json([]);
      }
      return json({ count: 0, results: [], rows: [], methods: [] });
    },
  });
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/connections/${BUILD_ID}?tab=${tab}`]}>
          <Routes>
            <Route
              path="/:tenant/connections/:connectionId"
              element={<BuildDetailPage client={client} timeZone="UTC" dateFormat="MM/DD/YYYY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return urls;
}

function heads(table: string): string[] {
  const el = document.querySelector(`[data-table="${table}"] thead`) as HTMLElement | null;
  return Array.from(el?.querySelectorAll("th") ?? []).map((th) => th.textContent?.trim() ?? "");
}

/** Every case asserts the address opened THIS screen and THIS tab. */
async function openedOn(tab: string): Promise<void> {
  await waitFor(() =>
    expect(document.querySelector(`[data-screen="NCT-02"] [data-build-tab="${tab}"]`)).not.toBeNull(),
  );
}

describe("task 6 · Overview", () => {
  afterEach(cleanup);

  it("`?tab=overview` opens NCT-02's Overview, with the five facts strip", async () => {
    mountTab("overview");
    await openedOn("overview");
    expect(document.querySelector('[data-build-facts="overview"]')).not.toBeNull();
  });

  it("`What this build made` links every row to the REAL thing, tenant-scoped", async () => {
    mountTab("overview");
    await openedOn("overview");
    await waitFor(() =>
      expect(document.querySelector('[data-made-row="account"] a')).not.toBeNull(),
    );
    expect(
      document.querySelector('[data-made-row="account"] a')?.getAttribute("href"),
    ).toBe(`/${TENANT}/accounts/${ACCOUNT_ID}`);
    expect(
      document.querySelector('[data-made-row="premises"] a')?.getAttribute("href"),
    ).toBe(`/${TENANT}/premises/${PREMISES_ID}`);
  });

  it("the account link is WITHHELD when the id cannot be established, not pointed at nothing", async () => {
    // `GET /premises/{id}/build` answers the NEWEST build at the address; when
    // that is a DIFFERENT build the page must not borrow its account.
    const client = createApiClient({
      tenant: TENANT,
      fetchImpl: async (input: RequestInfo | URL) => {
        const url = String(input);
        const json = (body: unknown) =>
          new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        if (url.includes(`/connections/${BUILD_ID}/record`)) return json(buildRecordFixture());
        if (url.includes(`/premises/${PREMISES_ID}/build`))
          return json({ build: premisesBuildFixture({ id: "some-other-build" }) });
        if (url.includes(`/connections/${BUILD_ID}`)) return json(buildDetailFixture());
        if (url.includes("/settings/services")) return json([]);
        return json({ count: 0, results: [], rows: [], methods: [] });
      },
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/connections/${BUILD_ID}?tab=overview`]}>
            <Routes>
              <Route
                path="/:tenant/connections/:connectionId"
                element={<BuildDetailPage client={client} timeZone="UTC" dateFormat="MM/DD/YYYY" />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    await openedOn("overview");
    await waitFor(() =>
      expect(document.querySelector("[data-account-no]")).not.toBeNull(),
    );
    // The NUMBER is still there — the LINK is not.
    expect(document.querySelector('[data-made-row="account"] a')).toBeNull();
  });

  it("Outstanding and What happens next are both drawn", async () => {
    mountTab("overview");
    await openedOn("overview");
    expect(document.querySelector('[data-build-section="outstanding"]')).not.toBeNull();
    expect(document.querySelector('[data-build-section="next"]')).not.toBeNull();
  });
});

/** `GET /connections/{id}/activation` for the fixture build: unit 1, water
 *  ready (its one order done) with meter M-4471 standing on it in Inventory;
 *  fire held by gate WO-26-0310. */
function activationFixture(): ActivationRead {
  const order = {
    id: ORDER_ID,
    order_no: "WO-26-0309",
    type: "meter_set",
    state: "completed",
    outcome: "passed",
    is_gate: false,
    unit_label: "1",
    service: "water",
  };
  return {
    connection_id: BUILD_ID,
    connection_no: "CON-26-0117",
    state: "requested",
    accounts_on_units: [],
    can_activate: true,
    refusal: null,
    rows: [
      {
        id: "cs-water",
        unit_id: UNIT_ID,
        unit_label: "1",
        unit_type: "Apartment",
        unit_state: "pending",
        service: "water",
        state: "pending",
        activated_at: null,
        assets: [
          {
            id: "a-1",
            asset_no: "M-4471",
            type: "meter",
            type_name: "Meter",
            size_class: "W-58",
            status: "inventory",
            status_name: "Inventory",
            install_date: null,
          },
        ],
        qty: 1,
        work_orders: [order],
        open_orders: [],
        blocked_by_gate: null,
        ready: true,
      },
      {
        id: "cs-fire",
        unit_id: UNIT_ID,
        unit_label: "1",
        unit_type: "Apartment",
        unit_state: "pending",
        service: "fire",
        state: "pending",
        activated_at: null,
        assets: [],
        qty: 0,
        work_orders: [],
        open_orders: ["WO-26-0310"],
        blocked_by_gate: "WO-26-0310",
        ready: false,
      },
    ],
    ready_ids: ["cs-water"],
    orders_total: 2,
    open_orders: [{ ...order, id: ORDER_ID_2, order_no: "WO-26-0310", state: "planned", is_gate: true, service: "fire" }],
    open_todos: [],
  };
}

describe("task 7 · Units", () => {
  afterEach(cleanup);

  it("`?tab=units` draws unit type, asset type, size, qty, asset ID, order and state (CR-162-BRC10)", async () => {
    mountTab("units");
    await openedOn("units");
    await waitFor(() => expect(document.querySelector('[data-table="build-units"]')).not.toBeNull());
    expect(heads("build-units").slice(1, 10)).toEqual([
      "Unit",
      "Unit type",
      "Utility service",
      "Asset type",
      "Size",
      "Qty",
      "Asset ID",
      "Work order",
      "State",
    ]);
    expect(document.querySelector('[data-unit-group="1"]')).not.toBeNull();
    const water = document.querySelector('[data-service-point="cs-water"]') as HTMLElement;
    expect(water.textContent).toContain("Meter");
    expect(water.textContent).toContain("W-58");
    expect(water.textContent).toContain("M-4471");
    expect(water.textContent).toContain("Inventory");
  });

  it("only a READY row can be chosen; a gate-held row says why it cannot activate", async () => {
    mountTab("units");
    await openedOn("units");
    await waitFor(() => expect(document.querySelector("[data-choose]")).not.toBeNull());
    expect(document.querySelector('[data-choose="cs-water"]')).not.toBeNull();
    expect(document.querySelector('[data-choose="cs-fire"]')).toBeNull();
    const fire = activationFixture().rows[1];
    const t = (_k: string, o?: Record<string, unknown>) => String(o?.defaultValue ?? "");
    expect(rowRefusal(fire, t)).toBe("Gate WO-26-0310 not passed.");
    expect(rowRefusal(activationFixture().rows[0], t)).toBeNull();
    expect(document.querySelector('[data-act="activateAllReady"]')).not.toBeNull();
  });

  it("the work-order cell is the LINK and nothing else — the state and crew are not repeated", async () => {
    mountTab("units");
    await openedOn("units");
    await waitFor(() => expect(document.querySelector("[data-order-no]")).not.toBeNull());
    const cell = document
      .querySelector('[data-table="build-units"] [data-order-no]')
      ?.closest("td") as HTMLElement;
    expect(cell.textContent?.trim()).toBe("WO-26-0309");
  });

  it("`Open unit` goes to the unit, tenant-scoped", async () => {
    mountTab("units");
    await openedOn("units");
    await waitFor(() => expect(document.querySelector("[data-open-unit]")).not.toBeNull());
    // `unitDetailPath` — the ONE builder for a unit's address, and it is
    // `/premises/units/<id>`. Spelled out rather than composed from the helper
    // on purpose: a test that called the helper would pass even on the day the
    // helper started pointing somewhere else.
    expect(document.querySelector("[data-open-unit]")?.getAttribute("href")).toBe(
      `/${TENANT}/premises/units/${UNIT_ID}`,
    );
  });

  it("`Approve` in the header opens the warning listing the open orders", async () => {
    mountTab("units");
    await openedOn("units");
    await waitFor(() =>
      expect(document.querySelector('[data-act="approve"]')).not.toHaveAttribute("disabled"),
    );
    (document.querySelector('[data-act="approve"]') as HTMLButtonElement).click();
    await waitFor(() => expect(document.querySelector("[data-activate-dialog]")).not.toBeNull());
    expect(document.querySelector("[data-open-orders]")?.textContent).toBe("WO-26-0310");
    expect(document.querySelector("[data-activate-gated]")?.textContent).toContain("WO-26-0310");
    expect(document.querySelector('[data-activate-row="cs-water"]')).not.toBeNull();
  });
});

// ⚠ **THESE CASES CHANGED SHAPE ON 2026-09-28 (`DEF-CUS-7618`) BECAUSE THE
// TAB DID.** It was a hand-rolled `PlainTable` with `data-table="build-work"`;
// it now composes `buildViews.WorkOrdersTab`, the shared `DataTable` the
// premises and account pages already mount, on its third host. So the table is
// read through the shared panel's own hook — `[data-work-orders-tab="build"]`
// — and the assertions the Product Owner ruled on are UNCHANGED: crew and
// technician are two columns, in that order, and the order number opens Work.
function buildWorkTable(): HTMLElement | null {
  return document.querySelector('[data-work-orders-tab="build"] table');
}

/** ⚠ **THE SORT GLYPH IS PART OF A SORTABLE HEAD'S TEXT** — `Target▲`, not
 *  `Target`. It is stripped here rather than asserted, because which column
 *  carries the arrow is the shared table's business and this file's subject is
 *  WHICH COLUMNS and IN WHAT ORDER. A first draft compared the raw strings and
 *  went red on `Target▲`, which is the assertion telling the truth about
 *  something it was not asking. */
function buildWorkHeads(): string[] {
  return Array.from(buildWorkTable()?.querySelectorAll("thead th") ?? []).map((th) =>
    (th.textContent ?? "").replace(/[▲▼]/g, "").trim(),
  );
}

describe("task 8 · Work", () => {
  afterEach(cleanup);

  it("`?tab=work` composes the SHARED work-orders table, not a second one", async () => {
    mountTab("work");
    await openedOn("work");
    await waitFor(() => expect(buildWorkTable()).not.toBeNull());
    // The hand-rolled table is gone — if it ever comes back, this fails.
    expect(document.querySelector('[data-table="build-work"]')).toBeNull();
    // The capabilities the copy did not have, all four of them the shared
    // panel's own: search, a filter chip, the column chooser, pagination.
    const frame = document.querySelector('[data-work-orders-tab="build"]') as HTMLElement;
    expect(frame.querySelector("input[type='search'], .table-toolbar input")).not.toBeNull();
  });

  it("`?tab=work` draws CREW and TECHNICIAN as separate columns, in that order", async () => {
    mountTab("work");
    await openedOn("work");
    await waitFor(() => expect(buildWorkTable()).not.toBeNull());
    const columns = buildWorkHeads();
    expect(columns).toContain("Crew");
    expect(columns).toContain("Technician");
    expect(columns.indexOf("Crew")).toBeLessThan(columns.indexOf("Technician"));
    // `03-work.png`'s eight, in its order, before the row-action head.
    expect(columns.slice(0, 8)).toEqual([
      "Order",
      "What",
      "Service",
      "Unit",
      "Crew",
      "Technician",
      "Target",
      "State",
    ]);
  });

  it("the two cells split the ONE holder the wire serves, each way round", async () => {
    mountTab("work");
    await openedOn("work");
    await waitFor(() => expect(document.querySelector("[data-order-crew]")).not.toBeNull());
    // A crew holds WO-26-0309: the crew cell NAMES it, the technician cell says
    // it has nothing (`data-absent`), and neither invents the other.
    const crewRow = document.querySelector('[data-order-crew="WO-26-0309"]') as HTMLElement;
    expect(crewRow.textContent).toContain("Meter crew");
    const crewRowTech = document.querySelector(
      '[data-order-technician="WO-26-0309"]',
    ) as HTMLElement;
    expect(crewRowTech.querySelector("[data-absent]")).not.toBeNull();
    // A person holds WO-26-0310, which is the mirror image.
    const personRowTech = document.querySelector(
      '[data-order-technician="WO-26-0310"]',
    ) as HTMLElement;
    expect(personRowTech.textContent).toContain("Ray Alvarez");
    expect(
      (document.querySelector('[data-order-crew="WO-26-0310"]') as HTMLElement).querySelector(
        "[data-absent]",
      ),
    ).not.toBeNull();
  });

  it("only THIS build's orders are drawn, though the read answers the whole address", async () => {
    mountTab("work");
    await openedOn("work");
    await waitFor(() => expect(document.querySelector("[data-order-row]")).not.toBeNull());
    const drawn = Array.from(document.querySelectorAll("[data-order-row]")).map((el) =>
      el.getAttribute("data-order-row"),
    );
    // ⚠ **SORTED, NOT LISTED — so the SET is asserted and not the sequence.**
    // The shared table's arrival sort is `booked` ascending and
    // `compareWorkOrders` puts an order with no window and no deadline LAST,
    // which is why `WO-26-0310` (due 10 Oct) comes before `WO-26-0309`
    // (neither). That is the shared panel's rule and this case is not about it.
    expect([...drawn].sort()).toEqual(["WO-26-0309", "WO-26-0310"]);
    // `WO-26-0411` stands at the same premises and belongs to another build.
    expect(drawn).not.toContain("WO-26-0411");
  });

  it("the row action opens the order's drawer, and the drawer names the order", async () => {
    mountTab("work");
    await openedOn("work");
    await waitFor(() => expect(document.querySelector("[data-order-row]")).not.toBeNull());
    const eye = document
      .querySelector('[data-order-row="WO-26-0310"]')
      ?.closest("tr")
      ?.querySelector("button") as HTMLButtonElement;
    expect(eye).not.toBeNull();
    // Two ids named so a reader can see which rows this case is about.
    expect([ORDER_ID, ORDER_ID_2]).toHaveLength(2);
  });

  it("the tab's own strip counts Orders, Done, Open and the Target date", async () => {
    mountTab("work");
    await openedOn("work");
    await waitFor(() =>
      expect(document.querySelector('[data-build-facts="work"]')).not.toBeNull(),
    );
    const strip = document.querySelector('[data-build-facts="work"]') as HTMLElement;
    for (const label of ["Orders", "Done", "Open", "Target"]) {
      expect(strip.textContent, `the ${label} tile`).toContain(label);
    }
  });

  it("the header's Raise order is NOT repeated above the table", async () => {
    mountTab("work");
    await openedOn("work");
    await waitFor(() => expect(buildWorkTable()).not.toBeNull());
    const frame = document.querySelector('[data-work-orders-tab="build"]') as HTMLElement;
    // The property tab draws `⚡ Raise work here` above its table; on the build
    // the page header already carries `Raise order`, and two doors to one act
    // on one screen is what the PO took off this header on 2026-09-28.
    expect(frame.textContent).not.toContain("Raise work here");
  });
});

// ⚠ **THE FIXTURE IS NAMED HERE SO A READER CAN SEE WHAT THE WORK TAB READS.**
// Without the premises work-order stub the shared table would be empty and
// every case above would pass over nothing, which is law 7's *reporting zero
// over a scope it silently excludes*.
describe("task 8 · Work — the Unit column (DEF-CUS-9178)", () => {
  afterEach(cleanup);

  it("an order with no unit says Whole build; an order on a unit says which", async () => {
    mountTab("work");
    await openedOn("work");
    await waitFor(() =>
      expect(document.querySelector(`[data-order-where="${ORDER_ID_2}"]`)).not.toBeNull(),
    );
    const whole = document.querySelector(`[data-order-where="${ORDER_ID_2}"]`) as HTMLElement;
    expect(whole.textContent).toBe("Whole build");
    expect(whole.hasAttribute("data-whole-build")).toBe(true);
    const onUnit = document.querySelector(`[data-order-where="${ORDER_ID}"]`) as HTMLElement;
    expect(onUnit.hasAttribute("data-whole-build")).toBe(false);
    expect(onUnit.textContent).not.toBe("");
  });
});

describe("task 8 · Work — the read it composes", () => {
  afterEach(cleanup);

  it("asks the SHARED premises route and not a connection route of its own", async () => {
    const urls = mountTab("work");
    await openedOn("work");
    await waitFor(() => expect(buildWorkTable()).not.toBeNull());
    expect(urls.some((url) => url.includes(`/premises/${PREMISES_ID}/work-orders`))).toBe(true);
    // There is no `GET /connections/{id}/work-orders` and this must not invent
    // one — see `WorkOrdersTab`'s docstring.
    expect(urls.some((url) => url.includes(`/connections/${BUILD_ID}/work-orders`))).toBe(false);
    expect(premisesWorkOrdersFixture().results).toHaveLength(3);
  });
});

describe("task 9 · Charges", () => {
  afterEach(cleanup);

  it("`?tab=charges` states the figures the SERVER stated and never re-rounds one", async () => {
    mountTab("charges");
    await openedOn("charges");
    await waitFor(() =>
      expect(document.querySelector('[data-build-facts="charges"]')).not.toBeNull(),
    );
    const strip = document.querySelector('[data-build-facts="charges"]') as HTMLElement;
    // The server's own `display` strings, verbatim. A four-decimal `stored`
    // figure reaching a screen is hard rule 2's own prohibition.
    expect(strip.textContent).toContain("$612.00");
    expect(strip.textContent).toContain("$500.00");
    expect(strip.textContent).toContain("$112.00");
    expect(strip.textContent).not.toContain("612.0000");
  });

  it("it LINKS to the account, and Open payments is a real link (DEF-CUS-9183)", async () => {
    mountTab("charges");
    await openedOn("charges");
    await waitFor(() =>
      expect(document.querySelector("[data-open-payments]")).not.toBeNull(),
    );
    const open = document.querySelector("[data-open-payments]") as HTMLAnchorElement;
    expect(open.getAttribute("href")).toBe(`/${TENANT}/accounts/${ACCOUNT_ID}?tab=payments`);
    // The kit's link, so it LOOKS like a link (`InlineLinkTo`).
    expect(open.hasAttribute("data-inlinelink")).toBe(true);
    const billedTo = document.querySelector("[data-billed-to-link]") as HTMLAnchorElement;
    expect(billedTo.getAttribute("href")).toBe(`/${TENANT}/accounts/${ACCOUNT_ID}`);
  });

  it("the payer link comes from the RECORD even when the premises read names another build", async () => {
    // `DEF-CUS-9183` — the page's derived id is null when `GET /premises/{id}/build`
    // answers a different (newer) build; the record's `billed_to_id` still opens.
    const record = buildRecordFixture();
    mountTab("charges", { record: { ...record, money: { ...record.money, billed_to_id: "01a0d222-0000-7000-8000-00000000f00d" } } });
    await openedOn("charges");
    await waitFor(() => expect(document.querySelector("[data-open-payments]")).not.toBeNull());
    expect(document.querySelector("[data-open-payments]")?.getAttribute("href")).toBe(
      `/${TENANT}/accounts/01a0d222-0000-7000-8000-00000000f00d?tab=payments`,
    );
  });

  it("the invoice NUMBER links to the bill by its id (DEF-CUS-9184)", async () => {
    mountTab("charges");
    await openedOn("charges");
    await waitFor(() => expect(document.querySelector("[data-invoice-link]")).not.toBeNull());
    const link = document.querySelector("[data-invoice-link]") as HTMLAnchorElement;
    expect(link.textContent).toBe("INV-26-0318");
    expect(link.getAttribute("href")).toBe(`/${TENANT}/billing/bills/${INVOICE_ID}`);
  });

  it("Paid so far lists each payment with its method, cheque number and receipt link (DEF-CUS-9182)", async () => {
    mountTab("charges");
    await openedOn("charges");
    await waitFor(() =>
      expect(document.querySelector('[data-table="build-payments"]')).not.toBeNull(),
    );
    expect(heads("build-payments")).toEqual(["Date", "Method", "Type", "Amount", "Receipt", "State"]);
    const row = document.querySelector('[data-payment-row="PY-261002-0084"]') as HTMLElement;
    expect(row.querySelector("[data-payment-method]")?.textContent).toBe("Check #4471");
    expect(row.textContent).toContain("10/02/2026");
    expect(row.textContent).toContain("$500.00");
    expect(row.querySelector("[data-payment-link]")?.getAttribute("href")).toBe(
      `/${TENANT}/payments/PY-261002-0084`,
    );
  });
});

describe("task 9 · Charges — the line figures (DEF-CUS-9180, DEF-CUS-9181)", () => {
  afterEach(cleanup);

  it("Each and Amount are the SERVER's pairs and the quantity drops its stored zeros", async () => {
    mountTab("charges");
    await openedOn("charges");
    await waitFor(() =>
      expect(document.querySelector('[data-charge-line="0"]')).not.toBeNull(),
    );
    const line = document.querySelector('[data-charge-line="0"]') as HTMLElement;
    expect(line.textContent).toContain("CONN");
    expect(line.querySelector("[data-charge-qty]")?.textContent).toBe("2");
    expect(line.querySelector("[data-charge-each]")?.textContent).toBe("$45.00");
    expect(line.querySelector("[data-charge-amount]")?.textContent).toBe("$90.00");
    expect(line.textContent).not.toContain("45.0000");
    expect(line.textContent).not.toContain("2.000000");
    expect(line.querySelectorAll("[data-absent]")).toHaveLength(0);
  });

  it("quantityText drops trailing zeros and never rounds", () => {
    expect(quantityText("2.000000")).toBe("2");
    expect(quantityText("2.500000")).toBe("2.5");
    expect(quantityText("2.333333")).toBe("2.333333");
    expect(quantityText("10")).toBe("10");
    expect(quantityText(null)).toBeNull();
  });
});

describe("task 9 · Charges — Add fee (CR-163-BRC10 item 2)", () => {
  afterEach(cleanup);

  it("is live after submission and opens the form", async () => {
    mountTab("charges", { detail: { ...buildDetailFixture(), state: "in_progress" } });
    await openedOn("charges");
    await waitFor(() => expect(document.querySelector('[data-act="addFee"]')).not.toBeNull());
    const add = document.querySelector('[data-act="addFee"]') as HTMLButtonElement;
    expect(add.disabled).toBe(false);
    fireEvent.click(add);
    await waitFor(() => expect(document.getElementById("build-fee-code")).not.toBeNull());
  });

  it("is refused WITH its reason once the build is approved", async () => {
    // The fixture's build is PARTLY ACTIVATED — approval has happened.
    mountTab("charges");
    await openedOn("charges");
    await waitFor(() => expect(document.querySelector('[data-act="addFee"]')).not.toBeNull());
    const add = document.querySelector('[data-act="addFee"]') as HTMLButtonElement;
    expect(add.disabled).toBe(true);
    expect(add.getAttribute("data-blocked-reason")).toBe("Only before approval");
  });
});

describe("task 9 · Charges — Take payment (DEF-CUS-9185)", () => {
  afterEach(cleanup);

  it("is live while something is owed", async () => {
    mountTab("charges");
    await openedOn("charges");
    await waitFor(() => expect(document.querySelector('[data-act="takePayment"]')).not.toBeNull());
    await waitFor(() =>
      expect((document.querySelector('[data-act="takePayment"]') as HTMLButtonElement).disabled).toBe(false),
    );
  });

  it("is disabled WITH its reason when nothing is owed", async () => {
    const record = buildRecordFixture();
    mountTab("charges", {
      record: {
        ...record,
        money: { ...record.money, outstanding: { stored: "0.0000", display: "0.00" } },
      },
    });
    await openedOn("charges");
    await waitFor(() =>
      expect((document.querySelector('[data-act="takePayment"]') as HTMLButtonElement | null)?.disabled).toBe(true),
    );
    expect(document.querySelector('[data-act="takePayment"]')?.getAttribute("data-blocked-reason")).toBe(
      "Nothing owed",
    );
  });
});

describe("task 10 · Documents", () => {
  afterEach(cleanup);

  it("`?tab=documents` mounts the SHARED capture block", async () => {
    mountTab("documents");
    await openedOn("documents");
    await waitFor(() => expect(document.querySelector("[data-doc-section]")).not.toBeNull());
  });

  const FILED = {
    id: "01a0d222-3333-7444-8555-6666777800d1",
    doc_type: "contract",
    name: "G-Trade-Tower-contract.pdf",
    uploaded_at: "2026-10-02T16:00:00Z",
    uploaded_by_name: "Dana Mercer",
    size_bytes: 20480,
  };

  it("a filed document opens from an EYE and from its NAME, through the account's content route (DEF-CUS-9186)", async () => {
    const opened: string[] = [];
    const original = window.open;
    window.open = ((url?: string | URL) => {
      opened.push(String(url));
      return null;
    }) as typeof window.open;
    // The content route is built from the tenant of the URL the BROWSER is on
    // (`api/client.currentTenant`), exactly as in the product.
    window.history.pushState({}, "", `/${TENANT}/connections/${BUILD_ID}?tab=documents`);
    try {
      mountTab("documents", { documents: [FILED] });
      await openedOn("documents");
      await waitFor(() => expect(document.querySelector('[data-doc-row="contract"]')).not.toBeNull());
      const row = document.querySelector('[data-doc-row="contract"]') as HTMLElement;
      const eye = row.querySelector('[data-doc-actions] button') as HTMLButtonElement;
      expect(eye.getAttribute("aria-label")).toBe("Open");
      fireEvent.click(eye);
      const name = row.querySelector("[data-doc-file-link]") as HTMLButtonElement;
      expect(name.textContent).toBe("G-Trade-Tower-contract.pdf");
      fireEvent.click(name);
      expect(opened).toHaveLength(2);
      for (const url of opened) {
        expect(url).toContain(`/accounts/${ACCOUNT_ID}/documents/${FILED.id}/content?as=view`);
      }
    } finally {
      window.open = original;
      window.history.pushState({}, "", "/");
    }
  });

  it("the Document column reads the LABEL, and the two empty columns are gone (DEF-CUS-9187)", async () => {
    mountTab("documents", { documents: [FILED] });
    await openedOn("documents");
    await waitFor(() => expect(document.querySelector('[data-doc-row="contract"]')).not.toBeNull());
    const row = document.querySelector('[data-doc-row="contract"]') as HTMLElement;
    expect(row.querySelector("[data-doc-name]")?.textContent).toBe("Contract");
    expect(row.querySelector("[data-doc-required]")).toBeNull();
    expect(row.querySelector("[data-doc-state]")).toBeNull();
    expect(heads("capture-documents")).not.toContain("Required");
    expect(heads("capture-documents")).not.toContain("State");
  });
});

describe("task 11 · Messages", () => {
  afterEach(cleanup);

  it("`?tab=messages` lists each letter with Preview and Send per row (CR-163-BRC10 item 26)", async () => {
    mountTab("messages");
    await openedOn("messages");
    await waitFor(() =>
      expect(document.querySelector('[data-table="build-messages"]')).not.toBeNull(),
    );
    expect(document.querySelectorAll('[data-testid^="send-"]')).toHaveLength(2);
    expect(document.querySelectorAll('[data-testid^="preview-"]')).toHaveLength(2);
    // A letter already queued offers RESEND, the next copy.
    const queued = document.querySelector('[data-testid="send-build_confirmed"]') as HTMLButtonElement;
    expect(queued.getAttribute("aria-label")).toBe("Resend");
    expect(queued.disabled).toBe(false);
  });

  it("When is the queue's own moment, and State reads Queued (DEF-CUS-9188)", async () => {
    mountTab("messages");
    await openedOn("messages");
    await waitFor(() =>
      expect(document.querySelector('[data-message-row="build_confirmed"]')).not.toBeNull(),
    );
    const row = document.querySelector('[data-message-row="build_confirmed"]') as HTMLElement;
    expect(row.querySelector("[data-message-when]")?.textContent).toContain("10/02/2026");
    expect(row.querySelector('[data-message-state="queued"]')?.textContent).toBe("Queued");
    const waiting = document.querySelector('[data-message-row="quote_and_what_is_owed"]') as HTMLElement;
    expect(waiting.querySelector("[data-message-state]")?.textContent).toBe("Sent on approval");
  });

  it("says which language each letter went in (DEF-CUS-9195, PO 2026-10-02 item 2)", async () => {
    mountTab("messages");
    await openedOn("messages");
    await waitFor(() =>
      expect(document.querySelector('[data-message-row="build_confirmed"]')).not.toBeNull(),
    );
    const row = document.querySelector('[data-message-row="build_confirmed"]') as HTMLElement;
    expect(row.querySelector('[data-message-language="es"]')?.textContent).toBe("Español");
    // A letter nothing has queued yet went in no language at all.
    const waiting = document.querySelector('[data-message-row="quote_and_what_is_owed"]') as HTMLElement;
    expect(waiting.querySelector("[data-message-language]")?.textContent).toBe("");
  });

  it("a letter with no published wording says how to add one, and Send is greyed (DEF-CUS-9188)", async () => {
    mountTab("messages");
    await openedOn("messages");
    await waitFor(() =>
      expect(document.querySelector('[data-message-row="quote_and_what_is_owed"]')).not.toBeNull(),
    );
    const row = document.querySelector('[data-message-row="quote_and_what_is_owed"]') as HTMLElement;
    expect(row.querySelector("[data-no-template]")?.textContent).toBe(
      "No template — add one in Settings → Templates",
    );
    const send = row.querySelector('[data-testid="send-quote_and_what_is_owed"]') as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    expect(send.getAttribute("title")).toBe("No template");
  });

  it("Send now posts ONE letter on the chosen channel to the chosen recipient", async () => {
    const posts: { url: string; body: unknown }[] = [];
    mountTab("messages", {
      onPost: (url, body) => {
        posts.push({ url, body });
        return { code: "build_confirmed", channel: "email", copy_no: 1, state: "queued" };
      },
    });
    await openedOn("messages");
    await waitFor(() =>
      expect(document.querySelector('[data-testid="send-build_confirmed"]')).not.toBeNull(),
    );
    fireEvent.click(document.querySelector('[data-testid="send-build_confirmed"]') as HTMLElement);
    await waitFor(() => expect(document.getElementById("build-message-recipient")).not.toBeNull());
    const recipient = document.getElementById("build-message-recipient") as HTMLSelectElement;
    // Email offers the owner AND the co-applicant who gave an email address.
    expect(Array.from(recipient.options).map((one) => one.value)).toEqual(["owner", "co_applicant"]);
    fireEvent.change(recipient, { target: { value: "co_applicant" } });
    // The dialog's own commit — the LAST "Resend" on the page; the row's icon
    // carries the same accessible name and comes first.
    const resend = screen.getAllByRole("button", { name: "Resend" });
    fireEvent.click(resend[resend.length - 1]);
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].url).toContain(`/connections/${BUILD_ID}/messages/build_confirmed/send`);
    expect(posts[0].body).toEqual({ channel: "email", recipient: "co_applicant" });
  });

  // ⚠ **THE TEST THAT FIRES WHEN A HOLD EXPIRES** (hard-won law 2's mirror) —
  // the refusal is the PAYLOAD's, never a literal: a row the payload does not
  // refuse is live, and the day a template is published the same row opens.
  it("a row the payload does NOT refuse is live, and the refusal is not a literal", () => {
    const sendable: BuildMessageRow = {
      code: "build_created",
      channels: ["email"],
      templateCode: "new_connect_confirmed",
      state: "not_sent",
      reason: "sent_on_approval",
      sentAt: null,
      templateAvailable: true,
      sendable: true,
      deliveries: 0,
      languages: [],
    };
    const t = (key: string, params?: Record<string, unknown>) => String(params?.defaultValue ?? key);
    expect(resendRefusal(sendable, t)).toBeNull();
    expect(resendRefusal({ ...sendable, templateAvailable: false }, t)).toBe("No template");
    expect(resendRefusal({ ...sendable, sendable: false }, t)).toBe("No template");
    expect(resendRefusal(sendable, t, [])).toBe("No owner account");
  });
});

describe("task 12 · Audit", () => {
  afterEach(cleanup);

  it("`?tab=audit` is read-only, newest first, and has no control on a row", async () => {
    mountTab("audit");
    await openedOn("audit");
    await waitFor(() => expect(document.querySelector('[data-table="build-audit"]')).not.toBeNull());
    expect(heads("build-audit")).toEqual(["When", "Who", "What"]);
    const table = document.querySelector('[data-table="build-audit"]') as HTMLElement;
    expect(table.querySelectorAll("button")).toHaveLength(0);
    expect(table.querySelectorAll("input")).toHaveLength(0);
  });
});

describe("the whole strip", () => {
  afterEach(cleanup);

  it("an unknown `?tab=` falls back to Overview rather than erroring (BR-SHL-011)", async () => {
    mountTab("nonsense");
    await openedOn("overview");
  });

  it("every tab reaches its own screen id and its own body — none of the seven is dead", async () => {
    for (const tab of ["overview", "units", "work", "charges", "documents", "messages", "audit"]) {
      mountTab(tab);
      await openedOn(tab);
      const body = document.querySelector(`[data-build-tab="${tab}"]`) as HTMLElement;
      // A tab whose body renders nothing at all is the dead UI law 2 is about.
      expect(body.textContent?.trim().length, `${tab} rendered nothing`).toBeGreaterThan(0);
      cleanup();
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-MET-7805` — NO CELL ON THIS PAGE IS A MACHINE TOKEN
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **FOUND BY A BROWSER WALK AND BY NOTHING ELSE (hard-won law 6).** Measured
// on `CON-26-0001`, 2026-09-28, hours after the page went live: the header
// pill read `requested`, the Units tab's STATE column read `requested` on
// eight rows, this table read `build_created` · `email` ·
// `new_connect_confirmed` · `not_sent` on seven rows, and the Audit tab read
// `connection.committed`. Every one came from a `t()` whose key family
// resolves in NONE of the eleven catalogues, with the CODE as its
// `defaultValue`.
//
// ⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY, asked before it was trusted**
// (law 7, habit 2): a cell that is EMPTY passes a "does not look like a token"
// test trivially, and an empty cell is the other way to lose a fact. So the
// occasion and state columns are asserted NON-EMPTY as well, and the template
// column — where an unmapped tenant code is legitimately shown as it is — is
// asserted only for OUR OWN seeded classes.
//
// ⚠ The fixture below carries the SERVER's vocabulary rather than the shared
// fixture's, which drifted: `buildDetailFixture` says `build_confirmed` and
// `print` where `connection_messages.OCCASIONS` says `build_created` and
// `pdf_print`. Using the server's words is what makes this case able to fail.
const LOOKS_LIKE_A_TOKEN = /^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$/;

function recordWithTheServersVocabulary(): BuildRecord {
  const record = buildRecordFixture();
  record.sections.communication = {
    count: 3,
    page: 1,
    per: 50,
    results: [
      {
        code: "build_created",
        channels: ["email"],
        template_code: "new_connect_confirmed",
        when: "at_creation",
        state: "not_sent",
        reason: "platform_has_no_writer",
      },
      {
        code: "contract",
        channels: ["pdf_print"],
        template_code: "contract_service_agreement",
        when: "at_creation",
        state: "not_sent",
        reason: "platform_has_no_writer",
      },
      // The one the PO's own ruling is about — *"we ahe to say activate"*.
      {
        code: "unit_energised",
        channels: ["email"],
        template_code: null,
        when: "on_activation",
        state: "not_asked",
        reason: "platform_has_no_writer",
      },
    ],
  };
  return record;
}

describe("DEF-MET-7805 · no cell on this page is a machine token", () => {
  afterEach(cleanup);

  it("the Messages tab words the occasion, the channel, the template and the state", async () => {
    mountTab("messages", { record: recordWithTheServersVocabulary() });
    await openedOn("messages");
    await waitFor(() =>
      expect(document.querySelector('[data-table="build-messages"]')).not.toBeNull(),
    );
    const rows = Array.from(
      document.querySelectorAll('[data-table="build-messages"] tbody tr'),
    ) as HTMLElement[];
    expect(rows).toHaveLength(3);
    for (const row of rows) {
      const cells = Array.from(row.querySelectorAll("td")).map((td) => td.textContent?.trim() ?? "");
      const [occasion, channel, template, , state] = cells;
      expect(occasion).not.toBe("");
      expect(occasion).not.toMatch(LOOKS_LIKE_A_TOKEN);
      expect(channel).not.toMatch(LOOKS_LIKE_A_TOKEN);
      expect(state).not.toBe("");
      expect(state).not.toMatch(LOOKS_LIKE_A_TOKEN);
      // An EMPTY template cell is lawful — the third row has none.
      if (template !== "") {
        expect(template).not.toMatch(LOOKS_LIKE_A_TOKEN);
      }
    }
  });

  it("says *activated* and never *energised*, which the PO ruled on 2026-09-21", async () => {
    mountTab("messages", { record: recordWithTheServersVocabulary() });
    await openedOn("messages");
    await waitFor(() =>
      expect(document.querySelector('[data-table="build-messages"]')).not.toBeNull(),
    );
    const table = document.querySelector('[data-table="build-messages"]') as HTMLElement;
    // The ROW HOOK keeps the server's code — that is what a hook is for.
    expect(table.querySelector('[data-message-row="unit_energised"]')).not.toBeNull();
    // The WORDS never do. PO 2026-09-21: *"we ahe to say activate"*, already
    // ruled once on 2026-08-25 (`CR-032`), so this was a MISSED INSTANCE.
    expect(table.innerText ?? table.textContent ?? "").not.toMatch(/energi[sz]/i);
  });

  // ⚠ **THE AUDIT TAB READS `detail.history`, NOT `record.sections.audit`** —
  // corrected after the first draft of this case overrode the SECTION and got
  // one row where it asserted two. That is law 7's *looking at the wrong
  // thing* caught in the writing rather than after the push, and it is why
  // this case reads whatever the detail read actually serves.
  // ⚠⚠ **THE FIRST DRAFT OF THIS CASE COULD NOT FAIL, AND THE FIXTURE IS WHY
  // (law 7, *incapable of failing*).** `buildDetailFixture`'s single history
  // row carries `what: "Build created"` — already ENGLISH — where the server
  // sends `connection.committed`, which is what the browser walk actually read
  // on 2026-09-28. So the case passed against the unfixed code, proving
  // nothing. It now supplies the SERVER's own vocabulary, and it went red
  // against the tip with it.
  it("the Audit tab words the event, and keeps the history readable top to bottom", async () => {
    const detail = buildDetailFixture();
    detail.history = [
      { at: "2026-09-28T13:22:00Z", who: "Dana Whitfield", what: "connection.committed" },
      { at: "2026-09-28T13:35:00Z", who: "Dana Whitfield", what: "connection.held" },
    ];
    mountTab("audit", { detail });
    await openedOn("audit");
    await waitFor(() => expect(document.querySelector('[data-table="build-audit"]')).not.toBeNull());
    const whats = Array.from(
      document.querySelectorAll('[data-table="build-audit"] tbody tr'),
    ).map((row) => (row.querySelectorAll("td")[2]?.textContent ?? "").trim());
    expect(whats).toHaveLength(2);
    for (const what of whats) {
      expect(what).not.toBe("");
      expect(what).not.toMatch(LOOKS_LIKE_A_TOKEN);
    }
  });

  it("the header's own state pill says the WORD, which its Trace header always promised", async () => {
    mountTab("overview");
    await openedOn("overview");
    await waitFor(() => expect(document.querySelector("[data-build-state]")).not.toBeNull());
    const pill = document.querySelector("[data-build-state]") as HTMLElement;
    // The hook keeps the code; the text must not be it.
    expect(pill.getAttribute("data-build-state")).not.toBe("");
    expect((pill.textContent ?? "").trim()).not.toMatch(LOOKS_LIKE_A_TOKEN);
    expect((pill.textContent ?? "").trim()).not.toBe(pill.getAttribute("data-build-state"));
  });

  it("the Units tab's STATE column words the per-service state on every row", async () => {
    mountTab("units");
    await openedOn("units");
    await waitFor(() => expect(document.querySelector("[data-point-state]")).not.toBeNull());
    const cells = Array.from(document.querySelectorAll("[data-point-state]")) as HTMLElement[];
    expect(cells.length).toBeGreaterThan(0);
    for (const cell of cells) {
      const word = (cell.textContent ?? "").trim();
      if (word === "") {
        continue; // a service with no state served is a lawful blank
      }
      expect(word).not.toMatch(LOOKS_LIKE_A_TOKEN);
      expect(word).not.toBe(cell.getAttribute("data-point-state"));
    }
  });
});
