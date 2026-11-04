// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-7800 — Plans & Rates → edit a charge code → step 2. The
//          Product Owner, on `BASE-W-COM`: the Amount box "will not accept
//          typing, is outlined red, and shows no message", and "then why this
//          field is shown then - user is confuse".
// Rules:   BR-SHL-025 (a control that must not be used is PRESENT and
//          read-only WITH its reason) · BR-RAT-690 / DEF-2190 (a code priced
//          per size states no scalar) · CLAUDE.md hard rule 2 and BR-RAT-087
//          (money is never formatted in the browser) · B14 rule 33 · hard-won
//          law 6 (no gate reads rendered output) · law 7 (a check's output
//          must distinguish pass from fail TO A READER).
// ───────────────────────────────────────────────────────
//
// **WHY THIS SCRIPT EXISTS AND WHAT IT MEASURES THAT A DOM TEST CANNOT.**
//
// The red the Product Owner photographed is NOT a validation mark. It is the
// product's own accent focus ring — `:focus-visible { outline: 2px solid
// var(--color-accent) }` in `styles/global.css`, `#ec3013` — which appears the
// instant the box is clicked and which jsdom does not compute at all. So the
// reproduction has to be a real browser with the real stylesheet, and it has
// to CLICK the box rather than render it.
//
// It prints, for the box, before and after the click: the class list, the
// computed border colour, the computed outline, whether any `input-invalid`
// exists anywhere on the page, whether an error node exists, and the VALUE.
// Read those lines; the script asserts the two that decide it and says which.
//
//   node 10-scripts/def_rat_7800_amount_box_walkthrough.mjs
//
// Env: SMOKE_BASE · SMOKE_TENANT · SMOKE_EMAIL · SMOKE_PASSWORD · CHARGE_ID ·
//      SHOT_OUT · PW_CHROME
//
// ⚠ THE STACK MUST BE BUILT SAME-ORIGIN. `.env.production` bakes a remote API
// host into the bundle, so a default `vite build` gives a page whose every
// fetch is refused by its own content-security policy and whose wizard never
// loads. Build with a mode whose `VITE_API_BASE_URL` is EMPTY and serve it
// through `server.mjs` with `API_PROXY_TARGET` pointing at the backend — that
// join is the deployed shape (see `10-scripts/11-smoke-stack.sh`).
//
// ⚠ THE CHARGE CODE MUST BE PRICED PER SIZE. `seed_demo`'s `BASE-W-COM` is a
// FLAT $15.00 with no `charge_code_amounts` rows, so it reproduces nothing;
// the reproduction seeded six rows against it. If the box comes back editable
// this script SAYS SO rather than passing — an unreproduced defect is a
// finding, not a delay.

import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8942";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const CHARGE_ID = process.env.CHARGE_ID ?? "";
const OUT = process.env.SHOT_OUT ?? "/tmp/def-rat-7800-shots";
const EXE = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const notes = [];
const failures = [];
function note(line) {
  console.log(line);
  notes.push(line);
}
function fail(line) {
  failures.push(line);
  console.error(`  ✗ ${line}`);
  notes.push(`  ✗ ${line}`);
}

/** Everything a person could call "red", read off the RENDERED box. */
async function readBox(page) {
  return page.evaluate(() => {
    const box = document.getElementById("charge-amount");
    if (box === null) {
      return { present: false };
    }
    const style = getComputedStyle(box);
    return {
      present: true,
      focused: document.activeElement === box,
      value: box.value,
      readOnly: box.readOnly,
      classes: box.className,
      borderColor: style.borderColor,
      outline: `${style.outlineStyle} ${style.outlineWidth} ${style.outlineColor}`,
      ariaInvalid: box.getAttribute("aria-invalid"),
      ariaReadOnly: box.getAttribute("aria-readonly"),
      help: document.getElementById("charge-amount-help")?.textContent ?? "ABSENT",
      errorNode: document.getElementById("charge-amount-error")?.textContent ?? "ABSENT",
      invalidAnywhere: [...document.querySelectorAll(".input-invalid")].map((one) => one.id),
      mode: (document.getElementById("charge-amount-rule") ?? {}).value ?? "ABSENT",
    };
  });
}

async function shot(page, name, width) {
  await page.setViewportSize({ width, height: 1100 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
  note(`  shot ${name}-${width}.png`);
}

async function main() {
  if (CHARGE_ID === "") {
    console.error("CHARGE_ID is required — the charge code this walk opens.");
    return 2;
  }
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 1100 } })).newPage();

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
  note(`signed in as ${EMAIL}; landed on ${page.url()}`);
  const version = await page.locator("text=/v?2\\.\\d+\\.\\d+/").first().textContent().catch(() => null);
  note(`version on screen: ${version ?? "NOT FOUND — reported rather than assumed"}`);

  await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${CHARGE_ID}/edit`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector('button:has-text("Continue")', { timeout: 20000 });
  await page.waitForTimeout(1200);
  note(`step 1: ${(await page.locator("h1").first().textContent())?.trim()}`);
  await page.locator('button:has-text("Continue")').last().click();
  await page.waitForTimeout(1500);

  const before = await readBox(page);
  note("STEP 2, AS LOADED:");
  note(`  ${JSON.stringify(before)}`);
  if (before.present !== true) {
    fail("there is no Amount box on step 2 — the walk cannot say anything about it");
    writeFileSync(`${OUT}/00-README.txt`, notes.join("\n"));
    await browser.close();
    return 1;
  }
  if (before.readOnly !== true) {
    fail(
      "the Amount box is EDITABLE, so this charge code is not priced per size and the " +
        "defect is NOT REPRODUCED here. Seed rows into charge_code_amounts first.",
    );
  }

  // THE PRODUCT OWNER'S OWN ACT — click it, then type into it.
  await page.locator("#charge-amount").click();
  await page.waitForTimeout(400);
  const focused = await readBox(page);
  note("AFTER THE CLICK (this is where the red comes from):");
  note(`  ${JSON.stringify(focused)}`);
  await shot(page, "01-amount-focused", 1440);
  await page.keyboard.type("99");
  await page.waitForTimeout(400);
  const typed = await readBox(page);
  note(`AFTER TYPING "99": value = ${JSON.stringify(typed.value)}`);
  await shot(page, "02-after-typing", 1440);
  await shot(page, "03-step-two", 1280);

  // ── the two things that decide it ────────────────────────────────────────
  if (typed.value.trim() === "") {
    fail("the Amount box is still EMPTY — the whole complaint was that it says nothing");
  } else {
    note(`  ✓ the box STATES something: ${JSON.stringify(typed.value)}`);
  }
  if (typed.classes.includes("input-invalid") || typed.ariaInvalid === "true") {
    fail("the Amount box is marked INVALID — a clerk cannot fix a box they cannot type in");
  } else {
    note("  ✓ the box is not marked invalid (no input-invalid, no aria-invalid)");
  }
  if (typed.errorNode !== "ABSENT") {
    fail(`an error node is rendered under a read-only box: ${JSON.stringify(typed.errorNode)}`);
  } else {
    note("  ✓ no error node under it");
  }
  if (typed.help === "ABSENT") {
    fail("the reason line is gone — BR-SHL-025 wants the reason WITH the read-only control");
  } else {
    note(`  ✓ its reason is still under it: ${JSON.stringify(typed.help)}`);
  }
  if (typed.value !== before.value) {
    fail("typing CHANGED the read-only box — a per-size code must state no scalar");
  } else {
    note("  ✓ typing changed nothing, which is BR-RAT-690 and is correct");
  }
  note(
    "  note — the red the reporter saw is the FOCUS RING: outline " +
      `${focused.outline} (var(--color-accent)), not a validation border. ` +
      `The border stayed ${focused.borderColor}.`,
  );

  writeFileSync(`${OUT}/00-README.txt`, notes.join("\n"));
  await browser.close();
  if (failures.length > 0) {
    console.error(`\nFAILED — ${failures.length} finding(s); see ${OUT}/00-README.txt`);
    return 1;
  }
  console.log(`\nPASSED — 5 of 5 checks; shots and notes in ${OUT}`);
  return 0;
}

main()
  .then((code) => process.exit(code))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
