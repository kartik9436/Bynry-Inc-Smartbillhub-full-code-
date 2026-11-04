// @vitest-environment jsdom
// DEF-BIL-10052 task 5 — ticking Estimate shows the estimate, marked Estimated.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";
import { createApiClient } from "@/api/client";

import { MoveOutEstimateNote } from "./MoveOutEstimateNote";

afterEach(cleanup);
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function mount(answer: Record<string, unknown>) {
  const asked: string[] = [];
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL) => {
      asked.push(String(input));
      return new Response(JSON.stringify(answer), { status: 200, headers: { "Content-Type": "application/json" } });
    },
  });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MoveOutEstimateNote client={client} accountId="acc-1" meterNo="W-5042" movedOutOn="2026-10-14" t={t} />
    </QueryClientProvider>,
  );
  return asked;
}

describe("DEF-BIL-10052 · the estimate a ticked box shows", () => {
  it("shows the estimated usage with its unit, marked Estimated, asked as of the move-out date", async () => {
    const asked = mount({ estimated: true, consumption: "64.0000", unit: "kgal" });
    expect(await screen.findByText(/64 kgal/)).toBeInTheDocument();
    expect(screen.getByText(t("customers.moveOut.estimate.why"))).toBeInTheDocument();
    expect(asked[0]).toContain("meter_no=W-5042");
    expect(asked[0]).toContain("moved_out_on=2026-10-14");
  });

  it("no history: tells the clerk to enter a reading", async () => {
    mount({ estimated: false, reason: "no_history" });
    expect(await screen.findByText(t("customers.moveOut.estimate.noHistory"))).toBeInTheDocument();
  });
});
