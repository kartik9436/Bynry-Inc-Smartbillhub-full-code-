// ── Trace ──────────────────────────────────────────────
// Story:    US-NOT-013 (the platform delivery dashboard + re-queue — the S8
//           dispatch home)   Screens: S8
// Rules:    BR-NOT-005 · BR-TEN-041 #8 · BR-BIL-036 (an absent address is
//           STATED, never a blank) · BR-SHL-025 (a forbidden control renders
//           disabled WITH its reason) · BR-PAY-018 (a held row releases only on
//           address verification)
// ───────────────────────────────────────────────────────
// The three assertions worth the file, in the order they would break:
//
//   1. **"0 delivered" is never rendered.** `delivered` and `bounced` are
//      provider facts and nothing in this product can write either; a zero
//      beside "sent: 142" reads to a clerk as 142 failed deliveries.
//   2. **A held row's Re-queue is disabled and says why.** Re-queueing it would
//      post the same letter to the address the customer's own mail already came
//      back from (BR-PAY-018) — the server refuses it too, and this is the
//      explanation rather than the guard.
//   3. **An unresolved address never renders as an absent one.** "Nobody looked"
//      and "this account holds no address" are different facts about a customer
//      (BR-BIL-036), and a blank cell would make them identical.
import { describe, expect, it } from "vitest";

import type { OutboundRow, OutboundSummary } from "@/api/endpoints";

import {
  ChannelStatusStrip,
  addressCell,
  lastErrorText,
  requeueBlockedReason,
  statusTiles,
} from "./SettingsNotificationsTab";

function aSummary(overrides: Partial<OutboundSummary> = {}): OutboundSummary {
  return {
    counts: [],
    totals: { queued: 4, sent: 142, failed: 6 },
    held: 1,
    returned: 0,
    retry_exhausted: 6,
    queued_by_channel: { pdf_print: 4 },
    unpopulated_statuses: ["delivered", "bounced"],
    problems: [],
    ...overrides,
  };
}

function aRow(overrides: Partial<OutboundRow> = {}): OutboundRow {
  return {
    id: "01a0-0000",
    source_type: "invoice",
    source_id: "01a0-1111",
    account_id: null,
    account_no: null,
    channel: "pdf_print",
    copy_no: 0,
    status: "failed",
    held: false,
    held_reason: null,
    attempts: 3,
    last_error: "provider timeout",
    batch_id: null,
    provider_reference: null,
    template_code: "bill_residential",
    template_version: 2,
    template_language: "en",
    recipient_address: "1901 Bluestem Ln",
    unavailable_reason: null,
    queued_at: "2026-08-15T10:00:00Z",
    dispatch_not_before: null,
    last_attempt_at: null,
    sent_at: null,
    returned_at: null,
    ...overrides,
  };
}

describe("US-NOT-013 · the dispatch home never states a delivery it cannot know", () => {
  it("renders delivered and bounced as NOT REPORTED, never as 0", () => {
    const tiles = statusTiles(aSummary());
    const delivered = tiles.find((tile) => tile.status === "delivered");
    const bounced = tiles.find((tile) => tile.status === "bounced");

    expect(delivered).toEqual({ status: "delivered", count: null, reported: false });
    expect(bounced).toEqual({ status: "bounced", count: null, reported: false });
    // …and the statuses this product CAN write still carry their figures.
    expect(tiles.find((tile) => tile.status === "failed")).toEqual({
      status: "failed",
      count: 6,
      reported: true,
    });
  });

  it("counts a status the server reports at zero as a real zero", () => {
    const tiles = statusTiles(aSummary({ totals: { queued: 0, failed: 6 } }));
    expect(tiles.find((tile) => tile.status === "queued")).toEqual({
      status: "queued",
      count: 0,
      reported: true,
    });
  });
});

describe("US-NOT-013 TC-4 · a held letter is never sent to the same wrong address", () => {
  it("disables Re-queue on a held row and names the reason", () => {
    expect(requeueBlockedReason(aRow({ held: true }))).toBe("notifications.queue.blocked.held");
  });

  it("disables Re-queue on a row the customer already has", () => {
    expect(requeueBlockedReason(aRow({ status: "sent", held: false }))).toBe(
      "notifications.queue.blocked.alreadySent",
    );
  });

  it("allows Re-queue on a failed row — that is the whole point of the screen", () => {
    expect(requeueBlockedReason(aRow())).toBeNull();
  });
});

describe("BR-BIL-036 · an absent address is stated, and 'nobody looked' is a different fact", () => {
  it("shows the address when there is one", () => {
    expect(addressCell(aRow())).toEqual({ text: "1901 Bluestem Ln", reasonKey: null });
  });

  it("says the address was never looked up when the owning module publishes no read", () => {
    const cell = addressCell(
      aRow({ recipient_address: null, unavailable_reason: "recipient_not_resolvable" }),
    );
    expect(cell).toEqual({
      text: null,
      reasonKey: "notifications.queue.address.notLookedUp",
    });
  });

  it("says none is on file when the account genuinely holds none", () => {
    const cell = addressCell(
      aRow({ recipient_address: null, unavailable_reason: "no_email_address" }),
    );
    expect(cell).toEqual({ text: null, reasonKey: "notifications.queue.address.noneOnFile" });
    // The two must never collapse into one blank cell.
    expect(cell.reasonKey).not.toBe("notifications.queue.address.notLookedUp");
  });

  // DEF-NOT-9668 / DEF-NOT-9669 — a text names WHY it has no number: the
  // customer holds no phone, or never chose texts. Neither is "not looked up".
  it("says a text has no phone on file", () => {
    const cell = addressCell(
      aRow({ channel: "sms", recipient_address: null, unavailable_reason: "no_mobile_number" }),
    );
    expect(cell).toEqual({ text: null, reasonKey: "notifications.queue.address.noPhone" });
  });

  it("says the customer did not choose texts", () => {
    const cell = addressCell(
      aRow({ channel: "sms", recipient_address: null, unavailable_reason: "no_sms_opt_in" }),
    );
    expect(cell).toEqual({ text: null, reasonKey: "notifications.queue.address.textsNotChosen" });
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-NOT-013@6c2a90f (the screen's own packet — see SettingsNotificationsTab.tsx)
// generated: 2026-08-16 by story-coder (DEF-128 notifications API lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest
// exceptions: (1) THE PURE PIECES ARE TESTED, NOT THE RENDER. The three rules
//         worth guarding are decisions (is this a real zero? may this control
//         fire? which absence is this?), and each is a pure exported function
//         so it is asserted directly rather than through a DOM query that would
//         break on a layout change and pass on a rule change.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ── The CONFIG half, added 2026-08-16 (surface-debt tails lane) ────────────
//
// Three more assertions, and the FIRST is the one a clerk gets wrong:
//
//   4. **Firm sends the REGULATED disconnect notice**, not a firmer reminder
//      (BR-NOT-008), and Final sends the 48-hour CERTIFIED letter at real
//      postage. `notices.TONE_TO_STEP` is the one mapping and this card is its
//      first surface anywhere.
//   5. **No channel switch is allowed to read as a send.** R2 has no dispatcher
//      run and no provider on any channel (PO 2026-08-16), and the card says so
//      on its face rather than leaving a toggle looking live.
//   6. **A class with no published body says so per class**, with the reason —
//      never an empty table, which would read as "this utility has no letters".
import { renderToStaticMarkup } from "react-dom/server";

import "@/i18n";
import i18n from "@/i18n";

import type { NotificationSettings } from "@/api/endpoints";

import { DispatchConfigPanel } from "./SettingsNotificationsTab";

const tr = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const RECEIPT_CONSUMER_DETAIL =
  "read at record time by apps/payments/receipts.py: with this ON, recording a payment " +
  "queues the customer's receipt";
const UNWIRED_DETAIL =
  "stored and editable; the credit-issue path does not queue `email_credit_issued` yet, " +
  "so this election is consulted by nothing today.";

function settings(over: Partial<NotificationSettings> = {}): NotificationSettings {
  return {
    dispatch_batch_size: 500,
    quiet_hours_start: "08:00",
    quiet_hours_end: "21:00",
    email_dispatch_active: false,
    sms_dispatch_active: false,
    // CR-009 C-13 (BR-NOT-022) — the four A15 elections, DEFAULT ON.
    receipt_on_record_payment: true,
    credit_notice_email: true,
    bookkeeper_copies: true,
    lockbox_receipts: true,
    election_consumers: {
      receipt_on_record_payment: { wired: true, detail: RECEIPT_CONSUMER_DETAIL },
      credit_notice_email: { wired: false, detail: UNWIRED_DETAIL },
      bookkeeper_copies: { wired: false, detail: UNWIRED_DETAIL },
      lockbox_receipts: { wired: false, detail: UNWIRED_DETAIL },
    },
    print_dispatch_active: true,
    print_cannot_be_switched_off: "BR-BIL-036",
    channel_lines: [
      { channel: "email", state: "off", provider: null, host: null },
      { channel: "sms", state: "off", provider: null, host: null },
      { channel: "pdf_print", state: "waitingPrintVendor", provider: null, host: null },
    ],
    editable_fields: [
      "dispatch_batch_size",
      "quiet_hours_start",
      "quiet_hours_end",
      "email_dispatch_active",
      "sms_dispatch_active",
      "receipt_on_record_payment",
      "credit_notice_email",
      "bookkeeper_copies",
      "lockbox_receipts",
    ],
    ...over,
  };
}

describe("S8 Notifications · the config half", () => {
  it("US-NOT-004 · no channel switch may read as a send", () => {
    // ⚠ AMENDED 2026-10-22 (`DEF-NOT-10533`). This asserted the card-wide
    // *"Nothing is sent in this release"* sentence, which was false once email
    // sent. The subject is unchanged — a switch is read in the SAME GLANCE as
    // what its channel is actually doing — and the line is now per channel.
    const html = renderToStaticMarkup(
      <ChannelStatusStrip
        settings={settings()}
        summary={aSummary()}
        readOnly={false}
        working={false}
        t={tr}
        onSave={() => undefined}
      />,
    );
    expect(html).not.toContain("no-dispatcher");
    expect(html).toContain('data-testid="channel-line-email"');
    // BR-BIL-036 / BR-NOT-024 — print has no switch; its line says what
    // happens to the letter.
    expect(html).toContain(tr("notifications.channels.line.waitingPrintVendor"));
    // The strip's print item exists and has NO switch. Asked with the
    // server's own spelling — `models.CHANNEL_PRINT` is `pdf_print` — because
    // `channel-switch-print` is absent from a screen that renders a print
    // switch too, so the wrong spelling would pass over the defect.
    expect(html).toContain("channel-status-pdf_print");
    expect(html).not.toContain("channel-switch-pdf_print");
  });

  it("CR-048 F2 · the strip answers 'why is nothing sending', with a COUNT", () => {
    // The CR's own sentence: *"Email — not switched on. 138 messages are
    // waiting."* The count is the queue's own, so the strip is checkable
    // rather than reassuring — a state with no figure beside it is the version
    // a clerk cannot act on.
    const html = renderToStaticMarkup(
      <ChannelStatusStrip
        settings={settings()}
        summary={aSummary({ queued_by_channel: { email: 138, sms: 0, pdf_print: 4 } })}
        readOnly={false}
        working={false}
        t={tr}
        onSave={() => undefined}
      />,
    );
    expect(html).toContain(tr("notifications.channels.line.off"));
    expect(html).toContain("138");
    // A real zero is a real zero, and it is said in words rather than as "0
    // waiting", which reads like a count nobody took.
    expect(html).toContain(tr("notifications.channels.waitingNone"));
    // The go-live gate is HERE now — that is the whole point of F2.
    expect(html).toContain("channel-switch-email");
    expect(html).toContain("channel-switch-sms");
  });

  it("CR-048 F2 · the PACING card keeps the two figures and gains no switch", () => {
    // What is left when the go-live gate moves out: how FAST the queue drains
    // and WHEN — a different question from whether anything sends at all.
    const html = renderToStaticMarkup(<DispatchConfigPanel settings={settings()} t={tr} />);
    expect(html).toContain(tr("notifications.pacing.title"));
    // The values a person came to see.
    expect(html).toContain("500");
    expect(html).toContain("08:00");
    // …and none of the four things that moved to the strip.
    expect(html).not.toContain("channel-switch-email");
    expect(html).not.toContain("channel-line-");
    expect(html).not.toContain("<button");
  });

  it("BR-SHL-025 · a non-admin sees the switches disabled WITH the reason", () => {
    const html = renderToStaticMarkup(
      <ChannelStatusStrip
        settings={settings()}
        summary={aSummary()}
        readOnly
        working={false}
        t={tr}
        onSave={() => undefined}
      />,
    );
    expect(html).toContain("disabled");
    expect(html).toContain(tr("notifications.dispatch.adminOnly"));
  });

  // ⚠ THE TWO C-12 SENDER-CARD CASES ARE GONE, 2026-10-22, WITH THE CARD
  // (`DEF-NOT-10534`, PO: *"We have to move everything in connector not any
  // other place"*). The read-only mail-server status that replaced it is
  // asserted in `waveJTabs.dom.test.tsx`.
});

// DEF-BIL-10530 — the two failure reasons this platform writes as a CODE read as
// words; a provider's own sentence is shown exactly as it arrived.
describe("What went wrong (DEF-BIL-10530)", () => {
  const t = (key: string) => `t:${key}`;
  it("names our own two codes in words and leaves a provider's sentence alone", () => {
    expect(lastErrorText("template_not_resolved", t)).toBe(
      "t:notifications.queue.error.template_not_resolved",
    );
    expect(lastErrorText("stuck_wrong_template_pin_2026_10_22", t)).toBe(
      "t:notifications.queue.error.stuck_wrong_template_pin_2026_10_22",
    );
    expect(lastErrorText("provider returned no result", t)).toBe("provider returned no result");
    expect(lastErrorText(null, t)).toBe("");
  });
});
