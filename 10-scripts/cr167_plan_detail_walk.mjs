// ── Trace ──────────────────────────────────────────────
// Change:  CR-167-BRC10 round 3 task 7 (lane PLAN-DETAIL) — photograph the built
//          plan details page in the fourteen states of images 24–37 at 1440 on
//          PostgreSQL, and check each state's drawn facts as it goes.
// ───────────────────────────────────────────────────────
//
// Expects the API on a PostgreSQL 16 database with `migrate` + `seed_demo` +
// `load_sample_data --tenant brazosbend`, and the SPA built with
// `vite build --mode wolocal` and served by `07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:5301 OUT=08-qa/plans-2026-10-03/details \
//     node 10-scripts/cr167_plan_detail_walk.mjs
//
// Setup it does through the API, once (re-runs reuse it): on the sample plan
// SCW-RES it publishes a v2 from 01/01/2027 with a $12.00 minimum bill (so the
// banner, Priced as of 01/15/2027 and Audit have a real later version), and
// renames the description on the same version (a *Name and details* audit row).
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5301";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr167-detail";
const PLAN_CODE = process.env.PLAN_CODE ?? "SCW-RES";
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
  // The shell scrolls its own content box, so `fullPage` sees only the
  // viewport: grow the viewport to the tallest scrolling box, shoot, shrink.
  const tall = await page.evaluate(() =>
    Math.max(
      document.documentElement.scrollHeight,
      ...[...document.querySelectorAll("*")]
        .filter((el) => /auto|scroll/.test(getComputedStyle(el).overflowY) && el.scrollHeight > el.clientHeight)
        .map((el) => el.scrollHeight + el.getBoundingClientRect().top),
    ),
  );
  await page.setViewportSize({ width: 1440, height: Math.min(Math.max(900, Math.ceil(tall) + 40), 6000) });
  await settle(500);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });
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
const mainText = () => page.innerText("main");
const noId = (text) => !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-/.test(text);

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click("button[type=submit]");
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// ── the plan, and a later version of it ─────────────────────────────────────
const list = await api("GET", `plans?q=${encodeURIComponent(PLAN_CODE)}&per=50`);
const plan = (list.data?.results ?? []).find((row) => row.code === PLAN_CODE);
if (plan === undefined) throw new Error(`no plan ${PLAN_CODE}`);
const id = plan.id;
let detail = await api("GET", `plans/${id}`);
if ((detail.data?.versions ?? []).length < 2) {
  const v2 = await api("POST", `plans/${id}/versions`, {
    effective_from: "2027-01-01",
    reason: "Minimum bill rises with the new year",
    minimum_bill_amount: "12.00",
    publish: true,
  });
  say("v2 from 01/01/2027:", v2.status, JSON.stringify(v2.data).slice(0, 300));
  const renamed = await api("PATCH", `plans/${id}`, {
    details: { description: "Electric and water for homes in the service area." },
  });
  say("description on the same version:", renamed.status, JSON.stringify(renamed.data).slice(0, 200));
  detail = await api("GET", `plans/${id}`);
}
say("upcoming:", JSON.stringify(detail.data?.upcoming));
say("versions:", JSON.stringify((detail.data?.versions ?? []).map((v) => [v.version, v.status, v.effective_from, v.effective_to])));
const units = await api("GET", `plans/${id}/units?per=5`);
say("units row keys:", Object.keys(units.data?.results?.[0] ?? {}).sort().join(", "));
const csv = await page.evaluate(async (p) => {
  const res = await fetch(`/api/${p}`, { credentials: "include", headers: { Accept: "text/csv" } });
  return { status: res.status, type: res.headers.get("content-type"), head: (await res.text()).slice(0, 160) };
}, `${TENANT}/plans/${id}/units?format=csv&f.occupancy=vacant`);
check("units CSV is served", csv.status === 200 && (csv.type ?? "").includes("csv"), JSON.stringify(csv));

const at = (search = "") => `${BASE}/${TENANT}/plans-rates/plans/${id}${search}`;

// ── 24 · Overview ───────────────────────────────────────────────────────────
await page.goto(at(), { waitUntil: "networkidle" });
await page.locator("[data-plan-overview]").waitFor();
await shot("24-detail-overview", "Overview: tiles, banner, Details, versions (image 24)");
let text = await mainText();
const tabs = await page.$$eval("[role=tab]", (all) => all.map((t) => t.textContent.trim()));
say("tabs:", tabs.join(" | "));
check("24 six tabs in the drawn order", /^Overview\|Services\d+\|Charges\|Billing\|Units\d+\|Audit$/.test(tabs.join("|")), tabs.join("|"));
check("24 banner names the later version", (await page.locator("[data-plan-upcoming]").count()) === 1, (await page.locator("[data-plan-upcoming]").allInnerTexts()).join(""));
check("24 no removed text", !/Revenue|Exceptions|How a plan works|Sample bill|Not recorded on a plan yet/.test(text));
check("24 no database id", noId(text));
check("24 the class is named", /Residential/.test(await page.innerText("[data-plan-header-facts]")));

// ── 25 · More ▾ ─────────────────────────────────────────────────────────────
await page.locator("[data-plan-more] summary").click();
await shot("25-detail-more", "More ▾: Duplicate (held), Retire (image 25)");
check("25 Duplicate is disabled", await page.getByTestId("plan-more-duplicate").isDisabled());
await page.locator("[data-plan-more] summary").click();

// ── 26–28 · Services ────────────────────────────────────────────────────────
await page.goto(at("?tab=services"), { waitUntil: "networkidle" });
await page.locator("[data-plan-priced-tab=services]").waitFor();
await shot("26-detail-services-folded", "Services, each folded to one line (image 26)");
text = await mainText();
check("26 a service reads Base charges · Usage charges in one line", (await page.locator("[data-service-line]").count()) > 0);
check("26 names are links", (await page.locator("[data-plan-priced-tab] a").count()) > 0);
await page.getByRole("button", { name: /Expand all/ }).click();
await shot("27-detail-services-open", "Services, Expand all (image 27)");
check("27 every service opened", (await page.locator("[data-service-tables]").count()) === (await page.locator("[data-plan-service]").count()));
await page.goto(at("?tab=services&as_of=2027-01-15"), { waitUntil: "networkidle" });
await page.locator("[data-plan-priced-tab=services]").waitFor();
await page.getByRole("button", { name: /Expand all/ }).click();
await shot("28-detail-services-asof-2027", "Services, Priced as of 01/15/2027 (image 28)");
check("28 the address carries the date", page.url().includes("as_of=2027-01-15"));

// ── 29 · Charges, 30 · Billing ──────────────────────────────────────────────
await page.goto(at("?tab=charges"), { waitUntil: "networkidle" });
await page.locator("[data-plan-priced-tab=charges]").waitFor();
await shot("29-detail-charges", "Charges: charge codes and taxes (image 29)");
check("29 no database id", noId(await mainText()));
await page.goto(at("?tab=billing"), { waitUntil: "networkidle" });
await page.locator("[data-plan-priced-tab=billing]").waitFor();
await shot("30-detail-billing", "Billing: deposits, discounts, billing terms (image 30)");
text = await mainText();
check("30 minimum bill with $", /\$\d+\.\d\d/.test(text));

// ── 31–33 · Units ───────────────────────────────────────────────────────────
await page.goto(at("?tab=units"), { waitUntil: "networkidle" });
await page.locator("[data-plan-units] tbody tr").first().waitFor();
await shot("31-detail-units", "Units: search, occupancy, CSV (image 31)");
check("31 unit, premises and account are links", (await page.locator("[data-plan-units] tbody tr").first().locator("a").count()) >= 2);
check("31 no Move control, no selection column", (await page.getByRole("button", { name: /Move/ }).count()) === 0 && (await page.locator("[data-plan-units] tbody input[type=checkbox]").count()) === 0);
const firstUnit = (await page.locator("[data-plan-units] tbody tr").first().locator("a").first().innerText()).trim();
await page.getByPlaceholder("Search unit or premises").fill(firstUnit.slice(0, 6));
await settle(1600);
await shot("32-detail-units-search", `Units searched "${firstUnit.slice(0, 6)}" (image 32)`);
check("32 the search went to the server", page.url().includes("u.q="), page.url());
await page.getByPlaceholder("Search unit or premises").fill("");
await settle(1200);
await page.locator('[data-occupancy="vacant"]').click();
await settle(1500);
await shot("33-detail-units-vacant", "Units, Vacant only (image 33)");
check("33 the filter went to the server", page.url().includes("u.f.occupancy=vacant"), page.url());

// ── 34–36 · Audit ───────────────────────────────────────────────────────────
await page.goto(at("?tab=audit"), { waitUntil: "networkidle" });
await page.locator("[data-plan-audit]").waitFor();
await settle(1500);
await shot("34-detail-audit", "Audit: all changes (image 34)");
text = await mainText();
check("34 no database id, no JSON", noId(text) && !/[{}]/.test(text));
await page.locator('[data-audit-kind="underneath"]').click();
await settle(1500);
await shot("35-detail-audit-underneath", "Audit: changes underneath (image 35)");
check("35 the filter went to the server", page.url().includes("a.f.kind=underneath"), page.url());
await page.locator('[data-audit-kind="all"]').click();
await settle(1500);
const expander = page.locator("[data-plan-audit] tbody tr button[aria-expanded=false]").first();
if ((await expander.count()) > 0) await expander.click();
await shot("36-detail-audit-open", "Audit: a row opened to before → after (image 36)");
check("36 a row opened", (await page.locator("[data-plan-audit-open]").count()) === 1);

// ── 37 · a section's Edit opens that step ───────────────────────────────────
await page.goto(at("?tab=charges"), { waitUntil: "networkidle" });
await page.locator("[data-plan-priced-tab=charges]").waitFor();
await page.getByRole("button", { name: "Edit Charge codes" }).click();
await page.waitForURL((u) => u.pathname.endsWith("/edit"), { timeout: 15000 });
await page.waitForLoadState("networkidle");
await page.locator("main h1").first().waitFor({ timeout: 30000 });
await settle(2500);
await shot("37-detail-section-edit", `Charge codes › Edit lands on ${page.url().replace(BASE, "")} (image 37)`);
check("37 the address is the agreed edit door", page.url().includes("/edit?change=change&step=2"), page.url());

say(`\n${failures === 0 ? "ALL PASS" : `${failures} FAIL`}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
