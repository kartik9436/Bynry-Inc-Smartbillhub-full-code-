// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  2026-10-22 — the Product Owner moved Notifications under Settings →
//          Configure, next to Templates, and ruled, verbatim:
//            *"We have to move everything in connector not any other place"*
//              (the mail server — `DEF-NOT-10534`)
//            *"A. Move it to Configure → Templates, next to the disconnection
//              letter it prints on."* (the Customer rights wording)
//            *"A. Each channel tells the clerk the truth about itself, in one
//              short line."* (`DEF-NOT-10533`)
//          Recorded in `12-governance/02-decision-log.md` the same day.
// Screens: SET-12 (Configure → Notifications) and its sub-strip
// Rules:   BR-NOT-015 (the rights footer is a PLATFORM DEFAULT, VISIBLY MARKED)
//          · BR-NOT-023 · B14 rule 33 · hard-won law 2 (built is not wired)
// ───────────────────────────────────────────────────────
// ⚠ THIS FILE USED TO ASSERT CR-048 WAVE J's FIVE TABS (2026-08-30): Settings ·
// Messages · Email sender (SMTP) · Customer rights wording · Blocked
// addresses. Two of those tabs are gone by ruling — the sender form to
// Connectors, the rights wording to Templates — so the file now asserts the
// THREE that remain, that neither gone tab survives as a copy here, that the
// mail server is a read of the connector, and that each channel carries its one
// live line. The rights warning's own by-name assertion moved with the card
// (`rightsOnTemplates.dom.test.tsx`).
//
// ⚠ **PROVED RED FIRST (law 7).** Run against the parent commit, the strip
// case fails naming `notifications-tab-sender` and `notifications-tab-rights`,
// and the channel-line case fails on `no-dispatcher` still present.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { NotificationSender, NotificationSettings, OutboundSummary } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  BLOCKED_SUB,
  MESSAGES_SUB,
  NotificationsTab,
  QUEUE_PAGE,
  TAB_SUBS,
  notificationSenderKey,
  notificationSettingsKey,
} from "./SettingsNotificationsTab";

const T = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function aSender(active = true): NotificationSender {
  const connection = {
    connected: true,
    active,
    provider_key: "email_smtp",
    provider_name: "Custom SMTP",
    host: "smtp.office365.com",
    send_from: "billing@springfieldwater.example",
    status: active ? "working" : "not_set_up",
  };
  return {
    sender_route: {
      mode: "tenant_smtp",
      configured: true,
      ...connection,
      detail: "Email goes through Custom SMTP (smtp.office365.com).",
    },
    connection,
    connectors_provider_key: "email_smtp",
    retired_fields: [
      "smtp_host",
      "smtp_port",
      "smtp_username",
      "smtp_secret_ref",
      "sender_from_address",
    ],
    editable_fields: [],
  };
}

function aSettings(): NotificationSettings {
  return {
    dispatch_batch_size: 500,
    quiet_hours_start: "08:00",
    quiet_hours_end: "21:00",
    email_dispatch_active: true,
    sms_dispatch_active: false,
    receipt_on_record_payment: true,
    credit_notice_email: true,
    bookkeeper_copies: true,
    lockbox_receipts: true,
    election_consumers: {},
    print_dispatch_active: true,
    print_cannot_be_switched_off: "BR-BIL-036",
    channel_lines: [
      { channel: "email", state: "sending", provider: "Custom SMTP", host: "smtp.office365.com" },
      { channel: "sms", state: "off", provider: null, host: null },
      { channel: "pdf_print", state: "waitingPrintVendor", provider: null, host: null },
    ],
    editable_fields: [],
  };
}

function aSummary(): OutboundSummary {
  return {
    totals: { queued: 3, sent: 12 },
    unpopulated_statuses: ["delivered", "bounced"],
    held: 0,
    queued_by_channel: {},
  } as unknown as OutboundSummary;
}

function client(): ApiClient {
  return {
    get: async () => ({ data: null, error: null }),
    patch: async () => ({ data: null, error: null }),
    post: async () => ({ data: null, error: null }),
    put: async () => ({ data: null, error: null }),
    delete: async () => ({ data: null, error: null }),
  } as unknown as ApiClient;
}

/** Render one sub-tab, every read PRIMED, mounted under the REAL path pattern
 *  (law 2: a bare router leaves `:tenant` undefined and every link reads `//…`). */
async function tabMarkup(sub: string | undefined, sender = aSender()): Promise<string> {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  await qc.prefetchQuery({
    queryKey: notificationSenderKey,
    queryFn: () => Promise.resolve(sender),
  });
  await qc.prefetchQuery({
    queryKey: notificationSettingsKey,
    queryFn: () => Promise.resolve(aSettings()),
  });
  await qc.prefetchQuery({
    queryKey: queryKeys.outboundSummary,
    queryFn: () => Promise.resolve(aSummary()),
  });
  await qc.prefetchQuery({
    queryKey: queryKeys.outboundQueue(QUEUE_PAGE, 1),
    queryFn: () => Promise.resolve({ results: [], count: 0 }),
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/springfield/settings/reference-data/notifications"]}>
          <Routes>
            <Route
              path="/:tenant/settings/reference-data/notifications"
              element={
                <NotificationsTab
                  readOnly={false}
                  client={client()}
                  sub={sub}
                  onOpenRule={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("2026-10-22 · Configure → Notifications keeps three tabs, and neither moved tab is copied here", () => {
  it("the sub-strip carries THREE tabs — Settings, Messages, Blocked — and no sender or rights tab", async () => {
    const html = await tabMarkup(undefined);
    expect(html).toContain('data-testid="notifications-subtabs"');
    for (const id of ["settings", "messages", "blocked"]) {
      expect(html).toContain(`data-testid="notifications-tab-${id}"`);
    }
    expect(html).not.toContain('data-testid="notifications-tab-sender"');
    expect(html).not.toContain('data-testid="notifications-tab-rights"');
    // Neither the SMTP form nor the rights card is on any tab of this screen.
    for (const sub of [undefined, MESSAGES_SUB]) {
      const tab = await tabMarkup(sub);
      expect(tab).not.toContain('data-testid="sender-smtp_host"');
      expect(tab).not.toContain('data-testid="rights-clauses"');
    }
  });

  it("each tab marks itself selected on its own segment and nowhere else", async () => {
    const pairs: [string | undefined, string][] = [
      [undefined, "settings"],
      [MESSAGES_SUB, "messages"],
      [BLOCKED_SUB, "blocked"],
    ];
    for (const [sub, id] of pairs) {
      const html = await tabMarkup(sub);
      const selected = [
        ...html.matchAll(/<button([^>]*?)data-testid="notifications-tab-([a-z]+)"/g),
      ]
        .filter((m) => m[1].includes('aria-selected="true"'))
        .map((m) => m[2]);
      expect(selected).toEqual([id]);
    }
  });

  it("⚠ no reserved tab segment is a shipped event key, and the list is exactly two", () => {
    const events = Object.keys(i18n.getResourceBundle("en", "translation") as object)
      .filter((key) => key.startsWith("notifications.rules.event."))
      .map((key) => key.slice("notifications.rules.event.".length));
    expect(events.length).toBeGreaterThan(20);
    for (const segment of TAB_SUBS) {
      expect(events).not.toContain(segment);
    }
    expect([...TAB_SUBS].sort()).toEqual([MESSAGES_SUB, BLOCKED_SUB].sort());
  });
});

describe("DEF-NOT-10534 · the mail server is a READ of Connectors", () => {
  it("shows Active: Custom SMTP (host), the sender, the state, and opens Connectors", async () => {
    const html = await tabMarkup(undefined);
    expect(html).toContain(
      T("notifications.mailServer.active", { provider: "Custom SMTP", host: "smtp.office365.com" }),
    );
    expect(html).toContain("billing@springfieldwater.example");
    expect(html).toContain(T("integrations.state.working"));
    expect(html).toContain('href="/springfield/settings/integrations/email_smtp"');
    // A read, never a form: no input on the card.
    expect(html).not.toMatch(/data-testid="sender-[a-z_]+"/);
  });

  it("a connector that cannot send is never called Active", async () => {
    const html = await tabMarkup(undefined, aSender(false));
    expect(html).not.toContain(
      T("notifications.mailServer.activeNoHost", { provider: "Custom SMTP" }),
    );
    expect(html).toContain(
      T("notifications.mailServer.notActive", {
        provider: "Custom SMTP",
        host: "smtp.office365.com",
      }),
    );
    expect(html).toContain(T("integrations.state.not_set_up"));
  });
});

describe("DEF-NOT-10533 · each channel tells the truth about itself, in one line", () => {
  it("the false card-wide sentence is gone, and each channel carries its live line", async () => {
    const html = await tabMarkup(undefined);
    expect(html).not.toContain('data-testid="no-dispatcher"');
    expect(html).toContain(
      T("notifications.channels.line.sendingHost", {
        provider: "Custom SMTP",
        host: "smtp.office365.com",
      }),
    );
    expect(html).toContain("Sending through Custom SMTP (smtp.office365.com)");
    expect(html).toContain(T("notifications.channels.line.off"));
    expect(html).toContain(T("notifications.channels.line.waitingPrintVendor"));
  });
});
