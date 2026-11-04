// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.34 (lane MVI-WIZ-REV) — Edit opens the Add form
//           (image 47) and saves back to the SAME request or move-in.
// Defect:   DEF-CUS-9731 — `?request=&edit=1` was ignored: the form autosaved
//           a NEW `MVI-` draft on open and never wrote to the request.
// Harness:  the REAL wizard at the REAL address the details view's Edit opens
//           (`/:tenant/move-ins/new?request=<id>&edit=1`, §9.DETAIL), over a
//           fake server that records every request it is sent.
// ───────────────────────────────────────────────────────
//
// RED FIRST (law 7), run with `MoveInWizard.tsx` at the tip's bytes (2.540.2)
// — all four failed:
//   no-draft case   → expected '' to be 'unit-b'  (the edit's form never read)
//   Park held       → expect(element).toBeDisabled()
//   Save & exit     → expected '' to be 'unit-b'
//   Not started     → Unable to find an element with the text:
//                     Edit move-in · MVI-26-0011
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a wizard that
// wrote nothing at all would pass the "no draft" case — so the same case
// asserts the request's answer is IN the form, and the save case asserts the
// PUT carries what the clerk typed. A test that waited too little would see
// "no POST" before the autosave fired — so the no-draft case waits for the
// form to fill first, which is after the moment the old autosave wrote.
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { MoveInWizard } from "../MoveInWizard";

const REQUEST_ID = "01a0fa42-2903-7d5d-92bb-901f5c01f899";
const PARK_ID = "0b7c4e10-0000-4000-8000-000000000001";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const UNITS = {
  count: 1,
  next: null,
  previous: null,
  results: [
    { id: "unit-b", unit_no: "SCW-U-308", label: "Unit 3B", premise_id: "p-b", premise_address: "8 Quarry Lane", occupancy: "vacant" },
  ],
};

/** `DEF-CUS-10190` — `GET /move-ins/units`, which replaced the vacant-only
 *  `GET /units` read on step 1: the same unit, in the search's own shape. */
const UNIT_SEARCH = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: "unit-b",
      unit_no: "SCW-U-308",
      label: "Unit 3B",
      premise_no: "P-00008",
      premise_name: null,
      address: { line1: "8 Quarry Lane", city: null, state: null, postal_code: null },
      meters: [],
      state: "vacant",
      occupant: null,
      selectable: true,
      path: "move_in",
      reason_key: null,
    },
  ],
};

let parkOnRequest = true;
/** DEF-CUS-10002 — what the last PUT wrote, served back by the next GET. */
let storedValues: Record<string, unknown> | null = null;
let putFails = false;

function form(editable: boolean) {
  return {
    request: {
      id: REQUEST_ID,
      request_no: "SR-26-0014",
      state: editable ? "submitted" : "approved",
      status: editable ? "to_approve" : "not_started",
      editable,
    },
    park_id: editable || !parkOnRequest ? null : PARK_ID,
    step: 1,
    values: storedValues ?? {
      service_request_id: REQUEST_ID,
      unit_id: "unit-b",
      opened_at: "2026-10-10",
      services: ["water"],
      customer: { full_name: "Kestrel Bakery LLC", email: "nilesh@bynry.io", phone: "(732) 630-0285", customer_kind: "company", account_type: "commercial", account_subtype: "", mailing_same: true, ssn: "", driving_licence: "" },
      preferences: { preferred_language: "" },
    },
  };
}

let calls: string[] = [];
let bodies: Record<string, unknown>[] = [];

function open(editable: boolean, edit = true) {
  calls = [];
  bodies = [];
  const client = createApiClient({
    tenant: "sixrivers",
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
      if (method !== "GET") {
        calls.push(`${method} ${path}`);
        bodies.push(init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {});
      }
      if (url.includes("/move-in-form") && method === "PUT" && putFails) return json({ detail: "down" }, 503);
      if (url.includes("/move-in-form")) return json(form(editable));
      if (/\/moves\/SR-26-0014/.test(url)) return json({ reference: "MVI-26-0011", status: "not_started" });
      if (/\/wizard-parks\//.test(url) && method === "GET") {
        return json({ id: PARK_ID, flow: "move_in", step: 1, reference: "SR-26-0014", values: {}, waiting_on: "" });
      }
      if (/\/wizard-parks/.test(url)) return json({ id: "new-park", flow: "move_in", step: 1, reference: "MVI-26-0099", values: {} }, 201);
      if (/\/service-requests\/[^/?]+(\?|$)/.test(url)) return json({ detail: "not found" }, 404);
      if (/\/move-ins\/units(\?|$)/.test(url)) return json(UNIT_SEARCH);
      if (/\/units(\?|$)/.test(url)) return json(UNITS);
      if (/\/accounts(\?|$)/.test(url)) return json({ count: 0, next: null, previous: null, results: [] });
      return json({ detail: "not found" }, 404);
    },
  } as never);
  function Where() {
    const location = useLocation();
    return <output data-testid="where">{location.pathname}</output>;
  }
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/sixrivers/move-ins/new?request=${REQUEST_ID}${edit ? "&edit=1" : ""}`]}>
          <Routes>
            <Route path="/:tenant/move-ins/new" element={<MoveInWizard client={client} />} />
            <Route path="/:tenant/moves/:ref" element={<Where />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("P2.34 · Edit opens the Add form on the request (DEF-CUS-9731)", () => {
  afterEach(() => {
    cleanup();
    parkOnRequest = true;
    storedValues = null;
    putFails = false;
  });

  it("an undecided request: the form fills from the request and writes NO draft of its own", async () => {
    open(true);
    await waitFor(() =>
      // `DEF-CUS-10190` — the unit search replaced the select: the chosen unit
      // is its own line, by NUMBER (never an id on screen).
      expect(document.querySelector('[data-move-in-unit-search="chosen"]')?.textContent).toContain("SCW-U-308"),
    );
    await waitFor(() => expect(screen.getByText("Edit move-in · SR-26-0014")).toBeInTheDocument());
    // Long enough for the old autosave (it wrote on the first settled render).
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(calls.filter((call) => call.includes("/wizard-parks"))).toEqual([]);
  });

  it("an undecided request: Park is held — its one draft is the request's own", async () => {
    open(true);
    await waitFor(() => expect(screen.getByText("Edit move-in · SR-26-0014")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Park" })).toBeDisabled();
  });

  it("an undecided request: Save draft & exit PUTs the form to the request and returns to it", async () => {
    open(true);
    await waitFor(() => expect(screen.getByText("Edit move-in · SR-26-0014")).toBeInTheDocument());
    await waitFor(() =>
      // `DEF-CUS-10190` — the unit search replaced the select: the chosen unit
      // is its own line, by NUMBER (never an id on screen).
      expect(document.querySelector('[data-move-in-unit-search="chosen"]')?.textContent).toContain("SCW-U-308"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save draft & exit" }));
    await waitFor(() => expect(calls).toContain(`PUT /api/sixrivers/service-requests/${REQUEST_ID}/move-in-form`));
    const body = bodies[calls.indexOf(`PUT /api/sixrivers/service-requests/${REQUEST_ID}/move-in-form`)];
    const values = body.values as Record<string, unknown>;
    expect(values.unit_id).toBe("unit-b");
    expect(values.opened_at).toBe("2026-10-10");
    expect((values.customer as Record<string, unknown>).full_name).toBe("Kestrel Bakery LLC");
    expect(values.service_request_id).toBe(REQUEST_ID);
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/sixrivers/moves/SR-26-0014"));
    expect(calls.filter((call) => call.startsWith("POST") && call.includes("/wizard-parks"))).toEqual([]);
  });

  it("an approved request (Not started): the title names the MVI- move-in and the form resumes the request's park", async () => {
    open(false);
    await waitFor(() => expect(screen.getByText("Edit move-in · MVI-26-0011")).toBeInTheDocument());
    await waitFor(() =>
      // `DEF-CUS-10190` — the unit search replaced the select: the chosen unit
      // is its own line, by NUMBER (never an id on screen).
      expect(document.querySelector('[data-move-in-unit-search="chosen"]')?.textContent).toContain("SCW-U-308"),
    );
    await new Promise((resolve) => setTimeout(resolve, 50));
    // One draft per move-in: the autosave PATCHes the request's park, never
    // POSTs a second one.
    expect(calls.filter((call) => call.startsWith("POST") && call.includes("/wizard-parks"))).toEqual([]);
    expect(calls.some((call) => call.includes("/move-in-form"))).toBe(false);
  });
  it("DEF-CUS-9735 · Not started with no park yet: the ONE draft written names the request and the job's MVI-", async () => {
    parkOnRequest = false;
    open(false);
    await waitFor(() => expect(screen.getByText("Edit move-in · MVI-26-0011")).toBeInTheDocument());
    await waitFor(() => expect(calls.filter((call) => call.startsWith("POST") && call.includes("/wizard-parks"))).toHaveLength(1));
    const body = bodies[calls.findIndex((call) => call.startsWith("POST") && call.includes("/wizard-parks"))];
    const subject = body.subject_ref as Record<string, unknown>;
    expect(subject.service_request_id).toBe(REQUEST_ID);
    expect(subject.move_in_no).toBe("MVI-26-0011");
  });

  // ⚠ **DEF-CUS-10002 — THE REQUEST'S EDIT NOW KEEPS ITSELF, IN ITS OWN STORE.**
  // PO-confirmed cause (2026-10-07): *"The move-in was opened from a service
  // request, where automatic save is off, so the work really was lost."* RED
  // at 2.559.1: no PUT was ever sent until Save draft & exit, so a clerk who
  // left by the side nav and came back found the request's old date.
  // ⚠ What would pass wrongly: a fix that turned the PARK autosave back on —
  // the work would survive in a second MVI- draft (DEF-CUS-9731) and the
  // request would still be stale. So it also asserts no park is written.
  it("DEF-CUS-10002 · an undecided request: a change is written to the REQUEST without Save, and is there on reopening", async () => {
    open(true);
    await waitFor(() => expect(screen.getByText("Edit move-in · SR-26-0014")).toBeInTheDocument());
    const date = await waitFor(() => {
      const input = document.getElementById("opened_at") as HTMLInputElement | null;
      expect(input?.value).toBe("10/10/2026");
      return input as HTMLInputElement;
    });
    // Past the settle window, then the clerk's own change.
    await new Promise((resolve) => setTimeout(resolve, 900));
    expect(calls.filter((call) => call.includes("/move-in-form"))).toEqual([]);
    fireEvent.change(date, { target: { value: "10/20/2026" } });
    fireEvent.blur(date);
    const put = `PUT /api/sixrivers/service-requests/${REQUEST_ID}/move-in-form`;
    await waitFor(() => expect(calls).toContain(put), { timeout: 3000 });
    const values = bodies[calls.lastIndexOf(put)].values as Record<string, unknown>;
    expect(values.opened_at).toBe("2026-10-20");
    expect(calls.filter((call) => call.includes("/wizard-parks"))).toEqual([]);
    // Leave (unmount) and open the Edit again: the server answers what was
    // written, and the form shows it.
    cleanup();
    storedValues = values;
    open(true);
    await waitFor(() =>
      expect((document.getElementById("opened_at") as HTMLInputElement | null)?.value).toBe("10/20/2026"),
    );
  });

  // ⚠ **DEF-CUS-10014 — A CHANGE TYPED THE MOMENT THE FORM LOADS IS STILL
  // SENT.** The baseline was taken by an 800 ms timer after the edit loaded,
  // so a date typed inside that window became the baseline and no PUT went;
  // *Leave without saving* then lost it (leave-guard walk A8, 2.560.3). The
  // case above waits 900 ms before typing and could never see this.
  // ⚠ What would pass wrongly: a fix that wrote on every render — so the case
  // above (no PUT while untouched, 900 ms) still stands beside this one.
  it("DEF-CUS-10014 · a change typed at once, with no pause after load, is written to the request", async () => {
    open(true);
    const date = await waitFor(() => {
      const input = document.getElementById("opened_at") as HTMLInputElement | null;
      expect(input?.value).toBe("10/10/2026");
      return input as HTMLInputElement;
    });
    fireEvent.change(date, { target: { value: "10/22/2026" } });
    fireEvent.blur(date);
    const put = `PUT /api/sixrivers/service-requests/${REQUEST_ID}/move-in-form`;
    await waitFor(() => expect(calls).toContain(put), { timeout: 3000 });
    const values = bodies[calls.lastIndexOf(put)].values as Record<string, unknown>;
    expect(values.opened_at).toBe("2026-10-22");
  });

  it("DEF-CUS-10002 · a failed autosave is SAID, in one short line, not swallowed", async () => {
    putFails = true;
    open(true);
    await waitFor(() => expect(screen.getByText("Edit move-in · SR-26-0014")).toBeInTheDocument());
    const date = await waitFor(() => {
      const input = document.getElementById("opened_at") as HTMLInputElement | null;
      expect(input?.value).toBe("10/10/2026");
      return input as HTMLInputElement;
    });
    await new Promise((resolve) => setTimeout(resolve, 900));
    expect(screen.queryByText("Changes not saved yet.")).toBeNull();
    fireEvent.change(date, { target: { value: "10/21/2026" } });
    fireEvent.blur(date);
    await waitFor(() => expect(screen.getByText("Changes not saved yet.")).toBeInTheDocument(), { timeout: 3000 });
  });

  it("DEF-CUS-9735 · Start (no edit=1) on an approved request resumes the request's park — no second draft", async () => {
    open(false, false);
    await waitFor(() =>
      // `DEF-CUS-10190` — the unit search replaced the select: the chosen unit
      // is its own line, by NUMBER (never an id on screen).
      expect(document.querySelector('[data-move-in-unit-search="chosen"]')?.textContent).toContain("SCW-U-308"),
    );
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(calls.filter((call) => call.startsWith("POST") && call.includes("/wizard-parks"))).toEqual([]);
    // Start is not an edit: the title stays the New move-in's.
    expect(screen.queryByText(/Edit move-in/)).toBeNull();
  });
});

