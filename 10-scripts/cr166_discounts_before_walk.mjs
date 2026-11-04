// ── Trace ──────────────────────────────────────────────
// Change:  CR-166-BRC10 — Plans & Rates › Discounts redesign, round 1 task 2:
//          REPRODUCE every problem the PO-approved mock-up lists (D1–D38, the
//          mock-up's `FIX` arrays wiz · list · detail · edit, in that order) on
//          TODAY's screen before anything is fixed (maintenance process,
//          `12-governance/22-product-maintenance-process.md`, step REPRODUCE).
//          Shape copied from `cr165_taxes_fees_before_walk.mjs` (taxes, same round).
// ───────────────────────────────────────────────────────
//
// It changes no product code. It photographs today's discounts list, the New
// discount wizard (every step), the details page (each tab, each status) and
// both edit doors at 1440 wide, and prints the text it read beside each
// photograph so the CR's table can quote what was on screen. It also probes,
// through the signed-in browser session, the server facts behind lifecycle
// ruling (b) and (c) that a screen can show (the Enrolled tile, the HTTP door
// that enrols an account).
//
// Expects:
//   * the API — `manage.py runserver 127.0.0.1:8591` on a scratch PostgreSQL 16
//     database with `migrate` + `seed_demo` + `load_sample_data --tenant
//     brazosbend` run (Brazos Bend, Dana — the sample block is what seeds the
//     six discounts, 75 units on Sample — Residential and the accounts);
//   * the SPA — `vite build --mode wolocal` then
//     `PORT=8592 API_PROXY_TARGET=http://127.0.0.1:8591 node 07-frontend/server.mjs`.
//
//   OUT=08-qa/discounts-2026-10-03/before node 10-scripts/cr166_discounts_before_walk.mjs
//
// ⚠ A native <select>'s open list is drawn by the browser, not the page, so a
// headless photograph cannot show it. Where a problem is ABOUT a list's choices
// the walk prints the options instead.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8592";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr166-before";
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
// Tall viewport on purpose: the app frame scrolls its OWN main column, so a
// "full page" photo of a 1000-high window stops at the fold.
const page = await browser.newPage({ viewport: { width: 1440, height: 2400 } });
const say = (...parts) => console.log(...parts);
const settle = () => page.waitForTimeout(900);
async function shot(name, caption, { full = true } = {}) {
  await settle();
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full });
  say(`\n=== ${name}.png — ${caption}`);
}
async function mainText() {
  return (await page.innerText("main")).replace(/\n{2,}/g, "\n");
}
async function api(method, path, body) {
  return page.evaluate(
    async ([m, p, b]) => {
      const res = await fetch(`/api/${p}`, {
        method: m,
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: b === undefined ? undefined : JSON.stringify(b),
      });
      let data = null;
      try {
        data = await res.json();
      } catch {
        data = null;
      }
      return { status: res.status, data };
    },
    [method, `${TENANT}/${path}`, body],
  );
}
async function controlKind(id) {
  return page
    .$eval(`#${id}`, (el) => `${el.tagName.toLowerCase()}${el.type ? `[type=${el.type}]` : ""}`)
    .catch(() => "(absent)");
}
async function optionsOf(id) {
  return page.$$eval(`#${id} option`, (os) => os.map((o) => o.textContent.trim())).catch(() => []);
}
async function buttons() {
  return page.$$eval("main button", (bs) =>
    bs
      .map((b) => {
        const label = (b.textContent.trim() || b.getAttribute("aria-label") || b.getAttribute("title") || "").replace(/\s+/g, " ");
        return `${label}${b.hasAttribute("disabled") ? " [DISABLED]" : ""}`;
      })
      .filter(Boolean),
  );
}
async function pressContinue() {
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.waitForTimeout(700);
}

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

const listed = await api("GET", "discounts?per=100");
const rows = listed.data?.results ?? [];
say("DISCOUNTS SERVED:", rows.length, JSON.stringify(rows.map((r) => [r.code, r.status, r.value_display, r.enrolled])));
const byCode = Object.fromEntries(rows.map((r) => [r.code, r]));

// ── 1 · THE LIST (D14–D18) ──────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("l01-list", "list as it opens (D14–D18)");
say(await mainText());
say("LIST COLUMNS:", JSON.stringify(await page.$$eval("main th", (ths) => ths.map((th) => th.textContent.trim()))));
say(
  "ROW ACTION CONTROLS:",
  JSON.stringify(
    await page.$$eval("main tbody tr", (trs) =>
      trs.slice(0, 3).map((tr) =>
        [...tr.querySelectorAll("button, a")].map((b) => b.getAttribute("aria-label") || b.getAttribute("title") || b.textContent.trim()),
      ),
    ),
  ),
);
say("TOOLBAR BUTTONS:", JSON.stringify(await buttons()));

// ── 2 · NEW DISCOUNT — every step (D1–D13) ──────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
await page.waitForSelector("#discount-code", { timeout: 30000 });
await shot("w01-step1-basics", "step 1 as it opens (D1 D2 D8 D10 D13)");
say(await mainText());
for (const id of ["discount-code", "discount-name", "discount-owner", "discount-funding", "discount-assistance-filing", "discount-type"]) {
  say(`  #${id}:`, await controlKind(id));
}
say("  type options:", JSON.stringify(await optionsOf("discount-type")));
await page.fill("#discount-code", "walkpct");
await page.fill("#discount-name", "Walk senior discount");
await page.fill("#discount-owner", "Customer service").catch(() => {});
await page.fill("#discount-funding", "Rate-payer funded").catch(() => {});
await pressContinue();

await page.waitForSelector("#discount-value", { timeout: 15000 });
await shot("w02-step2-value", "step 2 Value as it opens (D3 D4 D5 D6 D12)");
say(await mainText());
for (const id of ["discount-value", "discount-currency", "discount-scope", "discount-cap-per-bill", "discount-cap-per-year", "discount-cap-lifetime", "discount-floor", "discount-precedence", "discount-stacks", "discount-exclusivity"]) {
  say(`  #${id}:`, await controlKind(id));
}
say("  currency value:", await page.$eval("#discount-currency", (el) => el.value).catch(() => "(absent)"));
say("  scope options:", JSON.stringify(await optionsOf("discount-scope")));
await page.fill("#discount-value", "15");
await page.fill("#discount-currency", "usd").catch(() => {});
await settle();
await shot("w03-step2-filled", "step 2 filled: 15, currency typed by hand");
await pressContinue();

await page.waitForSelector("#discount-enrolment", { timeout: 15000 });
await shot("w04-step3-eligibility", "step 3 Eligibility as it opens (D7 D10 D11)");
say(await mainText());
for (const id of ["discount-eligibility-summary", "discount-enrolment", "discount-verification", "discount-recert-months", "discount-recert-notice", "discount-recert-grace", "discount-lapse", "discount-proof-before"]) {
  say(`  #${id}:`, await controlKind(id));
}
say("  enrolment options:", JSON.stringify(await optionsOf("discount-enrolment")));
await page.fill("#discount-eligibility-summary", "Age 65 or over").catch(() => {});
await pressContinue();

await page.waitForSelector("#discount-effective-from", { timeout: 15000 });
await shot("w05-step4-effective", "step 4 Effective & approval as it opens (D1 D10)");
say(await mainText());
for (const id of ["discount-effective-from", "discount-effective-to", "discount-budget-cap", "discount-budget-period", "discount-exhaustion"]) {
  say(`  #${id}:`, await controlKind(id));
}
await page.fill("#discount-effective-from", "2026-11-01").catch(() => {});
await pressContinue();

await page.waitForTimeout(1200);
await shot("w06-step5-review", "step 5 Review (D9)");
say(await mainText());
const reviewButtons = await buttons();
say("REVIEW BUTTONS:", JSON.stringify(reviewButtons));
const saveLabel = reviewButtons.map((b) => b.replace(" [DISABLED]", "")).find((b) => /^(Save|Create)/i.test(b) && !/exit/i.test(b));
say("pressing:", saveLabel);
if (saveLabel) {
  await page.getByRole("button", { name: saveLabel, exact: true }).first().click();
  await page.waitForTimeout(2500);
}
say("SAVED ->", page.url());
await shot("w07-after-save", "after saving the new discount");
say(await mainText());
const after = await api("GET", "discounts?per=100");
const walkRow = (after.data?.results ?? []).find((r) => r.code?.toUpperCase() === "WALKPCT");
say("WALK DISCOUNT stored as:", JSON.stringify(walkRow ? { code: walkRow.code, status: walkRow.status, currency: walkRow.currency, value: walkRow.value_display } : null));

// ── 3 · DETAILS of the live AUTOPAY discount (D19–D34) ──────────────────────
const autopay = byCode.AUTOPAY;
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${autopay.id}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("d01-autopay-overview", "details · AUTOPAY (Active, Automatic, on Sample — Residential) · Overview (D19–D28 D30 D33 D34)");
say(await mainText());
say("DETAIL BUTTONS:", JSON.stringify(await buttons()));
say("TABS:", JSON.stringify(await page.$$eval("[role='tab']", (ts) => ts.map((t) => t.textContent.trim()))));
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${autopay.id}?tab=plans`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
await shot("d02-autopay-plans", "details · AUTOPAY · Plans tab (D23 D29)");
say(await mainText());
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${autopay.id}?tab=audit`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
await shot("d03-autopay-audit", "details · AUTOPAY · Audit tab (D23 D31 D32)");
say(await mainText());

// CAP — the fixed-amount one ($25.00 off), for money without $.
const cap = byCode.CAP;
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${cap.id}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("d04-cap-overview", "details · CAP (fixed amount, budget) · Overview (D27)");
say(await mainText());

// MUNICIPAL — the one discount the sample data enrols somebody in.
const muni = byCode.MUNICIPAL;
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${muni.id}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("d05-municipal-overview", "details · MUNICIPAL (1 enrolled) · Overview — nowhere names the account (D30)");
say(await mainText());

// MILITARY — a draft.
const military = byCode.MILITARY;
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${military.id}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("d06-military-draft", "details · MILITARY (Draft) · buttons on a draft (D22)");
say(await mainText());
say("DRAFT DETAIL BUTTONS:", JSON.stringify(await buttons()));

// The walk's own new discount, if it saved.
if (walkRow) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${walkRow.id}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot("d07-walk-draft", "details · the walk's new discount right after saving (D33)");
  say(await mainText());
  say("NEW DRAFT DETAIL BUTTONS:", JSON.stringify(await buttons()));
}

// ── 4 · EDIT on a live discount (D35–D38) ───────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${autopay.id}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
say("LIVE DETAIL BUTTONS (edit doors):", JSON.stringify(await buttons()));
await page.getByRole("button", { name: "Edit", exact: true }).first().click();
await page.waitForTimeout(1800);
say("EDIT OPENS ->", page.url());
await shot("e01-edit-opens", "Edit pressed on live AUTOPAY — step 1 (D35)");
say(await mainText());
await pressContinue();
await page.waitForSelector("#discount-value", { timeout: 15000 });
const valueDisabled = await page.$eval("#discount-value", (el) => el.disabled);
say("EDIT step 2: value disabled =", valueDisabled, "· value =", await page.$eval("#discount-value", (el) => el.value));
await page.fill("#discount-value", "0.75").catch(() => {});
await shot("e02-edit-value", "Edit · step 2 on a live discount: value editable (D36)");
say(await mainText());
await pressContinue();
await pressContinue();
await page.waitForSelector("#discount-effective-from", { timeout: 15000 }).catch(() => {});
say(
  "EDIT step 4: effective_from =",
  await page.$eval("#discount-effective-from", (el) => `${el.value} disabled=${el.disabled}`).catch(() => "(absent)"),
  "· effective_to =",
  await page.$eval("#discount-effective-to", (el) => `${el.value} disabled=${el.disabled}`).catch(() => "(absent)"),
);
await shot("e03-edit-dates", "Edit · dates step of a new version: the OLD start pre-filled, nothing about the old version's end (D37)");
say(await mainText());
// A new value from 11/01/2026, with the reason the step demands — then Review.
await page.fill("#discount-effective-from", "2026-11-01");
await page.fill("#discount-change-reason", "Walk: autopay discount rises from November.");
await pressContinue();
await page.waitForTimeout(1200);
await shot("e04-edit-review", "Edit · review of the new version: fields only, no old → new, no bill example (D37 D38)");
say(await mainText());
say("EDIT REVIEW BUTTONS:", JSON.stringify(await buttons()));

// "Fix this version" — the second door.
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${autopay.id}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const fix = page.getByRole("button", { name: "Fix this version", exact: true });
if (await fix.count()) {
  await fix.first().click();
  await page.waitForTimeout(1800);
  say("FIX OPENS ->", page.url());
  await shot("e05-fix-opens", "Fix this version pressed on live AUTOPAY (D35)");
  say(await mainText());
  await pressContinue();
  await page.waitForSelector("#discount-value", { timeout: 15000 });
  await page.fill("#discount-value", "0.05");
  await shot("e06-fix-value", "Fix this version · step 2: value typed over, no reason asked yet (D38)");
  await pressContinue();
  await pressContinue();
  await page.fill("#discount-change-reason", "Walk: value typed as 0.50 meant 0.05.").catch(() => {});
  await shot("e07-fix-dates", "Fix this version · dates step: dates locked, reason asked here");
  say(await mainText());
  await pressContinue();
  await page.waitForTimeout(1200);
  await shot("e08-fix-review", "Fix this version · review: no before → after, no bill example (D38)");
  say(await mainText());
  say("FIX REVIEW BUTTONS:", JSON.stringify(await buttons()));
} else {
  say("FIX THIS VERSION: no such button on the live detail");
}

// ── 4b · NEW DISCOUNT with a FIXED amount — how is the currency entered? (D4)
await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
await page.waitForSelector("#discount-type", { timeout: 30000 });
await page.fill("#discount-code", "walkfix");
await page.fill("#discount-name", "Walk fixed credit");
await page.selectOption("#discount-type", { label: "Fixed amount — A flat sum off." });
await pressContinue();
await page.waitForSelector("#discount-value", { timeout: 15000 });
say("FIXED step 2: #discount-currency =", await controlKind("discount-currency"),
  "· value =", await page.$eval("#discount-currency", (el) => el.value).catch(() => "(absent)"),
  "· maxlength =", await page.$eval("#discount-currency", (el) => el.getAttribute("maxlength")).catch(() => "(absent)"));
await page.fill("#discount-value", "25");
await shot("w08-fixed-step2-currency", "step 2 of a FIXED amount: currency is a three-letter text box (D3 D4)");
say(await mainText());
await page.fill("#discount-currency", "CAD").catch(() => {});
await settle();
say("FIXED step 2 after typing CAD into the currency box:", await page.$eval("#discount-currency", (el) => el.value).catch(() => "(absent)"));
await shot("w09-fixed-currency-cad", "currency box accepts another utility's currency, typed by hand (D4)");

// ── 5 · server facts behind lifecycle rulings (b) and (c) a screen can show ─
// (c) AUTOPAY is Automatic and offered on a plan with 75 units — how many are enrolled?
const autopayDetail = await api("GET", `discounts/${autopay.id}`);
say(
  "AUTOPAY detail facts:",
  JSON.stringify({
    enrolment_mode: autopayDetail.data?.enrolment_mode ?? autopayDetail.data?.version?.enrolment_mode,
    enrolled: autopayDetail.data?.enrolled,
    offered_units: autopayDetail.data?.offered_units ?? autopayDetail.data?.offered_unit_count,
    plans: autopayDetail.data?.plans,
  }),
);
say("AUTOPAY detail keys:", Object.keys(autopayDetail.data ?? {}).join(","));

// (b) the ONE HTTP door that enrols an account: POST /accounts/{id}/discounts.
const accounts = await api("GET", "accounts?per=5");
const anAccount = (accounts.data?.results ?? [])[0];
say("probe account:", anAccount?.account_no, anAccount?.id);
const senior = byCode.SENIOR;
const claim = await api("POST", `accounts/${anAccount.id}/discounts`, { programme_id: senior.id });
say("POST /accounts/{id}/discounts {programme_id: SENIOR}:", claim.status, JSON.stringify(claim.data).slice(0, 400));

await browser.close();
