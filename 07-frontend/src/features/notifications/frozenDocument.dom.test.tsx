// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-049 task 3 — the SCREEN half. "A reprint and a regulator request
//          serve the stored copy and never re-render", which the CR marks as
//          *"The behaviour the PO actually asked for"*.
// Screens: SET-12 (Settings → Notifications), the dispatch queue
// Rules:   BR-NOT-027 (a sent legal document is FROZEN as the document — PO
//          2026-08-30) · BR-SHL-020 (plain language when something is absent) ·
//          B14 rule 21 · hard-won law 2 (built is not wired) · law 7 (RED first)
// ───────────────────────────────────────────────────────
// THE ONE THING THIS SUITE EXISTS FOR:
//
//   **A PERSON LOOKING AT THIS PANEL MUST BE ABLE TO TELL THE ORIGINAL FROM A
//   RECONSTRUCTION.** If they cannot, the whole change request has failed — the
//   store, the dispatcher's freeze and the route are all worth exactly nothing
//   the moment a screen shows a rebuild as though it were the letter.
//
// So the two acceptance cases are a matched pair, and the second is the sharper
// one: the panel must draw the ORIGINAL's text when there is one, and must draw
// NO DOCUMENT AT ALL when there is not. A caption over a re-render is precisely
// the failure `BR-NOT-027` was written for, and a caption is what nobody reads.
//
// ⚠ WHAT THIS SUITE CANNOT SEE. jsdom performs no layout, so nothing here is
// evidence about geometry. What it proves is STRUCTURE — which words are in the
// document, and which are absent — and absence is most of the point here.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { OutboundDocumentResponse } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { FrozenDocumentPanel, byteLabel, ttlHours } from "./FrozenDocumentPanel";
import { MESSAGES_SUB, NotificationsTab } from "./SettingsNotificationsTab";

const T = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

/** The letter as it was SERVED, with the wording that was in force that day. */
const SERVED_LETTER =
  "NOTICE OF DISCONNECTION\n\nIf you believe the amount on this notice is wrong, " +
  "contact us before the date shown above — not after it.";

/** The clause a System Admin edited AFTERWARDS. It must never appear. */
const TODAYS_EDITED_CLAUSE =
  "Call us within 10 days of the date on this notice if you believe this bill is wrong.";

const ORIGINAL: OutboundDocumentResponse = {
  message_id: "msg-1",
  channel: "pdf_print",
  status: "sent",
  template_code: "disconnect_notice_48_hour",
  template_version: 3,
  provenance: "original",
  is_original: true,
  exempt: false,
  unavailable_reason: null,
  message_key: "notifications.frozenDocument.original",
  detail: "this is the document as it was sent…",
  document: {
    id: "doc-1",
    kind: "disconnect_notice",
    channel: "pdf_print",
    display_name: "disconnect_notice/2026/08/A-1042-pdf_print.txt",
    content_type: "text/plain",
    content_hash: "9f2b7c1a4d",
    byte_length: 2048,
    stored_at: "2026-08-30T15:00:00Z",
    storage_backend: "filesystem",
    subject: null,
    text: SERVED_LETTER,
    download_url: "https://storage.example/sealed/doc-1?sig=abc",
    url_expires_in_seconds: 14400,
  },
};

const NOT_KEPT: OutboundDocumentResponse = {
  message_id: "msg-2",
  channel: "pdf_print",
  status: "queued",
  template_code: "disconnect_notice_48_hour",
  template_version: 3,
  provenance: "re_rendered_from_data_not_the_original",
  is_original: false,
  exempt: false,
  unavailable_reason: "document_not_stored",
  message_key: "notifications.frozenDocument.reRendered",
  detail: "no copy of this message was kept as it was sent…",
  document: null,
};

function clientReturning(body: OutboundDocumentResponse): ApiClient {
  return {
    get: vi.fn().mockResolvedValue({ data: body }),
  } as unknown as ApiClient;
}

function mount(node: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>{node}</ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-049 task 3 — the two states are visibly different", () => {
  it("draws the ORIGINAL letter, with the wording that was in force when it was sent", async () => {
    mount(
      <FrozenDocumentPanel
        messageId="msg-1"
        client={clientReturning(ORIGINAL)}
        onClose={() => undefined}
      />,
    );

    // The letter itself is on the screen…
    await waitFor(() => {
      expect(screen.getByText(/NOTICE OF DISCONNECTION/)).toBeInTheDocument();
    });
    expect(screen.getByText(/contact us before the date shown above/)).toBeInTheDocument();

    // …and it is HEADED as the original, in the backend's own sentence, so a
    // clerk is not left to infer provenance from the absence of a warning.
    expect(
      screen.getByText(
        new RegExp(T("notifications.frozenDocument.original", { sentOn: "" }).slice(0, 30)),
      ),
    ).toBeInTheDocument();

    // The proof it is unchanged is offered, not just claimed.
    expect(screen.getByText("9f2b7c1a4d")).toBeInTheDocument();
  });

  it("draws NO DOCUMENT AT ALL when no copy was kept — and says so", async () => {
    // ⚠ THE CASE THAT DECIDES THE TASK. The temptation is to show the re-render
    // under a caption; a caption is what nobody reads. There must be nothing to
    // read instead.
    mount(
      <FrozenDocumentPanel
        messageId="msg-2"
        client={clientReturning(NOT_KEPT)}
        onClose={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(new RegExp(T("notifications.frozenDocument.reRendered").slice(0, 40))),
      ).toBeInTheDocument();
    });

    // No letter. Not a shortened one, not a greyed-out one — none.
    expect(screen.queryByText(/NOTICE OF DISCONNECTION/)).not.toBeInTheDocument();
    // And no download link, because there is nothing to download.
    expect(screen.queryByText(T("notifications.frozenDocument.download"))).not.toBeInTheDocument();
  });

  it("the two states do not share a sentence", async () => {
    // If both states rendered the same words, "visibly different" would be a
    // claim in a docstring rather than a property of the screen (law 1).
    const original = mount(
      <FrozenDocumentPanel
        messageId="msg-1"
        client={clientReturning(ORIGINAL)}
        onClose={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText(/NOTICE OF DISCONNECTION/)).toBeInTheDocument();
    });
    const originalText = original.container.textContent ?? "";
    cleanup();

    const rebuilt = mount(
      <FrozenDocumentPanel
        messageId="msg-2"
        client={clientReturning(NOT_KEPT)}
        onClose={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(
        screen.getByText(new RegExp(T("notifications.frozenDocument.reRendered").slice(0, 40))),
      ).toBeInTheDocument();
    });
    const rebuiltText = rebuilt.container.textContent ?? "";

    expect(originalText).not.toEqual(rebuiltText);
    expect(originalText).toContain("NOTICE OF DISCONNECTION");
    expect(rebuiltText).not.toContain("NOTICE OF DISCONNECTION");
  });

  it("never shows a storage key, and never shows wording edited after the send", async () => {
    const { container } = mount(
      <FrozenDocumentPanel
        messageId="msg-1"
        client={clientReturning(ORIGINAL)}
        onClose={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText(/NOTICE OF DISCONNECTION/)).toBeInTheDocument();
    });
    const text = container.textContent ?? "";
    expect(text).not.toContain(TODAYS_EDITED_CLAUSE);
    expect(text).not.toContain("storage_key");
    expect(text).not.toContain("t/"); // the key layout `t/<web name>/<module>/<yyyy>/…` (CR-160-BRC10)
  });

  it("states the link's life from the SERVED number, never a hardcoded four", async () => {
    // The TTL is a setting so it can be shortened without a deploy (PO ruling
    // 2026-08-30). A screen that printed "4 hours" would go on saying four the
    // day somebody sets it to one.
    const shortened: OutboundDocumentResponse = {
      ...ORIGINAL,
      document: { ...ORIGINAL.document!, url_expires_in_seconds: 3600 },
    };
    mount(
      <FrozenDocumentPanel
        messageId="msg-1"
        client={clientReturning(shortened)}
        onClose={() => undefined}
      />,
    );
    await waitFor(() => {
      expect(
        screen.getByText(T("notifications.frozenDocument.linkExpires", { hours: 1 })),
      ).toBeInTheDocument();
    });
  });
});

describe("CR-049 task 3 — the small helpers", () => {
  it("turns the served seconds into whole hours", () => {
    expect(ttlHours(14400)).toBe(4);
    expect(ttlHours(3600)).toBe(1);
    // Never zero: "this link works for 0 hours" is worse than a rounded 1, and
    // a sub-hour TTL is a setting an operator chose.
    expect(ttlHours(60)).toBe(1);
  });

  it("labels bytes the way a person reads them", () => {
    expect(byteLabel(512)).toBe("512 B");
    expect(byteLabel(2048)).toBe("2.0 KB");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// HARD-WON LAW 2 — IS IT WIRED? The suite above proves the panel WORKS; this
// proves the product CONTAINS it.
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ EVERY TEST ABOVE PASSES ON A PANEL NOTHING RENDERS. That is the exact shape
// of the four defects in one day this law was written from, and of `CR-049`
// itself: a write-once store, a dispatcher that freezes before every hand-off,
// 145 green tests, and no way for a person to see a single document. So this
// case mounts the REAL dispatch home, finds the control on a queue row, clicks
// it, and reads the letter out of the panel that opens.

/** One stub transport answering every read the dispatch home makes. */
function dispatchHomeClient(document: OutboundDocumentResponse): ApiClient {
  const queueRow = {
    id: "msg-1",
    source_type: "notice",
    channel: "pdf_print",
    status: "sent",
    recipient_address: "1042 Ridge Rd, Katy TX",
    unavailable_reason: null,
    attempts: 1,
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
        return Promise.resolve({ data: { results: [queueRow], count: 1, problems: [] } });
      }
      if (path.endsWith("/document")) {
        return Promise.resolve({ data: document });
      }
      // The two config cards each own their failure branch, so an error here
      // still leaves the queue — and this test's subject — on the screen.
      return Promise.reject(new Error("not part of this case"));
    }),
  } as unknown as ApiClient;
}

describe("CR-049 task 3 — the route is WIRED to a screen (hard-won law 2)", () => {
  it("the dispatch home offers 'show what we sent' on a queue row, and it opens the letter", async () => {
    const user = userEvent.setup();
    mount(
      <NotificationsTab
        readOnly={false}
        client={dispatchHomeClient(ORIGINAL)}
        sub={MESSAGES_SUB} /* the queue lives on the Messages sub-tab (CR-048 wave I) */
        onOpenRule={() => undefined}
      />,
    );

    // ⚠ RED FIRST: before `SettingsNotificationsTab.tsx` imported and rendered
    // the panel, this button did not exist and the case failed here — which is
    // precisely the state CR-049 was in before this lane.
    const open = await screen.findByRole("button", {
      name: T("notifications.queue.showDocument"),
    });
    await user.click(open);

    // The letter that was SERVED, reached by clicking, in the running screen.
    await waitFor(() => {
      expect(screen.getByText(/NOTICE OF DISCONNECTION/)).toBeInTheDocument();
    });
    expect(screen.getByText(/contact us before the date shown above/)).toBeInTheDocument();
  });

  it("a row with no sealed copy opens the honest state, not a rebuilt letter", async () => {
    const user = userEvent.setup();
    mount(
      <NotificationsTab
        readOnly={false}
        client={dispatchHomeClient(NOT_KEPT)}
        sub={MESSAGES_SUB} /* the queue lives on the Messages sub-tab (CR-048 wave I) */
        onOpenRule={() => undefined}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: T("notifications.queue.showDocument") }),
    );

    await waitFor(() => {
      expect(
        screen.getByText(new RegExp(T("notifications.frozenDocument.reRendered").slice(0, 40))),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/NOTICE OF DISCONNECTION/)).not.toBeInTheDocument();
  });
});
