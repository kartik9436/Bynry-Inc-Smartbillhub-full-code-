// DEF-RAT-9792 + DEF-CUS-9780 walkthrough (2026-10-06) — run AFTER the CR-171 matrix M3 case
// (Harold Whitfield claims CAP and uploads cap-award-letter.pdf as Assistance evidence).
//
//   W_BASE=http://127.0.0.1:5792 W_TENANT=mvimatrix W_OUT=<folder> \
//   W_CAP=<CAP id> W_AUTOPAY=<AUTOPAY id> W_ACCOUNT=<Harold's account id> \
//   node 10-scripts/def_rat_9792_cus_9780_walkthrough.mjs
//
// At 1440, signed in as Marcus Lee (System Admin) and then Jo Ramirez (Billing Clerk):
//   1. AUTOPAY's Accounts tab draws no "+ Enroll an account" (DEF-RAT-9792);
//   2. CAP's Accounts tab still draws it;
//   3. POST /accounts/{Harold}/discounts with AUTOPAY answers 422 "This discount is applied automatically.";
//   4. CAP's Accounts tab shows Harold Proof pending with a "View proof" eye (System Admin), and the
//      eye opens the letter through the account document's content route (DEF-CUS-9780);
//   5. the clerk sees the row and no eye (BR-RAT-079).
//
// ⚖️ AMENDED 2026-10-06 (DEF-RAT-9833, PO D2 (b): "clark can add it later also on account"):
// Autopay is now addable by hand, so steps 1 and 3 are walked on MUNICIPAL (automatic, no person may
// add it) — pass its id as W_MUNICIPAL. Autopay's own door is 10-scripts/def_rat_9833_walkthrough.mjs.
// Prints PASS/FAIL per check; exits 1 on any FAIL.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");
const BASE = process.env.W_BASE ?? "http://127.0.0.1:5792";
const TENANT = process.env.W_TENANT ?? "mvimatrix";
const OUT = process.env.W_OUT ?? "/tmp/walk";
const CAP = process.env.W_CAP;
const AUTOPAY = process.env.W_MUNICIPAL ?? process.env.W_AUTOPAY;
const ACCOUNT = process.env.W_ACCOUNT;
const PASSWORD = "S3cure!passw0rd"; // the matrix world's lane fixture credential
mkdirSync(OUT, { recursive: true });
let fails = 0;
const check = (ok, name, detail = "") => {
  if (!ok) fails += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? " — " + detail : ""}`);
};

async function signIn(context, email) {
  const page = await context.newPage();
  page.setDefaultTimeout(25000);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);
  return page;
}
async function accountsTab(page, id) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${id}?tab=accounts`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-discount-accounts]");
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(500);
}

const browser = await chromium.launch({ executablePath: process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const admin = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await signIn(admin, "marcus@cedarford.example");

await accountsTab(page, AUTOPAY);
check((await page.locator("[data-discount-enroll]").count()) === 0, "Municipal account (automatic) draws no + Enroll an account");
await page.screenshot({ path: join(OUT, "1-autopay-accounts-no-enroll.png"), fullPage: true });

await accountsTab(page, CAP);
check((await page.locator("[data-discount-enroll]").count()) === 1, "CAP (a person applies) still draws + Enroll an account");
const eye = page.getByRole("button", { name: /View proof for AC-/ });
check((await eye.count()) === 1, "Harold's Proof pending row carries View proof (System Admin)");
check((await page.locator("[data-discount-accounts]").textContent()).includes("Proof pending"), "Harold still reads Proof pending — not verified");
await page.screenshot({ path: join(OUT, "2-cap-accounts-view-proof.png"), fullPage: true });

const refused = await page.evaluate(
  async ({ tenant, account, programme }) => {
    const res = await fetch(`/api/${tenant}/accounts/${account}/discounts`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ?? "" },
      body: JSON.stringify({ programme_id: programme }),
    });
    return { status: res.status, body: await res.json().catch(() => null) };
  },
  { tenant: TENANT, account: ACCOUNT, programme: AUTOPAY },
);
const key = refused.body?.field_errors?.[0]?.message_key ?? refused.body?.message_key;
check(refused.status === 422 && key === "customers.moveIn.discountAutomatic", "the account door refuses Municipal account by name", `${refused.status} ${key}`);

const [popup] = await Promise.all([page.waitForEvent("popup"), eye.click()]);
await popup.waitForLoadState("load").catch(() => undefined);
check(/\/accounts\/[^/]+\/documents\/[^/]+\/content\?as=view/.test(popup.url()), "the eye opens the account document's content route", popup.url().replace(BASE, ""));
// Headless Chromium draws a PDF as an empty viewer frame, so the bytes are asked for directly too.
const served = await admin.request.get(popup.url());
const body = await served.body();
check(
  served.status() === 200 && (served.headers()["content-type"] ?? "").startsWith("application/pdf") && body.subarray(0, 5).toString() === "%PDF-",
  "the letter itself is served",
  `${served.status()} ${served.headers()["content-type"]} ${body.length} bytes`,
);
await popup.setViewportSize({ width: 1440, height: 900 });
await popup.waitForTimeout(800);
await popup.screenshot({ path: join(OUT, "3-proof-opened.png") });
await admin.close();

const clerk = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const cpage = await signIn(clerk, "jo.ramirez@cedarford.example");
await accountsTab(cpage, CAP);
check((await cpage.getByRole("button", { name: /View proof for AC-/ }).count()) === 0, "a Billing Clerk sees the row and no proof (BR-RAT-079)");
await cpage.screenshot({ path: join(OUT, "4-cap-accounts-clerk.png"), fullPage: true });
await browser.close();
console.log(`  ${fails === 0 ? "ALL PASS" : fails + " FAIL"}`);
process.exit(fails === 0 ? 0 : 1);
