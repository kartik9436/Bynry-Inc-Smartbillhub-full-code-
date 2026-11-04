/**
 * RENDERED-OUTPUT CHECK — CR-070 wave A, the Work shell and the order that
 * stands alone, in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"* — and, the same day, *"for Cr68, 69
 * and 70 - you will have to ensure you refer to screenshot we build and not
 * just r10"*. The reference is `04-docs/05-modules/16-work/wireframes/
 * Work-007.png` read through `08-screen-layouts.md` (template W1 at this wave:
 * the head and the table; W2's KPI strip, filters and bulk row are wave G's).
 *
 * ⚠ **AND B14 RULE 21 MAKES IT UNAVOIDABLE HERE.** A Tailwind utility is
 * emitted ONLY for a file listed in `07-frontend/src/styles/route-b-migrated.txt`,
 * and ONLY for a token the app's theme declares — `tailwind.css` zeroes the
 * default palette, so `bg-white` or `text-slate-500` compile to NOTHING while
 * `tsc`, eslint and `toContain("flex")` all pass. `WorkShell.tsx` and
 * `OrdersPage.tsx` were added to that list in the commit that created them and
 * use only declared tokens; step 6 below reads computed style in a real engine
 * to prove the strip actually painted.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   su postgres -c "psql -c 'create database sbh_cr070a owner smartbillhub'"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cr070a?sslmode=disable"
 *   (cd 06-backend && python manage.py migrate --no-input && python manage.py seed_demo \
 *      && python manage.py load_sample_data --tenant brazosbend)
 *   # ⚠ `load_sample_data` IS NOT OPTIONAL. `seed_demo` alone leaves the Orders
 *   # tab empty and four of these checks then fail as though the screen were
 *   # broken; the eighteen open orders are sample-data rows.
 *   (cd 06-backend && python manage.py runserver 127.0.0.1:8070 --noreload &)
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4270 API_PROXY_TARGET=http://127.0.0.1:8070 node server.mjs &)
 *   # demo steps 4 and 6 — the terminal proof (quoted in the PR). ⚠ THE SCRIPT
 *   # IS IN THE REPOSITORY, and this line named a scratch file that was in
 *   # nobody's until 2026-09-04 (`DEF-WRK-3633`). Skip it and the walkthrough
 *   # fails five checks that read exactly like a broken screen:
 *   (cd 06-backend && python manage.py shell \
 *      -c "$(cat ../10-scripts/render-checks/cr070-a-terminal.py)")
 *   SMOKE_BASE=http://127.0.0.1:4270 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr070-a-work-shell-and-anchor.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** `sbh_dev` is reseeded
 * by other lanes, and a mid-run reseed looks exactly like a broken screen.
 *
 * ── WHAT IT ASSERTS (demo script A, clicked) ──────────────────────────────
 *   1  **THE RAIL'S *Work* OPENS A SHELL, NOT THE NOT-BUILT-YET PAGE.** The
 *      catch-all's marker is absent; the shell's strip has exactly two tabs
 *      (Orders · Templates) — the two whose screen exists at this wave (law 2).
 *   2  **THE ORDERS TABLE LISTS THE SEEDED OPEN ORDERS ACROSS TWO BUILDS**
 *      (`CON-26-0117`, `CON-26-0122`) — read off the DOM, and compared with what
 *      the server served (`GET /work-orders`), never a number typed into React.
 *   3  **THE LEAK INVESTIGATION ON `77 Cedar Ct` IS IN THE LIST AND ITS
 *      CONNECTION CELL IS A DASH** (US-WRK-001 TC-1) — the row the terminal
 *      raised in step 4 with a premises and no connection.
 *   4  **THE HEAD MATCHES THE PACK**: kicker WORK · title *Work orders* · the one
 *      sentence, and the seven columns of template W1 in the drawing's order.
 *   5  **NO DATABASE ID AND NO INTERNAL REFERENCE REACHES A CLERK** (B14 rules
 *      31 and 32), and nothing on the page says "not built yet" or "still being
 *      decided" (the register entry that used to say so is gone).
 *   6  **THE UTILITIES COMPILED**, read as computed style in a real engine —
 *      the strip is a flex row with a bottom border; the active tab is bold.
 *   7  **NO SIDEWAYS SCROLL AT 1440.**
 *   8  **LONE STAR RIDGE SEES THE SHELL AND AN EMPTY LIST** — a second tenant,
 *      provisioned for the walkthrough, lists zero of Brazos Bend's orders
 *      (hard rule 1; demo step 7). Skipped with a note when no second tenant
 *      is provisioned (`SMOKE_TENANT2` unset).
 *   Screenshots land in `$SMOKE_OUT` (default /tmp/cr070-a-work-shell), beside
 *   which a reviewer opens `wireframes/Work-007.png`.

 * ⚠ **THE STRIP'S HANDLE CHANGED ON 2026-09-05 (`DEF-WRK-3955`).** Work drew its
 * own tab strip and tagged it `[data-work-tabs]` / `[data-work-tab="…"]`; that
 * strip is deleted and the strip is now the SHARED page header's, which carries
 * `[data-page-header-tabs]` and `[data-tab="…"]` on every module. The selectors
 * below moved with it. If a check here goes looking for `data-work-tab` again,
 * the module has grown a second strip and that is the defect, not the selector.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4270";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const TENANT2 = process.env.SMOKE_TENANT2 ?? "";
const EMAIL2 = process.env.SMOKE_EMAIL2 ?? "";
const PASSWORD2 = process.env.SMOKE_PASSWORD2 ?? PASSWORD;
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr070-a-work-shell";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** The pack's head — `08-screen-layouts.md` Work-007, template W1's regions. */
const HEAD = {
  kicker: "Work",
  title: "Work orders",
  sentence: "Everything open, across every connection and every account.",
  columns: ["Order", "Type", "Premise", "Service", "State", "Outcome", "Connection"],
};

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bUS-[A-Z]{3}-\d{3,5}\b/,
  /\bWork-0\d\d\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** Sentences the shell must NOT carry any more — the register entry that left. */
const ABSENCE_SENTENCES = ["still being decided", "not built yet", "Nothing is scheduled here yet"];

async function signIn(page, tenant, email, password) {
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

async function openOrders(page, tenant, served) {
  await page.goto(`${BASE}/${tenant}/work`, { waitUntil: "networkidle" });
  // Wait for the list's own answer rather than a timer: the row count is read
  // off the DOM only once the server's page has arrived.
  await page.waitForFunction(
    () =>
      document.querySelector('[data-work-orders=""] tbody tr') !== null ||
      document.body.innerText.includes("No open orders"),
    null,
    { timeout: 20000 },
  );
  return served;
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // The server's own answer, captured rather than inferred.
  let served = null;
  page.on("response", async (response) => {
    if (!/\/work-orders(?:\?|$)/.test(response.url())) return;
    try {
      served = JSON.parse(await response.text());
    } catch {
      // a redirect or a non-JSON body has nothing to read
    }
  });

  console.log(`cr070-a: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════════════════════════════════════════════════════════════════════════
  // 1 · sign in, then the rail's Work
  // ═════════════════════════════════════════════════════════════════════════
  await signIn(page, TENANT, EMAIL, PASSWORD);
  console.log("   signed in as Alex Reed's stand-in (the owner login)");

  console.log("\n── the rail's Work → the shell ──");
  await page.click(`a[href="/${TENANT}/work"]`);
  await page.waitForURL((u) => u.pathname === `/${TENANT}/work`, { timeout: 20000 });
  await openOrders(page, TENANT, served);
  await page.screenshot({ path: join(OUT, "work-shell-orders.png"), fullPage: true });

  const text = await page.evaluate(() => document.body.innerText);
  check(
    (await page.locator('[data-not-built-yet="true"]').count()) === 0,
    "the not-built-yet page is gone — /work is a screen",
  );
  const tabs = await page.locator("[data-page-header-tabs] [data-tab]").evaluateAll((nodes) =>
    nodes.map((n) => n.getAttribute("data-tab")),
  );
  check(
    tabs.join(",") === "orders,templates",
    `the strip has exactly the two tabs whose screen exists (${tabs.join(", ")})`,
  );
  for (const sentence of ABSENCE_SENTENCES) {
    check(!text.includes(sentence), `no stale absence: "${sentence}"`);
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 2 · the Orders table: the seeded builds, read off the DOM vs the server
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── Orders ──");
  const rows = await page.locator('[data-work-orders=""] tbody tr').count();
  check(rows > 0, `the table drew ${rows} row(s)`);
  if (served !== null) {
    const shown = Math.min(served.count, 50);
    check(rows === shown, `the screen drew what the server served (${rows} = ${shown} of ${served.count})`);
  } else {
    check(false, "GET /work-orders was never observed — the table may be drawing from React");
  }
  const connections = new Set(
    (text.match(/CON-\d{2}-\d{4}/g) ?? []).map((s) => s),
  );
  // ⚠ The demo script names CON-26-0117 and CON-26-0122. MEASURED on the seeded
  // fixture (2026-09-03): Brazos Bend sells electric and water, so CON-26-0117's
  // gas and sewer orders are never planted and its four seeded orders are ALL
  // accepted — it has no OPEN order and must NOT be in this list. CON-26-0122
  // (four planned) is the build the script's second name still holds for, and
  // the list spans five builds. Asserted as measured, not as drawn.
  check(connections.has("CON-26-0122"), "an order on CON-26-0122 is listed");
  check(!connections.has("CON-26-0117"), "CON-26-0117 is NOT listed — its four seeded orders are all accepted (closed)");
  check(connections.size >= 2, `open orders span ${connections.size} connection(s)`);

  // 3 · the leak investigation with no build
  const cedar = page.locator('[data-work-orders=""] tbody tr', { hasText: "77 Cedar Ct" });
  const cedarCount = await cedar.count();
  check(cedarCount >= 1, `the Leak investigation on 77 Cedar Ct is in the list (${cedarCount})`);
  if (cedarCount >= 1) {
    const cells = await cedar.first().locator("td").allInnerTexts();
    const last = cells[cells.length - 1]?.trim() ?? "";
    check(last === "—", `its CONNECTION cell is a dash (read "${last}")`);
    check(cells.some((c) => c.includes("Leak investigation")), "its TYPE reads Leak investigation");
    check(!cells.some((c) => /CON-\d{2}-\d{4}/.test(c)), "it names no connection");
    if (served !== null) {
      const row = served.results.find((r) => r.premise && r.premise.address === "77 Cedar Ct");
      check(row !== undefined && row.connection === null, "the server serves it with connection: null");
    }
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 4 · the head against the pack (Work-007, template W1 at this wave)
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── the head and the columns, against wireframes/Work-007.png ──");
  const kicker = ((await page.locator('[data-work-orders=""] [data-kicker]').first().innerText()) ?? "").trim();
  check(kicker.toLowerCase() === HEAD.kicker.toLowerCase(), `kicker reads "${kicker}" (pack: WORK)`);
  const title = ((await page.locator('[data-work-orders=""] h1').first().innerText()) ?? "").trim();
  check(title === HEAD.title, `title reads "${title}"`);
  check(text.includes(HEAD.sentence), "the one sentence under the title is the pack's");
  // The shared table sets its headers in caps through CSS (B14 rule 20's 12px
  // header tier), so `innerText` comes back transformed — compared without case,
  // because the pack draws them in caps too (ORDER · TYPE · PREMISE …).
  const headers = await page.locator('[data-work-orders=""] thead th').allInnerTexts();
  const cleaned = headers.map((h) => h.replace(/[⇅↑↓]/g, "").trim()).filter((h) => h !== "");
  check(
    HEAD.columns.every((c, i) => (cleaned[i] ?? "").toLowerCase() === c.toLowerCase()),
    `columns are ${cleaned.join(" · ")} (pack order: ${HEAD.columns.join(" · ")})`,
  );
  // W2's pieces are wave G's — their ABSENCE is asserted so a lane cannot half-draw them.
  check(!/\bUNASSIGNED\b|\bDUE TODAY\b|\bIN THE FIELD\b/.test(text), "no KPI strip yet (wave G)");
  check(!cleaned.includes("Priority") && !cleaned.includes("Technician"), "no PRIORITY/TECHNICIAN column yet (wave G)");

  // 5 · nothing internal reaches the clerk
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = text.match(pattern);
    check(hit === null, `no ${pattern} in clerk copy${hit ? ` — found ${hit[0]}` : ""}`);
  }

  // 6 · the utilities actually compiled (rule 21 / DEF-974), read in a real engine
  const strip = await page.locator("[data-page-header-tabs]").first().evaluate((el) => {
    const s = getComputedStyle(el);
    return { display: s.display, borderBottomWidth: s.borderBottomWidth, borderBottomStyle: s.borderBottomStyle };
  });
  check(strip.display === "flex", `the strip is a flex row (display ${strip.display})`);
  check(
    strip.borderBottomStyle === "solid" && strip.borderBottomWidth !== "0px",
    `the strip has its bottom border (${strip.borderBottomWidth} ${strip.borderBottomStyle})`,
  );
  const active = await page.locator('[data-tab="orders"]').evaluate((el) => {
    const s = getComputedStyle(el);
    return { fontWeight: s.fontWeight, paddingLeft: s.paddingLeft };
  });
  check(Number(active.fontWeight) >= 600, `the active tab is bold (font-weight ${active.fontWeight})`);
  check(active.paddingLeft !== "0px", `the tab has real padding (${active.paddingLeft})`);

  // 7 · no sideways scroll
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `no sideways scroll at ${VIEWPORT.width} (overflow ${sideways}px)`);

  // the Templates tab still renders its blank page under the strip
  await page.click('[data-tab="templates"]');
  await page.waitForURL((u) => u.pathname.endsWith("/work/templates"), { timeout: 20000 });
  await page.waitForSelector('[data-work-order-templates=""]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "work-shell-templates.png"), fullPage: true });
  const templatesText = await page.evaluate(() => document.body.innerText);
  check(!templatesText.includes("still being decided"), "the templates page no longer says the module is undecided");
  check(
    templatesText.includes("Field work is being built as its own part of SMARTBillHub"),
    "the templates page says the module is being built",
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 8 · the isolation tenant — the shell, and an empty list (demo step 7)
  // ═════════════════════════════════════════════════════════════════════════
  if (TENANT2 !== "" && EMAIL2 !== "") {
    console.log(`\n── ${TENANT2}: the shell, and an empty list ──`);
    const page2 = await (await browser.newContext({ viewport: VIEWPORT })).newPage();
    let served2 = null;
    page2.on("response", async (response) => {
      if (!/\/work-orders(?:\?|$)/.test(response.url())) return;
      try {
        served2 = JSON.parse(await response.text());
      } catch {
        // nothing to read
      }
    });
    await signIn(page2, TENANT2, EMAIL2, PASSWORD2);
    await openOrders(page2, TENANT2, served2);
    await page2.screenshot({ path: join(OUT, "work-shell-second-tenant.png"), fullPage: true });
    const text2 = await page2.evaluate(() => document.body.innerText);
    check((await page2.locator("[data-page-header-tabs] [data-tab]").count()) === 2, "the second tenant sees the shell");
    check(!text2.includes("77 Cedar Ct") && !text2.includes("CON-26-0117"), "and none of Brazos Bend's orders");
    check(served2 !== null && served2.count === 0, `the server served ${served2 === null ? "nothing" : served2.count} order(s) — an empty list`);
    check(text2.includes("No open orders"), "the empty state says what is missing");
  } else {
    console.log("\n   · second tenant not provisioned for this run (SMOKE_TENANT2 unset) — isolation proved by tests/test_us_wrk_004_orders_list.py and the RLS probe on PostgreSQL");
  }

  await browser.close();

  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ cr070 wave A: the module exists, and an order can stand alone");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
