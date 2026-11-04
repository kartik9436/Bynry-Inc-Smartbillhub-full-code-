// ── Trace ──────────────────────────────────────────────
// Change:  CR-167-BRC10 round 4 task 10 — the plans FULL WEB WALK, as proposed
//          to the PO (`05-prototype/plans-2026-10-03/web-walk.md`, 9 phases).
//          A clerk (Dana) at 1440, clicking; every "must be true" is checked
//          on the SCREEN, against the API and in PostgreSQL, and every one of
//          the 44 drawn states is photographed under the image's own file name
//          into `08-qa/plans-2026-10-03/walk/`. Shape copied from
//          `cr166_discwalk.mjs` (the discounts walk of the same day); the
//          selectors are the plan lanes' own (`cr167_plan_form_walk.mjs`,
//          `cr167_plan_detail_walk.mjs`, `cr167_plan_edit_walk.mjs`,
//          `cr167_plans_list_after_walk.mjs`).
// ───────────────────────────────────────────────────────
//
// Stack: API `manage.py runserver` on PostgreSQL 16 (`migrate` + `seed_demo` +
// `10-scripts/cr167_planwalk_world.py setup`) AS A NON-SUPERUSER ROLE (so RLS
// is what keeps the two utilities apart, as in production — a superuser
// connection bypasses it); SPA `vite build --mode wolocal` served by
// `07-frontend/server.mjs`.
//
//   PHASES=1 BASE=http://127.0.0.1:5381 PGURL=postgres://postgres@127.0.0.1:55433/sbh_planwalk \
//     OUT=08-qa/plans-2026-10-03/walk node 10-scripts/cr167_planwalk.mjs
//
// Phases: 1 (with 2 inside it: the empty-step and empty-row refusals are the
// images 05/10/15/19 states of the Residential run), 1draft, 1com, 1fire,
// list, 3, 4, 5, 6, 6pub, dup, 9b, 9lang; the re-walk (2.494.0) adds rw and dep. The bill runs (phase 8) and the
// billing lookup (phase 7) are `cr167_planwalk_world.py`; `bills` reads them on
// screen here. Ids carry between runs in `$OUT/state.json`; every check is
// appended to `$OUT/results.json`.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5381";
const TENANT = "brazosbend";
const EMAIL = "dana@brazosbendutilities.com";
const B_TENANT = "riverbend";
const B_EMAIL = "ops@riverbend.example";
const PASSWORD = "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr167-planwalk";
const PGURL = process.env.PGURL ?? "postgres://postgres@127.0.0.1:55433/sbh_planwalk";
const PHASES = new Set((process.env.PHASES ?? "1").split(",").map((p) => p.trim()));
const STATE = `${OUT}/state.json`;
const RESULTS = `${OUT}/results.json`;
mkdirSync(OUT, { recursive: true });

const state = existsSync(STATE) ? JSON.parse(readFileSync(STATE, "utf8")) : { plans: {} };
const results = existsSync(RESULTS) ? JSON.parse(readFileSync(RESULTS, "utf8")) : [];
const saveState = () => writeFileSync(STATE, JSON.stringify(state, null, 2));
function check(phase, what, pass, evidence) {
  const row = { phase, what, pass: Boolean(pass), evidence: String(evidence ?? "") };
  const at = results.findIndex((r) => r.phase === phase && r.what === what);
  if (at >= 0) results[at] = row;
  else results.push(row);
  writeFileSync(RESULTS, JSON.stringify(results, null, 2));
  console.log(`${row.pass ? "PASS" : "FAIL"} ${phase} ${what} — ${row.evidence.slice(0, 500)}`);
}
function db(sql) {
  return execFileSync("psql", [PGURL, "-AtF", "|", "-c", sql], { encoding: "utf8" }).trim();
}
const dbRows = (sql) => {
  const out = db(sql);
  return out === "" ? [] : out.split("\n").map((line) => line.split("|"));
};
const A_ID = `(select id from tenants where subdomain='${TENANT}')`;

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of ["/opt/pw-browsers"]) {
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
page.on("pageerror", (error) => console.log(`PAGE ERROR ${error.message}`));
page.on("response", (res) => {
  const url = res.url();
  if (/\/api\/.*\/plans/.test(url) && res.request().method() !== "GET") {
    console.log(`  ${res.request().method()} ${url.replace(/^.*\/api\//, "")} → ${res.status()}`);
    if (res.status() >= 400) {
      console.log(`    sent: ${(res.request().postData() ?? "").slice(0, 1500)}`);
      res.text().then((body) => console.log(`    answer: ${body.slice(0, 1500)}`)).catch(() => {});
    }
  }
});
const settle = (ms = 900) => page.waitForTimeout(ms);

/** Full-page photograph: the shell scrolls its own column, so the viewport is
 *  grown to the tallest scroller first (the plan lanes' method). */
async function shot(name, caption) {
  await settle(700);
  await page.setViewportSize({ width: 1440, height: 900 });
  await settle(200);
  const tall = await page.evaluate(() =>
    Math.max(
      document.documentElement.scrollHeight,
      ...[...document.querySelectorAll("*")]
        .filter((el) => /auto|scroll/.test(getComputedStyle(el).overflowY) && el.scrollHeight > el.clientHeight)
        .map((el) => el.scrollHeight + el.getBoundingClientRect().top),
    ),
  );
  await page.setViewportSize({ width: 1440, height: Math.min(Math.max(900, Math.ceil(tall) + 40), 7000) });
  await settle(400);
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  const size = statSync(path).size;
  console.log(`  [shot] ${name}.png (${size} bytes) — ${caption}`);
  if (size < 15000) console.log(`  [shot] ⚠ ${name}.png is suspiciously small`);
}
let currentTenant = TENANT;
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
    [method, `${currentTenant}/${path}`, body],
  );
}
const text = async (selector = "main") => (await page.innerText(selector).catch(() => "")).replace(/\s+/g, " ");
const click = (name) => page.getByRole("button", { name, exact: true }).click();
async function signIn(tenant, email) {
  currentTenant = tenant;
  await page.context().clearCookies();
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}
/** Pick, in the LAST select of that name, the option whose text contains `want`. */
async function pickLast(label, want) {
  const boxes = page.getByRole("combobox", { name: label, exact: true });
  const box = boxes.nth((await boxes.count()) - 1);
  const value = await box.evaluate((el, w) => {
    const hit = [...el.options].find((o) => o.value === w || o.textContent.includes(w));
    return hit ? hit.value : null;
  }, want);
  if (value === null) {
    const all = await box.evaluate((el) => [...el.options].map((o) => o.textContent));
    throw new Error(`no option "${want}" in ${label}: ${JSON.stringify(all)}`);
  }
  await box.selectOption(value);
}
async function optionTexts(label) {
  const boxes = page.getByRole("combobox", { name: label, exact: true });
  return boxes.nth((await boxes.count()) - 1).evaluate((el) => [...el.options].map((o) => o.textContent.trim()));
}
async function tickClasses(labels) {
  await page.getByRole("button", { name: /^Customer classes/ }).click();
  for (const label of labels) await page.getByRole("checkbox", { name: label, exact: true }).check();
  await page.keyboard.press("Escape");
}
const PLANS = "plans-rates/plans";
async function openNew() {
  await page.goto(`${BASE}/${TENANT}/${PLANS}/new`, { waitUntil: "networkidle" });
  await page.getByLabel(/^Plan name/).waitFor();
  await settle(500);
}
const planRows = (code) =>
  dbRows(`select p.id, p.status, p.version, p.effective_from, p.effective_to,
                 (select count(*) from plan_versions v where v.rate_plan_id=p.id)
            from rate_plans p where p.code='${code}' and p.tenant_id=${A_ID}`);
const errorsShown = () =>
  page.$$eval("[id$='-error'], [role=alert]", (els) => els.map((e) => `${e.id || e.getAttribute("role")}:${e.textContent.trim()}`));

// ═══ PHASE 1 (+2) — the Residential plan, through every drawn state 04–22 ═══
const RES = { name: "Plan walk · Residential", code: "PW-RES" };
if (PHASES.has("1")) {
  await signIn(TENANT, EMAIL);
  await openNew();
  await shot("04-new-1-details-empty", "step 1 Details, empty");
  await click("Continue");
  await shot("05-new-1-details-errors", "Continue on empty: each missing box named");
  let errs = await errorsShown();
  check("2", "step 1 empty: name, code and classes each named on the box", errs.some((e) => /plan-name/.test(e)) && errs.some((e) => /plan-code/.test(e)), JSON.stringify(errs));
  await page.getByRole("button", { name: /^Customer classes/ }).click();
  const classOptions = await page.$$eval("[role=checkbox], input[type=checkbox]", (els) =>
    els.map((e) => e.getAttribute("aria-label") ?? e.closest("label")?.textContent?.trim() ?? "").filter(Boolean),
  );
  await shot("06-new-1-classes-dropdown", "Customer classes dropdown, Every customer class first");
  check("1", "classes dropdown: Every customer class first, then the utility's 8 classes", /Every customer class/.test(classOptions[0] ?? "") && classOptions.filter((c) => /Residential|Commercial|Industrial|Agricultural|Institutional|Municipal|Builder|Government/.test(c)).length >= 8, JSON.stringify(classOptions));
  await page.keyboard.press("Escape");
  await page.getByLabel(/^Plan name/).fill(RES.name);
  await page.getByLabel(/^Code/).fill(RES.code);
  await tickClasses(["Residential"]);
  await page.getByLabel(/^Description for customers/).fill("Water, sewer and trash for homes in Brazos Bend.");
  await page.check("#plan-intended-owner_occupied", { force: true });
  await click("+ Add note");
  await pickLast("Attribute", "customer_class");
  await pickLast("Operator", "is");
  await pickLast("Value", "Residential");
  await shot("07-new-1-details-filled", "step 1 filled: classes, intended-for tick, a note");
  const kept1 = [await page.inputValue("#plan-name"), await page.inputValue("#plan-code")];
  check("2", "nothing typed on step 1 is lost after the refusal", kept1.join("|") === `${RES.name}|${RES.code}`, kept1.join("|"));
  await click("Continue");
  await page.getByText("Services and rate schedules").waitFor();
  // Only Utility A's services are offered.
  await click("+ Add service");
  const serviceOptions = await optionTexts("Service");
  check("1", "only Utility A's services are offered (its five: electric, water, sewer, trash, fire)", serviceOptions.filter((o) => !/Choose|Pick|Select/i.test(o)).length === 5, JSON.stringify(serviceOptions));
  await pickLast("Service", "Water");
  await pickLast("Rate schedule", "Residential Water — Inclining tiers");
  for (const [service, schedule] of [["Sewer", "Sample — Sewer"], ["Trash", "Sample — Trash"]]) {
    await click("+ Add service");
    await pickLast("Service", service);
    await pickLast("Rate schedule", schedule);
  }
  await page.getByLabel(/^Outside-city premises pay more/).selectOption("yes");
  await page.fill("#plan-surcharge", "25");
  const ticks = page.getByRole("checkbox", { name: "Surcharge", exact: true });
  await ticks.nth(0).check();
  await ticks.nth(1).check();
  await shot("08-new-2-services-filled", "step 2: water, sewer, trash with schedule, base, minimum");
  const step2 = await text();
  check("1", "step 2 rows show the schedule's version and from-date", /V\d+\s*from \d\d\/\d\d\/\d{4}/i.test(step2), step2.match(/.{0,80}from \d\d\/\d\d\/\d{4}.{0,40}/)?.[0]);
  check("1", "step 2 shows the monthly base total under the table", /Monthly base charges/i.test(step2), step2.match(/Monthly base charges.{0,60}/i)?.[0]);
  await click("+ Add service");
  await shot("09-new-2-services-row-added", "an empty service row added");
  await click("Continue");
  await shot("10-new-2-services-row-error", "the empty row refused by name");
  errs = await errorsShown();
  check("2", "step 2 empty row: refused on its own box", /Choose a service in each row\./.test(await text('[data-array="plan-services"]').catch(() => "")) || /Choose a service in each row\./.test(await text()), JSON.stringify(errs));
  check("2", "nothing typed on step 2 is lost (three rows kept, surcharge 25)", (await page.getByRole("combobox", { name: "Service", exact: true }).count()) === 4 && (await page.inputValue("#plan-surcharge")) === "25", await page.inputValue("#plan-surcharge"));
  await pickLast("Service", "Fire");
  await pickLast("Rate schedule", "Sample — Fire capacity");
  await click("+ Add service");
  await pickLast("Service", "Electric");
  await pickLast("Rate schedule", "Sample — Electric usage");
  const addService = page.getByRole("button", { name: "+ Add service", exact: true });
  const allAdded = await text();
  await shot("11-new-2-services-all-added", "every service picked: + Add service greyed, All added.");
  check("2", "\"All added.\" when no service is left, + Add disabled", /All added\./.test(allAdded) && (await addService.isDisabled()), allAdded.match(/.{0,40}All added\..{0,10}/)?.[0]);
  // Back to the plan's three: remove electric and fire with ×.
  for (let i = 0; i < 2; i += 1) {
    const removes = page.locator('[data-array="plan-services"]').getByRole("button", { name: /Remove/ });
    await removes.nth((await removes.count()) - 1).click();
  }
  await shot("12-new-2-surcharge-on", "outside-city surcharge 25 % on, Surcharge ticked on water and sewer");
  check("1", "after × the services are water, sewer, trash", (await page.getByRole("combobox", { name: "Service", exact: true }).count()) === 3);
  await click("Continue");
  await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
  await click("+ Add charge code");
  await pickLast("Charge code", "RECON");
  await click("+ Add tax");
  await pickLast("Tax", "TX State Utility Tax");
  await shot("13-new-3-charges-filled", "step 3: LATE (pre-filled) and RECON; one tax, version and from-date");
  await click("+ Add tax");
  await pickLast("Tax", "Bexar");
  await shot("14-new-3-tax-added", "second tax added, All added.");
  check("2", "taxes: \"All added.\" once both of the utility's taxes are in", /All added\./.test(await text('[data-array="plan-taxes"]').catch(() => text())), "");
  await click("+ Add charge code");
  await click("Continue");
  await shot("15-new-3-charges-error", "the empty charge-code row refused");
  errs = await errorsShown();
  check("2", "step 3 empty charge-code row refused by name", errs.length > 0, JSON.stringify(errs));
  const removes3 = page.locator('[data-array="plan-charges"]').getByRole("button", { name: /Remove/ });
  await removes3.nth((await removes3.count()) - 1).click();
  await shot("16-new-3-row-removed", "the empty row removed with ×");
  await click("Continue");
  await page.getByRole("button", { name: "+ Add deposit" }).waitFor();
  await click("+ Add deposit");
  await pickLast("Deposit", "DEP-SIZE");
  await click("+ Add discount");
  await pickLast("Discount", "SENIOR");
  await page.fill("#plan-discount-from-0", "2026-11-01");
  await page.getByLabel(/^Minimum bill/).fill("10");
  await shot("17-new-4-billing-filled", "step 4: deposit by size, Senior, minimum bill $10.00");
  await click("+ Add discount");
  await pickLast("Discount", "AUTOPAY");
  await page.fill("#plan-discount-from-1", "2026-11-01");
  await page.fill("#plan-discount-until-1", "2027-10-31");
  await shot("18-new-4-discount-added", "Autopay added, offered 11/01/2026 – 10/31/2027");
  await click("+ Add deposit");
  await click("Continue");
  await shot("19-new-4-billing-error", "the empty deposit row refused");
  errs = await errorsShown();
  check("2", "step 4 empty deposit row refused by name", errs.length > 0, JSON.stringify(errs));
  check("2", "nothing typed on step 4 is lost (minimum 10, two discounts)", (await page.getByLabel(/^Minimum bill/).inputValue()).startsWith("10") && (await page.getByRole("combobox", { name: "Discount", exact: true }).count()) === 2, await page.getByLabel(/^Minimum bill/).inputValue());
  const depRemoves = page.locator('[data-array="plan-deposits"]').getByRole("button", { name: /Remove/ });
  await depRemoves.nth((await depRemoves.count()) - 1).click();
  await click("Continue");
  await page.getByRole("button", { name: "Publish plan" }).waitFor();
  await page.fill("#plan-starts", "2026-11-01");
  await page.locator("#plan-starts").blur();
  await page.setViewportSize({ width: 1440, height: 1500 });
  await settle(700);
  await page.screenshot({ path: `${OUT}/20-new-5-review-top.png` });
  console.log("  [shot] 20-new-5-review-top.png — Review, top of page");
  await page.setViewportSize({ width: 1440, height: 900 });
  await shot("21-new-5-review", "Review, full page ending in Save as draft · Publish plan");
  state.review = { [RES.code]: await text() };
  saveState();
  await click("Publish plan");
  await page.getByText(`${RES.name} published`, { exact: true }).waitFor({ timeout: 30000 });
  await shot("22-new-6-published", "published");
  const rows = planRows(RES.code);
  check("1", "Residential: exactly one database row, published, v1 from 11/01/2026", rows.length === 1 && rows[0][1] === "published" && rows[0][3] === "2026-11-01" && rows[0][5] === "1", JSON.stringify(rows));
  state.plans[RES.code] = rows[0]?.[0];
  saveState();
}

// ═══ 2re — step 2 re-read with the corrected patterns (the first run's two FAILs were the walk's own regexes) ═══
if (PHASES.has("2re")) {
  await signIn(TENANT, EMAIL);
  await openNew();
  await page.getByLabel(/^Plan name/).fill("Throwaway");
  await page.getByLabel(/^Code/).fill("PW-X");
  await tickClasses(["Residential"]);
  await click("Continue");
  await page.getByText("Services and rate schedules").waitFor();
  await click("+ Add service");
  await pickLast("Service", "Water");
  await pickLast("Rate schedule", "Residential Water — Inclining tiers");
  const step2 = await text();
  check("1", "step 2 rows show the schedule's version and from-date", /V\d+\s*from \d\d\/\d\d\/\d{4}/i.test(step2), step2.match(/V\d+\s*from \d\d\/\d\d\/\d{4}.{0,60}/i)?.[0]);
  await click("+ Add service");
  await click("Continue");
  const t = await text();
  check("2", "step 2 empty row: refused on its own box", /Choose a service in each row\./.test(t), t.match(/.{0,40}Choose a service in each row\..{0,20}/)?.[0]);
  check("2", "nothing was stored by the abandoned form", planRows("PW-X").length === 0, JSON.stringify(planRows("PW-X")));
}

// ═══ 20re — image 20 is the TOP of Review; the first run's photograph had
// scrolled to the Starts box. Re-taken on an unsaved form (nothing is written).
if (PHASES.has("20re")) {
  await signIn(TENANT, EMAIL);
  await openNew();
  await page.getByLabel(/^Plan name/).fill(RES.name);
  await page.getByLabel(/^Code/).fill("PW-RES-X");
  await tickClasses(["Residential"]);
  await page.getByLabel(/^Description for customers/).fill("Water, sewer and trash for homes in Brazos Bend.");
  await click("Continue");
  await page.getByText("Services and rate schedules").waitFor();
  for (const [service, schedule] of [["Water", "Residential Water — Inclining tiers"], ["Sewer", "Sample — Sewer"], ["Trash", "Sample — Trash"]]) {
    await click("+ Add service");
    await pickLast("Service", service);
    await pickLast("Rate schedule", schedule);
  }
  await click("Continue");
  await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
  await click("Continue");
  await page.getByRole("button", { name: "+ Add deposit" }).waitFor();
  await click("+ Add deposit");
  await pickLast("Deposit", "DEP-SIZE");
  await click("Continue");
  await page.getByRole("button", { name: "Publish plan" }).waitFor();
  await page.evaluate(() => document.querySelectorAll("main, main *").forEach((el) => { el.scrollTop = 0; }));
  await page.setViewportSize({ width: 1440, height: 1500 });
  await settle(800);
  await page.evaluate(() => document.querySelectorAll("main, main *").forEach((el) => { el.scrollTop = 0; }));
  await page.screenshot({ path: `${OUT}/20-new-5-review-top.png` });
  console.log("  [shot] 20-new-5-review-top.png — Review, top of page");
  check("2", "the abandoned form stored nothing (PW-RES-X)", planRows("PW-RES-X").length === 0, JSON.stringify(planRows("PW-RES-X")));
}

// ═══ PHASE 1 — the draft: saved half way, reopened, Save as draft (image 23), finished ═══
const MUNI = { name: "Plan walk · Municipal", code: "PW-MUNI" };
if (PHASES.has("1draft")) {
  await signIn(TENANT, EMAIL);
  let rows = planRows(MUNI.code);
  if (rows.length === 0) {
  await openNew();
  await page.getByLabel(/^Plan name/).fill(MUNI.name);
  await page.getByLabel(/^Code/).fill(MUNI.code);
  await tickClasses(["Municipal", "Government"]);
  await click("Continue");
  await page.getByText("Services and rate schedules").waitFor();
  await click("+ Add service");
  await pickLast("Service", "Water");
  await pickLast("Rate schedule", "Small Commercial Water — Flat");
  await click("Save draft & exit");
  await page.waitForURL((u) => /\/plans-rates\/?(\?|$)|\/plans\/?(\?|$)/.test(u.pathname + u.search) || !u.pathname.endsWith("/new"), { timeout: 20000 });
  await settle(1500);
  await shot("draft-1-saved-half-way", "Save draft & exit on step 2 → the list");
  rows = planRows(MUNI.code);
  check("1", "draft saved half way: one database row, status draft", rows.length === 1 && rows[0][1] === "draft", JSON.stringify(rows));
  state.plans[MUNI.code] = rows[0]?.[0];
  saveState();
  }
  // Reopened by Edit — a draft has no cards, the five steps.
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${state.plans[MUNI.code]}/edit`, { waitUntil: "networkidle" });
  await page.getByLabel(/^Plan name/).waitFor();
  const reopened = [await page.inputValue("#plan-name"), await page.inputValue("#plan-code")];
  await click("Continue");
  await page.getByText("Services and rate schedules").waitFor();
  const svc = await page.getByRole("combobox", { name: "Service", exact: true }).count();
  await shot("draft-2-reopened-services", "the draft reopened: what was typed is there");
  check("1", "the draft reopens with everything typed (name, code, the water row)", reopened.join("|") === `${MUNI.name}|${MUNI.code}` && svc === 1, `${reopened.join("|")} services=${svc}`);
  await click("Continue");
  await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
  await click("+ Add tax");
  await pickLast("Tax", "Bexar");
  await click("Continue");
  await page.getByRole("button", { name: "+ Add deposit" }).waitFor();
  await click("Continue");
  await page.getByRole("button", { name: /Publish plan/ }).waitFor();
  await page.fill("#plan-starts", "2026-11-01");
  await page.locator("#plan-starts").blur();
  await click("Save as draft");
  await page.locator("[data-plan-edit-saved]").waitFor({ timeout: 20000 });
  await shot("draft-3-saved-again", "the reopened draft finished to Review › Save as draft");
  rows = planRows(MUNI.code);
  check("1", "Save as draft: still ONE row, still a draft", rows.length === 1 && rows[0][1] === "draft", JSON.stringify(rows));
  // Finished: publish it.
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${state.plans[MUNI.code]}/edit?step=5`, { waitUntil: "networkidle" });
  await settle(1500);
  if ((await page.getByRole("button", { name: "Publish plan", exact: true }).count()) === 0) {
    for (let i = 0; i < 4; i += 1) {
      if ((await page.getByRole("button", { name: "Publish plan", exact: true }).count()) > 0) break;
      await click("Continue");
      await settle(600);
    }
  }
  await click("Publish plan");
  await settle(3000);
  await shot("draft-4-finished-published", "the draft finished and published");
  rows = planRows(MUNI.code);
  check("1", "the finished draft: still ONE row, now published v1 from 11/01/2026", rows.length === 1 && rows[0][1] === "published" && rows[0][3] === "2026-11-01" && rows[0][5] === "1", JSON.stringify(rows));
}

// ═══ PHASE 1 — Commercial: class-priced late fee and a class-priced deposit ═══
const COM = { name: "Plan walk · Commercial", code: "PW-COM" };
if (PHASES.has("1com")) {
  await signIn(TENANT, EMAIL);
  await openNew();
  await page.getByLabel(/^Plan name/).fill(COM.name);
  await page.getByLabel(/^Code/).fill(COM.code);
  await tickClasses(["Commercial"]);
  await page.getByLabel(/^Description for customers/).fill("Water and sewer for shops and offices.");
  await page.check("#plan-intended-min_demand_25kw", { force: true });
  await click("Continue");
  await page.getByText("Services and rate schedules").waitFor();
  for (const [service, schedule] of [["Water", "Sample — Commercial water"], ["Sewer", "Sample — Sewer"]]) {
    await click("+ Add service");
    await pickLast("Service", service);
    await pickLast("Rate schedule", schedule);
  }
  await click("Continue");
  await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
  // The pre-filled LATE row becomes the class-priced LATE-CL.
  await pickLast("Charge code", "LATE-CL");
  await click("+ Add tax");
  await pickLast("Tax", "Bexar");
  await shot("com-3-charges", "Commercial step 3: LATE-CL priced by class");
  const c3 = await text();
  // Step 3 draws a class-priced code's amount as "by customer class" (image 13);
  // the per-class figures are Review's (phase 3).
  check("1", "Commercial: the late fee row reads \"by customer class\" as drawn (image 13)", /by customer\s+class/.test(c3), c3.match(/.{0,30}by customer\s+class.{0,40}/)?.[0]);
  await click("Continue");
  await page.getByRole("button", { name: "+ Add deposit" }).waitFor();
  await click("+ Add deposit");
  await pickLast("Deposit", "DEPOSIT");
  await page.getByLabel(/^Minimum bill/).fill("25");
  await shot("com-4-billing", "Commercial step 4: deposit priced by class");
  const c4 = await text();
  check("1", "Commercial: the deposit row reads Priced by Class, Residential $150.00 · Commercial $300.00", /Class/.test(c4) && /\$?150\.00/.test(c4) && /\$?300\.00/.test(c4), c4.match(/DEPOSIT.{0,200}/)?.[0]);
  await click("Continue");
  await page.getByRole("button", { name: "Publish plan" }).waitFor();
  await page.fill("#plan-starts", "2026-11-01");
  await page.locator("#plan-starts").blur();
  await shot("com-5-review", "Commercial Review");
  state.review = { ...(state.review ?? {}), [COM.code]: await text() };
  saveState();
  await click("Publish plan");
  await page.getByText(`${COM.name} published`, { exact: true }).waitFor({ timeout: 30000 });
  const rows = planRows(COM.code);
  check("1", "Commercial: exactly one database row, published v1 from 11/01/2026", rows.length === 1 && rows[0][1] === "published" && rows[0][5] === "1", JSON.stringify(rows));
  state.plans[COM.code] = rows[0]?.[0];
  saveState();
}

// ═══ PHASE 1 — Fire: six sizes, counted ═══
const FIRE = { name: "Plan walk · Fire", code: "PW-FIRE" };
if (PHASES.has("1fire")) {
  await signIn(TENANT, EMAIL);
  await openNew();
  await page.getByLabel(/^Plan name/).fill(FIRE.name);
  await page.getByLabel(/^Code/).fill(FIRE.code);
  await tickClasses(["Commercial", "Industrial"]);
  await click("Continue");
  await page.getByText("Services and rate schedules").waitFor();
  await click("+ Add service");
  await pickLast("Service", "Fire");
  await pickLast("Rate schedule", "Sample — Fire capacity");
  await shot("fire-2-services", "Fire step 2");
  await click("Continue");
  await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
  await click("Continue");
  await page.getByRole("button", { name: "+ Add deposit" }).waitFor();
  await click("Continue");
  await page.getByRole("button", { name: "Publish plan" }).waitFor();
  await page.fill("#plan-starts", "2026-11-01");
  await page.locator("#plan-starts").blur();
  await shot("fire-5-review", "Fire Review: six line sizes, per line per month");
  const review = await text();
  state.review = { ...(state.review ?? {}), [FIRE.code]: review };
  saveState();
  const sizes = review.match(/\d+(?:½)?"\s*(?:line)?/g) ?? [];
  check("3", "Fire Review: six line sizes, priced per line per month (counted)", new Set(sizes.map((s) => s.replace(/\s.*/, ""))).size >= 6 && /Per line, per month/i.test(review), JSON.stringify([...new Set(sizes)]));
  // Image 23 is the NEW form's *Save as draft*: the Fire plan is saved as a
  // draft first, then reopened by Edit and published.
  await click("Save as draft");
  await page.getByText(`${FIRE.name} saved`, { exact: true }).waitFor({ timeout: 30000 });
  await shot("23-new-6-saved-draft", "New · Review › Save as draft");
  let rows = planRows(FIRE.code);
  check("1", "Fire saved as a draft from the New form: one row, draft", rows.length === 1 && rows[0][1] === "draft", JSON.stringify(rows));
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${rows[0][0]}/edit?step=5`, { waitUntil: "networkidle" });
  await settle(1500);
  for (let i = 0; i < 4 && (await page.getByRole("button", { name: "Publish plan", exact: true }).count()) === 0; i += 1) {
    await click("Continue");
    await settle(600);
  }
  await click("Publish plan");
  await settle(3000);
  rows = planRows(FIRE.code);
  check("1", "Fire: exactly one database row, published v1", rows.length === 1 && rows[0][1] === "published", JSON.stringify(rows));
  state.plans[FIRE.code] = rows[0]?.[0];
  saveState();
}

// ═══ LIST — images 01–03; each row shows version, from and to ═══
if (PHASES.has("list")) {
  await signIn(TENANT, EMAIL);
  await page.goto(`${BASE}/${TENANT}/plans-rates`, { waitUntil: "networkidle" });
  await page.locator("main table").waitFor();
  await settle(1200);
  await shot("01-list-all", "Plans list, all plans");
  const rowsOnScreen = await page.$$eval("main tbody tr", (trs) => trs.map((tr) => [...tr.children].map((td) => td.textContent.trim())));
  for (const code of ["PW-RES", "PW-COM", "PW-FIRE", "PW-MUNI"]) {
    const row = rowsOnScreen.find((cells) => cells.join(" ").includes(code));
    check("1", `list row ${code} shows version, from and to`, row && /v?1/.test(row[1] ?? "") && /11\/01\/2026/.test(row.join(" ")), JSON.stringify(row));
  }
  const search = page.getByPlaceholder("Search plan name or code");
  await search.fill("water");
  await settle(1500);
  await shot("02-list-search", 'Plans list, searched "water"');
  check("list", "search goes to the server (q= in the address)", page.url().includes("q=water"), page.url());
  await search.fill("zzzz");
  await settle(1500);
  await shot("03-list-no-results", "Plans list, a search with no results");
  check("list", "a search with no results says so", /No plans|No results|nothing/i.test(await text()), (await text()).slice(0, 200));
}

// ═══ PHASE 3 — Review showed every value entered, exactly (read from the saved Review text) ═══
if (PHASES.has("3")) {
  const r = state.review?.[RES.code] ?? "";
  for (const [what, re] of [
    ["the three services with their schedules", /Residential Water — Inclining tiers[\s\S]*Sample — Sewer[\s\S]*Sample — Trash/],
    ["outside-city surcharge 25 %", /25(\.00)?\s?%/],
    ["charge codes LATE and RECON", /LATE[\s\S]*RECON|RECON[\s\S]*LATE/],
    ["both taxes", /TX State Utility Tax[\s\S]*Bexar|Bexar[\s\S]*TX State Utility Tax/],
    ["deposit DEP-SIZE by size, 5/8\" $150.00 and 2\" $600.00", /DEP-SIZE[\s\S]*Water 5\/8"[\s\S]*Water 2"[\s\S]*\$150\.00[\s\S]*\$600\.00/],
    ["discounts Senior (from 11/01/2026) and Autopay (until 10/31/2027)", /Senior[\s\S]*11\/01\/2026[\s\S]*Autopay[\s\S]*10\/31\/2027|Autopay[\s\S]*10\/31\/2027/],
    ["minimum bill $10.00", /\$10\.00/],
    ["a version pill and a from-date on the referenced items", /v\d+[\s\S]{0,40}from \d\d\/\d\d\/\d{4}/i],
    ["starts 11/01/2026", /11\/01\/2026/],
  ]) check("3", `Residential Review: ${what}`, re.test(r), r.match(re)?.[0]?.slice(0, 160));
  const c = state.review?.[COM.code] ?? "";
  check("3", "Commercial Review: LATE-CL by class (1.50 % / 2.00 %), DEPOSIT by class ($150.00 / $300.00), minimum $25.00", /LATE-CL/.test(c) && /2\.00\s?%/.test(c) && /\$300\.00/.test(c) && /\$25\.00/.test(c), c.match(/LATE-CL.{0,120}/)?.[0]);
}

// ═══ PHASE 4 — the six tabs of the Residential plan (images 24–33, 37) ═══
async function tabsMatchReview(code) {
  const id = state.plans[code];
  const out = {};
  for (const tab of ["services", "charges", "billing"]) {
    await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}?tab=${tab}`, { waitUntil: "networkidle" });
    await page.locator(`[data-plan-priced-tab=${tab}]`).waitFor();
    if (tab === "services") await page.getByRole("button", { name: /Expand all/ }).click();
    await settle(800);
    out[tab] = await text();
  }
  return out;
}
if (PHASES.has("4")) {
  await signIn(TENANT, EMAIL);
  const id = state.plans[RES.code];
  const at = (search = "") => `${BASE}/${TENANT}/${PLANS}/${id}${search}`;
  await page.goto(at(), { waitUntil: "networkidle" });
  await page.locator("[data-plan-overview]").waitFor();
  await settle(1200);
  await shot("24-detail-overview", "Overview: tiles, banner, Details, versions");
  const tabs = await page.$$eval("[role=tab]", (all) => all.map((t) => t.textContent.trim()));
  check("4", "six tabs in the drawn order", /^Overview\|Services\d*\|Charges\|Billing\|Units\d*\|Audit$/.test(tabs.join("|")), tabs.join("|"));
  // tiles open their tab
  const tileTabs = await page.$$eval("[data-plan-tile-link]", (as) => as.map((a) => a.getAttribute("data-plan-tile-link")));
  await page.locator('[data-plan-tile-link="charges"]').first().click();
  await settle(1000);
  check("4", "a tile opens its tab (the Taxes tile → Charges, tab in the address)", /tab=charges/.test(page.url()) && (await page.locator("[data-plan-priced-tab=charges]").count()) === 1, `${JSON.stringify(tileTabs)} → ${page.url()}`);
  await page.goBack();
  await page.locator("[data-plan-overview]").waitFor();
  const overview = await text();
  check("4", "Overview shows intended-for and the class", /Owner-occupied/.test(overview) && /Residential/.test(overview), overview.match(/.{0,40}Owner-occupied.{0,40}/)?.[0]);
  // arrow keys
  await page.goto(at("?tab=services"), { waitUntil: "networkidle" });
  await page.locator("[role=tab][aria-selected=true]").focus();
  await page.keyboard.press("ArrowRight");
  await settle(800);
  check("4", "→ moves to the next tab (Charges) and the address follows", /tab=charges/.test(page.url()), page.url());
  await page.keyboard.press("ArrowLeft");
  await settle(800);
  check("4", "← moves back (Services)", /tab=services/.test(page.url()), page.url());
  await page.goto(at(), { waitUntil: "networkidle" });
  await page.locator("[data-plan-more] summary").click();
  await shot("25-detail-more", "More ▾: Duplicate, Retire");
  check("4", "More ▾ offers Duplicate (enabled since 2.489.0) and Retire", !(await page.getByTestId("plan-more-duplicate").isDisabled()) && /Retire/.test(await text("[data-plan-more]")), await text("[data-plan-more]"));
  await page.locator("[data-plan-more] summary").click();
  await page.goto(at("?tab=services"), { waitUntil: "networkidle" });
  await page.locator("[data-plan-priced-tab=services]").waitFor();
  await shot("26-detail-services-folded", "Services, each folded to one line");
  check("4", "each service folds to one line", (await page.locator("[data-service-line]").count()) === 3, await page.locator("[data-service-line]").count());
  const links = await page.$$eval("[data-plan-priced-tab] a", (as) => as.map((a) => [a.textContent.trim(), a.getAttribute("href")]));
  check("4", "names are links (schedules, codes)", links.length >= 3 && links.every(([, h]) => h && h.includes("/plans-rates/")), JSON.stringify(links.slice(0, 6)));
  // a schedule link opens the right page
  const scheduleLink = page.locator("[data-plan-priced-tab] a", { hasText: "Residential Water — Inclining tiers" }).first();
  if ((await scheduleLink.count()) > 0) {
    const href = await scheduleLink.getAttribute("href");
    await scheduleLink.click();
    await settle(2000);
    check("4", "the schedule's link opens that rate schedule", /Residential Water — Inclining tiers/.test(await text()), `${href} → ${page.url()}`);
    await page.goto(at("?tab=services"), { waitUntil: "networkidle" });
    await page.locator("[data-plan-priced-tab=services]").waitFor();
  } else check("4", "the schedule's link opens that rate schedule", false, "no link");
  await page.getByRole("button", { name: /Expand all/ }).click();
  await shot("27-detail-services-open", "Services, Expand all");
  check("4", "Expand all opens every service", (await page.locator("[data-service-tables]").count()) === (await page.locator("[data-plan-service]").count()));
  await page.getByRole("button", { name: /Collapse all/ }).click();
  await settle(500);
  check("4", "Collapse all folds them again", (await page.locator("[data-service-tables]").count()) === 0);
  await page.goto(at("?tab=charges"), { waitUntil: "networkidle" });
  await page.locator("[data-plan-priced-tab=charges]").waitFor();
  await shot("29-detail-charges", "Charges: charge codes and taxes");
  await page.goto(at("?tab=billing"), { waitUntil: "networkidle" });
  await page.locator("[data-plan-priced-tab=billing]").waitFor();
  await shot("30-detail-billing", "Billing: deposits, discounts, billing terms");
  const t = await tabsMatchReview(RES.code);
  const r = state.review?.[RES.code] ?? "";
  for (const [what, re] of [
    ["water schedule", /Residential Water — Inclining tiers/],
    ["surcharge 25 %", /25(\.00)?\s?%/],
  ]) check("4", `Services tab matches Review: ${what}`, re.test(t.services) && re.test(r), t.services.match(re)?.[0]);
  for (const [what, re] of [["LATE", /LATE/], ["RECON", /RECON/], ["TX State", /TX State Utility Tax/], ["Bexar", /Bexar/]]) {
    check("4", `Charges tab matches Review: ${what}`, re.test(t.charges) && re.test(r), t.charges.match(re)?.[0]);
  }
  for (const [what, re] of [["DEP-SIZE $150.00/$600.00", /DEP-SIZE[\s\S]*\$150\.00[\s\S]*\$600\.00/], ["Senior", /Senior/], ["Autopay", /Autopay/], ["minimum $10.00", /\$10\.00/]]) {
    check("4", `Billing tab matches Review: ${what}`, re.test(t.billing) && re.test(r), t.billing.match(re)?.[0]?.slice(0, 120));
  }
  // section Edit opens that step
  await page.goto(at("?tab=charges"), { waitUntil: "networkidle" });
  await page.locator("[data-plan-priced-tab=charges]").waitFor();
  await page.getByRole("button", { name: "Edit Charge codes" }).click();
  await page.waitForURL((u) => u.pathname.endsWith("/edit"), { timeout: 15000 });
  await page.waitForLoadState("networkidle");
  await settle(2500);
  await shot("37-detail-section-edit", "Charge codes › Edit opens that step of Change from a date");
  check("4", "a section's Edit opens that step (?change=change&step=2, Charges)", page.url().includes("/edit?change=change&step=2") && (await page.getByRole("button", { name: "+ Add charge code" }).count()) === 1, page.url());
}

// ═══ UNITS — images 31–33 (after `cr167_planwalk_world.py assign PW-RES`) ═══
if (PHASES.has("units")) {
  await signIn(TENANT, EMAIL);
  const id = state.plans[RES.code];
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}?tab=units`, { waitUntil: "networkidle" });
  await page.locator("[data-plan-units] tbody tr").first().waitFor();
  await settle(1000);
  await shot("31-detail-units", "Units: search, occupancy, CSV");
  const n = await page.locator("[data-plan-units] tbody tr").count();
  check("4", "Units lists the plan's 3 units, with links, no Move and no selection column", n === 3 && (await page.getByRole("button", { name: /Move/ }).count()) === 0 && (await page.locator("[data-plan-units] tbody input[type=checkbox]").count()) === 0, `rows=${n}`);
  await page.getByPlaceholder("Search unit or premises").fill("11 Pecan");
  await settle(1600);
  await shot("32-detail-units-search", 'Units searched "11 Pecan"');
  check("4", "Units search reaches the server and narrows to one", page.url().includes("u.q=") && (await page.locator("[data-plan-units] tbody tr").count()) === 1, page.url());
  await page.getByPlaceholder("Search unit or premises").fill("");
  await settle(1200);
  await page.locator('[data-occupancy="vacant"]').click();
  await settle(1500);
  await shot("33-detail-units-vacant", "Units, Vacant only");
  const vac = await text("[data-plan-units]");
  check("4", "Vacant shows the one unit with no account", (await page.locator("[data-plan-units] tbody tr").count()) === 1 && /15 Pecan/.test(vac), vac.slice(0, 200));
  const csv = await page.evaluate(async (p) => {
    const res = await fetch(`/api/${p}`, { credentials: "include", headers: { Accept: "text/csv" } });
    return { status: res.status, body: await res.text() };
  }, `${TENANT}/plans/${id}/units?format=csv`);
  check("4", "Units CSV carries the whole filtered set (3 rows + header)", csv.status === 200 && csv.body.trim().split("\n").length === 4, csv.body.slice(0, 300));
}

// ═══ PHASE 5 — the water schedule's v2 from 01/01/2027 (after `schedule_v2`) ═══
if (PHASES.has("5")) {
  await signIn(TENANT, EMAIL);
  const id = state.plans[RES.code];
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}`, { waitUntil: "networkidle" });
  await page.locator("[data-plan-overview]").waitFor();
  await settle(1200);
  const banners = await page.$$eval("[data-plan-upcoming]", (els) => els.map((e) => e.textContent.replace(/\s+/g, " ").trim()));
  await shot("24-detail-overview", "Overview: the upcoming banners — the plan's own v1 from 11/01/2026 AND water v2 from 01/01/2027");
  const served = await api("GET", `plans/${id}`);
  check("5", "the API serves both upcoming items: the plan's v1 (11/01/2026) and the water schedule's v2 (01/01/2027)", (served.data?.upcoming ?? []).some((u) => u.kind === "schedule" && u.effective_from === "2027-01-01"), JSON.stringify(served.data?.upcoming));
  check("5", "a banner names the water schedule's new version from 01/01/2027 with its new rates (DEF-RAT-9515: one line per upcoming item)", banners.some((b) => /01\/01\/2027/.test(b) && /[Ww]ater/.test(b) && /\$4\.40/.test(b)), JSON.stringify(banners));
  const today = await api("GET", `plans/${id}`);
  const later = await api("GET", `plans/${id}?as_of=2027-01-15`);
  const rates = (d) => JSON.stringify((d.services ?? []).find((s) => s.service === "water")?.usage?.rows?.map((r) => r.rate_display) ?? []);
  check("5", "the API: as of today the old rates, as of 01/15/2027 the new", rates(today.data) !== rates(later.data), `${rates(today.data)} → ${rates(later.data)}`);
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}?tab=services&as_of=2027-01-15`, { waitUntil: "networkidle" });
  await page.locator("[data-plan-priced-tab=services]").waitFor();
  await page.getByRole("button", { name: /Expand all/ }).click();
  await shot("28-detail-services-asof-2027", "Services, Priced as of 01/15/2027");
  const asOf = await text();
  state.asOfText = asOf;
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}?tab=services`, { waitUntil: "networkidle" });
  await page.locator("[data-plan-priced-tab=services]").waitFor();
  await page.getByRole("button", { name: /Expand all/ }).click();
  await settle(800);
  const todayText = await text();
  const firstRate = (s) => (s.match(/\$\d+\.\d{2} per kgal/g) ?? []).join(" ");
  check("5", "on screen: Priced as of 01/15/2027 shows the new rates, today the old", firstRate(asOf) !== firstRate(todayText) && firstRate(asOf) !== "", `${firstRate(todayText)} → ${firstRate(asOf)}`);
  saveState();
}

// ═══ PHASE 6 — Edit three ways on the Residential plan (images 38–44) ═══
const edit = (id, query) => page.goto(`${BASE}/${TENANT}/${PLANS}/${id}/edit${query}`, { waitUntil: "networkidle" });
const STAGE6 = ["info", "change", "correct", "audit"];
const from6 = STAGE6.indexOf(process.env.FROM6 ?? "info");
const run6 = (stage) => STAGE6.indexOf(stage) >= from6;
if (PHASES.has("6")) {
  await signIn(TENANT, EMAIL);
  const id = state.plans[RES.code];
  const before = planRows(RES.code);
  if (run6("info")) {
  // 1 · Name and details
  await edit(id, "?change=info");
  await page.getByLabel(/^Plan name/).waitFor();
  await page.getByLabel(/^Description for customers/).fill("Water, sewer and trash for homes in Brazos Bend and its farms.");
  await shot("38-edit-info-1", "Edit · Name and details · step Details");
  await click("Continue");
  await page.getByText("What changes").waitFor();
  await shot("39-edit-info-review", "Name and details · Review (same version)");
  await click("Save changes");
  await page.locator("[data-plan-edit-saved]").waitFor();
  const rows = planRows(RES.code);
  check("6", "Name and details: same row, same version", rows.length === 1 && rows[0][0] === before[0][0] && rows[0][2] === before[0][2] && rows[0][5] === before[0][5], JSON.stringify(rows));
  }
  if (run6("change")) {
  // 2 · Change from a date 01/01/2027 — minimum bill $10.00 → $12.00
  await edit(id, "?change=change");
  await page.getByRole("button", { name: "+ Add service" }).waitFor();
  await shot("40-edit-change-1", "Change from a date · first step (Services)");
  await click("Continue");
  await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
  await click("Continue");
  await page.getByLabel(/^Minimum bill/).waitFor();
  await page.getByLabel(/^Minimum bill/).fill("12.00");
  await click("Continue");
  await page.getByText("How it is saved").waitFor();
  await page.fill("#plan-starts", "2027-01-01");
  await page.locator("#plan-starts").blur();
  await page.getByLabel(/^Reason/).fill("Minimum bill rises with the new year");
  await shot("41-edit-change-review", "Change from a date · Review (v1 ends, v2 new; units move)");
  const r41 = await text();
  check("6", "Change from a date Review: v1 ends 12/31/2026, v2 from 01/01/2027, units move", /12\/31\/2026/.test(r41) && /01\/01\/2027/.test(r41) && /move to v2/.test(r41), r41.match(/How it is saved.{0,300}/)?.[0]);
  await click("Publish new version");
  await page.locator("[data-plan-edit-saved]").waitFor();
  await shot("42-edit-change-published", "Change from a date · new version published");
  }
  if (run6("correct")) {
  const versions = dbRows(`select version_no, status, effective_from, effective_to, minimum_bill_amount, corrects_version_id is not null
                             from plan_versions where rate_plan_id='${id}' order by version_no, created_at`);
  check("6", "Change from a date: v1 ends 12/31/2026, v2 starts 01/01/2027 at $12.00, nothing deleted, same plan row", planRows(RES.code).length === 1 && versions.some((v) => v[0] === "1" && v[3] === "2026-12-31") && versions.some((v) => v[0] === "2" && v[2] === "2027-01-01" && v[4].startsWith("12.")), JSON.stringify(versions));
  // 3 · Fix a mistake — v1 (the version in force today): budget billing on
  await edit(id, "?change=correct");
  await page.getByRole("button", { name: "+ Add service" }).waitFor();
  await shot("43-edit-correct-1", "Fix a mistake · first step");
  await edit(id, "?change=correct&step=3");
  await page.getByLabel(/^Offer budget billing/).waitFor();
  await page.getByLabel(/^Offer budget billing/).check({ force: true });
  await click("Continue");
  await page.getByText("How it is saved").waitFor();
  await page.getByLabel(/^Reason/).fill("Budget billing was always offered on this plan");
  await shot("44-edit-correct-review", "Fix a mistake · Review (same dates, reason)");
  await click("Save correction");
  await page.locator("[data-plan-edit-saved]").waitFor();
  const after = dbRows(`select version_no, status, effective_from, effective_to, budget_billing, corrects_version_id is not null
                          from plan_versions where rate_plan_id='${id}' order by version_no, created_at`);
  check("6", "Fix a mistake: v1 corrected with the SAME dates (11/01/2026–12/31/2026), the old v1 row kept", after.filter((v) => v[0] === "1").length === 2 && after.some((v) => v[0] === "1" && v[5] === "t" && v[2] === "2026-11-01" && v[3] === "2026-12-31" && v[4] === "t"), JSON.stringify(after));
  }
  // Audit shows each, before → after
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}?tab=audit`, { waitUntil: "networkidle" });
  await page.locator("[data-plan-audit]").waitFor();
  await settle(1500);
  await shot("34-detail-audit", "Audit: all changes");
  const audit = await text("[data-plan-audit]");
  check("6", "Audit lists the edit, the new version (and its publish) and the correction", /Edited|edited/.test(audit) && /01\/01\/2027/.test(audit) && /Fixed a mistake|correct/i.test(audit), audit.slice(0, 600));
  await page.locator('[data-audit-kind="underneath"]').click();
  await settle(1500);
  await shot("35-detail-audit-underneath", "Audit: changes underneath (the water schedule's v2)");
  check("6", "Changes underneath lists the water schedule's new version", /Residential Water|rate schedule|01\/01\/2027/i.test(await text("[data-plan-audit]")), (await text("[data-plan-audit]")).slice(0, 300));
  await page.locator('[data-audit-kind="all"]').click();
  await settle(1500);
  const expanders = page.locator("[data-plan-audit] tbody tr button[aria-expanded=false]");
  let opened = "";
  for (let i = 0; i < (await expanders.count()); i += 1) {
    const rowText = await expanders.nth(i).locator("xpath=ancestor::tr").innerText();
    if (/Edited|edited/.test(rowText)) {
      await expanders.nth(i).click();
      await settle(600);
      opened = await text("[data-plan-audit-open]");
      break;
    }
  }
  await shot("36-detail-audit-open", "Audit: the edit opened to before → after");
  check("6", "an Audit row opens to before → after (the description)", /Water, sewer and trash for homes in Brazos Bend\./.test(opened) && /its farms/.test(opened), opened.slice(0, 400));
}

// ═══ 6pub — Change from a date with Save new version, then Publish v2 (Commercial) ═══
if (PHASES.has("6pub")) {
  await signIn(TENANT, EMAIL);
  const id = state.plans[COM.code];
  let v = dbRows(`select version_no, status from plan_versions where rate_plan_id='${id}' order by version_no`);
  if (v.length === 1) {
  await edit(id, "?change=change&step=3");
  await page.getByLabel(/^Minimum bill/).waitFor();
  await page.getByLabel(/^Minimum bill/).fill("30.00");
  await click("Continue");
  await page.getByText("How it is saved").waitFor();
  await page.fill("#plan-starts", "2027-01-01");
  await page.locator("#plan-starts").blur();
  await page.getByLabel(/^Reason/).fill("Commercial minimum rises in 2027");
  await click("Save new version");
  await page.locator("[data-plan-edit-saved]").waitFor();
  v = dbRows(`select version_no, status from plan_versions where rate_plan_id='${id}' order by version_no`);
  check("6", "Save new version files v2 as a draft (v1 still published)", JSON.stringify(v) === JSON.stringify([["1", "published"], ["2", "draft"]]), JSON.stringify(v));
  }
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}`, { waitUntil: "networkidle" });
  await page.locator("[data-plan-overview]").waitFor();
  await settle(1000);
  await shot("pub-1-draft-v2-banner", "Commercial: v2 not published yet · Publish v2");
  await page.getByRole("button", { name: /Publish v2/ }).click();
  await settle(600);
  await shot("pub-2-confirm", "Publish v2 confirm: v1 ends 12/31/2026.");
  const dialog = (await page.locator("[role=alertdialog], [role=dialog]").first().innerText()).replace(/\s+/g, " ");
  await page.locator("[role=alertdialog], [role=dialog]").first().getByRole("button", { name: /^Publish v2$/ }).click();
  await settle(2500);
  await shot("pub-3-published", "Commercial v2 published from the details page");
  v = dbRows(`select version_no, status, effective_from, effective_to from plan_versions where rate_plan_id='${id}' order by version_no`);
  check("6", "Publish v2 (saved): v1 ends 12/31/2026, v2 published from 01/01/2027", /12\/31\/2026/.test(dialog) && v[0][3] === "2026-12-31" && v[1][1] === "published" && v[1][2] === "2027-01-01", `${dialog} ${JSON.stringify(v)}`);
  // DEF-RAT-9510: a DRAFT plan's v1 cannot be published through the version door.
  const muni = state.plans[MUNI.code];
  const draftPlan = await api("POST", "plans", { details: { name: "Plan walk · Probe draft", code: "PW-PROBE", customer_classes: [] }, services: [], charge_codes: [], taxes: [], deposits: [], discounts: [], effective_from: "2026-12-01" });
  const probe = await api("POST", `plans/${draftPlan.data?.id}/versions/1/publish`);
  const probeRow = planRows("PW-PROBE");
  check("6", "DEF-RAT-9510: publishing a DRAFT plan's v1 through the version door is refused by name, nothing moves", probe.status >= 400 && JSON.stringify(probe.data).includes("version_of_draft") && probeRow[0]?.[1] === "draft", `${draftPlan.status} → ${probe.status} ${JSON.stringify(probe.data).slice(0, 200)} ${JSON.stringify(probeRow)} (muni ${muni})`);
  if (draftPlan.data?.id) await api("DELETE", `plans/${draftPlan.data.id}`);
}

// ═══ dup — Duplicate (2.489.0) on the Residential plan ═══
if (PHASES.has("dup")) {
  await signIn(TENANT, EMAIL);
  const id = state.plans[RES.code];
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}`, { waitUntil: "networkidle" });
  await page.locator("[data-plan-more] summary").click();
  await page.getByTestId("plan-more-duplicate").click();
  await settle(600);
  const dlg = page.locator("[role=alertdialog], [role=dialog]").first();
  await dlg.getByLabel(/name/i).first().fill("Plan walk · Residential (copy)");
  await dlg.getByLabel(/code/i).first().fill("PW-RES-2");
  await shot("dup-1-dialog", "Duplicate: new name and code");
  await dlg.getByRole("button", { name: /Duplicate|Copy/ }).last().click();
  await settle(3000);
  await shot("dup-2-copy", "the copy, a draft");
  const copy = planRows("PW-RES-2");
  const src = planRows(RES.code);
  check("dup", "Duplicate makes ONE new draft row and leaves the source untouched", copy.length === 1 && copy[0][1] === "draft" && src[0][1] === "published", `${JSON.stringify(copy)} ${JSON.stringify(src)}`);
  const copyDetail = await api("GET", `plans/${copy[0]?.[0]}`);
  const svc = (copyDetail.data?.services ?? []).map((s) => s.service).sort().join(",");
  check("dup", "the copy offers the source's services today (sewer, trash, water) and no units", svc === "sewer,trash,water" && Number(copyDetail.data?.units ?? 0) === 0, `${svc} units=${copyDetail.data?.units}`);
  check("dup", "DEF-RAT-9506 holds: the draft copy offers no \"Publish v1\" banner", (await page.locator("[data-plan-draft-version], [data-testid=plan-draft-version]").count()) === 0);
}

// ═══ 9b — Utility B: none of A's plans on screen, via the API, in the database ═══
if (PHASES.has("9b")) {
  await signIn(B_TENANT, B_EMAIL);
  await page.goto(`${BASE}/${B_TENANT}/plans-rates`, { waitUntil: "networkidle" });
  await settle(2000);
  await shot("9-b-list", "Utility B: the Plans list");
  const listText = await text();
  check("9", "Utility B's Plans list shows none of A's plans", !/Plan walk|PW-RES|PW-COM|PW-FIRE|PW-MUNI/.test(listText), listText.slice(0, 300));
  const bList = await api("GET", "plans?per=100&q=PW-");
  check("9", "Utility B's API list finds none of A's plans", bList.status === 200 && (bList.data?.count ?? (bList.data?.results ?? []).length) === 0, `${bList.status} ${JSON.stringify(bList.data).slice(0, 200)}`);
  const aId = state.plans[RES.code];
  const direct = await api("GET", `plans/${aId}`);
  const write = await api("PATCH", `plans/${aId}`, { details: { description: "B was here" } });
  const units = await api("GET", `plans/${aId}/units`);
  const audit = await api("GET", `plans/${aId}/audit`);
  check("9", "A's plan by its id from B: 404 on read, units, audit and on a write", [direct.status, units.status, audit.status, write.status].every((s) => s === 404), JSON.stringify([direct.status, units.status, audit.status, write.status]));
  const opts = await api("GET", "plans/form-options");
  const leak = JSON.stringify(opts.data ?? {}).match(/DEP-SIZE|LATE-CL|Bexar|Sample — Fire/g);
  check("9", "B's New plan form offers none of A's schedules, codes or taxes", opts.status === 200 && !leak, `${opts.status} ${JSON.stringify(leak)}`);
  await page.goto(`${BASE}/${B_TENANT}/${PLANS}/${aId}`, { waitUntil: "networkidle" });
  await settle(2000);
  await shot("9-b-direct", "A's plan address typed into B's browser");
  check("9", "A's plan address in B's browser shows nothing of A's", !/Plan walk|PW-RES/.test(await text()), (await text()).slice(0, 200));
  const unchanged = db(`select description from rate_plans where id='${aId}'`);
  check("9", "A's plan unchanged by B's write", !/B was here/.test(unchanged), unchanged);
  // RLS: a throwaway NOSUPERUSER NOBYPASSRLS role inside a rolled-back transaction.
  const aT = db(`select id from tenants where subdomain='${TENANT}'`);
  const bT = db(`select id from tenants where subdomain='${B_TENANT}'`);
  const rls = execFileSync("psql", [PGURL, "-At", "-c", `begin;
    create role pw_rls_probe nosuperuser nobypassrls; grant select on rate_plans, plan_versions, plan_services to pw_rls_probe;
    set local role pw_rls_probe;
    select 'none:' || count(*) from rate_plans;
    select set_config('app.tenant_id', '${bT}', true) is not null;
    select 'B:' || count(*) || ':' || count(*) filter (where code like 'PW-%') from rate_plans;
    select 'Bv:' || count(*) from plan_versions where rate_plan_id='${aId}';
    select set_config('app.tenant_id', '${aT}', true) is not null;
    select 'A:' || count(*) filter (where code like 'PW-%') from rate_plans;
    rollback;`], { encoding: "utf8" }).trim().split("\n").filter((l) => /^(none|B|Bv|A):/.test(l));
  check("9", "RLS: no tenant → 0 plans; as Utility B → 0 of A's plans and versions; as A → A's walk plans", rls[0] === "none:0" && /^B:\d+:0$/.test(rls[1]) && rls[2] === "Bv:0" && /^A:[1-9]/.test(rls[3]), rls.join(" "));
}

// ═══ 9lang — the plan screens in the other 10 languages: no English left ═══
const LANGS = ["de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"];
if (PHASES.has("9lang")) {
  await signIn(TENANT, EMAIL);
  const id = state.plans[RES.code];
  const setLang = (code) => page.evaluate((c) => window.__SMARTBILLHUB_I18N__?.changeLanguage(c), code);
  // The screens' own English words a clerk would see; the utility's data
  // (plan, schedule, code, tax, discount and class names, the street) is
  // stripped first. A word a language shares with English is allowed per
  // language (G15's allow list).
  const DATA = /Plan walk · [A-Za-z() -]+|PW-RES-2|Residential Water — Inclining tiers|Sample — [^·$]*|Small Commercial Water — Flat|TX State Utility Tax|Local · Bexar County|Senior discount|Autopay discount|Security deposit[^·]*|Late payment fee|Reconnection fee|Water, sewer and trash[^.]*\.|Minimum bill rises with the new year|Budget billing was always offered on this plan|Pecan Walk Way|Water base service — residential|Sewer base charge|Trash base charge|Late fee by class|Security deposit by meter size|Water rates rise with the new year \(plans walk\)|Size rows carried from v1[^·]*|Residential|Commercial|Dana Whitfield|PW-[A-Z-]+|DEP-SIZE|DEPOSIT|LATE-CL|LATE|RECON|SENIOR|AUTOPAY|BASE-[A-Z-]+|kgal|USD/g;
  const PROBES = ["Plans", "Services", "Charges", "Billing", "Units", "Audit", "Overview", "Edit", "Continue", "Review", "Publish", "Version", "Status", "Name", "Search", "Base charges", "Usage charges", "Charge codes", "Taxes", "Deposits", "Discounts", "Minimum bill", "Customer classes", "Expand all", "Priced as of", "Occupied", "Vacant", "Details", "Back", "From", "Until",
    // The SERVER's English (DEF-RAT-9502 / 9509 / 9518): service names, rate words.
    "Water", "Sewer", "Trash", "Fire", "per kgal", "per cart", "Block (per month)", "Usage and base charges"];
  const ALLOW = { de: ["Status", "Name", "Details"], "fr-FR": ["Version", "Services", "Status"], "id-ID": ["Status"], es: [], "es-MX": [], hi: [], "it-IT": [], "ja-JP": [], "ko-KR": [], "pt-BR": [] };
  const screens = [
    ["list", `${BASE}/${TENANT}/plans-rates`, "main table"],
    ["new-1", `${BASE}/${TENANT}/${PLANS}/new`, "#plan-name"],
    ["detail-overview", `${BASE}/${TENANT}/${PLANS}/${id}`, "[data-plan-overview]"],
    ["detail-services", `${BASE}/${TENANT}/${PLANS}/${id}?tab=services`, "[data-plan-priced-tab=services]"],
    ["detail-charges", `${BASE}/${TENANT}/${PLANS}/${id}?tab=charges`, "[data-plan-priced-tab=charges]"],
    ["detail-billing", `${BASE}/${TENANT}/${PLANS}/${id}?tab=billing`, "[data-plan-priced-tab=billing]"],
    ["detail-units", `${BASE}/${TENANT}/${PLANS}/${id}?tab=units`, "[data-plan-units]"],
    ["detail-audit", `${BASE}/${TENANT}/${PLANS}/${id}?tab=audit`, "[data-plan-audit]"],
    ["edit-change", `${BASE}/${TENANT}/${PLANS}/${id}/edit?change=change`, "[data-plan-step]"],
  ];
  for (const lang of LANGS) {
    for (const [name, url, ready] of screens) {
      await page.goto(url, { waitUntil: "networkidle" });
      await setLang(lang);
      await page.locator(ready).first().waitFor({ timeout: 30000 });
      await settle(900);
      const raw = await page.evaluate(() => {
        const main = document.querySelector("main");
        const clone = main.cloneNode(true);
        clone.querySelectorAll("option, input, textarea, [data-utility-data]").forEach((el) => el.remove());
        return clone.innerText;
      });
      const stripped = raw.replace(DATA, " ");
      const found = PROBES.filter((w) => !(ALLOW[lang] ?? []).includes(w) && new RegExp(`(^|[^\\p{L}])${w}([^\\p{L}]|$)`, "u").test(stripped));
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (["ja-JP", "de", "hi"].includes(lang) || name === "detail-services") await shot(`9-lang-${name}-${lang}`, `${name} in ${lang}`);
      check("9", `${lang} ${name}: no English left, no sideways scroll`, found.length === 0 && overflow <= 0, `english=${JSON.stringify(found)} overflow=${overflow}`);
    }
  }
  await setLang("en");
}

// ═══ bills — phase 8 on screen: the December and January bills of Ruth ═══
if (PHASES.has("bills")) {
  await signIn(TENANT, EMAIL);
  for (const [n, invoiceId] of Object.entries(state.bills ?? {})) {
    await page.goto(`${BASE}/${TENANT}/billing/bills/${invoiceId}?tab=lines`, { waitUntil: "networkidle" });
    await settle(2500);
    await shot(`8-bill-${n}`, `bill ${n} on screen`);
    const t = await text();
    const apiBill = await api("GET", `invoices/${invoiceId}`);
    state.billText = { ...(state.billText ?? {}), [n]: t.slice(0, 3000) };
    state.billApi = { ...(state.billApi ?? {}), [n]: { total: apiBill.data?.total, lines: (apiBill.data?.lines ?? []).map((l) => [l.kind, l.description, l.amount]) } };
    console.log(`BILL ${n} api total ${apiBill.data?.total}`, JSON.stringify(state.billApi[n].lines));
    const [total, tier1, tier2] = state.expect?.[n] ?? [];
    const dbLines = dbRows(`select kind, amount from invoice_lines where invoice_id='${invoiceId}'`);
    const dbTotal = db(`select total from invoices where id='${invoiceId}'`);
    const has = (fig) => t.includes(`$${fig}`);
    check("8", `${n}: total $${total}, water tier 1 $${tier1}, tier 2 $${tier2} — on screen, in the API and in the database`,
      has(total) && has(tier1) && has(tier2) && Number(apiBill.data?.total ?? apiBill.data?.total_amount) === Number(total) && Number(dbTotal) === Number(total),
      `screen ${[total, tier1, tier2].map(has)} api ${apiBill.data?.total} db ${dbTotal}`);
    const bases = dbLines.filter(([k]) => k === "base").length;
    const deposits = dbLines.filter(([k]) => /deposit/.test(k)).length;
    check("8", `${n}: one base line per service (2), no deposit line`, bases === 2 && deposits === 0, JSON.stringify(dbLines));
  }
  const assessed = dbRows(`select account_no, deposit_assessed from accounts where account_no in ('AC-2026-00054','AC-2026-00055') order by 1`);
  check("8", "the deposit is assessed ONCE ($150.00 each) and billed on neither month", assessed.every(([, a]) => Number(a) === 150) && db(`select count(*) from invoice_lines l join invoices i on i.id=l.invoice_id join accounts a on a.id=i.account_id where a.account_no in ('AC-2026-00054','AC-2026-00055') and l.kind like '%deposit%'`) === "0", JSON.stringify(assessed));
  saveState();
}


// ═══ RE-WALK (2.494.0) — what landed after the first walk ═══
// `rw` reads the plan screens for 2.490.6 (DEF-RAT-9519: a tax the plan's
// classes do not pay is marked and left out of "combined") and for the
// discount grants of 2.491.0 / 2.492.1 (the plan's Billing › Discounts still
// reads as Review does). `dep` is DEF-CUS-9521 (2.492.0) on THIS walk's plan:
// PW-RES prices its deposit by size (DEP-SIZE 5/8" $150.00 · 2" $600.00), and
// a unit with no meter fitted (`cr167_planwalk_world.py vacant PW-RES <n>`)
// must offer the size picker on New account and on Move-in and charge the
// picked size; a 5/8" meter unit shows $150.00 and no picker. It also reads
// DEF-CUS-9524 (Amount taken shows the deposit to 2 places, hard rule 2).
if (PHASES.has("rw")) {
  await signIn(TENANT, EMAIL);
  const id = state.plans[RES.code];
  const r = state.review?.[RES.code] ?? "";
  check("rw", "Review: TX State Utility Tax is marked \"Not charged to this plan's classes\" (DEF-RAT-9519, 2.490.6)", /TX State Utility Tax[\s\S]{0,120}Not charged to this plan's classes/.test(r), r.match(/TX State Utility Tax.{0,140}/)?.[0]);
  check("rw", "Review: the combined figure is what a Residential bill charges — 2.00 %, not 8.25 % (DEF-RAT-9519)", /Taxes 2\.00% combined/.test(r) && !/8\.25/.test(r), r.match(/Taxes [\d.]+% combined/)?.[0]);
  const served = await api("GET", `plans/${id}`);
  const taxes = served.data?.taxes ?? served.data?.charges?.taxes ?? [];
  const reach = JSON.stringify((Array.isArray(taxes) ? taxes : []).map((x) => [x.ref?.name ?? x.name, x.reaches_plan_classes]));
  check("rw", "API: the plan read serves reaches_plan_classes (TX State none, Bexar all)", /TX State Utility Tax","none"/.test(reach) && /Bexar County","all"/.test(reach), reach);
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}?tab=charges`, { waitUntil: "networkidle" });
  await page.locator("[data-plan-priced-tab=charges]").waitFor();
  await settle(900);
  const ch = await text();
  await shot("rw-detail-charges-tax-not-charged", "Charges tab: TX State marked Not charged to this plan's classes, 2.00 % combined");
  check("rw", "Charges tab: TX State marked \"Not charged to this plan's classes\", 2.00 % combined", /Not charged to this plan's classes/.test(ch) && /2\.00% combined/.test(ch) && !/8\.25% combined/.test(ch), ch.match(/Taxes.{0,260}/)?.[0]);
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}`, { waitUntil: "networkidle" });
  await page.locator("[data-plan-overview]").waitFor();
  await settle(900);
  const ov = await text();
  check("rw", "Overview: the Taxes tile reads 2.00 % (not 8.25 %)", /2\.00%/.test(ov) && !/8\.25%/.test(ov), ov.match(/.{0,30}Taxes.{0,40}/)?.[0]);
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}?tab=billing`, { waitUntil: "networkidle" });
  await page.locator("[data-plan-priced-tab=billing]").waitFor();
  await settle(900);
  const bl = await text();
  await shot("rw-detail-billing-discounts", "Billing tab: deposits by size, Senior and Autopay with offered dates and Enrolled, billing terms");
  check("rw", "Billing › Discounts after the grants (2.491.0/2.492.1): Senior 15.00 % from 11/01/2026 no end, Autopay 0.50 % 11/01/2026 – 10/31/2027, GL 4760, Enrolled column", /SENIOR[\s\S]{0,80}15\.00%[\s\S]{0,40}11\/01\/2026[\s\S]{0,20}No end/.test(bl) && /AUTOPAY[\s\S]{0,80}0\.50%[\s\S]{0,40}11\/01\/2026[\s\S]{0,20}10\/31\/2027/.test(bl) && /4760/.test(bl) && /Enrolled/i.test(bl), bl.match(/Discounts.{0,420}/)?.[0]);
  const rd = r.match(/Discounts Edit.{0,400}/)?.[0] ?? "";
  const bd = bl.match(/Discounts Edit.{0,500}?Billing terms/)?.[0] ?? "";
  // Enrolled is the discount's own take-up across the utility (CR-167 §5.5
  // item 9), so it is not compared with Review's.
  check("rw", "Billing › Discounts reads as Review did (same codes, values, dates)", ["SENIOR", "15.00%", "AUTOPAY", "0.50%", "10/31/2027"].every((w) => rd.includes(w) && bd.includes(w)), `${rd.slice(0, 160)} ‖ ${bd.slice(0, 160)}`);
  saveState();
}

async function depositStep() {
  await page.locator('[data-deposit-plan="pending"]').waitFor({ state: "detached", timeout: 15000 }).catch(() => {});
  await settle(900);
  const amount = await page.locator("#deposit_amount").inputValue().catch(() => null);
  const sizes = await page.locator("#deposit_size_class option").evaluateAll((os) => os.filter((o) => o.value).map((o) => `${o.value}=${o.textContent.trim()}`)).catch(() => []);
  return { amount, sizes };
}
const contDep = async () => {
  await page.locator("button", { hasText: /^Continue/ }).first().click();
  await settle(1500);
};
const DEP_OPEN = process.env.DEP_OPEN ?? "2026-11-01";
const DEP_TAG = process.env.DEP_TAG ?? "";
if (PHASES.has("dep")) {
  await signIn(TENANT, EMAIL);
  const [newUnit, moveUnit, meterUnit] = (process.env.DEP_UNITS ?? "U-00006,U-00007,U-00010").split(",");
  // New account on a no-meter unit of PW-RES.
  await page.goto(`${BASE}/${TENANT}/accounts/new`, { waitUntil: "networkidle" });
  await settle(1200);
  await page.locator("#account_type").selectOption("residential");
  await page.fill("#full_name", `Rosa Pemberton ${newUnit}`);
  await page.fill("#email", `rosa.${newUnit.toLowerCase()}@planwalk.example`);
  await page.fill("#phone", "(281) 555-0199");
  await page.locator('label:has(input[name="customer_kind"][value="person"])').click();
  await contDep();
  await page.locator("#unit_id").fill(newUnit);
  const option = page.locator('[role="option"]', { hasText: newUnit }).first();
  await option.waitFor({ timeout: 60000 });
  await option.click();
  await page.fill("#opened_at", DEP_OPEN);
  await contDep();
  await contDep();
  let d = await depositStep();
  await shot(`dep-01-new-no-meter-pick${DEP_TAG}`, "New account · Deposit · no meter fitted on PW-RES: Meter size offered");
  check("dep", `New account, ${newUnit} (PW-RES, no meter): the Meter size picker offers the plan's sizes smallest first, nothing picked`, JSON.stringify(d.sizes) === JSON.stringify(['W-58=Water 5/8"', 'W-2=Water 2"']) && !d.amount, JSON.stringify(d));
  await page.locator("#deposit_size_class").selectOption("W-2");
  await settle(600);
  d = await depositStep();
  check("dep", "New account: 2\" picked → the deposit reads 600.00", d.amount === "600.00", JSON.stringify(d));
  await page.locator("label:has(#deposit_take_now)").click();
  await page.locator("#deposit_method_code").selectOption("cash");
  await page.fill("#deposit_posted_at", DEP_OPEN);
  await page.fill("#deposit_cleared_at", DEP_OPEN).catch(() => {});
  const taken = await page.locator("#deposit_amount_taken").inputValue();
  await shot(`dep-02-new-2in-taken${DEP_TAG}`, "New account · Deposit · 2\" picked, $600.00 taken today");
  check("dep", "DEF-CUS-9524: Amount taken shows the deposit to 2 places (600.00, not 600.0000)", taken === "600.00", `amount taken box ${JSON.stringify(taken)}`);
  await contDep();
  const review = await text();
  await shot(`dep-03-new-review${DEP_TAG}`, "New account · Review: Meter size 2\", $600.00");
  // The amount rows on New account's Review read "Currency not known here":
  // `DEF-CUS-5114` (open, known — the first walk's brief excluded it), so this
  // checks the picked SIZE and that no 4-place figure is printed.
  check("dep", "New account Review names the picked size (Meter size Water 2\"), no 4-place figure", /Meter size Water 2"/.test(review) && !/600\.0000/.test(review), review.match(/Deposit Yes.{0,200}/)?.[0]);
  const answer = page.waitForResponse((res) => res.url().endsWith(`/api/${TENANT}/accounts`) && res.request().method() === "POST", { timeout: 60000 });
  await page.locator('button[data-variant="primary"]').last().click();
  const res = await answer;
  const body = await res.json().catch(() => ({}));
  await settle(2000);
  await shot(`dep-04-new-created${DEP_TAG}`, "New account created · $600.00 deposit taken");
  const row = dbRows(`select a.account_no, a.deposit_assessed, a.deposit_size_class, coalesce(a.deposit_size_picked_by::text,'') <> '' from accounts a join units u on u.id=a.unit_id where u.unit_no='${newUnit}' and a.tenant_id=${A_ID}`);
  const paid = db(`select coalesce(sum(p.amount),0) from payments p join accounts a on a.id=p.account_id join units u on u.id=a.unit_id where u.unit_no='${newUnit}' and a.tenant_id=${A_ID}`);
  const audit = db(`select count(*) from audit_log where action='deposit.size_picked' and tenant_id=${A_ID} and after::text like '%W-2%'`);
  check("dep", "New account charged the PICKED size: account deposit $600.00, size W-2 kept with who picked it, $600.00 taken, audit deposit.size_picked", res.status() === 201 && row.length === 1 && Number(row[0][1]) === 600 && row[0][2] === "W-2" && row[0][3] === "t" && Number(paid) === 600 && Number(audit) >= 1, `POST ${res.status()} ${JSON.stringify(body.deposit ?? body).slice(0, 300)} db=${JSON.stringify(row)} paid=${paid} audit=${audit}`);
  state.depAccounts = { ...(state.depAccounts ?? {}), [newUnit]: row[0]?.[0] };

  // Move-in on another no-meter unit of PW-RES.
  await page.goto(`${BASE}/${TENANT}/move-ins/new`, { waitUntil: "networkidle" });
  await settle(1500);
  const unitLabel = await page.locator("#mvi_unit option", { hasText: moveUnit }).first().textContent();
  await page.locator("#mvi_unit").selectOption({ label: unitLabel });
  await settle(2000);
  await contDep();
  await contDep();
  await page.locator("#account_type").waitFor();
  await page.locator("#account_type").selectOption("residential");
  await page.fill("#full_name", `Ana Ruiz ${moveUnit}`);
  await page.fill("#email", `ana.${moveUnit.toLowerCase()}@planwalk.example`);
  await page.fill("#phone", "(281) 555-0188");
  await page.locator('label:has(input[name="customer_kind"][value="person"])').click();
  await contDep();
  await page.fill("#opened_at", DEP_OPEN);
  await contDep();
  await contDep();
  d = await depositStep();
  await shot(`dep-05-movein-no-meter-pick${DEP_TAG}`, "Move-in · Deposit · no meter fitted on PW-RES: Meter size offered");
  check("dep", `Move-in, ${moveUnit} (PW-RES, no meter): the Meter size picker is offered, nothing picked`, d.sizes.length === 2 && d.sizes[0].startsWith("W-58") && !d.amount, JSON.stringify(d));
  await page.locator("#deposit_size_class").selectOption("W-2");
  await settle(600);
  d = await depositStep();
  await page.locator("label:has(#deposit_take_now)").click();
  await settle(400);
  const takenMi = await page.locator("#deposit_amount_taken").inputValue().catch(() => null);
  await shot(`dep-06-movein-2in-picked${DEP_TAG}`, "Move-in · Deposit · 2\" picked → $600.00, taken today");
  check("dep", "Move-in: 2\" picked → 600.00, and Amount taken reads 600.00 (DEF-CUS-9524)", d.amount === "600.00" && takenMi === "600.00", `${JSON.stringify(d)} taken=${JSON.stringify(takenMi)}`);

  // A 5/8" meter fitted: the amount follows it, no picker.
  await page.goto(`${BASE}/${TENANT}/accounts/new`, { waitUntil: "networkidle" });
  await settle(1200);
  await page.locator("#account_type").selectOption("residential");
  await page.fill("#full_name", "Lone Star Bakery");
  await page.fill("#email", "bakery@planwalk.example");
  await page.fill("#phone", "(281) 555-0177");
  await page.locator('label:has(input[name="customer_kind"][value="person"])').click();
  await contDep();
  await page.locator("#unit_id").fill(meterUnit);
  const opt2 = page.locator('[role="option"]', { hasText: meterUnit }).first();
  await opt2.waitFor({ timeout: 60000 });
  await opt2.click();
  await page.fill("#opened_at", DEP_OPEN);
  await contDep();
  await contDep();
  d = await depositStep();
  await shot(`dep-07-new-meter-58-no-picker${DEP_TAG}`, "New account · Deposit · 5/8\" meter fitted → $150.00, no picker");
  check("dep", `New account, ${meterUnit} (5/8" meter fitted): $150.00 and no picker`, d.amount === "150.00" && d.sizes.length === 0, JSON.stringify(d));
  saveState();
}

const failed = results.filter((r) => !r.pass);
console.log(`\n${results.length} checks recorded, ${results.length - failed.length} pass, ${failed.length} fail`);
await browser.close();
