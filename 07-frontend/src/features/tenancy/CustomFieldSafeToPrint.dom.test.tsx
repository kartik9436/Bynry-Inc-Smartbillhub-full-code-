// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-TEN-9234 — Settings had no "Safe to print" switch, so a utility
//          could never let one of its own fields print on a bill from the
//          screen; the flag (`is_document_safe`) was reachable only by API.
//          Found by the custom-fields end-to-end walk (`cf_e2e_walk.mjs`
//          phase 17).
// Rules:   CR-161-BRC10 Rules table — *"Prints on a bill only when switched
//          on · 'Safe to print' is off by default"* · OQ-076 (fail-closed;
//          the server refuses the flag at create)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import type { CustomFieldDefinition } from "@/api/endpoints";

import { DefinitionModal } from "./SettingsCustomFields";

afterEach(() => cleanup());

const FIELD = {
  id: "cf-1",
  entity: "accounts",
  key: "contract_ref",
  label: "Contract ref",
  help_text: "",
  data_type: "text",
  options: [],
  is_required: false,
  is_active: true,
  is_document_safe: false,
  placement: { S18: "input" },
  display_order: 0,
} as unknown as CustomFieldDefinition;

function mount(existing: CustomFieldDefinition | null, sent: { path: string; body: unknown }[]) {
  const answer = <T,>(data: unknown) => ({ data: data as T, status: 200, headers: new Headers() });
  const client = {
    request: <T,>(path: string, options?: { body?: unknown }) => {
      sent.push({ path, body: options?.body });
      return Promise.resolve(answer<T>({ ...FIELD, ...(options?.body as object) }));
    },
    post: <T,>(path: string, body?: unknown) => {
      sent.push({ path, body });
      return Promise.resolve(answer<T>(FIELD));
    },
    get: <T,>() => Promise.resolve(answer<T>({})),
  } as unknown as ApiClient;
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <DefinitionModal
        client={client}
        existing={existing}
        catalogue={[]}
        rows={[]}
        onClose={() => undefined}
        onSaved={() => undefined}
      />
    </QueryClientProvider>,
  );
}

describe("DEF-TEN-9234 · Safe to print on Settings → Edit custom field", () => {
  it("Edit draws the switch, OFF by default, and saving sends is_document_safe", async () => {
    const sent: { path: string; body: unknown }[] = [];
    const user = userEvent.setup();
    mount(FIELD, sent);
    const box = screen.getByLabelText("Safe to print");
    expect(box).not.toBeChecked();
    await user.click(box);
    await user.click(screen.getByRole("button", { name: "Save field" }));
    const patch = sent.find((call) => call.path.includes("/settings/custom-fields/cf-1"));
    expect(patch?.body).toMatchObject({ is_document_safe: true });
  });

  it("Add does not offer it (the server refuses the flag at create)", () => {
    mount(null, []);
    expect(screen.queryByLabelText("Safe to print")).not.toBeInTheDocument();
  });
});
