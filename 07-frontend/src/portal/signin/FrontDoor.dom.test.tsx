// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-016 (CWP-015, EP-CWP-05) — the front door: sign in, and the
//           three doors beside it. Screen: CWP-015
// Rules:    BR-CWP-004 (a staff credential gets the ORDINARY failure — this
//           screen has no branch that could say otherwise) · B14 rule 33 ·
//           hard-won law 2 (a word styled as a door that opens nothing)
// Cases:    the wireframe's `s3` — two fields, the reset worded as a question,
//           and the form first on a phone
//
//           ⚠ **`FrontDoor.tsx` HAS NAMED A TEST FILE SINCE WAVE E AND NONE
//           EXISTED (`DEF-CWP-3862`).** Its own header says so in capitals —
//           *"NONE — `SignIn.test.tsx` DOES NOT EXIST AND THIS LINE NAMED IT
//           ANYWAY"* — so the busiest signed-out screen after the front page
//           had no check of any kind. This file is that half closed.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { PortalFront } from "../api/guestClient";

import { FrontDoorView } from "./FrontDoor";

const FRONT: PortalFront = {
  tenant: {
    slug: "pine-hill",
    name: "Pine Hill Water & Power",
    brand_primary_hex: "#EC3013",
    brand_accent_hex: null,
  },
  is_live: true,
  regional: { timezone: "America/Chicago", date_format: "DD-MMM-YY", language: null },
  locales: ["en", "es"],
  cards: [],
  links: { help: true, visit: true },
  switches: undefined,
  services: [{ code: "water", name: "Water", color: null }],
  strapline: "Your account, any time.",
  office_hours_text: "8am to 5pm, Monday to Friday",
  emergency_phone: "(512) 555-0100",
};

/** The REAL path pattern — a bare mount leaves `useParams().tenant` undefined
 *  and every address comes out `//portal/…` (`DEF-CWP-3925`). */
function draw() {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/sign-in"]}>
      <Routes>
        <Route path="/:tenant/portal/sign-in" element={<FrontDoorView front={FRONT} />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("CWP-015 · the front door (US-CWP-016)", () => {
  /**
   * ⚠ **THE THREE DOORS ARE ADDRESSES, NOT WORDS.** `DEF-CWP-3925` shipped
   * eight controls on the guest surface that looked like doors and opened
   * nothing, so the assertion is on the `href` and on the tenant in it.
   */
  it("the three doors beside the form are real addresses", () => {
    const { container } = draw();
    for (const [mark, href] of Object.entries({
      enrol: "/pine-hill/portal/enrol",
      // DEF-CWP-10567 (F-24): quick pay opens Pay, as it does from enrol.
      quick_pay: "/pine-hill/portal/pay",
      start_service: "/pine-hill/portal/start-service",
    })) {
      const door = container.querySelector(`[data-door="${mark}"]`);
      expect(door, `${mark} is not a door on CWP-015`).not.toBeNull();
      expect(door?.getAttribute("href")).toBe(href);
    }
    expect(container.innerHTML).not.toContain('href="//portal');
  });

  /**
   * ⚠ **THE WIREFRAME NAMES THIS STRING.** `s3`'s *Words* section: *"'Forgot
   * your password?' as a question, not 'Password recovery'."* It read
   * *"Forgotten it?"* — three words with no referent once a customer has
   * scrolled past the password box, and the same key now labels the door on
   * the FRONT page, where there is no password box at all.
   */
  it("the reset is worded as a question about the password", () => {
    const { container } = draw();
    const link = container.querySelector('a[href="/pine-hill/portal/forgot-password"]');
    expect(link?.textContent).toBe("Forgot your password?");
  });

  /**
   * ⚠ **ON A PHONE THE FORM COMES FIRST, AND THIS IS A CLASS CHECK STANDING
   * IN FOR A LAYOUT ONE — SAY SO PLAINLY (hard-won law 7).** jsdom computes
   * no layout, so nothing here can prove the panels moved; what it can prove
   * is that the two `max-md:order-*` rules are still present and still the
   * right way round, which is what a later edit would delete.
   *
   * **The layout itself was proved in a real engine** (hard-won law 6), at
   * `/pine-hill/portal/sign-in`, measured with `boundingBox()`:
   *
   *     @1280  brand top=219 left=110 | form top=219 left=648  → BESIDE
   *     @390   brand top=919 left=20  | form top=316 left=20   → ABOVE
   *
   * Before the change the form began at about 700px on a 390px screen, under
   * the utility's name, strapline, services, hours and phone number.
   */
  it("the phone order puts the sign-in card first and the brand panel second", () => {
    const { container } = draw();
    const brand = container.querySelector('[data-testid="front-door-brand"]')?.parentElement;
    const form = container.querySelector('[data-testid="front-door-signin"]')?.parentElement;
    expect(brand?.className).toContain("max-md:order-2");
    expect(form?.className).toContain("max-md:order-1");
    // Source order is unchanged — it is the READING order, and above 900px the
    // brand panel genuinely is first.
    const order = (brand as HTMLElement).compareDocumentPosition(form as HTMLElement);
    expect(order & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  /** `BR-CWP-004` — no *are you staff?* link, and nothing that would answer
   *  whether this utility has staff accounts to anybody who looked. */
  it("BR-CWP-004: nothing on this screen mentions staff", () => {
    const { container } = draw();
    expect(container.textContent ?? "").not.toMatch(/staff/i);
  });
});
