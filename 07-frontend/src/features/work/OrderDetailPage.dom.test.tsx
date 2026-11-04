// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-033 (the six-tab work order detail) · US-WRK-045 (the close
//           is `submit_field_result` and activates nothing).  Screen: Work-008
// Rules:    BR-MET-110 (marking complete sends for approval) · BR-WRK-037 (the
//           safety lock) · BR-WRK-025 (an assignment APPENDS) · B14 rules 6 ·
//           11 · 33 · BR-SHL-025 (the server enforces, whatever is drawn)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE ONE THING THIS FILE EXISTS TO ASSERT, AND WHICH NOTHING ELSE COULD.**
// `OrderDetailPage.test.tsx` renders to STATIC MARKUP, so it can see that a
// button is drawn and whether it is disabled — and it can never see whether
// pressing it reaches a server. That gap is exactly `DEF-CWP-3925`: four
// live-looking commits over a routed, tested, live screen, invisible to `tsc`,
// to 44 static cases and to every gate, because `G13` asks whether a PROP is
// passed and nothing asks whether a REFUSAL is still true.
//
// So each case below CLICKS the control and asserts the **path and the method**
// the client was asked for. A button wired to the wrong endpoint, or to none,
// fails here and nowhere else.
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (`/:tenant/work/orders/:orderNo`),
// never bare: `DEF-CWP-3925`'s second lesson is that a component mounted with
// no matching route has `useParams()` undefined, and every address it builds
// comes out `//…` — a protocol-relative URL to another host, which reads as a
// perfectly good string to `toContain`.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  ORDER_DETAIL_HELD_CONTROLS,
  ORDER_DETAIL_REASSIGN_OPENS,
  ORDER_DETAIL_WIRED_ENDPOINTS,
  OrderDetailPage,
} from "./OrderDetailPage";
import type { OrderChecklist } from "./workEndpoints";

const TENANT = "brazosbend";
const ID = "wo-4822";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

type Call = { method: string; path: string; body: unknown };

/** ⚠ **THE READS ARE NOISE HERE AND FILTERING THEM IS NOT A SHORTCUT.** The
 *  screen issues three GETs of its own on mount (the order, its checklist, its
 *  audit) and this file is about COMMITS. Counting everything would make
 *  "pressing Cancel sent nothing yet" read as three, and the assertion that
 *  matters would be untestable. */
const commits = (calls: Call[]): Call[] => calls.filter((c) => c.method !== "GET");

function fakeClient(calls: Call[], fail: string | null = null): ApiClient {
  const send = (method: string) => async (path: string, body?: unknown) => {
    calls.push({ method, path, body: body ?? null });
    if (fail !== null && path.endsWith(fail)) {
      // The server's OWN sentence, in the envelope the client hands on. The
      // screen must surface THIS, not a wording of its own (`BR-SHL-025`).
      throw { status: 409, data: { message: "Finish safety first." } };
    }
    // CR-168 P4.3 — the hold dialog reads the tenant's reasons (J1).
    if (method === "GET" && path === "/work/hold-reasons") {
      return {
        status: 200,
        data: [{ code: "PARTS", name: "Waiting for parts", active: true, rank: 1 }],
        etag: null,
        notModified: false,
      };
    }
    // ⚠ CR-168: a GET of the ORDER answers the open job the cache was seeded
    // with. It answered `state: "completed"` like every other call, so a
    // background refetch turned the page into its COMPLETED shape mid-case —
    // harmless while the page had one shape, wrong once it has two.
    if (method === "GET" && (path === `/work-orders/${ID}` || path.startsWith("/work-orders/by-number/"))) {
      return {
        status: 200,
        data: { id: ID, order_no: "WO-4822", type: "Meter exchange", state: "planned", dispatch_state: "scheduled", premise: null, account: null, priority: null, technician: null },
        etag: null,
        notModified: false,
      };
    }
    return { status: 200, data: { id: ID, state: "completed", dispatch_state: "on_hold" }, etag: null, notModified: false };
  };
  return {
    request: send("REQUEST"),
    get: send("GET"),
    post: send("POST"),
    put: send("PUT"),
    patch: send("PATCH"),
    del: send("DELETE"),
  } as unknown as ApiClient;
}

/** The order's own copies. `locked` is driven by the safety rows, exactly as
 *  the server derives it — never set independently, or the fixture could say
 *  *unlocked* over three untouched mandatory rows. */
function checklist(ticked: boolean): OrderChecklist {
  const rows = [1, 2, 3].map((seq) => ({
    id: `s${seq}`,
    seq,
    text: `Safety ${seq}`,
    is_mandatory: true,
    ticked_at: ticked ? "2026-03-15T15:15:00Z" : null,
  }));
  const outstanding = rows.filter((r) => r.is_mandatory && r.ticked_at === null);
  return {
    order_id: ID,
    order_no: "WO-4822",
    template: null,
    safety: rows,
    safety_lock: {
      locked: outstanding.length > 0,
      remaining: outstanding.length,
      first_outstanding: outstanding[0]?.text ?? null,
      ticked: rows.length - outstanding.length,
      total: rows.length,
      mandatory_total: rows.length,
    },
    tasks: [],
    tasks_total: 0,
    tasks_ticked: 0,
    tasks_est_minutes: 0,
    readings: [],
    materials: [],
    help: [],
    details: {
      access_notes: null,
      hazards: null,
      gate_code: null,
      show_account_summary: true,
      show_asset_card: false,
      show_access_notes: true,
      show_appointment: true,
    },
  } as unknown as OrderChecklist;
}

let where = "";

function Spy() {
  where = useLocation().pathname;
  return null;
}

function mount(client: ApiClient, ticked = true) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.workOrder(ID), {
    id: ID,
    order_no: "WO-4822",
    type: "Meter exchange",
    state: "planned",
    dispatch_state: "scheduled",
    premise: null,
    account: null,
    priority: null,
    // Image 03's job is D. Ortiz's. CR-168 round 3 (lane ASSIGN, P1.27): a job
    // NOBODY holds now reads *Assign…*, so the open-head cases below are
    // mounted on a held job, as drawn.
    technician: { kind: "person", name: "D. Ortiz", slug: "d-ortiz" },
  });
  queryClient.setQueryData(queryKeys.workOrderChecklist(ID), checklist(ticked));
  queryClient.setQueryData(queryKeys.workOrderAudit(ID), { order_no: "WO-4822", rows: [] });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/orders/${ID}?tab=overview`]}>
          <Spy />
          <Routes>
            <Route path="/:tenant/work/orders/:orderNo" element={<OrderDetailPage client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);
beforeEach(() => {
  where = "";
});

describe("Work-008 · the four actions REACH their endpoints (CR-070 wave L)", () => {
  // ⚠ **TWO CASES LEFT HERE WITH *Mark complete* (CR-168, ruling 18 — *"back
  // office cannot complete the job it can only accept it"*).** They proved the
  // button reached `POST …/field-result` and greyed under the safety lock. The
  // button is gone; `orderPage/orderPage.dom.test.tsx` proves this screen never
  // posts `field-result` on either shape.

  it("Put on hold… OPENS A DIALOG and posts the reason to /hold (CR-168 P4.3)", async () => {
    // ⚠ REWRITTEN BY CR-168. It asserted one press posted `{}` at once — the
    // defect image 10 draws over: an ellipsis promising a dialog that never
    // came, and a job held with no reason.
    const calls: Call[] = [];
    mount(fakeClient(calls));
    fireEvent.click(screen.getByText(t("work.order.actions.hold")));
    expect(commits(calls).length).toBe(0);
    await waitFor(() => expect(screen.getByText("Waiting for parts")).toBeTruthy());
    fireEvent.change(screen.getByLabelText(new RegExp(t("work.order.hold.reason"))), {
      target: { value: "PARTS" },
    });
    fireEvent.click(screen.getByRole("button", { name: t("work.order.hold.submit") }));
    await waitFor(() => expect(commits(calls).length).toBe(1));
    expect(commits(calls)[0]).toMatchObject({
      method: "POST",
      path: `/work-orders/${ID}/hold`,
      body: { reason_code: "PARTS" },
    });
  });

  it("Cancel order CONFIRMS FIRST and only then posts to /cancel (B14 rules 6, 11)", async () => {
    const calls: Call[] = [];
    mount(fakeClient(calls));
    fireEvent.click(screen.getByText(t("work.order.actions.cancel")));
    // ⚠ **NOTHING HAS BEEN SENT YET, AND THAT IS THE ASSERTION.** A destructive
    // commit that fired on the first click would pass a "does it reach its
    // endpoint" test perfectly and be worse than a dead button.
    expect(commits(calls).length).toBe(0);
    expect(screen.getByText(t("work.order.cancel.consequence"))).toBeTruthy();
    fireEvent.click(screen.getByText(t("work.order.cancel.confirm")));
    await waitFor(() => expect(commits(calls).length).toBe(1));
    expect(commits(calls)[0]).toMatchObject({ method: "POST", path: `/work-orders/${ID}/cancel` });
  });

  it("Reassign… opens Work-021, the screen that OWNS the picker", async () => {
    const calls: Call[] = [];
    mount(fakeClient(calls));
    fireEvent.click(screen.getByText(t("work.order.actions.reassign")));
    // A door, not a dead control, and not a second picker: `BR-WRK-026`'s
    // eligibility rules live on the edit screen and a copy here would be a
    // second place for them to be forgotten.
    // Asserted against the CONSTANT, so the button and the declared address
    // cannot drift apart — `DEF-WRK-4051`'s whole lesson.
    const expected = `/${TENANT}${ORDER_DETAIL_REASSIGN_OPENS.replace(":orderNo", ID)}`;
    await waitFor(() => expect(where).toBe(expected));
    expect(commits(calls).length).toBe(0);
  });

  it("a refusal shows the SERVER's own sentence, not a wording of ours", async () => {
    const calls: Call[] = [];
    mount(fakeClient(calls, "/cancel"));
    fireEvent.click(screen.getByText(t("work.order.actions.cancel")));
    fireEvent.click(screen.getByText(t("work.order.cancel.confirm")));
    await waitFor(() => expect(screen.queryByText("Finish safety first.")).toBeTruthy());
  });

  it("FIRES WHEN A HOLD EXPIRES: no control refuses over an endpoint this screen already calls", () => {
    // ⚠ **THE COMPARISON NOTHING WAS MAKING, and the reason `DEF-CWP-3925`
    // survived every check.** A hold is a rule with a CLOCK in it, and the day
    // the thing it waits for arrives it becomes a lie — but landing the thing
    // and releasing the control are two acts, and only the first feels like the
    // work. `ORDERS_HELD_CONTROLS`' version of this asks *is that ADDRESS
    // mounted*; a hold HERE names an ENDPOINT, so the equivalent question is
    // *does this screen already CALL it* — which is exactly the state all four
    // of wave H's entries were in from the day they were written.
    const wired = new Set<string>(ORDER_DETAIL_WIRED_ENDPOINTS);
    for (const hold of ORDER_DETAIL_HELD_CONTROLS) {
      expect(hold.releasedBy).toMatch(/^(GET|POST|PUT|PATCH|DELETE) \//);
      expect(i18n.exists(hold.reasonKey), `${hold.reasonKey} is not in the catalogue`).toBe(true);
      expect(
        wired.has(hold.releasedBy),
        `${hold.control} still refuses over "${hold.releasedBy}", which this screen ALREADY ` +
          "calls — release the control in the commit that wired it (hard-won law 2's mirror clause)",
      ).toBe(false);
    }
  });

  it("the wired list is the four paths the buttons are PROVED to reach", async () => {
    // Otherwise `ORDER_DETAIL_WIRED_ENDPOINTS` decays into a comment: a lane
    // could delete a handler and leave its entry, and the expiry case above
    // would go on trusting it.
    const calls: Call[] = [];
    mount(fakeClient(calls));
    fireEvent.click(screen.getByText(t("work.order.actions.cancel")));
    fireEvent.click(screen.getByText(t("work.order.cancel.confirm")));
    await waitFor(() => expect(commits(calls).length).toBe(1));
    const templated = commits(calls).map((c) => `${c.method} ${c.path.replace(ID, "{id}")}`);
    for (const path of templated) {
      expect(ORDER_DETAIL_WIRED_ENDPOINTS as readonly string[]).toContain(path);
    }
  });

  it("the four refusal strings are GONE from the catalogue, not just unused", () => {
    // ⚠ The precedent is `assets.flow.workR5`, deleted from all eleven
    // catalogues in the commit that made its control live. A refusal string for
    // a control that no longer refuses is stale copy a lane will later read as
    // a live hold — which is how `DEF-CWP-3925` stayed invisible for days.
    for (const key of [
      "work.order.held.markComplete",
      "work.order.held.reassign",
      "work.order.held.hold",
      "work.order.held.cancel",
    ]) {
      expect(i18n.exists(key), `${key} still exists in the catalogue`).toBe(false);
    }
  });
});


// ══════════════════════════════════════════════════════════════════════════
// THE CASES THAT WOULD HAVE CAUGHT `DEF-WRK-4518`, AND DID NOT EXIST
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **EVERY TEST OVER THIS SCREEN PRE-SEEDS THE CACHE OR ANSWERS 200 TO
// ANYTHING, SO NOT ONE OF THEM COULD SEE THAT THE ADDRESS WAS UNSERVEABLE.**
// `OrderDetailPage.test.tsx` puts the order straight into the query cache;
// `fakeClient` above returns `{status: 200}` for every path it is handed,
// whatever it says. Both are right for what they assert — one proves the
// markup, the other proves which endpoint a button reaches — and between them
// they mean the client never met a router.
//
// Meanwhile the real Django routes are `<uuid:order_id>` throughout, so an
// address carrying the order NUMBER — the only reference on screen, and the one
// the route parameter is named after — 404'd on all fourteen calls. The screen
// drew a dash for each and looked finished. `tsc` was green, because an order
// number IS a string; 75 cases were green; 165 gates were green.
//
// `routerFakeClient` is the missing piece and it is three lines of policy: it
// answers a path the way `apps/work/api.py` would. A screen that asks for an
// address the server does not serve now fails HERE, without a browser.
const UUID = "01a07859-ba02-7ebc-b7f4-081af9f5ab15";
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * A client that routes like the server does, and refuses like it does.
 *
 * `path("work-orders/<uuid:order_id>", …)` cannot match `WO-4822`, and
 * `path("work-orders/by-number/<str:order_no>", …)` is the ONE door that takes
 * a number. Anything else is a 404, exactly as Django answers it.
 */
/** ⚠ **A REAL `ApiError`, NOT A BARE `{status: 404}`.** `isApiError` is an
 *  `instanceof` check, so a fake that throws a plain object sends the screen
 *  down its *unreadable* branch while the product goes down *not found* — a
 *  test that passes while looking at the wrong thing. */
const notFoundError = () =>
  new ApiError(404, { code: "NOT_FOUND", message_key: "errors.notFound" } as never);

function routerFakeClient(calls: Call[], known = "WO-4822"): ApiClient {
  const row = {
    id: UUID, order_no: known, type: "Meter exchange", state: "planned",
    dispatch_state: "scheduled", premise: null, account: null, priority: null,
    technician: null,
  };
  const send = (method: string) => async (path: string, body?: unknown) => {
    calls.push({ method, path, body: body ?? null });
    const rest = path.replace(/^\/work-orders\//, "").split("?")[0];
    const byNumber = rest.match(/^by-number\/(.+)$/);
    if (byNumber) {
      if (decodeURIComponent(byNumber[1]) !== known) throw notFoundError();
      return { status: 200, data: row, etag: null, notModified: false };
    }
    // Every other route on this family opens with `<uuid:order_id>`.
    if (!UUID_RE.test(rest.split("/")[0])) throw notFoundError();
    return { status: 200, data: row, etag: null, notModified: false };
  };
  return {
    request: send("REQUEST"), get: send("GET"), post: send("POST"),
    put: send("PUT"), patch: send("PATCH"), del: send("DELETE"),
  } as unknown as ApiClient;
}

/** Mounted at a REAL address with an EMPTY cache — the two things every other
 *  case in this file deliberately does not do. */
function mountAt(address: string, client: ApiClient) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/orders/${address}?tab=overview`]}>
          <Routes>
            <Route path="/:tenant/work/orders/:orderNo" element={<OrderDetailPage client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("Work-008 · every address this screen opens at is one the server serves (DEF-WRK-4518)", () => {
  it("FAILS ON THE DEFECT: a NUMBER address asks a route that exists", async () => {
    const calls: Call[] = [];
    mountAt("WO-4822", routerFakeClient(calls));
    await waitFor(() => expect(screen.queryByText(t("work.order.overview.title"))).not.toBeNull());
    // Not one call may 404 against the real routing table. Before the fix every
    // one of them did, and the screen still rendered.
    const unserved = calls
      .filter((c) => c.method === "GET")
      // `CR-161-BRC10` W4 — the custom-field registry is TENANCY's route
      // (`GET /custom-fields`), served and not a work-order address at all.
      .filter((c) => c.path !== "/custom-fields")
      .filter((c) => {
        const rest = c.path.replace(/^\/work-orders\//, "").split("?")[0];
        return !rest.startsWith("by-number/") && !UUID_RE.test(rest.split("/")[0]);
      });
    expect(unserved).toEqual([]);
  });

  it("resolves ONCE, then every other call carries the id", async () => {
    const calls: Call[] = [];
    mountAt("WO-4822", routerFakeClient(calls));
    await waitFor(() => expect(calls.filter((c) => c.path.includes("by-number")).length).toBe(1));
    await waitFor(() => expect(calls.length).toBeGreaterThan(3));
    // Fourteen resolves for one page would be the tidy-looking wrong answer.
    expect(calls.filter((c) => c.path.includes("by-number")).length).toBe(1);
    expect(calls.filter((c) => c.path.includes("WO-4822") && !c.path.includes("by-number")))
      .toEqual([]);
  });

  it("a uuid address still goes STRAIGHT to the id route — no lookup at all", async () => {
    const calls: Call[] = [];
    mountAt(UUID, routerFakeClient(calls));
    await waitFor(() => expect(calls.length).toBeGreaterThan(3));
    expect(calls.filter((c) => c.path.includes("by-number"))).toEqual([]);
  });

  it("AN UNKNOWN ORDER SAYS SO — it does not draw a page of dashes", async () => {
    const calls: Call[] = [];
    mountAt("WO-9999", routerFakeClient(calls));
    await waitFor(() => expect(screen.queryByText(t("work.order.failedTitle"))).not.toBeNull());
    // The distinguishing assertion: the fact list is NOT drawn. A screen that
    // renders `Type — · Service —` over a failed read is indistinguishable from
    // one that loaded an order with nothing filled in, and that ambiguity is
    // the whole of why this defect survived.
    expect(screen.queryByText(t("work.order.overview.title"))).toBeNull();
    expect(screen.getByText(t("work.order.notFound", { order: "WO-9999" }))).toBeTruthy();
  });

  it("WHILE IT RESOLVES the page does not look finished-and-empty", () => {
    // No `await`: this is the first paint, before any answer has come back.
    const calls: Call[] = [];
    mountAt("WO-4822", routerFakeClient(calls));
    expect(screen.queryByText(t("work.order.overview.title"))).toBeNull();
    expect(screen.queryByText(t("work.order.actions.reassign"))).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// PO 2026-10-02 — "Move them to the top right like every other screen."
// ══════════════════════════════════════════════════════════════════════════
//
// Decision log 2026-10-02, "THREE UI RULINGS FROM THE RATE-SCHEDULE SWEEP" (2),
// extending the same day's page-actions ruling (B14 rule 2: right-aligned
// actions in the shared page head; rule 11 amended in the same commit). Until
// this change the four sat in a row at the BOTTOM of the body, under the
// consequence box — the only details screen of 166 that did. Every case above
// still passed on that layout, because each one finds a button by its WORDS
// and never asks WHERE it is; these two ask where.
describe("Work-008 · the actions sit top-right in the page head (PO 2026-10-02; ruling 16)", () => {
  // ⚠ REWRITTEN BY CR-168: *Mark complete* left the head (ruling 18), and so
  // did the consequence box the second case measured "after". An open job's
  // head is image 03's three — Reassign… · Put on hold… · Cancel order.
  // CR-168-BRC10 P6.3 (lane SRV-5) — *Print* joined the head, first; the
  // destructive one stays last.
  // `DEF-WRK-9690` (beta #28) — *Duplicate* follows *Print* on every shape.
  const LABELS = [
    "work.order.actions.print",
    "work.order.actions.duplicate",
    "work.order.actions.reassign",
    "work.order.actions.hold",
    "work.order.actions.cancel",
  ] as const;

  it("all five render inside the page head's action row, in order, Cancel last in the danger tier", () => {
    const { container } = mount(fakeClient([]));
    const head = container.querySelector(".page-header-actions");
    expect(head, "the shared page head has no action row").not.toBeNull();
    const buttons = Array.from((head as Element).querySelectorAll("button"));
    expect(buttons.map((b) => b.textContent)).toEqual(LABELS.map((k) => t(k)));
    expect(buttons[4]?.getAttribute("data-variant")).toBe("danger");
  });

  it("each label is drawn exactly ONCE — nothing at the bottom of the body", () => {
    mount(fakeClient([]));
    for (const key of LABELS) {
      expect(screen.getAllByText(t(key))).toHaveLength(1);
    }
  });
});
