// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Stories:  US-WRK-055 (Finished jobs) · US-WRK-056 (Raised on site) ·
//           US-WRK-057 (Alerts) — EP-WRK-11, `Work-034` (WRK-26)
// Rules:    BR-FLD-00004 · BR-FLD-00023 · BR-FLD-00028 · NFR-3 · B14 rules
//           6 · 15 · 17 · 31 · hard-won law 2 (the door is asserted by ADDRESS)
// ───────────────────────────────────────────────────────
//
// Mounted under the REAL path patterns (`/:tenant/work/field…`), never a bare
// MemoryRouter: without the `:tenant` segment every link this screen builds
// comes out `//work/…`, which `toContain` reads as a perfectly good string
// (hard-won law 2's fixture clause).
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { activeWorkTab } from "../WorkShell";
import { FIELD_DESK_SCREEN, FieldDeskPage } from "./FieldDeskPage";
import type { FieldDeskView } from "./FieldDeskPage";
import type { AcceptanceRow, FieldAlertRow, FieldRaisedRow, RouteFindingRow } from "./fieldDeskEndpoints";
import { commits, fakeClient } from "./fieldTestClient";
import type { Call } from "./fieldTestClient";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const ORDER_ID = "0b6f2c1e-1111-4a4a-9c9c-000000004903";

function result(over: Partial<AcceptanceRow> = {}): AcceptanceRow {
  return {
    id: ORDER_ID,
    order_no: "WO-4903",
    type: "Meter exchange",
    premise: { id: "p-1", premise_no: "P-00117", address: "500 Main St" },
    technician: "D. Ortiz",
    raised_in_field: false,
    waiting_days: 2,
    outcome: "partially_done",
    word: "partly_done",
    kind: "partial",
    is_failure: false,
    reason: null,
    reason_missing: true,
    blocker: null,
    blocker_known: null,
    steps_done: 3,
    steps_total: 5,
    remaining_steps: [
      { seq: 4, title: "Seal the meter", is_mandatory: true },
      { seq: 5, title: "Photo of the seal", is_mandatory: false },
    ],
    photographs: 4,
    completed_at: "2026-10-20T15:40:00Z",
    accepted_at: null,
    cost: { frozen: false, report_version: null, total: "138.42" },
    ...over,
  };
}

const BLOCKED = result({
  id: "0b6f2c1e-1111-4a4a-9c9c-000000004917",
  order_no: "WO-4917",
  outcome: "waiting_on_someone_else",
  word: "waiting_on_someone",
  kind: "blocked",
  reason: "Customer not home, gate locked",
  reason_missing: false,
  blocker: "part",
  blocker_known: true,
  steps_done: 1,
  steps_total: 4,
  cost: { frozen: false, report_version: null, total: "45.00" },
});

const TALLY = { passed: 7, partly_done: 2, failed: 1, waiting_on_someone: 3, none: 0 };

function page<Row>(rows: Row[], extra: Record<string, unknown> = {}) {
  return { count: rows.length, next: null, previous: null, results: rows, ...extra };
}

function Where() {
  return <span data-testid="where">{useLocation().pathname}</span>;
}

function mount(view: FieldDeskView, client: ApiClient) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const address =
    view === "results" ? `/${TENANT}/work/field` : `/${TENANT}/work/field/${view}`;
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[address]}>
          <Routes>
            <Route path="/:tenant/work/field" element={<FieldDeskPage view="results" client={client} />} />
            <Route path="/:tenant/work/field/raised" element={<FieldDeskPage view="raised" client={client} />} />
            <Route path="/:tenant/work/field/alerts" element={<FieldDeskPage view="alerts" client={client} />} />
            <Route path="/:tenant/work/field/findings" element={<FieldDeskPage view="findings" client={client} />} />
          </Routes>
          <Where />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-WRK-055 — Finished jobs: what the field said, accepted, reopened or followed on", () => {
  it("TC-1 — asks the acceptance queue for UNACCEPTED jobs, paged, and draws what the field said", async () => {
    const calls: Call[] = [];
    mount("results", fakeClient(calls, { "/work/acceptance-queue": page([result(), BLOCKED], { tally: TALLY }) }));
    await waitFor(() => expect(screen.getByText("WO-4903")).toBeInTheDocument());

    const read = calls.find((c) => c.path === "/work/acceptance-queue");
    expect(read?.query.accepted).toBe("false");
    expect(read?.query.page).toBe(1);
    expect(read?.query.per).toBeDefined();
    expect(read?.query.outcome).toBeUndefined();

    // The badge the screen carries, and the page head.
    expect(document.querySelector(`[data-screen="${FIELD_DESK_SCREEN}"]`)).not.toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: t("work.field.title") })).toBeInTheDocument();

    const first = screen.getByText("WO-4903").closest("tr") as HTMLElement;
    expect(within(first).getByText("D. Ortiz")).toBeInTheDocument();
    expect(within(first).getByText("Partly done")).toBeInTheDocument();
    // A partial with no reason says so — never a blank cell.
    expect(within(first).getByText("Reason missing")).toBeInTheDocument();
    expect(within(first).getByText("2 of 5")).toBeInTheDocument();
    expect(within(first).getByText("$138.42")).toBeInTheDocument();

    const blocked = screen.getByText("WO-4917").closest("tr") as HTMLElement;
    expect(within(blocked).getByText("Waiting on someone")).toBeInTheDocument();
    expect(within(blocked).getByText("A part")).toBeInTheDocument();
    expect(within(blocked).getByText("Customer not home, gate locked")).toBeInTheDocument();

    // B14 rule 31 — the order's id travels in the eye's ADDRESS and never in the text.
    expect(document.body.textContent).not.toContain(ORDER_ID);
    const eye = within(first).getByRole("link", { name: "View WO-4903" });
    expect(eye).toHaveAttribute("href", `/${TENANT}/work/orders/${ORDER_ID}`);
  });

  it("TC-2 — the outcome filter asks the SERVER again with the R4 word", async () => {
    const calls: Call[] = [];
    const user = userEvent.setup();
    mount(
      "results",
      fakeClient(calls, {
        "/work/acceptance-queue": (call: Call) =>
          call.query.outcome === "partly_done"
            ? page([result()], { tally: TALLY })
            : page([result(), BLOCKED], { tally: TALLY }),
      }),
    );
    await waitFor(() => expect(screen.getByText("WO-4917")).toBeInTheDocument());
    await user.click(screen.getByText(/\+ Filter/));
    await user.click(screen.getByRole("checkbox", { name: /Partly done/ }));
    await waitFor(() =>
      expect(calls.some((c) => c.path === "/work/acceptance-queue" && c.query.outcome === "partly_done")).toBe(true),
    );
    await waitFor(() => expect(screen.queryByText("WO-4917")).not.toBeInTheDocument());
  });

  it("FB-013 — the outcome filter offers Not done — payment received and asks the server for it", async () => {
    const calls: Call[] = [];
    const user = userEvent.setup();
    mount(
      "results",
      fakeClient(calls, { "/work/acceptance-queue": () => page([result()], { tally: TALLY }) }),
    );
    await waitFor(() => expect(screen.getByText("WO-4903")).toBeInTheDocument());
    await user.click(screen.getByText(/\+ Filter/));
    await user.click(screen.getByRole("checkbox", { name: /Not done — payment received/ }));
    await waitFor(() =>
      expect(calls.some((c) => c.path === "/work/acceptance-queue" && c.query.outcome === "not_done_paid")).toBe(true),
    );
  });

  it("TC-3 — Accept asks first, then posts the ONE acceptance every door uses", async () => {
    const calls: Call[] = [];
    mount("results", fakeClient(calls, { "/work/acceptance-queue": page([result()], { tally: TALLY }) }));
    await waitFor(() => expect(screen.getByText("WO-4903")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Accept WO-4903" }));
    expect(commits(calls)).toHaveLength(0);
    expect(screen.getByText("Costs and readings are saved.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Accept ✓/ }));
    await waitFor(() => expect(commits(calls)).toHaveLength(1));
    expect(commits(calls)[0].path).toBe(`/work-orders/${ORDER_ID}/accept`);
  });

  it("TC-4 — Reopen needs a reason and posts decision=reopen with a key minted at open", async () => {
    const calls: Call[] = [];
    mount(
      "results",
      fakeClient(calls, {
        "/work/acceptance-queue": page([result()], { tally: TALLY }),
        [`POST /work-orders/${ORDER_ID}/come-back`]: { id: "r1", order_id: ORDER_ID, order_no: "WO-4903", kind: "office_reopen", reason: "x", follow_on: null, duplicate: false },
      }),
    );
    await waitFor(() => expect(screen.getByText("WO-4903")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("More for WO-4903"));
    fireEvent.click(screen.getByText("Reopen…"));
    expect(screen.getByText("Reopen WO-4903?")).toBeInTheDocument();
    // Empty reason → refused on the form, nothing sent.
    fireEvent.click(screen.getByRole("button", { name: /Reopen ✓/ }));
    await waitFor(() => expect(screen.getByText("Give a reason.")).toBeInTheDocument());
    expect(commits(calls)).toHaveLength(0);
    fireEvent.change(document.getElementById("reason") as HTMLTextAreaElement, {
      target: { value: "Seal photo is blurred" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Reopen ✓/ }));
    await waitFor(() => expect(commits(calls)).toHaveLength(1));
    const posted = commits(calls)[0];
    expect(posted.path).toBe(`/work-orders/${ORDER_ID}/come-back`);
    expect(posted.body).toMatchObject({ decision: "reopen", reason: "Seal photo is blurred" });
    expect(typeof (posted.body as { key?: unknown }).key).toBe("string");
  });

  it("TC-5 — Raise follow-on finds a PUBLISHED template by typing and posts decision=follow_on", async () => {
    const calls: Call[] = [];
    mount(
      "results",
      fakeClient(calls, {
        "/work/acceptance-queue": page([result()], { tally: TALLY }),
        "/work/templates": page(
          [
            { id: "tpl-pub", name: "Reconnect visit", status: "published" },
            { id: "tpl-draft", name: "Reconnect draft", status: "draft" },
          ],
          { counts: { published: 1, draft: 1, inactive: 0 } },
        ),
        [`POST /work-orders/${ORDER_ID}/come-back`]: {
          id: "r2",
          order_id: ORDER_ID,
          order_no: "WO-4903",
          kind: "follow_on",
          reason: "x",
          follow_on: { id: "new", order_no: "WO-5001" },
          duplicate: false,
        },
      }),
    );
    await waitFor(() => expect(screen.getByText("WO-4903")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("More for WO-4903"));
    fireEvent.click(screen.getByText("Raise follow-on…"));
    fireEvent.change(document.getElementById("template") as HTMLInputElement, { target: { value: "Reco" } });
    await waitFor(() => expect(screen.getByRole("option", { name: /Reconnect visit/ })).toBeInTheDocument());
    // A draft is not a version (`BR-WRK-011`) and is never offered.
    expect(screen.queryByRole("option", { name: /Reconnect draft/ })).not.toBeInTheDocument();
    expect(calls.find((c) => c.path === "/work/templates")?.query.q).toBe("Reco");
    fireEvent.click(screen.getByRole("option", { name: /Reconnect visit/ }));
    fireEvent.change(document.getElementById("reason") as HTMLTextAreaElement, {
      target: { value: "Meter needs a second visit" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Raise ✓/ }));
    await waitFor(() => expect(commits(calls)).toHaveLength(1));
    expect(commits(calls)[0].body).toMatchObject({
      decision: "follow_on",
      template_id: "tpl-pub",
      reason: "Meter needs a second visit",
    });
  });

  it("TC-6 — an empty queue says so, in the kit's empty state", async () => {
    mount("results", fakeClient([], { "/work/acceptance-queue": page([], { tally: TALLY }) }));
    await waitFor(() => expect(screen.getByText("Nothing to review")).toBeInTheDocument());
  });
});

function raised(over: Partial<FieldRaisedRow> = {}): FieldRaisedRow {
  return {
    order_id: "0b6f2c1e-2222-4a4a-9c9c-000000005010",
    order_no: "WO-5010",
    status: "pending",
    dispatch_state: "scheduled",
    // FB-028 (PO 2026-10-31) — a raised order is the raiser's from the raise.
    assigned: true,
    assigned_to: { id: "tech-patel", name: "R. Patel" },
    template: { id: "tpl-1", name: "Reconnect visit", version_stamped: 3, version_picked: 2, version_moved: true },
    carried_from: null,
    premise: { id: "p-2", premise_no: "P-00891", address: "77 Cedar Ct" },
    account: { id: "a-1", account_no: "AC-2026-00050" },
    customer: { name: "Sarah Miller", customer_no: "C-50" },
    position: { lat: "29.7604", lng: "-95.3698", accuracy_m: "8" },
    need: "reconnect",
    urgency: "today",
    is_reconnect: true,
    note: null,
    captured_at: "2026-10-21T14:00:00Z",
    raised_by: "R. Patel",
    raised_at: "2026-10-21T14:05:00Z",
    photographs: 2,
    decided_by: null,
    decided_at: null,
    decision_reason: null,
    ...over,
  };
}

describe("US-WRK-056 — Raised on site: accept, or refuse with a reason", () => {
  it("FB-028 — Assigned to names who holds the order now, after an office reassign too", async () => {
    mount("raised", fakeClient([], {
      "/work/field-raised": page([raised({ assigned_to: { id: "tech-ortiz", name: "Ray Ortiz" } })], { counts: { pending: 1, accepted: 0, refused: 0 } }),
    }));
    await waitFor(() => expect(screen.getByText("WO-5010")).toBeInTheDocument());
    const row = screen.getByText("WO-5010").closest("tr") as HTMLElement;
    expect(within(row).getByText("Ray Ortiz")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Assigned to/ })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("tech-ortiz");
  });

  it("TC-1 — starts on PENDING and draws the template version that moved, the position and the photos", async () => {
    const calls: Call[] = [];
    mount("raised", fakeClient(calls, { "/work/field-raised": page([raised()], { counts: { pending: 1, accepted: 4, refused: 0 } }) }));
    await waitFor(() => expect(screen.getByText("WO-5010")).toBeInTheDocument());
    expect(calls.find((c) => c.path === "/work/field-raised")?.query.status).toBe("pending");
    const row = screen.getByText("WO-5010").closest("tr") as HTMLElement;
    expect(within(row).getByText("Reconnect")).toBeInTheDocument();
    expect(within(row).getByText("Reconnect visit · v2 → v3")).toBeInTheDocument();
    expect(within(row).getByText("29.7604, -95.3698 ±8 m")).toBeInTheDocument();
    // Raised by AND Assigned to — the raiser holds it (FB-028).
    expect(within(row).getAllByText("R. Patel")).toHaveLength(2);
    expect(within(row).getByText("77 Cedar Ct")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(raised().order_id);
  });

  it("TC-2 — Accept posts decision=accept", async () => {
    const calls: Call[] = [];
    const row = raised();
    mount("raised", fakeClient(calls, { "/work/field-raised": page([row], { counts: { pending: 1, accepted: 0, refused: 0 } }) }));
    await waitFor(() => expect(screen.getByText("WO-5010")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Accept WO-5010" }));
    // FB-028 — Accept = seen; the order stays with whoever holds it.
    expect(screen.getByText("Marks it seen. It stays assigned.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Accept ✓/ }));
    await waitFor(() => expect(commits(calls)).toHaveLength(1));
    expect(commits(calls)[0]).toMatchObject({
      path: `/work-orders/${row.order_id}/field-raise`,
      body: { decision: "accept" },
    });
  });

  it("TC-3 — Refuse is the danger tier, needs a reason, and posts decision=refuse", async () => {
    const calls: Call[] = [];
    const row = raised();
    mount("raised", fakeClient(calls, { "/work/field-raised": page([row], { counts: { pending: 1, accepted: 0, refused: 0 } }) }));
    await waitFor(() => expect(screen.getByText("WO-5010")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Refuse WO-5010" }));
    expect(screen.getByText("The order is canceled. Its history stays.")).toBeInTheDocument();
    const commit = screen.getByRole("button", { name: "Refuse order" });
    expect(commit.className).toMatch(/danger/);
    fireEvent.click(commit);
    await waitFor(() => expect(screen.getByText("Give a reason.")).toBeInTheDocument());
    expect(commits(calls)).toHaveLength(0);
    fireEvent.change(document.getElementById("reason") as HTMLTextAreaElement, {
      target: { value: "Duplicate of WO-5002" },
    });
    fireEvent.click(commit);
    await waitFor(() => expect(commits(calls)).toHaveLength(1));
    expect(commits(calls)[0].body).toEqual({ decision: "refuse", reason: "Duplicate of WO-5002" });
  });

  it("TC-4 — a decided raise offers no act on it", async () => {
    mount(
      "raised",
      fakeClient([], { "/work/field-raised": page([raised({ status: "accepted" })], { counts: { pending: 0, accepted: 1, refused: 0 } }) }),
    );
    await waitFor(() => expect(screen.getByText("WO-5010")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Accept WO-5010" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refuse WO-5010" })).not.toBeInTheDocument();
  });

  it("TC-5 — nothing pending reads as an empty filter, and clearing it asks for EVERY status", async () => {
    const calls: Call[] = [];
    mount(
      "raised",
      fakeClient(calls, {
        "/work/field-raised": (call: Call) =>
          call.query.status === "all"
            ? page([raised({ status: "refused" })], { counts: { pending: 0, accepted: 0, refused: 1 } })
            : page([], { counts: { pending: 0, accepted: 0, refused: 1 } }),
      }),
    );
    await waitFor(() => expect(screen.getByText(i18n.t("states.zeroResults.filtered"))).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: i18n.t("states.zeroResults.clearFilters") }));
    // A cleared filter is `all`, never the server's silent default of pending.
    await waitFor(() => expect(calls.some((c) => c.query.status === "all")).toBe(true));
    await waitFor(() => expect(screen.getByText("WO-5010")).toBeInTheDocument());
    expect(screen.getByText("Refused")).toBeInTheDocument();
  });

  it("TC-6 — a utility with no raises at all reads the pane's own empty state", async () => {
    // The empty state replaces the table only when NO filter is applied
    // (BR-SHL-012), so it is reached by clearing the pending filter.
    mount("raised", fakeClient([], { "/work/field-raised": page([], { counts: { pending: 0, accepted: 0, refused: 0 } }) }));
    await waitFor(() => expect(screen.getByText(i18n.t("states.zeroResults.filtered"))).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: i18n.t("states.zeroResults.clearFilters") }));
    await waitFor(() => expect(screen.getByText("Nothing raised on site")).toBeInTheDocument());
  });
});

function alert(over: Partial<FieldAlertRow> = {}): FieldAlertRow {
  return {
    id: "al-1",
    kind: "emergency",
    work_order_id: "0b6f2c1e-3333-4a4a-9c9c-000000004822",
    order_no: "WO-4822",
    premise: null,
    technician: "D. Ortiz",
    message: "Gas smell reported",
    sent_at: "2026-10-21T14:00:00Z",
    ack_required: true,
    ack_due_at: "2026-10-21T14:05:00Z",
    acknowledged_at: null,
    late: true,
    dispatch_told: true,
    escalated_at: "2026-10-21T14:05:30Z",
    ...over,
  };
}

describe("US-WRK-057 — Alerts: what was sent, and what went unanswered", () => {
  it("TC-1 — asks for every state, and an unanswered emergency reads Overdue and Dispatch told", async () => {
    const calls: Call[] = [];
    mount(
      "alerts",
      fakeClient(calls, {
        "/work/field-alerts": page([
          alert(),
          alert({ id: "al-2", kind: "dispatch_message", order_no: null, work_order_id: null, ack_required: false, late: false, dispatch_told: false, message: "Depot closes at 4" }),
        ]),
      }),
    );
    await waitFor(() => expect(screen.getByText("Gas smell reported")).toBeInTheDocument());
    expect(calls.find((c) => c.path === "/work/field-alerts")?.query.state).toBe("all");
    const row = screen.getByText("Gas smell reported").closest("tr") as HTMLElement;
    expect(within(row).getByText("Emergency")).toBeInTheDocument();
    expect(within(row).getByText("Overdue")).toBeInTheDocument();
    expect(within(row).getByText("Dispatch told")).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: "WO-4822" })).toHaveAttribute(
      "href",
      `/${TENANT}/work/orders/0b6f2c1e-3333-4a4a-9c9c-000000004822`,
    );
    const message = screen.getByText("Depot closes at 4").closest("tr") as HTMLElement;
    expect(within(message).getByText("No answer needed")).toBeInTheDocument();
  });

  it("TC-2 — the Answer filter asks the server for overdue", async () => {
    const calls: Call[] = [];
    const user = userEvent.setup();
    mount("alerts", fakeClient(calls, { "/work/field-alerts": page([alert()]) }));
    await waitFor(() => expect(screen.getByText("Gas smell reported")).toBeInTheDocument());
    await user.click(screen.getByText(/\+ Filter/));
    await user.click(screen.getByRole("checkbox", { name: /Overdue/ }));
    await waitFor(() =>
      expect(calls.some((c) => c.path === "/work/field-alerts" && c.query.state === "overdue")).toBe(true),
    );
  });

  it("TC-3 — no alerts says where they are sent from", async () => {
    mount("alerts", fakeClient([], { "/work/field-alerts": page([]) }));
    await waitFor(() => expect(screen.getByText("No alerts")).toBeInTheDocument());
    expect(screen.getByText("Send one from an order.")).toBeInTheDocument();
  });
});

describe("Work-034 — the door: one Work tab, three panes, each at its own address", () => {
  it("the sub-strip moves between the three addresses, and the Work tab stays lit", async () => {
    mount("results", fakeClient([], { "/work/acceptance-queue": page([], { tally: TALLY }), "/work/field-raised": page([], { counts: {} }), "/work/field-alerts": page([]) }));
    await waitFor(() => expect(screen.getByText("Nothing to review")).toBeInTheDocument());
    // The Work strip's own tab is a real link to the screen's address.
    const tab = document.querySelector('[data-tab="field"]') as HTMLElement;
    expect(tab).not.toBeNull();
    expect(tab.textContent).toContain("From the field");
    expect(tab.closest("a") ?? tab).toHaveAttribute("href", `/${TENANT}/work/field`);
    fireEvent.click(screen.getByRole("tab", { name: "Raised on site" }));
    await waitFor(() => expect(screen.getByTestId("where").textContent).toBe(`/${TENANT}/work/field/raised`));
    fireEvent.click(screen.getByRole("tab", { name: "Alerts" }));
    await waitFor(() => expect(screen.getByTestId("where").textContent).toBe(`/${TENANT}/work/field/alerts`));
    expect(activeWorkTab(`/${TENANT}/work/field`)).toBe("field");
    expect(activeWorkTab(`/${TENANT}/work/field/raised`)).toBe("field");
    expect(activeWorkTab(`/${TENANT}/work/field/alerts`)).toBe("field");
    // BR-WRK-067 — the fourth pane, at its own address (law 2: by ADDRESS).
    fireEvent.click(screen.getByRole("tab", { name: "Route findings" }));
    await waitFor(() => expect(screen.getByTestId("where").textContent).toBe(`/${TENANT}/work/field/findings`));
    expect(activeWorkTab(`/${TENANT}/work/field/findings`)).toBe("field");
  });
});

const SEAL_ID = "0b6f2c1e-2222-4a4a-9c9c-0000000000f2";
const LEAK_ORDER_ID = "0b6f2c1e-3333-4a4a-9c9c-000000004870";

function finding(over: Partial<RouteFindingRow> = {}): RouteFindingRow {
  return {
    id: SEAL_ID,
    key: "dana-f-4",
    kind: "broken_seal",
    urgency: "this_week",
    note: null,
    status: "open",
    conversion: null,
    rule: null,
    work_order: null,
    meter_no: "MTR-0471",
    stop: { premise_no: "P-00117", address: "1318 Maple St" },
    route: "WLK-07",
    technician: "D. Ortiz",
    photographs: 2,
    capture_point: { lat: "30.267200", lng: "-97.743100", accuracy_m: "6.00" },
    captured_at: "2026-10-22T14:05:00Z",
    received_at: "2026-10-22T14:06:00Z",
    converted_by: null,
    converted_at: null,
    ...over,
  };
}

const LEAK_DONE = finding({
  id: "0b6f2c1e-2222-4a4a-9c9c-0000000000f1",
  key: "dana-f-1",
  kind: "leak",
  status: "work_order_created",
  conversion: "by_rule",
  rule: "Leak → Leak repair",
  work_order: { id: LEAK_ORDER_ID, order_no: "WO-4870" },
});

describe("BR-WRK-067 — Route findings: open by default, a job by rule, else Create work order", () => {
  it("TC-1 — asks for OPEN findings, paged, and draws the place, the technician and the CAPTURE point", async () => {
    const calls: Call[] = [];
    mount("findings", fakeClient(calls, { "/work/route-findings": page([finding(), LEAK_DONE], { counts: { open: 1, work_order_created: 1 } }) }));
    await waitFor(() => expect(screen.getByText("Broken seal")).toBeInTheDocument());
    const read = calls.find((c) => c.path === "/work/route-findings");
    expect(read?.query.status).toBe("open");
    expect(read?.query.page).toBe(1);

    const open = screen.getByText("Broken seal").closest("tr") as HTMLElement;
    expect(within(open).getByText("MTR-0471 · 1318 Maple St")).toBeInTheDocument();
    expect(within(open).getByText("D. Ortiz")).toBeInTheDocument();
    // BR-MET-1202 — the phone's fix, under a header that says so.
    expect(screen.getByRole("columnheader", { name: /Capture point/ })).toBeInTheDocument();
    expect(within(open).getByText("30.267200, -97.743100 ±6.00 m")).toBeInTheDocument();
    expect(within(open).getByRole("button", { name: "Create work order for Broken seal" })).toBeInTheDocument();

    const done = screen.getByText("Leak").closest("tr") as HTMLElement;
    expect(within(done).getByText("WO-4870")).toBeInTheDocument();
    expect(within(done).queryByRole("button", { name: /Create work order/ })).toBeNull();
    expect(within(done).getByRole("link", { name: "View WO-4870" })).toHaveAttribute(
      "href",
      `/${TENANT}/work/orders/${LEAK_ORDER_ID}`,
    );
    // B14 rule 31 — ids travel in addresses, never in the text.
    expect(document.body.textContent).not.toContain(SEAL_ID);
    expect(document.body.textContent).not.toContain(LEAK_ORDER_ID);
  });

  it("TC-2 — Create work order posts the template and priority ONCE to the finding's own address", async () => {
    const calls: Call[] = [];
    const user = userEvent.setup();
    mount(
      "findings",
      fakeClient(calls, {
        "/work/route-findings": page([finding()], { counts: { open: 1, work_order_created: 0 } }),
        "/work/templates": page(
          [
            { id: "tpl-seal", name: "Seal check", active: true, version: 2 },
            { id: "tpl-draft", name: "Draft only", active: true, version: 0 },
          ],
          { counts: { published: 1, draft: 1, inactive: 0 } },
        ),
        "/work/raise-options": { types: [], priorities: [{ id: "pr-1", code: "P1", name: "Same day" }] },
        [`POST /work/route-findings/${SEAL_ID}/work-order`]: {
          ...finding({ status: "work_order_created", conversion: "by_hand", work_order: { id: "wo-2", order_no: "WO-4871" } }),
          duplicate: false,
        },
      }),
    );
    await waitFor(() => expect(screen.getByText("Broken seal")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Create work order for Broken seal" }));
    expect(screen.getByRole("heading", { name: "Create work order" })).toBeInTheDocument();
    // Nothing is sent without a template.
    fireEvent.click(screen.getByRole("button", { name: /Create ✓/ }));
    await waitFor(() => expect(screen.getByText("Pick a template.")).toBeInTheDocument());
    expect(commits(calls)).toHaveLength(0);
    await waitFor(() => expect(screen.getByRole("option", { name: "Seal check" })).toBeInTheDocument());
    // A draft cannot raise a job (BR-WRK-011) and is not offered.
    expect(screen.queryByRole("option", { name: "Draft only" })).toBeNull();
    await user.selectOptions(screen.getByLabelText(/Template/, { selector: "select" }), "tpl-seal");
    await user.selectOptions(screen.getByLabelText(/Priority/, { selector: "select" }), "pr-1");
    fireEvent.click(screen.getByRole("button", { name: /Create ✓/ }));
    await waitFor(() => expect(commits(calls)).toHaveLength(1));
    expect(commits(calls)[0].path).toBe(`/work/route-findings/${SEAL_ID}/work-order`);
    expect(commits(calls)[0].body).toEqual({ template_id: "tpl-seal", priority_id: "pr-1" });
    await waitFor(() => expect(screen.getByText("WO-4871 created.")).toBeInTheDocument());
  });

  it("TC-3 — nothing open is an empty FILTER; cleared, it asks for every status and says where findings come from", async () => {
    const calls: Call[] = [];
    mount("findings", fakeClient(calls, { "/work/route-findings": page([], { counts: { open: 0, work_order_created: 0 } }) }));
    await waitFor(() => expect(screen.getByText(i18n.t("states.zeroResults.filtered"))).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: i18n.t("states.zeroResults.clearFilters") }));
    // A cleared filter is `all`, never the server's silent default of open.
    await waitFor(() => expect(calls.some((c) => c.path === "/work/route-findings" && c.query.status === "all")).toBe(true));
    await waitFor(() => expect(screen.getByText("No route findings")).toBeInTheDocument());
    expect(screen.getByText("Findings from meter routes appear here.")).toBeInTheDocument();
  });
});
