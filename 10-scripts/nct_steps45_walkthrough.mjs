// ── Trace ──────────────────────────────────────────────
// Change:  `CR-150-BRC09` tasks 11–14 — **THE BROWSER WALK FOR STEP 4 ·
//          CHARGES AND STEP 5 · REVIEW**, against the drawings
//          `05-prototype/new-connect-redesign-2026-09-28/step4-charges.png`
//          and `step5-review.png`.
// Rules:   CLAUDE.md hard-won law 6 — **no gate in this repo reads rendered
//          output**, so this script and a person are the only things that can
//          say whether the screen is the screen we agreed · hard rule 2 (no
//          money is multiplied, summed or rounded in a browser) · B14 rule 44
//          (staff screens are built at 1440 and must work at 1280)
// ───────────────────────────────────────────────────────
//
// WHAT IT DOES THAT THE VITEST FILE CANNOT
// ----------------------------------------
// `NewConnectRedesignSteps45.dom.test.tsx` renders to a string. **Every
// element in it is zero by zero**, so it cannot see a strip that wraps, a
// column out of alignment or a footer off the page. This drives a real
// Chromium at the two widths B14 requires of a staff screen, takes the
// screenshots that go beside the drawings, and — the part no DOM test can do
// — **reads every money figure OFF THE RENDERED PAGE and checks that each one
// was served rather than computed.**
//
// ⚠ **THE MONEY CHECK IS THE ONE THAT MATTERS AND IT IS WRITTEN TO BE ABLE TO
// FAIL** (law 7, habit 2). It scrapes every `$…` on the page and compares the
// set against what the server sent over the wire — every `/connections/
// quote-preview` response is captured — plus the clerk's own typed string.
// **A figure on screen that is in neither set is arithmetic this browser did**,
// which is `DEF-088` and `DEF-127`, and it is reported by value.
//
// RUN:  BASE=http://127.0.0.1:8718 node 10-scripts/nct_steps45_walkthrough.mjs
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright-core");

const BASE = process.env.BASE || "http://127.0.0.1:8718";
const T = process.env.TENANT || "brazosbend";
const EMAIL = process.env.EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
// ⚠ NEVER `playwright install` — the browser is already in the image.
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OUT = process.env.OUT || "/tmp/claude-0/nct45-shots";
mkdirSync(OUT, { recursive: true });

const findings = [];
const notes = [];
const say = (...a) => console.log(...a);

const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1400 } });
const page = await ctx.newPage();

// ── EVERY MONEY FIGURE THE SERVER SENT ──────────────────────────────────────
// Captured off the wire rather than inferred, so the comparison below is
// between what was SERVED and what is DRAWN, which is the only pair that can
// tell an honest figure from a computed one.
const served = new Set();
page.on("response", async (r) => {
  const p = new URL(r.url()).pathname;
  if (!/\/connections\/quote-preview$|\/connections\/commit$/.test(p)) return;
  let body = "";
  try {
    body = await r.text();
  } catch {
    return;
  }
  for (const hit of body.matchAll(/"(?:stored|display|total|amount|unit_price)"\s*:\s*"([0-9.]+)"/g)) {
    served.add(Number(hit[1]).toFixed(2));
  }
});

const browserNoise = [];
// ⚠ **`frame-ancestors` IS SOMEBODY ELSE'S AND IT IS DATED.** The dev
// server sends its CSP on a `<meta>`, where that one directive is ignored by
// spec, so Chromium warns ONCE PER NAVIGATION — 15 identical lines in a walk
// that visits 15 pages. It comes from `07-frontend/server.mjs`, added in
// `c6caadf2f` on **2026-09-22** by another lane (`git log -S "frame-ancestors
// 'self'"`), and it says nothing about steps 4 or 5.
//
// ⚠ **IT WAS COUNTED AS A FINDING, WHICH PINNED THIS WALK'S EXIT CODE AT 1
// FOREVER** — a check that can never report success is a check nobody can
// use to tell a good run from a bad one (hard-won law 7, habit 3). It is
// matched BY ITS EXACT DIRECTIVE NAME rather than by widening the pattern:
// a broad `CSP` or `ignored` clause here would swallow a real policy error
// later, which is habit 2's question — what would make this pass wrongly?
const NOT_OURS =
  /ERR_CERT_AUTHORITY_INVALID|ERR_PROXY|ERR_NAME_NOT_RESOLVED|favicon|directive 'frame-ancestors' is ignored/i;
page.on("console", (m) => {
  if (m.type() !== "error") return;
  const text = m.text().slice(0, 140);
  (NOT_OURS.test(text) ? browserNoise : findings).push(`console: ${text}`);
});
page.on("pageerror", (e) => findings.push(`PAGEERROR ${e.message.slice(0, 160)}`));

/**
 * ⚠ **`fullPage: true` IS NOT ENOUGH HERE, AND IT FAILS SILENTLY.** It grows
 * the DOCUMENT; this app scrolls an INNER container (the shell's main region),
 * so the document stays exactly one viewport tall and every capture came back
 * `1440x1400` — one window of a Review screen thousands of pixels long, with
 * no error and nothing in the output to say so. Worse, the walk clicks
 * `+ Add template` before shooting, which scrolls that container, so the
 * picture did not even start at the top of the screen.
 *
 * **This is hard-won law 6's whole point turned against itself:** the
 * screenshot is the only artefact that diffs the running app against the
 * drawing, and a cropped one compares the drawing with a third of the screen
 * and reports agreement. It is also law 7's fifth shape — a check reporting
 * over a scope it silently excludes.
 *
 * So: scroll every scrollable element back to the top, measure the tallest
 * scroll height on the page, grow the VIEWPORT to fit it, and only then
 * shoot. The height is reported beside the file so a truncated capture is
 * visible in the log rather than only in the pixels.
 */
async function shot(tag) {
  await page.waitForTimeout(400);
  const width = page.viewportSize().width;
  const need = await page.evaluate(() => {
    let tallest = document.documentElement.scrollHeight;
    for (const el of document.querySelectorAll("*")) {
      if (el.scrollHeight > el.clientHeight + 4) {
        el.scrollTop = 0;
        const box = el.getBoundingClientRect();
        tallest = Math.max(tallest, Math.ceil(box.top + el.scrollHeight));
      }
    }
    window.scrollTo(0, 0);
    return tallest;
  });
  // Capped so a runaway virtualised list cannot ask for a 60,000px PNG.
  const height = Math.min(Math.max(need + 40, 1400), 9000);
  await page.setViewportSize({ width, height });
  await page.waitForTimeout(300);
  const file = `${OUT}/${tag}.png`;
  await page.screenshot({ path: file, fullPage: true });
  say(`  shot ${file} (${width}x${height}${height < need ? " ⚠ TRUNCATED" : ""})`);
  await page.setViewportSize({ width, height: 1400 });
  return file;
}

/** Every `$…` figure the page DRAWS, normalised to two decimals. */
async function drawnMoney() {
  const text = await page.evaluate(() => document.body.innerText);
  return [...text.matchAll(/\$([0-9][0-9,]*\.[0-9]{2})/g)].map((m) =>
    Number(m[1].replace(/,/g, "")).toFixed(2),
  );
}

// ── SIGN IN ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
say(`signed in as ${EMAIL}`);

// ── DRIVE TO THE CHARGES STEP ───────────────────────────────────────────────
// ⚠ **THE STEP NUMBER IS READ OFF THE PAGE, NEVER ASSUMED.** The five-step
// restructure is landing lane by lane, so a walk that hardcoded `?step=4`
// would silently open a different screen and pass — law 7's *looking at the
// wrong thing*, and the exact defect a hold-expiry test once had.
async function stepLine() {
  return await page.evaluate(() => {
    const hit = [...document.querySelectorAll("*")]
      .map((n) => (n.childElementCount === 0 ? n.textContent || "" : ""))
      .find((t) => /Step \d+ of \d+/.test(t));
    return (hit || "").trim();
  });
}

async function openStepWith(marker, label) {
  for (let step = 1; step <= 9; step += 1) {
    await page.goto(`${BASE}/${T}/connections/new?step=${step}`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForTimeout(700);
    if (await page.$(marker)) {
      say(`  ${label} is at ?step=${step} — "${await stepLine()}"`);
      return step;
    }
  }
  findings.push(`${label}: no step in 1..9 renders ${marker}`);
  return null;
}

say("\n══ STEP 4 · CHARGES ══");
const chargesStep = await openStepWith("[data-build-context]", "Charges");
if (chargesStep !== null) {
  // 1 · THE CONTEXT STRIP — seven cells, and each must hold a VALUE.
  const cells = await page.$$eval("[data-context-value]", (ns) =>
    ns.map((n) => `${n.getAttribute("data-context-value")}=${n.innerText.trim().slice(0, 40)}`),
  );
  say(`  context strip: ${cells.length} cells`);
  for (const c of cells) say(`    ${c}`);
  if (cells.length !== 7) findings.push(`context strip drew ${cells.length} cells, drawing has 7`);

  // 2 · BILLED TO — one select, three options, two of them unselectable.
  const payer = await page.$$eval("#nc_quote_payer option", (ns) =>
    ns.map((n) => `${n.value}${n.disabled ? " (disabled)" : ""}`),
  );
  say(`  billed to: ${payer.join(" · ")}`);
  if (payer.length !== 3) findings.push(`Who is billed drew ${payer.length} options, drawing has 3`);

  // 3 · BILLING PREFERENCES — present, and the two boxes refuse until exempt.
  for (const id of ["#nc_autopay", "#nc_tax_exempt", "#nc_tax_exempt_ref", "#nc_tax_exempt_expires"]) {
    if (!(await page.$(id))) findings.push(`billing preferences: ${id} is not on the screen`);
  }
  const refBefore = await page.$eval("#nc_tax_exempt_ref", (n) => n.disabled).catch(() => null);
  // ⚠ **CLICK THE LABEL, NOT THE INPUT — AND DO NOT SWALLOW THE FAILURE.**
  // `CheckboxField` renders its `<input>` as `peer sr-only`: it is a real,
  // focusable, keyboard-operable checkbox with ZERO SIZE, and the visible box
  // is the `<span data-checkbox-mark>` its `peer-checked:` rules paint. So
  // `page.click("#nc_tax_exempt")` fails Playwright's actionability check
  // every single time — the element is not visible.
  //
  // ⚠ **THIS LINE USED TO READ `.catch(() => undefined)` AND THAT IS THE BUG
  // WORTH RECORDING (hard-won law 7: what would make this check fail
  // wrongly?).** The swallowed click left the box unticked, the certificate
  // field correctly stayed disabled, and the walk then reported
  // *"tax-exempt boxes did not follow the tick"* — a CORRECT screen accused by
  // its own proof. A check whose failure path and whose subject's failure path
  // print the same sentence cannot tell you which one broke.
  let tickFailed = null;
  try {
    await page.click('label[for="nc_tax_exempt"]');
  } catch (err) {
    tickFailed = String(err).split("\n")[0];
  }
  if (tickFailed !== null) findings.push(`the walk could not tick Tax exempt: ${tickFailed}`);
  await page.waitForTimeout(200);
  const refAfter = await page.$eval("#nc_tax_exempt_ref", (n) => n.disabled).catch(() => null);
  say(`  certificate number disabled: before=${refBefore} after ticking exempt=${refAfter}`);
  if (tickFailed === null && (refBefore !== true || refAfter !== false)) {
    findings.push(`tax-exempt boxes did not follow the tick (${refBefore} -> ${refAfter})`);
  }

  // 4 · `check`, NEVER `cheque` — PO ruling 2026-09-29.
  const body = await page.evaluate(() => document.body.innerText);
  if (/cheque/i.test(body)) findings.push("the word CHEQUE is on step 4 — PO ruled `check`");

  // 5 · THE FOOTER — three rows, and Remaining carries NO figure.
  for (const sel of ["[data-charge-total]", "[data-charge-paid]", "[data-charge-remaining]"]) {
    if (!(await page.$(sel))) findings.push(`charges footer: ${sel} is missing`);
  }
  if (!(await page.$("[data-charge-remaining-absent]"))) {
    findings.push("⚠ REMAINING CARRIES A FIGURE — that is Total − Paid now, hard rule 2");
  }

  // 6 · ⚠ **THE MONEY CHECK.** Every drawn figure must have been served.
  const drawn = await drawnMoney();
  const invented = drawn.filter((f) => !served.has(f));
  say(`  money drawn: ${drawn.join(", ") || "(none)"}`);
  say(`  money served: ${[...served].join(", ") || "(none)"}`);
  if (invented.length > 0) {
    findings.push(
      `⚠⚠ MONEY ON SCREEN THAT THE SERVER DID NOT SEND: ${invented.join(", ")} — ` +
        "a figure computed in the browser (hard rule 2, DEF-088, DEF-127)",
    );
  } else {
    notes.push("every money figure on step 4 came from the server or the clerk's own box");
  }

  await shot("step4-charges-1440");
  await page.setViewportSize({ width: 1280, height: 1400 });
  await shot("step4-charges-1280");
  const wide = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  if (wide) findings.push("step 4 scrolls sideways at 1280 — B14 rule 44's minimum");
  await page.setViewportSize({ width: 1440, height: 1400 });
}

say("\n══ STEP 5 · REVIEW ══");
const reviewStep = await openStepWith("[data-at-a-glance]", "Review");
if (reviewStep !== null) {
  const glance = await page.$$eval("[data-glance-value]", (ns) =>
    ns.map((n) => `${n.getAttribute("data-glance-value")}=${n.innerText.trim().slice(0, 24)}`),
  );
  say(`  at a glance: ${glance.length} cells`);
  for (const c of glance) say(`    ${c}`);
  if (glance.length !== 9) findings.push(`At a glance drew ${glance.length} cells, drawing has 9`);

  const groups = await page.$$eval("[data-review-group]", (ns) =>
    ns.map((n) => n.getAttribute("data-review-group")),
  );
  const edits = await page.$$eval("[data-group-edit]", (ns) =>
    ns.map((n) => `${n.getAttribute("data-group-edit")}→step ${n.getAttribute("data-edits-step")}`),
  );
  say(`  groups: ${groups.join(", ")}`);
  say(`  edits:  ${edits.join(" · ")}`);
  if (groups.length !== 4) findings.push(`Review drew ${groups.length} groups, drawing has 4`);
  if (edits.length !== groups.length) {
    findings.push(`⚠ ${groups.length - edits.length} group(s) have NO Edit link`);
  }

  // ⚠ **THE EDIT LINK IS PRESSED, NOT MERELY COUNTED.** A link asserted by
  // attribute is a link nobody proved goes anywhere (hard-won law 2's mirror).
  const first = await page.$("[data-group-edit]");
  if (first) {
    const wants = await first.getAttribute("data-edits-step");
    await first.click();
    await page.waitForTimeout(600);
    const landed = new URL(page.url()).searchParams.get("step");
    say(`  pressed the first Edit: wanted step ${wants}, landed on ${landed}`);
    if (landed !== wants) findings.push(`an Edit link went to step ${landed}, not ${wants}`);
    // ⚠⚠ **RE-OPEN REVIEW; DO NOT `goBack()` — AND THIS WALK REPORTED FOUR
    // FALSE DEFECTS AND TWO MISLABELLED SCREENSHOTS BEFORE THAT WAS FIXED.**
    // The rail's Edit navigates with `replace`, so the Review entry is
    // OVERWRITTEN by the step it jumps to: history reads 4 → 1, never
    // 4 → 5 → 1. `goBack()` therefore lands on **Charges**, and every
    // assertion below then asks the Charges page for Review's markup and
    // truthfully reports it missing — *"the Communication fold lost
    // [data-telling-field=contact]"* over a fold that renders perfectly one
    // screen away. Worse, `shot("step5-review-1440")` saved a picture of
    // step 4 UNDER STEP 5's NAME, which is the proof itself lying.
    //
    // **Hard-won law 7, habit 2: ask what would make this check FAIL
    // wrongly.** A selector query that cannot tell *absent from this screen*
    // from *I am on the wrong screen* is not a check — it accuses the
    // component instead of itself. Re-opening by marker is self-verifying:
    // `openStepWith` returns null when it cannot find Review at all.
    const back = await openStepWith("[data-at-a-glance]", "Review");
    if (back === null) {
      findings.push("could not get back to Review after pressing Edit — the rest is unchecked");
    }
  }

  // The fold: every field the Communication step held.
  for (const sel of [
    '[data-telling-field="contact"]',
    '[data-telling-field="email"]',
    '[data-telling-field="phone"]',
    '[data-telling-field="language"]',
    '[data-array="messages"]',
    '[data-array-action="add-template"]',
  ]) {
    if (!(await page.$(sel))) findings.push(`the Communication fold lost ${sel}`);
  }
  // `+ Add template` must actually open the picker — the third absorbed panel.
  await page.click('[data-array-action="add-template"]').catch(() => undefined);
  await page.waitForTimeout(700);
  if (!(await page.$("[data-template-picker]"))) {
    findings.push("+ Add template did not open the picker — the third panel is unreachable");
  } else {
    notes.push("+ Add template opens the picker, with its search and its six columns");
  }

  const creates = await page.$$eval("[data-creates]", (ns) =>
    ns.map((n) => n.getAttribute("data-creates")),
  );
  say(`  what Create makes: ${creates.length} rows`);
  const reviewText = await page.evaluate(() => document.body.innerText);
  for (const stale of ["do not happen today", "no invoice is written"]) {
    if (reviewText.includes(stale)) {
      findings.push(`the drawing's STALE note is on screen: "${stale}"`);
    }
  }
  if (/cheque/i.test(reviewText)) findings.push("the word CHEQUE is on step 5");

  const drawn5 = await drawnMoney();
  const invented5 = drawn5.filter((f) => !served.has(f));
  say(`  money drawn: ${drawn5.join(", ") || "(none)"}`);
  if (invented5.length > 0) {
    findings.push(`⚠⚠ MONEY ON STEP 5 THE SERVER DID NOT SEND: ${invented5.join(", ")}`);
  }

  await shot("step5-review-1440");
  await page.setViewportSize({ width: 1280, height: 1400 });
  await shot("step5-review-1280");
  const wide5 = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  if (wide5) findings.push("step 5 scrolls sideways at 1280 — B14 rule 44's minimum");
}

say("\n══ WHAT THIS WALK FOUND ══");
if (findings.length === 0) say("  nothing");
for (const f of findings) say(`  ✗ ${f}`);
say("\n══ WHAT IT CONFIRMED ══");
for (const n of notes) say(`  ✓ ${n}`);
if (browserNoise.length > 0) say(`\n(browser noise, not ours: ${browserNoise.length} line(s))`);
writeFileSync(`${OUT}/findings.txt`, `${findings.join("\n")}\n---\n${notes.join("\n")}\n`);

await browser.close();
process.exit(findings.length === 0 ? 0 : 1);
