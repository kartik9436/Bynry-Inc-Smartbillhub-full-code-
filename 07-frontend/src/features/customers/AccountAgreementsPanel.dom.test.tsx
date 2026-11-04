// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Change:   CR-190-BRC10 lane AGREEMENT — Sent / Accepted / Expired on the
//           account, and Resend agreement
// Cases:    each status draws its own word · Resend posts to the request's own
//           address and is offered only on Sent and Expired · a read-only role
//           sees Resend disabled with its reason · an account never sent one
//           draws nothing · the header chip shows the newest per agreement
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { AccountAgreementsPanel, AgreementStatusChip } from "./AccountAgreementsPanel";
import type { AccountAgreement } from "./agreementsApi";

function row(over: Partial<AccountAgreement>): AccountAgreement {
  return {
    id: "r-1",
    template_code: "contract_service_agreement",
    agreement_name: "Service agreement",
    version: 2,
    status: "pending",
    issued_at: "2026-10-22T10:00:00Z",
    expires_at: "2026-10-29T10:00:00Z",
    accepted_at: null,
    accepted_date: null,
    accepted_name: null,
    accepted_document_id: null,
    sent_by_email: true,
    sent_by_letter: false,
    ...over,
  };
}

function client(rows: AccountAgreement[]) {
  const post = vi.fn(async (_path: string, _body: unknown) => ({ data: row({ id: "r-new" }), status: 201 }));
  const api = {
    get: vi.fn(async () => ({ data: { results: rows }, status: 200 })),
    post,
  } as unknown as ApiClient;
  return { api, post };
}

function draw(node: React.ReactElement) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>{node}</ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("the account's agreements (CR-190-BRC10)", () => {
  it("draws each status and offers Resend only where a new link helps", async () => {
    const { api, post } = client([
      row({ id: "a", status: "pending" }),
      row({ id: "b", status: "expired", template_code: "contract_deposit", agreement_name: "Deposit agreement" }),
      row({ id: "c", status: "accepted", accepted_date: "2026-10-20", accepted_name: "Ana Ruiz", accepted_document_id: "f-1" }),
      row({ id: "d", status: "voided" }),
    ]);
    draw(<AccountAgreementsPanel accountId="acc-1" timeZone="UTC" dateFormat="MM/DD/YYYY" writeBlockedReason={null} client={api} />);
    expect(await screen.findByText("Expired")).toBeInTheDocument();
    expect(screen.getByText("Sent", { selector: "span.pill" })).toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();
    expect(screen.getByText("Replaced")).toBeInTheDocument();
    const resends = screen.getAllByRole("button", { name: "Resend agreement" });
    expect(resends).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Open signed copy" })).toHaveLength(1);
    await userEvent.setup().click(resends[0]);
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toBe("/accounts/acc-1/agreements/a/resend");
  });

  it("a read-only role sees Resend disabled", async () => {
    const { api } = client([row({ status: "pending" })]);
    draw(<AccountAgreementsPanel accountId="acc-1" timeZone="UTC" dateFormat="MM/DD/YYYY" writeBlockedReason="Read only" client={api} />);
    const resend = await screen.findByRole("button", { name: "Resend agreement" });
    expect(resend).toBeDisabled();
  });

  it("a replaced request offers no second resend", async () => {
    const { api } = client([row({ id: "new", status: "pending" }), row({ id: "old", status: "expired" })]);
    draw(<AccountAgreementsPanel accountId="acc-1" timeZone="UTC" dateFormat="MM/DD/YYYY" writeBlockedReason={null} client={api} />);
    expect(await screen.findAllByRole("button", { name: "Resend agreement" })).toHaveLength(1);
  });

  it("an account never sent one draws nothing", async () => {
    const { api } = client([]);
    const { container } = draw(
      <AccountAgreementsPanel accountId="acc-1" timeZone="UTC" dateFormat="MM/DD/YYYY" writeBlockedReason={null} client={api} />,
    );
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(container.querySelector("[data-overview-group='agreements']")).toBeNull();
  });

  it("the header chip shows the newest request of each agreement", async () => {
    const { api } = client([row({ id: "new", status: "pending" }), row({ id: "old", status: "voided" })]);
    draw(<AgreementStatusChip accountId="acc-1" client={api} />);
    // (and in the panel, only the newest of the two may be resent — below)
    expect(await screen.findByText("Sent")).toBeInTheDocument();
    expect(screen.queryByText("Replaced")).toBeNull();
  });
});
