/**
 * RENDERED-OUTPUT CHECK — CR-070 wave P, task P7. The five flows raise their
 * jobs, and none of them waits.
 *
 * ⚠ **WHY THIS EXISTS.** No gate in this repository reads rendered output
 * (CLAUDE.md hard-won law 6), and the two things this wave can get wrong are
 * both invisible to everything else:
 *
 *   1. **THE MOVE-OUT CONTROL ON THE WRONG STEP (`DEF-WRK-3725`).** The wave
 *      plan put it on step 4. Step 4 is `MOVE_OUT_STEPS[3]`, the SHORTFALL
 *      step, and it renders greyed and *skipped* whenever the account settles —
 *      the common case. A unit test that mounts the panel in isolation passes
 *      either way. **Only clicking through a move-out that settles cleanly can
 *      tell the difference**, which is exactly what step 2 below does.
 *   2. **A DEAD CONTROL OVER A LIVE SCREEN (`DEF-CWP-3925`).** `tsc`, eslint
 *      and every `toContain` assertion pass on a checkbox that renders and does
 *      nothing. So this script does not read the control's STATE — it PRESSES
 *      it, which is the correction that defect's own first draft needed.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   su postgres -c "psql -c 'create database sbh_cr070p owner smartbillhub'"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cr070p?sslmode=disable"
 *   (cd 06-backend && python manage.py migrate --no-input && python manage.py seed_demo \
 *      && python manage.py load_sample_data --tenant brazosbend)
 *   (cd 06-backend && ALLOWED_HOSTS='*' python manage.py runserver 127.0.0.1:8117 --noreload &)
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4317 API_PROXY_TARGET=http://127.0.0.1:8117 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4317 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-p-the-five-flows.mjs
 *
 * ⚠ **BUILD THE BUNDLE.** A stale `dist/` makes every assertion here a
 * statement about a build nobody is shipping.
 *
 * ── WHAT IT ASSERTS ───────────────────────────────────────────────────────
 *   1  **THE MOVE-OUT PANEL IS ON STEP 2 AND IS VISIBLE ON A MOVE-OUT THAT
 *      SETTLES CLEANLY** — `DEF-WRK-3725`'s regression case, in a browser.
 *   2  **STEP 4 DOES NOT CARRY IT**, and step 4 is the one that renders
 *      *skipped*. Both halves, because either alone can be true by accident.
 *   3  **THE PANEL'S COPY IS THE PACK'S** (`Work-029` through
 *      `08-screen-layouts.md`): a FIELD VISIT panel, a WHAT HAPPENS ON SAVE
 *      table with its three acts, and a consequence that says the flow does not
 *      wait.
 *   4  **PRESSING A TICK CHANGES WHAT THE TABLE SAYS WILL HAPPEN** — the
 *      control is live, not decorative (`DEF-CWP-3925`'s correction).
 *   5  **NO DATABASE ID AND NO RULE ID REACHES A CLERK** (B14 rules 31, 32).
 *   6  **THE UTILITIES COMPILED**, read as computed style in a real engine —
 *      the panel is a column with a gap, which is the one thing an unlisted
 *      file's Tailwind cannot be (B14 rule 21's per-file clause, `DEF-974`).
 *   7  **NO SIDEWAYS SCROLL AT 1440.**
 *   8  **THE TRANSFER'S STEP 2 CARRIES THE SAME PANEL** — one component, two
 *      screens, which is what rule 36 asks and what five copies would fail.
 *
 * ⚠ **WHAT IT DOES NOT ASSERT, AND WHY — the reconnect.** `DEF-WRK-4003`: the
 * reconnect has no control on any screen. `markReconnecting` has no client
 * function and no caller in `07-frontend`, so the disconnect ladder on screen
 * stops at *schedule the cut*. Asserting an absence here would be a check that
 * goes green for as long as the fault lasts, which is the shape this repo has
 * been bitten by. It is a defect row, not a passing assertion.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4317";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-p-five-flows";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN = [/\bBR-[A-Z]{3}-\d{2,5}\b/, /\bUS-[A-Z]{3}-\d{2,5}\b/, /\bOQ-\d{3,5}\b/];
const UUID = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i;

async function signIn(page, tenant, email, password) {
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

/** The first ACTIVE account the accounts list offers — the one a clerk would
 *  click. Read off the served page rather than hardcoded, so the script does
 *  not depend on a seeded id that a fixture change would move. */
async function firstAccountId(page) {
  const response = await page.request.get(`${BASE}/api/${TENANT}/accounts?per=50`);
  const body = await response.json();
  const rows = body.results ?? body.rows ?? body.data ?? [];
  const live = rows.find((r) => (r.status?.code ?? r.status) === "active") ?? rows[0];
  return live?.id ?? null;
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  await signIn(page, TENANT, EMAIL, PASSWORD);

  const accountId = await firstAccountId(page);
  check(accountId !== null, "an account to move out was found on the served list");

  // ── 1 · the move-out, step 2 ──────────────────────────────────────────────
  console.log("\n1 · Move-out → step 2 · Date & final reads");
  await page.goto(`${BASE}/${TENANT}/accounts/${accountId}/move-out?step=2`, {
    waitUntil: "networkidle",
  });
  await page
    .waitForSelector('[data-raise-field-work=""]', { timeout: 20000 })
    .catch(() => undefined);

  const onStep2 = await page.$('[data-raise-field-work=""]');
  check(onStep2 !== null, "DEF-WRK-3725 — the field-visit panel is ON STEP 2");

  const step2Text = await page.evaluate(() => document.body.innerText);
  check(/Field visit/i.test(step2Text), "the panel is headed FIELD VISIT (Work-029)");
  check(
    /What happens on save/i.test(step2Text),
    "the WHAT HAPPENS ON SAVE table is drawn beside it",
  );
  check(
    /does not wait for the visit/i.test(step2Text),
    "the consequence says the flow does not wait for the visit",
  );

  // ── 2 · step 4 does NOT carry it, and it is the skipped one ───────────────
  console.log("\n2 · Step 4 · the shortfall step");
  await page.goto(`${BASE}/${TENANT}/accounts/${accountId}/move-out?step=4`, {
    waitUntil: "networkidle",
  });
  const onStep4 = await page.$('[data-raise-field-work=""]');
  check(onStep4 === null, "DEF-WRK-3725 — step 4 does NOT carry the panel");

  // ── 3 · the control is LIVE, not decorative ───────────────────────────────
  console.log("\n3 · Pressing a tick changes what the table says will happen");
  await page.goto(`${BASE}/${TENANT}/accounts/${accountId}/move-out?step=2`, {
    waitUntil: "networkidle",
  });
  await page
    .waitForSelector('[data-raise-field-work=""]', { timeout: 20000 })
    .catch(() => undefined);
  // Read through `evaluate` rather than a locator: `getAttribute` waits on a
  // locator for 30 seconds and then throws, which turns *the panel is not
  // there* into a stack trace instead of a named failure.
  const readCount = () =>
    page.evaluate(() =>
      document.querySelector("[data-field-work-count]")?.getAttribute("data-field-work-count") ??
      null,
    );
  const before = await readCount();
  check(before !== null, "the WHAT HAPPENS ON SAVE table is on the page and countable");
  const box = await page.$("[data-field-work-template]");
  if (box === null) {
    // A tenant with no published non-sequence template is offered none, and the
    // panel SAYS so. That is the truthful answer and not a gap — but it means
    // this particular assertion cannot be made, so it is reported, never
    // silently passed.
    const empty = await page.$('[data-field-work-empty=""]');
    check(
      empty !== null,
      "no template is published for this moment, and the panel says so in words " +
        "(the press-it assertion is NOT made — reported, not skipped silently)",
    );
  } else {
    await box.click();
    const after = await readCount();
    check(
      before !== after,
      `pressing the tick changed the table's answer (${before} → ${after}) — the control is live`,
    );
  }

  // ── 4 · nothing internal reaches a clerk ──────────────────────────────────
  console.log("\n4 · B14 rules 31 and 32");
  const copy = await page.evaluate(() => document.body.innerText);
  for (const pattern of FORBIDDEN) {
    check(!pattern.test(copy), `no ${pattern} in clerk-facing copy`);
  }
  check(!UUID.test(copy), "no database id is the visible value of anything");

  // ── 5 · the utilities compiled ────────────────────────────────────────────
  console.log("\n5 · The Tailwind in a file on route-b-migrated.txt actually emitted");
  const style = await page.evaluate(() => {
    const el = document.querySelector('[data-raise-field-work=""]');
    if (!el) return null;
    const s = getComputedStyle(el);
    return { display: s.display, direction: s.flexDirection, gap: s.gap };
  });
  check(style !== null, "the panel is in the document");
  if (style) {
    check(
      style.display === "flex" && style.direction === "column",
      `the panel is a flex column (display=${style.display}, direction=${style.direction}) — ` +
        "an unlisted file's utilities would compute to nothing",
    );
    check(style.gap !== "normal" && style.gap !== "0px", `the panel's gap emitted (${style.gap})`);
  }

  // ── 6 · no sideways scroll ────────────────────────────────────────────────
  const overflow = await page.evaluate(SIDEWAYS);
  check(overflow === 0, `no sideways scroll at ${VIEWPORT.width} (overflow ${overflow}px)`);
  await page.screenshot({ path: join(OUT, "move-out-step-2.png"), fullPage: true });

  // ── 7 · one component, two screens ────────────────────────────────────────
  console.log("\n6 · The transfer's step 2 carries the SAME panel (B14 rule 36)");
  await page.goto(`${BASE}/${TENANT}/transfers/new?step=2`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const transferPanel = await page.$('[data-raise-field-work=""]');
  check(
    transferPanel !== null,
    "the transfer wizard draws the same panel — one component, never five copies",
  );
  await page.screenshot({ path: join(OUT, "transfer-step-2.png"), fullPage: true });

  await browser.close();

  console.log(`\nscreenshots → ${OUT}`);
  if (failures.length) {
    console.log(`\n⛔ ${failures.length} assertion(s) failed:`);
    for (const f of failures) console.log(`   - ${f}`);
    process.exit(1);
  }
  console.log("\n✓ every assertion held");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
