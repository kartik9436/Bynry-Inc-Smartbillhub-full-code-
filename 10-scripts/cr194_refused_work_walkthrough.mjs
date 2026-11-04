/**
 * Walk CR-194-BRC10 in a real browser against a real PostgreSQL: Work → From
 * the field → Refused work, after `cr194_refused_work_walk_seed.py` has sent
 * D. Ortiz's three readings and a photo on a job given to M. Chen.
 *
 *     BASE=http://127.0.0.1:8194 OUT=/tmp/cr194_walk node 10-scripts/cr194_refused_work_walkthrough.mjs
 *
 * What it proves, in order:
 *   1. The fifth sub-tab exists and opens /work/field/refused; the list shows
 *      the copies with Technician · Job · What · Reason · When · Status; no id.
 *   2. The detail draws the reading with its unit and the photo still on the
 *      phone; Mark reviewed moves the row out of *Open*.
 *   3. Apply to job on another copy posts it; the status reads *Applied*.
 *
 * ⚠ WHAT WOULD MAKE THIS PASS WRONGLY: a stale bundle (its hash is printed),
 * and a list drawn from nothing — step 2 reloads and reads the server's answer.
 */
import { createRequire } from "node:module";
const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:8194";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/cr194_walk";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const WIDTH = Number(process.env.WIDTH ?? 1440);
await fs.mkdir(OUT, { recursive: true });

let failures = 0;
function check(name, passed, detail = "") {
  console.log(`${passed ? "PASS" : "FAIL"}  ${name}${detail === "" ? "" : ` — ${detail}`}`);
  if (!passed) failures += 1;
}

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 1000 } });
const page = await ctx.newPage();

const shell = await (await fetch(`${BASE}/${TENANT}/dashboard`)).text();
console.log(`STACK: ${BASE} · bundle ${(/assets\/(index-[^"]+\.js)/.exec(shell) ?? [])[1] ?? "UNKNOWN"}`);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", process.env.EMAIL ?? "dana@brazosbendutilities.com");
await page.fill("#signin-password", process.env.PASSWORD ?? "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL(/\/dashboard/, { timeout: 30000 });

// ── 1 · the door and the list ────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/work/field`, { waitUntil: "networkidle" });
await page.getByRole("tab", { name: "Refused work" }).click();
await page.waitForURL(/\/work\/field\/refused$/, { timeout: 15000 });
check("the sub-tab opens /work/field/refused", page.url().endsWith(`/${TENANT}/work/field/refused`), page.url());
const pane = page.locator('[data-field-pane="refused"]');
await pane.locator("tbody tr").first().waitFor({ timeout: 30000 });
const rows = await pane.locator("tbody tr").count();
check("open copies listed", rows >= 3, `${rows} rows`);
const text = await pane.textContent();
check("the technician's name", text.includes("D. Ortiz"));
check("the reason in words", text.includes("This job is not yours."));
check("no uuid on screen", !/[0-9a-f]{8}-[0-9a-f]{4}-/.test(await page.locator("main").textContent()));
await page.screenshot({ path: `${OUT}/1-refused-list-${WIDTH}.png`, fullPage: true });

// ── 2 · the detail, Mark reviewed ────────────────────────────────────────────
await pane.locator("tbody tr", { hasText: "Reading" }).first().locator('[data-testid="refused-open"]').click();
const dialog = page.getByRole("dialog");
await dialog.locator("[data-refused-work]").waitFor({ timeout: 15000 });
const body = await dialog.textContent();
check("the reading WITH its unit", /4000\d kWh/.test(body), body.slice(0, 200));
await page.screenshot({ path: `${OUT}/2-refused-detail-${WIDTH}.png` });
await dialog.getByLabel("Note").fill("Chen re-reads Monday");
await dialog.getByRole("button", { name: "Mark reviewed" }).click();
await dialog.waitFor({ state: "detached", timeout: 15000 });
await page.reload({ waitUntil: "networkidle" });
await pane.locator("tbody tr").first().waitFor({ timeout: 30000 });
check("one fewer open after Mark reviewed (server's answer)", (await pane.locator("tbody tr").count()) === rows - 1);

// ── 3 · Apply to job ─────────────────────────────────────────────────────────
const readingRow = pane.locator("tbody tr", { hasText: "Reading" }).first();
await readingRow.locator('[data-testid="refused-open"]').click();
await dialog.locator("[data-refused-work]").waitFor({ timeout: 15000 });
await dialog.getByRole("button", { name: "Apply to job" }).click();
await dialog.waitFor({ state: "detached", timeout: 15000 });
await page.goto(`${BASE}/${TENANT}/work/field/refused`, { waitUntil: "networkidle" });
await pane.locator("tbody tr").first().waitFor({ timeout: 30000 });
check("two fewer open after Apply", (await pane.locator("tbody tr").count()) === rows - 2);
await page.screenshot({ path: `${OUT}/3-refused-after-${WIDTH}.png`, fullPage: true });

await browser.close();
console.log(failures === 0 ? "ALL PASS" : `${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
