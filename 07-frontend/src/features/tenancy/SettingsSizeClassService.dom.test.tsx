// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-065 task B3 — Settings shows the utility service on a size class
//          AND lets a tenant set it. Screens: S8 / r10 SET-04.sizes
// Ruling:  PO 2026-09-02, verbatim: *"This is where we are setting rates for
//          fire  you should show only capacity for fire . in Setting a capacity
//          needs to tags to utility services ."* — TWO asks, and this file is
//          the second one, which is the fix for the first.
// Rules:   BR-TEN-078 (SUPERSEDED for this one list by that ruling) ·
//          BR-TEN-026 (only a service THIS tenant has enabled) · BR-TEN-071
//          (blank stays a real answer) · B14 rule 31 (no database id on screen)
// Note:    Written BEFORE the fix and shown RED — hard-won law 7.
// ───────────────────────────────────────────────────────
// ⚠ **WHY A DOM TEST AND NOT A MARKUP ASSERTION — hard-won law 2.** The
// Utility-service COLUMN has existed on this screen since CR-004 and nothing
// could ever set it: correct, rendered, and not the feature. A picker whose
// `onChange` reaches no payload is the same shape. So this drives the screen
// with a mouse and reads **the JSON body the server received**, through the real
// `ApiClient`, so the body under assertion is the one that goes over the wire.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ReferenceDataTab } from "./SettingsReferenceData";

const TEST_TENANT = "brazosbend";

interface Sent {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

/** Two rows as the list now serves them: a platform size that names its service
 *  and one a tenant added that nobody has tagged. `null` is the VALUE "nobody
 *  has said" and it lists on every service (BR-TEN-071). */
const ROWS = [
  {
    id: "01a0-fire-2",
    code: "FL-2",
    name: 'Fire line 2"',
    active: true,
    is_system: true,
    used_by: 0,
    service: { id: "svc-fire", code: "fire" },
  },
  {
    id: "01a0-own-14",
    code: "FL-14",
    name: 'Fire line 14"',
    active: true,
    is_system: false,
    used_by: 0,
    service: null,
  },
];

/** The tenant's services. `trash` is OFF, so it must not be offered: the server
 *  refuses a service this tenant has not enabled (BR-TEN-026), and offering it
 *  would draw a choice the write refuses. */
const SERVICES = [
  { service: "fire", name: "Fire", enabled: true },
  { service: "water", name: "Water", enabled: true },
  { service: "trash", name: "Trash", enabled: false },
];

function recordingClient(sent: Sent[]) {
  return createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (method !== "GET") {
        sent.push({
          method,
          url,
          body:
            init?.body === undefined || init?.body === null
              ? null
              : (JSON.parse(String(init.body)) as Record<string, unknown>),
        });
        return new Response(JSON.stringify({ ...ROWS[1], service: { id: "s", code: "fire" } }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("/settings/services")) {
        return new Response(JSON.stringify(SERVICES), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("/fixture-gap")) {
        return new Response(JSON.stringify({ missing: [] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(
        JSON.stringify({ count: ROWS.length, next: null, previous: null, results: ROWS }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    },
  });
}

function renderList(sent: Sent[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/settings/reference?list=service_size_classes"]}>
        <ToastProvider>
          <ReferenceDataTab readOnly={false} client={recordingClient(sent)} />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("CR-065 B3 — a tenant can see and set a size class's utility service", () => {
  it("the list draws the service, by name, and never a database id (B14 rule 31)", async () => {
    renderList([]);
    expect(await screen.findByText("Utility service")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Fire")).toBeInTheDocument());
    // The untagged row says so in words rather than showing a blank cell.
    expect(screen.getByText("All services")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("svc-fire");
    expect(document.body.textContent).not.toContain("01a0-fire-2");
  });

  it("the form SENDS the service the person picked — the half that did not exist", async () => {
    const sent: Sent[] = [];
    renderList(sent);
    await userEvent.click(await screen.findByRole("button", { name: /Add entry/i }));
    // Scoped to the DIALOG: the list behind it draws a column with the same
    // words, and the two are different things.
    const form = await screen.findByRole("dialog");
    const picker = within(form).getByLabelText("Utility service");
    // BR-TEN-026 — only what this tenant sells. Trash is off and is not offered.
    expect(Array.from(picker.querySelectorAll("option")).map((o) => o.textContent)).toEqual([
      "None — offered on every service",
      "Fire",
      "Water",
    ]);

    await userEvent.type(within(form).getByLabelText(/^Code/), "FL-16");
    await userEvent.type(within(form).getByLabelText(/^Name/), 'Fire line 16"');
    await userEvent.selectOptions(picker, "fire");
    await userEvent.click(within(form).getByRole("button", { name: "Add entry" }));

    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent[0].method).toBe("POST");
    expect(sent[0].body).toMatchObject({ code: "FL-16", name: 'Fire line 16"', service: "fire" });
  });

  it("leaving it blank SENDS an empty service, because clearing the tag is a real act", async () => {
    const sent: Sent[] = [];
    renderList(sent);
    await userEvent.click(await screen.findByRole("button", { name: /Add entry/i }));
    const form = await screen.findByRole("dialog");
    await userEvent.type(within(form).getByLabelText(/^Code/), "FL-18");
    await userEvent.type(within(form).getByLabelText(/^Name/), 'Fire line 18"');
    await userEvent.click(within(form).getByRole("button", { name: "Add entry" }));

    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent[0].body).toMatchObject({ service: "" });
  });
});
