// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-010 (S9 History) · DEF-RAT-10029
// ───────────────────────────────────────────────────────
// Browser proof for DEF-RAT-10029: Plans & Rates → History and its Change
// details dialog show no database id. Photographs the list and the dialog of
// every row (a plan change with a tax, a plan change with a discount, a charge
// code change, a rate schedule change, and a row stored with no `before`), on a
// BEFORE build and an AFTER build pointed at the same local API.
//
//   node 10-scripts/def_rat_10029_history_no_ids_walk.mjs <before-base> <after-base> <out-dir>
//   e.g. http://127.0.0.1:5830/brazosbend http://127.0.0.1:5829/brazosbend /tmp/shots
//
// Fails (exit 1) if the AFTER build shows a uuid in any list or dialog text,
// or if any API request leaves 127.0.0.1 (never walk against the live API).
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(here, "..", "07-frontend", "package.json"));
const { chromium } = require("playwright");

const [BEFORE, AFTER, OUT] = process.argv.slice(2);
mkdirSync(OUT, { recursive: true });
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
});
let failed = false;

async function walk(label, base) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on("request", (request) => {
    const url = new URL(request.url());
    // The API must be local; a web font from its CDN is not an API call.
    if (url.hostname !== "127.0.0.1" && url.pathname.includes("/api")) {
      console.log(`${label} OFF-HOST REQUEST ${request.url()}`);
      failed = true;
    }
  });
  await page.goto(`${base}/signin`);
  await page.fill("#signin-email", "dana@brazosbendutilities.com");
  await page.fill("#signin-password", "S3cure!passw0rd");
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin")),
    page.getByRole("button", { name: /^Sign in/ }).click(),
  ]);
  const listUrl = `${base}/plans-rates/history`;
  const rows = [];
  page.on("response", async (response) => {
    if (response.url().includes("/rate-changes") && response.request().method() === "GET") {
      try {
        const body = await response.json();
        for (const row of body.results ?? []) rows.push(row);
      } catch {
        /* not JSON */
      }
    }
  });
  await page.goto(listUrl);
  await page.waitForTimeout(4000);
  await page.screenshot({ path: `${OUT}/${label}-0-history-list.png`, fullPage: true });
  const listText = await page.locator("main").innerText();
  console.log(`${label} list uuid on screen: ${UUID.test(listText)}`);
  if (label === "after" && UUID.test(listText)) failed = true;
  const seen = new Set();
  let index = 0;
  for (const row of rows) {
    if (seen.has(row.id)) continue;
    seen.add(row.id);
    index += 1;
    const name = `${row.entity_type}-${(row.reason || "").replace(/[^a-z0-9]+/gi, "-").slice(0, 30)}`;
    await page.goto(`${listUrl}?diff=${row.id}`);
    await page.waitForTimeout(2500);
    const dialog = page.locator(".modal-overlay");
    const text = (await dialog.count()) > 0 ? await dialog.innerText() : "";
    console.log(`${label} dialog ${index} ${name} uuid on screen: ${UUID.test(text)}`);
    if (label === "after" && (text === "" || UUID.test(text))) failed = true;
    await page.screenshot({ path: `${OUT}/${label}-${index}-${name}-details.png`, fullPage: true });
  }
  await page.close();
}

await walk("before", BEFORE);
await walk("after", AFTER);
await browser.close();
console.log(failed ? "FAIL" : "PASS");
process.exit(failed ? 1 : 0);
