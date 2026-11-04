// CR-168-BRC10 round 4, lane TEMPLATES — the AFTER walk at 1440 wide: images
// 43–55 photographed in their states, and the brief's proof end to end on
// PostgreSQL —
//   build "Meter exchange — single phase" through all EIGHT steps, with an
//   instruction on a task and a help video link (and a held document), EDIT
//   every kind of row in place, publish v1, edit and publish v2 with a change
//   note, then raise a job and show it carries v2 and its checklist shows the
//   instruction.
//
//   BASE=http://127.0.0.1:5591 OUT=08-qa/work-2026-10-04/after \
//   ASSET_ID=<an electric meter's uuid> node 10-scripts/cr168_templates_after_walk.mjs
//
// Preconditions: migrate + seed_demo + load_sample_data --tenant brazosbend on
// PostgreSQL, the API with this branch, the SPA served by 07-frontend/server.mjs.
// WRITES IT MAKES: one template (two versions), one help document, one job.
// Run once per fresh seed — a second run meets a template of the same name.
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5591";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/after";
const ASSET_ID = process.env.ASSET_ID ?? "";
const NAME = "Meter exchange — single phase";
const VIDEO = "https://www.youtube.com/watch?v=Qx4dF2mT9sE";
const INSTRUCTION = "Isolate at the main before touching the meter.";
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

// A real (tiny) PDF for the held help document.
const PDF = join(process.env.PDF_DIR ?? "/tmp", "meter-exchange-procedure.pdf");
writeFileSync(
  PDF,
  "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n",
);

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
  // The frame scrolls inside <main>, so a "full page" shot is only the
  // viewport. Grow the viewport to the content, from the top, then restore.
  const tall = await page.evaluate(() => {
    const m = document.querySelector("main");
    m?.scrollTo(0, 0);
    window.scrollTo(0, 0);
    let h = document.documentElement.scrollHeight;
    for (const el of document.querySelectorAll("*")) {
      if (el.scrollHeight > el.clientHeight + 4 && getComputedStyle(el).overflowY !== "visible") h = Math.max(h, el.scrollHeight + 120);
    }
    return Math.min(h, 6000);
  });
  await page.setViewportSize({ width: 1440, height: Math.max(1100, tall) });
  await settle(500);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1100 });
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
const box = (name) => page.getByRole("textbox", { name, exact: true });
const pick = (name) => page.getByRole("combobox", { name, exact: true });
const press = (name) => page.getByRole("button", { name, exact: true }).first().click();
async function next() {
  await press("Continue");
  await settle(900);
}
async function selectByText(name, text) {
  const value = await pick(name).evaluate((el, t) => {
    const option = [...el.options].find((o) => o.textContent.includes(t) && o.value !== "");
    return option ? option.value : [...el.options].find((o) => o.value !== "")?.value ?? "";
  }, text);
  await pick(name).selectOption(value);
  return value;
}

// ── sign in ──────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── 43 · the list ────────────────────────────────────────────────────────
await go("/work/templates");
const t43 = await main();
check("43 · a Done to column, rows read Premises", /done to/i.test(t43) && t43.includes("Premises"));
await shot("43-templates-templates", "Templates · list with Done to");

// ── 48 · Details ─────────────────────────────────────────────────────────
await go("/work/templates/new?step=1");
await press("Continue");
await settle(600);
check("48 · step 1 refuses until it is named, serviced and scoped", (await main()).includes("Name it, pick a service, say what it is done to."));
await box("Name").fill(NAME);
await page.locator("#wtb_service").selectOption("electric");
await page.locator("#wtb_scope").selectOption("per_asset");
const groups = await page.locator("#wtb_type optgroup").count();
check("48 · job type is the two-level picker (optgroups)", groups > 0, `${groups} headings`);
const typeValue = await page.locator("#wtb_type").evaluate((el) => {
  const o = [...el.querySelectorAll("option")].find((x) => /meter/i.test(x.textContent ?? "") && x.value !== "");
  return o ? o.value : "";
});
if (typeValue) await page.locator("#wtb_type").selectOption(typeValue);
await shot("48-templates-builder-details", "Builder · Details (Done to asked, two-level job type)");
await next();

// ── 49 · Safety — add two, then correct the first in place ───────────────
await box("Add a safety check…").fill("Isolate at the mian breaker");
await press("+ Add");
await box("Add a safety check…").fill("Lock and tag the isolation point");
await press("+ Add");
await box("Check 1").fill("Isolate at the main breaker");
check("49 · a safety check edits in place", (await box("Check 1").inputValue()) === "Isolate at the main breaker");
await shot("49-templates-builder-safety", "Builder · Safety (row 1 corrected in place)");
await next();

// ── 50 · Tasks — add three, edit one, write an instruction ───────────────
for (const [title, minutes] of [["Photograph the old meter", "5"], ["Fit the meter", "20"], ["Record the reading", "5"]]) {
  await box("Add a task…").fill(title);
  await page.locator("#wtb_task_minutes").fill(minutes);
  await press("+ Add");
}
await box("Task 2").fill("Fit the new meter");
await box("Minutes 2").fill("25");
await box("Instruction 2").fill(INSTRUCTION);
const t50 = await main();
check("50 · total re-adds after an in-place minutes edit (35 min)", t50.includes("35 min total") || t50.includes("35 MIN TOTAL") || /35 min/i.test(t50));
await shot("50-templates-builder-tasks", "Builder · Tasks (task 2 edited, instruction under it)");
await next();

// ── 51 · Materials — add two, change a part and a quantity in place ──────
await selectByText("Add a part…", "CPL-58B");
await press("+ Add");
await selectByText("Add a part…", "GSK");
await press("+ Add");
await box("Quantity 2").fill("2");
const firstPart = await pick("Part 1").inputValue();
await selectByText("Part 1", "CPL-58B");
check("51 · a material's quantity edits in place", (await box("Quantity 2").inputValue()) === "2", `part 1 ${firstPart ? "kept" : "?"}`);
await shot("51-templates-builder-materials", "Builder · Materials (quantity edited in place)");
await next();

// ── 52 · Readings — add one, correct its range in place ──────────────────
await box("Prompt…").fill("Final register reading");
await page.locator("#wtb_reading_unit").fill("kWh");
await page.locator("#wtb_reading_min").fill("0");
await page.locator("#wtb_reading_max").fill("99999");
await press("+ Add");
await box("Max 1").fill("999999");
await box("Unit 1").fill("");
check("52 · an emptied unit says so on the cell", (await main()).includes("Needs a unit."));
await box("Unit 1").fill("kWh");
await shot("52-templates-builder-readings", "Builder · Readings (max corrected in place)");
await next();

// ── 53 · Help — a held document, a phone, a video link; edit in place ────
await box("What it is").fill("Meter exchange procedure");
await page.getByLabel("Choose a file", { exact: true }).setInputFiles(PDF);
await settle(2500);
check("53 · the document is held (its file name shows)", (await main()).includes("meter-exchange-procedure.pdf"));
await pick("Kind").selectOption("phone");
await box("What it is").fill("Metering supervisr");
await box("Where to find it").fill("(512) 555-0100");
await press("+ Add");
await pick("Kind").selectOption("link");
await box("What it is").fill("Fitting a single-phase meter");
await box("Where to find it").fill("http://www.youtube.com/watch?v=Qx4dF2mT9sE");
check("53 · an http address cannot be added", await page.getByRole("button", { name: "+ Add", exact: true }).isDisabled());
await box("Where to find it").fill(VIDEO);
await press("+ Add");
await box("What it is 2").fill("Metering supervisor");
const t53 = await main();
check("53 · the video is badged", t53.includes("▶ Video · needs a signal"));
check("53 · the sentence says links need a signal", t53.includes("Documents work with no signal; links need one."));
await shot("53-templates-builder-help", "Builder · Help (document held, phone corrected, video link)");
await next();

// ── 54 · Signature (Keep) ────────────────────────────────────────────────
await shot("54-templates-builder-signature", "Builder · Signature");
await next();

// ── 55 · Review — every row, and Publish v1 ──────────────────────────────
const t55 = await main();
for (const s of ["Isolate at the main breaker", "Fit the new meter", INSTRUCTION, "CPL-58B", "Final register reading", "meter-exchange-procedure.pdf", "Metering supervisor", "Fitting a single-phase meter", "Asset"]) {
  check(`55 · review shows "${s}"`, t55.includes(s));
}
check("55 · a first publish asks no change note", (await page.getByRole("textbox", { name: "What changed" }).count()) === 0);
await shot("55-templates-builder-review", "Builder · Review (the template summary)");
await page.getByRole("button", { name: /Publish template/ }).click();
await page.waitForURL(/\/work\/templates\/[0-9a-f-]{36}$/, { timeout: 30000 });
await settle(2000);
const templateId = page.url().split("/").pop();
let detail = (await api(`work/templates/${templateId}`)).body;
check("published v1 with scope per_asset", detail.version === 1 && detail.scope === "per_asset", `v${detail.version} ${detail.scope}`);
check("the instruction was stored", detail.bundle.tasks[1].instruction === INSTRUCTION);
const link = detail.bundle.help.find((h) => h.kind === "link");
const doc = detail.bundle.help.find((h) => h.kind === "document");
check("the link was stored as a link", link?.link === VIDEO);
check("the document is held (a file, a same-origin url)", Boolean(doc?.file?.name) && Boolean(doc?.url));

// ── 44 · Overview ────────────────────────────────────────────────────────
const t44 = await main();
check("44 · Overview shows every row", [INSTRUCTION, "CPL-58B", "Final register reading", "Metering supervisor"].every((s) => t44.includes(s)));
await shot("44-templates-template-overview", "Template · Overview (the same summary)");

// ── v2: open Tasks from Overview's ✎ Edit, change the instruction, publish ─
await page.getByRole("link", { name: /^Edit Tasks/ }).click();
await settle(2500);
check("✎ Edit on Overview opens the builder at Tasks", page.url().includes("step=3"));
await box("Instruction 3").fill("Read the register twice.");
for (let i = 0; i < 5; i += 1) await next();
await page.getByRole("textbox", { name: "What changed" }).fill("Instruction on reading the register");
await shot("55b-templates-builder-review-change-note", "Builder · Review on a published template (What changed)");
await page.getByRole("button", { name: /Publish template/ }).click();
await page.waitForURL(/\/work\/templates\/[0-9a-f-]{36}$/, { timeout: 30000 });
await settle(2000);
detail = (await api(`work/templates/${templateId}`)).body;
check("published v2", detail.version === 2, `v${detail.version}`);

// ── 46 · Versions ────────────────────────────────────────────────────────
await go(`/work/templates/${templateId}?tab=versions`);
const t46 = await main();
check("46 · v2's What changed is the note", t46.includes("Instruction on reading the register"));
await shot("46-templates-template-versions", "Template · Versions (v2 with its change note)");

// ── a job raised after publishing gets v2 and shows the instruction ──────
const raised = await api("work-orders", "POST", { template_id: templateId, asset_id: ASSET_ID });
console.log("RAISE", raised.status, JSON.stringify(raised.body).slice(0, 300));
const orderId = raised.body?.id;
if (orderId) {
  const checklist = (await api(`work-orders/${orderId}/checklist`)).body;
  check("the job carries v2", checklist.template_version === 2, `template_version ${checklist.template_version}`);
  check("the job's checklist carries the instruction", checklist.tasks?.[1]?.instruction === INSTRUCTION);
  await go(`/work/orders/${orderId}?tab=checklist`);
  check("the checklist shows the instruction under its task", (await main()).includes(INSTRUCTION));
  await shot("50c-order-checklist-instruction", "One order · Checklist (the instruction under its task)");
} else {
  check("a job was raised", false);
}

// ── 45 · Usage · 47 · Audit ──────────────────────────────────────────────
await go(`/work/templates/${templateId}?tab=usage`);
const t45 = await main();
check("45 · usage in words", /1 order raised across 2 versions/.test(t45), (t45.match(/\d+ orders? raised across \d+ versions?/) ?? [""])[0]);
await shot("45-templates-template-usage", "Template · Usage");
await go(`/work/templates/${templateId}?tab=audit`);
const t47 = await main();
check("47 · the history is read and the hold sentence is gone", t47.includes("Published v2") && !t47.includes("opens with the next release"));
check("47 · no act code on screen", !/replaced|help_document_stored|asset-types/.test(t47));
await shot("47-templates-template-audit", "Template · Audit");

await browser.close();
const failedChecks = checks.filter(([, ok]) => !ok);
console.log(`\n${checks.length - failedChecks.length} of ${checks.length} checks passed`);
process.exit(failedChecks.length === 0 ? 0 : 1);
