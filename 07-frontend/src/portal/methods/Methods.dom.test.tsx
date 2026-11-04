// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-046 (EP-CWP-09) · US-CWP-022 (EP-CWP-05) · Screen: CWP-039
// Rules:    BR-CWP-057 (a token with a brand and a last four — the served row
//           has no card number on it and this file asserts the DOM has none
//           either) · BR-CWP-056 (a refused control is visible, disabled and
//           carries its reason) · BR-CWP-040 (step-up before a method changes)
//           · B14 rule 17 · rule 31 (no database id on screen) · rule 33
// Cases:    the two saved methods · no digits beyond four anywhere in the DOM ·
//           the row id never renders · autopay refused with its reason ·
//           autopay allowed links to CWP-040 BY ADDRESS · the expired card ·
//           the code box appears only after a code is sent · the empty state
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **NOT ONE ASSERTION BELOW READS ENGLISH, AND THAT IS DELIBERATE.** Four
// lanes built six screens at once, so the eleven locale catalogues were a shared
// file and this lane's 49 keys were merged AFTER this code landed — every
// `t(...)` here rendered as its own KEY in between. An assertion on *"We never
// hold your full card number"* would have failed then; an assertion on
// `portal.methods.tokenBold` would have failed the day the words arrived. So the
// tests read STRUCTURE (data attributes), ADDRESSES (`href`) and SERVER DATA
// (the brand, the four digits, the date) — none of which is translated, and all
// of which is what these rules are actually about.
//
// ⚠ **AND THIS FILE BROKE ITS OWN RULE IN THREE PLACES.** Three cases pressed
// the Add control with `getByText("portal.methods.add")` — reading a key, which
// is reading the catalogue by another name — and all three went red the moment
// the wording landed: *Unable to find an element with the text:
// portal.methods.add*. The catalogue lane repaired them to
// `getByText("Add a method")`, which is the same bug wearing the other face: it
// passes today and fails the next time anybody edits that wording or runs this
// suite in another language. The control carries `data-add-method` now.
// **The general form is worth more than either fix: a test that finds a control
// by its LABEL is a test of the catalogue, and it breaks on the most ordinary
// act there is — translating a word.**
//
// ⚠ **AND THE COMPONENT IS MOUNTED UNDER THE REAL PATH PATTERN**
// (`/:tenant/portal/payment-methods`), not bare inside a `MemoryRouter`. That
// is hard-won law 2's fixture clause: with no matching route `useParams().tenant`
// is undefined, every address the page builds comes out `//portal/…` — a
// protocol-relative URL to another host — and `toContain` reads it as a
// perfectly good string. The address assertion below is only meaningful because
// of this.
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalPaymentMethods, PortalStepUpSent } from "./methodsApi";

/** `US-CWP-046` §4's test data, verbatim: Chase ••••4021 and Visa ••••8812. */
const TWO: PortalPaymentMethods = {
  methods: [
    {
      ref: "0198f0aa-1111-7000-8000-000000000001",
      brand: "Chase",
      last_four: "4021",
      kind: "bank",
      status: "verified",
      used_for: ["autopay", "one_off"],
      added_on: "2026-03-04",
      expires: null,
      usable: true,
    },
    {
      ref: "0198f0aa-1111-7000-8000-000000000002",
      brand: "Visa",
      last_four: "8812",
      kind: "card",
      status: "active",
      used_for: ["one_off"],
      added_on: "2026-06-02",
      expires: "11/27",
      usable: true,
    },
  ],
  autopay: { allowed: true, reason: null, bounces: 0 },
  card_fee: { payer: "utility", priced: false, reason: "no_processor" },
};

let load: () => Promise<PortalPaymentMethods> = async () => TWO;
// ⚠ TYPED AS THE CONTRACT, NOT AS ITS FIRST VALUE. Inferring the type from the
// happy path makes the `no_contact_on_file` case below a compile error — and
// the refusal is exactly what that case exists to exercise.
let stepUp: ReturnType<typeof vi.fn<() => Promise<PortalStepUpSent>>> = vi.fn(async () => ({
  sent: true,
  sent_to: "••• ••• 0144",
  channel: "sms",
}));

vi.mock("./methodsApi", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("./methodsApi");
  return {
    ...actual,
    getPaymentMethods: () => load(),
    askForStepUpCode: () => stepUp(),
    savePaymentMethod: async () => ({ saved: true }),
    removePaymentMethod: async () => ({ removed: true }),
  };
});

const { MethodsView } = await import("./Methods");

function draw() {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/payment-methods"]}>
      <Routes>
        <Route path="/:tenant/portal/payment-methods" element={<MethodsView />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** A run of five or more digits — the shape of a card number, and of nothing
 *  else this screen can legitimately show. */
const PAN_SHAPED = /\d{5,}/;

beforeEach(() => {
  load = async () => TWO;
  stepUp = vi.fn(async () => ({ sent: true, sent_to: "••• ••• 0144", channel: "sms" }) as PortalStepUpSent);
});
/**
 * **THE DESK TABLE HALF OF THE SCREEN** (`CR-085`).
 *
 * ⚠ **THIS SCREEN NOW DRAWS EVERY METHOD TWICE — ONCE AS A TABLE ROW AND ONCE
 * AS A PHONE CARD — AND ONLY ONE OF THEM IS EVER VISIBLE.** The switch is CSS
 * (`md:hidden` / `max-md:hidden`), and jsdom applies no CSS, so an unscoped
 * `screen.findByText(/Chase ••••4021/)` finds two elements and fails. Scoping
 * is not a workaround: waiting for the TABLE is what these cases mean, and
 * saying so stops the same query silently starting to answer with the card.
 * `CWP-027` and `CWP-041` take the same shape for the same reason.
 */
async function deskShows(container: HTMLElement, text: RegExp | string) {
  const table = await screen.findByRole("table");
  return within(table.parentElement as HTMLElement).getByText(text);
}

afterEach(cleanup);

describe("CWP-039 · your payment methods (US-CWP-046)", () => {
  it("TC-1 — lists both saved methods by brand and last four", async () => {
    const { container } = draw();
    await deskShows(container, /Chase ••••4021/);
    expect(await deskShows(container, /Visa ••••8812/)).toBeTruthy();
    // The bank mandate is VERIFIED and the card is ACTIVE — two different
    // facts, and the chip is the kit's, not a fifth one (B14 rule 36).
    expect(container.querySelector('[data-chip="verified"]')).toBeTruthy();
    expect(container.querySelector('[data-chip="active"]')).toBeTruthy();
    expect(await deskShows(container, "2026-03-04")).toBeTruthy();
  });

  it("TC-2 — BR-CWP-057: no run of digits longer than four reaches the DOM", async () => {
    const { container } = draw();
    await deskShows(container, /Chase ••••4021/);
    // ⚠ **EVERY TEXT NODE, ONE AT A TIME — AND THE FIRST DRAFT OF THIS TEST
    // READ `container.textContent` AND WAS WRONG.** That property concatenates
    // adjacent cells with no separator, so `••••4021` beside `2026-03-04` came
    // out as `40212026` and the test reported a card number on a screen that
    // had none. A run of digits only means anything to a human WITHIN one
    // rendered string, which is what this walks.
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const offenders: string[] = [];
    for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
      const text = node.nodeValue ?? "";
      if (PAN_SHAPED.test(text)) offenders.push(text);
    }
    expect(offenders).toEqual([]);
  });

  it("B14 rule 31 — the row id is never on screen, in text or in a data attribute", async () => {
    const { container } = draw();
    await deskShows(container, /Chase ••••4021/);
    // `ref` belongs in a URL and nowhere else. `data-row` DOES reach the DOM,
    // so the table is keyed on the four digits instead.
    expect(container.innerHTML).not.toContain("0198f0aa-1111-7000-8000-000000000001");
    expect(container.querySelector('[data-row="4021"]')).toBeTruthy();
  });

  it("TC-6 — an expired card says so and is drawn as unusable", async () => {
    load = async () => ({
      ...TWO,
      methods: [
        {
          ref: "0198f0aa-1111-7000-8000-000000000003",
          brand: "Visa",
          last_four: "4417",
          kind: "card",
          status: "expired",
          used_for: ["one_off"],
          added_on: "2025-08-01",
          expires: "08/26",
          usable: false,
        },
      ],
    });
    const { container } = draw();
    await deskShows(container, /Visa ••••4417/);
    expect(container.querySelector('[data-chip="expired"]')).toBeTruthy();
    // `muted` is the kit's word for a row that is listed but cannot be chosen.
    expect(container.querySelector('[data-row="4417"]')?.getAttribute("data-muted")).toBe("true");
  });

  /**
   * `CR-085` — **THE PHONE COULD NOT SEE THE STATUS AND COULD NOT REMOVE A
   * METHOD.**
   *
   * ⚠ **MEASURED, NOT INFERRED.** At 390 the table's own content is 459px wide
   * inside a 316px column: the `METHOD` cell wraps to one word a line
   * (*Silver / Creek / Credit / Union*), the status chip is clipped mid-word
   * (`VE`, `AC`), and the whole `ACTION` column — Change and Remove — sits off
   * the right-hand edge behind a sideways scroll. The screen exists to answer
   * *what is on file and what breaks if I remove one*, and on a phone it could
   * do neither.
   *
   * The wireframe's phone frame is a stack of cards, and `CWP-027` and
   * `CWP-041` take the same shape for the same reason.
   */
  it("CR-085 — a phone gets a card per method, with its status and its actions", async () => {
    const { container } = draw();
    await screen.findByRole("table");

    const cards = [...container.querySelectorAll("[data-method-card]")];
    expect(cards).toHaveLength(2);
    expect(cards.map((card) => card.getAttribute("data-method-card"))).toEqual(["4021", "8812"]);

    // ⚠ **THE THREE THINGS THAT WERE OFF THE EDGE OR CLIPPED**, per card.
    expect(cards[0].querySelector("[data-chip='verified']")).toBeTruthy();
    expect(cards[0].querySelector("[data-testid='method-card-remove']")).toBeTruthy();
    expect(cards[0].querySelector("[data-testid='method-card-edit']")).toBeTruthy();

    // Removing is the one action that redirects money, so the card's control
    // asks for the same fresh code the table's does (`BR-CWP-040`) — it is the
    // same handler, not a second path to the same write.
    fireEvent.click(cards[1].querySelector("[data-testid='method-card-remove']")!);
    await waitFor(() =>
      expect(container.querySelector("[data-step-up-target]")).toBeTruthy(),
    );
    expect(
      container.querySelector("[data-step-up-target]")?.getAttribute("data-step-up-target"),
    ).toBe("Visa ••••8812");
  });

  it("B14 rule 17 — with nothing saved, the screen says what fills it", async () => {
    load = async () => ({ ...TWO, methods: [] });
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-methods-empty]")).toBeTruthy());
    // An empty TABLE would assert nothing at all; this asserts there is none.
    expect(container.querySelector("[data-minitable]")).toBeNull();
  });
});

describe("CWP-039 · a refused control is visible, disabled and says why (BR-CWP-056)", () => {
  it("TC-4 — a cash-only account holds autopay with its reason ON the control", async () => {
    load = async () => ({
      ...TWO,
      autopay: { allowed: false, reason: "cash_only", bounces: 0 },
    });
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-held="true"]')).toBeTruthy());
    const button = container.querySelector('[data-held="true"] button');
    expect(button).toBeDisabled();
    // ⚠ THE REASON IS ON THE CONTROL, not only beside it — `HeldButton` puts it
    // on `title` as well, so a hover reads it.
    expect(button?.getAttribute("title")).toBeTruthy();
    // ⚠ AND THE LIST IS UNTOUCHED. Never hidden (BR-CWP-056).
    expect(await deskShows(container, /Chase ••••4021/)).toBeTruthy();
  });

  it("TC-5 — two bounces hold it too, and the control is disabled rather than absent", async () => {
    load = async () => ({ ...TWO, autopay: { allowed: false, reason: "bounced", bounces: 2 } });
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-held="true"]')).toBeTruthy());
    expect(container.querySelector('[data-held="true"] button')).toBeDisabled();
    expect(container.querySelector("[data-testid='methods-autopay']")).toBeTruthy();
  });

  /**
   * `DEF-CWP-4873` — **a plural noun after `1`, on screen.**
   *
   * *"1 bounced payments block autopay."* `13-wireframe-delta.md` row 39.7
   * recorded it and no defect row ever carried it, so it was still live on
   * 2026-09-11, reproduced with `bounces: 1`. The catalogue key had no plural
   * form at all — one string for every count, in eleven languages — and nothing
   * in this repo reads a sentence for grammar.
   */
  it("DEF-CWP-4873 — ONE bounce reads as one payment, not as *1 payments*", async () => {
    load = async () => ({ ...TWO, autopay: { allowed: false, reason: "bounced", bounces: 1 } });
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-held="true"]')).toBeTruthy());

    const held = container.querySelector('[data-held="true"]') as HTMLElement;
    expect(held.textContent).toContain("1 bounced payment blocks autopay.");
    expect(held.textContent).not.toContain("1 bounced payments");
  });

  it("two bounces still read as two payments", async () => {
    load = async () => ({ ...TWO, autopay: { allowed: false, reason: "bounced", bounces: 2 } });
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-held="true"]')).toBeTruthy());
    expect((container.querySelector('[data-held="true"]') as HTMLElement).textContent).toContain(
      "2 bounced payments block autopay.",
    );
  });

  it("when autopay IS allowed the control is a LIVE link to CWP-040, by address", async () => {
    // ⚠ **THE ASSERTION DEF-CWP-3925 COST A DAY TO LEARN.** A control that only
    // *exists* proves nothing: six shut doors sat over six live screens and
    // every test passed. So this asserts the DESTINATION — the real address of
    // `CWP-040`, tenant segment included — and it goes red the day the link is
    // replaced by a `<span>`, a `#` or a hold.
    const { container } = draw();
    await waitFor(() =>
      expect(container.querySelector("[data-testid='methods-autopay'] a")).toBeTruthy(),
    );
    const link = container.querySelector("[data-testid='methods-autopay'] a");
    expect(link?.getAttribute("href")).toBe("/pine-hill/portal/autopay");
    // And it is NOT held.
    expect(container.querySelector("[data-testid='methods-autopay'] [data-held]")).toBeNull();
  });
});

describe("CWP-039 · step-up before a method changes (US-CWP-022)", () => {
  it("there is no code box until a code has actually been asked for", async () => {
    const { container } = draw();
    await deskShows(container, /Chase ••••4021/);
    expect(container.querySelector("[data-testid='methods-step-up']")).toBeNull();
    expect(container.querySelector("#method-code")).toBeNull();
  });

  it("TC-1 — asking to add one sends a code and shows where it went, masked", async () => {
    const { container } = draw();
    await deskShows(container, /Chase ••••4021/);
    fireEvent.click(container.querySelector("[data-add-method]")!);
    await waitFor(() =>
      expect(container.querySelector("[data-testid='methods-step-up']")).toBeTruthy(),
    );
    expect(stepUp).toHaveBeenCalledTimes(1);
    // ⚠ THE MASKED DESTINATION AND NOTHING MORE — naming the contact would
    // hand a hijacked session the address it needs to intercept the code. The
    // ATTRIBUTE is asserted rather than the sentence, so this checks which
    // contact reached the screen rather than what a catalogue calls it.
    expect(container.querySelector("[data-step-up-sent]")?.getAttribute("data-step-up-sent")).toBe(
      "••• ••• 0144",
    );
    expect(container.querySelector("#method-code")).toBeTruthy();
  });

  it("the commit is held until a code is typed (B14 rule 33 — a reason on it)", async () => {
    const { container } = draw();
    await deskShows(container, /Chase ••••4021/);
    fireEvent.click(container.querySelector("[data-add-method]")!);
    await waitFor(() => expect(container.querySelector("#method-code")).toBeTruthy());
    const held = container.querySelector("[data-testid='methods-step-up'] button[disabled]");
    expect(held).toBeTruthy();
    expect(held?.getAttribute("title")).toBeTruthy();
  });

  it("TC-1 — removing one names the method it is about to remove", async () => {
    const { container } = draw();
    await deskShows(container, /Chase ••••4021/);
    // ⚠ **BY `testId`, NOT BY INDEX.** This read `button[0]` inside the row,
    // which was the remove button until the row gained the wireframe's ✎ — and
    // then it was the PENCIL, which is held, so the click did nothing at all
    // and this case failed over a screen that was right.
    fireEvent.click(container.querySelector('[data-testid="method-remove"]')!);
    await waitFor(() =>
      expect(container.querySelector("[data-step-up-target]")).toBeTruthy(),
    );
    // ⚠ WHICH card, in the words a person recognises. A confirmation that did
    // not say would be a step-up on an unnamed action.
    expect(
      container.querySelector("[data-step-up-target]")?.getAttribute("data-step-up-target"),
    ).toBe("Chase ••••4021");
  });

  /**
   * `DEF-CWP-3973` / delta 39.1–39.3 — **the drawing, checked against the
   * screen.** Every one of these was live and wrong on 2026-09-05 and not one
   * of them could fail a test this repo had: an information bar may legally
   * contain a button, a one-line table cell is a valid cell, and a `Remove`
   * button is a wired control with a label.
   */
  describe("CWP-039 · the wireframe, row by row", () => {
    it("39.2 · the primary action is beside the TITLE, not inside the notice", async () => {
      const { container } = draw();
      await deskShows(container, /Chase ••••4021/);

      const add = container.querySelector("[data-add-method]") as HTMLElement;
      expect(add).not.toBeNull();
      // ⚠ **ASSERTED BY CONTAINMENT, BOTH WAYS.** *It exists* passed before the
      // fix too; what was wrong was WHERE. An information bar is the one place
      // a primary action should never be — it reads as part of the
      // explanation rather than as the thing to press.
      expect(container.querySelector(".page-header")?.contains(add)).toBe(true);
      const notice = container.querySelector("[data-infobar]");
      if (notice !== null) expect(notice.contains(add)).toBe(false);
      // And it is live: the stored-instrument table exists now, so a hold here
      // would be a shut door over a working path (DEF-CWP-3925).
      expect(add).toBeEnabled();
    });

    it("39.3 · the METHOD cell is two lines — the name, then what kind it is", async () => {
      const { container } = draw();
      await deskShows(container, /Chase ••••4021/);

      const names = [...container.querySelectorAll("[data-method-name]")].map(
        (n) => n.textContent,
      );
      const kinds = [...container.querySelectorAll("[data-method-kind]")].map(
        (n) => n.textContent,
      );
      expect(names).toContain("Chase ••••4021");
      // A mandate has no expiry and says only what it is; a card carries both.
      expect(kinds).toContain("Bank account");
      expect(kinds.some((one) => (one ?? "").includes("expires"))).toBe(true);
    });

    it("39.3 · the row ends in icons, and the pencil is held with its reason", async () => {
      const { container } = draw();
      await deskShows(container, /Chase ••••4021/);

      const edit = container.querySelector('[data-testid="method-edit"]') as HTMLButtonElement;
      const remove = container.querySelector('[data-testid="method-remove"]') as HTMLButtonElement;
      expect(edit).not.toBeNull();
      expect(remove).not.toBeNull();
      // ⚠ **VISIBLE, DISABLED AND CARRYING ITS REASON** (CR-068 R3). There is
      // no edit endpoint; hiding the control would leave a customer who came
      // looking for it concluding the product cannot do it at all.
      expect(edit).toBeDisabled();
      expect(edit.getAttribute("title")).toBe("Changing one is not ready.");
      expect(remove).toBeEnabled();
    });

    it("39.5 · the autopay control is a normal-size button in a row, not a full-width bar", async () => {
      const { container } = draw();
      await deskShows(container, /Chase ••••4021/);

      const card = container.querySelector('[data-testid="methods-autopay"]') as HTMLElement;
      const control = card.querySelector("a, button") as HTMLElement;
      expect(control).not.toBeNull();
      // ⚠ **THE ROOT CAUSE, ASSERTED AT ITS ROOT.** `Card` is `flex flex-col`,
      // so a control placed DIRECTLY in it stretches to the card's width —
      // which is not one of the kit's two button sizes and read on screen as a
      // live switch spanning the card. The class list is identical either way,
      // so nothing but the parent can tell you.
      const row = control.closest("div");
      expect(row?.className ?? "").toContain("flex");
      expect(card.children).not.toContain(control);
      // And the standing of autopay is SAID, not left to the next screen.
      expect(card.querySelector("[data-autopay-stance]")?.textContent).toBe(
        "Autopay cannot be switched on yet.",
      );
    });
  });

  it("BR-CWP-034 — no contact on file dead-ends rather than falling back", async () => {
    stepUp = vi.fn(async () => ({ sent: false, reason: "no_contact_on_file" }));
    const { container } = draw();
    await deskShows(container, /Chase ••••4021/);
    fireEvent.click(container.querySelector("[data-add-method]")!);
    await waitFor(() => expect(container.querySelector("[data-methods-refused]")).toBeTruthy());
    // ⚠ AND NO CODE BOX. A form offered with nowhere to send the code would be
    // a dead end wearing a live control.
    expect(container.querySelector("#method-code")).toBeNull();
  });
});

describe("CWP-039 · the card fee is a stance and never a figure (OQ-1394)", () => {
  it("states who pays and shows no number", async () => {
    const { container } = draw();
    await waitFor(() =>
      expect(container.querySelector("[data-card-fee='utility']")).toBeTruthy(),
    );
    const panel = container.querySelector("[data-testid='methods-card-fee']");
    // ⚠ NO FIGURE, because there is no processor to price one from. A `$` here
    // would be a number nobody computed on a screen about money.
    expect(panel?.textContent).not.toContain("$");
    expect(panel?.textContent).not.toMatch(/\d+(\.\d+)?%/);
  });

  it("a tenant that passes the fee on says so, and still shows no number", async () => {
    load = async () => ({
      ...TWO,
      card_fee: { payer: "customer", priced: false, reason: "no_processor" },
    });
    const { container } = draw();
    await waitFor(() =>
      expect(container.querySelector("[data-card-fee='customer']")).toBeTruthy(),
    );
    expect(container.querySelector("[data-testid='methods-card-fee']")?.textContent).not.toContain(
      "$",
    );
  });
});
