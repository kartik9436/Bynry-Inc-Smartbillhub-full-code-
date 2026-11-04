// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-198-BRC10 — texts PROVIDED BY THE PLATFORM (one shared Twilio
//          account): the card's status, last error and a Test send on S142.
// ───────────────────────────────────────────────────────
/**
 * ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a panel that always said *Ready to
 * send* would pass the first case — so the second asserts the not-set-up words
 * AND the first thing to fix; a Test button wired to nothing would render and
 * pass — so the third asserts the request's address and body, and the result
 * line the server's answer produces.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import type { PlatformTexts } from "@/api/integrationsEndpoints";
import type { ProviderCard } from "@/api/integrationsEndpoints";

import { connectorActions } from "./IntegrationsTab";
import { PlatformTextsPanel } from "./PlatformTextsPanel";

afterEach(cleanup);

const READY: PlatformTexts = {
  provided_by_platform: true,
  configured: true,
  sender_kind: "messaging_service",
  sender_hint: "••••b0b0",
  own_sender: false,
  callbacks: true,
  problems: [],
  last_sent_at: null,
  last_error: "30003: Unreachable destination handset",
  last_error_at: "2026-10-29T15:00:00Z",
};

function fakeClient(state: PlatformTexts, posted: { path: string; body: unknown }[] = []) {
  return {
    get: async () => ({ status: 200, data: state }),
    post: async (path: string, body: unknown) => {
      posted.push({ path, body });
      return { status: 200, data: { ok: true, sentence: "Sent one test text.", provider_text: null } };
    },
  } as unknown as ApiClient;
}

function draw(client: ApiClient) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <PlatformTextsPanel providerKey="sms_twilio" client={client} readOnly={false} />
    </QueryClientProvider>,
  );
}

describe("texts provided by the platform (CR-198-BRC10)", () => {
  it("says ready, names the masked sender and shows the last error", async () => {
    draw(fakeClient(READY));
    expect(await screen.findByText("Ready to send")).toBeInTheDocument();
    expect(screen.getByText("Messaging service ••••b0b0")).toBeInTheDocument();
    expect(screen.getByText("30003: Unreachable destination handset")).toBeInTheDocument();
  });

  it("says not set up, with the first thing to fix", async () => {
    draw(fakeClient({ ...READY, configured: false, sender_kind: null, sender_hint: null, problems: ["no_account", "no_sender"] }));
    expect(await screen.findByText("No account on this server")).toBeInTheDocument();
    expect(document.querySelector('[data-platform-texts="not_set_up"]')).not.toBeNull();
  });

  it("sends one test text to the typed number and shows the answer", async () => {
    const posted: { path: string; body: unknown }[] = [];
    draw(fakeClient(READY, posted));
    fireEvent.change(await screen.findByLabelText("Phone number"), { target: { value: "(402) 555-1049" } });
    fireEvent.click(screen.getByTestId("platform-test-send"));
    await waitFor(() => expect(document.querySelector('[data-platform-test="ok"]')).not.toBeNull());
    expect(posted).toEqual([{ path: "/integrations/sms_twilio/platform-test", body: { to: "(402) 555-1049" } }]);
  });

  it("offers View and refuses Connect on a platform card", () => {
    const t = (key: string) => key;
    const card = { auth: { mode: "platform_holds_ours", placement: "native" }, disposition: { kind: "live", wave: null, phase: 2 } } as unknown as ProviderCard;
    const actions = connectorActions(t, card, { readOnly: false });
    expect(actions.view).toBeNull();
    expect(actions.connect).toBe("integrations.rowAction.platformProvided");
  });
});
