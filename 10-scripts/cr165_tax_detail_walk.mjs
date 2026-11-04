// ── Trace ──────────────────────────────────────────────
// Change:  CR-165-BRC10 round 3 task 6 — the tax DETAILS page rebuilt from
//          images 18–23 of 05-prototype/taxes-fees-2026-10-03 (DEF-RAT-9272,
//          P29–P43). This photographs the BUILT page in the six drawn states at
//          1440 wide and lays each beside its drawing for a side-by-side look.
// ───────────────────────────────────────────────────────
//
// Expects the same stack as `cr165_taxes_fees_before_walk.mjs`:
//   * the API — `manage.py runserver` on a scratch PostgreSQL 16 database with
//     `migrate` + `seed_demo` run (Brazos Bend, Dana);
//   * the SPA — `vite build --mode wolocal`, then `node 07-frontend/server.mjs`
//     with API_PROXY_TARGET pointing at the API.
//
//   BASE=http://127.0.0.1:8602 OUT=08-qa/taxes-fees-2026-10-03/after \
//     node 10-scripts/cr165_tax_detail_walk.mjs
//
// It stages three taxes through the same doors the screens use — `POST /taxes`
// (as the New form sends it), `POST /taxes/{id}/new-rate`, `PATCH /taxes/{id}`
// for a filing field, `POST /plans/{id}/taxes` — so the Audit tab has real
// rows. Every figure is this script's own; the drawing's are illustrations
// (B14 rule 37). Re-running it over its own leftovers creates nothing twice.
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8492";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = resolve(process.env.OUT ?? "/tmp/cr165-detail-after");
const DRAWINGS = resolve(new URL("../05-prototype/taxes-fees-2026-10-03/images", import.meta.url).pathname);
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
const page = await browser.newPage({ viewport: { width: 1440, height: 1500 } });
const say = (...parts) => console.log(...parts);

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
const check = (label, res) => {
  say(label, res.status, res.status >= 300 ? JSON.stringify(res.data).slice(0, 400) : "");
  return res;
};

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// ── what the three taxes need ───────────────────────────────────────────────
const ledger = await api("GET", "ledger/accounts");
// The chart answers `{rows: [{account_id, code, name}]}` (see `getLedgerAccounts`).
const glRows = (ledger.data?.rows ?? []).map((row) => ({ id: row.account_id, code: row.code, name: row.name }));
const liability = glRows.find((a) => /tax/i.test(String(a.name)) && String(a.code).startsWith("2")) ?? glRows.find((a) => String(a.code).startsWith("2"));
say("liability account", liability?.code, liability?.name);
const accounts = await api("GET", "settings/authority-accounts?per=200");
let authority = (accounts.data?.results ?? []).find((row) => row.account_number === "HC-4417");
if (authority === undefined) {
  authority = check(
    "authority account",
    await api("POST", "settings/authority-accounts", { authority_name: "Harbor City Finance", account_number: "HC-4417" }),
  ).data;
}
const plans = (await api("GET", "plans?per=10")).data?.results ?? [];

const existing = (await api("GET", "taxes?per=200&f.versions=all")).data?.results ?? [];
const byName = (name) => existing.find((row) => row.name === name && row.version === 1) ?? existing.find((row) => row.name === name);

async function ensure(name, body) {
  const have = byName(name);
  if (have !== undefined) {
    say("kept", name);
    return { id: have.id, fresh: false };
  }
  const made = check(`create ${name}`, await api("POST", "taxes", { name, ...body }));
  return { id: made.data?.id, fresh: true };
}

const filing = {
  filing_frequency: "monthly",
  due_date_rule: "20th_next_month",
  liability_gl_account_id: liability?.id,
  discount_treatment: "after",
  rounding_rule: "half_up",
  base_includes_usage: true,
  base_includes_base: true,
  premises_scope_kind: null,
  premises_scope_value: "",
};

// Image 18–21: a city levy typed far too high, coded, every filing field set.
const harbor = await ensure("Harbor City Levy", {
  ...filing,
  jurisdiction: { name: "Harbor City", authority: "Harbor City", level: "city", reference_no: null },
  kind: "percent",
  rate: "0.625",
  applies_to_services: ["electric"],
  applies_to_customer_classes: [],
  effective_from: "2026-09-01",
  effective_to: null,
  code: "HC-LEVY",
  bill_label: "Harbor City levy",
  authority_account_id: authority?.id,
  collection_allowance_percent: "0.005",
  interest_penalty_percent: "0.015",
  interest_penalty_basis: "monthly",
});
if (harbor.fresh) {
  check("  reminder", await api("PATCH", `taxes/${harbor.id}`, { filing_reminder_recipient: "filings@brazosbend.example" }));
  for (const plan of plans.slice(0, 2)) {
    check(`  attach ${plan.name}`, await api("POST", `plans/${plan.id}/taxes`, { tax: harbor.id, reason: "Harbor City levy applies here." }));
  }
}

// Image 22: a state tax with its next rate saved for January.
const lone = await ensure("Lone Star Utility Tax", {
  ...filing,
  jurisdiction: { name: "Lone Star State", authority: "Comptroller", level: "state", reference_no: null },
  kind: "percent",
  rate: "0.0625",
  applies_to_services: [],
  applies_to_customer_classes: ["commercial", "industrial"],
  effective_from: "2026-01-01",
  effective_to: null,
});
if (lone.fresh) {
  check("  new rate", await api("POST", `taxes/${lone.id}/new-rate`, { rate: "0.065", effective_from: "2027-01-01" }));
}

// Image 23: a county tax on its third version.
const hill = await ensure("Hill County", {
  ...filing,
  jurisdiction: { name: "Hill County", authority: "Hill County", level: "county", reference_no: null },
  kind: "percent",
  rate: "0.015",
  applies_to_services: [],
  applies_to_customer_classes: [],
  effective_from: "2024-01-01",
  effective_to: null,
});
if (hill.fresh) {
  const v2 = check("  v2", await api("POST", `taxes/${hill.id}/new-rate`, { rate: "0.0175", effective_from: "2025-01-01" }));
  const v2id = v2.data?.id ?? hill.id;
  check("  v3", await api("POST", `taxes/${v2id}/new-rate`, { rate: "0.02", effective_from: "2026-01-01" }));
}

// The page always opens the version current today; a list row is that one.
const current = (await api("GET", "taxes?per=200")).data?.results ?? [];
const idOf = (name) => current.find((row) => row.name === name)?.id;
// A live tax's liability account moves only through Settings › Accounting's
// own door (PO 2026-10-03 on CR-008) — so a kept row without one gets it there.
for (const name of ["Harbor City Levy", "Lone Star Utility Tax", "Hill County"]) {
  const row = current.find((one) => one.name === name);
  if (row !== undefined && row.gl_account_code == null && liability !== undefined) {
    check(`gl ${name}`, await api("PATCH", `taxes/${row.id}/gl-account`, { liability_gl_account_id: liability.id }));
  }
}

// ── the six drawn states ────────────────────────────────────────────────────
const DETAIL = (name) => `${BASE}/${TENANT}/plans-rates/taxes-fees/${idOf(name)}`;
async function photograph(name, url, drawing, after) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  if (after) await after();
  await page.waitForTimeout(600);
  const built = `${OUT}/${name}.png`;
  await page.screenshot({ path: built, fullPage: true });
  say(`\n=== ${name}.png`);
  say((await page.innerText("main")).replace(/\n{2,}/g, "\n").slice(0, 1800));
  const pair = await browser.newPage({ viewport: { width: 2900, height: 900 } });
  const b64 = (file) => readFileSync(file).toString("base64");
  await pair.setContent(
    `<body style="margin:0;display:flex;gap:20px;align-items:flex-start;background:#888">` +
      `<img style="width:1440px" src="data:image/png;base64,${b64(join(DRAWINGS, drawing))}">` +
      `<img style="width:1440px" src="data:image/png;base64,${b64(built)}"></body>`,
  );
  await pair.screenshot({ path: `${OUT}/${name}-side-by-side.png`, fullPage: true });
  await pair.close();
}

await photograph("18-detail-overview-over20", DETAIL("Harbor City Levy"), "18-detail-overview-over20.png");
await photograph("19-detail-plans", `${DETAIL("Harbor City Levy")}?tab=plans`, "19-detail-plans.png");
await photograph("20-detail-audit", `${DETAIL("Harbor City Levy")}?tab=audit`, "20-detail-audit.png");
await photograph("21-detail-more-menu", DETAIL("Harbor City Levy"), "21-detail-more-menu.png", async () => {
  await page.locator("[data-tax-more] summary").click();
});
await photograph("22-detail-overview-scheduled", DETAIL("Lone Star Utility Tax"), "22-detail-overview-scheduled.png");
await photograph("23-detail-overview-versions", DETAIL("Hill County"), "23-detail-overview-versions.png");

// ── the two doors, followed (hard-won law 2: a door is proved by walking it) ─
await page.goto(DETAIL("Harbor City Levy"), { waitUntil: "networkidle" });
await page.getByRole("button", { name: "Edit" }).click();
await page.waitForTimeout(800);
say("\nEdit →", new URL(page.url()).pathname + new URL(page.url()).search);
await page.goto(DETAIL("Harbor City Levy"), { waitUntil: "networkidle" });
await page.getByRole("link", { name: "Fix the rate" }).click();
await page.waitForTimeout(800);
say("Fix the rate →", new URL(page.url()).pathname + new URL(page.url()).search);
await browser.close();
