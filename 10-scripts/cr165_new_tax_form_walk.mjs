// ── Trace ──────────────────────────────────────────────
// Change:  CR-165-BRC10 round 2 task 4 — the New tax or fee form, photographed
//          in the SAME fourteen states as images 04–17 of
//          `05-prototype/taxes-fees-2026-10-03/images/`, so each pair can be
//          looked at side by side (B14 rule 42; the skill's close-out).
// ───────────────────────────────────────────────────────
//
// Expects the same stack as `cr165_taxes_fees_before_walk.mjs`:
//   * API — `manage.py runserver 127.0.0.1:<port>` on a scratch PostgreSQL 16
//     database with `migrate` + `seed_demo` (Brazos Bend, Dana);
//   * SPA — `vite build --mode wolocal`, then
//     `PORT=<port> API_PROXY_TARGET=http://127.0.0.1:<api> node 07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:8592 OUT=08-qa/taxes-fees-2026-10-03/after \
//     node 10-scripts/cr165_new_tax_form_walk.mjs
//
// Every photo is named after the drawing it is compared with: `04-…` beside
// `images/04-…`. A state the stack cannot reach yet (a list the back end has
// not served) is still photographed, and the printed line says what is missing.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8592";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr165-after";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1600 } });
const say = (...parts) => console.log(...parts);
async function shot(name, caption) {
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  say(`=== ${name}.png — ${caption}`);
}
const cont = () => page.getByRole("button", { name: "Continue", exact: true }).click();
async function optionLabels(id) {
  return page.$$eval(`#${id} option`, (els) => els.map((el) => el.textContent));
}
async function pickFirstReal(id) {
  const values = await page.$$eval(`#${id} option`, (els) => els.map((el) => el.value).filter((v) => v !== ""));
  if (values.length > 0) await page.selectOption(`#${id}`, values[0]);
  return values.length;
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees/new`, { waitUntil: "networkidle" });
await page.waitForSelector("#tax-name", { timeout: 30000 });
say("boundaries:", JSON.stringify(await optionLabels("tax-boundary")));
say("authorities:", JSON.stringify(await optionLabels("tax-authority")));

// 08 · errors first, on the empty form
await cont();
await shot("08-new-1-errors", "step 1, Continue on an empty form");

// 04 · filled
await page.fill("#tax-name", "State sales tax");
await pickFirstReal("tax-authority");
await shot("04-new-1-what-filled", "step 1 filled");

// 05 · services open — tick every offered service
await page.click("#tax-services");
for (const box of await page.$$("[data-check-dropdown-list] label:not(:first-child) input")) await box.check();
await shot("05-new-1-services-open", "services dropdown open");
await page.keyboard.press("Escape");

// 06 · classes open
await page.click("#tax-classes");
await shot("06-new-1-classes-open", "customer classes dropdown open");
await page.keyboard.press("Escape");

// 07 · a named place (only if the server offers one)
const boundaries = await page.$$eval("#tax-boundary option", (els) => els.map((el) => el.value));
let named = false;
for (const value of boundaries) {
  await page.selectOption("#tax-boundary", value);
  if (await page.$("#tax-place")) {
    named = true;
    break;
  }
}
await shot("07-new-1-named-place", named ? "a boundary that asks for a place" : "NO boundary from the server asks for a place yet");
if (boundaries.length > 0) await page.selectOption("#tax-boundary", boundaries[0]);

// 11 · step 2 errors
await cont();
await page.waitForSelector("[data-tax-step=much]");
await cont();
await shot("11-new-2-errors", "step 2, Continue with no rate");

// 09 · step 2 filled
await page.fill("#tax-rate", "6.25");
await page.fill("#tax-from", "2026-10-01");

await shot("09-new-2-how-filled", "step 2 filled at 6.25");

// 10 · the rate warning
await page.fill("#tax-rate", "62.5");
await shot("10-new-2-rate-warning", "step 2 at 62.5");

// 12 · a fixed amount (only if the server offers that basis)
const bases = await page.$$eval("#tax-basis option", (els) => els.map((el) => [el.value, el.textContent]));
say("bases:", JSON.stringify(bases));
const flat = bases.find(([value]) => value === "flat_per_bill");
if (flat) {
  await page.selectOption("#tax-basis", "flat_per_bill");
  await page.fill("#tax-rate", "6.25");
}
await shot("12-new-2-fixed-amount", flat ? "a fixed amount per bill" : "NO fixed-amount basis served yet");
if (flat) await page.selectOption("#tax-basis", "percent");
await page.fill("#tax-rate", "6.25");

// 14 · step 3 errors
await cont();
await page.waitForSelector("[data-tax-step=filing]");
await page.fill("#tax-code", "TX-STATE");
await page.fill("#tax-allowance", "0.5");
await page.fill("#tax-interest", "1.5");
await page.fill("#tax-reminder", "bad");
await cont();
await shot("14-new-3-filing-errors", "step 3 with no liability account and a bad email");

// 13 · step 3 filled
const accounts = await pickFirstReal("tax-liability");
say("liability accounts offered:", accounts);
await pickFirstReal("tax-due");
await pickFirstReal("tax-authority-account");
await page.fill("#tax-reminder", "filings@brazosbend.example");
await shot("13-new-3-filing-filled", "step 3 filled");

// 15 · review
await cont();
await page.waitForSelector("[data-tax-step=review]");
await shot("15-new-4-review", "review at 6.25");

// 16 · review with the warning
await page.getByRole("button", { name: /^Edit Rate/ }).click();
await page.fill("#tax-rate", "62.5");
await cont();
await cont();
await page.waitForSelector("[data-tax-step=review]");
await shot("16-new-4-review-rate-warning", "review at 62.5");

// back to 6.25, then save
await page.getByRole("button", { name: /^Edit Rate/ }).click();
await page.fill("#tax-rate", "6.25");
await cont();
await cont();
await page.getByRole("button", { name: "Save tax", exact: true }).click();
await page.waitForSelector("[data-tax-saved]", { timeout: 15000 }).catch(() => undefined);
await shot("17-new-5-saved", "after Save tax");
say("saved panel:", (await page.$("[data-tax-saved]")) !== null);
say((await page.innerText("main")).slice(0, 600));

await browser.close();
