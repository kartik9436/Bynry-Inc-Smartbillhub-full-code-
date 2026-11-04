#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-049 task 8 — "Note a template or item change as a change: the
//           audit trail on the wording itself" (PO 2026-08-30, BR-NOT-027
//           part 3).
// Screens:  SET-10 → a template → Version history → the Changed cell
// Rules:    BR-NOT-027 part 3 · BR-NOT-028 (PROPOSED) · B14 rule 21 · the PO's
//           ruling of 2026-08-30 that a table cell holds a VALUE and the
//           sentence goes in a tooltip or the opened detail · hard-won law 2
//           (built is not wired) · law 6 (diff the RUNNING app — no gate in
//           this repo reads rendered output)
// ───────────────────────────────────────────────────────
/**
 * Open the change trail in a REAL browser and read what comes back.
 *
 * ⚠ **WHY THIS EXISTS BESIDE PASSING DOM CASES.** jsdom performs no layout, so
 * the one thing this feature could get most visibly wrong — a cell that holds a
 * paragraph instead of a value, which is the 645px defect `DEF-2479` was about
 * — is invisible to every `toContain` in the suite. This is the instrument for
 * it, and it is the only one.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is looking at an
 * old app; that cost a full investigation on 2026-08-30.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://…/sbh_cr049_t8_ui" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8031 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4331 API_PROXY_TARGET=http://127.0.0.1:8031 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4331 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr049-template-change-trail.mjs
 *
 * It needs a tenant where ONE version has been superseded and at least one
 * letter was sent on the older one. On a freshly seeded demo tenant nothing has
 * ever been dispatched, so the impact half would legitimately read "nothing
 * already sent carries the older wording" — a real state, and not the one worth
 * driving a browser for.
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1. THE VERSION HISTORY HAS A "Changed" CELL, and it is on the page a person
 *      actually reaches — not a component that exists and is rendered nowhere.
 *   2. THE CELL HOLDS A VALUE, NOT A PARAGRAPH. Measured: its text is short and
 *      its rendered HEIGHT is one or two lines, never the 645px cell the PO
 *      photographed.
 *   3. THE FIRST VERSION SAYS SO rather than drawing the same blank as an edit
 *      that moved nothing.
 *   4. CLICKING IT OPENS THE RECORD, and the record names BOTH halves: what
 *      moved, and how many already-sent documents stand on the old wording.
 *   5. NO STORAGE KEY IS EVER RENDERED (CR-049 step 5d decision 4).
 *   6. THE PAGE DOES NOT SCROLL SIDEWAYS with the record open.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4331";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const CODE = process.env.SMOKE_TEMPLATE ?? "disconnect_notice_48_hour";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr049-change-trail";
const VIEWPORT = { width: 1728, height: 1080 };

/** A CELL, not a paragraph. Two lines of the 14px body scale is ~44px; the cell
 *  the PO photographed was 645px. 96 is deliberately generous — this is the
 *  guard against a paragraph, not a pixel budget. */
const CELL_MAX_HEIGHT = 96;

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

  console.log(`cr049 task 8: ${BASE} tenant=${TENANT} viewport=${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // The version history is its own page (`?view=history`, ruled 2026-08-30).
  await page.goto(
    `${BASE}/${TENANT}/settings/reference-data/templates?template=${CODE}&view=history`,
    { waitUntil: "networkidle" },
  );
  await page.waitForTimeout(2000);
  await page.screenshot({ path: join(OUT, "history.png"), fullPage: true });

  // ── 1 · IS THE CELL THERE, ON THE PAGE A PERSON REACHES? ──────────────────
  const changed = await page.$('[data-testid="version-changed-2"]');
  check(
    changed !== null,
    'the version history draws a "Changed" cell for v2 — without it this task is a ' +
      "service nothing calls (hard-won law 2)",
  );
  if (changed === null) {
    await browser.close();
    console.log(`\n⛔ ${failures.length} failure(s)`);
    process.exit(1);
  }

  // ── 2 · A VALUE, NOT A PARAGRAPH ──────────────────────────────────────────
  const cell = await page.evaluate(`(() => {
    const el = document.querySelector('[data-testid="version-changed-2"]');
    const r = el.getBoundingClientRect();
    return {
      text: (el.innerText || "").trim(),
      title: el.getAttribute("title") || "",
      height: Math.round(r.height),
      tag: el.tagName,
    };
  })()`);
  console.log(`   cell: ${JSON.stringify(cell)}`);
  check(
    cell.height > 0 && cell.height <= CELL_MAX_HEIGHT,
    `the Changed cell is a VALUE and not a paragraph — ${cell.height}px (max ${CELL_MAX_HEIGHT})`,
  );
  check(
    cell.text.length > 0 && cell.text.length <= 40,
    `its text is short: ${cell.text.length} char(s) — "${cell.text}"`,
  );
  check(
    cell.title.length > 0 && !cell.text.includes(cell.title),
    "the sentence is on the TOOLTIP and not inline (the PO's rule of 2026-08-30)",
  );

  // ── 3 · THE FIRST VERSION SAYS SO ─────────────────────────────────────────
  const first = await page.evaluate(`(() => {
    const el = document.querySelector('[data-testid="version-changed-1"]');
    return el ? (el.innerText || "").trim() : null;
  })()`);
  check(
    first !== null && first.length > 0,
    `the FIRST version states its own state rather than drawing a blank — "${first}"`,
  );

  // ── 4 · CLICK IT: BOTH HALVES OF THE ANSWER ───────────────────────────────
  await page.click('[data-testid="version-changed-2"]');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "record.png"), fullPage: true });

  const record = await page.evaluate(`(() => {
    const el = document.querySelector('[data-testid="change-record"]');
    if (!el) return { missing: true };
    const impact = el.querySelector('[data-testid="change-impact"]');
    const kept = el.querySelector("[data-document-id]");
    return {
      text: (el.innerText || "").trim(),
      fields: [...el.querySelectorAll('[data-testid^="change-field-"]')].map(
        (n) => (n.innerText || "").trim(),
      ),
      impactRows: impact ? impact.children.length : 0,
      keptDocumentId: kept ? kept.getAttribute("data-document-id") : null,
      html: el.innerHTML,
    };
  })()`);
  check(!record.missing, "clicking the cell opens the change record");
  if (!record.missing) {
    console.log(`   fields: ${JSON.stringify(record.fields)}`);
    check(record.fields.length > 0, `WHAT MOVED is named: ${record.fields.join(" | ")}`);
    check(
      record.impactRows > 0,
      `WHO IS HOLDING THE OLD WORDING is named: ${record.impactRows} letter(s) listed`,
    );
    check(
      record.keptDocumentId !== null,
      `each listed letter reaches its KEPT COPY by id (${record.keptDocumentId})`,
    );

    // ── 5 · NO STORAGE KEY, EVER ────────────────────────────────────────────
    check(
      !/t\/[0-9a-f-]{8,}\/\d{4}\/\d{2}\//i.test(record.html),
      "no storage key is rendered anywhere in the record (step 5d decision 4)",
    );
  }

  // ── 6 · THE PAGE DOES NOT SCROLL SIDEWAYS ─────────────────────────────────
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `the page does not scroll sideways with the record open (${sideways}px)`);

  await browser.close();
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    process.exit(1);
  }
  console.log(`\n✓ all checks passed — screenshots in ${OUT}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
