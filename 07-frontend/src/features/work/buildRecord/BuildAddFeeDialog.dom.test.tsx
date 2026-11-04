// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-163-BRC10 item 2 — Add a fee after submission.
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** A form that posted a figure it
// multiplied itself would pass a "a request went out" case. So every case
// reads the BODY: a priced code travels as a COUNT and its basis with NO
// amount, and only a code priced "entered when used" carries the clerk's
// figure — BR-BIL-020 asserted on the wire.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import { BuildAddFeeDialog, canBeAddedAfterSubmission } from "./BuildAddFeeDialog";

const BUILD = "01a0fdd1-a7b8-7f20-bf15-c0351b7555dc";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function charge(code: string, over: Record<string, unknown>) {
  return {
    id: `id-${code}`,
    code,
    name: `${code} name`,
    charge_type: "one_time",
    service: null,
    amount_rule: "flat",
    amount: "45.000000",
    percent: null,
    min_amount: null,
    max_amount: null,
    amount_display: "45.00",
    percent_display: null,
    min_amount_display: null,
    max_amount_display: null,
    gl_account_id: "gl-1",
    ...over,
  };
}

const CATALOGUE = [
  charge("CONN", {}),
  charge("TAP", { amount_rule: "per_case", amount: null, amount_display: null }),
  charge("LATE", { amount_rule: "percent_with_minimum", amount: null }),
  charge("NOGL", { gl_account_id: null }),
  charge("BASE-W", { charge_type: "recurring" }),
];

function mount(post: (body: unknown) => Response) {
  const bodies: unknown[] = [];
  const client = createApiClient({
    tenant: "sixrivers",
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/charges")) {
        return new Response(
          JSON.stringify({ count: 5, next: null, previous: null, results: CATALOGUE }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes(`/connections/${BUILD}/fees`) && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        bodies.push(body);
        return post(body);
      }
      return new Response("{}", { status: 404 });
    },
  });
  const onAdded = vi.fn();
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <BuildAddFeeDialog
        t={t}
        connectionId={BUILD}
        timeZone="UTC"
        dateFormat="MM/DD/YYYY"
        client={client}
        onClose={() => undefined}
        onAdded={onAdded}
      />
    </QueryClientProvider>,
  );
  return { bodies, onAdded };
}

const ok = () =>
  new Response(
    JSON.stringify({
      invoice_no: "BL-2610-000103",
      invoice_id: "inv",
      total: "45.000000",
      charge_code: "CONN",
    }),
    { status: 201, headers: { "Content-Type": "application/json" } },
  );

describe("CR-163-BRC10 item 2 · Add fee", () => {
  it("offers a flat priced code and an entered-when-used code — never a percent, a recurring code or a code with no GL", async () => {
    mount(ok);
    const code = (await screen.findByLabelText(/^Charge/)) as HTMLSelectElement;
    await waitFor(() => expect(code.options.length).toBe(3));
    expect(Array.from(code.options).map((one) => one.value)).toEqual(["", "CONN", "TAP"]);
    expect(canBeAddedAfterSubmission(CATALOGUE[2] as never)).toBe(false);
    expect(canBeAddedAfterSubmission(CATALOGUE[3] as never)).toBe(false);
    expect(canBeAddedAfterSubmission(CATALOGUE[4] as never)).toBe(false);
  });

  it("a priced code posts a COUNT and its basis, and NO amount", async () => {
    const { bodies, onAdded } = mount(ok);
    const code = (await screen.findByLabelText(/^Charge/)) as HTMLSelectElement;
    await waitFor(() => expect(code.options.length).toBe(3));
    fireEvent.change(code, { target: { value: "CONN" } });
    // The catalogue's own display price, read only.
    expect((screen.getByLabelText(/^Each/) as HTMLInputElement).value).toBe("45.00");
    expect((screen.getByLabelText(/^Each/) as HTMLInputElement).readOnly).toBe(true);
    fireEvent.change(screen.getByLabelText(/^Qty/), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText(/^Counted per/), { target: { value: "per unit" } });
    fireEvent.change(screen.getByLabelText(/^Posting date/), { target: { value: "2026-10-03" } });
    fireEvent.change(screen.getByLabelText(/^Payment terms/), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Add the fee" }));
    await waitFor(() => expect(onAdded).toHaveBeenCalledWith("BL-2610-000103"));
    expect(bodies[0]).toEqual({
      charge_code: "CONN",
      quantity: "2",
      basis: "per unit",
      posting_date: "2026-10-03",
      due_days: 30,
    });
  });

  it("an entered-when-used code posts the clerk's amount and NO count", async () => {
    const { bodies } = mount(ok);
    const code = (await screen.findByLabelText(/^Charge/)) as HTMLSelectElement;
    await waitFor(() => expect(code.options.length).toBe(3));
    fireEvent.change(code, { target: { value: "TAP" } });
    expect(screen.queryByLabelText(/^Qty/)).toBeNull();
    fireEvent.change(screen.getByLabelText(/^Amount/), { target: { value: "310.00" } });
    fireEvent.change(screen.getByLabelText(/^Posting date/), { target: { value: "2026-10-03" } });
    fireEvent.change(screen.getByLabelText(/^Payment terms/), { target: { value: "15" } });
    fireEvent.click(screen.getByRole("button", { name: "Add the fee" }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({
      charge_code: "TAP",
      amount: "310.00",
      posting_date: "2026-10-03",
      due_days: 15,
    });
  });

  it("the server's same-day refusal stays in the dialog, in its own words (OQ-BIL-12377)", async () => {
    const { onAdded } = mount(
      () =>
        new Response(
          JSON.stringify({
            code: "BIZ-STATE",
            message_key: "metering.connection.feeSameDay",
            params: { day: "2026-10-03" },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
    );
    const code = (await screen.findByLabelText(/^Charge/)) as HTMLSelectElement;
    await waitFor(() => expect(code.options.length).toBe(3));
    fireEvent.change(code, { target: { value: "CONN" } });
    fireEvent.change(screen.getByLabelText(/^Counted per/), { target: { value: "per premise" } });
    fireEvent.change(screen.getByLabelText(/^Posting date/), { target: { value: "2026-10-03" } });
    fireEvent.change(screen.getByLabelText(/^Payment terms/), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Add the fee" }));
    await waitFor(() =>
      expect(screen.getByText(t("metering.connection.feeSameDay"))).toBeInTheDocument(),
    );
    expect(onAdded).not.toHaveBeenCalled();
  });
});
