// ── Trace ──────────────────────────────────────────────
// Change:  CR-166-BRC10 follow-up (lane DISC-GARDEN) — PO ruling 2026-10-03,
//          option (b): Usage allowance is not offered on the New discount form
//          until free units before pricing is built. Photographs the New form's
//          type choices at 1440 on PostgreSQL, the server's refusal of a new
//          usage allowance, and a usage-allowance draft saved before the ruling
//          (its details page and its Edit form).
// ───────────────────────────────────────────────────────
//
// Expects the API on a PostgreSQL 16 database with `migrate` + `seed_demo` +
// `load_sample_data --tenant brazosbend`, the SPA built with `vite build` and
// served by `07-frontend/server.mjs`, and `psql` on PATH reaching the same
// database (DB_URL) — the pre-ruling row is made the only way one can be now:
// saved as a fixed amount and its version's type set the way the old create
// stored it.
//
//   BASE=http://127.0.0.1:5321 OUT=08-qa/discounts-2026-10-03/garden \
//   DB_URL=postgres://postgres@127.0.0.1:55433/sbh_discgarden \
//     node 10-scripts/cr166_garden_type_walk.mjs
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5321";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/garden";
const DB_URL = process.env.DB_URL ?? "postgres://postgres@127.0.0.1:55433/sbh_discgarden";
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
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const say = (...parts) => console.log(...parts);
const settle = (ms = 1000) => page.waitForTimeout(ms);
let failures = 0;
function check(name, ok, detail) {
  if (!ok) failures += 1;
  say(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
}
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

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click("button[type=submit]");
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// ── 1 · the New form's Type list ────────────────────────────────────────────
const served = await api("GET", "discounts/form-options");
const servedTypes = (served.data?.types ?? []).map((o) => o.value);
check("the server still serves usage_allowance (a saved one must read its type)", servedTypes.includes("usage_allowance"), servedTypes.join(", "));

await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
const type = page.locator("select#discount-type");
await type.waitFor();
const offered = await type.locator("option").evaluateAll((els) => els.map((el) => [el.value, el.textContent]));
say("offered:", JSON.stringify(offered));
check("the New form offers no Usage allowance", !offered.some(([value]) => value === "usage_allowance"));
await shot("01-new-form-type-list", `New discount · Type offers: ${offered.map(([, label]) => label).join(" | ")}`);
let n = 2;
for (const [value, label] of offered) {
  await type.selectOption(value);
  await shot(`0${n}-new-form-type-${value}`, `New discount · Type chosen: ${label}`);
  n += 1;
}

// ── 2 · the server refuses a new one by name ────────────────────────────────
const refused = await api("POST", "discounts", {
  code: "GARDEN2",
  name: "Garden allowance",
  discount_type: "usage_allowance",
  value: "2",
  applies_to: "one_service",
  applies_to_service: "water",
});
const typeError = (refused.data?.field_errors ?? []).find((e) => e.field === "discount_type");
check(
  "POST /discounts with usage_allowance is refused on the type box by name",
  refused.status === 422 && typeError?.message_key === "rating.discounts.usage_allowance_not_offered",
  `${refused.status} ${JSON.stringify(typeError)}`,
);

// ── 3 · a usage-allowance draft saved before the ruling ─────────────────────
let list = await api("GET", "discounts?q=GARDEN&per=50");
let garden = (list.data?.results ?? []).find((row) => row.code === "GARDEN");
if (garden === undefined) {
  const made = await api("POST", "discounts", {
    code: "GARDEN",
    name: "Garden allowance",
    program_owner: "billing",
    discount_type: "fixed_amount",
    value: "2",
    applies_to: "one_service",
    applies_to_service: "water",
    eligibility: "everyone",
    effective_from: "2026-10-01",
  });
  say("made as fixed amount:", made.status, JSON.stringify(made.data).slice(0, 200));
  execFileSync("psql", [
    DB_URL,
    "-Atc",
    `update discount_versions set discount_type='usage_allowance' where discount_id='${made.data.id}'`,
  ]);
  list = await api("GET", "discounts?q=GARDEN&per=50");
  garden = (list.data?.results ?? []).find((row) => row.code === "GARDEN");
}
check("the saved usage allowance is on the list", garden?.type === "usage_allowance", JSON.stringify(garden ?? null).slice(0, 200));

await page.goto(`${BASE}/${TENANT}/plans-rates/discounts`, { waitUntil: "networkidle" });
await page.getByText("Garden allowance").first().waitFor();
await shot("10-list-garden-still-listed", "Discounts list · the saved Garden allowance (draft) still reads");

await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${garden.id}`, { waitUntil: "networkidle" });
await page.getByRole("heading", { level: 1 }).waitFor();
const submitShown = await page.getByRole("button", { name: /Submit for approval/ }).count();
check("its details page offers Edit and no Submit for approval", submitShown === 0);
await shot("11-details-garden-edit-only", "Garden allowance details · Draft · Edit only");

const submitted = await api("POST", `discounts/${garden.id}/submit`, {});
check(
  "POST …/submit is refused (it could never be approved)",
  submitted.status >= 400 && submitted.data?.message_key === "rating.discounts.type_not_priceable",
  `${submitted.status} ${submitted.data?.message_key}`,
);

await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${garden.id}/edit?change=info`, { waitUntil: "networkidle" });
await page.locator("#discount-type").waitFor();
const tag = await page.locator("#discount-type").evaluate((el) => el.tagName);
const typeText = await page.locator("#discount-type").innerText();
check("Edit opens with the type read-only", tag !== "SELECT" && /Usage allowance/.test(typeText), `${tag} ${typeText}`);
await shot("12-edit-garden-type-read-only", "Edit Garden allowance · Type reads Usage allowance, not a list");

await browser.close();
say(`\n${failures === 0 ? "ALL PASS" : `${failures} FAIL`}`);
process.exit(failures === 0 ? 0 : 1);
