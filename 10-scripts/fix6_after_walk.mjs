// CR-168-BRC10 lane FIX-6 — the AFTER walk at 1440 wide, on PostgreSQL 16.
// One check per defect this lane fixed, each photographed:
//   DEF-WRK-9657 order numbers on Performance › Schedule stay on one line
//   DEF-WRK-9658 the Raise-across-buildings result links each job number
//   DEF-SHL-9615 a server refusal under Part number leaves when it is retyped
//   DEF-MET-9649 a one-unit build reads "1 unit"
//   DEF-CUS-9650 a move record's reads print through the quantity formatter
//   DEF-PAY-9644 Payments › Summary prints percentages at two places
//   DEF-WRK-9664 a certificate row's action reads "Edit" (image 33)
//   DEF-WRK-9660 a rule-raised job on an installed backflow names its premises
//   DEF-WRK-9661 the rule's Overview / Review promise what the sweep raises
// (DEF-MET-9614 is proved on PostgreSQL by its test, not walked: it has no screen
//  of its own beyond the import page's refusal line.)
//
//   BASE=http://127.0.0.1:5213 OUT=08-qa/work-2026-10-04/after \
//   SWEEP=<script sweeping one rule id given as $1> \
//   node 10-scripts/fix6_after_walk.mjs
//
// Preconditions: migrate + seed_demo + load_sample_data --tenant brazosbend on
// PostgreSQL, the API with this branch, the SPA served by 07-frontend/server.mjs.
// WRITES IT MAKES: jobs raised across buildings and two rules and
// their sweeps.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5213";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/after";
const SWEEP = process.env.SWEEP ?? "";
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
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const failed = [];
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`);
});
const settle = (ms = 1200) => page.waitForTimeout(ms);
const checks = [];
function check(name, ok, detail = "") {
  checks.push([name, ok]);
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}
async function shot(name, caption) {
  await settle();
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log(`=== ${name}.png — ${caption}`);
  if (failed.length) console.log("API 4xx/5xx:", JSON.stringify(failed.splice(0)));
}
async function go(path) {
  await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle", timeout: 30000 }).catch(() => console.log("goto timeout", path));
  await settle(1500);
}
async function api(path, method = "GET", body = undefined) {
  return page.evaluate(
    async ([tenant, p, m, b]) => {
      const res = await fetch(`/api/${tenant}/${p}`, {
        method: m,
        credentials: "include",
        headers: b === undefined ? {} : { "Content-Type": "application/json" },
        body: b === undefined ? undefined : JSON.stringify(b),
      });
      return { status: res.status, body: await res.json().catch(() => null) };
    },
    [TENANT, path, method, body],
  );
}
const main = () => page.locator("main").innerText();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.keyboard.press("Enter");
await page.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 30000 });
await settle(2000);

// ── DEF-WRK-9657 · Schedule ────────────────────────────────────────────────
await go("/work/performance?view=schedule");
const heights = await page.$$eval("[data-drag-order]", (els) => els.map((el) => [el.textContent, el.getBoundingClientRect().height]));
check("9657 · every order number on one line", heights.length > 0 && heights.every(([, h]) => h < 30), JSON.stringify(heights.slice(0, 3)));
await shot("fix6-9657-schedule", "Performance › Schedule — order numbers on one line");

// ── DEF-WRK-9658 · Raise across buildings ──────────────────────────────────
await go("/work/performance?view=across");
const select = page.locator("[data-across-template]");
const options = await select.locator("option").evaluateAll((os) => os.map((o) => [o.value, o.textContent]));
// The first template whose list offers assets to choose.
// One asset per tick — never the header's choose-all box.
const ticks = page.locator('tbody input[type="checkbox"][aria-label^="Choose"]');
let tickCount = 0;
for (const [value, label] of options.filter(([v]) => v)) {
  await select.selectOption(value);
  await settle(2000);
  tickCount = await ticks.count();
  if (tickCount === 0 && (await page.locator("[data-across-test-due]").isChecked())) {
    // Nothing due for test under this template: show every assigned asset.
    await page.locator("[data-across-test-due]").uncheck();
    await settle(1500);
    tickCount = await ticks.count();
  }
  if (tickCount > 0) {
    console.log("across template:", label, tickCount);
    break;
  }
}
for (let i = 0; i < Math.min(2, tickCount); i += 1) await ticks.nth(i).check();
await page.locator("[data-across-raise]").click();
await settle(2500);
const resultLinks = await page.$$eval("[data-raise-result-order]", (els) => els.map((el) => [el.textContent, el.getAttribute("href")]));
check(
  "9658 · each job number in the result is a link to its order",
  resultLinks.length > 0 && resultLinks.every(([no, href]) => href === `/${TENANT}/work/orders/${no}`),
  JSON.stringify(resultLinks),
);
await shot("fix6-9658-raise-across-result", "Raise across buildings — the job numbers link to their orders");
if (resultLinks.length > 0) {
  await page.locator("[data-raise-result-order]").first().click();
  await settle(2000);
  check("9658 · the link opens the order", page.url().endsWith(`/work/orders/${resultLinks[0][0]}`) && (await main()).includes(resultLinks[0][0]));
}

// ── DEF-SHL-9615 · Add a part, refused, retyped ────────────────────────────
const parts = await api("work/parts?page=1&per=5");
const existing = parts.body?.results?.[0]?.part_no;
await go("/work/parts");
await page.getByRole("button", { name: /Add a part|Add part/ }).first().click();
await settle(800);
const dialog = page.getByRole("dialog");
await dialog.locator("#part_no").fill(existing ?? "MTR-W34");
await dialog.locator("#name").fill("Walk duplicate");
const uom = dialog.locator("#unit_of_measure");
if ((await uom.evaluate((el) => el.tagName)) === "SELECT") {
  await uom.selectOption({ index: 1 });
} else {
  await uom.fill("each");
}
await dialog.locator("#unit_cost").fill("1.00");
await dialog.getByRole("button", { name: /Add|Save/ }).last().click();
await settle(1500);
const refusal = `${existing} is already in the register.`;
check("9615 · the refusal shows under Part number", (await dialog.innerText()).includes(refusal), existing);
await shot("fix6-9615-part-refused", "Add a part — the server's refusal under Part number");
await dialog.locator("#part_no").fill("FIX6-NEW-1");
await settle(600);
check("9615 · retyping the number takes the refusal away", !(await dialog.innerText()).includes(refusal));
await shot("fix6-9615-part-retyped", "Add a part — retyped, the refusal is gone");
await page.keyboard.press("Escape");

// ── DEF-MET-9649 · a one-unit build ────────────────────────────────────────
const builds = await api("connections?page=1&per=100");
const one = (builds.body?.results ?? []).find((b) => b.connection_no === "CON-26-0126") ?? (builds.body?.results ?? [])[0];
await go(`/connections/${one?.id}`);
const head = await page.locator("[data-screen='NCT-02']").innerText().catch(() => "");
check("9649 · the header reads 1 unit, never 1 units", /\b1 unit\b/.test(head) && !head.includes("1 units"), one?.connection_no);
await shot("fix6-9649-build-one-unit", "New connect build — 1 unit");

// ── DEF-CUS-9650 · a move record's reads ───────────────────────────────────
await go("/moves/MVI-26-0002");
const moveText = await main();
// The sample move-in has no meter on its unit, so it draws no reading: the
// six-places fix is proved by MoveRecordPage.test.tsx, and this check only
// says so rather than passing over nothing (law 7).
if (/No meter on this unit/.test(moveText)) {
  console.log("NOTE 9650 · the sample move has no reads to print; proved by its unit test");
} else {
  check("9650 · no reading printed to six places", !/\d\.\d{6}\b/.test(moveText));
}
await shot("fix6-9650-move-record", "Move-in record — opening reads");

// ── DEF-PAY-9644 · Payments › Summary ──────────────────────────────────────
await go("/payments?tab=summary");
const payText = await main();
check("9644 · no percentage printed to six places", !/\d\.\d{3,}%/.test(payText), (payText.match(/[\d.]+%/g) ?? []).join(" "));
await shot("fix6-9644-payments-summary", "Payments › Summary — percentages at two places");

// ── DEF-WRK-9664 · Certifications row action ───────────────────────────────
const techs = await api("work/crews?view=technicians&page=1&per=50");
const tech = (techs.body?.results ?? []).find((r) => (r.certifications ?? []).length > 0) ?? (techs.body?.results ?? [])[0];
await go(`/work/crews/${tech?.slug ?? tech?.id}?tab=certifications`);
const certText = await main();
check("9664 · the row action reads Edit, never Renew", (await page.getByRole("button", { name: "Edit" }).count()) > 0 && !(await page.getByRole("button", { name: "Renew" }).count()), tech?.name);
await shot("fix6-9664-certifications-edit", "Technician › Certifications — ✎ Edit, as image 33");
void certText;

// ── DEF-WRK-9660 / 9661 · rules ────────────────────────────────────────────
// The backflow type's id, read from the database by the caller (BACKFLOW_TYPE).
const backflow = process.env.BACKFLOW_TYPE ? { id: process.env.BACKFLOW_TYPE } : null;
const templates = await api("work/templates?page=1&per=100");
const tplRows = templates.body?.results ?? [];
const siteTpl = tplRows.find((r) => /Site inspection/.test(r.name));
const meterTpl = tplRows.find((r) => /Meter exchange/.test(r.name));
const both = [
  { kind: "asset_age_rule", params: {} },
  { kind: "compliance_calendar", params: { days_ahead: 3650 } },
];
const narrow = backflow
  ? [{ kind: "asset_age_rule", params: { asset_type_ids: [backflow.id] } }]
  : [{ kind: "asset_age_rule", params: {} }];

// The first template that would raise on the backflows tonight (one already
// open on them from an earlier walk answers *already open*, not a job).
let backflowTpl = siteTpl;
for (const row of tplRows) {
  const p = await api("work/rules/preview", "POST", { template_id: row.id, triggers: narrow });
  if ((p.body?.would_raise ?? 0) > 0) {
    backflowTpl = row;
    break;
  }
}
console.log("backflow template:", backflowTpl?.name);
const a = await api("work/rules", "POST", { name: `Backflow test due — FIX-6 ${Date.now() % 100000}`, template_id: backflowTpl?.id, triggers: narrow });
const b = await api("work/rules", "POST", { name: `Meter exchange on everything — FIX-6 ${Date.now() % 100000}`, template_id: meterTpl?.id, triggers: both });
console.log("rules created", a.status, b.status);

await go(`/work/rules/${b.body?.id}`);
const overview = await main();
const promised = b.body?.tonight?.would_raise ?? null;
check("9661 · the Overview says how many cannot be raised", (await page.locator("[data-rule-cannot-raise]").count()) === 1);
await shot("fix6-9661-rule-overview", "A rule's Overview — tonight it raises N, M more cannot be raised");
await go(`/work/rules/${b.body?.id}/edit?step=3`);
await settle(1500);
const review = await page.locator("[data-rule-tonight]").getAttribute("data-rule-tonight").catch(() => null);
const cannot = await page.locator("[data-rule-cannot-raise]").getAttribute("data-rule-cannot-raise").catch(() => null);
await shot("fix6-9661-rule-review", "The builder's Review — the same two numbers");
void overview;

if (SWEEP) {
  const sweptB = JSON.parse(execFileSync(SWEEP, [b.body.id], { encoding: "utf-8" }).trim());
  console.log("sweep B", JSON.stringify(sweptB));
  check("9661 · the Review's number is the number the sweep raised", String(sweptB.raised) === String(review), `review ${review} · raised ${sweptB.raised}`);
  check("9661 · the refused are counted, not swallowed", String(sweptB.refused) === String(cannot), `cannot ${cannot} · refused ${sweptB.refused}`);
  const sweptA = JSON.parse(execFileSync(SWEEP, [a.body.id], { encoding: "utf-8" }).trim());
  console.log("sweep A", JSON.stringify(sweptA));
  const jobs = await api(`work/rules/${a.body.id}/jobs?page=1&per=50`);
  console.log("jobs A", JSON.stringify(jobs.body?.results?.map((r) => [r.order_no, r.premise])));
  await go(`/work/rules/${a.body.id}?tab=jobs`);
  const jobsText = await main();
  check("9660 · the backflow job names its premises", sweptA.raised > 0 && (jobs.body?.results ?? []).every((r) => r.premise));
  await shot("fix6-9660-rule-jobs", "The rule's Jobs — the backflow job names its premises");
  void jobsText;
}
void promised;

const passed = checks.filter(([, ok]) => ok).length;
console.log(`\n${passed}/${checks.length} checks passed`);
await browser.close();
process.exit(passed === checks.length ? 0 : 1);
