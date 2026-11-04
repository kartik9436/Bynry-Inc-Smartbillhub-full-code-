// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-183-BRC10 T7 — start / change / end a temporary stop from the
//           account page, mounted under the real `/:tenant/accounts/:id` path.
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import { TemporaryStopModal, TemporaryStopStrip } from "./TemporaryStopAccount";

const ACCOUNT_ID = "01a0b000-0000-7000-8000-000000000002";
const LIMITS = { min_days: 10, max_months: 12 };

const LIVE = {
  id: "01a0b000-0000-7000-8000-000000000001",
  account_id: ACCOUNT_ID,
  account_no: "AC-2026-00551",
  status: "on_hold",
  channel: "staff",
  stop_from: "2026-10-13",
  restart_on: "2026-10-26",
  days: 13,
  reason: null,
  field_visit_needed: true,
  shutoff_order_no: "WO-26-0101",
  turnon_order_no: "WO-26-0102",
  ended_early: false,
  billed_during_hold: "base_only",
  request_no: null,
  request_id: null,
  restart_request_no: null,
  restart_request_id: null,
  restart_request_state: null,
};

const calls: { method: string; url: string; body: unknown }[] = [];

function mount(current: unknown, which: "strip" | "modal", onDone = vi.fn()) {
  calls.length = 0;
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ method, url: String(input), body: init?.body ? JSON.parse(String(init.body)) : null });
      const body = method === "GET" ? { current, limits: LIMITS, billed_during_hold: "base_only" } : { stop: LIVE, current: LIVE, limits: LIMITS, warnings: [] };
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    },
  });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[`/brazosbend/accounts/${ACCOUNT_ID}`]}>
        <Routes>
          <Route
            path="/:tenant/accounts/:accountId"
            element={
              which === "strip" ? (
                <TemporaryStopStrip accountId={ACCOUNT_ID} timeZone="America/Chicago" dateFormat="YYYY-MM-DD" client={client} />
              ) : (
                <TemporaryStopModal
                  accountId={ACCOUNT_ID}
                  accountLabel="Susan Cook"
                  today="2026-10-14"
                  timeZone="America/Chicago"
                  dateFormat="YYYY-MM-DD"
                  client={client}
                  onClose={vi.fn()}
                  onDone={onDone}
                />
              )
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return onDone;
}

describe("CR-183 — the account page's temporary stop", () => {
  afterEach(cleanup);

  it("the strip says on hold, base only, and the two visits by number", async () => {
    mount(LIVE, "strip");
    const strip = await screen.findByText((_, el) => el?.getAttribute("data-temporary-stop-strip") === "on_hold");
    expect(strip.textContent).toContain("2026-10-13");
    expect(strip.textContent).toContain(i18n.t("customers.temporaryStop.fact.baseOnly"));
    expect(strip.textContent).toContain("WO-26-0101");
    expect(strip.textContent).not.toContain(LIVE.id);
  });

  it("with no stop the window starts one and posts the dates and the tick", async () => {
    const onDone = mount(null, "modal");
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain(i18n.t("customers.temporaryStop.fact.limits", { min: 10, max: 12 }));
    fireEvent.change(within(dialog).getByLabelText(i18n.t("customers.temporaryStop.field.restartOn"), { exact: false }), {
      target: { value: "2026-11-01" },
    });
    fireEvent.click(within(dialog).getByLabelText(i18n.t("customers.temporaryStop.field.fieldVisit")));
    fireEvent.click(within(dialog).getByRole("button", { name: i18n.t("customers.temporaryStop.start.submit") }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const post = calls.find((c) => c.method === "POST");
    expect(post?.url).toContain(`/accounts/${ACCOUNT_ID}/temporary-stop`);
    expect(post?.body).toMatchObject({ stop_from: "2026-10-14", restart_on: "2026-11-01", field_visit_needed: true });
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("a running stop can be ended now", async () => {
    mount(LIVE, "modal");
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: i18n.t("customers.temporaryStop.change.endNow") }));
    await waitFor(() =>
      expect(calls.some((c) => c.method === "POST" && c.url.endsWith(`/temporary-stops/${LIVE.id}/end`))).toBe(true),
    );
  });
});
