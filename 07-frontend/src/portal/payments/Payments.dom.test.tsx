// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-048 (EP-CWP-09) · Screen: CWP-041
// Rules:    BR-CWP-061 (a bounce is TWO rows, the reversal DIRECTLY ABOVE,
//           worded *returned by the bank*) · BR-CWP-050 (a credit shows its
//           reason) · BR-CWP-051 (a write-off NEVER shows its reason code) ·
//           BR-CWP-056 (a held control carries its reason) · B14 rule 31 (no
//           database id on screen) · rule 33 · CLAUDE.md hard rule 4
// Cases:    the two rows and their ORDER · the negative sign, unmodified · the
//           credit's reason · the write-off with no reason anywhere · the held
//           controls · the empty state · the failed read
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalListRequest, PortalMoney, PortalMoneyRow } from "../api/portalClient";

// A plain function, not `vi.fn()` — a recording stand-in notices a rejected
// promise before the screen's own error handling does.
let readMoney: () => Promise<PortalMoney> = async () => {
  throw new Error("no behaviour set");
};
/** Every request, recorded — `DEF-CWP-5747`. Typed as the wrapper's own
 *  option bag, so an assertion about `filters.group` or `year` is checked
 *  against the shape that actually travels rather than against `{}`. */
let asked: (PortalListRequest & { year?: number; accountId?: string | null })[] = [];
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getMoneyList: (options: Record<string, unknown> = {}) => {
      asked.push(options);
      return readMoney();
    },
  };
});

const { PaymentsView } = await import("./Payments");

const PAYMENT: PortalMoneyRow = {
  kind: "payment",
  date: "2026-07-02",
  how: "Cheque",
  reference: "10174",
  // ⚠ **NOT THE SAME FIELD AS `reference`** (`CR-085` `CPB-20`): `reference` is
  // the cheque number the customer wrote and this is the payment's own number,
  // which is what the receipt document is filed under.
  receipt_reference: "PMT-2607-0031",
  receipt_available: true,
  applied_to: ["BL-2606-0147"],
  returned_by_the_bank: false,
  amount: "129.0200",
  currency: "USD",
  state: "reversed",
  money_type: "payment",
};

const REVERSAL: PortalMoneyRow = {
  ...PAYMENT,
  kind: "reversal",
  // A bounced cheque posts no receipt — the server sends `null` and the row
  // carries no receipt control at all (`CR-085` `CPB-20`).
  receipt_reference: null,
  applied_to: [],
  returned_by_the_bank: true,
  amount: "-129.0200",
  state: "bounced",
};

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (CLAUDE.md hard-won law 2). With an
 * `initialEntries` and no matching `<Route>`, `useParams().tenant` is
 * `undefined` and every href this screen builds comes out `//portal/…` — a
 * protocol-relative URL to another host that reads as a perfectly good string
 * to `toContain`. The door assertions below could not fail without this.
 */
function draw(money: PortalMoneyRow[]) {
  // ⚠ **THE STAND-IN APPLIES THE SEARCH, BECAUSE THE SEARCH IS THE SERVER'S
  // NOW (`DEF-CWP-5747`).** It reads the `q` the screen sent and answers the
  // rows that match — which is the behaviour under test. A stand-in that
  // returned every row whatever was asked would make the narrowing cases below
  // pass over a screen that had stopped narrowing at all: law 7's *incapable
  // of failing* shape, on the two cases whose whole subject is that one needle
  // narrows both halves.
  //
  // The predicate mirrors `apps/portal/selectors.MONEY_SEARCH_FIELDS` — the
  // date, the tender, the reference the customer can read and the receipt
  // number — plus the invoice numbers a payment settled.
  readMoney = async () => {
    const needle = String(asked[asked.length - 1]?.q ?? "").toLowerCase();
    const rows =
      needle === ""
        ? money
        : money.filter((row) =>
            [row.date, row.how, row.reference, ...row.applied_to].some((value) =>
              (value ?? "").toLowerCase().includes(needle),
            ),
          );
    return {
      money: rows,
      // The two the server serves since `DEF-CWP-5747`: `count` is what the
      // search matched and `populated` is whether anything moved money in the
      // chosen YEAR — which `count` cannot say once somebody has typed.
      count: rows.length,
      page: 1,
      per: 50,
      populated: money.length > 0,
    };
  };
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/payments"]}>
      <Routes>
        <Route path="/:tenant/portal/payments" element={<PaymentsView />} />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * **THE DESK TABLE HALF OF THE SCREEN** (`CR-085`).
 *
 * ⚠ **THIS SCREEN NOW DRAWS EVERY PAYMENT TWICE — ONCE AS A TABLE ROW AND ONCE
 * AS A PHONE CARD — AND ONLY ONE OF THEM IS EVER VISIBLE.** The switch is CSS
 * (`md:hidden` / `max-md:hidden`), and jsdom applies no CSS, so an unscoped
 * `screen.findByText("Bounced")` finds two elements and fails. Scoping is not a
 * workaround: the assertions below are ABOUT the table — its cells, its chips,
 * its muted row — and saying so is what stops the same query silently starting
 * to answer with the card instead. `CWP-027` took the same shape the same week.
 */
function desk(container: HTMLElement) {
  return within(container.querySelector("[data-list='CWP-041']") as HTMLElement);
}

/** `desk`, but it waits for the list to arrive first — the table is the last
 *  thing on the page to exist, so scoping to it before the read resolves gets a
 *  `null` container rather than a miss. */
async function deskFinds(container: HTMLElement, text: string) {
  await screen.findByRole("table");
  return desk(container).getByText(text);
}

afterEach(cleanup);

describe("CWP-041 · payments and receipts (US-CWP-048)", () => {
  it("DEF-CWP-3954 — Payments is the door to the eight money screens", async () => {
    // ⚠ **ALL SEVEN WERE SHIPPED AND UNREACHABLE**, and two of them were a
    // CLOSED LOOP: `Methods.tsx` linked to `/autopay`, `Autopay.tsx` linked
    // back to `/payment-methods`, and those were the only two references to
    // either address in the whole front end. Asserted BY ADDRESS, whole —
    // `toContain("/autopay")` passes on `//portal/autopay`, which is another
    // host. Drawn on the empty state too, because a customer who has paid
    // nothing yet is exactly the person looking for how to pay.
    const { container } = draw([]);
    await screen.findByText("Your payments will appear here.");
    // ⚠ **THEY ARE ERRAND CARDS NOW, NOT BARE BUTTONS**
    // (`DEF-CWP-3975`, delta 41.9). Same destinations and the same
    // by-address assertion; what changed is that each carries a title and a
    // grey line saying what the errand IS, because a column of undifferentiated
    // boxes is not a navigation design.
    //
    // ⚠ **AND THERE ARE EIGHT FROM 2026-09-08** (`DEF-CWP-4653`, `CR-085`).
    // Budget billing — `/level-pay` — used to be reachable ONLY from *Help
    // paying*, so a mainstream product for anyone with a summer-and-winter
    // bill sat behind a hardship screen. **This list is asserted whole and in
    // order ON PURPOSE**: a `toContain` per door would have let the eighth be
    // dropped again in silence, and the ORDER is the design — `level-pay` sits
    // beside the other ways of changing what you pay, above `fees`, which is
    // the one errand for somebody who is not a customer yet.
    const doors = [...container.querySelectorAll("[data-errand] a")].map((a) =>
      a.getAttribute("href"),
    );
    expect(doors).toEqual([
      "/pine-hill/portal/pay-now",
      "/pine-hill/portal/payment-methods",
      "/pine-hill/portal/autopay",
      "/pine-hill/portal/plan",
      "/pine-hill/portal/plan-offer",
      "/pine-hill/portal/money-back",
      "/pine-hill/portal/level-pay",
      "/pine-hill/portal/fees",
    ]);
    // ⚠ **AND EVERY ONE OF THEM SAYS WHAT IT IS.** A row of working
    // buttons passed every check we own — each wired, each labelled, G13
    // satisfied. Nothing asked whether a customer could tell *Your payment
    // plan* from *A plan we have offered you* from four words each.
    const cards = [...container.querySelectorAll("[data-errand]")];
    expect(cards).toHaveLength(8);
    for (const card of cards) {
      expect((card.querySelector("p")?.textContent ?? "").length).toBeGreaterThan(20);
    }
  });

  /**
   * Delta 41.1 · X4 — **the screen has a HEADING, not just a section label.**
   * The title WAS the kicker: small, uppercase, grey `YOUR PAYMENTS`.
   */
  it("41.1 · a page head with the kicker PAYMENTS over the title", async () => {
    const { container } = draw([PAYMENT]);
    await deskFinds(container, "Cheque");
    const head = container.querySelector(".page-header") as HTMLElement;
    expect(head).not.toBeNull();
    expect(head.querySelector("h1")?.textContent).toBe("What you have paid");
    expect(head.textContent).toContain("Payments");
  });

  /**
   * `DEF-CWP-3975` / delta 41.3 — **the reversal is drawn in RED, not merely
   * chipped red.** The drawing paints the whole row — date, how, reference and
   * the words *Returned by the bank* — over a negative amount. Only the chip
   * was red; every other cell read exactly like a payment that went through,
   * on the one row a customer must not skim past.
   */
  it("41.3 · every cell of the reversal is marked, and the row it undoes is not", async () => {
    const { container } = draw([REVERSAL, PAYMENT]);
    await deskFinds(container, "Bounced");

    // ⚠ **FOUR CELLS, COUNTED.** *Is there a red span somewhere* would pass
    // with one cell marked and three reading like an ordinary payment.
    // ⚠ Counted inside the TABLE, so the phone card's own marks cannot make
    // this number up for a desk row that lost one.
    const marked = container.querySelectorAll("[data-list='CWP-041'] [data-reversal]");
    expect(marked.length).toBeGreaterThanOrEqual(4);
    for (const one of marked) expect(one.className).toContain("text-danger-700");

    // ⚠ **AND THE ROW BENEATH IT IS NOT MARKED.** The original payment was
    // real; it is history, not a warning. A test that only counted red cells
    // would pass on a screen that painted both rows.
    const rows = [...container.querySelectorAll("tbody tr")];
    expect(rows).toHaveLength(2);
    expect(rows[0].querySelectorAll("[data-reversal]").length).toBeGreaterThanOrEqual(4);
    expect(rows[1].querySelectorAll("[data-reversal]")).toHaveLength(0);

    // The words in the applied-to cell carry the whole explanation, in red.
    // ⚠ Scoped to the TABLE — the phone card renders the same mark, and this
    // case is about the desk row.
    const said = container.querySelector(
      "[data-list='CWP-041'] [data-returned]",
    ) as HTMLElement;
    expect(said.textContent).toBe("Returned by the bank");
    expect(said.className).toContain("text-danger-700");
  });

  /**
   * `DEF-CWP-3974` / delta 41.2 — **REFERENCE is what a customer recognises.**
   * Every row read `SAMPLE-BL-2608-000077`: the internal `confirmation` column,
   * carrying a seed prefix, on a customer's screen. The column always held a
   * REAL value, so a test asserting the cell is non-empty passed over the wrong
   * FIELD — which is why this one asserts the SHAPE.
   */
  it("41.2 · the reference is the customer's, and never an internal string", async () => {
    const { container } = draw([{ ...PAYMENT, reference: "#10174" }]);
    await deskFinds(container, "Cheque");
    const text = container.textContent ?? "";
    expect(text).toContain("#10174");
    // The two shapes that must never reach this column again: our seed prefix,
    // and a bill number standing in for a payment reference (B14 rule 31 keeps
    // ids off the glass; this is the field-choice half of the same idea).
    expect(text).not.toContain("SAMPLE-");
    expect(text).not.toMatch(/\bBL-\d{4}-\d+\b(?![^<]*Applied)/);
  });

  it("TC-2 — a bounce is TWO rows and the reversal sits DIRECTLY ABOVE", async () => {
    // ⚠ **THE CASE THE SCREEN EXISTS FOR** (`BR-CWP-061`). Nothing edits a
    // payment (hard rule 4), so the customer sees both rows — and a screen that
    // showed one row with a changed status would be describing a database this
    // product does not have.
    const { container } = draw([REVERSAL, PAYMENT]);
    await deskFinds(container, "Bounced");

    const rows = container.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Returned by the bank");
    expect(rows[0]?.textContent).toContain("Bounced");
    expect(rows[1]?.textContent).toContain("BL-2606-0147");
    expect(rows[1]?.textContent).toContain("Reversed");
    // Both carry the SAME cheque number — that is what ties the pair together
    // for somebody holding a bank statement.
    expect(rows[0]?.textContent).toContain("10174");
    expect(rows[1]?.textContent).toContain("10174");
  });

  it("renders the MINUS the server sent, and takes no absolute value", async () => {
    // ⚠ A sign that means something. `credit_notes.amount <= 0` is a database
    // constraint precisely because two writers once stored opposite signs and a
    // panel read $272.30 on an account owing $222.30.
    const { container } = draw([REVERSAL, PAYMENT]);
    await deskFinds(container, "Bounced");
    expect(container.querySelector("[data-amount='0']")?.textContent).toBe("-$129.02");
    expect(container.querySelector("[data-amount='1']")?.textContent).toBe("$129.02");
  });

  it("TC-4 — a goodwill credit shows its date and its plain reason", async () => {
    const { container } = draw([
      {
        kind: "credit",
        date: "2026-07-12",
        how: null,
        reference: "CN-2607-0004",
        receipt_reference: null,
        receipt_available: false,
        applied_to: ["BL-2607-0139"],
        returned_by_the_bank: false,
        amount: "-25.8800",
        currency: "USD",
        state: "credited",
        money_type: "credit",
        reason: "reading dispute",
      },
    ]);
    await deskFinds(container, "Credited");
    expect(container.querySelector("[data-amount='0']")?.textContent).toBe("-$25.88");
    // ⚠ **SCOPED TO THE TABLE, BECAUSE THE CARD CARRIES THE SAME MARK.** Both
    // halves render `AppliedCell`, so a bare `container.querySelector` answers
    // with whichever comes first in the markup — the card — and this case is
    // about the desk cell. Both are asserted rather than either being trusted.
    const table = container.querySelector("[data-list='CWP-041']") as HTMLElement;
    expect(table.querySelector("[data-reason]")?.textContent).toBe("reading dispute");
    expect(
      container.querySelector("[data-money-card='0'] [data-reason]")?.textContent,
    ).toBe("reading dispute");
    expect(container.textContent).toContain("2026-07-12");
  });

  it("TC-5 — a write-off shows its amount and date and NEVER a reason", async () => {
    // ⚠ **THE NEGATIVE ASSERTION IS THE WHOLE TEST** (`BR-CWP-051`). The screen
    // cannot show a reason it is never sent, and this is what says so out loud.
    const { container } = draw([
      {
        kind: "write_off",
        date: "2026-05-12",
        how: null,
        reference: null,
        receipt_reference: null,
        receipt_available: false,
        applied_to: [],
        returned_by_the_bank: false,
        amount: "84.2000",
        currency: "USD",
        state: "written_off",
        money_type: "write_off",
      },
    ]);
    await screen.findAllByText("Written off");
    expect(container.querySelector("[data-amount='0']")?.textContent).toBe("$84.20");
    expect(container.textContent).toContain("2026-05-12");
    expect(container.textContent).not.toContain("bankruptcy");
    expect(container.textContent).not.toContain("customer_bankruptcy");
    expect(container.querySelector("[data-reason]")).toBeNull();
  });

  it("B14 rule 31 — no database id reaches the page", async () => {
    const { container } = draw([REVERSAL, PAYMENT]);
    await deskFinds(container, "Bounced");
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  });

  it("the CSV control is rendered, disabled, with its reason — and the RECEIPT is not held at all", async () => {
    // ⚠ An ABSENT control makes a customer ring up to ask where it went. A held
    // one answers itself — in six words (B14 rule 33).
    // ⚠ **AMENDED TWICE, AND THE SECOND TIME THE HOLD WENT AWAY.**
    // `DEF-CWP-4000` moved CSV into the page head, where the drawing puts it;
    // `CR-085` `CPB-20` RELEASED the receipt, which was held over a document
    // this product already kept. The footer row that carried it is gone with
    // it — a per-payment action never belonged in a per-page slot — so the
    // assertion is now that nothing is held down there at all.
    const { container } = draw([PAYMENT]);
    await deskFinds(container, "Reversed");
    expect(container.querySelector("[data-money-held]")).toBeNull();
    expect(screen.queryByText("Receipts arrive later this year")).not.toBeInTheDocument();
    // CSV is still honestly held: nothing in this product writes a customer CSV.
    const headActions = container.querySelector(".page-header-actions");
    expect(headActions?.textContent).toContain("Download CSV");
    expect(headActions?.querySelector("button")?.hasAttribute("disabled")).toBe(true);
  });

  it("a customer with no payments gets a sentence, never a table of dashes", async () => {
    const { container } = draw([]);
    expect(await screen.findByText("Your payments will appear here.")).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
    expect(container.querySelector("[data-money-held]")).toBeNull();
  });

  /**
   * `CR-085` — **THE PHONE COULD NOT SEE THE AMOUNT OR THE STATUS.**
   *
   * ⚠ **MEASURED, NOT INFERRED.** At 390 the table's own content is 637px wide
   * inside a 316px column, so `AMOUNT`, `STATUS` and the row action all sit off
   * the right-hand edge behind a sideways scroll a customer has no reason to
   * look for. *Did my payment go through* is the entire question this screen
   * exists to answer, and on a phone — the device most customers open it on —
   * neither half of the answer was on screen. `overflow-x-auto` (which
   * `MiniTable` correctly has) stops the PAGE moving; it does not make a figure
   * readable.
   *
   * The wireframe answers it the same way its bills frame does: the phone gets
   * a card per payment — amount, date and method, status, and which bill it
   * went against — and the desk keeps the table. One source for both, so
   * nothing can drift.
   */
  it("CR-085 — a phone gets a card per payment, with the figure and the status", async () => {
    const { container } = draw([REVERSAL, PAYMENT]);
    await screen.findByRole("table");

    const cards = [...container.querySelectorAll("[data-money-card]")];
    expect(cards).toHaveLength(2);

    // ⚠ **THE TWO THINGS THAT WERE OFF THE EDGE**, on the card, per row — and
    // the sign is still the server's, with no absolute value taken anywhere.
    expect(container.querySelector("[data-card-amount='0']")?.textContent).toBe("-$129.02");
    expect(container.querySelector("[data-card-amount='1']")?.textContent).toBe("$129.02");
    expect(cards[0].textContent).toContain("Bounced");
    expect(cards[1].textContent).toContain("Reversed");

    // ⚠ **AND THE SECOND HALF OF THE QUESTION** — *which bill did it go
    // against* — which is what a landlord and a disputed account need.
    expect(cards[0].textContent).toContain("Returned by the bank");
    expect(cards[1].textContent).toContain("BL-2606-0147");

    // The reversal is red on the card too. A phone reader must not skim past
    // money the bank took back (`BR-CWP-061`).
    expect(cards[0].querySelectorAll("[data-reversal]").length).toBeGreaterThanOrEqual(2);
    expect(cards[1].querySelectorAll("[data-reversal]")).toHaveLength(0);
  });

  it("says so when the read fails, rather than drawing an empty table", async () => {
    readMoney = async () => {
      throw new Error("read failed");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/payments"]}>
        <PaymentsView />
      </MemoryRouter>,
    );
    expect(await screen.findByText("We could not read your payments.")).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` `CPB-20` — THE RECEIPT, WHERE A PERSON LOOKS FOR IT
  //
  // This screen carried ONE held button under the table reading *"Receipts
  // arrive later this year"* — over a document `notifications` freezes at
  // dispatch and `tenancy.document_store` has been keeping all along. Even had
  // it worked, a single per-page control could not have said WHICH receipt.
  // ═══════════════════════════════════════════════════════════════════════

  it("CPB-20 · the desk row serves the receipt, by the PAYMENT number", async () => {
    const { container } = draw([PAYMENT]);
    await deskFinds(container, "Cheque");
    const table = container.querySelector("[data-list='CWP-041']") as HTMLElement;
    const receipt = table.querySelector("a[aria-label='Download this receipt']");
    // ⚠ **`PMT-2607-0031`, NOT `10174`.** `reference` on this row is the cheque
    // number the customer wrote; the receipt is filed under the payment's own
    // number. Addressing it off `reference` would answer *not found* on every
    // cheque — the row a person most often wants a receipt for.
    expect(receipt?.getAttribute("href")).toBe(
      "/api/pine-hill/portal/documents/PMT-2607-0031/file",
    );
    expect(screen.queryByText("Receipts arrive later this year")).not.toBeInTheDocument();
  });

  it("CPB-20 · and so does the PHONE card, which is the half that fell off before", async () => {
    // Hard-won law 2's mirror, one layer down: adding a control to the desk
    // table alone would be wave F's defect wearing the opposite face.
    const { container } = draw([PAYMENT]);
    await deskFinds(container, "Cheque");
    const card = container.querySelector("[data-money-card='0']") as HTMLElement;
    expect(card.querySelector("[data-card-receipt='0']")?.getAttribute("href")).toBe(
      "/api/pine-hill/portal/documents/PMT-2607-0031/file",
    );
  });

  it("CPB-20 · a payment whose receipt we did NOT keep is held, not offered", async () => {
    // ⚠ **THE STATE A BROWSER FOUND AND NO FIXTURE HAD.** Every test fixture
    // that gave a payment a number also gave it a kept copy, so the two facts
    // could not disagree in the suite — and on the live deployment they
    // disagree on every held dispatch. The first draft drew a live download
    // over a receipt the server then refused.
    const { container } = draw([{ ...PAYMENT, receipt_available: false }]);
    await deskFinds(container, "Cheque");
    const table = container.querySelector("[data-list='CWP-041']") as HTMLElement;
    expect(table.querySelector("a[aria-label='Download this receipt']")).toBeNull();
    const held = table.querySelector("button[aria-label='Download this receipt']");
    expect(held).toBeDisabled();
    expect(held?.getAttribute("title")).toBe("We kept no copy of this.");
    // And the phone card drops it rather than drawing a link that fails.
    expect(container.querySelector("[data-card-receipt='0']")).toBeNull();
  });

  it("CPB-20 · a reversal, a credit and a write-off offer NO receipt at all", async () => {
    // ⚠ **ABSENT, NOT REFUSED.** None of the three mints a payment number or
    // posts a receipt, so a control there could never once be used — and
    // `BR-CWP-056`'s *disable it with its reason* is for a control that MIGHT
    // work, never for one that cannot exist.
    const { container } = draw([
      REVERSAL,
      {
        kind: "write_off",
        date: "2026-05-12",
        how: null,
        reference: null,
        receipt_reference: null,
        receipt_available: false,
        applied_to: [],
        returned_by_the_bank: false,
        amount: "84.2000",
        currency: "USD",
        state: "written_off",
        money_type: "write_off",
      },
    ]);
    await deskFinds(container, "Bounced");
    expect(container.querySelectorAll("[aria-label='Download this receipt']")).toHaveLength(0);
  });

  it("DEF-CWP-4705 · a split payment's *See what this paid* is refused for the RIGHT reason", async () => {
    // ⚠ **THE REFUSAL WAS TRUE ENGLISH AND A FALSE STATEMENT.** This control
    // opens the BILL a payment settled, and it read *"No receipt for this
    // row."* — a sentence about a different document, printed beside a receipt
    // icon that on this very row is a live download. `G32` passed it every
    // time, because `G32` asks whether a refusal RESOLVES and never whether it
    // is TRUE; the control's own comment stated the correct reason in prose
    // three lines above the key that contradicted it.
    const { container } = draw([
      { ...PAYMENT, applied_to: ["BL-2606-0147", "BL-2607-0139"] },
    ]);
    await deskFinds(container, "Cheque");
    const table = container.querySelector("[data-list='CWP-041']") as HTMLElement;
    const view = table.querySelector("button[aria-label='See what this paid']");
    expect(view).toBeDisabled();
    expect(view?.getAttribute("title")).toBe("No single bill to open.");
    expect(view?.getAttribute("title")).not.toBe("No receipt for this row.");
    // And the receipt beside it is still a live download, which is exactly why
    // the old sentence was false rather than merely vague.
    expect(
      table.querySelector("a[aria-label='Download this receipt']")?.getAttribute("href"),
    ).toBe("/api/pine-hill/portal/documents/PMT-2607-0031/file");
  });

  it("DEF-CWP-4705 · and a payment that settled exactly one bill still opens it", async () => {
    // The negative case, so the fix cannot be "refuse everything".
    const { container } = draw([PAYMENT]);
    await deskFinds(container, "Cheque");
    const table = container.querySelector("[data-list='CWP-041']") as HTMLElement;
    const view = table.querySelector("a[aria-label='See what this paid']");
    expect(view?.getAttribute("href")).toBe("/pine-hill/portal/bills/BL-2606-0147");
  });

  /**
   * `DEF-CWP-4879` — **the search box and the filter did not exist at 390.**
   *
   * They lived inside `PortalListTable`, which this screen renders inside a
   * `max-md:hidden` wrapper — so on a phone they were not hidden, they were
   * never in the DOM. Measured in a browser on 2026-09-11: zero visible inputs
   * and zero segment buttons in `main` at 390, against one of each at 1280.
   * *Did my payment go through* is the whole question this screen answers, and
   * the phone half was the half that could not look anything up.
   *
   * ⚠ **jsdom APPLIES NO MEDIA QUERY, SO NO UNIT TEST CAN SEE A WIDTH** — a
   * case that asserted *the toolbar is visible at 390* would be asserting
   * nothing at all (hard-won law 7: ask what would make this check pass
   * wrongly). What a unit test CAN see is the structural fact underneath: the
   * toolbar is not inside the desktop-only half. The width itself is proved in
   * a browser at 390, and that proof is recorded in the lane's conformance file.
   */
  describe("DEF-CWP-4879 · the toolbar serves both widths", () => {
    it("draws the search box and the year filter OUTSIDE the desktop-only half", async () => {
      const { container } = draw([PAYMENT]);
      await screen.findByTestId("money");

      const toolbar = container.querySelector("[data-money-toolbar]");
      expect(toolbar).not.toBeNull();
      const deskOnly = container.querySelector("[data-money-table]") as HTMLElement;
      expect(deskOnly).not.toBeNull();
      // ⚠ **THE ASSERTION THAT COULD NOT PASS BEFORE THE FIX.**
      expect(deskOnly.contains(toolbar)).toBe(false);
      // And the table no longer draws a second one of its own.
      expect(container.querySelectorAll("[data-list-toolbar]")).toHaveLength(0);
      expect(within(toolbar as HTMLElement).getByRole("searchbox")).toBeInTheDocument();
      expect(toolbar?.querySelector("[data-segmented='CWP-041-year']")).not.toBeNull();
    });

    it("one search narrows BOTH halves, because both read one filtered list", async () => {
      const user = userEvent.setup();
      const other: PortalMoneyRow = { ...PAYMENT, reference: "20999", state: "received" };
      const { container } = draw([PAYMENT, other]);
      await screen.findByTestId("money");
      expect(container.querySelectorAll("[data-money-card]")).toHaveLength(2);

      await user.type(container.querySelector("#money-search") as HTMLElement, "20999");

      await waitFor(() =>
        expect(container.querySelectorAll("[data-money-card]")).toHaveLength(1),
      );
      // The desk table narrowed to the same one row.
      const deskOnly = container.querySelector("[data-money-table]") as HTMLElement;
      expect(deskOnly.querySelectorAll("tbody tr")).toHaveLength(1);
      // ⚠ **THE CARD'S INDEX IS ITS PLACE IN THE RESULT SET THE SERVER
      // ANSWERED — AMENDED 2026-09-19 (`DEF-CWP-5747`).** It used to be the
      // row's place in the whole UNFILTERED array, on the reasoning that an
      // attribute renumbering under a filter is a test that silently changes
      // what it asserts. The reasoning holds; the reference point moved,
      // because with the search on the server there is no unfiltered array in
      // the browser to count from. The hook is stable across a PAGE TURN, which
      // is what it is for, and the one matching row is the first of its result
      // set.
      expect(container.querySelector("[data-money-card='0']")).not.toBeNull();
    });

    it("a search that matches nothing says SO, and not *you have no payments*", async () => {
      const user = userEvent.setup();
      const { container } = draw([PAYMENT]);
      await screen.findByTestId("money");

      await user.type(container.querySelector("#money-search") as HTMLElement, "zzzz");

      // R-22 as the PO ruled it — three states, three sentences. *You have not
      // made a payment yet* to somebody who has made one and mistyped is the
      // small lie that makes a person ring.
      await waitFor(() => expect(container.querySelector("[data-money-nomatch]")).not.toBeNull());
      expect(container.querySelector("[data-money-empty]")).toBeNull();
      expect(container.querySelectorAll("[data-money-card]")).toHaveLength(0);
    });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CWP-5747` — THE PAGE AND THE SORT ARE THE SERVER'S, AND SO IS THE
// SEARCH THIS SCREEN'S OWN TOOLBAR FEEDS.
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CWP-5747 · the payments list asks the server for its page", () => {
  afterEach(() => {
    cleanup();
    asked = [];
  });

  it("asks for page 1 of fifty on the first render", async () => {
    draw([PAYMENT]);
    await screen.findByTestId("money");
    expect(asked[0].page).toBe(1);
    expect(asked[0].per).toBe(50);
  });

  it("sends what was typed as `q`, from the toolbar that serves BOTH widths", async () => {
    // ⚠ The box is the SCREEN's and not the table's (`DEF-CWP-4879`): the
    // table lives inside `max-md:hidden`, so a box drawn by the table is not
    // in the DOM on a phone at all. It feeds the server now instead of
    // filtering an array, and it is still one needle for both halves.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { container } = draw([PAYMENT]);
      await screen.findByTestId("money");
      fireEvent.change(container.querySelector("#money-search") as HTMLElement, {
        target: { value: "20999" },
      });
      await vi.advanceTimersByTimeAsync(400);
      expect(asked[asked.length - 1].q).toBe("20999");
    } finally {
      vi.useRealTimers();
    }
  });

  it("the year pair stays its own parameter and is not a chip", async () => {
    // ⚠ It is applied BEFORE `BR-CWP-061`'s bounce pairing, so it cannot be an
    // `f.` filter narrowing rows that have already been paired.
    const { container } = draw([PAYMENT]);
    await screen.findByTestId("money");
    fireEvent.click(container.querySelector("[data-segment='year']") as Element);
    const last = asked[asked.length - 1];
    expect(last.year).toBe(new Date().getFullYear());
    expect(last.filters?.year).toBeUndefined();
  });
});
