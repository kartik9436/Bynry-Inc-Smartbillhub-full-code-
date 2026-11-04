// ── Trace ──────────────────────────────────────────────
// Change:  CR-162-BRC10 — the New Connection lifecycle (lane NC-A): the premises
//          type's Account type on Settings, Pending at Create, Approve with the
//          open-orders warning, Activate what is ready, Activated, the To-do tab
//          with notes, and a single-family build with no master account.
// ───────────────────────────────────────────────────────
//
// THE WALK, IN A REAL CHROMIUM, AGAINST A REAL POSTGRESQL. Expects:
//   * the API — `manage.py runserver` on the walk's own scratch database, with
//     `seed_demo` run and the two builds made by
//     `NCA_STEP=create manage.py shell < nca_walk_seed.py` (G Trade Tower, an
//     apartment complex with Unit 1 and Unit 2, two installation orders each;
//     7 Wren Lane, single-family, one unit, no owner);
//   * the SPA — `vite build --mode wolocal` then
//     `PORT=8472 API_PROXY_TARGET=http://127.0.0.1:8471 node 07-frontend/server.mjs`;
//   * IDS — the JSON the seed step wrote (build, premises and master ids);
//   * COMPLETE — a shell command that marks a unit's orders complete, run
//     between screens exactly as a crew's accepted result would land.
//
//   BASE=http://127.0.0.1:8472 IDS=<json> OUT=<dir> COMPLETE="<cmd>" \
//     node 10-scripts/cr162_new_connection_lifecycle_walkthrough.mjs
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8472";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr162-walk";
const IDS = JSON.parse(readFileSync(process.env.IDS, "utf8"));
// A fresh code each run, so a re-run on the same scratch database adds a new type.
const NEW_TYPE = `mobile_home_park_${Date.now().toString(36)}`;
const COMPLETE = process.env.COMPLETE ?? "";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found");
}

let failures = 0;
function check(name, ok, detail = "") {
  if (!ok) failures += 1;
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${name}${detail ? `\n          ${detail}` : ""}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
page.on("pageerror", (e) => console.log("  page error:", e.message));
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 500) console.log(`  api ${r.status()} ${r.url()}`);
});

async function shot(name) {
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}
async function open(path) {
  await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
}
async function text(selector) {
  const loc = page.locator(selector).first();
  return (await loc.count()) === 0 ? null : ((await loc.textContent()) ?? "").trim();
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
console.log(`signed in — ${page.url()}`);

// ── 1 · Settings: the premises types carry an Account type ─────────────────
await open("/settings/reference-data?list=premises_types");
await page.locator("table").first().waitFor({ timeout: 30000 });
const heads = await page.$$eval("table thead th", (ths) => ths.map((t) => t.textContent.trim()));
check("Settings premises types: an 'Account type' column", heads.some((h) => h.startsWith("Account type")), heads.join(" | "));
const apartment = await text('tbody tr:has-text("apartment_complex") [data-account-kind]');
const single = await text('tbody tr:has-text("single_family") [data-account-kind]');
check("Apartment complex reads Master account", apartment === "Master account", String(apartment));
check("Single-family reads Regular account", single === "Regular account", String(single));
await shot("nca_01_settings_premises_types");

await page.getByRole("button", { name: "+ Add entry" }).first().click();
await page.locator("#code").waitFor({ timeout: 15000 });
await page.locator("#code").fill(NEW_TYPE);
await page.locator("#name").fill("Mobile home park");
await page.locator(".modal-foot button[type=submit], .modal-foot button").last().click();
await page.waitForTimeout(700);
const refusal = await text('[data-field="account_kind"] .field-error, #account_kind-error');
check("Saving with no account type is refused", (refusal ?? "").includes("Choose the account type"), String(refusal));
await shot("nca_02_settings_add_type_refused");
await page.locator(".seg-opt", { hasText: "Master account" }).first().click();
await page.locator(".modal-foot button[type=submit], .modal-foot button").last().click();
await page.waitForTimeout(1200);
await open("/settings/reference-data?list=premises_types");
const added = await text(`tbody tr:has-text("${NEW_TYPE}") [data-account-kind]`);
check("Mobile home park saved as Master account", added === "Master account", String(added));
await shot("nca_03_settings_type_saved");

// ── 2 · Create made everything Pending ─────────────────────────────────────
await open(`/premises/${IDS.tower_premises}`);
const tabs = await page.$$eval('[role="tab"], nav a', (els) => els.map((e) => e.textContent.trim()));
check("Premises page has no Build tab", !tabs.includes("Build"), tabs.join(" | "));
const premisesLink = await page.locator("[data-open-request]").first().getAttribute("href").catch(() => null);
check(
  "Pending premises links to its New Connection request",
  premisesLink === `/${TENANT}/connections/${IDS.tower}`,
  String(premisesLink),
);
await shot("nca_04_premises_pending_with_link");

await open(`/accounts/${IDS.tower_master}`);
const masterLink = await page.locator("[data-open-request]").first().getAttribute("href").catch(() => null);
check("Pending master account links to the request", masterLink === `/${TENANT}/connections/${IDS.tower}`, String(masterLink));
const pill = await page.locator("body").textContent();
check("Master account reads Pending", /Pending activation/i.test(pill ?? ""));
await shot("nca_05_master_account_pending");

// ── 3 · The request: Units tab, nothing ready yet ──────────────────────────
await open(`/connections/${IDS.tower}?tab=units`);
await page.locator('[data-table="build-units"]').waitFor({ timeout: 30000 });
const unitHeads = await page.$$eval('[data-table="build-units"] thead th', (ths) => ths.map((t) => t.textContent.trim()));
check("Units tab draws Unit type · Asset type · Size · Qty · Asset ID · Work order · State",
  ["Unit type", "Asset type", "Size", "Qty", "Asset ID", "Work order", "State"].every((h) => unitHeads.includes(h)),
  unitHeads.join(" | "));
await shot("nca_06_units_tab_before");

// ── 4 · Unit 1's orders complete → Approve → the warning ───────────────────
execSync(`${COMPLETE} complete_unit1`, { stdio: "inherit" });
await open(`/connections/${IDS.tower}?tab=units`);
await page.locator('[data-act="approve"]').waitFor({ timeout: 30000 });
await page.locator('[data-act="approve"]').click();
await page.locator("[data-activate-dialog]").waitFor({ timeout: 15000 });
const warning = await text("[data-open-orders]");
const warningLine = await text('[data-warning="activate-open-orders"]');
check("Warning lists Unit 2's open orders", (warning ?? "").split(", ").length === 2, `${warningLine}`);
check("Warning reads '2 of 4 not complete'", (warningLine ?? "").includes("2 of 4 not complete"), String(warningLine));
await shot("nca_07_approve_warning");
await page.locator('[data-act="activateReady"]').click();
await page.locator("[data-activate-dialog]").waitFor({ state: "detached", timeout: 30000 });
await open(`/connections/${IDS.tower}?tab=units`);
const stateWord = await page.locator("[data-build-detail]").first().textContent();
check("Request reads Partly activated", /Partly activated/i.test(stateWord ?? ""));
const unit1Active = await page.$$eval('[data-unit-group="Unit 1"] [data-unit-state]', (els) => els.map((e) => e.getAttribute("data-unit-state")));
check("Unit 1 is Active", unit1Active.includes("activated"), unit1Active.join(","));
const installed = await page.locator('[data-ready] :text("Installed")').count();
check("Unit 1's 2 meters read Installed", installed >= 2, `count ${installed}`);
await shot("nca_08_partly_activated");

await open(`/premises/${IDS.tower_premises}`);
check("Premises now Active (no pending link)", (await page.locator("[data-open-request]").count()) === 0);
await shot("nca_09_premises_active");
await open(`/accounts/${IDS.tower_master}`);
// The page's text runs words together ("ActiveBilling"), so a \b regex over the
// body is a check that fails wrongly. Ask what the Pending state DRAWS instead:
// its request link and its status word, both gone once the account is Active.
const masterLinks = await page.locator("[data-open-request]").count();
const masterNow = (await page.locator("body").textContent()) ?? "";
check(
  "Master account now Active (no request link, no Pending activation)",
  masterLinks === 0 && !/Pending activation/.test(masterNow),
  `links ${masterLinks}`,
);
await shot("nca_10_master_active");

// ── 5 · The rest complete → Activate all ready → Activated ─────────────────
execSync(`${COMPLETE} complete_rest`, { stdio: "inherit" });
await open(`/connections/${IDS.tower}?tab=units`);
await page.locator('[data-act="activateAllReady"]').click();
await page.locator("[data-activate-dialog]").waitFor({ timeout: 15000 });
await shot("nca_11_activate_all_dialog");
await page.locator('[data-act="activateReady"]').click();
await page.locator("[data-activate-dialog]").waitFor({ state: "detached", timeout: 30000 });
await open(`/connections/${IDS.tower}?tab=overview`);
const finalState = await page.locator("[data-build-detail]").first().textContent();
check("Request reads Activated", /Activated/i.test(finalState ?? "") && !/Partly activated/i.test(finalState ?? ""));
await shot("nca_12_activated");

// ── 6 · The To-do tab: a to-do and a note ──────────────────────────────────
await open(`/connections/${IDS.tower}?tab=todo`);
await page.locator('[data-act="addTodo"]').click();
await page.locator("#text").fill("Collect the meter keys");
await page.locator(".modal-foot button").last().click();
await page.waitForTimeout(1000);
await page.locator('[data-act="addNote"]').click();
await page.locator("#text").fill("Owner prefers morning visits");
await page.locator(".modal-foot button").last().click();
await page.waitForTimeout(1200);
const kinds = await page.$$eval('[data-table="build-todos"] tbody tr', (trs) => trs.map((t) => t.getAttribute("data-todo-row")));
check("To-do tab lists the note first, then the to-do", kinds.join(",") === "note,todo", kinds.join(","));
await shot("nca_13_todo_tab");

// ── 7 · Single-family: no master account ──────────────────────────────────
check("Single-family build made no master account", IDS.house_master === null, String(IDS.house_master));
await open(`/premises/${IDS.house_premises}`);
const houseLink = await page.locator("[data-open-request]").first().getAttribute("href").catch(() => null);
check("Single-family premises Pending, linked to its request", houseLink === `/${TENANT}/connections/${IDS.house}`, String(houseLink));
await shot("nca_14_single_family_pending");

await browser.close();
console.log(failures === 0 ? "\nWALK: ALL PASS" : `\nWALK: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
