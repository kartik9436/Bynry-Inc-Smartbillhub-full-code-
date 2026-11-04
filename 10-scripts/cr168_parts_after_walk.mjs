// CR-168-BRC10 round 4, lane PARTS — the AFTER walk at 1440 wide, the states of
// images 35–42 plus the proofs the brief asks for: a duplicate refused by name,
// an edit, a retire, the filters, the Issue log, and the import's five stages
// with the dry run writing nothing and the load keeping the category.
//
//   BASE=http://127.0.0.1:5551 OUT=08-qa/work-2026-10-04/after node 10-scripts/cr168_parts_after_walk.mjs
//
// Preconditions: migrate + seed_demo + load_sample_data --tenant brazosbend on
// PostgreSQL. WRITES IT MAKES: MTR-W34, GSKT-STD and SEAL-01 imported (the
// round-1 file, 08-qa/work-2026-10-04/parts-import-walk.csv); VLV-GT1 added,
// its cost edited 41.50 → 43.75, then retired; one issue of 2 × SEAL-01 against
// WO-0041 recorded through POST /work/parts/issues (the demo holds none, and an
// Issue log with no row photographs only its empty state). Run it once per
// fresh seed — a second run meets its own leftovers (MTR-W34 already on file).
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5551";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/after";
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
async function api(path) {
  return page.evaluate(async ([tenant, p]) => {
    const res = await fetch(`/api/${tenant}/${p}`, { credentials: "include" });
    return res.json();
  }, [TENANT, path]);
}
const partsAll = async () => (await api("work/parts?per=1000")).results ?? [];
const main = () => page.locator("main").innerText();

// ── sign in ──────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── 38–42 · Import parts, the round-1 file ───────────────────────────────
const before = await partsAll();
console.log("PARTS BEFORE IMPORT:", before.length, before.map((p) => p.part_no).join(" "));
await go("/work/parts/import");
await page.locator('input[type="file"]').setInputFiles(
  new URL("../08-qa/work-2026-10-04/parts-import-walk.csv", import.meta.url).pathname,
);
await settle(2000);
check("38 · Insert new only explains parts without numbering", (await main()).includes("Every other row is created.") && !(await main()).includes("Settings → Numbering"));
await shot("38-parts-import-parts-extract", "Import parts · Extract (file chosen)");
await page.getByRole("button", { name: /^Transform/ }).last().click();
await settle(2500);
const t2 = await main();
check("39 · sample values shown (MTR-W34, Meters, 118.00)", ["MTR-W34", "Meters", "118.00"].every((s) => t2.includes(s)));
check("39 · rows forward reads 5, never 0", /Rows forward to validation\s*5/.test(t2), (t2.match(/Rows forward to validation\s*\d+/) ?? [""])[0]);
await shot("39-parts-import-parts-transform", "Import parts · Transform");
await page.getByRole("button", { name: /^Validate/ }).last().click();
await settle(3000);
const t3 = await main();
check("40 · rule reads Every part needs a name.", t3.includes("Every part needs a name.") && !t3.includes("needs a description"));
check("40 · no 'blank in all 5 rows' over Category", !/Category — mapped from category, and blank/.test(t3));
check("40 · reject keys MTR-W58 and TAPE-XL", t3.includes("MTR-W58") && t3.includes("TAPE-XL"));
check("40 · unit fix speaks about parts", t3.includes("Add how it is counted — each, ft, roll.") && !t3.includes("on every premises"));
await shot("40-parts-import-parts-validate", "Import parts · Validate");
await page.getByRole("button", { name: /^Load/ }).last().click();
await settle(3000);
await shot("41-parts-import-parts-load", "Import parts · Load (dry run)");
const afterDry = await partsAll();
check("41 · the dry run wrote nothing", afterDry.length === before.length, `${before.length} → ${afterDry.length}`);
await page.getByText("I approve this load.").click().catch((e) => console.log("approve", String(e).split("\n")[0]));
await settle(800);
await page.getByRole("button", { name: /^Commit load/ }).click();
await settle(5000);
const t5 = await main();
check("42 · fix for the on-file row is the drawn one", t5.includes("Import it as Insert & update. Or take the row out."));
await shot("42-parts-import-parts-result", "Import parts · Result");
const loaded = await partsAll();
const cat = (no) => loaded.find((p) => p.part_no === no)?.category?.name ?? null;
check("42 · MTR-W34 loaded with category Meters", cat("MTR-W34") === "Meters", String(cat("MTR-W34")));
check("42 · GSKT-STD and SEAL-01 loaded as Consumables", cat("GSKT-STD") === "Consumables" && cat("SEAL-01") === "Consumables");
check("42 · three created", loaded.length === before.length + 3, `${before.length} → ${loaded.length}`);

// ── 35 · the register ────────────────────────────────────────────────────
await go("/work/parts");
const t35 = await main();
check("35 · Name column, Issue log live", /\bname\b/i.test(t35) && !/description/i.test(t35) && !t35.includes("Arrives with parts on jobs."));
await shot("35-parts-parts", "Parts · the register, row actions, + Filter");

// ── 37 · Add a part, refused ─────────────────────────────────────────────
await page.getByRole("button", { name: "+ Add part" }).first().click();
await settle(800);
await page.getByRole("button", { name: "Add part ✓" }).click();
await settle(800);
const t37 = await page.locator('[role="dialog"]').innerText();
check("37 · This is required. ×3, Unit cost must be a number.", (t37.match(/This is required\./g) ?? []).length === 3 && t37.includes("Unit cost must be a number."));
check("37 · no library English", !/String must contain|Invalid/.test(t37));
await shot("37-parts-add-a-part-refused", "Add a part — refused");

// ── duplicate, refused by name ───────────────────────────────────────────
const dlg = page.locator('[role="dialog"]');
await dlg.getByLabel(/^Part number/).fill("mtr-w34");
await dlg.getByLabel(/^Name/).fill('Water meter 3/4" positive displacement');
await dlg.getByLabel(/^Category/).selectOption({ label: "Meters" });
await dlg.getByLabel(/^Unit of measure/).fill("each");
await dlg.getByLabel(/^Unit cost/).fill("118.00");
await dlg.getByRole("button", { name: "Add part ✓" }).click();
await settle(1500);
const tdup = await dlg.innerText();
check("duplicate refused naming the part", tdup.includes("MTR-W34 is already in the register."));
await shot("36b-parts-add-a-part-duplicate", "Add a part — duplicate part number refused by name");

// ── 36 · Add a part, filled (a FRESH form — the refusal above stays under
// its field until the next press, which is the kit's FormModal behaviour) ──
await dlg.getByRole("button", { name: "Cancel" }).click();
await settle(600);
await page.getByRole("button", { name: "+ Add part" }).first().click();
await settle(800);
await dlg.getByLabel(/^Part number/).fill("VLV-GT1");
await dlg.getByLabel(/^Unit of measure/).fill("each");
await dlg.getByLabel(/^Name/).fill('Gate valve 1"');
await dlg.getByLabel(/^Category/).selectOption({ label: "Fittings" });
await dlg.getByLabel(/^Unit cost/).fill("41.50");
await shot("36-parts-add-a-part", "Add a part — filled");
await dlg.getByRole("button", { name: "Add part ✓" }).click();
await settle(2000);
check("VLV-GT1 added", (await partsAll()).some((p) => p.part_no === "VLV-GT1"));

// ── edit ─────────────────────────────────────────────────────────────────
await go("/work/parts?q=VLV-GT1");
await page.getByTestId("edit-part-VLV-GT1").click();
await settle(800);
await shot("36c-parts-edit-a-part", "Edit a part — opened from the pencil, filled with the part");
await page.locator('[role="dialog"]').getByLabel(/^Unit cost/).fill("43.75");
await page.locator('[role="dialog"]').getByRole("button", { name: /Save part/ }).click();
await settle(2000);
const edited = (await partsAll()).find((p) => p.part_no === "VLV-GT1");
check("edit saved 43.75", edited?.unit_cost === "43.7500", edited?.unit_cost);

// ── retire ───────────────────────────────────────────────────────────────
await page.getByTestId("retire-part-VLV-GT1").click();
await settle(800);
await shot("35b-parts-retire-confirm", "Retire a part — the danger-tier confirm");
await page.locator('[role="alertdialog"]').getByRole("button", { name: /Retire part/ }).click();
await settle(2000);
const retired = (await partsAll()).find((p) => p.part_no === "VLV-GT1");
check("VLV-GT1 retired", retired?.active === false);

// ── filters ──────────────────────────────────────────────────────────────
await go("/work/parts");
await page.getByText("+ Filter").click();
await page.getByLabel("Inactive").check();
await settle(2000);
const tin = await main();
check("Status · Inactive shows VLV-GT1 only", tin.includes("VLV-GT1") && !tin.includes("MTR-W34"));
await shot("35c-parts-filter-inactive", "Parts — filtered to Inactive");
await page.getByLabel("Inactive").uncheck();
await page.getByLabel("Meters").check();
await settle(2000);
const tm = await main();
check("Category · Meters shows MTR-W34, not SEAL-01", tm.includes("MTR-W34") && !tm.includes("SEAL-01"));
await shot("35d-parts-filter-meters", "Parts — filtered to Meters");

// ── Issue log ────────────────────────────────────────────────────────────
const seal = (await partsAll()).find((p) => p.part_no === "SEAL-01");
const issued = await page.evaluate(async ([tenant, partId]) => {
  const res = await fetch(`/api/${tenant}/work/parts/issues`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ part_id: partId, qty: "-2", order_ref: "WO-0041", purpose: "Meter exchange" }),
  });
  return res.status;
}, [TENANT, seal?.id]);
console.log("ISSUE RECORDED:", issued);
await go("/work/parts");
await page.locator('[data-segment="issues"]').click();
await settle(2000);
const tlog = await main();
check("Issue log lists SEAL-01 against WO-0041, quantity -2 each", tlog.includes("WO-0041") && tlog.includes("-2 each"));
await shot("35e-parts-issue-log", "Parts — the Issue log, released");

console.log(`\n${checks.filter(([, ok]) => ok).length} of ${checks.length} checks passed`);
await browser.close();
process.exit(checks.every(([, ok]) => ok) ? 0 : 1);
