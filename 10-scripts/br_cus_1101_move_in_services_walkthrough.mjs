// ── THE MOVE-IN'S SERVICES STEP, WALKED IN A BROWSER ──────────────────────
//
// `BR-CUS-1101` (PO ruling 2026-09-25) · the account takes a SUBSET of its
// unit's service points. Run it after any change to `MoveInWizard.tsx`,
// `moveShared.MOVE_IN_STEPS` or `newConnectStepKit.ServiceTicks`.
//
// **WHAT IT IS FOR, AND WHY A UNIT TEST CANNOT DO IT.** No gate in this repo
// reads rendered output (hard-won law 6). The three things below all pass
// `tsc` and every suite while being wrong on screen: a step that is declared
// and never mounted, a tick-list that renders with nothing ticked, and — the
// one filed three times on these wizards already — a **required choice whose
// Continue does nothing at all** when it is empty.
//
// ⚠ **THE SCREENSHOTS ARE md5'd AND COMPARED.** A previous lane captured two
// different wizard steps and got byte-identical files, because Continue
// silently no-opped and both captures were the same screen. Two captures with
// different names and one digest is therefore a FAILURE here, not a curiosity.
//
//   MVS_BASE     default http://127.0.0.1:8972
//   MVS_TENANT   default brazosbend
//   MVS_UNIT     the vacant unit with six service points (required)
//   MVS_EMAIL / MVS_PASSWORD   a billing clerk or system admin
//   MVS_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//   MVS_SHOTS    where the PNGs land
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const BASE = process.env.MVS_BASE || "http://127.0.0.1:8972";
const T = process.env.MVS_TENANT || "brazosbend";
const UNIT = process.env.MVS_UNIT || "";
const EMAIL = process.env.MVS_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MVS_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MVS_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.MVS_SHOTS || ".";

let pass = 0;
let fail = 0;
function ok(what, cond, detail = "") {
  if (cond) { pass += 1; console.log(`  ✓ ${what}`); }
  else { fail += 1; console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`); }
}

const digests = new Map();
async function shot(page, name) {
  const path = `${SHOTS}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  const md5 = createHash("md5").update(readFileSync(path)).digest("hex");
  for (const [other, seen] of digests) {
    if (seen === md5) {
      // ⚠ THE CHECK THAT MATTERS. Identical bytes under two names means the
      // walk photographed one screen twice and every later assertion is about
      // a page it never reached.
      ok(`${name} is a DIFFERENT screen from ${other}`, false, `both md5 ${md5}`);
      digests.set(name, md5);
      return md5;
    }
  }
  digests.set(name, md5);
  console.log(`    · ${name}.png md5 ${md5}`);
  return md5;
}

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const p = await ctx.newPage();
  p.setDefaultTimeout(25000);
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);

  console.log("\n── 1 · step 1, the unit ──────────────────");
  await p.goto(`${BASE}/${T}/move-ins/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  // Choose the seeded six-service unit in the picker.
  const picker = p.locator("select#mvi_unit").first();
  if ((await picker.count()) > 0) {
    await picker.selectOption(UNIT);
  } else {
    const box = p.locator("input#unit_id, input[name='unit_id']").first();
    await box.fill(UNIT);
  }
  await p.waitForTimeout(2500);
  ok("the rail draws SEVEN steps", (await p.locator("[data-wizard-step]").count()) === 7);
  // ⚠ **READ OFF THE DECLARED LIST'S OWN LABEL, CASE AND ALL.** The label was
  // renamed from `Services` to `Which services` after this walk first passed,
  // and a `.includes("Services")` written against the old casing would have
  // gone red for a rename rather than for a defect — or, worse, passed over a
  // rail that had lost the step entirely if the casing had gone the other way.
  ok("step 2 of the rail is the services step",
    (await p.locator('[data-wizard-step="2"]').innerText()).toLowerCase().includes("services"));
  await shot(p, "mvs-1-unit");

  console.log("\n── 2 · the services step, all chosen ────────");
  await p.locator("button", { hasText: /^Continue/ }).first().click();
  await p.waitForTimeout(2000);
  // ⚠ **CHIPS, NOT CHECKBOXES (B14 rule 9).** The first draft of this walk
  // drove `input[type=checkbox]`, because the first draft of the step WAS a
  // wall of checkboxes — which rule 9 forbids by name and which rule 36 breach
  // (e) records the PO complaining about on another screen. It is the kit's
  // `ChipMultiSelect` now, and this asserts the absence as well as the presence.
  const group = p.locator('[data-chip-select="move-in-services"]');
  const chips = group.locator("[data-chip]");
  const boxes = p.locator('input[type="checkbox"]');
  ok("it is NOT a wall of checkboxes (B14 rule 9)", (await boxes.count()) === 0,
    `${await boxes.count()} checkboxes on the step`);
  const n = await chips.count();
  ok("the unit's six services are chosen", n === 6, `saw ${n}`);
  await shot(p, "mvs-2-services-all");

  console.log("\n── 3 · empty, and Continue must SAY SO ─────");
  // ⚠ **THE CHIP IS A `<span>`; ITS REMOVE IS THE `×` BUTTON INSIDE IT.**
  // Clicking the chip itself does nothing — which the first run of this walk
  // read as "removed", because it then asserted on the CONSEQUENCE instead of
  // on the count. It asserts the count now, before going on.
  for (let guard = 0; guard < 10 && (await chips.count()) > 0; guard += 1) {
    await group.locator("[data-chip-remove]").first().click();
    await p.waitForTimeout(250);
  }
  ok("every chip can be removed", (await chips.count()) === 0);
  const before = p.url();
  await p.locator("button", { hasText: /^Continue/ }).first().click();
  await p.waitForTimeout(1500);
  ok("Continue did not advance", p.url() === before, p.url());
  const body = await p.locator("body").innerText();
  // ⚠ **THE ONE THIS WALK EXISTS FOR.** A required choice whose Continue
  // changes NOTHING on screen has been filed three times on these wizards.
  ok("and it says why, at the button", body.includes("Choose at least one service"));
  await shot(p, "mvs-3-services-empty");

  console.log("\n── 4 · three of six, added back ────────");
  // The way BACK matters as much as the way out: a clerk who removes one by
  // mistake must be able to put it back without leaving the step.
  const add = group.locator('[data-chip-add="move-in-services"]');
  for (const label of ["Electric", "Water", "Trash"]) {
    await add.selectOption({ label });
    await p.waitForTimeout(500);
  }
  const now = await chips.count();
  ok("exactly three are chosen", now === 3, `${now}`);
  await shot(p, "mvs-4-services-three");
  await p.locator("button", { hasText: /^Continue/ }).first().click();
  await p.waitForTimeout(1500);
  ok("Continue advances once one is chosen", p.url() !== before, p.url());
  await shot(p, "mvs-5-after-continue");

  console.log("\n── 5 · 1280 ───────────────────────");
  await p.setViewportSize({ width: 1280, height: 1000 });
  await p.locator("button", { hasText: /^Back/ }).first().click();
  await p.waitForTimeout(1500);
  const wide = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  ok("no horizontal scroll at 1280", !wide);
  await shot(p, "mvs-6-services-1280");
} catch (err) {
  fail += 1;
  console.log("  \u2717 the walk threw \u2014 " + (err && err.message));
} finally {
  await browser.close();
  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail === 0 ? 0 : 1);
}
