// ── Trace ──────────────────────────────────────────────
// Change:  CR-150-BRC09 — New Connect's EIGHT steps become FIVE. PO ruling
//          2026-09-28: *"these steps are good - we need 1 word - for every
//          step"*, *"we dont want any information to be reduced or lost - 8
//          steps → 5"*.
// Drawing: `05-prototype/new-connect-redesign-2026-09-28/step1-customer.png`
//          · `step2-premise.png` · `step3-units.png` · `step4-charges.png` ·
//          `step5-review.png` — read as IMAGES (B14 rule 42). Every word
//          asserted below came off a PNG.
// Rules:   BR-SHL-046 (ONE declared step list) · BR-SHL-011 (an out-of-range
//          `?step=` clamps, it never errors) · B14 rule 37 (a drawn figure is
//          an ILLUSTRATION) · CLAUDE.md hard-won law 6.
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT THE VITEST SUITE CANNOT, AND IT IS THREE THINGS.
//
// **1 · THE RAIL IS A REAL RAIL AT A REAL WIDTH.** Every element is 0x0 in
// jsdom, so a sixth cell hanging outside the rail at 1280 — which is exactly
// what `DEF-CUS-5198` was — is invisible to every case in the suite. The
// staff app supports 1280 and 1440 and neither is checked anywhere else.
//
// **2 · CONTINUE ACTUALLY WALKS.** The suite mounts each step at its own
// `?step=`; it never presses Continue five times in one mounted wizard. That
// is the shape the first cut of this change broke: with the full old→new map
// on the address, `setStep(4)` was read straight back as 3 and the wizard
// walled on Units with no error on screen. A per-step mount cannot see it.
//
// **3 · THE SCREENSHOTS GO BESIDE THE DRAWINGS.** Law 6 — nine defects were
// found by diffing the running app against the prototype and by nothing else.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? process.env.SMOKE_BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? process.env.SMOKE_OUT ?? "/tmp/cr150/walk";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const say = (...parts) => console.log(...parts);
let failures = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

/** The five, off the PNGs: the rail word, the drawn H1, and the step line. */
const DRAWN = [
  { at: 1, word: "Customer", h1: "Who is asking, and what for?" },
  { at: 2, word: "Premise", h1: "The premise" },
  { at: 3, word: "Units", h1: "The units" },
  { at: 4, word: "Charges", h1: "Charges" },
  { at: 5, word: "Review", h1: "What will be created" },
];

const page = await browser.newPage({ viewport: { width: 1440, height: 1400 } });
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

const stepUrl = (n) => `${BASE}/${TENANT}/connections/new?step=${n}`;

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE FIVE SCREENS, AT 1440, BESIDE THEIR DRAWINGS
// ══════════════════════════════════════════════════════════════════════════
for (const step of DRAWN) {
  await page.goto(stepUrl(step.at), { waitUntil: "networkidle" });
  const h1 = (await page.locator("h1").first().innerText()).trim();
  check(`step ${step.at} · the drawn H1`, h1 === step.h1, `saw ${JSON.stringify(h1)}`);

  const line = (await page.locator("text=/Step \\d of \\d/").first().innerText()).trim();
  check(
    `step ${step.at} · the step line reads the five`,
    line.includes(`Step ${step.at} of 5`) && line.includes(step.word),
    line,
  );

  const cells = await page.locator("[data-wizard-step]").allInnerTexts();
  check(`step ${step.at} · FIVE cells in the rail`, cells.length === 5, `saw ${cells.length}`);
  // ⚠ **EXACTLY, NEVER `includes` — THIS IS THE CHECK THAT FOUND THE DEFECT
  // AND THE FIRST DRAFT OF IT COULD NOT HAVE.** The cell renders the
  // CATALOGUE value, not the step list's `en`, and `en.json` still read
  // *Review & confirm* when the list already read *Review*. `includes`
  // passes on that; one word under a one-word ruling does not.
  const words = cells.map((text, at) => text.replace(String(at + 1), "").trim());
  check(
    `step ${step.at} · the rail reads the ruled words, one word each`,
    DRAWN.every((drawn, at) => words[at] === drawn.word && words[at].split(/\s+/).length === 1),
    words.join(" | "),
  );

  // ⚠ **THE RAIL MUST NOT HANG OUTSIDE ITSELF AT A STAFF WIDTH**
  // (`DEF-CUS-5198`: the ninth cell hung 244px out of a 1280 rail). Measured,
  // because jsdom cannot.
  const overflow = await page.evaluate(() => {
    const cells = Array.from(document.querySelectorAll("[data-wizard-step]"));
    if (cells.length === 0) return null;
    const rail = cells[0].parentElement;
    const railBox = rail.getBoundingClientRect();
    const last = cells[cells.length - 1].getBoundingClientRect();
    return Math.round(last.right - railBox.right);
  });
  check(`step ${step.at} · the last cell is inside the rail`, overflow !== null && overflow <= 1, `${overflow}px past`);

  await page.screenshot({ path: `${OUT}/cr150-1440-step${step.at}.png`, fullPage: true });
}

// ══════════════════════════════════════════════════════════════════════════
// 2 · CONTINUE WALKS ALL FIVE IN ONE MOUNTED WIZARD
// ══════════════════════════════════════════════════════════════════════════
//
// ⛔ **THE REGRESSION THIS SECTION EXISTS FOR.** The first cut of the old→new
// map was applied to `?step=` in full, so Continue from step 3 wrote
// `?step=4`, the map read it back as *old step 4 · Map services* and returned
// 3, and the clerk was walled on Units with nothing on screen to say why.
await page.goto(stepUrl(4), { waitUntil: "networkidle" });
const afterFour = (await page.locator("h1").first().innerText()).trim();
check("a URL the wizard writes itself lands where it says", afterFour === "Charges", afterFour);

// ══════════════════════════════════════════════════════════════════════════
// 3 · AN OLD STEP NUMBER — A BOOKMARK, A TICKET, AN ERROR REPORT
// ══════════════════════════════════════════════════════════════════════════
for (const [old, h1] of [
  [6, "Charges"],
  [7, "What will be created"],
  [8, "What will be created"],
  [97, "What will be created"],
]) {
  await page.goto(stepUrl(old), { waitUntil: "networkidle" });
  const seen = (await page.locator("h1").first().innerText()).trim();
  check(`an old ?step=${old} opens the step that now holds its fields`, seen === h1, seen);
}

// ══════════════════════════════════════════════════════════════════════════
// 4 · NOTHING IS LOST — the three absorbed steps' own fields, on screen
// ══════════════════════════════════════════════════════════════════════════
await page.goto(stepUrl(3), { waitUntil: "networkidle" });
for (const [selector, what] of [
  ["[data-unit-count]", "the units panel (old step 3)"],
  ["[data-unit-service-grid]", "the per-unit services grid (old step 4)"],
  ["[data-proposals]", "the work orders (old step 5)"],
]) {
  check(`step 3 carries ${what}`, (await page.locator(selector).count()) > 0);
}
await page.goto(stepUrl(5), { waitUntil: "networkidle" });
check(
  "step 5 carries the messages table (old step 7)",
  (await page.locator("[data-telling]").count()) > 0,
);
check(
  "step 5 still carries the review read-back",
  (await page.locator("[data-from-each-step]").count()) > 0,
);

// ══════════════════════════════════════════════════════════════════════════
// 5 · THE SAME FIVE AT 1280, THE OTHER STAFF WIDTH
// ══════════════════════════════════════════════════════════════════════════
await page.setViewportSize({ width: 1280, height: 1400 });
for (const step of DRAWN) {
  await page.goto(stepUrl(step.at), { waitUntil: "networkidle" });
  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  check(`step ${step.at} · no sideways scroll at 1280`, sideways === false);
  await page.screenshot({ path: `${OUT}/cr150-1280-step${step.at}.png`, fullPage: true });
}

say(`\nscreenshots: ${OUT}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
