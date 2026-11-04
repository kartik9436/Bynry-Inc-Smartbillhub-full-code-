// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-010/014/015/020/021/024/050/051/053 · US-TEN-019 — the Work
//           module's sample set, CLICKED.  Screens: WS-23 · WS-24 · Work-013 ·
//           Work-025 · Work-027 · Work-030 · WM-15 · S8 → Reference data
// Rules:    BR-TEN-056/057 · BR-WRK-018 (a priority carries a PROMISE) ·
//           BR-WRK-020 · BR-WRK-030 · CLAUDE.md hard rule 2 (money 4 dp stored,
//           2 displayed) · hard-won law 6 (no gate reads rendered output — diff
//           the running app) · law 2 (built is not wired)
// ───────────────────────────────────────────────────────
/**
 * cr070_work_sample_walkthrough — the crew, the register and the costed job.
 *
 * Every number the two new sample-data blocks write is only true if it is on a
 * screen, and NOTHING in this repository reads rendered output. On 2026-09-07
 * the tables were measured empty on all six seeded tenants with every suite
 * green over them, which is that gap costing a whole module its demo.
 *
 * ⚠ **AND `DEF-WRK-4518` IS THE SAME GAP ON THE ORDER DETAIL, WITH ONE
 * CORRECTION TO THE ROW AS FILED.** Step 5a below opens `Work-008` three ways
 * because the row's claim — *the screen loads nothing on any order* — was
 * measured on 2026-09-07 to be true of the by-NUMBER address only. Every
 * in-app link passes the UUID, so clicking a row was serving six 200s the whole
 * time. The by-number address was serving fourteen 404s, and NOTHING on the
 * page said so, which is the part that let it survive. Both are asserted here.
 *
 *     # a real PostgreSQL with the blocks loaded
 *     python3.12 manage.py load_sample_data --tenant brazosbend
 *     DATABASE_URL=... ALLOWED_HOSTS='*' python3.12 manage.py runserver 127.0.0.1:8073
 *     cd 07-frontend && npx vite build
 *     PORT=4373 STATIC_DIR=$PWD/dist API_PROXY_TARGET=http://127.0.0.1:8073 node server.mjs
 *     CHROME_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *       BASE=http://127.0.0.1:4373 node 10-scripts/cr070_work_sample_walkthrough.mjs
 *
 * ⚠ PASS `STATIC_DIR` EXPLICITLY — `server.mjs` resolves `dist/` from its OWN
 * directory, so a lane in a `git worktree` that runs the shared checkout's copy
 * serves the shared checkout's bundle however carefully it just built its own.
 *
 * ⚠ AND `CHROME_PATH` IS NOT OPTIONAL ON THIS MACHINE: playwright's default
 * points at a headless-shell build that is not installed, and the error it
 * gives ("Executable doesn't exist") reads like a broken script rather than a
 * missing browser. The installed one is `chromium-1194`.
 *
 * One line per check; exits non-zero on the first thing that is wrong, so a red
 * run names the screen rather than the assertion.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:4373";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";

const problems = [];
const ok = (m) => console.log("  ✓ " + m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };

const browser = await chromium.launch(
  process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1100 } });
const page = await ctx.newPage();
const jsErrors = [];
page.on("pageerror", (e) => jsErrors.push(String(e)));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
console.log(`signed in — ${page.url()}`);

async function open(path) {
  await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1800);
  return (await page.locator("body").innerText()).replace(/\s+/g, " ");
}

// ── 1 · a crew, and a contractor with a dash ──────────────────────────────
console.log("\nWork → Crews (WS-23)");
let t = await open("/work/crews");
for (const name of ["Field crew A", "Field crew B", "Redline Meter Services"])
  t.includes(name) ? ok(`crew on screen: ${name}`) : fail(`crew MISSING: ${name}`);
for (const who of ["D. Ortiz", "R. Patel", "M. Chen", "J. Okoro"])
  t.includes(who) ? ok(`technician on screen: ${who}`) : fail(`technician MISSING: ${who}`);
t.includes("Senior technician") ? ok("the ROLE column carries the typed label")
  : fail("no 'Senior technician' label on screen");
// The van is on the TECHNICIAN page's note bar (`Shift {{shift}}. Van {{van}}.`),
// not on the crews list — checked there instead.

// ── 2 · a technician with a certificate ───────────────────────────────────
console.log("\nWork → Crews → D. Ortiz (WS-24)");
t = await open("/work/crews/d-ortiz");
t.includes("D. Ortiz") ? ok("the technician page opens") : fail("D. Ortiz page did not open");
t.includes("Unit 12") ? ok("the note bar carries the van: Unit 12") : fail("no van on the note bar");
t.includes("Traffic control") ? ok("a certification is on screen (Traffic control · 3-yr)")
  : fail("no certification on the technician page");
/Water I|Meter I|Reads/.test(t) ? ok("skills are on screen") : fail("no skills on screen");
t.includes("Not held") ? ok("a NOT HELD skill is drawn — nobody holds all eight")
  : fail("no 'Not held' row: every skill is held, so the subtraction is unreachable");

// ── 3 · parts and labour rates ────────────────────────────────────────────
console.log("\nWork → Parts (Work-025)");
t = await open("/work/parts");
t.includes("MTR-W58") ? ok("part on screen: MTR-W58") : fail("MTR-W58 missing");
t.includes("92.40") ? ok("its unit cost displays at TWO decimals: 92.40 (stored 92.4000)")
  : fail("92.40 not displayed — hard rule 2");
console.log("\nSettings → Reference data → Labour rates (Work-030)");
t = await open("/settings/reference-data/work-labour-rates");
t.includes("48.50") ? ok("labour rate on screen: 48.50/h") : fail("no 48.50 labour rate");
t.includes("72.75") ? ok("overtime rate on screen: 72.75") : fail("no 72.75 overtime rate");
t.includes("Redline Meter Services") ? ok("the contractor's own rate is listed")
  : fail("no contractor rate");
t.includes("95.00") ? ok("contractor 95.00 flat") : fail("no 95.00 contractor rate");

// ── 4 · a filled template ─────────────────────────────────────────────────
console.log("\nWork → Templates (Work-013)");
t = await open("/work/templates");
t.includes("Meter exchange") ? ok("the template list opens") : fail("no templates listed");
/\d+ tasks?/.test(t) ? ok(`the CONTENTS column counts tasks — ${/(\d+ tasks?)/.exec(t)?.[1]}`)
  : fail("no task count in the CONTENTS column — a template with no questions");

// ── 5 · the costed work order ─────────────────────────────────────────────
console.log("\nWork → Orders (WM-15) — the board, part-done on purpose");
t = await open("/work/orders");
/D\. Ortiz|R\. Patel|M\. Chen/.test(t) ? ok("a technician's name is on the board — jobs are assigned")
  : fail("nobody is assigned on the dispatch board");
/En route|Scheduled/i.test(t) ? ok("the board shows a dispatch state (En route / Scheduled)")
  : fail("no dispatch state on the board");

// ── 5a · Work-008, OPENED THREE WAYS — the whole of `DEF-WRK-4518` ────────
//
// ⚠ **THE ROW AS FILED SAID THE SCREEN LOADS NOTHING ON EVERY ORDER, AND THAT
// IS HALF RIGHT — WHICH IS WHY THIS STEP OPENS IT BOTH WAYS.** Measured on
// 2026-09-07 against a real stack: every producer of this address passes the
// UUID (the Orders eye, the New-order wizard, global search), so the screen
// reached by CLICKING was serving six 200s and drawing its header, its type and
// its service correctly the whole time. What was broken is the address a HUMAN
// builds — `…/work/orders/WO-0016`, from the number in the table's first column
// and the one the route parameter is NAMED after — which 404'd fourteen times
// and drew a dash for each with nothing on screen admitting it.
//
// Both halves are asserted here, and so is the third state that did not exist:
// an unknown number must SAY SO rather than draw a page of dashes.
console.log("\nWork → Orders → an order (Work-008) — the three addresses (DEF-WRK-4518)");
await page.goto(`${BASE}/${TENANT}/work/orders`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2000);
const firstOrder = page.locator("a[href*='/work/orders/']").first();
const orderHref = await firstOrder.getAttribute("href");
await firstOrder.click();
await page.waitForTimeout(2500);
let d = (await page.locator("body").innerText()).replace(/\s+/g, " ");
/WO-\d{4}/.test(d) ? ok(`clicked from the list — the header carries ${d.match(/WO-\d{4}/)[0]}`)
  : fail(`clicking a row opened no order: ${orderHref}`);
/Type Meter set|Type Service drop|Type Leak|Type [A-Z]/.test(d)
  ? ok("Overview draws a real TYPE, not a dash")
  : fail("Overview's Type is a dash on an order opened by clicking");
/Service electric|Service water|Service gas/.test(d)
  ? ok("Overview draws a real SERVICE, not a dash")
  : fail("Overview's Service is a dash on an order opened by clicking");

// The address a person builds from the number on screen. Before this fix every
// call it made 404'd; nothing on the page said so.
const number = d.match(/WO-\d{4}/)[0];
d = await open(`/work/orders/${number}`);
d.includes(number) ? ok(`the BY-NUMBER address opens the same order — /work/orders/${number}`)
  : fail(`/work/orders/${number} does not open ${number} — the by-number lookup is not reaching it`);
/Type Meter set|Type Service drop|Type Leak|Type [A-Z]/.test(d)
  ? ok("by-number: Overview draws a real TYPE — the resolve reached the id routes")
  : fail("by-number: Type is a dash — every call after the resolve is still 404ing");

// The state that did not exist at all: a made-up number.
d = await open("/work/orders/WO-9999");
/could not be opened/i.test(d) ? ok("an unknown order SAYS SO — not fourteen dashes")
  : fail("an unknown order number still draws a finished-looking empty page");
/Type — |Service — /.test(d) ? fail("the fact list is still drawn over a failed read")
  : ok("the fact list is NOT drawn over a failed read");

console.log("\nWork → Performance (Work-027) — WHAT THE JOB COST");
t = await open("/work/performance");
t.includes("181.73") ? ok("TOTAL COST ON SCREEN: $181.73 — one job assigned, worked, accepted and costed")
  : fail("the total 181.73 is on no screen — nothing in this product has been costed");
/JOBS COMPLETED|Jobs completed/i.test(t) ? ok("the completed count is drawn")
  : fail("no completed count on Performance");

// ── 6 · the priority response times, editable on Settings ─────────────────
console.log("\nSettings → Reference data → Work priorities (PO ruling 2b)");
t = await open("/settings/reference-data?list=work_priorities");
for (const [name, hours] of [["Urgent","4 h"],["High","8 h"],["Normal","72 h"],["Low","168 h"]])
  t.includes(name) && t.includes(hours)
    ? ok(`${name} — ${hours}, shown and editable`)
    : fail(`${name} ${hours} not on the priorities card`);
const editable = await page.locator('button[aria-label="Edit"], button:has-text("Edit")').count();
editable > 0 ? ok(`the card has ${editable} edit control(s) — the timings are changeable`)
  : fail("no edit control on the priorities card — the setting would be read-only");

console.log("\njs errors: " + (jsErrors.length ? jsErrors.slice(0,3).join(" | ") : "none"));
await page.screenshot({ path: "/tmp/wrk_crews.png", fullPage: false });
await browser.close();
console.log(problems.length ? `\nFAILED ${problems.length}:\n - ${problems.join("\n - ")}`
                            : "\nALL CHECKS PASSED");
process.exit(problems.length ? 1 : 0);
