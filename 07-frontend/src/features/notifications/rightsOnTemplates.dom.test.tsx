// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  2026-10-22 — the Customer rights wording moved from Settings →
//          Notifications to Configure → Templates. PO, verbatim: *"A. Move it
//          to Configure → Templates, next to the disconnection letter it prints
//          on."* Editing stays System Admin only (the server's gate).
// Rules:   BR-NOT-015 (the rights footer is a PLATFORM DEFAULT, VISIBLY MARKED)
// ───────────────────────────────────────────────────────
// **THE ASSERTION THIS FILE EXISTS FOR: the red BR-NOT-015 warning travelled
// WITH the clauses** — asserted BY NAME (`rights-platform-notice`), as the old
// wave J suite did on the Notifications tab, so a later lane that drops it has
// to drop this line too. And the card is on a DISCONNECTION letter only.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import type { DisconnectRightsFooter } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { rightsFooterKey } from "./DisconnectRightsFooterCard";
import { TemplateCatalogTab, isDisconnectionLetter } from "./TemplateCatalog";

afterEach(() => {
  cleanup();
});

const PLATFORM_NOTICE = "These five clauses are wording provided as a starting point.";

function aFooter(): DisconnectRightsFooter {
  return {
    clauses: [
      {
        code: "weather_suppression",
        title: "Weather",
        purpose: "States the temperature limits on disconnection.",
        text: "We do not disconnect service on a day when the forecast is below 32°F.",
        enabled: true,
        is_default: true,
        default_text: "We do not disconnect service on a day when the forecast is below 32°F.",
        source_label: "Platform default — review against your own commission",
      },
    ],
    platform_default_notice: PLATFORM_NOTICE,
    tenant_wording_notice: "This clause has been replaced with your own wording.",
    prints_on: [{ code: "disconnect_notice_10_day", name: "Disconnect notice · 10-day warning" }],
    merge_fields: ["{account_no}"],
    merge_fields_reason: "One footer prints on all three disconnection notices.",
    can_edit: true,
    cannot_edit_reason: null,
  };
}

function client(): ApiClient {
  const never = () => new Promise(() => undefined);
  return {
    get: never,
    patch: never,
    post: never,
    put: never,
    delete: never,
  } as unknown as ApiClient;
}

function mount(code: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(rightsFooterKey, aFooter());
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[`/springfield/settings/reference-data/templates?template=${code}`]}
        >
          <Routes>
            <Route
              path="/:tenant/settings/reference-data/templates"
              element={<TemplateCatalogTab readOnly={false} client={client()} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("the Customer rights wording sits under the disconnection letter on Templates", () => {
  it("the 10-day notice carries the clauses AND the platform warning, by name", () => {
    mount("disconnect_notice_10_day");
    expect(screen.getByTestId("templates-rights")).toBeInTheDocument();
    expect(screen.getByTestId("rights-platform-notice")).toHaveTextContent(PLATFORM_NOTICE);
    expect(screen.getByTestId("rights-clauses")).toBeInTheDocument();
  });

  it("a letter that is not a disconnection notice does not carry it", () => {
    mount("bill_ready");
    expect(screen.queryByTestId("templates-rights")).toBeNull();
  });

  it("recognises every disconnection class and nothing else", () => {
    for (const code of [
      "disconnect_notice",
      "disconnect_notice_10_day",
      "disconnect_notice_5_day",
      "disconnect_notice_48_hour",
    ]) {
      expect(isDisconnectionLetter(code)).toBe(true);
    }
    expect(isDisconnectionLetter("disconnect_noticeboard")).toBe(false);
    expect(isDisconnectionLetter("email_disconnect_notice")).toBe(false);
  });
});
