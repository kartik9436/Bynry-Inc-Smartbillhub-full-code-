// ── Trace ──────────────────────────────────────────────
// Change:  CR-167-BRC10 — Plans & Rates › Plans redesign, round 1 (lane
//          PLAN-CR): REPRODUCE today's plan screens before anything is fixed
//          (maintenance process, step REPRODUCE) and INVENTORY every input of
//          today's 8-step New/Edit wizard, the list and the details page, so the
//          CR's field map (§5) is built from what the running screen offers and
//          not from the source. Shape copied from `cr166_discounts_before_walk.mjs`.
// ───────────────────────────────────────────────────────
//
// It changes no product code and writes nothing to the database except one
// draft plan created through the New plan wizard's own Save draft (phase 3),
// which is how a clerk would meet the step-2 "unable to add utility services"
// problem (ruling 6).
//
// Expects:
//   * the API — `manage.py runserver 127.0.0.1:8131` on a scratch PostgreSQL 16
//     database with `migrate` + `seed_demo` + `load_sample_data --tenant
//     brazosbend` run (Brazos Bend, Dana);
//   * the SPA — `vite build --mode wolocal` then
//     `PORT=5231 API_PROXY_TARGET=http://127.0.0.1:8131 node 07-frontend/server.mjs`.
//
//   OUT=08-qa/plans-2026-10-03/before node 10-scripts/cr167_plans_before_walk.mjs
//
// ⚠ A native <select>'s open list is drawn by the browser, not the page, so a
// headless photograph cannot show it; where a problem is ABOUT a list's choices
// the walk prints the options instead.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5231";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr167-before";
const PLAN_NAME = process.env.PLAN_NAME ?? "Sample — Residential";
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
// Tall viewport: the app frame scrolls its own main column.
const page = await browser.newPage({ viewport: { width: 1440, height: 2600 } });
const say = (...parts) => console.log(...parts);
const settle = () => page.waitForTimeout(900);
async function shot(name, caption) {
  await settle();
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  say(`\n=== ${name}.png — ${caption}`);
}
async function mainText() {
  return (await page.innerText("main")).replace(/\n{2,}/g, "\n");
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
/** Every form control in <main>: what a clerk can type, tick or pick. */
async function controls() {
  return page.$$eval("main input, main select, main textarea", (els) =>
    els
      .filter((el) => el.type !== "hidden")
      .map((el) => {
        const id = el.id || "";
        let label = "";
        if (id) {
          const l = document.querySelector(`label[for="${CSS.escape(id)}"]`);
          if (l) label = l.textContent.trim();
        }
        if (!label) label = el.getAttribute("aria-label") || "";
        if (!label) {
          const wrap = el.closest("label");
          if (wrap) label = wrap.textContent.trim();
        }
        if (!label) {
          // table array: the column head over this cell
          const td = el.closest("td");
          const table = el.closest("table");
          if (td && table) {
            const idx = Array.from(td.parentElement.children).indexOf(td);
            const th = table.querySelectorAll("thead th")[idx];
            if (th) label = `[col] ${th.textContent.trim()}`;
          }
        }
        const kind = `${el.tagName.toLowerCase()}${el.type ? `[${el.type}]` : ""}`;
        const value =
          el.type === "checkbox" || el.type === "radio"
            ? el.checked
              ? "checked"
              : "unchecked"
            : el.tagName === "SELECT"
              ? (el.options[el.selectedIndex]?.textContent ?? "").trim()
              : el.value;
        const options =
          el.tagName === "SELECT" ? Array.from(el.options).map((o) => o.textContent.trim()) : undefined;
        return {
          id,
          label: label.replace(/\s+/g, " ").slice(0, 90),
          kind,
          value: String(value).slice(0, 80),
          disabled: el.disabled,
          width: Math.round(el.getBoundingClientRect().width),
          options: options && options.length > 12 ? [...options.slice(0, 12), `…(+${options.length - 12})`] : options,
        };
      }),
  );
}
async function buttons() {
  return page.$$eval("main button, main a", (bs) =>
    bs
      .map((b) => {
        const label = (b.textContent.trim() || b.getAttribute("aria-label") || b.getAttribute("title") || "").replace(/\s+/g, " ");
        return `${b.tagName === "A" ? "link:" : ""}${label}${b.hasAttribute("disabled") ? " [DISABLED]" : ""}`;
      })
      .filter(Boolean),
  );
}
async function dump(tag) {
  const cs = await controls();
  say(`CONTROLS ${tag} (${cs.length}):`);
  for (const c of cs) say("  ", JSON.stringify(c));
  say(`BUTTONS ${tag}:`, JSON.stringify(await buttons()));
}
async function stepRail() {
  return page.$$eval("[data-wizard-step]", (els) =>
    els.map((e) => `${e.getAttribute("data-wizard-step")}:${e.textContent.trim()}:${e.getAttribute("data-state")}`),
  );
}
async function pressContinue() {
  const c = page.getByRole("button", { name: /^Continue/ });
  if ((await c.count()) === 0) return false;
  await c.first().click();
  await page.waitForTimeout(900);
  return true;
}

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

const listed = await api("GET", "plans?per=100");
const plans = listed.data?.results ?? listed.data ?? [];
say("PLANS SERVED:", listed.status, JSON.stringify((Array.isArray(plans) ? plans : []).map((p) => [p.id, p.name, p.code, p.status, p.version])));
const target = (Array.isArray(plans) ? plans : []).find((p) => p.name === PLAN_NAME) ?? plans[0];
say("TARGET PLAN:", target?.id, target?.name);
const full = await api("GET", `plans/${target.id}`);
say("PLAN READ KEYS:", JSON.stringify(Object.keys(full.data ?? {})));
say("PLAN READ:", JSON.stringify(full.data).slice(0, 6000));

// ── 1 · THE LIST ────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("l01-list", "plans list as it opens");
say(await mainText());
say("LIST COLUMNS:", JSON.stringify(await page.$$eval("main th", (ths) => ths.map((th) => th.textContent.trim()))));
await dump("list");

// ── 2 · THE DETAILS PAGE, each tab ──────────────────────────────────────────
for (const tab of ["overview", "units", "audit"]) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${target.id}?tab=${tab}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await shot(`d-${tab}`, `details · ${tab}`);
  say(await mainText());
  await dump(`details-${tab}`);
}

// ── 3 · EDIT, all 8 steps of the existing plan ──────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${target.id}/edit`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
for (let step = 1; step <= 8; step += 1) {
  say("RAIL:", JSON.stringify(await stepRail()));
  await shot(`e${step}-edit-step${step}`, `edit · step ${step}`);
  say(await mainText());
  await dump(`edit-step${step}`);
  if (step < 8 && !(await pressContinue())) {
    say("NO CONTINUE on step", step);
    break;
  }
}

// ── 4 · NEW plan: empty Continue, then the services step (ruling 6) ─────────
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
say("RAIL:", JSON.stringify(await stepRail()));
await shot("n1-new-step1-empty", "new · step 1 empty");
await dump("new-step1");
await pressContinue();
await shot("n2-new-step1-continue-empty", "new · step 1 · Continue pressed on empty");
say(await mainText());
await page.fill("#plan-name", "Walk — Plans before");
await page.fill("#plan-code", "WALKPB");
await pressContinue();
say("RAIL:", JSON.stringify(await stepRail()));
await shot("n3-new-step2-services", "new · step 2 services as it opens");
say(await mainText());
await dump("new-step2");
await pressContinue();
await shot("n4-new-step2-continue-empty", "new · step 2 · Continue with no service");
say(await mainText());

await browser.close();
