// CR-168-BRC10 final round, lane FIN-W — the open Work screen defects, each
// reproduced (or not) on the tip at 1440 on PostgreSQL 16, before and after.
//
//   BASE=http://127.0.0.1:5231 OUT=<dir> PREFIX=finw-before node 10-scripts/cr168_finw_walk.mjs
//
// ONE WRITE (9697: WO-0019's due set to a date, as the Edit form does). Prints one PASS/FAIL line per check; PASS means the screen does
// what the defect row says it should, so a "before" run on a live defect reads
// FAIL and the "after" run reads PASS.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5231";
const TENANT = "brazosbend";
const OUT = process.env.OUT ?? "/tmp/finw";
const PREFIX = process.env.PREFIX ?? "finw";
const ONLY = (process.env.ONLY ?? "").split(",").filter(Boolean);
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
const want = (id) => ONLY.length === 0 || ONLY.includes(id);

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const settle = (ms = 1200) => page.waitForTimeout(ms);
async function go(path) {
  try { await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle", timeout: 30000 }); }
  catch { console.log("goto timeout", path); }
  await settle(1500);
}
async function shot(name) {
  await settle(400);
  await page.screenshot({ path: `${OUT}/${PREFIX}-${name}.png` });
  console.log(`=== ${PREFIX}-${name}.png — ${page.url().replace(BASE, "")}`);
}
async function api(path) {
  return page.evaluate(async ([t, p]) => {
    const r = await fetch(`/api/${t}/${p}`, { credentials: "include" });
    let json = null; try { json = await r.json(); } catch { /* not JSON */ }
    return { status: r.status, body: json };
  }, [TENANT, path]);
}
const mainText = () => page.locator("main").innerText().catch(() => "");
/** How many text lines a cell's TEXT occupies — 1 means it did not wrap. Only
 *  the text nodes are measured: a decorative glyph beside the number (the
 *  Schedule board's drag handle) sits at another top on the SAME line and
 *  read as a wrap in this walk's first draft. */
const linesOf = (selector) => page.evaluate((sel) => [...document.querySelectorAll(sel)].slice(0, 6).map((el) => {
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const tops = new Set();
  let text = "";
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node.parentElement?.closest("[aria-hidden=true]") || node.textContent.trim() === "") continue;
    text += node.textContent.trim();
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const r of range.getClientRects()) tops.add(Math.round(r.top));
  }
  return { text, lines: tops.size };
}), selector);
async function write(path, method, body) {
  return page.evaluate(async ([t, p, m, b]) => {
    const r = await fetch(`/api/${t}/${p}`, { method: m, credentials: "include",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
    let json = null; try { json = await r.json(); } catch { /* not JSON */ }
    return { status: r.status, body: json };
  }, [TENANT, path, method, body]);
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
await settle(2000);
const version = await page.evaluate(() => document.body.innerText.match(/v\d+\.\d+\.\d+/)?.[0] ?? "?");
console.log(`bundle ${version}`);

// ── DEF-WRK-9698 · the order number on Orders ─────────────────────────────
if (want("9698")) {
  await go("/work/orders");
  await page.locator("main tbody tr").first().waitFor({ timeout: 30000 }).catch(() => {});
  await settle(800);
  const cells = await linesOf("tbody tr td [data-order-no], tbody tr td:nth-child(2) span.tabular-nums");
  check("9698 every order number sits on one line", cells.length > 0 && cells.every((c) => c.lines === 1), JSON.stringify(cells.slice(0, 3)));
  await shot("01-orders-order-number");
}

// ── DEF-WRK-9657 · the order number on the Schedule board ─────────────────
if (want("9657")) {
  await go("/work/performance?view=schedule");
  if (!(await page.locator("[data-testid=schedule-queue]").count())) {
    await page.getByRole("tab", { name: /Schedule/ }).click().catch(() => {});
    await settle(1500);
  }
  const cells = await linesOf("[data-testid=schedule-queue] [data-drag-order]");
  check("9657 the Schedule board's order numbers sit on one line", cells.length > 0 && cells.every((c) => c.lines === 1), JSON.stringify(cells.slice(0, 3)));
  await shot("02-schedule-order-number");
}

// ── DEF-WRK-9697 · a date-only due ────────────────────────────────────────
if (want("9697")) {
  // THE ONE WRITE: WO-0019's due set to a DATE, with exactly the body the
  // order's Edit form sends for a picked day (`OrderEditPage`: `${day}T00:00:00`).
  const target = (await api("work-orders/by-number/WO-0019")).body;
  const saved = await write(`work-orders/${target?.id}`, "PATCH", { due_at: "2026-10-09T00:00:00" });
  console.log(`9697 prep: PATCH due_at 2026-10-09T00:00:00 → ${saved.status} · due_at ${saved.body?.due_at ?? (await api("work-orders/by-number/WO-0019")).body?.due_at}`);
  const midnight = { order_no: "WO-0019" };
  {
    await go(`/work/orders/${midnight.order_no}`);
    const due = await page.evaluate(() => {
      const dt = [...document.querySelectorAll("dt")].find((d) => d.textContent === "Due");
      return dt?.nextElementSibling?.textContent ?? null;
    });
    check("9697 a date-only due reads as a date", !!due && !/00:00/.test(due), `${midnight.order_no} Due: ${due}`);
    await shot("03-order-date-only-due");
    await go("/work/orders");
    const listDue = await page.evaluate((no) => {
      const row = [...document.querySelectorAll("tbody tr")].find((tr) => tr.textContent.includes(no));
      return row ? row.innerText.replace(/\s+/g, " ") : null;
    }, midnight.order_no);
    check("9697 the list's Due for that order has no 00:00", listDue !== null && !/00:00/.test(listDue), listDue ?? "row not on page 1");
  }
}

// ── DEF-WRK-4104 / 4635 · the checklist tab ───────────────────────────────
if (want("4104")) {
  const list = await api("work-orders?page_size=100");
  const withTemplate = (list.body?.results ?? []).find((r) => r.template_id || r.template);
  const no = withTemplate?.order_no ?? "WO-0016";
  await go(`/work/orders/${no}?tab=checklist`);
  const text = await mainText();
  check("4104 no raw key over the task list", !/work\.order\.tasks/.test(text), text.split("\n").find((l) => /TASKS|tasks/.test(l)) ?? "");
  check("4635 the checklist does not say 'raised without a template'", !/without a template/i.test(text));
  await shot("04-order-checklist");
}

// ── DEF-WRK-4115 · the order opens by its number ──────────────────────────
if (want("4115")) {
  await go("/work/orders/WO-0016");
  const text = await mainText();
  check("4115 /work/orders/WO-0016 draws the order", text.includes("WO-0016") && !/could not be opened/i.test(text));
  await shot("05-order-by-number");
}

// ── DEF-WRK-4637 · a template that will not open ───────────────────────────
if (want("4637")) {
  await go("/work/templates/00000000-0000-4000-8000-000000000000");
  await settle(2500);
  const text = await mainText();
  const live = await page.evaluate(() => [...document.querySelectorAll("main button")].filter((b) => /Edit|Duplicate|Deactivate|Delete/.test(b.textContent) && !b.disabled).map((b) => b.textContent.trim()));
  check("4637 an unknown template says it could not be opened", !/^Loading$/m.test(text) && /unavailable|has this address|could not/i.test(text), text.split("\n").slice(0, 6).join(" | "));
  check("4637 no live command over nothing", live.length === 0, live.join(", "));
  await shot("06-template-unknown");
}

// ── DEF-WRK-4094 · ?q= ─────────────────────────────────────────────────────
if (want("4094")) {
  for (const [path, term] of [["/work/orders", "WO-0016"], ["/work/templates", "Meter"], ["/work/parts", "Meter"], ["/work/crews", "Ortiz"]]) {
    await go(`${path}?q=${encodeURIComponent(term)}`);
    const value = await page.locator('main input[type="search"]').first().inputValue().catch(() => "");
    check(`4094 ${path}?q= seeds the search`, value === term, `box reads '${value}'`);
  }
  await shot("07-crews-q");
}

// ── DEF-WRK-4102 / 4103 · Rules and Labour rates ──────────────────────────
if (want("4102")) {
  await go("/work/rules");
  const rules = await page.locator("main tbody tr").count();
  const served = (await api("work/rules")).body?.count;
  check("4102 Rules draws the rules the API serves", rules > 0, `${rules} rows drawn · ${served} served`);
  await shot("08-rules");
  await go("/settings/reference-data/work-labour-rates");
  const rates = await page.locator("main tbody tr").count();
  const servedRates = (await api("work/labour-rates")).body?.count;
  check("4103 Labour rates draws the rates the API serves", rates > 0, `${rates} rows drawn · ${servedRates} served`);
  await shot("09-labour-rates");
}

// ── DEF-WRK-4106 · the Performance search ─────────────────────────────────
if (want("4106")) {
  await go("/work/performance");
  const placeholders = await page.evaluate(() => [...document.querySelectorAll("main input[type=search]")].map((i) => i.placeholder));
  check("4106 no 'Search this list' on Performance", !placeholders.includes("Search this list"), JSON.stringify(placeholders));
  await shot("10-performance");
}

// ── DEF-WRK-4107 · Crews' composition sentence ────────────────────────────
if (want("4107")) {
  await go("/work/crews");
  const text = await mainText();
  const counts = (await api("work/crews/counts")).body;
  check("4107 Crews names its people, crews and contractors", /\d+\s+(people|technicians?)/i.test(text) && /\d+\s+crews?/i.test(text) && /\d+\s+contractors?/i.test(text), `counts ${JSON.stringify(counts)} · ${text.split("\n").slice(0, 8).join(" | ")}`);
  await shot("11-crews");
}

// ── DEF-WRK-3724 · the templates tab ──────────────────────────────────────
if (want("3724")) {
  await go("/work/templates");
  const text = await mainText();
  const back = await page.evaluate(() => [...document.querySelectorAll("main a, main button")].map((a) => a.textContent.trim()).filter((s) => s.startsWith("←")));
  const paragraphs = await page.evaluate(() => [...document.querySelectorAll("main p")].map((p) => p.textContent.trim()).filter((s) => s.split(/\s+/).length > 12));
  check("3724 no back arrow naming the Dashboard", !back.some((b) => /Dashboard/.test(b)), back.join(", "));
  check("3724 no paragraph of rationale", paragraphs.length === 0, paragraphs.slice(0, 2).join(" ¶ "));
  await shot("12-templates");
}

// ── DEF-RBS-4374 · the Work list card ──────────────────────────────────────
if (want("4374")) {
  await go("/runbooks");
  const work = page.locator("main").getByRole("link", { name: /Work list/ });
  const asButton = page.locator("main").getByRole("button", { name: /Work list/ });
  const linkCount = await work.count();
  const disabled = (await asButton.count()) > 0 ? await asButton.first().isDisabled() : null;
  check("4374 Work list → is a live door", linkCount > 0 || disabled === false, `links ${linkCount} · button disabled ${disabled}`);
  await shot("13-runbooks-work-list");
}

// ── DEF-WRK-9561 · Map tiles ──────────────────────────────────────────────
if (want("9561")) {
  await go("/work/map");
  await settle(3000);
  const tiles = await page.evaluate(() => document.querySelectorAll(".leaflet-tile-loaded, .leaflet-tile, img[src*='tile'], img[src*='arcgis']").length);
  check("9561 the Work map draws street tiles", tiles > 0, `${tiles} tiles`);
  await shot("14-work-map");
}


// ── DEF-SHL-5771 · one table type (a TableArray beside a DataTable) ────────
if (want("5771")) {
  await go("/work/performance?view=schedule");
  const fonts = await page.evaluate(() => {
    const kit = document.querySelector("[data-editable-table] thead th:not(:empty)");
    const list = document.querySelector(".data-table thead th, table thead th");
    const f = (el) => el ? getComputedStyle(el).fontFamily : null;
    return { tableArray: f(kit), tracking: kit ? getComputedStyle(kit).letterSpacing : null };
  });
  check("5771 a TableArray header is not monospace", !!fonts.tableArray && !/mono/i.test(fonts.tableArray), JSON.stringify(fonts));
  await shot("15-schedule-tablearray-headers");
}

// ── DEF-MET-4973 · an asset no template fits ──────────────────────────────
if (want("4973")) {
  const assets = (await api("assets?per=200")).body?.results ?? [];
  const m = assets.find((a) => a.asset_no === "M-7204");
  if (!m) console.log("SKIP 4973 M-7204 not found");
  else {
    await go(`/assets/${m.id}/work-orders/new`);
    const link = page.locator("main a[data-new-template-link]");
    const href = (await link.count()) ? await link.getAttribute("href") : null;
    check("4973 the refusal offers New template", href === `/${TENANT}/work/templates/new`, `href ${href}`);
    await shot("16-asset-raise-no-template");
  }
}

await browser.close();
