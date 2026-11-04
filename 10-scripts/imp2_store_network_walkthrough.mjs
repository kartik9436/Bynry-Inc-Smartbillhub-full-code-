// Lane IMP-2 — Q6 (store network from the file) and Q7 (saved column layout),
// walked through the screens. Decision log 2026-10-30 "Eight open payment
// questions answered (PO)" and "Lane IMP-2: Q6 … Q7 … built".
//
//   WEB=http://127.0.0.1:8197 OUT=<dir> FILES=<dir from imp2_walk_prep.py> \
//     node 10-scripts/imp2_store_network_walkthrough.mjs
//
// Against a PRIVATE walk database after `imp2_walk_prep.py` made four accounts
// and two files. What it does and prints:
//   1 · week1.csv (2 lockbox rows, 2 Hy-Vee rows, a Network column) → stage 2:
//       Network is mapped; tick "Save mapping as template", name it
//       "Hy-Vee weekly"; Validate → "Template Hy-Vee weekly saved."; load it.
//   2 · Payments list: the Hy-Vee rows read "Store · Hy-Vee", lockbox rows "File".
//   3 · A Hy-Vee payment's page: Source reads "Store · Hy-Vee".
//   4 · Deposits: a Lockbox batch and a "Store · Hy-Vee" batch for 29 Oct.
//   5 · week2.csv (same headers) → stage 2 says "Mapped with template Hy-Vee
//       weekly." and every column is already mapped.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
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
const WEB = process.env.WEB || "http://127.0.0.1:8197";
const TENANT = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "/tmp/imp2-walk/po";
const FILES = process.env.FILES || "/tmp/imp2-walk";
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME || resolveChromium(),
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--no-zygote", "--disable-gpu"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const say = (what) => console.log(what);
page.on("pageerror", (e) => say(`PAGE ERROR: ${e.message}`));
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 400) say(`API ${r.request().method()} ${new URL(r.url()).pathname} → ${r.status()}`);
});
const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
const body = () => page.evaluate(() => document.body.innerText);
const stage = () =>
  page.evaluate(() => document.querySelector('[data-workflow="runner"]')?.getAttribute("data-stage"));

async function waitStage(n) {
  for (let i = 0; i < 120; i += 1) {
    if ((await stage()) === String(n)) return true;
    await page.waitForTimeout(500);
  }
  return false;
}

/** Each header of the file → the column it is mapped to, as the screen shows it. */
async function mapped() {
  return page.evaluate(() =>
    ["Store Acct", "Paid", "Txn Date", "Receipt", "Network"]
      .map((header) => {
        const select = document.getElementById(`import-map-map-${header}`);
        return `${header}→${select ? select.options[select.selectedIndex]?.text : "?"}`;
      })
      .join(" · "),
  );
}

async function upload(file) {
  await page.goto(`${WEB}/${TENANT}/payments/imports/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.setInputFiles('input[type="file"]', `${FILES}/${file}`);
  await page.locator('button:has-text("Transform →")').click();
  return waitStage(2);
}

// ONLY=screens re-reads steps 2–4 and ONLY=week2 re-runs step 5, without
// loading a file again (a payments file already loaded is refused at upload).
const ONLY = process.env.ONLY || "";
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

  if (ONLY === "") {
  // ── 1 · week 1 ────────────────────────────────────────────────────────────
  await page.goto(`${WEB}/${TENANT}/payments/imports/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await shot("q7-01-step1");
  const step1 = await body();
  say(`step 1 says 'not available yet': ${step1.includes("not available yet")}`);
  say(`step 1 help 'Picked when the headers match.': ${step1.includes("Picked when the headers match.")}`);
  say(`reached stage 2: ${await upload("week1.csv")}`);
  await page.waitForTimeout(1500);
  say(`week 1 as the server guessed it: ${await mapped()}`);
  // A partner's own headers: the clerk maps the three it could not guess.
  for (const [header, label] of [
    ["Store Acct", "Account #"],
    ["Txn Date", "Date paid"],
    ["Receipt", "Reference"],
  ]) {
    await page.locator(`[id="import-map-map-${header}"]`).selectOption({ label });
  }
  say(`week 1 as the clerk mapped it: ${await mapped()}`);
  // The kit draws its own mark over the native box, so a person clicks the label.
  await page.locator("label", { hasText: "Save mapping as template" }).first().click();
  await page.waitForTimeout(300);
  say(`Validate disabled with no name: ${await page.locator('button:has-text("Validate →")').isDisabled()}`);
  await page.getByLabel(/Template name/).fill("Hy-Vee weekly");
  await shot("q7-02-step2-save-as-template");
  await page.locator('button:has-text("Validate →")').click();
  say(`reached stage 3: ${await waitStage(3)}`);
  await page.waitForTimeout(2500);
  await shot("q7-03-step3-template-saved");
  say(`'Template Hy-Vee weekly saved.' shown: ${(await body()).includes("Template Hy-Vee weekly saved.")}`);
  await page.locator('button:has-text("Load →")').click();
  say(`reached stage 4: ${await waitStage(4)}`);
  await page.waitForTimeout(3000);
  await shot("q6-03b-step4");
  say(`step 4: ${(await body()).replace(/\s+/g, " ").slice(0, 1200)}`);
  if (await page.locator('button:has-text("Commit load ✓")').isDisabled().catch(() => false)) {
    // The approval tick, if the server asked for one: click its label.
    const labels = page.locator("label:has(input[type=checkbox])");
    for (let i = 0; i < (await labels.count()); i += 1) {
      const text = (await labels.nth(i).innerText()).toLowerCase();
      if (text.includes("approv") || text.includes("confirm") || text.includes("checked")) {
        await labels.nth(i).click();
      }
    }
    await page.waitForTimeout(800);
  }
  await page.locator('button:has-text("Commit load ✓")').click();
  say(`reached stage 5: ${await waitStage(5)}`);
  await page.waitForTimeout(3000);
  await shot("q6-04-load-result");
  }

  if (ONLY !== "week2") {
  // ── 2 · Payments list ─────────────────────────────────────────────────────
  await page.goto(`${WEB}/${TENANT}/payments`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.getByRole("tab", { name: "Payments", exact: true }).or(
    page.locator("a, button").filter({ hasText: /^Payments$/ }).last(),
  ).first().click();
  await page.waitForTimeout(3000);
  await shot("q6-05-payments-list");
  const list = await body();
  say(`list rows reading 'Store · Hy-Vee': ${(list.match(/Store · Hy-Vee/g) || []).length}`);

  // ── 3 · a Hy-Vee payment's page ──────────────────────────────────────────
  const link = page.locator("tr", { hasText: "Store · Hy-Vee" }).first().locator("a").first();
  if ((await link.count()) > 0) {
    await link.click();
    await page.waitForTimeout(3000);
    await shot("q6-06-payment-page");
    say(`payment page Source 'Store · Hy-Vee': ${(await body()).includes("Store · Hy-Vee")}`);
  } else {
    say("payment page: no Hy-Vee row link found");
  }

  // ── 4 · Deposits ─────────────────────────────────────────────────────────
  await page.goto(`${WEB}/${TENANT}/finance/deposits`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  await shot("q6-07-deposits");
  const deposits = await body();
  say(`deposits 'Store · Hy-Vee' batch: ${deposits.includes("Store · Hy-Vee")} · Lockbox batch: ${deposits.includes("Lockbox")}`);

  }
  // ── 5 · week 2, same headers ─────────────────────────────────────────────
  if (ONLY === "" || ONLY === "week2") {
  say(`week 2 reached stage 2: ${await upload("week2.csv")}`);
  await page.waitForTimeout(1500);
  await shot("q7-08-week2-mapped-by-template");
  const week2 = await body();
  say(`'Mapped with template Hy-Vee weekly.' shown: ${week2.includes("Mapped with template Hy-Vee weekly.")}`);
  say(`week 2 as it arrived: ${await mapped()}`);
  }
} finally {
  await browser.close();
}
