#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-10161 — pre-2.580 portal stop asks get their temporary-stop row.
// Usage:    TSB_BASE=http://127.0.0.1:8098 node 10-scripts/def_cus_10161_temporary_stop_backfill_walk.mjs <phase>
//           phase = before (2.580 code, 0086 NOT applied) | after (0086 applied)
//                   | short-future (a 3-day ask dated in the future: "At least 10 days.")
//           Run against a PRIVATE database copy only; `after` approves a request.
// ───────────────────────────────────────────────────────
import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.TSB_BASE || "http://127.0.0.1:8098";
const T = process.env.TSB_TENANT || "brazosbend";
const OUT = process.env.TSB_OUT || "05-prototype/temporary-stop-backfill-2026-10-14";
const DB = process.env.TSB_DB || "smartbillhub_tsbf";
const STAFF = process.env.TSB_STAFF || "dana@brazosbendutilities.com";
const STAFF_PW = process.env.TSB_STAFF_PW || "S3cure!passw0rd";
const CHROME = process.env.TSB_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHORT = process.env.TSB_SHORT || "SR-26-0061"; // SR-26-0017's words: 13 → 16 Oct
const VACATION = process.env.TSB_VACATION || "SR-26-0062"; // SR-26-0022's words: 14 → 28 Oct
const NEW_FROM = process.env.TSB_NEW_FROM || "2026-10-15";
const NEW_RESTART = process.env.TSB_NEW_RESTART || "2026-10-27";
const SHORT_FUTURE = process.env.TSB_SHORT_FUTURE || "SR-26-0067"; // 16 → 19 Oct, 3 days
const phase = process.argv[2] || "before";

if (DB === "smartbillhub") {
  console.error("REFUSED: never walk the shared dev database");
  process.exit(2);
}
const KILL = setTimeout(() => {
  console.error("REFUSED: walk exceeded 25 minutes");
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
async function staffSignIn() {
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", STAFF);
  await page.fill("#signin-password", STAFF_PW);
  await page.locator("#signin-password").press("Enter");
  await page.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 30000 });
}
const idOf = (number) => sql(`select id from service_requests where request_no='${number}'`);
async function openRequest(number) {
  await page.goto(`${BASE}/${T}/requests/${idOf(number)}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { level: 1 }).waitFor();
}

try {
  await staffSignIn();
  if (phase === "before") {
    await openRequest(SHORT);
    await shot("01-before-request-unclassified.png");
    const body = await page.locator("main").innerText();
    check("before: no Temporary stop on the request", !/temporary stop/i.test(body));
    await page.locator('[data-decision-action="approve"]').click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    await shot("02-before-approve-offers-new-connection-move-in.png");
    const text = await dialog.innerText();
    check("before: Approve offers New connection / Move-in", /New connection/.test(text) && /Move-in/i.test(text));
  }

  if (phase === "after") {
    await page.goto(`${BASE}/${T}/requests`, { waitUntil: "domcontentloaded" });
    await page.getByText("All", { exact: true }).first().click().catch(() => undefined);
    await page.getByPlaceholder(/Search request/).fill("SR-26-006");
    await page.getByText(SHORT).first().waitFor({ timeout: 120000 });
    await shot("03-after-requests-list-typed.png");
    check("after: the list types the stop asks", (await page.getByText("Temporary stop").count()) > 0);

    await openRequest(VACATION);
    await shot("04-after-vacation-request-typed.png");

    await openRequest(SHORT);
    await shot("05-after-short-request-typed.png");
    check("after: the request reads Temporary stop", /temporary stop/i.test(await page.locator("main").innerText()));
    await page.locator('[data-decision-action="approve"]').click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    check("after: no New connection / Move-in offered", (await dialog.locator("[data-outcome-picker]").count()) === 0);
    await shot("06-after-approve-window-refuses.png");
    const refusal = await dialog.innerText();
    check("after: the window names the date problem", /10 days|has passed/i.test(refusal), refusal.split("\n").slice(0, 30).join(" | "));
    await dialog.locator("#temporary-stop-from").fill(NEW_FROM);
    await dialog.locator("#temporary-stop-restart").fill(NEW_RESTART);
    await shot("07-after-approve-window-dates-edited.png");
    await dialog.getByRole("button", { name: "Approve", exact: true }).click();
    await page.waitForTimeout(3000);
    await shot("08-after-approved.png");
    const row = sql(
      `select r.state||'|'||coalesce(r.outcome,'')||'|'||t.status||'|'||t.stop_from||'|'||t.restart_on from temporary_stops t join service_requests r on r.id=t.request_id where r.request_no='${SHORT}'`,
    );
    check("after: approved on the edited dates", row === `approved|temporary_stop|scheduled|${NEW_FROM}|${NEW_RESTART}`, row);
    const accountId = sql("select id from accounts where account_no='AC-2026-00001'");
    await page.goto(`${BASE}/${T}/accounts/${accountId}`, { waitUntil: "domcontentloaded" });
    await page.locator("[data-temporary-stop-strip]").waitFor({ timeout: 60000 }).catch(() => undefined);
    await shot("09-after-account-stop-scheduled.png");
  }
  if (phase === "short-future") {
    await openRequest(SHORT_FUTURE);
    await page.locator('[data-decision-action="approve"]').click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    await shot("10-short-future-approve-window-at-least-10-days.png");
    const text = await dialog.innerText();
    check("short-future: the window says At least 10 days", /At least 10 days/.test(text), text.split("\n").slice(0, 14).join(" | "));
    await dialog.locator("#temporary-stop-restart").fill("2026-10-30");
    await shot("11-short-future-restart-moved.png");
    await dialog.getByRole("button", { name: "Approve", exact: true }).click();
    await page.waitForTimeout(3000);
    await shot("12-short-future-approved.png");
    const row = sql(
      `select r.state||'|'||t.status||'|'||t.stop_from||'|'||t.restart_on from temporary_stops t join service_requests r on r.id=t.request_id where r.request_no='${SHORT_FUTURE}'`,
    );
    check("short-future: approved for 14 days", row === "approved|scheduled|2026-10-16|2026-10-30", row);
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
