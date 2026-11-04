// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-048 task E6 (test print and send test) over task B7 (the backend)
// Screens: SET-10 · the ten designers S91–S106
// Rules:   BR-SHL-025 (a control that cannot act renders DISABLED WITH ITS
//          REASON — never hidden, and never enabled over a route that refuses) ·
//          BR-NOT-005 (queue only; no synchronous send route may exist) ·
//          BR-NOT-013 (delivery is out of this release on every channel) ·
//          B14 rule 21 (TemplateDetail.tsx is on route-b-migrated.txt)
// ───────────────────────────────────────────────────────
// **WHAT WAVE E LEFT HERE, VERBATIM, BECAUSE IT IS THE REASON THIS FILE
// EXISTS.** The lane that rebuilt this designer wrote in the component: *"E6 IS
// THE ONE WAVE-E TASK THIS LANE COULD NOT BUILD, AND THESE TWO CONTROLS ARE WHY
// IT IS STATED RATHER THAN FAKED … both controls keep rendering DISABLED WITH
// THEIR OWN SENTENCES (BR-SHL-025), because the two have two different fixes,
// and neither is quietly enabled over a route that would refuse."*
//
// That was the right call and it is why the fix was cheap: the way to enable a
// control is to make its route exist, never to relax the check. Task B7 built
// the route, so the SEND half is now true and the PDF half is still not — and
// this file asserts BOTH, because a test that only proved the new button works
// would let a later lane enable the other one beside it and notice nothing.
//
// ── PROVED RED FIRST (hard-won law 7) ─────────────────────────────────────
// Run against the pre-change control — `disabled` unconditional, no result
// line — **4 failed, 2 passed**, quoted verbatim:
//   · the control is ENABLED when the server says a test can be queued
//       → element is disabled
//   · pressing it posts to the QUEUE route and to nothing that sends
//       → AssertionError: expected '/template-catalog/email_bill_ready/pr…'
//         to be '/template-catalog/email_bill_ready/qu…'
//   · it reports BOTH halves — queued, and it will not be delivered
//       → TestingLibraryElementError: Unable to find an element by:
//         [data-testid="test-send-result"]
//   · the sample PDF stays disabled beside an ENABLED send test
//       → TestingLibraryElementError: Unable to find an element by:
//         [data-testid="test-send-result"]
//
// **THE TWO THAT PASSED ARE THE NEGATIVE HALF AND ARE LABELLED AS SUCH RATHER
// THAN COUNTED AS PROOF** — the print-template case and the reason-is-drawn
// case described the OLD screen correctly and must keep passing, which is the
// point: they are what stops a later lane enabling the control everywhere.
//
// ⚠ **AND THE RED PROOF FOUND A BUG IN THIS FILE, WHICH IS THE ARGUMENT FOR
// DOING IT AT ALL.** The route case originally read `post.mock.calls[0][0]` and
// was GREEN — but the second failure above shows what call zero really is when
// the timing shifts: the designer's DEBOUNCED PREVIEW, posting to `…/preview`
// on the same client. A green that depends on a 400ms timer is a test that
// fails on a slower machine and gets "fixed" by loosening the assertion. It now
// reads EVERY call, which is both stabler and stricter.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import type { TemplateDetail, TemplateTestResult } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { TemplateWorkspace as TemplateDetailPanel } from "./TemplateWorkspace";

afterEach(cleanup);

/** The sentence the server sends when the test CAN be queued. It names the
 *  address and says nothing will leave — both halves, in one string, because
 *  the field answers two different questions depending on `can_test_send`. */
const CAN_SEND_REASON =
  "A test goes to you at dana@brazosbendutilities.com, and to nobody else. It is a " +
  "real message on the outgoing queue, so it proves the wording and the pipeline — " +
  "but no mail, text-message or print provider is connected yet, so it will sit " +
  "there rather than arrive.";

/** And the sentence for a PRINT class, which is a statement about ADDRESSES
 *  rather than about providers — this platform holds an email address and a
 *  mobile number for a user and no postal address. */
const CANNOT_SEND_REASON =
  "a test can only be sent to you, and the only addresses this platform holds for a " +
  "user are an email address and a mobile number. There is no way to post a test " +
  "letter to yourself.";

// DEF-2479 — the served sentence carries no module path and no OQ id now; the
// provenance is in `templates_api.py`'s comment beside the constant.
const PDF_REASON = "No sample PDF for this class — the preview shows the text body.";

/** Every path this screen POSTed, in call order. See the route case below for
 *  why the whole list is read rather than the first entry. */
function paths(post: ReturnType<typeof vi.fn>): string[] {
  return post.mock.calls.map((call) => String(call[0]));
}

function aResult(overrides: Partial<TemplateTestResult> = {}): TemplateTestResult {
  return {
    template_code: "email_bill_ready",
    channel: "email",
    queued: true,
    recipient_address: "dana@brazosbendutilities.com",
    will_be_delivered: false,
    dispatchable: false,
    problem: {
      code: "provider_not_configured",
      detail: "No mail provider is connected, so this row will wait on the queue.",
    },
    message_id: "msg-1",
    ...overrides,
  };
}

function aDetail(overrides: Partial<TemplateDetail> = {}): TemplateDetail {
  return {
    code: "email_bill_ready",
    name: "Bill ready · e-bill email",
    category: "billing",
    category_source: "cr_007",
    kind: "Email",
    used_by: "Nothing yet",
    group: "email",
    channel: "email",
    // CR-076 — the surfaces this class is a form for, SERVED. `"Email"` is
    // one channel, so the designer draws no switcher for it.
    preview_surfaces: ["email"],
    merge_fields: ["total_due"],
    merge_field_rows: [],
    sample_identity: { customer_name: "Yuki Nakamura", account_no: "A-11208" },
    derived_spelling: [],
    platform_default: null,
    mandatory_content: [],
    custom_field_variables: [],
    catalog_unavailable: null,
    body_unavailable: null,
    variants: [
      {
        id: "var-1",
        name: "Standard",
        category: "default",
        language: "default",
        is_default: true,
        active: true,
        published_version: 1,
        version_count: 1,
      },
    ],
    selected_variant: "var-1",
    versions: [
      {
        id: "ver-1",
        version: 1,
        status: "published",
        subject: "Your bill is ready",
        body: "Hi {first_name}, your bill of {total_due} is ready.",
        effective_from: null,
        created_by: null,
        published_by: null,
        published_at: "2026-08-16T00:00:00Z",
        archived_at: null,
        updated_at: "2026-08-16T00:00:00Z",
        pinned_by: 0,
        deletable: false,
        author_label: "platform seed",
        change_note: null,
        change_note_unavailable: "No column records what an edit changed.",
      },
    ],
    preview: null,
    preview_unavailable: null,
    sms_character_counter: 160,
    can_edit: true,
    cannot_edit_reason: null,
    // The interesting pair. Both are the SERVER's answer; the screen never
    // decides either for itself.
    can_test_send: true,
    // CR-048 wave I — the label the control draws, beside the sentence it
    // carries on hover. This fixture's template CAN be tested, so the label is
    // the "queues, does not send" one rather than a refusal.
    test_send_label: "Queues, does not send",
    test_send_reason: CAN_SEND_REASON,
    can_download_pdf: false,
    download_pdf_label: "No sample PDF",
    download_pdf_reason: PDF_REASON,
    can_set_default: false,
    set_default_label: "Default is fixed",
    set_default_reason: "The default variant is the row's KEY, not a flag on it.",
    language_selection_label: "Not chosen automatically",
    language_selection_reason: "Languages come from the tenant's regional settings.",
    set_default_br_ref: "OQ-252",
    language_selection_br_ref: "BR-SHL-041",
    ...overrides,
  };
}

function renderDetail(detail: TemplateDetail, client: Partial<ApiClient> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(["template-catalog", "detail", detail.code, "default"], detail);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <TemplateDetailPanel
            code={detail.code}
            client={client as ApiClient}
            readOnly={false}
            readOnlyReason={null}
            variantId={null}
            onSelectVariant={() => undefined}
            onBack={() => undefined}
            surfaces={[]}
            onOpenSurface={() => undefined}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** CR-199-BRC10 F3 — *Send test* opens the drawn dialog (`12-send-test.png`)
 *  first; the queue write happens on its confirm. This presses both, exactly
 *  as a person does — and a test that pressed only the bar button would now
 *  queue nothing, which is the point of the dialog. */
async function pressSendTest() {
  await userEvent.click(screen.getByTestId("test-send"));
  const dialog = screen.getByRole("alertdialog");
  await userEvent.click(within(dialog).getByRole("button", { name: "Send test" }));
}

describe("CR-048 E6 — the send test is enabled only where it is TRUE", () => {
  it("the control is ENABLED when the server says a test can be queued", () => {
    renderDetail(aDetail());
    expect(screen.getByTestId("test-send")).not.toBeDisabled();
  });

  it("a print template keeps the control VISIBLE and DISABLED, with its reason", () => {
    // BR-SHL-025's whole point: never hidden. A System Admin looking for the
    // button must find it and find out why it cannot be pressed — and the
    // reason must be the true one, about addresses rather than about providers.
    renderDetail(
      aDetail({
        can_test_send: false,
        test_send_label: "No address to send to",
        test_send_reason: CANNOT_SEND_REASON,
      }),
    );
    const control = screen.getByTestId("test-send");
    expect(control).toBeInTheDocument();
    expect(control).toBeDisabled();
    // ⚠ CR-048 wave I — the marker DRAWS the label and CARRIES the sentence.
    // Both are asserted: a label alone would let a later lane drop the
    // explanation, which is a control that refuses without saying why
    // (BR-SHL-025) — a worse defect than the paragraph this replaced.
    const note = screen.getByTestId("test-send-reason");
    expect(note).toHaveTextContent("No address to send to");
    expect(note).toHaveAttribute("title", CANNOT_SEND_REASON);
    expect(note.getAttribute("title")).toContain(
      "no way to post a test letter to yourself",
    );
  });

  it("the reason is drawn even when the control is ENABLED, because it says where the test goes", () => {
    renderDetail(aDetail());
    // The address is still on the screen — one hover away rather than as a
    // 226-character paragraph under the button. The claim this case exists to
    // make ("it says WHERE the test goes") is unchanged.
    const note = screen.getByTestId("test-send-reason");
    expect(note).toHaveTextContent("Queues, does not send");
    expect(note.getAttribute("title")).toContain("dana@brazosbendutilities.com");
  });

  it("pressing it posts to the QUEUE route and to nothing that sends", async () => {
    const post = vi.fn().mockResolvedValue({ data: aResult(), status: 200 });
    renderDetail(aDetail(), { post } as unknown as Partial<ApiClient>);
    await pressSendTest();
    await waitFor(() =>
      expect(paths(post)).toContain("/template-catalog/email_bill_ready/queue-test"),
    );
    // ⚠ **EVERY call is inspected, not `calls[0]`.** The designer's live
    // preview is a DEBOUNCED POST on the same client, so which call lands first
    // is a race — an early draft of this test read `calls[0][0]`, passed, and
    // failed during the RED proof with `expected '…/preview' to be
    // '…/queue-test'`. A green result that depends on a 400ms timer is a test
    // that will fail on somebody else's slower machine and be "fixed" by
    // loosening it. BR-NOT-005: the NAME is the contract, and no call this
    // screen makes may be spelled as a send.
    for (const path of paths(post)) {
      for (const forbidden of ["/send", "/send-test", "/test-send"]) {
        expect(path).not.toContain(forbidden);
      }
    }
  });

  it("it reports BOTH halves — queued, and the channel's own reason", async () => {
    const post = vi.fn().mockResolvedValue({
      data: aResult({
        channel_line: { channel: "email", state: "noMailServer", provider: null, host: null },
      }),
      status: 200,
    });
    renderDetail(aDetail(), { post } as unknown as Partial<ApiClient>);
    await pressSendTest();
    const result = await screen.findByTestId("test-send-result");
    // "Queued" ALONE reads, to the person who just pressed the button, as "a
    // test email is on its way". DEF-NOT-10537: the second half is the
    // channel's live line, never "nothing leaves the building".
    expect(result).toHaveTextContent("Queued for dana@brazosbendutilities.com.");
    expect(result).toHaveTextContent("Waiting for a mail server.");
    expect(result).not.toHaveTextContent("leaves the building");
  });

  it("DEF-NOT-10537 — a test the dispatcher will send says it is on its way", async () => {
    const post = vi.fn().mockResolvedValue({
      data: aResult({
        will_be_delivered: true,
        dispatchable: true,
        problem: null,
        channel_line: { channel: "email", state: "sending", provider: "Custom SMTP", host: "smtp.office365.com" },
      }),
      status: 200,
    });
    renderDetail(aDetail(), { post } as unknown as Partial<ApiClient>);
    await pressSendTest();
    const result = await screen.findByTestId("test-send-result");
    expect(result).toHaveTextContent("On its way to dana@brazosbendutilities.com.");
    expect(result).not.toHaveTextContent("Queued");
  });

  it("the sample PDF stays disabled beside an ENABLED send test", async () => {
    // The two always had two different fixes and only one has landed. Enabling
    // the PDF alongside would be the "enabled over a route that refuses"
    // BR-SHL-025 forbids, and nothing else in this suite would notice.
    const post = vi.fn().mockResolvedValue({ data: aResult(), status: 200 });
    renderDetail(aDetail(), { post } as unknown as Partial<ApiClient>);
    await pressSendTest();
    await screen.findByTestId("test-send-result");
    /* ⚠ **THE TWO CONTROLS ARE NO LONGER SIDE BY SIDE, AND THE CASE STILL HOLDS
       (2026-09-07).** *Send test to me* moved to the page head — it acts on the
       TEMPLATE, and while it lived beside Save it could only be reached by
       opening the editor. *Download sample PDF* is still the composer's,
       because it is about the document being written. So the assertion opens
       the wording form to reach it; what it pins is unchanged and is the thing
       worth pinning — one of the two is enabled and the other is not, and the
       disabled one still says why. */
    await userEvent.click(screen.getByTestId("edit-wording"));
    expect(screen.getByTestId("download-pdf")).toBeDisabled();
    // ⚠ DEF-2479 — THIS ASSERTED `"page writer is billing's"`, pinning a
    // sentence that named `apps/billing/documents.py` and OQ-149 on a water
    // utility's screen. The refusal is unchanged and still reachable; what
    // moved is the provenance and the paragraph.
    const note = screen.getByTestId("download-pdf-reason");
    expect(note).toHaveTextContent("No sample PDF");
    expect(note.getAttribute("title")).toBe(PDF_REASON);
    expect(note.textContent).not.toContain("apps/");
  });
});
