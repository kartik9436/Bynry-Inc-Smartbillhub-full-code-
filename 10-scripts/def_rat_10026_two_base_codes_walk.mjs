// DEF-RAT-10026 — a service may hold two base codes for one customer class
// (PO ruling 2026-10-09, *"yes please do it"*). The walk at 1440 on a LOCAL
// stack (never the live API):
//
//   MODE=before  New charge code: Base charge · Electric · BASE-E-OUT ·
//                Residential, while BASE-E already covers Residential →
//                step 1 shows "BASE-E already covers Residential." and Continue
//                is disabled (the defect, on the pre-fix build).
//   MODE=after   the same form saves BASE-E-OUT; then New rate schedule ·
//                Electric opens the base-code picker, which shows BASE-E and
//                BASE-E-OUT each as code · name with their classes, and
//                BASE-E-OUT is picked.
//
// Setup (the walk does not do it): a seeded tenant whose electric base code
// BASE-E is scoped to Residential, and an un-configured Settings code
// BASE-E-OUT (kind and service empty) so the Add picker offers it.
//
//   BASE=http://127.0.0.1:8791 MODE=after OUT=<dir> node 10-scripts/def_rat_10026_two_base_codes_walk.mjs
//
// WRITES (MODE=after): the BASE-E-OUT charge code. Prints PASS/FAIL per check
// and FAILS if any API call leaves 127.0.0.1.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8791";
const TENANT = process.env.TENANT ?? "brazosbend";
const MODE = process.env.MODE ?? "after";
const OUT = process.env.OUT ?? "08-qa/def-rat-10026";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PW = process.env.PW ?? "S3cure!passw0rd";
const NEW_CODE = process.env.NEW_CODE ?? "BASE-E-OUT";
const HELD = process.env.HELD ?? "BASE-E";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
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
let failures = 0;
function check(name, ok, detail = "") {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const hosts = new Set();
page.on("request", (request) => {
  const url = new URL(request.url());
  if (url.pathname.startsWith("/api/")) hosts.add(url.host);
});

async function shot(name) {
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log(`=== ${name}.png — ${page.url().replace(BASE, "")}`);
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PW);
await page.click('form button[type="submit"]');
await page.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 30000 });

// ── New charge code, step 1 (skipped with MODE=picker, once BASE-E-OUT exists) ─
const continueButton = page.getByRole("button", { name: "Continue" });
if (MODE !== "picker") {
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/new`, { waitUntil: "networkidle" });
await page.selectOption("#cc-kind", "base");
await page.selectOption("#cc-service", "electric");
await page.click("#cc-code");
await page.getByRole("option", { name: new RegExp(`^${NEW_CODE} ·`) }).first().click();
await page.selectOption("#cc-class", "residential");
await page.waitForTimeout(1500);
const warning = page.getByText(`${HELD} already covers Residential.`);

if (MODE === "before") {
  check("step 1 warns that BASE-E already covers Residential", await warning.first().isVisible().catch(() => false));
  check("Continue is disabled", await continueButton.isDisabled());
  await shot("0-before-already-covers-refused");
} else {
  check("no 'already covers' warning", (await warning.count()) === 0);
  check("Continue is enabled", await continueButton.isEnabled());
  await shot("1-step1-no-warning");
  await continueButton.click();
  await page.waitForTimeout(1200);
  // Step 2 — price it flat for every size if the form asks for one amount.
  const amount = page.locator('input[inputmode="decimal"]').first();
  if (await amount.count()) await amount.fill("14.00");
  await shot("2-step2-pricing");
  await continueButton.click();
  await page.waitForTimeout(1200);
  await page.locator('input[type="date"]').first().fill(process.env.FROM ?? "2026-10-01");
  await shot("3-step3-review");
  await page.getByRole("button", { name: /^Create charge code/ }).click();
  const created = page.getByText(`${NEW_CODE} created.`);
  await created.first().waitFor({ timeout: 30000 }).catch(() => undefined);
  check(`${NEW_CODE} created beside ${HELD}`, await created.first().isVisible().catch(() => false));
  await shot("4-base-e-out-created");
}
}

if (MODE !== "before") {
  // ── New rate schedule, step 1: the base-code picker ────────────────────
  await page.goto(`${BASE}/${TENANT}/plans-rates/rates/new`, { waitUntil: "networkidle" });
  await page.selectOption("#rs-service", "electric");
  await page.waitForTimeout(800);
  await page.fill("#rs-base-code", "");
  await page.click("#rs-base-code");
  await page.waitForTimeout(600);
  const outOption = page.getByRole("option", { name: new RegExp(`^${NEW_CODE} · `) }).first();
  const heldOption = page.getByRole("option", { name: new RegExp(`^${HELD} · `) }).first();
  check("picker offers BASE-E-OUT as code · name", await outOption.isVisible().catch(() => false));
  check("picker offers BASE-E as code · name", await heldOption.isVisible().catch(() => false));
  const outText = (await outOption.textContent().catch(() => "")) ?? "";
  check("BASE-E-OUT option shows its class", outText.includes("Residential"), outText);
  await shot("5a-rate-schedule-picker-top-base-e");
  // The list holds four electric codes and shows three; scroll it so the
  // fourth, BASE-E-OUT, is in the photograph too.
  await outOption.scrollIntoViewIfNeeded();
  await shot("5b-rate-schedule-picker-scrolled-base-e-out");
  await outOption.click();
  await page.waitForTimeout(500);
  const value = await page.inputValue("#rs-base-code");
  check("BASE-E-OUT picked on the rate schedule", value.startsWith(`${NEW_CODE} · `), value);
  await shot("6-rate-schedule-picked-base-e-out");
}

const foreign = [...hosts].filter((host) => !host.startsWith("127.0.0.1"));
check("every API call stayed on 127.0.0.1", hosts.size > 0 && foreign.length === 0, [...hosts].join(", "));
await browser.close();
process.exit(failures ? 1 : 0);
