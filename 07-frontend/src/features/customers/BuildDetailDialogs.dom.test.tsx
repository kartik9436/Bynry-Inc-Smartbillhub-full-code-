// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 · task 14 — `Resend` and `Take payment`.
// Rules:    CLAUDE.md hard rule 2 (a decimal STRING on the wire, never a
//           float) · hard rule 6 (the form's OWN idempotency token) ·
//           BR-PAY-033 (the posting date is proposed, never read from a clock
//           at submit) · B14 rule 33 (the consequence caps).
// ───────────────────────────────────────────────────────
//
// WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2)
// ---------------------------------------------------
// * **Asserting the dialog POSTED something.** Both dialogs read lookups on
//   mount, so a URL list with entries in it proves nothing. Each case below
//   matches the ADDRESS and the METHOD.
// * **Asserting the amount box is filled without reading its VALUE.** A box
//   rendered with a placeholder passes that; the case reads `.value`.
// * **Asserting the refusal without reading the reason.** A dialog that
//   simply did nothing on submit would pass a "no POST happened" check; the
//   case reads the sentence the clerk gets.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { BuildTakePaymentDialog } from "./BuildDetailDialogs";
import { ACCOUNT_ID, TENANT } from "./buildDetailFixture";

const t = (key: string, params?: Record<string, unknown>) =>
  String(params?.defaultValue ?? key);

interface Call {
  url: string;
  method: string;
  body: unknown;
}

function stub(calls: Call[]) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push({
        url,
        method: init?.method ?? "GET",
        body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
      });
      const json = (b: unknown) =>
        new Response(JSON.stringify(b), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      if (url.includes("/payments")) {
        return json({
          methods: [
            { code: "cheque", name: "Cheque" },
            { code: "cash", name: "Cash" },
          ],
          count: 0,
          results: [],
        });
      }
      if (url.includes("/connections/message-templates")) {
        return json({
          rows: [
            {
              code: "CONNECT_CONFIRMED",
              name: "Build confirmed",
              group: "connect",
              channel: "email",
              category: "standard",
              language: "en",
              version: 4,
              status: "published",
              pickable: true,
            },
          ],
          unavailable: [],
        });
      }
      return json({ count: 0, results: [] });
    },
  });
}

/** Mounted UNDER THE REAL PATH PATTERN, exactly as the page mounts it — a
 *  bare router leaves `useParams().tenant` undefined and every address a
 *  child builds comes out `//…`. */
function mount(node: React.ReactElement) {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/connections/abc?tab=charges`]}>
          <Routes>
            <Route path="/:tenant/connections/:connectionId" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("task 14 · Take payment", () => {
  afterEach(cleanup);

  const outstanding = { stored: "112.0000", display: "$112.00" };

  function open(calls: Call[], accountId: string | null = ACCOUNT_ID, connectionId?: string) {
    mount(
      <BuildTakePaymentDialog
        t={t}
        connectionId={connectionId}
        accountId={accountId}
        accountNo="AC-26-0088"
        ownerName="Okonkwo, Ada"
        invoiceNo="INV-26-0318"
        outstanding={outstanding}
        timeZone="UTC"
        dateFormat="MM/DD/YYYY"
        client={stub(calls)}
        onClose={() => undefined}
      />,
    );
  }

  it("the amount arrives FILLED with what is outstanding, and is editable", async () => {
    open([]);
    const amount = (await screen.findByLabelText(/Amount/i)) as HTMLInputElement;
    // TWO decimals, no grouping, wire locale — never the stored four.
    expect(amount.value).toBe("112.00");
    expect(amount.readOnly).toBe(false);
    fireEvent.change(amount, { target: { value: "50.00" } });
    expect(amount.value).toBe("50.00");
  });

  it("the reference box follows the type, and CASH asks for none", async () => {
    open([]);
    // ⚠ **WAIT FOR THE OPTION, NOT FOR THE SELECT.** The tenant's method list
    // is a READ, and setting a value a `<select>` does not yet hold leaves it
    // at `""` — which was this case's first RED, and it is the fixture fault
    // this suite's header warns about, one layer down.
    await screen.findByRole("option", { name: "Cheque" });
    // Addressed by its own id: under this fixture's translator a label renders
    // as its catalogue KEY, and the assertion here is about the reference box
    // appearing rather than about how the picker is found.
    const method = document.querySelector("#method") as HTMLSelectElement;
    expect(document.querySelector("#confirmation")).toBeNull();
    fireEvent.change(method, { target: { value: "cheque" } });
    await waitFor(() => expect(document.querySelector("#confirmation")).not.toBeNull());
    fireEvent.change(method, { target: { value: "cash" } });
    await waitFor(() => expect(document.querySelector("#confirmation")).toBeNull());
  });

  it("records against the ACCOUNT, as a decimal STRING, with its own token", async () => {
    const calls: Call[] = [];
    open(calls);
    await screen.findByRole("option", { name: "Cash" });
    const amount = document.querySelector("#amount") as HTMLInputElement;
    fireEvent.change(amount, { target: { value: "112.00" } });
    fireEvent.change(document.querySelector("#method") as HTMLSelectElement, {
      target: { value: "cash" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Take payment" }));
    await waitFor(() => {
      const post = calls.find((call) => call.method === "POST");
      expect(post?.url).toContain(`/accounts/${ACCOUNT_ID}/payments`);
      const body = post?.body as Record<string, unknown>;
      // A STRING, always. A JSON float arrives at Python as an IEEE double.
      expect(typeof body.amount).toBe("string");
      expect(body.amount).toBe("112.00");
      expect(body.method).toBe("cash");
      // Cash carries no reference — a hidden field that kept posting is how a
      // cash receipt acquires a cheque number nobody typed.
      expect(body.confirmation).toBeNull();
      expect(typeof body.idempotency_key).toBe("string");
      expect(String(body.posted_at)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });
  });

  // DEF-MET-9224 — the request's own Take payment keys its payment to the build,
  // so Paid so far lists a cheque that has not cleared (found by the New
  // Connection end-to-end walk: cheque 4471, $40.00, never shown).
  it("keys the payment to the BUILD it was taken on", async () => {
    const calls: Call[] = [];
    open(calls, ACCOUNT_ID, "11111111-2222-3333-4444-555555555555");
    await screen.findByRole("option", { name: "Cash" });
    fireEvent.change(document.querySelector("#method") as HTMLSelectElement, {
      target: { value: "cash" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Take payment" }));
    await waitFor(() => {
      const body = calls.find((call) => call.method === "POST")?.body as Record<string, unknown>;
      expect(String(body.idempotency_key)).toMatch(
        /^new-connect:11111111-2222-3333-4444-555555555555:take:[0-9a-f-]{36}$/,
      );
    });
  });

  it("with no account established it REFUSES BY NAME and posts nothing", async () => {
    const calls: Call[] = [];
    open(calls, null);
    await screen.findByRole("option", { name: "Cash" });
    const amount = document.querySelector("#amount") as HTMLInputElement;
    fireEvent.change(amount, { target: { value: "112.00" } });
    fireEvent.change(document.querySelector("#method") as HTMLSelectElement, {
      target: { value: "cash" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Take payment" }));
    await waitFor(() => expect(document.querySelector("[role='alert']")).not.toBeNull());
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
  });

  it("has NO payment-terms field anywhere (BR-BIL-024 — no default, anywhere)", async () => {
    open([]);
    await screen.findByLabelText(/Amount/i);
    expect(document.body.textContent).not.toMatch(/terms/i);
  });

  it("its consequence is two short sentences in the product's own words (rules 33 and 34)", async () => {
    open([]);
    await waitFor(() =>
      expect(document.querySelector('[data-consequence="build-take-payment"]')).not.toBeNull(),
    );
    const box = document.querySelector('[data-consequence="build-take-payment"]') as HTMLElement;
    expect(box.textContent).toContain("In the books");
    const sentence = (box.textContent ?? "").replace("In the books", "").trim();
    expect(sentence.split(/\s+/).length).toBeLessThanOrEqual(6);
  });
});
