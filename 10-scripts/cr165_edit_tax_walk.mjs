// ── Trace ──────────────────────────────────────────────
// Change:  CR-165-BRC10 round 3 task 7 — EDIT a tax or fee, photographed in the
//          SAME ten states as images 24–33 of
//          `05-prototype/taxes-fees-2026-10-03/images/`, so each pair can be
//          looked at side by side (B14 rule 42), and the three saves made
//          THROUGH THE SCREEN against the real API on PostgreSQL.
// ───────────────────────────────────────────────────────
//
// Expects the same stack as `cr165_taxes_fees_before_walk.mjs`:
//   * API — `manage.py runserver 127.0.0.1:<port>` on a scratch PostgreSQL 16
//     database with `migrate` + `seed_demo` (Brazos Bend, Dana);
//   * SPA — `vite build --mode wolocal`, then
//     `PORT=<port> API_PROXY_TARGET=http://127.0.0.1:<api> node 07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:8692 OUT=08-qa/taxes-fees-2026-10-03/after \
//     node 10-scripts/cr165_edit_tax_walk.mjs
//
// It stages three copies of the drawings' *ann arbor City* (150 %, 09/01/2026 –
// 11/10/2027) through `POST /taxes`, one per variation, so each save starts
// from the drawn tax: A is renamed-and-refiled in place, B gets a new rate
// from 11/01/2026, C is corrected to 6.25 %. It prints the three tax ids so
// the database can be read afterwards.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8692";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr165-edit-after";
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
const page = await browser.newPage({ viewport: { width: 1440, height: 1600 } });
const say = (...parts) => console.log(...parts);
const settle = () => page.waitForTimeout(900);
async function shot(name, caption) {
  await settle();
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  say(`\n=== ${name}.png — ${caption}`);
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
const press = (name) => page.getByRole("button", { name, exact: true }).click();

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// ── stage the drawn tax three times ─────────────────────────────────────────
const jurisdictions = await api("GET", "tax-jurisdictions?page=1&per=200");
const rows = jurisdictions.data?.results ?? jurisdictions.data?.rows ?? [];
const city = rows.find((row) => /city/i.test(row.name)) ?? rows[0];
const ledger = await api("GET", "ledger/accounts?f.status=active");
const liability = (ledger.data?.rows ?? []).find((row) => String(row.code).startsWith("22")) ?? ledger.data?.rows?.[0];
let account = await api("POST", "settings/authority-accounts", {
  authority_name: "City of Ottumwa Finance",
  account_number: "OTT-0042",
});
if (account.status >= 400) {
  const list = await api("GET", "settings/authority-accounts?page=1&per=200");
  account = { data: (list.data?.results ?? []).find((row) => row.account_number === "OTT-0042") };
}
say("authority:", city?.name, "· liability:", liability?.code, "· account:", account.data?.id);

async function stage(code) {
  const made = await api("POST", "taxes", {
    name: "ann arbor City",
    jurisdiction: city.id,
    kind: "percent",
    rate: "1.5",
    premises_scope_kind: null,
    premises_scope_value: "",
    applies_to_services: [],
    applies_to_customer_classes: [],
    base_includes_usage: true,
    base_includes_base: true,
    effective_from: "2026-09-01",
    effective_to: "2027-11-10",
    discount_treatment: "after",
    rounding_rule: "half_up",
    code,
    liability_gl_account_id: liability.account_id,
    filing_frequency: "monthly",
    due_date_rule: "20th_next_month",
    authority_account_id: account.data?.id,
    collection_allowance_percent: "0.005",
    interest_penalty_percent: "0.015",
    interest_penalty_basis: "monthly",
    filing_reminder_recipient: "filings@ottumwawater.example",
  });
  if (made.status >= 400) throw new Error(`stage ${code}: ${made.status} ${JSON.stringify(made.data)}`);
  return made.data.id;
}
const A = await stage(`AA-CITY-${Date.now() % 100000}`);
const B = await stage(`AA-CITY-B-${Date.now() % 100000}`);
const C = await stage(`AA-CITY-C-${Date.now() % 100000}`);
say("staged ids:", JSON.stringify({ A, B, C }));

const edit = (id, mode) => `${BASE}/${TENANT}/plans-rates/taxes-fees/${id}/edit?change=${mode}`;

// ── A · Name and filing (24–27) ─────────────────────────────────────────────
await page.goto(edit(A, "info"), { waitUntil: "networkidle" });
await page.waitForSelector("#tax-name");
await shot("24-edit-info-1-name", "Name and filing · Name — rate and reach read, locked");
await press("Continue");
await page.waitForSelector("#tax-reminder");
await shot("25-edit-info-2-filing", "Name and filing · Filing — liability locked (Settings › Accounting)");
await page.fill("#tax-reminder", "tax@ottumwawater.example");
await press("Continue");
await page.waitForSelector("[data-tax-versions]");
await shot("26-edit-info-3-review", "Review — before → after, v1 updated in place");
await press("Save changes");
await page.waitForSelector("[data-tax-edit-saved]");
await shot("27-edit-saved", "saved — Back to tax");

// ── B · New rate from a date (28–30) ────────────────────────────────────────
await page.goto(edit(B, "change"), { waitUntil: "networkidle" });
await page.waitForSelector("#tax-rate");
await page.fill("#tax-rate", "6.25");
await page.fill("#tax-from", "2026-11-01");
await shot("28-edit-change-1-rate", "New rate · 6.25 % from 11/01/2026 — Today's rate ends 10/31/2026");
await page.fill("#tax-from", "2026-08-01");
await press("Continue");
await page.waitForSelector("[data-tax-fix-count]");
await shot("29-edit-change-1-error", "New rate · 08/01/2026 — Must be after 09/01/2026");
await page.fill("#tax-from", "2026-11-01");
await press("Continue");
await page.waitForSelector("[data-tax-versions]");
await shot("30-edit-change-2-review", "Review — $90.00 → $3.75, v1 ends 10/31/2026, v2 new");
await press("Save new rate");
await page.waitForSelector("[data-tax-edit-saved]");
await shot("30b-edit-change-saved", "saved — v2 starts 11/01/2026");

// ── C · Fix a mistake (31–33) ───────────────────────────────────────────────
await page.goto(edit(C, "correct"), { waitUntil: "networkidle" });
await page.waitForSelector("#tax-rate");
await page.fill("#tax-rate", "6.25");
await page.fill("#tax-reason", "Rate typed as 150%.");
await shot("31-edit-correct-1-fix", "Fix the rate · dates read, reason given");
await page.fill("#tax-reason", "");
await press("Continue");
await page.waitForSelector("[data-tax-fix-count]");
await shot("32-edit-correct-1-error", "Fix the rate · no reason — Enter the reason.");
await page.fill("#tax-reason", "Rate typed as 150%.");
await press("Continue");
await page.waitForSelector("[data-tax-versions]");
await shot("33-edit-correct-2-review", "Review — superseded and kept, issued bills keep 150%");
await press("Save correction");
await page.waitForSelector("[data-tax-edit-saved]");
await shot("33b-edit-correct-saved", "saved — v2 replaces v1");

// ── what the server now holds ───────────────────────────────────────────────
for (const [label, id] of [["A", A], ["B", B], ["C", C]]) {
  const versions = await api("GET", `taxes/${id}/versions`);
  say(`\n${label} versions:`, JSON.stringify(versions.data));
}
const after = await api("GET", `taxes/${A}`);
say("\nA after PATCH:", JSON.stringify({ id: after.data?.id, reminder: after.data?.filing_reminder_recipient, version: after.data?.version }));
await browser.close();
