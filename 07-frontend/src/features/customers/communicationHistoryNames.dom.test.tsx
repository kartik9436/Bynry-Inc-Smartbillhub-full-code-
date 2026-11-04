// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-10653 — Customer 360 › Write to customer › Already sent
//           named every message "A message"
// Ruling:   PO 2026-10-29, D2 A — Already sent names every message type
// ───────────────────────────────────────────────────────
// The WHAT column, on the mounted history list. The catalogue half (every
// class in `catalogs.LISTINGS` has a name in all eleven catalogues) is
// `06-backend/tests/test_def_cus_10653_template_class_names.py`; this file
// proves the column READS those names, and that a row with no template class —
// a printed or portal BILL, whose layout is the bill template and not a
// message class — is named by what it is rather than "A message".
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { OutboundRow } from "@/api/endpoints";

const ROWS: Partial<OutboundRow>[] = [
  { id: "a", template_code: "email_past_due", channel: "email", source_type: "reminder" },
  { id: "b", template_code: "dunning", channel: "pdf_print", source_type: "reminder" },
  { id: "c", template_code: "service_work_order_logged", channel: "email", source_type: "appointment" },
  { id: "d", template_code: null, channel: "pdf_print", source_type: "invoice" },
  { id: "e", template_code: "a_class_nobody_has_named", channel: "email", source_type: "notice" },
];

vi.mock("@/api/endpoints", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/api/endpoints")>();
  return {
    ...real,
    getOutbound: async () => ({
      count: ROWS.length,
      next: null,
      previous: null,
      results: ROWS.map((row) => ({
        account_id: null,
        account_no: null,
        copy_no: 0,
        status: "queued",
        held: false,
        recipient_address: "rosa@example.com",
        queued_at: "2026-10-29T10:00:00Z",
        ...row,
      })),
      vocabulary: {},
    }),
  };
});

const { CommunicationHistory } = await import("./AccountCommunicationDialog");

afterEach(cleanup);

describe("DEF-CUS-10653 · Already sent names every message type (PO D2 A)", () => {
  it("names each row by its template class, and a bill with no class as a bill", async () => {
    const { container } = render(<CommunicationHistory accountId="acc-1" />);
    await screen.findAllByText("rosa@example.com");
    const cells = async (id: string) =>
      container.querySelector(`[data-outbound-row="${id}"]`)?.querySelectorAll("td")[1]?.textContent;

    expect(await cells("a")).toBe("Past-due reminder · Email");
    expect(await cells("b")).toBe("Past-due reminder");
    expect(await cells("c")).toBe("Work order logged");
    // RED before: "A message" — a printed bill has no template class.
    expect(await cells("d")).toBe("Bill");
    // The honest fallback stays for a class the catalogue does not know.
    expect(await cells("e")).toBe("A message");
  });
});
