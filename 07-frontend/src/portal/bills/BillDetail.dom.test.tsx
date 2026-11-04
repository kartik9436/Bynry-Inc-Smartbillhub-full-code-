// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-033 (EP-CWP-07) · Screen: CWP-028
// Rules:    BR-CWP-044 (grouped by service; every usage line carries its unit) ·
//           BR-CWP-071 (the readings show HOW they were taken) · BR-CWP-093 ·
//           B14 rule 20 (one table type) · rule 31 (no database id on screen) ·
//           CLAUDE.md hard rule 2 (DISPLAY 2) · hard rule 3
// Cases:    the addition a customer performs · the unit on every row · the
//           eleven-service grouping with fire counting on two lines · the
//           readings panel and its method sentence · the absent-not-zero rail
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { TenantRegionalProvider } from "@/components/TenantRegional";

import type { PortalBillDetail } from "../api/portalClient";

let readBill: () => Promise<PortalBillDetail> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getBillDetail: () => readBill() };
});

const { BillDetailView } = await import("./BillDetail");

/** `US-CWP-033` §4, line for line — the story's own bill. */
const BASE: PortalBillDetail = {
  number: "BL-2608-0141",
  issued_on: "2026-08-30",
  due_on: "2026-09-14",
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  total: "142.1800",
  owing: "142.1800",
  currency: "USD",
  state: "due",
  replaced_by: null,
  replaces: null,
  // null is the COMMON case - most tenants attach nothing (BR-CWP-093).
  attached_answer: null,
  subtotal_display: "128.09",
  tax_display: "14.09",
  total_display: "142.18",
  account: {
    brought_forward: "0.00",
    paid_since: "0.00",
    this_bill: "142.18",
    owing: "142.18",
  },
  groups: [
    {
      service: "water",
      service_name: "Water",
      subtotal_display: "70.42",
      lines: [
        { description: "Monthly service charge", quantity: null, unit: null, rate: null, rate_basis: null, rate_percent: null, amount: "18.5000", amount_display: "18.50", kind: "base" },
        { description: "Usage · first 2,000 gal", quantity: "2000", unit: "gal", rate: "0.0089", rate_basis: "per_unit", rate_percent: null, amount: "17.8000", amount_display: "17.80", kind: "usage" },
        { description: "Usage · 2,001–5,000 gal", quantity: "2820", unit: "gal", rate: "0.0121", rate_basis: "per_unit", rate_percent: null, amount: "34.1220", amount_display: "34.12", kind: "usage" },
      ],
    },
    {
      service: "sewer",
      service_name: "Sewer",
      subtotal_display: "35.67",
      lines: [
        { description: "Share of water used", quantity: "4820", unit: "gal", rate: "0.0074", rate_basis: "per_unit", rate_percent: null, amount: "35.6680", amount_display: "35.67", kind: "usage" },
      ],
    },
    {
      service: "trash",
      service_name: "Trash",
      subtotal_display: "22.00",
      lines: [
        { description: "Cart collection · 96 gal cart", quantity: "1", unit: "cart", rate: "22.0000", rate_basis: "per_unit", rate_percent: null, amount: "22.0000", amount_display: "22.00", kind: "usage" },
      ],
    },
    {
      service: "taxes_and_fees",
      service_name: null,
      subtotal_display: "14.09",
      lines: [
        { description: "State utility tax", quantity: null, unit: null, rate: "0.0425", rate_basis: "percent", rate_percent: "4.25", amount: "5.4200", amount_display: "5.42", kind: "tax" },
        { description: "Regulatory fee", quantity: null, unit: null, rate: null, rate_basis: null, rate_percent: null, amount: "8.6700", amount_display: "8.67", kind: "fee" },
      ],
    },
  ],
  readings: [
    {
      meter: "MTR-4417882",
      service: "water",
      read_at: "2026-08-31",
      prior_value: "148220 gal",
      current_value: "153040 gal",
      usage: "4820 gal",
      unit: "gal",
      read_method: "walk_by",
      read_method_origin: "recorded",
      estimated: false,
    },
  ],
};

/**
 * ⚠ **MOUNTED INSIDE THE REGIONAL PROVIDER, AND THAT IS NOT DECORATION**
 * (`DEF-CWP-3967` fault 3). Portal dates run through `usePortalDate`, which
 * hands back the SERVER'S OWN STRING when no tenant format has been published
 * — deliberately, because inventing `MM/DD/YYYY` for a utility in Berlin is
 * what `DEF-SHL-3964` was. A bare mount therefore publishes nothing, every
 * date renders raw, and a test written against it cannot tell a formatted date
 * from an unformatted one — which is the exact fault this file is now
 * asserting against.
 */
function draw(bill: PortalBillDetail) {
  readBill = async () => bill;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/bills/BL-2608-0141"]}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "DD-MMM-YY" }}>
        {/* WRAPPED IN THE REAL PATH PATTERN, NOT MOUNTED BARE (fixed
            2026-09-05 while building CWP-061). This helper rendered the view
            as the router's only child with no Route at all, so
            useParams().tenant was UNDEFINED and every address this screen
            builds came out //portal/... - a protocol-relative URL to another
            host, which reads as a perfectly good string to toContain. That is
            the fixture flaw DEF-CWP-3925 records for the portal front page, in
            a second file, and it is why no case here asserted an href until
            now: the one assertion that could catch a broken link cannot be
            WRITTEN against the broken mount. */}
        <Routes>
          <Route
            path="/:tenant/portal/bills/:number"
            element={<BillDetailView number="BL-2608-0141" />}
          />
        </Routes>
      </TenantRegionalProvider>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-028 · one bill line by line (US-CWP-033)", () => {
  // ═══════════════════════════════════════════════════════════════════════
  // The drawing's `AmountDueCard`, and the head it sits under.
  // ═══════════════════════════════════════════════════════════════════════

  it("the rail leads with WHAT IS DUE and WHEN, and the button to pay it", async () => {
    // ⚠ **THIS PAGE ANSWERED *what am I paying for* AND NEVER *what do I
    // pay*.** The rail carried a four-row reconciliation whose bottom line was
    // a plain grey row, and no due date and no Pay control appeared anywhere
    // on the screen a customer opens to settle a bill.
    // ⚠ Both figures are the SERVER'S: `owing` is `BR-CWP-043`'s own column
    // and `due_on` is the bill's own date. Nothing here subtracts.
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    // ⚠ **BOTH COPIES EXIST AND CSS SHOWS ONE** — the phone draws it above the
    // charges, the desk in the rail — so every assertion names which.
    for (const where of ["phone", "desk"] as const) {
      const card = container.querySelector(`[data-amount-due='${where}']`) as HTMLElement;
      expect(within(card).getByText("Amount due")).toBeTruthy();
      expect(card.querySelector("[data-figure='amount_due']")?.textContent).toBe("$142.18");
      expect(card.querySelector("[data-due-on='2026-09-14']")?.textContent).toBe("Due 14-Sep-26");
      // ⚠ Asserted WHOLE — `toContain` passes on `//portal/pay-now`.
      expect(card.querySelector("[data-bill-pay] a")?.getAttribute("href")).toBe(
        "/pine-hill/portal/pay-now",
      );
    }
    // ⚠ **THE PHONE COPY IS ABOVE THE CHARGES AND THE DESK COPY IS BELOW
    // THEM** — the whole reason there are two. `TwoCol` stacks the rail under
    // the main column at narrow widths, so a single card in the rail sat below
    // four charge tables on the screen a customer opens to ask what they owe.
    const marks = [...container.querySelectorAll("[data-amount-due], [data-testid='bill-charges']")]
      .map((el) => el.getAttribute("data-amount-due") ?? "charges");
    expect(marks).toEqual(["phone", "charges", "desk"]);
  });

  it("a SETTLED bill loses the button entirely and says it is paid", async () => {
    // The drawing's *Paid* state — *"the button disappears entirely"*. A
    // disabled Pay over a bill with nothing owing is a control that cannot do
    // anything.
    const { container } = draw({
      ...BASE,
      owing: "0.0000",
      state: "paid",
      account: { ...BASE.account, owing: "0.00" },
    });
    await screen.findByText("What you were charged");
    const card = container.querySelector("[data-amount-due='desk']") as HTMLElement;
    expect(card.querySelector("[data-figure='amount_due']")?.textContent).toBe("$0.00");
    expect(container.querySelector("[data-bill-pay]")).toBeNull();
    expect(card.querySelector("[data-bill-settled]")?.textContent).toBe("Paid in full.");
  });

  it("the title is the MONTH the bill arrived, and the number is still on the page", async () => {
    // ⚠ **A SWAP, NOT A REPLACEMENT** (B14 rule 31). A person arrives here
    // having clicked *my August bill*; `BL-2608-0141` in 40px type answers a
    // question nobody asked. The number stays as the charges card's subtitle,
    // which is where the drawing puts it.
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("August 2026");
    expect(container.querySelector("[data-bill-number='BL-2608-0141']")?.textContent).toContain(
      "BL-2608-0141",
    );
  });

  it("the subtitle carries the ISSUE date, and the due date is not printed twice", async () => {
    // The drawing's own subtitle is *covers … · issued Aug 5*, and the issue
    // date was the one date on the payload this screen never drew — the fact
    // that settles which month's bill a customer is holding. The due date now
    // lives in the amount card, once (B14 rule 32).
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    const subtitle = container.querySelector("[data-bill-number='BL-2608-0141']")?.textContent;
    expect(subtitle).toBe("BL-2608-0141 · 01-Aug-26 to 31-Aug-26 · issued 30-Aug-26");
    expect(subtitle).not.toContain("14-Sep-26");
  });

  it("TC-2 — the DISPLAYED lines add to the DISPLAYED total, on the page", async () => {
    // ⚠ **THE POINT OF THE SCREEN**, and it is read back out of the DOM rather
    // than out of the fixture: 18.50 + 17.80 + 34.12 + 35.67 + 22.00 = 128.09,
    // and 128.09 + 5.42 + 8.67 = 142.18. A penny of disagreement here is a
    // support call, and this is the only check in the repo that looks at what
    // the column actually prints.
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");

    const charges = ["water-1", "water-2", "sewer-0", "trash-0"].map((key) =>
      Number(
        container
          .querySelector(`[data-amount='${key}']`)!
          .textContent!.replace(/[$,]/g, ""),
      ),
    );
    const base = Number(
      container.querySelector("[data-amount='water-0']")!.textContent!.replace(/[$,]/g, ""),
    );
    const printedSubtotal = Number(
      container.querySelector("[data-figure='subtotal']")!.textContent!.replace(/[$,]/g, ""),
    );
    const printedTax = Number(
      container.querySelector("[data-figure='tax']")!.textContent!.replace(/[$,]/g, ""),
    );
    const printedTotal = Number(
      container.querySelector("[data-total='bill-total']")!.textContent!.match(/[\d.]+/)![0],
    );

    expect(base + charges.reduce((a, b) => a + b, 0)).toBe(128.09);
    expect(printedSubtotal).toBe(128.09);
    expect(Number((printedSubtotal + printedTax).toFixed(2))).toBe(printedTotal);
    expect(printedTotal).toBe(142.18);
  });

  it("TC-4 — every quantity cell carries its unit, and a bare number never appears", async () => {
    // ⚠ Asserted on EVERY cell, not on a sample: hard rule 3 is about the one
    // row somebody forgets. A line with no quantity draws an em-dash, which is
    // an absence and not a number.
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    const cells = [...container.querySelectorAll("[data-quantity]")];
    expect(cells.length).toBeGreaterThan(0);
    for (const cell of cells) {
      const text = cell.textContent ?? "";
      if (text === "—") continue;
      expect(text).toMatch(/^[\d,]+(\.\d+)? \S+$/);
    }
    expect(container.querySelector("[data-quantity='water-1']")?.textContent).toBe("2,000 gal");
    expect(container.querySelector("[data-quantity='sewer-0']")?.textContent).toBe("4,820 gal");
    expect(container.querySelector("[data-quantity='trash-0']")?.textContent).toBe("1 cart");
  });

  it("a quantity whose unit the server could not state draws an absence, never the number", async () => {
    const { container } = draw({
      ...BASE,
      groups: [
        {
          service: "water",
          service_name: "Water",
          // ⚠ **A REAL AMOUNT, AND THAT IS NOT INCIDENTAL** (`DEF-CWP-3967`
          // fault 5). This case is about a QUANTITY with no unit; a group
          // charging `$0.00` on every line is now dropped before it is drawn,
          // so a zero here would have made this assert the wrong absence.
          subtotal_display: "12.00",
          lines: [
            { description: "Unmeasured usage", quantity: null, unit: null, rate: null, rate_basis: null, rate_percent: null, amount: "12.0000", amount_display: "12.00", kind: "usage" },
          ],
        },
      ],
    });
    await screen.findByText("What you were charged");
    expect(container.querySelector("[data-quantity='water-0']")?.textContent).toBe("—");
  });

  it("TC-3 — a rate shows FOUR decimals and is never run through the money formatter", async () => {
    // `OQ-620(a)`: `0.0089` through `formatMoney` prints `$0.01`, and the line
    // then reconstructs to nothing a customer can check.
    // ⚠ **AND IT NOW CARRIES ITS CURRENCY AND ITS UNIT** (`DEF-CWP-3967`).
    // Four decimals was always right and was never enough: `0.0089` alone
    // does not say dollars, and does not say per what.
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    const rates = [...container.querySelectorAll("[data-row='water-1'] td")].map((c) => c.textContent);
    expect(rates).toContain("$0.0089 / gal");
    // ⚠ **ASSERTED ON THE RATE CELLS, NOT ON THE PAGE.** A page-wide
    // `not.toContain("$0.01")` is a FALSE POSITIVE waiting to happen: it fires
    // on `$0.0121`, which is a correct four-decimal rate with `$0.01` inside
    // it. A check that cannot tell pass from fail is worse than no check.
    const rateCells = [...container.querySelectorAll("[data-rate]")].map((c) => c.textContent);
    expect(rateCells.some((cell) => cell === "$0.01")).toBe(false);
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `DEF-CWP-3967` — the engine's own values, translated for a reader
  // ═══════════════════════════════════════════════════════════════════════

  it("DEF-CWP-3967 — a percentage rate reads as a percentage, not as a fraction", async () => {
    // ⚠ **`0.0425` IS NOT THE RIGHT ORDER OF MAGNITUDE TO GUESS AT.** The tax
    // row on the live bill read `0.0200` for a two per-cent tax; the spec
    // reads `4.25%`. The ×100 is the SERVER's — `wording.percent_text` takes
    // points, and a fraction handed to it prints `0.02%`, which is a
    // well-formed string and wrong by a factor of a hundred.
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    const cells = [...container.querySelectorAll("[data-rate]")].map((c) => c.textContent);
    expect(cells).toContain("4.25%");
    // …and no bare fraction survives anywhere in the rate column.
    expect(cells).not.toContain("0.0425");
  });

  it("DEF-CWP-3967 — a reading is dated, never a raw instant", async () => {
    // This panel was the ONE place in the portal printing an instant
    // untouched: `2026-07-31T00:00:00+00:00` reached the screen verbatim.
    // The fixture below is what the server actually sends as of `DEF-MET-4101`
    // — the calendar date — so this case now tests the real contract.
    const { container } = draw({
      ...BASE,
      readings: [{ ...BASE.readings[0], read_at: "2026-07-31" }],
    });
    await screen.findByText("What you were charged");
    const taken = container.querySelector("[data-read-at='0']")?.textContent ?? "";
    expect(taken).not.toContain("T00:00:00");
    expect(taken).not.toContain("+00:00");
    // ⚠ **`31-Jul-26` — THE DAY THE READING WAS TAKEN (`DEF-MET-4101`).**
    //
    // **This assertion read `30-Jul-26` until 2026-09-06, and the comment that
    // stood here explained at length why the day before was correct:** *"that
    // is the time zone working — midnight UTC on the 31st is seven in the
    // evening on the 30th in `America/Chicago`"*. The arithmetic was right and
    // the conclusion was wrong, because the premise was: a meter read's
    // `read_at` is not an instant at all. Metering stamps every one at
    // `00:00:00Z` of the read DAY — that midnight is what makes the per-date
    // uniqueness key work — so it is a CALENDAR DATE, and a calendar date has
    // no evening-before. The customer was being shown the wrong day on their
    // own bill, and this test held it in place.
    //
    // **It is worth knowing how that happened**, because nothing here was
    // careless: the lane looked at the rendered cell, reasoned carefully about
    // the offset, and wrote down what it saw. What it could not see was that
    // the SERVER was sending the wrong shape. A test written from the rendered
    // output alone will ratify whatever the product does — which is the other
    // half of "no gate reads rendered output", and the reason the fix came with
    // a case that pins the served CONTRACT as well as the drawn day.
    //
    // The server now sends `2026-07-31` and the cell says the 31st. The format
    // is still the tenant's own `DD-MMM-YY` rather than a guessed one, which
    // was the half of IS-8 this case got right all along.
    expect(taken).toBe("31-Jul-26");
  });

  it("DEF-CWP-3967 — a meter names the service it measures", async () => {
    // `W-5026` and `E-5026` are two serial numbers one letter apart. The
    // number stays — it is the label on the box in the yard — and the service
    // is what makes the row findable.
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    expect(container.querySelector("[data-meter='MTR-4417882']")?.textContent).toBe(
      "Water · MTR-4417882",
    );
  });

  it("DEF-CWP-3967 — a service that charged nothing is not drawn at all", async () => {
    // `FIRE 0 connection $0.00` occupied a full block of a live bill. A group
    // whose lines cancel to zero is a DIFFERENT thing and still draws, which
    // is why every line is examined and not only the subtotal.
    const { container } = draw({
      ...BASE,
      groups: [
        {
          service: "fire",
          service_name: "Fire",
          subtotal_display: "0.00",
          lines: [
            { description: "fire connection", quantity: "0", unit: "connection", rate: "0.0000", rate_basis: "per_unit", rate_percent: null, amount: "0.0000", amount_display: "0.00", kind: "usage" },
          ],
        },
        {
          service: "trash",
          service_name: "Trash",
          subtotal_display: "0.00",
          lines: [
            { description: "Cart collection", quantity: "1", unit: "cart", rate: "22.0000", rate_basis: "per_unit", rate_percent: null, amount: "22.0000", amount_display: "22.00", kind: "usage" },
            { description: "Goodwill credit", quantity: null, unit: null, rate: null, rate_basis: null, rate_percent: null, amount: "-22.0000", amount_display: "-22.00", kind: "adjustment" },
          ],
        },
      ],
    });
    await screen.findByText("What you were charged");
    expect(container.querySelector("[data-group='fire']")).toBeNull();
    // A charge and a credit that cancel is money that MOVED, and it is drawn.
    expect(container.querySelector("[data-group='trash']")).toBeTruthy();
  });

  it("TC-6 — fire COUNTS, on two lines, and eleven groups all render", async () => {
    // One 6" line at $60.00 and two 2" lines at $12.00 each: `$60.00 + 2 ×
    // $12.00` = `$84.00`, on TWO rows. Nothing collapses them, because the bill
    // did not.
    const { container } = draw({
      ...BASE,
      groups: [
        {
          service: "fire",
          service_name: "Fire",
          subtotal_display: "84.00",
          lines: [
            { description: 'Fire line · 6"', quantity: "1", unit: "line", rate: "60.0000", rate_basis: "per_unit", rate_percent: null, amount: "60.0000", amount_display: "60.00", kind: "usage" },
            { description: 'Fire line · 2"', quantity: "2", unit: "line", rate: "12.0000", rate_basis: "per_unit", rate_percent: null, amount: "24.0000", amount_display: "24.00", kind: "usage" },
          ],
        },
      ],
    });
    await screen.findByText("What you were charged");
    expect(container.querySelectorAll("[data-group='fire'] tbody tr")).toHaveLength(2);
    expect(container.querySelector("[data-amount='fire-0']")?.textContent).toBe("$60.00");
    expect(container.querySelector("[data-amount='fire-1']")?.textContent).toBe("$24.00");
    expect(container.querySelector("[data-subtotal='fire']")?.textContent).toContain("$84.00");
  });

  it("BR-CWP-044 — the groups are drawn in the order the server sent them", async () => {
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    const order = [...container.querySelectorAll("[data-group]")].map((el) =>
      el.getAttribute("data-group"),
    );
    expect(order).toEqual(["water", "sewer", "trash", "taxes_and_fees"]);
    // The service words come from the catalogue the product already has.
    expect(screen.getByText("Water")).toBeTruthy();
    expect(screen.getByText("Taxes and fees")).toBeTruthy();
  });

  it("TC-8 — the readings panel says HOW each reading was taken", async () => {
    const { container } = draw(BASE);
    await screen.findByText("Readings this bill");
    expect(container.querySelector("[data-reading='0']")?.textContent).toBe("153040 gal");
    expect(container.querySelector("[data-readings-method='']")?.textContent).toBe(
      "Both taken by a reader. Neither was estimated.",
    );
  });

  it("an estimated reading says so rather than claiming a reader took it", async () => {
    const { container } = draw({
      ...BASE,
      readings: [{ ...BASE.readings[0], estimated: true, read_method: null, read_method_origin: "not_stated" }],
    });
    await screen.findByText("Readings this bill");
    expect(container.querySelector("[data-readings-method='']")?.textContent).toContain(
      "estimated",
    );
  });

  it("BR-CWP-093 — a bill with no readings draws NO readings panel", async () => {
    draw({ ...BASE, readings: [] });
    await screen.findByText("What you were charged");
    expect(screen.queryByText("Readings this bill")).toBeNull();
  });

  it("BR-BIL-035 — an unstamped rail figure is ABSENT, never drawn as $0.00", async () => {
    const { container } = draw({
      ...BASE,
      account: { ...BASE.account, brought_forward: null, paid_since: null },
    });
    await screen.findByText("Your account");
    expect(container.querySelector("[data-figure='brought_forward']")).toBeNull();
    expect(container.querySelector("[data-figure='paid_since']")).toBeNull();
    // …and the row IS drawn when the figure is a real zero.
    cleanup();
    const zeroed = draw(BASE);
    await screen.findByText("Your account");
    expect(zeroed.container.querySelector("[data-figure='brought_forward']")?.textContent).toBe(
      "$0.00",
    );
  });

  it("B14 rule 31 — the reference on screen is the bill NUMBER and no id appears", async () => {
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    expect(container.querySelector("[data-bill-number]")?.getAttribute("data-bill-number")).toBe(
      "BL-2608-0141",
    );
    // A uuid, whole or truncated, is a rule-31 breach either way.
    expect(container.innerHTML).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/);
  });

  it("the screen tags itself CWP-028 and routes to both sibling screens", async () => {
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    expect(container.querySelector("[data-screen='CWP-028']")).toBeTruthy();
    expect(container.querySelector("[data-link='comparison']")).toBeTruthy();
    expect(container.querySelector("[data-link='document']")).toBeTruthy();
  });

  it("a bill it cannot read says so in the customer's words, WITH a way out", async () => {
    readBill = async () => {
      throw new Error("refused");
    };
    // ⚠ **MOUNTED UNDER THE REAL PATH PATTERN — the `draw` helper above says
    // why at length, and this case needs it for the first time: it now asserts
    // an ADDRESS, and a bare mount builds every address as `//portal/…`.**
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/bills/BL-2608-0141"]}>
        <Routes>
          <Route
            path="/:tenant/portal/bills/:number"
            element={<BillDetailView number="BL-2608-0141" />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("We could not read this bill.")).toBeTruthy();
    // ⚠ **R-10 (PO 2026-09-11): *"the thing they can do about it must be on
    // that same screen, next to the message. Not a page away. Not in a
    // menu."*** The head's back link is not *next to the message*; the ways
    // out are inside the card that carries the bad news.
    const state = container.querySelector("[data-portal-state='failed']");
    expect(state).not.toBeNull();
    expect(state?.querySelector("[data-way-out='retry']")).not.toBeNull();
    expect(state?.querySelector("[data-way-out='bills']")?.getAttribute("href")).toBe(
      "/pine-hill/portal/bills",
    );
  });
  it("CWP-061 — an answer attached to bills is DRAWN, under the charges", async () => {
    // ⚠ **`DEF-CWP-3985`.** Three of the four parts of this feature existed
    // and nothing joined them up: `also_show_on_screen` is a real column with
    // a sample row set to `bill`, `published_content.attached_answer` was
    // written and tested, and `AttachedAnswerCard` was fully built in the
    // portal kit — and **no portal screen imported it**, so a clerk could tick
    // *also show on the bill* and no customer could ever see it.
    draw({
      ...BASE,
      attached_answer: {
        slug: "estimated",
        question: 'What does "estimated" mean on my bill?',
        topic: "readings",
        body: "It means nobody could read the meter, so we worked it out from what you normally use.",
        asked_for: "en",
        shown_in: "en",
        is_fallback: false,
        updated_on: "2026-08-14",
      },
    });
    const card = await screen.findByText('What does "estimated" mean on my bill?');
    expect(card).toBeTruthy();
    expect(screen.getByText(/nobody could read the meter/)).toBeTruthy();
    // ⚠ THE LINK GOES TO THE ANSWER'S OWN PAGE BY SLUG — B14 rule 31, never a
    // row id — and `/help/:slug` is a real route, not a string that looks like
    // one.
    const link = document.querySelector('a[href="/pine-hill/portal/help/estimated"]');
    expect(link).not.toBeNull();
  });

  it("draws NOTHING when no answer is attached — the slot closes up", async () => {
    // ⚠ `BR-CWP-093`, and the same posture `TipBar` takes: not an empty frame,
    // not a placeholder, not a heading with nothing under it. Nobody can tell
    // the slot was there.
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    expect(container.querySelector("[data-attached-answer]")).toBeNull();
  });

  it("DEF-CWP-4150 — no raw ISO date reaches the subtitle, in the tenant's own format", async () => {
    // ⚠ **THIS IS THE TEST THAT DID NOT EXIST WHILE THE BUG DID.** The subtitle
    // interpolated `period_start`, `period_end` and `due_on` RAW, so the line
    // under the bill number read "· 2026-07-01 to 2026-07-31 · due 2026-08-22"
    // — and all 70 cases in this directory passed over it, because every one
    // of them asserts what a date SAYS and none asserts what shape it is.
    //
    // ⚠ **AND IT ONLY WORKS BECAUSE `draw` PUBLISHES A FORMAT.** Under a bare
    // mount `usePortalDate` hands back the server's own string deliberately, so
    // a formatted date and an unformatted one are the SAME string and this
    // assertion could never fail. The provider in `draw` is what gives it
    // teeth — `DD-MMM-YY`, which shares no characters with `YYYY-MM-DD`.
    const { container } = draw(BASE);
    await screen.findByText("What you were charged");
    const subtitle = container.querySelector("[data-bill-number]");
    expect(subtitle).not.toBeNull();
    const text = subtitle?.textContent ?? "";
    // The bill NUMBER legitimately contains digits and dashes; an ISO date is
    // the specific shape being refused.
    expect(text).not.toMatch(/\d{4}-\d{2}-\d{2}/);
    // …and it is not merely empty, which would satisfy the line above.
    expect(text.length).toBeGreaterThan(10);
  });
});
