#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-183-BRC10 — the temporary-stop walk (PO rulings B1–B4, 2026-10-14).
// Usage:    TS_BASE=http://127.0.0.1:8087 node 10-scripts/cr183_temporary_stop_walk.mjs <phase>
//           phase = ask | approve | portal-restart | approve-restart
//           Run against a PRIVATE database copy only; it writes requests.
// ───────────────────────────────────────────────────────
import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.TS_BASE || "http://127.0.0.1:8087";
const T = process.env.TS_TENANT || "brazosbend";
const OUT = process.env.TS_OUT || "05-prototype/temporary-stop-2026-10-14";
const DB = process.env.TS_DB || "smartbillhub_tstop";
const STAFF = process.env.TS_STAFF || "dana@brazosbendutilities.com";
const STAFF_PW = process.env.TS_STAFF_PW || "S3cure!passw0rd";
const PORTAL = process.env.TS_PORTAL || "alvarez0@example.invalid";
const PORTAL_PW = process.env.TS_PORTAL_PW || "Sample-Portal-2026!";
const CHROME = process.env.TS_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const STOP = process.env.TS_STOP || "2026-10-14";
const RESTART = process.env.TS_RESTART || "2026-10-30";
const phase = process.argv[2] || "ask";

const KILL = setTimeout(() => {
  console.error("REFUSED: walk exceeded 8 minutes");
  process.exit(3);
}, 1500000);

function sql(query) {
  return execSync(`psql -h localhost -U smartbillhub -d ${DB} -Atc "${query}"`, {
    env: { ...process.env, PGPASSWORD: "smartbillhub" },
  })
    .toString()
    .trim();
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({
  executablePath: CHROME,
  args: ["--disable-dev-shm-usage", "--js-flags=--max-old-space-size=4096"],
});
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
page.setDefaultTimeout(30000);
page.setDefaultNavigationTimeout(240000);
let failed = 0;
const check = (label, ok, detail = "") => {
  if (!ok) failed += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
};
async function shot(name) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(OUT, name), fullPage: true });
  console.log(`  shot ${name}`);
}

async function portalSignIn() {
  await page.goto(`${BASE}/${T}/portal/sign-in`, { waitUntil: "domcontentloaded" });
  await page.locator('input[type="email"]').first().fill(PORTAL);
  await page.locator('input[type="password"]').first().fill(PORTAL_PW);
  await page.getByRole("button", { name: "Sign in", exact: true }).last().click();
  await page.waitForURL((url) => !url.pathname.endsWith("/sign-in"), { timeout: 30000 });
}

async function staffSignIn() {
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", STAFF);
  await page.fill("#signin-password", STAFF_PW);
  await page.locator("#signin-password").press("Enter");
  await page.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 30000 });
}

try {
  if (phase === "ask") {
    await portalSignIn();
    await page.goto(`${BASE}/${T}/portal/stop-or-restart`, { waitUntil: "domcontentloaded" });
    await shot("01-portal-stop-or-restart.png");
    await page.locator('[data-action="continue"]').first().click();
    await page.fill("#stop_from", STOP);
    await page.fill("#start_again", RESTART);
    await page.fill("#reason", "Away visiting family");
    await shot("02-portal-dates.png");
    await page.locator('[data-action="continue"]').last().click();
    const phone = page.locator("#stop_phone");
    if ((await phone.inputValue()) === "") await phone.fill("(512) 555-0134");
    await shot("03-portal-check.png");
    await page.getByRole("button", { name: /Request this/ }).click();
    await page.waitForTimeout(2500);
    await shot("04-portal-asked.png");
    const row = sql(
      "select r.request_no||'|'||t.status||'|'||t.stop_from||'|'||t.restart_on from temporary_stops t join service_requests r on r.id=t.request_id order by t.created_at desc limit 1",
    );
    check("the ask is stored with its dates", row.includes(`|requested|${STOP}|${RESTART}`), row);
    await page.goto(`${BASE}/${T}/portal/account`, { waitUntil: "domcontentloaded" });
    await shot("05-portal-account-pending.png");
  }

  if (phase === "approve" || phase === "approve-restart") {
    const which = phase === "approve" ? "request_id" : "restart_request_id";
    const id = sql(`select ${which} from temporary_stops where ${which} is not null order by created_at desc limit 1`);
    await staffSignIn();
    await page.goto(`${BASE}/${T}/requests`, { waitUntil: "domcontentloaded" });
    await shot(phase === "approve" ? "06-staff-requests-list.png" : "13-staff-requests-list-restart.png");
    await page.goto(`${BASE}/${T}/requests/${id}`, { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { level: 1 }).waitFor();
    await shot(phase === "approve" ? "07-staff-request-typed.png" : "14-staff-restart-request.png");
    await page.locator('[data-decision-action="approve"]').click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    check("no New connection / Move-in offered", (await dialog.locator("[data-outcome-picker]").count()) === 0);
    if (phase === "approve") {
      await dialog.getByLabel("Field visit needed").check({ force: true });
    }
    await shot(phase === "approve" ? "08-staff-approve-window.png" : "15-staff-approve-restart.png");
    await dialog.getByRole("button", { name: "Approve", exact: true }).click();
    await page.waitForTimeout(3000);
    await shot(phase === "approve" ? "09-staff-approved.png" : "16-staff-restart-approved.png");
    const status = sql(
      "select s.code from accounts a join account_statuses s on s.id=a.status_id where a.account_no='AC-2026-00001'",
    );
    check(
      phase === "approve" ? "the account is on vacation_hold" : "the account is active again",
      status === (phase === "approve" ? "vacation_hold" : "active"),
      status,
    );
    const accountId = sql("select id from accounts where account_no='AC-2026-00001'");
    await page.goto(`${BASE}/${T}/accounts/${accountId}`, { waitUntil: "domcontentloaded" });
    await shot(phase === "approve" ? "10-staff-account-on-hold.png" : "17-staff-account-active.png");
  }

  if (phase === "list") {
    await staffSignIn();
    await page.goto(`${BASE}/${T}/requests`, { waitUntil: "domcontentloaded" });
    await page.getByText("All", { exact: true }).first().click();
    await page.getByPlaceholder(/Search request/).fill("SR-26-006");
    await page.getByText("SR-26-0061").first().waitFor({ timeout: 120000 });
    await shot("18-staff-requests-typed.png");
    const typed = await page.getByText("Temporary stop").count();
    check("the list types the stop ask", typed > 0, `${typed} cell(s)`);
  }

  if (phase === "counter") {
    // T7 — a clerk starts a stop for a customer on the phone, from the account.
    const accountId = sql("select id from accounts where account_no='AC-2026-00001'");
    await staffSignIn();
    await page.goto(`${BASE}/${T}/accounts/${accountId}`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Temporary stop" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    await dialog.locator("#temporary-stop-start-restart").fill(process.env.TS_COUNTER_RESTART || "2026-11-20");
    await shot("19-staff-counter-start.png");
    await dialog.getByRole("button", { name: "Schedule stop" }).click();
    await page.locator("[data-temporary-stop-strip]").waitFor({ timeout: 60000 });
    await shot("20-staff-counter-scheduled.png");
    const row = sql("select channel||'|'||status||'|'||stop_from||'|'||restart_on from temporary_stops order by created_at desc limit 1");
    check("the counter stop is scheduled", row.startsWith("staff|"), row);
  }

  if (phase === "account-on-hold") {
    const accountId = sql("select id from accounts where account_no='AC-2026-00001'");
    await staffSignIn();
    await page.goto(`${BASE}/${T}/accounts/${accountId}`, { waitUntil: "domcontentloaded" });
    await page.locator('[data-temporary-stop-strip="on_hold"]').waitFor({ timeout: 60000 });
    await shot("21-staff-account-on-hold.png");
    await page.getByRole("button", { name: "Temporary stop" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    await shot("22-staff-change-or-end.png");
    await dialog.getByRole("button", { name: "End now" }).click();
    await page.waitForTimeout(3000);
    await shot("23-staff-ended.png");
    const status = sql(
      "select s.code from accounts a join account_statuses s on s.id=a.status_id where a.account_no='AC-2026-00001'",
    );
    check("End now puts the account back on active", status === "active", status);
  }

  if (phase === "portal-restart") {
    await portalSignIn();
    await page.goto(`${BASE}/${T}/portal/account`, { waitUntil: "domcontentloaded" });
    await page.locator('[data-testid="temporary-stop"]').waitFor();
    await shot("11-portal-paused.png");
    await page.getByRole("button", { name: "Restart my service now" }).click();
    await page.locator("[data-temporary-stop-restart-asked]").waitFor();
    await shot("12-portal-restart-asked.png");
  }
} catch (error) {
  failed += 1;
  console.error(`FAIL: ${error?.message ?? error}`);
  await page.screenshot({ path: join(OUT, `FAILED-${phase}.png`), fullPage: true }).catch(() => undefined);
}
await browser.close();
clearTimeout(KILL);
console.log(failed === 0 ? `WALK ${phase}: PASS` : `WALK ${phase}: ${failed} FAIL`);
process.exit(failed === 0 ? 0 : 1);
