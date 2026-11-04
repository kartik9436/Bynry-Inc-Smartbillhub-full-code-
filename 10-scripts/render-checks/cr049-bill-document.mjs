#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-049 task 4 — "The bill: store the PDF and HTML at issue", and
//           DEF-2553, the page titled *view the bill as sent* that rebuilt the
//           bill on every open.
// Screens:  S30 → "View the bill as sent"
// Rules:    BR-NOT-027 · BR-BIL-030 (the bill's INPUTS are frozen, which is a
//           different rule) · B14 rule 21 · hard-won law 2 (built is not
//           wired) · law 6 (diff the RUNNING app — no gate in this repo reads
//           rendered output)
// ───────────────────────────────────────────────────────
/**
 * Open a bill in a REAL browser and read what comes back.
 *
 * ⚠ **WHY THIS EXISTS BESIDE 17 PASSING TEST CASES.** jsdom renders no layout,
 * and it renders no iframe content at all — which is precisely where the kept
 * bill is drawn. The whole of `CR-049` is a promise about what a person SEES
 * when they ask to see a bill again, and until something opens a browser and
 * looks, that promise is a docstring (hard-won law 1).
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is looking at an
 * old app — that happened on 2026-08-30 and cost a full investigation.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8031 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4231 API_PROXY_TARGET=http://127.0.0.1:8031 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4231 SMOKE_BILL=<invoice uuid> \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr049-bill-document.mjs
 *
 * `SMOKE_BILL` names a bill issued SINCE the freeze (it has a kept copy) and
 * `SMOKE_BILL_LEGACY` one issued before it (it has none). Give it both and it
 * asserts the pair; give it one and it asserts whichever state that bill is in.
 *
 * ⚠ **THE DEVELOPMENT DATABASE HAS BOTH, SO THE NEXT LANE DOES NOT HAVE TO MAKE
 * ONE.** Its 93 older bills all predate the freeze and answer *"rebuilt"*;
 * `BL-2608-CR049` was issued through the real path on 2026-08-30 and is the
 * kept one. A bill cannot be deleted (hard rule 4), so both stay.
 *
 * ⚠ **AND THE PROOF THIS HARNESS CANNOT MAKE ON ITS OWN:** it reads one build.
 * The case that decides `CR-049` is *change the code that draws a bill, then
 * open a bill already sent*, and that needs two builds. It was run by hand on
 * 2026-08-30 against this stack — one line of `documents._html_for` changed,
 * the backend restarted, and `GET /invoices/{id}/document` then answered with
 * `original_html` unchanged (hash `34536e02…`) while `body` carried the new
 * build's wording. **Automating it means restarting a server mid-run**, which is
 * a different kind of harness; recorded here so the next lane knows the proof
 * exists and how it was taken, rather than assuming this file made it.
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1. THE PAGE STATES WHICH OF THE TWO IT IS. A bill document with no
 *      provenance sentence is the defect, whatever else is on screen.
 *   2. A KEPT BILL DRAWS THE KEPT BYTES — in a frame, sandboxed, and the
 *      frame's own document contains the bill. Not a re-derivation of it.
 *   3. A BILL WITH NO KEPT COPY DRAWS NO FRAME AND NO CHECKSUM, and says
 *      "rebuilt" in a warning. A rebuild under a reassuring caption is the
 *      thing BR-NOT-027 forbids.
 *   4. THE TWO STATES ARE VISIBLY DIFFERENT — asserted as a comparison, not as
 *      two separate impressions.
 *   5. NO STORAGE KEY IS EVER RENDERED (CR-049 step 5d decision 4).
 *   6. THE PAGE DOES NOT SCROLL SIDEWAYS. A bill is wide and an iframe is the
 *      classic way to push a layout out of its box.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4231";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const KEPT = process.env.SMOKE_BILL ?? "";
const LEGACY = process.env.SMOKE_BILL_LEGACY ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr049-bill";
const VIEWPORT = { width: 1728, height: 1080 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS = `Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)`;

/** What the page says about ONE bill — read out of the rendered document. */
const READ_PAGE = `(() => {
  const body = document.body.innerText || "";
  const frame = document.querySelector("article iframe, iframe[srcdoc]");
  return {
    saysOriginal: body.includes("This is the bill as it was issued"),
    saysRebuilt: body.includes("No copy of this bill was kept"),
    saysRebuiltBands: body.includes("Rebuilt below"),
    hasFrame: frame !== null,
    frameSandbox: frame ? frame.getAttribute("sandbox") : null,
    frameHtml: frame ? (frame.getAttribute("srcdoc") || "").slice(0, 4000) : "",
    // WARNING: innerText returns the RENDERED text, and the label carries an
    // uppercase transform, so it reads CHECKSUM on screen. Matching the source
    // string case-sensitively would fail over correct behaviour.
    hasChecksum: /checksum/i.test(body),
    hasKey: body.includes("storage_key") || body.includes("t/"),
    openPdfLabel: [...document.querySelectorAll("a")]
      .map((a) => a.innerText.trim())
      .find((t) => t.toLowerCase().includes("page") || t.toLowerCase().includes("pdf")) || "",
    text: body.slice(0, 1200),
  };
})()`;

async function openBill(page, id, name) {
  await page.goto(`${BASE}/${TENANT}/billing/bills/${id}/document`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
  return page.evaluate(READ_PAGE);
}

(async () => {
  if (KEPT === "" && LEGACY === "") {
    console.log("⛔ give SMOKE_BILL and/or SMOKE_BILL_LEGACY an invoice id");
    process.exit(2);
  }

  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const page = await browser.newPage({ viewport: VIEWPORT });
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 160)}`);
  });

  console.log(`cr049 task 4: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  let kept = null;
  let legacy = null;

  if (KEPT !== "") {
    console.log(`\n── a bill issued SINCE the freeze (${KEPT.slice(0, 8)}) ──`);
    kept = await openBill(page, KEPT, "kept");
    check(
      kept.saysOriginal,
      "the page says THIS IS THE BILL AS IT WAS ISSUED — the sentence the server chose",
    );
    check(kept.hasFrame, "the kept bill is drawn on screen, in its own frame");
    check(
      kept.frameSandbox === "",
      `the frame is sandboxed with no allow-scripts (sandbox="${kept.frameSandbox}")`,
    );
    check(
      kept.frameHtml.includes("Services this period"),
      "the frame holds the BILL — the kept bytes, not a caption over nothing",
    );
    check(kept.hasChecksum, "the checksum that proves the copy is unchanged is on screen");
    check(!kept.saysRebuilt, "it does not also claim no copy was kept");
    check(
      kept.saysRebuiltBands,
      "the structured bands below are labelled as a rebuild, so neither is mistaken for the bill",
    );
    console.log(`   printable link reads: "${kept.openPdfLabel}"`);
    const sideways = await page.evaluate(SIDEWAYS);
    check(sideways === 0, `the page does not scroll sideways (${sideways}px)`);
  }

  if (LEGACY !== "") {
    console.log(`\n── a bill issued BEFORE the freeze (${LEGACY.slice(0, 8)}) ──`);
    legacy = await openBill(page, LEGACY, "legacy");
    check(legacy.saysRebuilt, "the page says NO COPY OF THIS BILL WAS KEPT");
    check(!legacy.hasFrame, "NO original is drawn — there is none, and none is invented");
    check(!legacy.hasChecksum, "no checksum is shown for a document nobody kept");
    check(!legacy.saysOriginal, "it does not also claim to be the original");
    const sideways = await page.evaluate(SIDEWAYS);
    check(sideways === 0, `the page does not scroll sideways (${sideways}px)`);
  }

  if (kept !== null && legacy !== null) {
    console.log("\n── the pair ──");
    check(
      kept.saysOriginal !== legacy.saysOriginal && kept.hasFrame !== legacy.hasFrame,
      "the two states are VISIBLY different — asserted as a comparison, not two impressions",
    );
    check(
      kept.openPdfLabel !== legacy.openPdfLabel,
      `the printable link says which page it opens ("${kept.openPdfLabel}" vs "${legacy.openPdfLabel}")`,
    );
  }

  for (const [name, seen] of [
    ["kept", kept],
    ["legacy", legacy],
  ]) {
    if (seen !== null) {
      check(!seen.text.includes("storage_key"), `${name}: no storage key is rendered`);
    }
  }

  await browser.close();
  console.log(`\nscreenshots → ${OUT}`);
  if (failures.length > 0) {
    console.log(`⛔ ${failures.length} failure(s)`);
    process.exit(1);
  }
  console.log("✓ all checks pass");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
