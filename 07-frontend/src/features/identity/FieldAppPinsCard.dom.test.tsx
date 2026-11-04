// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-187-BRC10 — closes the build of OQ-FLD-12797 (decision log
//          2026-10-24 "FOUR PO ANSWERS ON THE FIELD APP'S OPEN QUESTIONS" (3))
// Rules:   B14 rule 15 (row actions are icons with names) · rule 31's
//          neighbour (the label is the value, the hash is the evidence) ·
//          BR-IDN-019 (an Executive views) · BR-SHL-025 (disabled says why)
// ───────────────────────────────────────────────────────
// ⚠ MOUNTED UNDER `/:tenant/settings/security`, THE PATH `App.tsx` USES, and
// through the WHOLE Security tab rather than the card alone — so the test
// fails if the tab stops mounting the card (hard-won law 2: built is not wired).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { FieldAppPins, SecurityPolicy } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { remapNewPinErrors } from "@/features/identity/FieldAppPinsCard";
import { SecurityTab } from "@/features/identity/SettingsSecurityTab";

afterEach(cleanup);

const TENANT = "brazosbend";
const X1 = "C5+lpZ7tcVwmwQIMcRtPbsQtWLABXhQzejna0wHFr8M=";
const GTS = "hxqRlPTu1bMS/0DITB1SSu0vd4u/8l8TjPgfaAp63Gc=";
const X2 = "diGVwiVYbubAI3RW4hB9xU8e/CH2GnkuvVFZE8zmgzI=";

const POLICY = {
  pw_min_length: 8,
  pw_require_mixed: true,
  pw_require_symbol: false,
  pw_expiry_days: null,
  session_timeout_minutes: 60,
  ip_allowlist: [],
  absolute_session_hours: 12,
  keep_signed_in_offered: true,
  keep_signed_in_days: 30,
  lockout_max_failed: 5,
  lockout_minutes: 15,
  field_capture_hours: 168,
  password_link_valid_days: 7,
  // CR-195-BRC10: the card is shown only while the platform switches pinning
  // on; this file tests the card itself, so the server here says it is on.
  field_app_pinning_enabled: true,
  limits: {
    pw_min_length: { choices: [8, 10, 12], default: 8 },
    pw_expiry_days: { choices: [null, 90, 180], default: null },
    session_timeout_minutes: { choices: [15, 30, 45, 60], default: 60 },
    absolute_session_hours: { choices: [4, 8, 12], default: 12 },
    keep_signed_in_offered: { boolean: true, default: true },
    keep_signed_in_days: { choices: [1, 7, 30], default: 30 },
    lockout_max_failed: { choices: [3, 5, 10], default: 5 },
    lockout_minutes: { choices: [5, 15, 60], default: 15 },
    field_capture_hours: { choices: [1, 12, 24, 36, 48, 72, 168, 336, 720], default: 168 },
    password_link_valid_days: { choices: [1, 2, 3, 7, 14], default: 7 },
  },
} as SecurityPolicy;

function pins(overrides: Partial<FieldAppPins> = {}): FieldAppPins {
  return {
    pins: [
      { spki_sha256: X1, label: "ISRG Root X1", not_after: "2026-12-01", active: true, status: "expiring", days_left: 38 },
      { spki_sha256: GTS, label: "GTS Root R1", not_after: "2036-06-22", active: true, status: "valid", days_left: 3528 },
    ],
    source: "utility",
    warning_days: 60,
    min_valid: 2,
    ...overrides,
  };
}

interface Call {
  method: string;
  url: string;
  body: unknown;
}

function server(first: FieldAppPins, answerPut: (body: { pins: unknown[] }) => Response) {
  const calls: Call[] = [];
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: (async (input: unknown, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ method, url, body });
      const json = (value: unknown, status = 200) =>
        new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
      if (url.includes("/security-policy/field-app-pins")) {
        return method === "PUT" ? answerPut(body) : json(first);
      }
      if (url.includes("/security-policy/audit")) {
        return json({ rows: [] });
      }
      return json(POLICY);
    }) as typeof fetch,
  });
  return { client, calls };
}

function mount(client: ReturnType<typeof createApiClient>, readOnly = false): void {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/settings/security`]}>
          <Routes>
            <Route
              path="/:tenant/settings/security"
              element={<SecurityTab readOnly={readOnly} client={client} timeZone="UTC" dateFormat="DD-MMM-YY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function card(): Promise<HTMLElement> {
  const heading = await screen.findByRole("heading", { level: 3, name: "Field app certificates" });
  const section = heading.closest("section") as HTMLElement;
  await within(section).findByText("ISRG Root X1");
  return section;
}

const ok = (value: unknown) =>
  new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });

describe("OQ-FLD-12797 — Field app certificates on Settings → Security", () => {
  it("lists each key by its LABEL, with the hash smaller and the expiry and status beside it", async () => {
    const { client, calls } = server(pins(), () => ok(pins()));
    mount(client);
    const section = await card();
    // The address the card reads is the tenant's own — not `//settings/...`.
    expect(calls.some((c) => c.url.includes(`/api/${TENANT}/settings/security-policy/field-app-pins`))).toBe(true);
    const rows = within(section).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    const first = within(rows[0]);
    expect(first.getByText("ISRG Root X1")).toHaveClass("font-semibold");
    // The hash is present (copyable) but is not the main value.
    const hash = rows[0].querySelector("[data-pin-hash]") as HTMLElement;
    expect(hash.textContent).toBe(X1);
    expect(hash).toHaveClass("text-xs");
    expect(first.getByText("01-Dec-26")).toBeInTheDocument();
    expect(first.getByText("Expires soon")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Valid")).toBeInTheDocument();
  });

  it("warns when a key expires within the server's 60 days, and not otherwise", async () => {
    const { client } = server(pins(), () => ok(pins()));
    mount(client);
    const section = await card();
    expect(within(section).getByText(/A key expires within 60 days/)).toBeInTheDocument();
    cleanup();

    const calm = pins({
      pins: pins().pins.map((p) => ({ ...p, status: "valid" as const, days_left: 900 })),
    });
    const second = server(calm, () => ok(calm));
    mount(second.client);
    const quiet = await card();
    expect(within(quiet).queryByText(/A key expires within/)).toBeNull();
  });

  it("says when the platform's default keys are in force", async () => {
    const { client } = server(pins({ source: "default" }), () => ok(pins()));
    mount(client);
    const section = await card();
    expect(within(section).getByText("Platform default keys.")).toBeInTheDocument();
  });

  it("deactivates a key by sending the WHOLE list with that key switched off", async () => {
    let sent: { pins: { spki_sha256: string; active: boolean }[] } | null = null;
    const { client } = server(pins(), (body) => {
      sent = body as typeof sent;
      return ok(pins());
    });
    mount(client);
    const section = await card();
    const firstRow = within(section).getAllByRole("row")[1];
    fireEvent.click(within(firstRow).getByRole("button", { name: "Deactivate" }));
    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent!.pins.map((p) => [p.spki_sha256, p.active])).toEqual([
      [X1, false],
      [GTS, true],
    ]);
  });

  it("shows the server's reason where the click was made when it refuses", async () => {
    const { client } = server(pins(), () =>
      new Response(
        JSON.stringify({
          code: "VAL-003",
          message_key: "errors.identity.pins_invalid",
          params: {},
          field_errors: [{ field: "pins", code: "VAL-003", message_key: "errors.identity.pins_too_few", params: { min: 2 } }],
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );
    mount(client);
    const section = await card();
    fireEvent.click(within(within(section).getAllByRole("row")[1]).getByRole("button", { name: "Deactivate" }));
    expect(await within(section).findByText("Keep at least 2 valid keys.")).toBeInTheDocument();
  });

  it("adds a key through the form, appended to the list the server holds", async () => {
    let sent: { pins: { spki_sha256: string; label: string; not_after: string; active: boolean }[] } | null = null;
    const { client } = server(pins(), (body) => {
      sent = body as typeof sent;
      return ok(pins());
    });
    mount(client);
    const section = await card();
    fireEvent.click(within(section).getByRole("button", { name: "Add key" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/^Name/), { target: { value: "ISRG Root X2" } });
    fireEvent.change(within(dialog).getByLabelText(/^Key fingerprint/), { target: { value: X2 } });
    fireEvent.change(within(dialog).getByLabelText(/^Expires on/), { target: { value: "2040-09-17" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add key" }));
    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent!.pins).toHaveLength(3);
    expect(sent!.pins[2]).toEqual({ spki_sha256: X2, label: "ISRG Root X2", not_after: "2040-09-17", active: true });
  });

  it("is view-only for an Executive: every act disabled with its reason", async () => {
    const { client } = server(pins(), () => ok(pins()));
    mount(client, true);
    const section = await card();
    expect(within(section).getByRole("button", { name: "Add key" })).toBeDisabled();
    for (const button of within(section).getAllByRole("button", { name: "Deactivate" })) {
      expect(button).toBeDisabled();
      expect(button.getAttribute("title")).not.toBe("");
    }
  });

  it("an answer with no list is a failed read, not an empty one", async () => {
    const { client } = server({} as FieldAppPins, () => ok(pins()));
    mount(client);
    expect(await screen.findByText("Keys could not load.")).toBeInTheDocument();
  });

  it("moves the new row's server errors under the inputs they are about", () => {
    const remapped = remapNewPinErrors(
      {
        code: "VAL-002",
        message_key: "errors.identity.pins_invalid",
        field_errors: [
          { field: "pins[2].spki_sha256", message_key: "errors.identity.pin_hash_invalid" },
          { field: "pins", message_key: "errors.identity.pins_too_few" },
        ],
      },
      2,
    );
    expect(remapped.field_errors!.map((f) => f.field)).toEqual(["spki_sha256", "pins"]);
  });
});
