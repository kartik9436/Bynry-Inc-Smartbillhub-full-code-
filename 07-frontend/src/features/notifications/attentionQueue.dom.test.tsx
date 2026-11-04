// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-NOT-10650 (PO 2026-10-29, ruled "1A 2A 3B 4B, start")
// Screens:  S8 (Settings → Notifications → Messages needing attention)
// ───────────────────────────────────────────────────────
// The four rulings, on the mounted tab under its REAL path pattern:
//   1A opens on Needing attention, with a count, and switches to All messages;
//   2A checkboxes only where the server re-queues, a bar that is ABSENT at zero,
//      "Select all N matching" resolved by the SERVER, the tallied toast;
//   3B Fix address and retry posts ONLY the new address, for this message;
//   4B the error details panel shows the last attempt.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import type { OutboundRow } from "@/api/endpoints";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { MESSAGES_SUB, NotificationsTab } from "./SettingsNotificationsTab";

afterEach(cleanup);

const CASE_MS = 120_000;
const MESSAGES_PATH = "/riverside/settings/notifications/messages";

interface Recorded {
  method: "get" | "post";
  path: string;
  query?: Record<string, unknown>;
  body?: unknown;
}

function aRow(id: string, overrides: Partial<OutboundRow> = {}): OutboundRow {
  return {
    id,
    source_type: "invoice",
    source_id: `inv-${id}`,
    account_id: null,
    account_no: null,
    channel: "email",
    copy_no: 0,
    status: "failed",
    held: false,
    held_reason: null,
    attempts: 3,
    last_error: "550 5.1.1 mailbox does not exist",
    batch_id: null,
    provider_reference: "esp-7781-ab",
    template_code: "email_bill_ready",
    template_version: 1,
    template_language: "en",
    recipient_address: `${id}@exmaple.com`,
    unavailable_reason: null,
    queued_at: "2026-10-28T10:00:00Z",
    dispatch_not_before: null,
    last_attempt_at: "2026-10-28T11:00:00Z",
    next_attempt_at: null,
    provider_response: { code: 550, reason: "mailbox does not exist" },
    sent_at: null,
    returned_at: null,
    ...overrides,
  } as OutboundRow;
}

const FAILED = aRow("jo");
const SOFT = aRow("ann", { status: "bounced_soft" });
const HARD = aRow("bo", { status: "bounced_hard" });
const HELD = aRow("cy", { held: true, held_reason: "bad_address" });
const SENT = aRow("di", { status: "sent", last_error: null });

const VOCABULARY = {
  statuses: [],
  channels: [],
  source_types: [],
  unpopulated_statuses: [],
  disclosable_channels: [],
  requeueable_statuses: ["failed", "bounced", "bounced_soft", "queued"],
  retry_to_statuses: ["failed", "bounced", "bounced_hard", "bounced_soft"],
  retry_to_channels: ["email", "sms"],
  selection_cap: 500,
};

function client(
  calls: Recorded[],
  options: { matching?: number; requeue?: unknown; allRows?: OutboundRow[] } = {},
): ApiClient {
  return {
    get: async <T,>(path: string, opts?: { query?: Record<string, unknown> }) => {
      const query = opts?.query ?? {};
      calls.push({ method: "get", path, query });
      if (path === "/outbound/summary") {
        return {
          data: {
            counts: [],
            totals: {},
            held: 0,
            returned: 0,
            retry_exhausted: 0,
            queued_by_channel: {},
            unpopulated_statuses: [],
            problems: [],
          } as T,
        };
      }
      if (path === "/outbound") {
        const attention = query["f.attention"] === "true";
        const rows = attention
          ? [FAILED, SOFT, HARD, HELD]
          : (options.allRows ?? [FAILED, SOFT, HARD, HELD, SENT]);
        return {
          data: {
            count: attention ? (options.matching ?? rows.length) : rows.length,
            next: null,
            previous: null,
            results: rows,
            vocabulary: VOCABULARY,
            attention_count: 4,
          } as T,
        };
      }
      if (path === "/outbound/selection") {
        return {
          data: { message_ids: ["jo", "ann", "bo", "cy", "zz"], count: 5, cap: 500 } as T,
        };
      }
      throw new Error(`not part of this case: ${path}`);
    },
    post: async <T,>(path: string, body?: unknown) => {
      calls.push({ method: "post", path, body });
      if (path === "/outbound/requeue") {
        return {
          data: (options.requeue ?? {
            requeued: ["jo"],
            refused: [{ message_id: "di", code: "already_sent_not_requeueable" }],
            dispatched: false,
            toast: "Re-queued 1 ✓ · 1 refused",
          }) as T,
        };
      }
      if (path.endsWith("/retry-to")) {
        return {
          data: {
            retried_from: "jo",
            message: { id: "new", channel: "email", status: "queued", held: false },
            created: true,
            contact_record_changed: false,
            dispatched: false,
          } as T,
        };
      }
      throw new Error(`not part of this case: ${path}`);
    },
  } as unknown as ApiClient;
}

function mount(api: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <MemoryRouter initialEntries={[MESSAGES_PATH]}>
            <Routes>
              <Route
                path="/:tenant/settings/:tab/:sub"
                element={
                  <NotificationsTab
                    readOnly={false}
                    client={api}
                    sub={MESSAGES_SUB}
                    onOpenRule={() => undefined}
                  />
                }
              />
            </Routes>
          </MemoryRouter>
        </TenantRegionalProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const lists = (calls: Recorded[]) => calls.filter((c) => c.path === "/outbound");

describe("DEF-NOT-10650 1A · the screen opens on Needing attention", () => {
  it("asks for the attention view first, shows its count, and switches", async () => {
    const user = userEvent.setup({ delay: null });
    const calls: Recorded[] = [];
    mount(client(calls));
    await screen.findByText("jo@exmaple.com");

    expect(lists(calls)[0].query?.["f.attention"]).toBe("true");
    const attention = screen.getByRole("tab", { name: /Needing attention/ });
    expect(attention).toHaveAttribute("aria-selected", "true");
    expect(attention).toHaveTextContent("4");
    expect(screen.queryByText("di@exmaple.com")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "All messages" }));
    expect(await screen.findByText("di@exmaple.com")).toBeInTheDocument();
    expect(lists(calls).at(-1)?.query?.["f.attention"]).toBeUndefined();
  }, CASE_MS);
});

describe("DEF-NOT-10650 2A · selection", () => {
  it("draws a checkbox only where the server re-queues, and no bar at zero", async () => {
    const calls: Recorded[] = [];
    mount(client(calls));
    await screen.findByText("jo@exmaple.com");

    const boxes = screen.getAllByTestId("queue-row-select");
    // failed + bounced (soft) — never the hard bounce, never the held row.
    expect(boxes).toHaveLength(2);
    expect(screen.getByRole("checkbox", { name: "Select jo@exmaple.com" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Select bo@exmaple.com" })).toBeNull();
    expect(screen.queryByRole("checkbox", { name: "Select cy@exmaple.com" })).toBeNull();
    // ⚠ Empty never means all: with nothing ticked there is no Re-queue to press.
    expect(screen.queryByTestId("queue-selection-bar")).toBeNull();
    expect(screen.queryByTestId("queue-bulk-requeue")).toBeNull();
  }, CASE_MS);

  it("re-queues exactly the ticked ids and tallies each row in the toast", async () => {
    const user = userEvent.setup({ delay: null });
    const calls: Recorded[] = [];
    mount(client(calls));
    await screen.findByText("jo@exmaple.com");

    await user.click(screen.getByRole("checkbox", { name: "Select jo@exmaple.com" }));
    const bar = screen.getByTestId("queue-selection-bar");
    expect(bar).toHaveTextContent("1 selected");
    await user.click(within(bar).getByRole("button", { name: "Re-queue" }));

    await waitFor(() => {
      expect(calls.some((c) => c.path === "/outbound/requeue")).toBe(true);
    });
    const post = calls.find((c) => c.path === "/outbound/requeue");
    expect(post?.body).toEqual({ message_ids: ["jo"] });
    expect(await screen.findByText("1 re-queued. 1 could not be: already sent.")).toBeInTheDocument();
    // The selection is spent: the bar is gone.
    await waitFor(() => {
      expect(screen.queryByTestId("queue-selection-bar")).toBeNull();
    });
  }, CASE_MS);

  it("Select all on this page ticks the eligible rows only", async () => {
    const user = userEvent.setup({ delay: null });
    const calls: Recorded[] = [];
    mount(client(calls));
    await screen.findByText("jo@exmaple.com");

    await user.click(screen.getByRole("checkbox", { name: "Select all on this page" }));
    expect(screen.getByTestId("queue-selection-bar")).toHaveTextContent("2 selected");
  }, CASE_MS);

  it("Select all N matching is resolved by the SERVER from the same filter", async () => {
    const user = userEvent.setup({ delay: null });
    const calls: Recorded[] = [];
    mount(client(calls, { matching: 120 }));
    await screen.findByText("jo@exmaple.com");

    await user.click(screen.getByRole("checkbox", { name: "Select jo@exmaple.com" }));
    await user.click(screen.getByRole("button", { name: "Select all 120 matching" }));

    await waitFor(() => {
      expect(screen.getByTestId("queue-selection-bar")).toHaveTextContent("5 selected");
    });
    const asked = calls.find((c) => c.path === "/outbound/selection");
    expect(asked?.query?.["f.attention"]).toBe("true");
    await user.click(screen.getByRole("button", { name: "Re-queue" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path === "/outbound/requeue")?.body).toEqual({
        message_ids: ["jo", "ann", "bo", "cy", "zz"],
      });
    });
  }, CASE_MS);

  it("above the cap the explicit action is disabled and says why", async () => {
    const user = userEvent.setup({ delay: null });
    const calls: Recorded[] = [];
    mount(client(calls, { matching: 501 }));
    await screen.findByText("jo@exmaple.com");

    await user.click(screen.getByRole("checkbox", { name: "Select jo@exmaple.com" }));
    expect(screen.getByRole("button", { name: "Select all 501 matching" })).toBeDisabled();
    expect(screen.getByTestId("queue-selection-bar")).toHaveTextContent("At most 500 at once.");
    expect(calls.some((c) => c.path === "/outbound/selection")).toBe(false);
  }, CASE_MS);
});

describe("DEF-NOT-10654 · Try again only where the server re-queues", () => {
  it("is disabled with its reason on a hard bounce, as on a held row", async () => {
    mount(client([]));
    await screen.findByText("jo@exmaple.com");

    const tries = screen.getAllByRole("button", { name: "Try again" });
    // FAILED, SOFT, HARD, HELD — in the order the mock serves them.
    expect(tries[0]).toBeEnabled();
    expect(tries[1]).toBeEnabled();
    expect(tries[2]).toBeDisabled();
    expect(tries[2]).toHaveAttribute("title", "The address refused it. Fix the address instead.");
    expect(tries[3]).toBeDisabled();
  }, CASE_MS);
});

describe("DEF-NOT-10650 4B · error details", () => {
  it("shows the last attempt: error, provider reference and its response", async () => {
    const user = userEvent.setup({ delay: null });
    mount(client([]));
    await screen.findByText("jo@exmaple.com");

    await user.click(screen.getAllByRole("button", { name: "Error details" })[0]);
    const panel = await screen.findByTestId("queue-error-details");
    expect(within(panel).getByTestId("queue-error-last")).toHaveTextContent(
      "550 5.1.1 mailbox does not exist",
    );
    expect(within(panel).getByTestId("queue-error-reference")).toHaveTextContent("esp-7781-ab");
    expect(within(panel).getByTestId("queue-error-response")).toHaveTextContent('"code": 550');
    expect(within(panel).getByText("Provider's reference")).toBeInTheDocument();
    // B14 rule 31 — our own message id is never on screen.
    expect(panel).not.toHaveTextContent(/\bjo\b(?!@)/);
  }, CASE_MS);
});

describe("DEF-NOT-10650 3B · Fix address and retry", () => {
  it("says it is this message only, and posts only the new address", async () => {
    const user = userEvent.setup({ delay: null });
    const calls: Recorded[] = [];
    mount(client(calls));
    await screen.findByText("jo@exmaple.com");

    // Offered on the failed email and the hard bounce, never on the held row.
    expect(screen.getAllByTestId("queue-retry-to")).toHaveLength(3);
    await user.click(screen.getAllByTestId("queue-retry-to")[0]);
    expect(await screen.findByTestId("retry-to-scope")).toHaveTextContent(
      "Only this message. The customer's contact is unchanged.",
    );

    const field = screen.getByLabelText(/New email address/);
    await user.type(field, "not-an-email");
    await user.click(screen.getByRole("button", { name: "Retry ✓" }));
    expect((await screen.findAllByText("Enter a valid email address.")).length).toBeGreaterThan(0);
    expect(calls.some((c) => c.path.endsWith("/retry-to"))).toBe(false);

    await user.clear(field);
    await user.type(field, "jo@example.com");
    await user.click(screen.getByRole("button", { name: "Retry ✓" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/retry-to"))).toBe(true);
    });
    const post = calls.find((c) => c.path.endsWith("/retry-to"));
    expect(post?.path).toBe("/outbound/jo/retry-to");
    expect(post?.body).toEqual({ address: "jo@example.com" });
    expect(await screen.findByText("Queued to jo@example.com.")).toBeInTheDocument();
  }, CASE_MS);
});

describe("DEF-NOT-10665 · a failure retried to a new address (PO 2026-10-29, D1 A)", () => {
  it("says Retried to a new address under All messages", async () => {
    const user = userEvent.setup({ delay: null });
    const calls: Recorded[] = [];
    const RETRIED = aRow("ed", { retried_to_new_address: true });
    mount(client(calls, { allRows: [RETRIED, SENT] }));
    await screen.findByText("jo@exmaple.com");
    // The server leaves it out of Needing attention; the screen never asks again.
    expect(screen.queryByText("ed@exmaple.com")).toBeNull();

    await user.click(screen.getByRole("tab", { name: "All messages" }));
    const cell = await screen.findByText("ed@exmaple.com");
    const row = cell.closest("tr") as HTMLElement;
    expect(within(row).getByTestId("queue-row-retried")).toHaveTextContent(
      "Retried to a new address",
    );
    const sent = (await screen.findByText("di@exmaple.com")).closest("tr") as HTMLElement;
    expect(within(sent).queryByTestId("queue-row-retried")).toBeNull();
  }, CASE_MS);
});
