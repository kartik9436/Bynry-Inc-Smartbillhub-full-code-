// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-163-BRC10 item 1 · DEF-CUS-9177 — the build detail's Raise
//           work order form.
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** The defect was a POST that WAS
// made — with a literal type and nothing a clerk chose. So nothing here asserts
// merely that a request went out: every case reads the BODY and asserts each
// of the four choices travelled, and the refusal case asserts the server's own
// sentence is on screen.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import { BuildRaiseOrderDialog, raiseOrderBody } from "./BuildRaiseOrderDialog";

const BUILD = "01a0fdd1-a7b8-7f20-bf15-c0351b7555dc";
const UNIT = "01a0fdd1-0000-7000-8000-0000000000u2";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function template(id: string, name: string, service: string, version: number) {
  return {
    id,
    template_no: version > 0 ? `ST-${id}` : null,
    name,
    service: { id: `svc-${service}`, code: service, name: service },
    scope: "per_premise",
    sequence: 0,
    job_type: null,
    skill: null,
    safety_kit: null,
    crew_size: 1,
    est_duration_minutes: null,
    is_gate: false,
    no_gate_reason: null,
    is_sample: false,
    active: true,
    version,
    contents: {},
    status: version > 0 ? "published" : "draft",
  };
}

function mount(post: (body: unknown) => Response) {
  const bodies: unknown[] = [];
  const client = createApiClient({
    tenant: "sixrivers",
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/work/templates")) {
        return new Response(
          JSON.stringify({
            count: 3,
            next: null,
            previous: null,
            results: [
              template("t-solar", "Solar inspection", "solar", 1),
              template("t-water", "Installation Template", "water", 2),
              template("t-draft", "Not published", "solar", 0),
            ],
            counts: { published: 2, draft: 1, inactive: 0 },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/work-orders") && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        bodies.push(body);
        return post(body);
      }
      return new Response("{}", { status: 404 });
    },
  });
  const onRaised = vi.fn();
  const onClose = vi.fn();
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <BuildRaiseOrderDialog
        t={t}
        connectionId={BUILD}
        services={["battery", "solar"]}
        units={[
          { id: "01a0fdd1-0000-7000-8000-0000000000u1", label: "Suite 101" },
          { id: UNIT, label: "Suite 102" },
        ]}
        dateFormat="MM/DD/YYYY"
        client={client}
        onClose={onClose}
        onRaised={onRaised}
      />
    </QueryClientProvider>,
  );
  return { bodies, onRaised, onClose };
}

describe("DEF-CUS-9177 · Raise work order is a form", () => {
  it("offers PUBLISHED templates only, the build's services, its units and Whole build", async () => {
    mount(() => new Response("{}", { status: 201 }));
    const job = (await screen.findByLabelText(/Job type/)) as HTMLSelectElement;
    await waitFor(() => expect(job.options.length).toBe(3));
    const names = Array.from(job.options).map((one) => one.textContent);
    expect(names).toContain("Solar inspection");
    expect(names).toContain("Installation Template");
    expect(names).not.toContain("Not published");
    const unit = screen.getByLabelText(/^Unit/) as HTMLSelectElement;
    expect(Array.from(unit.options).map((one) => one.textContent)).toEqual([
      "Whole build",
      "Suite 101",
      "Suite 102",
    ]);
    const service = screen.getByLabelText(/^Service/) as HTMLSelectElement;
    expect(Array.from(service.options).map((one) => one.value)).toEqual(["", "battery", "solar"]);
    expect((screen.getByLabelText(/Target date/) as HTMLInputElement).type).toBe("date");
  });

  it("a Water template on a Battery/Solar build does NOT pre-pick Water (DEF-MET-9179's shape)", async () => {
    mount(() => new Response("{}", { status: 201 }));
    const job = (await screen.findByLabelText(/Job type/)) as HTMLSelectElement;
    await waitFor(() => expect(job.options.length).toBe(3));
    fireEvent.change(job, { target: { value: "t-water" } });
    expect((screen.getByLabelText(/^Service/) as HTMLSelectElement).value).toBe("");
    fireEvent.change(job, { target: { value: "t-solar" } });
    expect((screen.getByLabelText(/^Service/) as HTMLSelectElement).value).toBe("solar");
  });

  it("posts every choice the clerk made and names the order the server made", async () => {
    const { bodies, onRaised } = mount(
      () =>
        new Response(JSON.stringify({ id: "wo-1", order_no: "WO-0031", connection_id: BUILD }), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
    );
    const job = (await screen.findByLabelText(/Job type/)) as HTMLSelectElement;
    await waitFor(() => expect(job.options.length).toBe(3));
    fireEvent.change(job, { target: { value: "t-solar" } });
    fireEvent.change(screen.getByLabelText(/^Unit/), { target: { value: UNIT } });
    fireEvent.change(screen.getByLabelText(/Target date/), { target: { value: "2026-10-20" } });
    fireEvent.click(screen.getByRole("button", { name: "Raise order" }));
    await waitFor(() => expect(onRaised).toHaveBeenCalledWith("WO-0031"));
    expect(bodies[0]).toEqual({
      connection_id: BUILD,
      type: "Solar inspection",
      template_id: "t-solar",
      service: "solar",
      unit_id: UNIT,
      scope: "per_unit",
      // Noon UTC keeps the picked DAY in every tenant zone (see the body builder).
      due_at: "2026-10-20T12:00:00Z",
    });
  });

  it("a refusal stays in the dialog, in the server's own words", async () => {
    const { onRaised } = mount(
      () =>
        new Response(
          JSON.stringify({ code: "AUTH-002", message_key: "errors.auth-002", params: {} }),
          { status: 403, headers: { "Content-Type": "application/json" } },
        ),
    );
    const job = (await screen.findByLabelText(/Job type/)) as HTMLSelectElement;
    await waitFor(() => expect(job.options.length).toBe(3));
    fireEvent.change(job, { target: { value: "t-solar" } });
    fireEvent.click(screen.getByRole("button", { name: "Raise order" }));
    await waitFor(() => expect(screen.getByText(t("errors.auth-002"))).toBeInTheDocument());
    expect(onRaised).not.toHaveBeenCalled();
  });

  it("whole-build work posts no unit and the build's own scope", () => {
    expect(
      raiseOrderBody(BUILD, {
        templateId: "t-water",
        templateName: "Installation Template",
        service: "",
        unitId: "",
        targetDate: "",
      }),
    ).toEqual({
      connection_id: BUILD,
      type: "Installation Template",
      template_id: "t-water",
      service: null,
      unit_id: null,
      scope: "per_premise",
      due_at: null,
    });
  });
});
