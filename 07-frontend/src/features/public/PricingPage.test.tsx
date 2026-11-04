// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-018 (EP-TEN-03 — S1 itself)  Screens: S1
// Change:   DEF-TEN-4222 reopened 2026-10-02 — the public home page is redrawn
//           from the PO's approved draft (v6) and STOPS SHOWING PRICES.
// Rules:    BR-TEN-002 (sizes advisory) · BR-TEN-014 (14-day trial, no card) ·
//           BR-SHL-023 (ONE money path) · NFR-5 (no account cap)
// ───────────────────────────────────────────────────────
// Markup asserts on react-dom/server static output. No network anywhere: the
// page no longer reads the plan catalogue at all, so nothing is seeded.
//
// RED-PROVED (law 7) against the page as it stood before this lane: the
// no-price case failed on "$1,000.00", the link cases found no
// `bynry.com/book-a-demo` and a walkthrough button pointing at `/signup`, and
// the eleven-chip case found no `data-service-chip` at all.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { SIGNUP_SERVICES } from "@/features/tenancy/SignupWizard";

import {
  PricingPage,
  SIGNIN_HELP_ROUTE,
  SIGNUP_ROUTE,
  SUPPORT_PHONE,
  SUPPORT_PHONE_HREF,
  WALKTHROUGH_URL,
} from "./PricingPage";

function renderHome(): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/"]}>
      <PricingPage />
    </MemoryRouter>,
  );
}

/** Every `<a …>` opening tag, so a link is asserted by its own attributes. */
function anchors(html: string): string[] {
  return [...html.matchAll(/<a\b[^>]*>/g)].map((m) => m[0]);
}

function hrefOf(tag: string): string | undefined {
  return /href="([^"]*)"/.exec(tag)?.[1];
}

describe("DEF-TEN-4222 — the home page shows NO price (PO 2026-10-02)", () => {
  it("none of the three old subscription prices, and no per-month figure, appears anywhere", () => {
    const html = renderHome();
    for (const price of ["$1,000", "$5,000", "$8,000", "1,000.00", "5,000.00", "8,000.00"]) {
      expect(html, price).not.toContain(price);
    }
    expect(html).not.toMatch(/\/\s*month|per month/i);
    expect(html).not.toContain('data-pricing="plan"');
    expect(html).not.toContain("Starter");
    expect(html).not.toContain("Growth");
  });

  it("the ONLY dollar figures are the example statement and the two proof lines — never what we charge", () => {
    const html = renderHome();
    const figures = new Set(html.match(/\$[\d,]+\.\d{2}/g) ?? []);
    expect([...figures].sort()).toEqual(
      ["$1,270,167.00", "$18.00", "$229.64", "$28.06", "$31.18", "$68.40", "$84.00"].sort(),
    );
  });

  it("the example statement foots: five lines add to the amount due", () => {
    // 68.40 + 31.18 + 28.06 + 18.00 + 84.00 = 229.64, in cents to stay exact.
    expect(6840 + 3118 + 2806 + 1800 + 8400).toBe(22964);
    const html = renderHome();
    expect(html).toContain("Amount due 31 Oct 2026");
    expect(html).toContain("6&quot; line + 2 × 2&quot; lines");
  });

  it("says pricing is being revised, with the customer service number", () => {
    const html = renderHome();
    expect(html).toContain("Pricing is being revised. Ask us during the walkthrough, or call ");
    expect(html).toContain(SUPPORT_PHONE);
  });

  it("the old copy the ICP correction made false is gone", () => {
    const html = renderHome();
    expect(html).not.toContain("one-person office");
    expect(html).not.toContain("three thousand");
    expect(html).toContain("Billing for utilities up to 40,000 accounts.");
  });
});

describe("the links the PO named, by ADDRESS (draft v4/v6)", () => {
  it("Sign in goes to the existing tenant-less /signin-help, never a /signin", () => {
    expect(SIGNIN_HELP_ROUTE).toBe("/signin-help");
    const tags = anchors(renderHome()).filter((tag) => hrefOf(tag) === "/signin-help");
    expect(tags).toHaveLength(1);
    expect(renderHome()).not.toContain('href="/signin"');
  });

  it("EVERY Start free goes to the existing /signup wizard, with no plan in the address", () => {
    expect(SIGNUP_ROUTE).toBe("/signup");
    const html = renderHome();
    const starts = anchors(html).filter((tag) => hrefOf(tag)?.startsWith("/signup"));
    expect(starts).toHaveLength(2); // nav + hero
    for (const tag of starts) expect(hrefOf(tag)).toBe("/signup");
    expect(html).toContain("Start free — 14 days, no card"); // BR-TEN-014
  });

  it("BOTH Book a walkthrough go to Bynry's demo page in a new tab, safely", () => {
    expect(WALKTHROUGH_URL).toBe("https://www.bynry.com/book-a-demo");
    const tags = anchors(renderHome()).filter((tag) => tag.includes('data-public-link="walkthrough"'));
    expect(tags).toHaveLength(2); // hero + No-account-cap box
    for (const tag of tags) {
      expect(hrefOf(tag)).toBe(WALKTHROUGH_URL);
      expect(tag).toContain('target="_blank"');
      expect(tag).toContain('rel="noopener noreferrer"');
    }
  });

  it("the customer service number is a tel: link in all four places it is printed", () => {
    expect(SUPPORT_PHONE).toBe("+1 732-630-0285");
    const tags = anchors(renderHome()).filter((tag) => hrefOf(tag) === SUPPORT_PHONE_HREF);
    expect(SUPPORT_PHONE_HREF).toBe("tel:+17326300285");
    expect(tags).toHaveLength(4); // hero note · tile · No-account-cap box · footer
  });

  it("the five section words are in-page anchors to sections that exist", () => {
    const html = renderHome();
    for (const id of ["why", "how", "included", "trust", "sizes"]) {
      expect(html, id).toContain(`href="#${id}"`);
      expect(html, id).toContain(`id="${id}"`);
    }
  });

  it("no other address leaves the page: every href is one of the named destinations", () => {
    const allowed = new Set([
      "#top", "#why", "#how", "#included", "#trust", "#sizes",
      "/signin-help", "/signup", WALKTHROUGH_URL, SUPPORT_PHONE_HREF,
    ]);
    for (const tag of anchors(renderHome())) {
      expect(allowed.has(hrefOf(tag) ?? ""), tag).toBe(true);
    }
  });
});

describe("what the page says (draft v6)", () => {
  it("What's included carries ELEVEN service chips — the sign-up wizard's own list", () => {
    const html = renderHome();
    const chips = html.match(/data-service-chip="/g) ?? [];
    expect(chips).toHaveLength(11);
    expect(SIGNUP_SERVICES).toHaveLength(11);
    for (const service of SIGNUP_SERVICES) {
      expect(html, service.code).toContain(`data-service-chip="${service.code}"`);
    }
    expect(html).toContain("Thermal / Heat");
    expect(html).toContain(">Fire<");
  });

  it("six benefits, six steps (Field work among them), four included cards beside the services", () => {
    const html = renderHome();
    expect(html.match(/data-public-benefit="/g) ?? []).toHaveLength(6);
    expect(html.match(/data-public-step="/g) ?? []).toHaveLength(6);
    expect(html).toContain('data-public-step="field"');
    expect(html.match(/data-public-card="/g) ?? []).toHaveLength(5);
    expect(html).toContain("40,009 accounts · $1,270,167.00 in one run");
  });

  it("the trust strip: exactly SOC 2 · NIST · 50+ integrations · Go-live support, no type, framework or hours", () => {
    const html = renderHome();
    const strip = /<ul[^>]*data-public-trust[^>]*>(.*?)<\/ul>/.exec(html)?.[1] ?? "";
    expect([...strip.matchAll(/<li[^>]*>(.*?)<\/li>/g)].map((m) => m[1])).toEqual([
      "SOC 2",
      "NIST",
      "50+ integrations",
      "Go-live support",
    ]);
    expect(html).not.toMatch(/Type I|Type II|NIST CSF|Mon–Fri/);
  });

  it("Secure, connected, supported: four tiles, and the Audit card no longer names QuickBooks", () => {
    const html = renderHome();
    expect(html).toContain("Safe to run your utility on.");
    expect(html.match(/data-public-tile="/g) ?? []).toHaveLength(4);
    expect(html).toContain("your accounting system");
    expect(html).not.toContain("QuickBooks");
  });

  it("three sizes, no prices, and No account cap (BR-TEN-002 · NFR-5)", () => {
    const html = renderHome();
    expect(html.match(/data-public-size="/g) ?? []).toHaveLength(3);
    expect(html).toContain("Up to 3,000");
    expect(html).toContain("3,000–10,000");
    expect(html).toContain("10,000–40,000");
    expect(html).toContain("No account cap.");
  });

  it("the draft's own review marker is not built", () => {
    expect(renderHome()).not.toContain("Draft for review");
  });

  it("DEF-573 the public nav does not reach into its own buttons", () => {
    const markup = renderHome();
    const nav = /<nav class="([^"]*)"/.exec(markup);
    expect(nav).not.toBeNull();
    expect(nav?.[1]).not.toMatch(/_a:not\(/);
    expect(markup).toContain("text-btn");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-018@011ac24 · DEF-TEN-4222 (reopened 2026-10-02)
// generated: 2026-08-09 by story-coder v1 · REWRITTEN 2026-10-02 (maintenance lane — the redraw: no prices, the PO's link destinations by address, eleven chips, the v6 trust content)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
