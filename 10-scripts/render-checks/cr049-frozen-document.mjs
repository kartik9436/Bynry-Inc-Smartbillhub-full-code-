#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-049 task 3 — "A reprint and a regulator request serve the stored
//           copy and never re-render" (PO 2026-08-30, BR-NOT-027).
// Screens:  SET-12 → Messages (the dispatch queue) → "Show what we sent"
// Rules:    BR-NOT-027 · B14 rule 21 · hard-won law 2 (built is not wired) ·
//           law 6 (diff the RUNNING app — no gate in this repo reads rendered
//           output)
// ───────────────────────────────────────────────────────
/**
 * Click the reprint in a REAL browser and read what comes back.
 *
 * ⚠ **WHY THIS EXISTS BESIDE 220 PASSING DOM CASES.** jsdom renders no layout
 * and, more to the point here, jsdom is not the product: the whole of `CR-049`
 * is a promise about what a person SEES when they ask to see a letter again, and
 * until something opens a browser and looks, that promise is a docstring
 * (hard-won law 1). This is the instrument for it.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is looking at an old
 * app — that happened on 2026-08-30 and cost a full investigation.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8011 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4181 API_PROXY_TARGET=http://127.0.0.1:8011 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4181 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr049-frozen-document.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1. THE CONTROL EXISTS ON A QUEUE ROW. If it does not, the route this lane
 *      built is unreachable and `CR-049` is still worth nothing — which is
 *      exactly the state the task-2 lane reported and this task closes.
 *   2. CLICKING IT OPENS AN ANSWER, and the answer is ONE OF THE TWO STATES —
 *      never blank, never both.
 *   3. THE TWO STATES ARE DISTINGUISHABLE ON SCREEN. The panel either names
 *      itself the original, or carries the "not the original" sentence. A panel
 *      that showed a document with neither is the defect.
 *   4. NO STORAGE KEY IS EVER RENDERED (CR-049 step 5d decision 4).
 *   5. THE PAGE DOES NOT SCROLL SIDEWAYS with the panel open — a letter is
 *      long, and `<pre>` is the classic way to push a layout out of its box.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4181";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr049-frozen";
const VIEWPORT = { width: 1728, height: 1080 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS = `Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)`;

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const page = await browser.newPage({ viewport: VIEWPORT });
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 160)}`);
  });

  console.log(`cr049: ${BASE} tenant=${TENANT} viewport=${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // The queue lives on the Messages sub-tab (CR-048 wave I moved it there).
  await page.goto(`${BASE}/${TENANT}/settings/notifications/messages`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "queue.png"), fullPage: true });

  // ── 1 · IS THE CONTROL THERE? ─────────────────────────────────────────────
  const buttons = await page.$$('button:has-text("Show what we sent")');
  check(
    buttons.length > 0,
    `the queue offers "Show what we sent" (${buttons.length} row(s) carry it) — ` +
      "without this the reprint route is unreachable and CR-049 is still inert",
  );
  if (buttons.length === 0) {
    await browser.close();
    console.log(`\n⛔ ${failures.length} failure(s)`);
    process.exit(1);
  }

  // ── 2 · CLICK IT ──────────────────────────────────────────────────────────
  await buttons[0].click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: join(OUT, "document.png"), fullPage: true });

  const panel = await page.evaluate(`(() => {
    const heads = [...document.querySelectorAll("h3")];
    const head = heads.find((h) => (h.innerText || "").includes("The document we sent"));
    if (!head) return { missing: true };
    const section = head.closest("section");
    const text = (section.innerText || "").trim();
    const r = section.getBoundingClientRect();
    return {
      width: Math.round(r.width),
      height: Math.round(r.height),
      text,
      hasPre: section.querySelector("pre") !== null,
    };
  })()`);

  check(panel.missing !== true, "clicking it opens the document panel");
  if (panel.missing === true) {
    await browser.close();
    console.log(`\n⛔ ${failures.length} failure(s)`);
    process.exit(1);
  }
  console.log(`   panel ${panel.width}x${panel.height}px`);

  // ── 3 · WHICH OF THE TWO STATES, AND IS IT SAYING SO? ────────────────────
  const saysOriginal =
    panel.text.includes("This is the document as it was sent") ||
    panel.text.includes("It has not been re-rendered");
  const saysRebuilt = panel.text.includes("Re-rendered from data, not the original");
  const saysExempt =
    panel.text.includes("send test") || panel.text.includes("In-app alerts keep their own copy");

  check(
    saysOriginal || saysRebuilt || saysExempt,
    "the panel states WHICH it is — a document with no provenance sentence is the defect",
  );
  check(
    !(saysOriginal && saysRebuilt),
    "it does not claim both at once",
  );
  console.log(
    `   state: ${saysOriginal ? "ORIGINAL" : saysRebuilt ? "NOT THE ORIGINAL" : saysExempt ? "EXEMPT" : "??"}`,
  );

  // ⚠ THE PAIRING THAT MATTERS: a letter is shown ONLY beside "this is the
  // original". A `<pre>` of document text under the re-rendered sentence would
  // be a reconstruction wearing a caption — the thing BR-NOT-027 forbids.
  if (saysRebuilt) {
    check(
      panel.hasPre === false,
      "no letter is drawn beside the 'not the original' sentence",
    );
  }
  if (saysOriginal) {
    check(panel.hasPre === true, "the original's text is actually on screen");
  }

  // ── 4 · NO STORAGE KEY, EVER ─────────────────────────────────────────────
  check(
    !panel.text.includes("storage_key"),
    "no storage key is rendered (CR-049 step 5d decision 4)",
  );

  // ── 5 · THE PANEL DOES NOT PUSH THE PAGE SIDEWAYS ────────────────────────
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `the page does not scroll sideways with the panel open (${sideways}px)`);

  await browser.close();
  console.log(`\nscreenshots → ${OUT}`);
  if (failures.length > 0) {
    console.log(`⛔ ${failures.length} failure(s)`);
    for (const f of failures) console.log(`   - ${f}`);
    process.exit(1);
  }
  console.log("✓ all checks passed");
})();
