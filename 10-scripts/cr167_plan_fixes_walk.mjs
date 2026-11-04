// ── Trace ──────────────────────────────────────────────
// Change:  CR-167-BRC10 follow-up (lane PLAN-FIXES, 2026-10-03) — walk the
//          plan fixes in a real browser at 1440 on PostgreSQL 16 and
//          photograph each one.
// Defects: DEF-RAT-9352 (Duplicate) · DEF-RAT-9364 (publish a saved new
//          version) · DEF-RAT-9365 (What changes money) · DEF-RAT-9360 /
//          9363 (Audit words) · DEF-RAT-9361 (Vacant) · DEF-RAT-9285 /
//          9286 / 9287 / 9329 (verified on the new screens)
// ───────────────────────────────────────────────────────
//
// Expects the API on PostgreSQL (`migrate` + `seed_demo` + `load_sample_data
// --tenant brazosbend`) and the SPA built `--mode wolocal`, served by
// `PORT=<p> API_PROXY_TARGET=http://127.0.0.1:<api> node 07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:5351 RES=<SCW-RES id> COM=<SCW-COM id> \
//     OUT=08-qa/plans-2026-10-03/fixes node 10-scripts/cr167_plan_fixes_walk.mjs
//
// It WRITES: a copy of RES (then edited as a draft), a saved v2 of COM that is
// then published from the details page, a correction of COM's v1 and a
// Name-and-details edit. Run it on a fresh database.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5351";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr167-fixes";
const RES = process.env.RES;
const COM = process.env.COM;
if (!RES || !COM) throw new Error("RES=<plan id> COM=<plan id> are required");
mkdirSync(OUT, { recursive: true });

const say = (line) => console.log(line);
const checks = [];
function check(name, ok, detail = "") {
  checks.push([name, ok]);
  say(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
}
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
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on("pageerror", (error) => say(`PAGE ERROR ${error.message}`));
page.on("response", (response) => {
  const url = response.url();
  if (/\/plans/.test(url) && response.request().method() !== "GET") {
    say(`  ${response.request().method()} ${url.replace(/^.*\/api\/v1/, "")} → ${response.status()}`);
  }
});

async function shot(name, caption) {
  await page.waitForTimeout(700);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(200);
  const height = await page.evaluate(() => {
    const scroller = [...document.querySelectorAll("main, main *")].find(
      (el) => el.scrollHeight > el.clientHeight + 4 && getComputedStyle(el).overflowY !== "visible",
    );
    const main = document.querySelector("main");
    const top = main ? main.getBoundingClientRect().top : 0;
    return Math.ceil(Math.max(900, (scroller ?? main ?? document.body).scrollHeight + top + 40));
  });
  await page.setViewportSize({ width: 1440, height });
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  say(`=== ${name}.png — ${caption}`);
}
const click = (name) => page.getByRole("button", { name, exact: true }).click();
const plan = (id, query = "") => page.goto(`${BASE}/${TENANT}/plans-rates/plans/${id}${query}`, { waitUntil: "networkidle" });
const edit = (id, query) => page.goto(`${BASE}/${TENANT}/plans-rates/plans/${id}/edit${query}`, { waitUntil: "networkidle" });
const flat = async (locator) => (await locator.innerText()).replace(/\s+/g, " ").trim();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.getByRole("button", { name: /sign in/i }).click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// `COPY=<id>` re-photographs an existing copy's overview (read-only) and stops.
if (process.env.COPY) {
  await plan(process.env.COPY);
  await page.getByRole("heading", { level: 1 }).waitFor();
  await page.waitForTimeout(1000);
  check("9506 a draft plan offers no Publish v1 banner", (await page.getByTestId("plan-draft-version").count()) === 0);
  await shot("9352-duplicate-copy-overview", "The copy — a draft, its own name and code, Units 0");
  await browser.close();
  process.exit(0);
}
// `LANG_ONLY=1` — DEF-RAT-9507/9508/9509 on COM's Services tab (read-only):
// sizes smallest first, the Rate column and the service heading, en and ja-JP.
if (process.env.LANG_ONLY === "1") {
  await plan(COM, "?tab=services");
  await page.getByText(/Expand all/).first().click().catch(() => undefined);
  await page.waitForTimeout(1200);
  const all = await flat(page.locator("main"));
  const at = (label) => all.indexOf(label);
  check("9507 the smallest water size comes first", at('Water 5/8"') > -1 && at('Water 5/8"') < at('Water 3/4"') && at('Water 3/4"') < at('Water 1"'), `5/8 at ${at('Water 5/8"')}, 3/4 at ${at('Water 3/4"')}, 1 at ${at('Water 1"')}`);
  await shot("9507-services-sizes-en", "Services · base charges by meter size, smallest first (en)");
  await page.evaluate(() => window.__SMARTBILLHUB_I18N__?.changeLanguage("ja-JP"));
  await page.waitForTimeout(1200);
  const main = await flat(page.locator("main"));
  check("9508 ja-JP Rate column reads 単価, not 税率", main.includes("単価") && !main.includes("税率"));
  // The size NAMES ("Water 5/8\"") are the utility's own data; the heading is ours.
  const headings = (await page.locator('[data-plan-section="service"] h2, [data-plan-section="service"] h3').allInnerTexts()).map((h) => h.trim());
  check("9509 ja-JP headings read 電気 / 水, not Electric / Water", headings.some((h) => h.includes("水")) && !headings.some((h) => /Water|Electric/.test(h)), JSON.stringify(headings));
  await shot("9509-services-ja-JP", "Services in Japanese — 水 / 電気, 単価, sizes smallest first");
  await page.evaluate(() => window.__SMARTBILLHUB_I18N__?.changeLanguage("en"));
  say(`\n${checks.filter(([, ok]) => ok).length}/${checks.length} checks PASS`);
  await browser.close();
  process.exit(0);
}
// `AUDIT_ONLY=1` re-reads the Audit section (read-only) after a full run.
const AUDIT_ONLY = process.env.AUDIT_ONLY === "1";
if (!AUDIT_ONLY) {
// ── DEF-RAT-9361 · Vacant lists only vacant rows ────────────────────────────
await plan(RES, "?tab=units");
await page.getByRole("button", { name: "Vacant", exact: true }).click();
await page.waitForTimeout(1500);
const vacantRows = await page.locator("main table tbody tr").allInnerTexts();
const apt = vacantRows.find((row) => row.includes("Apt 102")) ?? "";
check("9361 Apt 102 under Vacant reads Vacant", apt.includes("Vacant") && !apt.includes("Occupied"), apt.replace(/\s+/g, " "));
check("9361 no row under Vacant reads Occupied", vacantRows.every((row) => !row.includes("Occupied")), `${vacantRows.length} rows`);
await shot("9361-units-vacant", "Units · Vacant — Apt 102 (closed account AC-2026-00042) reads Vacant");
await page.getByRole("button", { name: "Occupied", exact: true }).click();
await page.waitForTimeout(1500);
const occupiedRows = await page.locator("main table tbody tr").allInnerTexts();
check("9361 Apt 102 not under Occupied", occupiedRows.every((row) => !row.includes("Apt 102")), `${occupiedRows.length} rows`);
check("9361 no row under Occupied reads Vacant", occupiedRows.every((row) => !/\bVacant\b/.test(row)));
await shot("9361-units-occupied", "Units · Occupied");

// ── DEF-RAT-9352 · Duplicate ────────────────────────────────────────────────
await plan(RES);
await page.getByRole("heading", { level: 1 }).waitFor();
await page.locator("[data-plan-more] summary").click();
await shot("25-more-open", "More ▾ open — Duplicate live (image 25)");
await page.getByTestId("plan-more-duplicate").click();
await page.getByRole("dialog").waitFor();
await click("Duplicate");
await page.waitForTimeout(500);
await shot("9352-duplicate-refused", "Duplicate · empty name and code refused by name");
await page.getByRole("dialog").getByLabel(/^Plan name/).fill("Sample — Residential 2027");
await page.getByRole("dialog").getByLabel(/^Code/).fill("SCW-RES");
await click("Duplicate");
await page.waitForTimeout(1500);
await shot("9352-duplicate-code-taken", "Duplicate · a code in use refused by the server, under the box");
await page.getByRole("dialog").getByLabel(/^Code/).fill("SCW-RES-27");
await click("Duplicate");
await page.waitForURL((u) => !u.pathname.endsWith(RES), { timeout: 15000 });
await page.getByRole("heading", { level: 1 }).waitFor();
await page.waitForTimeout(1000);
const copyId = page.url().split("/plans/")[1].split(/[?/]/)[0];
const header = await flat(page.locator("[data-plan-detail]"));
check("9352 the copy opens as a draft", /Sample — Residential 2027/.test(header) && /Draft/i.test(header), copyId);
check("9506 a draft plan offers no Publish v1 banner", (await page.getByTestId("plan-draft-version").count()) === 0);
await shot("9352-duplicate-copy-overview", "The copy — a draft, its own name and code, Units 0");
await plan(copyId, "?tab=services");
await page.waitForTimeout(1200);
await shot("9352-duplicate-copy-services", "The copy · Services — the source's schedules as of today");
await plan(copyId, "?tab=charges");
await page.waitForTimeout(1200);
await shot("9352-duplicate-copy-charges", "The copy · Charges — its charge codes and taxes");

// ── DEF-RAT-9285 / 9287 / 9286 · a draft edited, then reopened ─────────────
await edit(copyId, "");
await page.getByLabel(/^Plan name/).waitFor();
await click("+ Add note");
await page.getByRole("combobox", { name: "Attribute" }).last().selectOption({ label: "Customer class" });
await page.getByRole("combobox", { name: "Operator" }).last().selectOption({ index: 1 });
await page.getByRole("combobox", { name: "Value" }).last().selectOption({ label: "Residential" });
await click("Continue");
await click("Continue");
await click("Continue");
await page.getByLabel(/^Minimum bill/).fill("10.00");
await click("Continue");
await page.waitForTimeout(1000);
await shot("9286-draft-review", "The copy · Review — the panel's counts beside the sections they count");
await click("Save as draft");
await page.waitForTimeout(1500);
await edit(copyId, "");
await page.getByLabel(/^Plan name/).waitFor();
const noteValue = await page.getByRole("combobox", { name: "Value" }).last().evaluate((el) => el.options[el.selectedIndex]?.text ?? "");
check("9285 the note's class reads by name on reopen", noteValue === "Residential", noteValue);
await shot("9285-draft-details-note", "Edit (draft) · step 1 — note *Customer class is Residential*, by name");
await edit(copyId, "?step=4");
await page.getByLabel(/^Minimum bill/).waitFor();
const minimum = await page.getByLabel(/^Minimum bill/).inputValue();
check("9287 the minimum bill box reads 10.00", minimum === "10.00", minimum);
await shot("9287-draft-billing-minimum", "Edit (draft) · Billing — Minimum bill 10.00, two places");

// ── DEF-RAT-9329 · Taxes on the Charges step ────────────────────────────────
await edit(RES, "?change=change&step=2");
await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
await page.waitForTimeout(800);
const charges = await flat(page.locator("main"));
check("9329 no 'No authority recorded' row", !charges.includes("No authority recorded"));
await shot("9329-charges-taxes", "Change from a date · Charges — Taxes are taxes, one row each");

// ── DEF-RAT-9365 · What changes reads $ ─────────────────────────────────────
await edit(COM, "?change=change&step=3");
await page.getByLabel(/^Minimum bill/).waitFor();
await page.getByLabel(/^Minimum bill/).fill("12.00");
await click("Continue");
await page.getByText("How it is saved").waitFor();
await page.fill("#plan-starts", "2027-01-01");
await page.locator("#plan-starts").blur();
const changes = await flat(page.getByRole("region", { name: "What changes" }));
check("9365 What changes reads $12.00", changes.includes("$12.00") && !/\b12\.00\b(?<!\$12\.00)/.test(changes.replace("$12.00", "")), changes);
await shot("9365-change-review", "Change from a date · Review — Minimum bill None → $12.00");
await page.getByLabel(/^Reason/).fill("New minimum bill from council");
await click("Save new version");
await page.locator("[data-plan-edit-saved]").waitFor();
say(`saved: ${await flat(page.locator("[data-plan-edit-saved]"))}`);

// ── DEF-RAT-9364 · publish the saved v2 from the details page ───────────────
await plan(COM);
const banner = page.getByTestId("plan-draft-version");
await banner.waitFor();
check("9364 the banner names v2", (await flat(banner)).includes("v2 not published yet."), await flat(banner));
await shot("9364-draft-banner", "Details · a saved v2 — banner with Publish v2, versions table shows Draft");
await banner.getByRole("button", { name: "Publish v2" }).click();
const confirm = page.getByRole("alertdialog");
await confirm.waitFor();
check("9364 the confirm says v1 ends 12/31/2026", (await flat(confirm)).includes("v1 ends 12/31/2026."), await flat(confirm));
await shot("9364-publish-confirm", "Publish v2 — the consequence: v1 ends 12/31/2026");
await confirm.getByRole("button", { name: "Publish v2" }).click();
await page.waitForTimeout(2000);
check("9364 the banner is gone", (await page.getByTestId("plan-draft-version").count()) === 0);
await shot("9364-published", "Published — v1 to 12/31/2026, v2 from 01/01/2027 scheduled");

// ── DEF-RAT-9363 / 9360 · a correction and a same-version edit in Audit ─────
await edit(COM, "?change=correct&step=3");
await page.getByLabel(/^Offer budget billing/).waitFor();
await page.getByLabel(/^Offer budget billing/).check({ force: true });
await click("Continue");
await page.getByText("How it is saved").waitFor();
await page.getByLabel(/^Reason/).fill("Budget billing was ruled on for this plan");
await shot("9365-correct-review", "Fix a mistake · Review — What changes");
await click("Save correction");
await page.locator("[data-plan-edit-saved]").waitFor();
await edit(COM, "?change=info");
await page.getByLabel(/^Description for customers/).fill("Water and electric for businesses inside the city.");
await click("Continue");
await page.getByText("What changes").waitFor();
await click("Save changes");
await page.locator("[data-plan-edit-saved]").waitFor();
}
// ── DEF-RAT-9504 · an every-class plan's base names who pays which ──────────
if (process.env.STD) {
  await plan(process.env.STD, "?tab=services");
  await page.waitForTimeout(1500);
  const base = await flat(page.locator('[data-base-state="ambiguous"]').first());
  check("9504 the ambiguous base names a class per code", /BASE-W · Residential/.test(base) || /BASE-E · Residential/.test(base), base);
  await shot("9504-every-class-base", "An every-class plan — each base code with the class it charges");
}
// ── DEF-CUS-9505 · the New account Review lists the deposit ─────────────────
await page.goto(`${BASE}/${TENANT}/accounts/new?step=5`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const reviewText = await flat(page.locator("main"));
check("9505 the Review has a Deposit block", /Deposit/.test(reviewText) && /No deposit on this plan\.|Yes — take one/.test(reviewText));
await shot("9505-new-account-review-deposit", "New account · Review — the Deposit block (the step's own answer)");
await plan(COM, "?tab=audit");
await page.waitForTimeout(1500);
const audit = await page.locator("main table tbody tr").allInnerTexts();
say(`audit rows: ${JSON.stringify(audit.map((row) => row.replace(/\s+/g, " ")))}`);
const fixRow = audit.find((row) => /Fixed a mistake/.test(row)) ?? "";
check("9363 the correction row says budget billing", /Budget billing/.test(fixRow) && !/Version terms/.test(fixRow), fixRow.replace(/\s+/g, " "));
const editRow = audit.find((row) => /Edited/.test(row) && /Description|business/i.test(row)) ?? audit.find((row) => /Edited/.test(row)) ?? "";
check("9360 the same-version edit names v1", /v1|V1/.test(editRow) && !/v2|V2/.test(editRow), editRow.replace(/\s+/g, " "));
const pubRow = audit.find((row) => /Published · v1/.test(row)) ?? "";
check("9360 a status reads as the pill does", /Status: Draft → Status: Published/.test(pubRow.replace(/\s+/g, " ")), pubRow.replace(/\s+/g, " "));
await shot("9363-audit", "Audit — the correction says Budget billing No → Yes; the description edit is v1");
const rows = page.locator("main table tbody tr");
for (let i = 0; i < Math.min(await rows.count(), 6); i += 1) {
  const row = rows.nth(i);
  const words = await flat(row);
  if (/Fixed a mistake/.test(words)) {
    await row.getByRole("button").first().click().catch(() => undefined);
    await page.waitForTimeout(600);
    await shot("9363-audit-correction-open", "Audit — the correction row opened: Before · After · Version");
    break;
  }
}

say(`\n${checks.filter(([, ok]) => ok).length}/${checks.length} checks PASS`);
await browser.close();
