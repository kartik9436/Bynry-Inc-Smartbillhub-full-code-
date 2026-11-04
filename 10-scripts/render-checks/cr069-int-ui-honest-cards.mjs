/**
 * RENDERED-OUTPUT CHECK — the Integrations grid (S8) and the connect modal
 * (S141), in a real browser, after `DEF-INT-4224`, `4228`, `4229`, `4230`.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. Every defect this file covers was found by the Product Owner
 * OPENING THE SCREEN — not by `tsc`, not by 66 passing cases, not by any gate.
 *
 * ⚠ **AND ONE OF THEM CANNOT BE SEEN ANY OTHER WAY.** `DEF-974`'s trap is a
 * Tailwind utility the theme does not emit: it is in the DOM, so `tsc`, eslint
 * and every `toContain` pass, and it renders as **nothing at all**. This file
 * was written after `max-w-[80%]` did exactly that in `IntegrationsTab.tsx` —
 * caught by grepping the built stylesheet, twenty minutes before it shipped.
 * So this script reads COMPUTED STYLE, not class names: a class assertion is
 * the thing that cannot catch the bug.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone int_ui --export)"
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     DATABASE_URL="$DATABASE_URL" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8164 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4364 API_PROXY_TARGET=http://127.0.0.1:8164 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4364 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr069-int-ui-honest-cards.mjs
 *
 * ⚠ **BUILD THE BUNDLE FIRST.** `server.mjs` serves `dist/`, so a stale build
 * means judging a version nobody ships.
 *
 * ── WHAT IT ASSERTS ───────────────────────────────────────────────────────
 *   1  Every card that offers **Connect** can actually be connected, and every
 *      card that cannot says so ON THE CARD, in words, before anything is
 *      typed. The counts are PRINTED, because a blind spot with no number is
 *      indistinguishable from an empty one (law 7's fifth shape).
 *   2  A held card's reason is a LINE OF TEXT with real pixels — not a `title`
 *      tooltip, which opens on hover, after a delay, and never on a touch
 *      screen (`DEF-SHL-4043`).
 *   3  Pressing a held Connect opens NO modal.
 *   4  The connect modal draws no wireframe annotation: no bordered field-slot
 *      box, no legend, no ALL-CAPS caption, and typewriter type only where
 *      characters are compared (`DEF-INT-4228`).
 *   5  On a sign-in provider the commit is the FOOTER's primary button
 *      (`DEF-INT-4229`), and the dead *Send bills from* box is gone.
 *   6  A required label carries a visible mark (`DEF-INT-4230`, r10 rule 10).
 *   7  The intro description is capped at a readable measure — asserted as
 *      MEASURED PIXELS against the container, which is the only form of this
 *      assertion that survives a class the theme never emitted.
 *   8  Nothing wraps one-word-per-line: the panel geometry a suite cannot see,
 *      because text content is identical however it wraps.
 *   9  No rule id, question id, defect id or database key on the glass
 *      (B14 rules 31 and 32).
 */

import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, readdirSync } from "node:fs";
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4364";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr069-int-ui";
const VIEWPORT = { width: 1440, height: 1000 };
const GRID = `${BASE}/${TENANT}/settings/integrations`;

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr069-int-ui: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 1 · the grid ═══════════════════════════════════════════════════════
  console.log("\n── 1 · every card that offers Connect can be connected ──");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  await page.goto(GRID, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-testid='integrations-grid']", { timeout: 20000 });

  const cards = await page.locator("[data-provider]").count();
  const held = await page.locator("[data-not-connectable]").count();
  const comingSoon = await page.locator("[data-coming-soon-connect]").count();
  const liveConnect = await page.locator('[data-card-action="connect"]').count();
  console.log(
    `   counted: ${cards} cards · ${liveConnect} offering Connect · ${held} held ` +
      `(cannot be connected) · ${comingSoon} coming soon`,
  );
  check(cards > 0, `the grid drew ${cards} cards`);
  check(
    held > 0,
    `${held} card(s) say up front that they cannot be connected — this was 0 before DEF-INT-4224`,
  );

  // ⚠ THE CONTROL. Without this, "everything is held" would pass step 1 just
  // as well as the fix does, and a grid that offers nothing is not the goal.
  check(liveConnect > 0, `${liveConnect} card(s) still offer a Connect that WORKS (the control)`);

  // ═════ 2 · the reason is a line of text, with pixels ══════════════════════
  console.log("\n── 2 · the reason is READ, not hovered ──");
  const heldCard = page.locator("[data-provider]").filter({ has: page.locator("[data-not-connectable]") }).first();
  const heldKey = await heldCard.getAttribute("data-provider");
  const reason = heldCard.locator("[data-held] span").last();
  const reasonBox = await reason.boundingBox();
  const reasonText = (await reason.innerText()).trim();
  console.log(`   the held card is "${heldKey}" and it reads: ${reasonText}`);
  check(reasonText.length > 0, `the reason is drawn as text: "${reasonText}"`);
  check(
    reasonBox !== null && reasonBox.width > 40 && reasonBox.height > 6,
    `the reason occupies real pixels (${Math.round(reasonBox?.width ?? 0)}×${Math.round(reasonBox?.height ?? 0)})`,
  );
  check(reasonText.split(/\s+/).length <= 6, `the reason is five or six words (B14 rule 33)`);
  const heldButton = heldCard.locator("[data-not-connectable]");
  check(await heldButton.isDisabled(), "the held Connect takes no press");

  // ═════ 3 · pressing it opens nothing ═════════════════════════════════════
  console.log("\n── 3 · a held Connect opens no form ──");
  await heldButton.click({ force: true }).catch(() => {});
  await page.waitForTimeout(400);
  check(
    (await page.locator('[role="dialog"]').count()) === 0,
    "no modal opened — a person finds out before they type, not after six fields",
  );

  // ═════ 4 · the description measure, in PIXELS ════════════════════════════
  console.log("\n── 4 · the description is capped at a readable measure ──");
  // ⚠ MEASURED, NOT ASSERTED BY CLASS NAME. `max-w-[80%]` is a class the theme
  // does not emit: present in the DOM, absent from the stylesheet, and the
  // element renders full width. Only geometry can tell the two apart.
  const intro = page.locator("section p").first();
  const introBox = await intro.boundingBox();
  const holder = await intro.evaluate((el) => {
    const parent = el.closest("section");
    return parent ? parent.getBoundingClientRect().width : 0;
  });
  const ratio = introBox && holder ? introBox.width / holder : 1;
  console.log(`   description ${Math.round(introBox?.width ?? 0)}px of ${Math.round(holder)}px = ${(ratio * 100).toFixed(0)}%`);
  check(ratio <= 0.85, `the description caps at ${(ratio * 100).toFixed(0)}% of the content width (B14 rule 18: 80%)`);

  await page.screenshot({ path: `${OUT}/1-grid.png`, fullPage: true });

  // ═════ 5 · the connect modal, on a provider that CAN be connected ════════
  console.log("\n── 5 · the connect form is a form, not a diagram ──");
  await page.locator('[data-card-action="connect"]').first().click();
  await page.waitForSelector('[role="dialog"]', { timeout: 15000 });
  const modal = page.locator('[role="dialog"]').first();

  check((await modal.locator("fieldset[data-field-slot]").count()) === 0, "no bordered field-slot box");
  check((await modal.locator("legend").count()) === 0, "no legend");

  // ALL-CAPS captions, measured from COMPUTED STYLE rather than from text —
  // `text-transform: uppercase` shouts without the source ever being capital.
  const shouty = await modal.evaluate((root) =>
    [...root.querySelectorAll("*")].filter((el) => {
      const s = getComputedStyle(el);
      return (
        s.textTransform === "uppercase" &&
        (el.textContent ?? "").trim().length > 3 &&
        el.children.length === 0
      );
    }).map((el) => (el.textContent ?? "").trim()),
  );
  console.log(`   uppercase-transformed text nodes in the modal: ${shouty.length}${shouty.length ? " → " + JSON.stringify(shouty.slice(0, 4)) : ""}`);
  check(shouty.length === 0, "nothing in the form is set in shouty capitals");

  const mono = await modal.evaluate((root) =>
    [...root.querySelectorAll("*")].filter((el) => {
      const s = getComputedStyle(el);
      return (
        /mono/i.test(s.fontFamily) && (el.textContent ?? "").trim().length > 0 && el.children.length === 0
      );
    }).map((el) => (el.textContent ?? "").trim().slice(0, 40)),
  );
  console.log(`   typewriter-type nodes: ${mono.length}${mono.length ? " → " + JSON.stringify(mono) : ""}`);
  // Monospace is legitimate ONLY for a masked credential hint, where a person
  // compares characters. Anything else is console output on a settings page.
  check(
    mono.every((one) => one.includes("••••")),
    "typewriter type appears only on a masked hint, never on prose",
  );

  await page.screenshot({ path: `${OUT}/2-connect-modal.png`, fullPage: true });

  // ═════ 6 · required fields are marked ════════════════════════════════════
  console.log("\n── 6 · a required box says it is required ──");
  // ⚠ **THIS CHECK PASSED OVER AN EMPTY SET ON ITS FIRST RUN, WHICH IS LAW 7's
  // *structurally incapable of failing*.** It opened whatever card happened to
  // be first — a sign-in provider, which by design has no typed field at all —
  // counted `0 required, 0 marks`, and reported a tick. A required-field check
  // that has never seen a required field is not a check. So the modal that is
  // opened here is chosen BECAUSE it has typed fields, and the count of those
  // fields is asserted to be non-zero before the marks are compared.
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  let inspected = null;
  const connectable = page.locator('[data-card-action="connect"]');
  for (let i = 0; i < (await connectable.count()); i += 1) {
    await connectable.nth(i).click();
    await page.waitForSelector('[role="dialog"]', { timeout: 15000 });
    const m = page.locator('[role="dialog"]').first();
    const n = await m.locator("[data-field-slot] input[required]").count();
    if (n > 0) {
      inspected = { n, marks: await m.locator("[data-field-slot] .field-required").count() };
      await page.screenshot({ path: `${OUT}/4-typed-form.png`, fullPage: true });
      break;
    }
    await page.keyboard.press("Escape");
    await page.waitForTimeout(250);
  }
  check(inspected !== null, "a provider with typed, required fields was found and opened");
  if (inspected !== null) {
    console.log(`   ${inspected.n} required input(s), ${inspected.marks} visible mark(s)`);
    check(inspected.n > 0, `the form under test really has ${inspected.n} required boxes (not a vacuous pass)`);
    check(
      inspected.marks >= inspected.n,
      `every required box carries a visible mark (r10 rule 10) — ${inspected.marks} of ${inspected.n}`,
    );
  }

  // ═════ 7 · no ids on the glass ═══════════════════════════════════════════
  console.log("\n── 7 · nothing internal reaches the clerk ──");
  const modalText = await modal.innerText();
  for (const pattern of FORBIDDEN) {
    check(!pattern.test(modalText), `no ${pattern} on screen`);
  }
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);

  // ═════ 8 · the sign-in provider — the commit is the footer's primary ═════
  console.log("\n── 8 · on a sign-in provider, the commit reads as the commit ──");
  const signInCard = page.locator("[data-provider]").filter({ has: page.locator("[data-card-action]") });
  let opened = false;
  const total = await signInCard.count();
  for (let i = 0; i < total; i += 1) {
    const one = signInCard.nth(i);
    const key = await one.getAttribute("data-provider");
    if (!/microsoft|google/.test(key ?? "")) continue;
    await one.locator("[data-card-action]").click();
    await page.waitForSelector('[role="dialog"]', { timeout: 15000 });
    opened = true;
    const m = page.locator('[role="dialog"]').first();
    const start = m.locator("[data-oauth-start]");
    check((await start.count()) === 1, `${key}: the sign-in press exists exactly once`);
    check(
      (await start.getAttribute("data-variant")) === "primary",
      `${key}: it is PRIMARY tier — it was secondary, buried in the form`,
    );
    const inFooter = await m.locator("[data-footer] [data-oauth-start]").count();
    check(inFooter === 1, `${key}: it sits in the FOOTER, where every other commit lives`);
    // The dead box: required, unsatisfiable, and read by nothing.
    check(
      (await m.locator('[data-field-slot] input[name="send_from"]').count()) === 0,
      `${key}: the "Send bills from" box that collected nothing is gone`,
    );
    const footerWords = (await m.locator("[data-footer-sentence]").innerText()).trim();
    console.log(`   ${key} footer sentence: ${footerWords}`);
    check(!/round trip/i.test(footerWords), "the footer no longer explains our mechanism to a clerk");
    await page.screenshot({ path: `${OUT}/3-signin-modal.png`, fullPage: true });
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
    break;
  }
  check(opened, "a sign-in provider was found and opened");

  // ═════ 9 · the geometry a suite cannot see ═══════════════════════════════
  console.log("\n── 9 · nothing wraps one word per line ──");
  // ⚠ THE ONE THING NO TEST CAN SEE: text content is identical however it
  // wraps, so a panel collapsed to a one-word column passes every assertion in
  // the suite. Measured as: a block of text whose height is many times its
  // line-height while its width is tiny.
  const skinny = await page.evaluate(() => {
    const bad = [];
    for (const el of document.querySelectorAll("p, span, h3, li")) {
      const text = (el.textContent ?? "").trim();
      if (text.split(/\s+/).length < 4 || el.children.length > 0) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const lh = parseFloat(getComputedStyle(el).lineHeight) || 16;
      const lines = Math.round(r.height / lh);
      if (lines >= 4 && r.width < 120) bad.push({ text: text.slice(0, 40), w: Math.round(r.width), lines });
    }
    return bad;
  });
  console.log(`   broken columns: ${skinny.length}${skinny.length ? " → " + JSON.stringify(skinny.slice(0, 3)) : ""}`);
  check(skinny.length === 0, "no block of text is wrapping one word per line");

  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  check(sideways <= 0, `the page does not scroll sideways (${sideways}px)`);

  await browser.close();

  console.log(`\nscreenshots in ${OUT}`);
  if (failures.length) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const one of failures) console.log(`   · ${one}`);
    process.exit(1);
  }
  console.log("\n✓ all checks passed");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
