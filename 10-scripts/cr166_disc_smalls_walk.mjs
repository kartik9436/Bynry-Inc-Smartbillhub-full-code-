// ── Trace ──────────────────────────────────────────────
// Change:  CR-166-BRC10 follow-up (lane DISC-SMALLS, 2026-10-03) — the browser
//          proof of the four small things, on PostgreSQL at 1440, clicking:
//          DEF-RAT-9310 Duplicate · DEF-478 add/remove a plan from the discount
//          page · DEF-1005 CSV on Accounts and Audit · DEF-BIL-9346 the bill's
//          Document tab names its discounts. Shape copied from
//          `cr166_discwalk.mjs`.
// ───────────────────────────────────────────────────────
//
// Stack: API `manage.py runserver` on a scratch PostgreSQL 16 database with
// `migrate` + `seed_demo` + `load_sample_data --tenant brazosbend` +
// `10-scripts/cr166_discwalk_world.py setup`; SPA `vite build --mode wolocal`
// served by `07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:5371 PGURL=postgres://postgres@127.0.0.1:55433/<db> \
//     DATABASE_URL=<same> OUT=08-qa/discounts-2026-10-03/smalls node 10-scripts/cr166_disc_smalls_walk.mjs
//
// It uses the sample SENIOR discount and the walk world's *Discount walk ·
// Residential* plan and Ruth Alvarez (DW-SENIOR); it issues ONE real cycle run
// (`cr166_discwalk_world.py run`) between adding the plan and removing it.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5371";
const TENANT = "brazosbend";
const EMAIL = "dana@brazosbendutilities.com";
const PASSWORD = "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr166-smalls";
const PGURL = process.env.PGURL ?? "postgres://postgres@127.0.0.1:55433/sbh_discsmalls";
const RUN = (process.env.RUN ?? "2026-09-16,2026-10-15").split(",");
const PLAN_NAME = "Discount walk · Residential";
const COPY_CODE = process.env.COPY_CODE ?? "SENIOR-RURAL";
mkdirSync(OUT, { recursive: true });

const results = [];
function check(step, what, pass, evidence) {
  const row = { step, what, pass: Boolean(pass), evidence: String(evidence ?? "") };
  results.push(row);
  writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2));
  console.log(`${row.pass ? "PASS" : "FAIL"} ${step} ${what} — ${row.evidence.slice(0, 300)}`);
}
const db = (sql) => execFileSync("psql", [PGURL, "-AtF", "|", "-c", sql], { encoding: "utf8" }).trim();

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const dir of readdirSync("/opt/pw-browsers")) {
    if (!dir.startsWith("chromium")) continue;
    for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
      const candidate = join("/opt/pw-browsers", dir, sub);
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
const page = await context.newPage();
const settle = (ms = 900) => page.waitForTimeout(ms);
async function shot(name, caption, fullPage = true) {
  await settle();
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage });
  console.log(`  [shot] ${name}.png (${statSync(path).size} bytes) — ${caption}`);
}
async function download(trigger) {
  const [file] = await Promise.all([page.waitForEvent("download"), trigger()]);
  const path = `${OUT}/${file.suggestedFilename()}`;
  await file.saveAs(path);
  return readFileSync(path, "utf8");
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

const tenantId = db(`select id from tenants where subdomain='${TENANT}'`);
const senior = db(`select id from discounts where tenant_id='${tenantId}' and code='SENIOR'`);
const planId = db(`select id from rate_plans where tenant_id='${tenantId}' and name='${PLAN_NAME}'`);
const page$ = (tab = "") => `${BASE}/${TENANT}/plans-rates/discounts/${senior}${tab ? `?tab=${tab}` : ""}`;

// ── 1 · DEF-RAT-9310 Duplicate ─────────────────────────────────────────────
await page.goto(page$(), { waitUntil: "networkidle" });
await page.locator("[data-discount-more] summary").click();
await shot("s01-more-duplicate-live", "More ▾ open — Duplicate enabled (image 23)", false);
const dupEnabled = await page.getByTestId("discount-more-duplicate").isEnabled();
check("1.1", "More ▾ Duplicate is enabled on a live discount", dupEnabled, `enabled=${dupEnabled}`);
await page.getByTestId("discount-more-duplicate").click();
const dialog = page.getByRole("dialog");
await dialog.waitFor();
await shot("s02-duplicate-dialog", "Duplicate dialog — code and bill line label", false);
await dialog.getByRole("button", { name: "Duplicate" }).click();
await settle(500);
await shot("s03-duplicate-empty-refused", "nothing typed — both boxes marked, nothing posted", false);
const marked = (await dialog.textContent()) ?? "";
check("1.2", "empty boxes are refused on the box", marked.includes("Enter a new code.") && marked.includes("Enter a bill line label."), marked.slice(0, 200));
await dialog.getByLabel(/^Code/).fill(COPY_CODE.toLowerCase());
await dialog.getByLabel(/Bill line label/).fill("Rural senior discount");
await dialog.getByRole("button", { name: "Duplicate" }).click();
await page.waitForURL((u) => !u.pathname.includes(senior), { timeout: 30000 });
await page.waitForSelector("text=Rural senior discount");
await shot("s04-duplicate-landed-on-draft", "lands on the copy — Draft, same value and conditions");
const copy = db(`select id from discounts where tenant_id='${tenantId}' and code='${COPY_CODE}'`);
const src = db(`select v.value, v.eligibility_code, v.enrolment_mode, v.verification_method, coalesce(v.cap_per_bill::text,''), v.stacking_precedence, coalesce(v.recertification_months::text,'') from discount_versions v where v.discount_id='${senior}' and v.status='active' and v.effective_from <= current_date and (v.effective_to is null or v.effective_to >= current_date)`);
const dup = db(`select v.value, v.eligibility_code, v.enrolment_mode, v.verification_method, coalesce(v.cap_per_bill::text,''), v.stacking_precedence, coalesce(v.recertification_months::text,'') from discount_versions v where v.discount_id='${copy}'`);
check("1.3", "the copy's version equals SENIOR's version in force", src !== "" && src === dup, `source=${src} copy=${dup}`);
const dupFacts = db(`select d.status, v.status, coalesce(v.effective_from::text,'none'), (select count(*) from discount_enrolments where discount_id=d.id), (select count(*) from plan_discount_rules where discount_id=d.id) from discounts d join discount_versions v on v.discount_id=d.id where d.id='${copy}'`);
check("1.4", "the copy is a draft with no dates, no enrollments, no plans", dupFacts === "draft|draft|none|0|0", dupFacts);
check("1.5", "the page shows the copy as Draft", ((await page.textContent("body")) ?? "").match(/Draft/i) !== null, page.url());

// ── 2 · DEF-478 add to a plan ──────────────────────────────────────────────
await page.goto(page$("plans"), { waitUntil: "networkidle" });
await shot("s05-plans-tab-before", "Plans tab — + Add to a plan is live");
await page.getByRole("button", { name: "+ Add to a plan" }).click();
await dialog.waitFor();
await dialog.getByRole("combobox").fill("Discount walk");
await dialog.getByText(PLAN_NAME, { exact: true }).first().click();
await dialog.getByRole("button", { name: "Add" }).click();
await settle(500);
check("2.1", "Add with no reason is refused on the box", ((await dialog.textContent()) ?? "").includes("Give a reason."), "Give a reason.");
await dialog.getByLabel(/Reason/).fill("Seniors on the walk tariff");
await shot("s06-add-to-plan-dialog", "Add to a plan — plan and reason", false);
await dialog.getByRole("button", { name: "Add" }).click();
await dialog.waitFor({ state: "detached" });
await page.waitForSelector(`text=${PLAN_NAME}`);
await shot("s07-plans-tab-added", "Plans tab — the walk plan offers it, since today");
const rule = db(`select available_from, coalesce(available_to::text,'open') from plan_discount_rules where discount_id='${senior}' and rate_plan_id='${planId}' order by created_at desc limit 1`);
const today = db("select current_date");
check("2.2", "the binding is offered from today, open-ended", rule === `${today}|open`, rule);

// ── 3 · enrol Ruth (through the Accounts tab) and DEF-1005 Accounts CSV ────
await page.goto(page$("accounts"), { waitUntil: "networkidle" });
await page.getByRole("button", { name: "+ Enroll an account" }).click();
await dialog.waitFor();
await dialog.getByRole("combobox").fill("Ruth");
await dialog.getByText(/Ruth Alvarez/).first().click();
await dialog.getByRole("button", { name: "Enroll" }).click();
await dialog.waitFor({ state: "detached" });
await settle(900);
const verify = page.getByRole("button", { name: /Verify proof/ });
if (await verify.count()) {
  await verify.first().click();
  await settle(900);
}
await shot("s08-accounts-tab-csv", "Accounts tab — ⤓ in the toolbar (image 20)");
const accountsCsv = await download(() => page.getByRole("button", { name: "Download CSV" }).first().click());
writeFileSync(`${OUT}/accounts.csv.txt`, accountsCsv);
const lines = accountsCsv.trim().split(/\r?\n/);
const enrolled = Number(db(`select count(*) from discount_enrolments where discount_id='${senior}' and (ended_on is null or ended_on >= current_date)`));
check("3.1", "Accounts CSV: the header and one row per current enrollment (the whole set)", lines[0].startsWith("Account,Customer,Address,Plan") && lines.length - 1 === enrolled, `${lines.length - 1} rows, ${enrolled} enrolled; ${lines.slice(0, 3).join(" / ")}`);
check("3.2", "Accounts CSV names Ruth by account number, never an id", accountsCsv.includes("Ruth Alvarez") && !accountsCsv.includes(senior), lines.find((l) => l.includes("Ruth")) ?? "");

// ── 4 · DEF-BIL-9346 a real issued bill carrying the discount ──────────────
const world = execFileSync(
  "/tmp/venv_a5c/bin/python",
  ["../10-scripts/cr166_discwalk_world.py", "run", RUN[0], RUN[1]],
  { cwd: new URL("../06-backend/", import.meta.url).pathname, encoding: "utf8", env: { ...process.env, JOBS_EAGER: "false", DJANGO_SETTINGS_MODULE: "config.settings.local" } },
);
writeFileSync(`${OUT}/bill-run.txt`, world);
const bill = db(`select i.id from invoices i join customer_accounts ca on ca.account_id=i.account_id join customers c on c.id=ca.customer_id where i.tenant_id='${tenantId}' and c.display_name='Ruth Alvarez' and i.status='issued' order by i.created_at desc limit 1`);
const dLines = db(`select description, amount from invoice_lines where invoice_id='${bill}' and kind='discount'`);
check("4.1", "Ruth's issued bill carries a discount line", dLines !== "", dLines);
await page.goto(`${BASE}/${TENANT}/billing/bills/${bill}`, { waitUntil: "networkidle" });
await page.waitForSelector('[data-bil="breakdown"]');
await shot("s09-bill-document-discounts", "Document tab — Discounts, never Charged to the bill");
const breakdown = (await page.textContent('[data-bil="breakdown"]')) ?? "";
check("4.2", "Document tab breakdown names Discounts and not 'Charged to the bill'", breakdown.includes("Discounts") && !breakdown.includes("Charged to the bill"), breakdown);
await page.goto(`${BASE}/${TENANT}/billing/bills/${bill}?tab=lines`, { waitUntil: "networkidle" });
await page.waitForSelector('[data-bil="charges-by-service"]');
await shot("s10-bill-charges-by-service", "Charges tab — By service row Discounts");
const byService = (await page.textContent('[data-bil="charges-by-service"]')) ?? "";
check("4.3", "By service names Discounts with its figure, no 'Charged to the bill' row", byService.includes("Discounts") && !byService.includes("Charged to the bill"), byService.slice(0, 300));

// ── 5 · DEF-478 remove from the plan (ruling 2) ────────────────────────────
await page.goto(page$("plans"), { waitUntil: "networkidle" });
await page.getByRole("button", { name: `Remove from ${PLAN_NAME}` }).click();
await dialog.waitFor();
await dialog.getByLabel(/Reason/).fill("Walk tariff closes to seniors");
await shot("s11-remove-from-plan-dialog", "× — danger, the consequence, a reason", false);
await dialog.getByRole("button", { name: "Remove" }).click();
await dialog.waitFor({ state: "detached" });
await settle(900);
await shot("s12-plans-tab-removed", "Plans tab after removal");
const ended = db(`select coalesce(available_to::text,'open') from plan_discount_rules where discount_id='${senior}' and rate_plan_id='${planId}' order by created_at desc limit 1`);
const yesterday = db("select current_date - 1");
check("5.1", "ruling 2: the binding ends yesterday (or is removed if it never started)", ended === yesterday || ended === "", `available_to=${ended || "(row deleted)"}`);
const ruthEnded = db(`select e.ended_on, e.end_reason from discount_enrolments e where e.discount_id='${senior}' order by e.created_at desc limit 1`);
check("5.2", "Ruth's enrollment ended with 'Removed from plan'", ruthEnded.includes(`Removed from plan ${PLAN_NAME}`), ruthEnded);
const keeps = db(`select count(*) from invoice_lines where invoice_id='${bill}' and kind='discount'`);
check("5.3", "the issued bill keeps its discount line (hard rule 4)", Number(keeps) > 0, `${keeps} discount line(s) on the issued bill`);

// ── 6 · Audit, and DEF-1005 Audit CSV ──────────────────────────────────────
await page.goto(page$("audit"), { waitUntil: "networkidle" });
await page.waitForSelector("[data-discount-audit] table");
await shot("s13-audit-with-reasons", "Audit — Added to plan / Removed from plan with the reasons; ⤓");
const audit = (await page.textContent("[data-discount-audit]")) ?? "";
check("6.1", "Audit shows both acts with the person's reasons", audit.includes("Seniors on the walk tariff") && audit.includes("Walk tariff closes to seniors"), audit.slice(0, 300));
const auditCsv = await download(() => page.getByRole("button", { name: "Download CSV" }).first().click());
writeFileSync(`${OUT}/audit.csv.txt`, auditCsv);
const auditRows = auditCsv.trim().split(/\r?\n/);
check("6.2", "Audit CSV: header, every row, the plan by name, no plan id", auditRows[0] === "When,Who,What,Change,Reason" && auditCsv.includes(PLAN_NAME) && !auditCsv.includes(planId), `${auditRows.length - 1} rows`);

await browser.close();
const failed = results.filter((row) => !row.pass);
console.log(`\n${results.length - failed.length} of ${results.length} PASS`);
process.exit(failed.length === 0 ? 0 : 1);
