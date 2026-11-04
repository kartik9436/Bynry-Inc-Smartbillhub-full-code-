// DEF-RAT-10027 / DEF-RAT-10028 — the tax's Filing step and Settings ›
// Accounting › Tax filing accounts, walked at 1440 on a LOCAL stack (never the
// live API; every /api call is asserted to stay on 127.0.0.1).
//
//   MODE=repro  — opens Edit → Name and filing → step 2 on a tax whose every
//                 filing field is saved, and prints what each box shows.
//   MODE=fixed  — the same, plus: the Tax filing accounts section and its Add
//                 pop-up with the authority picked from the tax authorities,
//                 the Filing step with a registration number chosen, and the
//                 empty-state link opening the section directly.
//
// Setup (a scratch database; the walk does not do it): the tax named by
// TAX_ID carries code, a liability account that sorts PAST the 50th row of the
// chart, a due rule, allowance, interest and an authority account.
//
//   BASE=http://127.0.0.1:8792 TAX_ID=<uuid> OUT=<dir> MODE=fixed \
//     node 10-scripts/def_rat_10027_10028_tax_filing_walk.mjs
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8792";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "08-qa/tax-filing-2026-10-09";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const TAX_ID = process.env.TAX_ID ?? "";
const EMPTY_TAX_ID = process.env.EMPTY_TAX_ID ?? "";
const MODE = process.env.MODE ?? "fixed";
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

/** What a select SHOWS: the text of its chosen option. */
async function shown(id) {
  return page.$eval(`#${id}`, (el) => {
    const select = el;
    const option = select.options[select.selectedIndex];
    return option ? option.text : "";
  });
}
async function value(id) {
  return page.$eval(`#${id}`, (el) => el.value);
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('form button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

async function openFilingStep(taxId) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees/${taxId}/edit?change=info`, { waitUntil: "networkidle" });
  await page.locator("button").filter({ hasText: /^Continue$/ }).first().click();
  await page.waitForSelector('[data-tax-step="filing"]', { timeout: 15000 });
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
}

// 1 · Edit → Name and filing → step 2, every saved value.
await openFilingStep(TAX_ID);
const seen = {
  code: await value("tax-code"),
  liability: await shown("tax-liability"),
  due: await shown("tax-due"),
  account: await shown("tax-authority-account"),
  allowance: await value("tax-allowance"),
  interest: await value("tax-interest"),
};
console.log("STEP 2 SHOWS", JSON.stringify(seen));
check("Code shows its saved value", seen.code !== "", seen.code);
check("Liability account shows its saved account, not the placeholder", !/^Choose/.test(seen.liability), seen.liability);
check("Due shows its saved rule", !/^Choose/.test(seen.due), seen.due);
check("Registration number shows its saved row", !/^Choose/.test(seen.account), seen.account);
check("Allowance shows its saved figure", seen.allowance !== "", seen.allowance);
check("Interest shows its saved figure", seen.interest !== "", seen.interest);
await shot(MODE === "repro" ? "0-before-edit-step2-saved-values" : "4-edit-step2-all-saved-values");

if (MODE === "fixed") {
  const under = await page.locator("[data-tax-authority-account-chosen]").innerText().catch(() => "");
  check("the chosen authority and number show under the field", under.includes("·"), under);
  const side = await page.locator('[data-tax-summary-fact="registration"] dd').innerText().catch(() => "");
  check("the side panel shows the authority and number", side.includes("·"), side);
  await shot("2-filing-step-registration-number-chosen");

  // 2 · A tax whose authority holds no number: the note names it, the link opens the section.
  if (EMPTY_TAX_ID) {
    await openFilingStep(EMPTY_TAX_ID);
    const note = await page.locator("[data-tax-add-account]").innerText();
    console.log("EMPTY NOTE", note);
    check("the empty note names the authority", /Bexar/.test(note), note);
    await shot("3-filing-step-empty-names-authority");
    await page.locator("[data-tax-add-account] a").click();
    // The wizard's leave guard (PO ruling 2026-10-07) asks first, because the
    // form has been stepped forward; leaving is the clerk's choice.
    const leave = page.getByRole("button", { name: "Leave without saving" });
    if (await leave.isVisible({ timeout: 3000 }).catch(() => false)) {
      await shot("3b-leave-guard-before-tax-filing-accounts");
      await leave.click();
    }
    await page.waitForTimeout(1500);
    console.log("AFTER ADD ONE", page.url().replace(BASE, ""));
    check("Add one opens Tax filing accounts directly", page.url().includes("/settings/accounting/authorities"), page.url());
  } else {
    await page.goto(`${BASE}/${TENANT}/settings/accounting/authorities`, { waitUntil: "networkidle" });
  }
  await page.waitForLoadState("networkidle");
  const heading = await page.locator("h3.settings-frame-title").first().innerText();
  check("the section is headed Tax filing accounts", heading === "Tax filing accounts", heading);
  const kicker = await page.locator(".settings-tab").first().innerText();
  check("no GL code mapping over the section", !kicker.includes("GL code mapping"));
  await shot("1a-tax-filing-accounts-section");

  // 3 · The Add pop-up: Authority is a dropdown of the tax authorities.
  await page.getByRole("button", { name: "Add number" }).click();
  await page.waitForSelector("#authority_jurisdiction", { timeout: 10000 });
  const options = await page.$$eval("#authority_jurisdiction option", (els) => els.map((el) => el.textContent));
  console.log("AUTHORITY OPTIONS", JSON.stringify(options));
  check("Authority is picked from the tax authorities", options.includes("Bexar County"), String(options.length));
  await page.selectOption("#authority_jurisdiction", { label: "Bexar County" });
  await page.fill("#account_number", "BXR-2026-0417");
  await shot("1b-add-pop-up-authority-dropdown");
  await page.getByRole("button", { name: "Save number" }).click();
  await page.waitForTimeout(1200);
  const table = await page.locator("table.settings-table").innerText();
  check("the new number is listed under its authority", table.includes("Bexar County") && table.includes("BXR-2026-0417"));
  await shot("1c-tax-filing-accounts-after-add");
}

check("every API call stayed on 127.0.0.1", [...hosts].every((h) => h.startsWith("127.0.0.1")), [...hosts].join(","));
await browser.close();
console.log(failures === 0 ? "ALL PASS" : `${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
