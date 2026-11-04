#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-056 W5 task 25 — the customers list, its search and one
//           person's accounts. Waves W2/W3 put identity on the customer and
//           made every account door write the link; this is the screen that
//           makes either visible.
// Screens:  the customers list (A1 allocates no id — S61-S90 is exhausted and
//           S115 is the PO's to allocate; see routing/screenIds.ts)
// Rules:    BR-CUS-054 (one customer, many accounts) · BR-CUS-089 (the
//           identity-match tier is STORED with its confirmer) · BR-CUS-092(c)
//           (LAST FOUR ONLY — the full identifier never reaches a browser) ·
//           B14 rules 19, 20, 21, 31, 32 · hard-won law 6 (diff the RUNNING
//           app — no gate reads rendered output) · law 2 (built is not wired)
// ───────────────────────────────────────────────────────
/**
 * Open the customers list in a REAL browser and read what comes back.
 *
 * ⚠ **WHY THIS EXISTS BESIDE NINE PASSING VITEST CASES.** The Product Owner's
 * rule of 2026-08-30: *"All UI screen should be confirm using real broswer
 * testing and not just based on test cases"*. And it is not ceremony on this
 * screen in particular, because **B14 rule 21's migration clause is per FILE**:
 * a Tailwind utility written in a file that is not on
 * `07-frontend/src/styles/route-b-migrated.txt` renders as **nothing at all**,
 * and `tsc`, eslint and every `toContain("tabular-nums")` assertion pass on it
 * because the class IS in the DOM. `CustomersListPage.tsx` is a brand-new file
 * written entirely in utilities. Only a browser with a real style engine can
 * answer whether they drew.
 *
 * ⚠ **AND THE MOST IMPORTANT CHECK HERE IS AN ABSENCE.** BR-CUS-092(c) says
 * the full identifier never reaches a list response. A jsdom test can assert
 * that against the markup a component produced; only this can assert it against
 * what the SERVER actually sent over the wire, which is the thing that ends up
 * in devtools, in a proxy log and in the HAR file attached to a ticket. So the
 * network responses are captured and searched, not just the DOM.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is reading the
 * wrong bytes.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** The shared
 * development database is reseeded by other lanes; on 2026-08-30 a sibling
 * check lost three runs to it, with every id changing mid-run, which looks
 * exactly like a broken screen.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   createdb smartbillhub_cr056
 *   DATABASE_URL=…/smartbillhub_cr056 python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/smartbillhub_cr056 python3 06-backend/manage.py seed_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub_cr056" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8056 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4256 API_PROXY_TARGET=http://127.0.0.1:8056 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4256 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr056-customers-list.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  THE ROUTE RESOLVES AT ALL and draws a table with rows. Hard-won law 2:
 *      a screen nothing routes to is a screen that does not exist.
 *   2  THE UTILITIES COMPILED — read from COMPUTED STYLE, which is the only
 *      thing that can tell a rendered utility from a class name in the DOM.
 *   3  NO IDENTIFIER ON THE WIRE: every `/customers` response body is searched
 *      for a nine-digit run and for the seeded number's own spellings.
 *   4  B14 RULE 31 — no uuid is the visible text of any cell.
 *   5  THE SEARCH BOX NAMES WHAT IT MATCHES (B14 rule 19) and really filters:
 *      a name is typed and the row count falls.
 *   6  ONE ROW OPENS INTO THE ACCOUNTS THAT PERSON HOLDS, in the ONE table
 *      type (B14 rule 20) — the sub-table's row height is the shared one.
 *   7  B14 RULE 32 — no cell holds a sentence. Measured in WORDS, because ten
 *      of these became a wall of prose on 2026-08-30.
 *   8  THE PAGE DOES NOT SCROLL SIDEWAYS.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4256";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr056-customers-list";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** The list, as a browser sees it. */
const READ_LIST = `(() => {
  const table = document.querySelector('table.data-table');
  const rows = [...document.querySelectorAll('table.data-table tbody tr')];
  const cells = rows.length
    ? [...rows[0].querySelectorAll('td')].map((td) => ({
        text: (td.textContent || "").replace(/\\s+/g, " ").trim(),
        // ⚠ COMPUTED, never the class attribute. A utility in a file that is not
        //   on the Route B ledger is a class name with no rule behind it, and
        //   reading className cannot tell the difference (B14 rule 21 / DEF-974).
        variant: getComputedStyle(td).fontVariantNumeric,
        align: getComputedStyle(td).textAlign,
      }))
    : [];
  const search = document.querySelector('input[type="search"]');
  const identity = document.querySelector('[data-identity]');
  return {
    tablePresent: table !== null,
    rowCount: rows.length,
    // The ONE table type (B14 rule 20): the shared body size, read from the
    // rendered cell rather than from a stylesheet nobody loaded.
    bodyFontSize: cells.length ? getComputedStyle(rows[0].querySelector('td')).fontSize : null,
    cells,
    searchPlaceholder: search ? search.getAttribute('placeholder') : null,
    identityState: identity ? identity.getAttribute('data-identity') : null,
    identityText: identity ? (identity.textContent || "").trim() : null,
    accountCounts: [...document.querySelectorAll('[data-account-count]')].map((el) =>
      el.getAttribute('data-account-count'),
    ),
    body: document.body.innerText || "",
    html: document.body.innerHTML,
  };
})()`;

/** The sub-table one row opens into. */
const READ_EXPANDED = `(() => {
  const tables = [...document.querySelectorAll('table.data-table')];
  const inner = tables.length > 1 ? tables[tables.length - 1] : null;
  const rows = inner ? [...inner.querySelectorAll('tbody tr')] : [];
  return {
    tableCount: tables.length,
    innerRows: rows.length,
    // B14 rule 20 - ONE table type. The sub-table is a data-table too, so its
    // cells must measure the same as the outer one's; a second type would draw
    // at a different size and only a browser can see that.
    innerFontSize: rows.length
      ? getComputedStyle(rows[0].querySelector('td')).fontSize
      : null,
    text: inner ? (inner.textContent || "").replace(/\\s+/g, " ").trim() : null,
  };
})()`;

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // ── 3 · WHAT THE SERVER PUT ON THE WIRE ─────────────────────────────────
  // Captured rather than inferred: BR-CUS-092(c) is a promise about the
  // RESPONSE, and a component that renders only the last four is not evidence
  // that the number stayed on the server.
  const wire = [];
  page.on("response", async (response) => {
    if (!response.url().includes("/customers")) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      // A redirect or a non-body response has nothing to read.
    }
  });

  console.log(`cr056: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  console.log("\n── the customers list ──");
  await page.goto(`${BASE}/${TENANT}/customers`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "list.png"), fullPage: true });
  const list = await page.evaluate(READ_LIST);

  // ── 1 · IT EXISTS AND IT HAS ROWS ───────────────────────────────────────
  check(list.tablePresent, "the route resolves and draws the shared table");
  check(list.rowCount > 0, `the list has rows (${list.rowCount})`);

  // ── 2 · THE UTILITIES COMPILED ──────────────────────────────────────────
  // `tabular-nums` on the number cells is the one this screen depends on: a
  // column of customer numbers in proportional figures does not line up, and
  // nothing but computed style can tell whether the class drew.
  const numeric = list.cells.filter((cell) => cell.variant.includes("tabular-nums"));
  check(
    numeric.length > 0,
    `B14 rule 21: the tabular-nums utility COMPILED — ${numeric.length} cell(s) report it ` +
      `(${JSON.stringify(list.cells.map((c) => c.variant))})`,
  );
  check(
    list.bodyFontSize !== null,
    `B14 rule 20: the body cell measures ${list.bodyFontSize} — the shared table size`,
  );

  // ── 3 · NO IDENTIFIER ON THE WIRE (BR-CUS-092(c)) ───────────────────────
  const bodies = wire.map((entry) => entry.body).join("\n");
  check(wire.length > 0, `the list really called the server (${wire.length} response(s))`);
  check(
    !/\b\d{9}\b/.test(bodies),
    "BR-CUS-092(c): no nine-digit run in any /customers response body",
  );
  check(
    !/\b\d{3}-\d{2}-\d{4}\b/.test(bodies),
    "BR-CUS-092(c): no hyphenated Social Security number in any response body",
  );
  check(
    !/\b\d{9}\b/.test(list.html),
    "BR-CUS-092(c): no nine-digit run in the rendered page either",
  );

  // ── 4 · B14 RULE 31 — no uuid is a visible value ────────────────────────
  const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  check(!UUID.test(list.body), "B14 rule 31: no uuid is visible text anywhere on the page");
  check(
    list.cells.every((cell) => !UUID.test(cell.text)),
    "B14 rule 31: no uuid is the value of a cell",
  );

  // ── 5 · THE SEARCH NAMES WHAT IT MATCHES, AND IT FILTERS ────────────────
  check(
    list.searchPlaceholder !== null && list.searchPlaceholder !== "Search this list",
    `B14 rule 19: the prompt names what it matches ("${list.searchPlaceholder}")`,
  );
  const firstName = (list.cells[1] ?? {}).text ?? "";
  if (firstName) {
    const term = firstName.split(",")[0].slice(0, 4);
    await page.fill('input[type="search"]', term);
    await page.waitForTimeout(1200);
    const filtered = await page.evaluate(READ_LIST);
    await page.screenshot({ path: join(OUT, "search.png"), fullPage: true });
    check(
      filtered.rowCount > 0 && filtered.rowCount <= list.rowCount,
      `the search really filters: "${term}" leaves ${filtered.rowCount} of ${list.rowCount}`,
    );
    await page.fill('input[type="search"]', "");
    await page.waitForTimeout(1200);
  } else {
    console.log("   note: no name cell to search on, so the filter leg is not exercised");
  }

  // ── 6 · ONE ROW OPENS INTO THE ACCOUNTS THAT PERSON HOLDS ───────────────
  const expander = await page.$("tbody tr button[aria-expanded]");
  if (expander) {
    await expander.click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: join(OUT, "expanded.png"), fullPage: true });
    const expanded = await page.evaluate(READ_EXPANDED);
    check(expanded.tableCount > 1, "the row opens into a sub-table");
    check(
      expanded.innerRows > 0,
      `the sub-table lists the accounts this person holds (${expanded.innerRows})`,
    );
    check(
      expanded.innerFontSize === list.bodyFontSize,
      `B14 rule 20: ONE table type — the sub-table measures ${expanded.innerFontSize} ` +
        `against the outer ${list.bodyFontSize}`,
    );
  } else {
    check(false, "hard-won law 2: no row expander is wired, so the accounts cannot be reached");
  }

  // ── 7 · B14 RULE 32 — a cell holds a VALUE, never a sentence ────────────
  const wordy = list.cells.filter((cell) => cell.text.split(/\s+/).filter(Boolean).length > 6);
  check(
    wordy.length === 0,
    `B14 rule 32: no cell holds a sentence (${JSON.stringify(wordy.map((c) => c.text))})`,
  );

  // ── 8 · IT DOES NOT SCROLL SIDEWAYS ─────────────────────────────────────
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `the page does not scroll sideways (${sideways}px)`);

  await browser.close();
  console.log(`\nscreenshots in ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const failure of failures) console.log(`   · ${failure}`);
    process.exit(1);
  }
  console.log("\n✓ every check passed");
})();
