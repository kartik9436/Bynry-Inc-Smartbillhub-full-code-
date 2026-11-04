// CR-171-BRC10 P2.01–P2.03 (lane MVI-LIST-UI) — the Move-ins list walked in a
// browser at 1440 against images 01 and 02, so the next change re-runs this
// instead of re-remembering it.
//
//   MIN_BASE=http://127.0.0.1:5721 node 10-scripts/cr171_movein_list_walk.mjs
//
// Writes A01-list.png and A02-list-filter-open-chips.png into
// 08-qa/movein-2026-10-05/after-list/ and prints one ✓/✗ line per check.
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(HERE, "..", "07-frontend", "package.json"));
const { chromium } = require("playwright");

const BASE = process.env.MIN_BASE || "http://127.0.0.1:5721";
const T = process.env.MIN_TENANT || "brazosbend";
const EMAIL = process.env.MIN_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MIN_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MIN_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OUT = process.env.MIN_OUT || join(HERE, "..", "08-qa", "movein-2026-10-05", "after-list");

let pass = 0;
let fail = 0;
function ok(what, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    fail += 1;
    console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`);
  }
}

const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const p = await context.newPage();
p.setDefaultTimeout(25000);
await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

await p.goto(`${BASE}/${T}/accounts?tab=move-ins`, { waitUntil: "networkidle" });
await p.waitForSelector("table tbody tr");

console.log("image 01 — the list");
ok("title is Move-ins", (await p.locator("h1").first().innerText()).trim() === "Move-ins");
ok(
  "primary reads + New move-in",
  (await p.locator('.page-header-actions [data-variant="primary"]').innerText()).trim() ===
    "+ New move-in",
);
ok("no sub-line under the head", (await p.locator(".page-header-rollup").count()) === 0);
const tiles = await p.locator(".kpi-grid .k").allInnerTexts();
ok(
  "five tiles in image 01's order",
  tiles.map((x) => x.trim().toUpperCase()).join("|") ===
    "TO APPROVE|NOT STARTED|DRAFTS|STARTING THIS WEEK|WAITING ON A READ",
  tiles.join("|"),
);
const heads = (await p.locator("table thead th").allInnerTexts()).map((x) => x.trim().toUpperCase());
ok(
  "columns in image 01's order",
  heads.filter((x) => x !== "").join("|").startsWith(
    "REFERENCE|CUSTOMER|UNIT|SERVICES|MOVE-IN DATE|STEP|OPENING READ|DEPOSIT|STATE",
  ),
  heads.join("|"),
);
const rows = await p.locator("table tbody tr").count();
const icons = await p.locator("[data-move-in-action]").count();
ok("one icon on every row", icons === rows, `${icons} icons / ${rows} rows`);
const body = await p.locator("body").innerText();
ok("no footnote about the Requests tab", !body.includes("Requests tab"));
ok("no sort sentence", !body.includes("newest first"));
const scroll = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
ok("no horizontal scroll at 1440", scroll);
await p.screenshot({ path: join(OUT, "A01-list.png"), fullPage: false });

console.log("image 02 — the filter");
await p.locator("summary", { hasText: "+ Filter" }).click();
await p.getByRole("checkbox", { name: "Open", exact: true }).check();
await p.waitForTimeout(800);
const panelOpen = await p.locator("details[open] summary", { hasText: "+ Filter" }).count();
if (panelOpen === 0) {
  await p.locator("summary", { hasText: "+ Filter" }).click();
}
const water = p.getByRole("checkbox", { name: "Water", exact: true });
if ((await water.count()) > 0) {
  await water.check();
}
await p.waitForTimeout(1200);
const chips = await p.locator("body").innerText();
ok("Status: Open chip", chips.includes("Status: Open"));
ok("Service: Water chip", chips.includes("Service: Water"));
const req = await p.evaluate(() =>
  performance
    .getEntriesByType("resource")
    .map((e) => e.name)
    .filter((n) => n.includes("/move-ins?"))
    .pop(),
);
ok("f.status=open leaves the browser", (req ?? "").includes("f.status=open"), req);
ok("f.state is never sent", !(req ?? "").includes("f.state"), req);
await p.screenshot({ path: join(OUT, "A02-list-filter-open-chips.png"), fullPage: false });

clearTimeout(KILL);
await browser.close();
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
