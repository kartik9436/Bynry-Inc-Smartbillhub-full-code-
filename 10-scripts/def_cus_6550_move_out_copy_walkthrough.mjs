// ── Trace ──────────────────────────────────────────────
// Screen:   ACC-06 step 3 · `Bill & deposit`, the `The draft bill` panel.
// Defect:   `DEF-CUS-6550` — the engine's refusal reached a clerk at 63 words
//           over four sentences, naming a PO ruling date and printing a Python
//           `None`; and every step ended with a 19-word audit line.
// Rules:    B14 rule 32 (no rule id or internal code in clerk-facing copy) ·
//           B14 rule 33 (a FACT is six words, an INSTRUCTION six words per
//           sentence, RATIONALE is ZERO words on screen) · CLAUDE.md hard rule
//           2 (money DISPLAYS to two decimals) · hard-won law 6 — diffing the
//           running app is the ONLY check in this repository that reads
//           rendered output.
// ───────────────────────────────────────────────────────
//
//   BASE=http://127.0.0.1:8972 node 10-scripts/def_cus_6550_move_out_copy_walkthrough.mjs
//
// ⚠ **READ-ONLY, AND IT SAYS SO RATHER THAN CLAIMING IT.** A move-out COMMITS
// and there is no undo (CLAUDE.md hard rule 4). This walk opens step 2, types
// a date, a reason and a reading so the engine has a window to price, presses
// `Continue` — which advances and writes nothing — and photographs step 3.
// **Nothing is submitted and nothing is parked.**
//
// ⚠ **WHY AN ACCOUNT THAT REFUSES TO PRICE, DELIBERATELY.** The sentence this
// walk exists to read only appears when the closing window CANNOT be priced.
// Measured on the seeded `brazosbend` database on 2026-09-24: of 74 open
// accounts, 36 price and **30 refuse with this family**. `A-10432` is one of
// the 30. On an account that prices, the panel draws the bill and this walk
// reports that instead of pretending it read a sentence.
//
// ⚠ **IT COUNTS WORDS RATHER THAN MATCHING A STRING.** A walk asserting the
// new sentence verbatim would pass on the next 60-word one somebody writes, as
// long as they wrote it in this file too. The cap is the rule, so the cap is
// what is checked — and `06-backend/tests/test_def_cus_6550_base_refusals_are_
// short.py` holds the same two numbers where the sentences are COMPOSED, which
// is the only place every one of the eight can be reached.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8972";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/moveout-copy";
const ACCOUNT = process.env.ACCOUNT ?? "01a0d23a-49e9-7dbe-95e1-78dafae4ec03"; // A-10432
const MOVED_OUT_ON = process.env.MOVED_OUT_ON ?? "2026-09-30";

// B14 rule 33, as the two numbers a check can hold. Same figures as the
// backend test and as `G33`; a change belongs in all three.
const WORDS_PER_SENTENCE = 6;
const SENTENCES = 2;
//: Rule 32's families, with CLAUDE.md's own optional module segment and its
//: load-bearing trailing lookahead — without it `DEF-6550` reads as `DEF-655`.
const ID = /\b(?:BR|DEF|OQ|GT|TC|IS|ADR|CR)-(?:[A-Z]{3}-)?\d{1,5}(?!\d)|\bS\d{1,3}\b/;
const RULING_DATE = /\b20\d\d-\d\d-\d\d\b/;

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

let failures = 0;
const check = (label, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
};

const browser = await chromium.launch({ executablePath: resolveChromium() });

// Both staff widths: 1440 is the design target, 1280 the laptop minimum. The
// staff app is not a mobile product (PO 2026-09-10).
for (const width of [1440, 1280]) {
  const suffix = width === 1440 ? "" : "-1280";
  const page = await browser.newPage({ viewport: { width, height: 1400 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}/move-out?step=2`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1800);
  const dateField = await page.$("#moved_out_on");
  if (dateField !== null) {
    await dateField.fill(MOVED_OUT_ON);
    await page.waitForTimeout(400);
  }
  const reason = await page.$("#close_reason");
  if (reason !== null) {
    await reason.selectOption({ index: 1 }).catch(() => undefined);
    await page.waitForTimeout(300);
  }
  const readingBox = await page.$(
    "[data-move-in-readings] input[inputmode], [data-move-in-readings] input[type=text]",
  );
  if (readingBox !== null) {
    await readingBox.fill("1943");
    await page.waitForTimeout(2000);
  }

  // ⚠ **PRESS `Continue`, DO NOT RE-NAVIGATE TO `?step=3`.** A remount throws
  // away the date and the reading typed above, so the preview would have
  // nothing to price and this walk would photograph a different screen from
  // the one a clerk reaches. `Continue` COMMITS NOTHING on this step.
  const advanced = await page.evaluate(() => {
    const button = [...document.querySelectorAll('[data-wizard="actions"] button')].find(
      (b) => /continue/i.test(b.textContent ?? "") && !b.disabled,
    );
    if (button === undefined) return false;
    button.click();
    return true;
  });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${OUT}/step-3${suffix}.png`, fullPage: true });

  const read = await page.evaluate(() => {
    const gap = document.querySelector("[data-final-bill-unavailable]");
    const audit = document.querySelector(".settings-audit-line");
    return {
      stepLine: (document.body.innerText.match(/Step \d+ of \d+[^\n]*/) ?? [""])[0],
      refusal: (gap?.textContent ?? "").trim(),
      audit: (audit?.textContent ?? "").trim(),
      draftSection: document.querySelector('[data-step-section="draft-bill"]') !== null,
      priced: document.querySelector('[data-move-matrix="draft-bill"]') !== null,
      bodyText: document.body.innerText,
    };
  });

  check(`${width}: Continue advanced to step 3`, advanced && read.stepLine.includes("3 of 4"),
    read.stepLine);
  check(`${width}: step 3 draws *The draft bill*`, read.draftSection);

  // ── THE SENTENCE ─────────────────────────────────────────────────────────
  if (read.refusal === "") {
    // NOT a pass and NOT a failure — it is a scope this walk could not cover,
    // and a blind spot with no number beside it is indistinguishable from an
    // empty one (CLAUDE.md hard-won law 7's fifth shape).
    console.log(
      `SKIP  ${width}: this account PRICED, so no refusal sentence was on screen — ` +
        `re-run with ACCOUNT= one that refuses (30 of 74 on the seeded tenant did ` +
        `on 2026-09-24)`,
    );
  } else {
    const sentences = read.refusal
      .split(/(?<=[.!?])\s+/)
      .map((s) => s.trim())
      .filter((s) => s !== "");
    const longest = Math.max(...sentences.map((s) => s.split(/\s+/).length));
    check(
      `${width}: the refusal is at most ${SENTENCES} sentences`,
      sentences.length <= SENTENCES,
      `${sentences.length}: ${JSON.stringify(read.refusal)}`,
    );
    check(
      `${width}: no sentence over ${WORDS_PER_SENTENCE} words`,
      longest <= WORDS_PER_SENTENCE,
      `longest ${longest} — ${JSON.stringify(read.refusal)}`,
    );
    check(
      `${width}: no rule id, defect id or screen id on screen (rule 32)`,
      !ID.test(read.refusal),
      JSON.stringify(read.refusal),
    );
    check(
      `${width}: no ruling date on screen (rule 33 — rationale is zero words)`,
      !RULING_DATE.test(read.refusal),
      JSON.stringify(read.refusal),
    );
    check(
      `${width}: no Python None reaches the clerk`,
      !/\bNone\b/.test(read.refusal),
      JSON.stringify(read.refusal),
    );
    check(
      `${width}: money on this sentence is 2dp, never the stored 4 or 6 (hard rule 2)`,
      !/\d+\.\d{3,}/.test(read.refusal),
      JSON.stringify(read.refusal),
    );
    console.log(`      the clerk reads: ${JSON.stringify(read.refusal)}`);
  }

  // ── THE AUDIT LINE, GONE FROM EVERY STEP ─────────────────────────────────
  check(`${width}: step 3 has no audit-log line`, read.audit === "" &&
    !read.bodyText.includes("audit log"), JSON.stringify(read.audit));
}

await browser.close();
console.log(failures === 0 ? "\nALL CHECKS PASS" : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
