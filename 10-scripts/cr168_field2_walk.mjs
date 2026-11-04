// ── Trace ──────────────────────────────────────────────
// Change:  CR-168-BRC10 §F.9, lane FIELD-2 — the field app on the technician
//          API, walked: R. Patel at 390 px works a job OFFLINE (Playwright's
//          offline mode) with a mocked 8 m fix, closes it, signs out; M. Chen
//          signs in on the same tablet and sees none of Patel's work; the
//          signal comes back and Patel's work syncs as Patel's. Then Dana at
//          1440 sees the bell, "photos uploading" switching to Accept, and no
//          "Location not precise".
// ───────────────────────────────────────────────────────
/**
 *   BASE=http://127.0.0.1:5197 ORDER_NO=WO-0046 TECH_PASSWORD=… OFFICE_PASSWORD=… \
 *     PHOTO=/path/a.jpg OUT=08-qa/work-2026-10-04/flows/field2 DISPATCH_CMD="…" \
 *     node 10-scripts/cr168_field2_walk.mjs
 *
 * ⚠ SIGNING IN NEEDS THE SERVER, so Chen's sign-in runs with the network up
 * but the TECHNICIAN API's write routes held (`route.abort`) — the tablet has
 * a session signal, not yet a data signal. "Back online" releases the hold.
 * The photo upload is held a little longer, so Dana can see the job closed
 * with its photo still uploading; releasing it is the photo arriving.
 *
 * What would make it pass wrongly: the outbox sending under Chen's identity
 * (checked on the server's receipts, not on screen), or a close carrying no
 * fix (checked on the order Dana opens: no "Location not precise").
 */
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, statSync } from "node:fs";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5197";
const TENANT = process.env.TENANT ?? "brazosbend";
const ORDER_NO = process.env.ORDER_NO ?? "WO-0046";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/flows/field2";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: EXE });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function shot(page, name) {
  const file = join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  const text = (await page.evaluate(() => document.body.innerText)).replace(/\s+/g, " ").slice(0, 260);
  console.log(`=== ${name}.png ${statSync(file).size} bytes ${page.url().replace(BASE, "")}\n    ${text}`);
}

async function signIn(page, email, password) {
  await page.goto(`${BASE}/${TENANT}/work/mobile/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  await sleep(2500);
}

// ── THE TABLET: 390 × 844, a fix of 8 m at the premises ──────────────────
const tablet = await browser.newContext({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
  permissions: ["geolocation"],
  geolocation: { latitude: 29.5601, longitude: -95.8072, accuracy: 8 },
});
const p = await tablet.newPage();
const sent = [];
p.on("request", (r) => {
  if (/\/work\/mobile\/(jobs\/[^/]+\/sync|photos\/)/.test(r.url())) sent.push(`${r.method()} ${r.url().replace(BASE, "")}`);
});

await signIn(p, "r.patel@sample.test", process.env.TECH_PASSWORD);
await shot(p, "01-patel-today-online");
await p.getByText(ORDER_NO).first().click();
await sleep(2000);
// Taking the job is an online act (technician-api.md #6).
const accept = p.getByRole("button", { name: /Accept job/ });
if (await accept.count()) {
  await accept.click();
  await sleep(1500);
}
await shot(p, "02-patel-job-accepted-online");
const jobUrl = p.url().replace(/\/$/, "");

// ── THE SIGNAL GOES ──────────────────────────────────────────────────────
await tablet.setOffline(true);
for (const box of await p.locator("[data-safety-id] input[type=checkbox]").all()) {
  if (!(await box.isChecked())) await box.click();
  await sleep(800);
}
for (const box of await p.locator("[data-task-id] label:not([data-task-camera]) input[type=checkbox]").all()) {
  if (!(await box.isChecked()) && (await box.isEnabled())) await box.click();
  await sleep(800);
}
const cameras = p.locator("[data-task-camera] input[type=file]");
for (let i = 0; i < (await cameras.count()); i += 1) {
  await cameras.nth(i).setInputFiles(process.env.PHOTO);
  await sleep(2500);
}
await shot(p, "03-patel-offline-ticked-and-photographed");

await p.locator('[data-pane="readings"] a').click();
await sleep(1500);
const reading = p.locator("[data-reading-id] input[inputmode=decimal]").first();
await reading.fill("4120");
await reading.blur();
await sleep(1500);
await shot(p, "04-patel-offline-reading");

await p.goto(`${jobUrl}/close`).catch(() => undefined); // offline: the SPA route, from the worker's cache
await sleep(500);
if (!(await p.getByText(/Passed/).count())) {
  // A full navigation with no signal may not be served; use the in-app link.
  await p.goBack();
  await sleep(800);
  await p.locator('[data-pane="close"] a').click();
}
await sleep(3500);
await p.getByLabel(/Passed/).check();
await shot(p, "05-patel-offline-close-with-8m-fix");
await p.locator('section[data-screen="WRK-23"] button').last().click();
await sleep(2500);
await shot(p, "06-patel-offline-after-close-waiting-to-send");

// ── PATEL SIGNS OUT, STILL OFFLINE ───────────────────────────────────────
await p.locator('[data-action="sign-out"]').click();
await sleep(2000);
await shot(p, "07-signed-out-offline");

// ── CHEN SIGNS IN. The session needs the server; data writes stay held. ──
let holdData = true;
let holdPhotos = true;
await p.route(/\/work\/mobile\/jobs\/[^/]+\/sync/, (route) => (holdData ? route.abort("internetdisconnected") : route.continue()));
await p.route(/\/work\/mobile\/photos\//, (route) => (holdPhotos ? route.abort("internetdisconnected") : route.continue()));
await tablet.setOffline(false);
await signIn(p, "m.chen@sample.test", process.env.TECH_PASSWORD);
await sleep(2000);
await shot(p, "08-chen-signed-in-sees-none-of-patels");
const chenSees = await p.evaluate(() => document.body.innerText);
console.log(`    Chen sees ${ORDER_NO}? ${chenSees.includes(ORDER_NO)}`);

// ── BACK ONLINE: the data goes, as Patel's ───────────────────────────────
console.log(`    sent while held: ${sent.length}`);
holdData = false;
await p.evaluate(() => window.dispatchEvent(new Event("online")));
await sleep(6000);
await shot(p, "09-chen-online-patels-data-sent-photo-uploading");

if (process.env.DISPATCH_CMD) console.log(execSync(process.env.DISPATCH_CMD).toString().trim().split("\n").slice(-2).join(" | "));

// ── DANA, 1440: the bell, the photo uploading, then Accept ───────────────
const office = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const d = await office.newPage();
await d.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await d.fill("#signin-email", process.env.OFFICE_EMAIL ?? "dana@brazosbendutilities.com");
await d.fill("#signin-password", process.env.OFFICE_PASSWORD);
await d.click('button[type="submit"]');
await d.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
await d.goto(`${BASE}/${TENANT}/work/orders/${ORDER_NO}`, { waitUntil: "networkidle" });
await sleep(2500);
await shot(d, "10-dana-order-photos-uploading");
await d.locator("details.shell-bell summary").click().catch(() => undefined);
await sleep(800);
await shot(d, "11-dana-bell-closed-photo-uploading");

// The photo arrives.
holdPhotos = false;
await p.evaluate(() => window.dispatchEvent(new Event("online")));
await sleep(8000);
await shot(p, "12-chen-tablet-nothing-waiting");
if (process.env.DISPATCH_CMD) console.log(execSync(process.env.DISPATCH_CMD).toString().trim().split("\n").slice(-2).join(" | "));

await d.reload({ waitUntil: "networkidle" });
await sleep(2500);
await d.locator("details.shell-bell summary").click().catch(() => undefined);
await sleep(800);
await shot(d, "13-dana-bell-photos-in-accept-available");
const text = await d.evaluate(() => document.body.innerText);
console.log(`    "Location not precise" on the order? ${text.includes("Location not precise")}`);
await d.keyboard.press("Escape");
await d.locator("details.shell-bell summary").click().catch(() => undefined);
const acceptEnabled = await d.locator('[data-action="accept"]').isEnabled().catch(() => false);
console.log(`    Accept available: ${acceptEnabled}`);
await d.locator('[data-action="accept"]').click();
await sleep(800);
await d.getByRole("button", { name: /accept/i }).last().click();
await sleep(3000);
await d.reload({ waitUntil: "networkidle" });
await sleep(1500);
await shot(d, "14-dana-accepted");
console.log(`    requests to the technician API: ${sent.length}`);
await browser.close();
