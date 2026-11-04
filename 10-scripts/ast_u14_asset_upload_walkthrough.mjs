// ── Trace ──────────────────────────────────────────────
// Change:  plan U14 of 04-docs/05-modules/05-assets/12-asset-upload-fix-plan.md
//          — the browser walk of journey J71
//          (08-qa/01-e2e/journeys/J71-asset-upload-carts-and-fire-lines-to-the-bill.md)
// Defects: DEF-AST-8097 · 8098 · 8099 · 8100 · 8101 · 8102 (the ones the upload
//          fix closed; this walk is their browser proof)
// Rules:   BR-AST-541 · BR-AST-034 · BR-AST-012 · hard-won law 6 (no gate reads
//          rendered output) · PO 2026-09-10 (clerk screens at 1280 and 1440)
// ───────────────────────────────────────────────────────
//
// HOW TO RUN IT (the stack this was first walked on, 2026-09-30):
//
//   PostgreSQL 16 on its own port, `migrate`, `seed_demo`, then the J71
//   preconditions (trash + fire switched on; premises 1408 Elm St offering
//   water · electric · trash · fire with Unit A = U-00001, Unit B = U-00003 and
//   Bulk 1–5 = U-00004…U-00008; premises 9 Water Only Rd, water only, Unit W =
//   U-00002) through the metering and tenancy service functions.
//   06-backend $ JOBS_EAGER=false CELERY_BROKER_URL=redis://… manage.py runserver
//   06-backend $ celery -A config.celery worker -Q celery,billing,integrations
//   07-frontend $ npx vite build --mode compose && node server.mjs
//   node 10-scripts/ast_u14_asset_upload_walkthrough.mjs <width> <step…>
//
// Steps: 1 templates · 2 devices insert · 3 re-upload override · 4 errors ·
// 5 250-row background job · 6 500-row update · 7 stage-2 groups.
// Steps 2, 3, 5 and 6 WRITE; the 1280 walk uses Unit B (U-00003) and its own
// external references so the two widths never collide.
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:58484";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = "S3cure!passw0rd";
const CHROME = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OUT = process.env.OUT ?? new URL("../08-qa/screens/asset-upload-2026-09-30/", import.meta.url).pathname;
const FILES = process.env.FILES ?? "/tmp/u14-files";
mkdirSync(OUT, { recursive: true });
mkdirSync(FILES, { recursive: true });

const WIDTH = Number(process.argv[2] ?? 1440);
const STEPS = process.argv.slice(3).map(Number);
const UNIT = process.env.UNIT_NO ?? (WIDTH === 1440 ? "U-00001" : "U-00003");
const TAG = process.env.TAG ?? (WIDTH === 1440 ? "A" : "B");

// ── The PO-confirmed tables, typed from the plan document ──────────────────
const PLAN = {
  assets_meters: [
    ["Identity", ["Meter number (existing only)", "External reference", "Serial number"]],
    ["Location", ["Unit"]],
    ["Service and billing", ["Service", "Connection size", "Unit of measure", "Multiplier", "Net metering"]],
    ["Meter details", ["Meter type", "Read method", "Register digits", "Manufacturer", "Model"]],
    ["Dates", ["Install date", "Certification due", "Warranty end"]],
    ["Purchase", ["Supplier", "Purchase cost"]],
  ],
  assets_submeters: [
    ["Identity", ["Sub-meter number (existing only)", "External reference", "Serial number"]],
    ["Location", ["Unit", "Parent / master meter"]],
    ["Service and billing", ["Service", "Unit of measure", "Multiplier", "Allocation share %", "Allocation rule", "Loss tolerance %"]],
    ["Meter details", ["Meter type", "Read method", "Register digits", "Manufacturer", "Model"]],
    ["Dates", ["Install date", "Certification due", "Warranty end"]],
    ["Purchase", ["Supplier", "Purchase cost"]],
  ],
  assets_devices: [
    ["Identity", ["Device number (existing only)", "Device type", "External reference", "Serial number"]],
    ["Location", ["Premises", "Unit", "Parent / linked meter"]],
    ["Service and billing", ["Service", "Size", "Unit of measure / capacity unit", "Export capacity (kW)"]],
    ["Device details", ["Manufacturer", "Model"]],
    ["Dates and testing", ["Install date", "Test frequency (months)", "Next test due", "Warranty end"]],
    ["Purchase", ["Supplier", "Purchase cost"]],
  ],
};
const COUNT = { assets_meters: 19, assets_submeters: 21, assets_devices: 19 };
const DEVICE_HEADER = PLAN.assets_devices.flatMap(([, cols]) => cols);

// ── Reporting ──────────────────────────────────────────────────────────────
const results = [];
function verdict(step, name, ok, detail = "") {
  results.push({ step, name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"} · step ${step} · ${name}${detail ? ` — ${detail}` : ""}`);
}
const shot = async (page, name) => {
  const p = join(OUT, `${WIDTH}-${name}.png`);
  await page.screenshot({ path: p, fullPage: true });
  console.log(`  screenshot ${p}`);
};

function csvLine(cells) {
  return cells.map((c) => (/[",\n]/.test(c) ? `"${c.replace(/"/g, '""')}"` : c)).join(",");
}
function deviceFile(name, rows) {
  const lines = [csvLine(DEVICE_HEADER)];
  for (const row of rows) lines.push(csvLine(DEVICE_HEADER.map((h) => row[h] ?? "")));
  const p = join(FILES, `${WIDTH}-${name}.csv`);
  writeFileSync(p, lines.join("\n") + "\n");
  return p;
}
function parseCsv(text) {
  const rows = [];
  let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') q = false;
      else cell += ch;
    } else if (ch === '"') q = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); rows.push(row); row = []; cell = "";
    } else cell += ch;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows.filter((r) => r.some((c) => c !== ""));
}

// ── Driving the five-stage runner ─────────────────────────────────────────
async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.keyboard.press("Enter");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}
async function openImport(page, target) {
  await page.goto(`${BASE}/${TENANT}/assets/import?target=${target}`, { waitUntil: "networkidle" });
}
async function settle(page, ms = 800) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(ms);
}
async function upload(page, file, mode = "insert") {
  await page.locator('input[type="file"]').setInputFiles(file);
  await settle(page, 1500);
  if (mode === "upsert") await page.getByText("Insert & update", { exact: true }).first().click();
  await settle(page);
}
const main = (page) => page.locator("main").innerText();
async function next(page, label) {
  await page.getByRole("button", { name: label }).last().click();
  await settle(page, 1200);
}
async function toStage(page, n) {
  const labels = { 2: /^Transform/, 3: /^Validate/, 4: /^Load →/ };
  for (let s = 2; s <= n; s++) await next(page, labels[s]);
}
let prefixForProgress = "run";
async function commitAndWait(page, timeoutMs = 20 * 60 * 1000) {
  const t0 = Date.now();
  await page.getByRole("button", { name: /^Commit load/ }).click();
  // The progress panel is `[data-workflow="progress"]` (importProgress.tsx) —
  // matched on the element, never on words: stage 4's approval copy always
  // contains a "%", which made the first draft of this check pass on nothing.
  let sawProgress = false, lastText = "";
  const states = new Set();
  const panel = page.locator('[data-workflow="progress"]');
  while (Date.now() - t0 < timeoutMs) {
    await page.waitForTimeout(250);
    if (await panel.count()) {
      const state = await panel.first().getAttribute("data-progress-state");
      const pct = await page.locator('[data-workflow="progress-pct"]').first().innerText().catch(() => "");
      const key = `${state} ${pct}`.trim();
      if (!states.has(key)) console.log(`  progress panel: ${key}`);
      states.add(key);
      if (!sawProgress) await shot(page, `${prefixForProgress}-progress`);
      sawProgress = true;
    }
    lastText = await main(page);
    if (/STAGE 5 OF 5/.test(lastText)) break;
  }
  return { seconds: (Date.now() - t0) / 1000, sawProgress, states: [...states], text: lastText };
}
async function downloads(page, prefix) {
  const saved = {};
  const buttons = page.locator("main").getByRole("button", { name: /download/i });
  const links = page.locator("main a", { hasText: /download/i });
  const all = [...(await buttons.all()), ...(await links.all())];
  for (const el of all) {
    const name = (await el.innerText()).trim();
    try {
      const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 15000 }), el.click()]);
      const p = join(FILES, `${WIDTH}-${prefix}-${dl.suggestedFilename()}`);
      await dl.saveAs(p);
      saved[name] = p;
      console.log(`  download "${name}" → ${p}`);
    } catch (e) {
      console.log(`  download "${name}" gave no file (${e.message.split("\n")[0]})`);
    }
  }
  return saved;
}
async function api(page, path) {
  return page.evaluate(async (p) => {
    const r = await fetch(p, { credentials: "include" });
    return { status: r.status, body: await r.text() };
  }, path);
}

// ── Steps ──────────────────────────────────────────────────────────────────
async function step1(page) {
  for (const target of Object.keys(PLAN)) {
    await openImport(page, target);
    await shot(page, `step1-${target}-stage1`);
    const [dl] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Download a sample CSV" }).click(),
    ]);
    const p = join(FILES, `${WIDTH}-${target}-${dl.suggestedFilename()}`);
    await dl.saveAs(p);
    const header = parseCsv(readFileSync(p, "utf8"))[0];
    const want = PLAN[target].flatMap(([, cols]) => cols);
    const ok = header.length === COUNT[target] && JSON.stringify(header) === JSON.stringify(want);
    verdict(1, `${target} sample header = plan's ${COUNT[target]} columns in order`, ok,
      ok ? `${header.length} columns` : `got ${JSON.stringify(header)}`);
  }
}

async function readGroups(page) {
  return page.locator("main select").first().evaluate((sel) =>
    [...sel.querySelectorAll("optgroup")].map((g) => [g.label, [...g.querySelectorAll("option")].map((o) => o.textContent.trim())]));
}
async function step7(page) {
  for (const target of Object.keys(PLAN)) {
    await openImport(page, target);
    const sample = join(FILES, `${WIDTH}-${target}-${target}_sample.csv`);
    await upload(page, sample);
    await toStage(page, 2);
    const groups = await readGroups(page);
    const ok = JSON.stringify(groups) === JSON.stringify(PLAN[target]);
    verdict(7, `${target} stage-2 picker headings = the six plan groups`, ok,
      ok ? groups.map(([g]) => g).join(" · ") : `got ${JSON.stringify(groups)}`);
    const ignores = await page.locator("main select").first().evaluate((sel) =>
      [...sel.options].filter((o) => o.textContent.trim() === "— ignore —").length);
    verdict(7, `${target} picker offers "— ignore —" once (DEF-AST-8361)`, ignores === 1, `${ignores}`);
    await shot(page, `step7-${target}-stage2`);
    // A native <select> never paints its open list in a headless screenshot,
    // so the first picker is drawn as a listbox for the picture only.
    await page.locator("main select").first().evaluate((sel) => { sel.size = 30; sel.style.height = "auto"; });
    await page.locator("main select").first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: join(OUT, `${WIDTH}-step7-${target}-picker-open.png`) });
    console.log(`  screenshot ${join(OUT, `${WIDTH}-step7-${target}-picker-open.png`)}`);
  }
}

const cart = (n, extra = {}) => ({ "Device type": "container_cart", "External reference": `J71-${TAG}-CART-${n}`, Unit: UNIT, Service: "trash", Size: "CART-64", ...extra });
const fire = (ref, size) => ({ "Device type": "fire_line", "External reference": `J71-${TAG}-${ref}`, Unit: UNIT, Service: "fire", Size: size });

async function step2(page) {
  const file = deviceFile("step2-devices", [cart(1), cart(2), fire("FL6-1", "FL-6"), fire("FL2-1", "FL-2"), fire("FL2-2", "FL-2")]);
  await openImport(page, "assets_devices");
  await upload(page, file, "insert");
  await shot(page, "step2-stage1");
  await toStage(page, 3);
  await shot(page, "step2-stage3");
  const v = await main(page);
  verdict(2, "stage 3: 5 will load, 0 blocked", /WILL LOAD\s*5/.test(v) && /BLOCKED[^\n]*\n\s*0/.test(v));
  await toStage(page, 4);
  await shot(page, "step2-stage4-dryrun");
  const r = await commitAndWait(page);
  await shot(page, "step2-stage5-result");
  console.log(r.text.slice(0, 2500));
  verdict(2, "receipt does not claim the devices are wired to no services (DEF-AST-8360)",
    !/Wired to no services|took no services from the unit/i.test(r.text));
  const files = await downloads(page, "step2");
  const resultFile = Object.values(files).find((f) => /result|receipt|loaded/i.test(f)) ?? Object.values(files)[0];
  if (resultFile) {
    const rows = parseCsv(readFileSync(resultFile, "utf8"));
    console.log(`  result file ${resultFile}: ${rows.length - 1} rows; header ${JSON.stringify(rows[0])}`);
    verdict(2, "result file lists the 5 loaded devices", rows.length - 1 >= 5, `${rows.length - 1} rows`);
  } else verdict(2, "result file downloadable", false, "no download on the result screen");
  const unitId = process.env.UNIT_ID ?? (WIDTH === 1440 ? process.env.UNIT_A_ID : process.env.UNIT_B_ID);
  if (unitId) {
    const c = await unitCount(page, unitId, "step2");
    const trash = (c.assetsText.match(/\tTrash\tTrash 64-gallon cart/g) ?? []).length;
    const fl = (c.assetsText.match(/\tFire\tFire line/g) ?? []).length;
    verdict(2, "unit's Assets tab shows 2 carts on Trash and 3 lines on Fire", trash === 2 && fl === 3, `trash ${trash} · fire ${fl}`);
  }
  return r;
}

async function unitCount(page, unitId, label) {
  await page.goto(`${BASE}/${TENANT}/premises/units/${unitId}?tab=assets`, { waitUntil: "networkidle" });
  await settle(page, 1500);
  await shot(page, `${label}-unit-assets`);
  const assetsText = await main(page);
  await page.goto(`${BASE}/${TENANT}/premises/units/${unitId}`, { waitUntil: "networkidle" });
  await settle(page, 1500);
  await shot(page, `${label}-unit-overview`);
  const overview = await main(page);
  return { assetsText, overview };
}

async function step3(page) {
  // Same five devices by their external reference, the two carts' Size moved
  // CART-64 → CART-96 (a 💲 column), Insert & update.
  const file = deviceFile("step3-reupload", [cart(1, { Size: "CART-96" }), cart(2, { Size: "CART-96" }), fire("FL6-1", "FL-6"), fire("FL2-1", "FL-2"), fire("FL2-2", "FL-2")]);
  await openImport(page, "assets_devices");
  await upload(page, file, "upsert");
  await shot(page, "step3-stage1-upsert");
  await toStage(page, 3);
  await shot(page, "step3-stage3");
  await toStage(page, 4);
  await shot(page, "step3-stage4-dryrun");
  const d = await main(page);
  verdict(3, "dry run: 5 existing records updated, 0 created", /Existing records updated\s*5/.test(d) && /Will create\s*0/.test(d));
  const r = await commitAndWait(page);
  await shot(page, "step3-stage5-result");
  console.log(r.text.slice(0, 2500));
  const files = await downloads(page, "step3");
  let found = false;
  for (const f of Object.values(files)) {
    const text = readFileSync(f, "utf8");
    if (/Size: CART-64 → CART-96/.test(text)) found = true;
    console.log(`  ${f}:\n${text.split("\n").slice(0, 4).join("\n")}`);
  }
  verdict(3, `result file lists "Size: CART-64 → CART-96"`, found);
}

async function step4(page) {
  const file = deviceFile("step4-errors", [
    { "Device type": "container_cart", "External reference": `J71-${TAG}-CART-W`, Unit: "U-00002", Service: "trash" },
    { "Device type": "container_cart", "External reference": `J71-${TAG}-CART-BAD`, Unit: UNIT, "Parent / linked meter": "M-NOPE", Service: "trash", Size: "W-58", "Unit of measure / capacity unit": "furlongs" },
  ]);
  await openImport(page, "assets_devices");
  await upload(page, file, "insert");
  await toStage(page, 3);
  await shot(page, "step4-stage3-errors");
  const v = await main(page);
  console.log(v.slice(v.indexOf("Fix the rejects"), v.indexOf("Fix the rejects") + 2500));
  verdict(4, "Unit W row refused by name (no Trash service)", /has no Trash service/i.test(v));
  const three = [/W-58 is a size for Water, not for Trash/i, /furlongs is not a unit of measure/i, /M-NOPE/];
  const hits = three.map((re) => re.test(v));
  verdict(4, "the bad row shows all three problems on screen", hits.every(Boolean), JSON.stringify(hits));
  // The rejected-rows file is offered on the receipt, so the run is committed
  // (it writes nothing: both rows are rejected) and the file taken from stage 5.
  await toStage(page, 4);
  await shot(page, "step4-stage4-dryrun");
  const approve = page.getByText("I approve this load.", { exact: true });
  if (await approve.count()) await approve.first().click();
  const r = await commitAndWait(page, 120000);
  await shot(page, "step4-stage5-result");
  console.log(r.text.slice(r.text.indexOf("STAGE"), r.text.indexOf("STAGE") + 1500));
  const files = await downloads(page, "step4");
  let fileHits = [false, false, false];
  for (const f of Object.values(files)) {
    const text = readFileSync(f, "utf8");
    fileHits = fileHits.map((h, i) => h || three[i].test(text));
    console.log(`  ${f}:\n${text.slice(0, 1500)}`);
  }
  verdict(4, "the failures file carries all three problems", fileHits.every(Boolean), JSON.stringify(fileHits));
}

async function bulk(page, n, mode, name, sizeOf) {
  const units = ["U-00004", "U-00005", "U-00006", "U-00007", "U-00008"];
  const rows = Array.from({ length: n }, (_, i) => ({
    "Device type": "container_cart", "External reference": `J71-BULK${process.env.RUNTAG ?? ""}-${String(i + 1).padStart(4, "0")}`,
    Unit: units[i % 5], Service: "trash", Size: sizeOf(i),
  }));
  const file = deviceFile(name, rows);
  await openImport(page, "assets_devices");
  await upload(page, file, mode);
  await toStage(page, 3);
  await shot(page, `${name}-stage3`);
  await toStage(page, 4);
  await shot(page, `${name}-stage4-dryrun`);
  prefixForProgress = name;
  const r = await commitAndWait(page);
  await shot(page, `${name}-stage5-result`);
  console.log(r.text.slice(0, 1800));
  return r;
}

const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 900 }, acceptDownloads: true });
const page = await ctx.newPage();
page.setDefaultTimeout(60000);
await signIn(page);
const log = {};
for (const s of STEPS) {
  try {
    if (s === 1) await step1(page);
    if (s === 2) log.step2 = await step2(page);
    if (s === 3) await step3(page);
    if (s === 4) await step4(page);
    if (s === 5) {
      const r = await bulk(page, 250, "insert", "step5-250", () => "CART-64");
      log.step5 = r;
      verdict(5, "250-row load ran with progress shown", r.sawProgress, `${r.seconds.toFixed(1)}s`);
      verdict(5, "result says 250 loaded", /250/.test(r.text));
    }
    if (s === 6) {
      // 250 created at step 5 + 250 more = 500 rows, Insert & update: 250 updates + 250 creates.
      const r = await bulk(page, 500, "upsert", "step6-500", (i) => (i < 250 ? "CART-96" : "CART-64"));
      verdict(6, "500-row insert-and-update completes", /STAGE 5 OF 5/.test(r.text), `${r.seconds.toFixed(1)}s`);
    }
    if (s === 7) await step7(page);
    if (s === 8) {
      const unitId = WIDTH === 1440 ? process.env.UNIT_A_ID : process.env.UNIT_B_ID;
      const c = await unitCount(page, unitId, "step2");
      console.log(c.assetsText.slice(0, 3000));
      console.log("---- overview ----");
      console.log(c.overview.slice(0, 3000));
    }
  } catch (e) {
    verdict(s, "step crashed", false, e.message.split("\n")[0]);
    await shot(page, `step${s}-crash`);
  }
}
await browser.close();
writeFileSync(join(FILES, `${WIDTH}-results-${STEPS.join("")}.json`), JSON.stringify(results, null, 2));
