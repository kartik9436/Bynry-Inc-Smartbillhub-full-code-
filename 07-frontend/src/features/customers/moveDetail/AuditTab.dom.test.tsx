// @vitest-environment jsdom
// DEF-CUS-9722 — image 29's *All · Changes · Messages* on a move-in's Audit
// tab, each a SERVER filter (`GET /audit-log?f.entity_id=<account>&f.kind=`),
// never a cut of the page in hand. Image 23 (a request's audit) draws none.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MoveAuditTab, RequestAuditTab } from "./AuditTab";

afterEach(cleanup);

const REGIONAL = { timeZone: "UTC", dateFormat: "MM/DD/YYYY" } as never;

function clientFor() {
  // G98 — the call's shape is typed on `vi.fn`'s generic rather than by two
  // parameters the body never reads (eslint `no-unused-vars`).
  const get = vi.fn<(url: string, opts?: { query?: Record<string, unknown> }) => Promise<unknown>>(async () => ({
    status: 200,
    data: { count: 0, next: null, previous: null, results: [] },
  }));
  return { get, client: { get } as never };
}

function mountTab(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

function kinds(get: ReturnType<typeof vi.fn>): unknown[] {
  return get.mock.calls.map((call) => (call[1] as { query?: Record<string, unknown> } | undefined)?.query?.["f.kind"]);
}

describe("DEF-CUS-9722 · the move-in Audit tab's All / Changes / Messages", () => {
  it("draws the three, All chosen, and asks the server for f.kind=all", async () => {
    const { get, client } = clientFor();
    mountTab(<MoveAuditTab accountId="acc-58" regional={REGIONAL} client={client} />);
    await waitFor(() => expect(get).toHaveBeenCalled());
    const chips = Array.from(document.querySelectorAll("[data-audit-kind]")).map((el) =>
      el.getAttribute("data-audit-kind"),
    );
    expect(chips).toEqual(["all", "changes", "messages"]);
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
    expect(get.mock.calls[0][0]).toBe("/audit-log");
    expect(kinds(get)).toEqual(["all"]);
  });

  it("Messages is a server filter, not a cut of the page", async () => {
    const { get, client } = clientFor();
    mountTab(<MoveAuditTab accountId="acc-58" regional={REGIONAL} client={client} />);
    await waitFor(() => expect(get).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: "Messages" }));
    await waitFor(() => expect(kinds(get)).toContain("messages"));
    const last = get.mock.calls.at(-1)?.[1] as { query: Record<string, unknown> };
    expect(last.query["f.entity_id"]).toBe("acc-58");
    expect(last.query.page).toBe(1);
  });

  it("a request's audit (image 23) draws no filter", async () => {
    const { client } = clientFor();
    mountTab(<RequestAuditTab requestId="req-14" regional={REGIONAL} client={client} />);
    await waitFor(() => expect(document.querySelector("[data-move-group='audit']")).not.toBeNull());
    expect(document.querySelector("[data-audit-kind]")).toBeNull();
  });
});
