// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:   DEF-CWP-4440 — PO 2026-09-07: *"you can also provdie language
//          option for gurst customers on top menu as drop down"*.
// Defect:  DEF-CWP-4442 — PO 2026-09-07: *"currently in drop down show only 2
//          elnglish and spanish"*. The list is the SERVER's now, off the front
//          payload, so the guest control and `CWP-024`'s cannot disagree.
// Rules:   BR-CWP-105 · B14 rule 8 (a real `<select>`) · B14 rule 31 (no
//          internal code on screen) · B14 rule 35 (a language in its own
//          language) · US-CWP-001 TC-3 (portal off → no nav) · hard-won law 2
//          and its mirror, DEF-CWP-3925 (a live-looking control over nothing)
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **EVERY CASE MOUNTS `GuestFrame`, NOT `GuestLanguage`.** A control tested
// on its own proves it works and says nothing about whether the frame draws
// it — which is precisely how the portal shipped a front page with two working
// doors out of eight, every screen live and every test green (`DEF-CWP-3925`).
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { PortalFront } from "../api/guestClient";
import { GUEST_LANGUAGE_KEY } from "../components/language";
import { GuestFrame } from "./GuestFrame";

afterEach(cleanup);
beforeEach(async () => {
  window.sessionStorage.clear();
  await i18n.changeLanguage("en");
});

const FRONT = (isLive = true): PortalFront => ({
  tenant: {
    slug: "pine-hill",
    name: "Pine Hill Water",
    brand_primary_hex: null,
    brand_accent_hex: null,
  },
  is_live: isLive,
  regional: { timezone: "America/Chicago", date_format: "DD-MMM-YY", language: "en" },
  // ⚠ **THE OFFER IS THE SERVER'S AND ARRIVES HERE** (`DEF-CWP-4442`). It was
  // `LOCALE_CODES` — the CATALOGUE registry — until 2026-09-07, which folded
  // the two questions `BR-CWP-105` says never to fold.
  locales: ["en", "es"],
  cards: [],
  links: { help: false, visit: false },
  switches: undefined,
  services: [],
  strapline: null,
  office_hours_text: null,
  emergency_phone: null,
});

function drawFrame(front: PortalFront) {
  // The REAL path pattern — a bare MemoryRouter leaves `useParams().tenant`
  // undefined and every address comes out `//portal/…` (`DEF-CWP-3925`).
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal"]}>
      <Routes>
        <Route path="/:tenant/portal" element={<GuestFrame front={front}>{null}</GuestFrame>} />
      </Routes>
    </MemoryRouter>,
  );
}

const picker = () => document.querySelector<HTMLSelectElement>('[data-guest-language="select"]');

describe("the guest's language dropdown (DEF-CWP-4440, PO 2026-09-07)", () => {
  it("is drawn in the guest frame's top menu", () => {
    drawFrame(FRONT());
    const control = picker();
    expect(control).not.toBeNull();
    // B14 rule 8 — a real `<select>`, not a div wearing one.
    expect(control?.tagName).toBe("SELECT");
    // In the nav, which is what *"on top menu"* means.
    expect(control?.closest("nav")).not.toBeNull();
  });

  it("names each language IN ITS OWN LANGUAGE and never as a code", () => {
    drawFrame(FRONT());
    const labels = Array.from(picker()?.options ?? []).map((o) => o.textContent);
    // B14 rule 35 — `English` and `Español`, each written the way its own
    // speakers write it, through the same `languageName` the portal's OTHER
    // language picker (`CWP-024`) uses. A list of ENGLISH names would be
    // unreadable to the one person who needs it: somebody who cannot read the
    // page they are looking at.
    expect(labels).toEqual(["English", "Español"]);
    // B14 rule 31 — an internal code is never the visible value of a field.
    // The VALUE attribute is the code; the text a person reads must not be.
    expect(labels).not.toContain("en");
    expect(labels).not.toContain("es");
  });

  it("offers the TWO the Product Owner ruled and not the eleven catalogues", () => {
    // ⚠ **THIS ASSERTED ELEVEN UNTIL 2026-09-07** (`DEF-CWP-4442`). PO,
    // verbatim: *"currently in drop down show only 2 elnglish and spanish"*.
    // The number comes off the wire, so a lane that narrows the constant and
    // forgets the screen — or the reverse — goes red here.
    drawFrame(FRONT());
    expect(Array.from(picker()?.options ?? []).map((o) => o.value)).toEqual(["en", "es"]);
  });

  it("adds the READER'S OWN language when it is neither, rather than going blank", () => {
    // ⚠ **THE DEFECT THE RULING CARRIED WITH IT.** Accounts already hold `de`
    // and `hi`. A `<select>` listing two options over a stored third renders
    // BLANK — no error, `tsc` green, every `toContain` passing — so the
    // reader's own language is listed as what it is. Nobody's stored choice
    // is reset (decision log 2026-09-07).
    void i18n.changeLanguage("de");
    drawFrame(FRONT());
    const labels = Array.from(picker()?.options ?? []).map((o) => o.textContent);
    expect(labels).toEqual(["English", "Español", "Deutsch"]);
    expect(picker()?.value).toBe("de");
    // ⚠ Not blank — the assertion that fails on the whole point of this fix.
    expect(picker()?.value).not.toBe("");
  });

  it("stops offering the old language once they have chosen away from it", () => {
    // One click, one way, by design: the third option is derived from what
    // the reader holds and not from a memory of what they held.
    void i18n.changeLanguage("de");
    drawFrame(FRONT());
    fireEvent.change(picker() as HTMLSelectElement, { target: { value: "es" } });
    cleanup();
    drawFrame(FRONT());
    expect(Array.from(picker()?.options ?? []).map((o) => o.value)).toEqual(["en", "es"]);
  });

  it("ACTUALLY changes the language when a guest picks one", async () => {
    // ⚠ The mirror of hard-won law 2: a control that looks live over a page
    // that does not move. This is the assertion that would fail on one.
    //
    // ⚠ **THE PICK WAS `de` UNTIL 2026-09-07 AND HAD TO MOVE** — not because
    // the behaviour changed but because `de` is no longer offered to a reader
    // on English (`DEF-CWP-4442`), and `fireEvent.change` to a value with no
    // `<option>` behind it sets the control to "" and asserts nothing. A test
    // that drives a control to an impossible value is testing the browser.
    drawFrame(FRONT());
    expect(i18n.language).toBe("en");
    fireEvent.change(picker() as HTMLSelectElement, { target: { value: "es" } });
    expect(i18n.language).toBe("es");
  });

  it("remembers the choice for the tab so a navigation cannot undo it", () => {
    drawFrame(FRONT());
    fireEvent.change(picker() as HTMLSelectElement, { target: { value: "es" } });
    expect(window.sessionStorage.getItem(GUEST_LANGUAGE_KEY)).toBe("es");
  });

  it("opens on the language the page is actually in, not on English", () => {
    window.sessionStorage.setItem(GUEST_LANGUAGE_KEY, "de");
    // The applier is what reads storage; here the page simply IS in German,
    // and the control must agree with it rather than contradict the screen.
    void i18n.changeLanguage("de");
    drawFrame(FRONT());
    expect(picker()?.value).toBe("de");
  });

  it("is NOT drawn when the portal is switched off", () => {
    // `US-CWP-001` TC-3 — a holding page has no nav and no control of any
    // kind, and no sentence to translate either.
    drawFrame(FRONT(false));
    expect(picker()).toBeNull();
  });

  /**
   * ⚠ **A UTILITY THAT OFFERS ONE LANGUAGE GETS NO CONTROL.** The wireframe's
   * `s2` states it as a screen state and gives the reason in five words: *"a
   * chooser with one option is furniture."* Most tenants are in exactly this
   * state and nobody had seen it, because the only fixture in the product
   * offers two.
   */
  it("one language offered → no picker at all", () => {
    drawFrame({ ...FRONT(), locales: ["en"] });
    expect(picker()).toBeNull();
    // The rest of the nav is untouched — this hides one control, not a bar.
    expect(document.querySelector("nav")).not.toBeNull();
  });

  /**
   * The mirror, and the reason the hide is keyed off the OPTIONS rather than
   * off the offer: a reader already on a language the utility does not offer
   * has a real second option, and hiding the control would strand them on a
   * language they never chose.
   */
  it("one language offered, but the reader is on another → the picker stays", () => {
    void i18n.changeLanguage("de");
    drawFrame({ ...FRONT(), locales: ["en"] });
    expect(Array.from(picker()?.options ?? []).map((o) => o.value)).toEqual(["en", "de"]);
  });

  /**
   * ⚠ **F-17 (`DEF-CWP-10553`), RULED 2026-10-23:** the label says it changes
   * the page (it used to be `LANGUAGE`, which said nothing of the kind).
   */
  it("carries an accessible name that says it changes the page", () => {
    drawFrame(FRONT());
    expect(screen.getByLabelText("Language (changes the page)")).toBe(picker());
  });

  it("an arrow-key pick switches at once, keeps focus on the picker and is announced in the new language", async () => {
    drawFrame(FRONT());
    const select = picker() as HTMLSelectElement;
    select.focus();
    fireEvent.change(select, { target: { value: "es" } });
    await waitFor(() => expect(i18n.language).toBe("es"));
    await waitFor(() =>
      expect(document.querySelector("[data-portal-status]")?.textContent).toBe("Página en español"),
    );
    expect(document.activeElement).toBe(picker());
    expect(picker()).toHaveAccessibleName("Idioma (cambia la página)");
  });
});
