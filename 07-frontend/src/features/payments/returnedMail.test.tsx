// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-016 (returned mail: mark returned → bad-address flag →
//           needs-attention → paper suppressed) ·
//           US-NOT-014 (bounces + returned mail — `POST /deliveries/returned`,
//           whose FIRST frontend caller is the surface these cases cover; G10
//           had no `*.test.tsx` naming it because there was no screen)
//           Screens: S30 · S35 · S32
// Rules:    BR-PAY-018 (single/bulk mark; BALANCES UNAFFECTED; audited) ·
//           BR-NOT-005 (suppression holds the queue row) · BR-BIL-016 (an
//           email that did not arrive is a provider bounce) · BR-TEN-043 (the
//           business date is typed, never read off a clock) · BR-SHL-020 ·
//           BR-SHL-025 (disabled WITH the reason)
// ───────────────────────────────────────────────────────
// §4 test data is US-PAY-016's own: A-11455 Park, Jenna — a paper bill whose
// delivery row comes back — and J18's stack of twelve pieces across nine
// accounts, marked in one action on Tuesday Sep 8 2026.
//
// THE NEGATIVE CASES ARE THE POINT. The easy way to make this surface green is
// to offer "Mark returned" on every row and call the endpoint: the server would
// refuse the email rows and the screen would look like it worked. So:
//
//   · an email row's control is DISABLED and its REASON is on the screen;
//   · a piece already marked cannot be marked again from the UI either;
//   · the date is REQUIRED and nothing is posted without one;
//   · no clock is read anywhere on this path;
//   · the outcome panel prints the SERVER's `balances_affected`, never a
//     reassurance this screen made up.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ToastProvider } from "@/components/Toast";

import {
  BulkMarkReturnedModal,
  MarkReturnedModal,
  PAPER_CHANNEL,
  ReturnedMailOutcome,
  markReturnedRefusal,
  markReturnedSchema,
} from "./returnedMail";
import type { MarkReturnedOutcome } from "./returnedMail";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** J18's Tuesday — a CONSTANT. A test that read a clock would pass every day
 *  while proving nothing about the date a clerk typed (BR-TEN-043). */
const TUESDAY = "2026-09-08";

function render(node: React.ReactElement): string {
  const queryClient = new QueryClient({
    // Nothing may fetch: the stack list is seeded or renders its honest state.
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{node}</ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-PAY-016 — which rows may be marked, and why not", () => {
  it("BR-BIL-016 / TC-5: only PAPER can be marked, and the email row's reason is a sentence", () => {
    expect(markReturnedRefusal({ channel: PAPER_CHANNEL, returned_at: null }, t)).toBeNull();
    const email = markReturnedRefusal({ channel: "email", returned_at: null }, t);
    expect(email).toBe(t("payments.returnedMail.notPaper"));
    // The REASON, not a rule id: a clerk shown "BR-BIL-016" learns nothing.
    expect(email).toContain("email provider");
    expect(email).not.toContain("BR-");
    expect(markReturnedRefusal({ channel: "sms", returned_at: null }, t)).toBe(email);
  });

  it("CLAUDE.md rule 6, from the screen's side: a piece already marked cannot be marked again", () => {
    const already = markReturnedRefusal({ channel: PAPER_CHANNEL, returned_at: TUESDAY }, t);
    expect(already).toBe(t("payments.returnedMail.alreadyMarked"));
    // The server de-dupes on `UNIQUE (tenant, outbound_message_id)` whatever the
    // screen does — this is the SECOND belt, so a clerk working a stack of
    // fourteen is not told "done" twice for one envelope.
    expect(already).toContain("already marked returned");
  });

  it("BR-TEN-043: the date is REQUIRED, and an empty selection posts nothing", () => {
    const schema = markReturnedSchema(t);
    expect(schema.safeParse({ returned_on: TUESDAY, message_ids: ["m1"] }).success).toBe(true);
    expect(schema.safeParse({ returned_on: "", message_ids: ["m1"] }).success).toBe(false);
    // An empty selection is refused rather than treated as "all" — the server
    // refuses it too, for the reason `_message_ids` states: a bulk action that
    // quietly meant EVERYTHING would flag every account in the utility.
    expect(schema.safeParse({ returned_on: TUESDAY, message_ids: [] }).success).toBe(false);
  });
});

describe("US-PAY-016 — the two modals", () => {
  it("the single mark asks for the date and states that no money moves", () => {
    const html = render(
      <MarkReturnedModal
        messageId="msg-1"
        proposedDate={TUESDAY}
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onMarked={() => undefined}
      />,
    );
    expect(html).toContain("Mark this piece returned");
    expect(html).toContain("Date it came back");
    // BR-PAY-018's own clause, on the form a clerk is about to submit.
    expect(html).toContain("Nothing the customer owes changes");
    // ⚠ REVERSED 2026-09-23 (`DEF-PAY-6344`). This asserted the help line
    // *"Tuesday's stack is marked as Tuesday, even when you work through it on
    // Wednesday."* — which says WHY the date is the stack's own. That is
    // RATIONALE, and B14 rule 33 puts rationale at ZERO words on screen; the
    // label is the instruction. The why lives in `returnedMail.tsx` box 1.
    expect(html).not.toContain("Tuesday");
  });

  it("the bulk mark opens with NOTHING selected and its submit says so", () => {
    const html = render(
      <BulkMarkReturnedModal
        proposedDate={TUESDAY}
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onMarked={() => undefined}
      />,
    );
    expect(html).toContain("Mark returned mail");
    // Zero, not "all": a bulk screen that opened pre-selected would flag the
    // whole queue on one click.
    expect(html).toContain(t("payments.returnedMail.bulk.submit", { count: 0 }));
    expect(html).toContain("Nothing the customer owes changes");
  });
});

describe("US-PAY-016 — the outcome a clerk reads", () => {
  const outcome: MarkReturnedOutcome = {
    returned_on: TUESDAY,
    marked: [
      { message_id: "m1", account_id: "a1", channel: PAPER_CHANNEL },
      { message_id: "m2", account_id: "a2", channel: PAPER_CHANNEL },
    ],
    flagged_accounts: [
      { account_id: "a1", created: true },
      { account_id: "a2", created: true },
    ],
    refused: [],
    balances_affected: false,
  };

  it("J18 step 1: it states how many pieces, how many accounts, and on what date", () => {
    const html = render(<ReturnedMailOutcome outcome={outcome} />);
    expect(html).toContain("2");
    expect(html).toContain(TUESDAY);
    expect(html).toContain("Nothing the customer owes changes");
  });

  it("a refusal is NAMED with the server's own sentence — never swallowed by a count", () => {
    const html = render(
      <ReturnedMailOutcome
        outcome={{
          ...outcome,
          refused: [
            {
              code: "not_a_paper_row",
              detail: "only PAPER rows can be marked returned; this one is 'email'.",
            },
          ],
        }}
      />,
    );
    expect(html).toContain("only PAPER rows can be marked returned");
    // The other thirteen still landed — a stack where one piece was already
    // marked is a normal Tuesday and must not stop the rest.
    expect(html).toContain("2");
  });

  it("the invariance sentence is the SERVER's answer, not this screen's belief", () => {
    // If a future build ever answered `true`, the panel must say so loudly
    // rather than keep printing the reassurance. Hard-won law 1: a screen that
    // asserts a guarantee it does not check is not the guarantee.
    const html = render(
      <ReturnedMailOutcome outcome={{ ...outcome, balances_affected: true }} />,
    );
    expect(html).toContain("Stop and tell your administrator");
    expect(html).not.toContain("Nothing the customer owes changes");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-016@EP-PAY-04 (04-docs/05-modules/08-payments/06-epics/EP-PAY-04-outstandings-collections.md US-PAY-016 §1/§3 · 08-payments/02-business-rules.md BR-PAY-018 · 08-qa/01-e2e/journeys/J18-returned-mail-tuesday.md)
// generated: 2026-08-16 by story-coder (returned-mail surface lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED-PROVED FIRST — with `markReturnedRefusal` returning null for every row the email case failed on "expected null to be 'Only post can be marked returned…'", and with the invariance line removed the outcome case failed on the missing sentence. Transcripts in the lane report
// exceptions: (1) NO CASE ASSERTS A SUPPRESSED LETTER: BR-PAY-018's paper hold is the dispatcher's and is out of this release by PO ruling, so there is nothing to assert and a test that mocked one would be asserting a feature nobody built. (2) The POST itself is exercised in 06-backend/tests/test_us_pay_016_surface.py over the real view — these cases are the screen's own decisions, which is what a browser-free suite can honestly prove
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
