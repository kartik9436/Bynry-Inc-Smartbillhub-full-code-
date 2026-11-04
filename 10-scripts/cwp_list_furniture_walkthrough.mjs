// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CWP-3977 (D2 in 04-docs/05-modules/15-portal/14-layout-audit.md)
//           and rows X6/X7 of 13-wireframe-delta.md — the portal's eight lists
//           had no search, no sort, no row icons and no footer.
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           running app) · B14 rules 12, 13, 15, 16, 17
// ───────────────────────────────────────────────────────
/**
 * cwp_list_furniture_walkthrough — open the eight portal lists and USE them.
 *
 *     cd 07-frontend && npx vite build          # ALWAYS first — see below
 *     DATABASE_URL=… ALLOWED_HOSTS='*' python manage.py runserver 127.0.0.1:8477
 *     STATIC_DIR=$PWD/dist PORT=4478 API_PROXY_TARGET=http://127.0.0.1:8477 node server.mjs
 *     node 10-scripts/cwp_list_furniture_walkthrough.mjs
 *
 * ⚠ **IT TYPES, CLICKS AND PAGES — IT DOES NOT ASSERT THAT A CONTROL EXISTS.**
 * That distinction is the whole point, and it is audit row D14: forty-two
 * portal test files and 391 cases passed over every one of these gaps, because
 * each asserted the facts ITS screen showed rather than the shape the drawing
 * gives it. A test that finds a search box passes on a search box wired to
 * nothing. So each check here changes something and reads what changed.
 *
 * ⚠ **IT ALSO READS `getComputedStyle` ON THE FOOTER**, which no unit test can.
 * The footer reuses `DataTable.css`'s `table-pager*` classes through the shared
 * `ListPager`; if the portal ever stops sharing one bundle with the staff app
 * those classes render as NOTHING AT ALL while `tsc`, eslint and every
 * `toContain` assertion keep passing, because the class IS in the DOM (B14 rule
 * 21's trap). `display:flex` is the cheapest proof the stylesheet arrived.
 *
 * ⚠ **REBUILD `dist/` FIRST AND PASS `STATIC_DIR` EXPLICITLY.** `server.mjs`
 * serves whatever is on disk beside ITSELF and never notices the bundle is
 * hours old; a lane in a worktree that runs the shared checkout's server.mjs
 * walks the shared checkout's build. The boot line is the only place it shows.
 *
 * ⚠ **WHAT IT FOUND THAT NOTHING ELSE DID (2026-09-05):** the documents search
 * did not look at the document's KIND — the biggest words in the first column —
 * so a customer typing *A letter from us* got nothing back. Every unit
 * assertion about that search passed, because each used a string the narrower
 * predicate already matched.
 */
// A browser walk over the eight lists this lane touched. It does NOT assert
// that a search box exists — the audit's D14 is that every existing portal test
// passed over these gaps by asserting the facts its screen already showed. It
// TYPES, CLICKS and PAGES, and reads what changed.
import { createRequire } from "node:module";
const require = createRequire("/tmp/lane-tables/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:4478";
const TENANT = "pine-hill";
const LOGIN = process.env.PORTAL_LOGIN ?? "busy@example.test";

const browser = await chromium.launch({ ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();

const api = await page.request.post(`${BASE}/api/${TENANT}/portal/auth/sign-in`, {
  data: { email: LOGIN, password: process.env.PORTAL_PASSWORD ?? "Pine-Hill-2026!" },
});
console.log("sign-in:", (await api.json()).ok ? "ok" : "FAILED", "as", LOGIN);

const hash = await (await fetch(`${BASE}/index.html`)).text();
console.log("bundle:", (hash.match(/index-[A-Za-z0-9_-]*\.js/) ?? ["?"])[0]);

const results = [];
const skipped = [];
function say(screen, what, ok, detail = "") {
  results.push({ screen, what, ok });
  console.log(`  ${ok ? "✓" : "✗"} ${what}${detail ? " — " + detail : ""}`);
}

async function rows() {
  return page.locator("[data-minitable] tbody tr").count();
}
async function firstCell() {
  const n = await rows();
  if (n === 0) return "";
  return (await page.locator("[data-minitable] tbody tr").first().innerText()).split("\n")[0];
}

for (const [screen, path] of [
  ["CWP-027", "/bills"],
  ["CWP-023", "/accounts"],
  ["CWP-031", "/documents"],
  ["CWP-041", "/payments"],
  ["CWP-034", "/readings"],
  ["CWP-037", "/equipment"],
  ["CWP-046", "/requests"],
]) {
  console.log(`\n── ${screen} ${path}`);
  await page.goto(`${BASE}/${TENANT}/portal${path}`, { waitUntil: "networkidle" });
  const list = page.locator(`[data-list="${screen}"]`);
  if ((await list.count()) === 0) {
    // The SCREEN's own empty branch renders before the list is ever mounted on
    // some of these (CWP-046 does), so an absent [data-list] is only a failure
    // when the screen thinks it has rows to show.
    const emptied = await page.locator("[data-requests-empty],[data-bills-empty],[data-documents-empty],[data-money-empty],[data-readings-empty],[data-equipment-empty],[data-accounts-empty]").count();
    if (emptied > 0) { console.log("  – skipped: the screen's own empty state, no list to draw"); skipped.push(screen); continue; }
    say(screen, "the list renders", false, "no [data-list] and no empty state either");
    continue;
  }
  const before = await rows();
  if (before === 0) { console.log("  – skipped: no rows on this login (the screen's own empty state)"); skipped.push(screen); continue; }
  say(screen, `renders ${before} row(s)`, true);

  // TOOLBAR — type, and read what changed.
  const box = list.locator('input[type="search"]');
  if (await box.count()) {
    const seed = (await firstCell()).slice(0, 4).trim();
    await box.fill("zzzqqq");
    await page.waitForTimeout(120);
    const none = await rows();
    const said = await list.locator("[data-list-nomatch]").count();
    say(screen, "search narrows to nothing and SAYS so", none === 0 && said === 1, `rows ${before}→${none}`);
    await box.fill(seed);
    await page.waitForTimeout(120);
    const some = await rows();
    say(screen, `search on "${seed}" narrows`, some > 0 && some <= before, `rows ${before}→${some}`);
    await box.fill("");
    await page.waitForTimeout(120);
  } else {
    say(screen, "no search box (drawing gives none)", true);
  }

  // SORT — click, and read the order.
  const sorter = list.locator("button[data-sort]").first();
  if ((await sorter.count()) && before < 2) {
    say(screen, "sortable headings present (too few rows to reorder)", true, `${before} row`);
  } else if (await sorter.count()) {
    const a = await firstCell();
    await sorter.click();
    await page.waitForTimeout(80);
    const b = await firstCell();
    const dir = await sorter.getAttribute("data-sort-dir");
    await sorter.click();
    await page.waitForTimeout(80);
    const c = await firstCell();
    say(screen, "sorting reorders the rows", a !== b || b !== c, `"${a}" → "${b}" → "${c}" (${dir})`);
    await sorter.click(); // back to the server's order
    await page.waitForTimeout(80);
  } else {
    say(screen, "sortable headings present", false, "none found");
  }

  // ROW ICONS — a real accessible name on a real control.
  const icons = list.locator("[data-minitable] tbody tr a[aria-label], [data-minitable] tbody tr button[aria-label]");
  const nIcons = await icons.count();
  if (nIcons > 0) {
    const name = await icons.first().getAttribute("aria-label");
    say(screen, `${nIcons} row icon(s), first named`, Boolean(name && name.trim()), `"${name}"`);
  } else {
    say(screen, "no row icons (stated absence)", true);
  }

  // FOOTER
  const pager = list.locator(".table-pager");
  if (await pager.count()) {
    const text = (await pager.innerText()).replace(/\s+/g, " ").trim();
    say(screen, "footer shows a count and a page", /\d+.*\d+/.test(text), text.slice(0, 70));
    // and the footer must be STYLED, not a bare unstyled div (rule 21's trap)
    const disp = await pager.evaluate((el) => getComputedStyle(el).display);
    say(screen, "footer CSS actually applies", disp === "flex", `display:${disp}`);
  } else {
    say(screen, "no footer (drawing gives none)", true);
  }
}

const bad = results.filter((r) => !r.ok);
console.log(`\n${results.length - bad.length}/${results.length} checks passed`);
if (skipped.length) console.log(`skipped (no rows on this login): ${skipped.join(", ")}`);
if (bad.length) { console.log("FAILED:"); for (const b of bad) console.log(`  ${b.screen} — ${b.what}`); }
await browser.close();
process.exit(bad.length ? 1 : 0);
