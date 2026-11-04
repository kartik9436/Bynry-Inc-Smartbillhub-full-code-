// ── Trace ──────────────────────────────────────────────
// Change:  CR-165-BRC10 — Plans & Rates › Taxes & fees redesign, round 1 task 2:
//          REPRODUCE every problem the PO-approved mock-up lists (P1–P50) on
//          TODAY's screen before anything is fixed (maintenance process,
//          `12-governance/22-product-maintenance-process.md`, step REPRODUCE).
// ───────────────────────────────────────────────────────
//
// It changes no product code. It photographs today's list, New tax wizard,
// details and edit at 1440 wide, and prints the text it read beside each
// photograph so the CR's table can quote what was on screen.
//
// Expects:
//   * the API — `manage.py runserver 127.0.0.1:8491` on a scratch PostgreSQL 16
//     database with `migrate` + `seed_demo` run (Brazos Bend, Dana);
//   * the SPA — `vite build --mode wolocal` then
//     `PORT=8492 API_PROXY_TARGET=http://127.0.0.1:8491 node 07-frontend/server.mjs`.
//
//   OUT=08-qa/taxes-fees-2026-10-03/before node 10-scripts/cr165_taxes_fees_before_walk.mjs
//
// ⚠ A native <select>'s open list is drawn by the browser, not the page, so a
// headless photograph cannot show it. Where a problem is ABOUT an open list
// (P1, P4, P10) the walk gives the select a `size` attribute for the one photo
// so its options are visible, and says so in the photo's caption line.
// Staging that the wizard cannot do (a liability GL account, a code) goes
// through the same `PATCH /taxes/{id}` the details page uses.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8492";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr165-before";
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
async function expandSelect(id, size) {
  await page.$eval(
    `#${id}`,
    (el, s) => {
      el.setAttribute("size", String(s));
      el.style.height = "auto";
      el.style.maxHeight = "none";
    },
    size,
  );
}
async function collapseSelect(id) {
  await page.$eval(`#${id}`, (el) => {
    el.removeAttribute("size");
    el.style.height = "";
    el.style.maxHeight = "";
  });
}
async function selectByLabel(id, label) {
  await page.selectOption(`#${id}`, { label });
}
async function pressContinue() {
  await page.getByRole("button", { name: "Continue", exact: true }).click();
}

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);
const services = await api("GET", "settings/services");
say(
  "SERVICES SERVED:",
  services.data.length,
  "· switched on:",
  services.data.filter((s) => s.enabled).map((s) => s.service).join(","),
);

// ── 1 · NEW TAX — step 1 ────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees/new`, { waitUntil: "networkidle" });
await page.waitForSelector("#name", { timeout: 30000 });
await shot("w01-step1-empty", "step 1 as it opens (P2 P3 P5)");
say(await mainText());

const serviceSelect = await page.$eval('[data-testid="tax-services"] select, select[aria-label*="service" i]', (el) => el.id).catch(() => null);
say("services select id:", serviceSelect);
// The two tick-list selects carry no id; give each one for the photo.
const selects = await page.$$eval("main select", (els) =>
  els.map((el, i) => {
    if (!el.id) el.id = `cr165-select-${i}`;
    return { id: el.id, options: [...el.options].map((o) => o.textContent.trim()) };
  }),
);
say("SELECTS:", JSON.stringify(selects));
const svc = selects.find((s) => s.options.some((o) => o === "Electric"));
const cls = selects.find((s) => s.options.some((o) => o === "Residential"));
if (svc?.id) {
  await expandSelect(svc.id, svc.options.length);
  await shot("w02-services-list", `services list, select expanded with size=${svc.options.length} for the photo (P1)`);
  await collapseSelect(svc.id);
}

await page.fill("#name", "ann arbor City");
await selectByLabel("jurisdiction", "City");
await selectByLabel("premises_scope_kind", "Inside city limits");
await settle();
if (cls?.id) {
  await expandSelect(cls.id, cls.options.length);
  await shot("w03-boundary-city-classes-open", "boundary = Inside city limits; class list expanded for the photo (P4 P6)");
  await collapseSelect(cls.id);
}
await page.fill("#premises_scope_value", "Katy");
await settle();
await page.waitForTimeout(1500);
await shot("w04-step1-filled-count", "step 1 filled, the reach count and its sample (P6 P7)");
say(await mainText());
await pressContinue();

// ── 1 · NEW TAX — step 2 ────────────────────────────────────────────────────
await page.waitForSelector("#kind", { timeout: 15000 });
await shot("w05-step2-empty", "step 2 as it opens (P8 P10–P16 P18)");
say(await mainText());
const kindOptions = await page.$$eval("#kind option", (os) => os.map((o) => o.textContent.trim()));
await expandSelect("kind", kindOptions.length);
await shot("w06-basis-open", `basis list expanded with size=${kindOptions.length} for the photo (P10)`, { full: false });
await collapseSelect("kind");
// The clerk means 1.5 %. Today's box takes a FRACTION, so 1.5 is 150 %.
await page.fill("#rate", "1.5");
await settle();
await shot("w07-step2-rate-1-5", "rate typed 1.5 meaning 1.5% (P8 P9)");
say(await mainText());
await pressContinue();

// ── 1 · NEW TAX — step 3 (review) ───────────────────────────────────────────
await page.waitForTimeout(1500);
await shot("w08-step3-review", "review after typing 1.5 — no over-20% warning (P9 P17 P18 P19)");
say(await mainText());
const saveButtons = await page.$$eval("main button", (bs) => bs.map((b) => b.textContent.trim()));
say("REVIEW BUTTONS:", JSON.stringify(saveButtons));
// ⚠ NOT "Save draft & exit": on a NEW tax that button sends no draft flag and
// puts the tax in force too (found by this walk's first run — see the CR).
const saveLabel = saveButtons.find((b) => /^Save tax/i.test(b)) ?? "Save tax or fee";
await page.getByRole("button", { name: saveLabel, exact: true }).first().click();
await page.waitForURL((u) => /taxes-fees\/[0-9a-f-]{36}$/.test(u.pathname), { timeout: 20000 }).catch(() => {});
await page.waitForTimeout(1500);
const annArborId = page.url().split("/").pop();
say("SAVED ->", page.url());

// ── 2 · a second tax over 20 %, through the same wizard ─────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees/new`, { waitUntil: "networkidle" });
await page.waitForSelector("#name");
await page.fill("#name", "Water Development Fee");
await selectByLabel("jurisdiction", "Texas Water Development Board");
await pressContinue();
await page.waitForSelector("#rate");
await page.fill("#rate", "0.625");
await pressContinue();
await page.waitForTimeout(1200);
await page.getByRole("button", { name: saveLabel, exact: true }).first().click();
await page.waitForTimeout(2000);
const waterId = page.url().split("/").pop();
say("SAVED second ->", page.url());

// ── 2b · "Save draft & exit" on a NEW tax — what does it store? ─────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees/new`, { waitUntil: "networkidle" });
await page.waitForSelector("#name");
await page.fill("#name", "Draft probe fee");
await selectByLabel("jurisdiction", "Special district");
await pressContinue();
await page.waitForSelector("#rate");
await page.fill("#rate", "0.01");
await shot("w09-save-draft-and-exit", "about to press Save draft & exit on a new tax");
await page.getByRole("button", { name: "Save draft & exit", exact: true }).click();
await page.waitForTimeout(2000);
const afterDraft = await api("GET", "taxes?per=100");
const probe = (afterDraft.data?.results ?? []).find((t) => t.name === "Draft probe fee");
say("DRAFT PROBE stored as:", JSON.stringify({ status: probe?.status, in_force: probe?.in_force }));
await shot("w10-after-save-draft", `list after Save draft & exit — the tax reads ${probe?.status}`);

// Staging the wizard cannot do: a liability GL account with a long name on the
// 150 % tax (the details page writes this same field through this same PATCH).
const accounts = await api("GET", "ledger/accounts?per=1000");
const rows = Array.isArray(accounts.data) ? accounts.data : accounts.data?.results ?? accounts.data?.rows ?? [];
const longGl = rows.find((a) => a.code === "2520") ?? rows.find((a) => a.type === "liability");
say("GL picked:", longGl?.code, longGl?.name);
const patch = await api("PATCH", `taxes/${annArborId}`, { liability_gl_account_id: longGl?.account_id ?? longGl?.id });
say("PATCH GL:", patch.status);

// ── 3 · THE LIST ────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("l01-list", "list with two taxes over 20% (P21–P28)");
say(await mainText());
const headers = await page.$$eval("main th", (ths) => ths.map((th) => th.textContent.trim()));
say("LIST COLUMNS:", JSON.stringify(headers));

// ── 4 · DETAILS of the 150 % tax ────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees/${annArborId}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("d01-overview", "details · Overview of the 150% tax (P29–P38 P42–P43)");
say(await mainText());
say("DETAIL BUTTONS:", JSON.stringify(await page.$$eval("main button", (bs) => bs.map((b) => b.textContent.trim()).filter(Boolean))));
await page.getByRole("tab", { name: "Plans" }).click().catch(async () => page.getByRole("button", { name: "Plans", exact: true }).last().click());
await shot("d02-plans-tab", "details · Plans tab of the new tax (P39)");
say(await mainText());
await page.getByRole("tab", { name: "Audit" }).click().catch(async () => page.getByRole("button", { name: "Audit", exact: true }).last().click());
await shot("d03-audit-tab", "details · Audit tab of the new tax (P39 P40)");
say(await mainText());

// The seeded State tax, which three plans carry.
const list = await api("GET", "taxes?per=100");
const state = (list.data?.results ?? []).find((t) => t.name === "TX State Utility Tax");
await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees/${state.id}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.getByRole("tab", { name: "Plans" }).click().catch(async () => page.getByRole("button", { name: "Plans", exact: true }).last().click());
await shot("d04-state-plans-tab", "details · Plans tab of TX State Utility Tax (P39)");
say(await mainText());

// ── 5 · EDIT (today: one correction form) ───────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees/${annArborId}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
await page.getByRole("button", { name: "Edit", exact: true }).first().click();
await page.waitForTimeout(1800);
say("EDIT OPENS ->", page.url());
await shot("e01-edit-opens", "Edit pressed on a live tax (P44 P45 P46)");
say(await mainText());
await pressContinue();
await page.waitForSelector("#rate", { timeout: 15000 });
const rateDisabled = await page.$eval("#rate", (el) => el.disabled);
const fromDisabled = await page.$eval("#effective_from", (el) => el.disabled).catch(() => "n/a");
say("EDIT step 2: rate disabled =", rateDisabled, "· effective_from disabled =", fromDisabled);
await page.fill("#rate", "0.015");
await shot("e02-edit-step2", "edit step 2: rate editable, dates shown (P46 P47)");
say(await mainText());
await pressContinue();
await page.waitForTimeout(1500);
await shot("e03-edit-review", "edit review before a reason is typed (P48 P49 P50)");
say(await mainText());
say("EDIT REVIEW BUTTONS:", JSON.stringify(await page.$$eval("main button", (bs) => bs.map((b) => b.textContent.trim()).filter(Boolean))));
const editSave = (await page.$$eval("main button", (bs) => bs.map((b) => b.textContent.trim()))).find((b) => /^(Save|File)/i.test(b) && !/draft/i.test(b));
if (editSave) {
  await page.getByRole("button", { name: editSave, exact: true }).first().click();
  await page.waitForTimeout(1500);
  await shot("e04-edit-save-no-reason", `pressed "${editSave}" with no reason (P48)`);
  say(await mainText());
  if (await page.$("#reason")) {
    await page.fill("#reason", "Rate typed as 1.5 meaning 1.5 percent; the authority's rate is 1.5%.");
    await page.getByRole("button", { name: editSave, exact: true }).first().click();
    await page.waitForTimeout(2500);
    await shot("e05-edit-saved", "after saving the correction with a reason (P49 P40)");
    say("AFTER CORRECTION ->", page.url());
    say(await mainText());
    const tabAudit = page.getByRole("tab", { name: "Audit" });
    if (await tabAudit.count()) {
      await tabAudit.click();
      await shot("e06-audit-after-correction", "Audit tab after the correction (P40)");
      say(await mainText());
    }
  }
}

// ── 5b · the list after one correction: does the superseded row still show? ─
await page.goto(`${BASE}/${TENANT}/plans-rates/taxes-fees`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("l02-list-after-correction", "list after correcting the 150% tax (P27 — no version column)");
say(await mainText());

// ── 6 · the back-end facts the CR quotes (read-and-try, scratch database) ───
// A coded live tax corrected through the server's own correction door.
const coded = await api("PATCH", `taxes/${state.id}`, { code: "TX-SUT" });
say("PATCH code on State tax:", coded.status);
const corr = await api("POST", `taxes/${state.id}/corrections`, { rate: "0.0650", reason: "Rate restated by the Comptroller, letter of 2026-09-30." });
say("CORRECT coded tax:", corr.status, JSON.stringify(corr.data).slice(0, 600));
const versions = await api("GET", `taxes/${annArborId}/versions`);
say("VERSIONS of 150% tax:", versions.status, JSON.stringify(versions.data).slice(0, 800));
say("WATER id", waterId, "ANN ARBOR id", annArborId);

await browser.close();
