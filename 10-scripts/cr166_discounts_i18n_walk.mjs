// ── Trace ──────────────────────────────────────────────
// Change:  CR-166-BRC10 round 3 task 8 — the four discount screens photographed
//          in all eleven languages at 1440 wide (DEF-RAT-9316).
// ───────────────────────────────────────────────────────
//
// Expects the API on a scratch PostgreSQL 16 database prepared with `migrate`
// + `seed_demo` + `load_sample_data --tenant brazosbend` +
// `10-scripts/cr166_discount_detail_walk_prep.py` (AUTOPAY live with a new value
// from next year and five accounts enrolled), and the SPA from
// `vite build --mode wolocal` served by `07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:5196 OUT=08-qa/discounts-2026-10-03/i18n \
//     node 10-scripts/cr166_discounts_i18n_walk.mjs
//
// Each screen is driven in English (so the walk can find its boxes by their
// labels), then switched to the language and photographed: list, New step 1
// (code, label and 15% typed), details Overview and Accounts (AUTOPAY), and
// Edit › New value from a date › Review (16% from 03/01/2027). Each photograph
// is checked not blank, and the screen's own text is searched for English
// words that are catalogue text; every hit is printed so a person can judge it
// (a discount's name is the utility's data and stays English).
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5196";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr166-i18n";
const LANGS = (process.env.LANGS ?? "en,de,es,es-MX,fr-FR,hi,id-ID,it-IT,ja-JP,ko-KR,pt-BR").split(",");
mkdirSync(OUT, { recursive: true });

// English words that are catalogue text on these four screens. A hit in a
// non-English photograph is printed, never silently passed.
const PROBES = [
  "Overview", "Accounts", "Audit", "Enrolled", "Receiving", "Offered to", "Granted", "units on its plans",
  "this month", "Version", "No end", "Retire", "Approve", "Send back", "Duplicate", "Details", "Eligibility",
  "Review", "Continue", "Cancel", "Search", "Filter", "Status", "Value", "Verification", "Code", "Discount",
  "What changes", "How it is saved", "Before", "After", "Percent off", "Bill line label", "Program owner",
  "Who qualifies", "Starts", "Ends", "Limits", "This discount", "off subtotal", "Renew by", "Customer",
  "Enroll", "New value", "Save", "Edit", "Plans", "Type", "From", "Active", "Draft", "Scheduled",
];

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
const page = await browser.newPage({ viewport: { width: 1440, height: 1700 } });
const setLang = async (code) => {
  await page.evaluate((c) => window.__SMARTBILLHUB_I18N__?.changeLanguage(c), code);
  await page.waitForTimeout(700);
};
const go = async (path) => {
  await page.goto(`${BASE}/${TENANT}/${path}`, { waitUntil: "networkidle" });
  await setLang("en");
};

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

const listJson = await page.evaluate(async (t) => {
  const res = await fetch(`/api/${t}/discounts?q=AUTOPAY`, { credentials: "include" });
  return res.json();
}, TENANT);
const autopay = (listJson.results ?? listJson.items ?? listJson).find((row) => row.code === "AUTOPAY");
if (!autopay) throw new Error("AUTOPAY not found — run cr166_discount_detail_walk_prep.py first");

async function shot(name, lang) {
  await setLang(lang);
  await page.waitForTimeout(600);
  const file = `${OUT}/${name}-${lang}.png`;
  await page.screenshot({ path: file, fullPage: true });
  const text = (await page.locator("main").innerText()).trim();
  if (text.length < 80) throw new Error(`${name}-${lang}: the screen is blank (${text.length} characters)`);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  const hits = lang === "en" ? [] : PROBES.filter((word) => new RegExp(`(^|[^A-Za-z])${word}([^A-Za-z]|$)`).test(text));
  console.log(`${name}-${lang}: ${text.length} chars, sideways overflow ${overflow}px, English probes: ${hits.join(", ") || "none"}`);
}

for (const lang of LANGS) {
  await go("plans-rates/discounts");
  await page.getByRole("table").waitFor();
  await shot("list", lang);

  await go("plans-rates/discounts/new");
  await page.getByLabel(/^Code/).fill("SENIOR");
  await page.getByLabel(/^Bill line label/).fill("Senior discount");
  await page.getByRole("textbox", { name: /^Percent off/ }).fill("15");
  await shot("new", lang);

  await go(`plans-rates/discounts/${autopay.id}`);
  await page.locator("[data-discount-overview]").waitFor();
  await shot("detail-overview", lang);

  await go(`plans-rates/discounts/${autopay.id}`);
  await page.getByRole("tab").nth(1).click();
  await page.waitForLoadState("networkidle");
  await shot("detail-accounts", lang);

  await go(`plans-rates/discounts/${autopay.id}/edit?change=change`);
  await page.getByRole("textbox", { name: /^Percent off/ }).fill("16");
  await page.getByLabel(/^New value starts/).fill("2027-03-01");
  // The Ends box carries today's version's end; a new value after it has none.
  await page.getByLabel(/^Ends/).fill("");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.waitForTimeout(500);
  await shot("edit-review", lang);
}

await browser.close();
