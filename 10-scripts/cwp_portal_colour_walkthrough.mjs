// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CWP-3736 — the customer portal rendered in the PRODUCT's accent
//          rather than the utility's own. Found by the Product Owner opening
//          the live page; found by nothing else, because no gate in this repo
//          reads rendered output (CLAUDE.md hard-won law 6).
// Rules:   PO ruling 2026-09-04, verbatim: "default will be our style guide and
//          then we will allow utility users to change it" — so a utility with
//          no colour must render r10's #ec3013, never grey.
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS MEASURES, IT DOES NOT ASSERT A CLASS NAME.** The whole reason
// DEF-CWP-3736 survived every check is that the tests asked whether a style
// ATTRIBUTE was present — it was — and never whether a rule consumed it. So
// this reads `getComputedStyle` out of a real engine, which is the one
// instrument that can answer "is this button the right colour".
//
// ⚠ **AND THE FIXTURE HEX IS DELIBERATELY NOT #EC3013.** The sample utility's
// brand_primary_hex is #EC3013 and the theme's --color-accent is #ec3013 — the
// same colour to the byte — so on the standard fixture a button painted with
// the product's constant and one painted with the tenant's hex are identical
// pixels. Only a colour that is not ours can tell them apart.
//
//   Start the app first, then:
//     node 10-scripts/cwp_portal_colour_walkthrough.mjs [baseUrl]
//   Default baseUrl is http://localhost:5173 (vite dev).
//   E2E_CHROMIUM_EXECUTABLE points at a pre-provisioned Chromium where the
//   sandbox cannot reach cdn.playwright.dev — same escape hatch as
//   playwright.config.ts.

import { createRequire } from "node:module";

// Reached the way `12-smoke-walkthrough.mjs` next door reaches it: resolved
// from the frontend's own package.json, because ESM ignores NODE_PATH and this
// script lives outside 07-frontend.
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.argv[2] ?? process.env.E2E_BASE_URL ?? "http://localhost:5173";
const TENANT = "silver-creek-water1";
const TENANT_HEX = "#0F7B6C"; // a teal no theme token holds
const THEME_ACCENT = "rgb(236, 48, 19)"; // r10's #ec3013, the style-guide default

function front(brandPrimaryHex) {
  return {
    tenant: {
      slug: TENANT,
      name: "Silver Creek Water",
      brand_primary_hex: brandPrimaryHex,
      brand_accent_hex: "#B45309", // served, deliberately unread — DEF-CWP-3737
    },
    is_live: true,
    cards: ["pay_bill", "report_problem", "start_service", "what_things_cost", "help_answers"],
    links: { help: true, visit: true },
    switches: {
      quick_pay_enabled: true,
      self_read_enabled: true,
      plans_enabled: true,
      requests_enabled: true,
      outage_reporting_enabled: true,
    },
    services: [{ code: "water", name: "Water", color: "#2563EB" }],
    strapline: "Water for the valley since 1948.",
    office_hours_text: "Mon-Fri 8:00am-4:30pm",
    emergency_phone: "(512) 555-0134",
  };
}

const failures = [];
function check(label, actual, expected) {
  const ok = actual === expected;
  console.log(`  ${ok ? "ok  " : "FAIL"}  ${label.padEnd(46)} ${actual}${ok ? "" : `   (wanted ${expected})`}`);
  if (!ok) failures.push(`${label}: ${actual}, wanted ${expected}`);
}

const browser = await chromium.launch({
  executablePath: process.env.E2E_CHROMIUM_EXECUTABLE || undefined,
});

async function measure(hex, path) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.route(`**/api/${TENANT}/**`, (route) =>
    route.request().url().includes("/portal/public/front")
      ? route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(front(hex)) })
      : route.fulfill({ status: 200, contentType: "application/json", body: '{"results":[],"count":0}' }),
  );
  await page.goto(`${BASE}/${TENANT}/portal${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const out = await page.evaluate(() => {
    const cs = (sel, prop) => {
      const el = document.querySelector(sel);
      return el ? getComputedStyle(el).getPropertyValue(prop).trim() : "(no element)";
    };
    return {
      primaryBg: cs('[data-variant="primary"]', "background-color"),
      primaryFg: cs('[data-variant="primary"]', "color"),
      // The hover step: overriding only the base leaves a teal button that
      // turns the product's red under the pointer.
      accent600: getComputedStyle(document.querySelector('[data-portal-frame="guest"]'))
        .getPropertyValue("--color-accent-600").trim() || "(unset)",
      // ⚠ THE INLINE DECLARATION, NOT THE COMPUTED VALUE — and the difference
      // is the whole mechanism. `getComputedStyle` INHERITS, so an unbranded
      // frame reports #ec3013 from `:root` and cannot tell "the tenant set
      // ours" from "nobody set anything and the style guide won". Only
      // `element.style` says which of those happened.
      frameAccentInline: document
        .querySelector('[data-portal-frame="guest"]')
        .style.getPropertyValue("--color-accent") || "(not written)",
      frameAccentComputed: getComputedStyle(document.querySelector('[data-portal-frame="guest"]'))
        .getPropertyValue("--color-accent").trim() || "(unset)",
      brand: document
        .querySelector('[data-portal-frame="guest"]')
        .style.getPropertyValue("--brand") || "(not written)",
    };
  });
  await page.close();
  return out;
}

console.log(`\n── a utility WITH a colour of its own (${TENANT_HEX}) ─────────────────`);
const branded = await measure(TENANT_HEX, "/report");
check("primary button background", branded.primaryBg, "rgb(15, 123, 108)");
check("--color-accent written on the frame", branded.frameAccentInline, TENANT_HEX);
check("--brand (deleted, nothing read it)", branded.brand, "(not written)");
console.log(`  note  hover step --color-accent-600 = ${branded.accent600}`);

console.log(`\n── a utility with NO colour: the style guide is the default ──────────`);
console.log(`   PO 2026-09-04: "default will be our style guide and then we will`);
console.log(`   allow utility users to change it" — so this must be r10's red,`);
console.log(`   never grey, and it must get there by NOTHING being written.`);
const bare = await measure(null, "/report");
check("primary button background", bare.primaryBg, THEME_ACCENT);
check("--color-accent written on the frame", bare.frameAccentInline, "(not written)");
// It gets the style guide's value by INHERITANCE, which is why nothing had to
// be written: `tokens.css` declares it at `:root` and the frame overrode
// nothing. That is the ruling's mechanism, measured.
check("--color-accent inherited from :root", bare.frameAccentComputed, "#ec3013");

await browser.close();
console.log("");
if (failures.length > 0) {
  console.log(`${failures.length} measurement(s) wrong:`);
  for (const f of failures) console.log("  -", f);
  process.exit(1);
}
console.log("every measured colour is the one the ruling asks for.");
