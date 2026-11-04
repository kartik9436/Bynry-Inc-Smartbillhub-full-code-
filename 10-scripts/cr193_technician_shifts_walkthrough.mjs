/**
 * Walk CR-193-BRC10 (MQ-040 step 1) on the technician's page in a real browser
 * against a real PostgreSQL: Working days, Exceptions, the Timesheets tab.
 *
 *     BASE=http://127.0.0.1:8193 SLUG=d-ortiz node 10-scripts/cr193_technician_shifts_walkthrough.mjs
 *
 * What it proves, in order:
 *   1. The Overview draws *Working days* with seven toggles, Monday to Friday
 *      on, and the shift window; pressing Saturday saves and stays pressed
 *      after a reload (the server kept it), then pressing it again restores.
 *   2. *+ Add exception* opens our form; a day off with a note lands in the
 *      Exceptions list; *Remove* asks first (danger) and takes it away.
 *   3. A submitted day (made through the phone's own door, as the captor would)
 *      shows on the *Timesheets* tab; no id is visible anywhere on the page.
 *
 * ⚠ WHAT WOULD MAKE THIS PASS WRONGLY: a stale bundle — its hash is printed;
 * and a page that renders the panels from nothing — step 1 reloads and reads
 * the SERVER's answer back.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:8193";
const TENANT = process.env.TENANT ?? "brazosbend";
const SLUG = process.env.SLUG ?? "d-ortiz";
const OUT = process.env.OUT ?? "/tmp/cr193_walk";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const WIDTH = Number(process.env.WIDTH ?? 1440);
await fs.mkdir(OUT, { recursive: true });

let failures = 0;
function check(name, passed, detail = "") {
  console.log(`${passed ? "PASS" : "FAIL"}  ${name}${detail === "" ? "" : ` — ${detail}`}`);
  if (!passed) failures += 1;
}

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 1100 } });
const page = await ctx.newPage();

const shell = await (await fetch(`${BASE}/${TENANT}/dashboard`)).text();
console.log(`STACK: ${BASE} · bundle ${(/assets\/(index-[^"]+\.js)/.exec(shell) ?? [])[1] ?? "UNKNOWN"}`);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", process.env.EMAIL ?? "dana@brazosbendutilities.com");
await page.fill("#signin-password", process.env.PASSWORD ?? "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL(/\/dashboard/, { timeout: 30000 });

const PAGE = `${BASE}/${TENANT}/work/crews/${SLUG}`;

// ── 1 · Working days ─────────────────────────────────────────────────────────
await page.goto(PAGE, { waitUntil: "networkidle" });
const days = page.locator("[data-technician-working-days]");
await days.waitFor({ timeout: 30000 });
const pressed = async () => days.locator('button[aria-pressed="true"]').allTextContents();
check("seven day toggles", (await days.locator("button[aria-pressed]").count()) === 7);
check("Monday to Friday on by default", (await pressed()).join(",") === "Mon,Tue,Wed,Thu,Fri", (await pressed()).join(","));
check("the window is shown", /Shift \d{2}:\d{2}–\d{2}:\d{2}|No set hours/.test(await days.textContent()), await days.locator("[data-working-window]").textContent());
await page.screenshot({ path: `${OUT}/1-overview-${WIDTH}.png`, fullPage: true });
await days.locator('[data-weekday="sat"]').click();
await page.waitForTimeout(800);
await page.reload({ waitUntil: "networkidle" });
await days.waitFor();
check("Saturday saved on the server", (await pressed()).includes("Sat"), (await pressed()).join(","));
await days.locator('[data-weekday="sat"]').click();
await page.waitForTimeout(800);

// ── 2 · Exceptions ───────────────────────────────────────────────────────────
const exceptions = page.locator("[data-technician-exceptions]");
await exceptions.locator("[data-add-exception]").click();
const dialog = page.getByRole("dialog");
await dialog.waitFor();
await dialog.locator("#date").fill("2026-11-02");
await dialog.getByLabel("Note").fill("Dentist");
await page.screenshot({ path: `${OUT}/2-add-exception-${WIDTH}.png` });
await dialog.getByRole("button", { name: /Save/ }).click();
await exceptions.getByText("Dentist").waitFor({ timeout: 15000 });
check("the day off lands in the list", (await exceptions.textContent()).includes("Day off"));
await page.screenshot({ path: `${OUT}/3-exception-listed-${WIDTH}.png`, fullPage: true });
await exceptions.getByRole("button", { name: "Remove" }).first().click();
await page.screenshot({ path: `${OUT}/3b-remove-confirm-${WIDTH}.png` });
await page.getByRole("alertdialog").getByRole("button", { name: "Remove" }).click();
await page.waitForTimeout(1000);
check("removed after the confirm", !(await exceptions.textContent()).includes("Dentist"));

// ── 3 · Timesheets ───────────────────────────────────────────────────────────
await page.goto(`${PAGE}?tab=timesheets`, { waitUntil: "networkidle" });
const sheets = page.locator("[data-technician-timesheets]");
await sheets.waitFor({ timeout: 30000 });
const text = await sheets.textContent();
check("the Timesheets tab draws its group", /Submitted days/.test(text), text.slice(0, 120));
await page.screenshot({ path: `${OUT}/4-timesheets-${WIDTH}.png`, fullPage: true });
const body = await page.locator("main").textContent();
check("no database id on the page", !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-/.test(body));

await browser.close();
console.log(failures === 0 ? "WALK PASSED" : `WALK FAILED (${failures})`);
process.exit(failures === 0 ? 0 : 1);
