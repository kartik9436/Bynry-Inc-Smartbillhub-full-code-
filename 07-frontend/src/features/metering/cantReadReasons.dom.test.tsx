// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-10609 — Settings → Reference data → Readings → Can't-read
//           reasons (decision log 2026-10-26, PO *"yes do it"*).
// Rules:    NFR-3 · BR-SHL-025 · B14 rules 15, 31, 33
// Note:     Mounted under the REAL path pattern (`/:tenant/settings/…`), and
//           the load-bearing assertions read the WIRE — a screen that draws the
//           right words and sends the wrong body would pass every visible check.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import { referenceCard } from "@/features/tenancy/referenceDataConfig";

import { CANT_READ_REASONS_ROUTE, CantReadReasonsPage } from "./CantReadReasonsPage";
import type { CantReadReasonRow } from "./cantReadReasonsEndpoints";

const TENANT = "silver-creek-water1";

interface Sent {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

const DOG: CantReadReasonRow = { code: "dog", name: "Dog", sort_order: 10, is_system: true, active: true, used: 4 };
const FLOOD: CantReadReasonRow = {
  code: "flooded_pit",
  name: "Flooded pit",
  sort_order: 90,
  is_system: false,
  active: false,
  used: 2,
};

function recordingClient(sent: Sent[], answer: (s: Sent) => Response | undefined): ApiClient {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const one = {
        method: init?.method ?? "GET",
        url: String(input),
        body: init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null,
      };
      sent.push(one);
      return answer(one) ?? json({ count: 2, next: null, previous: null, results: [DOG, FLOOD] });
    },
  });
}

function mount(client: ApiClient) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${CANT_READ_REASONS_ROUTE}`]}>
          <Routes>
            <Route path={`/:tenant${CANT_READ_REASONS_ROUTE}`} element={<CantReadReasonsPage client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => cleanup());

describe("Settings → Reference data → Readings → Can't-read reasons", () => {
  it("the READS card opens this screen", () => {
    const card = referenceCard("cant_read_reasons");
    expect(card?.group).toBe("reads");
    expect(card?.kind).toBe("link");
    expect(card?.target).toBe(CANT_READ_REASONS_ROUTE);
  });

  it("draws Name · Type · Status · Used from the server's page, never the code", async () => {
    const sent: Sent[] = [];
    mount(recordingClient(sent, () => undefined));
    const dog = (await screen.findByText("Dog")).closest("tr") as HTMLElement;
    expect(within(dog).getByText("Starting")).toBeInTheDocument();
    expect(within(dog).getByText("On")).toBeInTheDocument();
    expect(within(dog).getByText("4")).toBeInTheDocument();
    const flood = screen.getByText("Flooded pit").closest("tr") as HTMLElement;
    expect(within(flood).getByText("Own")).toBeInTheDocument();
    expect(within(flood).getByText("Off")).toBeInTheDocument();
    expect(flood.textContent ?? "").not.toContain("flooded_pit");
    const list = sent.find((s) => s.method === "GET");
    expect(list?.url).toMatch(/\/settings\/cant-read-reasons\?/);
    expect(list?.url).toMatch(/page=1/);
  });

  it("+ Add reason POSTs the name only", async () => {
    const sent: Sent[] = [];
    mount(recordingClient(sent, (s) => (s.method === "POST" ? json({ ...FLOOD, active: true, used: 0 }, 201) : undefined)));
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: "+ Add reason" }))[0] as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText(/Name/), "Flooded pit");
    await user.click(within(dialog).getByRole("button", { name: "Save ✓" }));
    await waitFor(() => expect(sent.some((s) => s.method === "POST")).toBe(true));
    const post = sent.find((s) => s.method === "POST");
    expect(post?.url).toMatch(/\/settings\/cant-read-reasons$/);
    expect(post?.body).toEqual({ name: "Flooded pit" });
  });

  it("rename PATCHes the name and switch PATCHes active", async () => {
    const sent: Sent[] = [];
    mount(recordingClient(sent, (s) => (s.method === "PATCH" ? json({ ...DOG, name: "Dog in yard" }) : undefined)));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Rename Dog" }));
    const dialog = await screen.findByRole("dialog");
    const field = within(dialog).getByLabelText(/Name/);
    await user.clear(field);
    await user.type(field, "Dog in yard");
    await user.click(within(dialog).getByRole("button", { name: "Save ✓" }));
    await waitFor(() => expect(sent.filter((s) => s.method === "PATCH")).toHaveLength(1));
    expect(sent.find((s) => s.method === "PATCH")?.body).toEqual({ name: "Dog in yard" });
    expect(sent.find((s) => s.method === "PATCH")?.url).toMatch(/\/settings\/cant-read-reasons\/dog$/);

    const flood = screen.getByText("Flooded pit").closest("tr") as HTMLElement;
    await user.click(within(flood).getByRole("button", { name: "Switch on" }));
    await waitFor(() => expect(sent.filter((s) => s.method === "PATCH")).toHaveLength(2));
    expect(sent.filter((s) => s.method === "PATCH")[1]?.body).toEqual({ active: true });
  });

  it("move up POSTs the direction; a starting reason cannot be deleted", async () => {
    const sent: Sent[] = [];
    mount(recordingClient(sent, (s) => (s.method === "POST" ? json(FLOOD) : undefined)));
    const user = userEvent.setup();
    const flood = (await screen.findByText("Flooded pit")).closest("tr") as HTMLElement;
    await user.click(within(flood).getByRole("button", { name: "Move up" }));
    await waitFor(() => expect(sent.some((s) => s.method === "POST")).toBe(true));
    const move = sent.find((s) => s.method === "POST");
    expect(move?.url).toMatch(/\/settings\/cant-read-reasons\/flooded_pit\/move$/);
    expect(move?.body).toEqual({ direction: "up" });

    const dog = screen.getByText("Dog").closest("tr") as HTMLElement;
    const del = within(dog).getByRole("button", { name: "Delete" });
    expect(del).toBeDisabled();
    expect(del).toHaveAttribute("title", "Starting reasons can only be switched off.");
  });

  it("a used reason's delete is refused inline with the way out", async () => {
    const sent: Sent[] = [];
    mount(
      recordingClient(sent, (s) =>
        s.method === "DELETE"
          ? json(
              { code: "BIZ-STATE", message_key: "metering.cantReadReasons.in_use", params: { used: 2 }, br_ref: "BR-FLD-00082" },
              409,
            )
          : undefined,
      ),
    );
    const user = userEvent.setup();
    const flood = (await screen.findByText("Flooded pit")).closest("tr") as HTMLElement;
    await user.click(within(flood).getByRole("button", { name: "Delete" }));
    const confirm = await screen.findByRole("alertdialog");
    await user.click(within(confirm).getByRole("button", { name: "Delete" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("Already used. Switch it off instead.");
    expect(sent.find((s) => s.method === "DELETE")?.url).toMatch(/\/settings\/cant-read-reasons\/flooded_pit$/);
  });
});
