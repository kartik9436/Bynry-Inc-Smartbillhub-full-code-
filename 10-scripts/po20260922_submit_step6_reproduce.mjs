// ── Trace ──────────────────────────────────────────────
// Change:  PO report 2026-09-22 — step 6 of `REQ-03` answers *"We could not
//          submit this request / Something went wrong. Nothing was saved — try
//          again."* on the deployed build (`v2.325.1`, tenant
//          `ottumwa-water-works`, draft `SR-26-0011`).
// Rules:   `22-product-maintenance-process.md` step 0 (REPRODUCE IT FIRST)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PO'S OWN TENANT IS NOT IN THIS TREE'S SEED** — the demo database
// holds `brazosbend` only — so this drives the SAME PATH on the tenant we
// have. If it reproduces here the cause is in the code; if it does not, the
// cause is that tenant's DATA and the next step is a readback, not a fix.
// Saying which of the two it is IS the finding.
//
//   BASE=http://127.0.0.1:8289 node 10-scripts/po20260922_submit_step6_reproduce.mjs
const { existsSync, readdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8289";
const TENANT = process.env.TENANT ?? "brazosbend";

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const dir of readdirSync("/opt/pw-browsers")) {
    if (!dir.startsWith("chromium")) continue;
    for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
      const c = join("/opt/pw-browsers", dir, sub);
      if (existsSync(c)) return c;
    }
  }
  throw new Error("no chromium");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1200 } })).newPage();
page.setDefaultTimeout(20000);

// Every request the page makes, so a 500 cannot hide behind a screen sentence.
const calls = [];
page.on("response", (r) => {
  const u = r.url();
  if (u.includes("/api/")) calls.push({ status: r.status(), method: r.request().method(), url: u.replace(BASE, "") });
});

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", "dana@brazosbendutilities.com");
  await page.fill("#signin-password", "S3cure!passw0rd");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  await page.goto(`${BASE}/${TENANT}/requests/new`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  await page.fill("#applicant_name", "Submit, Repro");
  const email = page.locator("#applicant_email");
  if ((await email.count()) > 0) await email.fill("submit.repro@example.com").catch(() => {});
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1500);

  await page.selectOption("#account_type_code", "residential");
  await page.waitForTimeout(700);
  // pick a service, so the request has something to be about
  const chips = page.locator("[data-service-pick], [data-service-option]");
  if ((await chips.count()) > 0) {
    await chips.first().click().catch(() => {});
    await page.waitForTimeout(400);
  }
  console.log(`  connection date opens on: ${await page.locator("#requested_start").inputValue().catch(() => "(absent)")}`);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1500);

  for (const [sel, val] of [["#address_as_given", "212 Balcones Drive"], ["#city", "Austin"], ["#postal_code", "78704"]]) {
    const el = page.locator(sel);
    if ((await el.count()) > 0) await el.fill(val).catch(() => {});
  }
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2000);
  await page.click('button:has-text("Continue")'); // documents — nothing required
  await page.waitForTimeout(2000);
  await page.click('button:has-text("Continue")'); // fees
  await page.waitForTimeout(2000);

  const url = page.url();
  console.log(`\n  on: ${url}`);
  const reqId = new URL(url).searchParams.get("request");
  console.log(`  draft: ${reqId}`);

  // ── STEP 6 · SUBMIT ──────────────────────────────────────────────────────
  const body = await page.locator("main").innerText().catch(() => "");
  const onSubmitPanel = body.split("\n").filter((l) => /REQUEST NUMBER|STATE|WAITING ON|already allocated/i.test(l));
  console.log(`  the On submit panel says:\n${onSubmitPanel.map((l) => `      ${l}`).join("\n")}`);

  calls.length = 0;
  // ⚠ **THE EXACT LABEL, NOT A `has-text("Submit")`.** The first draft of this
  // script used the loose match, and `.last()` resolved to the STEPPER's
  // "6 Check & submit" item — so it clicked a step, made NO api call, and then
  // "succeeded" because the success regex matched the request number already on
  // the panel. A check whose success condition is satisfied by the page it
  // started on is law 7's *incapable of failing*, in this lane's own script.
  const submit = page.locator('button:has-text("Submit the request")').first();
  if ((await submit.count()) === 0) {
    console.log("  ⚠ no Submit control on step 6");
  } else {
    await submit.click();
    const deadline = Date.now() + 30000;
    while (Date.now() < deadline) {
      const txt = await page.locator("main").innerText().catch(() => "");
      // Only terminal states — and NOT the request number, which is printed on
      // the panel before anything is pressed.
      if (/could not submit|Something went wrong|is with us now|Submitted ✓/i.test(txt)) break;
      if (calls.some((c) => /\/submit$/.test(c.url))) break;
      await page.waitForTimeout(800);
    }
    const after = await page.locator("main").innerText().catch(() => "");
    const failed = /could not submit|Something went wrong/i.test(after);
    console.log(`\n  ${failed ? "● REPRODUCED — the screen refuses" : "✓ submit went through"}`);
    console.log(`  screen now reads:\n${after.split("\n").slice(0, 25).map((l) => `      ${l}`).join("\n")}`);
  }
  console.log(`\n  API calls during submit:`);
  for (const c of calls) console.log(`      ${c.status}  ${c.method} ${c.url}`);
  await page.screenshot({ path: "/tmp/claude-0/shots/submit-step6.png", fullPage: true });
} catch (e) {
  console.log(`  stopped: ${e.message}`);
  await page.screenshot({ path: "/tmp/claude-0/shots/submit-ERROR.png", fullPage: true }).catch(() => {});
  console.log(`  API calls seen:`);
  for (const c of calls.slice(-15)) console.log(`      ${c.status}  ${c.method} ${c.url}`);
} finally {
  await browser.close();
}
