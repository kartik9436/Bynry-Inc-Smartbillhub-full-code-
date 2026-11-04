// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CWP-nnnn — ⚠ `nnnn` IS A PLACEHOLDER, NOT A TYPO: the row is
//          handed over in `scratchpad/lane-NOTIF-defects.md` and its id is
//          allocated at merge. Fill it in here in the same diff.
//          The portal enrolment code is minted, queued and
//          readable by nobody. PO: *"Atleast show me 6 digit code on this
//          screen - so that I can copy and paste it during enrolement"*.
// Ruling:  12-governance/02-decision-log.md 2026-09-05 §2.
// Screens: SET-12 → Messages needing attention (the dispatch queue)
// Rules:   B14 rule 21 · rule 36 · hard-won law 2 (built is not wired, and its
//          MIRROR — a live screen behind a dead control) · law 7 (RED first)
// ───────────────────────────────────────────────────────
// THE ONE THING THIS SUITE EXISTS FOR:
//
//   **A PERSON RUNNING A BETA TENANT MUST BE ABLE TO READ THE SIX DIGITS, AND
//   MUST STOP BEING ABLE TO THE DAY A PROVIDER IS CONNECTED.** Either half
//   alone is a defect: without the first, no enrolment can be completed at all;
//   without the second, a live utility's login codes are on a settings screen.
//
// ⚠ THE SECOND HALF IS ASSERTED AS AN ABSENCE, WHICH IS THE HARDER DIRECTION
// AND THE ONE THAT ROTS. `DEF-CWP-3925` is the standing record of what happens
// when a control's condition stops being true and nothing goes red: the whole
// front page of the portal kept refusing over screens that had shipped days
// earlier, past 391 passing cases. So the closed case here does not assert that
// a flag was read — it mounts the REAL tab with a connected channel and asserts
// the control is not in the document.
//
// ⚠ WHAT THIS SUITE CANNOT SEE. jsdom performs no layout. What it proves is
// STRUCTURE — which control is offered, and what the panel puts on the screen.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { OutboundUnsentResponse } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { MESSAGES_SUB, NotificationsTab } from "./SettingsNotificationsTab";
import { UnsentMessagePanel } from "./UnsentMessagePanel";

const T = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

/** The six digits a person is waiting for on enrolment step 2. */
const CODE = "492013";

/** No `portal_enrolment_code` template is published, so the row carries no
 *  pinned wording and there is NO body — the server serves the facts it
 *  stamped instead of inventing a message. This is the shape the enrolment
 *  code actually lands in. */
const OPEN_FACTS: OutboundUnsentResponse = {
  message_id: "msg-1",
  channel: "sms",
  source_type: "portal",
  status: "queued",
  disclosable: true,
  reason: "no_provider_connected",
  message_key: "notifications.unsent.noProvider",
  subject: null,
  body: null,
  facts: [
    { label: "Code", value: CODE },
    { label: "Expires in minutes", value: "10" },
    { label: "Purpose", value: "portal_enrolment" },
  ],
  body_state: "no_wording_published_so_the_facts_are_shown",
  body_state_key: "notifications.unsent.bodyFactsOnly",
};

/** A row that DOES carry a pinned wording renders as the dispatcher would. */
const OPEN_BODY: OutboundUnsentResponse = {
  ...OPEN_FACTS,
  message_id: "msg-2",
  channel: "email",
  source_type: "notice",
  subject: "Your bill is ready",
  body: "PAST DUE REMINDER\n\nYour balance is now overdue.",
  facts: [],
  body_state: "rendered_from_the_pinned_wording",
  // No key: when the letter is on the screen there is nothing left to explain
  // (B14 rule 32's description budget). See `unsent_preview.KEY_BY_BODY_STATE`.
  body_state_key: null,
};

/** A provider is connected. There is nothing to show and nothing IS shown. */
const CLOSED: OutboundUnsentResponse = {
  message_id: "msg-1",
  channel: "sms",
  source_type: "portal",
  status: "queued",
  disclosable: false,
  reason: "provider_connected",
  message_key: "notifications.unsent.providerConnected",
  subject: null,
  body: null,
  facts: [],
  body_state: null,
  body_state_key: null,
};

function clientReturning(body: OutboundUnsentResponse): ApiClient {
  return { get: vi.fn().mockResolvedValue({ data: body }) } as unknown as ApiClient;
}

function mount(node: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>{node}</ToastProvider>
    </QueryClientProvider>,
  );
}

describe("the code a beta tenant has to be able to read", () => {
  it("puts the six digits on the screen when nothing could have sent them", async () => {
    mount(
      <UnsentMessagePanel
        messageId="msg-1"
        client={clientReturning(OPEN_FACTS)}
        onClose={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText(CODE)).toBeInTheDocument();
    });
    // Labelled in a person's words — the server sends the label, so no screen
    // holds a second table of them.
    expect(screen.getByText("Code")).toBeInTheDocument();
    // And WHY there is no letter here, rather than an unexplained short panel.
    expect(screen.getByTestId("unsent-facts")).toBeInTheDocument();
  });

  it("draws a real message body when there is a published wording", async () => {
    mount(
      <UnsentMessagePanel
        messageId="msg-2"
        client={clientReturning(OPEN_BODY)}
        onClose={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText(/PAST DUE REMINDER/)).toBeInTheDocument();
    });
    expect(screen.getByText("Your bill is ready")).toBeInTheDocument();
  });

  it("shows NOTHING at all once a provider is connected — not a greyed body", async () => {
    // ⚠ THE CASE THAT DECIDES THE DESIGN. A body under a caption saying "this
    // would normally be hidden" is the failure; there must be nothing to read.
    const { container } = mount(
      <UnsentMessagePanel
        messageId="msg-1"
        client={clientReturning(CLOSED)}
        onClose={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("unsent-closed")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("unsent-facts")).not.toBeInTheDocument();
    expect(screen.queryByTestId("unsent-body")).not.toBeInTheDocument();
    expect(container.textContent ?? "").not.toContain(CODE);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// HARD-WON LAW 2, BOTH DIRECTIONS — is it wired, and does the control still
// mean what it says?
// ══════════════════════════════════════════════════════════════════════════

/** One stub transport answering every read the dispatch home makes.
 *
 *  `disclosableChannels` is the SERVER'S answer, so this fixture is where the
 *  two states of the whole feature are set — nothing else differs between the
 *  two cases below. */
function dispatchHomeClient(disclosable: string[], answer: OutboundUnsentResponse): ApiClient {
  const queueRow = {
    id: "msg-1",
    source_type: "portal",
    channel: "sms",
    status: "queued",
    recipient_address: "+15125550142",
    unavailable_reason: null,
    attempts: 0,
    last_error: null,
    held: false,
    held_reason: null,
    returned: false,
  };
  return {
    get: vi.fn((path: string) => {
      if (path === "/outbound/summary") {
        return Promise.resolve({
          data: {
            counts: [],
            totals: {},
            held: 0,
            returned: 0,
            retry_exhausted: 0,
            queued_by_channel: {},
            unpopulated_statuses: [],
            problems: [],
          },
        });
      }
      if (path === "/outbound") {
        return Promise.resolve({
          data: {
            results: [queueRow],
            count: 1,
            problems: [],
            vocabulary: {
              statuses: [],
              channels: [],
              source_types: [],
              unpopulated_statuses: [],
              disclosable_channels: disclosable,
            },
          },
        });
      }
      if (path.endsWith("/unsent")) {
        return Promise.resolve({ data: answer });
      }
      // The config cards each own their failure branch, so an error here still
      // leaves the queue — this test's subject — on the screen.
      return Promise.reject(new Error("not part of this case"));
    }),
  } as unknown as ApiClient;
}

describe("the dispatch home is where a tester actually clicks", () => {
  it("offers the control on a row nothing can send, and opens the code", async () => {
    const user = userEvent.setup();
    mount(
      <NotificationsTab
        readOnly={false}
        client={dispatchHomeClient(["sms", "pdf_print"], OPEN_FACTS)}
        sub={MESSAGES_SUB} /* the queue lives on the Messages sub-tab (CR-048 wave I) */
        onOpenRule={() => undefined}
      />,
    );

    // ⚠ RED FIRST: before `SettingsNotificationsTab.tsx` rendered the control
    // this failed here, which is exactly the state the product was in when the
    // PO could not finish an enrolment.
    await user.click(await screen.findByTestId("queue-show-unsent"));

    await waitFor(() => {
      expect(screen.getByText(CODE)).toBeInTheDocument();
    });
  });

  it("does NOT offer it once that channel has a provider — the control is absent", async () => {
    // ⚠ THE HALF THAT ROTS (DEF-CWP-3925). Asserted on the REAL tab rather than
    // on a boolean, because the failure this guards against is a control whose
    // condition stopped being true while every unit test went on passing.
    mount(
      <NotificationsTab
        readOnly={false}
        client={dispatchHomeClient([], CLOSED)}
        sub={MESSAGES_SUB}
        onOpenRule={() => undefined}
      />,
    );

    // The queue itself still renders — this is not an empty screen.
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: T("notifications.queue.showDocument") }),
      ).toBeInTheDocument();
    });
    // …and the disclosure is simply not there. Not disabled, not greyed.
    expect(screen.queryByTestId("queue-show-unsent")).not.toBeInTheDocument();
  });

  it("does not offer it to a read-only Executive, whose request the server refuses", async () => {
    // A4: Settings is View for an Executive and the route behind this control
    // is AdminOrClerk. A button that opens a 403 looks like a feature and is
    // not one — the screen and the server have to agree about who may look.
    mount(
      <NotificationsTab
        readOnly
        client={dispatchHomeClient(["sms", "pdf_print"], OPEN_FACTS)}
        sub={MESSAGES_SUB}
        onOpenRule={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: T("notifications.queue.showDocument") }),
      ).toBeInTheDocument();
    });
    expect(screen.queryByTestId("queue-show-unsent")).not.toBeInTheDocument();
  });

  it("says nothing about the message when the server does not answer the vocabulary", async () => {
    // An older server, or a response this screen cannot fully read, is *cannot
    // tell* — which lands on the same side as *a provider is connected*.
    const partial = {
      get: vi.fn((path: string) => {
        if (path === "/outbound/summary") {
          return Promise.resolve({
            data: {
              counts: [],
              totals: {},
              held: 0,
              returned: 0,
              retry_exhausted: 0,
              queued_by_channel: {},
              unpopulated_statuses: [],
              problems: [],
            },
          });
        }
        if (path === "/outbound") {
          return Promise.resolve({
            data: {
              results: [
                {
                  id: "msg-1",
                  source_type: "portal",
                  channel: "sms",
                  status: "queued",
                  recipient_address: "+15125550142",
                  unavailable_reason: null,
                  attempts: 0,
                  last_error: null,
                  held: false,
                  held_reason: null,
                  returned: false,
                },
              ],
              count: 1,
              problems: [],
            },
          });
        }
        return Promise.reject(new Error("not part of this case"));
      }),
    } as unknown as ApiClient;

    mount(
      <NotificationsTab
        readOnly={false}
        client={partial}
        sub={MESSAGES_SUB}
        onOpenRule={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: T("notifications.queue.showDocument") }),
      ).toBeInTheDocument();
    });
    expect(screen.queryByTestId("queue-show-unsent")).not.toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE TYPE COLUMN — a raw dotted key on a staff screen (the other half of the
// PO's screenshot)
// ══════════════════════════════════════════════════════════════════════════

/** Every kind `apps/notifications/models.py::SOURCE_TYPES` can write, in its
 *  order. The Type column builds its key from this value, so a kind with no
 *  catalogue entry prints its own dotted key to a clerk. */
const SOURCE_KINDS = [
  "invoice",
  "payment",
  "notice",
  "plan",
  "report",
  "ledger",
  "test",
  "bulk_action",
  "move",
  "account",
  "portal",
];

/** ⚠ THE FIVE THAT HAVE NO LABEL TODAY — measured 2026-09-05, and this list
 *  MAY ONLY SHRINK.
 *
 *  `portal` is the one the Product Owner photographed; the other four have been
 *  rendering raw for as long as they have existed and were found by looking for
 *  its siblings. The English and all eleven translations are written and handed
 *  over in `scratchpad/lane-NOTIF-keys.json` — this lane may not edit the
 *  catalogues, so the fix travels separately from the check that proves it.
 *
 *  **The assertion below is an EQUALITY, not a subset, on purpose.** The moment
 *  those keys land this case goes RED and its message says to empty this list —
 *  which is the only way a hand-over like this cannot be quietly forgotten
 *  (hard-won law 2's mirror: a hold with no test that fires when it expires is
 *  a promise nobody is keeping).
 *
 *  ⚠ **IT FIRED, ON THE SAME DAY, AND THIS IS WHAT THAT LOOKS LIKE WORKING.**
 *  The thirteen words landed in all eleven catalogues and this case went red
 *  with `expected [] to deeply equal ["test", "bulk_action", "move", …]` — the
 *  hand-over could not be forgotten because the check refused to stay green
 *  without it. The list is EMPTY now and the equality stays: a kind added to
 *  the platform's vocabulary without a label puts itself back in this array and
 *  turns this case red again. */
const UNLABELLED_TODAY: string[] = [];

describe("every source kind the platform can write has a label", () => {
  it("has no kind printing its own key, and would name any that did", () => {
    // ⚠ THE COMPARISON NOTHING ELSE IN THE REPO MAKES, and it is why five keys
    // could go missing unnoticed. G15 compares the eleven catalogues with EACH
    // OTHER — keys missing from all eleven are in perfect parity. G27 resolves
    // literal `t("…")` keys only and says so; this column builds its key from
    // data. G18 treats a computed key as naming a PREFIX FAMILY and asks
    // whether the catalogue's keys have a call site, never whether the call
    // site's VALUES all have keys. So the missing check is the backend's closed
    // vocabulary against the catalogue's label family, and this is it.
    const raw = SOURCE_KINDS.filter((kind) => {
      const key = `notifications.queue.source.${kind}`;
      return i18n.t(key) === key;
    });
    expect(raw).toEqual(
      UNLABELLED_TODAY,
    );
  });

  it("labels every one of the eleven kinds", () => {
    for (const kind of SOURCE_KINDS.filter((one) => !UNLABELLED_TODAY.includes(one))) {
      const key = `notifications.queue.source.${kind}`;
      expect(i18n.t(key)).not.toEqual(key);
    }
  });
});
