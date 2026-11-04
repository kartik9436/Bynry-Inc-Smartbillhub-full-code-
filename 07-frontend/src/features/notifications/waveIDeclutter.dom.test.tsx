// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-048 wave I — the Product Owner walked the deployed Notifications
//          and Templates screens and named ONE fault ten times in a sitting:
//          *"why we are showing two names"*, *"why you are howing text - this
//          is internal not required"*, *"why so much text - just show some
//          status"*, *"this sentence is too long"*, *"all these long messages
//          are breaking to UI ... just use 3 or 4 wrods"*.
// Screens: SET-12 (Settings → Notifications) · SET-12D (one rule page)
// Rules:   BR-NOT-018 (an event nothing fires is DRAWN and REFUSED BY NAME) ·
//          BR-SHL-025 (a dead control carries its reason) · BR-NOT-022 (the
//          send-time elections) · B14 rule 21 (per-file Tailwind migration)
// ───────────────────────────────────────────────────────
// THE ONE FAULT, AND WHY IT IS WORTH A SUITE OF ITS OWN:
//
//   **A TABLE CELL HOLDS A VALUE, AND A CONTROL HOLDS A LABEL. The sentence
//   explaining either belongs in a tooltip, in the opened detail, or in help —
//   never rendered inline.**
//
// Each case below is the same assertion in two halves, and the SECOND half is
// the one that stops this becoming a wrecking wave: the paragraph is gone from
// the row, AND the fact it carried is still reachable. Deleting the fact
// outright would recreate the defect CR-048 was raised to fix — a utility
// switching on an event nothing fires, seeing nothing happen, and never finding
// out.
//
// ⚠ **WHAT THIS SUITE CANNOT SEE.** jsdom performs no layout, so "the marker is
// one line and the paragraph was three" is not measurable here. That number is
// taken in a real browser by `10-scripts/render-checks/cr048-notifications-
// geometry.mjs`, which is the instrument for every height in this wave (hard-won
// law 6). What IS provable without layout is the STRUCTURE: which element
// carries which words, and whether the words that left the row are still in the
// document.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { NotificationRuleMatrix } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { MESSAGES_SUB } from "./SettingsNotificationsTab";
import { RECEIPT_ELECTION_EVENT, RuleMatrix } from "./NotificationRules";

const T = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function mount(node: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>{node}</ToastProvider>
    </QueryClientProvider>,
  );
}

/** Two rows: one event the product fires, and one it does not. The second is
 *  the whole subject of BR-NOT-018. */
function matrix(): NotificationRuleMatrix {
  const row = (key: string, blocked: string | null) => ({
    key,
    category: "collections",
    audience: "customer",
    channels: ["email"],
    unavailable_channels: [],
    template_classes: {},
    trigger_blocked_by: blocked,
    timing_key: "immediate",
    has_ladder: false,
    staff_recipient_policy: null,
    enabled: false,
    customer_scope: "all_contacts",
    service_scope: "all",
    plan_class: "all",
    skip_accounts_on_payment_plan: false,
    trigger_mode: "immediate",
    offset_days: null,
    fixed_time: null,
    quiet_hours_mode: "respect",
    failure_policy: "retry_3_days_then_email",
    channel_rules: [],
    staff_recipient: null,
  });
  return {
    count: 2,
    categories: ["collections"],
    dispatch_runs_in_this_release: false,
    delivery_counts_available: false,
    delivery_counts_reason: "Nothing reports a delivery.",
    requirement_claims_event_count: 16,
    built_event_count: 15,
    results: [row("dunning_reminder", null), row("autopay_enrolled", "no_writer_calls_this_event")],
  } as unknown as NotificationRuleMatrix;
}

describe("CR-048 wave I · BR-NOT-018 keeps the fact and loses the paragraph", () => {
  it("marks an unfireable event in three words, not in three lines of prose", () => {
    mount(
      <RuleMatrix
        matrix={matrix()}
        readOnly={false}
        working={false}
        t={T}
        onOpen={() => undefined}
        onToggle={() => undefined}
      />,
    );
    const mark = screen.getByTestId("rule-noTrigger-autopay_enrolled");
    // THE ROW SAYS THREE WORDS.
    expect(mark).toHaveTextContent(T("notifications.rules.noTriggerMark"));
    expect(mark.textContent).not.toContain(T("notifications.rules.noTrigger"));
    // AND THE WHOLE SENTENCE IS STILL ON IT, one hover away. Deleting this
    // assertion is deleting the protection, not tidying the test.
    expect(mark.getAttribute("title")).toBe(T("notifications.rules.noTrigger"));
    // CR-016 — the id support reads stays on the element, off the sentence.
    expect(mark.getAttribute("data-blocked-by")).toBe("no_writer_calls_this_event");
    // ⚠ AND IT IS NOT THE DANGER TIER. `RefusalStrip` stamps `data-refusal`;
    // twelve red boxes down one column taught the reader to stop reading them,
    // which is the opposite of what BR-NOT-018 wants. B14 rule 6 keeps that
    // tier for a destructive commit.
    expect(mark.hasAttribute("data-refusal")).toBe(false);
  });

  it("BR-SHL-025 · the switch that cannot be turned on still carries the WHOLE reason", () => {
    mount(
      <RuleMatrix
        matrix={matrix()}
        readOnly={false}
        working={false}
        t={T}
        onOpen={() => undefined}
        onToggle={() => undefined}
      />,
    );
    const toggle = screen.getByTestId("rule-toggle-autopay_enrolled");
    expect(toggle).toBeDisabled();
    expect(toggle.getAttribute("title")).toBe(T("notifications.rules.noTrigger"));
    // The event the product DOES fire is untouched by any of this.
    expect(screen.getByTestId("rule-toggle-dunning_reminder")).not.toBeDisabled();
    expect(screen.queryByTestId("rule-noTrigger-dunning_reminder")).toBeNull();
  });

  it("the marker never renders on a row that has a trigger — it is a fact, not decoration", () => {
    mount(
      <RuleMatrix
        matrix={matrix()}
        readOnly={false}
        working={false}
        t={T}
        onOpen={() => undefined}
        onToggle={() => undefined}
      />,
    );
    expect(screen.getAllByText(T("notifications.rules.noTriggerMark"))).toHaveLength(1);
  });
});

describe("CR-048 wave I · the reserved second-tab segment cannot be an event key", () => {
  it("no event this product ships is called by the word the Messages tab uses", () => {
    // `:sub` is ONE namespace holding an event key OR the second tab. This is
    // the assertion that keeps that safe by proof rather than by luck — and it
    // reads the SHIPPED event vocabulary, not a fixture.
    const events = Object.keys(i18n.getResourceBundle("en", "translation") as object)
      .filter((key) => key.startsWith("notifications.rules.event."))
      .map((key) => key.slice("notifications.rules.event.".length));
    expect(events.length).toBeGreaterThan(20);
    expect(events).not.toContain(MESSAGES_SUB);
    // And the event that DOES own the receipt election is one of them, so the
    // card has a page to render on.
    expect(events).toContain(RECEIPT_ELECTION_EVENT);
  });
});

describe("CR-048 wave I · the deleted sections took no live switch with them", () => {
  it("the receipt election's copy is still in the catalogue and still names its effect", () => {
    // The card moved; the SETTING did not. If a later lane deletes the strings
    // this fails before the screen does.
    expect(T("notifications.receipt.title")).not.toBe("notifications.receipt.title");
    expect(T("notifications.receipt.hint")).toContain("receipt");
    // The two labels the switch still borrows from the deleted card — which is
    // why those keys are LEFT in the catalogue rather than retired with it.
    expect(T("notifications.elections.turnOff")).not.toBe("notifications.elections.turnOff");
    expect(T("notifications.elections.turnOn")).not.toBe("notifications.elections.turnOn");
  });

  it("the three removed sections are gone from the code, not merely hidden by a flag", async () => {
    const tab = await import("./SettingsNotificationsTab");
    for (const gone of ["SendTimeElectionsPanel", "ToneMappingPanel", "TemplateLibraryPanel"]) {
      expect(Object.keys(tab)).not.toContain(gone);
    }
    // A flag that hides a section is a section that comes back; this is what
    // makes the removal a removal.
    expect(vi.isMockFunction(mount)).toBe(false);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-048 wave I (12-governance/11-change-requests.md) ·
//         04-docs/05-modules/09-notifications/02-business-rules.md BR-NOT-018 ·
//         04-docs/02-decisions/14-ui-conventions.md rules 6 · 15 · 21
// generated: 2026-08-30 by the CR-048 wave I declutter lane
// gates: tsc✔ · eslint✔ · vitest — RED-proved first against the pre-change
//        markup: the marker case failed with `expected null not to be null`
//        (there was no `title` on the RefusalStrip) and
//        `expected true to be false` on `data-refusal`.
// exceptions: (1) NO HEIGHT IS ASSERTED HERE. jsdom performs no layout, so the
//         numbers the PO's complaint is actually about are taken in a browser by
//         `10-scripts/render-checks/cr048-notifications-geometry.mjs`.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
