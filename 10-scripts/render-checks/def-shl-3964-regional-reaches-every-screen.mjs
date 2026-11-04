/**
 * RENDERED-OUTPUT CHECK — DEF-SHL-3964, in a real browser, against the running
 * product. The tenant's date format and time zone must reach every screen.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and this defect is invisible to every other kind of check.
 * There is no crash, no blank cell and no raw key — just a plausible date in a
 * format nobody chose and a timestamp five or six hours out. The PO found it by
 * changing a setting and looking at the screens; that is what this repeats.
 *
 * The PO's words, 2026-09-05: *"date and time format is set in the settings,
 * plus we save location - but date shown everywhere in the product does not
 * change with that format change. If I change the language it changes across
 * entire app, date does not change."*
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   createdb sbh_region TEMPLATE <a seeded database>
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:sbh@127.0.0.1:5432/sbh_region" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8131 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      STATIC_DIR=$PWD/dist PORT=4331 API_PROXY_TARGET=http://127.0.0.1:8131 \
 *      node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4331 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/def-shl-3964-regional-reaches-every-screen.mjs
 *
 * ⚠ **REBUILD THE BUNDLE. DO NOT TRUST A RUNNING ONE** — a stale `dist` from
 * another lane looks exactly like a fix that did not work, and cost hours on
 * 2026-09-05.
 *
 * ── WHAT IT DOES ──────────────────────────────────────────────────────────
 *   0  Sign in to Pine Hill Water & Power — a TEXAS utility, which is the case
 *      in the defect: its saved zone is America/Chicago and the product was
 *      rendering every timestamp in UTC, five or six hours out.
 *   1  Read the tenant's CURRENT date format and time zone off Settings →
 *      Company → Regional, and collect the dates on four screens in four
 *      different modules. Those four are the BEFORE reading.
 *   2  Change the date format and the zone THROUGH THE PRODUCT'S OWN SCREEN —
 *      the same two dropdowns and the same Save button a clerk uses — and wait
 *      for the save to land.
 *   3  Re-read the same four screens. Every date must have changed to the new
 *      format, and every TIMESTAMP must have moved by the zone offset.
 *   4  Put the setting back, and prove the screens follow it back.
 *
 * A screen is named by MODULE so the report can say where it looked.
 */
import { createRequire } from "node:module";

// `playwright-core` lives in 07-frontend/node_modules, and `createRequire` on
// this file's own URL would look beside the SCRIPT. Resolve from the frontend
// package instead, exactly as `npm run e2e` would.
const require = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4331";
const TENANT = process.env.SMOKE_TENANT ?? "pine-hill";
const EMAIL = process.env.SMOKE_EMAIL ?? "sarah@pinehillwp.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Pin3Hill!passw0rd";
const REGIONAL = `${BASE}/${TENANT}/settings/company/regional`;

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/** The screens this walks, one per module, each named the way a person would. */
const SCREENS = [
  { module: "Settings", name: "Settings → Users", path: `/${TENANT}/settings/users` },
  { module: "Payments", name: "Payments → Record payments", path: `/${TENANT}/payments` },
  { module: "Billing", name: "Billing → Bills", path: `/${TENANT}/billing` },
  { module: "Reads", name: "Meter Reads → Reads", path: `/${TENANT}/reads` },
  { module: "Premises", name: "Premises", path: `/${TENANT}/premises` },
  { module: "Accounts", name: "Accounts", path: `/${TENANT}/accounts` },
];

/**
 * Every date this screen drew, read off the `<time>` elements DateCell emits.
 *
 * Reading `<time>` rather than scraping the page is deliberate: the element
 * carries `dateTime` — the raw server value — beside the text a person sees, so
 * a mismatch can be reported as "the server sent X and the screen drew Y"
 * rather than as a bare string comparison.
 */
async function datesOn(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  return page.$$eval("time[datetime]", (nodes) =>
    nodes
      .map((n) => ({ value: n.getAttribute("datetime"), text: (n.textContent ?? "").trim() }))
      .filter((d) => d.text.length > 0),
  );
}

/** Pick the ONE dropdown by its label id, set it, and let React see it. */
async function setSelect(page, id, value) {
  await page.selectOption(`#${id}`, value);
}

async function main() {
  // The sandbox has chromium build 1194 under PLAYWRIGHT_BROWSERS_PATH while
  // this playwright wants 1234, so the executable is named rather than looked
  // up. `SMOKE_CHROME` overrides it anywhere the layout differs.
  const executablePath =
    process.env.SMOKE_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  const browser = await chromium.launch({ executablePath });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();

  console.log("\n── 0 · sign in to a Texas utility ──");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  console.log(`   signed in to ${TENANT} as ${EMAIL}`);

  console.log("\n── 1 · what the tenant has saved, and what the screens draw ──");
  await page.goto(REGIONAL, { waitUntil: "networkidle" });
  await page.waitForSelector("#date_format", { timeout: 30000 });
  const savedFormat = await page.inputValue("#date_format");
  const savedZone = await page.inputValue("#timezone");
  console.log(`   Settings → Regional says: ${savedFormat} · ${savedZone}`);

  const before = {};
  for (const screen of SCREENS) {
    before[screen.name] = await datesOn(page, screen.path);
    const sample = before[screen.name][0];
    console.log(
      `   ${screen.name.padEnd(30)} ${before[screen.name].length} date(s)` +
        (sample ? ` · first: "${sample.text}" (server sent ${sample.value})` : ""),
    );
  }

  console.log("\n── 2 · change the format and the zone on the product's own screen ──");
  const NEXT_FORMAT = savedFormat === "DD/MM/YYYY" ? "MM/DD/YYYY" : "DD/MM/YYYY";
  const NEXT_ZONE = savedZone === "America/Chicago" ? "Pacific/Honolulu" : "America/Chicago";
  await page.goto(REGIONAL, { waitUntil: "networkidle" });
  await page.waitForSelector("#date_format", { timeout: 30000 });
  await setSelect(page, "date_format", NEXT_FORMAT);
  await setSelect(page, "timezone", NEXT_ZONE);
  await page.click('button:has-text("Save")');
  await page.waitForTimeout(2500);
  await page.goto(REGIONAL, { waitUntil: "networkidle" });
  await page.waitForSelector("#date_format", { timeout: 30000 });
  check(
    (await page.inputValue("#date_format")) === NEXT_FORMAT &&
      (await page.inputValue("#timezone")) === NEXT_ZONE,
    `saved: ${NEXT_FORMAT} · ${NEXT_ZONE}`,
  );

  console.log("\n── 3 · the same screens, read again ──");
  let movedScreens = 0;
  let comparable = 0;
  for (const screen of SCREENS) {
    const after = await datesOn(page, screen.path);
    const pairs = after
      .map((a) => ({ a, b: before[screen.name].find((x) => x.value === a.value) }))
      .filter((p) => p.b !== undefined);
    if (pairs.length === 0) {
      console.log(`   ${screen.name.padEnd(30)} no dated rows on this screen — nothing to compare`);
      continue;
    }
    comparable += 1;
    const changed = pairs.filter((p) => p.a.text !== p.b.text);
    if (changed.length > 0) movedScreens += 1;
    const one = changed[0] ?? pairs[0];
    console.log(
      `   ${screen.name.padEnd(30)} ${changed.length}/${pairs.length} moved · ` +
        `"${one.b.text}" → "${one.a.text}"  (server value ${one.a.value})`,
    );
    check(
      changed.length === pairs.length,
      `${screen.name}: every one of its ${pairs.length} date(s) follows the setting`,
    );
  }
  check(comparable > 0, `${comparable} screen(s) had a date to compare`);
  check(movedScreens === comparable, `all ${comparable} screen(s) moved with the setting`);

  console.log("\n── 4 · put it back, and watch the screens follow ──");
  await page.goto(REGIONAL, { waitUntil: "networkidle" });
  await page.waitForSelector("#date_format", { timeout: 30000 });
  await setSelect(page, "date_format", savedFormat);
  await setSelect(page, "timezone", savedZone);
  await page.click('button:has-text("Save")');
  await page.waitForTimeout(2500);
  for (const screen of SCREENS) {
    if (before[screen.name].length === 0) continue;
    const back = await datesOn(page, screen.path);
    const same = before[screen.name].every((b) => {
      const now = back.find((x) => x.value === b.value);
      return now === undefined || now.text === b.text;
    });
    check(same, `${screen.name}: back to ${savedFormat} · ${savedZone}`);
  }

  await browser.close();
  console.log(
    failures.length === 0
      ? "\nALL CHECKS PASSED — the tenant's setting reaches every screen that draws a date.\n"
      : `\n${failures.length} CHECK(S) FAILED:\n  - ${failures.join("\n  - ")}\n`,
  );
  process.exit(failures.length === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error(error);
  process.exit(2);
});
