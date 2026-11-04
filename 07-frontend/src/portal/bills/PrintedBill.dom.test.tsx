// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-034 (EP-CWP-07) · Screen: CWP-029
// Rules:    BR-CWP-045 (serves the issued file; never re-renders) · B14 rule 31
//           (no database id on screen) · rule 32 (a stated absence, and no
//           internal code in customer copy) · rule 33 (a refusal is five or six
//           words)
// Cases:    the kept page offered as a download · TC-4's plain sentence when
//           no copy was kept · no storage key, no id, no reason code on screen
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalPrintedBill } from "../api/portalClient";

let readDocument: () => Promise<PortalPrintedBill> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getPrintedBill: () => readDocument() };
});

const { PrintedBillView } = await import("./PrintedBill");

const KEPT: PortalPrintedBill = {
  number: "BL-2608-0141",
  issued_on: "2026-08-30",
  provenance: "original",
  available: true,
  unavailable_reason: null,
  template_version: 3,
  byte_length: 48213,
  content_type: "application/pdf",
};

const NOT_KEPT: PortalPrintedBill = {
  ...KEPT,
  provenance: "re_rendered_from_data_not_the_original",
  available: false,
  unavailable_reason: "document_not_stored",
  byte_length: null,
  content_type: null,
};

/** ⚠ **RENDERED THROUGH A REAL ROUTE, NOT WITH PROPS.** The tenant and the bill
 *  number reach the screen from the address bar in the product, so they reach it
 *  the same way here — a prop supplied only by a test is a second way of getting
 *  a fact the router already has, and it is what `G13` refuses. */
function draw(document: PortalPrintedBill | null) {
  readDocument =
    document === null
      ? async () => {
          throw new Error("refused");
        }
      : async () => document;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/bills/BL-2608-0141/document"]}>
      <Routes>
        <Route path="/:tenant/portal/bills/:number/document" element={<PrintedBillView />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-029 · the bill as it was printed (US-CWP-034)", () => {
  it("offers the KEPT page as a download, and says when it was posted", async () => {
    const { container } = draw(KEPT);
    await screen.findByText("The bill we sent you");
    const link = container.querySelector("[data-download='printed-bill']");
    expect(link).toBeTruthy();
    // ⚠ AN ANCHOR TO THE SERVER'S OWN ROUTE — not a fetch, not a blob built in
    // the browser, and nothing that could produce a second copy of a legal
    // document.
    expect(link?.getAttribute("href")).toBe(
      "/api/pine-hill/portal/bills/BL-2608-0141/document.pdf",
    );
    expect(screen.getByText(/2026-08-30/)).toBeTruthy();
  });

  it("TC-4 — no kept copy is a plain sentence and a route to ask, never a rebuild", async () => {
    // ⚠ The one case this story exists for. A customer must not be handed a
    // fresh render under the sentence *"exactly as it was printed"*.
    const { container } = draw(NOT_KEPT);
    await screen.findByText("We do not have that file.");
    expect(container.querySelector("[data-download='printed-bill']")).toBeNull();
    expect(container.querySelector("[data-link='ask']")).toBeTruthy();
    expect(container.textContent).not.toContain("Exactly as it was printed");
  });

  it("B14 rule 32 — the server's reason CODE never reaches the customer's eye", async () => {
    // It rides in a data attribute for a bug report and appears in no sentence:
    // rule 32 forbids an internal code in customer-facing copy.
    const { container } = draw(NOT_KEPT);
    await screen.findByText("We do not have that file.");
    expect(
      container.querySelector("[data-document-absent]")?.getAttribute("data-document-absent"),
    ).toBe("document_not_stored");
    expect(screen.queryByText(/document_not_stored/)).toBeNull();
  });

  it("B14 rule 33 — the refusal is six words or fewer", async () => {
    draw(NOT_KEPT);
    const sentence = await screen.findByText("We do not have that file.");
    expect(sentence.textContent!.trim().split(/\s+/)).toHaveLength(6);
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` `CPB-19` — TWO ABSENCES, TWO SENTENCES, AND NEITHER IS A 500
  //
  // A bill whose stored bytes no longer hash to the record used to reach the
  // customer as a Django error page: `ContentHashMismatch` was left uncaught
  // ON PURPOSE, to keep `BR-NOT-027`'s distinction between *we no longer have
  // it* and *what we have is not what you received*. The distinction was
  // right; the stack trace was not.
  // ═══════════════════════════════════════════════════════════════════════

  it("CPB-19 · a copy we cannot vouch for says so, and does NOT say we kept none", async () => {
    const { container } = draw({
      ...NOT_KEPT,
      unavailable_reason: "document_bytes_do_not_match",
    });
    await screen.findByText("We cannot vouch for this copy.");
    // ⚠ **THE NEGATIVE IS THE POINT** (`BR-NOT-027`). Softening a tampered
    // document into *no copy was kept* is the one outcome this path must never
    // produce, and it is exactly what one shared sentence would have done.
    expect(screen.queryByText("We do not have that file.")).toBeNull();
    // The way out is still on the screen, and the code still is not (rule 32).
    expect(container.querySelector("[data-link='ask']")).toBeTruthy();
    expect(screen.queryByText(/document_bytes_do_not_match/)).toBeNull();
    expect(container.querySelector("[data-download='printed-bill']")).toBeNull();
  });

  it("B14 rule 31 — no id and no storage key is ever rendered", async () => {
    const { container } = draw(KEPT);
    await screen.findByText("The bill we sent you");
    expect(container.innerHTML).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/);
    expect(container.textContent).not.toContain("storage");
  });

  it("the screen tags itself CWP-029 and links back by the bill NUMBER", async () => {
    const { container } = draw(KEPT);
    await screen.findByText("The bill we sent you");
    expect(container.querySelector("[data-screen='CWP-029']")).toBeTruthy();
    expect(container.querySelector("[data-back='bill']")?.textContent).toContain("BL-2608-0141");
  });

  it("D8 — the kept page is FRAMED ON SCREEN, not just linked (CWP-029)", async () => {
    // ⚠ **`DEF-CWP-3983`.** This screen shipped as one sentence and a download
    // link — 22 words on the whole page — where `08-screen-layouts.md` gives
    // the issued page most of it, letter-shaped and centred.
    //
    // ⚠ **THE ASSERTION IS ABOUT WHICH BYTES, NOT ABOUT A BOX.** The frame
    // must point at `?view=1` on the SAME document route, because that is what
    // makes this the kept file rather than a re-render — the thing
    // `BR-CWP-045` and `BR-NOT-027` forbid, and the thing a preview built out
    // of the figures would silently be.
    const { container } = draw(KEPT);
    await screen.findByText("The bill we sent you");
    const frame = container.querySelector("[data-document-preview]");
    expect(frame).not.toBeNull();
    const object = frame!.querySelector("object");
    expect(object?.getAttribute("type")).toBe("application/pdf");
    expect(object?.getAttribute("data")).toContain("/document.pdf?view=1");
    // ⚠ The fallback is not decoration — it is what a browser with no PDF
    // viewer actually shows, so it has to be the way out of here.
    expect(frame!.querySelector("[data-download='printed-bill-fallback']")).not.toBeNull();
  });

  it("DEF-CWP-10570 (2.4.7) — the embedded bill takes Tab and draws the product's focus ring", async () => {
    const { container } = draw(KEPT);
    await screen.findByText("The bill we sent you");
    const object = container.querySelector("[data-document-preview] object") as HTMLObjectElement;
    expect(object.getAttribute("tabindex")).toBe("0");
    // 2px of the brand colour, 2px out, on :focus (a plugin-hosted object
    // never matches :focus-visible). #ec3013 is 3.76 on #f3f2f2.
    for (const cls of ["focus:outline-2", "focus:outline-offset-2", "focus:outline-accent"]) {
      expect(object.className.split(/\s+/)).toContain(cls);
    }
    // Inside the PDF viewer no CSS focus selector matches; the ring follows
    // the WINDOW's blur while the object is the active element.
    const ring = ["outline-2", "outline-offset-2", "outline-accent"];
    const classes = () => object.className.split(/\s+/);
    expect(object.hasAttribute("data-focus-inside")).toBe(false);
    for (const cls of ring) expect(classes()).not.toContain(cls);
    object.focus();
    expect(document.activeElement).toBe(object);
    await act(async () => {
      window.dispatchEvent(new Event("blur"));
      await new Promise((resolve) => setTimeout(resolve, 5));
    });
    expect(object.hasAttribute("data-focus-inside")).toBe(true);
    for (const cls of ring) expect(classes()).toContain(cls);
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
    });
    expect(object.hasAttribute("data-focus-inside")).toBe(false);
    for (const cls of ring) expect(classes()).not.toContain(cls);
  });

  it("draws NO frame when no copy was kept — an absence, never an empty box", async () => {
    // ⚠ A framed grey rectangle over *"we do not have that file"* would be the
    // worst of both: `BR-CWP-093` says nothing empty ever appears.
    const { container } = draw(NOT_KEPT);
    await screen.findByText("We do not have that file.");
    expect(container.querySelector("[data-document-preview]")).toBeNull();
  });

  it("a document it cannot read says so, and offers no download either way", async () => {
    const view = draw(null);
    expect(await screen.findByText("We could not read this document.")).toBeTruthy();
    expect(view.container.querySelector("[data-download='printed-bill']")).toBeNull();
  });


  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` step 2 — R-10 on the failed read, and the 390 mitigation.
  // ═══════════════════════════════════════════════════════════════════════

  it("R-10 · a failed read carries the way out beside the message", async () => {
    // PO 2026-09-11: *"the thing they can do about it must be on that same
    // screen, next to the message."* It matters most HERE: this is the screen
    // somebody opens from a cold link to send a bill to a landlord or an
    // accountant, so a dead end costs a phone call rather than a click.
    const { container } = draw(null);
    await screen.findByText(/could not read this document/i);
    const state = container.querySelector("[data-portal-state='failed']");
    expect(state).not.toBeNull();
    expect(state?.querySelector("[data-way-out='retry']")).not.toBeNull();
    expect(state?.querySelector("[data-way-out='bill']")?.getAttribute("href")).toBe(
      "/pine-hill/portal/bills/BL-2608-0141",
    );
    // The head survives, so the page still says where it is and how to leave.
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("The bill we sent you");
  });

  it("DEF-CWP-4865 — a phone is offered the document FULL SCREEN, not a thumbnail", async () => {
    // ⚠ **AT 390 THE FRAME RENDERS 165 × 213 px AND NOBODY CAN READ IT.**
    // `DocumentPreview` hardcodes `w-[62%]` with no responsive step: 62 % of a
    // 1,026px column is a readable 605, 62 % of a 316px one is a thumbnail of
    // a letter page. **The fix is one responsive class on that component**, and
    // `primitives.tsx` is outside this lane's boundary for `CR-085` step 2 —
    // it is handed on, written up in `CR-085-lane5-04-step2-after.md`.
    // What this screen can do without touching the kit is give the phone a way
    // to READ it: the browser's own viewer, full screen. Same `?view=1` stream
    // the frame embeds — the KEPT bytes, never a re-render (`BR-CWP-045`).
    const { container } = draw(KEPT);
    await screen.findByText("The bill we sent you");
    const full = container.querySelector("[data-open='printed-bill-full']");
    expect(full).not.toBeNull();
    expect(full?.getAttribute("href")).toBe(
      "/api/pine-hill/portal/bills/BL-2608-0141/document.pdf?view=1",
    );
    // ⚠ **PHONE ONLY.** Above `md` the framed copy is already readable and a
    // second control there would be furniture (B14 rule 32's budget).
    expect(full?.className).toContain("md:hidden");
    // ⚠ **AND IT IS NOT A SECOND DOCUMENT.** It points at the same stream the
    // frame does, so a customer cannot be shown two different bills.
    const framed = container.querySelector("[data-document-preview] object");
    expect(framed?.getAttribute("data")).toBe(full?.getAttribute("href"));
  });
});
