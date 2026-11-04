// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-PAY-6344 (PO, 2026-09-23, on the deployed build, Payments →
//          Summary → Mark returned post: *"this modal is showing db keys"*) ·
//          DEF-1122 (the same cell, filed 2026-08-27 and left open)
// Rules:   B14 rule 31 (PO 2026-08-30: *"no Databse ID on screen - that is a
//          rule"*) · B14 rule 33 (on-screen text is capped by what it is for;
//          RATIONALE is zero words) · BR-PAY-018 (the bulk mark) ·
//          BR-TEN-043 (the business date is typed, never read off a clock)
// Screens: S35 — the bulk mark over a Tuesday's stack, opened from S32
// ───────────────────────────────────────────────────────
// **THE PO'S SCREENSHOT, AS AN ASSERTION.** The Account column printed
// `01a07fa5-1034-71f7-995c-05da83d1c972` on every row. The rows below carry
// exactly those ids, a real street address in SENT TO, and the account NUMBER
// the server now serves beside the id — so the one question the PO asked, *is a
// database key on this screen*, is read off the RENDERED TEXT of every cell.
//
// ⚠ **READ AS `textContent`, NEVER AS MARKUP** (B14 rule 31's own status
// column): the id may legitimately ride in an attribute, and a check over the
// HTML string would go red on a correct fix and green on the breach.
//
// ⚠ **THE ROWS NAME A DIFFERENT ACCOUNT EACH**, so a cell that printed any
// row's id — not just the first — is caught.
//
// ⛔ **PROVED RED FIRST, IN THE HARNESS THAT RUNS IT (hard-won law 7).** All
// seven cases were run under vitest against the tip this lane started from,
// before a line of the fix existed, and all seven failed on their own
// assertion — among them `expected [ …(3) ] to deeply equal []` (three cells
// holding a uuid), `expected 'Mark this piece9 Quarry Ct01a0d2b9-77c4-…' to
// contain 'No account number'`, `expected 1 to be 3` (one accessible name
// shared by three boxes), and the dialog text reading `Date it came back*
// Tuesday's stack is marked as Tuesday, even when you work through it on
// Wednesday.`
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import i18n from "@/i18n";
import { ToastProvider } from "@/components/Toast";

import { BulkMarkReturnedModal, PAPER_CHANNEL } from "./returnedMail";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** Any uuid, any version — the shape the PO photographed. */
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

/** J18's Tuesday, a constant (BR-TEN-043). */
const TUESDAY = "2026-09-08";

function piece(overrides: Record<string, unknown>) {
  return {
    source_type: "invoice",
    source_id: "5b1e7c1e-0d0b-4d8e-9d4e-3f1c2a7b9e01",
    channel: PAPER_CHANNEL,
    copy_no: 0,
    status: "queued",
    held: false,
    held_reason: null,
    attempts: 0,
    last_error: null,
    batch_id: null,
    provider_reference: null,
    template_code: "bill_residential",
    template_version: 2,
    template_language: "en",
    unavailable_reason: null,
    queued_at: "2026-09-01T00:00:00+00:00",
    dispatch_not_before: null,
    last_attempt_at: null,
    sent_at: null,
    returned_at: null,
    ...overrides,
  };
}

/** Three pieces as the deployed build served them, plus the number. */
const STACK = [
  piece({
    id: "0c5d7a52-3b41-4f0e-9b7e-7d1f6a2c9e10",
    account_id: "01a07fa5-1034-71f7-995c-05da83d1c972",
    account_no: "AC-2026-00054",
    recipient_address: "107 Mill Pond Ln",
  }),
  piece({
    id: "1d6e8b63-4c52-4a1f-8c8f-8e2a7b3d0f21",
    account_id: "01a0cd45-b921-731c-b1eb-aadb7cd0fcc1",
    account_no: "AC-2026-00061",
    recipient_address: "4410 Bluestem Rd",
  }),
  // An account nobody has numbered yet — the absence is STATED, never the id.
  piece({
    id: "2e7f9c74-5d63-4b20-9d90-9f3b8c4e1032",
    account_id: "01a0d2b9-77c4-7e1a-a0f3-3c9d5e6f7a88",
    account_no: null,
    recipient_address: "9 Quarry Ct",
  }),
];

function answers(body: unknown) {
  return createApiClient({
    tenant: "brazosbend",
    fetchImpl: async () =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  });
}

async function drawStack(rows: unknown[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const client = answers({
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    vocabulary: {
      statuses: [],
      channels: [],
      source_types: [],
      unpopulated_statuses: [],
      disclosable_channels: [],
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BulkMarkReturnedModal
          proposedDate={TUESDAY}
          dateFormat="MM/DD/YYYY"
          client={client}
          onClose={() => undefined}
          onMarked={() => undefined}
        />
      </ToastProvider>
    </QueryClientProvider>,
  );
  // The stack has landed once its table is on screen (the loading frame is a
  // skeleton, not a table).
  return screen.findByRole("table");
}

afterEach(cleanup);

describe("S35 Mark returned post — no database key on screen (B14 rule 31)", () => {
  it("no cell a clerk reads is a uuid — the PO's screenshot, asserted", async () => {
    const table = await drawStack(STACK);
    const cells = within(table).getAllByRole("cell");
    const leaked = cells
      .map((cell) => (cell.textContent ?? "").trim())
      .filter((text) => UUID.test(text));
    expect(leaked).toEqual([]);
    // And nowhere else in the dialog either — a heading, a hint, a count.
    expect(document.body.textContent ?? "").not.toMatch(UUID);
  });

  it("the Account column reads the account NUMBER", async () => {
    const table = await drawStack(STACK);
    expect(within(table).getByText("AC-2026-00054")).toBeInTheDocument();
    expect(within(table).getByText("AC-2026-00061")).toBeInTheDocument();
  });

  it("an account with no number says so in words — never the id, never a dash", async () => {
    const table = await drawStack(STACK);
    const row = within(table).getByText("9 Quarry Ct").closest("tr");
    expect(row).not.toBeNull();
    const text = row?.textContent ?? "";
    expect(text).toContain(t("payments.row.noAccountNo"));
    expect(text).not.toMatch(UUID);
  });

  it("a piece tied to no account says so in the same words", async () => {
    const table = await drawStack([
      piece({
        id: "3f80ad85-6e74-4c31-8ea1-a04c9d5f2143",
        account_id: null,
        account_no: null,
        recipient_address: "12 Ridge Rd",
      }),
    ]);
    const row = within(table).getByText("12 Ridge Rd").closest("tr");
    expect(row?.textContent ?? "").toContain(t("payments.row.noAccountNo"));
  });
});

describe("S35 Mark returned post — each box says WHICH piece it marks", () => {
  it("no box carries the same visible words nine times over", async () => {
    await drawStack(STACK);
    // The column header already says PICK; the words beside every box were
    // noise to a sighted clerk and nine identical names to a screen reader.
    expect(screen.queryByText("Mark this piece")).toBeNull();
  });

  it("every box's accessible name is DIFFERENT and names its piece", async () => {
    await drawStack(STACK);
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes).toHaveLength(STACK.length);
    const names = boxes.map((box) => box.getAttribute("aria-label") ?? "");
    expect(new Set(names).size).toBe(STACK.length);
    expect(names[0]).toContain("107 Mill Pond Ln");
    expect(names[1]).toContain("4410 Bluestem Rd");
    for (const name of names) {
      expect(name).not.toMatch(UUID);
    }
    // Reachable by that name — which is what a screen-reader user navigates by.
    expect(screen.getByRole("checkbox", { name: names[0] })).toBe(boxes[0]);
  });

  it("one account's August and September bills are told apart by their date", async () => {
    // The stack lists EVERY unreturned paper piece, so one account at one
    // address appears once per billing cycle. Address and number alone would
    // give two boxes the same name; the queued date is what differs on screen.
    const august = piece({
      id: "4a91be96-7f85-4d42-9fb2-b15dae603254",
      account_id: "01a07fa5-1034-71f7-995c-05da83d1c972",
      account_no: "AC-2026-00054",
      recipient_address: "107 Mill Pond Ln",
      queued_at: "2026-08-01T00:00:00+00:00",
    });
    const september = { ...august, id: "5ba2cfa7-8096-4e53-a0c3-c26ebf714365", queued_at: "2026-09-01T00:00:00+00:00" };
    await drawStack([august, september]);
    const names = screen.getAllByRole("checkbox").map((box) => box.getAttribute("aria-label") ?? "");
    expect(new Set(names).size).toBe(2);
    expect(names[0]).toContain("08/01/2026");
    expect(names[1]).toContain("09/01/2026");
  });
});

describe("S35 Mark returned post — the date field carries no rationale (B14 rule 33)", () => {
  it("the fourteen-word 'why' sentence is not on screen", async () => {
    await drawStack(STACK);
    expect(document.body.textContent ?? "").not.toContain("Tuesday's stack");
    // The field itself is still there and still required.
    expect(screen.getByText(t("payments.returnedMail.dateLabel"))).toBeInTheDocument();
  });
});
