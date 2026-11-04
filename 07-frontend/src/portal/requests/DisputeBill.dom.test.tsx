// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-065 (EP-CWP-11) · Screen: CWP-055
// Rules:    CLAUDE.md hard rule 4 · BR-CWP-042 (a correction is a NEW bill) ·
//           B14 rule 31 · rule 32 · rule 33 · r10 rule 6 (danger is for a
//           DESTRUCTIVE commit and this is not one)
// Open:     OQ-CWP-1682 — the box must NOT promise a collection hold, because
//           nothing in this product records a disputed AMOUNT (`OQ-420`)
// Cases:    the bill is named by its number · the panel says the bill does not
//           change · NO hold is promised, in ANY catalogue · the send control
//           is held until both boxes are filled · the reference opens CWP-051
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

const sent = vi.fn(async () => ({
  reference: "SR-26-0087",
  bill_number: "BL-2608-0141",
  bill_changed: false,
  collection_held: false,
  reading_marked: false,
}));

/** The bill, as `GET portal/bills/{number}` serves it — the SAME read `CWP-028`
 *  makes, so the amount a customer disputes and the amount their bill shows are
 *  one answer (`12-reuse-map.md`). Only the fields this screen touches. */
let readBill: () => Promise<unknown> = async () => ({
  number: BILL_NUMBER,
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  total_display: "142.18",
  currency: "USD",
});

vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, disputeBill: () => sent(), getBillDetail: () => readBill() };
});

const BILL_NUMBER = "BL-2608-0141";

const { DisputeBillView } = await import("./DisputeBill");

const BILL = BILL_NUMBER;

/**
 * ⚠ **THE `:tenant` SEGMENT IS IN THE ROUTE AND NOT ONLY IN THE URL.**
 * `usePortalPath` reads `useParams().tenant` — the tenant is taken off the
 * address the browser is on and never typed (`BR-CWP-005`) — so a bare
 * `MemoryRouter` with no matching `Route` renders every link as `//portal/…`
 * and the href assertion below would be testing the harness rather than the
 * screen.
 */
function draw() {
  return render(
    <MemoryRouter initialEntries={[`/pine-hill/portal/bills/${BILL}/dispute`]}>
      <Routes>
        <Route path="/:tenant/portal/*" element={<DisputeBillView number={BILL} />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** ⚠ **THE FIVE REASONS ARE THE SCREEN'S, NOT THIS FIXTURE'S.** *What are you
 *  questioning* is a `<select>` of the five real reasons (the drawing's
 *  `Select`), so a value this file invented would silently not be selected at
 *  all — a `<select>` given an unknown value keeps `""`, which reads as a
 *  perfectly good assignment and leaves the form empty. */
const CHOSEN = "I think the meter reading is wrong";

/** Fill both required boxes and reach step 2. */
function fill(container: HTMLElement) {
  fireEvent.change(container.querySelector("#dispute-what") as HTMLSelectElement, {
    target: { value: CHOSEN },
  });
  fireEvent.change(container.querySelector("#dispute-reason") as HTMLTextAreaElement, {
    target: { value: "The house was empty for two weeks." },
  });
}

afterEach(() => {
  cleanup();
  sent.mockClear();
});

describe("CWP-055 · dispute a bill or a reading (US-CWP-065)", () => {
  // ══ CR-085 wave 4 · CPB-13 — the screen where you dispute money says it ══

  it("CPB-13 · DEF-CWP-4202 — the lead names the AMOUNT, not only the number", async () => {
    // ⚠ **THE ONE SCREEN IN THE PRODUCT WHERE A CUSTOMER DISPUTES MONEY NEVER
    // STATED THE MONEY.** Walked live on 2026-09-08: not one figure anywhere
    // on the page, on either step.
    const { container } = draw();
    expect(await screen.findByText("You are querying bill BL-2608-0141, $142.18.")).toBeTruthy();
    expect(container.querySelector("[data-bill-amount]")?.getAttribute("data-bill-amount")).toBe(
      "$142.18",
    );
  });

  it("CPB-13 · the check-and-send row is the number AND the figure", async () => {
    // The drawing's own first row: `Bill  BL-2608-0141 · $142.18`. A step that
    // asks a customer to confirm a claim about money without showing them the
    // money is not a check.
    const { container } = draw();
    await screen.findByText("You are querying bill BL-2608-0141, $142.18.");
    fill(container);
    fireEvent.click(screen.getByText("Check it"));
    expect(container.querySelector("[data-check='bill']")?.textContent).toBe(
      "BL-2608-0141 · $142.18",
    );
    expect(container.querySelector("[data-check='period']")?.textContent).toBe(
      "2026-08-01 to 2026-08-31",
    );
  });

  it("CPB-13 · a bill read that fails still lets the customer send the query", async () => {
    // ⚠ **THE FIGURE IS A COURTESY AND THE QUERY IS THE POINT.** Refusing a
    // customer their complaint because a second read failed would be worse
    // than the defect this closes; the server re-reads the bill for itself.
    readBill = async () => {
      throw new Error("nope");
    };
    const { container } = draw();
    expect(await screen.findByText("You are querying bill BL-2608-0141.")).toBeTruthy();
    fill(container);
    fireEvent.click(screen.getByText("Check it"));
    expect(container.querySelector("[data-check='bill']")?.textContent).toBe("BL-2608-0141");
    readBill = async () => ({
      number: BILL_NUMBER,
      period_start: "2026-08-01",
      period_end: "2026-08-31",
      total_display: "142.18",
      currency: "USD",
    });
  });

  it("CPB-13 · the consequence box is in the SAME COLUMN as the commit, above it", async () => {
    // ⚠ **DOM ORDER WAS ALREADY RIGHT AND THE SCREEN WAS WRONG** — the box was
    // in the right rail, so *before the commit* was true of the document and
    // false of the page. The assertion is therefore about the COMMON ANCESTOR,
    // which is the thing that was broken.
    const { container } = draw();
    await screen.findByText("You are querying bill BL-2608-0141, $142.18.");
    fill(container);
    fireEvent.click(screen.getByText("Check it"));
    const box = screen.getByText("The bill itself does not change.");
    const commit = screen.getByText("Send the query ✓");
    const card = container.querySelector("[data-testid='dispute']");
    expect(card).not.toBeNull();
    expect(card?.contains(box)).toBe(true);
    expect(card?.contains(commit)).toBe(true);
    // …and ABOVE it, which is r10 rule 11 and the half DOM order already had.
    expect(box.compareDocumentPosition(commit) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("CPB-13 · step 2 offers a way back to step 1", async () => {
    // `DEF-CWP-4202` row 55.4 — the customer had no route back to what they had
    // typed; the browser's own back button leaves the screen entirely.
    const { container } = draw();
    await screen.findByText("You are querying bill BL-2608-0141, $142.18.");
    fill(container);
    fireEvent.click(screen.getByText("Check it"));
    const back = container.querySelector("[data-action='back-to-step-1']");
    expect(back).not.toBeNull();
    fireEvent.click(back as Element);
    // Back on step 1, with what they typed still in the box.
    expect((container.querySelector("#dispute-reason") as HTMLTextAreaElement).value).toBe(
      "The house was empty for two weeks.",
    );
  });

  it("names the bill by its NUMBER and never by an id (B14 rule 31)", () => {
    const { container } = draw();
    expect(container.querySelector(`[data-bill-number='${BILL}']`)).not.toBeNull();
    expect(container.textContent).toContain(BILL);
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  });

  it("⚠ THE PANEL SAYS THE BILL ITSELF DOES NOT CHANGE (hard rule 4)", () => {
    const { container } = draw();
    expect(container.textContent).toContain("The bill itself does not change.");
    expect(container.textContent).toContain("If we agree, we issue a corrected bill.");
    // `BR-CWP-042`'s other half, which customers get wrong most often.
    expect(container.textContent).toContain(
      "Anything you are not questioning is still due on time.",
    );
  });

  it("⚠ NO COLLECTION HOLD IS PROMISED — OQ-CWP-1682 / OQ-420", () => {
    // The blueprint's box reads *"we hold collection on $142.18 · no late fee
    // while we look"*. `BR-MET-133` clause 4 needs the disputed AMOUNT and
    // nothing records one, so printing that would be a promise on a customer's
    // money that nothing behind it keeps.
    const { container } = draw();
    const words = (container.textContent ?? "").toLowerCase();
    expect(words).not.toContain("hold collection");
    expect(words).not.toContain("no late fee");
    expect(words).not.toContain("we hold");
    expect(words).not.toContain("$142.18");
  });

  it("⚠ AND NO CATALOGUE PROMISES ONE EITHER — all eleven", async () => {
    // A copy assertion the screen alone cannot make: the wording constraint is
    // on the CATALOGUES, so a later lane translating an English promise back in
    // would slip past a rendered-output check in ten languages.
    const catalogues = import.meta.glob("../../i18n/locales/*.json", { eager: true }) as Record<
      string,
      { default: Record<string, string> }
    >;
    const files = Object.entries(catalogues);
    expect(files).toHaveLength(11);
    for (const [name, module] of files) {
      for (const [key, value] of Object.entries(module.default)) {
        if (!key.startsWith("portal.dispute.")) continue;
        expect(
          /hold(ing)? (the )?collection|no late fee|sin recargo|keine Mahngeb/i.test(value),
          `${name} · ${key}`,
        ).toBe(false);
      }
    }
  });

  it("the five real reasons are a LIST, not an empty box", async () => {
    // ⚠ **THE DRAWING'S OWN REASONING** — *"The reasons are the five real
    // ones, in the customer's words, chosen from a list. An open text box
    // alone makes them compose an argument; a list lets them recognise their
    // situation."* This field was a bare text input, so the first thing a
    // customer met on the screen they open when something has gone wrong was
    // a blank line and no idea what to write on it.
    const { container } = draw();
    const select = container.querySelector("#dispute-what") as HTMLSelectElement;
    expect(select.tagName).toBe("SELECT");
    const options = [...select.querySelectorAll("option")].map((o) => o.textContent);
    expect(options).toEqual([
      "Choose one…",
      "The amount is higher than I expected",
      "I think the meter reading is wrong",
      "I am being charged for a service I do not have",
      "A payment I made is not shown",
      "Something else",
    ]);
    // ⚠ **THE VALUE THAT TRAVELS IS THE SENTENCE, NEVER A CODE** — it is
    // written into the words a clerk reads and `CWP-046` shows back to the
    // customer (B14 rule 32).
    for (const option of select.querySelectorAll("option")) {
      expect(option.getAttribute("value")).not.toMatch(/^[a-z_]+$/);
    }
    // Nothing is pre-chosen: the empty row is a real row and carries words.
    expect(select.value).toBe("");
  });

  it("the screen has a title and a way BACK to the bill it is about", async () => {
    // ⚠ **HARD-WON LAW 2's MIRROR.** This screen opened straight onto the
    // stepper — no `<h1>` for a screen reader to land on, and no route back to
    // the bill, so the only way out of a half-filled query was the browser's
    // own back button. Every other screen in this journey carries the same
    // head with the same link.
    const { container } = draw();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Something is wrong with this bill",
    );
    // ⚠ Asserted WHOLE — `toContain` passes on `//portal/bills/…`.
    const back = container.querySelector("[data-back='bill'] a");
    expect(back?.getAttribute("href")).toBe(`/pine-hill/portal/bills/${BILL}`);
    expect(back?.textContent).toContain(BILL);
  });

  it("the send control is HELD until both boxes are filled (rule 33 reason)", () => {
    const { container } = draw();
    const check = screen.getByText("Check it");
    expect(check).toBeDisabled();
    expect(check).toHaveAttribute("title", "Fill in both boxes first.");

    fill(container);
    expect(screen.getByText("Check it")).not.toBeDisabled();
  });

  it("⚠ NOT the danger tier — questioning a bill destroys nothing (r10 rule 6)", () => {
    const { container } = draw();
    fill(container);
    fireEvent.click(screen.getByText("Check it"));

    const send = screen.getByText("Send the query ✓");
    expect(send.getAttribute("data-variant")).not.toBe("danger");
  });

  it("step 2 reads the answers back before anything is sent", () => {
    const { container } = draw();
    fill(container);
    fireEvent.click(screen.getByText("Check it"));

    // ⚠ **THE FIGURE JOINED IT IN `CPB-13`.** Synchronously after `draw()` the
    // bill read has not landed, so this row is still the bare number here — the
    // case above is the one that waits for the read and asserts both halves.
    expect(container.querySelector("[data-check='bill']")?.textContent).toBe(BILL);
    expect(container.querySelector("[data-check='what']")?.textContent).toBe(CHOSEN);
    expect(sent).not.toHaveBeenCalled();
  });

  it("the customer's own reading is offered as EVIDENCE and is optional", () => {
    const { container } = draw();
    expect(container.querySelector("#dispute-reading")).not.toBeNull();
    expect(container.textContent).toContain(
      "Optional. We keep it as evidence, not as a meter reading.",
    );
    // And it is absent from the check page when it was left blank.
    fill(container);
    fireEvent.click(screen.getByText("Check it"));
    expect(container.querySelector("[data-check='own_reading']")).toBeNull();
  });

  it("the confirmation carries the reference AND a door to CWP-051", async () => {
    const { container } = draw();
    fill(container);
    fireEvent.click(screen.getByText("Check it"));
    fireEvent.click(screen.getByText("Send the query ✓"));
    await screen.findByText("Your query is with us");

    expect(container.querySelector("[data-reference='SR-26-0087']")).not.toBeNull();
    // ⚠ Hard-won law 2: a reference nothing can be looked up with is dead copy.
    const track = screen.getByText("Track this query →");
    expect(track.getAttribute("href")).toBe("/pine-hill/portal/requests/SR-26-0087");
  });
});
