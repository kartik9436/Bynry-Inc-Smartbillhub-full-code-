// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-043 (EP-CWP-08) · Screen: CWP-037
// Rules:    BR-CWP-073 (equipment is what an unmeasured service is billed on) ·
//           BR-CWP-093 (an empty state, never a blank table) · B14 rule 31
//           (shown by SERIAL, never by a database id) · BR-AST-007 (the test
//           cadence is DERIVED)
// Defects:  DEF-CWP-3991 (both meters read `Meter`) · DEF-CWP-3992 (`STATUS`
//           printed the stored label `Installed/Active`) · DEF-CWP-3995 (WHERE
//           dashes because no seeder writes `location_note`)
// Cases:    three items · the backflow device's TEST DUE · every identifier a
//           serial · the empty state · each row NAMED for what it is · the
//           state word from the CLASS · INSTALLED at month density · the page
//           head and its live door out
// CR-085:   s52 — **BARE REFERENCE NUMBERS, NOT A DETAIL RECORD.** Product
//           Owner, verbatim: *"just show IDs not details - Equipment ...
//           W-2209, 8841-C, F-0118 - this is enough + account status"*, and
//           the signed-off drawing's table is `Equipment · Reference ·
//           Installed · Whose · Monthly` with no location cell and no
//           last-read cell in it. `WHERE` and `LAST READ` are gone, and the
//           cases below that anchored on `Front boundary box` anchor on
//           something still drawn.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalEquipment } from "../api/portalClient";

let readEquipment: () => Promise<{ as_of: string; equipment: PortalEquipment[] }> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getAccountEquipment: () => readEquipment() };
});

const { EquipmentView } = await import("./Equipment");

/** `US-CWP-043` §4's own three. */
const METER: PortalEquipment = {
  serial_no: "88-40219",
  asset_no: "M-88402",
  kind: "Meter",
  kind_code: "meter",
  category: "meters",
  service: "water",
  where: "Front boundary box",
  fitted_on: "2021-03-04",
  service_name: "Water",
  // ⚠ **THE SEED'S OWN LABEL, WITH THE SLASH IN IT** — this is the exact
  // string `lookup_defaults.json` and `assets/services.py` plant, and the one
  // the PO saw on a customer's screen (`DEF-CWP-3992`).
  status: "Installed/Active",
  status_code: "active",
  behavior_class: "in_service",
  test_due_on: null,
  test_due: false,
  size_class: "W-58",
  // ⚠ **THE RATIFIED NAME, WHICH IS WHAT THE SCREEN DRAWS** (`DEF-CWP-4848`).
  // `tenancy.service_size_classes` names every band after its own service —
  // `Water 5/8"` — because a settings screen has nothing else saying which
  // service a band belongs to. On THIS screen the row already says.
  size_class_name: 'Water 5/8"',
  last_read_on: "2026-08-31",
  // `CPB-10` — the ordinary case: the utility's meter, and the WATER is what
  // is charged for rather than the box on the wall.
  maintained_by: "utility",
  charge_basis: "usage_only",
  monthly_charge: null,
  monthly_charge_bill: null,
};

const CART: PortalEquipment = {
  ...METER,
  serial_no: "C-11840",
  asset_no: "C-11840",
  kind: "Container / Cart",
  kind_code: "container_cart",
  category: "behind_the_meter",
  service: "trash",
  service_name: "Trash",
  where: "Rear alley",
  fitted_on: "2024-01-15",
  size_class: "CART-96",
  size_class_name: "Trash 96-gallon cart",
  // ⚠ **A CART IS NEVER READ.** `null`, and it renders as nothing.
  last_read_on: null,
};

const BACKFLOW: PortalEquipment = {
  ...METER,
  serial_no: "BF-2210",
  asset_no: "BF-2210",
  kind: "Backflow preventer",
  kind_code: "backflow",
  category: "behind_the_meter",
  // ⚠ **A DEVICE ON NO SERVICE POINT**, which is the drawing's third row: it
  // keeps its bare kind and gets no service word in front of it.
  service: null,
  service_name: null,
  test_due_on: "2026-11-14",
  test_due: false,
  size_class: null,
  size_class_name: null,
  last_read_on: null,
};

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/portal` PATTERN, AND THAT IS THE WHOLE
 * POINT OF THE `<Routes>` BELOW.** A bare `MemoryRouter` with no matching route
 * leaves `useParams().tenant` UNDEFINED, so `usePortalPath` builds
 * `//portal/report` — a protocol-relative URL to another host, which
 * `toContain` reads as a perfectly good string. That is how a whole class of
 * broken portal links hid (`DEF-CWP-3925`'s fixture note). With the pattern in
 * place the address is `/pine-hill/portal/report` and an assertion on it means
 * something.
 */
function draw(equipment: PortalEquipment[]) {
  readEquipment = async () => ({ as_of: "2026-09-02", equipment });
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/equipment"]}>
      <Routes>
        <Route path="/:tenant/portal/equipment" element={<EquipmentView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * ⚠ **EVERY ROW IS DRAWN TWICE NOW — ONCE AS A TABLE ROW AND ONCE AS A PHONE
 * CARD — AND ONLY ONE OF THEM IS EVER VISIBLE** (`CR-085`; the switch is CSS,
 * `md:hidden` / `max-md:hidden`, and jsdom applies no CSS). So a bare
 * `findByText` now finds two elements and throws. `findAllByText` is the
 * honest wait: it says *this text is on the screen* without claiming which
 * half drew it, and every assertion below reads a `data-` attribute that
 * belongs to exactly one half (the card's are prefixed `card-`, which is
 * `bills/Bills.tsx`'s own convention for the same reason).
 */

afterEach(cleanup);

describe("CWP-037 · meters and equipment (US-CWP-043)", () => {
  it("TC-1 — three items, each by its REFERENCE and what state it is in", async () => {
    const { container } = draw([METER, CART, BACKFLOW]);
    await screen.findAllByText(/Water Meter/);

    expect(container.querySelector("[data-serial='88-40219']")).not.toBeNull();
    expect(container.querySelector("[data-serial='C-11840']")).not.toBeNull();
    expect(container.querySelector("[data-serial='BF-2210']")).not.toBeNull();
    expect(container.querySelector("[data-chip='status-88-40219']")).not.toBeNull();
  });

  it("CR-085 s52 — the reference IS the row, and the detail columns are gone", async () => {
    // ⚠ **THE PRODUCT OWNER'S OWN RULING, ASSERTED** — *"just show IDs not
    // details ... this is enough + account status"*. The screen used to draw
    // six columns per meter; it draws what the thing is, its printed
    // reference, when it went in, and what state it is in.
    const { container } = draw([METER, CART]);
    await screen.findAllByText(/Water Meter/);
    const headers = [...container.querySelectorAll("th")].map((th) =>
      (th.textContent ?? "").replace("⇅", "").trim(),
    );
    // ⚠ **`Whose` AND `Monthly` JOINED IT ON 2026-09-08** (`CR-085` `CPB-10`) —
    // and they are not *details*, which is what the PO's ruling removed. The
    // signed-off drawing's own table is `Equipment · Reference · Installed ·
    // Whose · Monthly`, so the two the ruling took out (`Where`, `Last read`)
    // are still out and the two the drawing asked for are now in. The
    // assertion is EXACT rather than a superset, so a third column cannot
    // arrive here unnoticed.
    expect(headers).toEqual([
      "Equipment",
      "Reference",
      "Installed",
      "Whose",
      "Monthly",
      "Status",
    ]);
    expect(container.querySelector("[data-last-read='C-11840']")).toBeNull();
    // ⚠ **AND THE CART STILL CANNOT SAY IT MEASURED NOTHING** (TC-2's rule,
    // which the removal must not break): the fact that a cart is never read is
    // now an absent COLUMN rather than an empty cell, and there is no `0`
    // anywhere near it.
    expect(container.textContent ?? "").not.toContain("Last read");
    expect(container.querySelector("[data-serial='C-11840']")?.textContent).toBe("C-11840");
    // Where the thing physically sits is the utility's own record and is not
    // on a customer screen any more.
    expect(container.textContent ?? "").not.toContain("Rear alley");
    expect(container.textContent ?? "").not.toContain("Front boundary box");
  });

  it("CR-085 s52 — the phone frame is a stack of cards, and it cannot disagree with the table", async () => {
    // Measured in the browser at 390px: this table wanted 484. The drawing's
    // phone frame is a stack of cards, and both halves render the same rows.
    const { container } = draw([METER, CART]);
    await screen.findAllByText(/Water Meter/);
    expect(container.querySelectorAll("[data-equipment-cards] [data-equipment-card]")).toHaveLength(
      2,
    );
    expect(container.querySelector("[data-card-serial='88-40219']")?.textContent).toBe("88-40219");
    expect(container.querySelector("[data-card-kind='88-40219']")?.textContent).toBe(
      'Water Meter · 5/8"',
    );
    expect(container.querySelector("[data-card-fitted='88-40219']")?.textContent).toBe("Mar 2021");
    // ⚠ **THE CARD'S CHIP IS ITS OWN**, so an assertion about the table's chip
    // still means the table (`bills/Bills.tsx`'s convention).
    expect(container.querySelector("[data-chip='status-card-88-40219']")?.textContent).toBe(
      "In service",
    );
    expect(container.querySelector("[data-chip='status-88-40219']")?.textContent).toBe(
      "In service",
    );
    // The Product Owner's ruling holds at both widths — no location cell, no
    // last-read cell, on the card either.
    // ⚠ A BARE `not.toContain("0")` WOULD BE MEANINGLESS HERE — the cart's own
    // reference is `C-11840` and contains one. The card is asserted WHOLE
    // instead: the facts and nothing else, which is what *"just show IDs not
    // details"* asks for, and which no substring check could say.
    // ⚠ **SIX FACTS NOW, NOT FOUR** (`CR-085` `CPB-10`, 2026-09-08): the phone
    // card carries `Whose` and `Monthly` too, from the SAME `item` the table
    // row reads. That is the point of asserting it whole — a fact that were
    // true at 1280 and absent at 390 would pass every per-width test in this
    // file, and this is the one assertion that can see it.
    const card = container.querySelector("[data-equipment-card='C-11840']");
    expect(card?.textContent).toBe(
      "Trash Container / Cart · 96-gallon cartC-11840InstalledJan 2024In serviceWhoseOursMonthlyNo charge",
    );
  });

  it("TC-3 — the backflow device shows its TEST DUE from the cadence", async () => {
    // `BR-AST-007` — a DATE on the wire, the MONTH in the reader's own
    // language on screen. November 2026 → `NOV` in English.
    const { container } = draw([BACKFLOW]);
    await screen.findAllByText("Backflow preventer");
    expect(container.querySelector("[data-chip='test-due-BF-2210']")?.textContent).toContain(
      "NOV",
    );
  });

  it("TC-5 · negative — every identifier is a SERIAL, never a row id", async () => {
    const { container } = draw([METER, CART, BACKFLOW]);
    await screen.findAllByText(/Water Meter/);
    expect(container.textContent ?? "").not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
  });

  it("TC-8 · negative — no equipment is a SENTENCE, never a blank table", async () => {
    const { container } = draw([]);
    await screen.findByText("Nothing is recorded at your property yet.");
    expect(container.querySelector("[data-minitable]")).toBeNull();
    expect(container.querySelector("[data-equipment-empty]")).not.toBeNull();
  });

  it("DEF-CWP-4849 — the empty state offers a way to ASK, not just a sentence", async () => {
    // ⚠ **THE DRAWING SAYS SO IN FOUR WORDS.** Screen 52's `NOTHING
    // RECORDED` state is *"We have not recorded your equipment yet." WITH A WAY
    // TO ASK* — and the way to ask (the safety callout and its `Report a
    // problem` door) lived INSIDE the non-empty branch, so the customer most
    // likely to need us got one grey sentence and no control at all.
    //
    // ⚠ **ASSERTED BY WHAT IT OFFERS AND BY ITS ADDRESS, NOT BY ITS
    // WORDS.** The defect's own `prevention` says exactly this: a sentence that
    // is correct as far as it goes passes every assertion that could be written
    // about it. `/report` is `CWP-006` and is BUILT, so this is a live door.
    const { container } = draw([]);
    await screen.findByText("Nothing is recorded at your property yet.");
    const out = container.querySelector("[data-way-out='report']");
    expect(out).not.toBeNull();
    expect(out?.getAttribute("href")).toBe("/pine-hill/portal/report");
    // R-22 — the card says WHICH state it is, so a walkthrough can prove the
    // empty address and the failed address do not render the same thing.
    expect(container.querySelector("[data-portal-state='empty']")).not.toBeNull();
  });

  it("DEF-CWP-4846 — a failed read keeps the title, the screen id and a way out", async () => {
    // ⚠ **THE BRANCH A FIXTURE REACHES BY ACCIDENT IS THE ONE NOBODY
    // ASSERTED.** Every test for this state checked the SENTENCE; nothing
    // checked what disappeared with it, and an absence is invisible to
    // `toContain`. The failure branch used to return above `<PageHeader>`, so
    // the `<h1>`, the kicker, `data-screen` and the `← Usage` back link —
    // this screen's ONLY door — all went with the data.
    readEquipment = async () => {
      throw new Error("500");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/equipment"]}>
        <Routes>
          <Route path="/:tenant/portal/equipment" element={<EquipmentView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("We could not read your equipment.");
    expect(container.querySelector("[data-screen='CWP-037']")).not.toBeNull();
    expect(container.querySelector("h1")?.textContent).toBe(
      "What is installed at your property",
    );
    // The back link, BY ADDRESS — the defect's own `prevention` asks for this
    // rather than for the sentence.
    const back = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(back).toContain("/pine-hill/portal/usage");
    // R-10 — the thing they can do about it, beside the message.
    expect(container.querySelector("[data-way-out='retry']")).not.toBeNull();
  });

  it("the note tells the customer NOT to touch it, and whose it is", async () => {
    const { container } = draw([METER]);
    await screen.findAllByText(/Water Meter/);
    expect(container.textContent).toContain("belongs to the utility");
  });

  // ══════════════════════════════════════════════════════════════════════
  // 2026-09-05 — the wireframe pass (`13-wireframe-delta.md` §CWP-037),
  // every case below read off `wireframes/CWP-037.png` rather than off the
  // delta's notes. Where the two disagreed the image won and the delta row
  // is corrected in that file.
  // ══════════════════════════════════════════════════════════════════════

  it("37.2 — each row is NAMED for what it is, not for its type row", async () => {
    // ⚠ **THE DEFECT IN ONE ASSERTION (`DEF-CWP-3991`).** The seed asset type
    // is called `Meter`, so a property with a water meter and an electric
    // meter drew two rows both reading `Meter`. The service the thing stands
    // on is what a customer calls it.
    const { container } = draw([METER, CART, BACKFLOW]);
    await screen.findAllByText(/Water Meter/);
    // ⚠ **THE SIZE RIDES IN THIS CELL NOW (`DEF-CWP-4848`)** — the drawing
    // writes it there on both widths, and the ratified name's leading service
    // word comes off because the title has already said it.
    expect(container.querySelector("[data-kind='88-40219']")?.textContent).toBe(
      'Water Meter · 5/8"',
    );
    expect(container.querySelector("[data-kind='C-11840']")?.textContent).toBe(
      "Trash Container / Cart · 96-gallon cart",
    );
    // A device on no service point keeps its bare kind — the drawing's third
    // row, and never a stray separator with nothing in front of it.
    expect(container.querySelector("[data-kind='BF-2210']")?.textContent).toBe(
      "Backflow preventer",
    );
  });

  it("37.6 — STATUS is the catalogue's word for the CLASS, never the stored label", async () => {
    // ⚠ **`Installed/Active` IS A LOOKUP VALUE WITH A SLASH IN IT** and it was
    // reaching a customer, in a portal that renders in eleven languages
    // (`DEF-CWP-3992`). The fixture carries that exact string, so this test
    // fails the moment anything starts printing it again.
    const { container } = draw([METER]);
    await screen.findAllByText(/Water Meter/);
    const chip = container.querySelector("[data-chip='status-88-40219']");
    expect(chip?.textContent).toBe("In service");
    expect(container.textContent ?? "").not.toContain("Installed/Active");
  });

  it("37.6 · negative — an unknown behaviour class falls back to the utility's own word", async () => {
    // Better to say the utility's word than to say nothing: a tenant that has
    // added a stage this product does not know is not a reason for a blank
    // cell.
    const odd: PortalEquipment = {
      ...METER,
      behavior_class: "some_class_we_do_not_know",
      status: "In the field",
    };
    const { container } = draw([odd]);
    await screen.findAllByText(/Water Meter/);
    expect(container.querySelector("[data-chip='status-88-40219']")?.textContent).toBe(
      "In the field",
    );
  });

  it("37.6 — an in-service thing with a test coming shows the TEST chip alone", async () => {
    // `CWP-037.png` draws exactly one chip per row, and the test-due row does
    // not also say IN SERVICE.
    const { container } = draw([BACKFLOW]);
    await screen.findAllByText("Backflow preventer");
    expect(container.querySelector("[data-chip='test-due-BF-2210']")).not.toBeNull();
    expect(container.querySelector("[data-chip='status-BF-2210']")).toBeNull();
  });

  it("37.6 · negative — something NOT in service keeps its state chip as well", async () => {
    // The drawing followed off a cliff would hide *needs repair* behind
    // *test due Nov*. Both, when the state is not the ordinary one.
    const broken: PortalEquipment = {
      ...BACKFLOW,
      behavior_class: "out_of_service",
      status: "Needs repair",
    };
    const { container } = draw([broken]);
    await screen.findAllByText("Backflow preventer");
    expect(container.querySelector("[data-chip='status-BF-2210']")?.textContent).toBe(
      "Out of service",
    );
    expect(container.querySelector("[data-chip='test-due-BF-2210']")).not.toBeNull();
  });

  it("37.5 — INSTALLED is month and year, not a full date and not ISO", async () => {
    const { container } = draw([METER, CART]);
    await screen.findAllByText(/Water Meter/);
    expect(container.querySelector("[data-fitted='88-40219']")?.textContent).toBe("Mar 2021");
    expect(container.querySelector("[data-fitted='C-11840']")?.textContent).toBe("Jan 2024");
  });

  it("CR-085 s52 · negative — an unrecorded location cannot make the screen look broken", async () => {
    // ⚠ **`DEF-CWP-3995` IS CLOSED BY REMOVAL RATHER THAN BY A FIXTURE.** That
    // defect was every row of the demo utility drawing a dash, because `where`
    // is `assets.location_note` and no sample-data plant in the repo writes
    // one — a screen that looks broken when it is the data that is empty. The
    // column is not on the drawing and the Product Owner called it a detail,
    // so there is no cell left to dash.
    const nowhere: PortalEquipment = { ...METER, where: null };
    const { container } = draw([nowhere]);
    await screen.findAllByText(/Water Meter/);
    // ⚠ Scoped to the TABLE. The notice below it carries an em dash of its own
    // (*"— the meter belongs to the utility"*), so an unscoped assertion here
    // would be true of the copy and say nothing about the rows.
    expect(container.querySelector("table")?.textContent ?? "").not.toContain("—");
  });

  it("37.1 · 37.7 — the page head names the screen and the notice opens a LIVE door", async () => {
    // ⚠ **`/report` IS CWP-006 AND IT IS BUILT**, so this is a live link and
    // not a hold — checked in `portalRoutes.tsx` rather than assumed. The
    // address is asserted WITH its tenant, which only holds because `draw`
    // mounts under the real `/:tenant/portal` pattern.
    const { container } = draw([METER]);
    await screen.findByText("What is installed at your property");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "What is installed at your property",
    );
    const report = Array.from(container.querySelectorAll("a")).find(
      (a) => a.textContent === "Report a problem",
    );
    expect(report?.getAttribute("href")).toBe("/pine-hill/portal/report");
    // The way out is `← Usage`, and it is a real address too.
    const back = Array.from(container.querySelectorAll("a")).find((a) =>
      (a.textContent ?? "").includes("Usage"),
    );
    expect(back?.getAttribute("href")).toBe("/pine-hill/portal/usage");
  });

  it("37.8 — the BOLD span is the instruction, not the reassurance", async () => {
    // The customer's next action is *tell us*; whose the meter is explains
    // why. Emphasising the explanation instead is what the delta caught.
    const { container } = draw([METER]);
    await screen.findAllByText(/Water Meter/);
    const bold = Array.from(container.querySelectorAll("span.font-bold")).map(
      (n) => n.textContent,
    );
    expect(bold).toContain("Tell us rather than touching it");
  });

  it("37.9 — the notice opens with the word the build had dropped", async () => {
    const { container } = draw([METER]);
    await screen.findAllByText(/Water Meter/);
    expect(container.textContent).toContain("Something damaged, buried or leaking?");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// CR-085 blueprint · CPB-10 — *"Equipment says whose it is and what it costs"*.
// Screen 52's own question is *"what is installed at my address, whose is it,
// and what am I paying for it?"* and the table answered one third of it. The
// drawing's table is `Equipment · Reference · Installed · Whose · Monthly`.
// ═══════════════════════════════════════════════════════════════════════════

/**
 * ⚠ **`kind` AND `size_class` ARE THE LIVE SEED'S OWN VALUES NOW, AND THEY
 * WERE NOT (`DEF-CWP-4848`).** This fixture said `Fire line` / `F-2`; the
 * product's thirteenth `SEED_ASSET_TYPES` row is
 * `("fire_line", "Fire service line", TAB_BTM)` and the ratified fire bands are
 * `FL-2 … FL-12` (six of them — `HYD` was withdrawn by the PO on 2026-09-03).
 * A fixture one word away from the seed is how a stutter reaches a live screen
 * with every test green: `Fire` + `Fire service line` drew **`Fire Fire service
 * line`** on the utility being onboarded and `Fire` + `Fire line` drew `Fire
 * Fire line` here, which is the same defect one word shorter.
 */
const FIRE_LINE: PortalEquipment = {
  ...METER,
  serial_no: "F-0118",
  asset_no: "F-0118",
  kind: "Fire service line",
  kind_code: "fire_line",
  category: "meters",
  service: "fire",
  service_name: "Fire",
  where: null,
  size_class: "FL-2",
  //: The ratified name the server resolves the code to — *the SIZE CLASS picks
  //: the price*, so this is the figure a customer checks `$12.00` against.
  size_class_name: 'Fire line 2"',
  last_read_on: null,
  // A capacity service: the SIZE picks the price and the COUNT multiplies it,
  // so one of these carries a monthly figure of its own.
  charge_basis: "per_item",
  monthly_charge: "12.00",
  monthly_charge_bill: "BL-2608-000052",
};

describe("CPB-10 — whose it is, and what it costs", () => {
  afterEach(cleanup);

  it("says Ours against the utility's own kit", async () => {
    const { container } = draw([METER]);
    await screen.findAllByText("88-40219");
    // The drawing's callout defines the word: *"Equipment marked Ours is
    // maintained by us at no cost to you."*
    expect(container.querySelector("[data-whose='88-40219']")?.textContent).toBe("Ours");
  });

  it("says Yours against the customer's own kit", async () => {
    const { container } = draw([{ ...METER, maintained_by: "customer" }]);
    await screen.findAllByText("88-40219");
    expect(container.querySelector("[data-whose='88-40219']")?.textContent).toBe("Yours");
  });

  it("reads No charge against a meter, which is a FACT and not a gap", async () => {
    const { container } = draw([METER]);
    await screen.findAllByText("88-40219");
    // ⚠ A meter is not what you pay for — the water is. That is a different
    // claim from *we could not find what you were charged*, and the two must
    // not print the same thing.
    expect(container.querySelector("[data-monthly='88-40219']")?.textContent).toBe("No charge");
  });

  it("reads the bill's own rate against a capacity item", async () => {
    const { container } = draw([FIRE_LINE]);
    await screen.findAllByText("F-0118");
    // Money displays at two places (CLAUDE.md hard rule 2).
    expect(container.querySelector("[data-monthly='F-0118']")?.textContent).toBe("$12.00");
  });

  it("states the GAP differently from No charge when a charged item has no figure", async () => {
    // ⚠ **THE WHOLE REASON `charge_basis` TRAVELS.** A cart the customer IS
    // paying for, whose latest bill carried no such line, must not read *No
    // charge* — that is a false statement about money on the customer's own
    // screen. B14 rule 33 caps a refusal at five or six words.
    const { container } = draw([{ ...FIRE_LINE, monthly_charge: null, monthly_charge_bill: null }]);
    await screen.findAllByText("F-0118");
    expect(container.querySelector("[data-monthly='F-0118']")?.textContent).toBe("Not on your last bill");
  });

  it("explains what Ours and Yours mean, once, under the table", async () => {
    // B14 rule 32 — one sentence per section, and it is the sentence that
    // settles a repair bill without anybody reading a policy.
    const { container } = draw([METER, FIRE_LINE]);
    await screen.findAllByText("88-40219");
    expect(container.querySelector("[data-whose-note]")?.textContent).toContain("Ours");
    expect(container.querySelector("[data-whose-note]")?.textContent).toContain("Yours");
  });

  it("DEF-CWP-4848 — the fire line draws its SIZE, and does not stutter", async () => {
    // ⚠ **THE ONE ROW WITH A MONTHLY CHARGE IS THE ONE ROW WHOSE CHARGE
    // COULD NOT BE CHECKED.** CLAUDE.md's fire rule is that the SIZE CLASS
    // picks the price and the COUNT multiplies it — one 2" line is `$12.00`,
    // one 6" line `$60.00` — so a fire row showing `$12.00` and no size told a
    // customer a figure with nothing behind it. The drawing writes the size
    // into the equipment cell on BOTH widths and says why: *"Size is stated in
    // inches, as the customer's plumber would."*
    //
    // ⚠ **AND THE STUTTER IS THE SAME CELL.** The cell was composed
    // unconditionally as `{{service}} {{kind}}`, which is right for the seed
    // word *Meter* (`DEF-CWP-3991`) and wrong for a type the registry already
    // names after its service: `Fire` + `Fire service line`.
    const { container } = draw([FIRE_LINE]);
    await screen.findAllByText("F-0118");
    const cell = container.querySelector("[data-kind='F-0118']")?.textContent ?? "";
    expect(cell).toBe('Fire service line · 2"');
    expect(cell).not.toContain("Fire Fire");
    // ⚠ **THE CODE NEVER REACHES THE GLASS** (B14 rule 32 — no internal
    // code in clerk-facing copy). `FL-2` is on the wire and is not drawn.
    expect(container.textContent ?? "").not.toContain("FL-2");
  });

  it("DEF-CWP-4848 — a meter keeps its service word, and the size loses its own", async () => {
    // The other half of the same rule, and the reason it is not simply *drop
    // the service prefix*: `DEF-CWP-3991` was two rows at one property BOTH
    // reading `Meter`, with only the serial telling them apart. `Water` +
    // `Meter` must survive; only the size name's leading `Water` — a word the
    // title has already shown the reader — comes off.
    const { container } = draw([METER, CART]);
    await screen.findAllByText("88-40219");
    expect(container.querySelector("[data-kind='88-40219']")?.textContent).toBe(
      'Water Meter · 5/8"',
    );
    expect(container.querySelector("[data-kind='C-11840']")?.textContent).toBe(
      "Trash Container / Cart · 96-gallon cart",
    );
  });

  it("DEF-CWP-4848 — a row with no recorded size is the ordinary case and closes up", async () => {
    // `BR-CWP-093`. Most equipment has no size class, and a code the ratified
    // vocabulary does not name answers `null` on the server rather than
    // falling back to itself — printing `FL-99` is the breach the field exists
    // to avoid.
    const { container } = draw([BACKFLOW]);
    await screen.findAllByText("BF-2210");
    expect(container.querySelector("[data-kind='BF-2210']")?.textContent).toBe(
      "Backflow preventer",
    );
  });

  it("carries whose and monthly on the PHONE card too, not only in the table", async () => {
    // ⚠ **JSDOM APPLIES NO CSS SO BOTH HALVES ARE IN THE DOM**, and the card
    // marks its own cells — two elements carrying `data-monthly="F-0118"`
    // would make every assertion above ambiguous (the `bills/Bills.tsx` shape).
    const { container } = draw([FIRE_LINE]);
    await screen.findAllByText("F-0118");
    expect(container.querySelector("[data-card-whose='F-0118']")?.textContent).toBe("Ours");
    expect(container.querySelector("[data-card-monthly='F-0118']")?.textContent).toBe("$12.00");
  });
});
