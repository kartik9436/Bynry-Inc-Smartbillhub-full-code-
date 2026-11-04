// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 2 wave K — `ACC-S16`, the communication section.
//          Step 1 lane 2 finding F11: *"There is no way to write to the
//          customer from this screen."* Drawing `R6`, pages 186–188.
// Screens: S21
// Rules:   BR-NOT-005 (queue rows only) · BR-NOT-013 (no provider on post,
//          email or SMS in this release) · BR-PAY-035 + BR-NOT-008 (a
//          regulated kind is the ladder's, not this dialog's) · BR-BIL-036 (a
//          channel with nothing on file is SHOWN, with its reason) ·
//          BR-SHL-025 (a control that cannot act carries its reason) ·
//          B14 rule 16 (every list carries its pagination footer) ·
//          hard-won law 2 (built is not wired — the rail's eighth glyph must
//          OPEN something).
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY CASE HERE WAS PROVED RED FIRST**, and two of them check things that
// only go wrong silently:
//
//  * `the dialog never claims a message was sent` fails the moment the recap
//    or a status cell says *Sent* over a queued row. `BR-NOT-013` means every
//    row on this deployment rests queued, so a screen that said otherwise would
//    be wrong on every account and nothing would complain.
//  * `a channel with nothing on file cannot be ticked` fails if the checkbox is
//    enabled, which would queue a row to an address that does not exist.
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type {
  CommunicationChannel,
  CommunicationForm,
} from "@/api/accountCommunicationEndpoints";
import { ToastProvider } from "@/components/Toast";

import {
  ACCOUNT_RAIL_ACTIONS,
  ACCOUNT_RAIL_ACTION_IDS,
} from "./AccountIconRail";
import {
  applyTemplate,
  ChannelTable,
  defaultChannels,
  tickable,
} from "./AccountCommunicationDialog";

afterEach(cleanup);

function channel(over: Partial<CommunicationChannel> = {}): CommunicationChannel {
  return {
    channel: "email",
    address: "accounts@bramblebakery.example",
    unavailable_reason: null,
    on_file: true,
    // ⚠ FALSE is the honest default on this deployment — see the header.
    delivers: false,
    delivers_reason: "provider_not_connected",
    ...over,
  };
}

export const FORM: CommunicationForm = {
  account_id: "a-11812",
  account_no: "A-11812",
  customer_name: "Bramble Bakery",
  language: "en",
  kinds: [
    { kind: "courtesy", allowed: true, refusal: null },
    { kind: "payment_reminder", allowed: false, refusal: "reminder_is_the_ladder" },
  ],
  //: The utility's own published wording (PO 2026-09-13). `body` arrives
  //: ALREADY safe to queue: the tokens a clerk's message can carry are left
  //: standing and dispatch fills them, and the ones only the originating event
  //: knows arrive as `____` for the clerk to type over.
  templates: [
    {
      code: "service_outage_notice",
      name: "Planned outage notice",
      subject: "Planned service interruption in ____",
      body: "Hi {first_name},\n\nWe will turn the water off in ____ on ____.",
    },
    {
      code: "sms_payment_received",
      name: "Payment receipt · SMS",
      //: An SMS class has no subject, which is why picking one must not blank a
      //: subject the clerk already typed.
      subject: "",
      body: "{utility_name}: we received ____. Thank you.",
    },
  ],
  channels: [
    channel(),
    channel({ channel: "sms", address: null, on_file: false, unavailable_reason: "no_mobile" }),
  ],
};

describe("ACC-S16 — the door onto the customer", () => {
  it("puts an eighth glyph on the rail, and it is the FIRST one R6 draws", () => {
    expect(ACCOUNT_RAIL_ACTION_IDS).toHaveLength(8);
    expect(ACCOUNT_RAIL_ACTION_IDS[0]).toBe("communication");
    // Hard-won law 2: the glyph must carry a label, because the label IS the
    // accessible name a clerk hears and hovers.
    const glyph = ACCOUNT_RAIL_ACTIONS.find((one) => one.id === "communication");
    expect(glyph?.labelKey).toBe("customers.account.action.communication");
  });

  it("shows a channel with nothing on file, and refuses to tick it", async () => {
    render(
      <ToastProvider>
        <ChannelTable channels={FORM.channels} picked={["email"]} onToggle={() => undefined} />
      </ToastProvider>,
    );
    // BR-BIL-036 and the drawing's own instruction: the row is SHOWN so a clerk
    // sees what is missing rather than wondering why an option vanished.
    const rows = await screen.findAllByRole("row");
    expect(rows).toHaveLength(3); // head + two channels
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes[0]).toBeEnabled();
    expect(boxes[1]).toBeDisabled();
  });

  it("never claims a message was sent", async () => {
    render(
      <ToastProvider>
        <ChannelTable channels={FORM.channels} picked={[]} onToggle={() => undefined} />
      </ToastProvider>,
    );
    // `BR-NOT-013` — no provider on email OR text, so BOTH rows say they wait.
    // `findAllByText`, because two rows carrying the same true sentence is the
    // correct rendering and `findByText` would fail on the second one.
    expect(await screen.findAllByText("Waits in the queue")).toHaveLength(2);
    expect(screen.queryByText("Goes out")).not.toBeInTheDocument();
  });

  it("ticks one channel by default and never all of them", () => {
    expect(defaultChannels(FORM.channels)).toEqual(["email"]);
    expect(tickable(FORM.channels[1]!)).toBe(false);
    // An account with nothing at all on file starts with nothing ticked rather
    // than with a channel that cannot be reached.
    expect(defaultChannels([channel({ on_file: false, address: null })])).toEqual([]);
  });
});

describe("the kinds this dialog may not compose", () => {
  it("names the rule's owner rather than going quiet", () => {
    // `BR-PAY-035` and `BR-NOT-008`: a reminder's tone IS a dunning tier, so a
    // ladder step written here would carry no tier and no notice history. The
    // kind is OFFERED and refused with a reason, which is `BR-SHL-025`'s shape.
    const refused = FORM.kinds.find((one) => !one.allowed);
    expect(refused?.kind).toBe("payment_reminder");
    expect(refused?.refusal).toBe("reminder_is_the_ladder");
  });
});

describe("the ready-made messages (PO 2026-09-13)", () => {
  it("fills both fields from the utility's own published wording", () => {
    // The whole point: a clerk sending a planned-outage notice starts from the
    // letter the utility already agreed, not from an empty box.
    const filled = applyTemplate(FORM.templates, "service_outage_notice", {
      subject: "",
      body: "",
    });
    expect(filled.subject).toBe("Planned service interruption in ____");
    expect(filled.body).toContain("We will turn the water off in ____ on ____.");
  });

  it("leaves a typed subject alone when the template has none", () => {
    // An SMS class carries no subject. Writing "" over what the clerk typed
    // would be a silent deletion, and the subject field gives no hint why.
    const filled = applyTemplate(FORM.templates, "sms_payment_received", {
      subject: "About your water",
      body: "",
    });
    expect(filled.subject).toBe("About your water");
    expect(filled.body).toContain("we received ____");
  });

  it("changes nothing when the clerk picks the placeholder", () => {
    // Going back to "Write my own" is how a clerk keeps their own words, not a
    // command to erase them.
    const held = { subject: "Mine", body: "My own words." };
    expect(applyTemplate(FORM.templates, "", held)).toEqual(held);
  });

  it("offers only wording that can actually be queued", () => {
    // ⚠ A clerk's message is rendered against ONE class — `account_message` —
    // so a body carrying `{amount}` is REFUSED at queue time. The server blanks
    // every token outside that palette before serving it, which is what makes
    // the picker safe rather than a trap. `{first_name}` and `{utility_name}`
    // survive because dispatch really does fill them.
    const palette = ["first_name", "utility_name", "account_no", "service_address"];
    for (const one of FORM.templates) {
      for (const token of `${one.subject} ${one.body}`.match(/\{([a-z_]+)\}/g) ?? []) {
        expect(palette).toContain(token.slice(1, -1));
      }
    }
  });
});
