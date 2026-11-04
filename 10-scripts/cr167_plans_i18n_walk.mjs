// ── Trace ──────────────────────────────────────────────
// Change:  CR-167-BRC10 round 4 task 9 (lane PLAN-LANG) — the plan screens
//          photographed in all eleven languages at 1440 wide (DEF-RAT-9368).
// ───────────────────────────────────────────────────────
//
// Expects the API on a scratch PostgreSQL 16 database prepared with `migrate`
// + `seed_demo` + `load_sample_data --tenant brazosbend`, and the SPA from
// `vite build --mode wolocal` served by `07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:5361 OUT=08-qa/plans-2026-10-03/i18n \
//     node 10-scripts/cr167_plans_i18n_walk.mjs
//
// Setup through the API, once (re-runs reuse it): the sample plan SCW-RES
// gets a published v2 from 01/01/2027 with a $12.00 minimum bill, so the
// details page has its banner, two versions and real Audit rows — the same
// preparation as `cr167_plan_detail_walk.mjs`.
//
// Each screen is driven in English (so the walk finds its boxes by their
// English labels), then switched to the language and photographed:
//   list · New plan steps 1–5 and the saved panel · details Overview, More ▾,
//   Services (expanded), Charges, Billing, Units, Audit, the Retire dialog ·
//   Edit's three choices and Change from a date › Review.
// For every photograph it prints three numbers a person can judge: the
// characters on screen (a blank screen fails), the page's sideways overflow,
// and every English probe word found in the screen's own text. It also counts
// text boxes narrower than two characters that wrap — the "one character per
// line" failure — and prints them. A plan's name, a service's name and a
// schedule's name are the utility's data and stay English; they are not
// probes.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5361";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr167-i18n";
const PLAN_CODE = process.env.PLAN_CODE ?? "SCW-RES";
const EDIT_CODE = process.env.EDIT_CODE ?? "";
const LANGS = (process.env.LANGS ?? "en,de,es,es-MX,fr-FR,hi,id-ID,it-IT,ja-JP,ko-KR,pt-BR").split(",");
const ONLY = (process.env.ONLY ?? "").split(",").filter(Boolean);
const RUN = String(Date.now() % 100000);
mkdirSync(OUT, { recursive: true });

// English words that are catalogue text on the plan screens. A hit in a
// non-English photograph is printed, never silently passed.
const PROBES = [
  "Overview", "Services", "Charges", "Billing", "Units", "Audit", "Version", "No end", "Retire", "Duplicate",
  "Delete draft", "Edit", "More", "Details", "Review", "Continue", "Cancel", "Back", "Search", "Status",
  "Plan name", "Customer classes", "Description", "Intended for", "Rate schedule", "Base charges", "Minimum",
  "Charge code", "Taxes", "Deposits", "Discounts", "Billing terms", "Budget billing", "Minimum bill",
  "Publish plan", "Save as draft", "Starts", "Ends", "Plans", "New plan", "What changes", "How it is saved",
  "Change from a date", "Fix a mistake", "Name and details", "Before", "After", "Occupied", "Vacant",
  "Priced as of", "Collapse all", "Expand all", "Usage charges", "Effective from", "Schedules", "Open",
  "Draft", "Published", "Active", "Scheduled", "Ended", "Add service", "Add tax", "Add deposit",
  "Add discount", "Add charge code", "Choose", "Remove", "saved", "published", "See it", "starts",
];

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
const settle = (ms = 700) => page.waitForTimeout(ms);
const setLang = async (code) => {
  await page.evaluate((c) => window.__SMARTBILLHUB_I18N__?.changeLanguage(c), code);
  await settle(800);
};
const click = (name) => page.getByRole("button", { name, exact: true }).click();
async function pickLast(label, value) {
  const boxes = page.getByRole("combobox", { name: label, exact: true });
  await boxes.nth((await boxes.count()) - 1).selectOption(value);
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

const findings = [];
async function shot(name, lang) {
  await setLang(lang);
  // Grow the viewport to the page's own height, so a tall tab is one picture.
  const tall = await page.evaluate(() =>
    Math.max(
      document.documentElement.scrollHeight,
      ...[...document.querySelectorAll("*")]
        .filter((el) => /auto|scroll/.test(getComputedStyle(el).overflowY) && el.scrollHeight > el.clientHeight)
        .map((el) => el.scrollHeight + el.getBoundingClientRect().top),
    ),
  );
  await page.setViewportSize({ width: 1440, height: Math.min(Math.max(900, Math.ceil(tall) + 40), 6000) });
  await settle(400);
  const file = `${OUT}/${name}-${lang}.png`;
  await page.screenshot({ path: file, fullPage: true });
  const text = (await page.locator("main").innerText()).trim();
  if (text.length < 80) throw new Error(`${name}-${lang}: the screen is blank (${text.length} characters)`);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  // A box that wraps its text one character per line: rendered narrower than
  // two of its own characters and taller than two lines.
  const slivers = await page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll("main th, main td, main button, main label, main span, main a, main dt, main dd")) {
      const own = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join("");
      if (own.length < 2) continue;
      const r = el.getBoundingClientRect();
      const lh = parseFloat(getComputedStyle(el).lineHeight) || 16;
      const fs = parseFloat(getComputedStyle(el).fontSize) || 14;
      if (r.width > 0 && r.width < fs * 2.2 && r.height > lh * 2.5) out.push(own.slice(0, 20));
    }
    return out;
  });
  // The list's table must sit in its own box: wider content scrolls inside it,
  // never the page. Reported, not judged, so a person reads the number.
  const box = await page.evaluate(() => {
    const t = document.querySelector("main table");
    if (!t) return null;
    let el = t.parentElement;
    while (el && el !== document.body && !/auto|scroll/.test(getComputedStyle(el).overflowX)) el = el.parentElement;
    const host = el && el !== document.body ? el : t.parentElement;
    return { box: Math.round(host.getBoundingClientRect().width), table: Math.round(t.getBoundingClientRect().width) };
  });
  const hits = lang === "en" ? [] : PROBES.filter((word) => new RegExp(`(^|[^A-Za-z])${word}([^A-Za-z]|$)`).test(text));
  const line = `${name}-${lang}: ${text.length} chars, sideways ${overflow}px, table ${box ? `${box.table}px in ${box.box}px box` : "—"}, one-char wraps ${slivers.length ? slivers.join(" | ") : "none"}, English probes: ${hits.join(", ") || "none"}`;
  say(line);
  if (overflow > 0 || slivers.length || hits.length) findings.push(line);
  await page.setViewportSize({ width: 1440, height: 900 });
}
const want = (name) => ONLY.length === 0 || ONLY.some((o) => name.startsWith(o));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click("button[type=submit]");
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── setup, once ───────────────────────────────────────────────────────────
const list = await api("GET", `plans?q=${encodeURIComponent(PLAN_CODE)}&per=50`);
const plan = (list.data?.results ?? []).find((row) => row.code === PLAN_CODE);
if (plan === undefined) throw new Error(`no plan ${PLAN_CODE} — run load_sample_data first`);
const id = plan.id;
const detail = await api("GET", `plans/${id}`);
if ((detail.data?.versions ?? []).length < 2) {
  const v2 = await api("POST", `plans/${id}/versions`, {
    effective_from: "2027-01-01",
    reason: "Minimum bill rises with the new year",
    minimum_bill_amount: "12.00",
    publish: true,
  });
  say("v2 from 01/01/2027:", v2.status);
}
// Edit's Change from a date needs a plan with no later version waiting.
let editId = id;
{
  const all = await api("GET", "plans?per=100");
  const rows = all.data?.results ?? [];
  const pick = EDIT_CODE ? rows.find((r) => r.code === EDIT_CODE) : rows.find((r) => r.code !== PLAN_CODE && r.status === "published");
  if (pick) editId = pick.id;
  say("edit plan:", pick?.code ?? PLAN_CODE);
}
const at = (planId, search = "") => `${BASE}/${TENANT}/plans-rates/plans/${planId}${search}`;
const go = async (url) => {
  await page.goto(url, { waitUntil: "networkidle" });
  await setLang("en");
};
let served = null;
page.on("response", async (res) => {
  if (new URL(res.url()).pathname.endsWith("/plans/form-options") && res.ok()) served = await res.json().catch(() => null);
});

for (const lang of LANGS) {
  if (want("list")) {
    await go(`${BASE}/${TENANT}/plans-rates/plans`);
    await page.getByRole("table").waitFor();
    await shot("list", lang);
  }

  if (want("new")) {
    await go(`${BASE}/${TENANT}/plans-rates/plans/new`);
    await page.getByLabel(/^Plan name/).waitFor();
    // A fresh code each run: a code already filed is refused (duplicate_code).
    const stamp = `${RUN}${LANGS.indexOf(lang)}`;
    await page.getByLabel(/^Plan name/).fill(`Residential City Plan ${stamp}`);
    await page.getByLabel(/^Code/).fill(`RCP-${stamp}`);
    await page.getByLabel(/^Description for customers/).fill("Water for homes inside the city.");
    await shot("new-1-details", lang);
    await setLang("en");
    await click("Continue");
    await page.getByRole("button", { name: "+ Add service" }).waitFor();
    const sched = served?.schedules?.find((s) => s.service === "water") ?? served?.schedules?.[0];
    await click("+ Add service");
    await pickLast("Service", sched.service);
    await pickLast("Rate schedule", sched.ref.id);
    await shot("new-2-services", lang);
    await setLang("en");
    await click("Continue");
    await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
    if (served?.taxes?.length) {
      await click("+ Add tax");
      await pickLast("Tax", served.taxes[0].ref.id);
    }
    await shot("new-3-charges", lang);
    await setLang("en");
    await click("Continue");
    await page.getByRole("button", { name: "+ Add deposit" }).waitFor();
    await page.getByLabel(/^Minimum bill/).fill("10");
    await shot("new-4-billing", lang);
    await setLang("en");
    await click("Continue");
    await page.getByRole("button", { name: "Publish plan" }).waitFor();
    await page.fill("#plan-starts", "2026-11-01");
    await shot("new-5-review", lang);
    await setLang("en");
    await click("Save as draft");
    await page.getByText(`Residential City Plan ${stamp} saved`, { exact: true }).waitFor({ timeout: 20000 });
    await shot("new-6-saved", lang);
  }

  if (want("detail")) {
    await go(at(id));
    await page.locator("[data-plan-overview]").waitFor();
    await shot("detail-1-overview", lang);
    await page.locator("[data-plan-more] summary").click();
    await shot("detail-2-more", lang);
    await page.locator("[data-plan-more] summary").click();

    await go(at(id, "?tab=services"));
    await page.locator("[data-plan-priced-tab=services]").waitFor();
    await page.getByRole("button", { name: /Expand all/ }).click();
    await shot("detail-3-services", lang);

    await go(at(id, "?tab=charges"));
    await page.locator("[data-plan-priced-tab=charges]").waitFor();
    await shot("detail-4-charges", lang);

    await go(at(id, "?tab=billing"));
    await page.locator("[data-plan-priced-tab=billing]").waitFor();
    await shot("detail-5-billing", lang);

    await go(at(id, "?tab=units"));
    await page.locator("[data-plan-units] tbody tr").first().waitFor();
    await shot("detail-6-units", lang);

    await go(at(id, "?tab=audit"));
    await page.locator("[data-plan-audit]").waitFor();
    await settle(1200);
    await shot("detail-7-audit", lang);

    await go(at(id));
    await page.locator("[data-plan-overview]").waitFor();
    await page.locator("[data-plan-more] summary").click();
    await page.getByTestId("plan-more-retire").click();
    await page.locator('[role="dialog"], [role="alertdialog"], dialog[open]').first().waitFor();
    await shot("detail-8-retire-dialog", lang);
    await page.keyboard.press("Escape");
  }

  if (want("edit")) {
    await go(at(editId, "/edit"));
    await settle(1200);
    await shot("edit-1-choose", lang);
    await go(at(editId, "/edit?change=change&step=2"));
    await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
    await click("Continue");
    await page.getByLabel(/^Minimum bill/).waitFor();
    await page.getByLabel(/^Minimum bill/).fill("12.00");
    await click("Continue");
    await page.getByText("How it is saved").waitFor();
    await page.fill("#plan-starts", "2027-01-01");
    await page.locator("#plan-starts").blur();
    await shot("edit-2-change-review", lang);
  }
}

say(`\n${findings.length} photograph(s) with something to read:`);
for (const f of findings) say(`  ${f}`);
await browser.close();
