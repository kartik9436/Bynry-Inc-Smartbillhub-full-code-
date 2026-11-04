// ── Trace ──────────────────────────────────────────────
// Change:  CR-168-BRC10 — Work back-office redesign, round 1 (lane WORK-CR):
//          REPRODUCE today's Work back-office screens in the 65 states the
//          drawing draws (05-prototype/work-backoffice-2026-10-04/images), and
//          INVENTORY every control on them, so CR-168 §4 (re-measured) and §5
//          (the field map) are built from the running screen, not the source.
//          Shape copied from `cr167_plans_before_walk.mjs`.
// ───────────────────────────────────────────────────────
//
// Writes to the database only what a clerk's own presses write in phase 2
// (one hold, one cancel on a throwaway order, one raise attempt, one part
// add attempt), each named in the output.
//
// Expects the API on a scratch PostgreSQL 16 database (`migrate` + `seed_demo`
// + `load_sample_data --tenant brazosbend`) and the SPA from
// `vite build --mode wolocal` served by `07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:5411 OUT=08-qa/work-2026-10-04/before PHASE=1 \
//     node 10-scripts/cr168_work_before_walk.mjs
//
// ⚠ A native <select>'s open list cannot be photographed; the walk prints the
// options instead.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5411";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr168-before";
const PHASE = process.env.PHASE ?? "1";
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
const page = await browser.newPage({ viewport: { width: 1440, height: Number(process.env.VH ?? 2400) } });
const consoleErrors = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200)); });
const failed = [];
page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`); });
const say = (...parts) => console.log(...parts);
const settle = (ms = 1200) => page.waitForTimeout(ms);
async function shot(name, caption) {
  await settle();
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  say(`\n=== ${name}.png — ${caption} — ${page.url().replace(BASE, "")}`);
  if (failed.length) { say("API ERRORS:", JSON.stringify(failed.splice(0))); }
}
async function mainText() {
  try { return (await page.innerText("main", { timeout: 3000 })).replace(/\n{2,}/g, "\n"); }
  catch { return (await page.innerText("body")).replace(/\n{2,}/g, "\n"); }
}
async function dialogText() {
  const d = page.locator('[role="dialog"]');
  if (await d.count()) return (await d.first().innerText()).replace(/\n{2,}/g, "\n");
  return "(no dialog)";
}
async function api(method, path, body) {
  return page.evaluate(
    async ([m, p, b]) => {
      const res = await fetch(`/api/${p}`, {
        method: m, credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: b === undefined ? undefined : JSON.stringify(b),
      });
      let data = null;
      try { data = await res.json(); } catch { data = null; }
      return { status: res.status, data };
    },
    [method, `${TENANT}/${path}`, body],
  );
}
async function controls(scope = "main") {
  return page.$$eval(`${scope} input, ${scope} select, ${scope} textarea, ${scope} [role="combobox"]`, (els) =>
    els.filter((el) => el.type !== "hidden").map((el) => {
      const id = el.id || "";
      let label = "";
      if (id) { const l = document.querySelector(`label[for="${CSS.escape(id)}"]`); if (l) label = l.textContent.trim(); }
      if (!label) label = el.getAttribute("aria-label") || el.getAttribute("placeholder") || "";
      if (!label) { const wrap = el.closest("label"); if (wrap) label = wrap.textContent.trim(); }
      if (!label) {
        const td = el.closest("td"); const table = el.closest("table");
        if (td && table) { const idx = Array.from(td.parentElement.children).indexOf(td); const th = table.querySelectorAll("thead th")[idx]; if (th) label = `[col] ${th.textContent.trim()}`; }
      }
      const kind = `${el.tagName.toLowerCase()}${el.type ? `[${el.type}]` : ""}`;
      const value = el.type === "checkbox" || el.type === "radio" ? (el.checked ? "checked" : "unchecked")
        : el.tagName === "SELECT" ? (el.options[el.selectedIndex]?.textContent ?? "").trim() : (el.value ?? "");
      const options = el.tagName === "SELECT" ? Array.from(el.options).map((o) => o.textContent.trim()) : undefined;
      return { label: label.replace(/\s+/g, " ").slice(0, 80), kind, value: String(value).slice(0, 60), disabled: el.disabled || undefined,
        options: options && options.length > 14 ? [...options.slice(0, 14), `…(+${options.length - 14})`] : options };
    }),
  );
}
async function buttons(scope = "main") {
  return page.$$eval(`${scope} button, ${scope} a, ${scope} [role="tab"]`, (bs) =>
    bs.map((b) => {
      const label = (b.textContent.trim() || b.getAttribute("aria-label") || b.getAttribute("title") || "").replace(/\s+/g, " ").slice(0, 60);
      const dis = b.hasAttribute("disabled") || b.getAttribute("aria-disabled") === "true";
      const title = b.getAttribute("title");
      return `${b.tagName === "A" ? "link:" : ""}${label}${dis ? " [DISABLED]" : ""}${dis && title ? ` (title: ${title.slice(0, 60)})` : ""}`;
    }).filter((s) => s && s !== "link:"),
  );
}
async function heads() {
  return page.$$eval("main table", (ts) => ts.map((t) => Array.from(t.querySelectorAll("thead th")).map((th) => th.textContent.trim()).join(" | ")));
}
async function dump(tag, scope = "main") {
  const cs = await controls(scope);
  say(`CONTROLS ${tag} (${cs.length}):`);
  for (const c of cs) say("  ", JSON.stringify(c));
  say(`BUTTONS ${tag}:`, JSON.stringify(await buttons(scope)));
  if (scope === "main") say(`TABLE HEADS ${tag}:`, JSON.stringify(await heads()));
}
async function visit(path, name, caption) {
  try {
    await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle", timeout: 30000 });
  } catch (e) { say("goto timeout", path); }
  await settle(1500);
  await shot(name, caption);
  say(await mainText());
  await dump(name);
}
async function step(label, fn) {
  try { await fn(); } catch (e) { say(`!! STEP FAILED ${label}: ${String(e).split("\n")[0]}`); }
}

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

const orders = await api("GET", "work-orders?per=100");
const rows = orders.data?.results ?? orders.data?.rows ?? [];
say("ORDERS SERVED:", orders.status, rows.length, JSON.stringify(Object.keys(orders.data ?? {})));
say("ORDER ROWS:", JSON.stringify(rows.map((r) => [r.id, r.order_no ?? r.number, r.status ?? r.dispatch_state, r.assigned_to?.name ?? r.technician ?? r.assignee, r.outcome])).slice(0, 4000));
const awaiting = await api("GET", "work-orders/awaiting-approval?per=100");
const arows = awaiting.data?.results ?? awaiting.data?.rows ?? [];
say("AWAITING:", awaiting.status, arows.length, JSON.stringify(arows.map((r) => [r.id, r.order_no ?? r.number])).slice(0, 2000));
const techs = await api("GET", "work/technicians?per=100");
const trows = techs.data?.results ?? techs.data?.rows ?? techs.data ?? [];
say("TECHNICIANS:", techs.status, JSON.stringify(techs.data).slice(0, 1500));
const tpls = await api("GET", "work/templates?per=100");
const tplrows = tpls.data?.results ?? tpls.data?.rows ?? [];
say("TEMPLATES:", tpls.status, JSON.stringify(tplrows.map((t) => [t.id, t.name, t.status])).slice(0, 2000));
const rules = await api("GET", "work/rules?per=100");
const rrows = rules.data?.results ?? rules.data?.rows ?? [];
say("RULES:", rules.status, JSON.stringify(rrows.map((t) => [t.id, t.name, t.enabled])).slice(0, 2000));

globalThis.ctx = { rows, arows, trows, tplrows, rrows };
const mod = await import(`./cr168_work_before_walk_phase${PHASE}.mjs`);
await mod.default({ page, BASE, TENANT, OUT, say, settle, shot, mainText, dialogText, api, controls, buttons, dump, visit, step, ctx: globalThis.ctx });
say("\nCONSOLE ERRORS:", JSON.stringify(consoleErrors.slice(0, 40)));
await browser.close();
