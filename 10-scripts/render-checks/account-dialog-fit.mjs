/**
 * ACCOUNT DIALOGS — DOES EVERY PANEL FIT THE WINDOW IT OPENS IN?
 * ══════════════════════════════════════════════════════════════════════════
 *
 * ⚠ **THE FAULT THIS EXISTS FOR: A DIALOG A CLERK CANNOT CLOSE.** `DEF-SHL-5158`.
 * Measured at 1440x900 before the fix — Record a payment **1142px**, Write to
 * customer **1329px**, Edit account **1199px** — the card grew past the screen,
 * `.modal-overlay` scrolled the whole thing, and the ✕ went off the top of the
 * window with it. Nothing in this repo could see it: the element is in the DOM,
 * it has its classes, `tsc` and every suite pass, and **no gate reads rendered
 * output** (hard-won law 6). It is found by opening the product and looking, or
 * by this.
 *
 * ⚠ **AND IT WAS REPORTED AS CORRECT ONCE ALREADY.** When the eight wide
 * overlays were capped, these four were measured, called *"short"*, and left —
 * so the numbers above were sitting in a lane report that said the opposite.
 * That is why this is a script and not a reading: a measurement nobody can
 * re-run is an opinion with a number in it.
 *
 * WHAT IT ASSERTS, per dialog, at 1280 and 1440 (the staff app's two required
 * widths, PO 2026-09-10), viewport height 900:
 *
 *   1 · the card is no taller than the window less the overlay's 32px inset
 *       top and bottom — B14 rule 39's scale, and the same cap the wide
 *       variant already takes;
 *   2 · the CLOSE control is inside the viewport — the one that decides
 *       whether a clerk is stuck;
 *   3 · the FOOTER's last button is inside the viewport, so the commit is
 *       reachable without scrolling the page;
 *   4 · the page body does not scroll sideways.
 *
 * A dialog that cannot be opened on the seeded account is reported as SKIPPED
 * with its reason, never counted as a pass — a check that reports zero over a
 * scope it silently excludes is the shape law 7 warns about.
 *
 * RUN IT (the production join — the vite dev server has NO /api proxy):
 *   cd 07-frontend && npx vite build
 *   API_PROXY_TARGET=http://127.0.0.1:8011 PORT=8080 node server.mjs &
 *   node 10-scripts/render-checks/account-dialog-fit.mjs
 *
 * Exit 0 = every dialog fits · 1 = a finding · 2 = nothing could be measured.
 */

import { existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const WIDTHS = [1280, 1440];
const HEIGHT = 900;
/** The overlay's own inset, top and bottom. B14 rule 39's scale. */
const INSET = 64;

/**
 * ⚠ **THE LIST IS DISCOVERED FROM THE PAGE, NOT TYPED HERE — AND THE FIRST
 * DRAFT TYPED IT.** That draft named seven dialogs. Lane D then added an
 * eighth (`Change unit`) and reported, correctly, that this check *"walks a
 * hardcoded list and my new dialog is not in it, so that zero says nothing
 * about it"* — it printed **0 findings over 14 frames** while never opening
 * the new one at all. A check that reports zero over a scope it silently
 * excludes is hard-won law 7's own example, and this file was quoting that law
 * in its header while committing it.
 *
 * So the controls are enumerated from the rendered account page: every button
 * in the header's action row, every glyph on the icon rail, and every pencil
 * on an Overview group. **A dialog added tomorrow is measured tomorrow**, with
 * nobody remembering to edit this file.
 *
 * A control that is DISABLED is reported as skipped WITH the reason it carries,
 * never counted as a pass — a greyed pencil and an unchecked dialog must not
 * look the same in this output.
 */
const DISCOVER = `
  const seen = new Map();
  const add = (el, where) => {
    if (!(el instanceof HTMLElement)) return;
    const name = (el.getAttribute("aria-label") || el.textContent || "").trim();
    // A tab is a <button> too. Clicking one moves the screen instead of opening
    // a dialog, and the next measurement would then be of the wrong page.
    if (el.getAttribute("role") === "tab") return;
    if (!name || seen.has(name)) return;
    seen.set(name, { name, where, disabled: el.hasAttribute("disabled"),
                     reason: el.getAttribute("title") || "" });
  };
  // The page head's action row, the icon rail and the Overview's pencils —
  // the three places an account action can live. \`.page-header-actions\` is a
  // stylesheet class rather than a data hook because that is what the shared
  // page header actually draws; if it is ever renamed this check finds nothing
  // and SAYS SO, which is the outcome the zero-guard below exists for.
  document.querySelectorAll(".page-header-actions button").forEach((b) => add(b, "header"));
  document.querySelectorAll("[data-account-icon-rail] button").forEach((b) => add(b, "rail"));
  document.querySelectorAll("[data-overview-group] button").forEach((b) => add(b, "pencil"));
  return [...seen.values()];
`;

const findings = [];
const skipped = [];
const measured = [];
const say = (...a) => console.log(...a);

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}

async function firstAccountPath(page) {
  await page.goto(`${BASE}/${TENANT}/accounts`, { waitUntil: "networkidle" });
  const href = await page.getAttribute('a[href*="/accounts/"]', "href");
  if (!href) throw new Error("no account row on the Accounts list — seed one first");
  return href;
}

const run = async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  try {
    for (const width of WIDTHS) {
      const context = await browser.newContext({ viewport: { width, height: HEIGHT } });
      const page = await context.newPage();
      await signIn(page);
      const accountPath = await firstAccountPath(page);

      // ⚠ **DISCOVER ON THE ACCOUNT, NOT ON THE LIST.** `firstAccountPath`
      // leaves the browser on `/accounts`, and the first draft enumerated
      // controls right there — finding the LIST's three buttons and none of
      // the account's twenty-two. It reported *"2 frames, 0 findings"*, which
      // is a pass over almost nothing.
      await page.goto(`${BASE}${accountPath}`, { waitUntil: "networkidle" });
      await page.waitForSelector("[data-account-overview]", { timeout: 10000 });
      const controls = await page.evaluate(new Function(DISCOVER));
      if (controls.length === 0) {
        skipped.push(`@${width} — no control was found on the account page at all`);
      }
      for (const control of controls) {
        if (control.disabled) {
          // A greyed pencil is a real answer and must not read like a measured
          // pass. Its reason is printed so the skip can be judged.
          skipped.push(
            `${control.name} @${width} (${control.where}) — disabled: ${control.reason || "no reason given"}`,
          );
          continue;
        }
        await page.goto(`${BASE}${accountPath}`, { waitUntil: "networkidle" });
        try {
          // By the ACCESSIBLE NAME — `getByRole`, never an attribute selector.
          // An earlier draft matched `[aria-label=…], [title=…]` and silently
          // skipped *Record a payment*, whose words are the button's TEXT.
          await page
            .getByRole("button", { name: control.name, exact: true })
            .first()
            .click({ timeout: 4000 });
          await page.waitForSelector(".modal-card", { timeout: 4000 });
        } catch {
          skipped.push(`${control.name} @${width} (${control.where}) — did not open a dialog`);
          continue;
        }
        // Let the body settle; a card mid-fetch is shorter than the card a
        // clerk sees, which would make this pass wrongly.
        await page.waitForTimeout(400);

        const m = await page.evaluate(() => {
          const card = document.querySelector(".modal-card");
          if (!card) return null;
          const box = card.getBoundingClientRect();
          const close = card.querySelector(".modal-close, [data-modal-close]");
          const footButtons = card.querySelectorAll(".modal-foot button, .modal-foot a");
          const last = footButtons[footButtons.length - 1];
          const rect = (el) => (el ? el.getBoundingClientRect() : null);
          return {
            height: Math.round(box.height),
            top: Math.round(box.top),
            close: rect(close) && { top: Math.round(rect(close).top), bottom: Math.round(rect(close).bottom) },
            foot: rect(last) && { top: Math.round(rect(last).top), bottom: Math.round(rect(last).bottom) },
            sideways: document.documentElement.scrollWidth > document.documentElement.clientWidth,
          };
        });
        if (m === null) {
          skipped.push(`${control.name} @${width} — the card vanished before it could be measured`);
          continue;
        }
        measured.push(`${control.name} @${width}: ${m.height}px tall, top ${m.top}`);

        const cap = HEIGHT - INSET;
        if (m.height > cap) {
          findings.push(`${control.name} @${width}: the card is ${m.height}px in a ${HEIGHT}px window (cap ${cap})`);
        }
        if (m.close === null) {
          findings.push(`${control.name} @${width}: no close control found on the card`);
        } else if (m.close.top < 0 || m.close.bottom > HEIGHT) {
          findings.push(`${control.name} @${width}: the close control is off screen (top ${m.close.top})`);
        }
        if (m.foot !== null && (m.foot.top < 0 || m.foot.bottom > HEIGHT)) {
          findings.push(`${control.name} @${width}: the footer button is off screen (bottom ${m.foot.bottom})`);
        }
        if (m.sideways) {
          findings.push(`${control.name} @${width}: the page scrolls sideways`);
        }
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }

  say("");
  say("── measured ──");
  for (const line of measured) say(`  ${line}`);
  if (skipped.length) {
    say("");
    say(`── ${skipped.length} SKIPPED — not judged either way ──`);
    for (const line of skipped) say(`  ${line}`);
  }
  say("");
  if (findings.length) {
    say(`${findings.length} finding(s):`);
    for (const line of findings) say(`  ✗ ${line}`);
  } else if (measured.length === 0) {
    say("NOTHING WAS MEASURED — this is not a pass. Check the stack is up.");
  } else {
    say(`every dialog fits: ${measured.length} frame(s), 0 finding(s)`);
  }
  process.exitCode = findings.length ? 1 : measured.length === 0 ? 2 : 0;
};

run().catch((error) => {
  console.error(error);
  process.exit(2);
});
