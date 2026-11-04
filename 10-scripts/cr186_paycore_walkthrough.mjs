// CR-186-BRC10 lane PAY-CORE — posted, then cleared, walked through the screens.
//
//   WEB=http://127.0.0.1:8191 OUT=<dir> STEP=batch|cleared|cancel \
//     node 10-scripts/cr186_paycore_walkthrough.mjs
//
// Against a PRIVATE copy of the demo database, after the lane's set-up script
// has put Dana's till through the real services (cash $300 + cheques $200 and
// $300, closed). Each STEP prints what it read off the screen and saves a
// screenshot:
//   batch   · the Deposits list shows ONE all-tenders batch for the till; the
//             batch page shows Totals by tender (Cash 300 · Check 500) and the
//             three members "Not cleared yet"
//   cleared · after the reconcile: the same members show their clearing date
//             and a member's page offers no Cancel (cleared at the bank)
//   cancel  · a posted card payment is cancelled from its page
import { mkdirSync, existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const WEB = process.env.WEB || "http://127.0.0.1:8191";
const TENANT = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "/tmp/cr186-walk";
const STEP = process.env.STEP || "batch";
const BATCH = process.env.BATCH || "";
const PAYMENT = process.env.PAYMENT || "";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({
  executablePath: process.env.CHROME || resolveChromium(),
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--no-zygote", "--disable-gpu"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const say = (what) => console.log(`[${STEP}] ${what}`);
page.on("pageerror", (e) => say(`PAGE ERROR: ${e.message}`));
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 400) say(`API ${r.request().method()} ${new URL(r.url()).pathname} → ${r.status()}`);
});
const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
const body = () => page.evaluate(() => document.body.innerText);

try {
  await page.goto(`${WEB}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", process.env.EMAIL ?? "dana@brazosbendutilities.com");
  await page.fill("#signin-password", process.env.PASSWORD ?? "S3cure!passw0rd");
  await page.waitForTimeout(3000);
  await page.fill("#signin-password", process.env.PASSWORD ?? "S3cure!passw0rd");
  await Promise.all([
    page.waitForResponse((r) => r.request().method() === "POST" && r.status() < 400, { timeout: 90000 }),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForTimeout(2000);

  if (STEP === "batch" || STEP === "cleared") {
    await page.goto(`${WEB}/${TENANT}/finance/deposits`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await shot(`${STEP}-01-deposits-list`);
    const list = await body();
    const row = list.split("\n").find((line) => line.includes(BATCH)) ?? "(row not found)";
    say(`deposits row: ${row.replace(/\s+/g, " ").slice(0, 200)}`);
    await page.locator(`a:has-text("${BATCH}")`).first().click();
    await page.waitForTimeout(3000);
    await shot(`${STEP}-02-batch-page`);
    const detail = await body();
    say(`Totals by tender shown: ${detail.includes("Totals by tender")}`);
    say(`tender lines: ${(detail.match(/(Cash|Check)[^\n]*\n?[^\n]*\$\d[\d,]*\.\d\d/g) || []).join(" | ").replace(/\s+/g, " ")}`);
    say(`members not cleared: ${(detail.match(/Not cleared yet/g) || []).length}`);
    say(`clearing dates shown: ${(detail.match(/20\d\d-\d\d-\d\d/g) || []).length}`);
  }

  if (STEP === "cleared" || STEP === "cancel") {
    await page.goto(`${WEB}/${TENANT}/payments/${encodeURIComponent(PAYMENT)}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(3000);
    await shot(`${STEP}-03-payment-page`);
    const text = await body();
    say(`status words: ${(text.match(/\b(Posted|Cleared|Canceled)\b/g) || []).slice(0, 4).join(",")}`);
    const cancel = page.locator('button:has-text("Cancel")').first();
    const present = (await cancel.count()) > 0;
    say(`Cancel button present: ${present}${present ? ` · disabled: ${await cancel.isDisabled()}` : ""}`);
    if (STEP === "cleared" && present) {
      await cancel.hover().catch(() => undefined);
      await page.waitForTimeout(800);
      await shot(`${STEP}-04-cancel-refused-reason`);
      say(`refusal reason on screen: ${(await body()).includes("Issue a refund or credit")}`);
    }
    if (STEP === "cancel" && present && !(await cancel.isDisabled())) {
      await cancel.click();
      await page.waitForTimeout(1500);
      await page.selectOption('[role="dialog"] select, .modal-card select', { index: 1 }).catch(() => undefined);
      await shot(`${STEP}-04-cancel-dialog`);
      await page.locator('[role="dialog"] button:has-text("Cancel payment"), .modal-card button:has-text("Cancel payment")').last().click();
      await page.waitForTimeout(3000);
      await shot(`${STEP}-05-after-cancel`);
      say(`after cancel: ${(await body()).match(/canceled|Canceled/) ? "Canceled shown" : "no change seen"}`);
    }
  }
} finally {
  await browser.close();
}
