#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-054 task 20, the MODAL half — *"Dispute 259 to about 90; Correct
//           64 to about 25"*. The W5 wave of 2026-08-30 cut the five upload
//           stages and measured only `metering.upload.*`; these two windows were
//           never opened.
// Screens:  S29 · the read detail page, its Dispute window and its Correct
//           window (the same window a BILLED read titles *Correct billed read*).
// Rules:    B14 rule 32 (PO 2026-08-31) — a description budget: one sentence per
//           section, a stated absence closed by default, a row never repeats
//           what its own control offers, no rule id or internal code in
//           clerk-facing copy · B14 rule 10 (the asterisk marks required) ·
//           BR-MET-133 (PO 2026-08-26, what a billed dispute must say) ·
//           BR-MET-024 (a correction APPENDS) · hard rule 3 (never a quantity
//           without its unit) · hard-won law 6.
// ───────────────────────────────────────────────────────
/**
 * READ THE WORDS THAT ARE ACTUALLY ON THE SCREEN, NOT THE WORDS IN `en.json`.
 *
 * ⚠ **WHY THIS EXISTS BESIDE A PASSING WORD-BUDGET TEST.**
 * `CR054Task20ModalCopy.test.ts` counts the CATALOGUE, which is the right way to
 * stop copy growing back — but it cannot answer the only question a Product
 * Owner is actually asking: *how much writing is in front of the clerk when this
 * window opens?* Those are different numbers whenever a sentence is rendered
 * conditionally, rendered twice, or not rendered at all. This file opens the
 * window in Chromium and counts what a person can read.
 *
 * It found exactly that on its first run: the DISPUTE window's own catalogue
 * total is 95 words, and the window a clerk opens on an unbilled read draws
 * **54** — because `billedBillStands` renders only on a billed reading. A
 * budget measured on the catalogue alone would have been pessimistic by 41
 * words, and on the billed read it is the catalogue figure exactly, which is the
 * pair worth knowing.
 *
 * ⚠ **AND IT READS THE MODAL, NOT THE PAGE.** `document.body.innerText` behind
 * an open dialog includes the whole read-detail page underneath it, which would
 * report several hundred words and pass any ceiling written for a page. Every
 * count here is scoped to `[role="dialog"]`.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/sbh_cr054w1" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8041 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4241 API_PROXY_TARGET=http://127.0.0.1:8041 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4241 \
 *   SMOKE_READ=<a committed, undisputed, head reading uuid> \
 *   SMOKE_READ_BILLED=<a reading whose lifecycle is `billed`> \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr054-read-modals.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING** — the shared
 * development database is re-seeded by other lanes and a reseed looks exactly
 * like a broken screen from in here (`cr053-bill-surface.mjs` records the day
 * that cost an investigation). `createdb`, `migrate`, `seed_demo`.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is reading the wrong
 * bytes.
 *
 * ── PROVED RED FIRST, ON THE CASE IT WAS WRITTEN FOR (hard-won law 7) ────
 * `metering.read.override.note` was put back to its shipped wording — *"Nothing
 * is edited. A new reading is appended and becomes the current version; this one
 * stays readable in the history."* — and the frontend REBUILT, because a check
 * pointed at a stale bundle proves nothing. Two assertions failed and the right
 * two:
 *
 *     ⛔ 7 · under budget — 49 words (ceiling 45; it was 64 …)
 *     ⛔ 4 · no retired sentence is back (Nothing is edited)
 *     FAIL — 2 failing assertion(s)
 *
 * Restored and rebuilt: **27 assertions, 0 failing, 0 not exercised.** Measured
 * on `sbh_cr054w1`, Chromium, 1440x1000.
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  THE DISPUTE WINDOW OPENS and is a real dialog with a real box.
 *   2  ITS WORDS ARE UNDER BUDGET, counted from the rendered dialog — both on an
 *      unbilled reading and on a billed one, which are different screens.
 *   3  EVERY CONSEQUENCE A CLERK ACTS ON IS STILL THERE — the account leaves the
 *      bill run, and on a billed reading all four of BR-MET-133's facts.
 *   4  NONE OF THE RETIRED SENTENCES IS ON SCREEN — the ones that explained what
 *      does NOT happen.
 *   5  THE REQUIRED FIELD CARRIES ITS ASTERISK and the help text no longer
 *      spends a word saying "Required" (rule 32 clause 3 needs BOTH halves: the
 *      word is only redundant if the marker is really rendered).
 *   6  NO INTERNAL CODE IS VISIBLE (rule 32 clause 4) — no `snake_case` token,
 *      no rule id, no uuid anywhere in either dialog.
 *   7  THE CORRECT WINDOW opens, is under budget, keeps its unit (hard rule 3)
 *      and still says the correction is an APPEND (BR-MET-024).
 *   8  NEITHER DIALOG SCROLLS SIDEWAYS.
 */
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
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
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4241";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const READ = process.env.SMOKE_READ ?? "";
const READ_BILLED = process.env.SMOKE_READ_BILLED ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr054-read-modals";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** Something this run could NOT exercise, said out loud. A run that skipped an
 *  assertion because the DATA did not reach it has not passed it, and reporting
 *  it as a pass is how a check that cannot fail gets trusted. */
const skipped = [];
function notExercised(message) {
  console.log(`   ⊘ NOT exercised: ${message}`);
  skipped.push(message);
}

/** The same word rule the catalogue test uses, so the two figures compare. */
const COUNT_WORDS = (text) => (text.match(/[A-Za-z0-9’'%$/.-]+/g) || []).length;

/** Everything readable inside the open dialog, plus the shapes rule 32 and
 *  rule 10 turn on. Scoped to the dialog on purpose — see the note above. */
const READ_DIALOG = `(() => {
  const dialog = document.querySelector('[role="dialog"]');
  if (!dialog) return null;
  const box = dialog.getBoundingClientRect();
  const text = dialog.innerText || "";
  const labels = [...dialog.querySelectorAll("label")].map((l) => l.innerText || "");
  return {
    text,
    title: (dialog.querySelector("h1,h2,h3") || {}).innerText || "",
    labels,
    box: { w: Math.round(box.width), h: Math.round(box.height) },
    scrollsSideways: dialog.scrollWidth > dialog.clientWidth + 1,
    // B14 rule 10 — the asterisk really rendered, not merely intended.
    asterisks: (dialog.innerText.match(/\\*/g) || []).length,
    textareas: dialog.querySelectorAll("textarea").length,
  };
})()`;

/** Rule 32 clause 4, read off the rendered text rather than off the catalogue:
 *  a stored enum token, a rule id or a uuid in front of a clerk. */
function internalCodes(text) {
  const found = [];
  const enums = text.match(/\b[a-z]+_[a-z_]+\b/g);
  if (enums) found.push(...enums);
  const ruleIds = text.match(/\b(?:BR|US|EP|OQ|DEF|GT|IS|ADR)-[A-Z]{0,3}-?\d{3,5}\b/g);
  if (ruleIds) found.push(...ruleIds);
  const uuids = text.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi);
  if (uuids) found.push(...uuids);
  return found;
}

/** The sentences this pass deleted, in the words they used to be on screen.
 *  Named so a well-meaning restoration goes red rather than quiet. */
const RETIRED = [
  "has no field",
  "does not open one",
  "Nothing is edited",
  "Nothing here changes the reading",
  "not a change to that bill",
  "is the kind that helps",
  "an auditor needs",
];

async function openReadPage(page, readId) {
  await page.goto(`${BASE}/${TENANT}/reads/${readId}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
}

async function openDialogByLabel(page, labels) {
  for (const label of labels) {
    const button = page.locator(`button:has-text("${label}")`).first();
    if ((await button.count()) === 0) continue;
    if (await button.isDisabled()) continue;
    await button.click();
    await page.waitForSelector('[role="dialog"]', { timeout: 8000 });
    await page.waitForTimeout(400);
    return label;
  }
  return null;
}

async function closeDialog(page) {
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  console.log(`cr054 modals: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // ── THE DISPUTE WINDOW, ON AN UNBILLED READING ──────────────────────────
  console.log("\n── Dispute · an unbilled reading ──");
  if (!READ) {
    notExercised("SMOKE_READ was not set, so the Dispute window was never opened");
  } else {
    await openReadPage(page, READ);
    const opened = await openDialogByLabel(page, ["Dispute"]);
    if (opened === null) {
      notExercised("the Dispute control was absent or refused on SMOKE_READ");
    } else {
      const d = await page.evaluate(READ_DIALOG);
      await page.screenshot({ path: join(OUT, "dispute-unbilled.png") });
      check(d !== null && d.box.w > 300 && d.box.h > 200, `1 · the window is really on screen (${JSON.stringify(d && d.box)})`);
      const count = COUNT_WORDS(d.text);
      console.log(`      words on screen: ${count}`);
      // The catalogue total for this window is 95; the unbilled reading does
      // not draw BR-MET-133's 43-word strip, so what a clerk reads here is
      // roughly half of that. The ceiling is the measured figure.
      check(count <= 60, `2 · under budget on an unbilled reading — ${count} words (ceiling 60)`);
      check(d.textareas === 1, `2 · still one textarea, which is what the CR called it (${d.textareas})`);
      check(
        d.text.includes("System Admin") && d.text.includes("bill run"),
        "3 · the consequence a clerk acts on is on screen: the account leaves the next bill run until a System Admin clears it",
      );
      check(
        !d.text.includes("stays issued"),
        "3 · and BR-MET-133's billed-bill strip is NOT drawn on a reading no bill has used",
      );
      const back = RETIRED.filter((f) => d.text.includes(f));
      check(back.length === 0, `4 · no retired sentence is back (${back.join(" · ") || "none"})`);
      check(d.asterisks >= 1, `5 · B14 rule 10: the required marker is really rendered (${d.asterisks})`);
      check(
        !/\bRequired[.,]/.test(d.text),
        "5 · rule 32 clause 3: the help text no longer spends a word saying “Required” beside that marker",
      );
      const codes = internalCodes(d.text);
      check(codes.length === 0, `6 · rule 32 clause 4: no internal code on screen (${codes.slice(0, 4).join(", ") || "none"})`);
      check(!d.scrollsSideways, "8 · the dialog does not scroll sideways");
      await closeDialog(page);
    }
  }

  // ── THE DISPUTE WINDOW, ON A BILLED READING ─────────────────────────────
  console.log("\n── Dispute · a BILLED reading (BR-MET-133) ──");
  if (!READ_BILLED) {
    notExercised("SMOKE_READ_BILLED was not set, so BR-MET-133's strip was never read on screen");
  } else {
    await openReadPage(page, READ_BILLED);
    const opened = await openDialogByLabel(page, ["Dispute"]);
    if (opened === null) {
      notExercised("the Dispute control was absent or refused on SMOKE_READ_BILLED");
    } else {
      const d = await page.evaluate(READ_DIALOG);
      await page.screenshot({ path: join(OUT, "dispute-billed.png") });
      const count = COUNT_WORDS(d.text);
      console.log(`      words on screen: ${count}`);
      check(count <= 105, `2 · under budget on a billed reading — ${count} words (ceiling 105)`);
      // BR-MET-133, all four facts, read off the SCREEN. This is the half the
      // budget must never buy itself with.
      for (const fact of [
        "stands",
        "disputed amount does not age",
        "no late fees",
        "rest of the bill ages as usual",
        "billed correction",
      ]) {
        check(d.text.includes(fact), `3 · BR-MET-133 on screen: “${fact}”`);
      }
      const back = RETIRED.filter((f) => d.text.includes(f));
      check(back.length === 0, `4 · no retired sentence is back (${back.join(" · ") || "none"})`);
      const codes = internalCodes(d.text);
      check(codes.length === 0, `6 · rule 32 clause 4: no internal code on screen (${codes.slice(0, 4).join(", ") || "none"})`);
      check(!d.scrollsSideways, "8 · the dialog does not scroll sideways");
      await closeDialog(page);
    }
  }

  // ── THE CORRECT WINDOW ──────────────────────────────────────────────────
  console.log("\n── Correct the reading ──");
  const target = READ || READ_BILLED;
  if (!target) {
    notExercised("no reading id was given, so the Correct window was never opened");
  } else {
    await openReadPage(page, target);
    const opened = await openDialogByLabel(page, ["Override read", "Correct billed read"]);
    if (opened === null) {
      // ⚠ The BUTTON is "Override read" and the WINDOW is titled "Correct the
      // reading for M-…" — two names for one thing, which is why this list has
      // to be the button's words and not the window's. On a BILLED reading the
      // control refuses outright (`billedLocked`), so this window can only be
      // reached from a committed head.
      notExercised("the Correct control was absent or refused on this reading");
    } else {
      const d = await page.evaluate(READ_DIALOG);
      await page.screenshot({ path: join(OUT, "correct.png") });
      const count = COUNT_WORDS(d.text);
      console.log(`      opened via “${opened}” · words on screen: ${count}`);
      check(d.box.w > 300 && d.box.h > 200, `7 · the window is really on screen (${JSON.stringify(d.box)})`);
      check(count <= 45, `7 · under budget — ${count} words (ceiling 45; it was 64 in the catalogue before this pass)`);
      // BR-MET-024: the one fact a clerk needs before typing over a register.
      check(
        d.text.includes("history"),
        "7 · BR-MET-024 survives the cut: the window still says this reading stays in the history",
      );
      // Hard rule 3 — the register value is asked for in a named unit, and the
      // unit is a real one rather than an empty placeholder.
      const unitLine = (d.text.match(/In\s+([^\n—]+)—/) || [])[1];
      check(
        Boolean(unitLine && unitLine.trim().length > 0),
        `7 · hard rule 3: the value is asked for in a named unit (“${(unitLine || "").trim()}”)`,
      );
      check(
        !/register reading/i.test(d.text),
        "7 · rule 32 clause 3: the help no longer repeats the field's own label",
      );
      const back = RETIRED.filter((f) => d.text.includes(f));
      check(back.length === 0, `4 · no retired sentence is back (${back.join(" · ") || "none"})`);
      const codes = internalCodes(d.text);
      check(codes.length === 0, `6 · rule 32 clause 4: no internal code on screen (${codes.slice(0, 4).join(", ") || "none"})`);
      check(!d.scrollsSideways, "8 · the dialog does not scroll sideways");
      await closeDialog(page);
    }
  }

  await browser.close();

  console.log(`\n${failures.length === 0 ? "PASS" : "FAIL"} — ${failures.length} failing assertion(s)`);
  for (const f of failures) console.log(`   ⛔ ${f}`);
  if (skipped.length) {
    console.log(`   ⊘ ${skipped.length} assertion(s) NOT exercised by this run:`);
    for (const s of skipped) console.log(`      · ${s}`);
  }
  console.log(`   screenshots in ${OUT}`);
  process.exit(failures.length === 0 ? 0 : 1);
})();
