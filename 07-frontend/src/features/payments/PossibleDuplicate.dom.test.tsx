// @vitest-environment jsdom
// DEF-PAY-9263 · BR-PAY-1199 — "Looks like a duplicate" on a card or ACH
// payment (PO 2026-10-03: *"Warn "Looks like a duplicate", and let the clerk
// confirm"*). The ruled case: a second $30.00 card payment, same account, same
// day, reference AUTH-S8-0030. The server answers 409 naming the first one;
// the dialog shows it with *Go back* and *Record anyway*; *Record anyway*
// resends the same body with `confirm_duplicate: true`.
//
// RED FIRST: before the panel was wired, the 409 rendered as the generic
// refusal line and no `Record anyway` button existed, so the second test below
// failed at `findByRole("button", { name: "Record anyway" })`.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { ApiError, createApiClient } from "@/api/client";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";
import { BuildTakePaymentDialog } from "@/features/customers/BuildDetailDialogs";
import { ACCOUNT_ID, TENANT } from "@/features/customers/buildDetailFixture";

import { PossibleDuplicateNotice, possibleDuplicateOf } from "./PossibleDuplicate";

const t = (key: string, params?: Record<string, unknown>) => String(params?.defaultValue ?? key);

const WARNING = {
  code: "BIZ-IDEMPOTENT",
  message_key: "payments.record.possible_duplicate",
  br_ref: "BR-PAY-1199",
  params: {
    possible_duplicate: true,
    payment_id: "p-1",
    payment_no: "PY-261002-0093",
    posted_on: "2026-10-02",
    amount: "30.0000",
    currency: "USD",
    confirmation: "AUTH-S8-0030",
    method: "card",
  },
  field_errors: [],
};

interface Call {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

function stub(calls: Call[]) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body = typeof init?.body === "string" ? JSON.parse(init.body) : null;
      calls.push({ method, url, body });
      const json = (b: unknown, status = 200) =>
        new Response(JSON.stringify(b), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      if (method === "POST" && url.includes("/payments")) {
        return body?.confirm_duplicate === true
          ? json(
              {
                id: "p-2",
                payment_no: "PY-261002-0094",
                created: true,
                status: "cleared",
                amount: "30.0000",
                currency: "USD",
                problems: [],
              },
              201,
            )
          : json(WARNING, 409);
      }
      if (url.includes("/payments")) {
        return json({ methods: [{ code: "card", name: "Card" }], count: 0, results: [] });
      }
      return json({ count: 0, results: [] });
    },
  });
}

function open(calls: Call[], onClose: () => void) {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <TenantRegionalProvider value={{ timeZone: "UTC", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/connections/abc?tab=charges`]}>
            <Routes>
              <Route
                path="/:tenant/connections/:connectionId"
                element={
                  <BuildTakePaymentDialog
                    t={t}
                    accountId={ACCOUNT_ID}
                    accountNo="AC-2026-00060"
                    ownerName={null}
                    invoiceNo="INV-26-0318"
                    outstanding={{ stored: "30.0000", display: "$30.00" }}
                    timeZone="UTC"
                    dateFormat="MM/DD/YYYY"
                    client={stub(calls)}
                    onClose={onClose}
                  />
                }
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

async function fillCard() {
  await screen.findByRole("option", { name: "Card" });
  fireEvent.change(document.querySelector("#method") as HTMLSelectElement, {
    target: { value: "card" },
  });
  await waitFor(() => expect(document.querySelector("#confirmation")).not.toBeNull());
  fireEvent.change(document.querySelector("#confirmation") as HTMLInputElement, {
    target: { value: "AUTH-S8-0030" },
  });
}

describe("DEF-PAY-9263 · Looks like a duplicate", () => {
  afterEach(cleanup);

  it("reads the warning off the envelope, and nothing else", () => {
    const warning = new ApiError(409, WARNING as never);
    expect(possibleDuplicateOf(warning)).toEqual({
      paymentNo: "PY-261002-0093",
      postedOn: "2026-10-02",
      amount: "30.0000",
      currency: "USD",
      confirmation: "AUTH-S8-0030",
      matchedOn: "",
    });
    const refusal = new ApiError(422, {
      code: "BIZ-COMPLETENESS",
      message_key: "payments.record.refused",
      params: {},
      field_errors: [],
    } as never);
    expect(possibleDuplicateOf(refusal)).toBeNull();
    expect(possibleDuplicateOf(new Error("x"))).toBeNull();
  });

  it("names the earlier payment; Record anyway resends with the confirm flag", async () => {
    const calls: Call[] = [];
    let closed = false;
    open(calls, () => {
      closed = true;
    });
    await fillCard();
    fireEvent.click(screen.getByRole("button", { name: "Take payment" }));
    const panel = await screen.findByRole("alert");
    expect(panel).toHaveTextContent("Looks like a duplicate");
    // DEF-PAY-10776 — the warning takes focus, so the next Tab reaches Go back.
    expect(panel).toHaveFocus();
    // DEF-PAY-10774 — the sentence states what the matcher compares (Q1 = A:
    // account + amount + day, against a bill already paid), never "reference".
    expect(panel).toHaveTextContent("Same amount, same day. The bill is paid.");
    expect(panel).not.toHaveTextContent("Same amount, reference and day.");
    expect(panel).toHaveTextContent("PY-261002-0093");
    expect(panel).toHaveTextContent("10/02/2026");
    expect(panel).toHaveTextContent("$30.00");
    expect(panel).toHaveTextContent("AUTH-S8-0030");
    expect(closed).toBe(false);
    const first = calls.filter((c) => c.method === "POST");
    expect(first).toHaveLength(1);
    expect(first[0].body?.confirm_duplicate).toBeUndefined();

    fireEvent.click(screen.getByRole("button", { name: "Record anyway" }));
    await waitFor(() => expect(closed).toBe(true));
    const posts = calls.filter((c) => c.method === "POST");
    expect(posts).toHaveLength(2);
    expect(posts[1].body?.confirm_duplicate).toBe(true);
    // The same form, the same token: nothing else about the payment moved.
    expect(posts[1].body?.idempotency_key).toBe(posts[0].body?.idempotency_key);
    expect(posts[1].body?.amount).toBe(posts[0].body?.amount);
  });

  it("Go back clears the panel and sends nothing", async () => {
    const calls: Call[] = [];
    open(calls, () => undefined);
    await fillCard();
    fireEvent.click(screen.getByRole("button", { name: "Take payment" }));
    await screen.findByRole("button", { name: "Record anyway" });
    fireEvent.click(screen.getByRole("button", { name: "Go back" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Record anyway" })).toBeNull());
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
  });
});

// ── DEF-PAY-10782 (PO 2026-10-31 P8 = A) ──────────────────────────────────
// A repeated card/ACH reference is warned on an OPEN bill too, so the sentence
// must name the reference and never claim "The bill is paid.". RED FIRST: on
// the tip the panel said "Same amount, same day. The bill is paid." here.
describe("DEF-PAY-10782 · the warning says which match fired", () => {
  afterEach(cleanup);

  it("a repeated AUTH 88412 on an open bill reads 'Same reference, same day.'", () => {
    const earlier = possibleDuplicateOf(
      new ApiError(409, {
        ...WARNING,
        params: { ...WARNING.params, confirmation: "AUTH 88412", matched_on: "reference" },
      } as never),
    );
    expect(earlier?.matchedOn).toBe("reference");
    render(<PossibleDuplicateNotice earlier={earlier!} onGoBack={() => undefined} onRecordAnyway={() => undefined} />);
    const panel = screen.getByRole("alert");
    expect(panel).toHaveTextContent("Same reference, same day.");
    expect(panel).not.toHaveTextContent("The bill is paid.");
    expect(panel).toHaveTextContent("AUTH 88412");
  });
});
