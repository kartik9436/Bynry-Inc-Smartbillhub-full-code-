// `DEF-CUS` item 9 — *"the documents table shows no file"*, decided.
//
// The PO's screenshot shows `No file chosen` beside *Attach a file* and then a
// row of dashes. Two causes are possible and they have opposite fixes:
//
//   (a) the attach happened and the table does not show it  → a display bug
//   (b) no file was ever picked                             → not a bug at all
//
// `po20260922_new_request_reproduce.mjs` already proved the ATTACH path works
// end to end (row 0→1, `proof-of-identity.pdf · 193 B`, server `file_present:
// true`). **This script drives the OTHER button** — `Add another document`,
// the no-file path — and shows it produces exactly the drawn dash row.
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
  for (const root of ["/opt/pw-browsers"]) {
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const c = join(root, dir, sub);
        if (existsSync(c)) return c;
      }
    }
  }
  throw new Error("no chromium");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1200 } })).newPage();
page.setDefaultTimeout(20000);
try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", "dana@brazosbendutilities.com");
  await page.fill("#signin-password", "S3cure!passw0rd");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  await page.goto(`${BASE}/${TENANT}/requests/new`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  await page.fill("#applicant_name", "Item9, Proof");
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1200);
  await page.selectOption("#account_type_code", "residential");
  await page.waitForTimeout(500);
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(1200);
  for (const [sel, val] of [["#address_as_given", "212 Balcones Drive"], ["#city", "Austin"], ["#postal_code", "78704"]]) {
    const el = page.locator(sel);
    if ((await el.count()) > 0) await el.fill(val).catch(() => {});
  }
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2500);

  // ── (1) press `Attach a file` with NOTHING picked ────────────────────────
  console.log("\n  A · press `Attach a file` with no file chosen");
  const fileLabel = await page.evaluate(() => {
    const i = document.querySelector('input[type="file"]');
    return i && i.files && i.files.length ? i.files[0].name : "No file chosen";
  });
  console.log(`    · the picker reads: ${JSON.stringify(fileLabel)}`);
  await page.locator("[data-doc-attach]").click();
  await page.waitForTimeout(1500);
  const refusal = await page.locator("[data-doc-error]").textContent().catch(() => null);
  console.log(`    · refusal: ${JSON.stringify(refusal?.trim() ?? null)}`);
  console.log(`    · rows now: ${await page.locator("[data-doc-file]").count()}`);

  // ── (2) press `Add another document` — the NO-FILE path ──────────────────
  console.log("\n  B · press `Add another document` (the no-file button)");
  await page.locator("[data-doc-add]").click();
  const deadline = Date.now() + 25000;
  while (Date.now() < deadline) {
    if ((await page.locator("[data-doc-file]").count()) > 0) break;
    await page.waitForTimeout(600);
  }
  const files = await page.locator("[data-doc-file]").allTextContents();
  const states = await page.locator("[data-doc-state]").allTextContents();
  const picker = await page.evaluate(() => {
    const i = document.querySelector('input[type="file"]');
    return i && i.files && i.files.length ? i.files[0].name : "No file chosen";
  });
  console.log(`    · rows now: ${files.length}`);
  console.log(`    · FILE  column: ${files.map((c) => JSON.stringify(c.trim())).join(" | ")}`);
  console.log(`    · STATE column: ${states.map((c) => JSON.stringify(c.trim())).join(" | ")}`);
  console.log(`    · the picker still reads: ${JSON.stringify(picker)}`);
  await page.screenshot({ path: "/tmp/claude-0/shots/item9-add-another-document.png", fullPage: true });
  console.log("\n    → this is the PO's screenshot: `No file chosen` + a dash row.");
} catch (e) {
  console.log(`  stopped: ${e.message}`);
} finally {
  await browser.close();
}
