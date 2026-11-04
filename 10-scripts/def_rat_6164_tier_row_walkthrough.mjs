#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-6164 — RAT-03's tier ladder. The Product Owner, on the
//          deployed build v2.325.1: "version Deployed for tiered rate align all
//          input field in one row and UI breaking at bottom" and, separately,
//          "'Leave blank on the last row for no upper limit.' This text is
//          reapeted". THREE reported faults, TWO causes.
// Screens: RAT-03 step 3 — both structures that draw a ladder:
//          `Percent of another service` on the USAGE basis, and `Tiered`.
// Drawing: 05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf p046, and
//          04-docs/05-modules/06-rating/conformance/CR-087-p045-create-step3-rates.md
//          divergence D4, which recorded the repeated sentence and was never
//          turned into a check.
// Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output) · law 7
//          (a check's output must distinguish pass from fail to a READER, and
//          ask what would make it pass WRONGLY) · B14 rule 33 (on-screen text
//          is capped by what it is for) · rule 32 clause 3 (a row never repeats
//          what its own control offers) · rule 38 (where a drawing and our UI
//          rules disagree about how a FORM is built, the UI rules win) ·
//          12-governance/22-product-maintenance-process.md step 0 (REPRODUCE)
//          and step 4 (prove it against the reproduction, in a browser).
// ───────────────────────────────────────────────────────
/**
 * WALK RAT-03's TIER LADDER AND *MEASURE* IT, ON A REAL SEEDED UTILITY.
 *
 *     10-scripts/proof-db.sh clone <label>
 *     (06-backend) DATABASE_URL=… manage.py runserver 127.0.0.1:<api>
 *     (07-frontend) npx vite build && PORT=<web> \
 *        API_PROXY_TARGET=http://127.0.0.1:<api> node server.mjs
 *     BASE=http://127.0.0.1:<web> MODE=after \
 *        node 10-scripts/def_rat_6164_tier_row_walkthrough.mjs
 *
 * ⚠ **BOOT THROUGH `server.mjs`, THE DEPLOYED JOIN — NOT A DEV SERVER**, and
 * kill by the PID you recorded. `pkill -f "server.mjs"` matches every lane's
 * server and several are usually live (the maintenance process says so in its
 * own words).
 *
 * ⚠ **IT IS WRITTEN TO RUN BEFORE AND AFTER THE FIX AND TO PRINT A DIFFERENT
 * STORY EACH TIME.** `MODE=before` expects the reported screen and FAILS if the
 * defect is already gone; `MODE=after` (the default) expects the fix. A
 * walkthrough that passes in both worlds is law 7's *incapable of failing*.
 *
 * ⚠ **`fullPage: true` IS USELESS ON THIS APP AND THE FIRST DRAFT OF THIS FILE
 * WAS FOOLED BY IT.** `.app-shell` is `height:100vh; overflow:hidden` and the
 * real scroller is `main.view`, so `document.documentElement.scrollHeight`
 * reports the content's height while the shell stays locked at one viewport.
 * Playwright then captures a tall image whose bottom two thirds are BLANK — it
 * reads exactly like a screen that breaks at the bottom, and it is an artefact
 * of the capture. Every screenshot here scrolls `main.view` and captures the
 * VIEWPORT.
 *
 * THE FOUR THINGS IT READS OFF THE RENDERED SCREEN, none of which any gate in
 * this repo can see:
 *
 *   1. THE BASELINE. The y of all four controls in every tier row — `From`,
 *      `To`, `Rate` and `Remove tier`. Before: a 45px spread, with `To` lifted
 *      43px because its `help` line made its box 103px against 60px. After:
 *      within `BASELINE_TOLERANCE`.
 *   2. THE SENTENCE, COUNTED. Before: once per row — three blocks print it
 *      three times, six print it six, and it says *"on the LAST row"* under
 *      every one of them. After: exactly once, however many blocks are open.
 *   3. THE ATTACHMENT. After: the last row's `To` input names the sentence in
 *      `aria-describedby`, so taking it out of the box did not take it away
 *      from the field.
 *   4. THE BOTTOM. `+ Add tier` measured 1088px — the full width of its panel,
 *      because `Panel` is a column flex container and a Button that is its
 *      direct child stretches. After: narrower than the panel, like every other
 *      button in the product.
 *
 * AND IT DOES ALL FOUR AT **ONE, THREE AND SIX** BLOCKS, because a ladder
 * grows, and at **1440 and 390**.
 */
import { createRequire } from "node:module";
const require = createRequire(
  process.env.NODE_MODULES_FROM ?? "/home/user/SMARTBillHub/07-frontend/package.json",
);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8342";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/def-rat-6164";
const MODE = process.env.MODE ?? "after";

/** Two controls are on one line when their tops are within this. The inputs are
 *  36px tall and the ghost button 35px, so a 1px difference is the kit's own
 *  and not a layout fault. */
const BASELINE_TOLERANCE = 4;

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};
const ok = (m) => console.log("  ✓ " + m);

if (!(await fetch(`${BASE}/`).catch(() => null))) {
  console.log(`the SPA server at ${BASE} is not answering — nothing to walk`);
  process.exit(2);
}

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium",
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
note(`signed in — ${page.url()}`);

/**
 * ⚠ **A NAME THIS RUN HAS NOT USED BEFORE.** `rating.schedules.duplicate_name`
 * is a real refusal and a correct one; a walkthrough that only passes against a
 * fresh seed is one nobody can re-run, and re-running over its own leftovers is
 * half the value of having it.
 */
const RUN = Date.now().toString().slice(-6);

/** Open RAT-03 at step 3 with `model` selected. Every wait carries a DEADLINE
 *  and the producer is the page itself, which `waitForSelector` re-checks. */
/**
 * A `<select>` that is PRESENT is not a `<select>` that is POPULATED, and its
 * options arrive from the API after the element does.
 *
 * ⚠ **THIS FILE WAITED ON THE ELEMENT AND RACED THE FIRST TIME THE MACHINE WAS
 * BUSY** — `page.selectOption: options[0]: expected object, got undefined`,
 * which reads like a broken screen and is a broken WAIT. `waitForFunction`
 * carries its own deadline and re-checks the producer (the page) on every
 * poll, which is what CLAUDE.md asks of every wait in a walkthrough.
 */
async function optionsOf(id) {
  await page.waitForFunction(
    (sel) => {
      const el = document.querySelector(sel);
      return el !== null && Array.from(el.options).some((o) => o.value !== "");
    },
    `#${id}`,
    { timeout: 60000 },
  );
  return page.evaluate(
    (sel) =>
      Array.from(document.querySelector(sel).options)
        .filter((o) => o.value !== "" && !o.disabled)
        .map((o) => o.value),
    `#${id}`,
  );
}

async function openStep3(model) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/rates/new`, { waitUntil: "networkidle" });
  await page.waitForSelector("#rate-service", { timeout: 30000 });
  await page.locator("#rate-name").fill(`DEF-RAT-6164 ${model} ${RUN}`);
  const services = await optionsOf("rate-service");
  if (services.length === 0) throw new Error("step 1 offers no service at all — nothing to walk");
  await page.selectOption("#rate-service", services.includes("water") ? "water" : services[0]);
  await page.waitForTimeout(700);
  if ((await page.evaluate(() => document.querySelector("#rate-uom")?.value)) === "") {
    const units = await optionsOf("rate-uom");
    if (units.length) await page.selectOption("#rate-uom", units[0]);
  }
  await page.getByRole("button", { name: /continue|next/i }).first().click();
  await page.waitForTimeout(600);
  await page.getByRole("button", { name: /continue|next/i }).first().click();
  await page.waitForSelector("#rate-model", { timeout: 30000 });
  const models = await optionsOf("rate-model");
  if (!models.includes(model)) throw new Error(`step 3 does not offer "${model}" — it offers ${models.join(", ")}`);
  await page.selectOption("#rate-model", model);
  await page.waitForTimeout(700);
  if (model === "percent_of_service") {
    // ⚠ **CLICK THE LABEL, NOT THE INPUT.** `FormModal.css` hides the segmented
    // control's <input> and draws the states on the <label>; `.check()` on the
    // input times out against a control a person can plainly press.
    await page
      .locator("label.seg-opt")
      .filter({ has: page.locator('input[name="percent-basis-kind"][value="usage"]') })
      .click();
    await page.waitForTimeout(500);
  }
}

async function growTo(n) {
  let have = await page.locator(".rating-tier-row").count();
  const deadline = Date.now() + 60000;
  while (have < n) {
    if (Date.now() > deadline) throw new Error(`could not grow the ladder to ${n} blocks`);
    await page.getByRole("button", { name: /add tier/i }).first().click();
    await page.waitForTimeout(300);
    have = await page.locator(".rating-tier-row").count();
  }
  return have;
}

/** Everything this file judges, read off the DOM in one pass. */
async function readLadder() {
  return page.evaluate(() => {
    const box = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {
        top: Math.round(r.top),
        bottom: Math.round(r.bottom),
        left: Math.round(r.left),
        right: Math.round(r.right),
        w: Math.round(r.width),
        h: Math.round(r.height),
      };
    };
    const rowEls = Array.from(document.querySelectorAll(".rating-tier-row"));
    const rows = rowEls.map((rowEl, i) => {
      const remove = Array.from(rowEl.querySelectorAll("button")).find((b) =>
        /remove/i.test(b.textContent || ""),
      );
      return {
        i,
        from: box(document.getElementById(`tier-from-${i}`)),
        to: box(document.getElementById(`tier-to-${i}`)),
        rate: box(document.getElementById(`tier-price-${i}`)),
        remove: box(remove),
        // the field BOX heights — the mechanism, not just the symptom
        fromField: box(document.getElementById(`tier-from-${i}`)?.closest(".field")),
        toField: box(document.getElementById(`tier-to-${i}`)?.closest(".field")),
        describedBy: document.getElementById(`tier-to-${i}`)?.getAttribute("aria-describedby") ?? null,
      };
    });
    // Count the sentence by its own MEANING, not by a class: a help line that
    // moved out of a field must still be found, and one that moved into a
    // second place must still be counted twice.
    const sentences = Array.from(document.querySelectorAll("p"))
      .map((p) => ({ text: (p.textContent || "").trim(), id: p.id }))
      .filter((p) => /upper limit|no limit|last row|last To/i.test(p.text));
    const add = Array.from(document.querySelectorAll("button")).find((b) =>
      /\+ Add tier/.test(b.textContent || ""),
    );
    const panel = add ? add.closest("section.panel") : null;
    return {
      rows,
      sentences,
      add: box(add),
      panel: box(panel),
      rowCount: rowEls.length,
      viewportW: document.documentElement.clientWidth,
      // the PAGE must never scroll sideways (B14)
      docScrollW: document.documentElement.scrollWidth,
    };
  });
}

/** Scroll the REAL scroller (`main.view`), never the document, then shoot the
 *  VIEWPORT. See the header note about `fullPage`. */
async function shoot(name) {
  await page.evaluate(() => {
    const el = Array.from(document.querySelectorAll("body *")).find((e) => {
      const cs = getComputedStyle(e);
      return (
        (cs.overflowY === "auto" || cs.overflowY === "scroll") && e.scrollHeight > e.clientHeight + 1
      );
    });
    if (el) el.scrollTop = el.scrollHeight;
  });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${SHOTS}-${name}.png` });
}

function judge(label, m) {
  note(`\n── ${label} · ${m.rowCount} block(s), viewport ${m.viewportW}px ──`);

  // 1 · THE BASELINE
  //   At 390 the row's `auto-fit` grid collapses to ONE column and the controls
  //   STACK on purpose, so a baseline is meaningless there — the skill's own
  //   rule is that narrow layouts stack rather than shrink. Judged at >= 1280.
  const stacked = m.viewportW < 1280;
  for (const r of m.rows) {
    const tops = [r.from, r.to, r.rate, r.remove].filter(Boolean).map((b) => b.top);
    const spread = tops.length ? Math.max(...tops) - Math.min(...tops) : 0;
    const shape =
      `FROM=${r.from?.top ?? "—"} TO=${r.to?.top ?? "—"} RATE=${r.rate?.top ?? "—"} ` +
      `REMOVE=${r.remove?.top ?? "—"}  spread=${spread}px` +
      (r.toField && r.fromField ? `  (To box ${r.toField.h}px vs From box ${r.fromField.h}px)` : "");
    if (stacked) {
      note(`  row ${r.i}: ${shape}   — stacked at this width, baseline not judged`);
      continue;
    }
    if (MODE === "before") {
      if (spread <= BASELINE_TOLERANCE)
        fail(`BEFORE: row ${r.i} is already aligned (${spread}px) — the defect is gone; run MODE=after`);
      else ok(`BEFORE: row ${r.i} — ${shape}`);
    } else if (spread > BASELINE_TOLERANCE) {
      fail(`row ${r.i}: the four controls do NOT share a baseline — ${shape}`);
    } else ok(`row ${r.i}: one baseline — ${shape}`);
  }

  // 2 · THE SENTENCE, COUNTED
  const n = m.sentences.length;
  note(`  the "no upper limit" sentence appears ${n} time(s) over ${m.rowCount} block(s)`);
  m.sentences.forEach((s, i) => note(`      [${i}] ${s.text}`));
  if (MODE === "before") {
    if (n <= 1) fail(`BEFORE: the sentence appears ${n} time(s) — the defect is gone; run MODE=after`);
    else ok(`BEFORE: printed ${n} times, once per block, each saying "on the last row"`);
  } else if (m.rowCount === 0) {
    if (n !== 0) fail(`no ladder rows are drawn, yet the sentence is on screen ${n} time(s)`);
    else ok("no rows, no sentence — the flat case draws its price above and has no To box");
  } else if (n !== 1) {
    fail(`the sentence appears ${n} time(s) over ${m.rowCount} block(s) — it must appear exactly once`);
  } else ok(`exactly once over ${m.rowCount} block(s)`);

  // 3 · THE ATTACHMENT — only the LAST row's To may name it
  if (MODE === "after" && m.rowCount > 0) {
    const id = m.sentences[0]?.id ?? null;
    const last = m.rows[m.rows.length - 1];
    if (!id) fail("the sentence carries no id, so nothing can point at it");
    else if (!(last.describedBy ?? "").split(/\s+/).includes(id)) {
      fail(`the last row's To does not name the sentence — aria-describedby="${last.describedBy}"`);
    } else ok(`the last row's To names it: aria-describedby="${last.describedBy}"`);
    const strays = m.rows
      .slice(0, -1)
      .filter((r) => (r.describedBy ?? "").includes(id ?? "\u0000"));
    if (strays.length)
      fail(`${strays.length} row(s) other than the last also point at it — it is true of the last only`);
    else if (m.rowCount > 1) ok("no other row points at it — it is true of the last row only");
  }

  // 4 · THE BOTTOM
  if (m.add && m.panel) {
    const share = Math.round((m.add.w / m.panel.w) * 100);
    note(`  + Add tier is ${m.add.w}px inside a ${m.panel.w}px panel (${share}%)`);
    if (MODE === "before") {
      if (share < 90) fail(`BEFORE: + Add tier is already ${share}% of its panel — run MODE=after`);
      else ok(`BEFORE: + Add tier fills ${share}% of the panel — a button drawn as an empty box`);
    } else if (share >= 90) {
      fail(`+ Add tier is ${m.add.w}px, ${share}% of its panel — it reads as an input, not a button`);
    } else ok(`+ Add tier takes its own width (${share}% of the panel)`);
  }

  // B14 — the page itself never scrolls sideways, at any width
  if (m.docScrollW > m.viewportW + 1) {
    fail(`the PAGE scrolls sideways: scrollWidth ${m.docScrollW} > viewport ${m.viewportW}`);
  } else ok(`no horizontal page scroll (scrollWidth ${m.docScrollW})`);
}

for (const model of ["percent_of_service", "tiered"]) {
  note(`\n\n══ RAT-03 step 3 · ${model}${model === "percent_of_service" ? " · Usage" : ""} ══`);
  await openStep3(model);

  // ONE block. The percent card draws a flat price above and passes an EMPTY
  // ladder; `tiered` draws its single row. Both are the commonest case.
  await growTo(1).catch(() => {});
  judge(`${model} — as opened`, await readLadder());
  await shoot(`${MODE}-${model}-open-1440`);

  await growTo(3);
  judge(`${model} — grown`, await readLadder());
  await shoot(`${MODE}-${model}-3-1440`);

  await growTo(6);
  judge(`${model} — a long ladder`, await readLadder());
  await shoot(`${MODE}-${model}-6-1440`);

  // 390 — the layout stacks; what is judged here is that the PAGE does not
  // scroll sideways and the sentence is still printed once.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(600);
  judge(`${model} — a long ladder at phone width`, await readLadder());
  await shoot(`${MODE}-${model}-6-390`);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(400);
}

await browser.close();
note(`\nshots: ${SHOTS}-*.png`);
if (problems.length) {
  note(`\n${problems.length} problem(s):`);
  problems.forEach((p) => note("  ✗ " + p));
  process.exit(1);
}
note(`\nMODE=${MODE}: every check passed.`);
