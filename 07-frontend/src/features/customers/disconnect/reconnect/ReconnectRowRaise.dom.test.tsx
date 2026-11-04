// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9674 — the row's `+ Raise work order` answered a refusal
//          with silence: on DSC-26-0001 (electric cut) the server said 422
//          `customers.reconnect.workOrder.noTemplate`, the screen showed no
//          message, the row kept "0 raised · 1 to raise", and the button sent
//          nothing when pressed again (found by lane WALK-B, CR-168 round 7).
// Rules:   BR-WRK-055 (the flow never fails over its visit — so the clerk must
//          be TOLD the visit was not raised) · B14 rule 33 (a fact ≤ 6 words).
// ───────────────────────────────────────────────────────
//
// ⚠ WHAT WOULD MAKE THIS PASS WRONGLY: a client stub that resolves instead of
// rejecting. The real `api` client THROWS an `ApiError` on any 4xx, so the stub
// below throws one built from the exact envelope the server sent on the walk.
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

const CASE_NO = "DSC-26-0001";

function money(display: string) {
  return { stored: `${display}0000`, display, currency: "USD", unavailable: null };
}

function detail(): ReconnectDetail {
  return {
    case_no: CASE_NO,
    account: {
      account_no: "A-11340",
      customer_name: "Northwind Mfg.",
      address: "77 Industrial Way · Suite 1 · Silver Creek, TX 78611",
      account_kind: "regular",
      account_class: "Commercial",
      cut_on: "2026-10-05",
      balance: money("8315.00"),
    },
    master: { is_master: false, units: null, unit_accounts: null },
    services: {
      rows: [
        {
          service: "electric",
          scope: null,
          service_point: "77 Industrial Way · Suite 1",
          point_known: true,
          meter: null,
          meter_absence: { code: "meter_not_recorded", detail: "no meter is recorded." },
          how_options: ["work_order", "remote", "no_visit"],
          how_default: "work_order",
          instruction: null,
          work_order: null,
          reaches: null,
        },
      ],
      unavailable: null,
      addable: [],
    },
    owed: {
      lines: [],
      still_owed: money("8315.00"),
      total_is_the_ledger: { code: "fee_is_already_in_the_balance", detail: "read once." },
      plan_label: "Commercial",
    },
    deposit: { held_before_the_cut: null, disposition: "held", new_deposit_required: false },
    consequences: [],
    warning: null,
    commit_refused_by: null,
    step: "mark_reconnecting",
    restore_on: "2026-10-05",
  } as unknown as ReconnectDetail;
}

function mount(post: () => Promise<unknown>) {
  let posts = 0;
  const client = {
    get: async () => ({ status: 200, data: detail() }),
    post: async () => {
      posts += 1;
      return post();
    },
  } as never;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(reconnectKey(CASE_NO), detail());
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/brazosbend${reconnectPath(CASE_NO)}?step=1`]}>
        <Routes>
          <Route path={`/:tenant${RECONNECT_ROUTE}`} element={<ReconnectPage client={client} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return () => posts;
}

describe("DEF-CUS-9674 — a refused row raise is said, and the row can be pressed again", () => {
  it("shows the server's refusal on the row and re-enables the button", async () => {
    const refusal = new ApiError(422, {
      code: "VAL-001",
      message_key: "customers.reconnect.workOrder.noTemplate",
      params: {},
      field_errors: [],
      br_ref: null,
      trace_id: "b426843050684929bd38aa2a74ff78f9",
    } as never);
    const posts = mount(() => Promise.reject(refusal));
    const user = userEvent.setup();
    const button = await screen.findByRole("button", { name: "+ Raise work order" });
    await user.click(button);
    expect(await screen.findByText("Pick what the crew does")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Raise work order" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "+ Raise work order" }));
    expect(posts()).toBe(2);
  });

  it("says the job was not raised when the server answers 200 with no order and a warning", async () => {
    mount(() =>
      Promise.resolve({
        status: 200,
        data: {
          work_orders: [],
          warnings: [{ code: "work_orders_not_raised", message_key: "work.fromFlows.notRaised" }],
        },
      }),
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "+ Raise work order" }));
    expect(await screen.findByText("The work order was not raised.")).toBeInTheDocument();
  });
});
