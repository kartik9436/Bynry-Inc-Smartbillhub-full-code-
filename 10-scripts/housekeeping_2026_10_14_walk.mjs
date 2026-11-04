#!/usr/bin/env node
// Housekeeping lane, 2026-10-14 — decision log *"THE 77 OPEN TASKS FROM ROUNDS
// 1–3"* items 3, 10, 11. A browser walk of each user-facing fix, on a PRIVATE
// copy of the dev database (it commits a cancel). One mode per call:
//
//   HK_MODE=moveouts HK_SHOT=A1-before  — Accounts › Move-outs, searched for the
//       account, photographed; prints each row's date, reference and state.
//   HK_MODE=cancel HK_REF=MVI-26-00xx   — the move-in's details › More ▾ ›
//       Cancel move-in…, photographs the confirm (its "closes on" line), presses
//       it, photographs the result.
//   HK_MODE=runbook HK_KEY=bank_reconciliation — the runbook's Scope tab,
//       photographs the Settings-owned fields and prints each one's value.
//   HK_MODE=portaldocs                  — the customer portal's Documents page.
//   HK_MODE=charges                     — New Connection step 4's context strip
//       (a draft walked to Charges).
//
//   HK_BASE=http://127.0.0.1:8093 HK_OUT=05-prototype/housekeeping-2026-10-14
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.HK_BASE || "http://127.0.0.1:8093";
const T = process.env.HK_TENANT || "brazosbend";
const OUT = process.env.HK_OUT || "05-prototype/housekeeping-2026-10-14";
const EMAIL = process.env.HK_EMAIL || "sam.reyes@sample.test";
const PASSWORD = process.env.HK_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.HK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const MODE = process.env.HK_MODE || "moveouts";
const SHOT = process.env.HK_SHOT || MODE;
const ACCOUNT = process.env.HK_ACCOUNT || "AC-2026-00022";

const KILL = setTimeout(() => {
  console.error("REFUSED: walk exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
page.setDefaultTimeout(25000);
let failed = 0;
const check = (label, ok, detail = "") => {
  if (!ok) failed += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
};
async function shot(name) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(500);
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
  console.log(`  shot ${name}.png`);
}
async function signIn() {
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded", timeout: 180000 });
  await page.waitForSelector("#signin-email", { timeout: 180000 });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);
}

try {
  if (MODE === "moveouts") {
    await signIn();
    await page.goto(`${BASE}/${T}/accounts?tab=move-outs`, { waitUntil: "domcontentloaded" });
    const search = page.getByRole("searchbox").first();
    await search.waitFor();
    await search.fill(ACCOUNT);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    const rows = page.locator("tbody tr", { hasText: ACCOUNT });
    const n = await rows.count();
    const texts = [];
    for (let i = 0; i < n; i += 1) texts.push((await rows.nth(i).innerText()).replace(/\s+/g, " ").trim());
    console.log(`  rows for ${ACCOUNT}: ${n}`);
    for (const text of texts) console.log(`    ${text}`);
    const want = Number(process.env.HK_EXPECT_ROWS || "1");
    check(`${want} row(s) for ${ACCOUNT}`, n === want, String(n));
    if (process.env.HK_EXPECT_TEXT) {
      check(`a row reads ${process.env.HK_EXPECT_TEXT}`, texts.some((t) => t.includes(process.env.HK_EXPECT_TEXT)));
    }
    await shot(SHOT);
  } else if (MODE === "cancel") {
    const ref = process.env.HK_REF;
    await signIn();
    await page.goto(`${BASE}/${T}/moves/${ref}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("[data-move-more]");
    await shot(`${SHOT}-1-details`);
    await page.locator("[data-move-more] summary").click();
    await page.locator('[data-testid="move-more-cancel"]').click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    await page.waitForSelector("[data-cancel-reverses]");
    const reverses = (await dialog.innerText()).replace(/\s+/g, " ");
    console.log(`  confirm: ${reverses.slice(0, 400)}`);
    if (process.env.HK_EXPECT_TEXT) {
      check(`the confirm says ${process.env.HK_EXPECT_TEXT}`, reverses.includes(process.env.HK_EXPECT_TEXT));
    }
    await shot(`${SHOT}-2-confirm`);
    await dialog.getByRole("button", { name: "Cancel move-in" }).click();
    await dialog.waitFor({ state: "detached", timeout: 30000 }).catch(() => undefined);
    await page.waitForTimeout(1500);
    const head = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    check("the move-in now reads Cancelled", /Cancel+ed/.test(head), head.slice(0, 200));
    await shot(`${SHOT}-3-cancelled`);
  } else if (MODE === "cancel-api") {
    // ⚠ The details page offers *Cancel move-in…* only on Not started /
    // Scheduled / Waiting on a read (`moveRecordActions.moveInActionSlots`). A
    // reopened move-in whose opening reads were all taken reads *Completed*, so
    // the walk sends the SAME two requests the confirm modal sends —
    // `GET /moves/{ref}/cancel-preview` then `POST /moves/{ref}/cancel` — from
    // the signed-in browser session, and photographs every screen after.
    const ref = process.env.HK_REF;
    await signIn();
    await page.goto(`${BASE}/${T}/moves/${ref}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("[data-move-more]");
    await shot(`${SHOT}-1-details-before`);
    const call = (method, path) =>
      page.evaluate(
        async ([m, p]) => {
          const response = await fetch(p, {
            method: m,
            credentials: "include",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: m === "POST" ? "{}" : undefined,
          });
          return { status: response.status, body: await response.json().catch(() => null) };
        },
        [method, path],
      );
    const preview = await call("GET", `/api/${T}/moves/${ref}/cancel-preview`);
    console.log(`  preview ${preview.status} ${JSON.stringify(preview.body).slice(0, 400)}`);
    const closesOn = preview.body?.data?.reverses?.account?.closes_on ?? preview.body?.reverses?.account?.closes_on;
    check("the confirm would close the account on the earlier tenancy's date", closesOn === process.env.HK_EXPECT_CLOSES_ON, String(closesOn));
    const done = await call("POST", `/api/${T}/moves/${ref}/cancel`);
    console.log(`  cancel ${done.status} ${JSON.stringify(done.body).slice(0, 500)}`);
    check("the cancel was accepted", done.status === 200, String(done.status));
    await page.goto(`${BASE}/${T}/moves/${ref}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("[data-move-more]").catch(() => undefined);
    await page.waitForTimeout(1500);
    const head = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    check("the move-in now reads Cancelled", /Cancel+ed/.test(head), head.slice(0, 160));
    await shot(`${SHOT}-2-details-cancelled`);
    await page.goto(`${BASE}/${T}/accounts`, { waitUntil: "domcontentloaded" });
    const box = page.getByRole("searchbox").first();
    await box.waitFor();
    await box.fill(ACCOUNT);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    await shot(`${SHOT}-3-accounts-list`);
  } else if (MODE === "details") {
    const ref = process.env.HK_REF;
    await signIn();
    await page.goto(`${BASE}/${T}/moves/${ref}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("[data-move-more], h1");
    await page.waitForTimeout(1500);
    const head = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    console.log(`  head: ${head.slice(0, 200)}`);
    if (process.env.HK_EXPECT_TEXT) {
      check(`the details read ${process.env.HK_EXPECT_TEXT}`, head.includes(process.env.HK_EXPECT_TEXT));
    }
    await shot(SHOT);
  } else if (MODE === "runbook") {
    const key = process.env.HK_KEY || "bank_reconciliation";
    await signIn();
    if (process.env.HK_ADD_TEMPLATE) {
      // The clerk's own step: Runbooks › Templates › the template › + Add.
      await page.goto(`${BASE}/${T}/runbooks/templates/${key}`, { waitUntil: "domcontentloaded" });
      const add = page.getByRole("button", { name: /\+ Add/ }).first();
      await add.waitFor({ timeout: 30000 });
      await shot(`${SHOT}-0-template`);
      await add.click();
      await page.waitForTimeout(2500);
    }
    await page.goto(`${BASE}/${T}/runbooks/${key}#scope`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("[data-settings-owned]");
    await page.waitForTimeout(2000);
    const fields = page.locator("[data-settings-owned]");
    const n = await fields.count();
    for (let i = 0; i < n; i += 1) {
      const node = fields.nth(i);
      const setting = await node.getAttribute("data-settings-owned");
      const state = await node.getAttribute("data-settings-state");
      const value = await node.locator("[data-settings-value]").innerText().catch(() => "");
      const href = await node.locator("a[data-settings-open]").getAttribute("href").catch(() => "");
      console.log(`    ${setting} · ${state} · ${value.replace(/\s+/g, " ")} · ${href}`);
    }
    if (process.env.HK_EXPECT_SETTING) {
      const node = page.locator(`[data-settings-owned="${process.env.HK_EXPECT_SETTING}"]`).first();
      check(`${process.env.HK_EXPECT_SETTING} is loaded from Settings`,
        (await node.getAttribute("data-settings-state")) === "loaded");
    }
    await page.locator("[data-settings-owned]").first().scrollIntoViewIfNeeded();
    await shot(SHOT);
  } else if (MODE === "charges") {
    await signIn();
    await page.goto(`${BASE}/${T}/connections/new?step=4`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(3000);
    const strip = page.locator("[data-build-context]");
    const seen = await strip.waitFor({ timeout: 20000 }).then(() => true, () => false);
    check("step 4 draws the context strip (now composed from the build home)", seen);
    if (seen) {
      const cells = await strip.locator("[data-context-cell]").count();
      check("seven cells", cells === 7, String(cells));
      console.log(`  strip: ${(await strip.innerText()).replace(/\s+/g, " ")}`);
    }
    await shot(SHOT);
  } else if (MODE === "step2") {
    // DEF-SHL-10116 — as a BILLING CLERK: New Connection step 2, a State that
    // is not the utility's own. The reason comes from GET /shell/display now.
    await signIn();
    const asked = [];
    page.on("response", (response) => {
      const url = response.url();
      if (url.includes("/settings/regional") || url.includes("/shell/display")) {
        asked.push(`${response.status()} ${new URL(url).pathname}`);
      }
    });
    await page.goto(`${BASE}/${T}/connections/new?step=2`, { waitUntil: "domcontentloaded" });
    const state = page.locator("#nc_state");
    await state.waitFor({ timeout: 30000 });
    await state.fill("IA");
    await state.press("Tab");
    await page.waitForTimeout(1500);
    const body = await page.locator("main").innerText();
    check("step 2 says the State is not the utility's", body.includes("Not this utility's state."));
    console.log(`  requests: ${asked.join(" | ")}`);
    check("no admin-only regional read was made", !asked.some((line) => line.includes("/settings/regional")));
    await state.scrollIntoViewIfNeeded();
    await shot(SHOT);
  } else if (MODE === "portaldocs") {
    // DEF-CWP-10118 — the customer's Documents page: the live answer, then the
    // same page when the documents read cannot be reached at all (the request
    // is aborted in the browser — a dropped connection), which must read as a
    // FAILURE with Try again and never as "Nothing has been sent to you yet".
    const email = process.env.HK_PORTAL_EMAIL || "alvarez0@example.invalid";
    const password = process.env.HK_PORTAL_PASSWORD || "Pine-Hill-2026!";
    await page.goto(`${BASE}/${T}/portal`, { waitUntil: "domcontentloaded", timeout: 180000 });
    const signed = await page.request.post(`${BASE}/api/${T}/portal/auth/sign-in`, {
      data: { email, password },
    });
    check("portal sign-in", signed.ok(), String(signed.status()));
    await page.goto(`${BASE}/${T}/portal/documents`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('[data-testid="documents"]', { timeout: 60000 });
    await page.waitForTimeout(1500);
    const live = await page.locator('[data-testid="documents"]').first();
    const liveState = await page.locator("[data-portal-state]").first().getAttribute("data-portal-state").catch(() => null);
    console.log(`  live page: state=${liveState ?? "rows"} · ${(await live.innerText()).replace(/\s+/g, " ").slice(0, 160)}`);
    await shot(`${SHOT}-1-live`);
    await page.route(/\/api\/[^?]*\/documents(\?|$)/, (route) =>
      route.request().resourceType() === "fetch" || route.request().resourceType() === "xhr"
        ? route.abort("failed")
        : route.continue(),
    );
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForSelector("[data-portal-state='failed']", { timeout: 60000 }).catch(() => undefined);
    await page.waitForTimeout(1000);
    const body = await page.locator("main").innerText().catch(() => page.locator("body").innerText());
    check("an unreachable read is a FAILED state", (await page.locator("[data-portal-state='failed']").count()) > 0);
    check("…and never the empty sentence", !body.includes("Nothing has been sent to you yet"));
    check("…with Try again", (await page.locator("[data-way-out='retry']").count()) > 0);
    await shot(`${SHOT}-2-unreachable`);
  }
} catch (error) {
  failed += 1;
  console.error(`  ERROR ${error?.message ?? error}`);
  await shot(`${SHOT}-ERROR`).catch(() => undefined);
} finally {
  clearTimeout(KILL);
  await browser.close();
  console.log(failed === 0 ? "WALK PASS" : `WALK FAIL (${failed})`);
  process.exit(failed === 0 ? 0 : 1);
}
