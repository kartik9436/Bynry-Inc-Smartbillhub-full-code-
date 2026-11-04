// ── Trace ──────────────────────────────────────────────
// Change:  CR-167-BRC10 — Plans & Rates › Plans redesign, round 1 (lane
//          PLAN-CR), part 2 — a NEW plan through all 8 steps: REPRODUCE today's plan screens before anything is fixed
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
//   OUT=08-qa/plans-2026-10-03/before node 10-scripts/cr167_plans_before_walk_new.mjs
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

// ── PART 2 · a NEW plan through all eight steps, saved as a draft, reopened,
// published, then changed — so the problems the PO photographed on a real
// utility (DEF-RAT-9285..9288) can be checked on this database, and ruling 6
// ("unable to add utility services") and ruling 10 (no Publish on Review) can
// be met as a clerk meets them.
const CODE = process.env.CODE ?? `WALK${Date.now() % 100000}`;
async function pickByText(selectLocator, text) {
  const value = await selectLocator.evaluate((el, t) => {
    const o = Array.from(el.options).find((x) => x.textContent.trim().startsWith(t));
    return o ? o.value : null;
  }, text);
  if (value === null) return false;
  await selectLocator.selectOption(value);
  await page.waitForTimeout(500);
  return true;
}
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await page.fill("#plan-name", "Walk — Residential City");
await page.fill("#plan-code", CODE);
const classSelect = page.locator("main select").first();
say("CLASS PICK Residential:", await pickByText(classSelect, "Residential"));
await shot("p1-new-step1-filled", "new · step 1 filled (class picked from 'Add a class…')");
say(await mainText());
await pressContinue();
// step 2 — ruling 6
const serviceSelect = page.locator("main select").first();
say("SERVICE OPTIONS:", JSON.stringify(await serviceSelect.evaluate((el) => Array.from(el.options).map((o) => o.textContent.trim()))));
say("SERVICE PICK Water:", await pickByText(serviceSelect, "Water"));
await shot("p2-new-step2-water-added", "new · step 2 after picking Water from 'Add a service…'");
say(await mainText());
await dump("p-step2");
await pressContinue();
// step 3
const sched = page.locator("#schedule-water");
say("SCHEDULE OPTIONS water:", JSON.stringify(await sched.evaluate((el) => Array.from(el.options).map((o) => o.textContent.trim())).catch(() => [])));
await pickByText(sched, "Sample — Residential water");
await shot("p3-new-step3", "new · step 3 schedule picked");
await pressContinue();
// step 4
await shot("p4-new-step4", "new · step 4 charges");
say(await mainText());
await pressContinue();
// step 5
await shot("p5-new-step5", "new · step 5 taxes");
say(await mainText());
await pressContinue();
// step 6
await page.fill("#plan-minimum-bill", "10");
await shot("p6-new-step6", "new · step 6 minimum bill 10 typed");
await pressContinue();
// step 7
await page.selectOption("#eligibility-attribute", { label: "Customer class" });
await page.waitForTimeout(400);
await page.selectOption("#eligibility-operator", { label: "is" });
const valueKind = await page.$eval("#eligibility-value", (el) => el.tagName);
if (valueKind === "SELECT") await pickByText(page.locator("#eligibility-value"), "Residential");
else await page.fill("#eligibility-value", "Residential");
await page.getByRole("button", { name: /Add a note/ }).click();
await page.waitForTimeout(500);
await page.fill("#plan-effective-from", "2026-11-01");
await shot("p7-new-step7-note-added", "new · step 7 note Customer class is Residential, start 11/01/2026");
say(await mainText());
await pressContinue();
await shot("p8-new-step8-review", "new · step 8 review (what are the closing buttons?)");
say(await mainText());
await dump("p-step8");
await page.getByRole("button", { name: /Save draft/ }).first().click();
await page.waitForTimeout(2500);
say("AFTER SAVE DRAFT URL:", page.url());
const all = await api("GET", "plans?per=100");
const mine = (all.data?.results ?? []).find((p) => p.code === CODE);
say("SAVED DRAFT:", JSON.stringify(mine && { id: mine.id, status: mine.status, version: mine.version }));
const id = mine.id;
say("DRAFT READ:", JSON.stringify((await api("GET", `plans/${id}`)).data).slice(0, 3000));

// reopen the draft: step 6 (minimum bill, DEF-RAT-9287) and step 7 (DEF-RAT-9285)
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${id}/edit`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
for (let s = 1; s <= 5; s += 1) await pressContinue();
say("REOPENED step 6 minimum bill box:", await page.$eval("#plan-minimum-bill", (el) => el.value).catch(() => "(absent)"));
await shot("r6-reopen-step6-minimum", "reopened draft · step 6 minimum bill box");
await pressContinue();
await shot("r7-reopen-step7-notes", "reopened draft · step 7 notes");
say(await mainText());

// publish, then change the class and the minimum bill — the Audit tab (DEF-RAT-9288)
const pub = await api("POST", `plans/${id}/publish`, {});
say("PUBLISH:", pub.status, JSON.stringify(pub.data).slice(0, 300));
const before = (await api("GET", `plans/${id}`)).data;
const classes = await api("GET", "lookups/account_types?per=100");
say("CLASSES READ:", classes.status, JSON.stringify(classes.data).slice(0, 400));
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${id}?tab=overview`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("v1-published-overview", "published walk plan · overview");
say(await mainText());
say("BEFORE minimum/classes:", before.minimum_bill_amount, JSON.stringify(before.account_type_ids));
// change through the wizard, as a clerk does: step 1 add Commercial, step 6 minimum 12, step 8 reason, publish
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${id}/edit`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await pickByText(page.locator("main select").first(), "Commercial");
for (let s = 1; s <= 5; s += 1) await pressContinue();
await page.fill("#plan-minimum-bill", "12");
await pressContinue();
await pressContinue();
await page.fill("#plan-reason", "Walk: add Commercial, minimum 12");
await shot("c8-change-step8", "change · step 8 with reason");
await page.getByRole("button", { name: /Publish/ }).first().click();
await page.waitForTimeout(3000);
say("AFTER PUBLISH CHANGE URL:", page.url(), "|", (await mainText()).slice(0, 600));
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${id}?tab=audit`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("v2-audit-after-change", "published walk plan · audit after the change");
say(await mainText());
await browser.close();
