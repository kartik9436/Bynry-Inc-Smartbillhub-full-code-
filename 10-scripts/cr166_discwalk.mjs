// ── Trace ──────────────────────────────────────────────
// Change:  CR-166-BRC10 round 4 task 9 — the discounts FULL WEB WALK, as agreed
//          with the PO (`05-prototype/discounts-2026-10-03/web-walk.md`). A
//          clerk at 1440, clicking; every "must be true" is checked on the
//          SCREEN, against the API and in PostgreSQL. Shape copied from
//          `cr165_taxwalk.mjs` (the taxes walk of the same day).
// ───────────────────────────────────────────────────────
//
// Stack: API `manage.py runserver` on a scratch PostgreSQL 16 database with
// `migrate` + `seed_demo` + `10-scripts/cr166_discwalk_world.py setup`; SPA
// `vite build --mode wolocal` served by `07-frontend/server.mjs`.
//
//   PHASES=2,1 BASE=http://127.0.0.1:5197 PGURL=postgres://postgres@127.0.0.1:55433/<db> \
//     OUT=08-qa/discounts-2026-10-03/walk node 10-scripts/cr166_discwalk.mjs
//
// The bill runs are `cr166_discwalk_world.py run …` between phases; this
// script carries the discount ids between runs in `$OUT/state.json` and
// appends every check to `$OUT/results.json`.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5197";
const TENANT = "brazosbend";
const EMAIL = "dana@brazosbendutilities.com";
const B_TENANT = "riverbend";
const B_EMAIL = "ops@riverbend.example";
const PASSWORD = "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr166-discwalk";
const PGURL = process.env.PGURL ?? "postgres://postgres@127.0.0.1:55433/sbh_discwalk9";
const PHASES = new Set((process.env.PHASES ?? "2,1").split(",").map((p) => p.trim()));
const STATE = `${OUT}/state.json`;
const RESULTS = `${OUT}/results.json`;
mkdirSync(OUT, { recursive: true });

const state = existsSync(STATE) ? JSON.parse(readFileSync(STATE, "utf8")) : { discounts: {} };
const results = existsSync(RESULTS) ? JSON.parse(readFileSync(RESULTS, "utf8")) : [];
const saveState = () => writeFileSync(STATE, JSON.stringify(state, null, 2));
function check(phase, step, what, pass, evidence) {
  const row = { phase, step, what, pass: Boolean(pass), evidence: String(evidence ?? "") };
  const at = results.findIndex((r) => r.phase === phase && r.step === step && r.what === what);
  if (at >= 0) results[at] = row;
  else results.push(row);
  writeFileSync(RESULTS, JSON.stringify(results, null, 2));
  console.log(`${row.pass ? "PASS" : "FAIL"} ${phase}.${step} ${what} — ${row.evidence.slice(0, 400)}`);
}
function db(sql) {
  return execFileSync("psql", [PGURL, "-AtF", "|", "-c", sql], { encoding: "utf8" }).trim();
}
const dbRows = (sql) => {
  const out = db(sql);
  return out === "" ? [] : out.split("\n").map((line) => line.split("|"));
};

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
async function shot(step, n, caption) {
  await settle();
  const name = `discwalk_${step}_${n}.png`;
  const path = `${OUT}/${name}`;
  await page.screenshot({ path, fullPage: true });
  const size = statSync(path).size;
  console.log(`  [shot] ${name} (${size} bytes) — ${caption}`);
  if (size < 8000) console.log(`  [shot] ⚠ ${name} is suspiciously small`);
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
async function cont() {
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await settle(600);
}
async function signIn(tenant, email) {
  currentTenant = tenant;
  await page.goto(`${BASE}/${tenant}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}
async function tick(id, labels) {
  await page.click(`#${id}`);
  const list = page.locator(`[data-check-dropdown="${id}"] [data-check-dropdown-list]`);
  for (const label of labels) await list.locator("label", { hasText: label }).first().locator("input").check();
  if ((await page.getAttribute(`#${id}`, "aria-expanded")) === "true") await page.click(`#${id}`);
}
const DISC = "plans-rates/discounts";
const goList = () => page.goto(`${BASE}/${TENANT}/${DISC}`, { waitUntil: "networkidle" });
const goDisc = (id, tab) =>
  page.goto(`${BASE}/${TENANT}/${DISC}/${id}${tab ? `?tab=${tab}` : ""}`, { waitUntil: "networkidle" });
async function openNew() {
  await page.goto(`${BASE}/${TENANT}/${DISC}/new`, { waitUntil: "networkidle" });
  await page.waitForSelector("#discount-code", { timeout: 30000 });
  await settle(700);
}
async function openLimits() {
  if ((await page.getAttribute("[data-discount-limits]", "data-discount-limits")) !== "open") {
    await page.locator("[data-discount-limits] > button").first().click();
    await settle(300);
  }
}

// ── the discounts of step 1 (the walk's own figures, never signed law) ────────
const SPECS = [
  {
    key: "1", code: "SENIOR", name: "Senior discount", owner: "billing", funding: "Rate-payer funded", report: false,
    type: "percentage", value: "15", applies: "whole_bill", limits: { exclusivity: "low_income", stacking: "10" },
    who: "age_65_or_over", enrol: "apply_and_approve", verify: "one_time_proof", proofBefore: true,
    recertify: "", notice: "", grace: "", lapse: "never_expires", from: "2026-10-01", to: "", budget: "",
    valueShown: "15.00%", onBill: "−$9.00",
  },
  {
    key: "2", code: "CAP", name: "CAP credit", owner: "state_agency", funding: "State grant", report: true,
    type: "fixed_amount", value: "25", applies: "whole_bill",
    limits: { capYear: "300", floor: "50", exclusivity: "low_income", stacking: "20" },
    who: "state_assistance_program", enrol: "apply_and_approve", verify: "annual_recertification", proofBefore: false,
    recertify: "12", notice: "30", grace: "15", lapse: "notify_then_drop", from: "2026-10-01", to: "", budget: "",
    valueShown: "$25.00", onBill: "−$10.00",
  },
  {
    key: "3", code: "AUTOPAY", name: "Autopay discount", owner: "finance", funding: "Rate-payer funded", report: false,
    type: "percentage", value: "0.5", applies: "whole_bill", limits: { exclusivity: "payment_method", stacking: "30" },
    who: "autopay_on", enrol: "automatic", verify: "automatic", proofBefore: false,
    recertify: "", notice: "", grace: "", lapse: "never_expires", from: "2026-10-01", to: "", budget: "",
    valueShown: "0.50%", onBill: "−$0.30",
  },
  {
    key: "4", code: "MUNI", name: "Municipal account", owner: "city_or_county_agency", funding: "City budget", report: false,
    type: "percentage", value: "20", applies: "whole_bill",
    limits: { capBill: "5", exclusivity: "government_municipal", stacking: "40" },
    who: "government_account", enrol: "automatic", verify: "automatic", proofBefore: false,
    recertify: "", notice: "", grace: "", lapse: "never_expires", from: "2026-10-01", to: "", budget: "",
    valueShown: "20.00%", onBill: "−$5.00",
  },
  {
    key: "5", code: "LIFELINE", name: "Lifeline water", owner: "community_programs", funding: "Rate-payer funded", report: true,
    type: "fixed_amount", value: "10", applies: "one_service", service: "water",
    limits: { exclusivity: "low_income", stacking: "25" },
    who: "household_income_limit", enrol: "apply_and_approve", verify: "annual_recertification", proofBefore: false,
    recertify: "12", notice: "30", grace: "0", lapse: "drop_silently", from: "2026-10-01", to: "", budget: "",
    valueShown: "$10.00", onBill: "—",
  },
  {
    key: "6", code: "LEADWAIVE", name: "Lead line waiver", owner: "customer_service", funding: "Rate-payer funded", report: false,
    type: "charge_waiver", value: "", applies: "named_codes", codes: ["BASE-W"],
    limits: { stacking: "50" },
    who: "medical_equipment", enrol: "apply_and_approve", verify: "one_time_proof", proofBefore: false,
    recertify: "", notice: "", grace: "", lapse: "never_expires", from: "2026-10-01", to: "", budget: "",
    valueShown: "", onBill: "—",
  },
  {
    key: "7", code: "GARDEN", name: "Garden allowance", owner: "conservation", funding: "Conservation fund", report: false,
    type: "usage_allowance", value: "2", applies: "one_service", service: "water", limits: { stacking: "5" },
    who: "everyone", enrol: "automatic", verify: "automatic", proofBefore: false,
    recertify: "", notice: "", grace: "", lapse: "never_expires", from: "2026-10-01", to: "",
    budget: "500", budgetPeriod: "annual", budgetOut: "suspend",
    valueShown: "2", onBill: "—",
  },
];
const DRAFT = {
  key: "8", code: "PAPERLESS", name: "Paperless credit", owner: "billing", funding: "Rate-payer funded", report: false,
  type: "fixed_amount", value: "1.5", applies: "whole_bill", limits: {},
  who: "paperless_on", enrol: "automatic", verify: "automatic", proofBefore: false,
  recertify: "", notice: "", grace: "", lapse: "never_expires", from: "2026-11-01", to: "2027-10-31", budget: "",
};
// The step-7 typo discount (fix a value typed 1.5 instead of 15).
const VETERAN = {
  key: "9", code: "VETERAN", name: "Veteran discount", owner: "community_programs", funding: "Rate-payer funded", report: false,
  type: "percentage", value: "1.5", applies: "whole_bill", limits: { exclusivity: "military_veterans" },
  who: "veteran_or_military", enrol: "apply_and_approve", verify: "one_time_proof", proofBefore: false,
  recertify: "", notice: "", grace: "", lapse: "never_expires", from: "2026-10-01", to: "", budget: "",
};

async function fillDetails(spec) {
  await page.fill("#discount-code", spec.code);
  await page.fill("#discount-label", spec.name);
  await page.selectOption("#discount-owner", spec.owner);
  await page.fill("#discount-funding", spec.funding);
  if (spec.report) await page.check("#discount-assistance", { force: true });
  await page.selectOption("#discount-type", spec.type);
  await settle(200);
  if (spec.value !== "" && (await page.$("#discount-value"))) await page.fill("#discount-value", spec.value);
  await page.selectOption("#discount-applies", spec.applies);
  await settle(200);
  if (spec.service) await page.selectOption("#discount-service", spec.service);
  if (spec.codes) await tick("discount-codes", spec.codes);
  const l = spec.limits ?? {};
  if (Object.keys(l).length) {
    await openLimits();
    if (l.capBill) await page.fill("#discount-cap-bill", l.capBill);
    if (l.capYear) await page.fill("#discount-cap-year", l.capYear);
    if (l.capLifetime) await page.fill("#discount-cap-lifetime", l.capLifetime);
    if (l.floor) await page.fill("#discount-floor", l.floor);
    if (l.stacking) await page.fill("#discount-stacking", l.stacking);
    if (l.exclusivity) await page.selectOption("#discount-exclusivity", l.exclusivity);
  }
}
async function fillEligibility(spec) {
  await page.selectOption("#discount-who", spec.who);
  await settle(200);
  await page.selectOption("#discount-enrollment", spec.enrol);
  await page.selectOption("#discount-verification", spec.verify);
  if (spec.proofBefore) await page.check("#discount-proof-before", { force: true });
  if (spec.recertify !== "") await page.fill("#discount-recertify", spec.recertify);
  if (spec.lapse) await page.selectOption("#discount-lapse", spec.lapse).catch(() => {});
  if (spec.notice !== "") await page.fill("#discount-notice", spec.notice);
  if (spec.grace !== "") await page.fill("#discount-grace", spec.grace);
  await page.fill("#discount-starts", spec.from);
  if (spec.to) await page.fill("#discount-ends", spec.to);
  if (spec.budget) {
    await page.fill("#discount-budget", spec.budget);
    await page.selectOption("#discount-budget-period", spec.budgetPeriod);
    await page.selectOption("#discount-budget-out", spec.budgetOut);
  }
}
const discRows = (code) =>
  dbRows(`select d.id, d.status, d.name, v.version_no, v.status, v.value, v.effective_from, v.effective_to
            from discounts d join discount_versions v on v.discount_id=d.id
           where d.code='${code}' and d.tenant_id=(select id from tenants where subdomain='${TENANT}')
           order by v.version_no`);

async function createThrough(spec) {
  await openNew();
  await fillDetails(spec);
  await cont();
  await fillEligibility(spec);
  await cont();
  await shot(1, `${spec.key}_review`, `${spec.name} Review`);
  const review = await text();
  if (spec.onBill && spec.onBill !== "—") {
    check(1, spec.key, `${spec.name}: Review shows ${spec.onBill} on the $60.00 bill`, review.includes(spec.onBill.replace("−", "")), review.match(/On a \$60\.00 bill.{0,160}/)?.[0] ?? review.slice(0, 200));
  }
  await page.getByRole("button", { name: "Save as draft", exact: true }).click();
  await page.waitForSelector("#discount-saved-title", { timeout: 15000 }).catch(() => {});
  await shot(1, `${spec.key}_saved`, `${spec.name} saved`);
  const rows = discRows(spec.code);
  check(1, spec.key, `${spec.name}: exactly one row in the database, saved as a draft`, rows.length === 1 && rows[0][1] === "draft" && rows[0][4] === "draft", JSON.stringify(rows));
  if (rows.length) state.discounts[spec.key] = rows[0][0];
  saveState();
}

// ═══ STEP 2 — the form checks (run before step 1 saves anything) ═════════════
if (PHASES.has("2")) {
  await signIn(TENANT, EMAIL);
  await openNew();
  await cont();
  await shot(2, 1, "empty form, Continue pressed");
  const errs = await page.$$eval("[id$='-error']", (els) => els.map((e) => `${e.id}:${e.textContent}`));
  check(2, 1, "each missing box on step 1 is named on its box", errs.some((e) => e.startsWith("discount-code")) && errs.some((e) => e.startsWith("discount-label")) && errs.some((e) => e.startsWith("discount-value")), JSON.stringify(errs));
  // percent over 100 — nothing typed lost
  await page.fill("#discount-code", "OVER");
  await page.fill("#discount-label", "Typed over a hundred");
  await page.fill("#discount-funding", "Keep me");
  await page.fill("#discount-value", "150");
  await cont();
  await shot(2, 2, "150% refused");
  const over = await page.$eval("#discount-value-error", (e) => e.textContent).catch(() => null);
  const kept = [await page.inputValue("#discount-code"), await page.inputValue("#discount-label"), await page.inputValue("#discount-funding"), await page.inputValue("#discount-value")];
  check(2, 2, "percent over 100 refused on the Value box", over === "Cannot be over 100%.", over);
  check(2, 2, "nothing typed is lost", kept.join("|") === "OVER|Typed over a hundred|Keep me|150", kept.join("|"));
  // currency: the utility's, read-only
  const currency = await page.$eval("#discount-currency", (e) => [e.tagName, e.textContent ?? e.value, e.getAttribute("readonly"), e.getAttribute("disabled")]).catch(() => null);
  const currencyText = await page.locator("[data-read-only-fact=discount-currency], #discount-currency").first().innerText().catch(() => "");
  check(2, 3, "currency is the utility's and cannot be changed", currencyText.includes("USD") && !(await page.$("select#discount-currency, input#discount-currency:not([readonly])")), `${currencyText} · ${JSON.stringify(currency)}`);
  // step 2: no who-qualifies, end before start
  await page.fill("#discount-value", "15");
  await cont();
  await page.fill("#discount-starts", "2026-11-01");
  await page.fill("#discount-ends", "2026-10-01");
  await cont();
  await shot(2, 4, "no who-qualifies, end before start");
  const errs2 = await page.$$eval("[id$='-error']", (els) => els.map((e) => `${e.id}:${e.textContent}`));
  check(2, 4, "no who-qualifies and end-before-start each named on its box", errs2.some((e) => e.startsWith("discount-who") && e.includes("Choose who qualifies")) && errs2.some((e) => e.startsWith("discount-ends") && e.includes("Ends before it starts")), JSON.stringify(errs2));
  check(2, 4, "the start typed is kept", (await page.inputValue("#discount-starts")) === "2026-11-01", await page.inputValue("#discount-starts"));
  // the server refuses a currency other than the utility's, by name
  const cad = await api("POST", "discounts", { code: "CADTEST", name: "Typed currency", discount_type: "percentage", value: "5", currency: "CAD", applies_to: "whole_bill", eligibility: "everyone", effective_from: "2026-11-01" });
  check(2, 3, "the server refuses another currency by name", cad.status >= 400 && JSON.stringify(cad.data).includes("currency_not_utility"), `${cad.status} ${JSON.stringify(cad.data).slice(0, 200)}`);
  check(2, 3, "nothing was stored by the refused write", discRows("CADTEST").length === 0 && discRows("OVER").length === 0, "CADTEST rows " + discRows("CADTEST").length);
}

// ═══ STEP 1 — one discount of every kind, through the New form ═════════════
if (PHASES.has("1")) {
  await signIn(TENANT, EMAIL);
  for (const spec of [...SPECS, VETERAN]) await createThrough(spec);
  // 1.8 — a draft: Save draft & exit half way
  await openNew();
  await fillDetails(DRAFT);
  await page.getByRole("button", { name: /Save draft/ }).first().click();
  await settle(2000);
  await shot(1, "8_exit", "Save draft & exit half way");
  const half = discRows(DRAFT.code);
  check(1, 8, "Save draft & exit stores exactly one row, a draft", half.length === 1 && half[0][1] === "draft", JSON.stringify(half));
  if (half.length) state.discounts["8"] = half[0][0];
  saveState();
  await goList();
  await shot(1, "list", "list after step 1");
  const list = await api("GET", "discounts?page=1&per=50");
  const rows = list.data?.results ?? [];
  for (const spec of [...SPECS, DRAFT, VETERAN]) {
    const row = rows.find((r) => r.code === spec.code);
    check(1, spec.key, `${spec.name}: one list row, Draft`, rows.filter((r) => r.code === spec.code).length === 1 && row?.status === "draft", row ? `${row.code} · ${row.status} · ${row.value_display} · ${row.effective_from} → ${row.effective_to ?? "No end"}` : "missing");
  }
}

// A discount walked again after its fix: REDO=6 PHASES=1redo
if (PHASES.has("1redo")) {
  await signIn(TENANT, EMAIL);
  const keys = (process.env.REDO ?? "").split(",");
  for (const spec of [...SPECS, VETERAN].filter((s) => keys.includes(s.key))) {
    await createThrough(spec);
    const row = (await api("GET", "discounts?page=1&per=50")).data?.results?.find((r) => r.code === spec.code);
    check(1, spec.key, `${spec.name}: one list row, Draft`, row?.status === "draft", row ? `${row.code} · ${row.status} · ${row.value_display ?? "—"} · ${row.effective_from} → ${row.effective_to ?? "No end"}` : "missing");
  }
}

if (PHASES.has("1.8finish")) {
  await signIn(TENANT, EMAIL);
  const id = state.discounts["8"];
  await goDisc(id);
  await shot(1, "8_reopen", "the draft's details");
  await page.getByRole("link", { name: "Edit", exact: true }).or(page.getByRole("button", { name: "Edit", exact: true })).first().click();
  await settle(1500);
  await shot(1, "8_edit", "Edit on the draft");
  const kept = [await page.inputValue("#discount-code").catch(() => "?"), await page.inputValue("#discount-label").catch(() => "?"), await page.inputValue("#discount-value").catch(() => "?")];
  check(1, 8, "reopened: nothing typed before Save draft & exit is lost", kept[0] === "PAPERLESS" && kept[1] === "Paperless credit" && Number(kept[2]) === 1.5, kept.join("|") + " · " + page.url());
  await cont();
  await fillEligibility(DRAFT);
  await cont();
  await shot(1, "8_review", "the draft finished, Review");
  await page.getByRole("button", { name: /^Save/ }).last().click();
  await settle(2000);
  await shot(1, "8_saved", "the draft finished, saved");
  const rows = discRows(DRAFT.code);
  const elig = db(`select v.eligibility_code||'|'||v.effective_from||'|'||coalesce(v.effective_to::text,'') from discount_versions v join discounts d on d.id=v.discount_id where d.code='PAPERLESS'`);
  check(1, 8, "finished: the SAME row, still one, eligibility and dates stored", rows.length === 1 && rows[0][0] === id && elig === "paperless_on|2026-11-01|2027-10-31", `${JSON.stringify(rows)} · ${elig}`);
}

// ═══ STEP 3 — view each discount: every value as entered, buttons by status ══
// A box left EMPTY is stored as the server's default (notice 60 days, grace 0,
// stacking order 100, exclusivity group none) — the check expects that.
const num = (v) => (v === null || v === undefined || v === "" ? null : Number(v));
function expectedOf(spec) {
  const l = spec.limits ?? {};
  return {
    code: spec.code, name: spec.name, type: spec.type, currency: "USD",
    value: spec.type === "charge_waiver" ? 0 : Number(spec.value),
    program_owner: spec.owner, funding_source: spec.funding, report_in_assistance_filing: Boolean(spec.report),
    applies_to: spec.applies, applies_to_charge_codes: spec.codes ?? [],
    cap_per_bill: num(l.capBill), cap_per_year: num(l.capYear), cap_lifetime: num(l.capLifetime),
    bill_floor_amount: num(l.floor) ?? 0, stacking_precedence: num(l.stacking) ?? 100, stacks_with_others: true,
    exclusivity_group: l.exclusivity ?? "none", eligibility: spec.who, enrolment_mode: spec.enrol,
    verification: spec.verify, proof_before_first_reduction: Boolean(spec.proofBefore),
    recertification_months: num(spec.recertify), recertification_notice_days: num(spec.notice) ?? 60,
    recertification_grace_days: num(spec.grace) ?? 0, lapse_behaviour: spec.lapse,
    effective_from: spec.from, effective_to: spec.to || null,
    budget_cap: num(spec.budget), budget_period: spec.budget ? spec.budgetPeriod : undefined,
    exhaustion_behaviour: spec.budget ? spec.budgetOut : undefined,
  };
}
function actualOf(row) {
  return {
    code: row.code, name: row.name, type: row.type, currency: row.currency, value: num(row.value),
    program_owner: row.program_owner?.value ?? null, funding_source: row.funding_source,
    report_in_assistance_filing: row.report_in_assistance_filing, applies_to: row.applies_to,
    applies_to_charge_codes: row.applies_to_charge_codes ?? [],
    cap_per_bill: num(row.cap_per_bill), cap_per_year: num(row.cap_per_year), cap_lifetime: num(row.cap_lifetime),
    bill_floor_amount: num(row.bill_floor_amount) ?? 0, stacking_precedence: num(row.stacking_precedence),
    stacks_with_others: row.stacks_with_others, exclusivity_group: row.exclusivity_group?.value ?? null,
    eligibility: row.eligibility?.value ?? null, enrolment_mode: row.enrolment_mode, verification: row.verification,
    proof_before_first_reduction: row.proof_before_first_reduction,
    recertification_months: num(row.recertification_months), recertification_notice_days: num(row.recertification_notice_days),
    recertification_grace_days: num(row.recertification_grace_days), lapse_behaviour: row.lapse_behaviour,
    effective_from: row.effective_from, effective_to: row.effective_to ?? null, budget_cap: num(row.budget_cap),
    budget_period: row.budget_period, exhaustion_behaviour: row.exhaustion_behaviour,
  };
}
function diffOf(expected, actual) {
  const out = [];
  for (const [k, v] of Object.entries(expected)) {
    if (v === undefined) continue;
    if (JSON.stringify(v) !== JSON.stringify(actual[k])) out.push(`${k}: entered ${JSON.stringify(v)} · served ${JSON.stringify(actual[k])}`);
  }
  return out;
}
const OPTIONS_LABELS = {};
async function labelsOf() {
  if (Object.keys(OPTIONS_LABELS).length) return OPTIONS_LABELS;
  const fo = (await api("GET", "discounts/form-options")).data;
  for (const [list, rows] of Object.entries(fo)) if (Array.isArray(rows)) for (const r of rows) OPTIONS_LABELS[`${list}:${r.value}`] = r.label;
  return OPTIONS_LABELS;
}
if (PHASES.has("3")) {
  await signIn(TENANT, EMAIL);
  const labels = await labelsOf();
  for (const spec of [...SPECS, VETERAN, DRAFT]) {
    const id = state.discounts[spec.key];
    const row = (await api("GET", `discounts/${id}`)).data;
    const diffs = diffOf(expectedOf(spec), actualOf(row));
    check(3, spec.key, `${spec.name}: the API serves every value exactly as entered`, diffs.length === 0, diffs.join(" | ") || "31 values match");
    await goDisc(id);
    await shot(3, spec.key, `${spec.name} details › Overview`);
    const body = await text();
    const want = [
      spec.name, spec.code, labels[`program_owners:${spec.owner}`], spec.funding,
      labels[`eligibility:${spec.who}`], labels[`enrollment_modes:${spec.enrol}`],
      spec.limits?.exclusivity ? labels[`exclusivity_groups:${spec.limits.exclusivity}`] : null,
      spec.limits?.capYear ? "$300.00" : null, spec.limits?.floor ? "$50.00" : null, spec.limits?.capBill ? "$5.00" : null,
      spec.budget ? "$500.00" : null, spec.from ? `${spec.from.slice(5, 7)}/${spec.from.slice(8)}/${spec.from.slice(0, 4)}` : null,
      spec.to ? `${spec.to.slice(5, 7)}/${spec.to.slice(8)}/${spec.to.slice(0, 4)}` : null,
      row.value_display,
    ].filter(Boolean);
    const missing = want.filter((w) => !body.includes(w));
    check(3, spec.key, `${spec.name}: the Overview shows what was entered`, missing.length === 0, missing.length ? `not on screen: ${missing.join(", ")}` : `shown: ${want.join(" · ")}`);
    const buttons = await page.$$eval("main button, main a", (els) => els.map((e) => (e.textContent ?? "").trim()).filter(Boolean));
    const draftButtons = buttons.includes("Edit") && buttons.includes("Submit for approval") && !buttons.includes("Approve");
    check(3, spec.key, `${spec.name}: a Draft offers Edit and Submit for approval, not Approve`, draftButtons, buttons.filter((b) => /Edit|Submit|Approve|Send back|More/.test(b)).join(" · "));
  }
}

// ═══ STEP 4 — going live: Submit → Approve, by the same person ══════════════
async function submitAndApprove(spec, { expectRefusal = false } = {}) {
  const id = state.discounts[spec.key];
  await goDisc(id);
  if ((await api("GET", `discounts/${id}`)).data?.status === "draft") {
    await page.getByRole("button", { name: "Submit for approval", exact: true }).click();
    await settle(1500);
  }
  await shot(4, `${spec.key}_submitted`, `${spec.name} Waiting approval`);
  const waiting = (await api("GET", `discounts/${id}`)).data?.status;
  check(4, spec.key, `${spec.name}: Submit puts it in Waiting approval`, waiting === "waiting_approval", waiting);
  const buttons = await page.$$eval("main button", (els) => els.map((e) => (e.textContent ?? "").trim()));
  check(4, spec.key, `${spec.name}: Waiting approval offers Send back and Approve`, buttons.includes("Send back") && buttons.includes("Approve"), buttons.filter((b) => /Send back|Approve|Edit|Submit/.test(b)).join(" · "));
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await settle(600);
  await shot(4, `${spec.key}_confirm`, `${spec.name} Approve confirm`);
  const dialog = await page.innerText("[role=dialog], [role=alertdialog]").catch(() => "");
  await page.locator("[role=dialog], [role=alertdialog]").getByRole("button", { name: /^Approve/ }).click();
  await settle(2000);
  await shot(4, `${spec.key}_approved`, `${spec.name} after Approve`);
  const after = (await api("GET", `discounts/${id}`)).data;
  if (expectRefusal) {
    const shown = (await page.innerText("[role=dialog], [role=alertdialog]").catch(() => "")) || (await text());
    return { after, dialog, shown };
  }
  const today = "2026-10-03";
  const wanted = spec.from <= today ? "active" : "scheduled";
  const versions = dbRows(`select v.status, v.self_approved, v.approved_at is not null, v.submitted_by_user_id = v.approved_by_user_id
                             from discount_versions v where v.discount_id='${id}' order by v.version_no`);
  check(4, spec.key, `${spec.name}: approved = ${wanted === "active" ? "live" : "Scheduled"} with no Activate (ruling 1)`, after.status === wanted && versions[0]?.[0] === "active", `served ${after.status} · stored ${JSON.stringify(versions)} · confirm "${dialog.replace(/\s+/g, " ").slice(0, 80)}"`);
  return { after, dialog };
}
if (PHASES.has("4")) {
  await signIn(TENANT, EMAIL);
  for (const spec of [SPECS[0], SPECS[1], SPECS[2], SPECS[3], SPECS[5], VETERAN, DRAFT]) await submitAndApprove(spec);
  // a usage allowance: the engine cannot price it (EP-RAT-15) — approval refuses it by name
  const garden = await submitAndApprove(SPECS[6], { expectRefusal: true });
  check(4, 7, "Garden allowance: approval goes live (walk: free units before pricing)", garden.after.status === "active", `served ${garden.after.status} · on screen: ${garden.shown.replace(/\s+/g, " ").slice(0, 220)}`);
  // the second approver: switch the threshold ON ($100), approve a discount with no budget
  const before = (await api("GET", "settings/finance-controls")).data?.discount_second_approval_threshold_amount ?? null;
  const put = await api("PUT", "settings/finance-controls", { discount_second_approval_threshold_amount: "100" });
  check(4, "2nd", "the second-approval threshold can be switched on (Settings › Finance controls)", put.status === 200, `PUT → ${put.status} (was ${before})`);
  const lifeline = await submitAndApprove(SPECS[4], { expectRefusal: true });
  const v = dbRows(`select v.status, v.second_approval_required, v.second_approved_by_user_id is not null from discount_versions v where v.discount_id='${state.discounts["5"]}'`);
  check(4, "2nd", "Lifeline (no budget, threshold $100): needs a second approver before it is live (BR-RAT-077)", lifeline.after.status === "waiting_approval", `served ${lifeline.after.status} · stored ${JSON.stringify(v)} — DEF-RAT-9303 (known, open): live on one approval`);
  await api("PUT", "settings/finance-controls", { discount_second_approval_threshold_amount: before });
  // Audit names who did each step
  for (const spec of [SPECS[0], SPECS[4]]) {
    const audit = (await api("GET", `discounts/${state.discounts[spec.key]}/audit?page=1&per=50`)).data?.results ?? [];
    await goDisc(state.discounts[spec.key], "audit");
    await shot(4, `${spec.key}_audit`, `${spec.name} Audit`);
    const body = await text();
    check(4, spec.key, `${spec.name}: Audit shows who submitted and who approved`, body.includes("Submitted") && body.includes("Approved") && body.includes("Dana Whitfield"), audit.map((a) => `${a.action} · ${a.actor?.name ?? a.actor}`).slice(0, 6).join(" | "));
  }
  await goList();
  await shot(4, "list", "list after going live");
}

// ═══ STEP 5 — plans and enrollment ══════════════════════════════════════════
// The plan's discount list is saved through `PATCH /plans/{id} {discounts,
// reason}` — the request the plan wizard's step 6 sends. The wizard itself is
// not clicked: on the world's fixture plans its step 2 reads no service (said
// so in the report), and the walk is about discounts.
const WORLD = process.env.WORLD ? JSON.parse(readFileSync(process.env.WORLD, "utf8")) : {};
const ACCTS = WORLD.ACCOUNTS_JSON ?? {};
const PLANIDS = WORLD.PLANS_JSON ?? {};
async function setPlanDiscounts(planCode, keys, reason) {
  const res = await api("PATCH", `plans/${PLANIDS[planCode]}`, {
    reason,
    discounts: keys.map((k) => ({ discount: state.discounts[k] })),
  });
  console.log(`  plan ${planCode} ← ${keys.join(",")} → ${res.status}`);
  return res;
}
const enrolmentsOf = (key) =>
  dbRows(`select a.account_no, e.enrolled_on, coalesce(e.ended_on::text,''), e.verification_status, coalesce(e.end_reason,'')
            from discount_enrolments e join accounts a on a.id=e.account_id
           where e.discount_id='${state.discounts[key]}' order by a.account_no, e.enrolled_on`);
async function enrolOnScreen(key, acctKey) {
  await goDisc(state.discounts[key], "accounts");
  await page.getByRole("button", { name: /Enroll an account/ }).click();
  await settle(500);
  await page.fill("#account", ACCTS[acctKey].number);
  await settle(1500);
  await page.getByRole("option", { name: new RegExp(ACCTS[acctKey].number) }).first().click();
  await settle(300);
  await page.locator("[role=dialog]").getByRole("button", { name: "Enroll", exact: true }).click();
  await settle(2000);
  const dialog = await page.innerText("[role=dialog]").catch(() => "");
  return dialog.replace(/\s+/g, " ");
}
if (PHASES.has("5")) {
  await signIn(TENANT, EMAIL);
  const r1 = await setPlanDiscounts("DW-RES", ["1", "2", "3", "5", "6", "8", "9"], "Discount walk step 5");
  const r2 = await setPlanDiscounts("DW-MUNI", ["4"], "Discount walk step 5");
  check(5, 1, "the plans save their discounts", r1.status === 200 && r2.status === 200, `${r1.status} ${r2.status} ${JSON.stringify(r1.data).slice(0, 160)}`);
  await goDisc(state.discounts["1"], "plans");
  await shot(5, 1, "Senior › Plans");
  const plansBody = await text();
  check(5, 1, "Senior's Plans tab names Discount walk · Residential", plansBody.includes("Discount walk · Residential"), plansBody.slice(0, 300));
  // ruling 3 — automatic discounts enrol every qualifying account on their plans
  const auto = enrolmentsOf("3");
  check(5, 3, "Autopay enrolled by itself: exactly the one account with autopay on (ruling 3)", auto.length === 1 && auto[0][0] === ACCTS["DW-SENIOR"].number, JSON.stringify(auto));
  const muni = enrolmentsOf("4");
  check(5, 3, "Municipal enrolled by itself: exactly the municipal account (ruling 3)", muni.length === 1 && muni[0][0] === ACCTS["DW-CITY"].number, JSON.stringify(muni));
  await goDisc(state.discounts["3"], "accounts");
  await shot(5, 3, "Autopay › Accounts");
  check(5, 3, "Autopay's Accounts tab lists Ruth Alvarez, Receiving", (await text()).includes(ACCTS["DW-SENIOR"].number) && (await text()).includes("Receiving"), (await text()).slice(0, 300));
  // enrol on the plan → yes; off the plan → refused (ruling 2)
  const ok = await enrolOnScreen("1", "DW-SENIOR");
  await shot(5, 2, "Senior: Ruth Alvarez enrolled");
  const off = await enrolOnScreen("1", "DW-OFF");
  await shot(5, "2b", "Senior: off-plan account refused");
  check(5, 2, "an account on the plan is enrolled", enrolmentsOf("1").some((r) => r[0] === ACCTS["DW-SENIOR"].number && r[2] === ""), JSON.stringify(enrolmentsOf("1")) + ` · dialog after: "${ok}"`);
  check(5, 2, "the off-plan account is refused, on screen, by name (ruling 2)", off !== "" && !enrolmentsOf("1").some((r) => r[0] === ACCTS["DW-OFF"].number), `dialog: "${off.slice(0, 200)}"`);
  await page.keyboard.press("Escape");
  // take Senior off the plan → stopped from the next bill (ruling 2)
  const r3 = await setPlanDiscounts("DW-RES", ["2", "3", "5", "6", "8", "9"], "Discount walk step 5: remove Senior");
  const after = enrolmentsOf("1");
  check(5, 4, "Senior off the plan: its enrollment on that plan ends", r3.status === 200 && after.every((r) => r[2] !== ""), JSON.stringify(after));
  state.removedOn = "2026-10-03";
  saveState();
}
// ═══ DEF-RAT-9319 — the list fits 1440 in every language ════════════════════
const LANGS = ["en", "de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"];
const setLang = (l) => page.evaluate((code) => window.__SMARTBILLHUB_I18N__?.changeLanguage(code), l);
if (PHASES.has("9319")) {
  await signIn(TENANT, EMAIL);
  for (const lang of LANGS) {
    await goList();
    await setLang(lang);
    await settle(1200);
    const m = await page.evaluate(() => {
      const t = document.querySelector("main table");
      const box = document.querySelector("main [data-table-scroll]");
      const rows = [...t.querySelectorAll("tbody tr")];
      // the tallest Type cell's line count — 定/率 one per line was 2+ lines of 1 char
      const typeLines = Math.max(...rows.map((r) => {
        const c = r.children[2];
        const lh = parseFloat(getComputedStyle(c).lineHeight) || 18;
        return Math.round(c.querySelector("span")?.getBoundingClientRect().height / lh) || 1;
      }));
      const lastTh = [...t.querySelectorAll("thead th")].slice(-2)[0].getBoundingClientRect();
      return { table: Math.round(t.getBoundingClientRect().width), box: box.clientWidth, scrolls: getComputedStyle(box).overflowX, typeLines, statusRight: Math.round(lastTh.right), boxRight: Math.round(box.getBoundingClientRect().right), page: document.documentElement.scrollWidth };
    });
    if (lang === "en" || lang === "ja-JP" || lang === "ko-KR") await shot("9319", lang, `list at 1440 in ${lang}`);
    check("9319", lang, `${lang}: the list fits 1440 with no sideways scroll, Status in view, Type never one character a line`, m.table <= m.box && m.scrolls !== "auto" && m.page <= 1440 && m.typeLines <= 3, JSON.stringify(m));
  }
  await setLang("en");
}

// ═══ STEP 6 — the Accounts tab: proof pending → verify, end one ═════════════
async function verifyOnScreen(key, acctKey) {
  await goDisc(state.discounts[key], "accounts");
  // An enrollment ended TODAY is still in force today and is listed too (the
  // step-5 removal ended Ruth's first one on 10/03); verify every pending row
  // of this account, one at a time.
  for (let i = 0; i < 3; i++) {
    const buttons = page.getByRole("button", { name: `Verify proof for ${ACCTS[acctKey].number}` });
    if ((await buttons.count()) === 0) break;
    await buttons.first().click();
    await settle(2000);
  }
}
async function endOnScreen(key, acctKey, reason) {
  await goDisc(state.discounts[key], "accounts");
  await page.getByRole("button", { name: `End ${ACCTS[acctKey].number}` }).click();
  await settle(500);
  await page.fill("#reason", reason);
  await page.locator("[role=dialog]").getByRole("button", { name: "End it" }).click();
  await settle(2000);
}
const tabCount = async (name) => (await page.getByRole("tab", { name: new RegExp(`^${name}`) }).innerText()).replace(/\D/g, "");
if (PHASES.has("6")) {
  await signIn(TENANT, EMAIL);
  // Ruth on Senior: Proof pending → verified
  await goDisc(state.discounts["1"], "accounts");
  await shot(6, 1, "Senior › Accounts: Ruth Proof pending, a ✓ to verify");
  await verifyOnScreen("1", "DW-SENIOR");
  await shot(6, 2, "Senior › Accounts after Verify proof");
  const ruth = enrolmentsOf("1").filter((r) => r[0] === ACCTS["DW-SENIOR"].number && r[2] === "");
  check(6, 1, "Verify proof turns Ruth's Senior from Proof pending to Receiving (DEF-RAT-9325)", ruth.length === 1 && ruth[0][3] === "verified" && (await text()).includes("Receiving"), JSON.stringify(ruth));
  // CAP account: CAP, Lifeline and Senior (choice A — one of the group); Medic on the waiver; Pat on Senior then ended
  for (const [key, acct] of [["2", "DW-CAP"], ["5", "DW-CAP"], ["1", "DW-CAP"], ["6", "DW-MEDIC"], ["1", "DW-PLAIN"], ["9", "DW-PLAIN"]]) {
    if (enrolmentsOf(key).some((r) => r[0] === ACCTS[acct].number && (r[2] === "" || r[4] === "Walk step 6: moved away"))) continue; // walked already
    const dialog = await enrolOnScreen(key, acct);
    check(6, 2, `${ACCTS[acct].number} enrolled in ${key} and the dialog closes (DEF-RAT-9326)`, enrolmentsOf(key).some((r) => r[0] === ACCTS[acct].number && r[2] === "") && dialog === "", `dialog after: "${dialog.slice(0, 120)}"`);
  }
  await verifyOnScreen("1", "DW-CAP");
  await shot(6, 3, "Senior › Accounts: three enrolled");
  if (!enrolmentsOf("1").some((r) => r[0] === ACCTS["DW-PLAIN"].number && r[4] === "Walk step 6: moved away")) await endOnScreen("1", "DW-PLAIN", "Walk step 6: moved away");
  await shot(6, 4, "Senior › Accounts after ending Pat's enrollment");
  const pat = enrolmentsOf("1").filter((r) => r[0] === ACCTS["DW-PLAIN"].number);
  check(6, 3, "End stores the day and the reason, and the dialog closes", pat.every((r) => r[2] !== "") && pat.some((r) => r[4] === "Walk step 6: moved away") && !(await page.$("[role=dialog]")), JSON.stringify(pat));
  // Tab, Overview and the API agree
  const accounts = (await api("GET", `discounts/${state.discounts["1"]}/accounts?page=1&per=50`)).data;
  const rows = accounts?.results ?? accounts?.rows ?? [];
  const detail = (await api("GET", `discounts/${state.discounts["1"]}`)).data;
  await goDisc(state.discounts["1"]);
  await shot(6, 5, "Senior › Overview after step 6");
  const overview = await text();
  const tab = await tabCount("Accounts");
  check(6, 4, "Accounts tab rows, its count and Overview Receiving it agree (as image 19/20 draw them: 12 and 12)", rows.length === Number(tab) && detail.receiving === rows.length && overview.includes(String(detail.receiving)), `rows ${rows.length} (${rows.map((r) => `${r.account_number} ${r.status}`).join(", ")}) · tab ${tab} · receiving ${detail.receiving}`);
  check(6, 4, "Granted and each This month are a dash, never $0.00 (DEF-2430, known)", detail.granted_this_month === null && rows.every((r) => r.this_month === null), `granted ${detail.granted_this_month} · this_month ${rows.map((r) => r.this_month).join(",")}`);
  await goDisc(state.discounts["1"], "audit");
  await shot(6, 6, "Senior › Audit after step 6");
  const audit = (await api("GET", `discounts/${state.discounts["1"]}/audit?page=1&per=50`)).data?.results ?? [];
  check(6, 5, "Audit names enroll, verify and end, with who", ["discount.account_enrolled", "discount.enrolment_verified", "discount.enrolment_ended"].every((a) => audit.some((x) => x.action === a)), audit.map((a) => `${a.action} · ${a.actor?.name ?? a.actor}`).slice(0, 8).join(" | "));
}

// put Senior back after the removal check (and re-enroll Ruth)
if (PHASES.has("5back")) {
  await signIn(TENANT, EMAIL);
  const r = await setPlanDiscounts("DW-RES", ["1", "2", "3", "5", "6", "8", "9"], "Discount walk step 5: Senior back");
  check(5, 5, "Senior put back on the plan", r.status === 200, r.status);
  const again = await enrolOnScreen("1", "DW-SENIOR");
  await shot(5, 5, "Senior: Ruth enrolled again");
  check(5, 5, "Ruth Alvarez enrolled again", enrolmentsOf("1").some((x) => x[0] === ACCTS["DW-SENIOR"].number && x[2] === ""), JSON.stringify(enrolmentsOf("1")) + ` ${again}`);
}

// ═══ RESUME (round 4 task 9, second session) ════════════════════════════════
// The checkpoint's database was dropped, so steps 1, 4 and 5 are re-run on a
// fresh one only as far as steps 7–11 need: phase 1 as written, then `prep`
// approves Senior, CAP, Autopay, Municipal, Lifeline and Veteran through the
// screen (NOT the Lead line waiver — `DEF-RAT-9327` would stop the bill runs —
// nor Garden, which cannot go live, nor the Paperless draft), binds them to the
// plans the way phase 5 does, enrolls Ruth on Senior (and verifies her proof),
// Pat on Veteran and Carl on CAP. Run with OUT in a scratch folder so the
// checkpoint's step-1–6 photographs are not overwritten.
if (PHASES.has("prep")) {
  await signIn(TENANT, EMAIL);
  for (const spec of [SPECS[0], SPECS[1], SPECS[2], SPECS[3], SPECS[4], VETERAN]) await submitAndApprove(spec);
  const r1 = await setPlanDiscounts("DW-RES", ["1", "2", "3", "5", "9"], "Discount walk resume");
  const r2 = await setPlanDiscounts("DW-MUNI", ["4"], "Discount walk resume");
  check("prep", 1, "plans carry their discounts", r1.status === 200 && r2.status === 200, `${r1.status} ${r2.status}`);
  await enrolOnScreen("1", "DW-SENIOR");
  await verifyOnScreen("1", "DW-SENIOR");
  await enrolOnScreen("9", "DW-PLAIN");
  await enrolOnScreen("2", "DW-CAP");
  const ruth = enrolmentsOf("1").filter((r) => r[0] === ACCTS["DW-SENIOR"].number && r[2] === "");
  check("prep", 2, "Ruth receiving Senior (verified), Pat on Veteran, Carl on CAP", ruth.length === 1 && ruth[0][3] === "verified" && enrolmentsOf("9").length === 1 && enrolmentsOf("2").length === 1, `${JSON.stringify(ruth)} · veteran ${JSON.stringify(enrolmentsOf("9"))} · cap ${JSON.stringify(enrolmentsOf("2"))}`);
}

// ═══ STEP 7 — Edit, three ways ═════════════════════════════════════════════
const editAt = (key, mode) =>
  page.goto(`${BASE}/${TENANT}/${DISC}/${state.discounts[key]}/edit?change=${mode}`, { waitUntil: "networkidle" });
const versionsOf = (key) =>
  dbRows(`select v.id, v.version_no, v.status, v.value::numeric(9,2), v.effective_from, coalesce(v.effective_to::text,''),
                 coalesce(v.corrects_version_id::text,''), coalesce(v.superseded_by_version_id::text,''), coalesce(v.correction_reason,'')
            from discount_versions v where v.discount_id='${state.discounts[key]}' order by v.version_no`);
const auditOf = async (key) =>
  (await api("GET", `discounts/${state.discounts[key]}/audit?page=1&per=50`)).data?.results ?? [];
if (PHASES.has("7")) {
  await signIn(TENANT, EMAIL);
  // 7.1 Name and details — Autopay renamed, funding source changed: same row, same version
  const before = discRows("AUTOPAY");
  await editAt("3", "info");
  await page.getByLabel(/^Bill line label/).waitFor();
  await page.fill("#discount-label", "Autopay savings");
  await page.fill("#discount-funding", "Rate-payer funded (billing)");
  await shot(7, "1_details", "Autopay › Edit › Name and details");
  await cont();
  await cont();
  await page.locator("[data-discount-step=edit-review]").waitFor();
  await shot(7, "1_review", "Name and details › Review");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await page.locator("[data-discount-edit-saved]").waitFor({ timeout: 15000 });
  await shot(7, "1_saved", "Name and details saved");
  const after = discRows("AUTOPAY");
  const row3 = (await api("GET", `discounts/${state.discounts["3"]}`)).data;
  check(7, 1, "Name and details: the SAME row and the SAME version, name and funding changed", after.length === before.length && after[0][0] === before[0][0] && after[0][3] === before[0][3] && after[0][2] === "Autopay savings" && row3.funding_source === "Rate-payer funded (billing)", `before ${JSON.stringify(before)} · after ${JSON.stringify(after)} · served ${row3.name} / ${row3.funding_source}`);
  await goDisc(state.discounts["3"]);
  await shot(7, "1_overview", "Autopay › Overview after the rename");
  const ov3 = await text();
  check(7, 1, "Name and details: the details page shows the new name and funding source", ov3.includes("Autopay savings") && ov3.includes("Rate-payer funded (billing)"), ov3.slice(0, 200));

  // 7.2 Senior 15% → 12% from 01/01/2027
  await editAt("1", "change");
  const value = page.getByRole("textbox", { name: /^Percent off/ });
  await value.waitFor();
  await value.fill("12");
  await page.getByLabel(/^New value starts/).fill("2027-01-01");
  await shot(7, "2_value", "Senior › New value 12% from 01/01/2027");
  await cont();
  await page.locator("[data-discount-step=edit-review]").waitFor();
  await shot(7, "2_review", "New value › Review");
  const review2 = await text();
  check(7, 2, "New value Review: 15% → 12%, −$9.00 → −$7.20 on $60.00, bills before 01/01/2027 keep 15%", review2.includes("12") && review2.includes("$7.20") && review2.includes("$9.00") && review2.includes("01/01/2027"), review2.match(/What changes.{0,400}/)?.[0] ?? review2.slice(0, 400));
  await page.getByRole("button", { name: "Save new value", exact: true }).click();
  await page.locator("[data-discount-edit-saved]").waitFor({ timeout: 15000 });
  await shot(7, "2_saved", "New value saved");
  const sv = versionsOf("1");
  check(7, 2, "DB: v1 15% ends 12/31/2026, v2 12% starts 01/01/2027, nothing deleted", sv.length === 2 && sv[0][3] === "15.00" && sv[0][4] === "2026-10-01" && sv[0][5] === "2026-12-31" && sv[1][3] === "12.00" && sv[1][4] === "2027-01-01" && sv[1][5] === "", JSON.stringify(sv.map((v) => v.slice(1, 6))));
  const row1 = (await api("GET", `discounts/${state.discounts["1"]}`)).data;
  const vers1 = (await api("GET", `discounts/${state.discounts["1"]}/versions`)).data;
  const vlist = vers1?.results ?? vers1 ?? [];
  check(7, 2, "API: today 15% v1, scheduled next 12% from 01/01/2027; versions v1 → 12/31/2026 and v2 from 01/01/2027", row1.value_display?.startsWith("15") && row1.scheduled_next?.effective_from === "2027-01-01" && vlist.length === 2, `${row1.value_display} · next ${JSON.stringify(row1.scheduled_next)} · ${vlist.map((v) => `v${v.version_no} ${v.value_display} ${v.effective_from}→${v.effective_to ?? "-"}`).join(" | ")}`);
  await goDisc(state.discounts["1"]);
  await shot(7, "2_overview", "Senior › Overview with v2 scheduled");
  const ov1 = await text();
  check(7, 2, "Screen: the details page shows 12/31/2026 and 01/01/2027", ov1.includes("12/31/2026") && ov1.includes("01/01/2027"), ov1.match(/.{0,80}01\/01\/2027.{0,80}/)?.[0] ?? ov1.slice(0, 300));

  // 7.3 Fix a mistake — Veteran typed 1.5 instead of 15
  await editAt("9", "correct");
  const valueC = page.getByRole("textbox", { name: /^Percent off/ });
  await valueC.waitFor();
  await valueC.fill("15");
  await page.getByLabel(/Why it was wrong/).fill("Typed 1.5 instead of 15.");
  await shot(7, "3_fix", "Veteran › Fix a mistake 1.5 → 15 with a reason");
  await cont();
  await page.locator("[data-discount-step=edit-review]").waitFor();
  await shot(7, "3_review", "Fix a mistake › Review");
  await page.getByRole("button", { name: "Save correction", exact: true }).click();
  await page.locator("[data-discount-edit-saved]").waitFor({ timeout: 15000 });
  await shot(7, "3_saved", "Fix a mistake saved");
  const vv = versionsOf("9");
  check(7, 3, "DB: the old row (1.5%) is KEPT and marked replaced; the new one (15%) corrects it, same dates, reason stored", vv.length === 2 && vv[0][3] === "1.50" && vv[0][7] === vv[1][0] && vv[1][3] === "15.00" && vv[1][6] === vv[0][0] && vv[1][4] === vv[0][4] && vv[1][5] === vv[0][5] && vv[1][8] === "Typed 1.5 instead of 15.", JSON.stringify(vv.map((v) => [v[1], v[2], v[3], v[4], v[5], v[6] ? "corrects v1" : "", v[7] ? "superseded" : "", v[8]])));
  const row9 = (await api("GET", `discounts/${state.discounts["9"]}`)).data;
  check(7, 3, "API: Veteran now serves 15%", row9.value_display?.startsWith("15"), row9.value_display);

  // 7.4 Audit shows each
  for (const [key, want, label] of [["3", ["discount.details_updated", "discount.updated"], "Name and details"], ["1", ["discount.new_value"], "New value"], ["9", ["discount.correction_created", "discount.version_corrected"], "Fix a mistake"]]) {
    const audit = await auditOf(key);
    await goDisc(state.discounts[key], "audit");
    await shot(7, `4_audit_${key}`, `${label} › Audit`);
    const body = await text();
    const hit = audit.find((a) => want.includes(a.action));
    check(7, 4, `Audit shows the ${label} edit, by Dana`, Boolean(hit) && body.includes("Dana Whitfield"), audit.slice(0, 4).map((a) => `${a.action} · ${a.actor?.name ?? a.actor} · ${a.reason ?? ""} · ${JSON.stringify(a.after ?? "").slice(0, 80)}`).join(" | "));
  }
}

// DEF-RAT-9338 walked again after its fix: rename Autopay back, read the Audit tab.
if (PHASES.has("7redo")) {
  await signIn(TENANT, EMAIL);
  const was = (await api("GET", `discounts/${state.discounts["3"]}`)).data?.name;
  const to = was === "Autopay discount" ? "Autopay savings" : "Autopay discount";
  await editAt("3", "info");
  await page.getByLabel(/^Bill line label/).waitFor();
  await page.fill("#discount-label", to);
  await cont();
  await cont();
  await page.locator("[data-discount-step=edit-review]").waitFor();
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await page.locator("[data-discount-edit-saved]").waitFor({ timeout: 15000 });
  await goDisc(state.discounts["3"], "audit");
  await shot(7, "5_audit_rename", "Autopay › Audit after a rename alone (DEF-RAT-9338)");
  const body = await text();
  const audit = await auditOf("3");
  const top = audit[0];
  check(7, 5, "a rename alone is in the Audit: old name → new name, by Dana (DEF-RAT-9338)", top?.action === "discount.updated" && top?.before?.name === was && top?.after?.name === to && body.includes(`${was} → ${to}`) && body.includes("Dana Whitfield"), `${top?.action} · ${top?.before?.name} → ${top?.after?.name} · on screen: ${body.match(/Name:[^|]{0,60}/)?.[0] ?? "no Name row"}`);
}

// ═══ STEP 8 (screen half) — the issued bills on screen ═════════════════════
// The runs are `cr166_discwalk_world.py run …`; the server read billing uses is
// `… lookup SENIOR 2026-12-31 2027-01-01`. This phase opens Ruth's bills.
const ruthBills = () =>
  dbRows(`select i.id, i.period_end, i.total::numeric(12,2),
                 coalesce((select string_agg(l.description||' '||l.amount::numeric(12,2), '; ' order by l.amount) from invoice_lines l where l.invoice_id=i.id and l.kind='discount'),'')
            from invoices i join accounts a on a.id=i.account_id
           where a.account_no='${ACCTS["DW-SENIOR"].number}' order by i.period_end`);
if (PHASES.has("8")) {
  await signIn(TENANT, EMAIL);
  const bills = ruthBills();
  for (const [id, end, total, discLines] of bills) {
    await page.goto(`${BASE}/${TENANT}/billing/bills/${id}`, { waitUntil: "networkidle" });
    await page.getByRole("tab", { name: /^Charges/ }).click();
    await settle(1200);
    await shot(8, `bill_${end}${process.env.SUFFIX ?? ""}`, `Ruth's bill to ${end} › Charges`);
    const body = await text();
    const want = end === "2026-12-15" ? "9.00" : end === "2027-01-15" ? "7.20" : null;
    // DEF-BIL-9339: the discount lines sit under a Discounts heading, and no
    // Taxes & fees heading is drawn on a bill with no tax or fee
    const heads = await page.$$eval("main th[colspan]", (els) => els.map((e) => (e.textContent ?? "").trim()));
    check(8, `heads_${end}${process.env.SUFFIX ?? ""}`, `Ruth's bill to ${end}: discounts under "Discounts", no "Taxes & fees" heading (DEF-BIL-9339)`, heads.includes("Discounts") && !heads.some((h) => /taxes/i.test(h)), heads.join(" | "));
    if (want) check(8, `screen_${end}${process.env.SUFFIX ?? ""}`, `Ruth's bill to ${end} shows Senior −$${want} on screen`, body.includes(want) && body.includes("Senior"), `${discLines} · total ${total} · on screen ${body.match(/Senior.{0,60}/)?.[0] ?? "no Senior line"}`);
    else check(8, `screen_${end}${process.env.SUFFIX ?? ""}`, `Ruth's bill to ${end} shows no Senior line on screen`, !body.includes("Senior"), `${discLines} · total ${total}`);
  }
}

// ═══ STEP 10 — Retire Senior on a date, through the More menu ══════════════
if (PHASES.has("10")) {
  await signIn(TENANT, EMAIL);
  await goDisc(state.discounts["1"]);
  await page.locator("[data-discount-more] summary").click();
  await page.locator("[data-testid=discount-more-retire]").click();
  await settle(500);
  await page.fill("#effective_to", process.env.RETIRE_ON ?? "2027-01-31");
  await page.fill("#reason", "Walk step 10: programme closing");
  await shot(10, 1, "Retire Senior dialog, last day 01/31/2027");
  await page.locator("[role=dialog]").getByRole("button", { name: "Retire", exact: true }).click();
  await settle(2000);
  await shot(10, 2, "Senior after Retire");
  const open = await page.$("[role=dialog]");
  const sv = versionsOf("1");
  const row = (await api("GET", `discounts/${state.discounts["1"]}`)).data;
  const enr = enrolmentsOf("1");
  check(10, 1, "Retire stores the last day on the versions in force; nothing deleted; the dialog closes", !open && sv.length === 2 && sv[1][5] === (process.env.RETIRE_ON ?? "2027-01-31"), `${JSON.stringify(sv.map((v) => v.slice(1, 6)))} · served ${row.status} to ${row.effective_to} · enrolments ${JSON.stringify(enr)}`);
  const audit = await auditOf("1");
  check(10, 1, "Audit shows the retire, by Dana", audit.some((a) => a.action === "discount.retired"), audit.slice(0, 3).map((a) => `${a.action} · ${a.actor?.name ?? a.actor}`).join(" | "));
  await goDisc(state.discounts["1"], "audit");
  await shot(10, 3, "Senior › Audit after Retire");
}

// DEF-RAT-9340 walked again after its fix: retire Lifeline (nobody enrolled)
// through the same dialog and confirm it closes once the date is stored.
if (PHASES.has("10redo")) {
  await signIn(TENANT, EMAIL);
  await goDisc(state.discounts["5"]);
  await page.locator("[data-discount-more] summary").click();
  await page.locator("[data-testid=discount-more-retire]").click();
  await settle(500);
  await page.fill("#effective_to", "2027-02-28");
  await page.locator("[role=dialog]").getByRole("button", { name: "Retire", exact: true }).click();
  await settle(2000);
  await shot(10, "4_redo", "Lifeline after Retire — the dialog has closed (DEF-RAT-9340)");
  const open = await page.$("[role=dialog]");
  const lv = versionsOf("5");
  check(10, 4, "Retire closes its dialog once the date is stored (DEF-RAT-9340)", !open && lv[lv.length - 1]?.[5] === "2027-02-28", `dialog ${open ? "still open" : "closed"} · ${JSON.stringify(lv.map((v) => v.slice(1, 6)))}`);
}

// ═══ STEP 11 — Utility B; then every language on the four screens ══════════
if (PHASES.has("11b")) {
  await signIn(B_TENANT, B_EMAIL);
  await page.goto(`${BASE}/${B_TENANT}/${DISC}`, { waitUntil: "networkidle" });
  await shot(11, "b_list", "Riverbend Water › Discounts");
  const body = await text();
  const leaked = ["SENIOR", "Senior discount", "CAP credit", "Autopay savings", "Veteran", "Municipal account", "Lifeline"].filter((w) => body.includes(w));
  check(11, "b1", "Utility B's list shows none of A's discounts", leaked.length === 0, leaked.length ? `on screen: ${leaked.join(", ")}` : body.slice(0, 200));
  const list = await api("GET", "discounts?page=1&per=50");
  const rows = list.data?.results ?? [];
  const aCodes = ["SENIOR", "CAP", "AUTOPAY", "MUNI", "LIFELINE", "LEADWAIVE", "GARDEN", "PAPERLESS", "VETERAN"];
  check(11, "b2", "Utility B's API list carries none of A's discounts", list.status === 200 && !rows.some((r) => aCodes.includes(r.code)), `${list.status} · ${rows.length} rows: ${rows.map((r) => r.code).join(",")}`);
  const direct = await api("GET", `discounts/${state.discounts["1"]}`);
  const directAcc = await api("GET", `discounts/${state.discounts["1"]}/accounts?page=1&per=50`);
  const directAudit = await api("GET", `discounts/${state.discounts["1"]}/audit?page=1&per=50`);
  const write = await api("POST", `discounts/${state.discounts["1"]}/retire`, { effective_to: "2027-03-31" });
  check(11, "b3", "Utility B asking for A's Senior by its id: not found (read, accounts, audit) and a write refused", [direct, directAcc, directAudit].every((r) => r.status === 404) && write.status >= 400, `read ${direct.status} · accounts ${directAcc.status} · audit ${directAudit.status} · retire ${write.status}`);
  await goDisc(state.discounts["1"]);
  await settle(1500);
  currentTenant = B_TENANT;
  await page.goto(`${BASE}/${B_TENANT}/${DISC}/${state.discounts["1"]}`, { waitUntil: "networkidle" });
  await shot(11, "b_direct", "Riverbend Water › A's Senior id typed into the address bar");
  const dbody = await text();
  check(11, "b4", "Utility B typing A's discount address sees no Senior", !dbody.includes("Senior discount") && !dbody.includes("SENIOR"), dbody.slice(0, 200));
  const unchanged = versionsOf("1");
  check(11, "b3", "A's Senior unchanged by B's refused write", unchanged[1]?.[5] === (process.env.RETIRE_ON ?? "2027-01-31"), JSON.stringify(unchanged.map((v) => v.slice(1, 6))));
}

const PROBES = [
  "Overview", "Accounts", "Audit", "Enrolled", "Receiving", "Offered to", "Granted", "units on its plans",
  "this month", "Version", "No end", "Retire", "Approve", "Send back", "Duplicate", "Details", "Eligibility",
  "Review", "Continue", "Cancel", "Search", "Filter", "Status", "Value", "Verification", "Code", "Discount",
  "What changes", "How it is saved", "Before", "After", "Percent off", "Bill line label", "Program owner",
  "Who qualifies", "Starts", "Ends", "Limits", "This discount", "off subtotal", "Renew by", "Customer",
  "Enroll", "New value", "Save", "Edit", "Plans", "Type", "From", "Active", "Draft", "Scheduled",
  "Retired", "Waiting approval", "Proof pending", "Name and details", "Fix a mistake", "What to change",
];
// Words that are the utility's DATA (discount names, list values it typed or
// seeded), the shell's known untranslated nav (CR-166 §15), or proper nouns:
// excluded from the probe hits by the exact phrase they appear in.
const DATA = ["Autopay savings", "Autopay discount", "Senior discount", "CAP credit", "Municipal account", "Lifeline water", "Veteran discount",
  "Lead line waiver", "Garden allowance", "Paperless credit", "Discount walk · Residential", "Discount walk · Municipal",
  "Discount walk · Garden", "Discount walk · Other", "Rate-payer funded (billing)", "Rate-payer funded", "State grant",
  "City budget", "Conservation fund", "Discount Walk Way", "Dana Whitfield", "Ruth Alvarez", "Carl Jensen", "Pat Lindgren", "Brazos Bend"];
async function langPass(name, lang, step) {
  await setLang(lang);
  await settle(900);
  // FORCE_SQUEEZE=1 proves the broken-word check can fail (law 7): it narrows
  // every list cell to one character's width, the DEF-RAT-9319 shape.
  if (process.env.FORCE_SQUEEZE) await page.addStyleTag({ content: "main td span { display:inline-block; width:14px; word-break:break-all }" });
  const file = `${OUT}/discwalk_11_${name}_${lang}.png`;
  await page.screenshot({ path: file, fullPage: true });
  // <option> text is read too by innerText; a select's closed options are the
  // utility's list values (program owners), so they are left out here.
  let body = (await page.evaluate(() => {
    const main = document.querySelector("main").cloneNode(true);
    main.querySelectorAll("option").forEach((o) => o.remove());
    document.body.appendChild(main);
    main.style.position = "absolute";
    const out = main.innerText;
    main.remove();
    return out;
  })).trim();
  for (const d of DATA) body = body.split(d).join(" ");
  const m = await page.evaluate(() => {
    const doc = document.documentElement;
    const box = document.querySelector("main [data-table-scroll]");
    const t = document.querySelector("main table");
    let typeLines = 0;
    if (t && location.pathname.endsWith("/discounts")) {
      const rows = [...t.querySelectorAll("tbody tr")];
      typeLines = Math.max(0, ...rows.map((r) => {
        const c = r.children[2];
        const lh = parseFloat(getComputedStyle(c).lineHeight) || 18;
        return Math.round((c.querySelector("span")?.getBoundingClientRect().height ?? lh) / lh) || 1;
      }));
    }
    // a word BROKEN across lines (the ja/ko "定/率 one character a line" of
    // DEF-RAT-9319): every whitespace-separated word of every heading, label,
    // button and tab is measured with a Range; a word whose glyphs sit on more
    // than one line is reported. Wrapping BETWEEN words is allowed.
    const squeezed = [];
    for (const el of document.querySelectorAll("main th, main td, main button, main label, main h1, main h2, main [role=tab]")) {
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const text = node.textContent ?? "";
        const re = /\S+/g;
        for (let m = re.exec(text); m; m = re.exec(text)) {
          if (m[0].length < 2) continue;
          const range = document.createRange();
          range.setStart(node, m.index);
          range.setEnd(node, m.index + m[0].length);
          const tops = new Set([...range.getClientRects()].filter((r) => r.width > 0).map((r) => Math.round(r.top)));
          if (tops.size > 1) squeezed.push(m[0].slice(0, 20));
        }
      }
    }
    return { page: doc.scrollWidth - doc.clientWidth, table: t ? Math.round(t.getBoundingClientRect().width) : null, box: box ? box.clientWidth : null, typeLines, squeezed };
  });
  // The same word in that language, not English left behind (CR-166 §15 lists
  // them): German "Details" and "Code", French "Code" and "Type".
  const SAME = { de: ["Details", "Code"], "fr-FR": ["Code", "Type"] };
  const hits = lang === "en" ? [] : PROBES.filter((w) => !(SAME[lang] ?? []).includes(w) && new RegExp(`(^|[^A-Za-z])${w}([^A-Za-z]|$)`).test(body));
  const fits = m.page <= 0 && (m.table === null || m.box === null || m.table <= m.box) && m.typeLines <= 3 && m.squeezed.length === 0;
  check(11, `${name}_${lang}`, `${name} in ${lang}: no English left, nothing wraps badly at 1440`, hits.length === 0 && fits && body.length > 80, `english: ${hits.join(", ") || "none"} · ${JSON.stringify(m)}`);
  return { hits, m };
}
if (PHASES.has("11lang")) {
  await signIn(TENANT, EMAIL);
  const langs = (process.env.LANGS ?? LANGS.join(",")).split(",");
  for (const lang of langs) {
    await goList();
    await page.getByRole("table").waitFor();
    await langPass("list", lang);
    await setLang("en");
    await openNew();
    await page.fill("#discount-code", "SENIOR2");
    await page.fill("#discount-label", "Senior discount");
    await page.getByRole("textbox", { name: /^Percent off/ }).fill("15");
    await langPass("new", lang);
    await setLang("en");
    await goDisc(state.discounts["1"]);
    await page.locator("[data-discount-overview]").waitFor();
    await langPass("overview", lang);
    await setLang("en");
    await goDisc(state.discounts["1"], "accounts");
    await settle(800);
    await langPass("accounts", lang);
    await setLang("en");
    await editAt("2", "change");
    await page.getByRole("textbox", { name: /^Dollars off|^Amount off|^Amount/ }).or(page.locator("#discount-value")).first().fill("20");
    await page.getByLabel(/^New value starts/).fill("2027-03-01");
    await cont();
    await langPass("edit", lang);
    await setLang("en");
  }
}

await browser.close();
