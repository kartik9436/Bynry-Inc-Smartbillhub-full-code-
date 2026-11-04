// CR-168-BRC10 round 8, lane FIX-8B — each fix walked at 1440 on PostgreSQL 16
// after `cr168_r8_fix8b_walk_prep.py` (which prints the three order numbers).
//
//   BASE=http://127.0.0.1:5225 OUT=<dir> FINISHED=WO-0043 NOPRIO=WO-0044 \
//   MOVEOUT=WO-0045 ADVICE=WO-0027 node 10-scripts/cr168_r8_fix8b_walk.mjs
//
// WRITES IT MAKES: Send back on FINISHED (with a reason) and one Duplicate of
// NOPRIO. Everything else is a read. Prints PASS/FAIL per check.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5225";
const TENANT = "brazosbend";
const OUT = process.env.OUT ?? "/tmp/fix8b";
const FINISHED = process.env.FINISHED ?? "WO-0043";
const NOPRIO = process.env.NOPRIO ?? "WO-0044";
const MOVEOUT = process.env.MOVEOUT ?? "WO-0045";
const ADVICE = process.env.ADVICE ?? "WO-0027";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
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
function check(name, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const settle = (ms = 1200) => page.waitForTimeout(ms);
async function go(path) {
  try { await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle", timeout: 30000 }); }
  catch { console.log("goto timeout", path); }
  await settle(1500);
}
async function shot(name) {
  await settle(500);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log(`=== ${name}.png — ${page.url().replace(BASE, "")}`);
}
async function api(path, method = "GET", body) {
  return page.evaluate(async ([t, p, m, b]) => {
    const r = await fetch(`/api/${t}/${p}`, { method: m, credentials: "include",
      headers: b ? { "Content-Type": "application/json" } : {}, body: b ? JSON.stringify(b) : undefined });
    let json = null; try { json = await r.json(); } catch { /* not JSON */ }
    return { status: r.status, body: json };
  }, [TENANT, path, method, body]);
}
const main = () => page.locator("main").innerText();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── DEF-WRK-9680 · five tiles, one row at 1440 ─────────────────────────────
await go("/work/orders");
const rows = await page.evaluate(() => {
  const tops = [...document.querySelectorAll(".kpi-grid > .kpi")].map((el) => Math.round(el.getBoundingClientRect().top));
  return { tiles: tops.length, rows: new Set(tops).size, gridWidth: Math.round(document.querySelector(".kpi-grid").getBoundingClientRect().width) };
});
check("9680 five Orders tiles sit on ONE row at 1440", rows.tiles === 5 && rows.rows === 1, JSON.stringify(rows));
await shot("fix8b-01-orders-tiles-one-row-1440");
await page.setViewportSize({ width: 900, height: 1000 });
await settle(800);
const narrow = await page.evaluate(() => new Set([...document.querySelectorAll(".kpi-grid > .kpi")].map((el) => Math.round(el.getBoundingClientRect().top))).size);
check("9680 a narrow screen still wraps", narrow > 1, `rows at 900: ${narrow}`);
await page.setViewportSize({ width: 1440, height: 1000 });
await settle(800);

// ── DEF-WRK-9689 · Select all ─────────────────────────────────────────────
const head = page.locator("thead input[data-select-all]");
check("9689 the select column has a Select all box", (await head.count()) === 1);
await head.check();
await settle(600);
const bar = await page.locator("[data-bulk-bar]").innerText().catch(() => "");
const ticked = await page.locator("tbody input[type=checkbox]:checked").count();
const all = await page.locator("tbody input[type=checkbox]").count();
check("9689 Select all ticks every row on the page", ticked === all && all > 0, `${ticked} of ${all}; bar: ${bar.replace(/\n/g, " · ")}`);
await shot("fix8b-02-orders-select-all-1440");
await head.uncheck();
await settle(400);

// ── DEF-WRK-9582 · the Type filter in two levels ───────────────────────────
await page.locator("summary", { hasText: "Filter" }).first().click();
await settle(600);
const levels = await page.evaluate(() =>
  [...document.querySelectorAll("label[data-filter-level]")].slice(0, 8).map((l) => `${l.getAttribute("data-filter-level")}:${l.textContent}`));
check("9582 the Type filter draws headings and indented sub-types", levels.some((l) => l.startsWith("1:")) && levels.some((l) => l.startsWith("2:")), levels.join(" | "));
await shot("fix8b-03-orders-type-filter-two-levels-1440");
await page.keyboard.press("Escape");
await page.locator("summary", { hasText: "Filter" }).first().click();
await settle(400);

// ── DEF-SHL-5345 · one clear cross ────────────────────────────────────────
const search = page.locator('main input[type="search"]').first();
await search.fill("WO");
await settle(1000);
// ⚠ `getComputedStyle(input, "::-webkit-search-cancel-button")` CANNOT read a
// WebKit pseudo-element — Chromium answers the INPUT's own style ("auto")
// whether or not the button is hidden, so the round-7 probe built on it could
// not tell fixed from broken (law 7: looking at the wrong thing). This asks
// the two facts that decide it — the input carries the utility, and the
// shipped stylesheet holds the rule — and the clipped photograph shows it.
const crosses = await page.evaluate(() => {
  const input = document.querySelector('main input[type="search"]');
  const cls = "[&::-webkit-search-cancel-button]:appearance-none";
  let rule = false;
  for (const sheet of document.styleSheets) {
    try {
      const walk = (rules) => { for (const r of rules) { if (r.cssRules) walk(r.cssRules); if ((r.selectorText ?? "").includes("search-cancel-button") && /appearance:\s*none/.test(r.cssText)) rule = true; } };
      walk(sheet.cssRules);
    } catch { /* cross-origin */ }
  }
  return { utility: input.classList.contains(cls), rule };
});
check("5345 Chromium's own cancel button is hidden", crosses.utility && crosses.rule, JSON.stringify(crosses));
const sb = await search.boundingBox();
if (sb) await page.screenshot({ path: `${OUT}/fix8b-04-orders-search-one-cross.png`, clip: { x: sb.x - 8, y: sb.y - 8, width: sb.width + 16, height: sb.height + 16 } });
console.log("=== fix8b-04-orders-search-one-cross.png");
await search.fill("");

// ── DEF-WRK-9675 · 9681 · 9678 · the finished job ──────────────────────────
await go(`/work/orders/${FINISHED}`);
const pills = await page.evaluate(() => [...document.querySelectorAll(".page-header .pill, [class*=page-header] .pill")].map((p) => p.textContent));
check("9681 the head reads Complete first", pills[0] === "Complete", pills.join(" · "));
const heads = await page.locator(".page-header-actions button").allInnerTexts();
check("9675 the finished job offers Send back… beside Accept", heads.includes("Send back…") && heads.includes("Accept ✓"), heads.join(" · "));
const holder = await main();
const holderLine = holder.split("\n").find((l) => l.includes(" · C-")) ?? "";
check("9678 Holder carries the customer number", /· C-\d+/.test(holder), holderLine);
await shot("fix8b-05-finished-order-head-1440");
await page.getByRole("button", { name: "Send back…" }).click();
await settle(600);
await shot("fix8b-06-send-back-dialog-1440");
await page.getByRole("dialog").getByLabel(/Reason/).fill("No photo of the old meter.");
await page.getByRole("dialog").getByRole("button", { name: "Send back" }).click();
await settle(2000);
const after = await api(`work-orders/by-number/${FINISHED}`);
check("9675 Send back returns the job to the field", after.body?.state === "in_progress", `state ${after.body?.state} · dispatch ${after.body?.dispatch_state}`);
await go(`/work/orders/${FINISHED}?tab=audit`);
await shot("fix8b-07-sent-back-audit-1440");

// ── DEF-WRK-9677 · Due on a job with no priority ──────────────────────────
await go(`/work/orders/${NOPRIO}`);
const due = await page.evaluate(() => {
  const dt = [...document.querySelectorAll("dt")].find((d) => d.textContent === "Due");
  return dt?.nextElementSibling?.textContent ?? null;
});
check("9677 Due shows a date on a job with no priority", !!due && due !== "—", `Due: ${due}`);
await shot("fix8b-08-no-priority-due-1440");

// ── DEF-WRK-9690 · Duplicate ─────────────────────────────────────────────
await page.getByRole("button", { name: "Duplicate" }).click();
await settle(500);
await shot("fix8b-09-duplicate-confirm-1440");
await page.getByRole("alertdialog").getByRole("button", { name: "Duplicate" }).click();
await settle(2500);
const url = page.url();
check("9690 Duplicate opens a NEW order", !url.endsWith(`/${NOPRIO}`) && /\/work\/orders\/WO-\d+/.test(url), url.replace(BASE, ""));
await shot("fix8b-10-duplicate-new-order-1440");

// ── DEF-WRK-9694 · the move-out row's job has a checklist ──────────────────
await go(`/work/orders/${MOVEOUT}?tab=checklist`);
const taskRows = await page.locator("[data-task-row]").count();
const version = await api(`work-orders/by-number/${MOVEOUT}`);
check("9694 the move-out visit row's job carries its template's checklist", taskRows > 0, `${taskRows} task rows · raised by ${version.body?.source}`);
await shot("fix8b-11-move-out-row-checklist-1440");

// ── DEF-WRK-9676 · advice on a build job ─────────────────────────────────
const one = await api(`work-orders/by-number/${ADVICE}`);
const cands = await api(`work-orders/${one.body?.id}/candidates`);
const missing = (cands.body?.results ?? []).filter((c) => c.advice?.skill && c.advice?.has_skill === false).map((c) => c.name);
check("9676 a build job's advice names a missing skill", missing.length > 0, `${ADVICE}: missing skill for ${missing.join(", ")}`);
await go(`/work/orders/${one.body?.id}/edit`);
const picker = page.getByRole("combobox", { name: /Assigned to/ });
await picker.focus().catch(() => {});
await picker.click().catch(() => {});
await settle(1000);
await shot("fix8b-12-build-job-advice-1440");

await browser.close();
