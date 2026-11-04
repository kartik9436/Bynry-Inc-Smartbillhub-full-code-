// Combined walk of 2026-10-14 (decision log "EVERY ONE OF THE 77 TASKS IS
// WALKED END TO END IN A BROWSER") — the shared half of the step scripts:
// a browser, a staff sign-in, a portal sign-in, screenshots, PASS/FAIL lines.
// Each step script imports this; none of them writes to the database except
// through the screens they drive.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

export const BASE = process.env.CW_BASE || "http://127.0.0.1:8095";
export const T = process.env.CW_TENANT || "brazosbend";
export const OUT = process.env.CW_OUT || "05-prototype/combined-walk-2026-10-14";
export const STAFF_PASSWORD = process.env.CW_PASSWORD || "S3cure!passw0rd";
export const PORTAL_LOGIN = process.env.CW_PORTAL_LOGIN || "alvarez0@example.invalid";
export const PORTAL_PASSWORD = process.env.CW_PORTAL_PASSWORD || "Sample-Portal-2026!";

export async function open({ clock } = {}) {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  // The backend runs on a shifted clock for the later steps (README); the
  // browser's own clock is moved to the same day so a date picker agrees.
  if (clock) await page.clock.setSystemTime(new Date(clock));
  page.setDefaultTimeout(25000);
  const jsErrors = [];
  page.on("pageerror", (e) => jsErrors.push(String(e)));
  let failed = 0;
  const results = [];
  const check = (label, ok, detail = "") => {
    if (!ok) failed += 1;
    results.push({ label, ok, detail });
    console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  };
  const shot = async (name) => {
    await page.waitForLoadState("networkidle").catch(() => undefined);
    await page.waitForTimeout(500);
    await page.screenshot({ path: join(OUT, name), fullPage: true });
    console.log(`  shot ${name}`);
  };
  const staff = async (email = "dana@brazosbendutilities.com") => {
    await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
    await page.fill("#signin-email", email);
    await page.fill("#signin-password", STAFF_PASSWORD);
    await Promise.all([
      page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
      page.getByRole("button", { name: /sign in/i }).click(),
    ]);
    await page.waitForLoadState("networkidle").catch(() => undefined);
  };
  const portal = async () => {
    const r = await page.request.post(`${BASE}/api/${T}/portal/auth/sign-in`, {
      data: { email: PORTAL_LOGIN, password: PORTAL_PASSWORD },
    });
    if (!r.ok()) throw new Error(`portal sign-in ${r.status()} ${await r.text()}`);
  };
  const done = async () => {
    if (jsErrors.length) console.log(`  page errors: ${JSON.stringify(jsErrors.slice(0, 3))}`);
    await browser.close();
    console.log(failed === 0 ? "STEP PASSED" : `STEP: ${failed} FAILED`);
    return failed;
  };
  return { browser, page, check, shot, staff, portal, done, results, jsErrors };
}
