/**
 * RENDERED-OUTPUT CHECK — `CR-085` step 2 lane 3: **starting and stopping
 * service**, in a real browser, at **390 AND 1280**.
 *
 * ⚠ **WHY THIS EXISTS AND WHY IT IS A SECOND SCRIPT RATHER THAN AN EDIT TO
 * `cr068-c-start-service.mjs`.** That script proves wave C's JOURNEY — the four
 * rows and their figures, the draft that survives a closed tab, the consent,
 * the reference. This one proves the four defects `CR-085` step 2 lane 3
 * fixed, every one of which is a property of the RENDERED SCREEN that no suite
 * in this repo can see:
 *
 *   `DEF-CWP-4877` (high) — six fields marked required gated nothing, and the
 *                  refusal threw away the step the server sent.
 *   `DEF-CWP-4876` — steps 2, 3 and 4 drew no heading of any kind.
 *   `DEF-CWP-4875` — *IF YOU APPLY* printed `— deposit on your first bill.`
 *   `DEF-CWP-4878` — B14 rule 39's wizard anchors, MEASURED with
 *                  `getComputedStyle` rather than read off a stylesheet.
 *   `DEF-CWP-4931` — signed out, the two signed-in screens drew the STAFF
 *                  failure panel with a *Download error report* button and no
 *                  way to sign in (R-10 · R-22 · `CPB-17`).
 *
 * ⚠ **BOTH WIDTHS, EVERY TIME.** The skills file's own rule for a customer
 * screen: *"Portal · verify at 390 and 1280 · ignore nothing — those two are
 * the mandatory pair."* A four-step wizard that works at 1280 and cramps at 390
 * fails. Every geometry below is read at both and printed at both.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=8413 API_PROXY_TARGET=http://127.0.0.1:8000 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:8413 SMOKE_TENANT=brazosbend \
 *     SMOKE_ADDRESS="1408 Bluestem Ln" \
 *     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr085-lane3-start-and-stop.mjs
 *
 * ⚠ **THE GUEST EDGE IS THROTTLED AT SIXTY REQUESTS A MINUTE PER ADDRESS**
 * (`BR-CWP-022`). Two runs inside one minute make more than that, the saves are
 * turned away with `429`, and the form legitimately loses what was typed —
 * which looks exactly like a broken form and is not one. Space the runs, or
 * clear the cache the way `cr068-c-start-service.mjs` documents.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  try {
    execFileSync(wanted, ["--version"], { stdio: "ignore" });
    return wanted;
  } catch {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const candidate of [join(root, dir, "chrome-linux", "chrome"), join(root, dir)]) {
        try {
          execFileSync(candidate, ["--version"], { stdio: "ignore" });
          return candidate;
        } catch {
          // keep looking
        }
      }
    }
    return wanted;
  }
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8413";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const ADDRESS = process.env.SMOKE_ADDRESS ?? "1408 Bluestem Ln";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr085-lane3";
/** The mandatory pair. Nothing here is measured at only one of them. */
const WIDTHS = [
  { label: "390", width: 390, height: 860 },
  { label: "1280", width: 1280, height: 900 },
];

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** A date input wants `YYYY-MM-DD`; three weeks out, always a weekday. */
function startDate() {
  const day = new Date(Date.now() + 21 * 24 * 3600 * 1000);
  while (day.getDay() === 0 || day.getDay() === 6) day.setDate(day.getDate() + 1);
  return day.toISOString().slice(0, 10);
}

/**
 * B14 rule 39's anchors, read off the LIVE layout.
 *
 * ⚠ **`getComputedStyle` AND `getBoundingClientRect`, NEVER A STYLESHEET.** A
 * Tailwind utility is emitted only for a file the ledger owns, so a class can
 * be in the DOM, in the source, and declared by nothing — `tsc`, eslint and
 * every `toContain` pass over it and only a real engine can tell (`DEF-974`).
 */
const ANCHORS = `(() => {
  const px = (v) => Math.round(parseFloat(v) || 0);
  const out = {};
  const step = document.querySelector('[data-stepper] li');
  if (step) {
    const s = getComputedStyle(step);
    out.stepPadding = [px(s.paddingTop), px(s.paddingRight)];
    out.stepIconGap = px(s.columnGap || s.gap);
  }
  const bar = document.querySelector('[data-stepper]');
  if (bar) {
    const s = getComputedStyle(bar);
    out.railMarginBottom = px(s.marginBottom);
    out.stepGap = px(s.columnGap || s.gap);
  }
  const field = document.querySelector('[data-field]');
  if (field) {
    const label = field.querySelector('label');
    const input = field.querySelector('input, select, textarea');
    if (label && input) {
      out.labelToInput = Math.round(input.getBoundingClientRect().top - label.getBoundingClientRect().bottom);
    }
    const helper = field.querySelector('p');
    if (helper && input) {
      out.inputToHelper = Math.round(helper.getBoundingClientRect().top - input.getBoundingClientRect().bottom);
    }
  }
  const fields = [...document.querySelectorAll('[data-field]')];
  if (fields.length > 1) {
    const a = fields[0].getBoundingClientRect();
    const b = fields[1].getBoundingClientRect();
    out.fieldToField = Math.round(b.top - a.bottom);
  }
  out.sideways = Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth);
  out.h1 = [...document.querySelectorAll('h1')].map((h) => h.textContent.trim());
  return out;
})()`;

/** Every sentence on screen, so a leading em dash can be looked for. */
const SENTENCES = `[...document.querySelectorAll('[data-consequence] li')].map((n) => n.textContent.trim())`;

async function walk(context, size) {
  const page = await context.newPage();
  await page.setViewportSize({ width: size.width, height: size.height });
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  console.log(`\n══════ ${size.label}px ══════`);

  // ═════ 1 · CWP-008 — step 1, and the em-dash sentence ════════════════════
  console.log(`\n── 1 · ${ADDRESS}: the availability answer (CWP-008) ──`);
  await page.goto(`${BASE}/${TENANT}/portal/start-service`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-008"]', { timeout: 20000 });
  await page.fill("#availability-address", ADDRESS);
  await page.click('[data-action="check"]');
  await page.waitForSelector('[data-action="apply"]', { timeout: 20000 });
  const bullets1 = await page.evaluate(SENTENCES);
  console.log(`   IF YOU APPLY: ${JSON.stringify(bullets1)}`);
  // ⚠ `DEF-CWP-4875` — the assertion that would have caught it on the day.
  check(
    bullets1.every((one) => !one.startsWith("—")),
    "no sentence in IF YOU APPLY begins with an em dash",
  );
  await page.screenshot({ path: join(OUT, `${size.label}-1-availability.png`), fullPage: true });

  // ═════ 2 · step 2 — the head, and the gate ═══════════════════════════════
  console.log("\n── 2 · WHEN (CWP-047 step 2): the head, and the gate ──");
  await page.click('[data-action="apply"]');
  await page.waitForSelector('[data-step="when"]', { timeout: 20000 });
  const step2 = await page.evaluate(ANCHORS);
  console.log(`   h1: ${JSON.stringify(step2.h1)}`);
  // ⚠ `DEF-CWP-4876` — this measured `h1 count 0` at both widths on 2026-09-11.
  check(step2.h1.length === 1, `exactly one <h1> on the step (${step2.h1.length})`);
  check(
    step2.h1[0] === "When would you like it on?",
    `the drawn title: ${JSON.stringify(step2.h1[0])}`,
  );
  const sub2 = await page.locator('[data-screen="CWP-047"]').innerText();
  check(sub2.includes("step 2 of 4"), "the sub-line says step 2 of 4");
  check(
    sub2.includes(ADDRESS.split(",")[0]),
    "and it names the address being applied for — which step 1 was the last place to say",
  );
  check(step2.sideways === 0, `no sideways scroll (${step2.sideways}px)`);

  // ⚠ `DEF-CWP-4877` — the gate. Held, with the reason ON SCREEN and not only
  // on `title`, because nobody can hover a tooltip on a phone.
  const held2 = await page.locator('[data-action="continue"]').isDisabled();
  check(held2, "Continue is HELD with no start date");
  const reason2 = await page.locator('[data-step-held="start_date"]').count();
  check(reason2 === 1, "and the reason is visible text beside it, not only a tooltip");
  if (reason2 === 1) {
    console.log(`   reason: ${(await page.locator("[data-step-held]").innerText()).trim()}`);
  }
  await page.screenshot({ path: join(OUT, `${size.label}-2-when-held.png`), fullPage: true });

  await page.fill("#requested_start", startDate());
  await page.locator("#requested_start").blur();
  await page.waitForTimeout(600);
  check(
    !(await page.locator('[data-action="continue"]').isDisabled()),
    "typing the date releases it",
  );
  const bullets2 = await page.evaluate(SENTENCES);
  console.log(`   WHAT IT COSTS TO START: ${JSON.stringify(bullets2)}`);
  check(
    bullets2.every((one) => !one.startsWith("—")),
    "no sentence in WHAT IT COSTS TO START begins with an em dash",
  );

  // ⚠ `DEF-CWP-4878` — rule 39's anchors, at THIS width.
  console.log(
    `   rule 39 @${size.label}: step ${JSON.stringify(step2.stepPadding)} · icon gap ${step2.stepIconGap} · ` +
      `step gap ${step2.stepGap} · rail mb ${step2.railMarginBottom} · label→input ${step2.labelToInput} · ` +
      `input→helper ${step2.inputToHelper} · field→field ${step2.fieldToField}`,
  );
  check(
    step2.stepPadding[0] === 16 && step2.stepPadding[1] === 20,
    `wizard step cell 16×20 (measured ${step2.stepPadding.join("×")})`,
  );
  check(step2.stepIconGap === 12, `wizard step icon gap 12 (measured ${step2.stepIconGap})`);
  check(step2.railMarginBottom === 24, `wizard rail margin-bottom 24 (measured ${step2.railMarginBottom})`);
  check(step2.labelToInput === 5, `label → input 5 (measured ${step2.labelToInput})`);
  check(step2.inputToHelper === 6, `input → helper 6 (measured ${step2.inputToHelper})`);

  // ═════ 3 · step 3 — the head, the gate, and the asterisk that came off ════
  console.log("\n── 3 · ABOUT YOU (CWP-047 step 3) ──");
  await page.click('[data-action="continue"]');
  await page.waitForSelector('[data-step="about"]', { timeout: 20000 });
  const step3 = await page.evaluate(ANCHORS);
  check(step3.h1.length === 1 && step3.h1[0] === "About you", `the drawn title: ${JSON.stringify(step3.h1)}`);
  check(
    (await page.locator('[data-screen="CWP-047"]').innerText()).includes("step 3 of 4"),
    "the sub-line says step 3 of 4",
  );
  check(await page.locator('[data-action="continue"]').isDisabled(), "Continue is HELD on an empty form");
  console.log(`   reason: ${(await page.locator("[data-step-held]").innerText()).trim()}`);
  // ⚠ The asterisk came OFF the date of birth: the server accepts an
  // application without one, so demanding it refused applications the product
  // accepts (`DEF-CWP-4877`, and the decision log of 2026-09-11).
  const dobLabel = await page.locator('[data-field="date_of_birth"] label').innerText();
  check(!dobLabel.includes("*"), `the date of birth is not marked required: ${JSON.stringify(dobLabel)}`);
  const nameLabel = await page.locator('[data-field="first_name"] label').innerText();
  check(nameLabel.includes("*"), "and the first name still is — the asterisk now means something");
  check(step3.sideways === 0, `no sideways scroll (${step3.sideways}px)`);
  await page.screenshot({ path: join(OUT, `${size.label}-3-about-held.png`), fullPage: true });

  await page.fill("#first_name", "Daniel");
  await page.fill("#last_name", "Okafor");
  await page.fill("#email", "d.okafor@example.test");
  await page.fill("#phone", "(512) 555-7730");
  await page.locator("#phone").blur();
  await page.waitForTimeout(600);
  check(
    !(await page.locator('[data-action="continue"]').isDisabled()),
    "filling the name and the contact releases it — and the date of birth is still empty",
  );

  // ═════ 4 · step 4 — the head, and the commit ═════════════════════════════
  console.log("\n── 4 · CHECK AND SEND (CWP-009 step 4) ──");
  await page.click('[data-action="continue"]');
  await page.waitForSelector('[data-screen="CWP-009"]', { timeout: 20000 });
  const step4 = await page.evaluate(ANCHORS);
  check(
    step4.h1.length === 1 && step4.h1[0] === "Check this, then send it",
    `the drawn title: ${JSON.stringify(step4.h1)}`,
  );
  check(
    (await page.locator('[data-screen="CWP-009"]').innerText()).includes("step 4 of 4"),
    "the sub-line says step 4 of 4",
  );
  check(!(await page.locator('[data-action="send"]').isDisabled()), "the commit is live on a complete form");
  const readBack = await page.locator('[data-screen="CWP-009"]').innerText();
  check(readBack.includes("Daniel Okafor"), "the read-back names the applicant — never `Applicant —`");
  check(step4.sideways === 0, `no sideways scroll (${step4.sideways}px)`);
  await page.screenshot({ path: join(OUT, `${size.label}-4-check.png`), fullPage: true });

  // ═════ 5 · signed out at a signed-in address — R-10 · R-22 · CPB-17 ══════
  for (const route of ["stop-or-restart", "final-bill"]) {
    console.log(`\n── 5 · /${route}, signed OUT ──`);
    await page.goto(`${BASE}/${TENANT}/portal/${route}`, { waitUntil: "networkidle" });
    await page.waitForSelector("[data-portal-state]", { timeout: 20000 });
    const kind = await page.locator("[data-portal-state]").getAttribute("data-portal-state");
    const text = await page.locator("[data-portal-state]").innerText();
    console.log(`   state=${kind} · ${JSON.stringify(text.trim().slice(0, 140))}`);
    // ⚠ R-22 — told apart by its SENTENCE, and the kind is in the DOM so the
    // rule is observable by something other than a person reading fifty
    // screens.
    check(kind === "failed", `the state names itself: ${kind}`);
    // ⚠ R-10 — the way out is in the card, beside the message.
    check(
      (await page.locator('[data-way-out="sign-in"]').count()) === 1,
      "a Sign in control sits inside the card, next to the sentence",
    );
    check(
      !text.includes("Download error report"),
      "and the staff's Download error report is gone from a customer's screen",
    );
    const sideways = await page.evaluate(
      "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)",
    );
    check(sideways === 0, `no sideways scroll (${sideways}px)`);
    await page.screenshot({ path: join(OUT, `${size.label}-5-${route}-signed-out.png`), fullPage: true });
  }

  await page.close();
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext();
  console.log(`cr085-lane3: ${BASE} tenant=${TENANT} address=${JSON.stringify(ADDRESS)}`);
  for (const size of WIDTHS) {
    await walk(context, size);
  }
  await browser.close();

  console.log(`\n${failures.length === 0 ? "ALL CHECKS PASSED" : `${failures.length} FAILED:`}`);
  for (const one of failures) console.log(`  ⛔ ${one}`);
  console.log(`screenshots: ${OUT}`);
  process.exit(failures.length === 0 ? 0 : 1);
})();
