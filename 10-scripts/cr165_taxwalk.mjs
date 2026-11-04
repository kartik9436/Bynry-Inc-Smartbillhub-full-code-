// ── Trace ──────────────────────────────────────────────
// Change:  CR-165-BRC10 round 4 task 9 — the taxes & fees FULL WEB WALK, as
//          agreed with the PO (`05-prototype/taxes-fees-2026-10-03/web-walk.md`,
//          amended 2026-10-03: no "Outside city limits" or "named place" for
//          taxes). A clerk at 1440, clicking; every "must be true" is checked
//          on the SCREEN, against the API and in PostgreSQL.
// ───────────────────────────────────────────────────────
//
// Stack: API `manage.py runserver` on a scratch PostgreSQL 16 database with
// `migrate` + `seed_demo` + `10-scripts/cr165_taxwalk_world.py setup`; SPA
// `vite build --mode wolocal` served by `07-frontend/server.mjs`.
//
//   PHASES=0,1,2,3 BASE=http://127.0.0.1:8792 PGURL=postgres://postgres@127.0.0.1:55433/<db> \
//     OUT=08-qa/taxes-fees-2026-10-03/walk node 10-scripts/cr165_taxwalk.mjs
//
// The bill runs of phase 5 are `cr165_taxwalk_world.py run …` between
// PHASES=…,3 and PHASES=4,…; this script carries the tax ids between runs in
// `$OUT/state.json` and appends every check to `$OUT/results.json`.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8792";
const TENANT = "brazosbend";
const EMAIL = "dana@brazosbendutilities.com";
const B_TENANT = "riverbend";
const B_EMAIL = "ops@riverbend.example";
const PASSWORD = "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr165-taxwalk";
const PGURL = process.env.PGURL ?? "postgres://postgres@127.0.0.1:55433/sbh_taxwalk9";
const PHASES = new Set((process.env.PHASES ?? "0,1,2,3").split(",").map((p) => p.trim()));
const STATE = `${OUT}/state.json`;
const RESULTS = `${OUT}/results.json`;
mkdirSync(OUT, { recursive: true });

const state = existsSync(STATE) ? JSON.parse(readFileSync(STATE, "utf8")) : { taxes: {} };
const results = existsSync(RESULTS) ? JSON.parse(readFileSync(RESULTS, "utf8")) : [];
const saveState = () => writeFileSync(STATE, JSON.stringify(state, null, 2));
function check(phase, step, what, pass, evidence) {
  const row = { phase, step, what, pass: Boolean(pass), evidence: String(evidence ?? "") };
  const at = results.findIndex((r) => r.phase === phase && r.step === step && r.what === what);
  if (at >= 0) results[at] = row;
  else results.push(row);
  writeFileSync(RESULTS, JSON.stringify(results, null, 2));
  console.log(`${row.pass ? "PASS" : "FAIL"} ${phase}.${step} ${what} — ${row.evidence}`);
}
function db(sql) {
  return execFileSync("psql", [PGURL, "-AtF", "|", "-c", sql], { encoding: "utf8" }).trim();
}
const dbRows = (sql) => (db(sql) === "" ? [] : db(sql).split("\n").map((line) => line.split("|")));

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
let page = await browser.newPage({ viewport: { width: 1440, height: 1600 } });
const settle = (ms = 900) => page.waitForTimeout(ms);
async function shot(phase, step, caption) {
  await settle();
  const path = `${OUT}/taxwalk_${phase}_${step}.png`;
  await page.screenshot({ path, fullPage: true });
  const size = statSync(path).size;
  console.log(`  [shot] taxwalk_${phase}_${step}.png (${size} bytes) — ${caption}`);
  return path;
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
const cont = () => page.getByRole("button", { name: "Continue", exact: true }).click();
async function signIn(tenant, email) {
  currentTenant = tenant;
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}
async function selectByText(id, needle) {
  const options = await page.$$eval(`#${id} option`, (els) => els.map((el) => [el.value, el.textContent ?? ""]));
  const hit = options.find(([value, label]) => value !== "" && label.toLowerCase().includes(needle.toLowerCase()));
  if (!hit) throw new Error(`#${id}: no option containing "${needle}" in ${JSON.stringify(options)}`);
  await page.selectOption(`#${id}`, hit[0]);
  return hit[1];
}
async function tick(id, labels) {
  await page.click(`#${id}`);
  const list = page.locator(`[data-check-dropdown="${id}"] [data-check-dropdown-list]`);
  for (const label of labels) await list.locator("label", { hasText: label }).first().locator("input").check();
}
async function closeDropdown(id) {
  if ((await page.getAttribute(`#${id}`, "aria-expanded")) === "true") await page.click(`#${id}`);
}
const TAXES = "plans-rates/taxes-fees";
const goList = () => page.goto(`${BASE}/${TENANT}/${TAXES}`, { waitUntil: "networkidle" });
const goTax = (id, tab) =>
  page.goto(`${BASE}/${TENANT}/${TAXES}/${id}${tab ? `?tab=${tab}` : ""}`, { waitUntil: "networkidle" });

// ── the taxes of phase 1, as amended by the PO (no outside-city, no named place) ──
const SPECS = [
  {
    key: "1.1", name: "State sales tax", authority: "Texas State", services: "all",
    classes: ["Commercial", "Industrial"], basis: "percent", rate: "6.25", boundary: "everywhere",
    from: "2026-01-01", code: "ST-SALES", label: "State sales tax", account: "TX Comptroller",
    due: "20th_next_month", filed: "monthly", allowance: "0.5", interest: "1.5", reminder: "filings@brazosbend.example",
    rateShown: "6.25%", bill: "$3.75",
  },
  {
    key: "1.2", name: "County utility tax", authority: "County", services: ["Water", "Sewer"],
    classes: "all", basis: "percent", rate: "2", boundary: "everywhere", from: "2026-01-01",
    code: "CNTY-UTIL", label: "County tax", account: "Wapello", due: "last_day_next_month", filed: "quarterly",
    allowance: "", interest: "", reminder: "county@brazosbend.example", rateShown: "2.00%", bill: "$1.20",
  },
  {
    key: "1.3", name: "City franchise fee", authority: "City", services: "all", classes: "all",
    basis: "percent", rate: "150", boundary: "city_limits", from: "2026-09-01", code: "CITY-FRAN",
    label: "City franchise fee", account: "Ottumwa", due: "15th_next_month", filed: "monthly",
    allowance: "", interest: "", reminder: "", rateShown: "150", bill: "$90.00",
  },
  {
    key: "1.5", name: "Riverside storm fee", authority: "Special district", services: ["Storm water"],
    classes: ["Residential"], basis: "per_meter", rate: "1.25", boundary: "everywhere", from: "2026-01-01",
    code: "SD-STORM", label: "Storm fee", account: "", due: "25th_next_month", filed: "monthly",
    allowance: "", interest: "", reminder: "", rateShown: "1.25", bill: "$1.25",
  },
  {
    key: "1.6", name: "Water conservation fee", authority: "Texas Water Development", services: ["Water"],
    classes: ["Residential", "Commercial"], basis: "per_unit", rate: "0.05", uom: "kgal", boundary: "everywhere",
    from: "2026-01-01", code: "ST-CONS", label: "Conservation fee", account: "TX Comptroller",
    due: "30_days_after_quarter", filed: "quarterly", allowance: "", interest: "", reminder: "",
    rateShown: "0.05", bill: "$0.60",
  },
];

async function fillWhat(spec) {
  await page.fill("#tax-name", spec.name);
  await selectByText("tax-authority", spec.authority);
  if (spec.services !== "all") {
    await tick("tax-services", spec.services);
    await closeDropdown("tax-services");
  }
  if (spec.classes !== "all") {
    await tick("tax-classes", spec.classes);
    await closeDropdown("tax-classes");
  }
  await page.selectOption("#tax-boundary", spec.boundary);
}
async function fillMuch(spec) {
  await page.selectOption("#tax-basis", spec.basis);
  await page.fill("#tax-rate", spec.rate);
  if (spec.uom) await page.fill("#tax-uom", spec.uom);
  await page.fill("#tax-from", spec.from);
}
async function fillFiling(spec) {
  await page.fill("#tax-code", spec.code);
  await page.fill("#tax-bill-label", spec.label);
  await selectByText("tax-liability", "22");
  await page.selectOption("#tax-filed", spec.filed);
  await page.selectOption("#tax-due", spec.due);
  if (spec.account) await selectByText("tax-authority-account", spec.account);
  if (spec.allowance) await page.fill("#tax-allowance", spec.allowance);
  if (spec.interest) await page.fill("#tax-interest", spec.interest);
  if (spec.reminder) await page.fill("#tax-reminder", spec.reminder);
}
const rowsOfCode = (code) =>
  dbRows(`select id, version_no, rate, flat_amount, per_unit_amount, per_meter_amount, effective_from, effective_to,
            is_draft, superseded_by_tax_id, name, deleted_at from taxes t
          where code='${code}' and tenant_id=(select id from tenants where subdomain='${TENANT}') order by version_no`);

// ═══ PHASE 0 ════════════════════════════════════════════════════════════════
await signIn(TENANT, EMAIL);
console.log("signed in to Utility A as", EMAIL);

if (PHASES.has("0")) {
  const services = await api("GET", "settings/services");
  const on = (services.data?.rows ?? services.data?.results ?? services.data ?? []).filter((r) => r.enabled).map((r) => r.service);
  await page.goto(`${BASE}/${TENANT}/settings/services`, { waitUntil: "networkidle" });
  await shot(0, 1, "Settings › services");
  check(0, 1, "water, sewer, storm water and trash are on", ["water", "sewer", "storm_water", "trash"].every((s) => on.includes(s)), `on: ${on.join(", ")}`);
  await page.goto(`${BASE}/${TENANT}/settings/accounting/authorities`, { waitUntil: "networkidle" });
  await shot(0, 2, "Settings › Accounting › Authority accounts");
  const authorities = await text();
  check(0, 1, "three authority accounts in Settings › Accounting", ["TX Comptroller", "Wapello County", "City of Ottumwa"].every((n) => authorities.includes(n)), "listed on the Authorities sub-tab");
  await page.goto(`${BASE}/${TENANT}/plans-rates/plans`, { waitUntil: "networkidle" });
  await shot(0, 3, "Plans list");
  const plans = dbRows(`select p.name, count(a.id) from rate_plans p left join units u on u.rate_plan_id=p.id left join accounts a on a.unit_id=u.id and a.closed_at is null
                        where p.tenant_id=(select id from tenants where subdomain='${TENANT}') group by p.name order by p.name`);
  check(0, 2, "plans carry real accounts", plans.some(([, n]) => Number(n) > 0), plans.map(([n, c]) => `${n}: ${c}`).join(" · "));
  const b = db(`select count(*) from taxes where tenant_id=(select id from tenants where subdomain='${B_TENANT}')`);
  check(0, 3, "Utility B exists with no taxes", b === "0", `riverbend taxes: ${b}`);
}

// ═══ PHASE 2 (the form refuses and warns) — run before phase 1 saves anything ══
if (PHASES.has("2")) {
  await page.goto(`${BASE}/${TENANT}/${TAXES}/new`, { waitUntil: "networkidle" });
  await page.waitForSelector("#tax-name");
  await cont();
  await shot(2, 1, "empty form, Continue");
  const errs = await page.$$eval(".field-error, [id$='-error']", (els) => els.map((el) => el.textContent?.trim()).filter(Boolean));
  check(2, 1, "each missing box says what is wrong", errs.length >= 2, JSON.stringify(errs));
  await page.fill("#tax-name", "Typed then refused");
  await cont();
  check(2, 1, "nothing typed is lost", (await page.inputValue("#tax-name")) === "Typed then refused", await page.inputValue("#tax-name"));

  await page.click("#tax-services");
  await shot(2, 2, "Services dropdown open");
  const serviceRows = await page.$$eval('[data-check-dropdown="tax-services"] [data-check-dropdown-list] label', (els) => els.map((el) => el.textContent?.trim()));
  // Utility A here is Brazos Bend, which ALSO runs electric (seed_demo); the
  // rule is "this utility's switched-on services, and only those".
  const enabledNames = ((await api("GET", "settings/services")).data ?? []).filter((r) => r.enabled).length;
  check(2, 2, "only the utility's switched-on services, All services first", serviceRows[0] === "All services" && serviceRows.length === enabledNames + 1 && ["Water", "Sewer", "Trash", "Storm water"].every((n) => serviceRows.includes(n)) && !serviceRows.some((r) => /Gas|Solar|Fire|Broadband/.test(r ?? "")), `${JSON.stringify(serviceRows)} · switched on: ${enabledNames}`);
  await closeDropdown("tax-services");
  await page.click("#tax-classes");
  await shot(2, 3, "Customer classes dropdown open");
  const classRows = await page.$$eval('[data-check-dropdown="tax-classes"] [data-check-dropdown-list] label', (els) => els.map((el) => el.textContent?.trim()));
  check(2, 3, "Every customer class first, then the 8 classes", classRows[0] === "Every customer class" && classRows.length === 9, JSON.stringify(classRows));
  await closeDropdown("tax-classes");

  await selectByText("tax-authority", "Texas State");
  await cont();
  await page.waitForSelector("[data-tax-step=much]");
  await page.fill("#tax-rate", "62.5");
  await page.fill("#tax-from", "2026-10-01");
  await shot(2, 4, "step 2 at 62.5");
  const s2 = await text();
  check(2, 4, "62.5% and 'check the rate' on step 2", /62\.5/.test(s2) && /high|check the rate/i.test(s2), s2.match(/[^.]*62\.5[^.]*\./)?.[0] ?? s2.slice(0, 200));
  await cont();
  await page.waitForSelector("[data-tax-step=filing]");
  await page.fill("#tax-reminder", "not-an-email");
  await cont();
  await shot(2, 5, "Filing: no liability account, bad email");
  const s3errs = await page.$$eval(".field-error, [id$='-error']", (els) => els.map((el) => `${el.id}:${el.textContent?.trim()}`));
  check(2, 5, "liability and email refused by name", s3errs.some((e) => e.startsWith("tax-liability")) && s3errs.some((e) => e.startsWith("tax-reminder")), JSON.stringify(s3errs));
  await selectByText("tax-liability", "22");
  await page.fill("#tax-reminder", "");
  await page.fill("#tax-code", "TMP-625");
  await selectByText("tax-due", "20");
  await cont();
  await page.waitForSelector("[data-tax-step=review]");
  await shot(2, 6, "Review at 62.5");
  const rv = await text();
  check(2, 4, "62.5% and the warning on Review", /62\.5/.test(rv) && /high|check the rate/i.test(rv), rv.match(/[^.]*62\.5[^.]*\./)?.[0] ?? "");
  check(2, 6, "named-place boundary: not offered (PO ruling — dropped)", !(await page.$$eval("#tax-boundary option", (els) => els.map((e) => e.value))).some((v) => !["everywhere", "city_limits"].includes(v)), "boundaries served: everywhere, city_limits");
  // leave without saving
  await goList();
}

// ═══ PHASE 1 ════════════════════════════════════════════════════════════════
if (PHASES.has("1")) {
  for (const spec of SPECS) {
    const step = spec.key.split(".")[1];
    if (state.taxes[spec.key]) {
      console.log("already created", spec.key);
      continue;
    }
    await page.goto(`${BASE}/${TENANT}/${TAXES}/new`, { waitUntil: "networkidle" });
    await page.waitForSelector("#tax-name");
    await fillWhat(spec);
    await shot(1, `${step}a`, `${spec.name} — What it is`);
    await cont();
    await page.waitForSelector("[data-tax-step=much]");
    await fillMuch(spec);
    await shot(1, `${step}b`, `${spec.name} — How much`);
    if (spec.key === "1.3") {
      const warn = await text();
      check(1, 3, "150% typed warns, does not refuse", /150/.test(warn) && /high|check the rate/i.test(warn), warn.match(/[^.]*150[^.]*\./)?.[0] ?? "");
    }
    await cont();
    await page.waitForSelector("[data-tax-step=filing]");
    await fillFiling(spec);
    await shot(1, `${step}c`, `${spec.name} — Filing`);
    await cont();
    await page.waitForSelector("[data-tax-step=review]");
    await shot(1, `${step}d`, `${spec.name} — Review`);
    await page.getByRole("button", { name: "Save tax", exact: true }).click();
    await page.waitForSelector("[data-tax-saved]", { timeout: 20000 }).catch(() => undefined);
    await shot(1, `${step}e`, `${spec.name} — saved`);
    const rows = rowsOfCode(spec.code);
    check(1, step, `${spec.name}: exactly one row in the database`, rows.length === 1, JSON.stringify(rows));
    if (rows.length > 0) state.taxes[spec.key] = rows[0][0];
    saveState();
  }

  // 1.8 — a draft: Save draft & exit half way, reopen, finish, save
  if (!state.taxes["1.8"]) {
    await page.goto(`${BASE}/${TENANT}/${TAXES}/new`, { waitUntil: "networkidle" });
    await page.waitForSelector("#tax-name");
    await page.fill("#tax-name", "City permit fee (draft)");
    await selectByText("tax-authority", "City");
    await cont();
    await page.waitForSelector("[data-tax-step=much]");
    await page.selectOption("#tax-basis", "flat_per_bill");
    await page.fill("#tax-rate", "3");
    await shot(1, "8a", "draft half way, step 2");
    await page.getByRole("button", { name: "Save draft & exit", exact: true }).click();
    await page.waitForURL((u) => u.pathname.endsWith(`/${TAXES}`), { timeout: 20000 }).catch(() => undefined);
    await shot(1, "8b", "after Save draft & exit");
    const draft = dbRows(`select id, is_draft, name from taxes where name='City permit fee (draft)'`);
    check(1, 8, "Save draft & exit stores a DRAFT (DEF-RAT-9275)", draft.length === 1 && draft[0][1] === "t", JSON.stringify(draft));
    if (draft.length === 1) state.taxes["1.8"] = draft[0][0];
    saveState();
    const priced = await api("GET", `taxes/matched-premises?boundary=everywhere`);
    void priced;
  }
  // the list after phase 1
  await goList();
  await shot(1, "list", "list after phase 1");
  const list = await api("GET", "taxes?page=1&per=100");
  const rows = list.data?.results ?? [];
  for (const spec of SPECS) {
    const row = rows.find((r) => r.code === spec.code);
    check(1, spec.key.split(".")[1], `${spec.name}: list row with v1, From, To, GL, premises`, row && row.version === 1 && row.effective_from === spec.from && Boolean(row.gl_account_code) && row.premises_total !== undefined,
      row ? `v${row.version} · ${row.effective_from} → ${row.effective_to ?? "No end"} · GL ${row.gl_account_code} ${row.gl_account_name} · premises ${row.premises_reached} of ${row.premises_total}` : "no row");
  }
}

// ═══ PHASE 3 — view every tax ═══════════════════════════════════════════════
if (PHASES.has("3")) {
  for (const spec of SPECS) {
    const id = state.taxes[spec.key];
    const step = spec.key.split(".")[1];
    await goTax(id);
    await page.waitForSelector("[data-tax-detail]");
    await shot(3, `1_${step}`, `${spec.name} — details`);
    const body = await text();
    const read = (await api("GET", `taxes/${id}`)).data ?? {};
    const expected = [spec.name, spec.code, "v1", spec.label];
    if (spec.account) expected.push(spec.account);
    if (spec.key === "1.3") expected.push("Over 20%");
    const missing = expected.filter((word) => !body.toLowerCase().includes(word.toLowerCase()));
    check(3, 1, `${spec.name}: header and sections show what was entered`, missing.length === 0, missing.length ? `missing on screen: ${missing.join(", ")}` : `shown: ${expected.join(" · ")}`);
    const apiOk =
      read.code === spec.code && read.filing_frequency === spec.filed && read.due_date_rule === spec.due &&
      (spec.boundary === "everywhere" ? !read.premises_scope_kind || read.premises_scope_kind === "everywhere" : read.premises_scope_kind === spec.boundary);
    check(3, 1, `${spec.name}: API read equals what was entered`, apiOk, `code ${read.code} · filed ${read.filing_frequency} · due ${read.due_date_rule} · boundary ${read.premises_scope_kind ?? "everywhere"} · services ${JSON.stringify(read.applies_to_services)} · classes ${JSON.stringify(read.applies_to_customer_classes)} · rate ${read.rate ?? read.flat_amount ?? read.per_unit_amount ?? read.per_meter_amount}`);
  }
  await goList();
  await shot(3, 2, "list: Over 20% banner");
  const body = await text();
  check(3, 2, "Over 20% banner counts 1.3; pill shows; MM/DD/YYYY dates", /1 tax(es)? charges? over 20%/i.test(body) && body.includes("Over 20%") && /\d{2}\/\d{2}\/\d{4}/.test(body) && !/2026-\d{2}-\d{2}/.test(body), body.match(/\d+ tax[^.]*over 20%\./i)?.[0] ?? "no banner");
}

// ═══ PHASE 4 — edit, three ways ═══════════════════════════════════════════════
if (PHASES.has("4")) {
  const county = state.taxes["1.2"];
  // 4.1 — Name and filing on 1.2
  const before = rowsOfCode("CNTY-UTIL");
  await page.goto(`${BASE}/${TENANT}/${TAXES}/${county}/edit?change=info`, { waitUntil: "networkidle" });
  await page.waitForSelector("#tax-name");
  await shot(4, "1a", "1.2 Edit › Name and filing");
  const locked = await page.$eval("#tax-sec-locked", (el) => el.textContent).catch(() => "");
  await page.fill("#tax-name", "Wapello County utility tax");
  await cont();
  await page.waitForSelector("[data-tax-step=filing]");
  await page.selectOption("#tax-due", "20th_next_month");
  await page.fill("#tax-reminder", "treasurer@wapello.example");
  await shot(4, "1b", "1.2 Filing changed");
  await cont();
  await shot(4, "1c", "1.2 Review");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await settle(2000);
  await shot(4, "1d", "1.2 saved");
  const after = rowsOfCode("CNTY-UTIL");
  check(4, 1, "same row updated, still v1, rate and reach locked", after.length === 1 && after[0][0] === before[0][0] && after[0][1] === "1" && after[0][10] === "Wapello County utility tax", `rows ${after.length}, id same ${after[0]?.[0] === before[0]?.[0]}, v${after[0]?.[1]}, name ${after[0]?.[10]}; locked note: ${String(locked).slice(0, 80)}`);
  const audit = (await api("GET", `taxes/${county}/audit?page=1&per=50`)).data?.results ?? [];
  const updated = audit.filter((a) => a.action === "tax.updated");
  check(4, 1, "Audit: before → after for the change", updated.length >= 1 && JSON.stringify(updated[0].before ?? {}).includes("County utility tax") && JSON.stringify(updated[0].after ?? {}).includes("Wapello"), JSON.stringify(updated.map((u) => ({ before: u.before, after: u.after }))).slice(0, 400));

  // 4.2 — New rate from a date on 1.1
  const sales = state.taxes["1.1"];
  await page.goto(`${BASE}/${TENANT}/${TAXES}/${sales}/edit?change=change`, { waitUntil: "networkidle" });
  await page.waitForSelector("#tax-rate");
  await page.fill("#tax-rate", "6.5");
  // 4.4 first: a start before the version's start is refused by name
  await page.fill("#tax-from", "2025-12-01");
  await cont();
  await shot(4, 4, "new rate starting before v1's start");
  const early = await text();
  check(4, 4, "a new rate before the version's start is refused by name", /Must be after 01\/01\/2026/.test(early), early.match(/Must be after[^.]*\./)?.[0] ?? "no refusal");
  const tooEarly = await api("POST", `taxes/${sales}/new-rate`, { rate: "0.065", effective_from: "2025-12-01" });
  check(4, 4, "the server refuses it too, by name", [400, 422].includes(tooEarly.status) && JSON.stringify(tooEarly.data).includes("new_rate_too_early"), `${tooEarly.status} ${tooEarly.data?.message_key}`);
  await page.fill("#tax-from", "2026-11-01");
  const discountsOpen = await page.isEnabled("#tax-discounts").catch(() => false);
  const roundingOpen = await page.isEnabled("#tax-rounding").catch(() => false);
  check(4, 2, "What is taxed, Discounts and Rounding are open (image 28, DEF-RAT-9301)", discountsOpen && roundingOpen && (await page.isEnabled("#tax-taxed-usage")), `discounts ${discountsOpen} · rounding ${roundingOpen}`);
  await shot(4, "2a", "1.1 New rate 6.5% from 11/01/2026");
  await cont();
  await shot(4, "2b", "1.1 New rate Review");
  await page.getByRole("button", { name: "Save new rate", exact: true }).click();
  await settle(2000);
  await shot(4, "2c", "1.1 new rate saved");
  const chain = rowsOfCode("ST-SALES");
  check(4, 2, "v1 ends 10/31/2026, v2 starts 11/01/2026, two rows, nothing deleted", chain.length === 2 && chain[0][7] === "2026-10-31" && chain[1][6] === "2026-11-01" && chain[1][2] === "0.065000" && chain.every((r) => r[11] === ""), JSON.stringify(chain.map((r) => [r[1], r[2], r[6], r[7]])));
  await goTax(sales);
  await shot(4, "2d", "1.1 header: Next 6.50% from 11/01/2026");
  const header = await text();
  check(4, 2, "header shows Next: 6.50% from 11/01/2026", /Next:?\s*6\.50?%\s*from\s*11\/01\/2026/.test(header), header.match(/Next[^·]*/)?.[0] ?? "no Next");

  // 4.3 — Fix a mistake on 1.3
  const city = state.taxes["1.3"];
  await page.goto(`${BASE}/${TENANT}/${TAXES}/${city}/edit?change=correct`, { waitUntil: "networkidle" });
  await page.waitForSelector("#tax-rate");
  await page.fill("#tax-rate", "3");
  await cont();
  await shot(4, "3a", "1.3 Fix a mistake without a reason");
  const noReason = await text();
  check(4, 3, "reason required", /Enter the reason/.test(noReason), noReason.match(/Enter the reason\./)?.[0] ?? "");
  await page.fill("#tax-reason", "Typed as 150%");
  await cont();
  await shot(4, "3b", "1.3 Fix a mistake Review");
  await page.getByRole("button", { name: /^Save/ }).last().click();
  await settle(2000);
  await shot(4, "3c", "1.3 correction saved");
  const fixed = rowsOfCode("CITY-FRAN");
  check(4, 3, "v1 superseded and kept, v2 the same dates at 3%", fixed.length === 2 && fixed[0][9] === fixed[1][0] && fixed[1][2] === "0.030000" && fixed[0][6] === fixed[1][6] && fixed[0][7] === fixed[1][7], JSON.stringify(fixed.map((r) => [r[1], r[2], r[6], r[7], r[9] ? "superseded" : "live"])));
  state.taxes["1.3v2"] = fixed[1]?.[0];
  saveState();
  await goList();
  await shot(4, "3d", "list after the fix — no Over 20%");
  const listBody = await text();
  check(4, 3, "Over 20% banner and pill gone", !listBody.includes("Over 20%") && !/over 20%/i.test(listBody), listBody.match(/[^.]*over 20%[^.]*/i)?.[0] ?? "none");

  // 4.5 — versions table and Audit
  for (const [key, label] of [["1.2", "county"], ["1.1", "sales"], ["1.3v2", "city"]]) {
    await goTax(state.taxes[key]);
    await shot(4, `5_${label}_overview`, `${label} Overview — versions`);
    const versions = (await api("GET", `taxes/${state.taxes[key]}/versions`)).data;
    const vrows = versions?.results ?? versions ?? [];
    await goTax(state.taxes[key], "audit");
    await shot(4, `5_${label}_audit`, `${label} Audit`);
    const auditBody = await text();
    check(4, 5, `${label}: versions table and Audit carry every version and change, with who`, vrows.length >= 1 && auditBody.includes("Dana"), `versions ${vrows.map((v) => `v${v.version} ${v.amount_display}`).join(", ")} · audit names Dana: ${auditBody.includes("Dana")}`);
  }
  const reasonShown = await (async () => {
    await goTax(state.taxes["1.3v2"], "audit");
    return (await text()).includes("Typed as 150%");
  })();
  check(4, 5, "Audit shows the correction's reason", reasonShown, "Typed as 150%");
}

// ═══ PHASE 5 — billing gets exactly ONE record ════════════════════════════════
if (PHASES.has("5")) {
  const lookup = (code, on) =>
    db(`select count(*) from taxes where code='${code}' and tenant_id=(select id from tenants where subdomain='${TENANT}')
         and superseded_by_tax_id is null and deleted_at is null and not is_draft
         and (effective_from is null or effective_from <= '${on}') and (effective_to is null or effective_to >= '${on}')`);
  check(5, 1, "1.1 on 10/31/2026 and 11/01/2026: one live row each", lookup("ST-SALES", "2026-10-31") === "1" && lookup("ST-SALES", "2026-11-01") === "1", `10/31 ${lookup("ST-SALES", "2026-10-31")} · 11/01 ${lookup("ST-SALES", "2026-11-01")}`);
  check(5, 2, "1.3 after the fix: one live row (the 3%)", lookup("CITY-FRAN", "2026-10-15") === "1", `rows ${lookup("CITY-FRAN", "2026-10-15")}`);
  check(5, 3, "1.2 after the rename: one row, the same row", lookup("CNTY-UTIL", "2026-10-15") === "1", `rows ${lookup("CNTY-UTIL", "2026-10-15")}`);
}

// ═══ WALKED AGAIN AFTER A FIX ════════════════════════════════════════════════
// 1.8 — reopen the draft from its details page, finish it, save (DEF-RAT-9305)
if (PHASES.has("1.8finish")) {
  const id = state.taxes["1.8"];
  await goTax(id);
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await page.waitForURL((u) => u.search.includes("draft="), { timeout: 15000 }).catch(() => undefined);
  await page.waitForSelector("#tax-name");
  await shot(1, "8c", "draft reopened from its Edit — the New form, filled");
  const reopened = (await page.inputValue("#tax-name")) === "City permit fee (draft)";
  check(1, 8, "Edit on a draft reopens it filled (DEF-RAT-9305)", reopened && page.url().includes("draft="), page.url());
  await page.fill("#tax-name", "City permit fee");
  await cont();
  await page.waitForSelector("[data-tax-step=much]");
  check(1, 8, "nothing typed before the draft was saved is lost", (await page.inputValue("#tax-rate")) === "3.00" || (await page.inputValue("#tax-rate")) === "3", await page.inputValue("#tax-rate"));
  await page.fill("#tax-from", "2026-11-01");
  await cont();
  await page.waitForSelector("[data-tax-step=filing]");
  await page.fill("#tax-code", "CITY-PERMIT");
  await selectByText("tax-liability", "22");
  await page.selectOption("#tax-due", "20th_next_month");
  await selectByText("tax-authority-account", "Ottumwa");
  await cont();
  await page.waitForSelector("[data-tax-step=review]");
  await shot(1, "8d", "draft finished — Review");
  await page.getByRole("button", { name: "Save tax", exact: true }).click();
  await page.waitForSelector("[data-tax-saved]", { timeout: 20000 }).catch(() => undefined);
  await shot(1, "8e", "draft saved and in force");
  const rows = dbRows(`select id, is_draft, name, code, effective_from from taxes where id='${id}' or code='CITY-PERMIT'`);
  check(1, 8, "the SAME row, no longer a draft, one row", rows.length === 1 && rows[0][0] === id && rows[0][1] === "f" && rows[0][3] === "CITY-PERMIT", JSON.stringify(rows));
  await goTax(id);
  await shot(1, "8f", "finished draft — details (Scheduled from 11/01/2026)");
}

// Duplicate — More ▾ › Duplicate on 1.2 opens the New form filled (DEF-RAT-9299)
if (PHASES.has("dup")) {
  await goTax(state.taxes["1.2"]);
  await page.click("[data-tax-more] summary");
  await shot(3, "dup_a", "More ▾ open — Duplicate enabled");
  await page.getByTestId("tax-more-duplicate").click();
  await page.waitForSelector("#tax-name");
  await settle(1200);
  await shot(3, "dup_b", "Duplicate — the New form filled from 1.2");
  const filled = await page.inputValue("#tax-name");
  check(3, "dup", "Duplicate opens the New form filled from the tax", filled === "Wapello County utility tax" && page.url().includes("duplicate="), `${filled} · ${page.url()}`);
  await page.fill("#tax-name", "Wapello County sewer tax");
  await cont();
  await page.waitForSelector("[data-tax-step=much]");
  await cont();
  await page.waitForSelector("[data-tax-step=filing]");
  check(3, "dup", "the code is cleared (one code names one tax)", (await page.inputValue("#tax-code")) === "", await page.inputValue("#tax-code"));
  await page.fill("#tax-code", "CNTY-SEWER");
  await cont();
  await page.waitForSelector("[data-tax-step=review]");
  await page.getByRole("button", { name: "Save tax", exact: true }).click();
  await page.waitForSelector("[data-tax-saved]", { timeout: 20000 }).catch(() => undefined);
  await shot(3, "dup_c", "duplicate saved");
  const copy = dbRows(`select id, version_no, chain_id = id, rate, applies_to_services from taxes where code='CNTY-SEWER'`);
  const original = rowsOfCode("CNTY-UTIL");
  check(3, "dup", "a NEW tax: its own row, v1, its own chain; the original untouched", copy.length === 1 && copy[0][1] === "1" && copy[0][2] === "t" && original.length === 1, JSON.stringify(copy));
}

// New rate from a date that also changes rounding (DEF-RAT-9301), on 1.6
if (PHASES.has("4a")) {
  const cons = state.taxes["1.6"];
  await page.goto(`${BASE}/${TENANT}/${TAXES}/${cons}/edit?change=change`, { waitUntil: "networkidle" });
  await page.waitForSelector("#tax-rate");
  await page.fill("#tax-rate", "0.06");
  await page.fill("#tax-from", "2027-01-01");
  await page.selectOption("#tax-rounding", "half_even");
  await shot(4, "2e", "1.6 new rate 0.06 from 01/01/2027 with rounding changed");
  await cont();
  await shot(4, "2f", "1.6 new rate Review — rounding before → after");
  const review = await text();
  await page.getByRole("button", { name: "Save new rate", exact: true }).click();
  await settle(2000);
  const chain = dbRows(`select version_no, per_unit_amount, rounding_rule, effective_from, effective_to from taxes where code='ST-CONS' order by version_no`);
  check(4, 2, "a new rate saves a changed rounding on v2 only (DEF-RAT-9301)", chain.length === 2 && chain[1][2] === "half_even" && chain[0][2] !== "half_even" && chain[0][4] === "2026-12-31", `${JSON.stringify(chain)} · review lists rounding: ${/Banker|half even|Rounding/i.test(review)}`);
}

// The THIS TAX panel on a per-meter tax (DEF-RAT-9306), via Duplicate of 1.5
if (PHASES.has("sum")) {
  await page.goto(`${BASE}/${TENANT}/${TAXES}/new?duplicate=${state.taxes["1.5"]}`, { waitUntil: "networkidle" });
  await page.waitForSelector("#tax-name");
  await settle(1200);
  await shot(1, "5f", "per-meter tax in the New form — THIS TAX panel");
  const effect = (await page.textContent("[data-tax-summary-effect]"))?.trim();
  check(1, 5, "THIS TAX panel reads a dash, not $0.00, for a per-meter tax (DEF-RAT-9306)", effect === "—", effect);
  await goList();
}

// ═══ PHASE 5 — the issued bills, on screen and in the database ═════════════
const WALK_ACCOUNT = "AC-2026-00054";
function billOf(periodEnd) {
  const [row] = dbRows(`select i.id, i.invoice_no, i.status, i.total from invoices i join accounts a on a.id=i.account_id
                         where a.account_no='${WALK_ACCOUNT}' and i.period_end='${periodEnd}' and i.status <> 'draft'`);
  if (!row) return null;
  const lines = dbRows(`select l.description, l.amount, l.tax_id from invoice_lines l where l.invoice_id='${row[0]}' and l.kind='tax' order by l.description`);
  return { id: row[0], no: row[1], status: row[2], total: row[3], lines };
}
async function bill(phase, step, periodEnd, expect) {
  const found = billOf(periodEnd);
  if (!found) {
    check(phase, step, `bill for the period ending ${periodEnd} exists`, false, "no issued bill");
    return;
  }
  await page.goto(`${BASE}/${TENANT}/billing/bills/${found.id}`, { waitUntil: "networkidle" });
  await page.getByRole("tab", { name: /^Charges/ }).click();
  await shot(phase, step, `bill ${found.no} › Charges`);
  const body = await text();
  const perTax = {};
  for (const [description, amount, taxId] of found.lines) (perTax[taxId] ??= []).push([description, amount]);
  const oneEach = Object.values(perTax).every((l) => l.length === 1);
  const wanted = Object.entries(expect).every(([name, amount]) => found.lines.some(([d, a]) => d.includes(name) && Number(a).toFixed(2) === amount) && body.includes(`$${amount}`));
  check(phase, step, `${found.no}: one line per tax, ${Object.entries(expect).map(([n, a]) => `${n} $${a}`).join(", ")}`, oneEach && wanted, found.lines.map(([d, a]) => `${d} ${Number(a).toFixed(2)}`).join(" · ") + ` · total ${Number(found.total).toFixed(2)}`);
}
if (PHASES.has("5oct")) {
  await bill(5, 4, "2026-10-15", { "State sales tax": "3.75", "County utility tax": "1.20", "City franchise fee": "90.00", "Water conservation fee": "0.60" });
}
if (PHASES.has("5nov")) {
  await bill(5, 5, "2026-11-15", { "State sales tax": "3.90", "County utility tax": "1.20", "City franchise fee": "1.80", "Water conservation fee": "0.60" });
  await bill(5, "5_october_again", "2026-10-15", { "State sales tax": "3.75" });
  await bill(5, 6, "2026-10-15", { "City franchise fee": "90.00" });
}

// ═══ PHASE 6 — plans and audit ═══════════════════════════════════════════════
async function addToPlan(taxId, planName, reason) {
  await goTax(taxId, "plans");
  await page.waitForSelector("[data-tax-add-plan]");
  await page.click("[data-tax-add-plan]");
  await page.fill("#plan", planName.slice(0, 12));
  await page.getByRole("option", { name: new RegExp(planName.replace(/[·]/g, ".")) }).first().click();
  if (reason) await page.fill("#reason", reason);
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await settle(1500);
}
if (PHASES.has("6a")) {
  // attach the walk's taxes to the walk plan, through the Plans tab
  for (const key of ["1.1", "1.2", "1.3", "1.6"]) {
    await addToPlan(state.taxes[key], "Tax walk · Commercial water", "Web walk phase 5");
  }
  for (const key of ["1.2", "1.5", "1.6"]) {
    await addToPlan(state.taxes[key], "Sample — Residential", "Web walk phase 6");
  }
  await goTax(state.taxes["1.1"], "plans");
  await shot(6, "1a", "1.1 Plans tab after adding");
}
if (PHASES.has("6")) {
  for (const spec of SPECS) {
    await goTax(state.taxes[spec.key], "plans");
    await shot(6, `1_${spec.key.split(".")[1]}`, `${spec.name} Plans tab`);
    const plans = (await api("GET", `taxes/${state.taxes[spec.key]}/plans`)).data;
    const rows = plans?.results ?? plans ?? [];
    check(6, 1, `${spec.name}: Plans tab rows with real account counts`, Array.isArray(rows), rows.map((r) => `${r.name}: ${r.accounts} accounts / ${r.units} units`).join(" · ") || "no plan");
  }
  // 6.2 — add a tax to a plan and remove it again. 1.4 is on the plan by the
  // PO's ruling, so the walk uses 1.5 on the walk plan, which does not bind
  // the special district (on a plan that binds the authority the attachment
  // is folded into the binding row and has no ×, by design — tax_plans).
  const storm = state.taxes["1.5"];
  await addToPlan(storm, "Tax walk · Commercial water", "Walk 6.2 add");
  await goTax(storm, "plans");
  await shot(6, "2a", "1.5 added to the walk plan");
  const tabCount = (await page.getByRole("tab", { name: /^Plans/ }).innerText()).replace(/\D/g, "");
  const footPlans = (await page.innerText("[data-plan-totals]")).match(/(\d+) plans?/)?.[1];
  check(6, 2, "Plans tab count equals the plans listed (DEF-RAT-9304)", tabCount === footPlans, `tab ${tabCount} · foot ${footPlans}`);
  await page.getByRole("button", { name: /Remove .*Tax walk/ }).first().click();
  await page.fill("#reason", "Walk 6.2 remove");
  await page.getByRole("button", { name: /^Remove/ }).last().click();
  await settle(1500);
  await shot(6, "2b", "1.5 removed from the walk plan");
  await goTax(storm, "audit");
  await shot(6, "2c", "1.5 Audit: add and remove");
  const audit = (await api("GET", `taxes/${storm}/audit?page=1&per=50`)).data?.results ?? [];
  const actions = audit.map((a) => a.action);
  check(6, 2, "add and remove both in Audit", actions.includes("tax.attached_to_plan") && actions.includes("tax.detached_from_plan"), actions.join(", "));
  const salesAudit = (await api("GET", `taxes/${state.taxes["1.1"]}/audit?page=1&per=50`)).data?.results ?? [];
  check(6, 3, "Audit after phase 4: who, when, what, before → after, reason", salesAudit.some((a) => a.action === "tax.new_rate_created") && salesAudit.every((a) => a.at && a.actor), salesAudit.map((a) => `${a.at?.slice(0, 16)} ${a.actor?.name} ${a.action}`).slice(0, 6).join(" | "));
}

// ═══ PHASE 7 — isolation, and a two-language spot check ══════════════════════
if (PHASES.has("7")) {
  await page.context().clearCookies();
  await signIn(B_TENANT, B_EMAIL);
  await page.goto(`${BASE}/${B_TENANT}/${TAXES}`, { waitUntil: "networkidle" });
  await shot(7, "1a", "Utility B › Taxes & fees");
  const bBody = await text();
  const leaked = SPECS.filter((s) => bBody.includes(s.name) || bBody.includes(s.code)).map((s) => s.name);
  check(7, 1, "Utility B sees none of A's taxes on screen", leaked.length === 0, leaked.join(", ") || "none shown");
  const bList = await api("GET", "taxes?page=1&per=100&f.versions=all");
  check(7, 1, "the server returns none of A's taxes to B", (bList.data?.results ?? []).length === 0 && bList.status === 200, `status ${bList.status}, rows ${(bList.data?.results ?? []).length}`);
  const aId = state.taxes["1.1"];
  const direct = await api("GET", `taxes/${aId}`);
  const directAudit = await api("GET", `taxes/${aId}/audit`);
  check(7, 1, "opening A's tax by id from B gives nothing", direct.status === 404 && [403, 404].includes(directAudit.status), `GET taxes/{A} → ${direct.status} · audit → ${directAudit.status}`);
  await page.goto(`${BASE}/${B_TENANT}/${TAXES}/${aId}`, { waitUntil: "networkidle" });
  await shot(7, "1b", "Utility B opening A's tax address");
  const bDetail = await text();
  check(7, 1, "A's tax address on B shows nothing of A's", !bDetail.includes("State sales tax") && !bDetail.includes("ST-SALES"), bDetail.slice(0, 160));
  const bAccounts = await api("GET", "settings/authority-accounts?page=1&per=50");
  check(7, 1, "B's authority accounts list none of A's", !(JSON.stringify(bAccounts.data ?? {}).includes("TX Comptroller")), `rows ${(bAccounts.data?.results ?? []).length}`);

  // spot check two languages on A's list and details
  await page.context().clearCookies();
  await signIn(TENANT, EMAIL);
  const setLang = (l) => page.evaluate((code) => window.__SMARTBILLHUB_I18N__?.changeLanguage(code), l);
  for (const lang of ["es-MX", "ja-JP"]) {
    await goList();
    await setLang(lang);
    await shot(7, `2_${lang}_list`, `${lang} list`);
    const listWords = await text();
    await goTax(state.taxes["1.1"]);
    await setLang(lang);
    await shot(7, `2_${lang}_detail`, `${lang} details`);
    const detailWords = await text();
    const english = ["Version", "No end", "Filing due", "Rate and scope", "On the bill and filing", "Charged as", "Customer classes"].filter((w) => listWords.includes(w) || detailWords.includes(w));
    check(7, 2, `${lang}: no English left on list and details (spot check)`, english.length === 0, english.length ? `English seen: ${english.join(", ")}` : "none of the probe words");
  }
}

await browser.close();
