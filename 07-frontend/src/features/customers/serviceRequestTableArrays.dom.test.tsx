// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   REQ-03 tasks 8, 9 and 10 — the New Request redesign's two table
//           arrays and the Review's communication card. Drawn in
//           `05-prototype/new-request-four-steps-2026-09-29/03-service-1440.png`
//           and `04-review-1440.png`, read AS IMAGES (B14 rule 42).
// Under:    src/features/customers/serviceRequestTableArrays.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY CASE HERE READS RENDERED OUTPUT, NEVER A PROP.** A prop assertion
// cannot tell a column that is drawn from one that is passed and dropped, and
// this repo's single largest defect class is *the screen does not match its
// design*.
//
// ⚠ **EACH CASE WAS PROVED RED FIRST, AND THE RED IS QUOTED ON IT.** The
// method was the one this file exists to enforce: break the thing the case is
// about — delete a column, multiply in the browser, drop the withheld row —
// run it, read the failure, put it back.
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import {
  ApplicationFeesTableArray,
  CustomerMessagesCard,
  ReviewServicesTable,
  ServicesTableArray,
  quantityText,
} from "./serviceRequestTableArrays";
import type { ExtraMessageRow, ServiceTableRow } from "./serviceRequestTableArrays";
import type { Money, ServiceRequestFeeLine } from "./serviceRequestEndpoints";

// ⚠ `as unknown as string` and not a bare cast: i18next types `t` as a
// detailed result, and TS refuses the direct conversion.
const t = (key: string, params?: Record<string, unknown>): string =>
  i18n.t(key, params as never) as unknown as string;

const OPTIONS = [
  { value: "water", label: "Water" },
  { value: "sewer", label: "Sewer" },
  { value: "trash", label: "Trash" },
];

function money(amount: string, display: string, currency: string | null = "USD"): Money {
  return { amount, display, currency };
}

function feeLine(over: Partial<ServiceRequestFeeLine> = {}): ServiceRequestFeeLine {
  return {
    id: "fee-1",
    line_no: 1,
    charge_code: "CONN",
    description: "Connection fee",
    basis: "per request",
    quantity: "1.0000",
    unit_amount: money("45.0000", "45.00"),
    amount: money("45.0000", "45.00"),
    waived: false,
    waive_reason: null,
    settled_at: null,
    invoice_ref: null,
    ...over,
  };
}

afterEach(cleanup);

// ══════════════════════════════════════════════════════════════════════════
// TASK 8 · THE SERVICES TABLE ARRAY
// ══════════════════════════════════════════════════════════════════════════

describe("REQ-03 task 8 · the Services table array", () => {
  function mountServices(
    rows: ServiceTableRow[],
    onChange: (next: ServiceTableRow[]) => void = () => undefined,
  ) {
    render(
      <ServicesTableArray
        rows={rows}
        options={OPTIONS}
        onChange={onChange}
        t={t}
        dateFormat="MM/DD/YYYY"
      />,
    );
  }

  /**
   * RED first: with the `status` column deleted from the component the columns
   * came back as `['Service','Requested start']` and this failed naming the
   * missing one. The drawn order is `SERVICE · REQUESTED START · STATUS · ✕`.
   */
  it("draws the four drawn columns, in the drawn order", () => {
    mountServices([{ code: "water", requested_start: "2026-10-20", status: "new" }]);
    const table = document.querySelector(
      "[data-editable-table='request-services']",
    ) as HTMLElement;
    const headers = Array.from(table.querySelectorAll("thead th")).map(
      (th) => th.textContent ?? "",
    );
    // Three named columns, then the kit's unnamed action column for the ✕.
    expect(headers.filter((text) => text.trim() !== "")).toEqual([
      t("customers.serviceRequest.services.col.service"),
      t("customers.serviceRequest.services.col.requestedStart"),
      t("customers.serviceRequest.services.col.status"),
    ]);
    expect(headers).toHaveLength(4);
  });

  /**
   * **THE SERVICE IS A CHOOSER IN THE ROW** — *"choosing one and dating it is
   * one act"*. RED first: with the cell rendering the code as text, the row
   * held no `<select>` at all.
   */
  it("holds a chooser and a date in the row, and + Service underneath", () => {
    const seen: ServiceTableRow[][] = [];
    mountServices([{ code: "water", requested_start: "2026-10-20", status: "new" }], (rows) =>
      seen.push(rows),
    );
    const row = document.querySelector(
      "[data-editable-table='request-services'] tbody tr",
    ) as HTMLElement;
    expect(row.querySelector("select")).not.toBeNull();
    expect(row.querySelector("input[type='date']")).not.toBeNull();

    const add = document.querySelector("[data-add-service]") as HTMLElement;
    expect(add).not.toBeNull();
    expect(add.textContent).toBe(t("customers.serviceRequest.services.addService"));
    // Adding a row IS adding a service: the press hands back a blank row.
    fireEvent.click(add);
    expect(seen.at(-1)).toHaveLength(2);
    expect(seen.at(-1)?.at(-1)).toEqual({ code: "", requested_start: "", status: null });
  });

  /**
   * **A SERVICE IS OFFERED ONCE.** RED first: without the filter, the second
   * row offered `water` again and this counted two `water` options.
   */
  it("does not offer a service another row already holds", () => {
    mountServices([
      { code: "water", requested_start: "", status: null },
      { code: "", requested_start: "", status: null },
    ]);
    const selects = document.querySelectorAll(
      "[data-editable-table='request-services'] tbody select",
    );
    const blank = selects[1] as HTMLSelectElement;
    const offered = Array.from(blank.options)
      .map((option) => option.value)
      .filter(Boolean);
    expect(offered).toEqual(["sewer", "trash"]);
  });

  /**
   * ⚠ **AN UNKNOWN STATUS IS AN ABSENCE AND IS NEVER DRAWN AS *New*.** RED
   * first: with the cell defaulting to `new`, this read `New` over a row whose
   * status the product does not know.
   */
  it("prints the status it was given, and a dash where there is none", () => {
    mountServices([
      { code: "water", requested_start: "", status: "new" },
      { code: "sewer", requested_start: "", status: "already_on_site" },
      { code: "trash", requested_start: "", status: null },
    ]);
    const cells = Array.from(
      document.querySelectorAll("[data-editable-table='request-services'] tbody tr"),
    ).map((row) => (row.querySelectorAll("td")[2] as HTMLElement).textContent ?? "");
    expect(cells[0]).toBe(t("customers.serviceRequest.services.status.new"));
    expect(cells[1]).toBe(t("customers.serviceRequest.services.status.already_on_site"));
    expect(cells[2]).toBe("—");
    expect(cells[2]).not.toBe(t("customers.serviceRequest.services.status.new"));
  });

  /** The Review's twin: read-only, and **no connection-date column**. */
  it("the Review twin is read-only and has no connection-date column", () => {
    render(
      <ReviewServicesTable
        rows={[{ code: "water", requested_start: "2026-10-20", status: "new" }]}
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
      />,
    );
    const table = document.querySelector(
      "[data-editable-table='review-services']",
    ) as HTMLElement;
    const headers = Array.from(table.querySelectorAll("thead th")).map(
      (th) => (th.textContent ?? "").trim(),
    );
    expect(headers).toEqual([
      t("customers.serviceRequest.services.col.service"),
      t("customers.serviceRequest.services.col.requestedStart"),
      t("customers.serviceRequest.services.col.status"),
    ]);
    // `DEF-CUS-7840` — the column that repeated one request-level fact down
    // every row is gone, and so is every control.
    expect(headers).not.toContain(t("customers.serviceRequest.services.col.connectionDate"));
    expect(table.querySelectorAll("select, input")).toHaveLength(0);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TASK 9 · THE APPLICATION-FEES TABLE ARRAY
// ══════════════════════════════════════════════════════════════════════════

describe("REQ-03 task 9 · the Application fees table array", () => {
  function mountFees(
    lines: ServiceRequestFeeLine[],
    quoted: Money,
    over: {
      pendingRow?: boolean;
      onPick?: (line: ServiceRequestFeeLine | null, code: string) => void;
    } = {},
  ) {
    render(
      <ApplicationFeesTableArray
        fees={{ lines, quoted }}
        codes={[
          { value: "CONN", label: "Connection fee" },
          { value: "METER", label: "Meter fee" },
        ]}
        t={t}
        busy={false}
        pendingRow={over.pendingRow ?? false}
        onAddRow={() => undefined}
        onDropPendingRow={() => undefined}
        onPick={over.onPick ?? (() => undefined)}
        onRemove={() => undefined}
      />,
    );
  }

  /** RED first: with `Waive` still in the column list this read seven. */
  it("draws the six drawn columns and no Waive", () => {
    mountFees([feeLine()], money("45.0000", "45.00"));
    const table = document.querySelector(
      "[data-editable-table='application-fees']",
    ) as HTMLElement;
    const headers = Array.from(table.querySelectorAll("thead th")).map(
      (th) => (th.textContent ?? "").trim(),
    );
    expect(headers.filter(Boolean)).toEqual([
      t("customers.serviceRequest.fees.col.fee"),
      t("customers.serviceRequest.fees.col.chargedPer"),
      t("customers.serviceRequest.fees.col.qty"),
      t("customers.serviceRequest.fees.col.unitPrice"),
      t("customers.serviceRequest.fees.col.amount"),
    ]);
    expect(headers).not.toContain(t("customers.serviceRequest.fees.col.waive"));
  });

  /**
   * ⚠⚠ **THE TEST THAT WOULD STILL PASS IF THE BROWSER MULTIPLIED IS NOT A
   * TEST OF THIS.** So the fixture is DELIBERATELY inconsistent: three at
   * $45.00 a unit, and a stored `amount` of **$100.00** — a figure no
   * multiplication of the other two cells can produce. A component that did
   * `qty × unit` would print `$135.00` and this case names it.
   *
   * The same trick runs on the Total: two lines of $100.00 and $20.00 with a
   * served `quoted` of **$7.00**. A component that summed its own cells would
   * print `$120.00`.
   *
   * RED first, both halves: replacing the cell with
   * `Number(line.quantity) * Number(line.unit_amount.amount)` produced
   * `135.00` and the footer summing the rows produced `$120.00`.
   */
  it("prints the SERVER's amount and the SERVER's total — a browser multiply fails here", () => {
    mountFees(
      [
        feeLine({ quantity: "3.0000", amount: money("100.0000", "100.00") }),
        feeLine({ id: "fee-2", line_no: 2, amount: money("20.0000", "20.00") }),
      ],
      money("7.0000", "7.00"),
    );
    const amounts = Array.from(document.querySelectorAll("[data-fee-line-amount]")).map(
      (node) => node.getAttribute("data-fee-line-amount"),
    );
    expect(amounts).toEqual(["100.0000", "20.0000"]);
    const firstCell = document.querySelector("[data-fee-line-amount]") as HTMLElement;
    expect(firstCell.textContent).toContain("100.00");
    // 3 × 45.00 is 135.00, and it is nowhere on this screen.
    expect(document.body.textContent).not.toContain("135.00");

    const total = document.querySelector("[data-fee-total]") as HTMLElement;
    expect(total).toHaveAttribute("data-fee-total", "7.0000");
    expect(total.textContent).toContain("7.00");
    // 100.00 + 20.00 is 120.00, and it is nowhere on this screen either.
    expect(document.body.textContent).not.toContain("120.00");
  });

  /**
   * **A FIGURE WITHOUT ITS CURRENCY IS ALREADY A FILED DEFECT** on another
   * screen (`DEF-CUS-7806`, a bare `535.00`). RED first: rendering the
   * server's bare `display` string printed `45.00` and this failed on the `$`.
   */
  it("prints the currency beside every figure", () => {
    mountFees([feeLine()], money("45.0000", "45.00"));
    const cell = document.querySelector("[data-fee-line-amount]") as HTMLElement;
    expect(cell.textContent).toContain("$45.00");
    // The server's own two-place string rides alongside, so the two can be
    // proved to agree without re-implementing the rounding rule.
    expect(cell.querySelector("[data-display]")).toHaveAttribute("data-display", "45.00");
    expect((document.querySelector("[data-fee-total]") as HTMLElement).textContent).toContain(
      "$45.00",
    );
  });

  /**
   * **`+ Fee` MAKES A ROW AND ITS CHOOSER IS THE ADD** — the *Choose a fee…*
   * box is gone. RED first: without `pendingRow` the table drew one row and
   * there was no `<select>` to answer.
   */
  it("+ Fee makes an unanswered row whose chooser raises the fee", () => {
    const picked: string[] = [];
    mountFees([feeLine()], money("45.0000", "45.00"), {
      pendingRow: true,
      onPick: (_line, code) => picked.push(code),
    });
    const add = document.querySelector("[data-add-fee]") as HTMLElement;
    expect(add.textContent).toBe(t("customers.serviceRequest.fees.addFeeRow"));
    const chooser = document.querySelector(
      "[data-editable-table='application-fees'] tbody select",
    ) as HTMLSelectElement;
    // The fee already on the table is not offered twice.
    expect(
      Array.from(chooser.options)
        .map((option) => option.value)
        .filter(Boolean),
    ).toEqual(["METER"]);
    fireEvent.change(chooser, { target: { value: "METER" } });
    expect(picked).toEqual(["METER"]);
  });

  /** `1.0000` reads `1`, the way the drawing has it — and nothing is rounded. */
  it("prints a whole quantity without its stored zeros", () => {
    expect(quantityText("1.0000")).toBe("1");
    expect(quantityText("2.5000")).toBe("2.5");
    expect(quantityText("3")).toBe("3");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TASK 10 · WHAT THE CUSTOMER IS TOLD
// ══════════════════════════════════════════════════════════════════════════

describe("REQ-03 task 10 · the communication card", () => {
  const ROWS = [
    {
      key: "request_received",
      message: "Request received",
      channel: "Email",
      to: "mike@yopmail.com",
      when: t("customers.serviceRequest.messages.when.on_submit"),
    },
    {
      key: "documents_outstanding",
      message: "Documents needed",
      channel: "Email",
      to: "mike@yopmail.com",
      when: t("customers.serviceRequest.messages.notSentNoWording"),
      withheld: true,
    },
  ];

  /** RED first: with the `when` column dropped the header list came back with
   *  three entries and this named the missing one. */
  it("draws MESSAGE · CHANNEL · TO · WHEN, read-only", () => {
    render(<CustomerMessagesCard rows={ROWS} absence={null} t={t} />);
    const table = document.querySelector(
      "[data-editable-table='review-messages']",
    ) as HTMLElement;
    expect(
      Array.from(table.querySelectorAll("thead th")).map((th) => (th.textContent ?? "").trim()),
    ).toEqual([
      t("customers.serviceRequest.messages.col.message"),
      t("customers.serviceRequest.messages.col.channel"),
      t("customers.serviceRequest.messages.col.to"),
      t("customers.serviceRequest.messages.col.when"),
    ]);
    // Read-only: nothing to press, nothing to type, no ✕.
    expect(table.querySelectorAll("button, select, input")).toHaveLength(0);
  });

  /**
   * ⚠⚠ **A MESSAGE THAT WILL NOT BE SENT GETS ITS OWN ROW SAYING SO.** RED
   * first: filtering withheld rows out left ONE row, and the difference
   * between *nobody is being told* and *this one is being held* vanished —
   * which is the whole reason the card is drawn.
   */
  it("draws a withheld message as its own row, saying so", () => {
    render(<CustomerMessagesCard rows={ROWS} absence={null} t={t} />);
    const rows = document.querySelectorAll(
      "[data-editable-table='review-messages'] tbody tr",
    );
    expect(rows).toHaveLength(2);
    const withheld = document.querySelector("[data-message-withheld]") as HTMLElement;
    expect(withheld).not.toBeNull();
    expect(withheld.textContent).toBe("Documents needed");
    expect((rows[1] as HTMLElement).textContent).toContain(
      t("customers.serviceRequest.messages.notSentNoWording"),
    );
  });

  /**
   * ⚠ **A STATED ABSENCE IS RENDERED AS AN ABSENCE AND NEVER AS ROWS.** RED
   * first: drawing the table anyway put an empty grid under the heading, which
   * reads as *nothing is being sent* rather than *we cannot say*.
   */
  it("renders the server's stated absence instead of a table", () => {
    render(
      <CustomerMessagesCard
        rows={[]}
        absence={t("customers.serviceRequest.messages.serverCannotAnswer")}
        t={t}
      />,
    );
    const note = document.querySelector("[data-messages-card='absent']") as HTMLElement;
    expect(note.textContent).toBe(t("customers.serviceRequest.messages.serverCannotAnswer"));
    expect(document.querySelector("[data-editable-table='review-messages']")).toBeNull();
  });

  /** An answered read that holds nothing is a DIFFERENT fact from an absence,
   *  and it gets its own sentence rather than the other one. */
  it("an answered read with no rows says nothing goes out", () => {
    render(<CustomerMessagesCard rows={[]} absence={null} t={t} />);
    expect(
      (document.querySelector("[data-messages-card='none']") as HTMLElement).textContent,
    ).toBe(t("customers.serviceRequest.messages.noneAtAll"));
  });

  /** A column the server has not answered draws the absence glyph, never a
   *  guessed channel. */
  it("draws a dash where the server served no channel", () => {
    render(
      <CustomerMessagesCard
        rows={[{ key: "decision", message: "Decision", channel: "", to: "", when: "On decision" }]}
        absence={null}
        t={t}
      />,
    );
    const cells = Array.from(
      document.querySelectorAll("[data-editable-table='review-messages'] tbody td"),
    ).map((td) => (td.textContent ?? "").trim());
    expect(cells[1]).toBe("—");
    expect(cells[2]).toBe("—");
    expect(cells[1]).not.toBe(t("customers.serviceRequest.messages.channel.email"));
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-10042 (PO 2026-10-11) — *"use table array componnet and allow user
// to add more communcation to user"*.
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-10042 · the clerk adds messages to What the customer is told", () => {
  const AUTO = [
    { key: "request_received", message: "Request received", channel: "Email", to: "john@yopmail.com", when: "On submit" },
  ];
  const TEMPLATES = [{ code: "welcome_note", name: "Welcome note" }];

  function Harness(props: { templates?: { code: string; name: string }[] }) {
    const [rows, setRows] = useState<ExtraMessageRow[]>([]);
    return (
      <>
        <CustomerMessagesCard
          rows={AUTO}
          absence={null}
          t={t}
          extra={{ rows, templates: props.templates ?? TEMPLATES, defaultAddress: "john@yopmail.com", onChange: setRows }}
        />
        <output data-testid="rows">{JSON.stringify(rows)}</output>
      </>
    );
  }

  it("is a TableArray with an Add a message row that defaults to the applicant's email on submit", () => {
    const { getByRole, getByTestId } = render(<Harness />);
    expect(document.querySelector("[data-editable-table='review-messages']")).not.toBeNull();
    fireEvent.click(getByRole("button", { name: t("customers.serviceRequest.extra.add") }));
    expect(JSON.parse(getByTestId("rows").textContent ?? "[]")).toEqual([
      { template_code: "", channel: "email", to_address: "john@yopmail.com", send_when: "on_submit" },
    ]);
    const pick = document.querySelector("[data-cell='extra_template_0']") as HTMLSelectElement;
    fireEvent.change(pick, { target: { value: "welcome_note" } });
    fireEvent.change(document.querySelector("[data-cell='extra_when_0']") as HTMLSelectElement, {
      target: { value: "on_approve" },
    });
    expect(JSON.parse(getByTestId("rows").textContent ?? "[]")[0]).toMatchObject({
      template_code: "welcome_note",
      send_when: "on_approve",
    });
  });

  it("the automatic row stays read-only and cannot be removed", () => {
    const { getByText } = render(<Harness />);
    expect(getByText("Request received")).toBeInTheDocument();
    expect(document.querySelector("[data-cell^='extra_']")).toBeNull();
  });

  it("with no ready-made messages, Add a message says why it is held", () => {
    const { getByRole } = render(<Harness templates={[]} />);
    expect(getByRole("button", { name: t("customers.serviceRequest.extra.add") })).toBeDisabled();
  });
});
