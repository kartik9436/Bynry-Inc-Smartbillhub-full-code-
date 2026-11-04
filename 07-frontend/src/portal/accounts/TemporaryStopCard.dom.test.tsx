// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-183-BRC10 T8 — the paused-service card and B4's *Restart my
//           service now*, mounted under the portal's real `/account` path.
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { PortalTemporaryStop } from "../api/portalClient";

let answer: PortalTemporaryStop = {
  current: null,
  pending: null,
  can_restart_now: false,
  billed_during_hold: "base_only",
};
const restarts: string[] = [];

vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getTemporaryStop: async () => answer,
    askToRestartNow: async (id: string) => {
      restarts.push(id);
      answer = {
        ...answer,
        can_restart_now: false,
        current: answer.current && {
          ...answer.current,
          restart_reference: "SR-26-0021",
          restart_state: "submitted",
        },
      };
      return { reference: "SR-26-0021", supply_restarted: false };
    },
  };
});

const { TemporaryStopCard } = await import("./TemporaryStopCard");

function draw() {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/account"]}>
      <Routes>
        <Route path="/:tenant/portal/account" element={<TemporaryStopCard accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CR-183 — the customer's paused service", () => {
  afterEach(cleanup);

  it("draws nothing when there is no stop and no ask", async () => {
    answer = { current: null, pending: null, can_restart_now: false, billed_during_hold: "base_only" };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-testid]")).toBeNull());
  });

  it("shows the paused dates, base only, and sends the restart ask", async () => {
    answer = {
      current: {
        status: "on_hold",
        stop_from: "2026-10-13",
        restart_on: "2026-10-26",
        restart_reference: null,
        restart_state: null,
      },
      pending: null,
      can_restart_now: true,
      billed_during_hold: "base_only",
    };
    draw();
    const status = await screen.findByText((_, el) => el?.getAttribute("data-temporary-stop-status") === "on_hold");
    expect(status.textContent).toContain("2026");
    expect(document.body.textContent).toContain(i18n.t("portal.temporaryStop.baseOnly"));
    fireEvent.click(screen.getByRole("button", { name: i18n.t("portal.temporaryStop.restartNow") }));
    await waitFor(() => expect(restarts).toEqual(["acc-1"]));
    expect(
      await screen.findByText(i18n.t("portal.temporaryStop.restartAsked", { reference: "SR-26-0021" })),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: i18n.t("portal.temporaryStop.restartNow") })).toBeNull();
  });

  it("an ask still waiting for a clerk shows its reference", async () => {
    answer = {
      current: null,
      pending: { reference: "SR-26-0017", state: "submitted", stop_from: "2026-10-13", restart_on: "2026-10-16" },
      can_restart_now: false,
      billed_during_hold: "base_only",
    };
    draw();
    const line = await screen.findByText((_, el) => el?.hasAttribute("data-temporary-stop-pending") ?? false);
    expect(line.textContent).toContain("SR-26-0017");
  });
});
