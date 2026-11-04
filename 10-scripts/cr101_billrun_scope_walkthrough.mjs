// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 — Billing §03. Step 1 (`16 Scope`, blueprint p046–p048)
//           reads the blueprint's own short help, and the step-3 case filter
//           offers only the nine kinds the engine can raise (`DEF-2596`).
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           running app) · B14 rule 33 (on-screen text is capped by what it is
//           for) · B14 rule 37 (a drawn figure is an ILLUSTRATION — the cycle
//           fact is DERIVED, never typed) · 13-change-process.md's CLOSURE BAR
//           (PO 2026-08-18: *"CR is not closed until we have confirm user is
//           able to perform tasks using screen/broswer/UI"*)
// ───────────────────────────────────────────────────────
/**
 * cr101_billrun_scope_walkthrough — OPEN the bill run, READ what is rendered,
 * and measure it, at both staff widths.
 *
 *     node 10-scripts/cr101_billrun_scope_walkthrough.mjs
 *
 * ⚠ **IT READS THE RENDERED TEXT AND COUNTS THE WORDS.** Every `toContain` in
 * the suite passes on a sentence of eighteen words as happily as on one of
 * four, and no gate in this repo reads rendered output, so the only check that
 * can see a rule-33 breach is this one.
 *
 * ⚠ **WIDTHS: 1280 AND 1440 ONLY.** The staff app is a laptop and desktop
 * product (PO 2026-09-10) and the blueprint is drawn at 1440 on purpose — so a
 * 1280 finding is a PRODUCT finding, never drift from a drawing that does not
 * exist at that width.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/step2-shots";

const problems = [];
const note = (m) => console.log(m);
const ok = (m) => console.log("  ✓ " + m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };

/** Meaningful words — the unit B14 rule 33 counts in. */
const words = (s) => (s.match(/[A-Za-z0-9][A-Za-z0-9'’-]*/g) ?? []).length;
const sentences = (s) => s.split(/(?<=[.!?])\s+/).map((x) => x.trim()).filter(Boolean);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});

async function walk(width) {
  const ctx = await browser.newContext({ viewport: { width, height: 1000 } });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => fail(`[${width}] page error: ${e.message}`));

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });

  // ── STEP 1 · `16 Scope` ──────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/billing/run?step=1`, { waitUntil: "networkidle" });
  await page.locator('[data-wizard="rail"]').waitFor({ timeout: 30000 });
  note(`\n[${width}] step 1 — ${page.url()}`);

  const heading = (await page.locator('[data-brun="h"]').first().innerText()).trim();
  note(`  heading: "${heading}" (${words(heading)} words)`);
  if (words(heading) > 3) fail(`heading is ${words(heading)} words; B14 rule 33 caps a heading at 3`);
  else ok(`heading within rule 33's 3-word cap`);

  // Every piece of help on the step, measured rather than eyeballed.
  const helps = await page.locator(".field .field-help, .field-help").allInnerTexts();
  let worst = 0;
  let worstText = "";
  for (const raw of helps) {
    const text = raw.trim();
    if (text === "") continue;
    for (const one of sentences(text)) {
      if (words(one) > worst) { worst = words(one); worstText = one; }
    }
  }
  note(`  ${helps.filter((h) => h.trim() !== "").length} help line(s); longest sentence ${worst} words`);
  if (worst > 6) fail(`a help sentence runs ${worst} words — "${worstText}" (rule 33 caps a fact at 6)`);
  else ok(`every help sentence is within rule 33's 6-word cap`);

  // The retired rationale must be gone from the screen, not merely shortened.
  const body = await page.locator("body").innerText();
  if (body.includes("quietly skipped")) fail("the services RATIONALE is still on screen (rule 33: zero words)");
  else ok("the services rationale is off the screen");

  // ⚠ B14 rule 37 — the cycle fact is DERIVED. Pick a real cycle and read it.
  //
  // ⚠ **WAIT FOR THE OPTIONS FIRST.** The first version of this walk read the
  // picker the moment the rail appeared and reported *"no billing cycle is
  // offered"* over a picker that was carrying seven — the cycles query had
  // simply not answered. That is a check measuring how far the page had got,
  // which is the shape CLAUDE.md law 7 names, and it produced a false finding
  // on its first run.
  const picker = page.locator("#brun-cycle");
  // ⚠ **`state: "attached"`, NOT the default `"visible"`.** An `<option>` inside
  // a `<select>` is never "visible" to a browser driver, so the default wait
  // ALWAYS times out — and the version of this check that used it reported the
  // picker empty at both widths while the very next line read seven cycles out
  // of it. A check that cannot pass is law 7's second shape, and it took ten
  // minutes of walking to notice because the message it printed was plausible.
  await picker.locator("option[value]:not([value=''])").first()
    .waitFor({ state: "attached", timeout: 30000 })
    .catch(() => fail(`[${width}] the cycle picker never offered a cycle — the cycles read did not answer`));
  const options = await picker.locator("option").all();
  let picked = null;
  for (const option of options) {
    const value = await option.getAttribute("value");
    if (value) { picked = value; break; }
  }
  if (picked === null) {
    fail("no billing cycle is offered, so the derived cycle fact cannot be walked");
  } else {
    await picker.selectOption(picked);
    await page.waitForTimeout(400);
    const help = (await page.locator("#brun-cycle").locator("xpath=ancestor::*[contains(@class,'field')][1]").innerText()).trim();
    note(`  after choosing a cycle, the field reads:\n    ${help.replace(/\n/g, "\n    ")}`);
    if (help.includes("Only cycles set up here")) {
      fail("the cycle field still shows the generic help after a cycle was chosen — the derived fact is not wired");
    } else {
      ok("the cycle field shows the chosen cycle's own routes and code");
    }
  }

  // ── THE CONTINUITY BAND · blueprint p046 (the badge), p048 (the words) ────
  //
  // ⚠ **DRIVEN, NOT ASSERTED.** Hard-won law 2: a component whose prop nothing
  // passes renders nothing and every test still passes. The only way to know
  // this band is wired is to put a real period into the real input and read
  // what comes back — so the three states are PRODUCED here, from the run
  // history this tenant actually has, and the dates are DERIVED (B14 rule 37:
  // a date drawn in the blueprint is an illustration, never a value to type).
  const history = await page.evaluate(async (tenant) => {
    const r = await fetch(`/api/${tenant}/billing/runs`, { credentials: "same-origin" });
    if (!r.ok) return null;
    const body = await r.json();
    // The envelope is `{data: {runs: [...]}}` — `getBillRuns` reads `.runs`
    // out of `requireData`. Guessing `items`/`results` here returned an object
    // that is not an array, so the probe reported "no past run carries a
    // period" and the walk still printed WALK CLEAN over a band it had never
    // touched. That is a check reporting zero over a scope it excludes.
    return body?.data?.runs ?? body?.runs ?? null;
  }, TENANT);
  const rows = Array.isArray(history) ? history : [];
  const withPeriod = rows.filter((r) => r && r.cycle_id && r.period_end);
  if (withPeriod.length === 0) {
    // ⚠ **A FAILURE, NOT A NOTE.** The first version of this block skipped
    // with a note and the walk still ended "WALK CLEAN" — a pass over the one
    // feature it was added to exercise. Either the data is missing or the
    // probe is broken, and both need a person.
    fail(`[${width}] the continuity band was never driven: ${rows.length} run(s) read, none with a cycle and a period`);
  } else {
    const latest = withPeriod.sort((a, b) => (a.period_end < b.period_end ? 1 : -1))[0];
    const day = (iso, delta) =>
      new Date(Date.parse(`${iso}T00:00:00Z`) + delta * 86400000).toISOString().slice(0, 10);
    const probes = [
      ["continuous", day(latest.period_end, 1)],
      ["gap", day(latest.period_end, 4)],
      ["overlap", day(latest.period_end, -2)],
    ];
    await page.locator("#brun-cycle").selectOption(latest.cycle_id);
    await page.waitForTimeout(300);
    for (const [expected, from] of probes) {
      await page.locator("#brun-period-start").fill(from);
      await page.waitForTimeout(350);
      const band = page.locator('[data-brun="continuity"]');
      if ((await band.count()) === 0) {
        fail(`[${width}] period from ${from}: no continuity band rendered (expected ${expected})`);
        continue;
      }
      const state = await band.first().getAttribute("data-continuity");
      const text = (await band.first().innerText()).replace(/\n/g, " ").trim();
      note(`  period from ${from} -> ${state}: "${text}"`);
      if (state !== expected) fail(`[${width}] period from ${from} read "${state}", expected "${expected}"`);
      // ⚠ **MEASURE THE FACT, NOT THE WHOLE BAND — and the cap is unchanged.**
      // The first version counted the pill's label together with the fact and
      // split each date into its digit groups, so "3 days never billed:
      // 08/01/2026 – 08/03/2026." came back as ELEVEN words and flagged copy
      // that is well inside rule 33. What was wrong was the UNIT: a pill is
      // its own element and a date is one value a reader takes in at once.
      // Correcting what a check measures is not the same act as lowering its
      // cap, and only the first is allowed.
      const factText = (await band.first().locator("[data-continuity-fact]").innerText())
        .replace(/\d[\d/.\u2013-]*\d/g, "D")
        .trim();
      for (const one of sentences(factText)) {
        if (words(one) > 6) fail(`[${width}] continuity fact runs ${words(one)} words — "${one}"`);
      }
    }
    // And the state that must render NOTHING: no previous run to compare to.
    const emptyCycle = await page.locator("#brun-cycle option").evaluateAll(
      (nodes, used) => nodes.map((n) => n.value).filter((v) => v && v !== used)[0] ?? null,
      latest.cycle_id,
    );
    if (emptyCycle !== null) {
      await page.locator("#brun-cycle").selectOption(emptyCycle);
      await page.waitForTimeout(350);
      const n = await page.locator('[data-brun="continuity"]').count();
      if (n === 0) ok("a cycle with no earlier run draws no band at all, rather than a reassuring one");
      else note(`  (that cycle has earlier runs too — band still shown, which is correct)`);
      await page.locator("#brun-cycle").selectOption(latest.cycle_id);
      await page.waitForTimeout(250);
      await page.locator("#brun-period-start").fill(day(latest.period_end, -2));
      await page.waitForTimeout(350);
    }
  }

  await page.screenshot({ path: `${SHOTS}/run-scope-${width}.png`, fullPage: true });
  note(`  shot: ${SHOTS}/run-scope-${width}.png`);

  // ── STEP 3 · the case filter ─────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/billing/run?step=3`, { waitUntil: "networkidle" });
  await page.locator('[data-wizard="rail"]').waitFor({ timeout: 30000 });
  const families = page.locator("#brun-filter-families option");
  const kinds = page.locator("#brun-filter-case-filters option");
  if ((await families.count()) === 0) {
    note(`\n[${width}] step 3 — no run in flight, so the filters do not render. Not judged.`);
  } else {
    const familyNames = (await families.allInnerTexts()).map((x) => x.trim());
    note(`\n[${width}] step 3 — ${familyNames.length} famil(y/ies): ${familyNames.join(" | ")}`);

    // ⚠ **THE KINDS SELECT HOLDS THE OPEN FAMILY'S KINDS, NOT ALL OF THEM.**
    // The first version of this walk compared one family's eight against the
    // engine's nine and reported a product fault that was not there. So every
    // family is OPENED and its kinds collected — the only way to ask the
    // question the check claims to ask.
    const seen = new Set();
    for (const option of await families.all()) {
      const value = await option.getAttribute("value");
      if (!value) continue;
      await page.locator("#brun-filter-families").selectOption(value);
      await page.waitForTimeout(300);
      for (const raw of await kinds.allInnerTexts()) {
        const label = raw.trim().replace(/\s*\(\d+\)$/, "");
        if (label !== "" && !/^All$/i.test(label)) seen.add(label);
      }
    }
    note(`  ${seen.size} case kind(s) offered across every family`);
    if (seen.size !== 9) fail(`the case filter offers ${seen.size} kinds across all families; the engine raises 9`);
    else ok("the case filter offers exactly the nine kinds the engine raises");
    for (const dead of ["Late fee due", "Extra charges to add", "Owes a lot", "Way past due", "No usage this month", "Used a lot more than usual"]) {
      if ([...seen].some((k) => k.includes(dead))) fail(`"${dead}" is still offered and can never have a row`);
    }
  }
  await page.screenshot({ path: `${SHOTS}/run-check-${width}.png`, fullPage: true });
  note(`  shot: ${SHOTS}/run-check-${width}.png`);

  await ctx.close();
}

for (const width of [1280, 1440]) {
  await walk(width);
}
await browser.close();

console.log(`\n${problems.length === 0 ? "WALK CLEAN" : `WALK FOUND ${problems.length} PROBLEM(S)`}`);
for (const one of problems) console.log("  - " + one);
process.exit(problems.length === 0 ? 0 : 1);
