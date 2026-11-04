// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-10657 — S148's Confirm refused itself with "This step is not
//          built yet" on both of its steps, held on a refusal the server
//          dropped on 2026-09-25 (BR-CUS-1097).
// Ruling:  PO 2026-10-29, C1 *"Restore = Reconnect request"* — decision log
//          2026-10-29 *"C1 'Restore = Reconnect request': what it maps to"*.
// Rules:   BR-CUS-1097 (an owing account is never refused) · BR-PAY-036 (the
//          restoration is the clerk's explicit act) · hard-won law 2's mirror
//          (a hold writes the test that fires when it expires).
// ───────────────────────────────────────────────────────
//
// ⚠ THIS IS THE HOLD-EXPIRY TEST. It asserts the commit by ADDRESS — the POST
// the press must reach — so a screen that goes back to refusing, or that posts
// the wrong act for its step, goes red by name.
//
// ⚠ WHAT WOULD MAKE THIS PASS WRONGLY: a client stub that answers 200 to ANY
// path. So the stub records every path and body, and each case asserts the
// exact address and the exact body.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { ApiError } from "@/api/client";

import { ReconnectPage } from "./ReconnectPage";
import { RECONNECT_ROUTE, reconnectKey, reconnectPath } from "./reconnectEndpoints";
import type { ReconnectDetail } from "./reconnectEndpoints";

afterEach(cleanup);

const CASE_NO = "DSC-26-0002";

function money(display: string) {
  return { stored: `${display}0000`, display, currency: "USD", unavailable: null };
}

function row(service: string, how: string, work_order: unknown = null) {
  return {
    service,
    scope: null,
    service_point: "22 Cedar Court",
    point_known: true,
    meter: null,
    meter_absence: { code: "meter_not_recorded", detail: "no meter is recorded." },
    how_options: ["work_order", "remote", "no_visit"],
    how_default: how,
    instruction: null,
    work_order,
    reaches: null,
  };
}

function detail(over: Partial<ReconnectDetail> = {}): ReconnectDetail {
  return {
    case_no: CASE_NO,
    account: {
      account_no: "A-11721",
      customer_name: "Calloway, B.",
      address: "22 Cedar Court · Silver Creek, TX 78611",
      account_kind: "regular",
      account_class: "Residential",
      cut_on: "2026-09-20",
      balance: money("804.50"),
    },
    master: { is_master: false, units: null, unit_accounts: null },
    services: {
      rows: [
        row("water", "work_order"),
        row("electric", "no_visit"),
        row("gas", "work_order", { reference: "WO-4410", assignee: "Dana", done: false, accepted: false }),
      ],
      unavailable: null,
      addable: [],
    },
    owed: {
      lines: [],
      still_owed: money("804.50"),
      total_is_the_ledger: { code: "fee_is_already_in_the_balance", detail: "read once." },
      plan_label: "Residential",
    },
    deposit: { held_before_the_cut: null, disposition: "held", new_deposit_required: false },
    consequences: [{ code: "supply_back_on" }],
    // BR-CUS-1097 — money is owed, and that is a WARNING, never a refusal.
    warning: { code: "still_owed_you_may_continue", amount: money("804.50") },
    commit_refused_by: null,
    step: "mark_reconnecting",
    restore_on: "2026-09-26",
    ...over,
  } as unknown as ReconnectDetail;
}

function mount(data: ReconnectDetail, answer: () => Promise<unknown>) {
  const posts: { path: string; body: unknown }[] = [];
  const client = {
    get: async () => ({ status: 200, data }),
    post: async (path: string, body: unknown) => {
      posts.push({ path, body });
      return answer();
    },
  } as never;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(reconnectKey(CASE_NO), data);
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/brazosbend${reconnectPath(CASE_NO)}?step=2`]}>
        <Routes>
          <Route path={`/:tenant${RECONNECT_ROUTE}`} element={<ReconnectPage client={client} />} />
          <Route path="/:tenant/disconnects/:ref" element={<p>the case record</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return posts;
}

describe("DEF-CUS-10657 — Confirm on a CUT case sends the reconnect request", () => {
  it("posts the request with the date and the rows still to raise, and lands on the case", async () => {
    const posts = mount(detail(), () => Promise.resolve({ status: 200, data: { state: "reconnecting" } }));
    const user = userEvent.setup();
    const commit = await screen.findByRole("button", { name: /Request reconnect/ });
    // Money is owed and the press is LIVE (BR-CUS-1097).
    expect(commit).toBeEnabled();
    await user.click(commit);
    expect(await screen.findByText("the case record")).toBeInTheDocument();
    expect(posts).toEqual([
      {
        path: `/disconnects/${CASE_NO}/reconnect/request`,
        // Water is on Work order with no job → sent; electric is No visit →
        // not sent; gas already carries WO-4410 → not sent a second time.
        body: { on_date: "2026-09-26", services: ["water"] },
      },
    ]);
    expect(screen.queryByText("This step is not built yet")).not.toBeInTheDocument();
  });

  it("says the server's refusal in the catalogue's words and stays on the screen", async () => {
    const refusal = new ApiError(422, {
      code: "BIZ-004",
      message_key: "customers.disconnects.refused",
      params: { code: "not_cut", detail: "this case is 'reconnecting'." },
      field_errors: [],
      br_ref: "B18 §5.8.3",
      trace_id: "t",
    } as never);
    mount(detail(), () => Promise.reject(refusal));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Request reconnect/ }));
    expect(await screen.findByText("Request was not sent")).toBeInTheDocument();
    expect(screen.queryByText("the case record")).not.toBeInTheDocument();
  });
});

describe("DEF-CUS-10657 — Confirm on a RECONNECTING case completes the request", () => {
  it("posts the completion with the date — the clerk's explicit act (BR-PAY-036)", async () => {
    const posts = mount(
      detail({ step: "restore_service", warning: null }),
      () => Promise.resolve({ status: 200, data: { state: "restored" } }),
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Confirm restored/ }));
    expect(await screen.findByText("the case record")).toBeInTheDocument();
    expect(posts).toEqual([
      { path: `/disconnects/${CASE_NO}/reconnect/complete`, body: { on_date: "2026-09-26" } },
    ]);
  });
});
