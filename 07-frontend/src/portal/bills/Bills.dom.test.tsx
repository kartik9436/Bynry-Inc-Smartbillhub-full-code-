// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-032 (EP-CWP-07) · Screen: CWP-027
// Rules:    BR-CWP-043 (owing and amount are TWO columns; part-paid is a THIRD
//           state) · BR-CWP-042 (the corrected pair, the original naming its
//           replacement) · B14 rule 20 (one table) · rule 31 (no database id
//           on screen) · rule 33 (a refusal is five or six words)
// Cases:    the two columns · the three states · the corrected pair · the bill
//           number as the door to CWP-028 · Pay as the door to CWP-038 (the
//           hold that stood there is expired, DEF-CWP-3954) · the three doors
//           Bills is the only way to · the empty state
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { resolvePortalScreen } from "../routing/screenIds";

import type { PortalBill, PortalBills, PortalListRequest } from "../api/portalClient";

// A plain function, not `vi.fn()` — a recording stand-in notices a rejected
// promise before the screen's own error handling does.
let readBills: () => Promise<PortalBills> = async () => {
  throw new Error("no behaviour set");
};
/** ⚠ **EVERY REQUEST, RECORDED — `DEF-CWP-5747`.** The rows this screen draws
 *  look identical whether the page came from the server or from a browser
 *  holding every bill; what went out on the wire does not. */
let asked: PortalListRequest[] = [];
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getBills: (options: PortalListRequest = {}) => {
      asked.push(options);
      return readBills();
    },
  };
});

/** One payload, with the three whole-set facts the server now serves —
 *  `oldest_on` for the drawing's *since you started* line, `any_owing` for the
 *  *Pay* control, and `populated` to tell *no bills* from *no match*. */
function answer(bills: PortalBill[], over: Partial<PortalBills> = {}): PortalBills {
  const issued = bills.map((bill) => bill.issued_on).filter(Boolean) as string[];
  return {
    bills,
    oldest_on: issued.length === 0 ? null : issued.slice().sort()[0],
    any_owing: bills.some((bill) => Number(bill.owing) > 0),
    populated: bills.length > 0,
    count: bills.length,
    page: 1,
    per: 50,
    ...over,
  };
}

const { BillsView } = await import("./Bills");

const BASE: PortalBill = {
  number: "BL-2608-0141",
  issued_on: "2026-08-26",
  due_on: "2026-09-14",
  total: "142.1800",
  owing: "142.1800",
  currency: "USD",
  period_start: "2026-07-27",
  period_end: "2026-08-26",
  state: "due",
  // `DEF-CWP-3980` — the server's own countdown, computed against the same
  // `today` that produced `state`.
  due_in_days: 12,
  usage: [{ quantity_display: "4820", unit: "gal" }],
  replaced_by: null,
  replaces: null,
};

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, AND THAT IS NOT TIDINESS**
 * (CLAUDE.md hard-won law 2, `DEF-CWP-3925`). This helper used to render
 * `BillsView` bare inside a `MemoryRouter` with no `/:tenant/portal` route, so
 * `useParams().tenant` was `undefined` and every address the screen built came
 * out `//portal/…` — a protocol-relative URL to another host, which reads as a
 * perfectly good string to `toContain`. **A fixture that cannot tell a working
 * link from a broken one cannot be used to check a door**, and this file now
 * checks three of them.
 */
function draw(bills: PortalBill[]) {
  readBills = async () => answer(bills);
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/bills"]}>
      <Routes>
        <Route path="/:tenant/portal/bills" element={<BillsView />} />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * **THE DESKTOP TABLE HALF OF THE SCREEN.**
 *
 * ⚠ **THIS SCREEN NOW DRAWS EVERY BILL TWICE — ONCE AS A TABLE ROW AND ONCE AS
 * A PHONE CARD — AND ONLY ONE OF THEM IS EVER VISIBLE.** The switch is CSS
 * (`md:hidden` / `max-md:hidden`), and jsdom applies no CSS, so an unscoped
 * `screen.getByText("Part paid")` finds two elements and fails. Scoping to the
 * table is not a workaround: every assertion below is ABOUT the table — its
 * columns, its chips, its muted row — and saying so is what stops the same
 * query silently starting to answer with the card instead.
 */
function desk(container: HTMLElement) {
  return within(container.querySelector("[data-list='CWP-027']") as HTMLElement);
}

/** `desk`, but it waits for the list to arrive first — the table is the last
 *  thing on the page to exist, so scoping to it before the read resolves gets a
 *  `null` container rather than a miss. */
async function deskFinds(container: HTMLElement, text: string) {
  await screen.findByRole("table");
  return desk(container).getByText(text);
}

afterEach(cleanup);

describe("CWP-027 · bills (US-CWP-032)", () => {
  it("shows what the bill CHARGED and what it still OWES, in one AMOUNT cell", async () => {
    // ⚠ **`BR-CWP-043` ASKS FOR TWO COLUMNS AND THE PO'S FOUR-COLUMN RULING OF
    // 2026-09-11 LEAVES ROOM FOR ONE.** Both figures are still on the screen,
    // both are still the server's, and the screen still does no arithmetic to
    // get either — what changed is that `owing` is the second line of the
    // AMOUNT cell instead of a column of its own. The collision between the
    // rule and the ruling is recorded in `Bills.tsx` and in
    // `conformance/CR-085-lane5-04-step2-after.md`; this test pins the half
    // that must not be lost either way: **a part-paid bill shows both.**
    const { container } = draw([{ ...BASE, owing: "102.1800", state: "part_paid" }]);
    await deskFinds(container, "Part paid");
    expect(container.querySelector("[data-amount='BL-2608-0141']")?.textContent).toBe("$142.18");
    expect(container.querySelector("[data-owing='BL-2608-0141']")?.textContent).toContain("$102.18");
  });

  it("draws NO owing line where the bill is wholly paid or wholly due", async () => {
    // The second line is the part-paid case and only it. Repeating the amount
    // under itself on a due bill, or printing `$0.00 still owing` on a paid
    // one, is noise on the column a customer scans fastest.
    const { container } = draw([
      { ...BASE, owing: "142.1800", state: "due" },
      { ...BASE, number: "BL-2607-0139", owing: "0.0000", state: "paid" },
    ]);
    await deskFinds(container, "BL-2608-0141");
    expect(container.querySelector("[data-owing='BL-2608-0141']")).toBeNull();
    expect(container.querySelector("[data-owing='BL-2607-0139']")).toBeNull();
  });

  it("PO 2026-09-11 — the table is the blueprint's FOUR columns and no more", async () => {
    // ⚠ **THE RULING, PINNED BY ADDRESS RATHER THAN BY EYE.** Three drawings
    // covered this screen and disagreed: the 8 September blueprint draws four
    // columns, the 3 September PNG draws eight, the build had nine. The PO
    // ruled the blueprint is the design. A test that only asserted the four
    // PRESENT would pass on all nine, so this one counts the header row — the
    // four plus the row-action column the drawing ends every row with.
    const { container } = draw([BASE]);
    await deskFinds(container, "BL-2608-0141");
    const heads = [...container.querySelectorAll("thead th")].map((th) =>
      (th.textContent ?? "").replace(/[⇅↑↓]/g, "").trim(),
    );
    expect(heads).toHaveLength(5);
    expect(heads.slice(0, 4)).toEqual(["Bill", "Covers", "Amount", "Status"]);
    // The four the ruling takes OUT, by the handles they rendered under.
    expect(container.querySelector("[data-cell='issued']")).toBeNull();
    expect(container.querySelector("[data-cell='due']")).toBeNull();
    expect(container.querySelector("[data-cell='usage']")).toBeNull();
    expect(container.querySelector("[data-cell='owing']")).toBeNull();
  });

  it("part paid is its OWN chip — not a shade of paid or due", async () => {
    const { container } = draw([
      { ...BASE, owing: "102.1800", state: "part_paid" },
      { ...BASE, number: "BL-2607-0139", owing: "0.0000", state: "paid" },
      { ...BASE, number: "BL-2606-0111", state: "overdue", due_in_days: -3 },
    ]);
    await deskFinds(container, "Part paid");
    expect(desk(container).getByText("Paid")).toBeTruthy();
    // ⚠ `DEF-CWP-3980` — the chip COUNTS, so an overdue bill says how far.
    expect(desk(container).getByText("Overdue by 3 days")).toBeTruthy();
    expect(container.querySelectorAll("tbody tr")).toHaveLength(3);
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `DEF-CWP-3980` — the columns the payload was already carrying, and the
  // status word that would not count.
  // ═══════════════════════════════════════════════════════════════════════

  it("DEF-CWP-3980 — the row says WHICH MONTH the bill covers", async () => {
    // ⚠ **THE PAYLOAD WAS ALWAYS RIGHT AND THE SCREEN WAS THINNER THAN IT.**
    // `period_start` and `period_end` have come down on every row since this
    // list was built and nothing drew them, so a customer looking for their
    // August bill had to open bills one at a time to find out which month
    // each covered. A test asserting the columns the screen HAS passes
    // forever — which is why this one asserts the CELL, by content.
    const { container } = draw([BASE]);
    await deskFinds(container, "BL-2608-0141");
    // The column is `covers` now — the blueprint's own heading word (PO
    // 2026-09-11). Same two dates, same cell, one heading changed.
    const period = container.querySelector("[data-cell='covers']");
    expect(period?.textContent).toContain("2026");
    // Both ends, not just the one — a period is two dates.
    expect(period?.textContent).toMatch(/7.*8|Jul.*Aug/);
  });

  it("PO 2026-09-11 — USAGE left this list, and NO bare quantity is left behind", async () => {
    // ⚠ **THIS TEST USED TO ASSERT THE CELL AND NOW ASSERTS ITS ABSENCE, AND
    // THE REASON IS A RULING RATHER THAN A REGRESSION.** `DEF-CWP-3980` added
    // a `USAGE` column reading `4820 gal · 31 therm`; the blueprint's four
    // columns do not include one, and the PO ruled on 2026-09-11 that the
    // blueprint is the design. What the old test actually protected is hard
    // rule 3 — *a quantity NEVER appears without its unit* — and that is what
    // is kept here: with two units on the payload, this screen now prints
    // neither quantity anywhere, which is the only other way to obey the rule.
    // The figures are still drawn WITH their units one screen in, on
    // `CWP-028`, where `BillDetail.dom.test.tsx` pins them.
    const { container } = draw([
      {
        ...BASE,
        usage: [
          { quantity_display: "4820", unit: "gal" },
          { quantity_display: "31", unit: "therm" },
        ],
      },
    ]);
    await deskFinds(container, "BL-2608-0141");
    expect(container.querySelector("[data-bill-usage='BL-2608-0141']")).toBeNull();
    expect(container.querySelector("[data-cell='usage']")).toBeNull();
    // And not smuggled into another cell: neither bare figure is on the page.
    const table = container.querySelector("[data-list='CWP-027']")?.textContent ?? "";
    expect(table).not.toContain("4820");
    expect(table).not.toContain("31 therm");
  });

  it("DEF-CWP-3980 — the status chip COUNTS DOWN, and today is a word", async () => {
    // ⚠ **THE COUNT IS THE SERVER'S.** These three rows differ only in
    // `due_in_days`, which is what a browser subtracting its own clock could
    // not be trusted to produce: a device a time zone east of the utility
    // would draw *Due in 1 day* inside a chip the server called `overdue`.
    const { container } = draw([
      { ...BASE, due_in_days: 12 },
      { ...BASE, number: "BL-2608-0142", due_in_days: 0 },
      { ...BASE, number: "BL-2608-0143", due_in_days: 1 },
    ]);
    await deskFinds(container, "Due in 12 days");
    expect(desk(container).getByText("Due today")).toBeTruthy();
    // The singular form, from the catalogue's own `_one` — never "1 days".
    expect(desk(container).getByText("Due in 1 day")).toBeTruthy();
    expect(container.querySelectorAll("tbody tr")).toHaveLength(3);
  });

  it("DEF-CWP-3980 — a bill with no due date keeps the plain word", async () => {
    // `null` is a real answer, and inventing a countdown from a date that is
    // not there would be a figure with nothing behind it.
    const { container } = draw([{ ...BASE, due_on: null, due_in_days: null }]);
    await deskFinds(container, "BL-2608-0141");
    // Asserted on the CHIP, not by text — `Due` is also this table's own
    // column heading, and a `findByText` would answer with the header.
    expect(container.querySelector("[data-chip='state-BL-2608-0141']")?.textContent).toBe("Due");
  });

  it("BR-CWP-042 — the corrected pair are both listed and name each other", async () => {
    const { container } = draw([
      {
        ...BASE,
        number: "BL-2606-0137",
        total: "154.9000",
        owing: "0.0000",
        state: "corrected",
        replaced_by: "BL-2606-0147",
      },
      { ...BASE, number: "BL-2606-0147", total: "129.0200", replaces: "BL-2606-0137" },
    ]);
    await deskFinds(container, "Corrected");
    expect(container.querySelector("[data-replaced-by='BL-2606-0147']")?.textContent).toContain(
      "Replaced by BL-2606-0147",
    );
    expect(container.querySelector("[data-replaces='BL-2606-0137']")).toBeTruthy();
    // ⚠ The original is GREYED but present — a customer with a bank statement
    // has to be able to reconcile it against something.
    expect(container.querySelector("tr[data-muted='true']")).toBeTruthy();
  });

  // ═══════════════════════════════════════════════════════════════════════
  // The drawing's PHONE frame — a stack of cards rather than a table nobody
  // can read at 390 wide.
  // ═══════════════════════════════════════════════════════════════════════

  it("a phone gets one CARD per bill, carrying the month, the amount and the status", async () => {
    // ⚠ **THE TABLE IS 805px OF CONTENT IN A 316px COLUMN AT 390 WIDE**, so
    // `Amount`, `Owing` and `Status` all sat off the right-hand edge behind a
    // sideways scroll — a bill list that could not say what a bill COST, on
    // the device most customers open it on. `MiniTable`'s `overflow-x-auto`
    // stops the PAGE moving and does nothing about the figures.
    // ⚠ The MONTH is the card's heading, which is the drawing's own reasoning:
    // *"customers say 'my August bill' and mean the one that arrived in
    // August"*. The number is still drawn under it (B14 rule 31) and is still
    // where the card leads.
    const { container } = draw([{ ...BASE, owing: "102.1800", state: "part_paid" }]);
    await screen.findByRole("table");
    const card = container.querySelector("[data-bill-card='BL-2608-0141']") as HTMLElement;
    expect(card).not.toBeNull();
    expect(within(card).getByText("Aug 2026")).toBeTruthy();
    expect(within(card).getByText("BL-2608-0141")).toBeTruthy();
    expect(container.querySelector("[data-card-amount='BL-2608-0141']")?.textContent).toBe(
      "$142.18",
    );
    expect(within(card).getByText("Part paid")).toBeTruthy();
    // ⚠ The card is a DOOR, asserted whole — `toContain` passes on
    // `//portal/bills/…`, which points at another host.
    expect(
      container.querySelector("[data-bill-card-link='BL-2608-0141']")?.getAttribute("href"),
    ).toBe("/pine-hill/portal/bills/BL-2608-0141");
  });

  it("the card offers Pay only where something is OWED", async () => {
    const { container } = draw([
      { ...BASE, owing: "102.1800", state: "part_paid" },
      { ...BASE, number: "BL-2607-0139", owing: "0.0000", state: "paid" },
    ]);
    await screen.findByRole("table");
    expect(container.querySelector("[data-card-pay='BL-2608-0141']")).not.toBeNull();
    // *"Paid rows carry no filled button — nothing to do means nothing to
    // press."*
    expect(container.querySelector("[data-card-pay='BL-2607-0139']")).toBeNull();
  });

  it("Pay is absent from the head when every bill is SETTLED", async () => {
    // ⚠ **THE HEAD'S `Pay` USED TO ASK ONLY WHETHER THERE WERE ANY BILLS**, so
    // a customer whose every bill was paid still met a Pay control on the one
    // screen that exists to tell them they owe nothing. The empty-list case
    // was already pinned; this is the same rule one step further in, and it is
    // the drawing's — *"Pay on the unpaid bill only."*
    const { container } = draw([
      { ...BASE, owing: "0.0000", state: "paid" },
      { ...BASE, number: "BL-2607-0139", owing: "0.0000", state: "paid" },
    ]);
    await screen.findByRole("table");
    expect(container.querySelector("[data-bills-pay]")).toBeNull();
  });

  it("the head says how far back the list goes, and how many bills that is", async () => {
    // The drawing's own sentence — *"Every bill since you started, Jun 2026 ·
    // 3 bills"* — which answers *is this all of them* before a customer counts
    // the rows. The month is the OLDEST bill's, so it is the earliest row
    // rather than the first one the server happened to send.
    const { container } = draw([
      { ...BASE, number: "BL-2608-0141", issued_on: "2026-08-26" },
      { ...BASE, number: "BL-2606-0111", issued_on: "2026-06-24" },
    ]);
    await screen.findByRole("table");
    const since = container.querySelector("[data-bills-since]");
    expect(since?.getAttribute("data-bills-since")).toBe("2026-06-24");
    expect(since?.textContent).toBe("Every bill since you started, Jun 2026 · 2 bills");
  });

  it("the bill number is a LINK to that bill, and the link text is the number", async () => {
    // ⚠ **THIS IS `DEF-CWP-3954`'s KEYSTONE.** The number was bold text, so a
    // customer could read a list of their bills and could not open one — and
    // five screens hang off this one anchor (`CWP-028`, and from it
    // `CWP-029`, `CWP-030`, `CWP-055` and `CWP-054`).
    // ⚠ The href is asserted WHOLE. `toContain("/bills/BL-2608-0141")` passes
    // on `//portal/bills/BL-2608-0141`, which points at another host.
    const { container } = draw([BASE]);
    await vi.waitFor(() =>
      expect(container.querySelector("[data-chip='state-BL-2608-0141']")).toBeTruthy(),
    );
    const link = container.querySelector("[data-bill-link='BL-2608-0141']");
    expect(link?.getAttribute("href")).toBe("/pine-hill/portal/bills/BL-2608-0141");
    // ⚠ **BY ADDRESS *AND* BY THE SCREEN ID IT OPENS**, resolved through the
    // front end's own register — an address that stopped being CWP-028 is a
    // door that has quietly moved.
    expect(resolvePortalScreen("/bills/BL-2608-0141")?.id).toBe("CWP-028");
    // B14 rule 31 — the NUMBER is what a person reads, never a row id.
    expect(link?.textContent).toBe("BL-2608-0141");
  });

  it("Pay opens CWP-038, and the hold that stood over it is gone", async () => {
    // ⚠ **THE TEST THAT USED TO BE HERE PINNED A HOLD** — it asserted a
    // disabled button reading *Online payment arrives later this year*, and
    // it went on passing for every day after `CWP-038` *Pay now* landed. That
    // is hard-won law 2's mirror in its most durable form: *a hold with a test
    // that pins it and no test that expires it is a promise nobody is
    // keeping*. This is the test that expires it — it names the DESTINATION by
    // address, so the day anything closes that door again the suite says so.
    // The refusal about card rails has not been lost: `CWP-038` serves it per
    // account, in the server's words.
    const { container } = draw([BASE]);
    await vi.waitFor(() =>
      expect(container.querySelector("[data-chip='state-BL-2608-0141']")).toBeTruthy(),
    );
    expect(container.querySelector("[data-bills-pay] button[disabled]")).toBeNull();
    const pay = container.querySelector("[data-bills-pay] a");
    expect(pay?.getAttribute("href")).toBe("/pine-hill/portal/pay-now");
    expect(resolvePortalScreen("/pay-now")?.id).toBe("CWP-038");
    expect(container.textContent).not.toContain("Online payment arrives later this year");
  });

  it("the three screens Bills is the door to are all pointed at, by address", async () => {
    // `CWP-031` documents · `CWP-057` the overdue ladder · `CWP-056` help
    // paying. All three were shipped and unreachable (`DEF-CWP-3954`), and all
    // three are drawn whether or not this customer has a bill.
    const { container } = draw([]);
    await screen.findByText("Your first bill will appear here.");
    const doors = [...container.querySelectorAll("[data-where-next='bills'] a")].map((a) =>
      a.getAttribute("href"),
    );
    expect(doors).toEqual([
      "/pine-hill/portal/documents",
      "/pine-hill/portal/overdue",
      "/pine-hill/portal/help-paying",
    ]);
    // Each by the SCREEN it opens as well, so a moved address is named.
    expect(["/documents", "/overdue", "/help-paying"].map((p) => resolvePortalScreen(p)?.id)).toEqual([
      "CWP-031",
      "CWP-057",
      "CWP-056",
    ]);
  });

  it("B14 rule 31 — no database id reaches the page", async () => {
    const { container } = draw([BASE]);
    await vi.waitFor(() =>
      expect(container.querySelector("[data-chip='state-BL-2608-0141']")).toBeTruthy(),
    );
    expect(container.textContent).toContain("BL-2608-0141");
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  });

  it("a customer with no bills gets a sentence, never a table of dashes", async () => {
    const { container } = draw([]);
    expect(await screen.findByText("Your first bill will appear here.")).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
    // …and no Pay control either: there is nothing to pay.
    expect(container.querySelector("[data-bills-pay]")).toBeNull();
  });

  it("says so when the read fails, rather than drawing an empty table", async () => {
    readBills = async () => {
      throw new Error("read failed");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/bills"]}>
        <BillsView />
      </MemoryRouter>,
    );
    expect(await screen.findByText("We could not read your bills.")).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
  });


  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` step 2 — the phone's missing door, and R-10/R-22 on the three
  // states.
  // ═══════════════════════════════════════════════════════════════════════

  it("DEF-CWP-4864 — the PRINTED BILL has a door on a phone, not only on a desk", async () => {
    // ⚠ **THE TABLE IS `display:none` AT 390, AND THE ROW'S `↓ PDF` ICON WAS
    // INSIDE IT.** So the one screen that exists precisely so a customer can
    // send the real document to a landlord or an accountant had **no door
    // anywhere on a phone** — the width most customers open the portal on. The
    // card always linked the MONTH to the bill; what was missing was the
    // printed one.
    // ⚠ **A DOOR IS ASSERTED BY ADDRESS, NEVER BY LABEL** (hard-won law 2's
    // second half): `//portal/…` reads as a perfectly good string to
    // `toContain`, which is why this fixture mounts under the real path.
    const { container } = draw([BASE]);
    await deskFinds(container, "BL-2608-0141");
    const cards = container.querySelector("[data-bills-cards]") as HTMLElement;
    const printed = cards.querySelector("[data-card-print='BL-2608-0141']");
    expect(printed).not.toBeNull();
    expect(printed?.getAttribute("href")).toBe("/pine-hill/portal/bills/BL-2608-0141/document");
    const whole = cards.querySelector("[data-card-view='BL-2608-0141']");
    expect(whole?.getAttribute("href")).toBe("/pine-hill/portal/bills/BL-2608-0141");
    // ⚠ **WORDS, NOT ICONS.** The blueprint's standard A: every icon in the
    // portal carries its word, *because a phone has no hover* — and 390 is the
    // width where an `aria-label` alone reaches nobody at all.
    expect(printed?.textContent?.trim()).not.toBe("");
    expect(whole?.textContent?.trim()).not.toBe("");
  });

  it("the phone card shows what is still owing on a part-paid bill", async () => {
    // The half of `BR-CWP-043` the four-column ruling leaves room for, drawn
    // the same way on both halves so they cannot disagree about one bill.
    const { container } = draw([{ ...BASE, owing: "102.1800", state: "part_paid" }]);
    await deskFinds(container, "Part paid");
    expect(container.querySelector("[data-card-owing='BL-2608-0141']")?.textContent).toContain(
      "$102.18",
    );
  });

  it("R-10 · a failed read carries the way out beside the message", async () => {
    // PO 2026-09-11: *"the thing they can do about it must be on that same
    // screen, next to the message. Not a page away. Not in a menu."* This was
    // one grey sentence in a card with nothing at all to press — and the
    // drawing asks for both of these by name: *Retry, plus the phone number.*
    readBills = async () => {
      throw new Error("no");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/bills"]}>
        <Routes>
          <Route path="/:tenant/portal/bills" element={<BillsView />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText(/could not read your bills/i);
    const state = container.querySelector("[data-portal-state='failed']");
    expect(state).not.toBeNull();
    // ⚠ **THE WAYS OUT ARE INSIDE THE CARD**, not in the head — that is what
    // *next to the message* means, and a head link would satisfy a looser test.
    expect(state?.querySelector("[data-way-out='retry']")).not.toBeNull();
    expect(state?.querySelector("[data-way-out='help']")?.getAttribute("href")).toBe(
      "/pine-hill/portal/help",
    );
    // The head survives the failure, so the page still says where it is.
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Your bills");
  });

  it("R-22 · loading, empty and failed are three different KINDS", async () => {
    // The PO narrowed the blueprint's *"never the same picture"* to
    // *"differntiate it using text message"* — one card, three sentences. The
    // kind is in the DOM because nothing here can read whether a sentence
    // MEANS empty, and without it the rule cannot be checked at all.
    const empty = draw([]);
    await screen.findByText(/Your first bill will appear here/);
    expect(empty.container.querySelector("[data-portal-state='empty']")).not.toBeNull();
    expect(empty.container.querySelector("[data-portal-state='failed']")).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CWP-5747` — THE PAGE, THE SEARCH, THE CHIPS AND THE SORT ARE THE
// SERVER'S
//
// ⚠ **THESE ASSERT THE REQUEST, NEVER THE ROWS.** The rows this screen draws
// look identical whether the page came from the server or from a browser
// holding every bill the customer has ever had; what goes out on the wire does
// not. A case counting rendered rows was green through the whole life of this
// defect.
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CWP-5747 · the bills list asks the server for its page", () => {
  afterEach(() => {
    cleanup();
    asked = [];
  });

  it("asks for page 1 of fifty on the first render", async () => {
    draw([BASE]);
    await screen.findAllByText("BL-2608-0141");
    expect(asked[0].page).toBe(1);
    expect(asked[0].per).toBe(50);
  });

  it("sends a typed BILL NUMBER as `q` and goes back to page 1", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      draw([BASE]);
      const box = await screen.findByPlaceholderText(/search/i);
      fireEvent.change(box, { target: { value: "BL-2606" } });
      await vi.advanceTimersByTimeAsync(400);
      const last = asked[asked.length - 1];
      expect(last.q).toBe("BL-2606");
      expect(last.page).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("turns a typed MONTH NAME into the code the server stores", async () => {
    // ⚠ **B14 RULE 35, IN THE ONE PLACE IT BITES A SEARCH.** `BILL` prints
    // *Aug 2026* in the READER'S language and the server stores `2026-08-26`;
    // a server matching *August* would have to own eleven catalogues. So the
    // screen turns the word it drew back into `f.month=08` — and *aug 2026*
    // resolves both halves.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      draw([BASE]);
      const box = await screen.findByPlaceholderText(/search/i);
      fireEvent.change(box, { target: { value: "aug 2026" } });
      await vi.advanceTimersByTimeAsync(400);
      const last = asked[asked.length - 1];
      expect(last.filters?.month).toBe("08");
      expect(last.filters?.year).toBe("2026");
      // Nothing is left over for the server to match as text.
      expect(last.q).toBe("");
    } finally {
      vi.useRealTimers();
    }
  });

  it("sends the chip as a filter rather than narrowing what arrived", async () => {
    draw([BASE]);
    await screen.findAllByText("BL-2608-0141");
    const unpaid = document.querySelector("[data-segment='unpaid']") as Element;
    fireEvent.click(unpaid);
    expect(asked[asked.length - 1].filters?.state).toBe("unpaid");
  });

  it("the roll-up counts the SERVER's total and not the rows on screen", async () => {
    readBills = async () => answer([BASE], { count: 120, oldest_on: "2016-01-04" });
    render(
      <MemoryRouter initialEntries={["/pine-hill/portal/bills"]}>
        <Routes>
          <Route path="/:tenant/portal/bills" element={<BillsView />} />
        </Routes>
      </MemoryRouter>,
    );
    // ⚠ The drawing's sentence is *"Every bill since you started, Jun 2026 · 3
    // bills"*. Counted off a page it would read *· 50 bills* on page 1 of
    // eleven years, and name the wrong month.
    const since = await screen.findAllByText(/120/);
    expect(since.length).toBeGreaterThan(0);
  });

  it("keeps the Pay control on a page that holds no unpaid bill", async () => {
    // ⚠ **`any_owing` IS THE SERVER'S ANSWER OVER THE WHOLE SET.** Counted off
    // the page, a customer whose only unpaid bill is on page 2 would find the
    // Pay control simply missing — a refusal that is false, which is hard-won
    // law 2's mirror wearing a page number.
    const settled = { ...BASE, owing: "0.0000" };
    readBills = async () => answer([settled], { any_owing: true });
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/bills"]}>
        <Routes>
          <Route path="/:tenant/portal/bills" element={<BillsView />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findAllByText("BL-2608-0141");
    expect(container.querySelector("[data-bills-pay]")).not.toBeNull();
  });

  it("a search that matches nothing does NOT say *you have no bills*", async () => {
    readBills = async () => answer([], { populated: true, count: 0 });
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/bills"]}>
        <Routes>
          <Route path="/:tenant/portal/bills" element={<BillsView />} />
        </Routes>
      </MemoryRouter>,
    );
    // ⚠ **`count: 0` AND `populated: true` ARE THE SEARCH-MATCHED-NOTHING
    // CASE.** Answering it with the empty state would tell a customer of
    // eleven months that they have never been billed.
    await screen.findByTestId("bills");
    expect(container.querySelector("[data-portal-state='empty']")).toBeNull();
  });
});
