// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-002 (EP-WRK-01) — the acts on a build, RE-HOSTED. TC-1..7
//           re-pointed: every act reachable from the premises and from the
//           account, a forbidden state disabled with its reason, the danger
//           tier on Cancel alone. US-WRK-004 — the jobs at a place, each row
//           saying which anchor it stands on.
// Rules:    CR-070 §W.10 / §W.11 (one destination — PO 2026-09-04) ·
//           BR-SHL-025 (disabled WITH its reason; the server refuses anyway) ·
//           BR-MET-110 (a person accepts what the field sent) · B14 rule 6
//           (the danger tier is the destructive commit alone) · rule 31 (no
//           database id is ever a visible value) · rule 32 (no internal code
//           in clerk copy) · rule 33 (a refusal is five or six words)
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import {
  ConnectionCell,
  OPEN_ORDER_STATES,
  OrderWhenCell,
  WorkOrdersTab,
  acceptBlockedReason,
  buildStateTone,
  compareWorkOrders,
  isOpenOrder,
  scopedOrdersQueryKey,
  workOrderMatches,
} from "./buildViews";
import { buildHomePath, buildOrderPath } from "./workEndpoints";
import type { ScopedWorkOrderList, ScopedWorkOrderRow } from "./workEndpoints";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** The header row's labels, in order — the DRAWN column set.
 *
 * ⚠ It reads `<thead>` and nothing else on purpose. The column chooser lists
 * every declared column, hidden ones included, so a substring search over the
 * whole render can never tell a drawn column from a hidden one. */
function headers(html: string): string[] {
  const head = /<thead>(.*?)<\/thead>/s.exec(html);
  if (head === null) {
    return [];
  }
  return [...head[1].matchAll(/<th[^>]*>(.*?)<\/th>/gs)].map((m) =>
    m[1].replace(/<[^>]*>/g, "").replace(/[▲▼]/g, "").trim(),
  );
}

function order(over: Partial<ScopedWorkOrderRow> = {}): ScopedWorkOrderRow {
  return {
    id: "wo-4901",
    order_no: "WO-4901",
    type: "Meter set",
    premise: { id: "prm-1408", premise_no: "P-01408", address: "1408 Elm St" },
    service: "water",
    state: "planned",
    outcome: null,
    mode: "our_crew",
    is_gate: false,
    connection: { id: "con-0117", connection_no: "CON-26-0117", home: { kind: "premises", id: "prm-1408" } },
    account: null,
    raised_at: "2026-09-03T12:00:00Z",
    stands_on: "build",
    scope: "per_unit",
    unit_label: "Unit 1",
    external_ref: null,
    completed_at: null,
    accepted_at: null,
    accepted_by: null,
    field_data: null,
    // CR-089 wave C `C6` (`PUJ-16`) — *when is somebody coming* is a date and
    // a name, and this row served neither until this wave. The default is the
    // ordinary case a premises tab meets: raised, nobody assigned, no
    // appointment, and an SLA deadline stamped at the raise (`BR-WRK-018`).
    technician: null,
    window_start: null,
    window_end: null,
    due_at: null,
    ...over,
  };
}

function renderOrders(
  host: "premises" | "account",
  hostId: string,
  rows: ScopedWorkOrderRow[],
  openOrderId: string | null = null,
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const payload: ScopedWorkOrderList = {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
  };
  queryClient.setQueryData(scopedOrdersQueryKey(host, hostId), payload);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TENANT}/premises/${hostId}`]}>
        <WorkOrdersTab
          host={host}
          hostId={hostId}
          t={t}
          timeZone="America/Chicago"
          dateFormat="MM/DD/YYYY"
          openOrderId={openOrderId}
          onOpenOrder={() => undefined}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// `DEF-GOV-10106` — TC-1..TC-6 rendered `BuildTab`, the property's and the
// account's Build panel, which the PO took off both hosts on 2026-10-02
// (`CR-162-BRC10`: the New Connection's own page tracks progress and takes
// every action). The panel and the acts row it drew are deleted with them.
describe("CR-070 wave O — US-WRK-002 re-pointed: the acts, on whichever host", () => {
  it("TC-7: the state tone is a reading of the state and decides nothing", () => {
    expect(buildStateTone("activated")).toBe("success");
    expect(buildStateTone("on_hold")).toBe("warning");
    expect(buildStateTone("cancelled")).toBe("danger");
    expect(buildStateTone("draft")).toBe("neutral");
  });
});

describe("CR-070 wave O — US-WRK-004: the jobs at a place, and on an account", () => {
  it("TC-1: the ACCOUNT arrives on ALL and the PROPERTY arrives on OPEN — two drawings, one component", () => {
    // ⚠ **AMENDED TWICE, AND THE SECOND AMENDMENT SPLITS THE TWO HOSTS.**
    //
    // 2026-09-10 (`DEF-4739`/`DEF-4740`): this case used to be *"every job is
    // listed, finished ones included"* and asserted both rows on arrival. The
    // PROPERTY blueprint (`P8`, pages 32–34) draws the chip `OPEN` as that
    // tab's DEFAULT FILTER and its footer counts *2 open · 7 done*.
    //
    // 2026-09-13 (B14 rule 41): the ACCOUNTS blueprint draws the same table
    // differently. `ACC-T08`'s four rows are one Scheduled and three CLOSED
    // and its footer counts *1–4 of 4*, so the account arrives on every job at
    // this address, finished ones included. Applying `OPEN` there would hide
    // three of its four drawn rows on arrival.
    const rows = [
      order(),
      order({
        id: "wo-4902",
        order_no: "WO-4902",
        type: "Final read",
        stands_on: "account",
        state: "completed",
        completed_at: "2026-09-01T15:00:00Z",
      }),
    ];
    const onAccount = renderOrders("account", "acc-1", rows);
    expect(onAccount).toContain("WO-4901");
    expect(onAccount).toContain("WO-4902");

    // The PROPERTY is unmoved: its chip is applied and says so on screen,
    // which is what makes the absence readable rather than a list that quietly
    // lost a row (B14 rule 12).
    const onProperty = renderOrders("premises", "prm-1408", rows);
    expect(onProperty).toContain("WO-4901");
    expect(onProperty).not.toContain("WO-4902");
    expect(onProperty).toContain("Status: Open");

    // ⚠ **THE OTHER HALF — pressing `All` and seeing the finished job come
    // back — IS A CLICK, so it lives in `buildViewsWorkOrders.dom.test.tsx`.**
    // A static render can only ever show the arrival state; asserting the
    // cleared state here would mean asserting a filter this file cannot press,
    // which is a test named after a claim it does not make (law 7).
    // What IS provable here: the anchor sentence is still DECLARED on the
    // account host, and the token behind it never reaches the screen
    // (B14 rule 32). `ACC-T08` takes `Stands on` off the DEFAULT set, so it is
    // read off the column chooser rather than off a row — see TC-1b2.
    expect(onAccount).toContain("Stands on");
    expect(onAccount).not.toContain(">account<");
  });

  it("TC-1b: the property host draws the SEVEN drawn columns and hides the four the blueprint does not", () => {
    // `DEF-4740`: nine columns were drawn, `Where` was not one of them, and
    // `Service`, `Mode`, `Outcome` and `Stands on` are drawn nowhere on this
    // screen. Nothing is deleted — the four are declared and off by default, so
    // the column chooser still offers them.
    // ⚠ **READ THE HEADER ROW, NOT THE DOCUMENT.** The column chooser lists
    // every DECLARED column, hidden ones included — that is what it is for — so
    // `html).not.toContain(">Service<")` over the whole render is a check that
    // can never pass and would have said nothing about the drawing.
    expect(headers(renderOrders("premises", "prm-1408", [order()]))).toEqual([
      "Work",
      "What",
      "Where",
      "Crew",
      "Booked",
      "Status",
      "Actions",
    ]);
  });

  it("TC-1b2: the ACCOUNT host draws `ACC-T08`'s SEVEN columns, and `Stands on` is not one of them", () => {
    // ⚠ **AMENDED 2026-09-13 (B14 rule 41).** This case asserted that the
    // account host ADDS `Stands on` to the default set, on `US-WRK-004`'s
    // reasoning: a person on an account sees the move-out's final read, the
    // meter exchange and the build's install jobs in one list, and a list that
    // did not say which is which would be claiming they are the same kind of
    // thing. **That reasoning still stands and the column is still declared**
    // — what changed is the DEFAULT set, which the drawing decides.
    // `ACC-T08` draws `ORDER # · TYPE · PRIORITY · TECHNICIAN · DUE · STATUS ·
    // RAISED BY`, and `Stands on` is not among them. Nothing is deleted: it is
    // off by default and reachable through `Columns ▾`, exactly as `Service`,
    // `Mode` and `Outcome` already are.
    expect(headers(renderOrders("account", "acc-1", [order()]))).toEqual([
      "Order #",
      "Type",
      "Priority",
      "Technician",
      "Due",
      "Status",
      "Raised by",
      "Actions",
    ]);
  });

  it("TC-1b3: the account's sort is FIXED — priority rank, then due, and no header is a control", () => {
    // `ACC-T08`, verbatim: *"This list is not in date order and the footer has
    // to say so. It is sorted by priority rank, then by due time, and that sort
    // is fixed — there is no column to click."*
    const urgent = { id: "p1", code: "URG", name: "Urgent", colour: "danger" as const, rank: 1 };
    const routine = { id: "p2", code: "RTN", name: "Routine", colour: "neutral" as const, rank: 3 };
    const rows = [
      order({ id: "wo-a", order_no: "WO-AAAA", priority: routine, due_at: "2026-01-01T00:00:00Z" }),
      order({ id: "wo-b", order_no: "WO-BBBB", priority: urgent, due_at: "2026-12-01T00:00:00Z" }),
      // No priority at all sorts LAST, never first: a job nobody set a priority
      // on is not more urgent than one somebody marked Urgent.
      order({ id: "wo-c", order_no: "WO-CCCC", priority: null, due_at: "2025-01-01T00:00:00Z" }),
    ];
    const html = renderOrders("account", "acc-1", rows);
    expect(html.indexOf("WO-BBBB")).toBeLessThan(html.indexOf("WO-AAAA"));
    expect(html.indexOf("WO-AAAA")).toBeLessThan(html.indexOf("WO-CCCC"));
    // The footer says so, in five words (B14 rule 33 — a FACT caps at six).
    expect(html).toContain("Sorted by priority, then due.");
    // ⚠ **AND NO COLUMN IS SORTABLE — ASSERTED AGAINST THE CLASS THE SHARED
    // TABLE ACTUALLY EMITS, AND PROVED DISCRIMINATING BY THE PROPERTY.** The
    // first draft of this line read `not.toContain("th-sort-btn")`, a string
    // `DataTable` has never written: a check that cannot fail (law 7's
    // *structurally incapable of failing*). `table-sort` is the class on the
    // `<button>` a sortable header wraps its label in, and the property host —
    // whose `Work` and `Booked` columns ARE sortable — is the control that
    // shows this assertion can go red.
    expect(html).not.toContain("table-sort");
    expect(renderOrders("premises", "prm-1408", rows)).toContain("table-sort");
  });

  it("TC-1b4: PRIORITY and RAISED BY are drawn, and each STATES its absence rather than going blank", () => {
    // ⚠ **BOTH COLUMNS EXISTED, WERE WRITTEN, AND REACHED ONLY THE DISPATCHER
    // UNTIL 2026-09-13.** `work_orders.priority_id` is stamped at the raise
    // (`BR-WRK-018`) and `work_orders.source` is the column whose own docstring
    // reads *"`Work-007` draws it as RAISED BY"*. A utility that has seeded no
    // priorities has nothing to show, and a BLANK cell there would read as
    // *ordinary* — a claim about how urgent somebody's job is.
    const filled = renderOrders("account", "acc-1", [
      order({
        priority: { id: "p1", code: "URG", name: "Urgent", colour: "danger" as const, rank: 1 },
        source: "move_out",
      }),
    ]);
    expect(filled).toContain('data-priority="URG"');
    expect(filled).toContain("Urgent");
    expect(filled).toContain('data-raised-by="move_out"');
    // B14 rule 31 — the translated NAME reaches the screen, never the token.
    expect(filled).toContain("Move-out");

    const bare = renderOrders("account", "acc-1", [order({ priority: null, source: null })]);
    expect(bare).toContain("Priority");
    expect(bare).toContain("Raised by");
    expect(bare).not.toContain('data-priority="');
    expect(bare).not.toContain('data-raised-by="');
  });

  it("TC-1c: WHERE is drawn from the row the API already served, not from the drawer", () => {
    // `unit_label` has been on the scoped row since wave O and was visible only
    // inside the opened drawer — *"Where, within the building, so a resident can
    // be told whether it is their flat."*
    const html = renderOrders("premises", "prm-1408", [order({ unit_label: "Laundry" })]);
    expect(html).toContain("Laundry");
    expect(html).toContain('data-order-where="wo-4901"');
    // A job standing on the address itself has no unit: an absence, drawn as
    // one, never a blank cell.
    const whole = renderOrders("premises", "prm-1408", [
      order({ id: "wo-5000", order_no: "WO-5000", unit_label: null }),
    ]);
    expect(whole).toContain("—");
  });

  it("TC-2: an address with no jobs says so and OFFERS TO RAISE WORK", () => {
    // B14 rule 17, and the blueprint's own STATES row: *"Says so, and offers to
    // raise work — an empty list here is good news and should read like it."*
    // It said *No jobs have been raised here.* and offered nothing at all.
    const html = renderOrders("premises", "prm-1408", []);
    expect(html).toContain("Nobody is due to visit");
    expect(html).toContain("Nothing is open here");
    expect(html).toContain("⚡ Raise work here");
  });

  it("TC-2b: the drawn PRIMARY ACTION opens the wizard that raises a job", () => {
    // Hard-won law 2's mirror: a control is only real if its door opens. The
    // address is asserted rather than the label, because a label proves nothing.
    // ⚠ CR-168 round 3 (`DEF-WRK-4752`): the door now CARRIES the property —
    // *"with the property already the subject"* — as `?premises=`, and an
    // account's door opens the raise filled from the account (image 19).
    const html = renderOrders("premises", "prm-1408", [order()]);
    expect(html).toContain(`href="/${TENANT}/work/orders/new?premises=prm-1408"`);
    expect(renderOrders("account", "acc-1", [order()])).toContain(
      `href="/${TENANT}/accounts/acc-1/work-orders/new"`,
    );
    expect(html).toContain("⚡ Raise work here");
  });

  it("TC-3: the drawer opens on the row, and Mark complete is refused with its reason", () => {
    const planned = order();
    expect(acceptBlockedReason(planned, t)).toBe("The field has not finished this.");
    const finished = order({
      state: "completed",
      completed_at: "2026-09-01T15:00:00Z",
      field_data: { serial: "M-4471" },
    });
    expect(acceptBlockedReason(finished, t)).toBeNull();
    expect(acceptBlockedReason({ ...finished, accepted_at: "2026-09-02T09:00:00Z" }, t)).toBe(
      "This job is already accepted.",
    );
    // Both refusals are inside B14 rule 33's cap.
    for (const sentence of ["The field has not finished this.", "This job is already accepted."]) {
      expect(sentence.split(/\s+/).length).toBeLessThanOrEqual(6);
    }

    const html = renderOrders("premises", "prm-1408", [finished], finished.id);
    expect(html).toContain('data-work-order-panel="wo-4901"');
    expect(html).toContain("M-4471"); // what the field sent, drawn
    // BR-MET-110 — a null acceptance on a completed order IS the review queue,
    // so it is a sentence rather than a dash.
    expect(html).toContain("Nobody has accepted this yet.");
  });

  it("TC-4: the gate flag rides on the ORDER it produced, with an accessible name", () => {
    const html = renderOrders("premises", "prm-1408", [order({ is_gate: true })]);
    expect(html).toContain("data-gate");
    expect(html).toContain("🚩");
    expect(html).toContain("the service goes live when it passes");
  });

  it("TC-5: an order with no number shows its type, never its database id", () => {
    // B14 rule 31 — and `?? ""` rather than `?? row.id`, which is what the
    // retired screen did.
    const html = renderOrders("premises", "prm-1408", [order({ order_no: null })]);
    expect(html).toContain("Meter set");
    expect(html).not.toContain("wo-4901<");
  });

  // ── CR-089 wave C · C6 (PUJ-16) ─────────────────────────────────────────
  //
  // Seven columns — Order · Service · Stands on · Mode · Outcome · State ·
  // Actions — and **not one of them a date or a name**. A person standing on a
  // property asking *when is somebody coming* got a state word.

  it("C6: an appointment window is drawn as the date and the hours a customer was promised", () => {
    const html = renderOrders("premises", "prm-1408", [
      order({
        window_start: "2026-09-10T13:00:00Z",
        window_end: "2026-09-10T17:00:00Z",
        technician: { kind: "person", name: "A. Reyes", slug: "a-reyes" },
      }),
    ]);
    // The drawn labels (blueprint page 33): `Booked` and `Crew`. The product
    // said `When` and `Who` — the same two facts under two other words.
    expect(html).toContain("Booked");
    expect(html).toContain("Crew");
    expect(html).toContain("09/10/2026");
    expect(html).toContain("A. Reyes");
    expect(html).toContain('data-when="window"');
  });

  it("C6: an SLA deadline is LABELLED, never printed as though it were an appointment", () => {
    // ⚠ THE TWO ARE DIFFERENT PROMISES TO DIFFERENT PEOPLE. `due_at` is
    // BR-WRK-018's internal deadline, stamped at the raise from the priority's
    // hours; a clerk who reads a bare date will say it down the phone.
    const html = renderOrders("premises", "prm-1408", [
      order({ due_at: "2026-09-12T17:00:00Z" }),
    ]);
    expect(html).toContain("Due by");
    expect(html).toContain("09/12/2026");
    expect(html).toContain('data-when="due"');
  });

  it("C6: nobody going and nothing scheduled are STATED, never blank cells", () => {
    const html = renderOrders("premises", "prm-1408", [order()]);
    expect(html).toContain("Not scheduled");
    expect(html).toContain("Nobody yet");
    expect(html).toContain('data-when="none"');
  });

  it("C6: a finished job answers in the past tense", () => {
    // *When is somebody coming* has a past tense, and a stale window on a
    // completed order would read as a promise still outstanding.
    //
    // ⚠ **ASSERTED ON THE CELL RATHER THAN THROUGH THE TAB, AND THE REASON IS
    // THE DRAWN `OPEN` CHIP.** A completed order is behind that filter on
    // arrival, so a tab render would be asserting the past tense over a row
    // that is not on screen — a test named after a claim it does not make.
    // `OrderWhenCell` is where the past tense lives, and it is exported.
    const html = renderToStaticMarkup(
      <OrderWhenCell
        order={order({
          state: "completed",
          completed_at: "2026-09-04T15:20:00Z",
          window_start: "2026-09-04T13:00:00Z",
        })}
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
      />,
    );
    expect(html).toContain("Done");
    expect(html).toContain("09/04/2026");
    expect(html).toContain('data-when="completed"');
  });

  it("C6: `open` is a GROUPING of three states, and `done` is its complement", () => {
    // The drawn chip is `OPEN` and `work_orders` has five states, so the chip
    // is a grouping rather than one of them. Declared once, asserted here, so
    // the chip, the option list and the footer count cannot come to disagree.
    expect(OPEN_ORDER_STATES).toEqual(["planned", "in_progress", "blocked"]);
    for (const state of ["planned", "in_progress", "blocked"]) {
      expect(isOpenOrder(order({ state: state as ScopedWorkOrderRow["state"] }))).toBe(true);
    }
    for (const state of ["completed", "cancelled"]) {
      expect(isOpenOrder(order({ state: state as ScopedWorkOrderRow["state"] }))).toBe(false);
    }
  });

  it("C6: the soonest visit sorts first and an unbooked job sorts LAST", () => {
    // *Is anybody due to visit* is a question about the next date, and floating
    // an absence to the top of a list ordered by date would read as *this one
    // is next*.
    const booked = order({ id: "a", window_start: "2026-09-11T08:00:00Z" });
    const later = order({ id: "b", window_start: "2026-09-20T08:00:00Z" });
    const never = order({ id: "c", window_start: null, due_at: null });
    const ordered = [never, later, booked]
      .sort((x, y) => compareWorkOrders(x, y, "booked", "asc"))
      .map((row) => row.id);
    expect(ordered).toEqual(["a", "b", "c"]);
  });

  it("C6: the search box matches what the row SHOWS and nothing it does not", () => {
    const row = order({ unit_label: "Laundry", technician: { kind: "person", name: "K. Osei", slug: "k-osei" } });
    expect(workOrderMatches(row, "laundry")).toBe(true);
    expect(workOrderMatches(row, "osei")).toBe(true);
    expect(workOrderMatches(row, "WO-4901")).toBe(true);
    expect(workOrderMatches(row, "meter set")).toBe(true);
    // The id is never on screen, so it is never searchable either (B14 rule 31).
    expect(workOrderMatches(row, "wo-4901".toUpperCase())).toBe(true);
    expect(workOrderMatches(row, "corridor")).toBe(false);
  });
});

describe("CR-070 wave O — one destination: where a build is reached", () => {
  it("the CONNECTION cell keeps its words and moves its link to the build's home", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={[`/${TENANT}/work/awaiting-approval`]}>
        <ConnectionCell
          connection={{ connection_no: "CON-26-0117", home: { kind: "premises", id: "prm-1408" } }}
        />
      </MemoryRouter>,
    );
    // The TEXT did not change — `CON-26-0117` is what a clerk quotes down a
    // phone, so B14 rule 31 is satisfied.
    expect(html).toContain("CON-26-0117");
    expect(html).toContain(`href="/${TENANT}/premises/prm-1408?tab=build"`);
    // The retired destination, asserted absent BY NAME. G93 is the repo-wide
    // form of this check.
    expect(html).not.toContain("/connections/");
  });

  it("a build with no home draws its number as text rather than as a link to nowhere", () => {
    // A link that silently goes nowhere passes every test in this repo (law 6),
    // which is exactly what wave O exists to stop.
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={[`/${TENANT}/work/orders`]}>
        <ConnectionCell connection={{ connection_no: "CON-26-0199", home: null }} />
      </MemoryRouter>,
    );
    expect(html).toContain("CON-26-0199");
    expect(html).not.toContain("<a ");
  });

  it("an order with no build draws a dash, never a blank cell", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={[`/${TENANT}/work/orders`]}>
        <ConnectionCell connection={null} />
      </MemoryRouter>,
    );
    expect(html).toContain("—");
  });

  it("ONE function says where a build lives, and the two hosts differ by their tab", () => {
    expect(buildHomePath({ kind: "premises", id: "prm-1408" })).toBe("/premises/prm-1408?tab=build");
    expect(buildHomePath({ kind: "account", id: "acc-9" })).toBe("/accounts/acc-9?tab=work");
    // The drawer lands on the ORDERS tab of whichever host, because that is
    // where the list the drawer sits over lives.
    expect(buildOrderPath({ kind: "premises", id: "prm-1408" }, "wo-4901")).toBe(
      "/premises/prm-1408?tab=work-orders&order=wo-4901",
    );
    expect(buildOrderPath({ kind: "account", id: "acc-9" }, "wo-4901")).toBe(
      "/accounts/acc-9?tab=work&order=wo-4901",
    );
  });
});
