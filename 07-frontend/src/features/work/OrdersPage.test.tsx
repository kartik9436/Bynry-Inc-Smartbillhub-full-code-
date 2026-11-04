// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-024 (the dispatch columns, the third axis) · US-WRK-026
//           (six filters and no seventh) · US-WRK-027 (bulk acts, per order) ·
//           US-WRK-011 (the Area chip is tenancy's own list) · US-WRK-004
//           (the list, wave A) · US-WRK-001 TC-1 (no connection → a dash)
//           Screens: Work-007 at TEMPLATE W2
// Rules:    BR-WRK-006 · BR-WRK-018 · BR-WRK-023 · BR-WRK-024 · BR-WRK-026 ·
//           BR-WRK-027 · B14 rules 2 · 15 · 17 · 19 · 20 · 31 · 32 · 33 ·
//           hard-won law 2 (built is not wired, and its MIRROR: a hold that
//           has stopped being true)
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import { SCREEN_ROUTES } from "@/routing/screenIds";

import {
  ORDERS_HELD_CONTROLS,
  OrdersPage,
  WORK_ORDERS_SCREEN,
  dispatchStateTone,
  workOrderOutcomeTone,
  workOrderStateTone,
  workOrdersTableConfig,
} from "./OrdersPage";
import { mergeAcross } from "./candidateAdvice";
// ⚠ THE ROUTE CONSTANTS THEMSELVES, not the screen registry — see the case at
// the bottom of the holds block for why the difference is the whole point.
import { NEW_ORDER_WIZARD_ROUTE } from "./NewOrderWizard";
import { WORK_ORDER_DETAIL_ROUTE } from "./OrderDetailPage";
import {
  WORK_AWAITING_APPROVAL_ROUTE,
  WORK_CREWS_ROUTE,
  WORK_MAP_ROUTE,
  WORK_ORDERS_ROUTE,
  WORK_ORDER_EDIT_ROUTE,
  WORK_ORDER_TEMPLATES_ROUTE,
  WORK_PARTS_ROUTE,
  WORK_ROUTE,
} from "./WorkShell";
import { WORK_ORDER_DISPATCH_STATES, WORK_ORDER_FILTERS, WORK_ORDER_SOURCES } from "./workEndpoints";
import type { WorkKpis, WorkOrderDispatchRow, WorkOrderList } from "./workEndpoints";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** Work-007's own rows, as `apps/work/dispatch._dispatch_row` shapes them. */
function row(over: Partial<WorkOrderDispatchRow> = {}): WorkOrderDispatchRow {
  return {
    id: "wo-4901",
    order_no: "WO-4901",
    type: "Meter set",
    premise: { id: "p-1", premise_no: "P-00117", address: "500 Main St" },
    service: "electric",
    state: "planned",
    outcome: null,
    mode: "our_crew",
    is_gate: false,
    connection: {
      id: "con-0117",
      connection_no: "CON-26-0117",
      home: { kind: "premises", id: "p-1" },
    },
    account: null,
    raised_at: "2026-09-03T12:00:00Z",
    priority: { id: "pr-3", code: "NORMAL", name: "Normal", colour: "info", rank: 3 },
    technician: { kind: "person", name: "D. Ortiz", slug: "d-ortiz" },
    due_at: "2099-01-01T15:30:00Z",
    window_start: null,
    window_end: null,
    dispatch_state: "scheduled",
    source: "dispatcher",
    source_ref: null,
    area: { id: "ar-1", code: "N", name: "North" },
    ...over,
  };
}

/** The drawing's own overdue, unassigned, HIGH-priority leak with no build. */
const LEAK = row({
  id: "wo-4823",
  order_no: "WO-4823",
  type: "Leak investigation",
  premise: { id: "p-2", premise_no: "P-00891", address: "77 Cedar Ct" },
  service: "water",
  connection: null,
  account: { id: "a-10891", account_no: "A-10891" },
  priority: { id: "pr-2", code: "HIGH", name: "High", colour: "warning", rank: 2 },
  technician: null,
  dispatch_state: "queued",
  due_at: "2026-09-03T09:00:00Z",
  source: "high_usage_alert",
});

/** `Work-007`'s own figures: 4 · 5 · 2 · 3 · 1. */
const KPIS: WorkKpis = {
  open_total: 10,
  unassigned: { count: 4 },
  due_today: { count: 5, urgent: 2 },
  in_field: { count: 2 },
  awaiting_approval: { count: 3 },
  overdue: { count: 1, worst: { order_no: "WO-4823", days: 2 } },
};

function list(rows: WorkOrderDispatchRow[]): WorkOrderList {
  return { count: rows.length, next: null, previous: null, results: rows };
}

function seeded(data: WorkOrderList | null, kpis: WorkKpis | null = KPIS): QueryClient {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: data !== null } },
  });
  if (data !== null) {
    queryClient.setQueryData(queryKeys.workOrders("", 1, DEFAULT_PAGE_SIZE, {}), data);
  }
  if (kpis !== null) {
    queryClient.setQueryData(queryKeys.workKpis(), kpis);
  }
  queryClient.setQueryData(queryKeys.workAreas(), [
    { id: "ar-1", code: "N", name: "North" },
    { id: "ar-2", code: "R1", name: "Route 1" },
  ]);
  return queryClient;
}

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT BARE IN A `MemoryRouter`.**
 * Hard-won law 2's fixture clause: the portal front page's own test mounted its
 * component with no matching route, so `useParams().tenant` was `undefined` and
 * every address it built came out `//portal/…` — a protocol-relative URL to
 * another host, which reads as a perfectly good string to `toContain`. A
 * fixture that cannot tell a working link from a broken one is how six dead
 * doors shipped.
 */
function markup(data: WorkOrderList | null, kpis: WorkKpis | null = KPIS): string {
  return renderToStaticMarkup(
    <QueryClientProvider client={seeded(data, kpis)}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/orders`]}>
          <Routes>
            <Route path="/:tenant/work/orders" element={<OrdersPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

const CELLS = {
  select: () => null,
  // CR-070 wave H — the 👁 wave G held. The fixture declares it so the config
  // contract stays complete; the column's PRESENCE is asserted below.
  actions: () => null,
  premise: () => null,
  priority: () => null,
  technician: () => null,
  due: () => null,
  status: () => null,
  raisedBy: () => null,
  state: () => null,
  outcome: () => null,
  connection: () => null,
};

describe("US-WRK-024/026/027/011 — the dispatcher (Work-007, template W2)", () => {
  it("draws the head and the drawing's TEN default columns, keeping wave A's three on offer", () => {
    const html = markup(list([row(), LEAK]));
    expect(html).toContain("Work orders");
    expect(html).toContain(
      escapeHtml("Everything open, across every connection and every account."),
    );
    const config = workOrdersTableConfig(t, CELLS, []);
    expect(config.screenId).toBe(WORK_ORDERS_SCREEN);
    // `Work-007`'s ten, in the drawing's order, checkbox first — and, since
    // CR-070 wave H, the ACTIONS column carrying B14 rule 15's 👁. The drawing
    // puts row actions at the right of every table it draws; wave G left the
    // column out because there was no screen to open, and it opens `Work-008`.
    expect(config.columns.filter((c) => c.defaultVisible !== false).map((c) => c.key)).toEqual([
      "select",
      "order_no",
      "type",
      "premise",
      "service",
      "priority",
      "technician",
      "due",
      "dispatch_state",
      "source",
      "actions",
    ]);
    // ⚠ NOTHING WAS DELETED. STATE, OUTCOME and CONNECTION are still declared
    // and still served; they are off by default because the drawing draws ten,
    // and the `Columns ▾` control the drawing also puts on this card is exactly
    // what a dispatcher ticks them back on with.
    expect(config.columns.filter((c) => c.defaultVisible === false).map((c) => c.key)).toEqual([
      "state",
      "outcome",
      "connection",
    ]);
    // B14 rule 33 — a column label is a NAME of at most three words.
    for (const column of config.columns) {
      expect(column.label.split(/\s+/).length).toBeLessThanOrEqual(3);
    }
    expect(config.searchPlaceholder).toBe("work.orders.search");
    expect(i18n.exists("work.orders.search")).toBe(true);
  });

  it("BR-WRK-026: exactly SIX filters — the search and five chips — and there is no seventh", () => {
    // The rule counts SIX including the search box. The chips are the other
    // five, and this asserts the declaration rather than counting things on a
    // screen, so a sixth chip added later fails here rather than at a `400`
    // some dispatcher hits.
    expect(WORK_ORDER_FILTERS).toEqual([
      "q",
      "type",
      "status",
      "priority",
      "technician",
      "area",
    ]);
    expect(WORK_ORDER_FILTERS).toHaveLength(6);
    const config = workOrdersTableConfig(t, CELLS, [
      { name: "type", label: "Type", options: [] },
      { name: "status", label: "Status", options: [] },
      { name: "priority", label: "Priority", options: [] },
      { name: "technician", label: "Technician", options: [] },
      { name: "area", label: "Area", options: [] },
    ]);
    expect((config.filters ?? []).map((f) => f.name)).toEqual(
      WORK_ORDER_FILTERS.filter((name) => name !== "q"),
    );
  });

  it("US-WRK-011: the Area chip's options are the utility's own areas, read from tenancy", () => {
    const html = markup(list([row()]));
    expect(html).toContain("North");
    expect(html).toContain("Route 1");
  });

  it("draws the five tiles with the drawing's figures — 4 · 5 · 2 · 3 · 1 — and their sub-lines", () => {
    const html = markup(list([row(), LEAK]));
    for (const label of [
      "Unassigned",
      "Due today",
      "In the field",
      "Awaiting approval",
      "Overdue",
    ]) {
      expect(html).toContain(label);
    }
    expect(html).toContain("Nobody is going");
    expect(html).toContain("2 of them urgent"); // the plural form, from i18next
    expect(html).toContain("En route or on site");
    expect(html).toContain("Field done, nobody accepted");
    expect(html).toContain(escapeHtml("WO-4823 · 2 days")); // the worst one, NAMED
  });

  it("the tiles count over the UTILITY and the footer says 8 of 10 — never the page's own length", () => {
    // ⚠ A tile that changed when somebody typed in the search box would be a
    // fact about the search box. The denominator comes from `/work/kpis`.
    const html = markup(list([row(), LEAK]));
    expect(html).toContain(escapeHtml("Showing 2 of 10 open orders"));
    expect(html).toContain(escapeHtml("sorted by priority then due time"));
  });

  it("WO-4823 reads Unassigned in the danger tone and High in the warning tone", () => {
    const html = markup(list([LEAK]));
    expect(html).toContain("Unassigned");
    expect(html).toContain("High");
    // The pill takes the TENANT's own colour token — this screen invents none.
    const config = workOrdersTableConfig(t, CELLS, []);
    expect(config.columns.some((c) => c.key === "priority")).toBe(true);
  });

  it("BR-WRK-024: RAISED BY renders a WORD for all fourteen sources, never the raw token", () => {
    for (const source of WORK_ORDER_SOURCES) {
      const key = `work.orders.source.${source}`;
      expect(i18n.exists(key)).toBe(true);
      expect(t(key)).not.toBe(key); // DEF-322: a dotted key on a clerk's screen
    }
    const html = markup(list([LEAK]));
    expect(html).toContain("High-usage alert");
    expect(html).not.toContain("high_usage_alert");
  });

  it("BR-WRK-023: the third axis has seven words of its own, and shares none of its tones by accident", () => {
    for (const state of WORK_ORDER_DISPATCH_STATES) {
      expect(i18n.exists(`work.orders.dispatch.${state}`)).toBe(true);
    }
    expect(dispatchStateTone("queued")).toBe("neutral");
    expect(dispatchStateTone("scheduled")).toBe("success");
    expect(dispatchStateTone("en_route")).toBe("info");
    expect(dispatchStateTone("on_site")).toBe("info");
    expect(dispatchStateTone("on_hold")).toBe("warning");
    // ⚠ The two axes share the words `cancelled` and `complete`/`completed` and
    // mean different things by them, which is why they have separate mappings.
    expect(workOrderStateTone("completed")).toBe("success");
    expect(dispatchStateTone("complete")).toBe("muted");
    expect(workOrderOutcomeTone("passed")).toBe("success");
  });

  it("US-WRK-001 TC-1: a row with no connection draws a dash, and one with a build links to its home", () => {
    // CONNECTION is off by default now, so the cell is asserted through the
    // config rather than through the default markup — the column still exists
    // and still renders the shared cell.
    const config = workOrdersTableConfig(t, CELLS, []);
    const connection = config.columns.find((c) => c.key === "connection");
    expect(connection?.defaultVisible).toBe(false);
    expect(connection?.cell).toBeDefined();
  });

  it("B14 rule 31/32: no id, no rule number and no prose in a cell reaches the clerk", () => {
    const html = markup(list([row(), LEAK]));
    const visible = html.replace(/<[^>]*>/g, " ");
    expect(visible).not.toMatch(
      /\bBR-[A-Z]{3}-\d+|\bOQ-(?:[A-Z]{3}-)?\d+|\bDEF-(?:[A-Z]{3}-)?\d+|\bWork-0\d\d\b|\bWS-\d\d\b/,
    );
    expect(visible).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
    const body = html.slice(html.indexOf("<tbody"), html.indexOf("</tbody>"));
    // ⚠ **`"<p"` MATCHED `<path>` AND THIS ASSERTION WENT RED OVER A CORRECT
    // SCREEN (CR-070 wave H, 2026-09-05).** The rule being asserted is *no
    // PROSE in a cell* — a `<p>` paragraph. Wave H added B14 rule 15's 👁 to
    // the ACTIONS column, the icon is an inline `<svg>`, and every icon in
    // `components/icons.tsx` draws with `<path d="…">`. So the substring test
    // failed on a glyph, which is a check that cannot tell a paragraph from a
    // vector — CLAUDE.md law 11's *a check whose output cannot distinguish
    // pass from fail is worse than no check*, in miniature.
    //
    // The tag, not the prefix: `<p>` or `<p ` followed by a non-letter. A
    // paragraph is `<p>` or `<p class=…`; `<path` and `<polyline` are not.
    expect(body).not.toMatch(/<p(?![a-z])/);
    expect(html).not.toMatch(/>\s*null\b/);
  });

  it("B14 rule 17: the empty state says what is missing, and its button now GOES somewhere", () => {
    const html = markup(list([]));
    expect(html).toContain("No open orders");
    expect(html).toContain("Raised jobs appear here.");
    // ⚠ **THIS CASE USED TO ASSERT THE REFUSAL AND NOW ASSERTS THE OPPOSITE,
    // AND THAT IS THE MIRROR CLAUSE PAYING OUT (CR-070 wave H).** It read
    // `expect(html).toContain("Not from this screen yet.")` beside
    // `toContain("disabled")`, which was correct for exactly as long as there
    // was no wizard to open. Wave H landed `/:tenant/work/orders/new`, the
    // case went red, and the control is live.
    //
    // `DEF-CWP-3925` is what the other outcome costs: a greyed button with a
    // stale sentence over a screen that shipped days earlier, invisible to
    // `tsc`, to 391 test cases and to every gate. So the assertion is
    // INVERTED rather than deleted — it now fails if anybody re-disables the
    // control or puts the sentence back.
    expect(html).not.toContain("Not from this screen yet.");
    expect(html).toContain("+ New work order");
    const cta = html.slice(html.indexOf("state-empty"));
    expect(cta.slice(0, cta.indexOf("</button>"))).not.toContain("disabled=");
  });

  it("the bulk row is not drawn until something is ticked — an empty action bar is furniture", () => {
    const html = markup(list([row(), LEAK]));
    expect(html).not.toContain("data-bulk-bar");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// HARD-WON LAW 2's MIRROR — a hold that has stopped being true
// ══════════════════════════════════════════════════════════════════════════
//
// `DEF-CWP-3925`: the portal front page had TWO working doors out of eight;
// five cards and the sign-in bar were still refusing over screens that had
// shipped days earlier, with `tsc`, 391 cases and every gate green. The
// mechanism is a rule with a clock in it — correct the day it is written, rotten
// the day the screen arrives, because landing a screen and releasing the control
// that pointed at it are two acts and only the first feels like the work.
//
// `G103` owns this question for the customer portal and reads its `holds.ts`.
// **Nothing reads a STAFF hold.** These two cases are this screen's own version,
// and they go RED the day wave H registers either address.
describe("the holds this screen draws name what would release them", () => {
  // ⚠ **WAVE H LANDED AND THIS BLOCK WENT RED, WHICH IS THE ONLY REASON IT
  // EXISTS.** It used to hold two cases: *every held control declares the
  // address that releases it* and *FIRES WHEN WAVE H LANDS: no held address is
  // in the screen registry yet*. Wave H registered `/:tenant/work/orders/new`
  // and `/:tenant/work/orders/:orderNo`, the second case failed and named both
  // controls, and both are live on the screen now.
  //
  // The cases are REWRITTEN rather than deleted, and the rewrite is the point:
  // the list stays, empty, and these assertions now guard the OTHER direction —
  // that nothing has quietly been added back without an expiry test, and that
  // the two doors wave G held are really open.

  it("nothing on this screen refuses over an unbuilt address any more", () => {
    // An empty list is a STATEMENT: this screen holds nothing back. A lane
    // adding the next hold puts it here and inherits the expiry case below
    // instead of writing one from scratch — which is what nobody does.
    for (const hold of ORDERS_HELD_CONTROLS) {
      const entry: { releasedBy: string; reasonKey: string | null; control: string } = hold;
      expect(entry.releasedBy).toMatch(/^\/:tenant\//);
      if (entry.reasonKey !== null) {
        expect(i18n.exists(entry.reasonKey)).toBe(true);
      }
    }
  });

  it("FIRES WHEN A HOLD EXPIRES: no held address is a registered screen", () => {
    const registered = new Set(SCREEN_ROUTES.map((entry) => entry.path));
    for (const hold of ORDERS_HELD_CONTROLS) {
      const entry: { releasedBy: string; control: string } = hold;
      expect(
        registered.has(entry.releasedBy),
        `${entry.control} still refuses over ${entry.releasedBy}, which is now a registered ` +
          "screen — release the control in the commit that landed it (hard-won law 2's mirror clause)",
      ).toBe(false);
    }
  });

  // ══════════════════════════════════════════════════════════════════════
  // ⚠ **A REGISTRY ENTRY IS NOT A DOOR, AND EVERY CASE ABOVE KEYS ON THE
  // REGISTRY — WHICH IS EXACTLY WHAT `DEF-WRK-4051` WENT THROUGH.**
  // ══════════════════════════════════════════════════════════════════════
  //
  // Wave G's hold test asserted its addresses against `SCREEN_ROUTES`. Wave H
  // registered both, the test went red, and both controls were released — the
  // mechanism worked exactly as designed. **And for a while afterwards both
  // doors opened onto *"This screen is not built yet"*.**
  //
  // The route constants had been written `"/:tenant/work/orders/new"` and
  // `"/:tenant/work/orders/:orderNo"`, carrying their own `:tenant`. `App.tsx`
  // mounts every Work route as `ROUTE.slice(1)` **under a route that is
  // already `:tenant`**, so both came out `:tenant/:tenant/work/orders/…`,
  // matched nothing, and fell through to the not-built-yet screen.
  //
  // **The registry was right and the mount was wrong, and nothing compared
  // them.** So the hold-expiry test — the thing written to stop a refusal
  // rotting — could not tell a reachable screen from an unreachable one, and
  // it forced a release on that evidence. That is `DEF-CWP-3925`'s lesson one
  // level up: a check that cannot fail is worse than no check, because it is
  // trusted.
  //
  // These two cases close it. The first is the general invariant and would
  // have caught `DEF-WRK-4051` on the commit that introduced it; the second
  // ties the two addresses this screen actually released to the routes that
  // actually mount them.
  it("DEF-WRK-4051: no Work route constant carries its own :tenant", () => {
    const routes: [string, string][] = [
      ["WORK_ROUTE", WORK_ROUTE],
      ["WORK_ORDERS_ROUTE", WORK_ORDERS_ROUTE],
      ["WORK_ORDER_DETAIL_ROUTE", WORK_ORDER_DETAIL_ROUTE],
      ["NEW_ORDER_WIZARD_ROUTE", NEW_ORDER_WIZARD_ROUTE],
      ["WORK_ORDER_EDIT_ROUTE", WORK_ORDER_EDIT_ROUTE],
      ["WORK_MAP_ROUTE", WORK_MAP_ROUTE],
      ["WORK_AWAITING_APPROVAL_ROUTE", WORK_AWAITING_APPROVAL_ROUTE],
      ["WORK_CREWS_ROUTE", WORK_CREWS_ROUTE],
      ["WORK_PARTS_ROUTE", WORK_PARTS_ROUTE],
      ["WORK_ORDER_TEMPLATES_ROUTE", WORK_ORDER_TEMPLATES_ROUTE],
    ];
    // ⚠ **NINE OF THE THIRTEEN, AND THE SCOPE IS STATED RATHER THAN IMPLIED.**
    // `WORK_TECHNICIAN_ROUTE`, `WORK_TEMPLATE_NEW_ROUTE` and
    // `WORK_TEMPLATE_DETAIL_ROUTE` live in three other page modules, and
    // importing three more components into this file would tie the dispatcher's
    // suite to three screens other lanes are editing today — a red import there
    // would fail this file for a reason that has nothing to do with this
    // screen. The nine here include BOTH routes `DEF-WRK-4051` actually broke.
    // A gate reading the source is the right home for all thirteen.
    for (const [name, route] of routes) {
      expect(
        route.startsWith("/:tenant"),
        `${name} is "${route}" — App.tsx mounts it as ROUTE.slice(1) under a route that is ` +
          "already :tenant, so this one mounts at :tenant/:tenant/… and matches nothing. The " +
          "screen renders 'not built yet' and every registry-based check stays green over it.",
      ).toBe(false);
      expect(route.startsWith("/work")).toBe(true);
    }
  });

  it("the registry and the MOUNT agree for the two doors this screen released", () => {
    // ⚠ THE COMPARISON NOTHING WAS MAKING. A registered path proves a screen
    // has an entry; `"/:tenant" + ROUTE` is where the app will actually look
    // for it. When those two disagree the door is dead, and this is the only
    // assertion in the file that can see it.
    const registered = new Set(SCREEN_ROUTES.map((entry) => entry.path));
    for (const [name, route] of [
      ["NEW_ORDER_WIZARD_ROUTE", NEW_ORDER_WIZARD_ROUTE],
      ["WORK_ORDER_DETAIL_ROUTE", WORK_ORDER_DETAIL_ROUTE],
    ] as [string, string][]) {
      expect(
        registered.has(`/:tenant${route}`),
        `${name} mounts at "/:tenant${route}" and the screen registry does not list that path — ` +
          "one of the two is wrong, and the door is dead either way (DEF-WRK-4051)",
      ).toBe(true);
    }
  });

  it("the two doors wave G held are open: both addresses are registered", () => {
    // The MIRROR of the case above, and it is the half `DEF-CWP-3925` was
    // missing: nothing asked whether a door had started pointing at something.
    // If a later lane unmounts either route, this fails and says which.
    const registered = new Set(SCREEN_ROUTES.map((entry) => entry.path));
    expect(registered.has("/:tenant/work/orders/new")).toBe(true);
    expect(registered.has("/:tenant/work/orders/:orderNo")).toBe(true);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// BR-WRK-027 — the bulk act, and what the picker is allowed to offer
// ══════════════════════════════════════════════════════════════════════════
describe("BR-WRK-027 — ticking rows and driving them", () => {
  it("ruling 2 (BR-WRK-029 SUPERSEDED 2026-09-23): the bulk picker offers the UNION, with advice", () => {
    // ⚠ This case asserted the INTERSECTION until CR-168 round 3 (lane ASSIGN):
    // only the people eligible for every ticked order were offered. The PO
    // ruled the match ADVISES and never blocks, so a name missing the skill on
    // one order is OFFERED and the advice says so — an intersection would be
    // the retired refusal moved to the screen.
    const advice = (has_skill: boolean) => ({
      skill: { name: "Backflow" },
      has_skill,
      area_match: false,
      off_that_day: false,
      jobs_that_day: null,
      certifications_lapsed: [],
    });
    const ortiz = { kind: "person", id: "t-1", name: "D. Ortiz", best_fit: true, advice: advice(true) };
    const patel = { kind: "person", id: "t-2", name: "R. Patel", best_fit: false, advice: advice(true) };
    const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results }) as never;
    const merged = mergeAcross([page([ortiz, patel]), page([ortiz, { ...patel, advice: advice(false) }])]);
    expect(merged.map((c) => c.name)).toEqual(["D. Ortiz", "R. Patel"]);
    expect(merged[1].advice.has_skill).toBe(false);
    expect(mergeAcross([])).toEqual([]);
  });

  it("ticking two rows opens the bulk row and posts ONE call with BOTH ids", async () => {
    const posted: { path: string; body: unknown }[] = [];
    // ⚠ **THIS CLIENT ANSWERS EACH PATH WITH ITS OWN SHAPE AND REFUSES ANYTHING
    // ELSE.** The first draft answered every GET with a list envelope, so
    // `/work/kpis` came back as `{count,next,previous,results}` and the strip
    // crashed on `kpis.unassigned` — which is the hard-won-law-2 fixture
    // hazard from the other side: a fixture loose enough to answer a call it
    // does not understand cannot tell a working screen from a broken one.
    const empty = { count: 0, next: null, previous: null, results: [] };
    const client = {
      get: async (path: string) => {
        if (path === "/work/kpis") {
          return { status: 200, data: KPIS } as ApiResponse<unknown>;
        }
        if (path === "/work/areas") {
          return { status: 200, data: { results: [] } } as ApiResponse<unknown>;
        }
        if (path === "/work/crews") {
          return {
            status: 200,
            data: { ...empty, counts: { rows: 0, people: 0, crews: 0, contractors: 0 } },
          } as ApiResponse<unknown>;
        }
        if (path === "/work-orders") {
          // The seeded cache is refetched immediately (staleTime 0), so the
          // CLIENT is what the screen ends up drawing — seeding alone would
          // have this test asserting over an empty table.
          return { status: 200, data: list([row(), LEAK]) } as ApiResponse<unknown>;
        }
        if (path.startsWith("/lookups/work_")) {
          return { status: 200, data: empty } as ApiResponse<unknown>;
        }
        throw new Error(`unexpected call: ${path}`);
      },
      post: async (path: string, body: unknown) => {
        posted.push({ path, body });
        return {
          status: 200,
          data: {
            act: "priority",
            results: [
              { id: "wo-4901", ok: true },
              { id: "wo-4823", ok: true },
            ],
            done: 2,
            failed: 0,
          },
        } as ApiResponse<unknown>;
      },
    } as unknown as ApiClient;

    const queryClient = seeded(list([row(), LEAK]));
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/work/orders`]}>
            <Routes>
              <Route path="/:tenant/work/orders" element={<OrdersPage client={client} />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

    // ⚠ BY LABEL, NOT BY POSITION. `findAllByRole("checkbox")[0]` picked up the
    // `Columns ▾` chooser's own boxes, which is the kind of fixture that passes
    // for the wrong reason. Each row's box names its ORDER (B14 rule 31 — the
    // number, never the id), so the test asks for the rows it means.
    // ⚠ **WAIT FOR THE SCREEN TO SETTLE BEFORE TOUCHING IT.** Five queries feed
    // this page and each one that resolves re-renders it. A first version
    // clicked as soon as the boxes existed, and the tick landed mid-flight and
    // was lost — the bar read *1 order ticked* over two ticked boxes. That is a
    // fixture testing a screen that is still assembling itself, and the honest
    // fix is to wait rather than to weaken the assertion.
    // ⚠ **WAIT FOR QUIESCENCE, NOT FOR THE ELEMENT — AND THIS COST AN HOUR.**
    // Five queries feed this screen. A fixture that waits only until the
    // checkbox EXISTS resolves a node, yields to the event loop on the next
    // `await`, and a settling query re-renders the table and replaces that
    // node — so the click lands on a detached element and `onChange` never
    // fires. The symptom is silent and looks exactly like an application bug:
    // two boxes ticked, the bar reading *1 order ticked*, and a trace showing
    // the first `setSelected` was never called at all.
    await waitFor(() => {
      if (queryClient.isFetching() !== 0) throw new Error("still fetching");
      if (screen.queryByText("500 Main St") === null) throw new Error("rows not in yet");
    });
    await userEvent.click(await screen.findByLabelText("Select WO-4901"));
    await userEvent.click(await screen.findByLabelText("Select WO-4823"));
    // The bar appears only now, and it counts what is ticked.
    // ⚠ **TWO TICKS MUST MAKE TWO, AND THIS IS THE ASSERTION THAT FOUND THE
    // BUG.** The first version of the checkbox read `selected` out of the
    // memoised config's closure, so the second tick REPLACED the first and the
    // bar read *1 order ticked* over two ticked boxes — a dispatcher ticking
    // three rows would have assigned one. Nothing static could see it.
    expect(await screen.findByText("2 orders selected")).toBeDefined();
    expect(screen.getByText("Assign selected…")).toBeDefined();
    expect(screen.getByText("Reschedule selected…")).toBeDefined();
    expect(screen.getByText("Change priority…")).toBeDefined();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-024/026/027/011 (EP-WRK-05) · US-WRK-004 · US-WRK-001 (EP-WRK-01) · 08-screen-layouts.md Work-007 · 10-execution-plan.md wave G tasks G3, G4
// generated: 2026-09-05 by the CR-070 wave G build lane (grown from the wave A file)
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST — dropping `defaultVisible: false` from the three wave A columns fails "the drawing's TEN default columns"; adding "/:tenant/work/orders/:orderNo" to SCREEN_IDS fails "FIRES WHEN WAVE H LANDS"; both quoted in the lane report
// exceptions: the assign modal's own submit is exercised through mergeAcross (cr168Assign.dom.test.tsx drives the dialog) rather than through a full jsdom form round trip — the picker's RULE is the thing BR-WRK-029 signs, and the per-order write is proved on the server where the savepoint lives
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

describe("record links (PO 2026-10-19) — the Orders list", () => {
  it("the account number beside the address opens the account", () => {
    const html = markup(list([row(), LEAK]));
    expect(html).toContain(`href="/${TENANT}/accounts/a-10891"`);
    expect(html).toContain(">A-10891</a>");
  });
});
