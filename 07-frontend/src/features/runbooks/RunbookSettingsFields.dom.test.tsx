// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1 (`DEF-523`).
/* ══════════════════════════════════════════════════════════════════════════
 * A RUNBOOK INPUT SETTINGS OWNS — SHOWN WITH SETTINGS' VALUE AND ITS LINK.
 *
 * `OQ-WRK-12793` → A (PO 2026-10-13, *"1a, 2A 3A"*): *"Days to pay: 20, from
 * Settings"*. `DEF-WRK-10122`: the field was built and never mounted, and the
 * screens drew the runbook's own DEFAULT in a greyed box where Settings' value
 * belonged.
 *
 * Every case mounts the REAL setup page under the REAL path pattern
 * (`/:tenant/runbooks/:key`, `DEF-CWP-3925`) and reads the Settings family
 * through a recording client, so what is asserted is the VALUE THE SERVER
 * SENT and the ADDRESS the link builds — never a string this test typed into
 * the component.
 * ══════════════════════════════════════════════════════════════════════════ */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ApiError } from "@/api/client";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import fixture from "./__fixtures__/rbs004-setup.json";
import { RunbookSetupPage } from "./RunbookSetupPage";

afterEach(cleanup);

const TENANT = "brazosbend";
const KEY = "budget_relevel";

/** The recorded runbook, re-keyed, with three Settings-owned inputs:
 *  two the product's Settings holds and one it does not. Their `value` is
 *  the runbook's declared DEFAULT — deliberately different from Settings' —
 *  so a screen that printed it would fail every case below. */
const DETAIL = {
  ...fixture.detail,
  key: KEY,
  name: "Budget re-level",
  parameters: [
    ...fixture.detail.parameters,
    {
      name: "averaging_window",
      label: "Averaging window",
      type: "ref:setting",
      required: false,
      domain: null,
      multi: false,
      choices: [],
      setting_key: "billing.eligibility_months",
      value: 99,
      is_set: false,
      value_labels: {},
    },
    {
      name: "drift",
      label: "Re-level above drift of",
      type: "ref:setting",
      required: false,
      domain: null,
      multi: false,
      choices: [],
      setting_key: "billing.relevel_drift_pct",
      value: "99",
      is_set: false,
      value_labels: {},
    },
    {
      name: "vacant_means",
      label: "Vacant means",
      type: "ref:setting",
      required: false,
      domain: null,
      multi: false,
      choices: [],
      setting_key: "customers.vacant_definition",
      value: "no_occupant",
      is_set: false,
      value_labels: {},
    },
    // `DEF-WRK-10122` (2026-10-14) — the two NAME mismatches: each runbook key
    // is a field Settings holds under its own name.
    {
      name: "auto_match_tolerance",
      label: "Auto-match tolerance",
      type: "ref:setting",
      required: false,
      domain: null,
      multi: false,
      choices: [],
      setting_key: "payments.match_amount_tolerance",
      value: "9.99",
      is_set: false,
      value_labels: {},
    },
    {
      name: "quiet_hours",
      label: "Quiet hours",
      type: "ref:setting",
      required: false,
      domain: null,
      multi: false,
      choices: [],
      setting_key: "notifications.quiet_hours",
      value: "48",
      is_set: false,
      value_labels: {},
    },
  ],
};

type SettingsAnswer = "ok" | "fail" | "never";

function client(settings: SettingsAnswer, asked: string[]): ApiClient {
  const answer = <T,>(body: unknown): Promise<ApiResponse<T>> =>
    Promise.resolve({ status: 200, data: body as T, headers: new Headers() } as ApiResponse<T>);
  const get = <T,>(path: string) => {
    asked.push(path);
    if (path === `/runbooks/${KEY}`) return answer<T>(DETAIL);
    if (path === "/runbooks/runs") return answer<T>(fixture.runs);
    if (path === "/settings/budget-billing") {
      if (settings === "fail") {
        return Promise.reject(
          new ApiError(503, { code: null, message_key: "api.error.unexpected" }),
        );
      }
      if (settings === "never") return new Promise<ApiResponse<T>>(() => undefined);
      return answer<T>({ eligibility_months: 12, relevel_drift_pct: "20", relevel_cadence_months: 6 });
    }
    if (path === "/settings/finance-controls") {
      if (settings === "never") return new Promise<ApiResponse<T>>(() => undefined);
      return answer<T>({ bank_match_amount_tolerance: "0.2500", bank_match_date_tolerance_days: 3 });
    }
    if (path === "/notification-settings") {
      if (settings === "never") return new Promise<ApiResponse<T>>(() => undefined);
      return answer<T>({ quiet_hours_start: "21:00", quiet_hours_end: "08:00", dispatch_batch_size: 50 });
    }
    throw new Error(`the screen asked for ${path}, which this fixture does not record`);
  };
  const refuse = () => {
    throw new Error("this screen wrote something");
  };
  return { request: get, get, post: refuse, put: refuse, patch: refuse, del: refuse } as unknown as ApiClient;
}

async function openScope(settings: SettingsAnswer) {
  const asked: string[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <TenantRegionalProvider
        value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY", currency: "USD" }}
      >
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/runbooks/${KEY}#scope`]}>
            <Routes>
              <Route
                path="/:tenant/runbooks/:key"
                element={<RunbookSetupPage client={client(settings, asked)} />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeDefined());
  return { asked };
}

function field(setting: string): HTMLElement {
  const node = document.querySelector<HTMLElement>(`[data-settings-owned="${setting}"]`);
  if (node === null) throw new Error(`no Settings-owned field for ${setting}`);
  return node;
}

describe("RBS-004.3 · a Settings-owned input shows Settings' value, read-only, with its link", () => {
  it("the value is the one Settings holds — never the runbook's default", async () => {
    const { asked } = await openScope("ok");
    await waitFor(() =>
      expect(field("billing.eligibility_months").getAttribute("data-settings-state")).toBe("loaded"),
    );
    const months = field("billing.eligibility_months");
    expect(months.textContent).toContain("Averaging window");
    expect(months.textContent).toContain("From Settings");
    expect(months.querySelector("[data-settings-value]")?.textContent).toBe("12 months");
    // Hard rule 2: a percentage DISPLAYS 2.
    expect(field("billing.relevel_drift_pct").querySelector("[data-settings-value]")?.textContent).toBe(
      "20.00%",
    );
    // The runbook's own defaults (99) appear nowhere.
    expect(document.querySelector('[data-region="scope"]')?.textContent ?? "").not.toContain("99");
    // ONE read for the family, however many inputs share it.
    expect(asked.filter((path) => path === "/settings/budget-billing")).toHaveLength(1);
  });

  it("the link goes to the Settings page that edits it, built from the tenant", async () => {
    await openScope("ok");
    await waitFor(() =>
      expect(field("billing.eligibility_months").getAttribute("data-settings-state")).toBe("loaded"),
    );
    const open = field("billing.eligibility_months").querySelector("a[data-settings-open]");
    expect(open?.textContent).toBe("Open settings →");
    expect(open?.getAttribute("href")).toBe(
      `/${TENANT}/settings/reference-data/reference-data?list=budget_billing`,
    );
  });

  it("a key Settings does not hold says so — and its link goes to Settings, not nowhere", async () => {
    await openScope("ok");
    await waitFor(() =>
      expect(field("customers.vacant_definition").getAttribute("data-settings-state")).toBe("notSet"),
    );
    const vacant = field("customers.vacant_definition");
    expect(vacant.textContent).toContain("Not set in Settings");
    expect(vacant.textContent).not.toContain("no_occupant");
    expect(vacant.querySelector("a[data-settings-open]")?.getAttribute("href")).toBe(
      `/${TENANT}/settings`,
    );
  });

  it("DEF-WRK-10122 · a runbook name that Settings holds under its own name shows Settings' value", async () => {
    const { asked } = await openScope("ok");
    await waitFor(() =>
      expect(field("payments.match_amount_tolerance").getAttribute("data-settings-state")).toBe("loaded"),
    );
    const tolerance = field("payments.match_amount_tolerance");
    // Hard rule 2: an amount displays 2, with the tenant's currency.
    expect(tolerance.querySelector("[data-settings-value]")?.textContent).toBe("$0.25");
    expect(tolerance.querySelector("a[data-settings-open]")?.getAttribute("href")).toBe(
      `/${TENANT}/settings/accounting`,
    );
    const quiet = field("notifications.quiet_hours");
    expect(quiet.getAttribute("data-settings-state")).toBe("loaded");
    expect(quiet.querySelector("[data-settings-value]")?.textContent).toBe("21:00–08:00");
    expect(quiet.querySelector("a[data-settings-open]")?.getAttribute("href")).toBe(
      `/${TENANT}/settings/reference-data/notifications`,
    );
    // The runbook defaults (9.99, 48) appear nowhere.
    const scope = document.querySelector('[data-region="scope"]')?.textContent ?? "";
    expect(scope).not.toContain("9.99");
    expect(scope).not.toContain("48");
    expect(asked.filter((path) => path === "/settings/finance-controls")).toHaveLength(1);
    expect(asked.filter((path) => path === "/notification-settings")).toHaveLength(1);
  });

  it("a FAILED read is stated on every field, never a default and never 'Not set'", async () => {
    await openScope("fail");
    await waitFor(() => expect(field("billing.eligibility_months").textContent).toContain("Could not load"));
    for (const setting of [
      "billing.eligibility_months",
      "billing.relevel_drift_pct",
      "customers.vacant_definition",
    ]) {
      const node = field(setting);
      expect(node.getAttribute("data-settings-state")).toBe("notLoaded");
      expect(node.textContent).toContain("Could not load");
      expect(node.textContent).not.toContain("Not set in Settings");
    }
  });

  it("while the read is in flight it says Loading", async () => {
    await openScope("never");
    expect(field("billing.eligibility_months").textContent).toContain("Loading");
  });

  it("the scope dialog draws the same field, with the same value — no greyed box over a default", async () => {
    await openScope("ok");
    await waitFor(() =>
      expect(field("billing.eligibility_months").getAttribute("data-settings-state")).toBe("loaded"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Change scope" }));
    const dialog = await screen.findByRole("dialog");
    const inDialog = dialog.querySelector('[data-settings-owned="billing.eligibility_months"]');
    expect(inDialog?.querySelector("[data-settings-value]")?.textContent).toBe("12 months");
    // The old held text box read "This one lives in Settings" over the default.
    expect(dialog.textContent ?? "").not.toContain("This one lives in Settings");
    expect(screen.queryByDisplayValue("99")).toBeNull();
  });
});

/* ── Lifecycle ─────────────────────────────────────────────
 * packet: OQ-WRK-12793 → A (PO 2026-10-13) · DEF-WRK-10122
 * generated: 2026-10-13 by the runbook-wizard + settings-field lane
 * gates: ./node_modules/.bin/vitest run src/features/runbooks/RunbookSettingsFields.dom.test.tsx — RED before RunbookSettingsFields was mounted (no data-settings-owned on the Scope tab), GREEN after
 * status: VERIFIED-UNRATIFIED
 * ────────────────────────────────────────────────────────── */
