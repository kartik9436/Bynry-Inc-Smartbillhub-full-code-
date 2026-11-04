// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-001 (EP-CWP-01) — the frame around every no-login screen.
//           Screens: CWP-001 · CWP-002 · CWP-011 · CWP-012 · CWP-013 · CWP-015
// Rules:    09-component-inventory.md §1 `GuestFrame` (Help · Visit us · Pay a
//           bill · Report a problem as plain links + an outlined Sign in) ·
//           BR-CWP-093 (a door to nothing is never drawn) · CR-068 R3 (a
//           control is held UNTIL its screen lands) · B14 rule 31
// Defect:   DEF-CWP-3925 — the frame's own test, which did not exist
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS FILE IS THE ESCAPE REASON, WRITTEN AS CODE.** `GuestFrame` shipped
// with no test of its own and was exercised only sideways, through
// `FrontPage.test.tsx` — which asserted that `data-link="help"` was ABSENT
// when nothing was published and never once asked what it was when present.
// It was a `<span>`. So were *Visit us* and *Pay a bill*, and *Sign in* was a
// disabled button, on **every guest screen in the product**, over four screens
// that had landed in waves B, D, E and P.
//
// The cases below are therefore written the way the walkthrough looks at it:
// not *is the word on the page* but *where does it go when you press it*.

import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import pkg from "../../../package.json";

import type { ErrandCardKey, ErrandCardOffer, PortalFront } from "../api/guestClient";
import { resolvePortalScreen } from "../routing/screenIds";

import { GuestFrame } from "./GuestFrame";

/**
 * The server sends all six errand cards with whether each may be used (PO
 * ruling 2026-09-05). These suites are about doors OTHER than the card grid,
 * so they name the usable ones and let this build the payload — one place to
 * edit if the shape moves again.
 */
function offered(...keys: ErrandCardKey[]): ErrandCardOffer[] {
  return CARD_KEYS.map((key) =>
    keys.includes(key)
      ? { key, available: true as const, reason_code: null }
      : { key, available: false as const, reason_code: "switched_off_by_the_utility" as const },
  );
}

const CARD_KEYS: ErrandCardKey[] = [
  "pay_bill",
  "report_problem",
  "check_my_area",
  "start_service",
  "what_things_cost",
  "help_answers",
];


function front(over: Partial<PortalFront> = {}): PortalFront {
  return {
    tenant: {
      slug: "pine-hill",
      name: "Pine Hill Water & Power",
      brand_primary_hex: "#0F7B6C",
      brand_accent_hex: null,
    },
    is_live: true,
    // `DEF-CWP-3994` — the tenant's Regional settings ride on the front
    // payload, and the type makes them REQUIRED so a fixture cannot
    // quietly omit them and hide the wire being absent.
    regional: { timezone: "America/Chicago", date_format: "DD-MMM-YY", language: null },
    // `PORTAL_LOCALES` — the two the portal OFFERS (`BR-CWP-106`).
    locales: ["en", "es"],
    cards: offered("pay_bill", "report_problem", "start_service", "what_things_cost", "help_answers"),
    links: { help: true, visit: true },
    switches: {
      quick_pay_enabled: true,
      self_read_enabled: false,
      plans_enabled: true,
      requests_enabled: true,
      outage_reporting_enabled: true,
    },
    services: [],
    strapline: null,
    office_hours_text: "8am to 5pm, Monday to Friday",
    emergency_phone: "(512) 555-0100",
    ...over,
  };
}

/** Mounted under the real path pattern — `usePortalPath` reads `:tenant`. */
function render(data: PortalFront): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/pine-hill/portal"]}>
      <Routes>
        <Route
          path="/:tenant/portal"
          element={
            <GuestFrame front={data}>
              <p>a screen</p>
            </GuestFrame>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

/** Every `href` the frame emitted, in document order. */
function hrefs(html: string): string[] {
  return [...html.matchAll(/href="([^"]*)"/g)].map((m) => m[1]);
}

describe("GuestFrame · the nav a visitor uses without signing in", () => {
  /**
   * The defect itself. Each of these five words is a door, and a door is a
   * `href` — the assertion is deliberately on the ADDRESS and not on the tag,
   * because a `<span>` styled like a link is what shipped.
   */
  it("DEF-CWP-3925: all five doors are addresses, and each names a screen this product serves", () => {
    const html = render(front());
    const expected: Record<string, string> = {
      "/pine-hill/portal/help": "CWP-011",
      "/pine-hill/portal/visit": "CWP-013",
      "/pine-hill/portal/pay": "CWP-002",
      "/pine-hill/portal/report": "CWP-006",
      "/pine-hill/portal/track": "CWP-012",
      "/pine-hill/portal/sign-in": "CWP-015",
    };
    const found = hrefs(html);
    for (const [href, id] of Object.entries(expected)) {
      expect(found, `${href} is not a door on this frame`).toContain(href);
      const sub = href.replace("/pine-hill/portal", "") || "/";
      expect(resolvePortalScreen(sub)?.id, `${href} opens the wrong screen`).toBe(id);
    }
    // Nothing in the nav is disabled any more, and nothing promises a release.
    expect(html).not.toContain('data-held="true"');
    expect(html).not.toContain("Opens with the next release.");
    // A tenant-less href is the bug the FrontPage fixture used to hide.
    expect(found.every((one) => !one.startsWith("//"))).toBe(true);
  });

  /**
   * `BR-CWP-093` — a door to nothing is not drawn at all. Making the three
   * conditional words into links must not have made any of them unconditional,
   * which is the mistake this fix is one keystroke away from.
   */
  /**
   * ⚠ **THE ONE WAY THE 2026-09-05 RULING COULD HAVE BROKEN THIS FRAME, AND
   * THE REASON THIS CASE EXISTS.** That ruling puts all six errand cards in
   * the payload, so `front.cards.includes("pay_bill")` — the frame's old test
   * — became TRUE FOR EVERY TENANT, and a utility with quick pay switched off
   * would have grown a *Pay a bill* word in its top bar pointing at a door
   * `BR-CWP-002` refuses. The compiler caught it because the payload's shape
   * changed with it; had the ruling only added a field, nothing would have.
   *
   * So this case asks the question the shape change happened to answer:
   * **a card that is SENT and NOT AVAILABLE must put no word in the nav.**
   */
  it("a sent-but-unavailable card puts NO word in the top bar (the 2026-09-05 ruling)", () => {
    const all = CARD_KEYS.map((key) =>
      key === "pay_bill"
        ? { key, available: false as const, reason_code: "switched_off_by_the_utility" as const }
        : { key, available: true as const, reason_code: null },
    );
    const html = render(front({ cards: all, links: { help: true, visit: true } }));
    // Every key is in the payload — presence has stopped meaning anything.
    expect(all).toHaveLength(6);
    expect(html).not.toContain('data-link="pay_bill"');
    expect(hrefs(html)).not.toContain("/pine-hill/portal/pay");
    // …and the one beside it, sent AND available, still has its word.
    expect(html).toContain('data-link="report_problem"');
    expect(hrefs(html)).toContain("/pine-hill/portal/report");
  });

  it("BR-CWP-093: a word whose screen would be empty is ABSENT, not a dead link", () => {
    const html = render(front({ links: { help: false, visit: false }, cards: offered("report_problem") }));
    expect(html).not.toContain('data-link="help"');
    expect(html).not.toContain('data-link="visit"');
    expect(html).not.toContain('data-link="pay_bill"');
    expect(hrefs(html)).not.toContain("/pine-hill/portal/help");
    // Report a problem, Track and Sign in are unconditional and still there.
    expect(hrefs(html)).toContain("/pine-hill/portal/report");
    expect(hrefs(html)).toContain("/pine-hill/portal/track");
    expect(hrefs(html)).toContain("/pine-hill/portal/sign-in");
  });

  /** The portal switched off: a holding page, and no nav at all to link from. */
  it("US-CWP-001 TC-3: the portal is off → no nav, so no door of any kind", () => {
    const html = render(front({ is_live: false }));
    expect(html).not.toContain("<nav");
    expect(hrefs(html)).toEqual([]);
    expect(html).toContain("Pine Hill Water &amp; Power");
  });

  /**
   * ⚠ **THE EMERGENCY LINE, AND THE ASSERTION IS ITS POSITION.** *"Above
   * everything, on every width … Somebody standing in water must not have to
   * read a page."* The number was already on the page before this — in grey,
   * in the footer, below six errand cards — so a case that merely asked *is
   * the number present* would have passed over the exact defect, which is why
   * this one compares indexes.
   */
  it("the emergency number is ABOVE the screen, not only in the footer", () => {
    const html = render(front());
    const band = html.indexOf("data-emergency-band");
    const screen = html.indexOf("a screen");
    const footer = html.indexOf('data-footer="emergency"');
    expect(band, "no emergency band on the guest frame").toBeGreaterThan(-1);
    expect(band).toBeLessThan(screen);
    expect(screen).toBeLessThan(footer);
    expect(html).toContain("(512) 555-0100");
    expect(html).toContain("Is anyone in danger?");
    expect(html).toContain("Any hour.");
  });

  /**
   * ⚠ **THE TAIL FROM `CWP-006` MUST NOT COME WITH IT.** `portal.report
   * .emergencyTail` ends *"Do not use this form."* — true beside a report
   * form, and on `/sign-in` it would be telling a customer not to sign in.
   * The band reuses the title and the lead and mints its own ending.
   */
  it("the band does not tell a customer not to use the form they are looking at", () => {
    expect(render(front())).not.toContain("Do not use this form");
  });

  /** `BR-CWP-093` — a heading over an absent number is an empty container. */
  it("a utility with no emergency number gets no band at all", () => {
    const html = render(front({ emergency_phone: null }));
    expect(html).not.toContain("data-emergency-band");
    expect(html).not.toContain("Is anyone in danger?");
  });

  /** TC-3 again, one control along: a holding page carries no band either. */
  it("US-CWP-001 TC-3: the portal is off → no band", () => {
    expect(render(front({ is_live: false }))).not.toContain("data-emergency-band");
  });

  /** DEF-CWP-3736's guard, kept here now the frame has a test of its own. */
  it("DEF-CWP-3736: the accent the kit reads is the TENANT's hex, not the theme's", () => {
    const html = render(front());
    expect(html).toContain("--color-accent:#0F7B6C");
    expect(html).toContain("--color-accent-600:color-mix(in srgb, #0F7B6C 88%, black)");
    expect(html).not.toContain("--brand");
  });
});

/**
 * `DEF-CWP-9162` — PO 2026-10-02: *"The Customer Portal does not display the
 * application/version number."* Watched FAIL on `2.455.0` (no footer at all
 * without office hours, and no version in any footer) before the fix.
 */
describe("GuestFrame · the build version on every guest page (DEF-CWP-9162)", () => {
  const VERSION = (pkg as { version: string }).version;

  it("is in the footer, as words a screen reader can say", () => {
    const html = render(front());
    expect(html).toContain(`data-version="${VERSION}"`);
    expect(html).toContain(`Version ${VERSION}`);
    expect(html.indexOf("<footer")).toBeLessThan(html.indexOf(`Version ${VERSION}`));
  });

  it("is there when the utility set no office hours and no emergency number", () => {
    const html = render(front({ office_hours_text: null, emergency_phone: null }));
    expect(html).toContain(`Version ${VERSION}`);
  });

  it("is there on the holding page of a switched-off portal", () => {
    const html = render(front({ is_live: false }));
    expect(html).toContain(`Version ${VERSION}`);
    expect(html).not.toContain('data-footer="emergency"');
  });
});
